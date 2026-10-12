"""De la saisie au marqueur, en passant par le fichier de projet.

POURQUOI UN TEST QUI TRAVERSE TOUT

Chaque etage est deja teste separement. Ce qui ne l'est pas, c'est leur
raccord: la fenetre produit une carte, le projet l'ecrit et la relit, les
filtres la laissent passer, la scene la dessine, et la fenetre des
resultats la liste. Une seule cle mal nommee entre deux etages ne se voit
dans aucun test d'etage.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec import project_io  # noqa: E402
from neuxelec.pages.view3d_stimulation import View3DStimulationMixin  # noqa: E402
from neuxelec.ui.stimulation_dialog import StimulationDialog  # noqa: E402
from neuxelec.ui.stimulation_results_dialog import StimulationResultsDialog  # noqa: E402
from neuxelec.utils import stimulation as st  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Etat:
    def __init__(self):
        self.patient_id = "CHAINE"
        self.electrodes = [
            {"name": "A", "contacts_lps": [[float(i) * 2.0, 0.0, 0.0] for i in range(8)]}
        ]
        self.stimulations = []


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
    def __init__(self):
        self.scene: dict = {}

    @property
    def meshes(self):
        return list(self.scene.values())

    def add_mesh(self, mesh, **kwargs):
        acteur = _Acteur()
        self.scene[acteur] = (mesh, kwargs)
        return acteur

    def remove_actor(self, actor, **_kwargs):
        self.scene.pop(actor, None)


class _Page(View3DStimulationMixin):
    """Le mixin en mode Stimulation Result, sans Qt ni VTK."""

    def __init__(self, state):
        self.state = state
        self.plotter = _Plotter()
        self.interactor = None
        self.container_3d = None
        self.ui = None
        self._stimulation_mode = True
        self._stim_marker_actors = {}
        self._stim_filters = {}
        self._stim_hidden_electrodes = {}
        self._stim_results_dialog = None
        self._elec_actors = {}
        self._elec_label_actors = {}

    def _mni_t1_slices_are_visible(self):
        return False

    def _render(self):
        pass

    def tubes(self):
        return [
            (m, k) for m, k in self.plotter.meshes if "tube" in k.get("name", "")
        ]


def _saisir(app, etat, **reglages):
    """Remplir la fenetre comme le ferait un epileptologiste, et ranger."""
    noms = {("A", 0): "ctx-lh-hippocampus", ("A", 1): "wm-lh-temporal"}
    dialogue = StimulationDialog(
        etat.electrodes,
        0,
        int(reglages.get("contact", 0)),
        anatomy_lookup=lambda nom, i: noms.get((nom, i)),
    )

    dialogue.cmb_frequency.setCurrentText(str(reglages.get("hz", 1)))
    dialogue.spn_current.setValue(float(reglages.get("ma", 3.0)))

    for cle in reglages.get("events", []):
        dialogue.chk_events[cle].setChecked(True)

    if reglages.get("habitual"):
        dialogue.cmb_habitual.setCurrentIndex(
            dialogue.cmb_habitual.findData(reglages["habitual"])
        )

    for categorie, descripteur, lieu in reglages.get("responses", []):
        ligne = dialogue._add_response()
        ligne.cmb_category.setCurrentIndex(ligne.cmb_category.findData(categorie))
        ligne.cmb_descriptor.setCurrentIndex(
            ligne.cmb_descriptor.findText(descripteur)
        )

        if lieu:
            ligne.cmb_location.setCurrentText(lieu)

    dialogue.txt_notes.setPlainText(reglages.get("notes", ""))

    carte = dialogue.record()
    carte["id"] = st.next_id(etat.stimulations)
    etat.stimulations.append(carte)
    dialogue.close()
    return carte


def _aller_retour(etat):
    data = json.loads(json.dumps(project_io.build_project_dict_from_state(etat)))
    relu = _Etat()
    project_io.apply_project_dict_to_state(relu, data, "projet.nxp")
    return relu


# ----------------------------------------------------- la chaine entiere


def test_une_stimulation_saisie_se_retrouve_dessinee(app):
    etat = _Etat()
    _saisir(
        app,
        etat,
        hz=1,
        ma=3.0,
        events=["seizure_electroclinical"],
        habitual="identical",
        responses=[("motor", "Clonic jerks", "Hand")],
        notes="aura habituelle reconnue par le patient",
    )

    relu = _aller_retour(etat)
    page = _Page(relu)
    page.refresh_stimulation_markers()

    # Un tube entre les deux contacts, et les deux contacts en gris.
    assert len(page.tubes()) == 1
    maille, options = page.tubes()[0]
    # A1 en LPS x=0, A2 en x=2, donc en RAS x=0 et x=-2.
    assert round(maille.bounds[0], 2) == -2.0
    assert round(maille.bounds[1], 2) == 0.0
    assert options["color"] == st.COLOUR_HABITUAL


def test_la_carte_traverse_le_projet_sans_rien_perdre(app):
    etat = _Etat()
    depart = _saisir(
        app,
        etat,
        hz=50,
        ma=2.5,
        events=["after_discharges"],
        responses=[("somatosensory", "Tingling or paresthesia", "Hand")],
        notes="une note",
    )

    arrivee = _aller_retour(etat).stimulations[0]
    assert arrivee == depart


def test_l_anatomie_saisie_se_relit_sur_la_carte(app):
    etat = _Etat()
    _saisir(app, etat, responses=[("visual", "Phosphenes", "Central")])
    relu = _aller_retour(etat)

    for label, valeur in st.card_fields(relu.stimulations[0]):
        if label == "Anatomy":
            assert "ctx-lh-hippocampus" in valeur
            assert "wm-lh-temporal" in valeur
            return

    pytest.fail("la carte ne porte pas l'anatomie")


def test_plusieurs_stimulations_recoivent_des_identifiants_distincts(app):
    etat = _Etat()
    _saisir(app, etat, contact=0)
    _saisir(app, etat, contact=2)
    _saisir(app, etat, contact=4)
    assert [c["id"] for c in etat.stimulations] == ["stim-1", "stim-2", "stim-3"]


def test_les_filtres_de_la_fenetre_pilotent_la_scene(app):
    etat = _Etat()
    _saisir(app, etat, contact=0, hz=1, ma=3.0, events=["seizure_electroclinical"])
    _saisir(app, etat, contact=2, hz=50, ma=1.0, events=["after_discharges"])
    _saisir(app, etat, contact=4, hz=50, ma=5.0)

    page = _Page(etat)
    fenetre = StimulationResultsDialog(
        etat, on_filters_changed=page.set_stimulation_filters
    )

    assert fenetre.lst_cards.count() == 3
    assert "3 / 3" in fenetre.lbl_count.text()

    fenetre.chk_frequencies[50.0].setChecked(True)
    assert "2 / 3" in fenetre.lbl_count.text()
    assert len(page.tubes()) == 2

    fenetre.chk_silent.setChecked(False)
    assert "1 / 3" in fenetre.lbl_count.text()

    fenetre.reset_filters()
    assert "3 / 3" in fenetre.lbl_count.text()

    fenetre.close()


def test_une_carte_corrigee_garde_son_identifiant(app):
    """Le piege: une correction qui cree une seconde carte."""
    etat = _Etat()
    _saisir(app, etat, contact=0, ma=3.0)

    carte = etat.stimulations[0]
    dialogue = StimulationDialog(etat.electrodes, 0, 0, record=carte)
    dialogue.spn_current.setValue(5.0)
    corrigee = dialogue.record()
    corrigee["id"] = carte["id"]
    dialogue.close()

    etat.stimulations = [corrigee]
    assert len(etat.stimulations) == 1
    assert etat.stimulations[0]["id"] == "stim-1"
    assert etat.stimulations[0]["intensity_ma"] == 5.0


def test_une_paire_muette_arrive_jusqu_a_la_scene_en_gris(app):
    """Teste sans reponse est un resultat, pas une absence de resultat."""
    etat = _Etat()
    _saisir(app, etat, contact=0, ma=5.0)

    relu = _aller_retour(etat)
    page = _Page(relu)
    page.refresh_stimulation_markers()

    _maille, options = page.tubes()[0]
    assert options["color"] == st.COLOUR_SILENT
    assert "no response at 5 mA" in st.card_text(relu.stimulations[0])


# ------------------------------------- la fenetre ne reste pas perimee


def test_une_carte_ajoutee_apparait_dans_la_fenetre_ouverte(app):
    """Une liste qui se perime en silence est pire qu'une liste absente."""
    etat = _Etat()
    _saisir(app, etat, contact=0)

    page = _Page(etat)
    fenetre = StimulationResultsDialog(
        etat, on_filters_changed=page.set_stimulation_filters
    )
    page._stim_results_dialog = fenetre

    assert fenetre.lst_cards.count() == 1

    # Ce que fait le clic droit depuis la liste des electrodes.
    _saisir(app, etat, contact=2)
    page.refresh_stimulation_markers()

    assert fenetre.lst_cards.count() == 2
    assert "2 / 2" in fenetre.lbl_count.text()

    fenetre.close()


def test_recharger_garde_la_carte_qu_on_lisait(app):
    etat = _Etat()
    _saisir(app, etat, contact=0)
    _saisir(app, etat, contact=2)

    fenetre = StimulationResultsDialog(etat)
    fenetre.lst_cards.setCurrentRow(1)
    assert fenetre.selected_id() == "stim-2"

    fenetre.reload()
    assert fenetre.selected_id() == "stim-2"

    fenetre.close()


def test_la_fenetre_des_resultats_n_est_pas_modale():
    """Son premier onglet n'a de sens que si la scene reste manipulable."""
    import inspect

    from neuxelec.pages.view3d_stimulation import View3DStimulationMixin

    source = inspect.getsource(
        View3DStimulationMixin._open_stimulation_results_dialog
    )
    assert "setModal(False)" in source
    assert "dialog.show()" in source
    assert "dialog.exec()" not in source
