"""Deux couches MRI independantes, dans les coupes obliques et la vue 3D.

Les cases MRI 1 et MRI 2 etaient un selecteur de source deguise : cocher l'une
decochait l'autre, il n'y avait qu'une couche anatomique, et une variable
retenait laquelle des deux l'alimentait. Aucune ne pouvait etre reglee
separement et on ne pouvait pas les comparer sur un meme ecran.

LA CASE EST LA SEULE SOURCE DE VERITE. Un dictionnaire parallele de ce qui est
affiche paraissait plus propre et s'est desynchronise en une journee : plusieurs
endroits cochent ces cases en silence, signaux bloques, donc un miroir de leur
etat vieillit sans bruit et la page dessine autre chose que ce qui est affiche.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def rampe(amplitude: float, inversee: bool = False):
    _z, _y, x = np.indices((6, 7, 10))
    a = (9 - x if inversee else x) / 9.0 * amplitude
    return sitk.GetImageFromArray(a.astype(np.float32))


def tableau(img):
    return sitk.GetArrayFromImage(img)


class _Oblique:
    def __init__(self, t1_coche, t2_coche, opacite=None, t2=None):
        self._t1 = rampe(1000.0)
        self._t2 = rampe(4000.0, inversee=True) if t2 is None else t2
        self.chk_mri_t1 = QCheckBox()
        self.chk_mri_t1.setChecked(t1_coche)
        self.chk_mri_t2 = QCheckBox()
        self.chk_mri_t2.setChecked(t2_coche)
        self._oblique_mri_opacity = opacite or {"T1": 100, "T2": 50}

    def _get_t1_image(self):
        return self._t1

    def _get_t2_image(self):
        return self._t2

    _oblique_mri_sources = ObliqueSlicePage._oblique_mri_sources
    _get_active_mri_image = ObliqueSlicePage._get_active_mri_image


class _Vue3D:
    def __init__(self, t1_coche, t2_coche, opacite=None, t2=None):
        self._t1_img = rampe(1000.0)
        self._t2 = rampe(4000.0, inversee=True) if t2 is None else t2
        self.chk_mri_t1 = QCheckBox()
        self.chk_mri_t1.setChecked(t1_coche)
        self.chk_mri_t2 = QCheckBox()
        self.chk_mri_t2.setChecked(t2_coche)
        self._mri_opacity_3d = opacite or {"T1": 100, "T2": 50}

    def _get_t2_for_3d(self):
        return self._t2

    def _mni_t1_slices_are_visible(self):
        return False

    _mri_sources_3d = View3DPage._mri_sources_3d
    _get_active_mri_for_3d = View3DPage._get_active_mri_for_3d


PAGES = [
    pytest.param(_Oblique, "_oblique_mri_sources", "_get_active_mri_image", "_t1", id="oblique"),
    pytest.param(_Vue3D, "_mri_sources_3d", "_get_active_mri_for_3d", "_t1_img", id="3d"),
]


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_les_deux_cases_cochees_donnent_deux_couches(app, Page, sources, melange, nom_t1):
    """Ce que l'ancien code rendait impossible."""
    p = Page(True, True)
    assert [n for n, _, _ in getattr(p, sources)()] == ["T1", "T2"]


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_mri1_seule_rend_mri1(app, Page, sources, melange, nom_t1):
    """Normalisee, car les compositeurs ne renormalisent plus : seule la forme
    doit etre celle de MRI 1, pas ses valeurs brutes."""
    p = Page(True, False)
    obtenu = tableau(getattr(p, melange)()).ravel()
    assert np.corrcoef(obtenu, tableau(getattr(p, nom_t1)).ravel())[0, 1] == pytest.approx(1.0, abs=1e-6)
    assert obtenu.max() <= 1.0 + 1e-6


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_mri2_seule_rend_mri2(app, Page, sources, melange, nom_t1):
    """Le cas que l'utilisateur ne voyait pas : MRI 2 seule, sans MRI 1."""
    p = Page(False, True)
    obtenu = tableau(getattr(p, melange)()).ravel()
    assert np.corrcoef(obtenu, tableau(p._t2).ravel())[0, 1] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_l_opacite_d_une_seule_couche_est_visible(app, Page, sources, melange, nom_t1):
    """Le defaut signale : le curseur ne faisait rien.

    La couche sortait normalisee, puis le compositeur la re-etirait sur ses
    centiles, ce qui annulait exactement l'assombrissement."""
    pleine = tableau(getattr(Page(True, False, {"T1": 100, "T2": 50}), melange)())
    moitie = tableau(getattr(Page(True, False, {"T1": 50, "T2": 50}), melange)())
    assert moitie.max() == pytest.approx(0.5 * pleine.max(), rel=1e-5)


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_aucune_case_retombe_sur_mri1(app, Page, sources, melange, nom_t1):
    """Tout appelant qui demande l'anatomie doit trouver quelque chose."""
    p = Page(False, False)
    assert np.array_equal(tableau(getattr(p, melange)()), tableau(getattr(p, nom_t1)))


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
@pytest.mark.parametrize("opacite, vers_t1", [(0, True), (100, False)])
def test_le_fondu_atteint_ses_deux_extremites(
    app, Page, sources, melange, nom_t1, opacite, vers_t1
):
    p = Page(True, True, {"T1": 100, "T2": opacite})
    obtenu = tableau(getattr(p, melange)()).ravel()
    cible = tableau(getattr(p, nom_t1) if vers_t1 else p._t2).ravel()
    assert np.corrcoef(obtenu, cible)[0, 1] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_decocher_une_case_la_retire_aussitot(app, Page, sources, melange, nom_t1):
    """La case est lue a chaque appel, donc rien a resynchroniser."""
    p = Page(True, True)
    assert len(getattr(p, sources)()) == 2
    p.chk_mri_t2.setChecked(False)
    assert [n for n, _, _ in getattr(p, sources)()] == ["T1"]


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_une_mri2_absente_n_est_pas_dessinee_meme_cochee(
    app, Page, sources, melange, nom_t1
):
    """Une case cochee sur une image qui n'existe pas ne doit rien produire."""
    p = Page(True, True, t2=None)
    p._t2 = None
    assert [n for n, _, _ in getattr(p, sources)()] == ["T1"]


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_chaque_mri_garde_son_opacite(app, Page, sources, melange, nom_t1):
    pleine = tableau(getattr(Page(True, True, {"T1": 100, "T2": 0}), melange)())
    reduite = tableau(getattr(Page(True, True, {"T1": 40, "T2": 0}), melange)())
    assert reduite.mean() == pytest.approx(0.4 * pleine.mean(), rel=1e-5)


