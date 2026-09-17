"""Saving the planning MRI and the planned trajectories.

The registered planning MRI is what every trajectory of the plan rests on.
Writing it to disk, and recording where, is what lets its alignment be reviewed
again once the project has been closed and reopened.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from neuxelec.pages.files_page import FilesPage  # noqa: E402
from neuxelec.project_io import (  # noqa: E402
    apply_project_dict_to_state,
    load_project_json,
    save_project_json,
)
from neuxelec.state import AppState  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _plan():
    """Two trajectories, one per hemisphere, with a DIXI style reference."""
    return {
        "source": "NeuroInspire",
        "trajectories_t1": [
            {
                "name": "AD",
                "reference_key": "DIXI-D08-12AM",
                "contact_count": 3,
                "contact_separation_mm": 1.5,
                "contact_length_mm": 2.0,
                # 3.5 mm centre to centre, straight along x
                "entry_t1_lps": [-40.0, 0.0, 0.0],
                "target_t1_lps": [-10.0, 0.0, 0.0],
            },
            {
                "name": "AG",
                "reference_key": "DIXI-D08-12AM",
                "contact_count": 2,
                "contact_separation_mm": 1.5,
                "contact_length_mm": 2.0,
                "entry_t1_lps": [40.0, 0.0, 0.0],
                "target_t1_lps": [10.0, 0.0, 0.0],
            },
        ],
        "transform": {
            "mode": "affine",
            "reviewed": True,
            "manual": [{"translation_mm": [0.5, 0.0, 0.0]}],
            "planning_mri_path": r"C:\patient\planif.nii",
        },
    }


@pytest.fixture
def page(qt_app):
    page = FilesPage.__new__(FilesPage)
    page.state = AppState()
    page.state.patient_id = "PAT_TEST"
    page.state.plan = _plan()
    page._mri1_filename_label = lambda: "MRI1"
    return page


# ---------------------------------------------------------------------------
# the geometry
# ---------------------------------------------------------------------------


def test_the_deepest_contact_sits_on_the_target(page):
    contacts = page._planned_contacts_lps(page.state.plan["trajectories_t1"][0])
    assert len(contacts) == 3
    assert contacts[0] == pytest.approx((-10.0, 0.0, 0.0))


def test_contacts_step_back_by_separation_plus_length(page):
    """Centre to centre is what the reconstruction registers as the reference."""
    contacts = page._planned_contacts_lps(page.state.plan["trajectories_t1"][0])
    # target is at x = -10, entry at x = -40, so the shaft runs towards -x
    assert contacts[1] == pytest.approx((-13.5, 0.0, 0.0))
    assert contacts[2] == pytest.approx((-17.0, 0.0, 0.0))


def test_a_trajectory_without_a_reference_yields_no_contacts(page):
    traj = dict(page.state.plan["trajectories_t1"][0])
    traj.pop("contact_separation_mm")
    assert page._planned_contacts_lps(traj) == []


def test_a_single_contact_electrode(page):
    traj = dict(page.state.plan["trajectories_t1"][0])
    traj["contact_count"] = 1
    assert len(page._planned_contacts_lps(traj)) == 1


# ---------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------


def test_the_file_carries_the_header_and_every_contact(page, tmp_path):
    out = tmp_path / "plan.txt"
    written = page._write_planned_trajectories(out)
    assert written == 5  # 3 + 2

    text = out.read_text(encoding="utf-8")
    assert text.startswith("SEEG_planned_trajectories")
    assert "Patient: PAT_TEST" in text
    assert "Coordinate system: LPS (MRI1)" in text
    assert "Plan source: NeuroInspire" in text
    assert "affine, reviewed, 1 manual correction(s)" in text
    assert r"Planning MRI: C:\patient\planif.nii" in text

    assert "[AD] | reference=DIXI-D08-12AM" in text
    assert "[AG] | reference=DIXI-D08-12AM" in text
    assert text.count("contact=") == 5
    assert "x=-10.00 | y=0.00 | z=0.00" in text
    assert "entry  | x=-40.00" in text
    assert "target | x=-10.00" in text


def test_the_hemisphere_is_derived_from_the_target(page, tmp_path):
    out = tmp_path / "plan.txt"
    page._write_planned_trajectories(out)
    text = out.read_text(encoding="utf-8")
    # LPS: x < 0 is the left hemisphere.
    ad = text.split("[AD]")[1].splitlines()[0]
    ag = text.split("[AG]")[1].splitlines()[0]
    assert "hemisphere=" in ad and "hemisphere=" in ag
    assert ad != ag


def test_a_plan_with_no_trajectory_still_writes_a_readable_file(page, tmp_path):
    page.state.plan = {"source": "NeuroInspire", "trajectories_t1": []}
    out = tmp_path / "plan.txt"
    assert page._write_planned_trajectories(out) == 0
    assert "SEEG_planned_trajectories" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# the button
# ---------------------------------------------------------------------------


def test_the_button_follows_the_plan(page, qt_app):
    page.btn_save_plan = QPushButton("save plan")
    for name in ("btn_brainmask", "btn_iso_surface"):
        setattr(page, name, QPushButton(name))
    for name in FilesPage._BUSY_BUTTONS:
        if not hasattr(page, name):
            setattr(page, name, QPushButton(name))
    for name in (
        "chk_t1",
        "chk_t2",
        "chk_fmri",
        "chk_ct",
        "chk_pet",
        "chk_ictal",
        "chk_interictal",
    ):
        setattr(page, name, None)
    page.ui = None
    page._enable_3d_checkbox = lambda *a, **k: None
    page._refresh_coreg_progress_ui = lambda *a, **k: None
    page._sync_files_status_overview = lambda *a, **k: None
    page._enable_checkbox = lambda *a, **k: None

    page._update_buttons()
    assert page.btn_save_plan.isEnabled()

    page.state.plan = None
    page._update_buttons()
    assert not page.btn_save_plan.isEnabled()


# ---------------------------------------------------------------------------
# reopening the project
# ---------------------------------------------------------------------------


def test_the_registered_planning_mri_survives_the_project(tmp_path):
    """Reopening the JSON must find the registered planning MRI again."""
    image = tmp_path / "PAT_planningMRI_to_MRI1.nii.gz"
    image.write_bytes(b"not really an image, but a real path")

    state = AppState()
    state.patient_id = "PAT_TEST"
    state.plan = _plan()
    state.plan_mri_in_t1_path = str(image)

    project = tmp_path / "PAT_TEST.json"
    save_project_json(state, project)

    data = load_project_json(project)
    assert data["files"]["plan_mri"]["path"] == str(image)
    # The portability keys apply to it like any other image.
    assert data["files"]["plan_mri"]["path_rel"] == image.name

    reloaded = AppState()
    apply_project_dict_to_state(reloaded, data, project)
    assert reloaded.plan_mri_in_t1_path == str(image)
    assert reloaded.plan["transform"]["reviewed"] is True


def test_a_project_without_a_planning_mri_reloads_clean(tmp_path):
    state = AppState()
    state.patient_id = "PAT_TEST"
    project = tmp_path / "PAT_TEST.json"
    save_project_json(state, project)

    reloaded = AppState()
    apply_project_dict_to_state(reloaded, load_project_json(project), project)
    assert reloaded.plan_mri_in_t1_path is None
    assert reloaded.plan_mri_in_t1 is None


def test_a_moved_planning_mri_is_found_again(tmp_path):
    """It goes through the same relocation cascade as every other image."""
    from neuxelec.project_paths import resolve_project_paths

    original = tmp_path / "old" / "PAT_planningMRI_to_MRI1.nii.gz"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"planning mri in mri 1 space")

    state = AppState()
    state.patient_id = "PAT_TEST"
    state.plan_mri_in_t1_path = str(original)
    project = tmp_path / "old" / "PAT_TEST.json"
    save_project_json(state, project)

    data = load_project_json(project)
    moved = tmp_path / "new"
    os.rename(tmp_path / "old", moved)

    report = resolve_project_paths(data, moved / "PAT_TEST.json")
    found = [r for r in report.resolutions if r.entry.section == "plan_mri"]
    assert found and found[0].found
    assert Path(found[0].resolved).parent == moved
    assert found[0].verified is True
