"""
Detects leaf disc centroids in a fluorescence image and assigns them to a
rows × cols grid.
"""
import cv2
import numpy as np
from skimage import measure, morphology

from scipy.ndimage import distance_transform_edt
from skimage.segmentation import watershed
from skimage.feature import peak_local_max

# Rotate ROIs to put them on a grid
def pca_rotate(points):
    pts = points - points.mean(axis=0)
    _, _, Vt = np.linalg.svd(pts, full_matrices=False)
    return pts @ Vt.T, Vt

# Identify the centres of each row and column
def band_centers(values, n_bands):
    """Split sorted values into n_bands equal-count groups and return each group's mean."""
    vals = np.sort(values)
    splits = np.array_split(vals, n_bands)
    return np.array([s.mean() for s in splits])

# Attempt to estimate the centre of each leaf disc
def detect_centroids(img,
                     ROI_SIZE = 20,            # side length of square ROI (pixels) — used for darkness filtering only
                     MIN_AREA = 200,           # minimum area of a leaf disc to keep
                     GAUSSIAN_BLUR = 3,        # blur kernel to smooth thresholding
                     ADAPTIVE_THRESH_VAL = 101,# Adaptive threshold neighbourhood size
                     WATERSHED_THRESH = 30,    # Watershed segmentation size
                     CONST_VAL = 2):           # Neighbourhood size for adaptive threshold):
    """
    Segment leaf discs and return a list of dicts with cx, cy, area.
    No grid assignment — call assign_rois_to_grid() separately.
    """

    # Apply Gaussian Blur
    blur = cv2.GaussianBlur(img, (GAUSSIAN_BLUR, GAUSSIAN_BLUR), 0)

    # Apply adaptive threshold
    adaptive_thresh_image = cv2.adaptiveThreshold(blur, 255,
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, ADAPTIVE_THRESH_VAL, CONST_VAL)
    binary = adaptive_thresh_image.astype(bool)

    # Filter out small objects/debris
    binary_clean = morphology.remove_small_objects(binary, max_size=MIN_AREA)

    # Watershed segmentation
    distance = distance_transform_edt(binary_clean)
    coords = peak_local_max(distance,
                            min_distance=WATERSHED_THRESH,
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

# Attempt to assign each ROI to a row and column
def assign_rois_to_grid(img, centroid_dicts, expected_rows, expected_cols, ROI_SIZE = 20, locked = False):
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

    if locked:
        grid_regions = assignments
    else:
        grid_regions = {}
        for cell, idxs in assignments.items():
            if len(idxs) == 1:
                grid_regions[cell] = idxs
            else:
                best = min(idxs, key=lambda i: abs(areas[i] - median_area))
                grid_regions[cell] = [best]


    results = []
    half = ROI_SIZE // 2

    for (row, col), idxs in grid_regions.items():
        for idx in idxs:
            cx = centroid_dicts[idx]["cx"]
            cy = centroid_dicts[idx]["cy"]

            results.append({
                "row": row,
                "col": col,
                "centroid": (cx, cy)
            })

    # Check row and column assignments; we want the numbering to start in the top left
    first_row_y = []
    last_row_y = []
    first_col_x = []
    last_col_x = []

    for cur in results:
        cx,cy = cur['centroid']

        if cur['row'] == 0:
            first_row_y.append(cy)
        if cur['row'] == (expected_rows - 1):
            last_row_y.append(cy)

        if cur['col'] == 0:
            first_col_x.append(cx)
        if cur['col'] == (expected_cols - 1):
            last_col_x.append(cx)
    

    # Check if row 0 is on top or bottom, switch if so.
    # Guard against edge rows being completely empty (all discs missing).
    if first_row_y and last_row_y and np.mean(first_row_y) > np.mean(last_row_y):
        res_new = []
        for cur in results:
            cur["row"] = expected_rows-cur["row"]-1
            res_new.append(cur)
        results = res_new

    # Check if col 0 is on left or right, switch if so.
    if first_col_x and last_col_x and np.mean(first_col_x) > np.mean(last_col_x):
        res_new = []
        for cur in results:
            cur["col"] = expected_cols-cur["col"]-1
            res_new.append(cur)
        results = res_new

    # Finally, add 1 to all row and column numbers to account for zero indexing
    res_new = []
    for res in results:
        res["col"] = res["col"]+1
        res["row"] = res["row"]+1
        res_new.append(res)
    results = res_new

    return results

# Get candidate ROIs with row and column assignments
def get_candidate_rois(img, fn, expected_rows, expected_cols):
    """Convenience wrapper: detect centroids then assign to grid."""
    centroid_dicts = detect_centroids(img, fn)
    return assign_rois_to_grid(img, centroid_dicts, expected_rows, expected_cols)
