# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La rangee Pial Surface, et le couple curseur / boite.

CE QUI CHANGE

Pial Surface prend la forme de Brain Mask : la case, son curseur
d'opacite et une boite a compteur sur une seule rangee. Le libelle
"Pial Opacity" disparait avec elle, la case le dit deja.

LE PIEGE QUE LA BOITE AMENE AVEC ELLE

Un curseur et sa boite ne montrent qu'un seul reglage. Les remises a
zero posent le curseur **signaux bloques**, pour ne pas declencher un
rendu par reglage : la boite n'en apprend alors rien et garde
l'ancienne valeur. On lit deux chiffres differents pour la meme
opacite, et rien ne le signale. Le brainmask avait deja ce defaut
depuis qu'il a sa boite.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile  # noqa: E402
from PySide6.QtUiTools import QUiLoader  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QFrame,
    QLabel,
    QSlider,
    QSpinBox,
)

from neuxelec.pages.view3d import View3DPage  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def ui(app):
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly)
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    assert w is not None
    return w


# ------------------------------------------------------ la rangee


def test_la_rangee_piale_a_la_forme_de_celle_du_brainmask(ui):
    """Case, curseur, boite : le meme ordre, pour la meme lecture."""
    layout = ui.findChild(QFrame, "card3DSurfaces").layout()
    rangee = next(
        layout.itemAt(i).layout()
        for i in range(layout.count())
        if layout.itemAt(i).layout() is not None
        and layout.itemAt(i).layout().objectName() == "horizontalLayout_49"
    )
    noms = [
        rangee.itemAt(i).widget().objectName()
        for i in range(rangee.count())
        if rangee.itemAt(i).widget() is not None
    ]
    assert noms[:3] == [
        "chk_3d_showPialsurface",
        "sld_3d_PialOpacity",
        "spinBox_3d_pialOpacity",
    ], noms


@pytest.mark.parametrize(
    "classe,nom",
    [
        (QCheckBox, "chk_3d_showPialsurface"),
        (QSlider, "sld_3d_PialOpacity"),
        (QSpinBox, "spinBox_3d_pialOpacity"),
    ],
)
def test_chaque_controle_est_dans_surfaces_et_unique(ui, classe, nom):
    carte = ui.findChild(QFrame, "card3DSurfaces")
    assert carte.findChild(classe, nom) is not None, nom
    trouves = [w for w in ui.findChildren(classe) if w.objectName() == nom]
    assert len(trouves) == 1, "%s existe en %d exemplaires" % (nom, len(trouves))


def test_le_libelle_pial_opacity_a_disparu(ui):
    restes = [
        e
        for e in ui.findChildren(QLabel)
        if (e.text() or "").strip().lower() == "pial opacity"
    ]
    assert restes == []


def test_la_case_mni_est_toujours_la(ui):
    """Elle est cachee par le code, mais elle porte l'etat du mode."""
    assert ui.findChild(QCheckBox, "chk_3d_showMNIAtlas") is not None


# ------------------------------------------- poser les deux ensemble


class _Faux:
    """Un curseur ou une boite, assez pour compter les signaux bloques."""

    def __init__(self, valeur=0, leve=False):
        self.valeur = valeur
        self.bloque = False
        self.historique = []
        self._leve = leve

    def blockSignals(self, on):  # noqa: N802
        self.bloque = bool(on)
        self.historique.append(bool(on))

    def setValue(self, v):  # noqa: N802
        if self._leve:
            raise RuntimeError("widget detruit")
        assert self.bloque, "la valeur a ete posee signaux ouverts"
        self.valeur = int(v)


def test_les_deux_recoivent_la_valeur(app):
    curseur, boite = _Faux(10), _Faux(90)
    View3DPage._set_opacity_pair(curseur, boite, 50)
    assert curseur.valeur == 50
    assert boite.valeur == 50


def test_aucun_signal_n_est_emis(app):
    """Sinon la remise a zero declencherait un rendu par reglage."""
    curseur, boite = _Faux(), _Faux()
    View3DPage._set_opacity_pair(curseur, boite, 50)
    for widget in (curseur, boite):
        assert widget.historique == [True, False]
        assert not widget.bloque, "les signaux sont restes bloques"


def test_un_widget_absent_ne_fait_rien_lever(app):
    View3DPage._set_opacity_pair(None, _Faux(), 30)
    View3DPage._set_opacity_pair(_Faux(), None, 30)
    View3DPage._set_opacity_pair(None, None, 30)


def test_les_signaux_sont_rendus_meme_si_la_pose_echoue(app):
    """Un widget laisse muet ne previendrait plus personne."""
    casse = _Faux(leve=True)
    with pytest.raises(RuntimeError):
        View3DPage._set_opacity_pair(casse, _Faux(), 50)
    assert not casse.bloque


# --------------------------------------------- le grise suit le curseur


class _Page:
    """Les cases et les reglages, et rien d'autre."""

    _update_brain_opacity_slider_states = (
        View3DPage._update_brain_opacity_slider_states
    )

    def __init__(self, pial=False, brainmask=False, mni=False):
        self.chk_pial = QCheckBox()
        self.chk_pial.setChecked(pial)
        self.chk_brainmask = QCheckBox()
        self.chk_brainmask.setChecked(brainmask)
        self.chk_mni_atlas = QCheckBox()
        self.chk_mni_atlas.setChecked(mni)
        self.sld_3d_PialOpacity = QSlider()
        self.spn_3d_pialOpacity = QSpinBox()
        self.sld_3d_brainMaskOpacity = QSlider()
        self.spn_3d_brainMaskOpacity = QSpinBox()
        self.chk_mni_brain = None
        self.sld_mni_brain_opacity = None
        self.spn_mni_brain_opacity = None


@pytest.mark.parametrize(
    "pial,mni,attendu",
    [(True, False, True), (False, False, False), (True, True, False)],
)
def test_la_boite_piale_est_grisee_comme_son_curseur(app, pial, mni, attendu):
    """Une boite active a cote d'un curseur grise laisserait croire
    qu'elle commande encore."""
    page = _Page(pial=pial, mni=mni)
    page._update_brain_opacity_slider_states()
    assert page.sld_3d_PialOpacity.isEnabled() is attendu
    assert page.spn_3d_pialOpacity.isEnabled() is attendu


@pytest.mark.parametrize("brainmask", [True, False])
def test_la_boite_du_brainmask_suit_aussi(app, brainmask):
    page = _Page(brainmask=brainmask)
    page._update_brain_opacity_slider_states()
    assert page.sld_3d_brainMaskOpacity.isEnabled() is brainmask
    assert page.spn_3d_brainMaskOpacity.isEnabled() is brainmask
