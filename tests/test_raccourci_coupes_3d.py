# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le raccourci Ctrl + fleche + molette des coupes de la vue 3D.

LE DEFAUT SIGNALE

"Mon raccourci pour changer mes slices, axial, coronal et saggital ne
marche pas."

LA CAUSE

Le raccourci se joue en deux temps : une touche arme un plan, la
molette le deplace. Qt ne livre pas ces deux evenements au meme
endroit. La molette va au widget **sous le curseur**, donc a la vue
3D. La touche va au widget qui a le **focus**.

Le filtre etait pose sur le seul interacteur. Afficher un plan se fait
en cochant sa case, ce qui donne le focus a cette case : la fleche y
allait, et le plan n'etait jamais arme. Le raccourci ne fonctionnait
donc qu'immediatement apres un clic dans la vue 3D.

LA CORRECTION

Un second filtre, pose sur l'application, voit la touche quel que soit
le focus. Il ne la consomme que si la vue 3D a le focus, pour qu'une
fleche continue d'atteindre l'arbre ou le champ de texte qui la
detient.

LES CONVENTIONS

    Ctrl + fleche gauche + molette -> sagittal
    Ctrl + fleche bas    + molette -> coronal
    Ctrl + fleche haut   + molette -> axial
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QSlider,
    QWidget,
)

from neuxelec.pages import view3d as mod  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402

PLANS = {"axial": Qt.Key_Up, "coronal": Qt.Key_Down, "sagittal": Qt.Key_Left}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Les vraies methodes, sur de vrais widgets."""

    _slice_slider_and_checkbox = View3DPage._slice_slider_and_checkbox
    _plane_from_keyboard_wheel_arrow = View3DPage._plane_from_keyboard_wheel_arrow
    _handle_slice_slider_keyboard_wheel_event = (
        View3DPage._handle_slice_slider_keyboard_wheel_event
    )
    _handle_slice_plane_key_from_application = (
        View3DPage._handle_slice_plane_key_from_application
    )

    def __init__(self):
        self._view3d_is_fullscreen = False
        self._slice_wheel_active_plane = None

        self._fenetre = QWidget()
        disposition = QHBoxLayout(self._fenetre)

        # Tient la place de l'interacteur PyVista.
        self.interactor = QWidget()
        self.interactor.setFocusPolicy(Qt.StrongFocus)
        disposition.addWidget(self.interactor)

        # Ce qui prend le focus dans la vraie page.
        self.case_ailleurs = QCheckBox()
        self.champ_ailleurs = QLineEdit()
        for w in (self.case_ailleurs, self.champ_ailleurs):
            w.setFocusPolicy(Qt.StrongFocus)
            disposition.addWidget(w)

        self._page_widget = self._fenetre

        for plan in PLANS:
            curseur = QSlider()
            curseur.setRange(0, 200)
            curseur.setValue(100)
            setattr(self, f"sld_{plan}_plane", curseur)
            setattr(self, f"chk_{plan}_plane", QCheckBox())

        self._fenetre.show()

        # Hors ecran, une fenetre montree n'est pas active, et sans
        # fenetre active Qt ne designe aucun widget focalise.
        self._fenetre.activateWindow()
        QApplication.processEvents()

    def curseur(self, plan):
        return getattr(self, f"sld_{plan}_plane")

    def case(self, plan):
        return getattr(self, f"chk_{plan}_plane")


def _touche(cle, mods=Qt.ControlModifier, enfoncee=True):
    return QKeyEvent(
        QEvent.KeyPress if enfoncee else QEvent.KeyRelease, cle, mods
    )


def _molette(crans=1, mods=Qt.ControlModifier):
    return QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, 120 * crans),
        Qt.NoButton,
        mods,
        Qt.NoScrollPhase,
        False,
    )


@pytest.fixture
def page(app):
    p = _Page()
    yield p
    p._fenetre.close()


def _geste(page, plan, crans=1, focus=None):
    """Le geste complet : la touche par l'application, la molette par la vue."""
    if focus is not None:
        focus.setFocus()

    filtre = mod._SlicePlaneKeyFilter(page)
    consomme = filtre.eventFilter(None, _touche(PLANS[plan]))
    page._handle_slice_slider_keyboard_wheel_event(_molette(crans))
    return consomme


# ------------------------------------------- le defaut exact


@pytest.mark.parametrize("plan", sorted(PLANS))
def test_le_raccourci_marche_sans_cliquer_dans_la_vue(page, plan):
    """Le focus est sur la case qui vient d'afficher le plan."""
    _geste(page, plan, focus=page.case_ailleurs)
    assert page.curseur(plan).value() == 101


