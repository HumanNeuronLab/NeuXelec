from __future__ import annotations

"""
Unified image ingestion / sanitizing for NeuXelec.

Whatever the input format (NIfTI .nii / .nii.gz, FreeSurfer .mgz / .mgh, or an
already-converted DICOM series), every image entering NeuXelec is cleaned so it
behaves predictably downstream:

  * **per-modality intensity sanitizing**. For CT this clamps to the valid
    Hounsfield range: raw clinical CTs routinely carry padding values
    (e.g. -8192) and metal/saturation spikes (e.g. 57343 HU) that corrupt the
    ANTs coregistration metric, a common cause of a "very bad" CT->T1 alignment;
  * optional 1 mm isotropic spacing for the T1 reference.

Voxel ORIENTATION is deliberately left untouched: NeuXelec's viewers
(reconstruction, check-coregistration) are calibrated to the orientation of the
images as loaded, and reorienting the stored voxel grid flips their left/right
handling. A `reorient_to_canonical` helper exists for a future display-only use
but is NOT applied on load. Isotropic resampling preserves physical (world)
coordinates; intensity clamping changes voxel values on purpose, only for the
modalities that need it.

The pure functions here (`read_image_any`, `normalize_image`, ...) are GUI-free
and unit-testable. `ingest_image_with_prompt` wraps them and, whenever a change
was applied, asks the user where to save the cleaned copy so that copy becomes
the file NeuXelec actually uses.
"""

import logging
from pathlib import Path

import numpy as np
import SimpleITK as sitk

logger = logging.getLogger(__name__)

# NeuXelec's viewers (reconstruction + check-coregistration) assume voxel data
# in RAS orientation: array axis 0 (i / ix) increases toward the patient's Right,
# axis 2 (k) toward Superior. Both the axial/coronal plane assignment and the
# L/R side markers are built on that assumption, so RAS is the canonical space
# every image is brought into. (Physical world coordinates remain LPS, as always
# in SimpleITK, so exported millimetre coordinates are unaffected.)
CANONICAL_ORIENTATION = "RAS"

# Valid Hounsfield window for CT. Air ~ -1000, water = 0, dense bone ~ +2000,
# hard upper bound kept at +3071 (12-bit CT convention). Anything outside is
# padding / metal saturation and is clamped.
CT_HU_MIN = -1024.0
CT_HU_MAX = 3071.0

DEFAULT_TARGET_SPACING = (1.0, 1.0, 1.0)
SPACING_TOLERANCE = 1e-3

# Modality groups (case-insensitive keys).
_CT_MODS = {"CT"}
_MRI_MODS = {"T1", "T2", "MRI", "MR"}
_FUNC_MODS = {"PET", "ICTALSPECT", "INTERICTALSPECT", "SPECT", "SISCOM"}


# ---------------------------------------------------------------------------
# Reading (format-agnostic)
# ---------------------------------------------------------------------------
def read_image_any(path: str | Path) -> sitk.Image:
    """Read an image in any NeuXelec-supported format as a SimpleITK image.

    * .nii / .nii.gz and other ITK-native formats: read directly.
    * .mgz / .mgh (FreeSurfer / FastSurfer): read with nibabel and converted to
      a SimpleITK image with a correct LPS physical space (SimpleITK has no MGH
      reader).

    DICOM folders are expected to have been converted to NIfTI upstream.
    """
    p = Path(path)
    name = p.name.lower()
    if name.endswith(".mgz") or name.endswith(".mgh"):
        return _read_mgh_as_sitk(p)
    return sitk.ReadImage(str(p))


def _read_mgh_as_sitk(p: Path) -> sitk.Image:
    """Convert a FreeSurfer MGH/MGZ volume to a SimpleITK image (LPS space).

    nibabel affines are voxel -> RAS millimetres; SimpleITK works in LPS, so the
    first two axes (R, A) are negated to obtain (L, P, S).
    """
    import nibabel as nib

    n = nib.load(str(p))
    data = np.asanyarray(n.dataobj)
    if data.ndim == 4:
        data = data[..., 0]
    # nibabel data is (i, j, k); SimpleITK GetImageFromArray wants (k, j, i).
    arr = np.ascontiguousarray(np.transpose(data, (2, 1, 0)))
    img = sitk.GetImageFromArray(arr)

    aff = np.asarray(n.affine, dtype=np.float64)
    ras2lps = np.diag([-1.0, -1.0, 1.0])
    aff_lps = aff.copy()
    aff_lps[:3, :3] = ras2lps @ aff[:3, :3]
    aff_lps[:3, 3] = ras2lps @ aff[:3, 3]

    spacing = np.linalg.norm(aff_lps[:3, :3], axis=0)
    spacing[spacing == 0] = 1.0
    direction = aff_lps[:3, :3] / spacing

    img.SetSpacing(tuple(float(s) for s in spacing))
    img.SetOrigin(tuple(float(o) for o in aff_lps[:3, 3]))
    img.SetDirection(tuple(float(v) for v in direction.flatten(order="C")))
    return img


