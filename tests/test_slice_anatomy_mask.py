# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unticking the brainmask shows the whole MRI slice, and nothing else moves.

The 3D view used to refuse that state: unticking both the brainmask and the
pial surface ticked the brainmask straight back on, so the slice was always cut
to the brain. Showing the skull and the scalp is what you want when you are
judging an entry point.

What must not follow is the overlays. PET, fMRI and SISCOM outside the brain is
reconstruction noise, so they stay masked whatever the checkbox says. All five
slice layers go through one function, which is where the two rules part.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Volume:
    """Just enough of a SimpleITK image for the early return."""

    def __init__(self, size=(4, 5, 6)):
        self._size = size

    def GetSize(self):
        return self._size


class _Page:
    """A stand-in carrying only what the two rules read."""

    def __init__(self, brainmask: bool, pial: bool, mni: bool = False):
        self.chk_brainmask = QCheckBox()
        self.chk_brainmask.setChecked(brainmask)
        self.chk_pial = QCheckBox()
        self.chk_pial.setChecked(pial)
        self._mni = mni
        self.masked_called = False

    def _mni_t1_slices_are_visible(self):
        return self._mni

    def _get_3d_plane_mask_for_slices(self, ref_img):
        # Reaching this means the mask was asked for.
        self.masked_called = True
        return None

    _anatomical_slice_is_masked = View3DPage._anatomical_slice_is_masked
    _get_slice_cache_mask_np = View3DPage._get_slice_cache_mask_np


@pytest.mark.parametrize(
    "brainmask, pial, expected",
    [
        (True, False, True),
        (False, True, True),
        (True, True, True),
        (False, False, False),
    ],
)
def test_only_unticking_both_shows_the_whole_slice(app, brainmask, pial, expected):
    page = _Page(brainmask, pial)
    assert page._anatomical_slice_is_masked() is expected


def test_mni_slices_stay_masked_whatever_the_boxes_say(app):
    """An MNI slice only means something inside the template brain."""
    page = _Page(brainmask=False, pial=False, mni=True)
    assert page._anatomical_slice_is_masked() is True


def test_the_anatomical_layer_is_left_whole(app):
    page = _Page(brainmask=False, pial=False)
    mask = page._get_slice_cache_mask_np(_Volume((4, 5, 6)), anatomical=True)

    assert mask is not None
    assert mask.shape == (6, 5, 4)  # z, y, x
    assert mask.all()
    assert not page.masked_called, "the brain mask was asked for anyway"


def test_the_overlays_keep_their_mask(app):
    """The default is False, and every overlay call site leaves it alone."""
    page = _Page(brainmask=False, pial=False)
    page._get_slice_cache_mask_np(_Volume(), anatomical=False)
    assert page.masked_called, "an overlay escaped the brain mask"


def test_a_ticked_box_still_masks_the_anatomy(app):
    page = _Page(brainmask=True, pial=False)
    page._get_slice_cache_mask_np(_Volume(), anatomical=True)
    assert page.masked_called


def test_the_two_anatomical_call_sites_are_the_expected_ones():
    """The split is only correct if exactly the base texture and the crop box
    ask for it. An overlay picking up anatomical=True would silently spill."""
    import inspect

    source = inspect.getsource(View3DPage)
    anatomical = [
        line.strip()
        for line in source.splitlines()
        if "_get_slice_cache_mask_np(ref_img" in line and "anatomical=True" in line
    ]
    others = [
        line.strip()
        for line in source.splitlines()
        if "_get_slice_cache_mask_np(ref_img" in line and "anatomical=True" not in line
    ]
    assert len(anatomical) == 2, anatomical
    assert len(others) == 3, others


# ---------------------------------------------------------------------------
# the context-menu option that unticking both boxes used to hide
# ---------------------------------------------------------------------------


class _Menu:
    """The three things the option's condition reads."""

    def __init__(self, electrodes=True, mni=False, plane=True):
        class _State:
            pass

        self.state = _State()
        self.state.electrodes = [{"name": "A_L"}] if electrodes else []
        self.chk_mni_atlas = QCheckBox()
        self.chk_mni_atlas.setChecked(mni)
        self._plane = plane
        # Both unticked: the state that used to be unreachable.
        self.chk_brainmask = QCheckBox()
        self.chk_pial = QCheckBox()

    def _any_slice_plane_visible(self):
        return self._plane

    _show_keep_electrodes_through_slices_option = (
        View3DPage._show_keep_electrodes_through_slices_option
    )


def test_the_option_survives_unticking_both_boxes(app):
    """It decides whether electrodes are clipped by the planes, which has
    nothing to do with a brain surface being drawn."""
    menu = _Menu()
    assert menu.chk_brainmask.isChecked() is False
    assert menu.chk_pial.isChecked() is False
    assert menu._show_keep_electrodes_through_slices_option() is True


@pytest.mark.parametrize(
    "electrodes, mni, plane, expected",
    [
        (True, False, True, True),
        (False, False, True, False),   # nothing to keep visible
        (True, True, True, False),     # MNI electrodes keep their own behaviour
        (True, False, False, False),   # no plane, nothing clips anything
    ],
)
def test_the_option_still_hides_when_it_is_useless(app, electrodes, mni, plane, expected):
    menu = _Menu(electrodes=electrodes, mni=mni, plane=plane)
    assert menu._show_keep_electrodes_through_slices_option() is expected
