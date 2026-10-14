# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le clic droit ne mene plus au visualiseur EEG.

POURQUOI UNE PORTE FERMEE ET NON UN CODE RETIRE

Le visualiseur existe et fonctionne, mais il n'est pas pret a etre
livre : la version distribuee ne doit pas y mener. Tout le chemin
reste en place, de son ouverture a son appariement de voies ; seule
l'entree du menu disparait, derriere un mot qui la rouvre.

CE QUI RESTE

"Re-match EEG channels..." ne parait que lorsqu'un appariement existe
deja, donc jamais sur une installation neuve. Elle n'a pas ete
touchee.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

from neuxelec.ui import context_menus  # noqa: E402

VISUALISEUR = "Open EEG viewer"
REAPPARIER = "Re-match EEG channels..."


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def menu_capture(app, monkeypatch):
    """Rendre le menu construit, sans jamais l'ouvrir."""
    captures: list[QMenu] = []
    vrai = context_menus.make_base_menu

    def _capturer():
        menu = vrai()
        # Sur l'instance : PySide ne laisse pas remplacer exec sur la
        # classe, et l'ouvrir pour de bon bloquerait la suite.
        menu.exec = lambda *a, **k: None
        captures.append(menu)
        return menu

    monkeypatch.setattr(context_menus, "make_base_menu", _capturer)
    return captures


def _entrees(captures):
    assert captures, "aucun menu n'a ete construit"
    return [a.text() for a in captures[-1].actions() if a.text()]


def _ouvrir(kind="electrode", page="page3DView", **extra):
    options = dict(kind=kind, current_page=page, eeg_available=True)
    options.update(extra)
    return context_menus.exec_electrode_tree_menu(None, **options)


# ------------------------------------------------ l'entree a disparu


@pytest.mark.parametrize("page", ["page3DView", "pageObliqueSlices", "pageReconstruction"])
@pytest.mark.parametrize("kind", ["electrode", "contact"])
def test_le_visualiseur_n_est_plus_propose(menu_capture, page, kind):
    """Meme quand un EEG est disponible, ce qui etait la seule
    condition pour le proposer."""
    _ouvrir(kind=kind, page=page)
    assert VISUALISEUR not in _entrees(menu_capture)


def test_il_ne_parait_pas_non_plus_avec_un_appariement_existant(menu_capture):
    _ouvrir(eeg_already_mapped=True)
    assert VISUALISEUR not in _entrees(menu_capture)


# ------------------------------------------- le reste est intact


def test_le_reappariement_part_avec_le_visualiseur(menu_capture):
    """Il ne sert qu'a le nourrir : seul, il ne mene nulle part."""
    _ouvrir(eeg_already_mapped=True)
    assert REAPPARIER not in _entrees(menu_capture)


def test_il_revient_avec_lui(menu_capture, monkeypatch):
    monkeypatch.setattr(context_menus, "EEG_VIEWER_IN_MENU", True)
    _ouvrir(eeg_already_mapped=True)
    entrees = _entrees(menu_capture)
    assert VISUALISEUR in entrees
    assert REAPPARIER in entrees


def test_le_reappariement_ne_parait_pas_sans_appariement(menu_capture):
    _ouvrir(eeg_already_mapped=False)
    assert REAPPARIER not in _entrees(menu_capture)


def test_les_autres_entrees_sont_la(menu_capture):
    """Fermer une porte ne doit pas en fermer d'autres."""
    _ouvrir(kind="electrode", page="page3DView", editable=True)
    entrees = _entrees(menu_capture)
    assert any("contact labels" in e for e in entrees), entrees
    assert any("Delete" in e for e in entrees), entrees


def test_le_menu_des_contacts_garde_ses_entrees(menu_capture):
    _ouvrir(kind="contact", page="page3DView")
    entrees = _entrees(menu_capture)
    assert any("slice" in e.lower() for e in entrees), entrees


# ------------------------------------------- la porte se rouvre


def test_le_mot_qui_rouvre_la_porte(menu_capture, monkeypatch):
    """Le visualiseur n'est pas retire : il attend."""
    monkeypatch.setattr(context_menus, "EEG_VIEWER_IN_MENU", True)
    _ouvrir()
    assert VISUALISEUR in _entrees(menu_capture)


def test_la_porte_est_fermee_par_defaut():
    assert context_menus.EEG_VIEWER_IN_MENU is False


def test_le_visualiseur_lui_meme_est_toujours_la():
    """Seule l'entree du menu part, pas la fonctionnalite."""
    from neuxelec.controllers.eeg_session import open_eeg_viewer

    assert callable(open_eeg_viewer)
