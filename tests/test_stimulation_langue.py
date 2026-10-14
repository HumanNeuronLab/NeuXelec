# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les deux fenetres de stimulation en anglais et en francais.

POURQUOI

Tout le monde ne lit pas l'anglais a l'hopital, et une fenetre qu'on ne
lit pas est une fenetre qu'on ne remplit pas.

CE QUE CES TESTS PROTEGENT

1. La LANGUE CHANGE L'AFFICHAGE, JAMAIS LA DONNEE. Un descripteur choisi
   en francais s'enregistre en anglais, sans quoi deux fiches du meme
   patient ne seraient plus comparables, et un filtre ne retrouverait
   plus ce qu'il a servi a ranger.
2. Changer de langue au milieu d'une saisie ne coute pas ce qui est
   deja tape.
3. Le vocabulaire clinique est traduit en entier: une liste a moitie
   traduite est pire que pas de traduction du tout.
4. Un texte absent du dictionnaire revient en anglais, pas en blanc.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from neuxelec.ui.stimulation_dialog import StimulationDialog  # noqa: E402
from neuxelec.ui.stimulation_results_dialog import StimulationResultsDialog  # noqa: E402
from neuxelec.utils import i18n  # noqa: E402
from neuxelec.utils import stimulation as st  # noqa: E402
from neuxelec.utils import stimulation_display as sd  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def anglais_au_depart():
    """Chaque test part et repart en anglais: la langue est globale."""
    i18n.set_language(i18n.ENGLISH)
    yield
    i18n.set_language(i18n.ENGLISH)


def _electrodes():
    return [{"name": "A", "contacts_lps": [[float(i) * 2.0, 0.0, 0.0] for i in range(8)]}]


class _Etat:
    def __init__(self, cartes=None):
        self.electrodes = _electrodes()
        self.stimulations = list(cartes or [])
        self.stimulation_display: dict = {}


# ================================================== le dictionnaire


def test_le_vocabulaire_clinique_est_traduit_en_entier():
    """Une liste a moitie traduite est pire que pas de traduction."""
    manquants: list[str] = []

    for cat in st.CATEGORIES:
        if cat.label not in i18n.FR:
            manquants.append(cat.label)

        for descripteur in cat.descriptors:
            if descripteur != st.OTHER and descripteur not in i18n.FR:
                manquants.append(descripteur)

    for liste in (st.BODY_PARTS, st.VISUAL_FIELDS, st.EARS):
        for valeur in liste:
            if valeur != st.OTHER and valeur not in i18n.FR:
                manquants.append(valeur)

    for paires in (
        st.EVENTS,
        st.HABITUAL,
        st.REPRODUCIBILITY,
        st.BEHAVIOURAL_STATES,
        st.ASM_STATES,
        st.POLARITIES,
        st.LATERALITIES,
        st.MOTOR_SIGNS,
    ):
        for _cle, label in paires:
            if label not in i18n.FR:
                manquants.append(label)

    assert sorted(set(manquants)) == []


def test_les_reglages_d_affichage_sont_traduits():
    manquants = [
        label
        for paires in (sd.COLOUR_MODES, sd.WHERE_CHOICES, sd.PRESETS)
        for _cle, label in paires
        if label not in i18n.FR
    ]
    assert manquants == []


def test_la_legende_est_traduite():
    manquants = [texte for _c, texte in st.COLOUR_LEGEND if texte not in i18n.FR]
    assert manquants == []


def test_un_texte_inconnu_revient_en_anglais():
    """En blanc, il serait illisible; en anglais, il reste lisible."""
    i18n.set_language(i18n.FRENCH)
    assert i18n.tr("something nobody translated") == "something nobody translated"


def test_les_termes_cliniques_sont_ceux_de_la_specialite():
    i18n.set_language(i18n.FRENCH)
    assert i18n.tr("Speech arrest") == "Arret du langage"
    assert i18n.tr("After-discharges") == "Post-decharges"
    assert i18n.tr("Epigastric rising sensation") == "Sensation epigastrique ascendante"
    assert i18n.tr("Habitual seizure, electro-clinical") == (
        "Crise habituelle, electro-clinique"
    )


