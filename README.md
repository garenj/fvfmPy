# fvfmPy: Fluorescence Imaging Processing Pipeline

Semi-automated analysis of leaf disc fluorescence images from a [Walz ImagingPAM](https://www.walz.com/) fluorometer.

This program automatically identifies regions of interest in leaf disc arrays, computes **Fv/Fm = (Fm − Fo) / Fm** for each leaf disc, and exports results to CSV for further processing.

---

## Overview

This program is a semi-automated data analysis pipeline that processes fluorescence images generated from a Walz ImagingPAM fluorometer. The user specifies a folder containing .PIM or .TIF images, and for each image:

1. The program attempts to automatically identify regions of interest (ROIs)
2. The program estimates row and column numbers
3. The program estimates Fv/Fm within each ROI and logs each observation
4. Finally, observations are collated and output in a "long-format" CSV 

Optionally, the user has the opportunity to:

5. Rotate or crop the image
6. Manually specify row and column numbers
7. Adjust image segmentation parameters
8. Manually adjust ROI placement
9. Re-analyze previous images

---

## Requirements

- Python 3.10 or later
- Windows 10/11 or macOS 10.15+

Python dependencies:

```
matplotlib
numpy
opencv-python
pandas
PySide6
scipy
scikit-image
```

---

## Quick start

```bash
# 1. Create a new virtual environment: 
python3 -m venv .venv 

# 2. Install fvfmPy within the virtual environment: 
.\.venv\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ fvfmPy==1.0.0 

# 3. Run fvfmPy: .\.venv\Scripts\fvfmPy.exe
```

---

## Files

| File | Description |
|---|---|
| `src/fvfmPy/fvfmPy.py` | Main pipeline script |
| `src/fvfmPy/analyze_ROIs.py` | Extracts fluorescence metrics from image|
| `src/fvfmPy/apply_rotation.py` | Applies a given rotation to image |
| `src/fvfmPy/estimate_grid_dims.py` | Jenks natural-break grid dimension estimator |
| `src/fvfmPy/get_candidate_rois.py` | Watershed-based leaf disc centroid detection and grid assignment |
| `src/fvfmPy/load_pim_img.py` | Reader for proprietary Walz .PIM format|
| `src/fvfmPy/load_tif_img.py` | Multi-frame .TIF loader |
| `requirements.txt` | Python dependency list |
| `USER_GUIDE.pdf` | Full step-by-step user documentation |

---

## Output

Output is written to a "long-format" .CSV file in a location specified by the user. A complete description of the output file format can be found in the [User's Guide](https://github.com/garenj/fvfmPy/blob/876176313b9d5a737e4ec425b3f6ad44c19b8fb5/USER_GUIDE.pdf).

---

## R package

For users who prefer R and RStudio, an R wrapper package is available from this [link](https://github.com/garenj/fvfmR). It exposes the same pipeline via three
simple R functions, with the Python backend running transparently via
[reticulate](https://rstudio.github.io/reticulate/).

---

## Documentation

See the [User's Guide](https://github.com/garenj/fvfmPy/blob/876176313b9d5a737e4ec425b3f6ad44c19b8fb5/USER_GUIDE.pdf) for detailed walkthrough of the data analysis pipeline, description of optional processing steps, output file descriptions, and troubleshooting tips.

---

## Authors

Josef Garen, Pieter Arnold, and Kristine Crous
