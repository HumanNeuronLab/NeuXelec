# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ce que NeuXelec demande au clic sur Perform coreg.

Deux questions, dans cet ordre, et la premiere est presque toujours sautee.

Les espaces coincident peut-etre deja : une carte statistique et l'anatomie
dont elle sort partagent leur grille. Estimer une transformation entre les deux
a rendu, en mesure, une rotation de 56 degres et plus de 30 mm d'erreur au bord
du cerveau, sans aucune alerte.

La transformation existe peut-etre deja : plusieurs modalites d'un meme examen
partagent une position, donc la matrice estimee pour la premiere sert aux
autres. L'appliquer coute une seconde au lieu de trois minutes, et donne
exactement le meme resultat a chaque fois.

POURQUOI choice() ET NON question()

question() rend un booleen, donc fermer la fenetre y est indiscernable d'un
clic sur le bouton de refus : la premiere question se fermait, et la seconde
s'ouvrait aussitot. choice() rend None quand la fenetre est fermee, ce qui
laisse distinguer "non" de "laisse-moi tranquille".
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

import neuxelec.pages.files_page as page_module  # noqa: E402
from neuxelec.pages.files_page import FilesPage  # noqa: E402
from neuxelec.ui.neuxelec_message_dialog import NeuXelecMessageDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Les quatre choses que la decision consulte."""

    def __init__(self, fichier=None):
        self.fichier = fichier

    def _display_modality_name(self, modality):
        return modality

    def _dialog_parent(self):
        return None

    def _ask_existing_matrix(self):
        return self.fichier

    _coreg_choice_before_starting = FilesPage._coreg_choice_before_starting


@pytest.fixture
def scene(monkeypatch):
    def preparer(memes_espaces: bool, reponses: list, fichier=None):
        monkeypatch.setattr(page_module, "same_physical_space",
                            lambda a, b: memes_espaces, raising=False)
        import neuxelec.coregistration as cg
        monkeypatch.setattr(cg, "same_physical_space", lambda a, b: memes_espaces)
        restantes = list(reponses)
        monkeypatch.setattr(NeuXelecMessageDialog, "choice",
                            staticmethod(lambda *a, **k: restantes.pop(0)))
        return _Page(fichier)._coreg_choice_before_starting("CT", "a", "b")
    return preparer


def test_memes_espaces_et_on_garde_telle_quelle(app, scene):
    """Le cas qui evite les 30 mm d'erreur silencieuse."""
    assert scene(True, ["identity"]) == ("identity", None)


def test_memes_espaces_mais_on_insiste(app, scene):
    """L'utilisateur reste maitre : il peut passer outre, puis on lui demande
    s'il a deja une matrice."""
    assert scene(True, ["estimate", "estimate"]) == ("estimate", None)


def test_memes_espaces_on_insiste_et_on_fournit_une_matrice(app, scene):
    assert scene(True, ["estimate", "apply"], fichier="C:/essai/t.mat") == (
        "apply", "C:/essai/t.mat")


def test_fermer_la_premiere_fenetre_n_ouvre_pas_la_seconde(app, scene):
    """Fermer, c'est renoncer. Une seule reponse est fournie a la scene : si
    la seconde question s'ouvrait, pop() sur une liste vide leverait."""
    assert scene(True, [None]) is None


def test_espaces_differents_aucune_question_sur_l_espace(app, scene):
    """Une seule question dans le cas courant, pas deux."""
    assert scene(False, ["estimate"]) == ("estimate", None)


def test_une_matrice_fournie_est_retournee(app, scene):
    assert scene(False, ["apply"], fichier="C:/essai/transfo.mat") == (
        "apply", "C:/essai/transfo.mat")


def test_fermer_la_question_de_la_matrice_annule_tout(app, scene):
    assert scene(False, [None]) is None


def test_annuler_le_choix_du_fichier_annule_tout(app, scene):
    """Et ne retombe pas en douce sur trois minutes d'estimation."""
    assert scene(False, ["apply"], fichier=None) is None


def test_fournir_une_matrice_n_ouvre_pas_la_question_de_sauvegarde():
    """Une matrice qui existe deja n'a ni a etre sauvee, ni a etre demandee."""
    import inspect

    source = inspect.getsource(FilesPage._perform_coreg) \
        if hasattr(FilesPage, "_perform_coreg") else ""
    if not source:
        for nom, membre in vars(FilesPage).items():
            if callable(membre) and "_coreg_choice_before_starting" in str(
                    getattr(membre, "__code__", None) and membre.__code__.co_names):
                source = inspect.getsource(membre)
                break
    assert "if existing_matrix:" in source
    assert "self._pending_matrix_save_path = None" in source
