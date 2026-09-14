"""Cortical mask from a FreeSurfer-style parcellation.

Functional maps (PET, SPECT, SISCOM, fMRI) are clinically informative mostly in
the cortical ribbon. When a parcellation is loaded, this builds a boolean mask
of the cortex so the functional overlays can be restricted to it, hiding
white-matter, deep grey nuclei and CSF signal.

Cortex is detected by LABEL NAME (robust across DK / Destrieux / aparc+aseg),
never by hard-coded numbers:
    * FreeSurfer cortical ribbon labels are named ``ctx-lh-...`` / ``ctx-rh-...``
      (Desikan-Killiany) or ``ctx_lh_...`` / ``ctx_rh_...`` (Destrieux);
    * the generic aseg cortex labels are ``Left-Cerebral-Cortex`` /
      ``Right-Cerebral-Cortex``.
"""

from __future__ import annotations

import numpy as np


def _label_name(entry) -> str:
    """A LUT entry is either a name, or a ``(name, (r, g, b))`` tuple."""
    if isinstance(entry, (tuple, list)) and entry:
        return str(entry[0])
    return str(entry)


def is_cortex_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if n.startswith("ctx-") or n.startswith("ctx_"):
        return True
    return "cerebral-cortex" in n or "cerebral cortex" in n


def cortex_label_ids(lut: dict) -> set[int]:
    """Return the set of label ids in ``lut`` that name a cortical region."""
    out: set[int] = set()
    for idx, entry in (lut or {}).items():
        try:
            if is_cortex_name(_label_name(entry)):
                out.add(int(idx))
        except Exception:
            continue
    return out


def build_cortex_mask(parc_data: np.ndarray, lut: dict) -> np.ndarray | None:
    """Boolean mask (same shape as ``parc_data``) of cortical voxels.

    Returns ``None`` if the LUT names no cortical label (so callers can fall back
    to showing everything rather than hiding the whole map).
    """
    ids = cortex_label_ids(lut)
    if not ids:
        return None
    return np.isin(np.asarray(parc_data), list(ids))
