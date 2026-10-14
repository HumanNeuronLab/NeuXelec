# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le modele des resultats de stimulation: vocabulaire, carte, filtres.

CE QUE CES TESTS PROTEGENT

Le vocabulaire est une synthese de la litterature, pas une norme: il
n'existe pas de classification standard des reponses evoquees. Les tests
qui suivent figent donc les quelques points ou se tromper coute cher.

1. Les onze categories du consensus EStiMapp sont toutes presentes.
   Celles que l'on oublie spontanement sont language, vestibular,
   autonomic, affective et cognitive.
2. Chaque liste finit par OTHER. Sans cela une reponse hors vocabulaire
   serait perdue, et le vocabulaire etant incomplet par nature, cela
   arrivera.
3. La localisation depend de la categorie: un corps pour le moteur et le
   somatosensoriel, un champ visuel pour le visuel, une oreille pour
   l'auditif, rien pour le reste. C'est ce qui permet a la fenetre de
   saisie de ne montrer qu'un seul champ au lieu de les demander tous.
4. Le protocole se remplit depuis la frequence, d'apres la Table 2 de
   l'ACNS, pour qu'il ne reste a saisir que ce qui differe.
5. Une paire inhabituelle avertit, elle ne refuse pas: l'ACNS classe les
   paires non adjacentes, celles a cheval sur deux electrodes et le
   monopolaire parmi ses questions non resolues, donc pratiquees. Seul un
   contact contre lui-meme est impossible.
6. Un couple teste sans reponse est une donnee, pas une absence de
   donnee.
"""

from __future__ import annotations

import pytest

from neuxelec.utils import stimulation as st

ONZE_CATEGORIES = {
    "motor",
    "language",
    "somatosensory",
    "visual",
    "auditory",
    "olfactory_gustatory",
    "vestibular",
    "autonomic",
    "affective",
    "cognitive",
    "other",
}


def _electrodes():
    """Deux electrodes, A a 8 contacts et B a 4."""
    return [
        {"name": "A", "contacts_lps": [[float(i), 0.0, 0.0] for i in range(8)]},
        {"name": "B", "contacts_lps": [[0.0, float(i), 10.0] for i in range(4)]},
    ]


# ------------------------------------------------- le vocabulaire


def test_les_onze_categories_du_consensus_sont_la():
    assert {c.key for c in st.CATEGORIES} == ONZE_CATEGORIES


@pytest.mark.parametrize(
    "oubliee", ["language", "vestibular", "autonomic", "affective", "cognitive"]
)
def test_les_categories_qu_on_oublie_sont_presentes(oubliee):
    assert st.category(oubliee) is not None


@pytest.mark.parametrize("cat", st.CATEGORIES, ids=lambda c: c.key)
def test_chaque_categorie_finit_par_other(cat):
    assert cat.descriptors[-1] == st.OTHER


@pytest.mark.parametrize("liste", [st.BODY_PARTS, st.VISUAL_FIELDS, st.EARS])
def test_chaque_localisation_finit_par_other(liste):
    assert liste[-1] == st.OTHER


def test_une_categorie_inconnue_ne_leve_pas():
    assert st.category("telepathie") is None


def test_le_deja_vu_est_cognitif():
    """Il n'est pas une categorie, c'est un phenomene mnesique."""
    descripteurs = st.category("cognitive").descriptors
    assert any("Deja-vu" in d for d in descripteurs)
    assert any("Jamais-vu" in d for d in descripteurs)


def test_l_illusion_et_l_hallucination_sont_distinguees():
    """Le glossaire ILAE les separe: l'illusion deforme un percept reel,
    l'hallucination n'a aucun stimulus externe."""
    visuels = st.category("visual").descriptors
    assert any("hallucination" in d.lower() for d in visuels)
    assert any("illusion" in d.lower() for d in visuels)


def test_la_sensation_cephalique_a_une_place():
    """Une aura frequente, absente des onze categories."""
    assert any(
        "Cephalic" in d for d in st.category("somatosensory").descriptors
    )


# --------------------------------------- la localisation suit la categorie


@pytest.mark.parametrize("cat", ["motor", "somatosensory"])
def test_le_moteur_et_le_sensitif_se_localisent_sur_le_corps(cat):
    assert st.localisation_values(cat) == st.BODY_PARTS


def test_le_visuel_se_localise_dans_le_champ():
    assert st.localisation_values("visual") == st.VISUAL_FIELDS


def test_l_auditif_se_localise_sur_une_oreille():
    assert st.localisation_values("auditory") == st.EARS


@pytest.mark.parametrize(
    "cat", ["language", "vestibular", "autonomic", "affective", "cognitive"]
)
def test_les_autres_ne_demandent_pas_de_localisation(cat):
    assert st.localisation_values(cat) == ()


def test_seul_le_moteur_est_signe():
    """Positif, un mouvement apparait; negatif, un mouvement en cours
    s'arrete. L'ACNS demande cette distinction d'abord."""
    signes = {c.key for c in st.CATEGORIES if c.signed}
    assert signes == {"motor"}


