"""SEEG2parc: attribute cerebral parcellation labels to depth electrode contacts.

Pure-Python port of the depth-electrode branch of the MATLAB SEEG2parc
(Pierre Megevand, Human Neuron Lab, University of Geneva;
https://github.com/HumanNeuronLab/SEEG2parc), so that NeuXelec can produce a
Voxeloc-identical BIDS ``electrodes.tsv`` (``tissueLabel`` + ``tissueWeights``).

For each depth contact, a 3x3x3 voxel cube centred on the (rounded) contact
voxel is sampled in the parcellation volume. Each voxel is weighted by the
inverse of its Euclidean distance to the centre:

    * centre and 6 face neighbours (dist 0 or 1) -> weight 1
    * 12 edge neighbours          (dist sqrt(2)) -> weight 1/sqrt(2)
    * 8 corner neighbours         (dist sqrt(3)) -> weight 1/sqrt(3)

Per-label weights are summed, sorted descending and normalised to fractions of
1. Labels are named via a FreeSurfer-style lookup table.

The parcellation is ``aparc+aseg`` with the generic cerebral white-matter
labels (2 = Left, 41 = Right) replaced by the detailed ``wmparc`` labels, exactly
like the reference implementation. The white-matter substitution is applied only
when a ``wmparc`` volume is supplied (FreeSurfer/FastSurfer), so the core routine
still works with any integer label volume + lookup table.

This module has no Qt / app dependencies on purpose: it is a self-contained,
testable function.
"""

from __future__ import annotations

import numpy as np

# Generic cerebral white-matter labels in aparc+aseg, replaced by wmparc detail.
_WM_LABELS = (2, 41)


def _cube_weight_kernel() -> np.ndarray:
    """3x3x3 kernel of 1 / Euclidean-distance-to-centre (centre = 1)."""
    k = np.zeros((3, 3, 3), dtype=np.float64)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for dk in (-1, 0, 1):
                dist = float(np.sqrt(di * di + dj * dj + dk * dk))
                k[di + 1, dj + 1, dk + 1] = 1.0 if dist == 0.0 else 1.0 / dist
    return k


_CUBE_WEIGHTS = _cube_weight_kernel()


def build_parcellation_volume(
    parc_data: np.ndarray,
    wmparc_data: np.ndarray | None = None,
) -> np.ndarray:
    """Return the labelling volume: aparc+aseg with WM (2/41) replaced by wmparc.

    ``wmparc_data`` must be on the exact same voxel grid as ``parc_data``. When it
    is ``None`` the parcellation is returned unchanged (generic mode).
    """
    vol = np.asarray(parc_data)
    if wmparc_data is None:
        return vol.astype(np.int64, copy=True)
    wm = np.asarray(wmparc_data)
    if wm.shape != vol.shape:
        raise ValueError(
            f"wmparc shape {wm.shape} does not match parcellation shape {vol.shape}"
        )
    out = vol.astype(np.int64, copy=True)
    mask = np.isin(out, _WM_LABELS)
    out[mask] = wm[mask].astype(np.int64)
    return out


def label_contact(
    ijk: tuple[float, float, float],
    parc_vol: np.ndarray,
    lut: dict[int, str] | None = None,
) -> list[tuple[str, float]]:
    """Label a single contact given its voxel index in ``parc_vol``.

    Returns a list of ``(region_name, weight)`` sorted by descending weight, the
    weights summing to 1. Returns ``[("unknown", 1.0)]`` if the cube is empty.
    """
    i, j, k = (int(round(float(c))) for c in ijk)

    # 3x3x3 cube, clipped defensively to the volume bounds (contacts are interior
    # in practice, so this virtually never triggers).
    i0, i1 = max(0, i - 1), min(parc_vol.shape[0], i + 2)
    j0, j1 = max(0, j - 1), min(parc_vol.shape[1], j + 2)
    k0, k1 = max(0, k - 1), min(parc_vol.shape[2], k + 2)
    cube = parc_vol[i0:i1, j0:j1, k0:k1]
    weights = _CUBE_WEIGHTS[
        i0 - (i - 1): i1 - (i - 1),
        j0 - (j - 1): j1 - (j - 1),
        k0 - (k - 1): k1 - (k - 1),
    ]
    if cube.size == 0:
        return [("unknown", 1.0)]

    labels = np.unique(cube)
    scored: list[tuple[int, float]] = []
    for lab in labels:
        w = float(weights[cube == lab].sum())
        if w > 0.0:
            scored.append((int(lab), w))
    if not scored:
        return [("unknown", 1.0)]

    total = sum(w for _, w in scored)
    scored.sort(key=lambda lw: lw[1], reverse=True)

    def name_of(idx: int) -> str:
        if lut is not None and idx in lut:
            entry = lut[idx]
            # NeuXelec LUTs map index -> (name, (r, g, b)); keep only the name.
            if isinstance(entry, (tuple, list)) and entry:
                return str(entry[0])
            return str(entry)
        return "unknown" if idx == 0 else f"label-{idx}"

    return [(name_of(idx), w / total) for idx, w in scored]


