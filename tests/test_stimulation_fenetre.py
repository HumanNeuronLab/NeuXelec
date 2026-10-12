"""La fenetre de saisie d'un resultat de stimulation.

CE QU'ELLE DOIT RENDRE FACILE

La carte porte une trentaine de champs, parce que c'est ce qu'il faut
pour qu'elle soit encore lisible dans six mois. Demander trente champs,
c'est n'en faire remplir aucun. Ces tests verifient les quatre gestes
qui evitent cela:

1. le second contact est deja propose, et c'est l'adjacent;
2. choisir une frequence remplit impulsion, train et courant d'apres la
   Table 2 de l'ACNS, SANS ecraser ce qui a ete tape a la main;
3. la localisation montre un corps, un champ visuel ou une oreille selon
   la categorie, et rien du tout pour celles qui ne se localisent pas;
4. le detail des post-decharges n'apparait que lorsqu'il y a quelque
   chose a decrire.

CE QU'ELLE REFUSE

Un seul cas: un contact contre lui-meme, ou une paire qui ne designe
aucun contact. Une paire non adjacente, a cheval sur deux electrodes ou
monopolaire avertit et s'enregistre, parce que ces trois cas se
pratiquent.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from neuxelec.ui.stimulation_dialog import StimulationDialog  # noqa: E402
from neuxelec.utils import stimulation as st  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _electrodes():
    return [
        {"name": "A", "contacts_lps": [[float(i), 0.0, 0.0] for i in range(8)]},
        {"name": "B", "contacts_lps": [[0.0, float(i), 10.0] for i in range(4)]},
    ]


@pytest.fixture
def fenetre(app):
    """A1 est le contact stimule."""
    d = StimulationDialog(_electrodes(), 0, 0)
    yield d
    d.close()


# --------------------------------------------- la paire est pre-remplie


def test_le_contact_adjacent_est_deja_propose(fenetre):
    """Le bipolaire adjacent est la norme clinique."""
    assert fenetre.cmb_second.currentText() == "A2"


def test_le_dernier_contact_propose_celui_d_avant(app):
    d = StimulationDialog(_electrodes(), 0, 7)
    assert d.cmb_second.currentText() == "A7"
    d.close()


def test_les_contacts_de_la_meme_electrode_viennent_en_tete(fenetre):
    choix = [fenetre.cmb_second.itemText(i) for i in range(fenetre.cmb_second.count())]
    assert choix[0] == "A2"
    assert "B1" in choix
    assert choix.index("A8") < choix.index("B1")


def test_le_contact_stimule_ne_se_propose_pas_lui_meme(fenetre):
    choix = [fenetre.cmb_second.itemText(i) for i in range(fenetre.cmb_second.count())]
    assert "A1" not in choix


def test_une_paire_adjacente_n_affiche_rien(fenetre):
    assert fenetre.pair_problem() is None
    assert not fenetre.lbl_pair_problem.isVisibleTo(fenetre)


# ------------------------------------------- ce qui est refuse, ce qui avertit


def test_un_contact_inconnu_est_signale(fenetre):
    fenetre.cmb_second.setEditText("Z9")
    assert "No contact named Z9" in fenetre.pair_problem()


def test_un_contact_inconnu_empeche_d_enregistrer(fenetre):
    fenetre.cmb_second.setEditText("Z9")
    assert fenetre.pair_is_impossible()


def test_un_contact_contre_lui_meme_empeche_d_enregistrer(fenetre):
    fenetre.cmb_second.setEditText("A1")
    assert fenetre.pair_is_impossible()


def test_une_paire_non_adjacente_avertit_mais_s_enregistre(fenetre):
    fenetre.cmb_second.setEditText("A5")
    assert "not adjacent" in fenetre.pair_problem()
    assert not fenetre.pair_is_impossible()


def test_une_paire_a_cheval_avertit_mais_s_enregistre(fenetre):
    fenetre.cmb_second.setEditText("B1")
    assert "two electrodes" in fenetre.pair_problem()
    assert not fenetre.pair_is_impossible()


def test_un_second_contact_vide_est_reclame(fenetre):
    fenetre.cmb_second.setEditText("")
    assert "Name the second contact" in fenetre.pair_problem()
    assert fenetre.pair_is_impossible()


def test_enregistrer_une_paire_impossible_ne_ferme_pas(fenetre):
    fenetre.cmb_second.setEditText("A1")
    fenetre.accept()
    assert fenetre.result() != int(QDialog.DialogCode.Accepted)
    assert fenetre.lbl_pair_problem.isVisibleTo(fenetre)


def test_enregistrer_une_paire_valide_ferme(fenetre):
    fenetre.accept()
    assert fenetre.result() == int(QDialog.DialogCode.Accepted)


# ------------------------------------------------------- le monopolaire


def test_le_monopolaire_remplace_la_paire_par_une_reference(fenetre):
    index = fenetre.cmb_polarity.findData("monopolar")
    fenetre.cmb_polarity.setCurrentIndex(index)
    assert not fenetre.cmb_second.isVisibleTo(fenetre)
    assert fenetre.txt_reference.isVisibleTo(fenetre)


def test_le_monopolaire_n_a_pas_de_probleme_de_paire(fenetre):
    fenetre.cmb_second.setEditText("Z9")
    index = fenetre.cmb_polarity.findData("monopolar")
    fenetre.cmb_polarity.setCurrentIndex(index)
    assert fenetre.pair_problem() is None
    assert not fenetre.pair_is_impossible()


def test_le_monopolaire_s_enregistre_sans_second_contact(fenetre):
    index = fenetre.cmb_polarity.findData("monopolar")
    fenetre.cmb_polarity.setCurrentIndex(index)
    fenetre.txt_reference.setText("scalp Fz")
    carte = fenetre.record()
    assert carte["polarity"] == "monopolar"
    assert carte["contact_b"] is None
    assert st.pair_label(carte) == "A1 vs scalp Fz"


# ------------------------------------------------- le protocole se remplit


def test_le_protocole_part_sur_le_un_hertz(fenetre):
    assert fenetre.frequency_hz() == 1.0
    assert fenetre.spn_pulse.value() == 500
    assert fenetre.spn_train.value() == 30.0
    assert fenetre.spn_current.value() == 3.0


def test_passer_en_cinquante_hertz_remplit_le_protocole_court(fenetre):
    fenetre.cmb_frequency.setCurrentText("50")
    assert fenetre.spn_pulse.value() == 300
    assert fenetre.spn_train.value() == 4.0
    assert fenetre.spn_current.value() == 2.0


def test_un_courant_tape_a_la_main_survit_au_changement_de_frequence(fenetre):
    """Le piege: ecraser ce que l'utilisateur vient de saisir."""
    fenetre.spn_current.setValue(4.5)
    fenetre.cmb_frequency.setCurrentText("50")
    assert fenetre.spn_current.value() == 4.5