# ----------------------------------------------------- le protocole


def test_un_hertz_remplit_le_protocole_bas():
    p = st.default_protocol(1.0)
    assert p == {"pulse_width_us": 500, "train_duration_s": 30.0, "intensity_ma": 3.0}


@pytest.mark.parametrize("hz", [50.0, 60.0])
def test_la_haute_frequence_remplit_le_protocole_court(hz):
    p = st.default_protocol(hz)
    assert p["pulse_width_us"] == 300
    assert p["train_duration_s"] == 4.0


def test_une_frequence_illisible_retombe_sur_le_bas():
    assert st.default_protocol("beaucoup")["pulse_width_us"] == 500


def test_le_protocole_par_defaut_est_une_copie():
    """Sinon modifier une carte changerait le defaut des suivantes."""
    p = st.default_protocol(1.0)
    p["intensity_ma"] = 99.0
    assert st.default_protocol(1.0)["intensity_ma"] == 3.0


# ------------------------------------------------- l'avertissement de charge


def test_un_courant_usuel_n_avertit_pas():
    assert st.charge_warning(3.0, 500) is None


def test_un_courant_fort_a_large_impulsion_avertit():
    message = st.charge_warning(8.0, 300)
    assert message is not None
    assert "charge density" in message


def test_un_courant_fort_a_impulsion_breve_n_avertit_pas():
    """La charge est le produit du courant par la duree."""
    assert st.charge_warning(8.0, 100) is None


def test_au_dela_de_la_plage_proposee_on_avertit_toujours():
    assert "0.5-10 mA" in st.charge_warning(15.0, 100)


def test_un_courant_illisible_ne_leve_pas():
    assert st.charge_warning(None, 300) is None


# ------------------------------------------------------- la paire


def test_une_paire_adjacente_ne_dit_rien():
    assert st.pair_warning(_electrodes(), 0, 0, 0, 1) is None


def test_une_paire_non_adjacente_avertit():
    assert "not adjacent" in st.pair_warning(_electrodes(), 0, 0, 0, 3)


def test_une_paire_a_cheval_sur_deux_electrodes_avertit():
    message = st.pair_warning(_electrodes(), 0, 0, 1, 0)
    assert "two electrodes" in message


def test_le_monopolaire_n_avertit_pas():
    assert st.pair_warning(_electrodes(), 0, 0, None, None) is None


def test_un_contact_contre_lui_meme_est_refuse():
    """Le seul cas impossible."""
    assert st.pair_error(0, 2, 0, 2) is not None


def test_une_paire_valide_n_a_pas_d_erreur():
    assert st.pair_error(0, 2, 0, 3) is None


def test_le_meme_rang_sur_deux_electrodes_est_valide():
    assert st.pair_error(0, 2, 1, 2) is None


# --------------------------------------------- lire un nom de contact


def test_un_nom_de_contact_se_lit():
    assert st.parse_contact_name("A3", _electrodes()) == (0, 2)


def test_la_casse_et_les_espaces_sont_pardonnes():
    assert st.parse_contact_name("  b2 ", _electrodes()) == (1, 1)


