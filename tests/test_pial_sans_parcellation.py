"""La surface piale garde sa couleur, meme avec une parcellation chargee.

CE QUI A CHANGE

La piale etait repeinte avec l'atlas des qu'une parcellation etait
active : chaque sommet recevait la couleur du label echantillonne sous
lui. C'etait la seule facon de voir la parcellation en 3D avant que
l'onglet Parcellation ne sache tracer les regions une par une.

Elle fait desormais double emploi, et la version peinte montrait tout
sans offrir de quoi en retirer quoi que ce soit. Ces tests figent la
nouvelle regle : la piale est un cerveau d'une seule couleur, et le
rendu ne consulte meme plus la parcellation.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyvista as pv  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402

COULEUR = (0.82, 0.78, 0.75)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Propriete:
    def BackfaceCullingOff(self): pass
    def FrontfaceCullingOff(self): pass
    def SetInterpolationToPhong(self): pass


class _Acteur:
    def GetProperty(self):
        return _Propriete()

    def PickableOn(self): pass


class _Plotter:
    def __init__(self):
        self.appels = []

    def add_mesh(self, mesh, **kwargs):
        self.appels.append((mesh, kwargs))
        return _Acteur()


class _Page:
    """De quoi parcourir la branche piale de bout en bout."""

    def __init__(self):
        self.plotter = _Plotter()
        self.chk_pial = QCheckBox()
        self.chk_pial.setChecked(True)
        self.chk_brainmask = QCheckBox()
        self._brainmask_img = None
        self._lh_pial_mask_img = None
        self._rh_pial_mask_img = None
        # Deux hemispheres distincts : la fusion est sur le chemin.
        self._lh_pial_poly = pv.Sphere(radius=3.0, center=(-5.0, 0.0, 0.0))
        self._rh_pial_poly = pv.Sphere(radius=3.0, center=(5.0, 0.0, 0.0))
        self._show_lh_pial = True
        self._show_rh_pial = True
        self._brain_color = COULEUR
        self._brain_render_params = {}
        self._brain_actor = None
        self.parcellation_consultee = 0
        self.rendus = 0

    # --- ce que le rendu appelle autour ---
    def _remove_actor(self, which): pass
    def _setup_brain_render_lights(self): pass
    def _apply_brain_actor_opacity_mode(self, actor, opacity): pass
    def _apply_actor_clipping(self): pass
    def _refresh_multiplanar_clipped_scene(self): pass
    def render_all_surface_projections(self): pass

    def _render(self):
        self.rendus += 1

    def _get_active_parcellation_img_and_lut(self):
        """Une parcellation bien chargee, que le rendu ne doit plus lire."""
        self.parcellation_consultee += 1
        return object(), {17: ("Left-Hippocampus", (220, 216, 20))}

    _render_brain = View3DPage._render_brain
    _parcellation_hover_display_active = (
        View3DPage._parcellation_hover_display_active
    )

    def _any_slice_plane_visible(self):
        return False


def _rendre(page):
    page._render_brain(reset_camera=False)
    assert len(page.plotter.appels) == 1, "la piale n'a pas ete dessinee"
    return page.plotter.appels[0][1]


def test_la_piale_est_dessinee(app):
    page = _Page()
    kwargs = _rendre(page)
    assert kwargs["color"] == COULEUR
    assert page.rendus == 1


def test_la_piale_n_est_jamais_peinte_avec_l_atlas(app):
    """Le defaut retire : des scalaires par sommet, couleur du label."""
    page = _Page()
    kwargs = _rendre(page)
    assert "scalars" not in kwargs, "la piale porte encore des scalaires"
    assert "rgb" not in kwargs


def test_le_rendu_ne_consulte_meme_plus_la_parcellation(app):
    """Pas seulement le resultat : le travail lui-meme a disparu.

    Echantillonner un atlas sous chaque sommet d'une piale coute un
    passage sur toute la surface, a chaque rendu.
    """
    page = _Page()
    _rendre(page)
    assert page.parcellation_consultee == 0


def test_le_maillage_dessine_porte_les_deux_hemispheres(app):
    """La fusion reste sur le chemin : on ne perd pas un cote."""
    page = _Page()
    page._render_brain(reset_camera=False)
    maillage = page.plotter.appels[0][0]
    bornes = maillage.bounds
    assert bornes[0] < -5.0 and bornes[1] > 5.0, bornes
    assert "parcel_rgb" not in maillage.array_names


def test_le_survol_ne_s_accroche_plus_a_la_piale(app):
    """Annoncer un nom de region sur une surface unie induirait en erreur."""
    page = _Page()
    page._render_brain(reset_camera=False)
    assert page._brain_actor is not None
    assert page._parcellation_hover_display_active() is False