def test_une_impulsion_tapee_a_la_main_survit_aussi(fenetre):
    fenetre.spn_pulse.setValue(250)
    fenetre.cmb_frequency.setCurrentText("50")
    assert fenetre.spn_pulse.value() == 250


def test_une_frequence_illisible_ne_leve_pas(fenetre):
    fenetre.cmb_frequency.setCurrentText("beaucoup")
    assert fenetre.frequency_hz() == 1.0


def test_la_virgule_decimale_est_acceptee(fenetre):
    fenetre.cmb_frequency.setCurrentText("0,5")
    assert fenetre.frequency_hz() == 0.5


# --------------------------------------------- les fleches du courant


def test_la_fleche_monte_le_courant_d_un_demi_milliampere(fenetre):
    depart = fenetre.spn_current.value()
    fenetre._step_current(1)
    assert fenetre.spn_current.value() == pytest.approx(depart + 0.5)


def test_la_fleche_descend_le_courant(fenetre):
    depart = fenetre.spn_current.value()
    fenetre._step_current(-1)
    assert fenetre.spn_current.value() == pytest.approx(depart - 0.5)


def test_descendre_le_courant_jusqu_en_bas_donne_NA(fenetre):
    """Le bas de la plage veut dire "non note", pas zero milliampere."""
    for _ in range(20):
        fenetre._step_current(-1)

    assert fenetre.spn_current.text() == "NA"
    assert fenetre.record()["intensity_ma"] is None


def test_un_courant_fort_affiche_l_avertissement_de_charge(fenetre):
    fenetre.cmb_frequency.setCurrentText("50")
    fenetre.spn_current.setValue(8.0)
    assert fenetre.lbl_charge.isVisibleTo(fenetre)
    assert "charge density" in fenetre.lbl_charge.text()