def test_un_contact_hors_plage_est_refuse():
    """B n'a que 4 contacts."""
    assert st.parse_contact_name("B9", _electrodes()) is None


def test_une_electrode_inconnue_est_refusee():
    assert st.parse_contact_name("Z1", _electrodes()) is None


def test_un_nom_sans_numero_est_refuse():
    assert st.parse_contact_name("A", _electrodes()) is None


def test_un_texte_vide_est_refuse():
    assert st.parse_contact_name("", _electrodes()) is None


def test_le_contact_zero_est_refuse():
    """Les etiquettes comptent a partir de 1."""
    assert st.parse_contact_name("A0", _electrodes()) is None


def test_le_nom_le_plus_long_gagne():
    """Avec une electrode A et une electrode A1, "A12" est le contact 12
    de A, pas le contact 2 de A1... et inversement si A1 existe."""
    electrodes = [
        {"name": "A", "contacts_lps": [[0.0, 0.0, 0.0]] * 15},
        {"name": "A1", "contacts_lps": [[0.0, 0.0, 0.0]] * 4},
    ]
    assert st.parse_contact_name("A12", electrodes) == (1, 1)
    assert st.parse_contact_name("A9", electrodes) == (0, 8)


def test_l_etiquette_d_un_contact_compte_depuis_un():
    assert st.contact_name("A", 0) == "A1"


# ------------------------------------------------------- la carte


def test_une_carte_porte_la_frequence_et_l_impulsion():
    """Les deux champs sans lesquels une carte est illisible."""
    r = st.new_record(electrode="A", contact=0, contact_b=1, electrode_b="A")
    assert r["frequency_hz"] == 1.0
    assert r["pulse_width_us"] == 500


def test_le_protocole_se_remplit_depuis_la_frequence():
    r = st.new_record(electrode="A", contact=0, frequency_hz=50.0)
    assert r["intensity_ma"] == 2.0
    assert r["train_duration_s"] == 4.0


def test_une_valeur_donnee_a_la_main_gagne_sur_le_defaut():
    r = st.new_record(electrode="A", contact=0, frequency_hz=50.0, intensity_ma=5.5)
    assert r["intensity_ma"] == 5.5


def test_une_carte_porte_l_habituel_et_la_reproductibilite():
    r = st.new_record(electrode="A", contact=0)
    assert "habitual" in r
    assert "reproducibility" in r


def test_une_carte_neuve_est_datee():
    assert st.new_record(electrode="A", contact=0)["created"]


def test_les_identifiants_se_suivent():
    assert st.next_id([]) == "stim-1"
    assert st.next_id([{"id": "stim-1"}, {"id": "stim-4"}]) == "stim-5"


def test_un_identifiant_etranger_ne_casse_pas_la_suite():
    assert st.next_id([{"id": "autre"}, {"id": "stim-2"}]) == "stim-3"


def test_les_reponses_sont_des_blocs_independants():
    """Deux reponses a une stimulation gardent chacune sa localisation."""
    r = st.new_record(
        electrode="A",
        contact=0,
        responses=[
            st.new_response("motor", "Clonic jerks", location="Hand", laterality="contralateral"),
            st.new_response("visual", "Phosphenes", location="Left hemifield"),
        ],
    )
    assert r["responses"][0]["location"] == "Hand"
    assert r["responses"][1]["location"] == "Left hemifield"


def test_une_carte_ne_partage_pas_ses_listes():
    """Deux cartes construites de suite doivent etre independantes."""
    a = st.new_record(electrode="A", contact=0, events=["spikes"])
    b = st.new_record(electrode="A", contact=1)
    a["events"].append("after_discharges")
    assert b["events"] == []


# ---------------------------------------------- teste et muet


def test_un_couple_sans_evenement_ni_reponse_est_muet():
    assert st.is_silent(st.new_record(electrode="A", contact=0))


def test_une_post_decharge_suffit_a_ne_plus_etre_muet():
    r = st.new_record(electrode="A", contact=0, events=["after_discharges"])
    assert not st.is_silent(r)


