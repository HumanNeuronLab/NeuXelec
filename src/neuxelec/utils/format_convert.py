from __future__ import annotations

from pathlib import Path

import nibabel as nib
import SimpleITK as sitk


def _reorient_sitk(img: sitk.Image, orient: str = "RAS") -> sitk.Image:
    """
    Reorient image to a canonical orientation (RAS recommended for neuro tools).
    This avoids left/right or anterior/posterior flips when mixing DICOM and NIfTI.
    """
    try:
        return sitk.DICOMOrient(img, orient)
    except Exception:
        # If orientation fails for any reason, keep original
        return img


#: How deep we look for a series when the chosen folder holds none itself.
#: A clinical export nests at most patient / study / series, so three levels
#: are enough, and the cap stops a mis-click on a whole drive from walking it.
_DICOM_SEARCH_DEPTH = 3


def _subdirectories(root: Path, depth: int) -> list[Path]:
    """Directories under ``root``, breadth first, down to ``depth`` levels."""
    out: list[Path] = []
    level = [root]
    for _ in range(depth):
        nxt: list[Path] = []
        for d in level:
            try:
                nxt.extend(sorted(p for p in d.iterdir() if p.is_dir()))
            except OSError:
                continue
        if not nxt:
            break
        out.extend(nxt)
        level = nxt
    return out


def find_dicom_series(dicom_folder: str) -> list[tuple[str, str]]:
    """Every DICOM series reachable from ``dicom_folder``, as (directory, series id).

    The folder itself is looked at first and the search stops there as soon as
    it holds a series, so a folder that already worked keeps behaving exactly
    as it did.

    Only when it holds none do we descend. A clinical export is handed over as
    ``PAT_xxx/DICOM/SERIE_1/*.dcm`` and pointing at ``PAT_xxx`` is the natural
    thing to do, yet GetGDCMSeriesIDs has no recursive mode at all, unlike
    GetGDCMSeriesFileNames, and simply reports nothing.

    ITK prints "No Series were found" from C++ for every directory without
    DICOM in it, which would be one warning per folder walked, so its warnings
    are silenced for the duration of the scan and restored afterwards.
    """
    reader = sitk.ImageSeriesReader()
    root = Path(dicom_folder)

    display = sitk.ProcessObject.GetGlobalWarningDisplay()
    sitk.ProcessObject.SetGlobalWarningDisplay(False)
    try:
        found = [(str(root), sid) for sid in reader.GetGDCMSeriesIDs(str(root))]
        if found:
            return found
        for sub in _subdirectories(root, _DICOM_SEARCH_DEPTH):
            found.extend((str(sub), sid) for sid in reader.GetGDCMSeriesIDs(str(sub)))
        return found
    finally:
        sitk.ProcessObject.SetGlobalWarningDisplay(display)


def _series_label(directory: str, series_id: str) -> str:
    """One line describing a series, for the message asking which one to take."""
    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(directory, series_id)
    name = ""
    if files:
        r = sitk.ImageFileReader()
        r.SetFileName(files[0])
        r.LoadPrivateTagsOff()
        try:
            r.ReadImageInformation()
            for key in ("0008|103e", "0018|1030"):  # SeriesDescription, ProtocolName
                if r.HasMetaDataKey(key) and r.GetMetaData(key).strip():
                    name = r.GetMetaData(key).strip()
                    break
        except Exception:
            pass
    return "%s, %d slices, in %s" % (name or "unnamed series", len(files), directory)


