"""
Entry point for calling the FvFm pipeline from R via reticulate.

R calls setup() once to register the inst/python directory, then calls
run_pipeline() or generate_prg() as needed.
"""

import os
import sys
import runpy

_PYTHON_DIR = None


def setup(python_dir):
    """Register the inst/python directory so sibling .py files can be imported."""
    global _PYTHON_DIR
    _PYTHON_DIR = str(python_dir)
    if _PYTHON_DIR not in sys.path:
        sys.path.insert(0, _PYTHON_DIR)


def _py_dir():
    if _PYTHON_DIR is not None:
        return _PYTHON_DIR
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def run_pipeline(directory, lock_transforms=False):
    """
    Run the FvFm analysis pipeline on a folder of TIFF files.

    Parameters
    ----------
    directory : str
        Path to the folder containing .tif / .tiff files.
    lock_transforms : bool
        If True, pass --lock-transforms to the pipeline.
    """
    d = _py_dir()
    if d not in sys.path:
        sys.path.insert(0, d)

    old_argv = sys.argv[:]
    old_cwd  = os.getcwd()
    sys.argv = ['FvFm_pipeline.py', str(directory)]
    if lock_transforms:
        sys.argv.append('--lock-transforms')

    try:
        runpy.run_path(os.path.join(d, 'FvFm_pipeline.py'), run_name='__main__')
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)   # restore R's working directory after pipeline os.chdir()


def generate_prg(directory):
    """
    Generate an ImagingWin script.prg from a folder of .pim files.

    Parameters
    ----------
    directory : str
        Path to the folder containing .pim files.
    """
    d = _py_dir()
    if d not in sys.path:
        sys.path.insert(0, d)

    old_argv = sys.argv[:]
    sys.argv = ['generate_prg.py', str(directory)]

    try:
        runpy.run_path(os.path.join(d, 'generate_prg.py'), run_name='__main__')
    finally:
        sys.argv = old_argv
