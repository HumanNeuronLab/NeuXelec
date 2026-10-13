"""Sort out what a patient folder holds, so it can be made readable again.

A single modality leaves four files behind: the DICOM folder it came from,
the NIfTI of that conversion, the cleaned ``_neuxelec`` copy, and the
volume written after the coregistration. Times seven modalities, plus the
ANTs transforms, the brain mask and the defacing, and the folder is no
longer readable.

WHAT DECIDES THAT A FILE IS NOT YOURS

An allow-list, never the opposite. A file belongs to NeuXelec only when
its name matches something NeuXelec is known to write, or when the
project records it as something NeuXelec produced. Everything else is
yours and is reported as untouchable, including every DICOM folder,
every image you imported and every FreeSurfer output.

That direction matters. A deny-list ("delete what looks useless") would
grow a hole the first time someone stores a file we did not think of. An
allow-list can only ever be incomplete, and being incomplete here means
proposing to tidy less than we could, which is the harmless failure.

THREE OUTCOMES

``SOURCE``   yours: shown with its size so the volume is explained, never
             moved, never deleted, not selectable.
``USED``     produced by NeuXelec, and the project still points at it:
             it can be moved into a subfolder, and the paths follow.
WHERE THE ALLOW-LIST FALLS SHORT, ON PURPOSE

The name of a coregistered volume is typed by the user in the save
dialog, so nothing in it says NeuXelec wrote it. Such a file is only
recognised while the project still points at it. Once the project has
forgotten it, because the registration was run again and saved
elsewhere, it is reported as yours and left alone. That is the harmless
direction: tidying less than we could has never lost anyone a file.

``ORPHAN``   produced by NeuXelec, and nothing points at it any more:
             a superseded ANTs output, the result of a registration that
             was run again. This is the only thing deletion is offered
             for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SOURCE = "source"
USED = "used"
ORPHAN = "orphan"

#: Suffixes NeuXelec writes next to the images it is given.
PRODUCED_SUFFIXES = (
    "_neuxelec.nii.gz",
    "_1mm_iso.nii.gz",
    "_activation.nii.gz",
    "_anatomy.nii.gz",
    "_3d.nii.gz",
    "_to_T1_Applied.nii.gz",
    "_to_T1_AppliedAnatomy.nii.gz",
    "0GenericAffine.mat",
    "1Warp.nii.gz",
    "1InverseWarp.nii.gz",
)

#: Prefixes of the ANTs by-products of the brain mask and the defacing.
PRODUCED_PREFIXES = ("brainmask_", "deface_")

#: Subfolders NeuXelec creates and owns entirely.
PRODUCED_FOLDERS = ("mni",)

#: Where the tidied files go, next to the project.
DEFAULT_SUBFOLDER = "neuxelec"

#: Fields of the session state that name a file the USER chose. A file
#: named here is yours even when its name looks like one of ours, which
#: happens as soon as a cleaned copy is imported as the source next time.
SOURCE_FIELDS = (
    "t1_source_path",
    "t2_source_path",
    "fmri_source_path",
    "ct_source_path",
    "pet_source_path",
    "ictal_spect_source_path",
    "interictal_spect_source_path",
    "parcel1_path",
    "parcel2_path",
    "mni_parcel2_path",
    "lh_pial_path",
    "rh_pial_path",
    "plan_trajectories_path",
    "brainmask_path",
    "siscom_path",
)

#: Fields that name a file NeuXelec produced and still uses.
PRODUCED_FIELDS = (
    "t1_conformed_path",
    "brainmask_generated_path",
    "t2_coreg_path",
    "fmri_coreg_path",
    "ct_coreg_path",
    "pet_coreg_path",
    "ictal_spect_coreg_path",
    "interictal_spect_coreg_path",
    "siscom_coreg_path",
    "fmri_reg_path",
    "plan_mri_in_t1_path",
    "t1_to_mni_affine_path",
    "t1_to_mni_warp_path",
    "t1_to_mni_inverse_warp_path",
    "t1_to_mni_warped_path",
)

#: Fields that name the file NeuXelec reads for a modality. It is either
#: the source itself or the cleaned copy of it; the name decides which.
IN_USE_FIELDS = (
    "t1_path",
    "t2_path",
    "fmri_path",
    "ct_path",
    "pet_path",
    "ictal_spect_path",
    "interictal_spect_path",
)


@dataclass
class Entry:
    """One file of the folder, and what may be done with it."""

    path: Path
    size: int
    category: str
    reason: str
    field: str | None = None

    @property
    def is_tidyable(self) -> bool:
        return self.category in (USED, ORPHAN)


def _normalise(path) -> str:
    """Compare paths the way the file system does, not the way they read."""
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return str(path)


def paths_of(state, fields) -> dict[str, str]:
    """{normalised path: field name} for the fields that hold one."""
    out: dict[str, str] = {}
    for field in fields:
        value = getattr(state, field, None)
        if isinstance(value, str) and value.strip():
            out.setdefault(_normalise(value), field)
    return out


def looks_produced(path) -> bool:
    """Does this name match something NeuXelec is known to write?"""
    name = Path(path).name
    lowered = name.lower()

    for suffix in PRODUCED_SUFFIXES:
        if lowered.endswith(suffix.lower()):
            return True

    for prefix in PRODUCED_PREFIXES:
        if lowered.startswith(prefix.lower()):
            return True

    parents = {p.name.lower() for p in Path(path).parents}
    return any(folder.lower() in parents for folder in PRODUCED_FOLDERS)


def classify(path, state) -> tuple[str, str, str | None]:
    """(category, reason, field) for one file.

    The order is the whole safety of this module: what the project calls a
    source is yours whatever its name, and a name we do not recognise is
    yours too.
    """
    key = _normalise(path)

    sources = paths_of(state, SOURCE_FIELDS)
    if key in sources:
        return SOURCE, "the project opened this file as your own data", sources[key]

    produced = paths_of(state, PRODUCED_FIELDS)
    if key in produced:
        return USED, "produced by NeuXelec, and the project still uses it", produced[key]

    in_use = paths_of(state, IN_USE_FIELDS)
    if key in in_use:
        if looks_produced(path):
            return USED, "a copy NeuXelec made, and reads for this modality", in_use[key]
        return SOURCE, "the file you imported for this modality", in_use[key]

    if looks_produced(path):
        return ORPHAN, "produced by NeuXelec, and nothing points at it any more", None

    return SOURCE, "NeuXelec did not write this file", None


def scan(folder, state, subfolder: str = DEFAULT_SUBFOLDER) -> list[Entry]:
    """Every file of the folder, classified, biggest first.

    Subfolders are walked, except the one tidied files already went into:
    a file that is already put away is not clutter any more.
    """
    root = Path(folder)
    entries: list[Entry] = []

    if not root.is_dir():
        return entries

    for parent, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() != subfolder.lower()]
        for name in names:
            p = Path(parent) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            category, reason, field = classify(p, state)
            entries.append(Entry(p, size, category, reason, field))

    entries.sort(key=lambda e: (-e.size, str(e.path)))
    return entries


def totals(entries) -> dict[str, dict[str, int]]:
    """How many files and how many bytes, per category."""
    out = {c: {"files": 0, "bytes": 0} for c in (SOURCE, USED, ORPHAN)}
    for e in entries:
        bucket = out.setdefault(e.category, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += int(e.size)
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


def destination_of(entry: Entry, folder, subfolder: str = DEFAULT_SUBFOLDER) -> Path:
    """Where a file goes when it is tidied away.

    The tree below the patient folder is kept, so two files of the same
    name coming from two subfolders cannot land on each other.
    """
    root = Path(folder)
    try:
        relative = entry.path.relative_to(root)
    except ValueError:
        relative = Path(entry.path.name)
    return root / subfolder / relative


def plan(entries, folder, move: list, delete: list, subfolder: str = DEFAULT_SUBFOLDER):
    """What will happen, before anything happens.

    Returns (moves, deletions, refused). ``refused`` holds what was asked
    for and will not be done, with the reason: it is shown rather than
    silently dropped.
    """
    chosen_move = {_normalise(p) for p in move}
    chosen_delete = {_normalise(p) for p in delete}

    moves: list[tuple[Entry, Path]] = []
    deletions: list[Entry] = []
    refused: list[tuple[Entry, str]] = []

    for entry in entries:
        key = _normalise(entry.path)
        wants_move = key in chosen_move
        wants_delete = key in chosen_delete

        if not (wants_move or wants_delete):
            continue

        if entry.category == SOURCE:
            refused.append((entry, "this file is yours, NeuXelec does not touch it"))
            continue

        if wants_delete and entry.category == USED:
            refused.append(
                (entry, "the project still uses this file: it can be moved, not deleted")
            )
            continue

        if wants_delete:
            deletions.append(entry)
        else:
            moves.append((entry, destination_of(entry, folder, subfolder)))

    return moves, deletions, refused


# ---------------------------------------------------------------------------
# Doing it
# ---------------------------------------------------------------------------
def send_to_recycle_bin(path) -> bool:
    """Delete through the Windows recycle bin, so it can be taken back.

    Returns False when the recycle bin is not available, and deletes
    nothing in that case: the caller says so rather than quietly erasing
    a file for good.
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
        # The API wants the list double-terminated.
        operation.pFrom = str(Path(path).resolve()) + "\0\0"
        operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        return result == 0 and not operation.fAnyOperationsAborted
    except Exception:
        return False


