"""La rangee du brainmask est revenue dans la carte Surfaces.

OU ELLE ETAIT, ET POURQUOI ELLE REVIENT

Elle avait ete posee dans la carte SLICE PLANES. Son curseur et sa
boite y etaient partis, mais le libelle "Brain Mask Opacity" etait
reste seul dans SURFACES, sans rien a commander.

CE QUE CES TESTS PROTEGENT

Le retour ne doit rien changer a l'onglet MNI. La rangee du gabarit
etait posee **juste apres** celle du patient : avec celle-ci partie,
l'ancrage l'aurait envoyee en bas de la carte des coupes, sous les
trois plans. Elle s'ancre desormais au titre de la carte.
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
    QLabel,
    QSlider,
    QSpinBox,
)

from neuxelec.utils.resources import resource_path  # noqa: E402

RANGEE = "horizontalLayout_3dBrainmask"
WIDGETS = (
    (QCheckBox, "chk_3d_showBrainmask"),
    (QSlider, "sld_3d_brainMaskOpacity"),
    (QSpinBox, "spinBox_3d_brainMaskOpacity"),
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def ui(app):
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly)
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    assert w is not None
    return w


def _rang(layout, nom):
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        sous = item.layout()
        if sous is not None and sous.objectName() == nom:
            return i
        widget = item.widget()
        if widget is not None and widget.objectName() == nom:
            return i
    return -1


@pytest.mark.parametrize("classe,nom", WIDGETS)
def test_les_trois_controles_sont_dans_surfaces(ui, classe, nom):
    carte = ui.findChild(QFrame, "card3DSurfaces")
    assert carte.findChild(classe, nom) is not None, nom


@pytest.mark.parametrize("classe,nom", WIDGETS)
def test_ils_ne_sont_plus_dans_la_carte_des_coupes(ui, classe, nom):
    carte = ui.findChild(QFrame, "card3DSlices")
    assert carte.findChild(classe, nom) is None, nom


@pytest.mark.parametrize("classe,nom", WIDGETS)
def test_chacun_n_existe_qu_en_un_exemplaire(ui, classe, nom):
    """Le piege de toute la session : une copie qui finit par mentir."""
    trouves = [w for w in ui.findChildren(classe) if w.objectName() == nom]
    assert len(trouves) == 1, "%s existe en %d exemplaires" % (nom, len(trouves))


def test_elle_suit_la_rangee_de_la_piale(ui):
    """Les deux surfaces se lisent l'une sous l'autre, de la meme forme.

    La rangee Pial Opacity a disparu depuis : son curseur est monte
    dans la rangee Pial Surface, qui a desormais la meme forme que
    celle-ci.
    """
    layout = ui.findChild(QFrame, "card3DSurfaces").layout()
    rang_piale = _rang(layout, "horizontalLayout_49")
    rang_brainmask = _rang(layout, RANGEE)
    assert rang_piale >= 0 and rang_brainmask >= 0
    assert rang_piale < rang_brainmask, (rang_piale, rang_brainmask)
    assert rang_brainmask == rang_piale + 1, "une rangee s'est glissee entre les deux"


def test_le_libelle_orphelin_a_disparu(ui):
    """Son curseur etait parti sans lui, il ne commandait plus rien."""
    orphelins = [
        e
        for e in ui.findChildren(QLabel)
        if (e.text() or "").strip().lower() == "brain mask opacity"
    ]
    assert orphelins == [], "le libelle sans curseur est encore la"


def test_la_carte_des_coupes_ne_garde_que_ses_plans(ui):
    """Rien d'autre ne doit etre parti avec la rangee."""
    carte = ui.findChild(QFrame, "card3DSlices")
    for nom in (
        "chk_3d_showAxialPlane",
        "chk_3d_showCoronalPlane",
        "chk_3d_showSagittalPlane",
    ):
        assert carte.findChild(QCheckBox, nom) is not None, nom


def test_le_titre_des_coupes_reste_en_premier(ui):
    """C'est l'ancre de la rangee du gabarit MNI."""
    layout = ui.findChild(QFrame, "card3DSlices").layout()
    assert _rang(layout, "lbl3DSlicesCard") == 0
