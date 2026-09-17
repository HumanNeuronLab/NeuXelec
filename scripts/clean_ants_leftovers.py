"""Reclaim the disk that the old ANTs by-products still occupy.

Until 1.2.1, the brain mask, the defacing and the MNI coordinates each ran their
own registration of the T1 onto the template and each kept the whole output:
the transforms, plus two resampled volumes of about 50 MB that nothing ever read.
NeuXelec now computes that registration once and asks ANTs only for the
transforms, but the files already written stay where they are.

This script finds them and, on request, removes them.

    python scripts/clean_ants_leftovers.py D:\\Patients          # report only
    python scripts/clean_ants_leftovers.py D:\\Patients --delete # actually remove

Nothing is removed without ``--delete``. Only the exact file names below are
ever considered, and the transforms NeuXelec still uses are never among them.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

#: Superseded by the shared registration in mni/T1_to_MNI_*. Nothing reads them.
_SUPERSEDED_PREFIXES = ("brainmask_", "deface_")
_SUPERSEDED_SUFFIXES = (
    "0GenericAffine.mat",
    "1Warp.nii.gz",
    "1InverseWarp.nii.gz",
    "Warped.nii.gz",
    "InverseWarped.nii.gz",
)

#: Written by the shared registration itself, and still never read: the two
#: resampled volumes. The three transforms beside them are kept.
_UNUSED_SHARED = (
    "T1_to_MNI_Warped.nii.gz",
    "T1_to_MNI_InverseWarped.nii.gz",
)

#: Kept, always. Listed so the intent is explicit rather than implied.
KEPT = (
    "T1_to_MNI_0GenericAffine.mat",
    "T1_to_MNI_1Warp.nii.gz",
    "T1_to_MNI_1InverseWarp.nii.gz",
    "T1_brainmask.nii.gz",
    "T1_deface_mask.nii.gz",
)


def is_superseded(name: str) -> bool:
    if name in _UNUSED_SHARED:
        return True
    for prefix in _SUPERSEDED_PREFIXES:
        if not name.startswith(prefix):
            continue
        tail = name[len(prefix) :]
        if tail in _SUPERSEDED_SUFFIXES:
            return True
    return False


def scan(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            if name in KEPT:
                continue
            if is_superseded(name):
                found.append(Path(directory) / name)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="folder to scan, patient folders and all")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="remove the files instead of only listing them",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"Not a folder: {root}")
        return 2

    files = scan(root)
    if not files:
        print(f"Nothing to reclaim under {root}")
        return 0

    total = 0
    by_folder: dict[Path, int] = {}
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total += size
        by_folder[path.parent] = by_folder.get(path.parent, 0) + size

    print(f"{len(files)} files, {total / 1e6:.0f} MB, in {len(by_folder)} folder(s):\n")
    for folder, size in sorted(by_folder.items(), key=lambda item: -item[1]):
        print(f"  {size / 1e6:7.0f} MB  {folder}")

    if not args.delete:
        print("\nNothing was removed. Add --delete to actually reclaim this space.")
        return 0

    removed = 0
    freed = 0
    for path in files:
        try:
            size = path.stat().st_size
            path.unlink()
            removed += 1
            freed += size
        except OSError as error:
            print(f"  could not remove {path}: {error}")
    print(f"\nRemoved {removed} files, {freed / 1e6:.0f} MB reclaimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
