# fvfmPy and fvfmR: Fluorescence Processing Pipeline

Semi-automated analysis of leaf disc fluorescence images from a [Walz ImagingPAM](https://www.walz.com/) fluorometer.

This program automatically identifies regions of interest in leaf disc arrays, computes **Fv/Fm = (Fm − Fo) / Fm** for each leaf disc, and exports results to CSV for further processing.

---

## Overview

This program (`fvfmPy.py`) is a semi-automated data analysis pipeline that processes fluorescence images generated from a Walz ImagingPAM fluorometer. The user specifies a folder containing .PIM or .TIF images, and for each image:

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

- Python 3.9 or later
- Windows 10/11 or macOS 10.15+

Python dependencies (install once with `pip install -r requirements.txt`):

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
# 1. Clone the repo
git clone https://github.com/garenj/fvfmPy.git
cd fvfmPy

# 2. Create and activate a virtual environment
python3 -m venv .venv          # macOS
source .venv/bin/activate      # macOS

python -m venv .venv         # Windows
.venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the FvFm pipeline
python3 fvfmPy.py 
```

---

## Files

| File | Description |
|---|---|
| `fvfmPy.py` | Main pipeline script |
| `utils/analyze_ROIs.py` | Extracts fluorescence metrics from image|
| `utils/apply_rotation.py` | Applies a given rotation to image |
| `utils/estimate_grid_dims.py` | Jenks natural-break grid dimension estimator |
| `utils/get_candidate_rois.py` | Watershed-based leaf disc centroid detection and grid assignment |
| `utils/load_pim_img.py` | Reader for proprietary Walz .PIM format|
| `utils/load_tif_img.py` | Multi-frame .TIF loader |
| `requirements.txt` | Python dependency list |
| `USER_GUIDE.pdf` | Full step-by-step user documentation |

---

## Output

All output files are written to the TIFF folder:

| File | Description |
|---|---|
| `results_all.csv` | One row per leaf disc: filename, row, col, leaf_number, centroid_x/y, mean_Fo, mean_Fm, FvFm |
| `output<filename>.jpg` | Annotated visualisation for each TIFF (blue ROIs, row/col labels; orange = duplicate assignment) |
| `checkpoint.json` | Progress file for resuming interrupted sessions |

---

## R package

For users who prefer R and RStudio, an R wrapper package is available in the
[`fvfmR/`](fvfmR/) subdirectory. It exposes the same pipeline via three
simple R functions, with the Python backend running transparently via
[reticulate](https://rstudio.github.io/reticulate/).

```r
# Install from GitHub (run once)
remotes::install_github("garenj/fvfmPy", subdir = "fvfmR")

# Set up the Python environment (run once after installing)
library(fvfm)
fvfm_setup()

# Use
convert_pim("path/to/pim/folder")           # generate ImagingWin script.prg
run_fvfm("path/to/tif/folder")              # run the full analysis pipeline
run_fvfm("path/to/tif/folder",
         lock_transforms = TRUE)            # lock rotation/crop across images
```

The OpenCV GUI windows appear as native OS windows alongside RStudio. Text
prompts (grid dimensions, CSV overwrite) appear in the R console.

---

## Documentation

See [USER_GUIDE.pdf](USER_GUIDE.pdf) for detailed installation instructions, a walkthrough of every interactive step, output file descriptions, and troubleshooting.

---

## Authors

Josef Garen and Pieter Arnold  
