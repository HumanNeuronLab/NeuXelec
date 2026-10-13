"""Ce que le mode visualisation interdit.

LE CHOIX QUI STRUCTURE TOUT

Les reglages d'affichage restent libres : couleurs, opacites, filtres,
camera, coupe montree. Ce qui est interdit, c'est de modifier les
donnees du patient, et le fichier projet ne s'ecrit plus du tout.

POURQUOI LE REFUS EST DANS L'ECRITURE ET NON SUR LE BOUTON

Six endroits ecrivent le projet, et trois le font seuls : apres une
electrode renommee, une camera enregistree, une position de coupe
memorisee. Un garde-fou sur le bouton aurait laisse ces trois-la
ecrire. Le premier test de ce fichier est donc celui du refus central ;
le bouton n'en est que la moitie visible.
"""

from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from neuxelec.project_io import save_project_json  # noqa: E402
from neuxelec.ui import context_menus  # noqa: E402
from neuxelec.utils.app_mode import (  # noqa: E402
    ProjectIsViewOnly,
    is_edit_mode,
    is_view_only,
)


class _State:
    def __init__(self, mode):
        self.app_mode = mode
        self.project_path = None
        self.electrodes = []
        self.markers = []
        self.stimulations = []


# ------------------------------------------------------------- lire le mode


@pytest.mark.parametrize(
    "valeur, edition",
    [
        ("edit", True),
        ("EDIT", True),
        ("  edit  ", True),
        ("visualization", False),
        ("", True),
        (None, True),
    ],
)
def test_le_mode_se_lit_de_la_meme_facon_partout(valeur, edition):
    """Vide ou absent veut dire edition: un projet ouvert normalement ne
    doit pas devenir lecture seule par accident."""
    etat = _State(valeur)

    assert is_edit_mode(etat) is edition
    assert is_view_only(etat) is (not edition)


# ------------------------------------------------------------- le projet


def test_le_projet_ne_s_ecrit_pas_en_visualisation(tmp_path):
    chemin = tmp_path / "patient.json"

    with pytest.raises(ProjectIsViewOnly):
        save_project_json(_State("visualization"), chemin)

    assert not chemin.exists(), "un fichier a ete ecrit malgre le refus"


def test_un_projet_existant_n_est_pas_ecrase_non_plus(tmp_path):
    """Le cas qui compte vraiment : un projet relu en lecture seule ne doit
    pas pouvoir etre remplace par l'etat de la session."""
    chemin = tmp_path / "patient.json"
    chemin.write_text('{"patient_id": "original"}', encoding="utf-8")

    with pytest.raises(ProjectIsViewOnly):
        save_project_json(_State("visualization"), chemin)

    assert "original" in chemin.read_text(encoding="utf-8")


def test_en_edition_le_projet_s_ecrit(tmp_path):
    chemin = tmp_path / "patient.json"

    save_project_json(_State("edit"), chemin)

    assert chemin.exists()


# ------------------------------------------------- ce que les menus montrent


def _source(fonction):
    return inspect.getsource(fonction)


@pytest.mark.parametrize(
    "entree",
    [
        '"Add marker…"',
        '"Edit marker…"',
        '"Move marker"',
        '"Delete marker"',
        '"Load MNI electrodes.tsv…"',
    ],
)
def test_les_entrees_du_menu_3d_qui_modifient_sont_sous_garde(entree):
    """Chacune ecrit dans le projet. Les lignes voisines, Marker list,
    Hide marker et Export marker, ne doivent pas l'etre."""
    texte = _source(context_menus.exec_3d_view_menu)
    i = texte.index(entree)
    avant = texte[:i]

    assert "if editable" in avant, f"{entree} n'est protege par rien"


@pytest.mark.parametrize("entree", ['"Marker list"', '"Hide marker"', '"Export marker…"'])
def test_ce_qui_ne_modifie_rien_reste_offert(entree):
    texte = _source(context_menus.exec_3d_view_menu)
    ligne = [l for l in texte.splitlines() if entree in l]

    assert ligne, f"{entree} a disparu du menu"
    assert all("if editable" not in l for l in ligne)


def test_ajouter_une_stimulation_demande_le_mode_edition():
    texte = _source(context_menus.exec_electrode_tree_menu)
    i = texte.index('"Add stimulation result"')

    assert "if editable" in texte[:i]


def test_supprimer_un_patient_mni_demande_le_mode_edition():
    texte = _source(context_menus.exec_mni_electrode_tree_menu)
    i = texte.index('"Delete patient"')

    assert "if editable" in texte[:i]


@pytest.mark.parametrize(
    "fonction",
    [
        context_menus.exec_3d_view_menu,
        context_menus.exec_electrode_tree_menu,
        context_menus.exec_mni_electrode_tree_menu,
    ],
)
def test_chaque_menu_sait_dans_quel_mode_il_est(fonction):
    assert "editable" in inspect.signature(fonction).parameters


def test_la_vue_3d_transmet_le_mode_a_ses_deux_menus():
    """Un menu qui accepte le parametre mais ne le recoit jamais serait
    protege sur le papier seulement."""
    from neuxelec.pages import view3d

    texte = inspect.getsource(view3d)

    assert texte.count("editable=is_edit_mode(self.state)") == 2

# ------------------------------------------------- ce que les fenetres montrent


class _StimState(_State):
    def __init__(self, mode):
        super().__init__(mode)
        self.stimulation_display = {}
        self.stimulation_filters = {}


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _fenetre_stimulation(app, mode):
    from neuxelec.ui.stimulation_results_dialog import StimulationResultsDialog

    f = StimulationResultsDialog(_StimState(mode))
    f.show()
    app.processEvents()
    return f


def test_en_visualisation_les_fiches_se_lisent_seulement(app):
    """Les trois boutons disparaissent au lieu de rester grises: un bouton
    eteint promet encore quelque chose.

    isHidden et non isVisible: les boutons des fiches vivent dans un
    onglet, et un onglet au second plan rend invisible tout ce qu'il
    porte, y compris ce que l'on n'a pas cache.
    """
    f = _fenetre_stimulation(app, "visualization")

    assert f.btn_add.isHidden()
    assert f.btn_edit.isHidden()
    assert f.btn_delete.isHidden()
    assert not f.btn_export.isHidden(), "l'export ne modifie rien et doit rester"

    f.hide()
    f.deleteLater()


def test_en_edition_ils_sont_tous_la(app):
    f = _fenetre_stimulation(app, "edit")

    assert not f.btn_add.isHidden()
    assert not f.btn_edit.isHidden()
    assert not f.btn_delete.isHidden()

    f.hide()
    f.deleteLater()


def test_la_liste_des_marqueurs_retient_le_mode(app):
    from neuxelec.ui.marker_list_dialog import MarkerListDialog

    lecture = MarkerListDialog(markers_provider=lambda: [], editable=False)
    edition = MarkerListDialog(markers_provider=lambda: [])

    assert lecture._editable is False
    assert edition._editable is True

    texte = inspect.getsource(MarkerListDialog)
    for entree in ('"Edit marker"', '"Delete marker"'):
        ligne = [l for l in texte.splitlines() if "addAction(" + entree in l]
        assert ligne, f"{entree} a disparu"
        assert "self._editable" in ligne[0], f"{entree} n'est protege par rien"

    lecture.deleteLater()
    edition.deleteLater()
