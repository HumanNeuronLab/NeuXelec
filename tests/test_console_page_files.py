# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La page Files est une console.

CE QUI A CHANGE

Les cinq etapes sont des tuiles de meme taille, en haut, et le cockpit
passe dessous, en deux colonnes. Chaque ligne de l'imagerie n'a plus un
mot d'etat mais trois points: charge, coregistre, enregistre. Et les six
cases a cocher de la coregistration ont quitte la page: Align et Review
demandent sur quelle image ils travaillent.

CE QUE CES TESTS PROTEGENT

Un seul calcul decide de ce que valent les quatre colonnes. Les points,
la ligne de resume en haut a droite et la ligne grise de chaque tuile le
lisent tous les trois. S'il etait refait a trois endroits, la page
finirait par se contredire elle-meme, et c'est exactement ce qu'un
cockpit ne doit jamais faire.
"""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QWidget  # noqa: E402

from neuxelec.pages import files_page as module_page  # noqa: E402
from neuxelec.pages.files_page import FilesPage  # noqa: E402

UI = Path(__file__).resolve().parents[1] / "resources" / "ui" / "MainWindow.ui"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Etat:
    """Un etat de patient ou tout ce qui n'est pas dit est absent."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, nom):
        return None


class _Page:
    """La page reduite a ce que la console calcule.

    Les methodes sont celles de FilesPage, empruntees et non recopiees:
    un test qui passerait sur une copie ne dirait rien de la page.
    """

    IMAGING_ROWS = FilesPage.IMAGING_ROWS
    MARKS = FilesPage.MARKS
    STEP_CARDS = FilesPage.STEP_CARDS
    ALIGNABLE = FilesPage.ALIGNABLE
    SAVE_BUTTONS = FilesPage.SAVE_BUTTONS
    SAVED_PATHS = FilesPage.SAVED_PATHS
    SAVED_ALL_PATHS = FilesPage.SAVED_ALL_PATHS

    _set_dynamic_property = staticmethod(FilesPage._set_dynamic_property)
    _coreg_image_for = FilesPage._coreg_image_for
    _imaging_states = FilesPage._imaging_states
    _imaging_marks = FilesPage._imaging_marks
    _sync_imaging_columns = FilesPage._sync_imaging_columns
    _sync_files_header = FilesPage._sync_files_header
    _sync_step_lines = FilesPage._sync_step_lines
    _sync_current_step = FilesPage._sync_current_step
    _step_done_flags = FilesPage._step_done_flags
    _saved_flags = FilesPage._saved_flags
    _loaded_alignable = FilesPage._loaded_alignable
    _check_only = FilesPage._check_only
    _ask_which_modality = FilesPage._ask_which_modality
    _pending_review = FilesPage._pending_review
    ask_what_to_align = FilesPage.ask_what_to_align
    ask_what_to_review = FilesPage.ask_what_to_review
    _display_modality_name = FilesPage._display_modality_name

    def __init__(self, etat=None, ui=None):
        self.state = etat if etat is not None else _Etat()
        self.ui = ui

    def _dialog_parent(self):
        return None


PATIENT = dict(
    t1_path="t1.nii",
    t2_path="t2.nii",
    t2_coreg_in_t1=object(),
    t2_validated=True,
    t2_coreg_path="t2_in_t1.nii",
    ct_path="ct.nii",
    ct_coreg_in_t1=object(),
    pet_path="pet.nii",
)


# ------------------------------------------- ce que disent les colonnes


def test_les_trois_colonnes_suivent_une_image_du_disque_au_disque():
    etats = _Page(_Etat(**PATIENT))._imaging_states()

    # Relue et ecrite: la ligne est verte de bout en bout.
    assert etats["T2"] == {"load": "done", "coreg": "done", "save": "done"}

    # Recalee mais pas encore relue: la colonne reste orange, parce que
    # ce qui n'est pas relu ne peut pas etre enregistre.
    assert etats["CT"] == {"load": "done", "coreg": "todo", "save": "off"}

    # Chargee seulement: orange aussi. La ligne de la tuile dit lequel
    # des deux gestes manque.
    assert etats["PET"] == {"load": "done", "coreg": "todo", "save": "off"}

    # Rien: trois cercles vides, et rien n'est du.
    assert set(etats["fMRI"].values()) == {"off"}


