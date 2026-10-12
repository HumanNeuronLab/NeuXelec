"""Exporter les resultats de stimulation.

QUATRE FORMATS, DEUX USAGES

Un tableau (CSV, TSV) porte une ligne par paire stimulee, les reponses
rassemblees dans une case: c'est ce qu'attend un tableur ou le script
d'un collegue. Un rapport (TXT) imprime les fiches a la suite, pour le
dossier. JSON garde les enregistrements tels quels, reponses imbriquees
comprises: c'est le seul sans perte.

CE QUE CES TESTS PROTEGENT

1. Rien n'est recalcule a la sortie. Un champ jamais rempli sort vide,
   un protocole non note sort NA, jamais un zero silencieux.
2. Les contacts comptent a partir de 1, comme partout ailleurs.
3. Les coordonnees sont celles que l'application affiche.
4. Le JSON relu redonne exactement les memes fiches.
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from neuxelec.utils import stimulation as st
from neuxelec.utils import stimulation_export as se


def _electrodes():
    return [
        {"name": "A", "contacts_lps": [[float(i) * 2.0, 1.0, 3.0] for i in range(8)]},
        {"name": "B", "contacts_lps": [[0.0, float(i), 10.0] for i in range(4)]},
    ]


def _complete():
    return st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        record_id="stim-1",
        created="2026-10-12T10:00:00",
        anatomy=["A1 ctx-lh-hippocampus", "A2 wm-lh-temporal"],
        frequency_hz=50.0,
        intensity_ma=2.5,
        pulse_width_us=300,
        train_duration_s=4.0,
        threshold_ma=1.5,
        at_ad_threshold=True,
        behavioural_state="awake",
        asm="reduced",
        time_since_last_seizure="2 days",
        task="counting",
        events=["after_discharges", "seizure_aura"],
        habitual="identical",
        reproducibility="reproduced",
        ad_location="A1-A2",
        ad_remote=True,
        ad_evolution="spread to A5",
        aborted=True,
        responses=[
            st.new_response(
                "somatosensory",
                "Tingling or paresthesia",
                location="Hand",
                laterality="contralateral",
            ),
            st.new_response("cognitive", "Deja-vu (familiarity)"),
        ],
        notes="une note",
        operator="JV",
    )


def _muette():
    return st.new_record(
        electrode="B",
        contact=0,
        electrode_b="B",
        contact_b=1,
        record_id="stim-2",
        intensity_ma=5.0,
    )


def _non_notee():
    return st.new_record(
        electrode="A",
        contact=4,
        polarity="monopolar",
        reference="scalp Fz",
        record_id="stim-3",
        frequency_hz=st.NOT_SET,
        intensity_ma=st.NOT_SET,
        pulse_width_us=st.NOT_SET,
        train_duration_s=st.NOT_SET,
    )


def _ligne(record):
    return se.row_of(record, _electrodes())


# ------------------------------------------------- la ligne du tableau


def test_une_ligne_par_stimulation():
    lignes = se.rows_of([_complete(), _muette()], _electrodes())
    assert len(lignes) == 2


def test_toutes_les_colonnes_sont_la():
    ligne = _ligne(_complete())
    assert set(ligne) == set(se.COLUMNS)


def test_la_paire_et_les_contacts():
    ligne = _ligne(_complete())
    assert ligne["pair"] == "A1-A2"
    assert ligne["electrode_a"] == "A"
    assert ligne["label_a"] == "A1"
    assert ligne["label_b"] == "A2"


def test_les_contacts_comptent_a_partir_de_un():
    """Comme partout ailleurs: A1 est le contact numero 1."""
    ligne = _ligne(_complete())
    assert ligne["contact_a"] == 1
    assert ligne["contact_b"] == 2


def test_les_coordonnees_sont_celles_qu_on_voit():
    """L'etat garde du LPS, l'application montre du RAS."""
    ligne = _ligne(_complete())
    assert ligne["x_a"] == "-0.00" or ligne["x_a"] == "0.00"
    assert ligne["y_a"] == "-1.00"
    assert ligne["z_a"] == "3.00"
    assert ligne["x_b"] == "-2.00"


def test_l_anatomie_est_rangee_par_contact():
    ligne = _ligne(_complete())
    assert ligne["anatomy_a"] == "ctx-lh-hippocampus"
    assert ligne["anatomy_b"] == "wm-lh-temporal"


def test_le_protocole_sort_tel_quel():
    ligne = _ligne(_complete())
    assert ligne["frequency_hz"] == "50"
    assert ligne["intensity_ma"] == "2.5"
    assert ligne["pulse_width_us"] == "300"
    assert ligne["train_duration_s"] == "4"


def test_un_protocole_non_note_sort_NA():
    """Jamais un zero silencieux: NA se lit, zero ment."""
    ligne = _ligne(_non_notee())
    for colonne in ("frequency_hz", "intensity_ma", "pulse_width_us", "train_duration_s"):
        assert ligne[colonne] == "NA", colonne


def test_un_seuil_absent_sort_vide():
    """Absent n'est pas NA: on ne l'a pas cherche."""
    assert _ligne(_muette())["threshold_ma"] == ""


def test_le_monopolaire_n_a_pas_de_second_contact():
    ligne = _ligne(_non_notee())
    assert ligne["electrode_b"] == ""
    assert ligne["contact_b"] == ""
    assert ligne["x_b"] == ""
    assert ligne["reference"] == "scalp Fz"


def test_les_evenements_tiennent_dans_une_case():
    ligne = _ligne(_complete())
    assert "after_discharges" in ligne["events"]
    assert "seizure_aura" in ligne["events"]
    assert se.JOIN in ligne["events"]


def test_les_reponses_tiennent_dans_une_case():
    ligne = _ligne(_complete())
    assert ligne["n_responses"] == 2
    assert "somatosensory" in ligne["response_categories"]
    assert "cognitive" in ligne["response_categories"]
    assert se.JOIN in ligne["responses"]


def test_une_paire_muette_est_marquee():
    assert _ligne(_muette())["silent"] == "yes"
    assert _ligne(_complete())["silent"] == "no"


def test_les_oui_non_sont_lisibles():
    ligne = _ligne(_complete())
    assert ligne["at_ad_threshold"] == "yes"
    assert ligne["discharge_remote"] == "yes"
    assert ligne["interrupted"] == "yes"
    assert _ligne(_muette())["interrupted"] == "no"


def test_une_electrode_disparue_ne_leve_pas():
    carte = st.new_record(electrode="Z", contact=0, record_id="stim-9")
    ligne = se.row_of(carte, _electrodes())
    assert ligne["x_a"] == ""


def test_une_fiche_vide_ne_leve_pas():
    assert se.row_of({}, _electrodes())["pair"]


# ------------------------------------------------- les fichiers


def test_le_csv_se_relit(tmp_path):
    chemin = se.write_csv(
        tmp_path / "stim.csv", [_complete(), _muette()], _electrodes()
    )
    texte = chemin.read_text(encoding="utf-8")
    lignes = list(csv.DictReader(io.StringIO(texte)))

    assert len(lignes) == 2
    assert lignes[0]["pair"] == "A1-A2"
    assert lignes[1]["silent"] == "yes"


def test_le_csv_commence_par_ses_entetes(tmp_path):
    chemin = se.write_csv(tmp_path / "stim.csv", [_complete()], _electrodes())
    premiere = chemin.read_text(encoding="utf-8").splitlines()[0]
    assert premiere.split(",")[0] == "id"
    assert "pair" in premiere


def test_le_csv_n_a_pas_de_lignes_vides(tmp_path):
    """Sans newline="" chaque ligne en gagnerait une sous Windows."""
    chemin = se.write_csv(tmp_path / "stim.csv", [_complete(), _muette()], _electrodes())
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 3
    assert all(ligne.strip() for ligne in lignes)


def test_le_tsv_est_separe_par_des_tabulations(tmp_path):
    chemin = se.write_tsv(tmp_path / "stim.tsv", [_complete()], _electrodes())
    assert "\t" in chemin.read_text(encoding="utf-8").splitlines()[0]


def test_le_json_est_sans_perte(tmp_path):
    """Le seul format qui garde les reponses imbriquees."""
    depart = [_complete(), _muette()]
    chemin = se.write_json(tmp_path / "stim.json", depart, _electrodes())
    relu = json.loads(chemin.read_text(encoding="utf-8"))
    assert relu == depart


def test_le_rapport_imprime_les_fiches(tmp_path):
    chemin = se.write_report(tmp_path / "stim.txt", [_complete()], patient="TEST")
    texte = chemin.read_text(encoding="utf-8")
    assert "TEST" in texte
    assert "A1-A2" in texte
    assert "Protocol" in texte
    assert "Tingling" in texte


def test_le_rapport_compte_les_stimulations(tmp_path):
    chemin = se.write_report(tmp_path / "stim.txt", [_complete(), _muette()])
    assert "2 stimulation(s)" in chemin.read_text(encoding="utf-8")


def test_un_rapport_sans_stimulation_ne_leve_pas(tmp_path):
    chemin = se.write_report(tmp_path / "stim.txt", [])
    assert "0 stimulation(s)" in chemin.read_text(encoding="utf-8")


# ------------------------------------------------- le format suit le nom


@pytest.mark.parametrize(
    "nom, marqueur",
    [
        ("stim.csv", ","),
        ("stim.tsv", "\t"),
    ],
)
def test_l_extension_decide_du_tableau(tmp_path, nom, marqueur):
    chemin = se.write_any(tmp_path / nom, [_complete()], _electrodes())
    assert marqueur in chemin.read_text(encoding="utf-8").splitlines()[0]


def test_l_extension_json_donne_du_json(tmp_path):
    chemin = se.write_any(tmp_path / "stim.json", [_complete()], _electrodes())
    assert isinstance(json.loads(chemin.read_text(encoding="utf-8")), list)


def test_l_extension_txt_donne_un_rapport(tmp_path):
    chemin = se.write_any(
        tmp_path / "stim.txt", [_complete()], _electrodes(), patient="P1"
    )
    assert "P1" in chemin.read_text(encoding="utf-8")


def test_une_extension_inconnue_donne_du_csv(tmp_path):
    chemin = se.write_any(tmp_path / "stim.xyz", [_complete()], _electrodes())
    assert chemin.read_text(encoding="utf-8").splitlines()[0].startswith("id,")


def test_le_dossier_est_cree_au_besoin(tmp_path):
    chemin = se.write_csv(
        tmp_path / "nouveau" / "dossier" / "stim.csv", [_complete()], _electrodes()
    )
    assert chemin.exists()
