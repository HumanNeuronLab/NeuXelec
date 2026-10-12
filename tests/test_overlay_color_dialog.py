"""Une fenetre pour la couleur des six calques, au lieu de six entrees.

Ce qui doit tenir :
  - les six calques sont proposes, dans l'ordre des anciennes entrees ;
  - le second controle suit le calque choisi, parce que le fMRI n'a pas les
    memes echelles que le PET ;
  - le CT montre un bouton de couleur et non une echelle, puisqu'il porte
    une couleur unie ;
  - la reponse arrive au bon appliqueur, et a lui seul.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.view3d import View3DPage  # noqa: E402
from neuxelec.ui.overlay_color_dialog import OverlayColorDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def calques():
    return [
        {"key": "pet", "label": "PET", "kind": "colormap",
         "options": ["hot", "inferno", "jet"], "current": "jet"},
        {"key": "fmri", "label": "fMRI", "kind": "colormap",
         "options": ["hot", "coolwarm", "RdBu_r"], "current": "coolwarm"},
        {"key": "ct", "label": "CT", "kind": "solid", "current": "#20C0A0"},
    ]


def test_les_calques_sont_proposes_dans_l_ordre(app, calques):
    dlg = OverlayColorDialog(calques)
    assert [dlg.combo_layer.itemText(i) for i in range(dlg.combo_layer.count())] == [
        "PET", "fMRI", "CT"
    ]


def test_le_premier_calque_ouvre_sur_son_echelle_courante(app, calques):
    dlg = OverlayColorDialog(calques)
    assert dlg.combo_selection.currentText() == "jet"
    assert dlg.selection() == ("pet", "jet")


def test_changer_de_calque_change_les_echelles_offertes(app, calques):
    """Le fMRI a ses propres echelles : offrir celles du PET serait faux."""
    dlg = OverlayColorDialog(calques)
    dlg.combo_layer.setCurrentIndex(1)

    offertes = [dlg.combo_selection.itemText(i) for i in range(dlg.combo_selection.count())]
    assert offertes == ["hot", "coolwarm", "RdBu_r"]
    assert dlg.combo_selection.currentText() == "coolwarm"
    assert dlg.selection() == ("fmri", "coolwarm")


def test_le_ct_montre_un_bouton_de_couleur_et_pas_une_echelle(app, calques):
    """Le CT porte une couleur unie, il n'a pas de valeur par voxel."""
    dlg = OverlayColorDialog(calques)
    dlg.show()

    dlg.combo_layer.setCurrentIndex(2)
    assert dlg.btn_solid_color.isVisible()
    assert not dlg.combo_selection.isVisible()
    assert dlg.btn_solid_color.text() == "#20C0A0"  # affiche en majuscules
    assert dlg.selection() == ("ct", "#20c0a0")

    dlg.combo_layer.setCurrentIndex(0)
    assert dlg.combo_selection.isVisible()
    assert not dlg.btn_solid_color.isVisible()
    dlg.close()


def test_une_echelle_choisie_est_bien_celle_qui_revient(app, calques):
    dlg = OverlayColorDialog(calques)
    dlg.combo_selection.setCurrentIndex(1)
    assert dlg.selection() == ("pet", "inferno")


def test_sans_calque_la_fenetre_refuse_de_s_ouvrir(app):
    with pytest.raises(ValueError):
        OverlayColorDialog([])


# ----------------------------------------------------------------- routage


class _Page:
    """De quoi verifier que la reponse arrive au bon appliqueur."""

    OVERLAY_COLORMAPS = View3DPage.OVERLAY_COLORMAPS
    FMRI_COLORMAPS = View3DPage.FMRI_COLORMAPS

    def __init__(self):
        self.appels = []
        self._ct_color = (0.5, 0.5, 0.5)
        self._spect_colormap = {"ictal": "jet", "interictal": "turbo"}
        self._pet_colormap_name = "hot"
        self._siscom_colormap_name = "viridis"
        self._fmri_cmap_name = "coolwarm"

    def _dialog_parent(self):
        return None

    _tuple_to_qcolor = View3DPage._tuple_to_qcolor
    _overlay_color_layers = View3DPage._overlay_color_layers
    _open_overlay_color_dialog = View3DPage._open_overlay_color_dialog

    def _apply_pet_colormap(self, c):
        self.appels.append(("pet", c))

    def _apply_siscom_colormap(self, c):
        self.appels.append(("siscom", c))

    def _apply_fmri_colormap(self, c):
        self.appels.append(("fmri", c))

    def _apply_spect_colormap(self, layer, c):
        self.appels.append((layer, c))

    def _apply_modality_color(self, which, c):
        self.appels.append((which, c))