def test_la_colonne_dit_recale_seulement_quand_c_est_relu():
    """Le piege de la colonne fusionnee: un calcul fini n'est pas un
    resultat valide, et seul un resultat valide s'enregistre."""
    etat = _Etat(t1_path="t1.nii", ct_path="ct.nii", ct_coreg_in_t1=object())
    assert _Page(etat)._imaging_states()["CT"]["coreg"] == "todo"

    etat.ct_validated = True
    assert _Page(etat)._imaging_states()["CT"]["coreg"] == "done"


def test_mri1_est_la_reference_et_n_a_qu_une_pastille():
    """On ne recale pas MRI 1 sur MRI 1, et on ne l'enregistre pas comme
    une sortie: ses deux dernieres cases sont vides, pas grises."""
    etats = _Page(_Etat(siscom_z_in_t1=object(), **PATIENT))._imaging_states()

    assert etats["T1"] == {"load": "done", "coreg": "na", "save": "na"}
    assert _Page.MARKS["na"] == ""
    assert "ref" not in _Page.MARKS

    # SISCOM nait dans l'espace de MRI 1: sa colonne ne dit que la
    # relecture, qui manque encore ici.
    assert etats["SISCOM"]["load"] == "done"
    assert etats["SISCOM"]["coreg"] == "todo"


def test_un_projet_rouvert_ne_redemande_pas_un_alignement_deja_fait():
    """A la reouverture, le fichier est la et l'image ne l'est pas encore.

    Lire la seule image en memoire aurait affiche "a aligner" sur une
    modalite dont le volume recale est sur le disque.
    """
    etats = _Page(
        _Etat(t1_path="t1.nii", ct_path="ct.nii", ct_validated=True, ct_coreg_path="ct_in_t1.nii")
    )._imaging_states()

    assert etats["CT"] == {"load": "done", "coreg": "done", "save": "done"}


# ------------------------------------------- ce que dit le haut de page


def test_le_resume_compte_exactement_ce_que_montrent_les_points(app):
    hote = QWidget()
    nom = QLabel(hote)
    nom.setObjectName("filesPatientName")
    ligne = QLabel(hote)
    ligne.setObjectName("filesSummaryLine")

    # Le CT est relu mais pas encore ecrit: il reste donc une sortie.
    page = _Page(_Etat(patient_id="PAT_BB", **dict(PATIENT, ct_validated=True)), ui=hote)
    etats = page._imaging_states()
    page._sync_files_header(etats)

    assert nom.text() == "PAT_BB"
    resume = ligne.text()
    assert "4 of 8 images" in resume
    assert "1 to coregister" in resume  # le PET
    assert "1 to save" in resume  # le CT
    hote.deleteLater()


def test_sans_rien_de_charge_le_resume_le_dit_sans_chiffres(app):
    hote = QWidget()
    ligne = QLabel(hote)
    ligne.setObjectName("filesSummaryLine")

    page = _Page(_Etat(), ui=hote)
    page._sync_files_header(page._imaging_states())

    assert ligne.text() == "Nothing loaded yet."
    hote.deleteLater()


def test_la_tuile_courante_est_la_premiere_qui_reste_a_faire(app):
    from PySide6.QtWidgets import QFrame

    hote = QWidget()
    cadres = {}
    for numero, carte in zip("12345", FilesPage.STEP_CARDS):
        f = QFrame(hote)
        f.setObjectName(carte)
        cadres[numero] = f
        k = QLabel(hote)
        k.setObjectName(f"filesStepKicker{numero}")

    page = _Page(_Etat(t1_path="t1.nii"), ui=hote)
    page._sync_current_step()

    # Des images chargees, pas de masque: l'etape 2 est celle qui reste.
    assert cadres["2"].property("current") is True
    assert [c.property("current") for n, c in cadres.items() if n != "2"] == [
        False,
        False,
        False,
        False,
    ]
    hote.deleteLater()


# ------------------------------------------- ce que fait le bouton Align


def _page_avec_cases(app, etat):
    hote = QWidget()
    page = _Page(etat, ui=hote)
    for attribut in ("chk_t2", "chk_ct", "chk_pet", "chk_ictal", "chk_interictal", "chk_fmri"):
        setattr(page, attribut, QCheckBox(hote))
    return page, hote