def test_l_illusion_et_l_hallucination_restent_distinctes():
    """Le glossaire ILAE les separe, le francais aussi."""
    i18n.set_language(i18n.FRENCH)
    assert "Illusion" in i18n.tr(
        "Visual illusion (micropsia, macropsia, metamorphopsia)"
    )
    assert "Hallucination" in i18n.tr("Complex visual hallucination")


# ================================================== la fenetre de saisie


def test_la_fenetre_de_saisie_porte_le_selecteur(app):
    d = StimulationDialog(_electrodes(), 0, 0)
    assert d.header.cmb_language is not None
    assert [
        d.header.cmb_language.itemData(i) for i in range(d.header.cmb_language.count())
    ] == [i18n.ENGLISH, i18n.FRENCH]
    d.close()


def test_passer_en_francais_traduit_les_etiquettes(app):
    d = StimulationDialog(_electrodes(), 0, 0)
    ligne = d._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    assert ligne.fld_location.label.text() == "WHERE ON THE BODY"

    d.change_language(i18n.FRENCH)
    assert d._rows[0].fld_location.label.text() == "OU SUR LE CORPS"
    assert d.header.lbl_title.text() == "RESULTAT DE STIMULATION"
    d.close()


def test_le_descripteur_s_affiche_en_francais_et_s_enregistre_en_anglais(app):
    """Le point qui compte: la langue change l'affichage, pas la donnee."""
    d = StimulationDialog(_electrodes(), 0, 0)
    ligne = d._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))

    d.change_language(i18n.FRENCH)
    ligne = d._rows[0]
    index = ligne.cmb_descriptor.findData("Clonic jerks")
    ligne.cmb_descriptor.setCurrentIndex(index)

    assert ligne.cmb_descriptor.currentText() == "Secousses cloniques"
    assert d.record()["responses"][0]["descriptor"] == "Clonic jerks"
    d.close()


def test_la_localisation_aussi_s_enregistre_en_anglais(app):
    i18n.set_language(i18n.FRENCH)
    d = StimulationDialog(_electrodes(), 0, 0)
    ligne = d._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    index = ligne.cmb_location.findData("Hand")
    ligne.cmb_location.setCurrentIndex(index)

    assert ligne.cmb_location.currentText() == "Main"
    assert d.record()["responses"][0]["location"] == "Hand"
    d.close()


def test_les_cles_du_vocabulaire_ne_changent_pas_de_langue(app):
    i18n.set_language(i18n.FRENCH)
    d = StimulationDialog(_electrodes(), 0, 0)
    d.cmb_state.setCurrentIndex(d.cmb_state.findData("asleep"))
    assert d.cmb_state.currentText() == "Endormi"
    assert d.record()["behavioural_state"] == "asleep"
    d.close()


def test_changer_de_langue_ne_coute_pas_la_saisie(app):
    d = StimulationDialog(_electrodes(), 0, 0)
    d.cmb_frequency.setCurrentText("50")
    d.spn_current.setValue(4.5)
    d.txt_task.setText("comptage")
    d.txt_notes.setPlainText("une note")
    d.chk_events["after_discharges"].setChecked(True)
    ligne = d._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("language"))

    d.change_language(i18n.FRENCH)

    carte = d.record()
    assert carte["frequency_hz"] == 50.0
    assert carte["intensity_ma"] == 4.5
    assert carte["task"] == "comptage"
    assert carte["notes"] == "une note"
    assert carte["events"] == ["after_discharges"]
    assert carte["responses"][0]["category"] == "language"
    d.close()


def test_changer_de_langue_garde_la_paire_et_l_identifiant(app):
    carte = st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=3,
        record_id="stim-7",
        created="2026-10-12T10:00:00",
    )
    d = StimulationDialog(_electrodes(), 0, 0, record=carte)
    d.change_language(i18n.FRENCH)

    sortie = d.record()
    assert sortie["id"] == "stim-7"
    assert sortie["created"] == "2026-10-12T10:00:00"
    assert sortie["contact_b"] == 3
    d.close()


