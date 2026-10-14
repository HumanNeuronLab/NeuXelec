# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les reglages des calques suivent le projet.

CE QUI CHANGE

Rouvrir un projet remettait chaque calque fonctionnel a son defaut : la
fenetre du PET, le seuil du SISCOM, l'opacite du CT. Le reglage trouve a
la main etait refait a chaque ouverture.

CE QUE CES TESTS PROTEGENT

Le plus utile des quatre est celui qui compare les listes de noms au
.ui : un nom de widget mal orthographie ne casse rien, ne leve rien, et
le reglage disparait simplement sans que personne ne s'en apercoive.

Vient ensuite l'ordre : les cases qui montrent un calque sont appliquees
apres les valeurs dont elles dependent, pour que la scene soit dessinee
une fois avec les bons reglages au lieu d'etre dessinee aux valeurs par
defaut puis corrigee.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
    QWidget,
)

from neuxelec.pages.oblique_display_settings import (  # noqa: E402
    OBLIQUE_DISPLAY_WIDGETS,
)
from neuxelec.pages.view3d_display_settings import (  # noqa: E402
    VIEW3D_DISPLAY_WIDGETS,
)
from neuxelec.project_io import (  # noqa: E402
    apply_project_dict_to_state,
    build_project_dict_from_state,
)
from neuxelec.utils import display_settings as ds  # noqa: E402

UI = Path(__file__).resolve().parents[1] / "resources" / "ui" / "MainWindow.ui"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page(QWidget):
    """Une page reduite a quelques reglages, chacun d'un type different."""

    def __init__(self):
        super().__init__()
        self.ui = self

        self.sld = QSlider(self)
        self.sld.setObjectName("sld_test")
        self.sld.setRange(0, 100)
        self.sld.setValue(40)

        self.dsb = QDoubleSpinBox(self)
        self.dsb.setObjectName("dsb_test")
        self.dsb.setRange(0.0, 10.0)
        self.dsb.setValue(2.5)

        self.sb = QSpinBox(self)
        self.sb.setObjectName("sb_test")
        self.sb.setRange(0, 999)
        self.sb.setValue(12)

        self.chk = QCheckBox(self)
        self.chk.setObjectName("chk_test")
        self.chk.setChecked(True)

        self.cmb = QComboBox(self)
        self.cmb.setObjectName("cmb_test")
        self.cmb.addItems(["hot", "jet", "viridis"])
        self.cmb.setCurrentIndex(2)


NOMS = ("sld_test", "dsb_test", "sb_test", "cmb_test", "chk_test")


# --------------------------------------------------- lire et reposer


def test_chaque_type_de_reglage_se_lit(app):
    valeurs = ds.read_widgets(_Page(), NOMS)

    assert valeurs == {
        "sld_test": 40,
        "dsb_test": 2.5,
        "sb_test": 12,
        "cmb_test": "viridis",
        "chk_test": True,
    }


def test_ce_qui_a_ete_lu_se_repose(app):
    valeurs = ds.read_widgets(_Page(), NOMS)
    autre = _Page()
    autre.sld.setValue(0)
    autre.dsb.setValue(0.0)
    autre.sb.setValue(0)
    autre.chk.setChecked(False)
    autre.cmb.setCurrentIndex(0)

    appliques = ds.apply_widgets(autre, valeurs, NOMS)

    assert set(appliques) == set(NOMS)
    assert autre.sld.value() == 40
    assert autre.dsb.value() == pytest.approx(2.5)
    assert autre.sb.value() == 12
    assert autre.chk.isChecked()
    assert autre.cmb.currentText() == "viridis"


def test_un_reglage_inconnu_est_ignore_sans_bruit(app):
    """Un projet ecrit avant qu'un reglage existe, ou un widget retire de
    l'interface: l'ouverture ne doit pas en souffrir."""
    page = _Page()

    appliques = ds.apply_widgets(page, {"sld_disparu": 3, "sld_test": 70}, None)

    assert appliques == ["sld_test"]
    assert page.sld.value() == 70


def test_une_palette_absente_de_la_liste_ne_change_rien(app):
    page = _Page()

    assert ds.apply_widgets(page, {"cmb_test": "inexistante"}, ("cmb_test",)) == []
    assert page.cmb.currentText() == "viridis"


def test_l_ordre_demande_est_l_ordre_applique(app):
    """La case qui montre un calque doit passer apres ses valeurs."""
    page = _Page()
    vus = []
    page.sld.valueChanged.connect(lambda _v: vus.append("sld"))
    page.chk.toggled.connect(lambda _v: vus.append("chk"))
    page.sld.setValue(0)
    page.chk.setChecked(False)
    vus.clear()

    ds.apply_widgets(page, {"chk_test": True, "sld_test": 55}, ("sld_test", "chk_test"))

    assert vus == ["sld", "chk"]


# --------------------------------------------------- les listes disent vrai


@pytest.mark.parametrize(
    "noms, page",
    [(VIEW3D_DISPLAY_WIDGETS, "vue 3D"), (OBLIQUE_DISPLAY_WIDGETS, "coupe oblique")],
)
def test_chaque_nom_existe_vraiment_dans_l_interface(noms, page):
    """Le test qui compte : un nom mal orthographie ne leve rien, ne casse
    rien, et le reglage disparait sans bruit."""
    texte = io.open(UI, encoding="utf-8").read()
    manquants = [n for n in noms if f'name="{n}"' not in texte]

    assert not manquants, f"{page}: {manquants} n'existent pas dans MainWindow.ui"


