"""Resolving a project's file paths after the files have moved.

Everything here works on real files in a temporary folder: the module's whole
job is to talk to the filesystem, so stubbing it would test nothing.
"""

import json
import os

import pytest

from neuxelec.project_paths import (
    annotate_paths,
    apply_resolutions,
    apply_substitution,
    derive_substitution,
    file_fingerprint,
    fingerprint_matches,
    iter_path_entries,
    relocate_into_folder,
    resolve_project_paths,
    set_manual_path,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write(path, content=b"image"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def _project(t1=None, ct=None, **extra):
    """A minimal project dict shaped like the real one."""
    files = {
        "t1": {"path": t1, "source_path": None, "was_conformed": False},
        "ct": {"path": ct, "coreg_in_t1_path": None, "validated": False},
    }
    for section, block in extra.items():
        files[section] = block
    return {"schema_version": 1, "patient_id": "P1", "files": files}


def _by_key(report, section, key="path"):
    for resolution in report.resolutions:
        if resolution.entry.section == section and resolution.entry.key == key:
            return resolution
    raise AssertionError(f"no resolution for {section}.{key}")


# ---------------------------------------------------------------------------
# entries
# ---------------------------------------------------------------------------


def test_every_path_key_is_collected_and_nothing_else():
    data = _project(t1="a.nii", ct="b.nii")
    data["files"]["mni"] = {
        "space_name": "MNI152NLin2009cAsym",
        "template_path": "t.nii",
        "t1_to_mni_affine_path": "aff.mat",
    }
    keys = {(e.section, e.key) for e in iter_path_entries(data)}
    assert keys == {
        ("t1", "path"),
        ("ct", "path"),
        ("mni", "template_path"),
        ("mni", "t1_to_mni_affine_path"),
    }


def test_companion_keys_are_not_mistaken_for_paths(tmp_path):
    data = _project(t1=_write(tmp_path / "t1.nii"))
    annotate_paths(data, tmp_path / "p.json")
    # path_rel and path_fp exist now; they must not become entries of their own.
    assert "path_rel" in data["files"]["t1"]
    assert [(e.section, e.key) for e in iter_path_entries(data)] == [("t1", "path")]


def test_secondary_paths_never_block():
    data = _project(t1="a.nii")
    data["files"]["t1"]["source_path"] = "dicom_folder"
    data["files"]["mni"] = {"t1_to_mni_affine_path": "aff.mat", "template_path": "t.nii"}
    essential = {(e.section, e.key) for e in iter_path_entries(data) if e.essential}
    assert essential == {("t1", "path")}


def test_registered_volume_is_essential_only_once_validated():
    data = _project(ct="ct.nii")
    data["files"]["ct"]["coreg_in_t1_path"] = "ct_in_t1.nii"
    assert not _entry(data, "ct", "coreg_in_t1_path").essential

    data["files"]["ct"]["validated"] = True
    assert _entry(data, "ct", "coreg_in_t1_path").essential


def _entry(data, section, key):
    for entry in iter_path_entries(data):
        if entry.section == section and entry.key == key:
            return entry
    raise AssertionError(f"no entry for {section}.{key}")


# ---------------------------------------------------------------------------
# fingerprints
# ---------------------------------------------------------------------------


def test_fingerprint_separates_two_files_of_the_same_name(tmp_path):
    a = _write(tmp_path / "one" / "T1.nii", b"x" * 100)
    b = _write(tmp_path / "two" / "T1.nii", b"y" * 250)
    assert fingerprint_matches(file_fingerprint(a), file_fingerprint(b)) is False
    assert fingerprint_matches(file_fingerprint(a), file_fingerprint(a)) is True


def test_a_copy_keeps_its_fingerprint(tmp_path):
    a = _write(tmp_path / "one" / "T1.nii", b"x" * 100)
    b = _write(tmp_path / "two" / "T1.nii", b"x" * 100)
    assert fingerprint_matches(file_fingerprint(a), file_fingerprint(b)) is True


def test_nothing_to_compare_is_not_a_match():
    assert fingerprint_matches(None, {"size": 1}) is None
    assert fingerprint_matches({}, {"size": 1}) is None
    assert fingerprint_matches({"size": 1}, None) is None


def test_a_folder_is_never_reported_as_a_mismatch(tmp_path):
    folder = tmp_path / "dicom"
    folder.mkdir()
    assert file_fingerprint(str(folder)) == {"dir": True}
    assert fingerprint_matches({"dir": True}, {"dir": True}) is None
    assert fingerprint_matches({"dir": True}, {"size": 12}) is False


# ---------------------------------------------------------------------------
# substitutions
# ---------------------------------------------------------------------------


def test_substitution_is_the_common_tail_removed():
    old = os.path.join("D:", os.sep, "Patients", "P1", "img", "t1.nii")
    new = os.path.join("E:", os.sep, "Data", "P1", "img", "t1.nii")
    substitution = derive_substitution(old, new)
    assert substitution is not None
    other_old = os.path.join("D:", os.sep, "Patients", "P1", "ct", "ct.nii")
    expected = os.path.join("E:", os.sep, "Data", "P1", "ct", "ct.nii")
    assert apply_substitution(other_old, substitution) == expected


def test_substitution_ignores_an_unrelated_path():
    substitution = derive_substitution(
        os.path.join("D:", os.sep, "A", "t1.nii"), os.path.join("E:", os.sep, "B", "t1.nii")
    )
    assert apply_substitution(os.path.join("Z:", os.sep, "other", "ct.nii"), substitution) is None


def test_no_common_tail_means_no_substitution():
    assert derive_substitution("/a/b/t1.nii", "/c/d/ct.nii") is None


def test_a_path_that_did_not_move_yields_no_substitution():
    assert derive_substitution("/a/b/t1.nii", "/a/b/t1.nii") is None


def test_substitution_matches_on_whole_folders_only():
    """``D:/Patients`` must not swallow ``D:/PatientsArchive``."""
    substitution = (os.path.join("D:", os.sep, "Patients"), os.path.join("E:", os.sep, "Data"))
    assert (
        apply_substitution(os.path.join("D:", os.sep, "PatientsArchive", "t1.nii"), substitution)
        is None
    )


# ---------------------------------------------------------------------------
# the cascade
# ---------------------------------------------------------------------------


def test_nothing_moved_changes_nothing(tmp_path):
    t1 = _write(tmp_path / "img" / "t1.nii")
    data = _project(t1=t1)
    report = resolve_project_paths(data, tmp_path / "p.json")

    assert _by_key(report, "t1").how == "unchanged"
    assert not report.needs_user_input
    assert not report.changed
    assert apply_resolutions(data, report) == 0


def test_the_whole_folder_moved_to_another_machine(tmp_path):
    """Saved under one root, reopened under another: relative paths carry it."""
    source = tmp_path / "old" / "PAT"
    t1 = _write(source / "img" / "t1.nii", b"a" * 40)
    ct = _write(source / "img" / "ct.nii", b"b" * 60)
    project = source / "PAT.json"
    project.write_text("{}")

    data = _project(t1=t1, ct=ct)
    annotate_paths(data, project)

    # The folder is moved wholesale, the project file with it.
    destination = tmp_path / "new" / "PAT"
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source, destination)

    report = resolve_project_paths(data, destination / "PAT.json")
    assert not report.needs_user_input
    assert _by_key(report, "t1").how == "relative"
    assert _by_key(report, "t1").verified is True
    assert os.path.exists(_by_key(report, "t1").resolved)

    assert apply_resolutions(data, report) == 2
    assert data["files"]["t1"]["path"] == str(destination / "img" / "t1.nii")
    assert data["files"]["t1"]["path_rel"] == "img/t1.nii"


def _scattered(tmp_path, old_root_of, new_root_of):
    """Nine files in three folders, described by where each folder went."""
    data = _project()
    data["files"] = {}
    roots = {}
    for index, group in enumerate(("a", "b", "c")):
        old_root, new_root = old_root_of(group), new_root_of(group)
        roots[group] = (old_root, new_root)
        for which in range(3):
            name = f"{group}{which}.nii"
            _write(new_root / name, bytes([index, which]) * 50)
            data["files"][f"{group}{which}"] = {"path": str(old_root / name)}
    return data, roots


def _answer_until_resolved(report, roots):
    """Point at one file per folder, only while something is still missing."""
    answers = 0
    for group, (_old_root, new_root) in roots.items():
        target = _by_key(report, f"{group}0")
        if target.found:
            continue
        answers += 1
        set_manual_path(report, target, str(new_root / f"{group}0.nii"))
    return answers


def test_unrelated_folders_take_one_answer_each(tmp_path):
    """Three folders that moved in three different ways: three questions, not nine."""
    data, roots = _scattered(
        tmp_path,
        lambda group: tmp_path / f"old_{group}" / f"img_{group}",
        lambda group: tmp_path / f"new_{group}" / f"img_{group}",
    )

    report = resolve_project_paths(data, tmp_path / "elsewhere" / "p.json", search=False)
    assert len(report.missing_essential) == 9

    assert _answer_until_resolved(report, roots) == 3
    assert report.missing_essential == []
    assert all(r.found for r in report.resolutions)


def test_folders_that_moved_together_take_a_single_answer(tmp_path):
    """The usual case: one patient tree relocated wholesale. One question."""
    data, roots = _scattered(
        tmp_path,
        lambda group: tmp_path / "old" / group,
        lambda group: tmp_path / "new" / group,
    )

    report = resolve_project_paths(data, tmp_path / "elsewhere" / "p.json", search=False)
    assert len(report.missing_essential) == 9

    assert _answer_until_resolved(report, roots) == 1
    assert report.missing_essential == []
    assert all(r.found for r in report.resolutions)


def test_a_file_moved_by_mistake_is_found_by_name(tmp_path):
    """Someone drags the T1 into a subfolder: no question should be asked."""
    root = tmp_path / "PAT"
    t1 = _write(root / "t1.nii", b"a" * 40)
    data = _project(t1=t1)
    annotate_paths(data, root / "p.json")

    (root / "IRM").mkdir()
    os.rename(t1, root / "IRM" / "t1.nii")

    report = resolve_project_paths(data, root / "p.json")
    assert _by_key(report, "t1").how == "search"
    assert _by_key(report, "t1").verified is True
    assert not report.needs_user_input


def test_a_namesake_from_another_patient_is_refused(tmp_path):
    """The whole point of the fingerprint: never bind the wrong patient."""
    root = tmp_path / "PAT"
    t1 = _write(root / "images" / "T1.nii", b"a" * 40)
    data = _project(t1=t1)
    annotate_paths(data, root / "p.json")

    os.remove(t1)
    # Another patient's T1, same name, different content, sitting right there.
    _write(root / "images" / "other" / "T1.nii", b"z" * 900)

    report = resolve_project_paths(data, root / "p.json")
    resolution = _by_key(report, "t1")
    assert not resolution.found
    assert resolution.verified is False
    assert resolution.candidate.endswith("T1.nii")
    assert report.needs_user_input


def test_the_user_can_override_a_refused_candidate(tmp_path):
    root = tmp_path / "PAT"
    t1 = _write(root / "T1.nii", b"a" * 40)
    data = _project(t1=t1)
    annotate_paths(data, root / "p.json")
    os.remove(t1)
    replacement = _write(root / "new" / "T1.nii", b"z" * 900)

    report = resolve_project_paths(data, root / "p.json")
    resolution = _by_key(report, "t1")
    assert not resolution.found

    set_manual_path(report, resolution, replacement)
    assert resolution.found
    assert resolution.how == "manual"
    assert resolution.verified is False  # honoured, and still flagged
    assert not report.needs_user_input


def test_a_secondary_file_alone_never_opens_the_dialog(tmp_path):
    """The DICOM source deleted after conversion must not nag on every open."""
    root = tmp_path / "PAT"
    t1 = _write(root / "t1.nii")
    data = _project(t1=t1)
    data["files"]["t1"]["source_path"] = str(root / "dicom_gone")

    report = resolve_project_paths(data, root / "p.json")
    assert len(report.missing) == 1
    assert report.missing_essential == []
    assert not report.needs_user_input


def test_relocate_into_folder_finds_everything_at_once(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new" / "PAT"
    data = _project()
    data["files"] = {}
    for index, name in enumerate(("t1.nii", "ct.nii", "pet.nii")):
        _write(new_root / "images" / name, bytes([index]) * 70)
        data["files"][name.split(".")[0]] = {"path": str(old_root / name)}

    report = resolve_project_paths(data, tmp_path / "p.json", search=False)
    assert len(report.missing_essential) == 3

    fixed = relocate_into_folder(report, str(new_root))
    assert len(fixed) == 3
    assert report.missing_essential == []


def test_an_old_project_without_fingerprints_still_resolves(tmp_path):
    """1.2.0 wrote absolute paths only. Those projects must keep working."""
    root = tmp_path / "PAT"
    t1 = _write(root / "t1.nii")
    data = _project(t1=str(tmp_path / "gone" / "t1.nii"))
    assert "path_fp" not in data["files"]["t1"]

    report = resolve_project_paths(data, root / "p.json")
    resolution = _by_key(report, "t1")
    assert resolution.resolved == t1
    assert resolution.verified is None  # found, but nothing proves it is the one
    assert report.unverified == [resolution]


def test_missing_paths_are_kept_not_erased(tmp_path):
    data = _project(t1=str(tmp_path / "gone" / "t1.nii"))
    report = resolve_project_paths(data, tmp_path / "p.json")
    apply_resolutions(data, report)
    assert data["files"]["t1"]["path"] == str(tmp_path / "gone" / "t1.nii")

    apply_resolutions(data, report, clear_missing=True)
    assert data["files"]["t1"]["path"] is None


def test_annotate_skips_a_path_on_another_drive(tmp_path):
    """A relative path that would climb out of the tree is not written."""
    data = _project(t1=_write(tmp_path / "far" / "away" / "deep" / "deeper" / "t1.nii"))
    annotate_paths(data, tmp_path / "a" / "b" / "c" / "p.json")
    assert "path_rel" not in data["files"]["t1"]
    assert data["files"]["t1"]["path_fp"]["size"] == 5


def test_annotate_is_idempotent_and_reuses_the_fingerprint(tmp_path):
    data = _project(t1=_write(tmp_path / "t1.nii"))
    annotate_paths(data, tmp_path / "p.json")
    first = json.dumps(data, sort_keys=True)
    annotate_paths(data, tmp_path / "p.json")
    assert json.dumps(data, sort_keys=True) == first


def test_emptying_a_path_removes_its_companions(tmp_path):
    data = _project(t1=_write(tmp_path / "t1.nii"))
    annotate_paths(data, tmp_path / "p.json")
    data["files"]["t1"]["path"] = None
    annotate_paths(data, tmp_path / "p.json")
    assert "path_rel" not in data["files"]["t1"]
    assert "path_fp" not in data["files"]["t1"]


def test_a_dicom_source_folder_is_relocated_as_a_folder(tmp_path):
    root = tmp_path / "PAT"
    series = root / "DICOM" / "series_701"
    series.mkdir(parents=True)
    (series / "0001.dcm").write_bytes(b"d")
    data = _project(t1=_write(root / "t1.nii"))
    data["files"]["t1"]["source_path"] = str(series)
    annotate_paths(data, root / "p.json")
    assert data["files"]["t1"]["source_path_fp"] == {"dir": True}

    moved = tmp_path / "moved"
    os.rename(root, moved)
    report = resolve_project_paths(data, moved / "p.json")
    source = _by_key(report, "t1", "source_path")
    assert source.found
    assert os.path.isdir(source.resolved)


def test_the_search_never_leaves_its_budget(tmp_path):
    """A deep tree must not be walked to the bottom looking for one file."""
    deep = tmp_path / "root"
    current = deep
    for level in range(8):
        current = current / f"level{level}"
    _write(current / "t1.nii")

    data = _project(t1=str(tmp_path / "gone" / "t1.nii"))
    report = resolve_project_paths(data, deep / "p.json")
    assert not _by_key(report, "t1").found


@pytest.mark.parametrize("bad", [None, {}, {"files": None}, {"files": {"t1": "oops"}}])
def test_malformed_projects_do_not_raise(bad, tmp_path):
    data = bad if isinstance(bad, dict) else {}
    report = resolve_project_paths(data, tmp_path / "p.json")
    assert report.resolutions == []
    assert apply_resolutions(data, report) == 0
    annotate_paths(data, tmp_path / "p.json")


# ---------------------------------------------------------------------------
# the MNI template, which belongs to the installation and not to the patient
# ---------------------------------------------------------------------------


def _bundled_template():
    from neuxelec.coregistration import _default_brainmask_template_paths

    template, _mask = _default_brainmask_template_paths()
    return str(template) if template and os.path.exists(str(template)) else None


def test_the_template_is_never_offered_to_the_user():
    data = _project(t1="t1.nii")
    data["files"]["mni"] = {"template_path": "template_T1.nii"}
    entry = _entry(data, "mni", "template_path")
    assert not entry.user_locatable
    assert _entry(data, "t1", "path").user_locatable


def test_an_unverified_template_is_left_for_recomputation(tmp_path):
    """A project with no fingerprint must not revive stale MNI transforms.

    The stored transforms are reused only while the template they were computed
    against is the current one. Binding the template on its file name alone
    would make that check pass for a template that may well be a different file.
    """
    bundled = _bundled_template()
    if bundled is None:
        pytest.skip("no bundled MNI template in this checkout")

    data = _project(t1=_write(tmp_path / "t1.nii"))
    data["files"]["mni"] = {
        "template_path": str(tmp_path / "old_install" / os.path.basename(bundled))
    }

    report = resolve_project_paths(data, tmp_path / "p.json", search=False)
    template = _by_key(report, "mni", "template_path")
    assert not template.found
    assert not report.needs_user_input  # secondary: it must not open the dialog


def test_a_template_proven_identical_is_rebound(tmp_path):
    bundled = _bundled_template()
    if bundled is None:
        pytest.skip("no bundled MNI template in this checkout")

    data = _project(t1=_write(tmp_path / "t1.nii"))
    data["files"]["mni"] = {
        "template_path": str(tmp_path / "old_install" / os.path.basename(bundled)),
        "template_path_fp": file_fingerprint(bundled),
    }

    report = resolve_project_paths(data, tmp_path / "p.json", search=False)
    template = _by_key(report, "mni", "template_path")
    assert template.found
    assert template.how == "application"
    assert template.verified is True
