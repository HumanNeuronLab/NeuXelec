# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Poser un marqueur: la croix suit la souris, le clic la laisse.

LE GESTE DEMANDE

Avant, le marqueur allait au point du clic droit qui ouvrait le menu: il
fallait viser avant de savoir qu'on visait, et on ne voyait le resultat
qu'une fois la fenetre ouverte.

Maintenant: le menu arme la pose, le curseur devient une croix, le clic
gauche pose le marqueur sur la coupe qui est dessous, et la fenetre des
parametres s'ouvre ensuite.

Une croix rouge etait aussi dessinee dans la scene et suivait la souris.
Elle a ete retiree: redessiner toute la scene a chaque mouvement la
faisait trainer derriere le curseur, et deux croix decalees disent moins
qu'une.

CE QUE CES TESTS PROTEGENT

1. La coupe est reconnue: un marqueur sait sur quelle image il a ete
   pose, ce qu'un point dans l'espace ne dit pas.
2. Rien n'est dessine pendant la pose: le curseur en croix suffit, et
   la scene reste aussi vive qu'avant pendant qu'on vise.
3. Les boutons sont consommes, pas les simples mouvements: un
   glissement ne peut partir que d'un appui, et l'appui n'atteint
   jamais la camera.
4. Un clic hors des coupes ne pose rien et n'annule pas: ce n'est pas un
   endroit.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.view3d_markers import View3DMarkersMixin  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Acteur:
    def __init__(self, nom):
        self.nom = nom

    def PickableOff(self):
        pass


class _Plotter:
    def __init__(self):
        self.scene: dict = {}

    def add_mesh(self, mesh, **kwargs):
        acteur = _Acteur(kwargs.get("name", ""))
        self.scene[acteur] = (mesh, kwargs)
        return acteur

    def remove_actor(self, actor, **_kwargs):
        self.scene.pop(actor, None)


class _Interacteur:
    def __init__(self):
        self.curseur = None

    def setCursor(self, forme):
        self.curseur = forme

    def unsetCursor(self):
        self.curseur = None


class _Page(View3DMarkersMixin):
    """Le mixin sur un decor minimal, avec trois plans sous la souris."""

    def __init__(self, sous_la_souris=None):
        self.plotter = _Plotter()
        self.interactor = _Interacteur()
        self._marker_placing = False
        self._marker_placing_ras = None
        self._marker_placing_plane = None
        self._marker_placement_actor = None
        self.rendus = 0
        self.crees = []

        self._coronal_plane_actor = _Acteur("coronal")
        self._axial_plane_actor = _Acteur("axial")
        self._sagittal_plane_actor = _Acteur("sagittal")
        self._axial_pet_actor = _Acteur("axial-pet")

        for nom in (
            "_coronal_pet_actor",
            "_coronal_siscom_actor",
            "_axial_siscom_actor",
            "_sagittal_pet_actor",
            "_sagittal_siscom_actor",
        ):
            setattr(self, nom, None)

        #: Ce que la pioche VTK renverra: (acteur, point).
        self._sous_la_souris = sous_la_souris or (None, None)

    def _vtk_pick_actor_and_ras_from_qpos(self, qpos):
        return self._sous_la_souris

    def _render(self):
        self.rendus += 1

    def _create_marker_at_ras(self, ras, plane=""):
        self.crees.append((list(ras), plane))


def _souris(kind, bouton=Qt.LeftButton, x=10.0, y=10.0):
    return QMouseEvent(
        kind, QPointF(x, y), bouton, bouton, Qt.NoModifier
    )


def _touche(cle):
    return QKeyEvent(QEvent.KeyPress, cle, Qt.NoModifier)


# ------------------------------------------- reconnaitre la coupe


@pytest.mark.parametrize("plan", ["coronal", "axial", "sagittal"])
def test_chaque_plan_est_reconnu(app, plan):
    page = _Page()
    acteur = getattr(page, f"_{plan}_plane_actor")
    page._sous_la_souris = (acteur, (1.0, 2.0, 3.0))
    assert page._slice_under_qpos(None) == (plan, (1.0, 2.0, 3.0))


def test_une_surcouche_compte_pour_sa_coupe(app):
    """Le TEP d'une coupe axiale est encore la coupe axiale."""
    page = _Page()
    page._sous_la_souris = (page._axial_pet_actor, (0.0, 0.0, 0.0))
    assert page._slice_under_qpos(None)[0] == "axial"


def test_le_cerveau_n_est_pas_une_coupe(app):
    """Un marqueur pose sur la surface ne serait sur aucune image."""
    page = _Page()
    page._sous_la_souris = (_Acteur("pie-mere"), (0.0, 0.0, 0.0))
    assert page._slice_under_qpos(None) == (None, None)


