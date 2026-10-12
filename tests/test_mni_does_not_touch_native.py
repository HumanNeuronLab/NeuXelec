"""Le mode MNI ne doit rien laisser derriere lui dans la vue native.

C'est le contrat de toute la session : les onglets sont des panneaux de
commande sur une scene, et passer par le MNI doit rendre la vue du
patient exactement telle qu'on l'avait laissee.

Ces tests exercent la vraie memoire du mode, celle qui existait avant
cette session, pour qu'aucune de ses modifications ne l'ait entamee. Ils
ne touchent pas au trace des electrodes MNI, qui n'a pas bouge d'une
ligne : ils verifient justement qu'il n'avait pas a bouger.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

from neuxelec.pages.view3d_mni import View3DMniMixin  # noqa: E402

#: Les onze cases que le mode MNI promet de rendre telles quelles.
CASES = (
    "chk_brainmask",
    "chk_iso",
    "chk_pial",
    "chk_ct",
    "chk_pet",
    "chk_siscom",
    "chk_coronal_plane",
    "chk_axial_plane",
    "chk_sagittal_plane",
    "chk_parcel1",
    "chk_parcel2",
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Les onze cases, et les deux methodes qui les gerent."""

    def __init__(self, etat):
        for nom in CASES:
            case = QCheckBox()
            case.setChecked(bool(etat.get(nom, False)))
            setattr(self, nom, case)
        self._switching_mni_to_native_brain = False

    _store_native_checkbox_state_for_mni = (
        View3DMniMixin._store_native_checkbox_state_for_mni
    )
    _set_native_checkboxes_for_mni = View3DMniMixin._set_native_checkboxes_for_mni

    def etat(self):
        return {nom: getattr(self, nom).isChecked() for nom in CASES}

    def activables(self):
        return {nom: getattr(self, nom).isEnabled() for nom in CASES}


DEPARTS = [
    pytest.param({"chk_brainmask": True, "chk_ct": True}, id="brainmask et CT"),
    pytest.param(
        {"chk_pial": True, "chk_parcel1": True, "chk_axial_plane": True},
        id="pial, parcellation et une coupe",
    ),
    pytest.param({}, id="rien d'affiche"),
    pytest.param(dict.fromkeys(CASES, True), id="tout coche"),
]


@pytest.mark.parametrize("depart", DEPARTS)
def test_un_aller_retour_rend_la_vue_native_intacte(app, depart):
    page = _Page(depart)
    avant = page.etat()

    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)
    page._set_native_checkboxes_for_mni(False)

    assert page.etat() == avant


@pytest.mark.parametrize("depart", DEPARTS)
def test_le_mode_mni_eteint_bien_tout_le_natif(app, depart):
    """Aucun objet du patient ne doit rester sur le gabarit."""
    page = _Page(depart)
    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)

    assert not any(page.etat().values())


def test_le_cerveau_et_la_piale_restent_cliquables_en_mode_mni(app):
    """Ce sont les deux portes de sortie du mode."""
    page = _Page(dict.fromkeys(CASES, True))
    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)

    activables = page.activables()
    assert activables["chk_brainmask"]
    assert activables["chk_pial"]
    assert not activables["chk_ct"]
    assert not activables["chk_parcel1"]


def test_sortir_par_un_clic_sur_le_cerveau_ne_defait_pas_ce_clic(app):
    """Restaurer l'ancien etat annulerait le geste qui fait sortir."""
    page = _Page({"chk_ct": True, "chk_pial": True})
    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)

    page._switching_mni_to_native_brain = True
    page.chk_brainmask.setChecked(True)
    page._set_native_checkboxes_for_mni(False)

    assert page.chk_brainmask.isChecked(), "le clic de sortie a ete annule"
    assert not page.chk_pial.isChecked(), "l'ancien etat a ete restaure quand meme"


def test_deux_allers_retours_ne_derivent_pas(app):
    """La memoire ne doit pas se remplir de l'etat eteint du passage precedent."""
    page = _Page({"chk_brainmask": True, "chk_parcel1": True})
    avant = page.etat()

    for _ in range(3):
        page._store_native_checkbox_state_for_mni()
        page._set_native_checkboxes_for_mni(True)
        page._set_native_checkboxes_for_mni(False)

    assert page.etat() == avant


def test_les_cases_redeviennent_toutes_cliquables_en_sortant(app):
    page = _Page({})
    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)
    page._set_native_checkboxes_for_mni(False)

    assert all(page.activables().values())


def test_une_case_absente_ne_fait_rien_lever(app):
    """Toutes les pages n'ont pas tous ces controles."""
    page = _Page({})
    page.chk_iso = None
    page.chk_siscom = None
    page._store_native_checkbox_state_for_mni()
    page._set_native_checkboxes_for_mni(True)
    page._set_native_checkboxes_for_mni(False)
