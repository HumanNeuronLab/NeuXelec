# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""L'encadre ELECTRODE PARAMETERS tient sans defiler.

LE DEFAUT

Douze rangees pour la hauteur de huit : il fallait defiler pour
atteindre Estimate Contacts. Mesure, l'encadre reclamait 483 px pour
334 disponibles sur une fenetre de 1330x940.

CE QUI A CHANGE

Le nom et l'hemisphere partagent une ligne, le nombre de contacts et
leur ecartement aussi. Les deux libelles de section restent : ce sont
eux qui separent les compartiments. Les champs et les deux boutons
Pick passent de 35 a 26 px de haut, et le rembourrage par defaut de Qt
est ramene a 4.

LE PIEGE DE CET ENCADRE

Il n'a que 341 px de large. Gagner en hauteur en elargissant les
rangees troquerait un defilement vertical contre un horizontal, qui
cache le bord droit des champs sans rien dire. Ces tests mesurent donc
les deux sens.

Et Qt ajoute le rembourrage et la bordure **par-dessus** min-width :
un champ a min-width 68 et padding 8 occupe 86 px reels. C'est cette
largeur reelle qui compte, pas le chiffre de la feuille.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Sans polices, les metriques de Qt sont celles d'un repli et une
# mesure en pixels ne dit rien de ce que l'utilisateur verra. On
# pointe donc vers les polices du systeme quand elles existent, avant
# toute QApplication, et les mesures se sautent si elles manquent.
if os.path.isdir("C:/Windows/Fonts"):
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from neuxelec.utils.resources import resource_path  # noqa: E402
from neuxelec.utils.ui_loader import load_ui  # noqa: E402

#: Les tailles de fenetre ou l'encadre doit tenir.
TAILLES = [(1330, 940), (1600, 900), (1920, 1080)]


def _exiger_des_polices() -> None:
    """Sauter la mesure quand Qt n'a aucune police.

    La verification est **tardive**, et non une marque posee a
    l'import : QFontDatabase a besoin d'une QApplication, et
    l'interroger avant la fait mourir le processus sans un mot.
    """
    try:
        familles = QFontDatabase.families()
    except Exception:
        familles = []
    if not familles:
        pytest.skip("aucune police installee : une mesure en pixels ne dirait rien")

#: Tout ce que le code cherche dans cet encadre. Reagencer ne doit
#: rien perdre : un widget absent ne leve rien, il cesse d'agir.
FONCTIONNELS = (
    (QLineEdit, "editReco_nameElec"),
    (QCheckBox, "chkReco_hemiLeft"),
    (QCheckBox, "chkReco_hemiRight"),
    (QComboBox, "comboReco_electrodeRef"),
    (QLineEdit, "editReco_nbContacts"),
    (QLineEdit, "editReco_interContact"),
    (QPushButton, "btnReco_pickDeepest"),
    (QLineEdit, "editReco_deepestX"),
    (QLineEdit, "editReco_deepestY"),
    (QLineEdit, "editReco_deepestZ"),
    (QPushButton, "btnReco_pickSecond"),
    (QLineEdit, "editReco_secondtX"),
    (QLineEdit, "editReco_secondtY"),
    (QLineEdit, "editReco_secondtZ"),
    (QCheckBox, "chkReco_snapping"),
    (QCheckBox, "chkReco_localMax"),
    (QPushButton, "btnReco_estimate"),
    (QPushButton, "btnReco_newElectrode"),
)


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont("Segoe UI", 9))
    return app


@pytest.fixture(scope="module")
def fenetre(app):
    w = load_ui(resource_path("resources/ui/MainWindow.ui"))
    page = w.findChild(QWidget, "pageReconstruction")
    assert page is not None
    for pile in w.findChildren(QStackedWidget):
        if pile.indexOf(page) >= 0:
            pile.setCurrentWidget(page)
    w.show()
    return w


def _zone(fenetre, taille):
    fenetre.resize(*taille)
    QApplication.processEvents()
    QApplication.processEvents()
    return fenetre.findChild(QScrollArea, "scrollArea")


# ------------------------------------------------- rien n'est perdu


@pytest.mark.parametrize("classe,nom", FONCTIONNELS)
def test_chaque_controle_survit_au_reagencement(fenetre, classe, nom):
    assert fenetre.findChild(classe, nom) is not None, nom


