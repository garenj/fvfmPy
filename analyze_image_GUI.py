import cv2
from pathlib import PurePath



def analyze_ROIs(fn, rois, ROIsize, expected_cols, warp_M=None, warp_size=None, crop_rect=None, output_dir=None):

    images = []

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


    # Pre-scan assignments to find grid cells claimed by more than one centroid.
    # This happens when the declared grid dims are wrong (e.g. 5×9 instead of 5×10).
    # cell_counts = {}
    # for a in assignments:
    #     key = (int(a["r"]), int(a["c"]))
    #     cell_counts[key] = cell_counts.get(key, 0) + 1
    # duplicate_cells = {cell for cell, n in cell_counts.items() if n > 1}
    # if duplicate_cells:
    #     pairs = ", ".join(f"{r+1},{c+1}" for r, c in sorted(duplicate_cells))
    #     print(f"  WARNING: {len(duplicate_cells)} grid cell(s) have multiple ROIs assigned "
    #           f"(cells: {pairs}) — check grid dimensions. Duplicates shown in orange.")



    half = ROIsize/2

    #for cur_ass in assignments:
    for roi in rois:
        cx, cy = roi['centroid']
        #cy, cx = cur_ass["y"], cur_ass["x"]
        row, col = roi['row'], roi['col']
        #row, col = cur_ass["r"], cur_ass["c"]

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

        leaf_number = int(row) * expected_cols + int(col) + 1
        results.append({
            "filename": str(PurePath(fn).name),
            "row": int(row) + 1,
            "col": int(col) + 1,
            "leaf_number": leaf_number,
            "centroid_x": float(cx),
            "centroid_y": float(cy),
            "mean_Fo": mean_Fo_cur,
            "mean_Fm": mean_Fm_cur,
            "FvFm": float(FvFm)
        })

    return results
   