def test_le_vide_n_est_pas_une_coupe(app):
    assert _Page()._slice_under_qpos(None) == (None, None)


# ------------------------------------------- armer la pose


def test_armer_met_le_curseur_en_croix(app):
    page = _Page()
    page.begin_marker_placement()
    assert page.marker_placement_active()
    assert page.interactor.curseur == Qt.CrossCursor


def test_armer_ne_pose_rien_tout_de_suite(app):
    page = _Page()
    page.begin_marker_placement()
    assert page.crees == []
    assert page.plotter.scene == {}


def test_sans_plotter_armer_ne_leve_pas(app):
    page = _Page()
    page.plotter = None
    page.begin_marker_placement()
    assert not page.marker_placement_active()


# ------------------------------------------- la croix suit la souris


def test_rien_n_est_dessine_pendant_la_pose(app):
    """Le curseur en croix suffit. Une croix dessinee dans la scene
    trainait derriere la souris, puisqu'il fallait tout redessiner."""
    page = _Page()
    page.begin_marker_placement()
    page._sous_la_souris = (page._axial_plane_actor, (1.0, 2.0, 3.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseMove))
    assert page.plotter.scene == {}


def test_le_mouvement_n_est_pas_consomme(app):
    """Il ne change rien: le laisser passer garde la vue aussi vive."""
    page = _Page()
    page.begin_marker_placement()
    assert page._handle_marker_placement_event(_souris(QEvent.MouseMove)) is False


# ------------------------------------------- le clic la laisse


def test_le_clic_gauche_pose_le_marqueur(app):
    page = _Page()
    page.begin_marker_placement()
    page._sous_la_souris = (page._coronal_plane_actor, (4.0, 5.0, 6.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseMove))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))

    assert page.crees == [([4.0, 5.0, 6.0], "coronal")]
    assert not page.marker_placement_active()


