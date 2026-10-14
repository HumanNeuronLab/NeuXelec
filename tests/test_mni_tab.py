# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""L'onglet MNI : entrer, emprunter, sortir, tout rendre.

Ce qui doit tenir :

  - arriver sur l'onglet allume le mode MNI, et le quitter l'eteint. Tout
    le mode MNI passe par la meme bascule qu'avant, celle qui sait deja
    retenir puis restituer les onze cases natives ;
  - les cartes empruntees reviennent exactement a leur place, y compris
    dans la grille de l'onglet Brain, ou une carte rendue a la fin
    changerait de rangee ;
  - quitter le mode MNI par un autre chemin, en cliquant Brain mask par
    exemple, ne laisse pas l'onglet ouvert avec les cartes en otage.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile  # noqa: E402
from PySide6.QtUiTools import QUiLoader  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QFrame,
    QPushButton,
    QTabWidget,
)

from neuxelec.pages.view3d import View3DPage  # noqa: E402
from neuxelec.ui.card_borrowing import CardBorrower  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402

EMPRUNTEES = ("card3DSlices", "card3DParcellation", "card3DRegions")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Juste de quoi exercer l'onglet, sans la scene 3D."""

    def __init__(self, ui):
        self.ui = ui
        self.chk_mni_atlas = QCheckBox()
        self.bascules = []
        self.chk_mni_atlas.toggled.connect(lambda v: self.bascules.append(bool(v)))
        self.rafraichissements = 0
        self.charges = 0
        self.opacites = []
        self._loading_overlay = None

    def open_mni_electrodes_files(self):
        self.charges += 1

    def _update_brain_opacity(self):
        self.opacites.append(self._mni_brain_opacity())

    def _refresh_parcellation_regions(self, force=False):
        self.rafraichissements += 1

    _build_mni_tab = View3DPage._build_mni_tab
    _build_mni_brain_row = View3DPage._build_mni_brain_row
    _row_index_of = staticmethod(View3DPage._row_index_of)
    _on_mni_brain_toggled = View3DPage._on_mni_brain_toggled
    _stop_region_plot_for_mode_switch = View3DPage._stop_region_plot_for_mode_switch
    _mni_brain_opacity = View3DPage._mni_brain_opacity
    MNI_BRAIN_OPACITY_DEFAULT = View3DPage.MNI_BRAIN_OPACITY_DEFAULT
    _mni_tab_index = View3DPage._mni_tab_index
    _enter_mni_tab = View3DPage._enter_mni_tab
    _enter_mni_tab_work = View3DPage._enter_mni_tab_work
    _leave_mni_tab = View3DPage._leave_mni_tab
    _leave_mni_tab_work = View3DPage._leave_mni_tab_work
    _on_mni_state_changed = View3DPage._on_mni_state_changed
    _on_3d_tab_changed = View3DPage._on_3d_tab_changed
    MNI_BORROWED_LEFT = View3DPage.MNI_BORROWED_LEFT
    MNI_BORROWED_RIGHT = View3DPage.MNI_BORROWED_RIGHT


@pytest.fixture
def page(app):
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly)
    try:
        ui = QUiLoader().load(f)
    finally:
        f.close()
    assert ui is not None
    p = _Page(ui)
    p._build_mni_tab()
    # Le vrai cablage, pose par _hook_controls, que ce double n'execute pas.
    ui.findChild(QTabWidget, "tabWidget3D").currentChanged.connect(
        p._on_3d_tab_changed
    )
    return p


def _jouer_les_minuteries(tours=6):
    """Derouler les QTimer.singleShot(0) poses par les bascules.

    Elles existent pour que le voile de chargement ait le temps de
    s'afficher avant que la scene ne se defasse.
    """
    for _ in range(tours):
        QApplication.processEvents()


def _place(ui, nom):
    """Ou se trouve une carte, au sens de ce qui change la mise en page.

    Dans une grille, c'est la case qui compte : l'ordre d'insertion n'a
    aucun effet, et le comparer ferait echouer le test pour rien.
    """
    carte = ui.findChild(QFrame, nom)
    assert carte is not None, nom
    endroit = CardBorrower._locate(carte)
    if endroit is None:
        return None
    if endroit.grid is not None:
        return (endroit.layout.objectName(), endroit.grid)
    return (endroit.layout.objectName(), endroit.index)


# ------------------------------------------------------------- l'onglet


def test_l_onglet_mni_existe_et_vient_en_dernier(page):
    onglets = page.ui.findChild(QTabWidget, "tabWidget3D")
    assert onglets.tabText(onglets.count() - 1) == "MNI"
    assert page._mni_tab_index() == onglets.count() - 1


def test_la_case_du_cadre_brain_est_retiree_de_la_vue(page):
    """L'onglet la remplace. Elle reste la, tout le mode passe par elle."""
    assert not page.chk_mni_atlas.isVisible()


def test_le_bouton_de_chargement_est_pose(page):
    bouton = page.ui.findChild(QPushButton, "btn_3d_loadMniElectrodes")
    assert bouton is not None
    bouton.click()
    assert page.charges == 1


