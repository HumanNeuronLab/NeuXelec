"""Survoler une region de la parcellation 3D en donne le nom.

POURQUOI REMONTER DE L'ACTEUR ET NON DU POINT

L'infobulle des coupes echantillonne le volume sous le curseur. Sur
une surface de region, ce serait faux une fois sur deux : la surface
est tracee **a la frontiere** de sa region, et le point pique tombe
donc aussi bien d'un cote que de l'autre.

Un acteur, lui, n'appartient qu'a une region. Le nom est retenu au
moment ou la surface est posee, a cote de l'acteur, pour ne pas
dependre d'un tableau qui aurait pu changer depuis.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Acteur:
    def __init__(self, nom):
        self.nom = nom


class _Page:
    _region_under_mouse = View3DPage._region_under_mouse
    _parcellation_hover_display_active = (
        View3DPage._parcellation_hover_display_active
    )

    def __init__(self, regions=None, noms=None, sous_la_souris=None, coupes=False):
        self._region_actors = dict(regions or {})
        self._region_names = dict(noms or {})
        self._sous_la_souris = sous_la_souris
        self._coupes = coupes

    def _pick_prop_from_mouse(self, x, y):
        return self._sous_la_souris

    def _any_slice_plane_visible(self):
        return self._coupes

    def _get_active_parcellation_img_and_lut(self):
        return None, {}


def _page_avec_deux_regions(pointe=None):
    hippocampe, amygdale = _Acteur("hippo"), _Acteur("amy")
    acteurs = {17: hippocampe, 18: amygdale}
    noms = {17: "Left-Hippocampus", 18: "Left-Amygdala"}
    cible = {"hippo": hippocampe, "amy": amygdale}.get(pointe)
    return _Page(acteurs, noms, cible), hippocampe, amygdale


# ------------------------------------------- nommer la region


def test_survoler_une_region_donne_son_nom(app):
    page, _, _ = _page_avec_deux_regions("hippo")
    assert page._region_under_mouse(10, 10) == ("Left-Hippocampus", 17)


def test_chaque_region_rend_la_sienne(app):
    page, _, _ = _page_avec_deux_regions("amy")
    assert page._region_under_mouse(10, 10) == ("Left-Amygdala", 18)


def test_survoler_le_vide_ne_nomme_rien(app):
    page, _, _ = _page_avec_deux_regions(None)
    assert page._region_under_mouse(10, 10) is None


def test_survoler_un_autre_acteur_ne_nomme_rien(app):
    """Le cerveau ou une electrode ne sont pas des regions."""
    page, _, _ = _page_avec_deux_regions("hippo")
    page._sous_la_souris = _Acteur("cerveau")
    assert page._region_under_mouse(10, 10) is None


def test_sans_region_tracee_rien_n_est_interroge(app):
    page = _Page({}, {}, _Acteur("x"))
    assert page._region_under_mouse(10, 10) is None


def test_une_region_sans_nom_garde_son_numero(app):
    """Une etiquette absente de la table de couleurs existe quand meme."""
    acteur = _Acteur("inconnu")
    page = _Page({4242: acteur}, {}, acteur)
    assert page._region_under_mouse(10, 10) == ("label-4242", 4242)


# ------------------------------------- quand le survol est actif


def test_le_survol_s_active_des_qu_une_region_est_tracee(app):
    """Sans coupe visible et sans parcellation chargee : les surfaces
    portent leur nom toutes seules."""
    page, _, _ = _page_avec_deux_regions("hippo")
    assert page._parcellation_hover_display_active() is True


def test_sans_region_ni_coupe_le_survol_reste_muet(app):
    page = _Page({}, {}, None, coupes=False)
    assert page._parcellation_hover_display_active() is False


def test_sans_region_une_coupe_ne_suffit_pas_sans_parcellation(app):
    """La parcellation doit etre chargee pour que la coupe la montre."""
    page = _Page({}, {}, None, coupes=True)
    assert page._parcellation_hover_display_active() is False


# ----------------------------------- le nom suit la pose de l'acteur


def test_le_nom_est_retenu_au_moment_ou_la_surface_est_posee():
    """La source du nom est la region tracee, pas le tableau.

    Le tableau peut etre filtre, vide ou refait entre la pose et le
    survol ; l'acteur, lui, ne bouge pas.
    """
    import inspect

    source = inspect.getsource(View3DPage._add_region_actor)
    assert "_region_names[int(region.label)] = str(region.name)" in source


def test_effacer_les_regions_efface_aussi_leurs_noms():
    """Sinon un nom survivrait a la region qu'il designait."""
    import inspect

    source = inspect.getsource(View3DPage._clear_region_actors)
    assert "_region_names = {}" in source
