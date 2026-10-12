"""Changer l'opacite de la parcellation se voit tout de suite.

LE DEFAUT SIGNALE

Avec une coupe affichee, bouger le curseur d'opacite de la
parcellation ne changeait rien : il fallait deplacer un plan pour que
la nouvelle valeur apparaisse.

La parcellation est **peinte dans la texture** de chaque coupe.
Changer son opacite ne deplace aucun plan, mais oblige a refaire cette
texture. C'est exactement ce que dit la documentation de
_refresh_all_visible_slice_planes_full, qui n'etait pourtant appelee
qu'en mode MNI : en natif on se contentait de redecouper la scene et
de redessiner les surcouches, ce qui laisse la texture intacte.

L'ORDRE COMPTE

Le decoupage passe avant la reconstruction : les contours colores sont
rebatis a la fin de celle-ci, et ils doivent connaitre un etat de
decoupe deja a jour.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from neuxelec.pages.view3d import View3DPage  # noqa: E402


class _Page:
    _refresh_base_slice_cache_and_scene = (
        View3DPage._refresh_base_slice_cache_and_scene
    )

    def __init__(self, mni=False):
        self._mni = mni
        self.appels = []
        self.caches_invalides = []

    def _invalidate_slice_volume_cache(self, **quoi):
        self.caches_invalides.append(quoi)

    def _mni_t1_slices_are_visible(self):
        return self._mni

    def _apply_actor_clipping(self):
        self.appels.append("decoupe")

    def _refresh_all_visible_slice_planes_full(self):
        self.appels.append("textures")

    def _render(self):
        self.appels.append("rendu")


# ------------------------------------------- la texture est refaite


def test_en_natif_la_texture_des_coupes_est_refaite():
    """Le defaut exact : elle ne l'etait pas."""
    page = _Page(mni=False)
    page._refresh_base_slice_cache_and_scene()
    assert "textures" in page.appels, page.appels


def test_en_mni_elle_l_est_toujours():
    """Ce cas marchait deja, il doit continuer."""
    page = _Page(mni=True)
    page._refresh_base_slice_cache_and_scene()
    assert "textures" in page.appels, page.appels


# ------------------------------------------------- l'ordre


def test_le_decoupage_precede_la_reconstruction():
    """Les contours sont rebatis a la fin : la decoupe doit etre a jour."""
    page = _Page(mni=False)
    page._refresh_base_slice_cache_and_scene()
    assert page.appels.index("decoupe") < page.appels.index("textures")


def test_le_mode_mni_ne_decoupe_pas():
    """Le gabarit n'a pas de scene native a tailler."""
    page = _Page(mni=True)
    page._refresh_base_slice_cache_and_scene()
    assert "decoupe" not in page.appels, page.appels


# ------------------------------------------- le cache et le rendu


@pytest.mark.parametrize("mni", [False, True])
def test_le_cache_anatomique_est_invalide(mni):
    """Sans cela la texture serait refaite a partir de l'ancienne."""
    page = _Page(mni=mni)
    page._refresh_base_slice_cache_and_scene()
    assert page.caches_invalides == [{"base": True, "pet": False, "siscom": False}]


@pytest.mark.parametrize("mni", [False, True])
def test_la_scene_est_rendue(mni):
    page = _Page(mni=mni)
    page._refresh_base_slice_cache_and_scene()
    assert page.appels[-1] == "rendu", page.appels


def test_une_panne_de_redessin_n_empeche_pas_le_rendu():
    """Le cache est deja invalide : laisser la scene figee serait pire."""

    class _Cassee(_Page):
        def _refresh_all_visible_slice_planes_full(self):
            raise RuntimeError("plus de carte graphique")

    page = _Cassee(mni=False)
    page._refresh_base_slice_cache_and_scene()
    assert page.appels[-1] == "rendu", page.appels