def test_revenir_en_anglais_remet_l_anglais(app):
    d = StimulationDialog(_electrodes(), 0, 0)
    d.change_language(i18n.FRENCH)
    d.change_language(i18n.ENGLISH)
    assert d.header.lbl_title.text() == "STIMULATION RESULT"
    d.close()


def test_une_fenetre_francaise_enregistre_comme_une_anglaise(app):
    """Deux fiches du meme patient doivent rester comparables."""

    def _carte(langue):
        i18n.set_language(langue)
        d = StimulationDialog(_electrodes(), 0, 0)
        ligne = d._add_response()
        ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("visual"))
        ligne.cmb_descriptor.setCurrentIndex(
            ligne.cmb_descriptor.findData("Phosphenes")
        )
        sortie = d.record()
        d.close()
        return sortie

    anglaise = _carte(i18n.ENGLISH)
    francaise = _carte(i18n.FRENCH)
    assert anglaise["responses"] == francaise["responses"]


def test_enregistrer_marche_dans_les_deux_langues(app):
    i18n.set_language(i18n.FRENCH)
    d = StimulationDialog(_electrodes(), 0, 0)
    d.accept()
    assert d.result() == int(QDialog.DialogCode.Accepted)
    d.close()


# ================================================== la fenetre des resultats


def test_la_fenetre_des_resultats_porte_le_selecteur(app):
    d = StimulationResultsDialog(_Etat())
    assert d.header.cmb_language is not None
    d.close()


def test_les_onglets_se_traduisent(app):
    d = StimulationResultsDialog(_Etat())
    d.change_language(i18n.FRENCH)
    assert [d.tabs.tabText(i) for i in range(3)] == [
        "Filtres d'affichage",
        "Apparence",
        "Fiches de stimulation",
    ]
    d.close()


def test_changer_de_langue_garde_les_filtres(app):
    d = StimulationResultsDialog(_Etat())
    d.chk_frequencies[50.0].setChecked(True)
    d.chk_filter_categories["motor"].setChecked(True)
    d.chk_min.setChecked(True)
    d.spn_min.setValue(2.5)

    d.change_language(i18n.FRENCH)

    filtres = d.filters()
    assert filtres["frequencies"] == {50.0}
    assert filtres["categories"] == {"motor"}
    assert filtres["min_intensity_ma"] == 2.5
    d.close()


def test_changer_de_langue_garde_les_regles(app):
    d = StimulationResultsDialog(_Etat())
    d.cmb_preset.setCurrentIndex(0)
    d._load_preset()
    avant = [r["colour"] for r in d.display_settings()["rules"]]

    d.change_language(i18n.FRENCH)

    apres = d.display_settings()["rules"]
    assert [r["colour"] for r in apres] == avant
    assert d.display_settings()["colour_mode"] == sd.BY_RULES
    d.close()


def test_changer_de_langue_garde_l_onglet_ouvert(app):
    d = StimulationResultsDialog(_Etat())
    d.tabs.setCurrentIndex(2)
    d.change_language(i18n.FRENCH)
    assert d.tabs.currentIndex() == 2
    d.close()


def test_la_fiche_se_lit_en_francais(app):
    carte = st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        record_id="stim-1",
        habitual="identical",
        events=["after_discharges"],
        responses=[st.new_response("motor", "Clonic jerks", location="Hand")],
    )
    d = StimulationResultsDialog(_Etat([carte]))
    d.change_language(i18n.FRENCH)
    texte = d.lbl_card.text()
    assert "Paire" in texte
    assert "Post-decharges" in texte
    assert "Secousses cloniques" in texte
    d.close()


def test_le_compte_se_traduit(app):
    carte = st.new_record(electrode="A", contact=0, record_id="stim-1")
    d = StimulationResultsDialog(_Etat([carte]))
    d.change_language(i18n.FRENCH)
    assert "montrees dans la vue 3D" in d.lbl_count.text()
    d.close()


def test_sans_stimulation_le_message_se_traduit(app):
    d = StimulationResultsDialog(_Etat())
    d.change_language(i18n.FRENCH)
    assert d.lbl_count.text() == "Aucune stimulation enregistree."
    d.close()
