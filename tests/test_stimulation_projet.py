"""Les resultats de stimulation survivent a la fermeture du projet.

POURQUOI DANS LE PROJET ET PAS AILLEURS

Une carte de stimulation est un document clinique saisi a la main. La
perdre, c'est perdre une heure d'examen au lit du patient, qu'aucun
recalcul ne reconstruit.

LA COMPATIBILITE EN ARRIERE

Un projet ecrit avant cette fonction n'a pas de bloc "stimulations". Il
doit se relire comme n'en ayant aucune, pas lever.
"""

from __future__ import annotations

import json

from neuxelec import project_io
from neuxelec.utils import stimulation as st


class _Etat:
    """Le strict necessaire pour un aller-retour."""

    def __init__(self, stimulations=None):
        self.patient_id = "TEST"
        self.stimulation_display: dict = {}
        self.electrodes = [
            {"name": "A", "contacts_lps": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]}
        ]
        self.stimulations = list(stimulations or [])


def _carte():
    return st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        record_id="stim-1",
        frequency_hz=50.0,
        intensity_ma=2.5,
        events=["after_discharges", "seizure_aura"],
        habitual="partial",
        reproducibility="reproduced",
        responses=[
            st.new_response(
                "somatosensory",
                "Tingling or paresthesia",
                location="Hand",
                laterality="contralateral",
            )
        ],
        notes="le patient etait distrait",
    )


def _aller_retour(etat):
    """Ecrire puis relire par le vrai chemin du projet."""
    data = project_io.build_project_dict_from_state(etat)
    # Passer par JSON: c'est ce que fait l'ecriture sur disque, et c'est la
    # qu'un objet non serialisable se ferait voir.
    data = json.loads(json.dumps(data))
    relu = _Etat()
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    return relu


# ------------------------------------------------- l'aller-retour


def test_une_carte_survit_a_l_aller_retour():
    relu = _aller_retour(_Etat([_carte()]))
    assert len(relu.stimulations) == 1


def test_elle_revient_identique():
    carte = _carte()
    relu = _aller_retour(_Etat([carte]))
    assert relu.stimulations[0] == carte


def test_le_protocole_revient():
    relu = _aller_retour(_Etat([_carte()]))
    carte = relu.stimulations[0]
    assert carte["frequency_hz"] == 50.0
    assert carte["intensity_ma"] == 2.5
    assert carte["pulse_width_us"] == 300


def test_les_evenements_multiples_reviennent():
    relu = _aller_retour(_Etat([_carte()]))
    assert set(relu.stimulations[0]["events"]) == {"after_discharges", "seizure_aura"}


def test_le_bloc_de_reponse_revient_entier():
    relu = _aller_retour(_Etat([_carte()]))
    reponse = relu.stimulations[0]["responses"][0]
    assert reponse["category"] == "somatosensory"
    assert reponse["location"] == "Hand"
    assert reponse["laterality"] == "contralateral"


def test_les_notes_reviennent():
    relu = _aller_retour(_Etat([_carte()]))
    assert relu.stimulations[0]["notes"] == "le patient etait distrait"


def test_plusieurs_cartes_gardent_leur_ordre():
    cartes = [
        st.new_record(electrode="A", contact=0, record_id="stim-1"),
        st.new_record(electrode="A", contact=1, record_id="stim-2"),
    ]
    relu = _aller_retour(_Etat(cartes))
    assert [c["id"] for c in relu.stimulations] == ["stim-1", "stim-2"]


# ------------------------------------------- les projets d'avant


def test_un_projet_sans_le_bloc_se_relit():
    """Le defaut a eviter: lever sur tous les projets existants."""
    etat = _Etat()
    data = project_io.build_project_dict_from_state(etat)
    data.pop("stimulations", None)
    relu = _Etat([_carte()])
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    assert relu.stimulations == []


def test_un_bloc_abime_se_relit_en_liste_vide():
    etat = _Etat()
    data = project_io.build_project_dict_from_state(etat)
    data["stimulations"] = "ceci n'est pas une liste"
    relu = _Etat()
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    assert relu.stimulations == []


def test_un_etat_sans_l_attribut_s_ecrit_quand_meme():
    """Une page ancienne peut tenir un etat sans cet attribut."""

    class _Vieux(_Etat):
        def __init__(self):
            super().__init__()
            del self.stimulations

    data = project_io.build_project_dict_from_state(_Vieux())
    assert data["stimulations"] == []


# ------------------------------------------- un projet neuf


def test_un_projet_neuf_a_le_bloc(tmp_path):
    chemin = project_io.create_empty_project_file(tmp_path / "neuf.nxp", "PATIENT")
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["stimulations"] == []


def test_l_etat_de_depart_a_une_liste_vide():
    from neuxelec.state import AppState

    assert AppState().stimulations == []


# ------------------------------------- les reglages d'affichage


def _etat_avec_affichage(affichage):
    etat = _Etat()
    etat.stimulation_display = dict(affichage)
    return etat


def test_les_reglages_d_affichage_survivent():
    """Les refaire a chaque ouverture serait la raison de ne pas s'en servir."""
    from neuxelec.utils import stimulation_display as sd

    reglages = sd.default_settings()
    reglages["colour_mode"] = sd.BY_RULES
    reglages["rules"] = sd.preset_rules("clinical")
    reglages["line_width_mm"] = 2.6

    relu = _aller_retour(_etat_avec_affichage(reglages))
    assert relu.stimulation_display["colour_mode"] == sd.BY_RULES
    assert relu.stimulation_display["line_width_mm"] == 2.6
    assert len(relu.stimulation_display["rules"]) == 4


def test_une_regle_relue_designe_encore_les_memes_cartes():
    """Les conditions contiennent des ensembles, que JSON ne connait pas."""
    from neuxelec.utils import stimulation_display as sd

    reglages = sd.default_settings()
    reglages["colour_mode"] = sd.BY_RULES
    reglages["rules"] = [
        sd.new_rule("habituelle", when={"habitual": {"identical"}}, colour="#AA0000")
    ]

    relu = _aller_retour(_etat_avec_affichage(reglages))
    carte = st.new_record(electrode="A", contact=0, habitual="identical")
    assert sd.style_for(carte, relu.stimulation_display)["colour"] == "#AA0000"


def test_un_projet_sans_reglages_se_relit():
    etat = _Etat()
    data = project_io.build_project_dict_from_state(etat)
    data.pop("stimulation_display", None)
    relu = _Etat()
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    assert relu.stimulation_display == {}


def test_des_reglages_abimes_se_relisent_en_vide():
    etat = _Etat()
    data = project_io.build_project_dict_from_state(etat)
    data["stimulation_display"] = "pas un dictionnaire"
    relu = _Etat()
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    assert relu.stimulation_display == {}


def test_un_projet_neuf_a_le_bloc_d_affichage(tmp_path):
    chemin = project_io.create_empty_project_file(tmp_path / "neuf2.nxp", "PATIENT")
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["stimulation_display"] == {}


def test_l_etat_de_depart_a_des_reglages_vides():
    from neuxelec.state import AppState

    assert AppState().stimulation_display == {}
