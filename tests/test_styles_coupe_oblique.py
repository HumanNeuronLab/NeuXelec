"""Les curseurs et les boites a fleches de la coupe oblique.

DEUX CHOSES QUE SEULE UNE INTERFACE CHARGEE PEUT DIRE

La poignee d'un curseur est dessinee par la feuille de style, mais
**rognee** par la hauteur du widget. Demander une poignee de 20 px a un
curseur haut de 15 laisse un rectangle arrondi a la place du cercle,
sans qu'aucune erreur ne soit levee. C'est arrive en agrandissant ces
curseurs.

Et Qt resout un ``url()`` relatif contre le repertoire courant, pas
contre le .ui. Lance d'ailleurs que la racine du projet, NeuXelec
perdait les fleches de ses boites a compteur et la croix de ses cases a
cocher, en silence.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyleOptionSlider,
    QWidget,
)

from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import (  # noqa: E402
    _est_absolu,
    absolutise_stylesheet_urls,
    load_ui,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------- les chemins d'images


@pytest.mark.parametrize(
    "chemin",
    ["C:/images/a.svg", "/usr/share/a.svg", ":/qt/a.svg", "D:/x.png"],
)
def test_un_chemin_absolu_n_est_pas_touche(chemin):
    assert _est_absolu(chemin)
    feuille = "a { image: url(%s); }" % chemin
    assert absolutise_stylesheet_urls(feuille) == feuille


def test_un_chemin_relatif_devient_absolu():
    sortie = absolutise_stylesheet_urls("a { image: url(resources/images/spin_up.svg); }")
    assert "url(resources/" not in sortie
    assert str(resource_path("resources/images/spin_up.svg").as_posix()) in sortie


@pytest.mark.parametrize("guillemet", ["", "'", '"']) 
def test_les_guillemets_sont_admis(guillemet):
    feuille = "a { image: url(%sresources/images/spin_up.svg%s); }" % (
        guillemet,
        guillemet,
    )
    assert "url(resources/" not in absolutise_stylesheet_urls(feuille)


def test_une_feuille_sans_image_revient_telle_quelle():
    feuille = "QWidget { color: red; }"
    assert absolutise_stylesheet_urls(feuille) is feuille
    assert absolutise_stylesheet_urls("") == ""


def test_toutes_les_images_de_la_feuille_existent(app):
    """Une image renommee ne leve rien : elle disparait, simplement."""
    import re

    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    urls = re.findall(r"url\(([^)]+)\)", w.styleSheet())
    assert urls, "la feuille ne reference plus aucune image"

    manquantes = [u for u in urls if not u.startswith(":") and not Path(u).exists()]
    assert manquantes == [], manquantes


def test_la_feuille_chargee_n_a_plus_aucun_chemin_relatif(app):
    """C'est ce qui la rend independante du repertoire de lancement."""
    import re

    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    relatifs = [
        u for u in re.findall(r"url\(([^)]+)\)", w.styleSheet()) if not _est_absolu(u)
    ]
    assert relatifs == [], relatifs


# ------------------------------------------------- les curseurs


@pytest.fixture(scope="module")
def page_oblique(app):
    """La page montee dans une fenetre, seule facon de mesurer un style."""
    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    page = w.findChild(QWidget, "pageObliqueSlices")
    assert page is not None
    for pile in w.findChildren(QStackedWidget):
        if pile.indexOf(page) >= 0:
            pile.setCurrentWidget(page)
    w.resize(1700, 1000)
    w.show()
    app.processEvents()
    return w, page


def _geometrie(slider):
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    style = slider.style()
    return (
        style.subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider),
        style.subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, slider),
    )


def test_aucune_poignee_n_est_rognee(page_oblique):
    """Le defaut qu'a produit l'agrandissement : une poignee plus haute
    que son curseur devient un rectangle arrondi."""
    _, page = page_oblique
    rognees = []
    for slider in page.findChildren(QSlider):
        poignee, _ = _geometrie(slider)
        if slider.height() < poignee.height():
            rognees.append(
                "%s : curseur %d px, poignee %d px"
                % (slider.objectName(), slider.height(), poignee.height())
            )
    assert rognees == [], rognees


def test_la_poignee_reste_ronde(page_oblique):
    """Largeur et hauteur egales, sinon ce n'est plus un disque."""
    _, page = page_oblique
    slider = page.findChild(QSlider, "horizontalSlider_obliqueSlice_petOpacity")
    poignee, _ = _geometrie(slider)
    assert poignee.width() == poignee.height(), (poignee.width(), poignee.height())


def test_les_curseurs_sont_plus_gros_qu_ailleurs(page_oblique, app):
    """C'est la demande : cette page se pilote l'oeil sur les coupes."""
    w, page = page_oblique
    oblique = page.findChild(QSlider, "horizontalSlider_obliqueSlice_petOpacity")
    ailleurs = w.findChild(QWidget, "page3DView").findChild(QSlider, "sld_3d_petOpacity")
    assert ailleurs is not None, "pas de curseur temoin dans la vue 3D"

    poignee_o, rainure_o = _geometrie(oblique)
    poignee_a, rainure_a = _geometrie(ailleurs)
    assert poignee_o.height() > poignee_a.height()
    assert rainure_o.height() > rainure_a.height()
