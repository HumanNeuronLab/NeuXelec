# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aucun texte des deux fenetres ne doit rester en anglais.

POURQUOI UN TEST QUI LIT LE CODE

Raccourcir une phrase change sa cle. Le dictionnaire, lui, ne le sait
pas: la traduction tombe en silence et la fenetre repasse a l'anglais a
cet endroit precis, ce qui ne se voit qu'a l'oeil, sur une capture, dans
la bonne langue. C'est arrive trois fois en une seule passe de mise en
forme.

Ce test lit donc le source des deux fenetres, y releve tout ce qui est
donne a traduire, et exige que le dictionnaire le connaisse.

CE QU'IL NE RELEVE PAS

Les textes construits a l'execution (le nom d'une electrode, ce que
l'utilisateur a tape) n'ont rien a faire dans un dictionnaire.
"""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest

from neuxelec.utils import i18n

#: Les fenetres qui parlent les deux langues.
FENETRES = (
    "src/neuxelec/ui/stimulation_dialog.py",
    "src/neuxelec/ui/stimulation_results_dialog.py",
)

#: Les fonctions dont le premier argument est montre a l'utilisateur.
TRADUITES = {"tr", "field", "explain", "section"}

#: field(label, widget, hint, unit): l'indice aussi est montre.
INDICE_EN_TROISIEME = {"field"}

RACINE = Path(__file__).resolve().parents[1]


def _nom_appele(noeud: ast.Call) -> str:
    cible = noeud.func

    if isinstance(cible, ast.Name):
        return cible.id

    if isinstance(cible, ast.Attribute):
        return cible.attr

    return ""


def _texte(noeud) -> str | None:
    """La chaine litterale d'un argument, concatenations comprises."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value

    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Add):
        gauche = _texte(noeud.left)
        droite = _texte(noeud.right)

        if gauche is not None and droite is not None:
            return gauche + droite

    return None


def _textes_a_traduire(chemin: Path) -> set[str]:
    arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
    trouves: set[str] = set()

    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue

        nom = _nom_appele(noeud)

        if nom not in TRADUITES:
            continue

        positions = [0]

        if nom in INDICE_EN_TROISIEME:
            positions.append(2)

        for index in positions:
            if index >= len(noeud.args):
                continue

            texte = _texte(noeud.args[index])

            if texte:
                trouves.add(texte)

        for mot in noeud.keywords:
            if mot.arg in ("hint",):
                texte = _texte(mot.value)

                if texte:
                    trouves.add(texte)

    return trouves


@pytest.mark.parametrize("fenetre", FENETRES)
def test_tout_le_texte_de_la_fenetre_est_traduit(fenetre):
    manquants = sorted(
        texte
        for texte in _textes_a_traduire(RACINE / fenetre)
        if texte and texte not in i18n.FR
    )
    assert manquants == [], manquants


def test_le_releve_trouve_bien_des_textes():
    """Un relevé vide ferait passer le test sans rien verifier."""
    for fenetre in FENETRES:
        assert len(_textes_a_traduire(RACINE / fenetre)) > 20


def test_les_titres_de_la_fiche_sont_traduits():
    """Ils viennent du modele, pas des fenetres."""
    from neuxelec.utils import stimulation as st

    carte = st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        anatomy=["A1 x"],
        threshold_ma=1.0,
        at_ad_threshold=True,
        behavioural_state="awake",
        asm="reduced",
        time_since_last_seizure="2 days",
        task="counting",
        events=["after_discharges"],
        habitual="identical",
        reproducibility="reproduced",
        ad_location="A1-A2",
        ad_remote=True,
        ad_evolution="spread",
        aborted=True,
        responses=[st.new_response("motor", "Clonic jerks")],
        notes="note",
        operator="JV",
    )

    manquants = [
        label for label, _valeur in st.card_fields(carte) if label not in i18n.FR
    ]
    assert manquants == []