def convert_dicom_folder_to_nifti(dicom_folder: str, out_nifti_path: str) -> str:
    """
    Convert a DICOM series folder to NIfTI (.nii/.nii.gz) using SimpleITK.
    Returns the output path.
    """
    dicom_folder = str(Path(dicom_folder))
    out_nifti_path = str(out_nifti_path)

    series = find_dicom_series(dicom_folder)
    if not series:
        raise RuntimeError("No DICOM series found in the selected folder.")

    directory, series_id = series[0]

    # Several series at the top level keep the historical behaviour, the first
    # one. Several series found by descending is a different matter: those are
    # separate acquisitions, and guessing would quietly load a localizer where
    # a T1 was meant. Name them and let the user point at one.
    if len(series) > 1 and directory != dicom_folder:
        shown = [_series_label(d, s) for d, s in series[:12]]
        listing = "\n".join("  - " + s for s in shown)
        if len(series) > 12:
            listing += "\n  - ... and %d more" % (len(series) - 12)
        raise RuntimeError(
            "This folder holds no DICOM series itself, and several were found "
            "in its subfolders. Select the subfolder of the one you want:\n\n" + listing
        )

    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(reader.GetGDCMSeriesFileNames(directory, series_id))

    img = reader.Execute()
    img = _reorient_sitk(img, "RAS")  # ✅ important
    sitk.WriteImage(img, out_nifti_path)
    return out_nifti_path


def convert_mgz_to_nifti(mgz_path: str, out_nifti_path: str) -> str:
    """
    Convert FreeSurfer .mgz/.mgh to NIfTI (.nii/.nii.gz) using nibabel.

    IMPORTANT:
      FreeSurfer volumes can come in a different orientation than typical neuro NIfTI.
      We reorient to a canonical orientation to avoid flips in downstream viewers.
    """
    mgz_path = str(mgz_path)
    out_nifti_path = str(out_nifti_path)

    img = nib.load(mgz_path)  # supports .mgz and .mgh

    # ✅ Make orientation canonical (RAS-like in nibabel terminology)
    img = nib.as_closest_canonical(img)

    # ✅ Ensure qform/sform are set (some tools behave better with both)
    try:
        affine = img.affine
        img.set_qform(affine, code=1)
        img.set_sform(affine, code=1)
    except Exception:
        pass

    nib.save(img, out_nifti_path)
    return out_nifti_path


def convert_to_nifti_if_needed(
    input_path: str,
    parent=None,
    output_path: str | None = None,
) -> str:
    """Convert DICOM folder or .mgz/.mgh to NIfTI and return the NIfTI path.

    Rules:
      - If input_path is already NIfTI (.nii / .nii.gz), it is returned as-is.
      - If it is a directory, it is treated as a DICOM folder.
      - If it is .mgz/.mgh, it is treated as a FreeSurfer volume.
      - If it is a single DICOM file (.dcm/.ima), we do a best-effort conversion.

    If output_path is provided, the conversion is saved there without opening
    a save dialog. This is useful for bulk DICOM import.
    """
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    # Already NIfTI
    if p.is_file() and (p.name.endswith(".nii") or p.name.endswith(".nii.gz")):
        return str(p)

    def _normalize_nifti_output_path(path_like: str) -> str:
        out = str(path_like)

        # Keep .nii.gz unchanged
        if out.endswith(".nii.gz"):
            return out

        # Keep .nii unchanged
        if out.endswith(".nii"):
            return out

        # Otherwise default to .nii.gz
        return out + ".nii.gz"

    # If no output path was provided, keep the old behavior:
    # ask the user where to save this converted file.
    if output_path is None:
        from PySide6.QtWidgets import QFileDialog

        source_dir = p.parent if p.is_file() else p
        default_name = (p.stem + ".nii.gz") if p.is_file() else (p.name + ".nii.gz")
        default_path = str(source_dir / default_name)

        dialog_options = QFileDialog.Options()

        output_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Save converted NIfTI",
            default_path,
            "NIfTI (*.nii.gz *.nii);;All files (*.*)",
            options=dialog_options,
        )

        if not output_path:
            raise RuntimeError("Conversion cancelled by user.")

    out_path = _normalize_nifti_output_path(str(output_path))

    if p.is_dir():
        return convert_dicom_folder_to_nifti(str(p), out_path)

    if p.suffix.lower() in {".mgz", ".mgh"}:
        return convert_mgz_to_nifti(str(p), out_path)

    if p.suffix.lower() in {".dcm", ".ima"}:
        img = sitk.ReadImage(str(p))
        img = _reorient_sitk(img, "RAS")
        sitk.WriteImage(img, out_path)
        return out_path

    return str(p)
