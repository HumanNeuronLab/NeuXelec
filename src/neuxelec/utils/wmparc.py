"""Locate the FreeSurfer wmparc that belongs to an aparc+aseg parcellation.

``aparc+aseg`` labels the cortex gyrus by gyrus but puts every cerebral
white-matter voxel under a single generic label (2 = left, 41 = right), so a
depth contact in white matter would only ever be reported as "white matter".
FreeSurfer also produces ``wmparc``, which splits that white matter per gyrus
(``wm-lh-superiortemporal``, ...) plus ``Left/Right-UnsegmentedWhiteMatter`` for
the deep white matter. SEEG2parc (and Voxeloc) substitute the wmparc value for
those generic labels, which is what makes a white-matter contact informative.

The substitution is only valid when both volumes come from the same FreeSurfer
run, hence this sibling lookup. Shared by the BIDS export and the Oblique Slice
contacts table so the two can never diverge.
"""

from __future__ import annotations

from pathlib import Path

import SimpleITK as sitk

#: wmparc file names written by FreeSurfer / FastSurfer, in lookup order.
WMPARC_CANDIDATES = (
    "wmparc.mgz",
    "wmparc.nii.gz",
    "wmparc.nii",
    "wmparc.DKTatlas.mapped.mgz",
    "wmparc.DKTatlas.mapped.nii.gz",
)


def _read_any(path: str):
    """Read a volume, including FreeSurfer .mgz (which SimpleITK cannot open)."""
    try:
        from .image_ingest import read_image_any

        return read_image_any(str(path))
    except Exception:
        pass
    try:
        return sitk.ReadImage(str(path))
    except Exception:
        return None


def find_sibling_wmparc(parc_path, ref_img):
    """Return a wmparc image resampled on ``ref_img``'s grid, or None.

    Only triggers when ``parc_path`` looks like a FreeSurfer aparc+aseg volume
    and a wmparc file sits next to it. Returns None (never raises) otherwise, so
    callers simply fall back to the parcellation as it is.
    """
    if not parc_path or ref_img is None:
        return None
    try:
        p = Path(str(parc_path))
        name = p.name.lower()
        if "aparc" not in name or "aseg" not in name:
            return None

        for candidate in WMPARC_CANDIDATES:
            wp = p.parent / candidate
            if not wp.exists():
                continue
            wm = _read_any(str(wp))
            if wm is None:
                continue
            if wm.GetSize() != ref_img.GetSize():
                wm = sitk.Resample(
                    wm,
                    ref_img,
                    sitk.Transform(),
                    sitk.sitkNearestNeighbor,
                    0.0,
                    wm.GetPixelID(),
                )
            return wm
    except Exception:
        return None
    return None
