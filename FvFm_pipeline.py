"""
Image analysis pipeline for semi-automated processing of leaf fluorescence images.
This script accepts .tif files converted from .pim from a Walz imaging PAM fluorometer.

Pipeline steps (per image):
  1. load_tif_img        — load the Fo (first) frame as 8-bit grayscale for display
  2. correct_perspective — optional interactive rotation to level a tilted tray
  3. crop_image          — optional interactive crop to exclude tray edges / labels
  4. detect_centroids    — segment leaf discs and locate their centres
  5. estimate/confirm grid dims — determine the rows × cols layout of the tray
  6. assign_rois_to_grid — map detected centroids to grid positions
  7. ROIPicker           — interactive review: add / move / delete ROI points
  8. get_Fo_Fm           — extract mean Fo & Fm per ROI from the raw TIFF frames,
                           compute Fv/Fm = (Fm-Fo)/Fm, and write a visualisation JPG
  9. Output preview      — review the visualisation before accepting; redo ROI picker if needed

After all images: results are collected into a CSV file in directory_path.

Authors: Josef Garen, Pieter Arnold

"""

# Import libraries
import os
import sys
import argparse
import cv2
import json
import numpy as np
import pandas
import skimage

# Import functions
from load_tif_img import load_tif_img
from get_candidate_rois import detect_centroids, assign_rois_to_grid
from roi_picker import ROIPicker
from get_Fo_Fm import get_Fo_Fm
from perspective_corrector import correct_perspective
from image_cropper import crop_image
from guess_grid_dims import estimate_grid_dims, confirm_grid_dims, _focus_terminal

# Set up parameters
ROI_SIZE = 10  # side length of the square averaging window in pixels (roi_size × roi_size)

# Expected grid dimensions — set both to known values to skip prompting when
# auto-detection agrees (within ±1). Set both to None to always prompt.
DEFAULT_ROWS = None  # e.g. 5
DEFAULT_COLS = None  # e.g. 10

# Parse command-line arguments
parser = argparse.ArgumentParser(description="FvFm image analysis pipeline")
parser.add_argument("directory", nargs="?", default=None,
                    help="Path to folder containing .tif files")
parser.add_argument("--lock-transforms", action="store_true",
                    help="After each rotation/crop step, prompt to apply the same "
                         "settings to all remaining images")
args = parser.parse_args()

# Step 1: Find .tif image files
if args.directory:
    directory_path = args.directory
else:
    directory_path = input("Enter path to folder containing .tif files: ").strip()

if not os.path.isdir(directory_path):
    sys.exit(f"Error: '{directory_path}' is not a valid directory.")

os.chdir(directory_path)
contents = os.listdir()

# Filter and sort .tif files so processing order is consistent and reproducible
tif_files = sorted([f for f in contents if f.endswith('.tif') or f.endswith('.tiff')])

print(f"Found {len(tif_files)} TIFF files")
print(tif_files)

# --- Checkpoint: resume from a previous interrupted run if available ---
checkpoint_path = os.path.join(directory_path, "checkpoint.json")
results_all = []   # flat list of per-ROI result dicts across all images
processed_files = []

if os.path.exists(checkpoint_path):
    try:
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: checkpoint.json is corrupt (interrupted write). Starting fresh.")
        checkpoint = {}
    if checkpoint.get("directory_path") == directory_path:
        n_done = len(checkpoint.get("processed_files", []))
        print(f"\nCheckpoint found: {n_done} of {len(tif_files)} images already processed.")
        resp = input("Resume from checkpoint? [y/n]: ").strip().lower()
        if resp == 'y':
            results_all     = checkpoint.get("results_all", [])
            processed_files = checkpoint.get("processed_files", [])
            done_set        = set(processed_files)
            tif_files       = [f for f in tif_files if f not in done_set]
            print(f"Resuming — {len(tif_files)} images remaining.\n")
        else:
            print("Starting fresh.\n")

# Locked perspective/crop — once set, applied automatically to all remaining images
# without showing the interactive window.
locked_warp = None   # stores (warp_M, warp_size) after user chooses to lock
locked_crop = None   # stores crop_rect after user chooses to lock