def test_un_courant_usuel_n_affiche_rien(fenetre):
    fenetre.spn_current.setValue(3.0)
    assert not fenetre.lbl_charge.isVisibleTo(fenetre)


# ------------------------------------- le detail des decharges est conditionnel


def test_le_detail_des_decharges_est_cache_au_depart(fenetre):
    assert not fenetre.frm_discharge.isVisibleTo(fenetre)


def test_cocher_une_post_decharge_le_montre(fenetre):
    fenetre.chk_events["after_discharges"].setChecked(True)
    assert fenetre.frm_discharge.isVisibleTo(fenetre)


def test_cocher_une_crise_le_montre_aussi(fenetre):
    fenetre.chk_events["seizure_aura"].setChecked(True)
    assert fenetre.frm_discharge.isVisibleTo(fenetre)


def test_le_decocher_le_recache(fenetre):
    fenetre.chk_events["after_discharges"].setChecked(True)
    fenetre.chk_events["after_discharges"].setChecked(False)
    assert not fenetre.frm_discharge.isVisibleTo(fenetre)


def test_other_seul_ne_montre_pas_le_detail(fenetre):
    """Il n'y a pas de post-decharge a decrire."""
    fenetre.chk_events[st.OTHER].setChecked(True)
    assert not fenetre.frm_discharge.isVisibleTo(fenetre)


def test_les_quatre_niveaux_de_crise_sont_cochables(fenetre):
    for key, _ in st.EVENT_SEIZURES:
        assert key in fenetre.chk_events


# ------------------------------------------------ les blocs de reponse


def test_il_n_y_a_aucun_bloc_au_depart(fenetre):
    """Une paire testee et muette est une carte valide."""
    assert fenetre.record()["responses"] == []
    assert fenetre.lbl_no_response.isVisibleTo(fenetre)


def test_ajouter_un_bloc_cache_le_rappel(fenetre):
    fenetre._add_response()
    assert not fenetre.lbl_no_response.isVisibleTo(fenetre)


def test_un_bloc_s_enleve(fenetre):
    ligne = fenetre._add_response()
    fenetre._remove_response(ligne)
    assert fenetre.record()["responses"] == []


def test_deux_blocs_gardent_chacun_sa_localisation(fenetre):
    premier = fenetre._add_response()
    premier.cmb_category.setCurrentIndex(premier.cmb_category.findData("motor"))
    premier.cmb_location.setCurrentText("Hand")

    second = fenetre._add_response()
    second.cmb_category.setCurrentIndex(second.cmb_category.findData("visual"))
    second.cmb_location.setCurrentText("Left hemifield")

    reponses = fenetre.record()["responses"]
    assert reponses[0]["location"] == "Hand"
    assert reponses[1]["location"] == "Left hemifield"


# ------------------------------- la localisation suit la categorie


def test_le_moteur_propose_un_corps(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    assert ligne.cmb_location.isVisibleTo(ligne)
    assert ligne.cmb_location.itemText(0) == st.BODY_PARTS[0]


def test_le_visuel_propose_un_champ(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("visual"))
    assert ligne.cmb_location.itemText(0) == st.VISUAL_FIELDS[0]


def test_l_auditif_propose_une_oreille(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("auditory"))
    assert ligne.cmb_location.itemText(0) == st.EARS[0]


def test_le_langage_ne_demande_pas_de_localisation(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("language"))
    assert not ligne.cmb_location.isVisibleTo(ligne)
    assert not ligne.cmb_laterality.isVisibleTo(ligne)


def test_seul_le_moteur_demande_le_signe(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    assert ligne.cmb_sign.isVisibleTo(ligne)
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("cognitive"))
    assert not ligne.cmb_sign.isVisibleTo(ligne)


def test_changer_de_categorie_change_les_descripteurs(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("language"))
    assert ligne.cmb_descriptor.currentText() == "Speech arrest"
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("auditory"))
    assert ligne.cmb_descriptor.currentText() == "Tinnitus"


def test_le_texte_libre_n_apparait_qu_avec_other(fenetre):
    ligne = fenetre._add_response()
    assert not ligne.txt_other.isVisibleTo(ligne)
    ligne.cmb_descriptor.setCurrentIndex(ligne.cmb_descriptor.findText(st.OTHER))
    assert ligne.txt_other.isVisibleTo(ligne)


