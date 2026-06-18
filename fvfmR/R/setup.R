#' Set up the Python environment for the fvfm package
#'
#' Creates a dedicated virtual environment called \code{fvfm-env} and installs
#' all required Python packages. Run this once after installing the package,
#' or again if you need to reinstall the Python dependencies.
#'
#' @param python Path to a Python 3.9+ executable. \code{NULL} (default) lets
#'   reticulate find Python on your system PATH.
#'
#' @return Invisible \code{NULL}. Called for its side effect.
#' @export
#'
#' @examples
#' \dontrun{
#' fvfm_setup()
#' }
fvfm_setup <- function(python = NULL) {
  if (!requireNamespace("reticulate", quietly = TRUE)) {
    stop("Package 'reticulate' is required. Install it with:\n",
         "  install.packages('reticulate')")
  }

  env_name <- "fvfm-env"

  if (!reticulate::virtualenv_exists(env_name)) {
    message("Creating Python virtual environment 'fvfm-env' ...")
    reticulate::virtualenv_create(envname = env_name, python = python)
  } else {
    message("Python virtual environment 'fvfm-env' already exists.")
  }

  message("Installing Python packages (this may take a minute) ...")
  reticulate::py_install(
    packages = c("opencv-python", "numpy", "pandas",
                 "scikit-image", "scipy", "matplotlib"),
    envname  = env_name,
    pip      = TRUE
  )

  message(
    "\nSetup complete. Python dependencies are installed in 'fvfm-env'.\n",
    "Start each new R session with:\n",
    "  library(fvfm)\n",
    "  run_fvfm('/path/to/tif/folder')"
  )
  invisible(NULL)
}