def seeg2parc(
    contacts_ijk,
    parc_data: np.ndarray,
    lut: dict[int, str] | None = None,
    wmparc_data: np.ndarray | None = None,
) -> list[list[tuple[str, float]]]:
    """Label every contact.

    Parameters
    ----------
    contacts_ijk : sequence of (i, j, k)
        Voxel indices of each contact in the parcellation volume's own grid
        (compute with ``inv(parc_affine) @ [x, y, z, 1]`` from world coordinates).
    parc_data : ndarray
        aparc+aseg integer label volume (nibabel data array).
    lut : dict[int, str], optional
        FreeSurfer-style index -> region name.
    wmparc_data : ndarray, optional
        wmparc volume on the same grid, for the WM (2/41) substitution.

    Returns
    -------
    list (per contact) of lists of (region_name, weight) sorted by weight.
    """
    parc_vol = build_parcellation_volume(parc_data, wmparc_data)
    return [label_contact(ijk, parc_vol, lut) for ijk in contacts_ijk]


def cube_label_weights(parc_vol: np.ndarray, ijk) -> list[tuple[int, float]]:
    """Return ``[(label, weight), ...]`` for the 3x3x3 weighted cube at ``ijk``.

    Weights are normalised to sum to 1 and sorted by descending weight. Same
    weighting as :func:`label_contact`, but keyed by integer label (name lookup
    is left to the caller). Useful for a UI breakdown / tooltip.
    """
    i, j, k = (int(round(float(c))) for c in ijk)
    i0, i1 = max(0, i - 1), min(parc_vol.shape[0], i + 2)
    j0, j1 = max(0, j - 1), min(parc_vol.shape[1], j + 2)
    k0, k1 = max(0, k - 1), min(parc_vol.shape[2], k + 2)
    cube = parc_vol[i0:i1, j0:j1, k0:k1]
    if cube.size == 0:
        return []
    weights = _CUBE_WEIGHTS[
        i0 - (i - 1): i1 - (i - 1),
        j0 - (j - 1): j1 - (j - 1),
        k0 - (k - 1): k1 - (k - 1),
    ]
    scored: list[tuple[int, float]] = []
    for lab in np.unique(cube):
        w = float(weights[cube == lab].sum())
        if w > 0.0:
            scored.append((int(lab), w))
    total = sum(w for _, w in scored)
    if total <= 0.0:
        return []
    scored.sort(key=lambda lw: lw[1], reverse=True)
    return [(lab, w / total) for lab, w in scored]


def region_confidence(parc_vol: np.ndarray, ijk, label: int) -> float:
    """Fraction (0..1) of the 3x3x3 weighted cube at ``ijk`` occupied by ``label``.

    This is the per-contact "confidence" that the contact belongs to ``label``,
    using the same inverse-distance weighting as :func:`label_contact`. Handy for
    a UI column next to the single-voxel region name.
    """
    i, j, k = (int(round(float(c))) for c in ijk)
    i0, i1 = max(0, i - 1), min(parc_vol.shape[0], i + 2)
    j0, j1 = max(0, j - 1), min(parc_vol.shape[1], j + 2)
    k0, k1 = max(0, k - 1), min(parc_vol.shape[2], k + 2)
    cube = parc_vol[i0:i1, j0:j1, k0:k1]
    if cube.size == 0:
        return 0.0
    weights = _CUBE_WEIGHTS[
        i0 - (i - 1): i1 - (i - 1),
        j0 - (j - 1): j1 - (j - 1),
        k0 - (k - 1): k1 - (k - 1),
    ]
    total = float(weights.sum())
    if total <= 0.0:
        return 0.0
    return float(weights[cube == label].sum()) / total


def world_to_voxel(points_world, affine: np.ndarray) -> np.ndarray:
    """Map (N,3) world coordinates to fractional voxel indices via inv(affine)."""
    pts = np.atleast_2d(np.asarray(points_world, dtype=np.float64))
    inv = np.linalg.inv(np.asarray(affine, dtype=np.float64))
    homog = np.c_[pts, np.ones(len(pts))]
    return (inv @ homog.T).T[:, :3]
