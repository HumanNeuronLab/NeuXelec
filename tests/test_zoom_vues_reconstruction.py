# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les trois vues CT de la page Reconstruction remplissent leur cadre.

LE DEFAUT

Une coupe conformee est carree, les cadres de la page sont plus larges
que hauts (1.35 a 1.46 selon la fenetre). La fenetre de recadrage du
zoom gardait la forme de l'**image**, puis le resultat etait mis a
l'echelle en conservant son rapport : deux bandes restaient a gauche
et a droite, a tous les niveaux de zoom.

CE QUI CHANGE

Des le premier cran de zoom, la fenetre prend la forme du **cadre**.
La vue le remplit alors entierement.

A zoom 1 elle garde la forme de l'image : remplir y couperait une
partie du cerveau sans qu'on l'ait demande. Les bandes qui restent la
sont desormais noires comme le fond de la coupe, au lieu du gris qui
dessinait un cadre autour d'elle.

A SURFACE EGALE

Le zoom dit combien de l'image on regarde ; changer la forme de la
fenetre ne doit pas changer cette quantite, seulement sa repartition.
Sans cela, le premier cran de zoom ferait un saut.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from neuxelec.pages.reconstruction_page import ReconstructionPage  # noqa: E402

#: Une coupe conformee, et les rapports mesures sur la vraie page.
PLEIN = 256
CADRES = (0.95, 1.35, 1.46)


class _Page:
    """Juste de quoi exercer le recadrage."""

    _crop_for_zoom = ReconstructionPage._crop_for_zoom
    _shape_crop_to_frame = staticmethod(ReconstructionPage._shape_crop_to_frame)

    def __init__(self, zoom):
        self._zoom = float(zoom)

    def _get_zoom(self, _plane):
        return self._zoom


def _image(largeur=PLEIN, hauteur=PLEIN):
    return np.zeros((hauteur, largeur), dtype=np.float32)


# ------------------------------------------------- la forme du cadre


@pytest.mark.parametrize("aspect", CADRES)
@pytest.mark.parametrize("zoom", [1.2, 1.5, 2.0, 4.0])
def test_la_fenetre_prend_la_forme_du_cadre(aspect, zoom):
    """Le defaut : elle gardait celle de l'image, donc les bandes."""
    crop, _ = _Page(zoom)._crop_for_zoom(_image(), "axial", 128, 128, aspect)
    hauteur, largeur = crop.shape
    assert largeur / hauteur == pytest.approx(aspect, abs=0.02), (largeur, hauteur)


@pytest.mark.parametrize("zoom", [1.5, 2.0, 4.0])
def test_la_surface_vue_suit_le_zoom(zoom):
    """Changer la forme ne doit pas changer combien on voit."""
    crop, _ = _Page(zoom)._crop_for_zoom(_image(), "axial", 128, 128, 1.46)
    hauteur, largeur = crop.shape
    part = (largeur * hauteur) / float(PLEIN * PLEIN)
    assert part == pytest.approx(1.0 / (zoom * zoom), rel=0.05), part


@pytest.mark.parametrize("aspect", CADRES)
@pytest.mark.parametrize("zoom", [1.01, 1.2, 2.0, 8.0])
def test_la_fenetre_ne_sort_jamais_de_l_image(aspect, zoom):
    crop, st = _Page(zoom)._crop_for_zoom(_image(), "axial", 128, 128, aspect)
    hauteur, largeur = crop.shape
    assert 1 <= largeur <= PLEIN
    assert 1 <= hauteur <= PLEIN
    assert st["x0"] >= 0 and st["y0"] >= 0
    assert st["x0"] + st["cw"] <= PLEIN
    assert st["y0"] + st["ch"] <= PLEIN


@pytest.mark.parametrize("centre", [(0, 0), (255, 255), (0, 255), (10, 200)])
def test_un_centre_au_bord_garde_la_fenetre_dedans(centre):
    """Le recadrage se rabat sur le bord plutot que de lire dehors."""
    cx, cy = centre
    crop, st = _Page(2.0)._crop_for_zoom(_image(), "axial", cx, cy, 1.46)
    assert crop.size > 0
    assert st["x0"] + st["cw"] <= PLEIN
    assert st["y0"] + st["ch"] <= PLEIN


# ------------------------------------------------------- a zoom 1


@pytest.mark.parametrize("aspect", CADRES)
def test_a_zoom_un_l_image_entiere_est_rendue(aspect):
    """Remplir y couperait une partie du cerveau sans qu'on le demande."""
    img = _image()
    crop, st = _Page(1.0)._crop_for_zoom(img, "axial", 128, 128, aspect)
    assert crop.shape == img.shape
    assert (st["cw"], st["ch"]) == (float(PLEIN), float(PLEIN))


def test_sans_cadre_connu_la_forme_de_l_image_est_gardee():
    """Un cadre pas encore dispose ne doit pas deformer la vue."""
    crop, _ = _Page(2.0)._crop_for_zoom(_image(), "axial", 128, 128, None)
    hauteur, largeur = crop.shape
    assert largeur == hauteur


# ------------------------------------------- une image non carree


def test_une_image_rectangulaire_suit_aussi_le_cadre():
    crop, _ = _Page(2.0)._crop_for_zoom(_image(320, 200), "axial", 160, 100, 1.46)
    hauteur, largeur = crop.shape
    assert largeur / hauteur == pytest.approx(1.46, abs=0.02)


def test_un_cadre_trop_etire_est_rabattu_dans_l_image():
    """La forme demandee ne tient pas : on prefere des bandes a une
    lecture hors du volume."""
    largeur, hauteur = ReconstructionPage._shape_crop_to_frame(
        PLEIN, PLEIN, 12.0, PLEIN, PLEIN
    )
    assert largeur <= PLEIN and hauteur <= PLEIN
    assert hauteur >= 1


# ----------------------------------------------------- la forme lue


class _Cadre:
    def __init__(self, largeur, hauteur):
        self._l, self._h = largeur, hauteur

    def width(self):
        return self._l

    def height(self):
        return self._h


def test_la_forme_du_cadre_est_son_rapport():
    assert ReconstructionPage._frame_aspect(_Cadre(526, 390)) == pytest.approx(526 / 390)


@pytest.mark.parametrize("taille", [(0, 100), (100, 0), (1, 1), (-5, 50)])
def test_un_cadre_sans_taille_ne_donne_pas_de_forme(taille):
    """Avant le premier affichage, le cadre ne mesure rien."""
    assert ReconstructionPage._frame_aspect(_Cadre(*taille)) is None


# --------------------------------------------------------- le fond


def test_le_fond_des_vues_est_noir():
    """Les bandes de zoom 1 se fondent dans la coupe au lieu de
    dessiner un cadre gris autour d'elle."""
    style = ReconstructionPage.IMAGE_BACKGROUND_STYLE
    assert "black" in style
    assert "rgb(30,30,30)" not in style
