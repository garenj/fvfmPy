.fvfm_env_name  <- "fvfm-env"
.fvfm_py_loaded <- FALSE

# Activate the virtual environment and load the Python entry point.
# Called internally before every user-facing function; safe to call multiple times.
.ensure_python <- function() {
  if (!requireNamespace("reticulate", quietly = TRUE)) {
    stop("Package 'reticulate' is required. Install it with:\n",
         "  install.packages('reticulate')")
  }

  # Set the virtualenv before Python initialises (has no effect once it has started).
  if (!reticulate::py_available(initialize = FALSE)) {
    if (!reticulate::virtualenv_exists(.fvfm_env_name)) {
      stop(
        "Python environment 'fvfm-env' not found.\n",
        "Run fvfm_setup() once to create it, then try again."
      )
    }
    reticulate::use_virtualenv(.fvfm_env_name, required = TRUE)
  }

  # Source the Python entry point once per session; cache in package env.
  if (!isTRUE(.fvfm_py_loaded)) {
    entry  <- system.file("python", "fvfm_run.py", package = "fvfm")
    py_dir <- system.file("python",                 package = "fvfm")
    if (!nzchar(entry)) {
      stop("Cannot find the fvfm Python files. Try reinstalling the package.")
    }
    reticulate::source_python(entry)
    reticulate::py$setup(py_dir)   # register inst/python on Python's sys.path
    .fvfm_py_loaded <<- TRUE
  }

  invisible(NULL)
}


#' Run the Fv/Fm leaf disc analysis pipeline
#'
#' Processes every TIFF file in \code{directory} interactively. A sequence of
#' GUI windows will appear for rotation correction, cropping, grid dimension
#' confirmation, and ROI review. Results are written to \code{results_all.csv}
#' in the same folder.
#'
#' The GUI windows are native OS windows that appear alongside RStudio. Click
#' into each window to interact with it; the R console is used for text prompts
#' (grid dimensions, CSV overwrite confirmation).
#'
#' @param directory Path to the folder containing \code{.tif} or \code{.tiff}
#'   files.
#' @param lock_transforms Logical. If \code{TRUE}, the rotation and crop
#'   settings confirmed for the first image are applied automatically to all
#'   remaining images. Useful for batches from the same tray setup.
#'   Default: \code{FALSE}.
#'
#' @return Invisible \code{NULL}. Results are written to
#'   \code{results_all.csv} in \code{directory}.
#' @export
#'
#' @examples
#' \dontrun{
#' run_fvfm("~/Dropbox/Experiment1/tifs")
#' run_fvfm("~/Dropbox/Experiment1/tifs", lock_transforms = TRUE)
#' }
run_fvfm <- function(directory, lock_transforms = FALSE) {
  .ensure_python()
  dir <- normalizePath(directory, mustWork = TRUE)
  reticulate::py$run_pipeline(dir, lock_transforms = isTRUE(lock_transforms))
  invisible(NULL)
}


#' Generate an ImagingWin script to batch-convert .pim files to TIFF
#'
#' Scans \code{directory} for \code{.pim} files and writes a
#' \code{script.prg} file in the same folder. Load and run this script inside
#' ImagingWinGigE on Windows to export all \code{.pim} files to multi-frame
#' TIFF.
#'
#' @param directory Path to the folder containing \code{.pim} files.
#'
#' @return Invisible \code{NULL}. \code{script.prg} is written to
#'   \code{directory}.
#' @export
#'
#' @examples
#' \dontrun{
#' convert_pim("C:/Data/Experiment1/raw")
#' }
convert_pim <- function(directory) {
  .ensure_python()
  dir <- normalizePath(directory, mustWork = TRUE)
  reticulate::py$generate_prg(dir)
  invisible(NULL)
}
