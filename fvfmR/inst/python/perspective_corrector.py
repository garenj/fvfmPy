"""
Interactive rotation-correction tool for fluorescence images.

Pipeline role: optional first step — lets the user level a tilted tray by
clicking two points along a horizontal row of discs. Returns the rotated image
and the affine matrix so the same transform can be applied to the raw Fo/Fm
frames inside get_Fo_Fm().
"""
import cv2
import numpy as np


def correct_perspective(img):
    """
    Interactive rotation tool. Click two points along a row of discs that
    should be horizontal; the image is rotated to level that line.

    Controls:
      Left-click  — place a point (up to 2)
      r           — reset clicks
      s           — skip (return image unchanged)
      Enter/Space — apply rotation (requires 2 clicks)

    Returns:
      (rotated_img, M, (out_w, out_h))  — M is the 2x3 affine matrix
      (img, None, None)                 — if the user pressed 's'
    """
    WINDOW = "Rotation correction — click 2 points along a horizontal row.  r=reset  c=skip  Enter=apply"

    h, w = img.shape[:2]
    scale = min(1.0, 1200 / max(h, w))
    disp_w, disp_h = int(w * scale), int(h * scale)

    clicks = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 2:
            clicks.append((int(x / scale), int(y / scale)))

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, disp_w, disp_h)
    cv2.moveWindow(WINDOW, 100, 50)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    cv2.setMouseCallback(WINDOW, on_mouse)

    while True:
        disp = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
        disp = cv2.resize(disp, (disp_w, disp_h))

        for px, py in clicks:
            cv2.circle(disp, (int(px * scale), int(py * scale)), 7, (0, 255, 0), -1)

        if len(clicks) == 2:
            p1 = (int(clicks[0][0] * scale), int(clicks[0][1] * scale))
            p2 = (int(clicks[1][0] * scale), int(clicks[1][1] * scale))
            cv2.line(disp, p1, p2, (0, 255, 255), 2)
            dx = clicks[1][0] - clicks[0][0]
            dy = clicks[1][1] - clicks[0][1]
            angle = np.degrees(np.arctan2(dy, dx))
            label = f"Rotation: {angle:+.1f} deg    Press Enter to apply"
        elif len(clicks) == 1:
            label = "Click a second point along the same row"
        else:
            label = "Click the first point"

        cv2.putText(disp, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.imshow(WINDOW, disp)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('r'):
            clicks.clear()
        elif key == ord('c'):
            cv2.destroyWindow(WINDOW)
            return img, None, None
        elif key in (13, 32) and len(clicks) == 2:   # Enter or Space
            break

    cv2.destroyWindow(WINDOW)

    dx = clicks[1][0] - clicks[0][0]
    dy = clicks[1][1] - clicks[0][1]
    angle = np.degrees(np.arctan2(dy, dx))

    cx, cy = w / 2.0, h / 2.0
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)

    # Expand canvas so corners are not clipped
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    out_w = int(h * sin_a + w * cos_a)
    out_h = int(h * cos_a + w * sin_a)

    # Shift rotation centre to centre of expanded canvas
    M[0, 2] += (out_w - w) / 2.0
    M[1, 2] += (out_h - h) / 2.0

    rotated = cv2.warpAffine(img, M, (out_w, out_h))
    return rotated, M, (out_w, out_h)
