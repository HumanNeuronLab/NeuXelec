# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les deux barres de rotation des plans de coupe.

CE QU'ELLES NE SONT PAS

Ce ne sont pas des barres de defilement dans un document. Elles
portent un angle, qui boucle, et chaque bout vaut un degre. La page
avale deja tous les clics gauches pour les lire comme une position : un
clic sur une fleche devait donc etre reconnu **avant**, sans quoi viser
la fleche du haut ramenait le plan a 0 au lieu de lui retirer un degre.

CE QUE CES TESTS FIGENT

  - les deux fleches existent et sont atteignables a la souris ;
  - un clic au centre de chacune est reconnu comme tel, mesure par le
    style de Qt et non devine d'apres la hauteur ;
  - le pas vaut un degre, et l'angle boucle aux deux bouts ;
  - un clic ailleurs reste une position, comme avant.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QScrollBar,
    QStackedWidget,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import load_ui  # noqa: E402

BARRES = ("verticalScrollBar_1st", "verticalScrollBar_2nd")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Les deux methodes, et le compte des redessins demandes."""

    _rotation_arrow_at = ObliqueSlicePage._rotation_arrow_at
    _step_rotation = ObliqueSlicePage._step_rotation

    def __init__(self):
        self.redessins = []

    def _on_rotation_changed(self, slot_index):
        self.redessins.append(int(slot_index))


@pytest.fixture(scope="module")
def fenetre(app):
    """La page montee : un style ne se mesure que sur un widget reel."""
    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    page = w.findChild(QWidget, "pageObliqueSlices")
    assert page is not None
    for pile in w.findChildren(QStackedWidget):
        if pile.indexOf(page) >= 0:
            pile.setCurrentWidget(page)
    w.resize(1700, 1000)
    w.show()
    app.processEvents()
    for nom in BARRES:
        barre = w.findChild(QScrollBar, nom)
        barre.setRange(0, 359)
    app.processEvents()
    return w


def _rect(barre, sous_controle):
    option = QStyleOptionSlider()
    barre.initStyleOption(option)
    return barre.style().subControlRect(
        QStyle.CC_ScrollBar, option, sous_controle, barre
    )


def _clic(barre, point: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPointF(point),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )


# ------------------------------------------------- les fleches existent


@pytest.mark.parametrize("nom", BARRES)
def test_les_deux_fleches_ont_une_surface(fenetre, nom):
    """Le reglage global les mettait a 0 px : elles etaient la, invisibles
    et inatteignables."""
    barre = fenetre.findChild(QScrollBar, nom)
    for sous in (QStyle.SC_ScrollBarSubLine, QStyle.SC_ScrollBarAddLine):
        r = _rect(barre, sous)
        assert r.width() > 0 and r.height() > 0, (nom, sous, r)


@pytest.mark.parametrize("nom", BARRES)
def test_les_fleches_sont_aux_deux_bouts(fenetre, nom):
    barre = fenetre.findChild(QScrollBar, nom)
    haut = _rect(barre, QStyle.SC_ScrollBarSubLine)
    bas = _rect(barre, QStyle.SC_ScrollBarAddLine)
    assert haut.top() <= 1, haut
    assert bas.bottom() >= barre.height() - 2, (bas, barre.height())


# --------------------------------------------- un clic est reconnu


@pytest.mark.parametrize("nom", BARRES)
@pytest.mark.parametrize(
    "sous,attendu",
    [(QStyle.SC_ScrollBarSubLine, -1), (QStyle.SC_ScrollBarAddLine, 1)],
)
def test_un_clic_sur_une_fleche_est_reconnu(fenetre, nom, sous, attendu):
    barre = fenetre.findChild(QScrollBar, nom)
    page = _Page()
    assert page._rotation_arrow_at(barre, _clic(barre, _rect(barre, sous).center())) == attendu


@pytest.mark.parametrize("nom", BARRES)
def test_un_clic_sur_la_poignee_n_est_pas_une_fleche(fenetre, nom):
    """Sinon on ne pourrait plus attraper la poignee."""
    barre = fenetre.findChild(QScrollBar, nom)
    barre.setValue(180)
    page = _Page()
    centre = _rect(barre, QStyle.SC_ScrollBarSlider).center()
    assert page._rotation_arrow_at(barre, _clic(barre, centre)) == 0


# ------------------------------------------------------- le pas


@pytest.mark.parametrize(
    "depart,pas,attendu",
    [
        (40, 1, 41),
        (40, -1, 39),
        (359, 1, 0),      # l'angle boucle
        (0, -1, 359),     # et dans l'autre sens
        (0, 1, 1),
        (180, -1, 179),
    ],
)
def test_le_pas_vaut_un_degre_et_l_angle_boucle(app, depart, pas, attendu):
    barre = QScrollBar(Qt.Vertical)
    barre.setRange(0, 359)
    barre.setValue(depart)

    page = _Page()
    page._step_rotation(barre, 1, pas)

    assert barre.value() == attendu
    assert page.redessins == [1], "le plan n'a pas ete redessine"


def test_le_redessin_porte_sur_la_bonne_coupe(app):
    barre = QScrollBar(Qt.Vertical)
    barre.setRange(0, 359)
    page = _Page()
    page._step_rotation(barre, 2, 1)
    assert page.redessins == [2]


def test_une_barre_sans_etendue_ne_fait_rien(app):
    """Avant que la page n'ait pose sa plage, minimum et maximum sont nuls."""
    barre = QScrollBar(Qt.Vertical)
    barre.setRange(0, 0)
    page = _Page()
    page._step_rotation(barre, 1, 1)
    assert barre.value() == 0
