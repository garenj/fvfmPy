"""
Browse the first frame of every .tif file in a directory.
Use this to determine EX_ROWS / EX_COLS before running the pipeline.

Controls:
  Esc / Space / Right arrow — next image
  Left arrow / b            — previous image
  q                         — quit
"""

import os
import cv2
import numpy as np

# ── Set this to the folder you want to inspect ──────────────────────────────
directory_path = "/Users/u1058369/Downloads/44 subset for ESA tif/block6"
# ─────────────────────────────────────────────────────────────────────────────

tif_files = sorted([
    f for f in os.listdir(directory_path)
    if f.lower().endswith(('.tif', '.tiff'))
])

if not tif_files:
    print("No .tif files found in", directory_path)
    raise SystemExit

WINDOW = "TIF Browser — Esc/Space=next  b/Left=prev  q=quit"
cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)

i = 0
while 0 <= i < len(tif_files):
    fn = os.path.join(directory_path, tif_files[i])
    images = []
    success, images = cv2.imreadmulti(fn, images, flags=cv2.IMREAD_UNCHANGED)

    if not success or len(images) == 0:
        print(f"Could not load: {fn}")
        i += 1
        continue

    frame = images[0]
    min_val, max_val = np.min(frame), np.max(frame)
    display = ((frame - min_val) / (max_val - min_val) * 255).astype(np.uint8)
    display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)

    label = f"[{i+1}/{len(tif_files)}]  {tif_files[i]}"
    cv2.putText(display, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2, cv2.LINE_AA)

    h, w = display.shape[:2]
    cv2.resizeWindow(WINDOW, min(w, 1200), min(h, 900))
    cv2.imshow(WINDOW, display)

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (27, 32, 83, 0xFF & ord('n')):   # Esc, Space, Right, n
            i += 1
            break
        elif key in (ord('b'), 81):                  # b, Left arrow
            i = max(0, i - 1)
            break
        elif key == ord('q'):
            i = len(tif_files)                       # exit outer loop
            break
        elif cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            i = len(tif_files)
            break

cv2.destroyAllWindows()
