"""Le mode Stimulation Result de la vue 3D.

CE QUE CE MODE EST

Un resultat de stimulation porte sur une PAIRE, et un cerveau couvert
d'electrodes en couleurs est le pire fond pour en lire un: le trait
colore se perd parmi vingt tiges colorees. Entrer dans le mode efface
donc les electrodes dessinees en couleurs natives et ne laisse que les
stimulations retenues par les filtres: un tube colore d'un contact a
l'autre, et les deux contacts en gris.

CE QUE CE MODE N'EST PAS

Il ne touche a rien d'autre. Les coupes, les surcouches, la parcellation
et la camera continuent de fonctionner, parce que le mode ne change que
la VISIBILITE des acteurs d'electrodes.

CE QUE CES TESTS PROTEGENT

1. Sortir du mode remet exactement ce qui etait la, y compris une
   electrode que l'utilisateur avait masquee lui-meme avant d'entrer.
2. Hors du mode, rien n'est dessine: un tube au milieu des electrodes ne
   dirait rien.
3. Un acteur reconstruit est visible, donc le mode doit se reappliquer
   apres chaque reconstruction.
4. Le dessin suit les reglages: endroit, couleur, epaisseur, opacite.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.view3d_stimulation import View3DStimulationMixin  # noqa: E402
from neuxelec.ui import context_menus  # noqa: E402
from neuxelec.ui.stimulation_results_dialog import StimulationResultsDialog  # noqa: E402
from neuxelec.utils import stimulation as st  # noqa: E402
from neuxelec.utils import stimulation_display as sd  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _electrodes():
    return [
        {"name": "A", "contacts_lps": [[float(i) * 2.0, 0.0, 0.0] for i in range(8)]},
        {"name": "B", "contacts_lps": [[0.0, float(i), 10.0] for i in range(4)]},
    ]


def _cartes():
    return [
        st.new_record(
            electrode="A",
            contact=0,
            electrode_b="A",
            contact_b=1,
            record_id="stim-1",
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
            record_id="stim-2",
            frequency_hz=50.0,
            intensity_ma=1.0,
            events=["after_discharges"],
            habitual="no",
            responses=[st.new_response("visual", "Phosphenes")],
        ),
        st.new_record(
            electrode="B",
            contact=0,
            electrode_b="B",
            contact_b=1,
            record_id="stim-3",
            frequency_hz=50.0,
            intensity_ma=5.0,
        ),
    ]


class _Etat:
    def __init__(self, cartes=None, affichage=None):
        self.electrodes = _electrodes()
        self.stimulations = list(cartes if cartes is not None else _cartes())
        self.stimulation_display = dict(affichage or {})


# ======================================================== les couleurs


def test_une_crise_habituelle_est_la_couleur_la_plus_forte():
    carte = st.new_record(
        electrode="A",
        contact=0,
        events=["seizure_electroclinical"],
        habitual="identical",
    )
    assert st.marker_colour(carte) == st.COLOUR_HABITUAL


def test_une_crise_partiellement_habituelle_a_sa_couleur():
    carte = st.new_record(
        electrode="A", contact=0, events=["seizure_aura"], habitual="partial"
    )
    assert st.marker_colour(carte) == st.COLOUR_PARTIAL


def test_une_crise_non_habituelle_est_en_dessous():
    carte = st.new_record(
        electrode="A", contact=0, events=["seizure_atypical"], habitual="no"
    )
    assert st.marker_colour(carte) == st.COLOUR_SEIZURE


def test_une_reponse_sans_crise_a_sa_couleur():
    carte = st.new_record(
        electrode="A", contact=0, responses=[st.new_response("visual", "Phosphenes")]
    )
    assert st.marker_colour(carte) == st.COLOUR_RESPONSE


def test_une_post_decharge_seule_a_sa_couleur():
    carte = st.new_record(electrode="A", contact=0, events=["after_discharges"])
    assert st.marker_colour(carte) == st.COLOUR_DISCHARGE


def test_un_couple_muet_est_gris():
    assert st.marker_colour(st.new_record(electrode="A", contact=0)) == st.COLOUR_SILENT


def test_une_aura_habituelle_sans_evenement_coche_compte_quand_meme():
    """Elle peut etre saisie sans qu'aucune case de crise soit cochee, et
    c'est une trouvaille majeure."""
    carte = st.new_record(
        electrode="A",
        contact=0,
        habitual="identical",
        responses=[st.new_response("cognitive", "Deja-vu (familiarity)")],
    )
    assert st.marker_colour(carte) == st.COLOUR_HABITUAL


def test_la_legende_couvre_toutes_les_couleurs():
    assert {c for c, _ in st.COLOUR_LEGEND} == {
        st.COLOUR_HABITUAL,
        st.COLOUR_PARTIAL,
        st.COLOUR_SEIZURE,
        st.COLOUR_RESPONSE,
        st.COLOUR_DISCHARGE,
        st.COLOUR_SILENT,
    }


# ======================================================== le faux decor


class _Acteur:
    def __init__(self):
        self._visible = True

    def GetVisibility(self):
        return self._visible

    def SetVisibility(self, on):
        self._visible = bool(on)

    def ForceOpaqueOn(self):
        pass


class _Plotter:
    """Il enleve pour de bon: sinon il cacherait que le code n'enleve pas."""

    def __init__(self):
        self.scene: dict = {}
        self.retires = []

    @property
    def meshes(self):
        return list(self.scene.values())

    def add_mesh(self, mesh, **kwargs):
        acteur = _Acteur()
        self.scene[acteur] = (mesh, kwargs)
        return acteur

    def add_point_labels(self, points, labels, **kwargs):
        acteur = _Acteur()
        self.derniers_labels = list(labels)
        self.scene[acteur] = (points, dict(kwargs))
        return acteur

    def remove_actor(self, actor, **_kwargs):
        self.retires.append(actor)
        self.scene.pop(actor, None)


