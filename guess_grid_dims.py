import subprocess
import sys
import ctypes
import cv2
import numpy as np


def _focus_terminal():
    """Bring the user's terminal window to the front so keyboard input works."""
    platform = sys.platform
    if platform == 'darwin':
        for app in ('Terminal', 'iTerm2', 'iTerm', 'Code'):
            r = subprocess.run(
                ['osascript', '-e',
                 f'tell application "System Events" to (name of processes) contains "{app}"'],
                capture_output=True, text=True
            )
            if 'true' in r.stdout:
                subprocess.run(
                    ['osascript', '-e', f'tell application "{app}" to activate'],
                    capture_output=True
                )
                return
    elif platform == 'win32':
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass  # focus is best-effort; terminal still usable if this fails


def _focus_python():
    """Return focus to the Python/OpenCV windows after a terminal prompt."""
    platform = sys.platform
    if platform == 'darwin':
        subprocess.run(
            ['osascript', '-e',
             'tell application "System Events"\n'
             '  set ps to (every process whose name starts with "python" or name starts with "Python")\n'
             '  if (count of ps) > 0 then set frontmost of item 1 of ps to true\n'
             'end tell'],
            capture_output=True
        )
    # On Windows, OpenCV windows regain focus automatically when clicked;
    # no explicit refocus call is needed.


def _pca_rotate(points):
    pts = points - points.mean(axis=0)
    _, _, Vt = np.linalg.svd(pts, full_matrices=False)
    return pts @ Vt.T


def _count_bands(coords_1d, max_bands=30):
    """
    Count distinct bands in 1D centroid coordinates using natural-break gap analysis.

    Sorts all consecutive gaps between centroids, then finds the largest jump
    in the sorted gap distribution (Jenks natural break). This jump separates
    the many small within-band gaps from the few large between-band gaps.
    Band count = 1 + number of gaps above that threshold.

    This replaces the residual-minimisation approach, which fails when
    within-cluster noise is large relative to band spacing — doubling n halves
    the residual by splitting each cluster into two sub-clusters, and the
    empty-band check cannot catch it because noise populates the extras.
    """
    coords = np.sort(coords_1d.astype(float))
    if len(coords) < 2:
        return 1

    gaps = np.diff(coords)
    sorted_gaps = np.sort(gaps)

    if len(sorted_gaps) < 2:
        return 1 if gaps[0] == 0 else 2

    # Largest jump in sorted gaps = natural break between within- and between-band gaps
    meta_gaps = np.diff(sorted_gaps)
    break_idx = int(np.argmax(meta_gaps))
    threshold = (sorted_gaps[break_idx] + sorted_gaps[break_idx + 1]) / 2

    n_bands = 1 + int(np.sum(gaps > threshold))
    return min(n_bands, max_bands)


# How many cells may differ from the number of detected centroids before we
# treat the gap-analysis result as invalid and search for a better candidate.
_CELL_TOLERANCE = 4


def _fallback_grid_search(N, aspect, n_rows_hint, n_cols_hint):
    """
    Enumerate (r, c) pairs where r <= c and |r*c - N| <= _CELL_TOLERANCE.
    Score each by how closely c/r matches the observed PCA span ratio (aspect),
    with a small tiebreaker term that prefers candidates near the gap-analysis
    hints.  Returns (r, c) with the lowest score.
    """
    best = None
    best_score = float('inf')
    for r in range(1, N + 1):
        if r * r > N + _CELL_TOLERANCE:
            break
        for c in range(r, N + _CELL_TOLERANCE + 1):
            if r * c > N + _CELL_TOLERANCE:
                break
            if abs(r * c - N) <= _CELL_TOLERANCE:
                aspect_err = abs(c / r - aspect)
                gap_err = ((r - n_rows_hint) ** 2 + (c - n_cols_hint) ** 2) ** 0.5
                score = aspect_err + 0.01 * gap_err
                if score < best_score:
                    best_score = score
                    best = (r, c)
    return best