def test_une_reponse_suffit_a_ne_plus_etre_muet():
    r = st.new_record(
        electrode="A", contact=0, responses=[st.new_response("motor", "Myoclonus")]
    )
    assert not st.is_silent(r)


def test_le_resume_d_un_couple_muet_le_dit_avec_son_intensite():
    """"Pas de reponse" sans l'intensite atteinte n'est pas une donnee."""
    r = st.new_record(electrode="A", contact=0, contact_b=1, electrode_b="A", intensity_ma=5.0)
    ligne = st.summary_line(r)
    assert "no response" in ligne
    assert "5 mA" in ligne


# ----------------------------------------------- les quatre niveaux de crise


@pytest.mark.parametrize(
    "niveau",
    [
        "seizure_electroclinical",
        "seizure_aura",
        "seizure_subclinical",
        "seizure_atypical",
    ],
)
def test_les_quatre_niveaux_de_crise_existent(niveau):
    assert niveau in st.EVENT_LABELS


def test_les_decharges_ne_sont_pas_des_crises():
    assert "after_discharges" not in st.SEIZURE_EVENTS
    assert "spikes" not in st.SEIZURE_EVENTS


def test_une_crise_est_reconnue():
    r = st.new_record(electrode="A", contact=0, events=["seizure_aura"])
    assert st.has_seizure(r)


def test_une_post_decharge_seule_n_est_pas_une_crise():
    r = st.new_record(electrode="A", contact=0, events=["after_discharges"])
    assert not st.has_seizure(r)


# ------------------------------------------------- les etiquettes


def test_une_paire_bipolaire_se_nomme():
    r = st.new_record(electrode="A", contact=0, electrode_b="A", contact_b=1)
    assert st.pair_label(r) == "A1-A2"


def test_une_paire_a_cheval_se_nomme_aussi():
    r = st.new_record(electrode="A", contact=7, electrode_b="B", contact_b=0)
    assert st.pair_label(r) == "A8-B1"


def test_le_monopolaire_nomme_sa_reference():
    r = st.new_record(
        electrode="A", contact=0, polarity="monopolar", reference="scalp Fz"
    )
    assert st.pair_label(r) == "A1 vs scalp Fz"


def test_le_monopolaire_sans_reference_se_nomme_quand_meme():
    r = st.new_record(electrode="A", contact=0, polarity="monopolar")
    assert st.pair_label(r) == "A1 (monopolar)"


def test_une_reponse_se_lit_en_une_ligne():
    reponse = st.new_response(
        "somatosensory", "Tingling or paresthesia", location="Hand", laterality="contralateral"
    )
    ligne = st.response_label(reponse)
    assert "Somatosensory" in ligne
    assert "Tingling" in ligne
    assert "contralateral hand" in ligne


def test_other_est_remplace_par_son_texte_libre():
    reponse = st.new_response("other", st.OTHER, other="une impression indicible")
    assert "une impression indicible" in st.response_label(reponse)


def test_le_signe_moteur_parait_dans_la_ligne():
    reponse = st.new_response("motor", "Movement arrest", sign="negative")
    assert "negative" in st.response_label(reponse)


def test_le_resume_cite_la_paire_le_protocole_et_la_reponse():
    r = st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        frequency_hz=50.0,
        intensity_ma=2.0,
        responses=[st.new_response("language", "Speech arrest")],
    )
    ligne = st.summary_line(r)
    assert "A1-A2" in ligne
    assert "50 Hz" in ligne
    assert "2 mA" in ligne
    assert "Speech arrest" in ligne


# -------------------------------------------------------- les filtres


def _trois_cartes():
    return [
        st.new_record(
            electrode="A",
            contact=0,
            electrode_b="A",
            contact_b=1,
            frequency_hz=1.0,
            intensity_ma=3.0,
            events=["seizure_electroclinical"],
            habitual="identical",
            reproducibility="reproduced",
            responses=[st.new_response("motor", "Clonic jerks", location="Hand")],
        ),
        st.new_record(
            electrode="A",
            contact=2,
            electrode_b="A",
            contact_b=3,
            frequency_hz=50.0,
            intensity_ma=1.0,
            events=["after_discharges"],
            habitual="no",
            reproducibility="single_trial",
            responses=[st.new_response("visual", "Phosphenes")],
        ),
        st.new_record(
            electrode="B",
            contact=0,
            electrode_b="B",
            contact_b=1,
            frequency_hz=50.0,
            intensity_ma=5.0,
        ),
    ]