def test_le_signe_moteur_n_est_garde_que_pour_le_moteur(fenetre):
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("cognitive"))
    assert ligne.response()["sign"] == ""


# ------------------------------------------------- la carte produite


def test_la_carte_porte_la_paire_et_le_protocole(fenetre):
    fenetre.cmb_frequency.setCurrentText("50")
    fenetre.spn_current.setValue(2.5)
    carte = fenetre.record()
    assert carte["electrode"] == "A"
    assert carte["contact"] == 0
    assert carte["electrode_b"] == "A"
    assert carte["contact_b"] == 1
    assert carte["frequency_hz"] == 50.0
    assert carte["intensity_ma"] == 2.5
    assert carte["pulse_width_us"] == 300


def test_la_carte_porte_les_evenements_coches(fenetre):
    fenetre.chk_events["after_discharges"].setChecked(True)
    fenetre.chk_events["seizure_atypical"].setChecked(True)
    assert set(fenetre.record()["events"]) == {"after_discharges", "seizure_atypical"}


def test_la_carte_porte_l_habituel_et_la_reproductibilite(fenetre):
    fenetre.cmb_habitual.setCurrentIndex(fenetre.cmb_habitual.findData("identical"))
    fenetre.cmb_reproducibility.setCurrentIndex(
        fenetre.cmb_reproducibility.findData("reproduced")
    )
    carte = fenetre.record()
    assert carte["habitual"] == "identical"
    assert carte["reproducibility"] == "reproduced"


def test_la_carte_porte_le_seuil_quand_il_est_donne(fenetre):
    fenetre.txt_threshold.setText("1.5")
    assert fenetre.record()["threshold_ma"] == 1.5


def test_un_seuil_vide_reste_vide(fenetre):
    assert fenetre.record()["threshold_ma"] is None


def test_un_seuil_illisible_ne_leve_pas(fenetre):
    fenetre.txt_threshold.setText("un peu")
    assert fenetre.record()["threshold_ma"] is None


def test_la_carte_porte_les_notes_et_l_operateur(fenetre):
    fenetre.txt_notes.setPlainText("le patient etait distrait")
    fenetre.txt_operator.setText("JV")
    carte = fenetre.record()
    assert carte["notes"] == "le patient etait distrait"
    assert carte["operator"] == "JV"


def test_la_carte_porte_la_tache(fenetre):
    """Une reponse de langage est illisible sans elle."""
    fenetre.txt_task.setText("denomination")
    assert fenetre.record()["task"] == "denomination"


# ------------------------------------------------- relire une carte


def _carte_complete():
    return st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=2,
        record_id="stim-7",
        created="2026-10-12T10:00:00",
        frequency_hz=50.0,
        intensity_ma=4.5,
        pulse_width_us=250,
        train_duration_s=3.0,
        threshold_ma=2.0,
        behavioural_state="asleep",
        asm="reduced",
        task="comptage",
        events=["after_discharges", "seizure_electroclinical"],
        habitual="identical",
        reproducibility="reproduced",
        ad_location="A1-A2, et A5 a distance",
        ad_remote=True,
        aborted=True,
        responses=[
            st.new_response("motor", "Movement arrest", sign="negative", location="Hand"),
            st.new_response("visual", "Phosphenes", location="Central"),
        ],
        notes="une note",
        operator="JV",
    )


def test_une_carte_existante_se_relit(app):
    d = StimulationDialog(_electrodes(), 0, 0, record=_carte_complete())
    assert d.cmb_second.currentText() == "A3"
    assert d.frequency_hz() == 50.0
    assert d.spn_current.value() == 4.5
    assert d.spn_pulse.value() == 250
    d.close()


def test_le_protocole_relu_n_est_pas_ecrase_par_la_frequence(app):
    """Le piege: la frequence relue declenche le remplissage par defaut."""
    d = StimulationDialog(_electrodes(), 0, 0, record=_carte_complete())
    assert d.spn_current.value() == 4.5
    assert d.spn_train.value() == 3.0
    d.close()


def test_les_evenements_et_les_reponses_sont_relus(app):
    d = StimulationDialog(_electrodes(), 0, 0, record=_carte_complete())
    assert d.chk_events["after_discharges"].isChecked()
    assert d.chk_events["seizure_electroclinical"].isChecked()
    assert len(d._rows) == 2
    assert d.frm_discharge.isVisibleTo(d)
    d.close()


