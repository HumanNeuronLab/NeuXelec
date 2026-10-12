"""Les trois barres de coupe de la page Reconstruction.

Elles portent desormais le meme habit que les barres de rotation de la
coupe oblique : plus larges, poignee en capsule, et une fleche a chaque
bout. Un clic sur une fleche avance d'une coupe.

CE QUE CES TESTS GARDENT

Les regles de style sont ecrites une fois et citent les cinq barres,
celles de la coupe oblique et celles de la reconstruction. Une liste
de selecteurs se modifie a la main et se trompe sans rien dire : un
sous-controle mal recopie, et les fleches disparaissent de la moitie
des barres. Ces tests mesurent donc la geometrie rendue par le style,
sur les deux pages, plutot que de relire la feuille.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QScrollBar,
    QStackedWidget,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)

from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import load_ui  # noqa: E402

RECONSTRUCTION = ("scrollReco_coronal", "scrollReco_sagittal", "scrollReco_axial")
OBLIQUE = ("verticalScrollBar_1st", "verticalScrollBar_2nd")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def fenetre(app):
    """Les deux pages montees : un style ne se mesure que sur un widget."""
    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    for nom in ("pageReconstruction", "pageObliqueSlices"):
        page = w.findChild(QWidget, nom)
        assert page is not None, nom
        for pile in w.findChildren(QStackedWidget):
            if pile.indexOf(page) >= 0:
                pile.setCurrentWidget(page)
        w.resize(1700, 1000)
        w.show()
        app.processEvents()
    return w


def _rect(barre, sous_controle):
    option = QStyleOptionSlider()
    barre.initStyleOption(option)
    return barre.style().subControlRect(
        QStyle.CC_ScrollBar, option, sous_controle, barre
    )


def _prete(fenetre, nom):
    barre = fenetre.findChild(QScrollBar, nom)
    assert barre is not None, nom
    barre.setRange(0, 255)
    barre.setValue(128)
    return barre


# ------------------------------------------------- les deux fleches


@pytest.mark.parametrize("nom", RECONSTRUCTION)
@pytest.mark.parametrize(
    "sous", [QStyle.SC_ScrollBarSubLine, QStyle.SC_ScrollBarAddLine]
)
def test_chaque_fleche_a_une_surface(fenetre, nom, sous):
    """Sans surface, la fleche est la mais invisible et inatteignable."""
    r = _rect(_prete(fenetre, nom), sous)
    assert r.width() > 0 and r.height() > 0, (nom, r)


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_les_fleches_sont_aux_deux_bouts(fenetre, nom):
    barre = _prete(fenetre, nom)
    haut = _rect(barre, QStyle.SC_ScrollBarSubLine)
    bas = _rect(barre, QStyle.SC_ScrollBarAddLine)
    assert haut.top() <= 1, haut
    assert bas.bottom() >= barre.height() - 2, (bas, barre.height())


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_un_clic_au_centre_d_une_fleche_tombe_bien_dessus(fenetre, nom):
    barre = _prete(fenetre, nom)
    style = barre.style()
    option = QStyleOptionSlider()
    barre.initStyleOption(option)
    for sous in (QStyle.SC_ScrollBarSubLine, QStyle.SC_ScrollBarAddLine):
        centre = _rect(barre, sous).center()
        trouve = style.hitTestComplexControl(QStyle.CC_ScrollBar, option, centre, barre)
        assert trouve == sous, (nom, sous, trouve)


# ------------------------------------------------- le meme habit


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_elles_ont_la_meme_largeur_que_celles_de_la_coupe_oblique(fenetre, nom):
    """C'est la demande : le meme objet sur les deux pages."""
    temoin = _prete(fenetre, OBLIQUE[0])
    assert _prete(fenetre, nom).width() == temoin.width()


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_la_poignee_a_la_meme_forme_que_celle_de_la_coupe_oblique(fenetre, nom):
    temoin = _rect(_prete(fenetre, OBLIQUE[0]), QStyle.SC_ScrollBarSlider)
    ici = _rect(_prete(fenetre, nom), QStyle.SC_ScrollBarSlider)
    assert ici.width() == temoin.width()


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_la_poignee_n_occupe_pas_toute_la_barre(fenetre, nom):
    """Les deux bouts appartiennent aux fleches."""
    barre = _prete(fenetre, nom)
    poignee = _rect(barre, QStyle.SC_ScrollBarSlider)
    assert poignee.top() > 1
    assert poignee.bottom() < barre.height() - 2


# ----------------------------------------------- une fleche, une coupe


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_le_pas_vaut_une_coupe(fenetre, nom):
    barre = _prete(fenetre, nom)
    barre.setSingleStep(1)
    depart = barre.value()

    barre.triggerAction(QScrollBar.SliderSingleStepAdd)
    assert barre.value() == depart + 1

    barre.triggerAction(QScrollBar.SliderSingleStepSub)
    assert barre.value() == depart


@pytest.mark.parametrize("nom", RECONSTRUCTION)
def test_les_bouts_ne_debordent_pas(fenetre, nom):
    """Un indice de coupe ne boucle pas, contrairement a un angle."""
    barre = _prete(fenetre, nom)
    barre.setSingleStep(1)

    barre.setValue(barre.maximum())
    barre.triggerAction(QScrollBar.SliderSingleStepAdd)
    assert barre.value() == barre.maximum()

    barre.setValue(barre.minimum())
    barre.triggerAction(QScrollBar.SliderSingleStepSub)
    assert barre.value() == barre.minimum()


# ------------------------------- les barres obliques n'ont pas bouge


@pytest.mark.parametrize("nom", OBLIQUE)
@pytest.mark.parametrize(
    "sous", [QStyle.SC_ScrollBarSubLine, QStyle.SC_ScrollBarAddLine]
)
def test_la_coupe_oblique_garde_ses_fleches(fenetre, nom, sous):
    """Etendre une liste de selecteurs peut casser ceux qui y etaient."""
    r = _rect(_prete(fenetre, nom), sous)
    assert r.width() > 0 and r.height() > 0, (nom, r)