def update_state_paths(state, renames: dict[str, str]) -> list[str]:
    """Point the session at the files where they now are.

    Every string attribute that named a moved file is rewritten, so the
    project describes the new locations as soon as it is saved. Returns
    the names of the fields that changed, for the report.
    """
    if not renames:
        return []

    table = {_normalise(old): str(new) for old, new in renames.items()}
    changed: list[str] = []

    for name, value in list(vars(state).items()):
        if name.startswith("_"):
            continue
        if isinstance(value, str):
            new = table.get(_normalise(value))
            if new and new != value:
                setattr(state, name, new)
                changed.append(name)
        elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            remplace = [table.get(_normalise(v), v) for v in value]
            if remplace != value:
                setattr(state, name, remplace)
                changed.append(name)

    return changed


def apply_plan(moves, deletions, state=None, use_recycle_bin: bool = True) -> dict:
    """Move, then delete, and say exactly what happened.

    Moving comes first: if a move fails the file is still where the
    project expects it, and nothing has been deleted yet.
    """
    import shutil

    report = {
        "moved": [],
        "deleted": [],
        "failed": [],
        "fields": [],
        "bytes_moved": 0,
        "bytes_deleted": 0,
        "recycle_bin": False,
    }
    renames: dict[str, str] = {}

    for entry, destination in moves:
        try:
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            if Path(destination).exists():
                raise FileExistsError(f"{destination} already exists")
            shutil.move(str(entry.path), str(destination))
        except Exception as e:
            report["failed"].append((str(entry.path), f"move: {e}"))
            continue
        renames[str(entry.path)] = str(destination)
        report["moved"].append((str(entry.path), str(destination)))
        report["bytes_moved"] += int(entry.size)

    for entry in deletions:
        done = send_to_recycle_bin(entry.path) if use_recycle_bin else False
        if not done:
            try:
                Path(entry.path).unlink()
            except Exception as e:
                report["failed"].append((str(entry.path), f"delete: {e}"))
                continue
        else:
            report["recycle_bin"] = True
        report["deleted"].append(str(entry.path))
        report["bytes_deleted"] += int(entry.size)

    if state is not None:
        report["fields"] = update_state_paths(state, renames)

    return report