class _Page(View3DStimulationMixin):
    """Le mixin sur un decor minimal: pas de Qt, pas de VTK."""

    def __init__(self, cartes=None, mni=False, affichage=None):
        self.state = _Etat(cartes, affichage)
        self.plotter = _Plotter()
        self.interactor = None
        self.container_3d = None
        self.ui = None
        self._stimulation_mode = False
        self._stim_marker_actors = {}
        self._stim_filters = {}
        self._stim_hidden_electrodes = {}
        self._stim_chrome_filter = None
        self._stim_frame = None
        self._stim_badge = None
        self._stim_escape = None
        self._stim_results_dialog = None
        self._mni = mni
        self.rendus = 0

        # Deux electrodes, chacune ses contacts et sa tige.
        self._elec_actors = {
            (0, "points"): _Acteur(),
            (0, "line"): _Acteur(),
            (1, "points"): _Acteur(),
            (1, "line"): _Acteur(),
        }
        self._elec_label_actors = {(0, "labels"): _Acteur()}

    def _mni_t1_slices_are_visible(self):
        return self._mni

    def _render(self):
        self.rendus += 1

    @property
    def _dernier_appel_labels(self):
        return list(getattr(self.plotter, "derniers_labels", []))

    # La fenetre et le decor demandent du vrai Qt: ce test ne les regarde pas.
    def _open_stimulation_results_dialog(self):
        self.fenetre_ouverte = True

    def _close_stimulation_results_dialog(self):
        self.fenetre_ouverte = False

    def _show_stimulation_chrome(self, on):
        self.decor = bool(on)

    def _dialog_parent(self):
        return None


def _meshes(page):
    return page.plotter.meshes


def _couleurs(page):
    return [k.get("color") for _m, k in _meshes(page)]


def _noms(page):
    return [k.get("name", "") for _m, k in _meshes(page)]


def _visibles(page):
    return [a.GetVisibility() for a in page._native_electrode_actors()]


# ======================================================== entrer, sortir


def test_entrer_efface_les_electrodes_natives():
    page = _Page()
    page.enter_stimulation_mode()
    assert not any(_visibles(page))


def test_entrer_ouvre_la_fenetre_et_pose_le_decor():
    page = _Page()
    page.enter_stimulation_mode()
    assert page.fenetre_ouverte
    assert page.decor


def test_sortir_remet_les_electrodes():
    page = _Page()
    page.enter_stimulation_mode()
    page.leave_stimulation_mode()
    assert all(_visibles(page))


def test_sortir_remet_ce_qui_etait_masque_a_la_main():
    """Le piege: rendre visible une electrode que l'utilisateur avait
    masquee lui-meme avant d'entrer."""
    page = _Page()
    page._elec_actors[(1, "points")].SetVisibility(False)
    page.enter_stimulation_mode()
    page.leave_stimulation_mode()
    assert page._elec_actors[(1, "points")].GetVisibility() is False
    assert page._elec_actors[(0, "points")].GetVisibility() is True


def test_sortir_efface_les_tubes():
    page = _Page()
    page.enter_stimulation_mode()
    page.leave_stimulation_mode()
    assert page._stim_marker_actors == {}


def test_sortir_retire_le_decor_et_ferme_la_fenetre():
    page = _Page()
    page.enter_stimulation_mode()
    page.leave_stimulation_mode()
    assert page.decor is False
    assert page.fenetre_ouverte is False


def test_le_mode_se_bascule():
    page = _Page()
    page.toggle_stimulation_mode()
    assert page.stimulation_mode_active()
    page.toggle_stimulation_mode()
    assert not page.stimulation_mode_active()


def test_entrer_deux_fois_ne_masque_pas_deux_fois():
    """Sinon le second passage retiendrait "invisible" comme etat d'avant."""
    page = _Page()
    page.enter_stimulation_mode()
    page.enter_stimulation_mode()
    page.leave_stimulation_mode()
    assert all(_visibles(page))


def test_sortir_sans_etre_entre_ne_fait_rien():
    page = _Page()
    page.leave_stimulation_mode()
    assert all(_visibles(page))


def test_une_reconstruction_est_remasquee():
    """Un acteur reconstruit est visible: le mode doit se reappliquer."""
    page = _Page()
    page.enter_stimulation_mode()
    page._elec_actors[(0, "points")] = _Acteur()
    assert page._elec_actors[(0, "points")].GetVisibility() is True
    page.apply_stimulation_mode_visibility()
    assert page._elec_actors[(0, "points")].GetVisibility() is False


def test_hors_du_mode_la_reapplication_ne_fait_rien():
    page = _Page()
    page.apply_stimulation_mode_visibility()
    assert all(_visibles(page))


# ======================================================== le dessin


def test_hors_du_mode_rien_n_est_dessine():
    """Un tube au milieu des electrodes natives ne dirait rien."""
    page = _Page()
    page.refresh_stimulation_markers()
    assert _meshes(page) == []


def test_dans_le_mode_chaque_paire_donne_un_tube():
    page = _Page([_cartes()[0]])
    page.enter_stimulation_mode()
    assert sum("tube" in n for n in _noms(page)) == 1


