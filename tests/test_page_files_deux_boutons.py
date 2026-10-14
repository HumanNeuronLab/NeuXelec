# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La page Files n'a plus que deux boutons: Load et Save.

CE QUI A CHANGE

Quatorze boutons servaient a charger et a enregistrer, plus treize
cellules de chargement par modalite. Il en reste deux, et les gestes
qu'ils ouvrent appellent exactement les memes fonctions qu'avant.

CE QUE CES TESTS PROTEGENT

La fenetre Save n'invente aucun etat: chaque ligne lit le vrai bouton de
la page, celui que _update_buttons active et que _saved_flags marque.
S'il etait recopie ici, la fenetre finirait par dire autre chose que la
page. Les tests verifient donc que la lecture et le clic passent bien
par ce bouton-la.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from neuxelec.ui.save_outputs_dialog import ROWS, SaveOutputsDialog  # noqa: E402

UI = Path(__file__).resolve().parents[1] / "resources" / "ui" / "MainWindow.ui"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Une page reduite a ses boutons Save, dans des etats varies."""

    def __init__(self, app, etats=None):
        self.hote = QWidget()
        defaut = {
            "btn_save_t2": (True, True),
            "btn_save_ct": (True, False),
            "btn_save_pet": (True, False),
            "btn_save_ictal": (True, True),
            "btn_save_interictal": (False, False),
            "btn_save_fmri": (False, False),
            "btn_save_siscom": (True, False),
            "btn_save_brainmask": (False, False),
            "btn_save_plan": (True, True),
        }
        self.clics = []
        for attribut, (actif, enregistre) in (etats or defaut).items():
            b = QPushButton(self.hote)
            b.setEnabled(actif)
            b.setProperty("saved", enregistre)
            b.clicked.connect(lambda _c=False, n=attribut: self.clics.append(n))
            setattr(self, attribut, b)


def _ligne(fenetre, libelle):
    for i, (nom, _attr) in enumerate(ROWS):
        if nom == libelle:
            return fenetre._lignes[i]
    raise AssertionError(f"ligne {libelle} absente")


# ------------------------------------------------- ce que la fenetre montre


def test_les_neuf_sorties_sont_listees(app):
    f = SaveOutputsDialog(_Page(app))

    assert [n for n, _a in ROWS] == [
        "MRI 2",
        "CT post-implant",
        "PET",
        "Ictal SPECT",
        "Interictal SPECT",
        "fMRI",
        "SISCOM",
        "Brain mask",
        "Implantation plan",
    ]
    assert len(f._lignes) == 9
    f.deleteLater()


def test_les_trois_etats_se_distinguent(app):
    """Vert: sur le disque. Orange: relu, pas encore ecrit. Gris: rien a
    enregistrer, et le bouton ne promet rien."""
    f = SaveOutputsDialog(_Page(app))

    assert _ligne(f, "MRI 2")["etat"].text() == "saved"
    assert _ligne(f, "CT post-implant")["etat"].text() == "not saved"
    assert _ligne(f, "fMRI")["etat"].text() == "nothing to save"
    assert not _ligne(f, "fMRI")["bouton"].isEnabled()
    assert _ligne(f, "CT post-implant")["bouton"].isEnabled()
    f.deleteLater()


def test_le_bouton_global_compte_ce_qui_reste(app):
    f = SaveOutputsDialog(_Page(app))

    assert "3" in f.btn_all.text(), f.btn_all.text()
    assert f.btn_all.isEnabled()
    f.deleteLater()


def test_tout_enregistre_le_bouton_global_se_tait(app):
    etats = {attribut: (True, True) for _n, attribut in ROWS if attribut != "btn_save_all"}
    f = SaveOutputsDialog(_Page(app, etats))

    assert f.btn_all.text() == "Nothing left to save"
    assert not f.btn_all.isEnabled()
    f.deleteLater()


# ------------------------------------------------- ce que la fenetre fait


def test_une_ligne_clique_le_vrai_bouton_de_la_page(app):
    """Et non une copie: les regles de ce qui peut etre enregistre restent
    la ou elles sont ecrites."""
    page = _Page(app)
    f = SaveOutputsDialog(page)

    _ligne(f, "CT post-implant")["bouton"].click()

    assert page.clics == ["btn_save_ct"]
    f.deleteLater()


def test_enregistrer_tout_saute_ce_qui_l_est_deja_et_ce_qui_ne_peut_pas(app):
    page = _Page(app)
    f = SaveOutputsDialog(page)

    f.btn_all.click()

    assert set(page.clics) == {"btn_save_ct", "btn_save_pet", "btn_save_siscom"}
    f.deleteLater()


def test_apres_un_enregistrement_la_ligne_se_relit(app):
    """Le bouton de la page porte le nouvel etat: la fenetre doit le
    reprendre, pas garder celui qu'elle avait affiche."""
    page = _Page(app)
    f = SaveOutputsDialog(page)
    page.btn_save_ct.clicked.connect(
        lambda: page.btn_save_ct.setProperty("saved", True)
    )

    _ligne(f, "CT post-implant")["bouton"].click()

    assert _ligne(f, "CT post-implant")["etat"].text() == "saved"
    f.deleteLater()