def test_align_demande_quelle_image_et_coche_celle_la(app, monkeypatch):
    """Les six cases ont quitte la page, pas le code: c'est toujours une
    case cochee que lisent perform_coreg et check_coreg."""
    page, hote = _page_avec_cases(
        app, _Etat(t1_path="t1.nii", ct_path="ct.nii", pet_path="pet.nii")
    )

    demandes = []

    class _Dialogue:
        @staticmethod
        def choice(parent, titre, question, choix, cancel_primary=False):
            demandes.append([cle for cle, _libelle, _p in choix])
            return "PET"

        @staticmethod
        def warning(*a, **k):
            raise AssertionError("rien a avertir ici")

    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _Dialogue)

    lances = []
    page.perform_coreg = lambda: lances.append("align")
    page.ask_what_to_align()

    assert demandes == [["CT", "PET"]]  # seules les images chargees
    assert lances == ["align"]
    assert page.chk_pet.isChecked()
    assert not page.chk_ct.isChecked()
    hote.deleteLater()


def test_annuler_la_question_ne_lance_rien(app, monkeypatch):
    page, hote = _page_avec_cases(app, _Etat(t1_path="t1.nii", ct_path="ct.nii"))

    class _Dialogue:
        @staticmethod
        def choice(*a, **k):
            return None

        @staticmethod
        def warning(*a, **k):
            raise AssertionError("rien a avertir ici")

    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _Dialogue)

    lances = []
    page.check_coreg = lambda: lances.append("review")
    page.ask_what_to_review()

    assert lances == []
    hote.deleteLater()


def test_sans_mri1_la_question_ne_se_pose_pas(app, monkeypatch):
    page, hote = _page_avec_cases(app, _Etat(ct_path="ct.nii"))

    avertis = []

    class _Dialogue:
        @staticmethod
        def choice(*a, **k):
            raise AssertionError("la question ne devrait pas etre posee")

        @staticmethod
        def warning(parent, titre, message):
            avertis.append(message)

    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _Dialogue)

    lances = []
    page.perform_coreg = lambda: lances.append("align")
    page.ask_what_to_align()

    assert lances == []
    assert avertis and "MRI 1" in avertis[0]
    hote.deleteLater()


def test_les_boutons_s_allument_sur_les_images_chargees():
    """Et non sur une case cochee, puisqu'il n'y en a plus a cocher."""
    import inspect

    source = inspect.getsource(FilesPage._update_buttons)

    assert "_loaded_alignable()" in source
    assert "self._selected_modality()" not in source


# ------------------------------------------- ce que le .ui contient


def _texte_ui():
    return io.open(UI, encoding="utf-8").read()


def test_chaque_ligne_d_imagerie_a_ses_trois_points():
    texte = _texte_ui()

    for cle, *_reste in FilesPage.IMAGING_ROWS:
        assert f'name="pill_FilesCoreg_{cle}"' in texte, cle
        for colonne in ("coreg", "save"):
            assert f'name="{colonne}_FilesCoreg_{cle}"' in texte, (cle, colonne)
        assert f'name="review_FilesCoreg_{cle}"' not in texte, cle

    for titre in ("Load", "Coreg", "Save"):
        assert f'name="filesColHead{titre}"' in texte


def test_les_cinq_tuiles_ont_exactement_la_meme_taille():
    """Ce n'est pas un effet de mise en page: les cinq rectangles sont
    fixes a la meme taille, et ils sont cinq a tenir dans la feuille."""
    racine = ET.parse(UI).getroot()
    tailles = []
    for carte in FilesPage.STEP_CARDS:
        widget = next(w for w in racine.iter("widget") if w.get("name") == carte)
        mesure = widget.find("property[@name='minimumSize']/size")
        tailles.append((mesure.find("width").text, mesure.find("height").text))

    assert len(set(tailles)) == 1, tailles

    largeur = int(tailles[0][0])
    feuille = next(w for w in racine.iter("widget") if w.get("name") == "filesSheet")
    large = int(feuille.find("property[@name='minimumSize']/size/width").text)
    assert 5 * largeur + 4 * 14 + 2 * 20 == large


def test_les_cases_de_coregistration_sont_hors_de_la_vue():
    racine = ET.parse(UI).getroot()
    pane = next(w for w in racine.iter("widget") if w.get("name") == "coregHiddenPane")

    assert pane.find("property[@name='visible']/bool").text == "false"
    dedans = {w.get("name") for w in pane.iter("widget")}
    for cle in ("T1", "T2", "CT", "PET", "ictalSPECT", "interictalSPECT", "fMRI"):
        assert f"chk_FilesCoreg_{cle}" in dedans, cle