def test_une_carte_relue_garde_son_identifiant_et_sa_date(app):
    d = StimulationDialog(_electrodes(), 0, 0, record=_carte_complete())
    carte = d.record()
    assert carte["id"] == "stim-7"
    assert carte["created"] == "2026-10-12T10:00:00"
    d.close()


def test_une_carte_relue_ressort_fidele(app):
    """L'aller-retour par la fenetre ne doit rien perdre."""
    depart = _carte_complete()
    d = StimulationDialog(_electrodes(), 0, 0, record=depart)
    sortie = d.record()

    for champ in (
        "electrode",
        "contact",
        "electrode_b",
        "contact_b",
        "frequency_hz",
        "intensity_ma",
        "pulse_width_us",
        "train_duration_s",
        "threshold_ma",
        "behavioural_state",
        "asm",
        "task",
        "habitual",
        "reproducibility",
        "ad_location",
        "ad_remote",
        "aborted",
        "notes",
        "operator",
    ):
        assert sortie[champ] == depart[champ], champ

    assert set(sortie["events"]) == set(depart["events"])
    assert len(sortie["responses"]) == 2
    assert sortie["responses"][0]["sign"] == "negative"
    assert sortie["responses"][0]["location"] == "Hand"
    assert sortie["responses"][1]["location"] == "Central"
    d.close()


# ------------------------------------------------- l'anatomie


def test_l_anatomie_des_deux_contacts_est_nommee(app):
    """Une paire bipolaire chevauche souvent deux regions."""
    noms = {("A", 0): "ctx-lh-hippocampus", ("A", 1): "wm-lh-temporal"}
    d = StimulationDialog(
        _electrodes(), 0, 0, anatomy_lookup=lambda nom, i: noms.get((nom, i))
    )
    texte = d.lbl_anatomy.text()
    assert "A1 ctx-lh-hippocampus" in texte
    assert "A2 wm-lh-temporal" in texte
    assert d.record()["anatomy"] == ["A1 ctx-lh-hippocampus", "A2 wm-lh-temporal"]
    d.close()


def test_sans_parcellation_l_anatomie_se_tait(fenetre):
    assert not fenetre.lbl_anatomy.isVisibleTo(fenetre)
    assert fenetre.record()["anatomy"] == []


def test_une_recherche_d_anatomie_qui_leve_ne_casse_rien(app):
    def casse(_nom, _i):
        raise RuntimeError("pas de parcellation")

    d = StimulationDialog(_electrodes(), 0, 0, anatomy_lookup=casse)
    assert d.record()["anatomy"] == []
    d.close()


def test_l_anatomie_suit_le_changement_de_paire(app):
    noms = {("A", 0): "hippocampe", ("A", 4): "amygdale"}
    d = StimulationDialog(
        _electrodes(), 0, 0, anatomy_lookup=lambda nom, i: noms.get((nom, i))
    )
    d.cmb_second.setEditText("A5")
    assert "amygdale" in d.lbl_anatomy.text()
    d.close()


# ------------------------------------------------- sans electrode


def test_sans_electrode_la_fenetre_ne_leve_pas(app):
    """Le menu ne devrait pas s'ouvrir, mais la fenetre ne doit pas tomber."""
    d = StimulationDialog([], 0, 0)
    assert d.record()["electrode"] == ""
    d.close()


# ================================================== ce que la fenetre dit


def test_chaque_champ_porte_sa_question(fenetre):
    """Le defaut signale: une liste deroulante nue sous Motor pouvait etre
    le descripteur, la partie du corps ou le cote, et rien ne le disait."""
    ligne = fenetre._add_response()
    for champ, attendu in (
        (ligne.fld_category, "KIND OF RESPONSE"),
        (ligne.fld_descriptor, "WHAT EXACTLY"),
        (ligne.fld_laterality, "WHICH SIDE"),
        (ligne.fld_note, "NOTE ON THIS RESPONSE"),
    ):
        assert champ.label.text() == attendu


def test_la_question_de_localisation_suit_la_categorie(fenetre):
    """C'est la plainte exacte: on ne comprenait pas ce qui etait demande."""
    ligne = fenetre._add_response()

    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    assert ligne.fld_location.label.text() == "WHERE ON THE BODY"

    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("visual"))
    assert ligne.fld_location.label.text() == "WHICH PART OF THE VISUAL FIELD"

    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("auditory"))
    assert ligne.fld_location.label.text() == "WHICH EAR"


