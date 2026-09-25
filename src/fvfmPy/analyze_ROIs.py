import cv2
from pathlib import PurePath

from .load_pim_img import load_pim
from .apply_rotation import apply_rotation

# Function to extract fluorescence metrics from currently identified ROIs
def analyze_ROIs(fn, rois, ROIsize, rotate_angle = None, crop_rect=None):

    images = []

    # Load data file frames
    if fn.endswith(".tif") or fn.endswith(".tiff"):
        # Read the multi-frame TIFF file
        success, images = cv2.imreadmulti(fn, images, flags=cv2.IMREAD_UNCHANGED)
        if not success or len(images) < 2:
            raise RuntimeError(
                f"Expected at least 2 frames in '{fn}', got {len(images)}. "
                "Check the file is a valid Walz PAM TIFF export."
            )
    elif fn.endswith(".pim"):
        images = load_pim(fn)
        if len(images) < 2:
            raise RuntimeError(
                f"Expected at least 2 frames in '{fn}', got {len(images)}. "
                "Check the file is a valid Walz PAM .pim file"
            )
    else:
        print("File format incorrect")
        return
    
    # Get just the important frames
    Fo_frame = images[0]
    Fm_frame = images[1]

    # If needed, apply rotation
    if rotate_angle is not None:
        Fo_frame = apply_rotation(Fo_frame, rotate_angle)
        Fm_frame = apply_rotation(Fm_frame, rotate_angle)

    # If needed, apply crop
    if crop_rect is not None:
        x1, y1, x2, y2 = crop_rect
        Fo_frame = Fo_frame[y1:y2, x1:x2]
        Fm_frame = Fm_frame[y1:y2, x1:x2]

    results = []
    half = ROIsize/2
    expected_cols = max([d['col'] for d in rois])

    # Loop over each ROI
    for roi in rois:
        cx, cy = roi['centroid']
        row, col = roi['row'], roi['col']

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

        leaf_number = (int(row)-1) * expected_cols + int(col)

        # Assemble results for current ROI
        results.append({
            "filename": str(PurePath(fn).name),
            "row": int(row),
            "col": int(col),
            "leaf_number": leaf_number,
            "centroid_x": float(cx),
            "centroid_y": float(cy),
            "mean_Fo": mean_Fo_cur,
            "mean_Fm": mean_Fm_cur,
            "FvFm": float(FvFm)
        })

    # Sort by leaf number
    results.sort(key=lambda x: x["leaf_number"])
    print(f"  [analyze ROIs] {len(rois)} measurements logged from file {PurePath(fn).name}")

    return results
   