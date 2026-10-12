"""Les reglages d'affichage des stimulations, et les regles.

CE QUE CES TESTS PROTEGENT

1. Une regle est une condition plus un style, et la PREMIERE regle active
   qui correspond gagne. Sans cet ordre, deux regles qui se recouvrent
   donneraient un resultat imprevisible.
2. Un style laisse vide dans une regle retombe sur le reglage global:
   une regle qui ne change que la couleur ne doit pas avoir a repeter
   l'epaisseur et l'opacite.
3. Une carte qu'aucune regle ne reclame est dessinee en gris pale, pas
   effacee. Sinon une regle trop etroite ferait disparaitre une paire
   qui a bel et bien ete testee.
4. Les conditions traversent le JSON: elles contiennent des ensembles,
   que JSON ne connait pas.
"""

from __future__ import annotations

import json

import pytest

from neuxelec.utils import stimulation as st
from neuxelec.utils import stimulation_display as sd


def _habituelle():
    return st.new_record(
        electrode="A",
        contact=0,
        electrode_b="A",
        contact_b=1,
        events=["seizure_electroclinical"],
        habitual="identical",
        responses=[st.new_response("motor", "Clonic jerks")],
    )


def _visuelle():
    return st.new_record(
        electrode="A",
        contact=2,
        electrode_b="A",
        contact_b=3,
        intensity_ma=1.0,
        responses=[st.new_response("visual", "Phosphenes")],
    )


def _muette():
    return st.new_record(
        electrode="B", contact=0, electrode_b="B", contact_b=1, intensity_ma=5.0
    )


# ------------------------------------------------- les reglages par defaut


def test_les_reglages_par_defaut_dessinent_un_trait():
    assert sd.default_settings()["where"] == sd.WHERE_LINE


def test_la_couleur_par_defaut_suit_la_valeur_de_la_trouvaille():
    assert sd.default_settings()["colour_mode"] == sd.BY_FINDING


def test_les_reglages_par_defaut_sont_une_copie():
    a = sd.default_settings()
    a["where"] = sd.WHERE_CONTACTS
    assert sd.default_settings()["where"] == sd.WHERE_LINE


def test_la_liste_de_regles_part_vide():
    """Les preregleges se chargent d'un clic, ils ne s'imposent pas."""
    assert sd.default_settings()["rules"] == []


# ------------------------------------------------- la couleur selon le mode


def test_le_mode_trouvaille_reprend_le_classement():
    style = sd.style_for(_habituelle(), {"colour_mode": sd.BY_FINDING})
    assert style["colour"] == st.COLOUR_HABITUAL


def test_le_mode_categorie_colore_par_la_reponse():
    style = sd.style_for(_visuelle(), {"colour_mode": sd.BY_CATEGORY})
    assert style["colour"] == sd.CATEGORY_COLOURS["visual"]


def test_le_mode_categorie_sur_une_carte_sans_reponse_reste_gris():
    style = sd.style_for(_muette(), {"colour_mode": sd.BY_CATEGORY})
    assert style["colour"] == sd.DEFAULT_GREY


def test_le_mode_couleur_unique():
    style = sd.style_for(
        _visuelle(), {"colour_mode": sd.FIXED, "fixed_colour": "#123456"}
    )
    assert style["colour"] == "#123456"


def test_la_categorie_prise_est_celle_de_la_premiere_reponse():
    carte = st.new_record(
        electrode="A",
        contact=0,
        responses=[
            st.new_response("language", "Speech arrest"),
            st.new_response("motor", "Myoclonus"),
        ],
    )
    style = sd.style_for(carte, {"colour_mode": sd.BY_CATEGORY})
    assert style["colour"] == sd.CATEGORY_COLOURS["language"]


# ------------------------------------------------------- les regles


def _reglages_a_regles(regles):
    reglages = sd.default_settings()
    reglages["colour_mode"] = sd.BY_RULES
    reglages["rules"] = regles
    return reglages


def test_une_regle_qui_correspond_donne_sa_couleur():
    regles = [sd.new_rule("habituelle", when={"habitual": ["identical"]}, colour="#AA0000")]
    style = sd.style_for(_habituelle(), _reglages_a_regles(regles))
    assert style["colour"] == "#AA0000"
    assert style["rule"] == "habituelle"


def test_la_premiere_regle_qui_correspond_gagne():
    """Deux regles qui se recouvrent: l'ordre decide, et il est connu."""
    regles = [
        sd.new_rule("premiere", when={"habitual": ["identical"]}, colour="#111111"),
        sd.new_rule("seconde", when={"categories": ["motor"]}, colour="#222222"),
    ]
    assert sd.style_for(_habituelle(), _reglages_a_regles(regles))["colour"] == "#111111"


def test_une_regle_eteinte_est_ignoree():
    regles = [
        sd.new_rule(
            "eteinte", when={"habitual": ["identical"]}, colour="#111111", enabled=False
        ),
        sd.new_rule("active", when={"categories": ["motor"]}, colour="#222222"),
    ]
    assert sd.style_for(_habituelle(), _reglages_a_regles(regles))["colour"] == "#222222"


def test_une_carte_sans_regle_reste_visible_en_pale():
    """Le piege: une regle trop etroite ferait disparaitre une paire
    reellement testee."""
    regles = [sd.new_rule("rien", when={"categories": ["auditory"]}, colour="#111111")]
    style = sd.style_for(_habituelle(), _reglages_a_regles(regles))
    assert style["colour"] == sd.DEFAULT_GREY
    assert style["opacity"] < 1.0


def test_une_regle_qui_ne_change_que_la_couleur_garde_le_reste():
    regles = [sd.new_rule("couleur", when={"habitual": ["identical"]}, colour="#AA0000")]
    reglages = _reglages_a_regles(regles)
    reglages["line_width_mm"] = 3.0
    style = sd.style_for(_habituelle(), reglages)
    assert style["line_width_mm"] == 3.0


