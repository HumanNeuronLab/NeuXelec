"""The files one modality has left behind, from the import to the save.

A CT goes through four states before it is of any use: the DICOM folder
it arrived in, the NIfTI written when that folder was converted, the
cleaned copy NeuXelec reads, and the volume resampled into MRI 1 that
the user saves at the end. Only the last one is needed afterwards, and
the other three sit in the patient folder for ever.

So, at the moment the last one is written, this module answers one
question: what else of this modality is on disk, and how big is it. The
window built on top lets the user tick what to remove, and nothing is
ticked for them: these are their files, including the DICOM.

WHAT HAPPENS TO THE PROJECT

Deleting the import would leave the project pointing at files that are
gone, and NeuXelec would ask for them at the next opening. So the
modality is pointed at the volume that was just saved, which is a
perfectly good image of that modality, already in the space of MRI 1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

#: Ce que chaque modalite retient, dans l'ordre de la chaine.
#:   (champ de l'etat, ce que c'est, en une ligne)
CHAIN_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "T2": (
        ("t2_source_path", "what you imported"),
        ("t2_path", "the copy NeuXelec reads"),
        ("t2_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "fMRI": (
        ("fmri_source_path", "what you imported"),
        ("fmri_path", "the copy NeuXelec reads"),
        ("fmri_reg_path", "the grey anatomy recovered from the colour fusion"),
        ("fmri_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "CT": (
        ("ct_source_path", "what you imported"),
        ("ct_path", "the copy NeuXelec reads"),
        ("ct_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "PET": (
        ("pet_source_path", "what you imported"),
        ("pet_path", "the copy NeuXelec reads"),
        ("pet_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "ictalSPECT": (
        ("ictal_spect_source_path", "what you imported"),
        ("ictal_spect_path", "the copy NeuXelec reads"),
        ("ictal_spect_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "interictalSPECT": (
        ("interictal_spect_source_path", "what you imported"),
        ("interictal_spect_path", "the copy NeuXelec reads"),
        ("interictal_spect_coreg_path", "an earlier volume aligned on MRI 1"),
    ),
    "SISCOM": (
        ("siscom_path", "the SISCOM map"),
        ("siscom_coreg_path", "an earlier SISCOM aligned on MRI 1"),
    ),
    "brainmask": (
        ("brainmask_path", "the mask you loaded"),
        ("brainmask_generated_path", "the mask NeuXelec computed"),
    ),
}

#: Le champ qui recoit le fichier garde, une fois le reste efface.
KEEPER_FIELDS: dict[str, tuple[str, ...]] = {
    "T2": ("t2_path", "t2_source_path"),
    "fMRI": ("fmri_path", "fmri_source_path"),
    "CT": ("ct_path", "ct_source_path"),
    "PET": ("pet_path", "pet_source_path"),
    "ictalSPECT": ("ictal_spect_path", "ictal_spect_source_path"),
    "interictalSPECT": ("interictal_spect_path", "interictal_spect_source_path"),
    "SISCOM": ("siscom_path",),
    "brainmask": ("brainmask_path",),
}


@dataclass
class ChainFile:
    """One file of the chain, and what is known about it."""

    path: Path
    size: int
    label: str
    fields: list[str] = field(default_factory=list)
    is_folder: bool = False
    file_count: int = 1

    @property
    def name(self) -> str:
        return self.path.name


def _normalise(path) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return str(path)


def folder_weight(folder) -> tuple[int, int]:
    """(bytes, files) of a folder, walked once."""
    octets = 0
    combien = 0
    for parent, _dirs, names in os.walk(str(folder)):
        for name in names:
            try:
                octets += os.path.getsize(os.path.join(parent, name))
                combien += 1
            except OSError:
                continue
    return octets, combien


def converted_nifti(state, modality: str) -> str | None:
    """The NIfTI written when a DICOM folder was converted, if any."""
    table = getattr(state, "converted_nifti_by_role", None)
    if isinstance(table, dict):
        value = table.get(str(modality))
        if isinstance(value, str) and value.strip():
            return value
    return None


def chain_for(modality: str, state, keep=None) -> list[ChainFile]:
    """Everything of this modality that is on disk, except what is kept.

    The order is the order of the pipeline, so the list reads like the
    history of the modality. A file named by two fields appears once,
    with both names recorded, because deleting it has to clear both.
    """
    keep_key = _normalise(keep) if keep else None
    out: list[ChainFile] = []
    seen: dict[str, ChainFile] = {}

    entries: list[tuple[str | None, str, str]] = []
    for champ, libelle in CHAIN_FIELDS.get(str(modality), ()):
        entries.append((champ, getattr(state, champ, None), libelle))

    nifti = converted_nifti(state, modality)
    if nifti:
        # Juste apres l'import: c'est la sortie de la conversion DICOM.
        entries.insert(1, (None, nifti, "the NIfTI written when converting that DICOM"))

    for champ, valeur, libelle in entries:
        if not isinstance(valeur, str) or not valeur.strip():
            continue

        p = Path(valeur)
        key = _normalise(p)
        if keep_key and key == keep_key:
            continue

        if key in seen:
            if champ and champ not in seen[key].fields:
                seen[key].fields.append(champ)
            continue

        if not p.exists():
            continue

        if p.is_dir():
            octets, combien = folder_weight(p)
            fichier = ChainFile(p, octets, libelle, [], True, combien)
        else:
            try:
                octets = p.stat().st_size
            except OSError:
                continue
            fichier = ChainFile(p, octets, libelle)

        if champ:
            fichier.fields.append(champ)

        seen[key] = fichier
        out.append(fichier)

    return out


def human_size(n: int) -> str:
    """A size a human reads, not a number of bytes."""
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def send_to_recycle_bin(path) -> bool:
    """Delete through the Windows recycle bin, so it can be taken back.

    Returns False when the recycle bin is not available, and deletes
    nothing in that case: the caller then says so rather than quietly
    erasing a file for good.
    """
    if os.name != "nt":
        return False

    try:
        import ctypes
        from ctypes import wintypes

        class _SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        operation = _SHFILEOPSTRUCTW()
        operation.wFunc = FO_DELETE
        # L'API veut la liste terminee par deux zeros.
        operation.pFrom = str(Path(path).resolve()) + "\0\0"
        operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

        code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        return code == 0 and not operation.fAnyOperationsAborted
    except Exception:
        return False


def _delete(path, use_recycle_bin: bool) -> tuple[bool, bool]:
    """(done, through the recycle bin)."""
    if use_recycle_bin and send_to_recycle_bin(path):
        return True, True

    import shutil

    p = Path(path)
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return True, False


def delete_chosen(
    chosen,
    state,
    modality: str,
    keep,
    use_recycle_bin: bool = True,
) -> dict:
    """Remove the chosen files, then leave the project coherent.

    Every field that named a deleted file is cleared, and the modality is
    pointed at ``keep``, the volume just saved: a project reopened after
    this finds an image where it expects one, instead of asking for files
    that are gone.
    """
    report = {
        "deleted": [],
        "failed": [],
        "bytes": 0,
        "recycle_bin": False,
        "fields": [],
    }

    efface: set[str] = set()

    for fichier in chosen:
        try:
            _done, corbeille = _delete(fichier.path, use_recycle_bin)
        except Exception as e:
            report["failed"].append((str(fichier.path), str(e)))
            continue
        report["deleted"].append(str(fichier.path))
        report["bytes"] += int(fichier.size)
        report["recycle_bin"] = report["recycle_bin"] or corbeille
        efface.update(fichier.fields)

    if not report["deleted"]:
        return report

    for champ in sorted(efface):
        if hasattr(state, champ):
            setattr(state, champ, None)
            report["fields"].append(champ)

    if keep:
        for champ in KEEPER_FIELDS.get(str(modality), ()):
            if getattr(state, champ, None) is None:
                setattr(state, champ, str(keep))
                if champ not in report["fields"]:
                    report["fields"].append(champ)

    return report
