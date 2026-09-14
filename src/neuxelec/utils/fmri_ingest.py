"""Classification and preparation of functional-MRI inputs.

Clinical fMRI reaches NeuXelec in very different shapes, and the display /
coregistration pipeline must know which one it is dealing with:

* ``stat_map``   : a scalar 3D statistical map (t / z / F, contrast, % signal
                   change) from SPM, FSL, AFNI, BrainVoyager, a scanner "t-Map"
                   series... This is the native case: threshold + colormap.
* ``rgb_fusion`` : a colour fusion exported by the scanner (Siemens syngo BOLD
                   "Fused" series, ImageType MPR COLOR FUSION; GE / Philips
                   equivalents): the thresholded activation is burned in colour
                   on a grey anatomical volume. No statistical value survives,
                   only "coloured or not" plus the position on the colour ramp.
                   The activation is recovered from the colour, the grey
                   anatomy is kept for the registration to the T1.
* ``bold_4d``    : a raw BOLD time series. It needs a first-level analysis
                   (GLM) that NeuXelec does not perform; the caller must refuse
                   it with a clear message.

The module is pure (SimpleITK + numpy + scipy) and GUI-free so it can be unit
tested on real exports.
"""
from __future__ import annotations

import numpy as np
import SimpleITK as sitk
from scipy import ndimage

KIND_STAT_MAP = "stat_map"
KIND_RGB_FUSION = "rgb_fusion"
KIND_BOLD_4D = "bold_4d"

# Shapes of the usual MNI templates (2 mm / 1 mm / 0.5-ish). A map with one of
# these shapes is most probably in template space, not in the patient's space.
_MNI_SHAPES = {(91, 109, 91), (182, 218, 182), (193, 229, 193)}

# NIfTI intent codes that identify a statistical map.
_NIFTI_INTENT_NAMES = {
    2: "correlation",
    3: "t statistic",
    4: "F statistic",
    5: "z score",
    6: "chi-square",
    22: "p value",
    23: "log p value",
    24: "log10 p value",
}

# A voxel is "coloured" when its RGB channels differ by more than this. Grey
# anatomy has R = G = B (chroma 0); the colour ramps used for activation are
# saturated (chroma close to 255). Anti-aliased overlay edges sit in between.
DEFAULT_CHROMA_MIN = 40.0


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def nifti_intent(img: sitk.Image) -> tuple[int, str | None]:
    """(intent_code, human name) read from the NIfTI header, (0, None) if absent."""
    try:
        code = int(float(img.GetMetaData("intent_code")))
    except Exception:
        return 0, None
    return code, _NIFTI_INTENT_NAMES.get(code)