# ---------------------------------------------------------------------------
# Orientation
# ---------------------------------------------------------------------------
def orientation_code(img: sitk.Image) -> str:
    """Return the 3-letter orientation code (e.g. 'LPS', 'LIP') of an image."""
    try:
        return sitk.DICOMOrientImageFilter_GetOrientationFromDirectionCosines(
            img.GetDirection()
        )
    except Exception:
        return "???"


def reorient_to_canonical(img: sitk.Image) -> sitk.Image:
    """Reorient to the canonical orientation (RAS). Pure axis permutation/flip:
    no interpolation, physical coordinates preserved. Safe for intensity images
    and label maps."""
    return sitk.DICOMOrient(img, CANONICAL_ORIENTATION)


# ---------------------------------------------------------------------------
# Intensity sanitizing (per modality)
# ---------------------------------------------------------------------------
def _modality_group(modality: str) -> str:
    m = (modality or "").upper().replace(" ", "").replace("_", "").replace("-", "")
    if m in _CT_MODS:
        return "CT"
    if m in _MRI_MODS:
        return "MRI"
    if m in _FUNC_MODS:
        return "FUNC"
    return "OTHER"


def sanitize_intensities(img: sitk.Image, modality: str) -> tuple[sitk.Image, str | None]:
    """Sanitize voxel intensities according to modality.

    Returns (image, note) where note is a short human-readable description of
    what changed, or None if nothing was modified.

      * CT   -> clamp to the valid Hounsfield window [-1024, 3071].
      * MRI  -> replace non-finite values; clip negative magnitudes to 0.
      * FUNC -> replace non-finite values only (functional units are arbitrary).
    """
    group = _modality_group(modality)
    arr = sitk.GetArrayFromImage(img).astype(np.float32)
    before = arr.copy()
    note = None

    nonfinite = ~np.isfinite(arr)
    if nonfinite.any():
        arr[nonfinite] = 0.0

    if group == "CT":
        lo = float(np.sum(arr < CT_HU_MIN))
        hi = float(np.sum(arr > CT_HU_MAX))
        np.clip(arr, CT_HU_MIN, CT_HU_MAX, out=arr)
        if lo or hi or nonfinite.any():
            note = (
                f"CT intensities clamped to [{int(CT_HU_MIN)}, {int(CT_HU_MAX)}] HU "
                f"({int(lo)} low + {int(hi)} high voxels)"
            )
    elif group == "MRI":
        neg = float(np.sum(arr < 0.0))
        if neg:
            np.clip(arr, 0.0, None, out=arr)
        if neg or nonfinite.any():
            note = "MRI: non-finite/negative voxels cleaned"
    else:  # FUNC / OTHER
        if nonfinite.any():
            note = "non-finite voxels cleaned"

    if note is None and np.array_equal(before, arr):
        return img, None

    out = sitk.GetImageFromArray(arr)
    out.CopyInformation(img)
    return out, note


# ---------------------------------------------------------------------------
# Spacing (optional isotropic)
# ---------------------------------------------------------------------------
def is_isotropic_1mm(img: sitk.Image, tol: float = SPACING_TOLERANCE) -> bool:
    return all(abs(float(s) - 1.0) <= tol for s in img.GetSpacing())


def resample_to_spacing(
    img: sitk.Image,
    target_spacing: tuple[float, float, float] = DEFAULT_TARGET_SPACING,
    is_label: bool = False,
) -> sitk.Image:
    """Resample to an isotropic spacing, preserving the physical field of view.
    Nearest-neighbour for label maps, linear otherwise."""
    old_size = np.asarray(img.GetSize(), dtype=np.float64)
    old_spacing = np.asarray(img.GetSpacing(), dtype=np.float64)
    new_spacing = np.asarray(target_spacing, dtype=np.float64)
    new_size = np.maximum(np.round(old_size * old_spacing / new_spacing), 1).astype(int)

    r = sitk.ResampleImageFilter()
    r.SetOutputSpacing(tuple(float(v) for v in new_spacing))
    r.SetSize([int(v) for v in new_size])
    r.SetOutputOrigin(img.GetOrigin())
    r.SetOutputDirection(img.GetDirection())
    r.SetTransform(sitk.Transform(3, sitk.sitkIdentity))
    r.SetInterpolator(sitk.sitkNearestNeighbor if is_label else sitk.sitkLinear)
    r.SetDefaultPixelValue(0.0)
    r.SetOutputPixelType(img.GetPixelID())
    return r.Execute(img)


