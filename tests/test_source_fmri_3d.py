# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La case fMRI de la vue 3D ne s'allume que s'il y a un fMRI.

LE DEFAUT SIGNALE

Sur un patient sans fMRI, la case etait cochable, et la cocher
affichait quelque chose d'inexplique.

A ses debuts le fMRI etait range dans la case MRI 2, faute de case a
lui. Il a depuis sa propre modalite, mais le repli sur MRI 2 est reste
dans la source : un patient avec un MRI 2 coregistre, et c'est le cas
de BB, voyait donc sa case fMRI s'activer, et la cocher lui montrait
son T2 seuille et colorie comme une carte d'activation.

Le commentaire place juste sous ce repli affirmait qu'il n'existait
pas. C'est desormais vrai.
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


class _Etat:
    def __init__(self, **images):
        for nom in (
            "fmri_coreg_in_t1",
            "fmri_in_t1",
            "t2_coreg_in_t1",
            "t2_in_t1",
        ):
            setattr(self, nom, images.get(nom))


class _Page:
    _fmri_source_image = View3DPage._fmri_source_image
    _refresh_fmri_3d_controls = View3DPage._refresh_fmri_3d_controls

    def __init__(self, state):
        self.state = state
        self.chk_fmri_3d = QCheckBox()
        self.chk_fmri_3d.setChecked(True)

    def _sync_fmri_min_cluster_widget(self):
        pass

    def _set_checked(self, case, valeur):
        case.blockSignals(True)
        case.setChecked(bool(valeur))
        case.blockSignals(False)


IMAGE = object()


# --------------------------------------------- la source


def test_sans_rien_il_n_y_a_pas_de_source(app):
    assert _Page(_Etat())._fmri_source_image() is None


@pytest.mark.parametrize("attribut", ["fmri_coreg_in_t1", "fmri_in_t1"])
def test_un_fmri_est_une_source(app, attribut):
    page = _Page(_Etat(**{attribut: IMAGE}))
    assert page._fmri_source_image() is IMAGE


@pytest.mark.parametrize("attribut", ["t2_coreg_in_t1", "t2_in_t1"])
def test_un_mri2_n_est_pas_une_source(app, attribut):
    """Le defaut exact : c'est ce que BB voyait s'afficher."""
    page = _Page(_Etat(**{attribut: IMAGE}))
    assert page._fmri_source_image() is None


def test_le_fmri_prime_quand_les_deux_existent(app):
    autre = object()
    page = _Page(_Etat(fmri_coreg_in_t1=IMAGE, t2_coreg_in_t1=autre))
    assert page._fmri_source_image() is IMAGE


def test_le_coregistre_prime_sur_le_brut(app):
    brut = object()
    page = _Page(_Etat(fmri_coreg_in_t1=IMAGE, fmri_in_t1=brut))
    assert page._fmri_source_image() is IMAGE


# ------------------------------------------- la case suit


def test_la_case_reste_grisee_sans_fmri(app):
    page = _Page(_Etat())
    page._refresh_fmri_3d_controls()
    assert not page.chk_fmri_3d.isEnabled()


def test_le_cas_de_bb_ne_l_allume_plus(app):
    """Un MRI 2 coregistre et valide, aucun fMRI."""
    page = _Page(_Etat(t2_coreg_in_t1=IMAGE))
    page._refresh_fmri_3d_controls()
    assert not page.chk_fmri_3d.isEnabled()


def test_une_case_grisee_est_aussi_decochee(app):
    """Sinon elle resterait cochee sur un calque qui n'existe pas."""
    page = _Page(_Etat(t2_coreg_in_t1=IMAGE))
    page._refresh_fmri_3d_controls()
    assert not page.chk_fmri_3d.isChecked()


def test_un_vrai_fmri_allume_la_case(app):
    page = _Page(_Etat(fmri_coreg_in_t1=IMAGE))
    page._refresh_fmri_3d_controls()
    assert page.chk_fmri_3d.isEnabled()


def test_sans_case_rien_ne_leve(app):
    page = _Page(_Etat())
    page.chk_fmri_3d = None
    page._refresh_fmri_3d_controls()
