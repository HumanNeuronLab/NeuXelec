"""Display helpers for functional-MRI / statistical activation maps.

A functional map (t-map, z-map, %-signal-change, contrast) is not an anatomical
image: it is a small number of high-value clusters. Rendered as grayscale it
saturates to white ("white patches"). Here we compute robust display levels and
pick a colormap so the map can be shown as a *thresholded coloured overlay* on
the anatomy, the same way PET / SISCOM are.

The routine is deliberately parameter-free and robust: it decides on its own
whether the map is one-sided (positive activation -> ``hot``) or two-sided
(activation + deactivation -> a diverging colormap, symmetric threshold), and it
derives sensible threshold / max levels from percentiles so the user only has to
fine-tune afterwards with the sliders.
"""

from __future__ import annotations

import numpy as np

# Default colour scales of the fMRI overlay, shared by the 3D View and the
# Oblique Slice page so the map looks the same everywhere. Chosen to be distinct
# from the other overlays (PET "jet", SISCOM "hot", SPECT "inferno"/"turbo").
FMRI_DEFAULT_CMAP = "plasma"            # one-sided map (activation only)
FMRI_DEFAULT_CMAP_DIVERGING = "coolwarm"  # two-sided map (activation + deactivation)


def fmri_default_cmap(diverging: bool) -> str:
    return FMRI_DEFAULT_CMAP_DIVERGING if diverging else FMRI_DEFAULT_CMAP


# Minimum cluster size ("extent threshold", SPM's k / FSL cluster thresholding)
# offered in the right-click menus, in mm3 so it does not depend on the voxel
# size. 0 = off (every supra-threshold voxel is shown).
MIN_CLUSTER_CHOICES_MM3 = (0.0, 50.0, 100.0, 200.0, 500.0, 1000.0)


def min_cluster_label(mm3: float) -> str:
    v = float(mm3 or 0.0)
    return "Off" if v <= 0.0 else f"{int(round(v))} mm³"


def filter_small_clusters(arr: np.ndarray, threshold: float, min_voxels: int) -> np.ndarray:
    """Zero out supra-threshold clusters smaller than ``min_voxels``.

    Clusters are connected components (26-connectivity, like FSL) of the
    voxels with |value| >= ``threshold``. Voxels below the threshold are left
    untouched so the display threshold keeps behaving as before. Returns a new
    array (float32); the input is not modified.
    """
    from scipy import ndimage

    a = np.asarray(arr, dtype=np.float32)
    out = a.copy()
    if int(min_voxels) <= 1:
        return out
    supra = np.isfinite(a) & (np.abs(a) >= float(threshold))
    if not np.any(supra):
        return out
    lab, n = ndimage.label(supra, structure=np.ones((3, 3, 3), dtype=bool))
    if n == 0:
        return out
    sizes = np.bincount(lab.ravel())
    small_labels = np.where(sizes < int(min_voxels))[0]
    # Label 0 is the background (sub-threshold voxels): never touch it.
    small_labels = small_labels[small_labels != 0]
    if small_labels.size:
        out[np.isin(lab, small_labels)] = 0.0
    return out


def auto_fmri_levels(arr: np.ndarray, kind: str | None = None) -> dict:
    """Return robust display levels for a functional map.

    Parameters
    ----------
    arr : ndarray
        The functional-map voxel values (any shape).
    kind : str, optional
        ``"rgb_fusion"`` for an activation recovered from a scanner colour
        fusion (see ``utils.fmri_ingest``): the statistical threshold was
        already applied by the scanner, so every non-zero voxel is shown
        (threshold just above 0) and the ramp spans (0, 1].

    Returns
    -------
    dict with keys:
        ``diverging`` : bool   -- two-sided map (activation + deactivation)
        ``threshold`` : float  -- magnitude below which voxels are hidden
        ``vmax``      : float  -- magnitude mapped to the top of the colormap
        ``cmap``      : str    -- suggested matplotlib colormap name
    """
    a = np.asarray(arr, dtype=np.float32)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return {"diverging": False, "threshold": 0.0, "vmax": 1.0, "cmap": FMRI_DEFAULT_CMAP}

    # The "signal" is the non-zero population: a functional map is mostly a
    # zero (or near-zero) background with a few clusters. Judging the map on the
    # whole volume (millions of zeros) would swamp every percentile.
    nz = finite[np.abs(finite) > 1e-6]
    if nz.size == 0:
        return {"diverging": False, "threshold": 0.0, "vmax": 1.0, "cmap": FMRI_DEFAULT_CMAP}

    if kind == "rgb_fusion":
        diverging = bool(np.any(nz < 0))
        vmax = float(max(1.0, np.max(np.abs(nz))))
        # Colour-ramp values start at 0.05 (utils.fmri_ingest): a threshold
        # of 0.02 keeps every coloured voxel and excludes the zero background.
        return {
            "diverging": diverging,
            "threshold": 0.02,
            "vmax": vmax,
            "cmap": fmri_default_cmap(diverging),
        }

    pos = nz[nz > 0]
    neg = nz[nz < 0]
    pos_strength = float(np.percentile(pos, 99)) if pos.size else 0.0
    neg_strength = float(-np.percentile(neg, 1)) if neg.size else 0.0

    # Two-sided only when the negative side is a real, sizeable signal.
    diverging = (
        neg.size > 0.05 * nz.size
        and neg_strength > 0.30 * max(pos_strength, 1e-6)
    )

    if diverging:
        vmax = float(np.percentile(np.abs(nz), 99))
    else:
        vmax = float(np.percentile(pos if pos.size else np.abs(nz), 99))
    cmap = fmri_default_cmap(diverging)

    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    # Default threshold at ~35% of the display max: always leaves a visible
    # cluster, and the user raises/lowers it with the slider.
    thr = 0.35 * vmax
    return {"diverging": bool(diverging), "threshold": thr, "vmax": vmax, "cmap": cmap}
