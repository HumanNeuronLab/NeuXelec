# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Choisir MRI 1 ou MRI 2 dans la colonne des calques.

CE QUI CHANGE

Les deux IRM partagent une carte parce qu'elles partagent un reglage,
une opacite. Une liste deroulante y choisissait laquelle : deux gestes
pour une seule question, et un choix de plus que les autres calques
n'en demandent. La colonne repond deja a cette question, donc cliquer
MRI 1 regle MRI 1, comme cliquer PET montre les reglages du PET.

Chaque IRM garde sa propre valeur : la carte change ce qu'elle edite,
pas ce qu'elle dessine. Le titre de la carte nomme celle qui est
reglee, sans quoi rien ne distinguerait les deux etats du meme
curseur.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLabel,
    QSlider,
    QSpinBox,
)

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402
from neuxelec.ui.overlay_layer_list import LAYERS, LAYERS_OBLIQUE  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import load_ui  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------- les listes ont disparu du .ui


@pytest.fixture(scope="module")
def ui(app):
    return load_ui(resource_path("resources/ui/MainWindow.ui"))


@pytest.mark.parametrize(
    "nom", ["comboBox_3dView_MRI", "comboBox_obliqueSlice_MRI"]
)
def test_le_selecteur_a_disparu(ui, nom):
    assert ui.findChild(QComboBox, nom) is None, nom


@pytest.mark.parametrize("nom", ["lbl3DMRICard", "lblObliqueMRICard"])
def test_le_titre_de_la_carte_existe_pour_le_remplacer(ui, nom):
    """C'est lui qui dira desormais quelle IRM est reglee."""
    assert ui.findChild(QLabel, nom) is not None, nom


@pytest.mark.parametrize(
    "layers,cle", [(LAYERS, "mri1"), (LAYERS, "mri2"),
                   (LAYERS_OBLIQUE, "mri1"), (LAYERS_OBLIQUE, "mri2")]
)
def test_les_deux_irm_partagent_toujours_leur_carte(layers, cle):
    """Une seule carte pour un seul reglage : c'est tout l'interet."""
    cartes = {l.card for l in layers if l.key in ("mri1", "mri2")}
    assert len(cartes) == 1, cartes
    assert cle in {l.key for l in layers}


# ----------------------------------------------- la vue 3D


class _Page3D:
    _on_overlay_layer_selected = View3DPage._on_overlay_layer_selected
    _sync_mri_opacity_widgets_3d = View3DPage._sync_mri_opacity_widgets_3d
    MRI_CARD_TITLES = View3DPage.MRI_CARD_TITLES

    def __init__(self, ui):
        self.ui = ui
        self._mri_edited_3d = "T1"
        self._mri_opacity_3d = {"T1": 100, "T2": 40}
        self.sld_mri_3d = QSlider()
        self.sld_mri_3d.setRange(0, 100)
        self.spn_mri_3d = QSpinBox()
        self.spn_mri_3d.setRange(0, 100)
        self.emis = []
        self.sld_mri_3d.valueChanged.connect(self.emis.append)


@pytest.fixture
def page3d(ui):
    return _Page3D(ui)


def test_choisir_mri2_regle_mri2(page3d):
    page3d._on_overlay_layer_selected("mri2")
    assert page3d._mri_edited_3d == "T2"
    assert page3d.sld_mri_3d.value() == 40


def test_revenir_sur_mri1_rend_sa_valeur(page3d):
    page3d._on_overlay_layer_selected("mri2")
    page3d._on_overlay_layer_selected("mri1")
    assert page3d._mri_edited_3d == "T1"
    assert page3d.sld_mri_3d.value() == 100


def test_le_titre_nomme_l_irm_reglee(page3d, ui):
    titre = ui.findChild(QLabel, "lbl3DMRICard")
    page3d._on_overlay_layer_selected("mri2")
    assert titre.text() == "MRI 2"
    page3d._on_overlay_layer_selected("mri1")
    assert titre.text() == "MRI 1"


@pytest.mark.parametrize("cle", ["pet", "ct", "siscom", "fmri", "ictal"])
def test_un_autre_calque_ne_touche_pas_a_l_irm(page3d, cle):
    """Choisir le PET ne doit pas rediriger le curseur des IRM."""
    page3d._on_overlay_layer_selected("mri2")
    page3d._on_overlay_layer_selected(cle)
    assert page3d._mri_edited_3d == "T2"


def test_changer_d_irm_n_emet_aucun_signal(page3d):
    """Sinon la valeur affichee serait relue comme un geste de
    l'utilisateur, et ecraserait celle de l'autre IRM."""
    page3d._on_overlay_layer_selected("mri2")
    assert page3d.emis == [], page3d.emis


# ----------------------------------------------- la coupe oblique


class _PageOblique:
    _on_overlay_layer_selected = ObliqueSlicePage._on_overlay_layer_selected
    _sync_oblique_mri_opacity_widgets = (
        ObliqueSlicePage._sync_oblique_mri_opacity_widgets
    )
    MRI_CARD_TITLES = ObliqueSlicePage.MRI_CARD_TITLES

    def __init__(self, ui):
        self.ui = ui
        self._oblique_mri_edited = "T1"
        self._oblique_mri_opacity = {"T1": 90, "T2": 30}
        self.sld_mri = QSlider()
        self.sld_mri.setRange(0, 100)
        self.spn_mri = QSpinBox()
        self.spn_mri.setRange(0, 100)


def test_la_coupe_oblique_suit_le_meme_chemin(ui):
    page = _PageOblique(ui)
    titre = ui.findChild(QLabel, "lblObliqueMRICard")

    page._on_overlay_layer_selected("mri2")
    assert page._oblique_mri_edited == "T2"
    assert page.sld_mri.value() == 30
    assert titre.text() == "MRI 2"

    page._on_overlay_layer_selected("mri1")
    assert page._oblique_mri_edited == "T1"
    assert page.sld_mri.value() == 90
    assert titre.text() == "MRI 1"


def test_un_autre_calque_ne_touche_pas_a_l_irm_en_oblique(ui):
    page = _PageOblique(ui)
    page._on_overlay_layer_selected("mri2")
    page._on_overlay_layer_selected("siscom")
    assert page._oblique_mri_edited == "T2"