# ------------------------------------------------------- entrer et sortir


def test_arriver_sur_l_onglet_allume_le_mode_mni(page):
    onglets = page.ui.findChild(QTabWidget, "tabWidget3D")
    page._on_3d_tab_changed(page._mni_tab_index())
    _jouer_les_minuteries()
    assert page.chk_mni_atlas.isChecked()
    assert page.bascules == [True]
    assert onglets is not None


def test_quitter_l_onglet_eteint_le_mode_mni(page):
    page._on_3d_tab_changed(page._mni_tab_index())
    _jouer_les_minuteries()
    page._on_3d_tab_changed(0)
    _jouer_les_minuteries()
    assert not page.chk_mni_atlas.isChecked()
    assert page.bascules == [True, False]


def test_les_cartes_sont_empruntees_puis_rendues_a_leur_place(page):
    """Le piege : une carte rendue a la fin d'une grille change de rangee."""
    avant = {nom: _place(page.ui, nom) for nom in EMPRUNTEES}

    page._on_3d_tab_changed(page._mni_tab_index())
    _jouer_les_minuteries()
    gauche = page.ui.findChild(QFrame, "card3DMniLeft")
    droite = page.ui.findChild(QFrame, "card3DMniRight")
    # Tous les reglages a gauche, le tableau seul a droite.
    assert page.ui.findChild(QFrame, "card3DSlices").parentWidget() is gauche
    assert page.ui.findChild(QFrame, "card3DParcellation").parentWidget() is gauche
    assert page.ui.findChild(QFrame, "card3DRegions").parentWidget() is droite
    ordre = [
        droite.layout().itemAt(i).widget().objectName()
        for i in range(droite.layout().count())
    ]
    assert ordre == ["card3DRegions"]

    page._on_3d_tab_changed(0)
    _jouer_les_minuteries()
    assert {nom: _place(page.ui, nom) for nom in EMPRUNTEES} == avant


def test_revenir_deux_fois_ne_double_pas_les_emprunts(page):
    page._on_3d_tab_changed(page._mni_tab_index())
    _jouer_les_minuteries()
    page._on_3d_tab_changed(page._mni_tab_index())
    _jouer_les_minuteries()
    gauche = page.ui.findChild(QFrame, "card3DMniLeft")
    # Compter les cartes empruntees, et non les elements de la colonne :
    # elle porte aussi le bouton de chargement et le reglage d'opacite.
    cartes = [
        gauche.layout().itemAt(i).widget().objectName()
        for i in range(gauche.layout().count())
        if gauche.layout().itemAt(i).widget() is not None
        and gauche.layout().itemAt(i).widget().objectName().startswith("card3D")
    ]
    assert cartes == list(_Page.MNI_BORROWED_LEFT)


def test_l_onglet_parcellation_rafraichit_toujours_son_tableau(page):
    """Le comportement d'avant ne doit pas avoir disparu dans l'aiguillage."""
    onglets = page.ui.findChild(QTabWidget, "tabWidget3D")
    index = next(
        i for i in range(onglets.count()) if onglets.tabText(i) == "Parcellation"
    )
    page._on_3d_tab_changed(index)
    assert page.rafraichissements == 1


# --------------------------------------------- quitter par un autre chemin


def test_eteindre_le_mni_ailleurs_ne_laisse_pas_les_cartes_en_otage(page):
    """Cliquer Brain mask quitte le mode MNI : l'onglet doit suivre."""
    avant = {nom: _place(page.ui, nom) for nom in EMPRUNTEES}
    onglets = page.ui.findChild(QTabWidget, "tabWidget3D")
    onglets.setCurrentIndex(page._mni_tab_index())
    _jouer_les_minuteries()
    assert page._mni_borrower.is_borrowing()

    # Le mode MNI s'eteint par un autre chemin.
    page.chk_mni_atlas.setChecked(False)
    for _ in range(4):
        QApplication.processEvents()

    assert onglets.currentIndex() == 0, "l'onglet MNI est reste ouvert"
    assert {nom: _place(page.ui, nom) for nom in EMPRUNTEES} == avant


def test_sortir_sans_etre_entre_ne_fait_rien(page):
    page._leave_mni_tab()
    assert page.bascules == []
    assert not page._mni_borrower.is_borrowing()


# ------------------------------------------- l'opacite propre au gabarit


def test_le_gabarit_a_son_propre_curseur(page):
    """Il ne partage plus celui du brainmask, qui commande le cerveau du
    patient : deux objets de la scene, deux reglages."""
    from PySide6.QtWidgets import QSlider, QSpinBox

    curseur = page.ui.findChild(QSlider, "sld_3d_mniBrainOpacity")
    boite = page.ui.findChild(QSpinBox, "spinBox_3d_mniBrainOpacity")
    assert curseur is not None and boite is not None
    assert curseur.value() == _Page.MNI_BRAIN_OPACITY_DEFAULT