def estimate_grid_dims(centroids):
    """
    Estimate grid dimensions from detected centroid positions.

    Step 1 — gap analysis: count bands independently on each PCA axis.
    Step 2 — cell-count sanity check: if |n_rows * n_cols - N| > _CELL_TOLERANCE
             the gap analysis result is implausible (e.g. 2×10=20 for 47 discs).
             In that case, enumerate all (r,c) where r*c ≈ N and score by
             how well the aspect ratio c/r matches the observed PCA span ratio.

    PCA rotation aligns x with the direction of greatest variance (columns
    for wider-than-tall grids), so rotated[:, 0] → n_cols and
    rotated[:, 1] → n_rows.

    Returns (est_rows, est_cols).
    """
    pts = np.array(centroids, dtype=float)
    N = len(pts)
    if N < 2:
        return 1, 1

    rotated = _pca_rotate(pts)

    x_span = max(rotated[:, 0].max() - rotated[:, 0].min(), 1e-6)
    y_span = max(rotated[:, 1].max() - rotated[:, 1].min(), 1e-6)
    aspect = x_span / y_span

    n_cols = _count_bands(rotated[:, 0], max_bands=30)
    n_rows = _count_bands(rotated[:, 1], max_bands=20)

    # Ensure n_rows <= n_cols (PCA may align the longer axis as y)
    if n_rows > n_cols:
        n_rows, n_cols = n_cols, n_rows

    # If the estimated cell count is far from N, fall back to aspect-ratio search
    if abs(n_rows * n_cols - N) > _CELL_TOLERANCE:
        candidate = _fallback_grid_search(N, aspect, n_rows, n_cols)
        if candidate is not None:
            old = f"{n_rows}x{n_cols}={n_rows*n_cols}"
            n_rows, n_cols = candidate
            print(f"  [grid estimate] gap analysis gave {old} cells (not {N}); "
                  f"corrected to {n_rows}x{n_cols} by cell-count constraint")

    print(f"  [grid estimate] {N} centroids, span ratio {aspect:.2f} -> "
          f"{n_rows} rows x {n_cols} cols ({n_rows * n_cols} cells)")
    return n_rows, n_cols


def confirm_grid_dims(img, centroids, est_rows, est_cols,
                      default_rows=None, default_cols=None):
    """
    Decide the grid dimensions to use, with three behaviours:

    1. Defaults set AND detected matches defaults (within ±1): return defaults
       silently — no window, no terminal prompt.
    2. Defaults set BUT detected differs: pause and prompt, showing both values.
       Enter uses the default; typing ROWS,COLS overrides.
    3. No defaults: always prompt (original behaviour).

    Returns (confirmed_rows, confirmed_cols).
    """
    n = len(centroids)
    defaults_set = default_rows is not None and default_cols is not None

    # Case 1: auto pass-through when estimate matches default (exact or ±1)
    if defaults_set:
        if abs(est_rows - default_rows) <= 1 and abs(est_cols - default_cols) <= 1:
            if est_rows == default_rows and est_cols == default_cols:
                print(f"  {n} discs — grid {default_rows}x{default_cols} (auto-confirmed)")
            else:
                print(f"  {n} discs — using default {default_rows}x{default_cols} "
                      f"(detected {est_rows}x{est_cols}; type ROWS,COLS in terminal if wrong)")
            return default_rows, default_cols

    # Cases 2 & 3: show window and prompt
    disp = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    for cx, cy in centroids:
        cv2.circle(disp, (int(cx), int(cy)), 6, (0, 255, 0), 2)

    line1 = f"{n} discs  |  detected: {est_rows} rows x {est_cols} cols"
    if defaults_set:
        line1 += f"  |  default: {default_rows} rows x {default_cols} cols"
    cv2.putText(disp, line1,
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(disp, "Check terminal to confirm or adjust",
                (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

    WINDOW = "Grid dimension check — see terminal"
    h, w = disp.shape[:2]
    scale = min(1.0, 1200 / max(h, w))
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, int(w * scale), int(h * scale))
    cv2.moveWindow(WINDOW, 100, 50)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    cv2.imshow(WINDOW, disp)
    cv2.waitKey(1)

    print(f"\n  {n} discs detected — estimated: {est_rows}x{est_cols}", end="")
    if defaults_set:
        print(f"  (default: {default_rows}x{default_cols})")
        prompt = f"  Press Enter to use default ({default_rows},{default_cols}), or type ROWS,COLS to override: "
        fallback_rows, fallback_cols = default_rows, default_cols
    else:
        print()
        prompt = "  Press Enter to accept estimate, or type ROWS,COLS to override: "
        fallback_rows, fallback_cols = est_rows, est_cols

    # Drop topmost so the terminal can come forward, then restore after.
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 0)
    _focus_terminal()
    response = input(prompt).strip()
    _focus_python()
    cv2.destroyWindow(WINDOW)

    if response:
        try:
            r, c = response.split(',')
            return int(r.strip()), int(c.strip())
        except (ValueError, IndexError):
            print(f"  Could not parse '{response}', using fallback.")

    return fallback_rows, fallback_cols