def test_le_champ_entier_disparait_quand_il_ne_s_applique_pas(fenetre):
    """L'etiquette doit partir avec la liste, pas rester orpheline."""
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("language"))
    assert not ligne.fld_location.isVisibleTo(ligne)
    assert not ligne.fld_laterality.isVisibleTo(ligne)
    assert not ligne.fld_sign.isVisibleTo(ligne)


def test_le_signe_moteur_propose_les_deux_sens(fenetre):
    """Positif et negatif: la distinction que l'ACNS demande d'abord."""
    ligne = fenetre._add_response()
    ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData("motor"))
    textes = [
        ligne.cmb_sign.itemText(i) for i in range(ligne.cmb_sign.count())
    ]
    assert any("Positive" in t for t in textes)
    assert any("Negative" in t for t in textes)


def test_les_blocs_sont_numerotes(fenetre):
    premier = fenetre._add_response()
    second = fenetre._add_response()
    assert premier.lbl_index.text() == "RESPONSE 1"
    assert second.lbl_index.text() == "RESPONSE 2"


def test_retirer_un_bloc_renumerote_les_suivants(fenetre):
    premier = fenetre._add_response()
    second = fenetre._add_response()
    fenetre._remove_response(premier)
    assert second.lbl_index.text() == "RESPONSE 1"


def test_le_second_contact_se_tape(fenetre):
    """La liste est editable: on peut nommer n'importe quel contact."""
    assert fenetre.cmb_second.isEditable()


def test_la_reference_remplace_le_second_contact_etiquette_comprise(fenetre):
    index = fenetre.cmb_polarity.findData("monopolar")
    fenetre.cmb_polarity.setCurrentIndex(index)
    assert not fenetre.fld_second.isVisibleTo(fenetre)
    assert fenetre.fld_reference.isVisibleTo(fenetre)
    assert fenetre.fld_reference.label.text() == "REMOTE REFERENCE"


# ================================================== la fenetre s'agrandit


def test_la_fenetre_fait_deux_listes_et_demie_de_large(fenetre):
    """Elle se lit a cote de la liste d'electrodes, pas par-dessus la vue."""
    from neuxelec.ui.neuxelec_dialog import ELECTRODE_LIST_WIDTH

    assert fenetre.width() == int(ELECTRODE_LIST_WIDTH * 2.5)


def test_elle_est_plus_haute_que_large(fenetre):
    assert fenetre.height() > fenetre.width()


def test_elle_se_reduit_assez_pour_degager_la_page(fenetre):
    """Une fenetre qui ne se reduit pas gene celui qui veut regarder
    derriere elle."""
    assert fenetre.minimumWidth() <= 400
    assert fenetre.minimumHeight() <= 300


def test_aucun_encadre_ne_depasse_a_la_taille_par_defaut(app):
    """Rien n'est coupe a l'ouverture: on ne defile jamais lateralement.

    A la taille MINIMALE, en revanche, le contenu deborde volontiers:
    c'est le but, la fenetre doit pouvoir se faire toute petite pour
    degager la page, et on defile verticalement.

    Saute quand aucune police n'est installee: la largeur d'un encadre
    est alors celle d'une police de repli, qui n'est pas celle que
    l'utilisateur verra.
    """
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QFrame

    if not QFontDatabase.families():
        pytest.skip("aucune police: les largeurs de texte ne veulent rien dire")

    d = StimulationDialog(_electrodes(), 0, 0)
    d._add_response()
    d.move(-6000, 0)
    d.show()

    for _ in range(4):
        QApplication.processEvents()

    # La largeur utile: la fenetre moins ses marges et sa barre verticale.
    utile = d.width() - 20 - 32 - 14

    for frame in d.findChildren(QFrame):
        if frame.objectName() in ("card", "responseBlock"):
            assert frame.minimumSizeHint().width() <= utile, frame.objectName()

    d.close()


def test_le_bouton_agrandir_existe(fenetre):
    assert fenetre.header.btn_maximise is not None
    assert fenetre.header.btn_maximise.isEnabled()


def test_agrandir_et_revenir(fenetre):
    fenetre.show()
    QApplication.processEvents()
    fenetre.toggle_maximised()
    QApplication.processEvents()
    assert fenetre.isMaximized()
    fenetre.toggle_maximised()
    QApplication.processEvents()
    assert not fenetre.isMaximized()