def test_le_curseur_et_sa_boite_se_suivent(page):
    from PySide6.QtWidgets import QSlider, QSpinBox

    curseur = page.ui.findChild(QSlider, "sld_3d_mniBrainOpacity")
    boite = page.ui.findChild(QSpinBox, "spinBox_3d_mniBrainOpacity")
    curseur.setValue(30)
    assert boite.value() == 30
    boite.setValue(80)
    assert curseur.value() == 80


def test_bouger_le_curseur_redessine_le_gabarit(page):
    from PySide6.QtWidgets import QSlider

    page.ui.findChild(QSlider, "sld_3d_mniBrainOpacity").setValue(25)
    assert page.opacites[-1] == 0.25


def test_l_opacite_reste_entre_zero_et_un(page):
    from PySide6.QtWidgets import QSlider

    curseur = page.ui.findChild(QSlider, "sld_3d_mniBrainOpacity")
    curseur.setRange(-400, 400)
    curseur.setValue(-300)
    assert page._mni_brain_opacity() == 0.0
    curseur.setValue(300)
    assert page._mni_brain_opacity() == 1.0


def test_sans_curseur_l_opacite_garde_sa_valeur_de_depart(app):
    """Une page sans l'onglet doit rester utilisable."""
    class _Nue:
        MNI_BRAIN_OPACITY_DEFAULT = 50
        _mni_brain_opacity = View3DPage._mni_brain_opacity

    assert _Nue()._mni_brain_opacity() == 0.5


# ---------------------------------------- le cerveau du gabarit, dans les coupes


def test_la_rangee_du_gabarit_est_dans_la_carte_des_coupes(page):
    """A cote de celle du patient, jamais en meme temps qu'elle."""
    from PySide6.QtWidgets import QCheckBox as _QCheckBox
    from PySide6.QtWidgets import QSlider, QSpinBox

    carte = page.ui.findChild(QFrame, "card3DSlices")
    assert carte.findChild(_QCheckBox, "chk_3d_showMniBrain") is not None
    assert carte.findChild(QSlider, "sld_3d_mniBrainOpacity") is not None
    assert carte.findChild(QSpinBox, "spinBox_3d_mniBrainOpacity") is not None


def test_la_rangee_du_gabarit_est_juste_sous_le_titre(page):
    """Son rang ne depend plus d'une voisine qui peut demenager.

    Elle suivait la rangee du brainmask du patient, qui est repartie
    dans la carte Surfaces : l'ancrage l'aurait alors envoyee en bas de
    la carte, sous les trois plans.
    """
    carte = page.ui.findChild(QFrame, "card3DSlices")
    layout = carte.layout()
    rang_titre = page._row_index_of(layout, "lbl3DSlicesCard")
    assert rang_titre >= 0, "le titre de la carte est introuvable"

    from PySide6.QtWidgets import QCheckBox as _QCheckBox

    case = carte.findChild(_QCheckBox, "chk_3d_showMniBrain")
    rang_gabarit = next(
        i
        for i in range(layout.count())
        if layout.itemAt(i).layout() is not None
        and layout.itemAt(i).layout().indexOf(case) >= 0
    )
    assert rang_gabarit == rang_titre + 1


def test_la_rangee_du_gabarit_est_cachee_au_depart(page):
    """Elle n'apparait qu'en mode MNI."""
    assert not page.chk_mni_brain.isVisible()
    assert not page.sld_mni_brain_opacity.isVisible()


def test_la_case_du_gabarit_cache_son_cerveau_sans_le_refaire(page):
    class _Acteur:
        def __init__(self):
            self.visible = True

        def SetVisibility(self, v):  # noqa: N802
            self.visible = bool(v)

    page._mni_atlas_actor = _Acteur()
    page._render = lambda: None

    page.chk_mni_brain.setChecked(False)
    assert not page._mni_atlas_actor.visible
    page.chk_mni_brain.setChecked(True)
    assert page._mni_atlas_actor.visible


def test_sans_acteur_la_case_ne_fait_rien_lever(page):
    page._mni_atlas_actor = None
    page._render = lambda: None
    page.chk_mni_brain.setChecked(False)


def test_changer_de_repere_decoche_le_trace_des_regions(page):
    """Il ne se transporte pas : les maillages sont tailles dans un
    espace, et celui d'en face a ses propres etiquettes."""
    from PySide6.QtWidgets import QCheckBox as _QCheckBox
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from neuxelec.ui.parcellation_region_panel import ParcellationRegionPanel

    hote = QWidget()
    cadre = QFrame(hote)
    cadre.setObjectName("card3DRegions")
    QVBoxLayout(cadre)
    panneau = ParcellationRegionPanel(hote)
    assert panneau.build()
    panneau.set_plotting(True)

    page._region_panel = panneau
    page._region_actors = {}
    page._region_queue = []
    page._clear_region_actors = lambda: None

    page._stop_region_plot_for_mode_switch()
    assert not panneau.is_plotting()
    assert isinstance(cadre.findChild(_QCheckBox, ""), object)


def test_sans_panneau_la_bascule_ne_fait_rien_lever(page):
    page._region_panel = None
    page._stop_region_plot_for_mode_switch()
