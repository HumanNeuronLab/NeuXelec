# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le cerveau n'est dessine que si une source est cochee.

Le defaut : _render_brain redessinait le brainmask des lors que son image
existait, meme sa case decochee. _on_brain_source, lui, retire l'acteur et
documente "aucune des deux" comme un choix legitime. Les deux se
contredisaient, et le brainmask revenait au premier rendu venu, par
exemple en changeant de parcellation.

Ces tests lisent la logique de rendu sur un double de la page, sans carte
graphique : ce qui compte est la decision, dessiner ou retirer.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Juste de quoi atteindre la decision du rendu."""

    def __init__(self, brainmask=True, pial=False, image=True):
        self.plotter = object()
        self.chk_brainmask = QCheckBox()
        self.chk_brainmask.setChecked(brainmask)
        self.chk_pial = QCheckBox()
        self.chk_pial.setChecked(pial)
        self._brainmask_img = object() if image else None
        self._lh_pial_mask_img = None
        self._rh_pial_mask_img = None
        self._lh_pial_poly = None
        self._rh_pial_poly = None
        self._show_lh_pial = True
        self._show_rh_pial = True
        self.retires = []
        self.maillages = 0
        self.rendus = 0

    def _remove_actor(self, which):
        self.retires.append(which)

    def _render(self):
        self.rendus += 1

    def _binarymask_to_polydata(self, _img):
        self.maillages += 1
        return None          # suffit : la suite retire l'acteur

    _render_brain = View3DPage._render_brain


def test_le_brainmask_coche_est_dessine(app):
    page = _Page(brainmask=True)
    page._render_brain()
    assert page.maillages == 1, "le maillage n'a pas ete demande"


def test_le_brainmask_decoche_n_est_pas_dessine(app):
    """Le defaut signale : il revenait des qu'un rendu passait par la."""
    page = _Page(brainmask=False)
    page._render_brain()
    assert page.maillages == 0, "le brainmask a ete dessine malgre sa case"
    assert "brain" in page.retires


def test_sans_image_rien_n_est_dessine(app):
    page = _Page(brainmask=True, image=False)
    page._render_brain()
    assert page.maillages == 0
    assert "brain" in page.retires


def test_la_surface_piale_cochee_passe_avant(app):
    """Elle a sa propre branche, qui ne doit pas tomber dans celle du
    brainmask."""
    page = _Page(brainmask=False, pial=True)
    page._render_brain()
    # Aucune surface piale chargee : la branche piale retire et sort,
    # sans jamais demander le maillage du brainmask.
    assert page.maillages == 0
    assert "brain" in page.retires


# ------------------------------------------------------ la case en mode MNI


class _PageOpacite:
    """De quoi exercer _update_brain_opacity_slider_states."""

    def __init__(self, mni=False):
        from PySide6.QtWidgets import QSlider, QSpinBox

        self.chk_mni_atlas = QCheckBox()
        self.chk_mni_atlas.setChecked(mni)
        self.chk_brainmask = QCheckBox()
        self.chk_pial = QCheckBox()
        self.sld_3d_brainMaskOpacity = QSlider()
        self.spn_3d_brainMaskOpacity = QSpinBox()
        self.sld_3d_PialOpacity = QSlider()

    _update_brain_opacity_slider_states = (
        View3DPage._update_brain_opacity_slider_states
    )


def test_la_case_du_brainmask_disparait_en_mode_mni(app):
    """Elle commande le cerveau du patient : cliquee depuis l'onglet MNI
    elle quitterait le mode, ce qui n'est pas ce qu'on demande en reglant
    un cerveau."""
    page = _PageOpacite(mni=True)
    page.chk_brainmask.show()
    page._update_brain_opacity_slider_states()
    assert not page.chk_brainmask.isVisible()


def test_la_case_revient_hors_du_mode_mni(app):
    page = _PageOpacite(mni=False)
    page.chk_brainmask.setVisible(False)
    page._update_brain_opacity_slider_states()
    assert not page.chk_brainmask.isHidden()


def test_toute_la_rangee_du_brainmask_disparait_en_mode_mni(app):
    """Curseur et boite compris : ils commandent le cerveau du patient, et
    le gabarit a desormais son propre reglage dans son onglet."""
    page = _PageOpacite(mni=True)
    for w in (page.chk_brainmask, page.sld_3d_brainMaskOpacity, page.spn_3d_brainMaskOpacity):
        w.show()
    page._update_brain_opacity_slider_states()
    assert not page.chk_brainmask.isVisible()
    assert not page.sld_3d_brainMaskOpacity.isVisible()
    assert not page.spn_3d_brainMaskOpacity.isVisible()


def test_le_curseur_du_brainmask_ne_sert_plus_qu_au_patient(app):
    """Il etait actif en mode MNI parce qu'il y commandait le gabarit."""
    page = _PageOpacite(mni=True)
    page.chk_brainmask.setChecked(False)
    page._update_brain_opacity_slider_states()
    assert not page.sld_3d_brainMaskOpacity.isEnabled()

    natif = _PageOpacite(mni=False)
    natif.chk_brainmask.setChecked(True)
    natif._update_brain_opacity_slider_states()
    assert natif.sld_3d_brainMaskOpacity.isEnabled()
    assert natif.spn_3d_brainMaskOpacity.isEnabled()
