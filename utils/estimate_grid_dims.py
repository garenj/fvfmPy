import numpy as np

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

