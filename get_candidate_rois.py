"""
Detects leaf disc centroids in a fluorescence image and assigns them to a
rows × cols grid.

Pipeline role: called after load_tif_img to produce a list of centroid
coordinates that are passed to the ROI picker for user review.

Note: ROI_SIZE here is used only as a darkness filter during centroid detection
and for the mean_intensity field (which the pipeline does not use downstream).
The ROI size that controls the actual Fv/Fm calculation window is set
separately as ROI_SIZE in FvFm_pipeline.py and passed to get_Fo_Fm().
"""
import cv2
import numpy as np
from skimage import io, filters, measure, morphology

from scipy.ndimage import distance_transform_edt
from skimage.segmentation import watershed
from skimage.feature import peak_local_max

#ROI_SIZE = 20          # side length of square ROI (pixels) — used for darkness filtering only
#MIN_AREA = 200        # minimum area of a leaf disc to keep
#GAUSSIAN_BLUR = 3      # blur kernel to smooth thresholding
#ADAPTIVE_THRESH_VAL = 101 # Neighbourhood size for adaptive threshold


def pca_rotate(points):
    pts = points - points.mean(axis=0)
    _, _, Vt = np.linalg.svd(pts, full_matrices=False)
    return pts @ Vt.T, Vt

def band_centers(values, n_bands):
    """Split sorted values into n_bands equal-count groups and return each group's mean."""
    vals = np.sort(values)
    splits = np.array_split(vals, n_bands)
    return np.array([s.mean() for s in splits])


def detect_centroids(img,
                     ROI_SIZE = 20,          # side length of square ROI (pixels) — used for darkness filtering only
                     MIN_AREA = 200,        # minimum area of a leaf disc to keep
                     GAUSSIAN_BLUR = 3,      # blur kernel to smooth thresholding
                     ADAPTIVE_THRESH_VAL = 101): # Neighbourhood size for adaptive threshold):
    """
    Segment leaf discs and return a list of dicts with cx, cy, area.
    No grid assignment — call assign_rois_to_grid() separately.
    """
    blur = cv2.GaussianBlur(img, (GAUSSIAN_BLUR, GAUSSIAN_BLUR), 0)

    adaptive_thresh_image = cv2.adaptiveThreshold(blur, 255,
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, ADAPTIVE_THRESH_VAL, 2)
    binary = adaptive_thresh_image
    binary_clean = morphology.remove_small_objects(binary, min_size=MIN_AREA)

    distance = distance_transform_edt(binary_clean)

    coords = peak_local_max(distance,
                            min_distance=30,
                            footprint=np.ones((25, 25)),
                            labels=binary_clean)

    markers = np.zeros(distance.shape, dtype=int)
    markers[tuple(coords.T)] = np.arange(1, len(coords) + 1)

    labels = watershed(-distance, markers, mask=binary_clean)
    regions = measure.regionprops(labels)

    half = ROI_SIZE // 2
    centroids = []
    for r in regions:
        cy, cx = r.centroid
        x1, x2 = int(cx - half), int(cx + half)
        y1, y2 = int(cy - half), int(cy + half)
        x1, x2 = max(0, x1), min(img.shape[1], x2)
        y1, y2 = max(0, y1), min(img.shape[0], y2)
        roi = img[y1:y2, x1:x2]
        if roi.mean() < 20:
            continue
        centroids.append({"cx": cx, "cy": cy, "area": r.area})

    return centroids


def assign_rois_to_grid(img, centroid_dicts, expected_rows, expected_cols, ROI_SIZE = 20):
    """
    Assign detected centroids to a rows x cols grid via PCA rotation and
    nearest-band matching. Returns roi list compatible with the pipeline.
    """
    if not centroid_dicts:
        return []

    cx_arr = np.array([d["cx"] for d in centroid_dicts])
    cy_arr = np.array([d["cy"] for d in centroid_dicts])
    areas  = np.array([d["area"] for d in centroid_dicts])

    centroids_xy = np.column_stack([cx_arr, cy_arr])
    coords_rot, _ = pca_rotate(centroids_xy)
    x_rot = coords_rot[:, 0]
    y_rot = coords_rot[:, 1]

    row_centers = band_centers(y_rot, expected_rows)
    col_centers = band_centers(x_rot, expected_cols)

    assignments = {}
    for i in range(len(centroid_dicts)):
        r = np.argmin(np.abs(row_centers - y_rot[i]))
        c = np.argmin(np.abs(col_centers - x_rot[i]))
        assignments.setdefault((r, c), []).append(i)

    grid_regions = {}
    median_area = np.median(areas)

    for r in range(expected_rows):
        for c in range(expected_cols):
            cell = (r, c)
            if cell in assignments:
                idxs = assignments[cell]
                if len(idxs) > 1:
                    idx = min(idxs, key=lambda i: abs(areas[i] - median_area))
                else:
                    idx = idxs[0]
                grid_regions[cell] = idx

    results = []
    half = ROI_SIZE // 2

    for (row, col), idx in grid_regions.items():
        cx = centroid_dicts[idx]["cx"]
        cy = centroid_dicts[idx]["cy"]

        x1, x2 = int(cx - half), int(cx + half)
        y1, y2 = int(cy - half), int(cy + half)
        x1, x2 = max(0, x1), min(img.shape[1], x2)
        y1, y2 = max(0, y1), min(img.shape[0], y2)

        results.append({
            "row": row,
            "col": col,
            "centroid": (cx, cy),
            "mean_intensity": img[y1:y2, x1:x2].mean()
        })

    return results


def get_candidate_rois(img, fn, expected_rows, expected_cols):
    """Convenience wrapper: detect centroids then assign to grid."""
    centroid_dicts = detect_centroids(img, fn)
    return assign_rois_to_grid(img, centroid_dicts, expected_rows, expected_cols)