def classify_fmri_image(img: sitk.Image) -> dict:
    """Describe an fMRI input image.

    Returns a dict:
        kind        : one of KIND_STAT_MAP / KIND_RGB_FUSION / KIND_BOLD_4D
        mni_like    : True when the grid looks like an MNI template grid
        intent      : NIfTI intent code (0 if none)
        intent_name : e.g. "t statistic", or None
        signed      : stat map only, True when negative values exist
        notes       : short human-readable remarks
    """
    notes: list[str] = []
    ncomp = int(img.GetNumberOfComponentsPerPixel())
    dim = int(img.GetDimension())
    size = tuple(int(s) for s in img.GetSize())

    pixel_type = img.GetPixelIDTypeAsString()
    if ncomp in (3, 4) and "8-bit" in pixel_type:
        # RGB / RGBA 8-bit vector volume: colour fusion exported by a scanner.
        kind = KIND_RGB_FUSION
        notes.append(f"RGB volume ({ncomp} channels): scanner colour fusion")
    elif ncomp > 1:
        # Multi-component non-colour data (time points stored as components).
        kind = KIND_BOLD_4D
        notes.append(f"multi-volume data ({ncomp} components)")
    elif dim == 4 and size[3] > 1:
        kind = KIND_BOLD_4D
        notes.append(f"4D time series ({size[3]} volumes)")
    else:
        kind = KIND_STAT_MAP

    intent, intent_name = nifti_intent(img)
    if intent_name:
        notes.append(f"NIfTI intent: {intent_name}")

    mni_like = tuple(size[:3]) in _MNI_SHAPES
    if mni_like:
        notes.append("grid matches an MNI template: the map may be in template space")

    signed = False
    if kind == KIND_STAT_MAP:
        try:
            arr = sitk.GetArrayViewFromImage(img)
            signed = bool(np.any(arr < 0))
        except Exception:
            signed = False

    return {
        "kind": kind,
        "mni_like": bool(mni_like),
        "intent": int(intent),
        "intent_name": intent_name,
        "signed": signed,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Colour fusion -> activation map + grey anatomy
# ---------------------------------------------------------------------------
def squeeze_to_3d(img: sitk.Image) -> sitk.Image:
    """Drop a trailing singleton 4th dimension (x, y, z, 1) if present."""
    if img.GetDimension() == 4 and img.GetSize()[3] == 1:
        return sitk.Extract(img, list(img.GetSize()[:3]) + [0], [0, 0, 0, 0])
    return img


def split_rgb_fusion(
    img_rgb: sitk.Image,
    chroma_min: float = DEFAULT_CHROMA_MIN,
    min_cluster_voxels: int = 1,
) -> tuple[sitk.Image, sitk.Image, dict]:
    """Separate a colour fusion into (activation, anatomy, info).

    activation : float32, same grid. 0 outside the coloured overlay; inside,
                 the position on the colour ramp, in (0, 1]: pure red -> ~0.05,
                 yellow / white -> 1. Cool colours (blue -> cyan), used by some
                 vendors for deactivation, give the same ramp with a NEGATIVE
                 sign. These are RELATIVE units: the statistical threshold was
                 applied by the scanner before export and is not recoverable.
    anatomy    : float32 luminance (mean of R, G, B), used as the moving image
                 for the registration to the T1 (the fusion background is the
                 patient's own anatomical scan).
    info       : voxel / cluster counts for the user report.
    """
    if img_rgb.GetNumberOfComponentsPerPixel() < 3:
        raise ValueError("split_rgb_fusion expects an RGB (vector) image")
    # A DICOM series reader returns (x, y, z, 1) for a single multi-frame file.
    img_rgb = squeeze_to_3d(img_rgb)

    arr = sitk.GetArrayFromImage(img_rgb).astype(np.float32)  # (z, y, x, c)
    if arr.shape[-1] > 3:
        arr = arr[..., :3]
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(axis=-1)
    chroma = mx - arr.min(axis=-1)
    coloured = chroma > float(chroma_min)

    # Warm ramp (red -> yellow -> white): red dominant, blue lowest.
    warm = coloured & (r >= g) & (r > b)
    # Cool ramp (blue -> cyan): blue dominant. Some vendors use it for
    # deactivation / negative contrasts.
    cool = coloured & (b > r)
    # Green-dominant colours are not part of either standard ramp; keep them
    # as (weak) positive activation rather than dropping them silently.
    other = coloured & ~warm & ~cool

    # Position on the ramp = secondary channel over the dominant one:
    # red (255,0,0) -> 0, yellow (255,255,0) -> 1 ; blue (0,0,255) -> 0,
    # cyan (0,255,255) -> 1.
    level = np.clip(g / np.maximum(mx, 1.0), 0.0, 1.0)
    act = np.zeros(mx.shape, dtype=np.float32)
    act[warm] = 0.05 + 0.95 * level[warm]
    act[other] = 0.05 + 0.95 * level[other]
    act[cool] = -(0.05 + 0.95 * level[cool])

    n_clusters = 0
    largest = 0
    if np.any(coloured):
        lab, n_clusters = ndimage.label(act != 0)
        if n_clusters:
            sizes = ndimage.sum(np.ones_like(act, dtype=np.float32), lab, range(1, n_clusters + 1))
            sizes = np.asarray(sizes, dtype=np.int64)
            largest = int(sizes.max())
            if int(min_cluster_voxels) > 1:
                small = np.isin(lab, np.where(sizes < int(min_cluster_voxels))[0] + 1)
                act[small] = 0.0
                n_clusters = int(np.sum(sizes >= int(min_cluster_voxels)))

    anatomy = arr.mean(axis=-1).astype(np.float32)

    act_img = sitk.GetImageFromArray(act)
    act_img.CopyInformation(img_rgb)
    anat_img = sitk.GetImageFromArray(anatomy)
    anat_img.CopyInformation(img_rgb)

    info = {
        "n_coloured": int(coloured.sum()),
        "n_positive": int(np.sum(act > 0)),
        "n_negative": int(np.sum(act < 0)),
        "n_clusters": int(n_clusters),
        "largest_cluster_voxels": int(largest),
        "voxel_volume_mm3": float(np.prod(img_rgb.GetSpacing())),
        "chroma_min": float(chroma_min),
    }
    return act_img, anat_img, info
