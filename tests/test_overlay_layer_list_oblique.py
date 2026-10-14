# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La colonne des calques de l'onglet Overlay, en coupe oblique.

Meme colonne qu'en vue 3D, avec les noms de widgets d'ici. Ces tests
repetent donc les memes exigences sur l'autre page, parce que c'est le
fichier .ui qui peut les trahir, pas la classe : une case renommee ou
une carte deplacee ferait disparaitre une ligne en silence.

Deux choses leur sont propres :

  - la carte ANATOMICAL IMAGE a ete scindee en CT et MRI, pour qu'un
    calque choisi montre ses reglages et eux seuls ;
  - la carte DISPLAY a disparu. Son reglage de taille des contacts
    n'etait jamais touche, et sa case Micro tetrodes descend dans la
    colonne, sous les calques : elle n'ouvre aucune carte, donc elle
    garde son texte au lieu du bouton des calques.
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
)

from neuxelec.ui.overlay_layer_list import (  # noqa: E402
    LAYERS_OBLIQUE,
    TOGGLES_OBLIQUE,
    OverlayLayerList,
)
from neuxelec.utils.resources import resource_path  # noqa: E402

CARTES = (
    "cardObliqueMRI",
    "cardObliqueCT",
    "cardObliquePET",
    "cardObliqueSISCOM",
    "cardObliquefMRI",
    "cardObliqueSPECT",
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _charger():
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly), "MainWindow.ui illisible"
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    assert w is not None, "MainWindow.ui ne se charge pas"
    return w


@pytest.fixture
def brut(app):
    """L'interface telle qu'elle sort du fichier, colonne non montee."""
    return _charger()


@pytest.fixture
def monte(app):
    """L'interface avec la colonne batie, comme la page oblique la monte."""
    w = _charger()
    liste = OverlayLayerList(
        w,
        layers=LAYERS_OBLIQUE,
        frame_name="cardObliqueLayerList",
        toggles=TOGGLES_OBLIQUE,
    )
    assert liste.build(), "la colonne ne s'est pas construite"
    return w, liste


# ------------------------------------------------- ce que le .ui promet


def test_chaque_calque_pointe_sur_des_widgets_reels(brut):
    """Une faute de frappe ferait disparaitre la ligne sans rien dire."""
    for layer in LAYERS_OBLIQUE:
        assert brut.findChild(QCheckBox, layer.checkbox) is not None, layer.checkbox
        assert brut.findChild(QFrame, layer.card) is not None, layer.card


def test_la_carte_anatomique_a_ete_scindee(brut):
    assert brut.findChild(QFrame, "cardObliqueCT") is not None
    assert brut.findChild(QFrame, "cardObliqueMRI") is not None
    assert brut.findChild(QFrame, "cardObliqueAnatomical") is None


def test_le_titre_overlay_settings_a_disparu(brut):
    titres = [
        e
        for e in brut.findChildren(QLabel)
        if (e.text() or "").strip().upper() == "OVERLAY SETTINGS"
    ]
    assert titres == [], "le titre prend encore de la place"


def test_le_cadre_de_la_colonne_existe(brut):
    cadre = brut.findChild(QFrame, "cardObliqueLayerList")
    assert cadre is not None
    assert cadre.maximumWidth() == 158


# ------------------------------------------------------- la colonne batie


def test_les_huit_calques_ont_leur_ligne(monte):
    _, liste = monte
    assert sorted(liste._buttons) == sorted(layer.key for layer in LAYERS_OBLIQUE)


@pytest.mark.parametrize(
    "cle,carte", [(layer.key, layer.card) for layer in LAYERS_OBLIQUE]
)
def test_une_seule_carte_visible_a_la_fois(monte, cle, carte):
    w, liste = monte
    liste.select(cle)
    visibles = [n for n in CARTES if not w.findChild(QFrame, n).isHidden()]
    assert visibles == [carte]


def test_le_reglage_de_taille_des_contacts_a_disparu(brut):
    """Il valait 4 et n'etait jamais touche ; les deux points qui le
    lisaient retombent deja sur 4 quand le widget manque."""
    from PySide6.QtWidgets import QSpinBox

    assert brut.findChild(QSpinBox, "spinBox_obliqueSlice_SizeContacts") is None


def test_la_carte_display_videe_est_cachee(monte):
    """Un cadre vide garderait ses marges et une ligne de vide."""
    w, _ = monte
    assert w.findChild(QFrame, "cardObliqueDisplay").isHidden()


def test_la_case_micro_tetrodes_est_dans_la_colonne(monte):
    w, liste = monte
    colonne = w.findChild(QFrame, "cardObliqueLayerList")
    case = liste.toggles()["micro_tetrodes"]
    assert case.objectName() == "layerToggle"
    assert case.text() == "Micro tetrodes"
    assert colonne.isAncestorOf(case)


def test_la_case_micro_tetrodes_n_est_pas_une_copie(monte):
    w, _ = monte
    cases = [
        c
        for c in w.findChildren(QCheckBox)
        if c.objectName() == "layerToggle" or c.text() == "Micro tetrodes"
    ]
    assert len(cases) == 1, "la case existe en %d exemplaires" % len(cases)


def test_la_case_micro_tetrodes_garde_son_explication(monte):
    """L'infobulle dit que la position est calculee, pas mesuree."""
    _, liste = monte
    assert "calculated position" in liste.toggles()["micro_tetrodes"].toolTip()


@pytest.mark.parametrize("cle", [layer.key for layer in LAYERS_OBLIQUE])
def test_choisir_un_calque_ne_cache_pas_les_micro_tetrodes(monte, cle):
    """Elles ne dependent d'aucun calque : elles restent accessibles."""
    _, liste = monte
    liste.select(cle)
    assert not liste.toggles()["micro_tetrodes"].isHidden()


def test_la_case_est_celle_de_la_carte_et_non_une_copie(monte):
    """Le piege : deux objets pour un seul etat, et la copie qui ment."""
    w, _ = monte
    for layer in LAYERS_OBLIQUE:
        cases = [
            c for c in w.findChildren(QCheckBox) if c.objectName() == layer.checkbox
        ]
        assert len(cases) == 1, f"{layer.checkbox} existe en {len(cases)} exemplaires"


def test_la_case_a_quitte_sa_carte_pour_la_ligne(monte, brut):
    """Avant elle est dans la carte, apres elle n'y est plus."""
    avant = brut.findChild(QFrame, "cardObliquePET")
    assert any(
        c.objectName() == "chk_obliqueSlice_PET" for c in avant.findChildren(QCheckBox)
    )

    w, _ = monte
    apres = w.findChild(QFrame, "cardObliquePET")
    assert not any(
        c.objectName() == "chk_obliqueSlice_PET" for c in apres.findChildren(QCheckBox)
    )


def test_les_deux_blocs_spect_restent_distincts(monte):
    """Seules leurs cases les nommaient : sans etiquette on verrait deux
    series de reglages identiques."""
    w, _ = monte
    carte = w.findChild(QFrame, "cardObliqueSPECT")
    textes = [(e.text() or "").strip() for e in carte.findChildren(QLabel)]
    assert "Ictal SPECT" in textes
    assert "Inter-ictal SPECT" in textes


def test_le_grise_suit_la_case_et_non_une_relecture_de_l_etat(monte):
    w, liste = monte
    case = w.findChild(QCheckBox, "chk_obliqueSlice_PET")
    case.setEnabled(False)
    liste.refresh()
    assert not liste._buttons["pet"].isEnabled()

    case.setEnabled(True)
    liste.refresh()
    assert liste._buttons["pet"].isEnabled()