# ---------------------------------------------------------------------------
# High-level normalization (pure)
# ---------------------------------------------------------------------------
def normalize_image(
    img: sitk.Image,
    modality: str,
    make_isotropic: bool = False,
    is_label: bool = False,
) -> tuple[sitk.Image, list[str]]:
    """Bring an image into NeuXelec's canonical space.

    Returns (normalized_image, changes) where `changes` is a list of short
    human-readable descriptions. An empty list means the image was already
    canonical and needed no modification.
    """
    changes: list[str] = []

    # Reorient to the canonical orientation NeuXelec's viewers are built around
    # (RAS: ix -> patient Right, 3rd axis -> Superior). A correctly-oriented
    # study such as PAT_6980 is already RAS and passes through unchanged; a
    # non-canonical study such as EL046 (LIP) is brought into the same frame so
    # it displays identically. Pure axis permutation/flip, physical coordinates
    # preserved.
    src_orient = orientation_code(img)
    if src_orient != CANONICAL_ORIENTATION:
        img = reorient_to_canonical(img)
        changes.append(f"reoriented {src_orient} -> {CANONICAL_ORIENTATION}")

    if not is_label:
        img, note = sanitize_intensities(img, modality)
        if note:
            changes.append(note)

    if make_isotropic and not is_isotropic_1mm(img):
        old = tuple(round(float(s), 3) for s in img.GetSpacing())
        img = resample_to_spacing(img, DEFAULT_TARGET_SPACING, is_label=is_label)
        changes.append(f"resampled {old} -> 1x1x1 mm")

    return img, changes


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------
def suggest_normalized_path(input_path: str | Path) -> str:
    """Suggest '<stem>_neuxelec.nii.gz' next to the input file."""
    p = Path(input_path)
    name = p.name
    for ext in (".nii.gz", ".nii", ".mgz", ".mgh"):
        if name.lower().endswith(ext):
            stem = name[: -len(ext)]
            return str(p.with_name(f"{stem}_neuxelec.nii.gz"))
    return str(p.with_name(f"{p.stem}_neuxelec.nii.gz"))


# ---------------------------------------------------------------------------
# High-level ingestion with GUI save prompt
# ---------------------------------------------------------------------------
def ingest_image_with_prompt(
    path: str | Path,
    modality: str,
    parent=None,
    make_isotropic: bool = False,
    is_label: bool = False,
) -> tuple[str, sitk.Image, dict]:
    """Read `path`, normalize it, and return (final_path, image, info).

    If normalization changed anything, the user is asked where to save the
    normalized copy (defaulting to '<stem>_neuxelec.nii.gz' next to the source).
    The saved copy becomes the file NeuXelec uses, so every modality ends up in
    the same clean, canonical space. If the user cancels the save dialog, the
    copy is written next to the source automatically so the pipeline never falls
    back to a mis-oriented / unclamped image.

    info keys: changes (list[str]), original_path, final_path,
    original_orientation, final_orientation, original_spacing, final_spacing,
    was_modified (bool).
    """
    from PySide6.QtWidgets import QFileDialog

    from ..ui.neuxelec_message_dialog import NeuXelecMessageDialog

    src_img = read_image_any(path)
    src_orient = orientation_code(src_img)
    src_spacing = [float(s) for s in src_img.GetSpacing()]

    norm_img, changes = normalize_image(
        src_img, modality, make_isotropic=make_isotropic, is_label=is_label
    )

    info = {
        "changes": changes,
        "original_path": str(path),
        "final_path": str(path),
        "original_orientation": src_orient,
        "final_orientation": orientation_code(norm_img),
        "original_spacing": src_spacing,
        "final_spacing": [float(s) for s in norm_img.GetSpacing()],
        "was_modified": bool(changes),
    }

    if not changes:
        return str(path), src_img, info

    summary = "\n".join(f"  • {c}" for c in changes)
    suggested = suggest_normalized_path(path)
    out_path, _ = QFileDialog.getSaveFileName(
        parent,
        f"Save normalized {modality}",
        suggested,
        "NIfTI image (*.nii.gz *.nii);;All files (*)",
    )
    if not out_path:
        # User cancelled: still persist next to the source so the alignment /
        # display fix is not silently lost.
        out_path = suggested

    if not out_path.lower().endswith((".nii", ".nii.gz")):
        out_path += ".nii.gz"

    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(norm_img, out_path)
    except Exception as e:  # pragma: no cover - disk/permission failure
        NeuXelecMessageDialog.critical(
            parent,
            f"{modality} normalization failed",
            f"The normalized {modality} could not be saved:\n\n{e}",
        )
        # Fall back to the in-memory normalized image with the original path.
        return str(path), norm_img, info

    info["final_path"] = str(out_path)
    NeuXelecMessageDialog.information(
        parent,
        f"{modality} normalized",
        (
            f"The loaded {modality} was brought into NeuXelec's canonical space "
            "so it stays aligned with the other images:\n\n"
            f"{summary}\n\n"
            f"Saved as:\n{out_path}"
        ),
    )
    return str(out_path), norm_img, info