@pytest.mark.parametrize("plan", sorted(PLANS))
def test_il_marche_aussi_avec_le_focus_dans_la_vue(page, plan):
    """Le cas qui fonctionnait deja doit continuer."""
    _geste(page, plan, focus=page.interactor)
    assert page.curseur(plan).value() == 101


def test_chaque_fleche_ne_bouge_que_son_plan(page):
    _geste(page, "axial", focus=page.case_ailleurs)
    assert page.curseur("axial").value() == 101
    assert page.curseur("coronal").value() == 100
    assert page.curseur("sagittal").value() == 100


def test_la_molette_vers_le_bas_recule(page):
    _geste(page, "axial", crans=-1, focus=page.case_ailleurs)
    assert page.curseur("axial").value() == 99


def test_le_plan_s_affiche_de_lui_meme(page):
    """Inutile de cocher la case avant de naviguer."""
    _geste(page, "coronal", focus=page.champ_ailleurs)
    assert page.case("coronal").isChecked()


# --------------------------- la fleche n'est pas volee a son widget


def test_la_fleche_continue_vers_le_champ_de_texte(page):
    """Sinon Ctrl + fleche gauche ne deplacerait plus le curseur de
    saisie dans un champ de la page."""
    assert _geste(page, "sagittal", focus=page.champ_ailleurs) is False


def test_elle_est_consommee_quand_la_vue_a_le_focus(page):
    """C'est la raison de cette consommation : empecher PyVista de
    tourner la camera a la fleche."""
    assert _geste(page, "axial", focus=page.interactor) is True


def test_le_relachement_non_plus_n_est_pas_vole(page):
    page.interactor.setFocus()
    filtre = mod._SlicePlaneKeyFilter(page)
    filtre.eventFilter(None, _touche(Qt.Key_Up))
    page.champ_ailleurs.setFocus()
    relache = filtre.eventFilter(None, _touche(Qt.Key_Up, enfoncee=False))
    assert relache is False


# ------------------------------------------- quand il doit se taire


def test_une_autre_page_ne_capte_rien(page):
    """Le filtre voit toutes les touches de l'application."""
    page._fenetre.hide()
    _geste(page, "axial", focus=None)
    assert page.curseur("axial").value() == 100


def test_le_plein_ecran_laisse_la_camera_tranquille(page):
    page._view3d_is_fullscreen = True
    _geste(page, "axial", focus=page.case_ailleurs)
    assert page.curseur("axial").value() == 100


def test_sans_interacteur_rien_ne_leve(page):
    page.interactor = None
    _geste(page, "axial", focus=page.case_ailleurs)
    assert page.curseur("axial").value() == 100


def test_une_fleche_seule_n_arme_rien(page):
    """Sans Ctrl, la fleche appartient au widget qui a le focus."""
    filtre = mod._SlicePlaneKeyFilter(page)
    filtre.eventFilter(None, _touche(Qt.Key_Up, Qt.NoModifier))
    page._handle_slice_slider_keyboard_wheel_event(_molette(1))
    assert page.curseur("axial").value() == 100


def test_la_molette_seule_ne_bouge_aucun_plan(page):
    """Elle doit rester le zoom de la camera."""
    page._handle_slice_slider_keyboard_wheel_event(_molette(1))
    assert page.curseur("axial").value() == 100


def test_relacher_la_fleche_desarme(page):
    filtre = mod._SlicePlaneKeyFilter(page)
    filtre.eventFilter(None, _touche(Qt.Key_Up))
    filtre.eventFilter(None, _touche(Qt.Key_Up, enfoncee=False))
    page._handle_slice_slider_keyboard_wheel_event(_molette(1))
    assert page.curseur("axial").value() == 100


def test_relacher_ctrl_desarme(page):
    filtre = mod._SlicePlaneKeyFilter(page)
    filtre.eventFilter(None, _touche(Qt.Key_Up))
    filtre.eventFilter(None, _touche(Qt.Key_Control, enfoncee=False))
    page._handle_slice_slider_keyboard_wheel_event(_molette(1))
    assert page.curseur("axial").value() == 100


def test_le_filtre_ignore_ce_qui_n_est_pas_une_touche(page):
    """Il est pose sur l'application : il doit etre indolore."""
    filtre = mod._SlicePlaneKeyFilter(page)
    assert filtre.eventFilter(None, _molette(1)) is False


# --------------------------------------- le filtre est bien pose


def test_le_filtre_est_installe_sur_l_application():
    """Pose sur le seul interacteur, il ne verrait pas la touche."""
    import inspect

    source = inspect.getsource(View3DPage)
    assert "app.installEventFilter(self._slice_plane_key_filter)" in source


def test_le_filtre_de_l_interacteur_reste(page):
    """Il porte la molette, le survol et le marqueur."""
    import inspect

    source = inspect.getsource(View3DPage)
    assert "self.interactor.installEventFilter(" in source
