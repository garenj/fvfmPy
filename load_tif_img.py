"""
Loads the first frame (Fo) from a multi-frame Walz TIFF and returns it as a
normalised 8-bit grayscale image for use in centroid detection.
"""
import cv2
import numpy as np

from PySide6.QtGui import QImage, QPixmap


def load_tif_img(fn):
    """
    Read a multi-frame TIFF and return the Fo (first) frame as 8-bit grayscale.

    The raw frame is a 16-bit fluorescence image; pixel values are linearly
    scaled to 0–255 so that OpenCV thresholding functions work correctly.

    Returns: uint8 grayscale array (H × W).
    """
    images = []
    success, images = cv2.imreadmulti(fn, images, flags=cv2.IMREAD_UNCHANGED)

    if len(images) == 0:
        raise ValueError(f"Failed to load frames from {fn}")

    Fo_frame = images[0]

    # Scale 16-bit fluorescence values to 8-bit for OpenCV thresholding
    min_val = np.min(Fo_frame)
    max_val = np.max(Fo_frame)
    scaled_img = ((Fo_frame - min_val) / (max_val - min_val)) * 255
    gray = scaled_img.astype(np.uint8)
    return(gray)

def numpy_to_pixmap(gray):
    h, w = gray.shape

    qimage = QImage(
        gray.data,
        w,
        h,
        gray.strides[0],          # bytes per line
        QImage.Format_Grayscale8
    )

    # Make a copy so Qt owns the image data
    return QPixmap.fromImage(qimage.copy())