def test_sans_filtre_tout_passe():
    cartes = _trois_cartes()
    assert len(st.filter_records(cartes, st.empty_filters())) == 3


def test_un_filtre_vide_passe_aussi():
    assert len(st.filter_records(_trois_cartes(), None)) == 3


def test_le_filtre_d_amperage_minimum():
    f = st.empty_filters()
    f["min_intensity_ma"] = 3.0
    gardees = st.filter_records(_trois_cartes(), f)
    assert {r["intensity_ma"] for r in gardees} == {3.0, 5.0}


def test_le_filtre_d_amperage_maximum():
    f = st.empty_filters()
    f["max_intensity_ma"] = 3.0
    gardees = st.filter_records(_trois_cartes(), f)
    assert {r["intensity_ma"] for r in gardees} == {3.0, 1.0}


def test_le_filtre_de_frequence():
    f = st.empty_filters()
    f["frequencies"] = {50.0}
    assert len(st.filter_records(_trois_cartes(), f)) == 2


def test_le_filtre_d_evenement():
    f = st.empty_filters()
    f["events"] = {"after_discharges"}
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 1
    assert gardees[0]["electrode"] == "A"
    assert gardees[0]["contact"] == 2


def test_deux_evenements_demandes_veulent_dire_l_un_ou_l_autre():
    f = st.empty_filters()
    f["events"] = {"after_discharges", "seizure_electroclinical"}
    assert len(st.filter_records(_trois_cartes(), f)) == 2


def test_le_filtre_de_categorie_de_reponse():
    f = st.empty_filters()
    f["categories"] = {"visual"}
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 1
    assert gardees[0]["responses"][0]["category"] == "visual"


def test_le_filtre_de_l_aura_habituelle():
    """Le signe le plus localisateur, d'apres le survey international."""
    f = st.empty_filters()
    f["habitual"] = {"identical"}
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 1
    assert gardees[0]["habitual"] == "identical"


def test_le_filtre_des_reponses_reproduites():
    f = st.empty_filters()
    f["only_reproduced"] = True
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 1
    assert gardees[0]["reproducibility"] == "reproduced"


def test_on_peut_ecarter_les_couples_muets():
    f = st.empty_filters()
    f["include_silent"] = False
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 2
    assert all(not st.is_silent(r) for r in gardees)


def test_les_couples_muets_sont_gardes_par_defaut():
    """Teste sans reponse est un resultat."""
    assert any(st.is_silent(r) for r in st.filter_records(_trois_cartes(), st.empty_filters()))


def test_les_filtres_se_cumulent():
    f = st.empty_filters()
    f["frequencies"] = {50.0}
    f["min_intensity_ma"] = 3.0
    gardees = st.filter_records(_trois_cartes(), f)
    assert len(gardees) == 1
    assert gardees[0]["electrode"] == "B"


# ----------------------------------------------- ou dessiner la paire


def test_le_point_dessine_est_le_milieu_de_la_paire():
    """En bipolaire la densite de courant est maximale entre les deux
    contacts, pas sur l'un des deux."""
    r = st.new_record(electrode="A", contact=0, electrode_b="A", contact_b=2)
    assert st.pair_midpoint_lps(r, _electrodes()) == [1.0, 0.0, 0.0]


def test_le_monopolaire_se_dessine_sur_son_contact():
    r = st.new_record(electrode="A", contact=3, polarity="monopolar")
    assert st.pair_midpoint_lps(r, _electrodes()) == [3.0, 0.0, 0.0]


def test_une_paire_a_cheval_a_aussi_un_milieu():
    r = st.new_record(electrode="A", contact=0, electrode_b="B", contact_b=0)
    assert st.pair_midpoint_lps(r, _electrodes()) == [0.0, 0.0, 5.0]


