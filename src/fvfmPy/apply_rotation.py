import cv2

# Applies a given rotation to the current image
def apply_rotation(img, angle):

    h, w = img.shape[:2]

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
    return rotated 