# ------------------------------------------------- ce que le .ui contient


def test_la_page_n_a_plus_les_quatorze_boutons():
    texte = io.open(UI, encoding="utf-8").read()
    partis = (
        "btn_FilesCoreg_loadImaging",
        "btn_FilesCoreg_loadParcellations",
        "btn_FilesCoreg_loadSurfaces",
        "btn_FilesCoreg_loadPlanning",
        "btn_FilesCoreg_saveT2",
        "btn_FilesCoreg_saveCT",
        "btn_FilesCoreg_savePET",
        "btn_FilesCoreg_saveIctalSPECT",
        "btn_FilesCoreg_saveInterIctalSPECT",
        "btn_FilesCoreg_savefMRI",
        "btn_FilesCoreg_savePlan",
        "btn_FilesCoreg_saveAll",
        "btn_FilesCoreg_SaveBrainmask",
        "btn_FilesCoreg_SaveSISCOM",
        "cardFilesToLoad",
    )
    restants = [n for n in partis if f'name="{n}"' in texte]

    assert not restants, f"encore dans le .ui: {restants}"


def test_les_deux_boutons_sont_la():
    texte = io.open(UI, encoding="utf-8").read()

    for nom in ("btn_FilesCoreg_load", "btn_FilesCoreg_save"):
        assert f'name="{nom}"' in texte


def test_le_masque_se_charge_par_le_bouton_load():
    """Le bouton Load a mask faisait double emploi: le chargement des
    surfaces propose deja le role Brain mask. Ce test tient les deux
    bouts, l'entree du menu et le role offert par la fonction."""
    import inspect

    from neuxelec.pages.files_page import FilesPage

    choix = inspect.getsource(FilesPage.ask_what_to_load)
    assert "Surfaces and brain mask" in choix

    surfaces = inspect.getsource(FilesPage.load_surfaces_bundle)
    assert '"BRAINMASK"' in surfaces

    texte = io.open(UI, encoding="utf-8").read()
    assert 'name="btn_FilesCoreg_loadBrainMask"' not in texte


def test_le_numero_est_sur_la_tuile_et_le_titre_dit_le_geste():
    """Le titre criait STEP 2 - PREPARE BRAIN MASK. Le numero est porte
    par la tuile, et le titre n'a plus qu'a nommer ce qu'on y fait."""
    texte = io.open(UI, encoding="utf-8").read()

    assert "PREPARE BRAIN MASK" not in texte
    for numero in range(1, 6):
        assert f"<string>STEP {numero}</string>" in texte

    for titre in ("Load data", "Brain mask", "Align on MRI 1", "SISCOM map", "Save outputs"):
        assert f"<string>{titre}</string>" in texte


def test_tout_l_habillage_de_la_page_tient_dans_un_bloc():
    """Trois blocs decrivaient les memes titres, avec trois tailles. Ce
    test tient le nombre a un: celui d'en bas de la feuille de style."""
    texte = io.open(UI, encoding="utf-8").read()

    assert texte.count("Page Files: la console") == 1
    assert "QWidget#pageFiles QLabel#cardBulkImportTitle" not in texte
    assert "QWidget#pageFiles QLabel#cardFilesToLoadTitle" not in texte

    i = texte.index("Page Files: la console")
    regles = texte[i:]
    for regle in (
        "QFrame#filesSheet",
        'QWidget#pageFiles QFrame[filesTile="true"]',
        'QWidget#pageFiles QLabel[uiRole="statusMark"]',
        'QWidget#pageFiles QLabel[uiRole="statusColHead"]',
    ):
        assert regle in regles, regle

# ------------------------------------------------- ce que les contours disent


def test_le_contour_rose_dit_enregistre_et_non_enregistrable(app):
    """Sur la page, le contour rose disait qu'un fichier existe sur le
    disque. Il dit la meme chose ici."""
    f = SaveOutputsDialog(_Page(app))

    ecrit = _ligne(f, "MRI 2")["bouton"].styleSheet()
    pas_ecrit = _ligne(f, "CT post-implant")["bouton"].styleSheet()

    assert "#FF487D" in ecrit
    assert "#FF487D" not in pas_ecrit
    f.deleteLater()


def test_la_question_du_chargement_ne_recommande_rien():
    """Quatre reponses qui se valent: aucune n'est mise en avant, et c'est
    la sortie qui porte le contour."""
    import inspect

    from neuxelec.pages.files_page import FilesPage

    texte = inspect.getsource(FilesPage.ask_what_to_load)

    assert texte.count("False),") == 4
    assert "cancel_primary=True" in texte


def test_la_fenetre_de_choix_sait_marquer_son_annulation():
    import inspect

    from neuxelec.ui.neuxelec_message_dialog import NeuXelecMessageDialog

    assert "cancel_primary" in inspect.signature(NeuXelecMessageDialog.choice).parameters
