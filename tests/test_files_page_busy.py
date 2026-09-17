"""A long operation must give the buttons back when it finishes.

``_set_busy`` used to read ``setEnabled((not busy) and b.isEnabled())``. By the
time that ran with ``busy=False`` the button was already disabled, so the
expression stayed false and the button was lost for the rest of the session.
Every caller happened to follow with ``_update_buttons()``, which rebuilt the
states and hid the trap, until the planning MRI registration did not: reviewing
the CT alignment and every Save button died with it.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

from neuxelec.pages.files_page import FilesPage  # noqa: E402

CHECKBOXES = ("chk_t1", "chk_t2", "chk_fmri", "chk_ct", "chk_pet", "chk_ictal", "chk_interictal")


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _State:
    """A patient whose CT is validated, so its Save button is live."""

    t1_path = r"C:\patient\T1.nii"
    ct_path = r"C:\patient\CT.nii"
    ct_validated = True
    t2_validated = False
    fmri_validated = False
    pet_validated = False
    ictal_spect_validated = False
    interictal_spect_validated = False
    siscom_validated = False
    brainmask_generated = True


@pytest.fixture
def page(qt_app):
    page = FilesPage.__new__(FilesPage)
    page.state = _State()
    for name in FilesPage._BUSY_BUTTONS + ("btn_brainmask", "btn_iso_surface"):
        setattr(page, name, QPushButton(name))
    for name in CHECKBOXES:
        setattr(page, name, QCheckBox(name))
    page.chk_ct.setChecked(True)
    page._page_widget = None
    page.ui = None
    # These live in the main window and are not what this is about.
    page._enable_3d_checkbox = lambda *a, **k: None
    page._refresh_coreg_progress_ui = lambda *a, **k: None
    page._sync_files_status_overview = lambda *a, **k: None
    page._update_buttons()
    return page


def _states(page):
    return {name: getattr(page, name).isEnabled() for name in FilesPage._BUSY_BUTTONS}


def test_busy_gives_every_button_back(page):
    """The regression: this is what the planning MRI registration broke."""
    before = _states(page)
    assert before["btn_check_coreg"], "reviewing the CT alignment must be possible"
    assert before["btn_save_ct"], "a validated CT must be savable"

    page._set_busy(True)
    assert not any(_states(page).values()), "everything is taken away while busy"

    page._set_busy(False)
    assert _states(page) == before


def test_a_button_that_was_off_stays_off(page):
    """Giving the buttons back must not enable what was never available."""
    before = _states(page)
    assert not before["btn_save_pet"], "no PET is validated in this patient"

    page._set_busy(True)
    page._set_busy(False)
    assert not _states(page)["btn_save_pet"]


def test_nested_operations_restore_the_outermost_state(page):
    before = _states(page)
    page._set_busy(True)
    page._set_busy(True)
    page._set_busy(False)
    assert _states(page) == before


def test_restoring_twice_is_harmless(page):
    before = _states(page)
    page._set_busy(True)
    page._set_busy(False)
    page._set_busy(False)
    assert _states(page) == before


def test_update_buttons_still_agrees_after_a_busy_cycle(page):
    """Callers that also rebuild the states must reach the same place."""
    before = _states(page)
    page._set_busy(True)
    page._set_busy(False)
    page._update_buttons()
    assert _states(page) == before