def test_une_electrode_disparue_ne_leve_pas():
    """Une carte peut survivre a la suppression de son electrode."""
    r = st.new_record(electrode="Z", contact=0)
    assert st.pair_midpoint_lps(r, _electrodes()) is None


def test_un_second_contact_disparu_retombe_sur_le_premier():
    r = st.new_record(electrode="A", contact=1, electrode_b="Z", contact_b=0)
    assert st.pair_midpoint_lps(r, _electrodes()) == [1.0, 0.0, 0.0]


# ------------------------------------------------- la carte d'identite


def _carte_riche():
    return st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        anatomy=["A1 ctx-lh-hippocampus", "A2 wm-lh-temporal"],
        frequency_hz=50.0,
        intensity_ma=2.5,
        threshold_ma=1.5,
        behavioural_state="asleep",
        asm="reduced",
        task="denomination",
        events=["after_discharges", "seizure_electroclinical"],
        habitual="identical",
        reproducibility="reproduced",
        ad_location="A1-A2, A5",
        ad_remote=True,
        ad_evolution="extension vers A5",
        aborted=True,
        responses=[
            st.new_response(
                "language", "Speech arrest", note="revenu en deux secondes"
            ),
            st.new_response("motor", "Movement arrest", sign="negative", location="Hand"),
        ],
        notes="patient distrait",
        operator="JV",
        created="2026-10-12T10:00:00",
    )


def _valeur(carte, etiquette):
    for label, value in st.card_fields(carte):
        if label == etiquette:
            return value
    return None


def test_la_carte_commence_par_la_paire():
    assert st.card_fields(_carte_riche())[0] == ("Pair", "A1-A2")


def test_la_carte_donne_le_protocole_entier():
    """Les quatre nombres sans lesquels elle ne se relit pas."""
    protocole = _valeur(_carte_riche(), "Protocol")
    assert "50 Hz" in protocole
    assert "2.5 mA" in protocole
    assert "300 µs" in protocole
    assert "train 4 s" in protocole


def test_la_carte_nomme_les_deux_contacts():
    anatomie = _valeur(_carte_riche(), "Anatomy")
    assert "ctx-lh-hippocampus" in anatomie
    assert "wm-lh-temporal" in anatomie


def test_la_carte_porte_l_habituel_et_la_reproductibilite():
    carte = _carte_riche()
    assert "Identical" in _valeur(carte, "Habitual event")
    assert "Reproduced" in _valeur(carte, "Reproducibility")


def test_la_carte_decrit_la_post_decharge():
    carte = _carte_riche()
    assert "remote" in _valeur(carte, "Discharge seen at")
    assert "A5" in _valeur(carte, "Evolution")
    assert _valeur(carte, "Interrupted") is not None


def test_la_carte_numerote_les_reponses():
    carte = _carte_riche()
    assert "Speech arrest" in _valeur(carte, "Response")
    assert "Movement arrest" in _valeur(carte, "Response 2")


def test_une_note_de_reponse_suit_sa_reponse():
    assert "revenu en deux secondes" in _valeur(_carte_riche(), "Response")


def test_un_champ_vide_ne_parait_pas():
    """Une ligne vide sur une carte clinique est du bruit."""
    etiquettes = [label for label, _ in st.card_fields(st.new_record(electrode="A", contact=0))]
    assert "Task" not in etiquettes
    assert "Notes" not in etiquettes
    assert "Anatomy" not in etiquettes


def test_un_champ_non_precise_ne_parait_pas():
    carte = st.new_record(electrode="A", contact=0, behavioural_state="unspecified")
    assert _valeur(carte, "Patient") is None


def test_une_paire_muette_le_dit_avec_son_intensite():
    carte = st.new_record(electrode="A", contact=0, intensity_ma=5.0)
    assert _valeur(carte, "Result") == "tested, no response at 5 mA"


def test_une_paire_qui_a_repondu_n_a_pas_de_ligne_resultat():
    assert _valeur(_carte_riche(), "Result") is None