def test_l_ordre_des_cinq_etapes_est_celui_du_travail():
    texte = _texte_ui()
    places = [(texte.index(f'name="{carte}"'), carte) for carte in FilesPage.STEP_CARDS]

    assert [carte for _i, carte in sorted(places)] == list(FilesPage.STEP_CARDS)

    for numero in range(1, 6):
        assert f'name="filesStepKicker{numero}"' in texte


def test_la_page_tient_dans_la_fenetre_sans_ascenseur(app):
    """Mesure, et non promesse: la feuille est rendue puis mesuree."""
    from PySide6.QtCore import QFile
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtWidgets import QScrollArea, QStackedWidget

    fichier = QFile(str(UI))
    fichier.open(QFile.ReadOnly)
    fenetre = QUiLoader().load(fichier)
    fichier.close()

    pile = fenetre.findChild(QStackedWidget, "stackedWidget")
    pile.setCurrentWidget(fenetre.findChild(QWidget, "pageFiles"))
    fenetre.resize(1600, 900)
    fenetre.show()
    for _ in range(8):
        app.processEvents()

    feuille = fenetre.findChild(QWidget, "filesSheet")
    zone = fenetre.findChild(QScrollArea, "filesWorkflowScrollArea")

    assert feuille.height() <= zone.viewport().height()
    assert feuille.width() <= zone.viewport().width()

    fenetre.hide()
    fenetre.deleteLater()


# ------------------------------------------- la vraie page, en entier


def test_la_vraie_page_se_construit_et_se_rafraichit_sur_ce_ui(app):
    """Le seul test qui monte la page entiere sur le vrai .ui.

    Les autres empruntent une methode a la fois. Celui-ci construit
    FilesPage comme l'application le fait, puis appelle le rafraichissement
    qui peint tout: un widget disparu du .ui s'y verrait tout de suite.
    """
    from neuxelec.pages.files_page import FilesPage as VraiePage
    from neuxelec.state import AppState
    from neuxelec.utils.resources import resource_path
    from neuxelec.utils.ui_loader import load_ui

    ui = load_ui(resource_path("resources/ui/MainWindow.ui"))
    etat = AppState()
    etat.patient_id = "PAT_BB"
    page = VraiePage(ui, etat)

    page._update_buttons()
    assert ui.findChild(QLabel, "filesSummaryLine").text() == "Nothing loaded yet."
    assert ui.findChild(QLabel, "filesStepKicker1").property("current") is True

    etat.t1_path = "t1.nii"
    etat.ct_path = "ct.nii"
    etat.ct_coreg_in_t1 = object()
    etat.ct_validated = True
    etat.pet_path = "pet.nii"
    page._update_buttons()

    assert ui.findChild(QLabel, "filesSummaryLine").text() == (
        "3 of 8 images  ·  1 to coregister  ·  1 to save"
    )
    assert ui.findChild(QLabel, "save_FilesCoreg_CT").property("status") == "todo"
    assert ui.findChild(QLabel, "coreg_FilesCoreg_PET").property("status") == "todo"
    assert ui.findChild(QLabel, "cardCoregistrationSubtitle").text() == "1 to align."
    # Sans objet ne met rien: la case de MRI 1 est vide.
    assert ui.findChild(QLabel, "save_FilesCoreg_T1").text() == ""

    # Les deux boutons ouvrent une fenetre: ils s'allument sur ce qui est
    # charge, sans qu'une seule case soit cochee.
    assert page.btn_perform.isEnabled()
    assert page.btn_check_coreg.isEnabled()

    # La barre ne se montre que pendant un calcul.
    assert not page.coreg_bar.isVisible()

    ui.deleteLater()