# Step 2: Loop over image files (index-based to allow going back)
i = 0
while i < len(tif_files):
    fn = tif_files[i]
    print(f"Processing ({i+1}/{len(tif_files)}): {fn}")

    # Load Fo frame as 8-bit grayscale
    img = load_tif_img(fn)

    # --- Rotation correction ---
    if locked_warp is not None:
        warp_M, warp_size = locked_warp
        img = cv2.warpAffine(img, warp_M, warp_size)
        print("  Rotation: using saved settings.")
    else:
        img, warp_M, warp_size = correct_perspective(img)
        if warp_M is not None and args.lock_transforms:
            resp = input("  Apply this rotation to all remaining images? [y/n]: ").strip().lower()
            if resp == 'y':
                locked_warp = (warp_M, warp_size)
                print("  Rotation locked for remaining images.")

    # --- Crop ---
    if locked_crop is not None:
        x1, y1, x2, y2 = locked_crop
        img = img[y1:y2, x1:x2].copy()
        crop_rect = locked_crop
        print("  Crop: using saved settings.")
    else:
        img, crop_rect = crop_image(img)
        if crop_rect is not None and args.lock_transforms:
            resp = input("  Apply this crop to all remaining images? [y/n]: ").strip().lower()
            if resp == 'y':
                locked_crop = crop_rect
                print("  Crop locked for remaining images.")

    # Detect leaf disc centroids, estimate grid dims, confirm with user
    centroid_dicts = detect_centroids(img, fn)
    centroids_xy = [(d["cx"], d["cy"]) for d in centroid_dicts]
    est_rows, est_cols = estimate_grid_dims(centroids_xy)
    ex_rows, ex_cols = confirm_grid_dims(img, centroids_xy, est_rows, est_cols,
                                         default_rows=DEFAULT_ROWS, default_cols=DEFAULT_COLS)

    # Assign centroids to confirmed grid
    roi_list = assign_rois_to_grid(img, centroid_dicts, ex_rows, ex_cols)

    roi_coords = []
    for j in range(len(roi_list)):
        x, y = roi_list[j]['centroid']
        x, y = x.item(), y.item()
        roi_coords.append([x, y])

    # Format the ROIs in a way that ROI picker likes
    new_roi_list = [{"id": 0,
        "type": "points",
        "color": [0, 0, 255],
        "pts": roi_coords}]

    tmp_json = os.path.join(directory_path, "tmp_data.json")
    tmp_img  = os.path.join(directory_path, "tmp_img.jpg")

    with open(tmp_json, "w") as json_file:
        json.dump(new_roi_list, json_file, indent=4)

    cv2.imwrite(tmp_img, img)

    # --- Inner loop: ROI picker → extraction → preview ---
    # Repeats if the user chooses to redo the ROI picker from the output preview.
    # Flag variables communicate want_back / skip / quit / restart decisions to the outer loop.
    _want_back = False
    _skip      = False
    _quit      = False
    _restart   = False   # restart current image from crop + grid dims step
    res        = None

    while True:
        # Instantiate ROI Picker with candidate ROIs and run gui
        # Keys: Enter/Space=confirm, b=go back to previous image, Esc=quit session
        roi_picker = ROIPicker(tmp_img, tmp_json)
        roi_list_fixed = roi_picker.run_gui()

        # Quit the entire session if requested (Esc in ROI picker)
        if roi_picker.want_quit:
            _quit = True
            break

        # Go back to previous image if requested
        if roi_picker.want_back:
            _want_back = True
            break

        # Guard against confirming with no ROI points (e.g. accidental Esc on a blank image)
        total_points = sum(len(roi['pts']) for roi in roi_list_fixed if roi['type'] == 'points')
        if total_points == 0:
            print(f"  Warning: no ROI points confirmed for {fn}.")
            resp = input("  Skip this image and move on, or re-open the ROI picker? [s/r]: ").strip().lower()
            if resp == 'r':
                continue  # re-open ROI picker
            else:
                print(f"  Skipping {fn}.")
                _skip = True
                break

        # Get Fo and Fm values for each ROI
        res = get_Fo_Fm(fn, roi_list_fixed, roi_size=ROI_SIZE, expected_rows=ex_rows,
                        expected_cols=ex_cols, warp_M=warp_M, warp_size=warp_size,
                        crop_rect=crop_rect, output_dir=directory_path)

        # Per-image Fv/Fm summary — nan-safe in case any disc had Fm≈0
        fvfm_arr  = np.array([r["FvFm"] for r in res])
        n_nan     = int(np.sum(np.isnan(fvfm_arr)))
        n_total   = len(fvfm_arr)
        mean_fvfm = float(np.nanmean(fvfm_arr)) if n_total > n_nan else float('nan')
        std_fvfm  = float(np.nanstd(fvfm_arr))  if n_total > n_nan else float('nan')
        min_fvfm  = float(np.nanmin(fvfm_arr))  if n_total > n_nan else float('nan')
        max_fvfm  = float(np.nanmax(fvfm_arr))  if n_total > n_nan else float('nan')
        summary   = (f"Fv/Fm: mean={mean_fvfm:.3f}  std={std_fvfm:.3f}  "
                     f"min={min_fvfm:.3f}  max={max_fvfm:.3f}  n={n_total - n_nan}/{n_total}")
        print(f"  {summary}")
        if n_nan:
            print(f"  WARNING: {n_nan} disc(s) had Fm~0 (nan Fv/Fm) — check for dead tissue or wrong ROI.")
        n_out = int(np.sum((fvfm_arr < 0) | (fvfm_arr > 1)))
        if n_out:
            print(f"  WARNING: {n_out} disc(s) have Fv/Fm outside [0,1] — check ROI placement and frame order.")
        seen_cells, n_dup = set(), 0
        for r in res:
            cell = (r["row"], r["col"])
            if cell in seen_cells:
                n_dup += 1
            seen_cells.add(cell)
        if n_dup:
            print(f"  WARNING: {n_dup} ROI(s) share a grid cell — orange in preview. Redo with corrected grid dims.")

        # --- Output preview ---
        # Show the visualisation written by get_Fo_Fm so the user can check ROI
        # placement and Fv/Fm values before committing to the next image.
        output_img_path = os.path.join(directory_path, "output" + fn + ".jpg")
        preview = cv2.imread(output_img_path)

        if preview is not None:
            h, w = preview.shape[:2]
            scale = min(1.0, 1200 / max(h, w))

            # Build banner with font scaled to fit the (possibly cropped) image width
            HINT_TEXT = "Enter/Space=accept  r=redo ROI picker  b=restart from crop+grid dims"
            banner_w  = preview.shape[1]
            fscale = 0.30
            for candidate in (0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30):
                (tw, th), _ = cv2.getTextSize(
                    max([summary, HINT_TEXT], key=lambda t: len(t)),
                    cv2.FONT_HERSHEY_SIMPLEX, candidate, 1)
                if tw <= banner_w - 20:
                    fscale = candidate
                    break
            (_, th), _ = cv2.getTextSize('Ag', cv2.FONT_HERSHEY_SIMPLEX, fscale, 1)
            banner_h = int(th * 2.5) + 20  # 10 px top + 10 px bottom margin
            banner   = np.zeros((banner_h, banner_w, 3), dtype=np.uint8)
            cv2.putText(banner, summary,
                        (10, 10 + th), cv2.FONT_HERSHEY_SIMPLEX,
                        fscale, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(banner, HINT_TEXT,
                        (10, 10 + int(th * 2.5)), cv2.FONT_HERSHEY_SIMPLEX,
                        fscale, (180, 180, 180), 1, cv2.LINE_AA)
            combined = np.vstack([banner, preview])

            PREVIEW_WIN = f"Output preview: {fn}"
            ch, cw = combined.shape[:2]
            disp_scale = min(1.0, 1200 / max(ch, cw))
            cv2.namedWindow(PREVIEW_WIN, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(PREVIEW_WIN, int(cw * disp_scale), int(ch * disp_scale))
            cv2.moveWindow(PREVIEW_WIN, 100, 50)
            cv2.setWindowProperty(PREVIEW_WIN, cv2.WND_PROP_TOPMOST, 1)
            cv2.imshow(PREVIEW_WIN, combined)

            redo = restart = False
            while True:
                key = cv2.waitKey(20) & 0xFF
                if key in (13, 32):      # Enter or Space — accept
                    break
                elif key == ord('r'):    # r — redo ROI picker only
                    redo = True
                    break
                elif key == ord('b'):    # b — restart from crop + grid dims
                    restart = True
                    break

            cv2.destroyWindow(PREVIEW_WIN)

            if redo:
                print("  Redoing ROI picker.")
                continue  # back to top of inner loop
            if restart:
                _restart = True
                break  # exit inner loop → outer loop will replay this image from the top

        break  # accept — exit inner loop

    # --- Handle signals from inner loop ---
    if _quit:
        print("\nSession ended by user (Esc). Saving results collected so far.")
        break  # exit outer while loop and fall through to CSV writing

    if _restart:
        print(f"  Restarting {fn} from crop and grid dims.")
        continue  # replay current i without incrementing — reruns rotate→crop→detect→grid→ROI

    if _want_back:
        if i > 0:
            i -= 1
            prev_fn = tif_files[i]
            results_all     = [r for r in results_all     if r["filename"] != prev_fn]
            processed_files = [f for f in processed_files if f != prev_fn]
            print(f"Going back to: {prev_fn}")
        else:
            print("Already at first image, reprocessing.")
        continue

    if _skip:
        i += 1
        continue

    # Commit accepted results and save checkpoint
    results_all.extend(res)
    processed_files.append(fn)

    # Write to a temp file then rename so a crash mid-write never corrupts the checkpoint
    checkpoint_tmp = checkpoint_path + ".tmp"
    with open(checkpoint_tmp, "w") as f:
        json.dump({
            "directory_path": directory_path,
            "processed_files": processed_files,
            "results_all": results_all
        }, f, indent=4)
    os.replace(checkpoint_tmp, checkpoint_path)

    i += 1

# Write the DataFrame to a CSV file
# index=False prevents pandas from writing row indices as a column
csv_path = os.path.join(directory_path, "results_all.csv")
if os.path.exists(csv_path):
    _focus_terminal()
    resp = input(f"\nresults_all.csv already exists in {directory_path}. Overwrite? [y/n]: ").strip().lower()
    if resp != 'y':
        print("CSV not written. Results are still saved in checkpoint.json.")
        csv_path = None

if csv_path:
    df = pandas.DataFrame(results_all)
    df.to_csv(csv_path, index=False)
    print(f"\nDone. Results saved to: {csv_path}")