def test_la_carte_porte_sa_provenance():
    carte = _carte_riche()
    assert _valeur(carte, "Interpreted by") == "JV"
    assert "2026-10-12" in _valeur(carte, "Recorded")


def test_la_carte_se_lit_en_texte():
    texte = st.card_text(_carte_riche())
    assert texte.startswith("Pair: A1-A2")
    assert "Speech arrest" in texte


def test_une_carte_vide_ne_leve_pas():
    assert st.card_fields({})
    assert st.card_text(None)


# ------------------------------------------- un parametre non note


def test_un_protocole_non_note_reste_vide():
    """Un protocole inconnu n'est pas un protocole a zero: inventer un
    chiffre ferait croire a une mesure."""
    carte = st.new_record(
        electrode="A",
        contact=0,
        frequency_hz=st.NOT_SET,
        intensity_ma=st.NOT_SET,
        pulse_width_us=st.NOT_SET,
        train_duration_s=st.NOT_SET,
    )
    assert carte["frequency_hz"] is None
    assert carte["intensity_ma"] is None
    assert carte["pulse_width_us"] is None
    assert carte["train_duration_s"] is None


def test_le_defaut_reste_le_defaut():
    """None veut dire "prends le defaut", NOT_SET veut dire "non note"."""
    carte = st.new_record(electrode="A", contact=0, frequency_hz=50.0)
    assert carte["intensity_ma"] == 2.0


def test_une_valeur_non_notee_s_affiche_NA():
    carte = st.new_record(
        electrode="A", contact=0, frequency_hz=st.NOT_SET, intensity_ma=st.NOT_SET
    )
    assert "NA" in st.summary_line(carte)


def test_la_fiche_affiche_NA_dans_le_protocole():
    carte = st.new_record(
        electrode="A",
        contact=0,
        frequency_hz=st.NOT_SET,
        intensity_ma=st.NOT_SET,
        pulse_width_us=st.NOT_SET,
        train_duration_s=st.NOT_SET,
    )
    protocole = _valeur(carte, "Protocol")
    assert protocole.count("NA") == 4


def test_un_protocole_a_moitie_note_montre_les_deux():
    carte = st.new_record(
        electrode="A", contact=0, frequency_hz=50.0, intensity_ma=st.NOT_SET
    )
    protocole = _valeur(carte, "Protocol")
    assert "50 Hz" in protocole
    assert "NA" in protocole


def test_la_mise_en_forme_d_une_valeur():
    assert st.amount(2.5, "mA") == "2.5 mA"
    assert st.amount(None, "mA") == "NA"
    assert st.amount("illisible") == "NA"
    assert st.amount(3) == "3"


def test_un_courant_non_note_est_ecarte_par_une_borne():
    """Il ne peut etre ni au-dessus ni au-dessous: le compter pour zero
    le ferait passer pour le plus faible de tous."""
    carte = st.new_record(electrode="A", contact=0, intensity_ma=st.NOT_SET)
    f = st.empty_filters()
    f["max_intensity_ma"] = 5.0
    assert st.matches_filters(carte, f) is False


def test_une_frequence_non_notee_est_ecartee_par_le_filtre():
    carte = st.new_record(electrode="A", contact=0, frequency_hz=st.NOT_SET)
    f = st.empty_filters()
    f["frequencies"] = {1.0}
    assert st.matches_filters(carte, f) is False


def test_sans_filtre_une_carte_non_notee_passe():
    carte = st.new_record(electrode="A", contact=0, intensity_ma=st.NOT_SET)
    assert st.matches_filters(carte, st.empty_filters()) is True


def test_sans_courant_ni_impulsion_aucun_avertissement_de_charge():
    assert st.charge_warning(None, None) is None
    assert st.charge_warning(None, 300) is None
    assert st.charge_warning(8.0, None) is None


def test_un_couple_muet_sans_courant_le_dit_quand_meme():
    carte = st.new_record(electrode="A", contact=0, intensity_ma=st.NOT_SET)
    assert "NA" in _valeur(carte, "Result")