@pytest.mark.parametrize("classe,nom", FONCTIONNELS)
def test_aucun_controle_n_a_ete_duplique(fenetre, classe, nom):
    trouves = [x for x in fenetre.findChildren(classe) if x.objectName() == nom]
    assert len(trouves) == 1, "%s existe en %d exemplaires" % (nom, len(trouves))


# ------------------------------------------------- l'encadre tient


@pytest.mark.parametrize("taille", TAILLES)
def test_il_tient_en_hauteur(fenetre, taille):
    """Le defaut signale : il fallait defiler pour voir Estimate."""
    _exiger_des_polices()
    zone = _zone(fenetre, taille)
    demande = zone.widget().sizeHint().height()
    offert = zone.viewport().height()
    assert demande <= offert, "il manque %d px" % (demande - offert)


@pytest.mark.parametrize("taille", TAILLES)
def test_il_tient_en_largeur(fenetre, taille):
    """Sinon on aurait troque un defilement contre l'autre."""
    _exiger_des_polices()
    zone = _zone(fenetre, taille)
    demande = zone.widget().minimumSizeHint().width()
    offert = zone.viewport().width()
    assert demande <= offert, "il deborde de %d px" % (demande - offert)


def test_il_reste_de_la_marge_et_pas_un_pixel(fenetre):
    """Une police un peu plus large ailleurs ramenerait la barre."""
    _exiger_des_polices()
    zone = _zone(fenetre, (1330, 940))
    contenu = zone.widget()
    assert zone.viewport().width() - contenu.minimumSizeHint().width() >= 15
    assert zone.viewport().height() - contenu.sizeHint().height() >= 15


# ------------------------------------------- les rangees fondues


def _rangee_de(fenetre, nom_widget):
    """La disposition horizontale qui contient ce widget."""
    cible = fenetre.findChild(QWidget, nom_widget)
    for lay in fenetre.findChildren(QHBoxLayout):
        if lay.indexOf(cible) >= 0:
            return lay
    return None


def test_le_nom_et_l_hemisphere_partagent_une_ligne(fenetre):
    """C'est la demande."""
    rangee = _rangee_de(fenetre, "editReco_nameElec")
    assert rangee is not None
    for nom in ("chkReco_hemiLeft", "chkReco_hemiRight"):
        assert rangee.indexOf(fenetre.findChild(QCheckBox, nom)) >= 0, nom


def test_le_nombre_de_contacts_et_l_ecartement_partagent_une_ligne(fenetre):
    rangee = _rangee_de(fenetre, "editReco_nbContacts")
    assert rangee is not None
    assert rangee.indexOf(fenetre.findChild(QLineEdit, "editReco_interContact")) >= 0


@pytest.mark.parametrize(
    "profond,superficiel",
    [
        ("btnReco_pickDeepest", "editReco_deepestZ"),
        ("btnReco_pickSecond", "editReco_secondtZ"),
    ],
)
def test_chaque_pick_reste_avec_ses_trois_coordonnees(fenetre, profond, superficiel):
    rangee = _rangee_de(fenetre, profond)
    assert rangee is not None
    assert rangee.indexOf(fenetre.findChild(QLineEdit, superficiel)) >= 0


# ------------------------------------- les champs restent lisibles


@pytest.mark.parametrize(
    "nom",
    ["editReco_deepestX", "editReco_deepestY", "editReco_deepestZ"],
)
def test_une_coordonnee_longue_n_est_pas_coupee(fenetre, nom):
    """Resserrer un champ ne doit pas rogner ce qu'on y lit."""
    _exiger_des_polices()
    _zone(fenetre, (1330, 940))
    champ = fenetre.findChild(QLineEdit, nom)
    champ.setText("-131.45")
    QApplication.processEvents()

    largeur_texte = QFontMetrics(champ.font()).horizontalAdvance("-131.45")
    assert champ.width() >= largeur_texte + 8, (champ.width(), largeur_texte)


def test_les_champs_gardent_une_hauteur_lisible(fenetre):
    """26 px laissent passer le texte ; moins le couperait."""
    _exiger_des_polices()
    _zone(fenetre, (1330, 940))
    for _classe, nom in FONCTIONNELS:
        champ = fenetre.findChild(QLineEdit, nom)
        if champ is None:
            continue
        hauteur_texte = QFontMetrics(champ.font()).height()
        assert champ.height() >= hauteur_texte + 6, (nom, champ.height())
