# FvFm Processing Pipeline — User Guide

Semi-automated analysis of leaf disc fluorescence images from a Walz Imaging PAM fluorometer.  
Computes Fv/Fm = (Fm − Fo) / Fm for each leaf disc and exports results to CSV.

---

## Contents

1. [What you need before starting](#1-what-you-need-before-starting)
2. [Install Python](#2-install-python)
3. [Install VS Code](#3-install-vs-code)
4. [Get the pipeline files](#4-get-the-pipeline-files)
5. [Set up the Python environment](#5-set-up-the-python-environment)
6. [Convert .pim files to TIFF](#6-convert-pim-files-to-tiff)
7. [Prepare your TIFF files](#7-prepare-your-tiff-files)
8. [Run the pipeline](#8-run-the-pipeline)
9. [Interactive steps — what to do at each screen](#9-interactive-steps--what-to-do-at-each-screen)
10. [Output files](#10-output-files)
11. [Resuming an interrupted session](#11-resuming-an-interrupted-session)
12. [Command-line options](#12-command-line-options)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. What you need before starting

| Requirement | Notes |
|---|---|
| **macOS 10.15+ or Windows 10/11** | Both are fully supported. |
| **Python 3.9 or later** | Free, see Section 2. |
| **VS Code** | Free code editor used to run the pipeline, see Section 3. |
| **Pipeline files** | The `.py` files described in Section 4. |
| **Multi-frame TIFF images** | Exported from ImagingWin — must contain at least two frames (Fo and Fm) per file. |

---

## 2. Install Python

1. Open your web browser and go to **https://www.python.org/downloads/**
2. Click **Download Python 3.x.x** (the large yellow button — take whatever the current version is).
3. Open the downloaded file and follow the installer for your operating system:

**macOS:**
- Drag Python into your Applications folder.
- After installation, open Terminal (search "Terminal" in Spotlight) and run the certificate installer:
  ```
  /Applications/Python\ 3.x/Install\ Certificates.command
  ```
  (Replace `3.x` with the version you installed. This is required for secure downloads.)

**Windows:**
- Run the installer. On the first screen, **tick "Add Python to PATH"** before clicking Install Now — this is essential.
- Click **Install Now** and follow the prompts.

**Verify it worked:**

- macOS — open Terminal and type: `python3 --version`
- Windows — open Command Prompt (search "cmd" in the Start menu) and type: `python --version`

You should see something like `Python 3.13.7`. If you see an error, restart your computer and try again.

---

## 3. Install VS Code

**macOS:**
1. Go to **https://code.visualstudio.com/** and click **Download for Mac**.
2. Open the downloaded zip, then drag **Visual Studio Code** into your Applications folder.

**Windows:**
1. Go to **https://code.visualstudio.com/** and click **Download for Windows**.
2. Run the installer, accepting the defaults. Tick **"Add to PATH"** if offered.

**Both platforms:**
3. Open VS Code.
4. Install the **Python extension**:
   - Click the Extensions icon in the left sidebar (looks like four squares).
   - Search for `Python` (publisher: Microsoft).
   - Click **Install**.

---

## 4. Get the pipeline files

The pipeline consists of these files — all must be in the **same folder**:

```
FvFm_pipeline.py        ← main script you will run
get_Fo_Fm.py
get_candidate_rois.py
guess_grid_dims.py
image_cropper.py
perspective_corrector.py
roi_picker.py
load_tif_img.py
requirements.txt
```

Place this folder somewhere convenient, for example `~/Documents/FvFm_pipeline/`.

**Open the folder in VS Code:**
- In VS Code: **File → Open Folder…** and select the pipeline folder.

---

## 5. Set up the Python environment

A *virtual environment* (venv) keeps the pipeline's dependencies isolated from the rest of your computer. You only need to do this **once**.

### Open the VS Code terminal

In VS Code: **Terminal → New Terminal** (or press `` Ctrl+` ``).  
A panel opens at the bottom showing a command prompt. All commands below are typed here and confirmed with **Return**.

### Create the virtual environment

**macOS:**
```bash
python3 -m venv .venv
```

**Windows:**
```
python -m venv .venv
```

This creates a hidden folder called `.venv` inside the pipeline folder.

### Activate the virtual environment

**macOS:**
```bash
source .venv/bin/activate
```

**Windows:**
```
.venv\Scripts\activate
```

You will see `(.venv)` appear at the start of the prompt, confirming the environment is active.

> **Every time you open a new terminal session** you must activate the environment again before running the pipeline — use the same activation command as above for your operating system.

### Install the required packages

```
pip install -r requirements.txt
```

This downloads and installs OpenCV, NumPy, pandas, scikit-image, and matplotlib. It may take a minute or two. You only need to do this once (or again after a Python upgrade).

> **Windows note:** if pip reports an error about a missing Visual C++ build tool, install the [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (free) and re-run the command. This is occasionally required by scikit-image.

---

## 6. Convert .pim files to TIFF

Skip this section if you already have multi-frame TIFF files.

Raw measurements from the Walz ImagingWinGigE software are saved as proprietary `.pim` files. Before running the FvFm pipeline you must convert them to multi-frame TIFF. The conversion itself must happen on the **Windows machine running ImagingWin**, but `generate_prg.py` creates the conversion script for you.

### Step A — Generate the ImagingWin script

On any machine (macOS or Windows), with the venv active:

**macOS:**
```bash
python3 generate_prg.py /path/to/your/pim/folder
```

**Windows:**
```
python generate_prg.py C:\path\to\your\pim\folder
```

Or omit the path and type it when prompted. The script will:
1. Find every `.pim` file in the folder (sorted alphabetically).
2. Write a `script.prg` file into that same folder.
3. Print a summary of the files queued.

**Tip — inserting the path without typing:** drag the folder from Finder / File Explorer into the terminal after typing `python3 generate_prg.py ` (with a trailing space).

The generated `script.prg` looks like this:
```
-- Program Start -- |
Load Pim File = |27_120_y2_i
Export to Tiff File = |27_120_y2_i.tif
Load Pim File = |27_15_y2_i
Export to Tiff File = |27_15_y2_i.tif
...
```

> **Note:** ImagingWin requires the `Load Pim File` line to omit the `.pim` extension. `generate_prg.py` handles this automatically.

### Step B — Run the script in ImagingWin (Windows only)

1. Copy `script.prg` to the Windows machine if needed (e.g. via Dropbox or USB).
2. Open **ImagingWinGigE**.
3. From the menu, choose **Script → Load script**, and select `script.prg`.
4. Click **Run**. ImagingWin will load and export each `.pim` file in sequence.
5. When complete, the `.tif` files will be in the same folder as the `.pim` files.

---

## 7. Prepare your TIFF files

- Each TIFF file must contain **at least two frames**: frame 1 = Fo (dark-adapted), frame 2 = Fm (saturating pulse). This is the default multi-frame export from ImagingWin.
- Place all TIFF files for one batch into a single folder, for example:  
  `~/Dropbox/Experiment1/tifs/`
- You do not need to rename the files — the pipeline processes them in alphabetical order.

---

## 8. Run the pipeline

Make sure the virtual environment is active (you see `(.venv)` in the prompt). Then:

**macOS:**
```bash
python3 FvFm_pipeline.py /path/to/your/tif/folder
```

**Windows:**
```
python FvFm_pipeline.py C:\path\to\your\tif\folder
```

Replace the path with the actual location of your TIFF folder.

**Tip — inserting the path without typing it:**
- *macOS:* type `python3 FvFm_pipeline.py ` (trailing space), then drag your TIFF folder from Finder into the terminal. The path is inserted automatically.
- *Windows:* type `python FvFm_pipeline.py ` (trailing space), then drag your TIFF folder from File Explorer into the terminal. If the path contains spaces, it will be quoted automatically.

If you omit the path, the pipeline will ask you to type it interactively.

### Lock transforms across images

If all images in a batch have the same tray orientation and crop region, use `--lock-transforms` to apply the rotation and crop from the first image to all remaining images automatically:

```bash
python3 FvFm_pipeline.py ~/Dropbox/Experiment1/tifs/ --lock-transforms
```

---

## 9. Interactive steps — what to do at each screen

The pipeline processes one TIFF file at a time. For each file you will see a sequence of GUI windows and terminal prompts. The steps are:

---

### Step 1 — Rotation correction

**What you see:** the Fo image with a crosshair cursor.

**Purpose:** level a tilted tray so the leaf disc grid is properly aligned.

**What to do:**
1. Click on one leaf disc near the **left** end of any horizontal row.
2. Click on another leaf disc near the **right** end of the **same** row.
3. A yellow line appears between your clicks with the calculated angle.
4. Press **Enter** or **Space** to apply the rotation.

**Keys:**
| Key | Action |
|---|---|
| Left-click (×2) | Place the two alignment points |
| `r` | Reset — clear clicks and try again |
| `c` | Skip — leave the image unrotated |
| Enter / Space | Apply rotation |

---

### Step 2 — Crop

**What you see:** the (rotated) Fo image with a crosshair cursor.

**Purpose:** exclude tray edges, sample labels, or other non-disc areas from centroid detection.

**What to do:**
1. Click and drag a rectangle around the area containing only the leaf discs.
2. Release the mouse button.
3. Press **Space** or **Enter** to confirm the crop.

**Keys:**
| Key | Action |
|---|---|
| Click + drag | Draw the crop rectangle |
| Space / Enter | Confirm crop |
| Esc / `c` | Skip — use the full image |

---

### Step 3 — Grid dimension check

**What you see:** the cropped image with green circles on detected disc centroids, and a terminal prompt.

**Purpose:** confirm the number of rows and columns in the tray.

**What to do:**
1. Look at the terminal. It shows the estimated grid, e.g.:  
   `47 discs detected — estimated: 5×10`
2. Count the rows and columns in the image to verify.
3. Press **Enter** to accept the estimate, or type `ROWS,COLS` (e.g. `5,10`) and press **Enter** to override.

**Tips:**
- The estimate is usually correct. Override it only if the number clearly does not match.
- If the image shows orange-highlighted ROIs in a later step, the grid dims may be wrong — restart this step with `b` from the preview screen.

---

### Step 4 — ROI Picker

**What you see:** the Fo image with coloured circles at each detected leaf disc centroid.

**Purpose:** review and correct the automatically placed ROI points before Fv/Fm is calculated.

**Status bar (top of window):**
- **Row 1** (white): number of ROI points, mouse position, zoom level.
- **Row 2** (grey): key reference.

**Keys:**
| Key | Action |
|---|---|
| Double-click on a point | **Remove** that point |
| Double-click on empty space | **Add** a new point (must have an ROI selected first) |
| `s` | **Select** the nearest point to the cursor |
| `d` | **Delete** the selected point |
| `a` | **Add** a point at the current cursor position |
| `w` | **Move** the selected point to the current cursor position |
| `+` / `=` | Zoom in |
| `-` / `_` | Zoom out |
| `b` | Go **back** to the previous image |
| Enter / Space | **Confirm** ROIs and proceed to extraction |
| Esc | **Quit** the session (saves results collected so far) |

**What to check:**
- Every leaf disc should have exactly one circle on it.
- Add missing discs (double-click on them or use `a`).
- Remove spurious points on background, tray edges, or labels (double-click or use `d`).
- A missing disc is fine — leave it absent rather than forcing a point.

---

### Step 5 — Output preview

**What you see:** the Fo image with blue rectangles around each ROI and green row,col labels. The banner shows Fv/Fm statistics.

**Purpose:** review extraction results before committing to the next image.

**Check for:**
- **Orange** rectangles and labels — these indicate two ROIs were assigned the same grid cell, which means the grid dimensions are wrong.
- Fv/Fm values outside the range 0–0.85 may indicate a problem with ROI placement or image quality.
- Any `WARNING` messages printed in the terminal alongside the statistics.

**Keys:**
| Key | Action |
|---|---|
| Enter / Space | **Accept** — save results and move to the next image |
| `r` | **Redo ROI picker** — go back to Step 4 only (ROI positions were wrong) |
| `b` | **Restart from crop + grid dims** — go back to Step 2 (crop or grid dims were wrong) |

---

### End of batch — CSV prompt

After all images are processed you will be asked:

```
results_all.csv already exists. Overwrite? [y/n]:
```

- Type `y` and press Enter to overwrite the existing file.
- Type `n` and press Enter to keep the existing file (results are still saved in `checkpoint.json`).

---

## 10. Output files

All output files are written to your TIFF folder:

| File | Description |
|---|---|
| `results_all.csv` | One row per leaf disc per image: filename, row, col, leaf_number, centroid_x/y, mean_Fo, mean_Fm, FvFm. |
| `output<filename>.jpg` | Visualisation image for each TIFF showing ROI positions and row,col labels. Orange = duplicate assignment. |
| `checkpoint.json` | Progress file used to resume an interrupted session (see Section 10). |

### CSV columns

| Column | Description |
|---|---|
| `filename` | Source TIFF filename |
| `row` | Row number (1 = top) |
| `col` | Column number (1 = left) |
| `leaf_number` | Sequential leaf index across the grid (row-major order) |
| `centroid_x`, `centroid_y` | Pixel coordinates of the disc centre in the cropped image |
| `mean_Fo` | Mean pixel intensity in the Fo frame within the ROI window |
| `mean_Fm` | Mean pixel intensity in the Fm frame within the ROI window |
| `FvFm` | (Fm − Fo) / Fm. `nan` if Fm ≈ 0 (dead tissue). |

---

## 11. Resuming an interrupted session

If you close the terminal or press **Esc** mid-session, the pipeline saves a `checkpoint.json` in your TIFF folder recording all images processed so far.

To resume, simply run the same command again:

```bash
python3 FvFm_pipeline.py /path/to/your/tif/folder
```

Already-processed files are skipped automatically and the pipeline continues from where it left off.

To **start fresh** (reprocess all files), delete `checkpoint.json` from your TIFF folder before running.

---

## 12. Command-line options

```
python3 FvFm_pipeline.py [directory] [--lock-transforms]
python  FvFm_pipeline.py [directory] [--lock-transforms]   # Windows
```

| Argument | Description |
|---|---|
| `directory` | Path to the folder containing your TIFF files. Optional — if omitted, you will be prompted. |
| `--lock-transforms` | After confirming rotation and crop for the first image, apply the same rotation and crop to all subsequent images automatically. Useful for batches where all images are from the same tray setup. |

---

## 13. Troubleshooting

### "command not found: python3" (macOS) / "'python' is not recognized" (Windows)
Python is not installed or was not added to PATH during installation. Repeat Section 2, making sure to tick **"Add Python to PATH"** on Windows, then restart your computer and try again.

### "No module named cv2" (or numpy, pandas, etc.)
The virtual environment is not active, or the packages were not installed into it. Activate it first:

*macOS:*
```bash
source .venv/bin/activate
pip install -r requirements.txt
```
*Windows:*
```
.venv\Scripts\activate
pip install -r requirements.txt
```

### Windows: pip install fails with a Visual C++ error
scikit-image occasionally needs a C compiler on Windows. Install the free [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/), restart, re-activate the venv, and run `pip install -r requirements.txt` again.

### The GUI window opens but is blank or crashes immediately
The TIFF file may not contain two frames, or may be corrupted. The terminal will print an error message. Check that the file was exported from ImagingWin as a multi-frame TIFF.

### Grid estimate is wrong (e.g. 2x10 instead of 5x10)
Type the correct dimensions at the grid prompt (e.g. `5,10`). If this keeps happening for the same tray type, note the correct dimensions to use as the override each time.

### Orange ROIs appear on the preview
Two or more centroids were assigned to the same grid cell — the declared grid dimensions are too small (e.g. you confirmed 5x9 but the tray is 5x10). Press `b` on the preview screen to restart from the crop + grid dims step and enter the correct dimensions.

### The pipeline window appears behind other windows
The pipeline attempts to bring windows to the front automatically.
- *macOS:* uses AppleScript. If it does not work, click the window in the Dock or use Mission Control (F3).
- *Windows:* uses the Windows API. If it does not work, click the window in the taskbar.

### Windows: the terminal loses focus and the typing prompt is not visible
This can happen if Windows restricts foreground window changes. Click anywhere in the terminal/Command Prompt window to bring it forward, then type your response.

### "checkpoint.json is corrupt. Starting fresh."
The pipeline crashed mid-write. All images processed up to the previous one are safe. The pipeline will reprocess the image that was interrupted.

### The CSV already has data from a previous run
When prompted `Overwrite? [y/n]`, type `n` to keep the old file. The new results are still in `checkpoint.json`, or delete the old CSV and type `y` to replace it.

---

*Pipeline developed by Josef Garen and Pieter Arnold.*

*Code building and checking was supported by Claude Code.*
