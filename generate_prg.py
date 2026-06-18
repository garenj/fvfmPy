"""
Generate an ImagingWinGigE script.prg to batch-convert .pim files to multi-frame TIFF.

Usage:
    python generate_prg.py /path/to/pim/folder
    python generate_prg.py          # prompts for the folder path

The script.prg is written into the same folder as the .pim files.
Copy it to the Windows machine running ImagingWin, then run it via:
    ImagingWin menu -> Script -> Load script -> Run
"""

import argparse
import sys
from pathlib import Path


def generate_prg(directory: str) -> None:
    folder = Path(directory)
    if not folder.is_dir():
        sys.exit(f"Error: '{directory}' is not a valid directory.")

    pim_files = sorted(folder.glob("*.pim"))
    if not pim_files:
        sys.exit(f"No .pim files found in '{directory}'.")

    lines = ["-- Program Start -- |"]
    for pim in pim_files:
        # ImagingWin requires the Load line to omit the .pim extension
        lines.append(f"Load Pim File = |{pim.stem}")
        lines.append(f"Export to Tiff File = |{pim.stem}.tif")

    prg_path = folder / "script.prg"
    # Write with Windows line endings — ImagingWin runs on Windows only
    prg_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

    print(f"Written: {prg_path}")
    print(f"{len(pim_files)} file(s) queued:")
    for pim in pim_files:
        print(f"  {pim.stem}.pim  ->  {pim.stem}.tif")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate ImagingWin script.prg to batch-convert .pim files to TIFF"
    )
    parser.add_argument("directory", nargs="?", default=None,
                        help="Folder containing .pim files (prompted if omitted)")
    args = parser.parse_args()

    directory = args.directory or input("Enter path to folder containing .pim files: ").strip()
    generate_prg(directory)
