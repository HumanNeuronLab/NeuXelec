"""Find a project's files again when the stored paths no longer point anywhere.

A NeuXelec project stores around thirty absolute paths: the anatomical MRI, the
CT, the registered volumes, the parcellations, the pial surfaces, the brain mask,
the MNI transforms. Written as absolute paths, they describe one folder layout on
one machine. Move the folder, change the drive letter, or send the ``.json`` to a
colleague, and every one of them points nowhere.

The fix is not a single project root. Images legitimately live in several places,
so each path is resolved on its own, through a cascade:

1. the stored absolute path, when it still exists (nothing has moved);
2. the path relative to the project file, stored alongside the absolute one;
3. a substitution *learned* from a path already resolved, so relocating one file
   relocates every sibling that shared its folder;
4. a bounded search by file name, starting from the project folder and from the
   folders of the files already found;
5. the user, asked once per folder rather than once per file.

**A candidate is never accepted on its name alone.** Saving records a fingerprint
for every file (its size, and the image geometry when the header can be read). A
file found by steps 2 to 4 is bound only if its fingerprint matches. Two patients
whose T1 is called ``T1.nii`` is not a hypothetical in a clinical folder tree, and
silently binding the wrong one would be far worse than asking.

Projects written before fingerprints existed simply carry none: those resolve as
*unverified*, which the caller reports rather than hides.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Suffixes of the companion keys written next to each stored path.
REL_SUFFIX = "_rel"
FP_SUFFIX = "_fp"

#: How many parent steps a relative path may climb and still be trusted. Two is
#: enough for the usual ``patient/project/x.json`` plus ``patient/images/t1.nii``
#: layout, and stops a relative path from spanning unrelated trees.
MAX_RELATIVE_UP = 2

#: Human names for the blocks of ``data["files"]``.
SECTION_LABELS: dict[str, str] = {
    "t1": "MRI 1",
    "t2": "MRI 2",
    "fmri": "fMRI",
    "ct": "CT",
    "pet": "PET",
    "ictal_spect": "Ictal SPECT",
    "interictal_spect": "Interictal SPECT",
    "siscom": "SISCOM",
    "brainmask": "Brain mask",
    "mni": "MNI",
    "plan_mri": "Planning MRI",
    "parcel1": "Parcellation 1",
    "parcel2": "Parcellation 2",
    "lh_pial": "Left pial surface",
    "rh_pial": "Right pial surface",
}

#: Human names for the path keys inside a block.
KEY_ROLES: dict[str, str] = {
    "path": "image",
    "source_path": "original source",
    "coreg_in_t1_path": "registered in MRI 1",
    "conformed_path": "1 mm isotropic copy",
    "generated_path": "generated file",
    "reg_path": "activation map",
    "template_path": "MNI template",
    "t1_to_mni_affine_path": "MRI 1 to MNI affine",
    "t1_to_mni_warp_path": "MRI 1 to MNI warp",
    "t1_to_mni_inverse_warp_path": "MNI to MRI 1 warp",
    "t1_to_mni_warped_path": "MRI 1 resampled in MNI",
}

#: Paths whose absence costs a feature or a recomputation, never the project.
#: They are resolved like the others but never hold the project open: the raw
#: DICOM source is routinely deleted after conversion, and the MNI transforms are
#: re-verified and regenerated on demand by ``mni_coordinates``.
SECONDARY_KEYS: frozenset[str] = frozenset(
    {
        "source_path",
        "generated_path",
        "template_path",
        "t1_to_mni_affine_path",
        "t1_to_mni_warp_path",
        "t1_to_mni_inverse_warp_path",
        "t1_to_mni_warped_path",
    }
)

#: Formats whose header SimpleITK can read without loading the voxels.
_GEOMETRY_SUFFIXES = (".nii", ".nii.gz", ".mgz", ".mgh", ".nrrd", ".nhdr", ".mha")

#: Bounds on the search by name, so a project on a network share cannot hang the
#: application while it walks a whole drive.
_SEARCH_MAX_DEPTH = 3
_SEARCH_MAX_DIRS = 4000


# =============================================================================
# Paths, compared the way Windows compares them
# =============================================================================


def _norm(path: str | os.PathLike) -> str:
    """Normalised for comparison: separators, redundant parts, and case."""
    return os.path.normcase(os.path.normpath(str(path)))


def _same_path(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return _norm(a) == _norm(b)


def _exists(path: str | None) -> bool:
    if not path:
        return False
    try:
        return os.path.exists(str(path))
    except (OSError, ValueError):
        return False


def _is_path_key(key: str) -> bool:
    """``path``, ``source_path``, ``t1_to_mni_affine_path``...

    The companion keys are safe by construction: neither ``path_rel`` nor
    ``path_fp`` ends with ``_path``.
    """
    return key == "path" or key.endswith("_path")


# =============================================================================
# Fingerprints
# =============================================================================


def _geometry_of(path: str) -> dict[str, Any]:
    """Image dimensions and spacing, read from the header alone."""
    if not os.path.basename(path).lower().endswith(_GEOMETRY_SUFFIXES):
        return {}
    try:
        import SimpleITK as sitk

        reader = sitk.ImageFileReader()
        reader.SetFileName(str(path))
        reader.ReadImageInformation()
        return {
            "dim": [int(v) for v in reader.GetSize()],
            "spacing": [round(float(v), 4) for v in reader.GetSpacing()],
        }
    except Exception:
        # An unreadable header is not an error here: the size alone still
        # identifies the file, and FreeSurfer surfaces have no header at all.
        return {}


def file_fingerprint(path: str | None) -> dict[str, Any] | None:
    """Enough to tell this file from another file of the same name.

    Returns ``None`` when the path does not exist. A directory (a DICOM series
    picked as a source) is marked as such and carries no size, so it can only
    ever be reported as unverified, never as a mismatch.
    """
    if not path:
        return None
    try:
        if os.path.isdir(str(path)):
            return {"dir": True}
        stat = os.stat(str(path))
    except (OSError, ValueError):
        return None

    fingerprint: dict[str, Any] = {"size": int(stat.st_size)}
    fingerprint.update(_geometry_of(str(path)))
    return fingerprint


def _values_differ(want: Any, got: Any) -> bool:
    if isinstance(want, list) or isinstance(got, list):
        return list(want or []) != list(got or [])
    return want != got


def fingerprint_matches(
    expected: dict[str, Any] | None, actual: dict[str, Any] | None
) -> bool | None:
    """``True`` identical, ``False`` different, ``None`` nothing to compare on.

    ``None`` is the honest answer for a project saved before fingerprints existed,
    and for a DICOM folder. The caller decides what to do with it; it must never
    be read as a match.
    """
    if not expected or not actual:
        return None

    if bool(expected.get("dir")) != bool(actual.get("dir")):
        return False
    if expected.get("dir"):
        return None  # a folder's content legitimately varies; nothing to assert

    compared = False
    for key in ("size", "dim", "spacing"):
        want = expected.get(key)
        got = actual.get(key)
        if want is None or got is None:
            continue
        compared = True
        if _values_differ(want, got):
            return False
    return True if compared else None


# =============================================================================
# The entries of a project
# =============================================================================


@dataclass(frozen=True)
class PathEntry:
    """One stored path, with everything needed to find it again and to say so."""

    section: str
    key: str
    stored: str
    relative: str | None = None
    fingerprint: dict[str, Any] | None = None
    essential: bool = True

    @property
    def label(self) -> str:
        return SECTION_LABELS.get(self.section, self.section.replace("_", " ").upper())

    @property
    def role(self) -> str:
        return KEY_ROLES.get(self.key, self.key.replace("_", " "))

    @property
    def name(self) -> str:
        return os.path.basename(str(self.stored).rstrip("\\/")) or str(self.stored)

    @property
    def folder(self) -> str:
        return os.path.dirname(str(self.stored))

    @property
    def user_locatable(self) -> bool:
        """False for files that belong to the installation, not to the patient.

        The MNI template ships with NeuXelec. Listing it in the relocation dialog
        would ask the user to go and find a file that is not theirs.
        """
        return self.key != "template_path"

    def describe(self) -> str:
        """``MRI 1`` or ``CT · registered in MRI 1``, for the dialog and the log."""
        if self.key == "path":
            return self.label
        return f"{self.label} · {self.role}"


def _entry_is_essential(key: str, block: dict[str, Any]) -> bool:
    """A path is essential when the project cannot honour what it claims.

    A registered volume only matters once its modality is validated, and the
    isotropic copy only once the T1 was actually conformed. Anything stored for
    convenience is secondary.
    """
    if key in SECONDARY_KEYS:
        return False
    if key == "coreg_in_t1_path":
        return bool(block.get("validated", False))
    if key == "conformed_path":
        return bool(block.get("was_conformed", False))
    return True


def iter_path_entries(data: dict[str, Any]) -> list[PathEntry]:
    """Every non-empty path stored under ``data["files"]``, in a stable order."""
    files = data.get("files")
    if not isinstance(files, dict):
        return []

    entries: list[PathEntry] = []
    for section, block in files.items():
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            if not _is_path_key(str(key)):
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            relative = block.get(f"{key}{REL_SUFFIX}")
            fingerprint = block.get(f"{key}{FP_SUFFIX}")
            entries.append(
                PathEntry(
                    section=str(section),
                    key=str(key),
                    stored=value,
                    relative=str(relative) if isinstance(relative, str) and relative else None,
                    fingerprint=fingerprint if isinstance(fingerprint, dict) else None,
                    essential=_entry_is_essential(str(key), block),
                )
            )
    return entries


# =============================================================================
# Writing the companion keys
# =============================================================================


def _relative_to_project(path: str, project_dir: Path) -> str | None:
    """The path seen from the project folder, when the two are related enough."""
    try:
        rel = os.path.relpath(str(path), str(project_dir))
    except (OSError, ValueError):
        return None  # different drives on Windows
    if os.path.isabs(rel):
        return None
    if list(Path(rel).parts).count("..") > MAX_RELATIVE_UP:
        return None
    return Path(rel).as_posix()


def annotate_paths(data: dict[str, Any], project_path: str | os.PathLike) -> dict[str, Any]:
    """Add ``<key>_rel`` and ``<key>_fp`` next to every stored path.

    Called when saving. The absolute path is left untouched, so a project stays
    readable by a version of NeuXelec that knows nothing of these keys.
    """
    files = data.get("files")
    if not isinstance(files, dict):
        return data

    project_dir = Path(str(project_path)).parent
    for block in files.values():
        if not isinstance(block, dict):
            continue
        for key in list(block.keys()):
            if not _is_path_key(str(key)):
                continue
            rel_key = f"{key}{REL_SUFFIX}"
            fp_key = f"{key}{FP_SUFFIX}"
            value = block.get(key)

            if not isinstance(value, str) or not value.strip():
                block.pop(rel_key, None)
                block.pop(fp_key, None)
                continue

            relative = _relative_to_project(value, project_dir)
            if relative:
                block[rel_key] = relative
            else:
                block.pop(rel_key, None)

            fingerprint = _fingerprint_for_save(value, block.get(fp_key))
            if fingerprint:
                block[fp_key] = fingerprint
            # A file that is unreachable right now keeps the fingerprint it had:
            # that is exactly the situation the fingerprint exists for.
    return data


def _fingerprint_for_save(path: str, previous: Any) -> dict[str, Any] | None:
    """Reuse the stored fingerprint when the file is byte-for-byte the same.

    Saving a project should not re-read fifteen image headers every time. The
    size settles it: if it has not changed, neither has the geometry.
    """
    try:
        if isinstance(previous, dict) and "size" in previous and not previous.get("dir"):
            if os.path.isfile(path) and int(os.stat(path).st_size) == int(previous["size"]):
                return previous
    except (OSError, ValueError, TypeError):
        pass
    return file_fingerprint(path)


# =============================================================================
# Substitutions learned from a file that was found
# =============================================================================


def derive_substitution(old: str, new: str) -> tuple[str, str] | None:
    """The folder move that turns ``old`` into ``new``.

    ``D:/Patients/P1/img/t1.nii`` found at ``E:/Data/P1/img/t1.nii`` yields
    ``("D:/Patients", "E:/Data")``: the longest common tail is dropped, and what
    remains on each side is the move. Returns ``None`` when the two paths share
    no tail at all, or when nothing actually moved.
    """
    old_parts = list(Path(str(old)).parts)
    new_parts = list(Path(str(new)).parts)

    common = 0
    while (
        common < len(old_parts)
        and common < len(new_parts)
        and os.path.normcase(old_parts[-1 - common]) == os.path.normcase(new_parts[-1 - common])
    ):
        common += 1

    if common == 0:
        return None

    old_prefix = old_parts[: len(old_parts) - common]
    new_prefix = new_parts[: len(new_parts) - common]
    if not old_prefix or not new_prefix:
        return None

    old_root = str(Path(*old_prefix))
    new_root = str(Path(*new_prefix))
    if _same_path(old_root, new_root):
        return None
    return (old_root, new_root)


def apply_substitution(path: str, substitution: tuple[str, str]) -> str | None:
    """``path`` rewritten through a learned move, or ``None`` if it is unrelated."""
    old_root, new_root = substitution
    if not old_root or not new_root:
        return None

    # normpath keeps the original casing, so offsets computed on it are valid on
    # the string we slice; normcase is used for the comparison only.
    normalised = os.path.normpath(str(path))
    root = os.path.normpath(str(old_root))
    boundary = root if root.endswith(("\\", "/")) else root + os.sep

    if not os.path.normcase(normalised).startswith(os.path.normcase(boundary)):
        return None
    tail = normalised[len(boundary) :].lstrip("\\/")
    if not tail:
        return None
    return str(Path(new_root) / tail)


# =============================================================================
# Search by name
# =============================================================================


class _NameIndex:
    """File names found under a set of roots, walked once and bounded.

    Walking once and looking names up matters: a project can have thirty missing
    paths, and re-walking the tree for each of them would turn a slow network
    share into a frozen application.
    """

    def __init__(self, *, max_depth: int = _SEARCH_MAX_DEPTH, max_dirs: int = _SEARCH_MAX_DIRS):
        self.max_depth = max_depth
        self.budget = max_dirs
        self._visited: set[str] = set()
        self._files: dict[str, list[str]] = {}
        self._dirs: dict[str, list[str]] = {}

    def add_roots(self, roots: list[str]) -> None:
        queue: deque[tuple[str, int]] = deque()
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            key = _norm(root)
            if key in self._visited:
                continue
            self._visited.add(key)
            queue.append((root, 0))

        while queue and self.budget > 0:
            current, depth = queue.popleft()
            self.budget -= 1
            try:
                children = list(os.scandir(current))
            except (OSError, ValueError):
                continue

            for child in children:
                try:
                    is_dir = child.is_dir()
                except OSError:
                    continue
                bucket = self._dirs if is_dir else self._files
                bucket.setdefault(os.path.normcase(child.name), []).append(child.path)
                if is_dir and depth < self.max_depth:
                    key = _norm(child.path)
                    if key not in self._visited:
                        self._visited.add(key)
                        queue.append((child.path, depth + 1))

    def candidates(self, name: str, *, want_dir: bool = False) -> list[str]:
        bucket = self._dirs if want_dir else self._files
        return list(bucket.get(os.path.normcase(str(name)), []))


def find_by_name(
    name: str,
    roots: list[str],
    *,
    want_dir: bool = False,
    max_depth: int = _SEARCH_MAX_DEPTH,
    max_dirs: int = _SEARCH_MAX_DIRS,
) -> str | None:
    """First file called ``name`` under ``roots``. Kept for one-off lookups."""
    index = _NameIndex(max_depth=max_depth, max_dirs=max_dirs)
    index.add_roots(roots)
    candidates = index.candidates(name, want_dir=want_dir)
    return candidates[0] if candidates else None


# =============================================================================
# The resolution itself
# =============================================================================


@dataclass
class Resolution:
    """What became of one stored path."""

    entry: PathEntry
    resolved: str | None = None
    #: unchanged | relative | substitution | application | search | manual | missing
    how: str = "missing"
    #: True verified, False mismatch, None nothing to compare on.
    verified: bool | None = None
    #: A file of the right name whose fingerprint did not match, kept so the
    #: dialog can show the user what was found and let them decide.
    candidate: str | None = None

    @property
    def found(self) -> bool:
        return bool(self.resolved)

    @property
    def moved(self) -> bool:
        return bool(self.resolved) and not _same_path(self.resolved, self.entry.stored)

    @property
    def blocking(self) -> bool:
        """Missing, and the project needs it."""
        return not self.found and self.entry.essential


@dataclass
class ResolutionReport:
    project_path: str
    resolutions: list[Resolution] = field(default_factory=list)
    substitutions: list[tuple[str, str]] = field(default_factory=list)

    @property
    def missing(self) -> list[Resolution]:
        return [r for r in self.resolutions if not r.found]

    @property
    def missing_essential(self) -> list[Resolution]:
        return [r for r in self.resolutions if r.blocking]

    @property
    def relocated(self) -> list[Resolution]:
        return [r for r in self.resolutions if r.moved]

    @property
    def unverified(self) -> list[Resolution]:
        return [r for r in self.resolutions if r.moved and r.verified is None]

    @property
    def needs_user_input(self) -> bool:
        """Only an essential file nobody could find opens the dialog."""
        return bool(self.missing_essential)

    @property
    def changed(self) -> bool:
        return bool(self.relocated)

    def summary(self) -> str:
        return (
            f"{len(self.resolutions)} paths, {len(self.relocated)} relocated, "
            f"{len(self.missing)} missing ({len(self.missing_essential)} essential)"
        )


def _app_default_for(entry: PathEntry) -> str | None:
    """Paths that belong to the installation, not to the patient folder.

    The MNI template ships with NeuXelec, so it is found next to the application
    rather than asked of the user, whose project may well have been written by an
    installation in another folder. The file name must still match: a project
    built against a different template must fall through and be recomputed, not
    silently bound to whatever ships today.
    """
    if entry.key != "template_path":
        return None
    try:
        from .coregistration import _default_brainmask_template_paths

        template, _mask = _default_brainmask_template_paths()
    except Exception:
        logger.debug("Could not resolve the bundled MNI template", exc_info=True)
        return None

    if not template or not os.path.exists(str(template)):
        return None
    if os.path.normcase(os.path.basename(str(template))) != os.path.normcase(entry.name):
        return None
    return str(template)


def _accept(
    resolution: Resolution,
    candidate: str,
    how: str,
    report: ResolutionReport,
    *,
    force: bool = False,
    require_verified: bool = False,
) -> bool:
    """Bind ``candidate`` to ``resolution`` if its fingerprint allows it.

    ``force`` is the user pointing at a file themselves: their choice wins, but a
    mismatch is still recorded so the dialog can say so. ``require_verified``
    is the opposite: nothing short of a proven match will do.
    """
    verified = fingerprint_matches(resolution.entry.fingerprint, file_fingerprint(candidate))
    if require_verified and verified is not True:
        return False
    if verified is False and not force:
        # A file of the right name that is not the right file. Remember it for
        # the dialog, and keep looking.
        resolution.candidate = candidate
        resolution.verified = False
        return False

    resolution.resolved = candidate
    resolution.how = how
    resolution.verified = verified
    resolution.candidate = None

    substitution = derive_substitution(resolution.entry.stored, candidate)
    if substitution and substitution not in report.substitutions:
        report.substitutions.append(substitution)
    return True


def _try_substitutions(resolution: Resolution, report: ResolutionReport) -> bool:
    for substitution in list(report.substitutions):
        candidate = apply_substitution(resolution.entry.stored, substitution)
        if candidate and _exists(candidate):
            if _accept(resolution, candidate, "substitution", report):
                return True
    return False


def _substitutions_to_fixed_point(
    pending: list[Resolution], report: ResolutionReport
) -> list[Resolution]:
    """Apply learned moves until none of them resolves anything more."""
    progress = True
    while progress and pending:
        progress = False
        remaining: list[Resolution] = []
        for resolution in pending:
            if _try_substitutions(resolution, report):
                progress = True
            else:
                remaining.append(resolution)
        pending = remaining
    return pending


def resolve_project_paths(
    data: dict[str, Any],
    project_path: str | os.PathLike,
    *,
    search: bool = True,
) -> ResolutionReport:
    """Resolve every stored path, without touching ``data``.

    The caller applies the result with :func:`apply_resolutions`, after asking the
    user about whatever could not be found.
    """
    project_path = str(project_path)
    project_dir = Path(project_path).parent
    report = ResolutionReport(project_path=project_path)
    report.resolutions = [Resolution(entry=entry) for entry in iter_path_entries(data)]

    pending: list[Resolution] = []

    # 1. Nothing has moved.
    for resolution in report.resolutions:
        if _exists(resolution.entry.stored):
            resolution.resolved = resolution.entry.stored
            resolution.how = "unchanged"
        else:
            pending.append(resolution)

    if not pending:
        return report

    # 2. Relative to the project file, and paths owned by the installation.
    still_pending: list[Resolution] = []
    for resolution in pending:
        candidate = None
        if resolution.entry.relative:
            candidate = os.path.normpath(str(project_dir / resolution.entry.relative))
        if candidate and _exists(candidate) and _accept(resolution, candidate, "relative", report):
            continue
        app_path = _app_default_for(resolution.entry)
        # Only a proven match. The MNI transforms stored in a project are reused
        # when the template they were computed against is still the current one,
        # so binding the template on its file name alone could silently revive
        # transforms computed against a different template. A project with no
        # fingerprint (written before 1.2.1) therefore leaves its template
        # unresolved, and mni_coordinates recomputes, exactly as it does today.
        if app_path and _accept(resolution, app_path, "application", report, require_verified=True):
            continue
        still_pending.append(resolution)
    pending = still_pending

    # 3. Substitutions: one relocated file can unlock a folder that in turn
    #    unlocks another, so this runs to a fixed point.
    pending = _substitutions_to_fixed_point(pending, report)

    # 4. Search by name, from the project folder and from what was already found.
    if search and pending:
        index = _NameIndex()
        index.add_roots(_search_roots(project_dir, report))

        progress = True
        while progress and pending:
            progress = False
            remaining: list[Resolution] = []
            for resolution in pending:
                want_dir = bool((resolution.entry.fingerprint or {}).get("dir"))
                accepted = False
                for candidate in index.candidates(resolution.entry.name, want_dir=want_dir):
                    if _accept(resolution, candidate, "search", report):
                        accepted = True
                        break
                if accepted:
                    progress = True
                else:
                    remaining.append(resolution)
            pending = remaining
            if progress and pending:
                pending = _substitutions_to_fixed_point(pending, report)
                index.add_roots(_search_roots(project_dir, report))

    logger.info("Project paths: %s", report.summary())
    return report


def _search_roots(project_dir: Path, report: ResolutionReport) -> list[str]:
    """Where to look: the project folder, then every folder already resolved."""
    roots = [str(project_dir)]
    for resolution in report.resolutions:
        if not resolution.resolved:
            continue
        folder = os.path.dirname(resolution.resolved)
        if folder and folder not in roots:
            roots.append(folder)
    return roots


# =============================================================================
# Manual relocation, driven by the dialog
# =============================================================================


def set_manual_path(
    report: ResolutionReport, resolution: Resolution, new_path: str
) -> list[Resolution]:
    """Bind a path the user picked, and propagate the move to its siblings.

    The user's choice is always honoured, even when the fingerprint disagrees;
    ``resolution.verified`` is then ``False`` so the caller can warn. Returns the
    other resolutions that the derived substitution just fixed.
    """
    _accept(resolution, str(new_path), "manual", report, force=True)

    fixed: list[Resolution] = []
    for other in report.resolutions:
        if other is resolution or other.found:
            continue
        if _try_substitutions(other, report):
            fixed.append(other)
    return fixed


def relocate_into_folder(report: ResolutionReport, folder: str) -> list[Resolution]:
    """Look for every missing file under ``folder``. Returns what was found."""
    if not folder or not os.path.isdir(folder):
        return []

    index = _NameIndex()
    index.add_roots([str(folder)])

    fixed: list[Resolution] = []
    progress = True
    while progress:
        progress = False
        for resolution in report.resolutions:
            if resolution.found:
                continue
            if _try_substitutions(resolution, report):
                fixed.append(resolution)
                progress = True
                continue
            want_dir = bool((resolution.entry.fingerprint or {}).get("dir"))
            for candidate in index.candidates(resolution.entry.name, want_dir=want_dir):
                if _accept(resolution, candidate, "search", report):
                    fixed.append(resolution)
                    progress = True
                    break
    return fixed


# =============================================================================
# Writing the result back
# =============================================================================


def apply_resolutions(
    data: dict[str, Any], report: ResolutionReport, *, clear_missing: bool = False
) -> int:
    """Write the resolved paths into ``data``. Returns how many changed.

    ``clear_missing`` empties the paths nobody could find. It is off by default:
    keeping the old value lets the user see, and fix, where the file used to be
    the next time they open the project.
    """
    files = data.get("files")
    if not isinstance(files, dict):
        return 0

    project_dir = Path(report.project_path).parent
    changed = 0
    for resolution in report.resolutions:
        block = files.get(resolution.entry.section)
        if not isinstance(block, dict):
            continue
        key = resolution.entry.key

        if resolution.found:
            if not resolution.moved:
                continue
            block[key] = resolution.resolved
            relative = _relative_to_project(str(resolution.resolved), project_dir)
            if relative:
                block[f"{key}{REL_SUFFIX}"] = relative
            else:
                block.pop(f"{key}{REL_SUFFIX}", None)
            fingerprint = file_fingerprint(resolution.resolved)
            if fingerprint:
                block[f"{key}{FP_SUFFIX}"] = fingerprint
            changed += 1
        elif clear_missing:
            block[key] = None
            block.pop(f"{key}{REL_SUFFIX}", None)
            changed += 1
    return changed