def test_poser_rend_le_curseur(app):
    page = _Page()
    page.begin_marker_placement()
    page._sous_la_souris = (page._axial_plane_actor, (0.0, 0.0, 0.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page.interactor.curseur is None


def test_un_clic_hors_des_coupes_ne_pose_rien(app):
    """Ce n'est pas un endroit: la pose reste armee."""
    page = _Page()
    page.begin_marker_placement()
    page._sous_la_souris = (_Acteur("pie-mere"), (0.0, 0.0, 0.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page.crees == []
    assert page.marker_placement_active()


# ------------------------------------------- annuler


def test_le_clic_droit_annule(app):
    page = _Page()
    page.begin_marker_placement()
    page._handle_marker_placement_event(
        _souris(QEvent.MouseButtonPress, Qt.RightButton)
    )
    assert not page.marker_placement_active()
    assert page.crees == []


def test_echap_annule(app):
    page = _Page()
    page.begin_marker_placement()
    page._handle_marker_placement_event(_touche(Qt.Key_Escape))
    assert not page.marker_placement_active()


def test_annuler_rend_le_curseur(app):
    page = _Page()
    page.begin_marker_placement()
    page.cancel_marker_placement()
    assert page.interactor.curseur is None


# ------------------------------------------- rien ne passe pendant la pose


@pytest.mark.parametrize(
    "evenement",
    [QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick],
)
def test_les_boutons_sont_consommes_pendant_la_pose(app, evenement):
    """Un glissement ne peut partir que d'un appui, et l'appui n'atteint
    jamais la camera."""
    page = _Page()
    page.begin_marker_placement()
    assert page._handle_marker_placement_event(_souris(evenement)) is True


def test_le_clic_du_milieu_est_consomme_aussi(app):
    page = _Page()
    page.begin_marker_placement()
    assert (
        page._handle_marker_placement_event(
            _souris(QEvent.MouseButtonPress, Qt.MiddleButton)
        )
        is True
    )


def test_hors_pose_rien_n_est_consomme(app):
    page = _Page()
    assert page._handle_marker_placement_event(_souris(QEvent.MouseMove)) is False
    assert page._handle_marker_placement_event(_touche(Qt.Key_Escape)) is False
    assert (
        page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress)) is False
    )


# ------------------------------------------- le guide le dit


def test_le_guide_decrit_le_nouveau_geste():
    """Le geste a change: le guide ne doit pas decrire l'ancien."""
    from neuxelec.help.content import MANUAL_SECTIONS

    corps = next(s.body for s in MANUAL_SECTIONS if s.id == "view3d")
    assert "arms the placement" in corps
    assert "the cursor becomes a cross" in corps
    assert "Export all" in corps


def test_l_abandon_est_documente():
    from neuxelec.help.content import SHORTCUTS

    lignes = [a for _c, t, a in SHORTCUTS if "placing a marker" in t]
    assert len(lignes) == 1
    assert "Esc" in lignes[0]


# ================================================== deplacer un marqueur


class _PageAvecMarqueurs(_Page):
    """La page, avec de quoi retrouver et redessiner les marqueurs."""

    def __init__(self, marqueurs=None, **kwargs):
        super().__init__(**kwargs)
        self._marqueurs = list(marqueurs or [])
        self._marker_moving_id = ""
        self.redessins = 0
        self.sauvegardes = 0

    def _marker_by_id(self, marker_id):
        for m in self._marqueurs:
            if str(m.get("id")) == str(marker_id):
                return m

        return None

    def _render_anatomical_markers(self):
        self.redessins += 1

    def _save_markers_to_project_json(self):
        self.sauvegardes += 1

    def _refresh_marker_list_dialog(self):
        pass


def _page_avec_un_marqueur():
    return _PageAvecMarqueurs(
        marqueurs=[
            {
                "id": "m1",
                "name": "Lesion",
                "ras": [0.0, 0.0, 0.0],
                "plane": "axial",
                "color": "#FF3B30",
                "size_mm": 4.0,
            }
        ]
    )


def test_reprendre_un_marqueur_arme_la_pose(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    assert page.marker_placement_active()
    assert page.marker_being_moved() == "m1"
    assert page.interactor.curseur == Qt.CrossCursor


def test_un_marqueur_inconnu_n_arme_rien(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("jamais-vu")
    assert not page.marker_placement_active()


def test_deplacer_arme_le_meme_geste(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._coronal_plane_actor, (9.0, 8.0, 7.0))
    assert page.marker_placement_active()
    assert page.plotter.scene == {}


def test_le_clic_deplace_le_marqueur(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._coronal_plane_actor, (9.0, 8.0, 7.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))

    marqueur = page._marker_by_id("m1")
    assert marqueur["ras"] == [9.0, 8.0, 7.0]
    assert marqueur["plane"] == "coronal"


def test_deplacer_ne_redemande_pas_les_parametres(app):
    """Il a deja un nom: le lui redemander serait une corvee."""
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._axial_plane_actor, (1.0, 1.0, 1.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page.crees == []


def test_deplacer_garde_le_reste_du_marqueur(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._axial_plane_actor, (1.0, 1.0, 1.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))

    marqueur = page._marker_by_id("m1")
    assert marqueur["name"] == "Lesion"
    assert marqueur["color"] == "#FF3B30"
    assert marqueur["size_mm"] == 4.0


def test_deplacer_redessine_et_enregistre(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._axial_plane_actor, (1.0, 1.0, 1.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page.redessins == 1
    assert page.sauvegardes == 1


def test_le_deplacement_change_de_coupe(app):
    """Un marqueur pose sur l'axiale peut finir sur la coronale."""
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (page._sagittal_plane_actor, (2.0, 3.0, 4.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page._marker_by_id("m1")["plane"] == "sagittal"


def test_abandonner_un_deplacement_ne_bouge_rien(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._handle_marker_placement_event(_touche(Qt.Key_Escape))
    assert page._marker_by_id("m1")["ras"] == [0.0, 0.0, 0.0]
    assert page.marker_being_moved() == ""


def test_un_clic_hors_des_coupes_ne_deplace_pas(app):
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page._sous_la_souris = (_Acteur("pie-mere"), (5.0, 5.0, 5.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page._marker_by_id("m1")["ras"] == [0.0, 0.0, 0.0]
    assert page.marker_placement_active()


def test_poser_un_neuf_apres_un_deplacement_annule_cree_bien_un_neuf(app):
    """Le piege: garder le marqueur repris et deplacer au lieu de creer."""
    page = _page_avec_un_marqueur()
    page.begin_marker_move("m1")
    page.cancel_marker_placement()
    page.begin_marker_placement()
    page._sous_la_souris = (page._axial_plane_actor, (3.0, 3.0, 3.0))
    page._handle_marker_placement_event(_souris(QEvent.MouseButtonPress))
    assert page.crees == [([3.0, 3.0, 3.0], "axial")]
    assert page._marker_by_id("m1")["ras"] == [0.0, 0.0, 0.0]


def test_le_guide_decrit_le_deplacement():
    from neuxelec.help.content import MANUAL_SECTIONS

    corps = next(s.body for s in MANUAL_SECTIONS if s.id == "view3d")
    assert "Move marker" in corps
    assert "picks it back up" in corps


# ================================================== exporter tous les marqueurs


class _PageExport(_PageAvecMarqueurs):
    """De quoi ecrire un fichier sans ouvrir de vraie fenetre."""

    def __init__(self, marqueurs=None, patient="P1", **kwargs):
        super().__init__(marqueurs=marqueurs, **kwargs)
        self.state = type("E", (), {"patient_id": patient})()

    def _markers(self):
        # Sans cela la vraie methode lirait l'etat, trouverait une liste
        # vide, et le vrai dialogue d'avertissement bloquerait le test.
        return list(self._marqueurs)

    def _dialog_parent(self):
        return None


def _trois_marqueurs():
    return [
        {
            "id": "m1",
            "name": "Lesion",
            "type": "Lesion",
            "ras": [1.0, 2.0, 3.0],
            "plane": "axial",
            "color": "#FF3B30",
            "size_mm": 4.0,
            "description": "la cible",
            "voxel_xyz": [10.0, 20.0, 30.0],
        },
        {"id": "m2", "name": "Entry", "ras": [4.0, 5.0, 6.0], "size_mm": 3.0},
        {"id": "m3", "name": "Target", "ras": [7.0, 8.0, 9.0], "size_mm": 2.0},
    ]


def test_le_fichier_contient_tous_les_marqueurs(app, monkeypatch, tmp_path):
    """La demande: un fichier qui regroupe toute la liste."""
    from neuxelec.pages import view3d_markers as mod

    cible = tmp_path / "tous.txt"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    page = _PageExport(_trois_marqueurs())
    page._export_all_markers()

    texte = cible.read_text(encoding="utf-8")
    assert "3 marker(s)" in texte
    for nom in ("Lesion", "Entry", "Target"):
        assert f"Name: {nom}" in texte


def test_le_fichier_nomme_le_patient(app, monkeypatch, tmp_path):
    from neuxelec.pages import view3d_markers as mod

    cible = tmp_path / "tous.txt"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    page = _PageExport(_trois_marqueurs(), patient="PAT42")
    page._export_all_markers()
    assert "Patient: PAT42" in cible.read_text(encoding="utf-8")


def test_le_fichier_porte_les_coordonnees_et_la_coupe(app, monkeypatch, tmp_path):
    from neuxelec.pages import view3d_markers as mod

    cible = tmp_path / "tous.txt"
    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(cible), ""))
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    page = _PageExport(_trois_marqueurs())
    page._export_all_markers()

    texte = cible.read_text(encoding="utf-8")
    assert "X: 1.00" in texte
    assert "axial slice" in texte
    assert "i: 10.00" in texte


def test_une_liste_vide_le_dit(app, monkeypatch):
    from neuxelec.pages import view3d_markers as mod

    appels = []
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog,
        "warning",
        classmethod(lambda cls, *a, **k: appels.append(a)),
    )

    page = _PageExport([])
    page._export_all_markers()
    assert appels


def test_annuler_n_ecrit_rien(app, monkeypatch, tmp_path):
    from neuxelec.pages import view3d_markers as mod

    monkeypatch.setattr(
        mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )

    page = _PageExport(_trois_marqueurs())
    page._export_all_markers()
    assert list(tmp_path.iterdir()) == []


def test_l_extension_est_ajoutee(app, monkeypatch, tmp_path):
    from neuxelec.pages import view3d_markers as mod

    monkeypatch.setattr(
        mod.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "sans_extension"), "")),
    )
    monkeypatch.setattr(
        mod.NeuXelecMessageDialog, "information", classmethod(lambda cls, *a, **k: None)
    )

    page = _PageExport(_trois_marqueurs())
    page._export_all_markers()
    assert (tmp_path / "sans_extension.txt").exists()


def test_la_liste_porte_le_bouton(app):
    """A cote de Fermer: il emporte toute la liste."""
    from neuxelec.ui.marker_list_dialog import MarkerListDialog

    d = MarkerListDialog(markers_provider=lambda: [])
    assert d.btn_export_all is not None
    assert d.btn_export_all.parent() is d.btn_close.parent()
    d.close()


def test_le_clic_droit_de_la_liste_ne_propose_plus_l_export_unitaire():
    """Deux exports voisins qui ne font pas la meme chose: celui de la
    liste emporte tout, il reste seul.

    Lu dans la source: PySide ne laisse pas remplacer exec sur la classe
    QMenu, et ouvrir le vrai menu bloquerait le test pour toujours.
    """
    import inspect

    from neuxelec.ui.marker_list_dialog import MarkerListDialog

    source = inspect.getsource(MarkerListDialog._open_context_menu)
    assert '"Export marker"' not in source
    # Le reste du menu n'a pas bouge.
    assert '"Edit marker"' in source
    assert '"Delete marker"' in source


def test_le_bouton_de_la_liste_reste_le_seul_export(app):
    from neuxelec.ui.marker_list_dialog import MarkerListDialog

    d = MarkerListDialog(markers_provider=lambda: [])
    assert d.btn_export_all is not None
    assert not hasattr(d, "exportMarker")
    d.close()