def test_les_coins_redimensionnent(fenetre):
    """Les quatre coins, pas seulement les bords."""
    from PySide6.QtCore import QPoint, Qt

    largeur, hauteur = fenetre.width(), fenetre.height()
    coins = {
        (2, 2): Qt.LeftEdge | Qt.TopEdge,
        (largeur - 2, 2): Qt.RightEdge | Qt.TopEdge,
        (2, hauteur - 2): Qt.LeftEdge | Qt.BottomEdge,
        (largeur - 2, hauteur - 2): Qt.RightEdge | Qt.BottomEdge,
    }

    for (x, y), attendu in coins.items():
        assert fenetre._resize_edges(QPoint(x, y)) == attendu, (x, y)


def test_chaque_coin_a_son_curseur(fenetre):
    from PySide6.QtCore import Qt

    assert fenetre._cursor_for_edges(Qt.LeftEdge | Qt.TopEdge) == Qt.SizeFDiagCursor
    assert fenetre._cursor_for_edges(Qt.RightEdge | Qt.TopEdge) == Qt.SizeBDiagCursor


def test_les_bords_redimensionnent(fenetre):
    """Une fenetre sans cadre ne se redimensionne que si on l'ecrit."""
    from PySide6.QtCore import QPoint, Qt

    assert fenetre._resize_edges(QPoint(2, 2)) == (Qt.LeftEdge | Qt.TopEdge)
    assert fenetre._resize_edges(QPoint(fenetre.width() - 2, 2)) == (
        Qt.RightEdge | Qt.TopEdge
    )
    assert fenetre._resize_edges(QPoint(fenetre.width() // 2, 2)) == Qt.TopEdge
    assert not fenetre._resize_edges(QPoint(fenetre.width() // 2, fenetre.height() // 2))


# ================================================== plus de fond clair


def test_la_zone_defilante_est_transparente():
    """Le defaut signale: on voyait un fond clair entre les encadres."""
    from neuxelec.ui.neuxelec_dialog import STYLE

    assert "QScrollArea {" in STYLE.replace("{{", "{")
    assert "background: transparent" in STYLE


def test_aucun_pixel_clair_ne_reste(app):
    """Mesure, pas supposition: on compte les pixels clairs de la fenetre."""
    d = StimulationDialog(_electrodes(), 0, 0)
    d._add_response()
    d.show()
    QApplication.processEvents()

    image = d.grab().toImage()
    gris_par_defaut = 0

    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            pixel = image.pixelColor(x, y)
            # Le gris de Qt quand rien n'est peint.
            if (pixel.red(), pixel.green(), pixel.blue()) == (239, 239, 239):
                gris_par_defaut += 1

    d.close()
    assert gris_par_defaut == 0


def test_la_palette_est_celle_de_la_fenetre_principale():
    """Les trois valeurs des encadres de MainWindow.ui."""
    from neuxelec.ui.neuxelec_dialog import FIELD, LINE, PANEL

    assert PANEL == "#11131B"
    assert LINE == "#252834"
    assert FIELD == "#151720"


# ================================================== la case a cocher


def test_la_case_cochee_montre_une_croix_pas_un_aplat():
    """Demande explicite: une croix rose, pas une pastille pleine."""
    from neuxelec.ui.neuxelec_dialog import STYLE

    assert "neuxelec_checkbox_cross" in STYLE
    # L'aplat rose d'avant: le fond d'une case cochee est celui d'un champ.
    assert "background-color: #FF487D;\n}" not in STYLE


def test_la_croix_est_celle_de_l_application():
    import os

    from neuxelec.ui.neuxelec_dialog import CHECK_CROSS

    assert os.path.exists(CHECK_CROSS)
    assert CHECK_CROSS.endswith("neuxelec_checkbox_cross.svg")


def test_les_fleches_sont_celles_de_l_application():
    """Un caractere fleche depend de la police: parfois il n'y en a pas."""
    import os

    from neuxelec.ui.neuxelec_dialog import SPIN_DOWN, SPIN_LEFT, SPIN_RIGHT, SPIN_UP

    for chemin in (SPIN_UP, SPIN_DOWN, SPIN_LEFT, SPIN_RIGHT):
        assert os.path.exists(chemin), chemin


def test_les_spinbox_ont_leurs_fleches():
    """Sans regle, Qt dessine deux points gris a la place."""
    from neuxelec.ui.neuxelec_dialog import STYLE

    for regle in ("QSpinBox::up-arrow", "QDoubleSpinBox::down-arrow"):
        assert regle in STYLE

    assert "spin_up.svg" in STYLE
    assert "spin_down.svg" in STYLE


def test_la_barre_de_defilement_est_celle_du_logiciel():
    """Le meme trait que dans la page oblique et la reconstruction."""
    from neuxelec.ui.neuxelec_dialog import ROSE, STYLE

    assert "QScrollBar::handle:vertical" in STYLE
    assert "#3B3E48" in STYLE
    assert f"border: 1px solid {ROSE}" in STYLE


# ================================================== NA dans la saisie


def test_les_quatre_champs_du_protocole_proposent_NA(fenetre):
    """Demande explicite: pouvoir dire qu'on n'a pas l'information."""
    from neuxelec.utils import stimulation as st

    assert fenetre.spn_current.specialValueText() == st.NOT_AVAILABLE
    assert fenetre.spn_pulse.specialValueText() == st.NOT_AVAILABLE
    assert fenetre.spn_train.specialValueText() == st.NOT_AVAILABLE
    assert fenetre.cmb_frequency.findText(st.NOT_AVAILABLE) >= 0


def test_un_champ_au_minimum_s_enregistre_non_note(fenetre):
    fenetre.spn_current.setValue(fenetre.spn_current.minimum())
    fenetre.spn_pulse.setValue(fenetre.spn_pulse.minimum())
    fenetre.spn_train.setValue(fenetre.spn_train.minimum())
    carte = fenetre.record()
    assert carte["intensity_ma"] is None
    assert carte["pulse_width_us"] is None
    assert carte["train_duration_s"] is None


def test_une_frequence_NA_s_enregistre_non_notee(fenetre):
    from neuxelec.utils import stimulation as st

    fenetre.cmb_frequency.setCurrentText(st.NOT_AVAILABLE)
    assert fenetre.record()["frequency_hz"] is None


def test_une_frequence_NA_ne_remplit_rien(fenetre):
    """Rien a deduire d'une frequence inconnue."""
    from neuxelec.utils import stimulation as st

    fenetre.spn_pulse.setValue(250)
    fenetre.cmb_frequency.setCurrentText(st.NOT_AVAILABLE)
    assert fenetre.spn_pulse.value() == 250


def test_le_champ_affiche_bien_NA(fenetre):
    fenetre.spn_current.setValue(fenetre.spn_current.minimum())
    assert fenetre.spn_current.text() == "NA"


def test_une_carte_non_notee_se_relit(app):
    from neuxelec.utils import stimulation as st

    carte = st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        frequency_hz=st.NOT_SET,
        intensity_ma=st.NOT_SET,
        pulse_width_us=st.NOT_SET,
        train_duration_s=st.NOT_SET,
    )
    d = StimulationDialog(_electrodes(), 0, 0, record=carte)
    assert d.cmb_frequency.currentText() == st.NOT_AVAILABLE
    assert d.record()["intensity_ma"] is None
    d.close()


def test_un_courant_non_note_n_avertit_pas_sur_la_charge(fenetre):
    fenetre.spn_current.setValue(fenetre.spn_current.minimum())
    assert not fenetre.lbl_charge.isVisibleTo(fenetre)


# ================================================== reduire la fenetre


def test_la_fenetre_porte_un_bouton_reduire(fenetre):
    """Sans lui, une fenetre sans cadre ne peut que se fermer."""
    assert fenetre.header.btn_minimise is not None
    assert fenetre.header.btn_minimise.isEnabled()


def test_elle_est_une_vraie_fenetre_pas_un_simple_dialogue(fenetre):
    """C'est ce qui lui donne sa place dans la barre des taches."""
    from PySide6.QtCore import Qt

    assert bool(fenetre.windowFlags() & Qt.Window)
    assert bool(fenetre.windowFlags() & Qt.WindowMinimizeButtonHint)


def test_reduire_ne_la_ferme_pas(fenetre):
    fenetre.show()
    QApplication.processEvents()
    fenetre.showMinimized()
    QApplication.processEvents()
    assert fenetre.isMinimized()
    assert not fenetre.isHidden()
