"""
Extracts mean Fo and Fm values for each leaf disc ROI and computes Fv/Fm.

Pipeline role: called after the ROI picker has confirmed centroid positions.
Reads both frames from the original TIFF, applies the same perspective
correction and crop used on the Fo preview image, then averages pixel
intensities within a square window (roi_size × roi_size) centred on each
confirmed centroid. Writes a visualisation JPG showing ROI positions and
grid labels.
"""
import os
import cv2
import numpy as np

def band_centers(values, n_bands):
    """
    Split sorted values into n_bands groups by largest gaps and return each group's mean.

    Uses gap-based splitting (unlike the equal-count version in get_candidate_rois)
    so that genuinely clustered row/column positions are kept together even when
    the number of points per band is unequal.
    """
    vals = np.sort(values)
    if n_bands == 1:
        return np.array([vals.mean()])
    gaps = np.diff(vals)
    split_indices = np.sort(np.argsort(gaps)[-(n_bands - 1):] + 1)
    splits = np.split(vals, split_indices)
    return np.array([s.mean() for s in splits if len(s) > 0])

def get_Fo_Fm(fn, rois, roi_size, expected_rows, expected_cols, warp_M=None, warp_size=None, crop_rect=None, output_dir=None):
    """
    Compute mean Fo, mean Fm, and Fv/Fm for every confirmed ROI centroid.

    Parameters
    ----------
    fn          : filename of the multi-frame TIFF (relative to cwd)
    rois        : ROI list returned by ROIPicker.run_gui() — uses rois[0]['pts']
    roi_size    : side length of the square averaging window in pixels
    expected_rows, expected_cols : grid dimensions for row/col assignment
    warp_M, warp_size : affine matrix and canvas size from perspective_corrector
                        (None if no rotation was applied)
    crop_rect   : (x1, y1, x2, y2) from image_cropper (None if not cropped)
    output_dir  : directory to write the visualisation JPG (defaults to cwd)

    Returns
    -------
    List of dicts with keys: filename, row, col, leaf_number,
    centroid_x, centroid_y, mean_Fo, mean_Fm, FvFm.
    """
    images = []
    coords = rois[0]["pts"]
    #print(type(coords))
    coords = np.array(coords)

    x_all = coords[:, 0]
    y_all = coords[:, 1]

    row_centers = band_centers(y_all, expected_rows)
    col_centers = band_centers(x_all, expected_cols)

    # --- Assign each region to nearest grid cell ---
    assignments = []
    first_row_y = []
    last_row_y = []
    first_col_x = []
    last_col_x = []

    for i in range(len(x_all)):
        x = coords[i][0]
        y = coords[i][1]
        r = np.argmin(np.abs(row_centers - y))
        c = np.argmin(np.abs(col_centers - x))

        if r == 0:
            first_row_y.append(y)
        if r == (expected_rows - 1):
            last_row_y.append(y)

        if c == 0:
            first_col_x.append(x)
        if c == (expected_cols - 1):
            last_col_x.append(x)

        assignments.append({
            "x": x,
            "y": y,
            "r": r,
            "c": c,
            "i": i
        })

    # Check if row 0 is on top or bottom, switch if so.
    # Guard against edge rows being completely empty (all discs missing).
    if first_row_y and last_row_y and np.mean(first_row_y) > np.mean(last_row_y):
        ass_new = []
        for cur in assignments:
            cur["r"] = expected_rows-cur["r"]-1
            ass_new.append(cur)
        assignments = ass_new

    
    # Check if col 0 is on left or right, switch if so.
    if first_col_x and last_col_x and np.mean(first_col_x) > np.mean(last_col_x):
        ass_new = []
        for cur in assignments:
            cur["c"] = expected_cols-cur["c"]-1
            ass_new.append(cur)
        assignments = ass_new

    


    #print(type(assignments))
    # --- Resolve collisions & gaps ---
    """
    grid_regions = {}

    median_area = np.median(areas)

    for r in range(expected_rows):
        for c in range(expected_cols):

            cell = (r, c)

            if cell in assignments:
                idxs = assignments[cell]

                # Over-segmentation → choose best region
                if len(idxs) > 1:
                    idx = min(
                        idxs,
                        key=lambda i: abs(areas[i] - median_area)
                    )
                else:
                    idx = idxs[0]

                grid_regions[cell] = idx


    

    results = []
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    half = ROI_SIZE // 2

    for (row, col), idx in grid_regions.items():
        r = regions[idx]
        cy, cx = r.centroid

        x1, x2 = int(cx - half), int(cx + half)
        y1, y2 = int(cy - half), int(cy + half)

        x1, x2 = max(0, x1), min(img.shape[1], x2)
        y1, y2 = max(0, y1), min(img.shape[0], y2)

        roi = img[y1:y2, x1:x2]
        mean_val = roi.mean()

        results.append({
            "row": row,
            "col": col,
            "centroid": (cx, cy),
            "mean_intensity": mean_val
        })

        cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(vis, f"{row},{col}",
                    (int(cx)+5, int(cy)+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (0,255,0), 1)
        cv2.imwrite("output"+fn+".jpg", vis)

    """

    # Read the multi-frame TIFF file
    success, images = cv2.imreadmulti(fn, images, flags=cv2.IMREAD_UNCHANGED)
    if not success or len(images) < 2:
        raise RuntimeError(
            f"Expected at least 2 frames in '{fn}', got {len(images)}. "
            "Check the file is a valid Walz PAM TIFF export."
        )
    Fo_frame = images[0]
    Fm_frame = images[1]

    if warp_M is not None:
        Fo_frame = cv2.warpAffine(Fo_frame, warp_M, warp_size)
        Fm_frame = cv2.warpAffine(Fm_frame, warp_M, warp_size)

    if crop_rect is not None:
        x1, y1, x2, y2 = crop_rect
        Fo_frame = Fo_frame[y1:y2, x1:x2]
        Fm_frame = Fm_frame[y1:y2, x1:x2]

    results = []

    # Convert to 8-bit for visualisation; guard against flat (blank/saturated) frames
    min_val = np.min(Fo_frame)
    max_val = np.max(Fo_frame)
    if max_val > min_val:
        scaled_img = ((Fo_frame - min_val) / (max_val - min_val)) * 255
    else:
        scaled_img = np.zeros_like(Fo_frame, dtype=float)
    gray = scaled_img.astype(np.uint8)
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    half = roi_size // 2

    # Pre-scan assignments to find grid cells claimed by more than one centroid.
    # This happens when the declared grid dims are wrong (e.g. 5×9 instead of 5×10).
    cell_counts = {}
    for a in assignments:
        key = (int(a["r"]), int(a["c"]))
        cell_counts[key] = cell_counts.get(key, 0) + 1
    duplicate_cells = {cell for cell, n in cell_counts.items() if n > 1}
    if duplicate_cells:
        pairs = ", ".join(f"{r+1},{c+1}" for r, c in sorted(duplicate_cells))
        print(f"  WARNING: {len(duplicate_cells)} grid cell(s) have multiple ROIs assigned "
              f"(cells: {pairs}) — check grid dimensions. Duplicates shown in orange.")

    # BGR colour pairs: (box, label)  normal=blue/green  duplicate=orange
    CLR_NORMAL = ((255, 0, 0),     (0, 255, 0))
    CLR_DUP    = ((0, 165, 255),   (0, 165, 255))

    for cur_ass in assignments:
        cy, cx = cur_ass["y"], cur_ass["x"]
        row, col = cur_ass["r"], cur_ass["c"]

        x1 = max(0, int(cx - half))
        x2 = min(Fo_frame.shape[1], int(cx + half))
        y1 = max(0, int(cy - half))
        y2 = min(Fo_frame.shape[0], int(cy + half))

        if x2 <= x1 or y2 <= y1:
            print(f"  Warning: ROI at ({cx:.0f},{cy:.0f}) row {int(row)+1} col {int(col)+1} "
                  "is outside image bounds — skipped.")
            continue

        mean_Fo_cur = float(Fo_frame[y1:y2, x1:x2].mean())
        mean_Fm_cur = float(Fm_frame[y1:y2, x1:x2].mean())

        # Guard against dead/unlit discs where Fm ≈ 0
        FvFm = (mean_Fm_cur - mean_Fo_cur) / mean_Fm_cur if mean_Fm_cur > 0 else float('nan')

        box_clr, lbl_clr = CLR_DUP if (int(row), int(col)) in duplicate_cells else CLR_NORMAL
        cv2.rectangle(vis, (x1, y1), (x2, y2), box_clr, 2)
        cv2.putText(vis, f"{int(row)+1},{int(col)+1}",
                    (int(cx) + 5, int(cy) + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, lbl_clr, 1)

        leaf_number = int(row) * expected_cols + int(col) + 1
        results.append({
            "filename": fn,
            "row": int(row) + 1,
            "col": int(col) + 1,
            "leaf_number": leaf_number,
            "centroid_x": float(cx),
            "centroid_y": float(cy),
            "mean_Fo": mean_Fo_cur,
            "mean_Fm": mean_Fm_cur,
            "FvFm": float(FvFm)
        })

    # Write visualisation once after all ROIs are drawn
    cv2.imwrite(os.path.join(output_dir or ".", "output" + fn + ".jpg"), vis)

    return results
