# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La surface 3D du SISCOM, visible sur le fond noir de la scene.

LE DEFAUT

Le maillage du blob est l'isosurface **au seuil** : tous ses sommets
portent donc la meme valeur, celle du bas de l'echelle. Il etait
colorie par cette echelle, et le bas de "hot" est noir. Le blob
disparaissait dans le fond de la scene en attendant de coder une
intensite qu'il n'a pas.

Il recoit desormais une couleur unie et claire. Les coupes, elles,
gardent l'echelle et leur barre : elles traversent le champ et ont
bien une intensite a montrer.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QSlider  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Maillage:
    def __init__(self, n=8):
        self.n_points = n
        self.points = np.zeros((n, 3), dtype=np.float32)
        self.tableaux = {}

    def __setitem__(self, nom, valeurs):
        self.tableaux[nom] = valeurs


class _Plotter:
    def __init__(self):
        self.appels = []

    def add_mesh(self, mesh, **kwargs):
        self.appels.append((mesh, kwargs))
        return object()


class _Page:
    """De quoi parcourir _render_siscom sans scene ni carte graphique."""

    SISCOM_SURFACE_COLOR = View3DPage.SISCOM_SURFACE_COLOR
    _render_siscom = View3DPage._render_siscom

    def __init__(self, coupe_visible=False, garder=False):
        self.plotter = _Plotter()
        self.chk_siscom = QCheckBox()
        self.chk_siscom.setChecked(True)
        self.dsb_siscom_z = QDoubleSpinBox()
        self.dsb_siscom_z.setRange(0.0, 10.0)
        self.dsb_siscom_z.setValue(2.0)
        self.sld_siscom_opacity = QSlider()
        self.sld_siscom_opacity.setRange(0, 100)
        self.sld_siscom_opacity.setValue(70)
        self._siscom_fixed_zmax = 5.0
        self._siscom_actor = None
        self._coupe_visible = coupe_visible
        self._keep_siscom_blob_through_slices = garder
        self.retires = []
        self.rendus = 0

        volume = np.zeros((6, 6, 6), dtype=np.float32)
        volume[2:4, 2:4, 2:4] = 4.0
        self._siscom_img = sitk.GetImageFromArray(volume)

    # --- ce que le rendu appelle autour ---
    def _any_slice_plane_visible(self):
        return self._coupe_visible

    def _get_active_surface_mask_resampled_to(self, _img):
        return None

    def _apply_cortex_to_image(self, img):
        return img

    def _threshold_image_to_polydata(self, _img, absolute_threshold=None):
        return _Maillage()

    def _sample_sitk_values_at_ras_points(self, _img, points):
        return np.full((len(points),), 4.0, dtype=np.float32)

    def _remove_actor(self, which):
        self.retires.append(which)

    def _remove_siscom_scalar_bar(self):
        pass

    def _update_siscom_scalar_bar(self):
        pass

    def _apply_actor_clipping(self):
        pass

    def _render(self):
        self.rendus += 1


def _kwargs(page):
    page._render_siscom()
    assert page.plotter.appels, "le blob n'a pas ete dessine"
    return page.plotter.appels[-1][1]


# ------------------------------------------------------ la couleur


def test_la_surface_porte_une_couleur_unie(app):
    kwargs = _kwargs(_Page())
    assert "color" in kwargs
    assert tuple(kwargs["color"]) == tuple(View3DPage.SISCOM_SURFACE_COLOR)


def test_la_surface_n_est_plus_coloriee_par_l_echelle(app):
    """Le defaut retire : tous ses sommets tombaient au bas de "hot"."""
    kwargs = _kwargs(_Page())
    assert "scalars" not in kwargs, "la surface suit encore l'echelle"
    assert "cmap" not in kwargs
    assert "clim" not in kwargs


def test_la_couleur_se_lit_sur_un_fond_noir(app):
    """C'est tout l'objet du changement."""
    for composante in View3DPage.SISCOM_SURFACE_COLOR:
        assert 0.8 <= composante <= 1.0, View3DPage.SISCOM_SURFACE_COLOR


def test_l_opacite_reglee_est_respectee(app):
    page = _Page()
    page.sld_siscom_opacity.setValue(40)
    assert _kwargs(page)["opacity"] == pytest.approx(0.4)


# --------------------------------------- quand le blob est montre


def test_le_blob_parait_quand_aucune_coupe_n_est_visible(app):
    page = _Page(coupe_visible=False)
    page._render_siscom()
    assert page.plotter.appels, "le blob manque alors qu'aucune coupe n'est la"


def test_une_coupe_visible_efface_le_blob(app):
    """Sans quoi la coupe et le volume se recouvriraient."""
    page = _Page(coupe_visible=True)
    page._render_siscom()
    assert page.plotter.appels == []
    assert "siscom" in page.retires


def test_le_blob_traverse_les_coupes_si_on_le_demande(app):
    """L'entree Keep SISCOM blob du clic droit."""
    page = _Page(coupe_visible=True, garder=True)
    page._render_siscom()
    assert page.plotter.appels, "le blob a disparu malgre le reglage"


def test_la_case_decochee_retire_le_blob(app):
    page = _Page()
    page.chk_siscom.setChecked(False)
    page._render_siscom()
    assert page.plotter.appels == []
    assert "siscom" in page.retires
