"""Une boite de message s'elargit pour ses boutons.

LE DEFAUT SIGNALE

Le choix du repere de parcellation affichait "lative space (patient
MRI 1" et "space (MNI152NLin2009cA" : les deux libelles etaient
rognes.

La taille de depart est calculee dans __init__, avant que le moindre
bouton existe, puisqu'ils sont ajoutes ensuite par _add_button et
_add_choice_button. La fenetre restait donc a 570 px quoi qu'ils
demandent.

Elle s'elargit maintenant a l'affichage, quand ils existent. Elargir
plutot que raccourcir les libelles : un bouton dit ce qu'il fait, et
c'est la fenetre qui doit s'y plier.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.path.isdir("C:/Windows/Fonts"):
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from PySide6.QtGui import QFontDatabase, QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from neuxelec.pages.files_page import FilesPage  # noqa: E402
from neuxelec.ui.neuxelec_message_dialog import NeuXelecMessageDialog  # noqa: E402

#: Le libelle exact qui etait coupe.
LONG = "MNI space (MNI152NLin2009cAsym)"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _exiger_des_polices():
    """Sans police, une largeur de texte ne veut rien dire.

    Tardif et non une marque a l'import : QFontDatabase a besoin d'une
    QApplication, et l'interroger avant tue le processus sans un mot.
    """
    try:
        familles = QFontDatabase.families()
    except Exception:
        familles = []
    if not familles:
        pytest.skip("aucune police installee")


def _boite(libelles, message="Une question."):
    d = NeuXelecMessageDialog("Titre", message, parent=None, kind="question")
    d._add_button("Cancel", primary=False, accepted=False)
    for i, libelle in enumerate(libelles):
        d._add_choice_button(text=libelle, value=str(i), primary=(i == 0))
    d.show()
    QApplication.processEvents()
    QApplication.processEvents()
    return d


def _boutons(d):
    return [b for b in d.findChildren(QPushButton) if len(b.text()) >= 3]


def test_aucun_bouton_n_est_coupe(app):
    """Le cas signale, avec ses deux libelles reels."""
    _exiger_des_polices()
    d = _boite([LONG, "Native space (patient MRI 1)"])
    try:
        for b in _boutons(d):
            besoin = QFontMetrics(b.font()).horizontalAdvance(b.text())
            assert b.width() >= besoin + 16, (b.text(), b.width(), besoin)
    finally:
        d.close()


def test_la_fenetre_s_est_elargie(app):
    """570 px est la taille de depart ; elle ne suffit pas ici."""
    _exiger_des_polices()
    d = _boite([LONG, "Native space (patient MRI 1)"])
    try:
        assert d.width() > 570, d.width()
    finally:
        d.close()


def test_une_boite_ordinaire_garde_sa_taille(app):
    """Elargir ne doit pas gonfler les fenetres qui tiennent deja."""
    _exiger_des_polices()
    d = _boite(["Yes", "No"])
    try:
        assert d.width() == 570, d.width()
    finally:
        d.close()


@pytest.mark.parametrize("combien", [1, 2])
def test_elle_suit_le_nombre_de_boutons(app, combien):
    _exiger_des_polices()
    d = _boite([LONG] * combien)
    try:
        for b in _boutons(d):
            besoin = QFontMetrics(b.font()).horizontalAdvance(b.text())
            assert b.width() >= besoin + 16, (b.text(), b.width(), besoin)
    finally:
        d.close()


def test_l_ecran_prime_sur_les_boutons(app):
    """Au-dela, mieux vaut un libelle rogne qu'une fenetre hors champ.

    Trois libelles longs demandent plus que l'ecran n'offre : la
    fenetre s'arrete au bord, et ce sont les boutons qui cedent.
    """
    _exiger_des_polices()
    d = _boite([LONG] * 3)
    try:
        ecran = d.screen()
        if ecran is None:
            pytest.skip("aucun ecran")
        assert d.buttons_layout.sizeHint().width() > d.width(), "cas mal choisi"
        assert d.width() <= ecran.availableGeometry().width()
    finally:
        d.close()


def test_elle_ne_depasse_pas_l_ecran(app):
    """Un libelle absurde ne doit pas sortir la fenetre de l'ecran."""
    _exiger_des_polices()
    d = _boite(["x" * 400])
    try:
        ecran = d.screen()
        if ecran is not None:
            assert d.width() <= ecran.availableGeometry().width()
    finally:
        d.close()


def test_le_texte_du_choix_de_repere_tient(app):
    """Les libelles reels de NeuXelec, tels que la page les pose."""
    _exiger_des_polices()
    d = _boite(
        [
            "Native space (patient MRI 1)",
            "MNI space (%s)" % FilesPage.MNI_SPACE_NAME,
        ]
    )
    try:
        textes = {b.text() for b in _boutons(d)}
        assert "MNI space (%s)" % FilesPage.MNI_SPACE_NAME in textes
        for b in _boutons(d):
            besoin = QFontMetrics(b.font()).horizontalAdvance(b.text())
            assert b.width() >= besoin + 16, b.text()
    finally:
        d.close()
