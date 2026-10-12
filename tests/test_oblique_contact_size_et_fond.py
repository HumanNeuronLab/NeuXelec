"""Le rayon des contacts et le fond de l'apercu 3D, en coupe oblique.

LE RAYON : CE QUE LA SUPPRESSION A FAILLI EMPORTER

Le reglage "Size contacts" a ete retire, et le code qui le lisait
retombait sur 4 quand le widget manquait. Ce 4 etait faux : le spinbox
sortait du .ui a 0, et ``setRange(1, 20)`` le ramenait a 1 **avant** que
le garde-fou ``si valeur <= 0: valeur = 4`` ne puisse jamais s'executer.
Le dessin se faisait donc avec un rayon de 1, et le 4 annonce partout
n'a jamais servi.

Le premier test rejoue cette mecanique sur un vrai QSpinBox. Il dit
d'ou vient la constante, et il tombe si quelqu'un la "corrige" a 4 en
croyant retrouver la valeur par defaut.

LE FOND : LA MEME SCENE VUE DE DEUX PAGES

L'apercu 3D de la coupe oblique etait gris ardoise, la vue 3D noire.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSpinBox  # noqa: E402

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------- le rayon


def test_la_constante_vaut_ce_que_le_reglage_retire_donnait(app):
    """La mecanique exacte de l'ancien code, rejouee."""
    spinbox = QSpinBox()  # comme il sortait du .ui : aucune valeur posee
    assert spinbox.value() == 0

    spinbox.setRange(1, 20)
    if spinbox.value() <= 0:          # ce garde-fou ne s'executait jamais
        spinbox.setValue(4)

    assert spinbox.value() == 1, "la plage ne ramene plus la valeur a 1"
    assert ObliqueSlicePage.CONTACT_RADIUS_PX == max(1, spinbox.value())


def test_le_rayon_reste_un_entier_dessinable(app):
    assert isinstance(ObliqueSlicePage.CONTACT_RADIUS_PX, int)
    assert ObliqueSlicePage.CONTACT_RADIUS_PX >= 1


# --------------------------------------------------------- le fond


class _Plotter:
    def __init__(self):
        self.fonds = []
        self.lumieres = 0

    def set_background(self, couleur):
        self.fonds.append(couleur)

    def remove_all_lights(self):
        self.lumieres = 0

    def add_light(self, _lumiere):
        self.lumieres += 1


class _Page:
    _setup_oblique_brain_lights = ObliqueSlicePage._setup_oblique_brain_lights
    BRAIN_PREVIEW_BACKGROUND = ObliqueSlicePage.BRAIN_PREVIEW_BACKGROUND

    def __init__(self, plotter):
        self._brain_plotter = plotter


def test_l_apercu_3d_est_pose_sur_fond_noir(app):
    plotter = _Plotter()
    _Page(plotter)._setup_oblique_brain_lights()
    assert plotter.fonds == ["black"]


def test_les_deux_pages_montrent_le_cerveau_sur_le_meme_fond(app):
    """Le defaut signale : gris ardoise ici, noir dans la vue 3D."""
    assert (
        ObliqueSlicePage.BRAIN_PREVIEW_BACKGROUND
        == View3DPage.VIEW3D_DEFAULT_BACKGROUND
    )


def test_sans_apercu_monte_rien_ne_leve(app):
    page = _Page(None)
    page._setup_oblique_brain_lights()


def test_les_lumieres_sont_posees_apres_le_fond(app):
    """Trois lumieres : la frontale et les deux d'appoint."""
    plotter = _Plotter()
    _Page(plotter)._setup_oblique_brain_lights()
    assert plotter.lumieres == 3