def test_la_tuile_qui_calcule_garde_son_message(app):
    """Le piege: un rafraichissement pendant le calcul.

    _update_buttons repeint les cinq lignes grises, et il est appele a
    chaque evenement. Sans garde, la phrase de progression serait
    remplacee par l'etat general une fraction de seconde apres avoir ete
    ecrite, et l'utilisateur ne verrait jamais ou en est son calcul.
    """
    import time

    from neuxelec.pages.files_page import FilesPage as VraiePage
    from neuxelec.state import AppState
    from neuxelec.utils.resources import resource_path
    from neuxelec.utils.ui_loader import load_ui

    ui = load_ui(resource_path("resources/ui/MainWindow.ui"))
    etat = AppState()
    etat.t1_path = "t1.nii"
    etat.t2_path = "t2.nii"
    page = VraiePage(ui, etat)

    page._start_coreg_progress_animation("T2")
    page._coreg_progress_start_time = time.monotonic() - 70
    page._tick_coreg_progress()
    ligne = ui.findChild(QLabel, "cardCoregistrationSubtitle").text()

    page._update_buttons()

    assert ui.findChild(QLabel, "cardCoregistrationSubtitle").text() == ligne
    assert "MRI 2" in ligne
    # La phrase est dans la tuile, le pourcentage dans la barre: une
    # barre de 156 px ne peut pas porter les deux.
    assert page.coreg_bar.format() == "%p%"
    assert page.coreg_bar.value() > 0

    page._coreg_progress_timer.stop()
    ui.deleteLater()


# ------------------------------------------- Review apres un calcul


class _DialogueMuet:
    """Une fenetre de choix qui ne devrait pas s'ouvrir."""

    demandes = 0

    @classmethod
    def choice(cls, *a, **k):
        cls.demandes += 1
        return None

    @staticmethod
    def warning(*a, **k):
        raise AssertionError("rien a avertir ici")


def test_review_ouvre_l_alignement_qui_vient_d_etre_calcule(app, monkeypatch):
    """La question n'a qu'une reponse sensee juste apres un calcul.

    La poser quand meme fait cliquer deux fois au moment precis ou l'on
    attend de voir le resultat.
    """
    page, hote = _page_avec_cases(
        app, _Etat(t1_path="t1.nii", ct_path="ct.nii", pet_path="pet.nii")
    )
    _DialogueMuet.demandes = 0
    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _DialogueMuet)

    lances = []
    page.check_coreg = lambda: lances.append("review")
    page._modalite_a_relire = "PET"
    page.ask_what_to_review()

    assert lances == ["review"]
    assert _DialogueMuet.demandes == 0
    assert page.chk_pet.isChecked()
    hote.deleteLater()


def test_une_fois_relu_la_question_revient(app, monkeypatch):
    """Sinon Review resterait colle a la derniere image alignee, et il
    n'y aurait plus aucun moyen d'en relire une autre."""
    page, hote = _page_avec_cases(
        app, _Etat(t1_path="t1.nii", ct_path="ct.nii", pet_path="pet.nii", pet_validated=True)
    )
    demandes = []

    class _Dialogue:
        @staticmethod
        def choice(parent, titre, question, choix, cancel_primary=False):
            demandes.append([c for c, _l, _p in choix])
            return "CT"

        @staticmethod
        def warning(*a, **k):
            raise AssertionError("rien a avertir ici")

    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _Dialogue)

    lances = []
    page.check_coreg = lambda: lances.append("review")
    page._modalite_a_relire = "PET"
    page.ask_what_to_review()

    assert demandes == [["CT", "PET"]]
    assert lances == ["review"]
    assert page.chk_ct.isChecked()
    hote.deleteLater()


def test_une_image_dechargee_ne_s_ouvre_pas_toute_seule(app, monkeypatch):
    """Le souvenir du dernier calcul survit au dechargement de l'image."""
    page, hote = _page_avec_cases(app, _Etat(t1_path="t1.nii", ct_path="ct.nii"))
    demandes = []

    class _Dialogue:
        @staticmethod
        def choice(parent, titre, question, choix, cancel_primary=False):
            demandes.append([c for c, _l, _p in choix])
            return None

        @staticmethod
        def warning(*a, **k):
            raise AssertionError("rien a avertir ici")

    monkeypatch.setattr(module_page, "NeuXelecMessageDialog", _Dialogue)

    page.check_coreg = lambda: (_ for _ in ()).throw(AssertionError("pas de relecture"))
    page._modalite_a_relire = "PET"  # le PET n'est plus charge
    page.ask_what_to_review()

    assert demandes == [["CT"]]
    hote.deleteLater()


def test_le_calcul_fini_laisse_la_modalite_en_attente():
    """Le lien entre les deux moities: _on_coreg_ok pose le souvenir."""
    import inspect

    source = inspect.getsource(FilesPage._on_coreg_ok)

    assert "self._modalite_a_relire = modality" in source