@pytest.mark.parametrize(
    "noms", [VIEW3D_DISPLAY_WIDGETS, OBLIQUE_DISPLAY_WIDGETS]
)
def test_les_cases_des_calques_viennent_en_dernier(noms):
    cases = [i for i, n in enumerate(noms) if n.startswith("chk_")]
    valeurs = [i for i, n in enumerate(noms) if not n.startswith("chk_")]

    assert cases, "aucune case de calque dans la liste"
    assert min(cases) > max(valeurs), "une valeur est appliquee apres sa case"


@pytest.mark.parametrize(
    "noms", [VIEW3D_DISPLAY_WIDGETS, OBLIQUE_DISPLAY_WIDGETS]
)
def test_aucun_nom_n_est_liste_deux_fois(noms):
    assert len(set(noms)) == len(noms)


# --------------------------------------------------- l'aller-retour du projet


class _FakePage:
    def __init__(self, bloc):
        self._bloc = bloc

    def display_settings_dict(self):
        return self._bloc


class _State:
    app_mode = "edit"

    def __init__(self, view3d=None, oblique=None):
        self.view3d_page = _FakePage(view3d) if view3d is not None else None
        self.oblique_page = _FakePage(oblique) if oblique is not None else None
        self.electrodes = []
        self.markers = []
        self.stimulations = []
        self.display_settings = {}
        self.display_settings_applied = set()


def test_le_projet_retient_ce_que_les_pages_disent():
    etat = _State(
        view3d={"widgets": {"sld_3d_ctOpacity": 70}},
        oblique={"widgets": {"chk_obliqueSlice_PET": True}},
    )
    etat.display_settings_applied = {"view3d", "oblique"}

    data = build_project_dict_from_state(etat)

    assert data["display"]["view3d"]["widgets"]["sld_3d_ctOpacity"] == 70
    assert data["display"]["oblique"]["widgets"]["chk_obliqueSlice_PET"] is True


def test_une_page_absente_ne_fait_pas_echouer_l_enregistrement():
    """Au demarrage, ou dans les tests, les pages n'existent pas toujours."""
    data = build_project_dict_from_state(_State())

    assert data["display"] == {}


def test_ce_qui_a_ete_enregistre_revient_dans_l_etat():
    etat = _State(view3d={"widgets": {"sld_3d_petGamma": 33}})
    etat.display_settings_applied = {"view3d"}
    data = build_project_dict_from_state(etat)

    relu = _State()
    apply_project_dict_to_state(relu, data, "C:/patient/projet.json")

    assert relu.display_settings["view3d"]["widgets"]["sld_3d_petGamma"] == 33


def test_un_projet_ecrit_avant_n_a_pas_ce_bloc():
    relu = _State()

    apply_project_dict_to_state(relu, {"patient_id": "x"}, "C:/patient/projet.json")

    assert relu.display_settings == {}

# --------------------------------------------------- quand ils sont reposes


class _MainWindow:
    """La seule methode qui nous interesse, sur un objet nu."""

    from neuxelec.main_window import NeuxelecWindow as _MW

    _restore_display_settings = _MW._restore_display_settings

    def __init__(self, bloc):
        self.state = _State()
        self.state.display_settings = bloc


class _PageQuiRecoit:
    def __init__(self):
        self.recus = []

    def apply_display_settings(self, data):
        self.recus.append(data)
        return []


def test_les_reglages_sont_reposes_quand_la_page_s_ouvre():
    fenetre = _MainWindow({"view3d": {"widgets": {"sld_3d_ctOpacity": 55}}})
    page = _PageQuiRecoit()

    fenetre._restore_display_settings("view3d", page)

    assert page.recus == [{"widgets": {"sld_3d_ctOpacity": 55}}]


def test_revenir_sur_la_page_ne_les_repose_pas():
    """Sinon un reglage change entre deux visites serait annule."""
    fenetre = _MainWindow({"view3d": {"widgets": {"sld_3d_ctOpacity": 55}}})
    page = _PageQuiRecoit()

    fenetre._restore_display_settings("view3d", page)
    fenetre._restore_display_settings("view3d", page)
    fenetre._restore_display_settings("view3d", page)

    assert len(page.recus) == 1


def test_sans_bloc_la_page_n_est_pas_derangee():
    fenetre = _MainWindow({})
    page = _PageQuiRecoit()

    fenetre._restore_display_settings("oblique", page)

    assert page.recus == []


def test_les_deux_pages_sont_servies():
    """Une page branchee et l'autre oubliee serait le defaut le plus
    probable ici, et le moins visible."""
    import inspect

    from neuxelec.main_window import NeuxelecWindow

    texte = inspect.getsource(NeuxelecWindow._on_page_changed)

    assert '_restore_display_settings("oblique"' in texte
    assert '_restore_display_settings("view3d"' in texte

def test_une_page_jamais_ouverte_ne_perd_pas_ses_reglages():
    """Le piege de cette fonction: les reglages sont reposes quand la page
    s'ouvre. Rester sur les coupes obliques puis enregistrer lirait une
    vue 3D restee aux valeurs par defaut, et effacerait ce que le projet
    gardait."""
    etat = _State(view3d={"widgets": {"sld_3d_ctOpacity": 0}})
    etat.display_settings = {"view3d": {"widgets": {"sld_3d_ctOpacity": 88}}}
    etat.display_settings_applied = set()

    data = build_project_dict_from_state(etat)

    assert data["display"]["view3d"]["widgets"]["sld_3d_ctOpacity"] == 88


def test_une_page_ouverte_fait_foi():
    etat = _State(view3d={"widgets": {"sld_3d_ctOpacity": 12}})
    etat.display_settings = {"view3d": {"widgets": {"sld_3d_ctOpacity": 88}}}
    etat.display_settings_applied = {"view3d"}

    data = build_project_dict_from_state(etat)

    assert data["display"]["view3d"]["widgets"]["sld_3d_ctOpacity"] == 12
