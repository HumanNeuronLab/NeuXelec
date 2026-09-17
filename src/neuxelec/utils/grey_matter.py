"""Tell grey matter from white matter and CSF in a parcellation.

A depth electrode crosses grey and white matter alternately. The contacts that
record what the clinician is after are the ones sitting in grey matter, so both
the oblique slice and the 3D view can narrow the display to those.

Two decisions shape this module.

**Grey matter is defined by exclusion.** Listing every grey structure would tie
the filter to one atlas and would quietly drop a contact the day FreeSurfer adds
a label. A labelled voxel that is neither white matter, nor CSF or ventricle,
nor background counts as grey. An unfamiliar atlas therefore errs towards
showing a contact rather than hiding it, which is the safe direction: a hidden
contact is one nobody looks at.

**It is not the cortical ribbon.** ``cortex_mask`` restricts functional overlays
to the cortex, which is right for a PET map. It would be wrong here: in SEEG the
hippocampus and the amygdala are exactly where the interesting contacts are, and
they are deep grey, not cortex.

Classification is by LABEL NAME, like :mod:`cortex_mask`, so it survives
Desikan-Killiany, Destrieux, aparc+aseg and the wmparc substitution.
"""

from __future__ import annotations

import re

import numpy as np

#: The five corpus callosum labels of aparc+aseg, which are white matter.
_CORPUS_CALLOSUM = {
    "ccposterior",
    "ccmidposterior",
    "cccentral",
    "ccmidanterior",
    "ccanterior",
}

_BACKGROUND = {"", "unknown", "background", "none", "undetermined"}


def _label_name(entry) -> str:
    """A LUT entry is either a name, or a ``(name, (r, g, b))`` tuple."""
    if isinstance(entry, (tuple, list)) and entry:
        return str(entry[0])
    return str(entry)


def _compact(name: str) -> str:
    """Lowercase, letters and digits only, so separators stop mattering."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def is_white_matter_name(name: str) -> bool:
    """White matter, including the wmparc gyral labels and the callosum."""
    c = _compact(name)
    if c.startswith("wmlh") or c.startswith("wmrh"):
        return True
    if "whitematter" in c:  # Left-Cerebral-White-Matter, UnsegmentedWhiteMatter
        return True
    if c in _CORPUS_CALLOSUM:
        return True
    return c == "wmhypointensities"


def is_csf_name(name: str) -> bool:
    """Ventricles, CSF and the structures that line them."""
    c = _compact(name)
    return (
        "ventricle" in c
        or c == "csf"
        or "choroidplexus" in c
        or "vessel" in c
    )


def is_background_name(name: str) -> bool:
    return _compact(name) in _BACKGROUND


def is_grey_matter_name(name: str) -> bool:
    """Everything that is labelled and is not white matter, CSF or background."""
    return not (
        is_background_name(name) or is_white_matter_name(name) or is_csf_name(name)
    )


def grey_matter_label_ids(lut: dict) -> set[int]:
    """Label ids of ``lut`` that name grey matter."""
    out: set[int] = set()
    for idx, entry in (lut or {}).items():
        try:
            if int(idx) == 0:
                continue  # 0 is background in every FreeSurfer-style atlas
            if is_grey_matter_name(_label_name(entry)):
                out.add(int(idx))
        except Exception:
            continue
    return out


def dominant_label_at(parc_vol: np.ndarray, voxel_zyx) -> int | None:
    """The SEEG2parc label of a contact: dominant region of the weighted cube.

    Same measure as the contacts table and the BIDS export, so the filter can
    never disagree with the region the table displays.
    """
    from ..seeg2parc import cube_label_weights

    weights = cube_label_weights(parc_vol, voxel_zyx)
    if not weights:
        return None
    return int(weights[0][0])


def grey_matter_flags(parcel_img, parc_vol: np.ndarray, lut: dict, points_lps) -> list[bool]:
    """One flag per point: does its SEEG2parc region sit in grey matter?

    A point that falls outside the parcellation, or whose label is unknown to
    the lookup table, is reported as grey so it stays visible.
    """
    if points_lps is None:
        return []
    grey_ids = grey_matter_label_ids(lut)
    flags: list[bool] = []
    # Never test the truth value of ``points_lps``: the oblique page hands over
    # a numpy (N, 3) array, and ``array or []`` raises.
    for point in points_lps:
        try:
            index = parcel_img.TransformPhysicalPointToIndex(
                tuple(float(v) for v in point)
            )
            # SimpleITK indexes (x, y, z); the numpy volume is [z, y, x].
            label = dominant_label_at(parc_vol, (index[2], index[1], index[0]))
        except Exception:
            label = None
        if label is None:
            flags.append(True)
            continue
        if not grey_ids:
            flags.append(True)
            continue
        flags.append(label in grey_ids)
    return flags