def test_une_regle_peut_changer_l_epaisseur_et_l_endroit():
    regles = [
        sd.new_rule(
            "grosse",
            when={"habitual": ["identical"]},
            colour="#AA0000",
            where=sd.WHERE_BOTH,
            line_width_mm=4.0,
            opacity=0.5,
        )
    ]
    style = sd.style_for(_habituelle(), _reglages_a_regles(regles))
    assert style["where"] == sd.WHERE_BOTH
    assert style["line_width_mm"] == 4.0
    assert style["opacity"] == 0.5


def test_les_identifiants_de_regle_se_suivent():
    assert sd.next_rule_id([]) == "rule-1"
    assert sd.next_rule_id([{"id": "rule-2"}]) == "rule-3"


def test_une_regle_sans_condition_prend_tout():
    regles = [sd.new_rule("tout", colour="#ABCDEF")]
    for carte in (_habituelle(), _visuelle(), _muette()):
        assert sd.style_for(carte, _reglages_a_regles(regles))["colour"] == "#ABCDEF"


# ------------------------------------------------------- les prereglages


@pytest.mark.parametrize("nom", [cle for cle, _ in sd.PRESETS])
def test_chaque_preglage_donne_des_regles(nom):
    assert sd.preset_rules(nom)


def test_un_preglage_inconnu_ne_leve_pas():
    assert sd.preset_rules("inexistant") == []


def test_le_preglage_clinique_met_l_habituel_en_tete():
    regles = sd.preset_rules("clinical")
    assert regles[0]["colour"] == st.COLOUR_HABITUAL
    assert sd.style_for(_habituelle(), _reglages_a_regles(regles))["colour"] == (
        st.COLOUR_HABITUAL
    )


def test_le_preglage_clinique_amincit_les_muettes():
    regles = sd.preset_rules("clinical")
    style = sd.style_for(_muette(), _reglages_a_regles(regles))
    assert style["line_width_mm"] < 1.0


def test_le_preglage_eloquent_distingue_langage_et_moteur():
    regles = sd.preset_rules("eloquent")
    reglages = _reglages_a_regles(regles)
    langage = st.new_record(
        electrode="A", contact=0, responses=[st.new_response("language", "Speech arrest")]
    )
    moteur = st.new_record(
        electrode="A", contact=2, responses=[st.new_response("motor", "Clonic jerks")]
    )
    assert sd.style_for(langage, reglages)["colour"] != sd.style_for(moteur, reglages)["colour"]


def test_un_preglage_est_une_copie_neuve():
    """Le modifier ne doit pas changer le preglage pour la fois d'apres."""
    regles = sd.preset_rules("clinical")
    regles[0]["colour"] = "#000000"
    assert sd.preset_rules("clinical")[0]["colour"] == st.COLOUR_HABITUAL


# ------------------------------------------------- la traversee du JSON


def test_une_regle_traverse_le_json():
    """Une condition contient des ensembles, que JSON ne connait pas."""
    regle = sd.new_rule("essai", when={"categories": {"motor", "visual"}})
    relue = json.loads(json.dumps(regle))
    assert sd.rule_matches(
        relue,
        st.new_record(
            electrode="A", contact=0, responses=[st.new_response("motor", "Myoclonus")]
        ),
    )


def test_des_reglages_entiers_traversent_le_json():
    reglages = _reglages_a_regles(sd.preset_rules("clinical"))
    relus = json.loads(json.dumps(reglages))
    assert sd.style_for(_habituelle(), relus)["colour"] == st.COLOUR_HABITUAL


def test_une_condition_vide_traverse_aussi():
    relue = json.loads(json.dumps(sd.new_rule("tout")))
    assert sd.rule_matches(relue, _muette())


# ------------------------------------------------------- la legende


def test_la_legende_suit_le_mode_trouvaille():
    entrees = sd.legend_entries({"colour_mode": sd.BY_FINDING})
    assert len(entrees) == len(st.COLOUR_LEGEND)


def test_la_legende_du_mode_categorie_a_onze_lignes():
    assert len(sd.legend_entries({"colour_mode": sd.BY_CATEGORY})) == len(st.CATEGORIES)


def test_la_legende_des_regles_nomme_les_regles():
    reglages = _reglages_a_regles(sd.preset_rules("eloquent"))
    textes = [texte for _c, texte in sd.legend_entries(reglages)]
    assert "Language" in textes
    assert "matched by no rule" in textes


def test_la_legende_des_regles_ignore_les_eteintes():
    regles = sd.preset_rules("eloquent")
    regles[0]["enabled"] = False
    textes = [t for _c, t in sd.legend_entries(_reglages_a_regles(regles))]
    assert "Language" not in textes


def test_la_legende_de_la_couleur_unique_tient_en_une_ligne():
    assert len(sd.legend_entries({"colour_mode": sd.FIXED})) == 1


# ------------------------------------------------------- robustesse


def test_sans_reglages_le_style_reste_complet():
    style = sd.style_for(_habituelle(), None)
    for cle in ("where", "colour", "line_width_mm", "contact_radius_mm", "opacity"):
        assert cle in style


def test_une_valeur_illisible_retombe_sur_le_defaut():
    style = sd.style_for(_habituelle(), {"line_width_mm": "epais"})
    assert style["line_width_mm"] == 1.4


def test_une_carte_vide_ne_leve_pas():
    assert sd.style_for({}, sd.default_settings())["colour"]


def test_le_gris_est_celui_des_reglages():
    assert sd.grey_colour({"grey_colour": "#123123"}) == "#123123"
    assert sd.grey_colour({}) == sd.DEFAULT_GREY
