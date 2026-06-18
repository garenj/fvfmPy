# FvFm Processing Pipeline

Semi-automated analysis of leaf disc fluorescence images from a [Walz ImagingPAM](https://www.walz.com/) fluorometer.

Computes **Fv/Fm = (Fm − Fo) / Fm** for each leaf disc in a tray and exports results to CSV.

---

## Overview

The pipeline covers two stages:

**Stage 1 — Convert raw instrument files to TIFF** (`generate_prg.py`)  
Walz ImagingWinGigE saves measurements as proprietary `.pim` files. This utility generates an ImagingWin batch script (`script.prg`) that converts every `.pim` file in a folder to a multi-frame TIFF — one frame per measurement. The conversion is then run inside ImagingWin on Windows.

**Stage 2 — Extract and compute Fv/Fm** (`FvFm_pipeline.py`)  
A semi-interactive pipeline that processes each TIFF file in a folder. For each image the user:
1. Optionally corrects tray rotation.
2. Crops to the disc area.
3. Confirms the detected grid dimensions (rows × columns).
4. Reviews and corrects automatically placed ROI points.
5. Views the output preview and accepts or re-does any step.

Results are written to `results_all.csv` with one row per leaf disc per image.

---

## Requirements

- Python 3.9 or later
- Windows 10/11 or macOS 10.15+
- [Walz ImagingWinGigE](https://www.walz.com/downloads/) (Windows only, for `.pim` → TIFF conversion)

Python dependencies (install once with `pip install -r requirements.txt`):

```
opencv-python
numpy
pandas
scikit-image
matplotlib
```

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/fvfm-pipeline.git
cd fvfm-pipeline

# 2. Create and activate a virtual environment
python3 -m venv .venv          # macOS
source .venv/bin/activate      # macOS
# python -m venv .venv         # Windows
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (If starting from .pim files) Generate the ImagingWin conversion script
python3 generate_prg.py /path/to/pim/folder
# Copy script.prg to the Windows machine, load in ImagingWin, and run.

# 5. Run the FvFm pipeline on a folder of TIFFs
python3 FvFm_pipeline.py /path/to/tif/folder
```

---

## Files

| File | Description |
|---|---|
| `FvFm_pipeline.py` | Main pipeline script |
| `generate_prg.py` | Utility: generate ImagingWin `.prg` script from a folder of `.pim` files |
| `get_Fo_Fm.py` | Fo/Fm extraction and Fv/Fm calculation per ROI |
| `get_candidate_rois.py` | Watershed-based leaf disc centroid detection and grid assignment |
| `guess_grid_dims.py` | Jenks natural-break grid dimension estimator |
| `roi_picker.py` | Interactive ROI review GUI |
| `image_cropper.py` | Interactive crop GUI |
| `perspective_corrector.py` | Interactive rotation correction GUI |
| `load_tif_img.py` | Multi-frame TIFF loader |
| `batch_convert_pim_script_generator.R` | Legacy R script (superseded by `generate_prg.py`) |
| `requirements.txt` | Python dependency list |
| `USER_GUIDE.md` | Full step-by-step user documentation |

---

## Output

All output files are written to the TIFF folder:

| File | Description |
|---|---|
| `results_all.csv` | One row per leaf disc: filename, row, col, leaf_number, centroid_x/y, mean_Fo, mean_Fm, FvFm |
| `output<filename>.jpg` | Annotated visualisation for each TIFF (blue ROIs, row/col labels; orange = duplicate assignment) |
| `checkpoint.json` | Progress file for resuming interrupted sessions |

---

## Documentation

See [USER_GUIDE.md](USER_GUIDE.md) for detailed installation instructions, a walkthrough of every interactive step, output file descriptions, and troubleshooting.

---

## Authors

Josef Garen and Pieter Arnold  
*Code development supported by Claude Code.*