def test_les_six_calques_sont_offerts_avec_leur_valeur_courante(app):
    calques = _Page()._overlay_color_layers()
    assert [c["key"] for c in calques] == [
        "pet", "siscom", "fmri", "ictal", "interictal", "ct"
    ]
    par_cle = {c["key"]: c for c in calques}
    assert par_cle["fmri"]["options"] == list(View3DPage.FMRI_COLORMAPS)
    assert par_cle["pet"]["options"] == list(View3DPage.OVERLAY_COLORMAPS)
    assert par_cle["ictal"]["current"] == "jet"
    assert par_cle["ct"]["kind"] == "solid"
    # 0,5 x 255 vaut 127,5, tronque a 127, soit 0x7F.
    assert par_cle["ct"]["current"] == "#7f7f7f"


@pytest.mark.parametrize(
    "reponse,attendu",
    [
        (("pet", "turbo"), ("pet", "turbo")),
        (("siscom", "gray"), ("siscom", "gray")),
        (("fmri", "RdBu_r"), ("fmri", "RdBu_r")),
        (("ictal", "plasma"), ("ictal", "plasma")),
        (("interictal", "hot"), ("interictal", "hot")),
        (("ct", "#123456"), ("ct", "#123456")),
    ],
)
def test_la_reponse_arrive_au_bon_appliqueur(app, monkeypatch, reponse, attendu):
    monkeypatch.setattr(OverlayColorDialog, "choose",
                        staticmethod(lambda *a, **k: reponse))
    page = _Page()
    page._open_overlay_color_dialog()
    assert page.appels == [attendu]


def test_annuler_ne_touche_a_rien(app, monkeypatch):
    monkeypatch.setattr(OverlayColorDialog, "choose", staticmethod(lambda *a, **k: None))
    page = _Page()
    page._open_overlay_color_dialog()
    assert page.appels == []


# ------------------------------------------------- la meme chose pour l'oblique


class _PageOblique:
    """La coupe oblique : cinq calques, aucune couleur unie."""

    from neuxelec.pages.oblique_slice_page import ObliqueSlicePage as _Src

    OVERLAY_COLORMAPS = _Src.OVERLAY_COLORMAPS
    FMRI_COLORMAPS = _Src.FMRI_COLORMAPS

    def __init__(self):
        self.appels = []
        self._pet_colormap_name = "turbo"
        self._siscom_colormap_name = "gray"
        self._ospect_colormap = {"ictal": "plasma", "interictal": "inferno"}

    def _dialog_parent(self):
        return None

    def _ofmri_img(self):
        return None

    def _ofmri_cmap(self, _img):
        return "RdBu_r"

    _overlay_color_layers = _Src._overlay_color_layers
    _open_overlay_color_dialog = _Src._open_overlay_color_dialog

    def _apply_pet_colormap(self, c):
        self.appels.append(("pet", c))

    def _apply_siscom_colormap(self, c):
        self.appels.append(("siscom", c))

    def _apply_oblique_fmri_colormap(self, c):
        self.appels.append(("fmri", c))

    def _apply_oblique_spect_colormap(self, layer, c):
        self.appels.append((layer, c))


def test_l_oblique_propose_cinq_calques_et_aucune_couleur_unie(app):
    """Elle ne surimprime pas le CT : tout y porte une valeur par voxel."""
    calques = _PageOblique()._overlay_color_layers()
    assert [c["key"] for c in calques] == ["pet", "siscom", "fmri", "ictal", "interictal"]
    assert all(c["kind"] == "colormap" for c in calques)

    par_cle = {c["key"]: c for c in calques}
    assert par_cle["pet"]["current"] == "turbo"
    assert par_cle["ictal"]["current"] == "plasma"
    assert par_cle["fmri"]["current"] == "RdBu_r"


def test_l_oblique_garde_sa_propre_liste_pour_le_fmri(app):
    """Elle offre huit echelles la ou la vue 3D en offre six : ce sont deux
    listes differentes, et les confondre en retirerait a l'une."""
    from neuxelec.pages.oblique_slice_page import ObliqueSlicePage
    from neuxelec.pages.view3d import View3DPage

    assert len(ObliqueSlicePage.FMRI_COLORMAPS) == 8
    assert len(View3DPage.FMRI_COLORMAPS) == 6
    assert "RdBu_r" in ObliqueSlicePage.FMRI_COLORMAPS


@pytest.mark.parametrize(
    "reponse,attendu",
    [
        (("pet", "hot"), ("pet", "hot")),
        (("siscom", "jet"), ("siscom", "jet")),
        (("fmri", "coolwarm"), ("fmri", "coolwarm")),
        (("ictal", "viridis"), ("ictal", "viridis")),
        (("interictal", "gray"), ("interictal", "gray")),
    ],
)
def test_la_reponse_arrive_au_bon_appliqueur_dans_l_oblique(app, monkeypatch, reponse, attendu):
    monkeypatch.setattr(OverlayColorDialog, "choose", staticmethod(lambda *a, **k: reponse))
    page = _PageOblique()
    page._open_overlay_color_dialog()
    assert page.appels == [attendu]


def test_annuler_ne_touche_a_rien_dans_l_oblique(app, monkeypatch):
    monkeypatch.setattr(OverlayColorDialog, "choose", staticmethod(lambda *a, **k: None))
    page = _PageOblique()
    page._open_overlay_color_dialog()
    assert page.appels == []
