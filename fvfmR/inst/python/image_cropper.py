"""
Interactive crop tool for fluorescence images.

Pipeline role: optional second step — lets the user drag a rectangle to
exclude labels, tray edges, or other artefacts before centroid detection.
Returns the cropped image and the crop rectangle so the same region can be
extracted from the raw Fo/Fm frames inside get_Fo_Fm().
"""
import cv2
import numpy as np


def crop_image(img):
    """
    Let the user drag a rectangle to define the area for ROI detection.
    Eliminates labels and other edge artefacts from the image before segmentation.

    Controls (shown by OpenCV in the window title):
      Click + drag — draw rectangle
      Space / Enter — confirm crop
      Esc / c       — skip (no crop applied)

    Returns:
      (cropped_img, (x1, y1, x2, y2))  — crop applied
      (img, None)                        — skipped
    """
    h, w = img.shape[:2]
    scale = min(1.0, 1200 / max(h, w))
    disp_w, disp_h = int(w * scale), int(h * scale)

    disp = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    disp = cv2.resize(disp, (disp_w, disp_h))

    cv2.putText(disp, "Drag to crop  |  Space/Enter=confirm  Esc/c=skip",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    WINDOW = "Crop region"
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, disp_w, disp_h)
    cv2.moveWindow(WINDOW, 100, 50)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)

    x, y, rw, rh = cv2.selectROI(WINDOW, disp, showCrosshair=False, fromCenter=False)
    cv2.destroyWindow(WINDOW)

    if rw == 0 or rh == 0:
        return img, None

    # Map display-space rectangle back to original image coordinates
    x1 = max(0, int(x / scale))
    y1 = max(0, int(y / scale))
    x2 = min(w, int((x + rw) / scale))
    y2 = min(h, int((y + rh) / scale))

    return img[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)
