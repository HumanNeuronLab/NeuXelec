"""Ce que l'utilisateur lit doit dire MRI 1 et MRI 2, jamais T1 et T2.

Les cles internes restent T1 et T2 : les renommer casserait les projets deja
enregistres, les noms de fichiers et les termes BIDS, ou T1w est le mot juste.
Seul le texte affiche est traduit, par _display_modality_name.

Le defaut corrige : la fenetre de revue et la console manuelle recevaient la
cle brute, de sorte qu'un utilisateur venant de charger MRI 2 s'entendait
demander d'ajuster T2.
"""

from __future__ import annotations

import inspect
import io
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.files_page import FilesPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    _display_modality_name = FilesPage._display_modality_name


@pytest.mark.parametrize(
    "cle, attendu",
    [("T1", "MRI 1"), ("T2", "MRI 2"), ("CT", "CT"), ("PET", "PET"), ("fMRI", "fMRI")],
)
def test_la_traduction_des_noms(app, cle, attendu):
    assert _Page()._display_modality_name(cle) == attendu


def test_la_console_manuelle_recoit_un_nom_traduit():
    """C'est ce nom que la console imprime dans son titre, son sous-titre et
    une demi-douzaine d'etiquettes."""
    source = io.open(
        "src/neuxelec/pages/files_page.py", encoding="utf-8-sig"
    ).read()
    assert "moving_name = self._display_modality_name(modality)" in source
    assert "moving_name = modality\n" not in source


def test_aucun_message_n_affiche_plus_la_cle_brute():
    """Un f-string qui interpole {modality} montre T2 a l'ecran.

    La seule exception toleree construit un nom de fichier, ou la cle est au
    contraire ce qu'il faut : un fichier nomme "MRI 2_..." serait pire.
    """
    source = io.open(
        "src/neuxelec/pages/files_page.py", encoding="utf-8-sig"
    ).read()
    coupables = []
    for numero, ligne in enumerate(source.split("\n"), 1):
        if "{modality}" not in ligne:
            continue
        if ".mat" in ligne or ".nii" in ligne or "filename" in ligne.lower():
            continue  # un nom de fichier garde la cle
        coupables.append((numero, ligne.strip()[:80]))
    assert coupables == [], coupables


def test_le_fichier_d_interface_ne_dit_jamais_T1_ni_T2():
    """Les etiquettes de la page de coregistration."""
    source = io.open("resources/ui/MainWindow.ui", encoding="utf-8").read()
    visibles = re.findall(r"<string>([^<]*)</string>", source)
    fautifs = [t for t in visibles if re.search(r"\bT ?[12]\b", t)]
    assert fautifs == [], fautifs