def test_tous_les_contacts_sont_dessines_en_gris():
    """Le fond du mode: on voit ou sont les electrodes sans qu'elles
    concurrencent le resultat."""
    page = _Page([])
    page.enter_stimulation_mode()
    gris = [k for _m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"]
    assert len(gris) == 1
    assert gris[0]["color"] == sd.DEFAULT_GREY


def test_le_gris_couvre_les_contacts_des_deux_electrodes():
    page = _Page([])
    page.enter_stimulation_mode()
    maille = next(
        m for m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    # A va de x=0 a x=14 en LPS, B est a z=10: les bornes couvrent les deux.
    assert maille.bounds[0] < -13.0
    assert maille.bounds[5] > 9.0


def test_une_electrode_masquee_reste_masquee_dans_le_mode():
    """Le mode est une facon de regarder, pas une facon de defaire."""
    page = _Page([])
    page.state.electrodes[1]["visible"] = False
    page.enter_stimulation_mode()
    maille = next(
        m for m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    # B est a z=10: si elle etait dessinee, les bornes y monteraient.
    assert maille.bounds[5] < 5.0


def test_un_contact_masque_n_est_pas_dessine():
    page = _Page([])
    page.state.electrodes[0]["contacts_visible"] = [False] * 8
    page.state.electrodes[1]["visible"] = False
    page.enter_stimulation_mode()
    assert not any(
        k.get("name") == "stimulation_grey_contacts" for _m, k in _meshes(page)
    )


def test_aucune_tige_n_est_dessinee():
    """Un trait entre contacts concurrencerait le tube du resultat."""
    page = _Page([])
    page.enter_stimulation_mode()
    assert not any("line" in k.get("name", "") for _m, k in _meshes(page))


def test_le_tube_relie_les_deux_contacts():
    """A1 est en LPS x=0, A2 en x=2, donc en RAS x=0 et x=-2."""
    page = _Page([_cartes()[0]])
    page.enter_stimulation_mode()
    tube = next(m for m, k in _meshes(page) if "tube" in k.get("name", ""))
    bornes = tube.bounds
    assert round(bornes[0], 2) == -2.0
    assert round(bornes[1], 2) == 0.0


def test_le_tube_porte_le_filtre_et_les_contacts_restent_gris():
    """C'est la demande exacte: le trait porte le filtre, les contacts non."""
    page = _Page([_cartes()[0]])
    page.enter_stimulation_mode()
    par_nom = {k.get("name", ""): k.get("color") for _m, k in _meshes(page)}
    assert par_nom["stimulation_stim-1_tube"] == st.COLOUR_HABITUAL
    assert par_nom["stimulation_grey_contacts"] == sd.DEFAULT_GREY
    # Rien n'est peint par-dessus les contacts tant qu'on ne le demande pas.
    assert not any(n.endswith(("-a", "-b")) for n in par_nom)


def test_le_monopolaire_n_a_pas_de_tube():
    carte = st.new_record(
        electrode="A", contact=3, polarity="monopolar", record_id="stim-9"
    )
    page = _Page([carte])
    page.enter_stimulation_mode()
    assert not any("tube" in n for n in _noms(page))
    assert sum(n.endswith("-a") for n in _noms(page)) == 1


def test_toutes_les_paires_visibles_sont_dessinees():
    page = _Page()
    page.enter_stimulation_mode()
    assert sum("tube" in n for n in _noms(page)) == 3


def test_une_electrode_disparue_ne_casse_pas_le_reste():
    cartes = _cartes() + [st.new_record(electrode="Z", contact=0, record_id="stim-9")]
    page = _Page(cartes)
    page.enter_stimulation_mode()
    assert sum("tube" in n for n in _noms(page)) == 3


def test_le_mode_mni_ne_dessine_rien():
    """Les stimulations du patient n'ont pas leur place sur un gabarit."""
    page = _Page(mni=True)
    page.enter_stimulation_mode()
    assert _meshes(page) == []


def test_sans_plotter_rien_ne_leve():
    page = _Page()
    page.plotter = None
    page.enter_stimulation_mode()


def test_la_scene_est_rendue():
    page = _Page()
    page.enter_stimulation_mode()
    assert page.rendus >= 1


# ======================================================== les reglages


def test_dessiner_sur_les_contacts_colore_les_contacts():
    page = _Page([_cartes()[0]], affichage={"where": sd.WHERE_CONTACTS})
    page.enter_stimulation_mode()
    par_nom = {k.get("name", ""): k.get("color") for _m, k in _meshes(page)}
    assert not any("tube" in n for n in par_nom)
    peints = {v for n, v in par_nom.items() if n.endswith(("-a", "-b"))}
    assert peints == {st.COLOUR_HABITUAL}


def test_les_deux_colore_tout():
    page = _Page([_cartes()[0]], affichage={"where": sd.WHERE_BOTH})
    page.enter_stimulation_mode()
    peints = {
        k.get("color")
        for _m, k in _meshes(page)
        if k.get("name", "") != "stimulation_grey_contacts"
    }
    assert peints == {st.COLOUR_HABITUAL}
    assert any("tube" in n for n in _noms(page))


def test_l_epaisseur_du_tube_suit_le_reglage():
    fin = _Page([_cartes()[0]], affichage={"line_width_mm": 0.4})
    fin.enter_stimulation_mode()
    gros = _Page([_cartes()[0]], affichage={"line_width_mm": 4.0})
    gros.enter_stimulation_mode()

    def _diametre(page):
        tube = next(m for m, k in page.plotter.meshes if "tube" in k.get("name", ""))
        return tube.bounds[3] - tube.bounds[2]

    assert _diametre(gros) > _diametre(fin)


def test_la_taille_des_contacts_suit_le_reglage():
    """Mesuree sur les billes grises, qui sont tous les contacts."""

    def _epaisseur(rayon):
        page = _Page([], affichage={"contact_radius_mm": rayon})
        page.state.electrodes = [{"name": "A", "contacts_lps": [[0.0, 0.0, 0.0]]}]
        page.enter_stimulation_mode()
        maille = next(
            m for m, k in page.plotter.meshes if k.get("name") == "stimulation_grey_contacts"
        )
        return maille.bounds[1] - maille.bounds[0]

    assert _epaisseur(3.0) == pytest.approx(6.0, abs=0.4)
    assert _epaisseur(1.0) == pytest.approx(2.0, abs=0.2)


def test_l_opacite_suit_le_reglage():
    """Elle porte sur les resultats, pas sur le fond gris, qui doit rester
    lisible pour situer les electrodes."""
    page = _Page([_cartes()[0]], affichage={"opacity": 0.3})
    page.enter_stimulation_mode()
    tube = next(k for _m, k in _meshes(page) if "tube" in k.get("name", ""))
    fond = next(
        k for _m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    assert tube["opacity"] == 0.3
    assert fond["opacity"] == 1.0


def test_le_gris_des_contacts_suit_le_reglage():
    page = _Page([_cartes()[0]], affichage={"grey_colour": "#123456"})
    page.enter_stimulation_mode()
    fond = next(
        k for _m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    assert fond["color"] == "#123456"


def test_les_regles_decident_la_couleur():
    regles = sd.preset_rules("eloquent")
    page = _Page(affichage={"colour_mode": sd.BY_RULES, "rules": regles})
    page.enter_stimulation_mode()
    tubes = {
        k.get("name", ""): k.get("color") for _m, k in _meshes(page) if "tube" in k.get("name", "")
    }
    # stim-1 est moteur, stim-2 visuel.
    assert tubes["stimulation_stim-1_tube"] == sd.CATEGORY_COLOURS["motor"]
    assert tubes["stimulation_stim-2_tube"] == sd.CATEGORY_COLOURS["visual"]


def test_changer_les_reglages_redessine():
    page = _Page([_cartes()[0]])
    page.enter_stimulation_mode()
    page.set_stimulation_display_settings({"where": sd.WHERE_CONTACTS})
    assert not any("tube" in n for n in _noms(page))
    assert page.state.stimulation_display["where"] == sd.WHERE_CONTACTS


# ======================================================== les filtres


def test_poser_un_filtre_redessine_la_scene():
    page = _Page()
    page.enter_stimulation_mode()
    filtres = st.empty_filters()
    filtres["frequencies"] = {50.0}
    page.set_stimulation_filters(filtres)
    assert sum("tube" in n for n in _noms(page)) == 2


def test_ecarter_les_muets_les_retire_de_la_scene():
    page = _Page()
    page.enter_stimulation_mode()
    filtres = st.empty_filters()
    filtres["include_silent"] = False
    page.set_stimulation_filters(filtres)
    assert sum("tube" in n for n in _noms(page)) == 2


def test_les_visibles_suivent_les_filtres():
    page = _Page()
    filtres = st.empty_filters()
    filtres["habitual"] = {"identical"}
    page.set_stimulation_filters(filtres)
    assert [c["id"] for c in page.visible_stimulations()] == ["stim-1"]


def test_sans_filtre_tout_est_visible():
    assert len(_Page().visible_stimulations()) == 3


# ======================================================== la fenetre


@pytest.fixture
def fenetre(app):
    etat = _Etat()
    recues: list[dict] = []
    recus_affichage: list[dict] = []
    d = StimulationResultsDialog(
        etat,
        on_filters_changed=recues.append,
        on_display_changed=recus_affichage.append,
    )
    d._recues = recues
    d._recus_affichage = recus_affichage
    yield d
    d.close()


def test_la_fenetre_a_trois_onglets(fenetre):
    assert [fenetre.tabs.tabText(i) for i in range(fenetre.tabs.count())] == [
        "Visualisation filters",
        "Appearance",
        "Stimulation cards",
    ]


def test_au_depart_tout_passe(fenetre):
    assert len(st.filter_records(fenetre._records(), fenetre.filters())) == 3


def test_le_compte_est_affiche(fenetre):
    assert "3 / 3" in fenetre.lbl_count.text()


def test_sans_stimulation_le_compte_le_dit(app):
    d = StimulationResultsDialog(_Etat([]))
    assert "No stimulation recorded" in d.lbl_count.text()
    d.close()


# ---------------------------------------------------- les filtres


def test_le_filtre_d_amperage_ne_compte_que_coche(fenetre):
    fenetre.spn_min.setValue(4.0)
    assert fenetre.filters()["min_intensity_ma"] is None
    fenetre.chk_min.setChecked(True)
    assert fenetre.filters()["min_intensity_ma"] == 4.0


def test_le_filtre_de_frequence(fenetre):
    fenetre.chk_frequencies[50.0].setChecked(True)
    assert fenetre.filters()["frequencies"] == {50.0}
    assert "2 / 3" in fenetre.lbl_count.text()


def test_le_filtre_d_evenement(fenetre):
    fenetre.chk_filter_events["after_discharges"].setChecked(True)
    assert fenetre.filters()["events"] == {"after_discharges"}


def test_le_filtre_de_categorie(fenetre):
    fenetre.chk_filter_categories["visual"].setChecked(True)
    assert fenetre.filters()["categories"] == {"visual"}
    assert "1 / 3" in fenetre.lbl_count.text()


def test_le_filtre_de_l_habituel(fenetre):
    fenetre.chk_filter_habitual["identical"].setChecked(True)
    assert fenetre.filters()["habitual"] == {"identical"}


def test_non_precise_n_est_pas_un_filtre_propose(fenetre):
    assert "unspecified" not in fenetre.chk_filter_habitual


def test_les_onze_categories_sont_filtrables(fenetre):
    assert len(fenetre.chk_filter_categories) == len(st.CATEGORIES)


def test_tous_les_evenements_sont_filtrables(fenetre):
    assert len(fenetre.chk_filter_events) == len(st.EVENTS)


def test_les_muets_sont_inclus_au_depart(fenetre):
    assert fenetre.filters()["include_silent"] is True


def test_chaque_changement_est_annonce(fenetre):
    fenetre.chk_frequencies[50.0].setChecked(True)
    assert fenetre._recues[-1]["frequencies"] == {50.0}


def test_tout_remontrer_remet_les_filtres_a_zero(fenetre):
    fenetre.chk_frequencies[50.0].setChecked(True)
    fenetre.chk_filter_categories["visual"].setChecked(True)
    fenetre.chk_min.setChecked(True)
    fenetre.chk_silent.setChecked(False)
    fenetre.reset_filters()
    filtres = fenetre.filters()
    assert filtres["frequencies"] == set()
    assert filtres["categories"] == set()
    assert filtres["min_intensity_ma"] is None
    assert filtres["include_silent"] is True


# ---------------------------------------------------- l'apparence


def test_les_reglages_par_defaut_sont_proposes(fenetre):
    reglages = fenetre.display_settings()
    assert reglages["colour_mode"] == sd.BY_FINDING
    assert reglages["where"] == sd.WHERE_LINE


def test_changer_un_reglage_est_annonce(fenetre):
    fenetre.spn_line_width.setValue(3.0)
    assert fenetre._recus_affichage[-1]["line_width_mm"] == 3.0


def test_charger_un_preglage_remplit_les_regles(fenetre):
    fenetre.cmb_preset.setCurrentIndex(0)
    fenetre._load_preset()
    reglages = fenetre.display_settings()
    assert reglages["colour_mode"] == sd.BY_RULES
    assert len(reglages["rules"]) == 4


def test_une_regle_se_fabrique_depuis_les_filtres(fenetre):
    """La condition s'ecrit a un seul endroit: l'onglet des filtres."""
    fenetre.chk_filter_categories["language"].setChecked(True)
    fenetre._add_rule_from_filters()
    regles = fenetre.display_settings()["rules"]
    assert len(regles) == 1
    assert regles[0]["when"]["categories"] == ["language"]


def test_la_regle_fabriquee_porte_un_nom_lisible(fenetre):
    fenetre.chk_filter_categories["language"].setChecked(True)
    fenetre._add_rule_from_filters()
    assert fenetre.display_settings()["rules"][0]["name"] == "Language"


def test_une_regle_sans_filtre_se_nomme_quand_meme(fenetre):
    fenetre._add_rule_from_filters()
    assert fenetre.display_settings()["rules"][0]["name"] == "Every stimulation"


def test_une_regle_se_retire(fenetre):
    fenetre._add_rule_from_filters()
    fenetre._remove_rule(0)
    assert fenetre.display_settings()["rules"] == []


def test_l_ordre_des_regles_se_change(fenetre):
    fenetre.chk_filter_categories["motor"].setChecked(True)
    fenetre._add_rule_from_filters()
    fenetre.chk_filter_categories["motor"].setChecked(False)
    fenetre.chk_filter_categories["visual"].setChecked(True)
    fenetre._add_rule_from_filters()

    avant = [r["name"] for r in fenetre.display_settings()["rules"]]
    fenetre._move_rule(1, -1)
    apres = [r["name"] for r in fenetre.display_settings()["rules"]]
    assert apres == list(reversed(avant))


def test_la_couleur_unique_ne_parait_que_dans_son_mode(fenetre):
    # Un onglet qui n'est pas au premier plan est masque tout entier.
    fenetre.tabs.setCurrentIndex(1)
    assert not fenetre.fld_fixed_colour.isVisibleTo(fenetre)
    index = fenetre.cmb_colour_mode.findData(sd.FIXED)
    fenetre.cmb_colour_mode.setCurrentIndex(index)
    assert fenetre.fld_fixed_colour.isVisibleTo(fenetre)


def test_les_reglages_sauves_sont_relus(app):
    etat = _Etat(affichage={"colour_mode": sd.FIXED, "line_width_mm": 2.6})
    d = StimulationResultsDialog(etat)
    assert d.display_settings()["colour_mode"] == sd.FIXED
    assert d.display_settings()["line_width_mm"] == 2.6
    d.close()


def test_les_regles_sauvees_sont_relues(app):
    etat = _Etat(
        affichage={"colour_mode": sd.BY_RULES, "rules": sd.preset_rules("clinical")}
    )
    d = StimulationResultsDialog(etat)
    assert len(d.display_settings()["rules"]) == 4
    d.close()


# ---------------------------------------------------- les cartes


def test_chaque_stimulation_a_sa_ligne(fenetre):
    assert fenetre.lst_cards.count() == 3


def test_la_ligne_resume_la_stimulation(fenetre):
    assert "A1-A2" in fenetre.lst_cards.item(0).text()


def test_la_carte_affichee_est_celle_choisie(fenetre):
    fenetre.lst_cards.setCurrentRow(1)
    assert fenetre.selected_id() == "stim-2"
    assert "A3-A4" in fenetre.lbl_card.text()


def test_la_carte_d_un_couple_muet_le_dit(fenetre):
    fenetre.lst_cards.setCurrentRow(2)
    assert "no response at 5 mA" in fenetre.lbl_card.text()


def test_sans_carte_les_boutons_sont_eteints(app):
    d = StimulationResultsDialog(_Etat([]))
    assert not d.btn_edit.isEnabled()
    assert not d.btn_delete.isEnabled()
    d.close()


def test_supprimer_retire_la_carte(fenetre, monkeypatch):
    from neuxelec.ui import stimulation_results_dialog as mod

    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "question", classmethod(lambda *a, **k: True)
    )
    fenetre.lst_cards.setCurrentRow(1)
    fenetre.delete_selected()
    assert [c["id"] for c in fenetre._records()] == ["stim-1", "stim-3"]


def test_refuser_la_suppression_ne_retire_rien(fenetre, monkeypatch):
    from neuxelec.ui import stimulation_results_dialog as mod

    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "question", classmethod(lambda *a, **k: False)
    )
    fenetre.delete_selected()
    assert len(fenetre._records()) == 3


def test_l_electrode_est_retrouvee_par_son_nom():
    """Par le nom et non par l'indice: une electrode supprimee entre-temps
    deplacerait sinon la carte sur sa voisine."""
    assert StimulationResultsDialog._contact_of(
        {"electrode": "B", "contact": 1}, _electrodes()
    ) == (1, 1)


def test_un_contact_hors_plage_n_est_pas_retrouve():
    assert (
        StimulationResultsDialog._contact_of({"electrode": "B", "contact": 9}, _electrodes())
        is None
    )


# ======================================================== les menus


@pytest.fixture
def menu_capture(app, monkeypatch):
    captures = []
    vrai = context_menus.make_base_menu

    def _capturer():
        menu = vrai()
        menu.exec = lambda *a, **k: None
        captures.append(menu)
        return menu

    monkeypatch.setattr(context_menus, "make_base_menu", _capturer)
    return captures


def _entrees(captures):
    assert captures, "aucun menu n'a ete construit"
    return [a.text() for a in captures[-1].actions() if a.text()]


@pytest.mark.parametrize(
    "page", ["page3DView", "pageObliqueSlices", "pageReconstruction"]
)
def test_le_clic_droit_sur_un_contact_propose_la_saisie(menu_capture, page):
    context_menus.exec_electrode_tree_menu(None, kind="contact", current_page=page)
    assert "Add stimulation result" in _entrees(menu_capture)


def test_le_clic_droit_sur_une_electrode_ne_le_propose_pas(menu_capture):
    context_menus.exec_electrode_tree_menu(
        None, kind="electrode", current_page="page3DView"
    )
    assert "Add stimulation result" not in _entrees(menu_capture)


def _menu_3d(menu_capture, **extra):
    options = dict(has_lh=True, has_rh=True, show_lh=True, show_rh=True)
    options.update(extra)
    context_menus.exec_3d_view_menu(None, **options)
    return _entrees(menu_capture)


def test_la_vue_3d_propose_le_mode(menu_capture):
    """Un mode, pas une fenetre: l'entree doit le dire avant le clic."""
    assert "Mode: Stimulation Result" in _menu_3d(menu_capture)


def test_dans_le_mode_l_entree_propose_d_en_sortir(menu_capture):
    assert "Leave mode: Stimulation Result" in _menu_3d(
        menu_capture, stimulation_mode_on=True
    )


# ======================================================== le guide


def test_le_guide_a_son_chapitre():
    from neuxelec.help.content import MANUAL_SECTIONS

    chapitres = {s.id: s for s in MANUAL_SECTIONS}
    assert "stimulation" in chapitres
    assert chapitres["stimulation"].title == "Stimulation results"


def test_le_raccourci_des_coupes_est_documente():
    from neuxelec.help.content import SHORTCUTS

    lignes = [
        (contexte, action)
        for contexte, touches, action in SHORTCUTS
        if "arrow + wheel" in touches
    ]
    assert len(lignes) == 1
    contexte, action = lignes[0]
    assert contexte == "3D view"
    assert "axial" in action and "coronal" in action and "sagittal" in action


def test_le_clic_droit_sur_un_contact_est_documente():
    from neuxelec.help.content import SHORTCUTS

    assert any("stimulation result" in action for _c, _t, action in SHORTCUTS)


# ======================================================== le decor


class _PageAvecDecor(_Page):
    """Le mixin sur un vrai conteneur Qt, pour juger le decor."""

    def __init__(self, conteneur, **kwargs):
        super().__init__(**kwargs)
        self.container_3d = conteneur
        self._layout_3d = conteneur.layout()
        self._stim_container_style = None
        self._stim_container_margins = None

    def _show_stimulation_chrome(self, on):
        View3DStimulationMixin._show_stimulation_chrome(self, on)


@pytest.fixture
def page_decoree(app):
    from PySide6.QtWidgets import QWidget

    conteneur = QWidget()
    conteneur.resize(800, 600)
    page = _PageAvecDecor(conteneur)
    conteneur.show()
    QApplication.processEvents()
    yield page
    conteneur.close()


def test_le_decor_est_cache_au_depart(page_decoree):
    page_decoree._build_stimulation_chrome()
    assert not page_decoree._stim_badge.isVisible()


def test_entrer_montre_le_badge_et_la_sortie(page_decoree):
    page_decoree.enter_stimulation_mode()
    QApplication.processEvents()
    assert page_decoree._stim_badge.isVisible()
    assert page_decoree._stim_escape.isVisible()


def test_le_badge_dit_le_mode(page_decoree):
    page_decoree.enter_stimulation_mode()
    assert page_decoree._stim_badge.text() == "STIMULATION RESULTS"


def test_le_badge_est_blanc_sur_noir_en_majuscules(page_decoree):
    page_decoree.enter_stimulation_mode()
    style = page_decoree._stim_badge.styleSheet()
    assert "#FFFFFF" in style
    assert "#000000" in style
    assert page_decoree._stim_badge.text().isupper()


def test_le_cadre_est_une_bordure_du_conteneur_pas_un_calque(page_decoree):
    """LE DEFAUT CORRIGE.

    Un calque plein cadre paraissait transparent dans la feuille de
    style, mais au-dessus d'une fenetre OpenGL native un widget qui
    recouvre ne laisse rien passer: il peignait un rectangle opaque et
    le cerveau disparaissait avec toute la scene.

    La bordure est donc posee sur le conteneur, et la vue retrecie
    d'autant: rien n'est dessine par-dessus la scene.
    """
    page_decoree.enter_stimulation_mode()
    QApplication.processEvents()
    assert "#FF487D" in page_decoree.container_3d.styleSheet()
    assert getattr(page_decoree, "_stim_frame", None) is None


def test_sortir_enleve_la_bordure(page_decoree):
    page_decoree.enter_stimulation_mode()
    page_decoree.leave_stimulation_mode()
    QApplication.processEvents()
    assert "#FF487D" not in page_decoree.container_3d.styleSheet()


def test_la_feuille_de_style_d_origine_est_rendue(page_decoree):
    """Le conteneur en avait peut-etre une: elle ne doit pas se perdre."""
    page_decoree.container_3d.setStyleSheet("QWidget { color: #123456; }")
    page_decoree.enter_stimulation_mode()
    page_decoree.leave_stimulation_mode()
    assert page_decoree.container_3d.styleSheet() == "QWidget { color: #123456; }"


def test_le_badge_ne_vole_pas_les_clics(page_decoree):
    """Sinon on ne pourrait plus tourner le cerveau en dessous."""
    from PySide6.QtCore import Qt

    page_decoree.enter_stimulation_mode()
    assert page_decoree._stim_badge.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_le_badge_et_la_sortie_sont_en_haut_a_droite(page_decoree):
    page_decoree.enter_stimulation_mode()
    QApplication.processEvents()
    page_decoree._update_stimulation_chrome_geometry()

    badge = page_decoree._stim_badge
    sortie = page_decoree._stim_escape
    largeur = page_decoree.container_3d.width()

    assert badge.y() < 40
    assert sortie.y() < 40
    assert sortie.x() + sortie.width() <= largeur
    # La sortie est a droite du badge.
    assert sortie.x() > badge.x()


def test_le_bouton_de_sortie_quitte_le_mode(page_decoree):
    page_decoree.enter_stimulation_mode()
    page_decoree._stim_escape.click()
    QApplication.processEvents()
    assert not page_decoree.stimulation_mode_active()


def test_sortir_cache_le_decor(page_decoree):
    page_decoree.enter_stimulation_mode()
    page_decoree.leave_stimulation_mode()
    QApplication.processEvents()
    assert not page_decoree._stim_badge.isVisible()
    assert not page_decoree._stim_escape.isVisible()


def test_le_decor_suit_le_redimensionnement(page_decoree):
    page_decoree.enter_stimulation_mode()
    QApplication.processEvents()
    page_decoree.container_3d.resize(500, 400)
    QApplication.processEvents()
    page_decoree._update_stimulation_chrome_geometry()
    assert page_decoree._stim_escape.x() + page_decoree._stim_escape.width() <= 500


def test_sans_conteneur_le_decor_ne_leve_pas(app):
    page = _Page()
    View3DStimulationMixin._show_stimulation_chrome(page, True)


# ======================================================== les etiquettes


class _PageAvecLabels(_Page):
    """Une page qui sait quelles etiquettes sont allumees."""

    def __init__(self, contacts_allumes=(), electrodes_allumees=(), **kwargs):
        super().__init__(**kwargs)
        self._contacts_allumes = set(contacts_allumes)
        self._electrodes_allumees = set(electrodes_allumees)

    def _get_local_contact_labels_visible(self, elec_id, nombre):
        return [(elec_id, i) in self._contacts_allumes for i in range(nombre)]

    def is_electrode_label_visible(self, elec_id):
        return elec_id in self._electrodes_allumees


def _labels(page):
    for _m, k in _meshes(page):
        if k.get("name") == "stimulation_grey_labels":
            return k

    return None


def test_sans_etiquette_allumee_aucune_n_est_dessinee():
    page = _PageAvecLabels(cartes=[])
    page.enter_stimulation_mode()
    assert _labels(page) is None


def test_une_etiquette_de_contact_allumee_est_dessinee_en_gris():
    page = _PageAvecLabels(contacts_allumes={(0, 0), (0, 1)}, cartes=[])
    page.enter_stimulation_mode()
    options = _labels(page)
    assert options is not None
    assert options["text_color"] == sd.DEFAULT_GREY


def test_l_etiquette_de_contact_porte_le_bon_nom():
    page = _PageAvecLabels(contacts_allumes={(0, 2)}, cartes=[])
    page.enter_stimulation_mode()
    textes = page._dernier_appel_labels
    assert textes == ["A3"]


def test_l_etiquette_d_electrode_allumee_est_dessinee():
    page = _PageAvecLabels(electrodes_allumees={1}, cartes=[])
    page.enter_stimulation_mode()
    assert "B" in page._dernier_appel_labels


def test_les_etiquettes_suivent_le_gris_choisi():
    page = _PageAvecLabels(
        contacts_allumes={(0, 0)}, cartes=[], affichage={"grey_colour": "#445566"}
    )
    page.enter_stimulation_mode()
    assert _labels(page)["text_color"] == "#445566"


# ======================================================== le mode MNI


def test_le_mode_ne_touche_pas_aux_electrodes_mni():
    """Demande explicite: la vue MNI n'est pas impactee."""
    page = _Page()
    page._mni_electrode_actors = {("set", "A", "points"): _Acteur()}
    page.enter_stimulation_mode()
    assert page._mni_electrode_actors[("set", "A", "points")].GetVisibility() is True


def test_en_mode_mni_rien_n_est_dessine_meme_le_gris():
    page = _Page(mni=True)
    page.enter_stimulation_mode()
    assert _meshes(page) == []


# =============================== le mode ne change que les electrodes


def test_le_mode_ne_change_que_la_couleur_et_la_tige():
    """Demande explicite: entrer dans le mode ne doit rien changer de ce
    qui etait affiche, sauf que les electrodes passent en gris et que la
    tige disparait."""
    page = _PageAvecLabels(contacts_allumes={(0, 0), (0, 1)}, electrodes_allumees={0})
    page.enter_stimulation_mode()

    noms = _noms(page)
    # Les contacts sont la, en gris.
    assert "stimulation_grey_contacts" in noms
    # Les etiquettes allumees sont toujours la, en gris.
    assert "stimulation_grey_labels" in noms
    assert _labels(page)["text_color"] == sd.DEFAULT_GREY
    # La tige, elle, a disparu.
    assert not any("line" in n for n in noms)


def test_les_etiquettes_eteintes_le_restent():
    """Le mode n'allume rien de lui-meme."""
    page = _PageAvecLabels(cartes=[])
    page.enter_stimulation_mode()
    assert "stimulation_grey_labels" not in _noms(page)


def test_le_mode_ne_touche_pas_les_coupes_ni_les_surcouches():
    """Il ne manipule que les deux registres d'acteurs d'electrodes."""
    import inspect

    source = inspect.getsource(View3DStimulationMixin._native_electrode_actors)
    assert '"_elec_actors", "_elec_label_actors"' in source

    entree = inspect.getsource(View3DStimulationMixin.enter_stimulation_mode)
    for interdit in ("slice", "overlay", "parcellation", "pial", "camera"):
        assert interdit not in entree.lower()


# ============================ les filtres retirent des contacts


def test_sans_filtre_tous_les_contacts_sont_la():
    """La demande: on les voit toutes, et c'est le filtre qui retire."""
    page = _Page()
    page.enter_stimulation_mode()
    maille = next(
        m for m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    # A va de x=0 a x=14 en LPS, B est a z=10: les deux electrodes sont la.
    assert maille.bounds[0] < -13.0
    assert maille.bounds[5] > 9.0


def test_un_filtre_ne_garde_que_les_contacts_retenus():
    page = _Page()
    page.enter_stimulation_mode()

    filtres = st.empty_filters()
    filtres["habitual"] = {"identical"}
    page.set_stimulation_filters(filtres)

    maille = next(
        m for m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    # Seule stim-1 passe: A1 et A2, soit x=0 et x=-2 en RAS, plus le
    # rayon des billes. A8 serait a -14, B a z=10.
    assert maille.bounds[0] > -4.0
    assert maille.bounds[1] < 2.0
    assert maille.bounds[5] < 2.0


def test_un_filtre_qui_ne_garde_rien_n_affiche_aucun_contact():
    page = _Page()
    page.enter_stimulation_mode()

    filtres = st.empty_filters()
    filtres["categories"] = {"auditory"}
    page.set_stimulation_filters(filtres)

    assert not any(
        k.get("name") == "stimulation_grey_contacts" for _m, k in _meshes(page)
    )


def test_enlever_le_filtre_ramene_tous_les_contacts():
    page = _Page()
    page.enter_stimulation_mode()

    filtres = st.empty_filters()
    filtres["habitual"] = {"identical"}
    page.set_stimulation_filters(filtres)
    page.set_stimulation_filters(st.empty_filters())

    maille = next(
        m for m, k in _meshes(page) if k.get("name") == "stimulation_grey_contacts"
    )
    assert maille.bounds[5] > 9.0


def test_un_filtre_pose_est_reconnu_comme_tel():
    assert st.filters_are_active(st.empty_filters()) is False
    assert st.filters_are_active(None) is False

    pose = st.empty_filters()
    pose["categories"] = {"motor"}
    assert st.filters_are_active(pose) is True

    borne = st.empty_filters()
    borne["min_intensity_ma"] = 2.0
    assert st.filters_are_active(borne) is True

    muets = st.empty_filters()
    muets["include_silent"] = False
    assert st.filters_are_active(muets) is True


def test_les_contacts_d_une_stimulation_sont_ses_deux_bouts():
    cartes = _cartes()
    assert st.contacts_of([cartes[0]]) == {("A", 0), ("A", 1)}


def test_un_monopolaire_n_a_qu_un_contact():
    carte = st.new_record(electrode="A", contact=3, polarity="monopolar")
    assert st.contacts_of([carte]) == {("A", 3)}


# ============================ ajouter depuis la fenetre des resultats


def test_la_fenetre_porte_un_bouton_ajouter(fenetre):
    """Une fenetre de resultats ou l'on ne peut rien creer obligeait a
    ressortir pour faire le geste ailleurs."""
    assert fenetre.btn_add is not None
    assert fenetre.btn_add.isEnabled()


def test_le_bouton_ajouter_marche_meme_sans_carte(app):
    d = StimulationResultsDialog(_Etat([]))
    assert d.btn_add.isEnabled()
    d.close()


def test_ajouter_depuis_la_fenetre(app, monkeypatch):
    """La fiche saisie rejoint la liste, avec un identifiant neuf."""
    from neuxelec.ui import stimulation_results_dialog as mod

    etat = _Etat()
    d = StimulationResultsDialog(etat)

    class _Saisie:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return int(mod.QDialog.DialogCode.Accepted)

        def record(self):
            return st.new_record(electrode="B", contact=2, electrode_b="B", contact_b=3)

    monkeypatch.setattr(mod, "QDialog", mod.QDialog)
    monkeypatch.setitem(
        __import__("sys").modules,
        "neuxelec.ui.stimulation_dialog",
        type("M", (), {"StimulationDialog": _Saisie}),
    )

    d.add_stimulation()
    assert len(d._records()) == 4
    assert d._records()[-1]["electrode"] == "B"
    assert d._records()[-1]["id"] == "stim-4"
    assert d.lst_cards.count() == 4
    d.close()


def test_ajouter_sans_electrode_le_dit(app, monkeypatch):
    from neuxelec.ui import stimulation_results_dialog as mod

    appels = []
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog,
        "warning",
        classmethod(lambda cls, *a, **k: appels.append(a)),
    )

    etat = _Etat([])
    etat.electrodes = []
    d = StimulationResultsDialog(etat)
    d.add_stimulation()
    assert appels
    d.close()


def test_le_contact_de_depart_se_choisit_dans_la_saisie(app):
    """C'est ce qui permet d'ouvrir la saisie sans designer de contact."""
    from neuxelec.ui.stimulation_dialog import StimulationDialog

    d = StimulationDialog(_electrodes(), 0, 0)
    assert d.cmb_first.isEditable()

    d.cmb_first.setEditText("B2")
    carte = d.record()
    assert carte["electrode"] == "B"
    assert carte["contact"] == 1
    # Le second suit, sinon la paire resterait a cheval sans qu'on l'ait
    # demande.
    assert carte["electrode_b"] == "B"
    d.close()


def test_un_contact_de_depart_inconnu_bloque(app):
    from neuxelec.ui.stimulation_dialog import StimulationDialog

    d = StimulationDialog(_electrodes(), 0, 0)
    d.cmb_first.setEditText("Z9")
    assert d.pair_is_impossible()
    assert "Z9" in d.pair_problem()
    d.close()


# ============================ exporter depuis la fenetre


def test_la_fenetre_porte_un_bouton_exporter(fenetre):
    assert fenetre.btn_export is not None
    assert fenetre.btn_export.isEnabled()


def test_exporter_sans_rien_le_dit(app, monkeypatch):
    from neuxelec.ui import stimulation_results_dialog as mod

    appels = []
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog,
        "warning",
        classmethod(lambda cls, *a, **k: appels.append(a)),
    )

    d = StimulationResultsDialog(_Etat([]))
    d.export_stimulations()
    assert appels
    d.close()


def test_exporter_ecrit_le_fichier_choisi(app, monkeypatch, tmp_path):
    from neuxelec.ui import stimulation_results_dialog as mod

    cible = tmp_path / "sortie.csv"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    d = StimulationResultsDialog(_Etat())
    d.export_stimulations()

    assert cible.exists()
    lignes = cible.read_text(encoding="utf-8").splitlines()
    # Une entete et trois stimulations.
    assert len(lignes) == 4
    assert lignes[0].startswith("id,")
    d.close()


def test_annuler_l_export_n_ecrit_rien(app, monkeypatch, tmp_path):
    from neuxelec.ui import stimulation_results_dialog as mod

    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )

    d = StimulationResultsDialog(_Etat())
    d.export_stimulations()
    assert list(tmp_path.iterdir()) == []
    d.close()


def test_un_echec_d_ecriture_est_dit(app, monkeypatch):
    from neuxelec.ui import stimulation_results_dialog as mod

    monkeypatch.setattr(
        mod.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("Z:/nulle/part/impossible.csv", "")),
    )
    appels = []
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog,
        "critical",
        classmethod(lambda cls, *a, **k: appels.append(a)),
    )

    d = StimulationResultsDialog(_Etat())
    d.export_stimulations()
    assert appels
    d.close()


def test_exporter_est_dans_la_barre_de_la_fenetre(fenetre):
    """Il emporte tout, donc il n'a pas sa place a cote de Modifier et
    Supprimer, qui agissent sur la fiche choisie."""
    assert fenetre.btn_export.parent() is not fenetre.btn_edit.parent()
    assert fenetre.btn_export.parent() is fenetre.btn_close.parent()


def test_exporter_ignore_la_fiche_choisie(app, monkeypatch, tmp_path):
    """La question posee: est-ce que ca n'exporte qu'une seule fiche."""
    from neuxelec.ui import stimulation_results_dialog as mod

    cible = tmp_path / "tout.csv"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    etat = _Etat()
    d = StimulationResultsDialog(etat)
    d.lst_cards.setCurrentRow(1)

    d.export_stimulations()

    lignes = cible.read_text(encoding="utf-8").splitlines()
    # Une entete et les trois stimulations, pas seulement celle choisie.
    assert len(lignes) == 1 + len(etat.stimulations)
    d.close()
