"""La place du bouton User guide dans le menu de gauche.

POURQUOI IL A DESCENDU

Il etait colle a Save project, dans le bloc qui dit ce qu'on fait de
ce projet : identifiant du patient, enregistrement. Le guide parle de
l'application et non du patient, et il coupait ce groupe avant qu'on
arrive aux quatre pages.

POURQUOI AU-DESSUS DES LOGOS ET NON DESSOUS

Les deux logos sont la signature institutionnelle, la fin visuelle du
panneau. Un bouton pose apres eux se lit comme un oubli, c'est
l'endroit le moins regarde de la fenetre, et c'est le premier element
ecrase quand la fenetre raccourcit.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import load_ui  # noqa: E402

#: Les quatre pages, dans l'ordre du menu.
NAVIGATION = (
    "btn_menu_fileCoreg",
    "btn_menu_reconstruction",
    "btn_menu_obliqueSlice",
    "btn_menu_3Dview",
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def menu(app):
    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    cadre = w.findChild(QFrame, "menu")
    assert cadre is not None
    return w, cadre, cadre.layout()


def _rang(layout, nom):
    """Le rang d'un element du menu, widget ou sous-disposition."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None and widget.objectName() == nom:
            return i
        sous = item.layout()
        if sous is not None and sous.objectName() == nom:
            return i
    return -1


def test_le_bouton_existe_toujours(menu):
    w, _, _ = menu
    assert w.findChild(QPushButton, "btn_menu_userGuide") is not None


def test_il_est_apres_les_quatre_pages(menu):
    """Il ne coupe plus le bloc du projet."""
    _, _, layout = menu
    guide = _rang(layout, "btn_menu_userGuide")
    assert guide >= 0
    for nom in NAVIGATION:
        page = _rang(layout, nom)
        assert page >= 0, nom
        assert guide > page, nom


def test_il_est_avant_les_logos(menu):
    """Les logos restent la signature, en pied de panneau."""
    _, _, layout = menu
    guide = _rang(layout, "btn_menu_userGuide")
    logos = _rang(layout, "frame_institution_logos")
    assert logos >= 0
    assert guide < logos, (guide, logos)


def test_il_a_quitte_le_voisinage_de_save_project(menu):
    """Le defaut de depart : les deux se suivaient."""
    _, _, layout = menu
    save = _rang(layout, "btn_menu_saveProject")
    guide = _rang(layout, "btn_menu_userGuide")
    assert save >= 0
    assert guide - save > 1, "le guide est encore colle a Save project"


def test_les_logos_sont_les_derniers(menu):
    """Rien ne doit se glisser apres eux."""
    _, _, layout = menu
    logos = _rang(layout, "frame_institution_logos")
    assert logos == layout.count() - 1, (logos, layout.count())


def test_les_deux_logos_portent_toujours_leur_image(menu):
    """Deplacer un voisin ne doit pas les avoir vides."""
    w, _, _ = menu
    for nom in ("logo_HUG", "logo_UNIGE"):
        etiquette = w.findChild(QLabel, nom)
        assert etiquette is not None, nom
        image = etiquette.pixmap()
        assert image is not None and not image.isNull(), nom


def test_le_menu_garde_un_seul_bouton_de_guide(menu):
    w, _, _ = menu
    trouves = [
        b for b in w.findChildren(QPushButton) if b.objectName() == "btn_menu_userGuide"
    ]
    assert len(trouves) == 1


def test_l_ordre_des_quatre_pages_n_a_pas_bouge(menu):
    """Deplacer un item renumerote la disposition autour de lui."""
    _, _, layout = menu
    rangs = [_rang(layout, nom) for nom in NAVIGATION]
    assert all(r >= 0 for r in rangs), rangs
    assert rangs == sorted(rangs), rangs


def test_le_menu_est_bien_une_colonne(menu):
    _, cadre, layout = menu
    assert isinstance(layout, QVBoxLayout)
