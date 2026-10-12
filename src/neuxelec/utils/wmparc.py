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

POURQUOI COMPARER TOUTE LA GRILLE, ET PAS LA SEULE TAILLE

FreeSurfer ecrit ``wmparc.mgz`` en LIA, et un ``.nii.gz`` converti a cote
est en RAS. Les deux font 256x256x256 : comparer les seules tailles les
declare compatibles, aucun reechantillonnage n'a lieu, et les deux
tableaux sont ensuite fusionnes voxel a voxel dans deux ordres d'axes
differents. Un contact de substance blanche gauche recoit alors une
etiquette droite, sans que rien ne le signale. La taille ne dit rien de
l'orientation : l'origine, l'espacement et la direction la disent.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
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


def _same_grid(a, b) -> bool:
    """Les deux volumes occupent-ils exactement la meme grille ?

    Taille, espacement, origine et direction : il faut les quatre pour
    que l'indice ``(i, j, k)`` de l'un designe le meme point physique que
    celui de l'autre, ce que la fusion suppose.
    """
    try:
        return bool(
            a.GetSize() == b.GetSize()
            and np.allclose(a.GetSpacing(), b.GetSpacing(), atol=1e-4)
            and np.allclose(a.GetOrigin(), b.GetOrigin(), atol=1e-3)
            and np.allclose(a.GetDirection(), b.GetDirection(), atol=1e-6)
        )
    except Exception:
        return False


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
            if not _same_grid(wm, ref_img):
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
