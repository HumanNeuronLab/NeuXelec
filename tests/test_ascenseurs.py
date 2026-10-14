# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les ascenseurs de NeuXelec, decrits a un seul endroit.

CE QUI A CHANGE

Il y avait trois dessins d'ascenseur dans le meme projet: une capsule
grise bordee de rose sur les coupes, un degrade orange dans le guide et
la liste des marqueurs, un filet sans fleches dans les fenetres. Lequel
on voyait dependait de l'endroit ou la fenetre etait trop petite.

Le dessin des coupes de la page Reconstruction sert maintenant partout,
et il est ecrit dans un seul fichier, pose sur l'application entiere.

CE QUE CES TESTS PROTEGENT

La regle est simple et facile a casser sans le vouloir: personne d'autre
ne decrit d'ascenseur. Une feuille de style plus proche du widget gagne
sur celle de l'application, donc une seule regle recopiee dans une
fenetre suffirait a ramener un deuxieme dessin, et il ne se verrait que
le jour ou cette fenetre serait trop petite.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.ui.scrollbars import SCROLLBARS_QSS, apply_scrollbars  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "src" / "neuxelec"
UI = RACINE / "resources" / "ui" / "MainWindow.ui"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_personne_d_autre_ne_decrit_d_ascenseur():
    """Un selecteur QScrollBar hors du fichier commun ramenerait un
    deuxieme dessin, visible seulement dans une fenetre trop petite."""
    coupables = []

    for chemin in sorted(SOURCE.rglob("*.py")):
        if chemin.name == "scrollbars.py":
            continue
        texte = io.open(chemin, encoding="utf-8").read()
        for numero, ligne in enumerate(texte.split("\n"), 1):
            if "QScrollBar" not in ligne:
                continue
            # Le code a le droit de nommer la classe: un import, un
            # findChild, une annotation. C'est le selecteur qui est
            # interdit, et un selecteur finit par une accolade ou une
            # virgule de liste.
            nu = ligne.strip()
            if re.search(r"QScrollBar[^,]*\{|QScrollBar::|QScrollBar:[a-z]+\s*,?\s*$", nu):
                coupables.append(f"{chemin.relative_to(RACINE)}:{numero}: {nu[:60]}")

    assert coupables == [], coupables


def test_le_fichier_d_interface_n_en_decrit_plus_aucun():
    """La fenetre en declare toujours comme widgets, les barres de coupe
    par exemple. C'est sa feuille de style qui ne doit plus en parler."""
    texte = io.open(UI, encoding="utf-8").read()
    debut = texte.index('<string notr="true">')
    feuille = texte[debut : texte.index("</string>", debut)]

    assert "QScrollBar" not in feuille


def test_l_application_les_pose_au_demarrage():
    texte = io.open(SOURCE / "app.py", encoding="utf-8").read()

    assert "apply_scrollbars(app)" in texte


def test_les_deux_sens_et_les_quatre_fleches_sont_decrits():
    for regle in (
        "QScrollBar:vertical",
        "QScrollBar:horizontal",
        "QScrollBar::handle:vertical",
        "QScrollBar::handle:horizontal",
        "QScrollBar::up-arrow:vertical",
        "QScrollBar::down-arrow:vertical",
        "QScrollBar::left-arrow:horizontal",
        "QScrollBar::right-arrow:horizontal",
    ):
        assert regle in SCROLLBARS_QSS, regle


@pytest.mark.parametrize(
    "image", ["spin_up.svg", "spin_down.svg", "spin_left.svg", "spin_right.svg"]
)
def test_les_fleches_existent(image):
    """Une image manquante ne fait pas d'erreur: la fleche disparait, et
    le bout de la barre devient un carre muet."""
    assert f"resources/images/{image}" in SCROLLBARS_QSS
    assert (RACINE / "resources" / "images" / image).exists()


def test_le_dessin_est_celui_des_coupes():
    """Les trois nombres qui font ce dessin, et que les coupes avaient:
    la piste de 16 px, les deux bouts de 18 px, la poignee bordee de
    rose."""
    assert "width: 16px;" in SCROLLBARS_QSS
    assert "padding: 18px 0px 18px 0px;" in SCROLLBARS_QSS
    assert "border: 1px solid #FF487D;" in SCROLLBARS_QSS


def test_les_poser_deux_fois_ne_les_ecrit_pas_deux_fois(app):
    avant = app.styleSheet()
    try:
        app.setStyleSheet("")
        apply_scrollbars(app)
        une_fois = app.styleSheet()
        apply_scrollbars(app)

        assert app.styleSheet() == une_fois
        assert une_fois.count("QScrollBar::handle:vertical {") == 1
    finally:
        app.setStyleSheet(avant)


def test_une_feuille_deja_posee_n_est_pas_perdue(app):
    avant = app.styleSheet()
    try:
        app.setStyleSheet("QLabel { color: #ABCDEF; }")
        apply_scrollbars(app)

        assert "QLabel { color: #ABCDEF; }" in app.styleSheet()
        assert "QScrollBar:vertical" in app.styleSheet()
    finally:
        app.setStyleSheet(avant)