@pytest.mark.parametrize("Page, sources, melange, nom_t1", PAGES)
def test_les_echelles_differentes_ne_s_ecrasent_pas(app, Page, sources, melange, nom_t1):
    """MRI 2 porte des valeurs quatre fois plus grandes. Sans normalisation
    separee, elle recouvrirait MRI 1 quelles que soient les opacites."""
    melangee = tableau(getattr(Page(True, True), melange)())
    assert float(melangee.max()) <= 1.0 + 1e-6


def test_les_deux_pages_partagent_le_meme_melange():
    """Une seule implementation, sinon les deux pages finissent par diverger."""
    import inspect

    for fonction in (ObliqueSlicePage._get_active_mri_image, View3DPage._get_active_mri_for_3d):
        assert "blend_mri_volumes" in inspect.getsource(fonction)


def test_aucune_page_ne_garde_un_miroir_de_l_etat_des_cases():
    """Le defaut qui faisait que cocher MRI 2 ne montrait rien."""
    import inspect

    for module in (ObliqueSlicePage, View3DPage):
        source = inspect.getsource(module)
        assert "_oblique_mri_shown" not in source
        assert "_mri_shown_3d" not in source


# ---------------------------------------------------------------------------
# le rafraichissement, calque sur celui du PET
# ---------------------------------------------------------------------------


def test_la_vue_3d_repeint_les_plans_deja_affiches():
    """Le defaut signale : il fallait changer de coupe pour voir l'opacite.

    Vider le cache ne suffit pas, les plans gardent la texture qu'on leur a
    donnee. Le PET l'a toujours fait correctement, par
    _render_visible_pet_overlays_only ; son equivalent anatomique existait dans
    le fichier sans aucun appelant.
    """
    import inspect

    source = inspect.getsource(View3DPage._refresh_3d_mri_source_controls)
    assert "_render_visible_slice_planes_only" in source
    assert "_invalidate_slice_volume_cache" in source


def test_le_curseur_3d_attend_la_fin_du_glissement():
    """L'opacite d'une IRM est cuite dans la texture, pas une propriete
    d'acteur comme celle du PET : la recalculer a chaque pixel reconstruirait
    67 Mo de RGBA et rendrait le curseur pateux."""
    import inspect

    source = inspect.getsource(View3DPage._on_mri_opacity_changed_3d)
    assert "QTimer" in source
    assert "setSingleShot" in source


def test_les_coupes_obliques_redessinent_les_deux_fentes():
    """Leur equivalent : render_slices_only repasse par les deux fentes."""
    import inspect

    source = inspect.getsource(ObliqueSlicePage._on_oblique_mri_opacity_changed)
    assert "_invalidate_oblique_image_caches" in source
    assert "_schedule_refresh" in source


def test_la_vue_3d_ne_parente_aucun_minuteur_a_la_page():
    """View3DPage est un objet ordinaire, pas un QObject.

    QTimer(self) y leve donc TypeError. Le defaut etait invisible : le
    gestionnaire d'opacite enregistrait la valeur puis mourait sur cette ligne,
    de sorte que la nouvelle opacite n'apparaissait qu'apres avoir decoche puis
    recoche la couche. ObliqueSlicePage, elle, est un QObject et peut le faire.
    """
    import io
    import re

    from PySide6.QtCore import QObject

    assert not issubclass(View3DPage, QObject)
    source = io.open(
        "src/neuxelec/pages/view3d.py", encoding="utf-8-sig"
    ).read()
    code = [
        ligne for ligne in source.splitlines()
        if "QTimer(self)" in ligne and not ligne.strip().startswith("#")
    ]
    assert code == [], code
