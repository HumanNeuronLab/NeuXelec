# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les deux bascules d'electrodes de la vue 3D doivent montrer leur etat.

Une bascule qui ne change pas d'aspect quand on clique dessus n'est pas une
bascule : rien ne dit si l'affichage est actif. Ces tests dessinent le
bouton dans les deux etats et regardent les pixels, parce que c'est la
seule facon de verifier qu'une feuille de style s'applique vraiment. Une
regle peut etre presente dans le fichier et n'avoir aucun effet, masquee
par une autre plus specifique.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile  # noqa: E402
from PySide6.QtUiTools import QUiLoader  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from neuxelec.utils.resources import resource_path  # noqa: E402

#: Le rose d'accent de NeuXelec.
ACCENT = (0xFF, 0x48, 0x7D)

BASCULES = ["btn_3d_elecShaft", "btn_3d_microTetrodes"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def fenetre(app):
    chemin = resource_path("resources/ui/MainWindow.ui")
    f = QFile(str(chemin))
    assert f.open(QFile.ReadOnly), "MainWindow.ui illisible"
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    assert w is not None, "MainWindow.ui ne se charge pas"
    return w


def _couleurs(bouton: QPushButton, coche: bool) -> set[tuple[int, int, int]]:
    """Les couleurs presentes dans le bouton, dessine dans cet etat."""
    bouton.setCheckable(True)
    bouton.setChecked(coche)
    bouton.resize(140, 38)
    bouton.ensurePolished()
    image = bouton.grab().toImage()
    return {
        tuple(image.pixelColor(x, y).getRgb()[:3])
        for y in range(image.height())
        for x in range(image.width())
    }


@pytest.mark.parametrize("nom", BASCULES)
def test_la_bascule_existe_dans_l_interface(fenetre, nom):
    assert fenetre.findChild(QPushButton, nom) is not None


@pytest.mark.parametrize("nom", BASCULES)
def test_le_contour_rose_apparait_quand_c_est_coche(fenetre, nom):
    bouton = fenetre.findChild(QPushButton, nom)
    assert ACCENT in _couleurs(bouton, True), "pas de contour rose une fois coche"


@pytest.mark.parametrize("nom", BASCULES)
def test_le_contour_rose_disparait_quand_c_est_decoche(fenetre, nom):
    bouton = fenetre.findChild(QPushButton, nom)
    assert ACCENT not in _couleurs(bouton, False), "contour rose alors que decoche"


@pytest.mark.parametrize("nom", BASCULES)
def test_les_deux_etats_ne_se_ressemblent_pas(fenetre, nom):
    """Au-dela du contour : le fond change aussi, donc l'etat se lit de loin."""
    bouton = fenetre.findChild(QPushButton, nom)
    assert _couleurs(bouton, True) != _couleurs(bouton, False)
