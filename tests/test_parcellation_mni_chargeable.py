# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La seconde parcellation du repere MNI, chargee par l'utilisateur.

POURQUOI ELLE MANQUAIT

La case 1 du repere MNI porte le Schaefer 2018 fourni avec NeuXelec.
La case 2 tenait le Brainnetome, accorde pour un usage non commercial
avec partage a l'identique : une restriction que l'article 7 de la
GPL-3.0 ne permet pas de transmettre a qui recoit NeuXelec. Elle est
donc restee vide, et sa case a cocher grisee.

CE QUI CHANGE

Le bouton Load parcellation demande d'abord le repere. En MNI, le
fichier choisi remplit la case 2, et le cockpit le montre.

CE QUE LA VERIFICATION ATTRAPE

Un atlas qui ne decrit pas le meme endroit du monde que le gabarit, et
qui se poserait donc a cote du cerveau. Elle compare les boites
englobantes **physiques** et non les grilles : deux atlas du meme
repere peuvent avoir des champs de vue et des tailles de voxel
differents sans se contredire. La mesure elle-meme est eprouvee dans
test_geometrie_parcellation.

Un avertissement de moins, note au passage : l'ancien fichier
Brainnetome a beau tenir sur une grille de 182x218x182 la ou le
gabarit fait 193x229x193, leurs cosinus directeurs different aussi, et
une fois ceux-ci pris en compte les deux boites se superposent. La
difference de grille ne disait donc rien du repere.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile  # noqa: E402
from PySide6.QtUiTools import QUiLoader  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel  # noqa: E402

from neuxelec.pages.files_page import FilesPage  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402
from neuxelec.state import AppState  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _image(taille, origine, valeur=1, pas=1.0, direction=None):
    arr = np.full(tuple(reversed(taille)), valeur, dtype=np.int16)
    img = sitk.GetImageFromArray(arr)
    img.SetSpacing((pas, pas, pas))
    img.SetOrigin(origine)
    if direction is not None:
        img.SetDirection(direction)
    return img


#: Les deux geometries reelles : le gabarit, et l'ancien Brainnetome.
GABARIT = ((193, 229, 193), (96.0, 132.0, -78.0))
AUTRE_MNI = ((182, 218, 182), (-90.0, 126.0, -72.0))


# ------------------------------------------- la verification de geometrie


def test_un_atlas_du_meme_repere_passe(app):
    """Un atlas a 2 mm couvrant la meme boite que le gabarit."""
    gabarit = _image(*GABARIT)
    atlas = _image((97, 115, 97), (96.0, 132.0, -78.0), pas=2.0)
    assert FilesPage._physical_containment_fraction(atlas, gabarit) >= 0.99


def test_un_atlas_ailleurs_est_attrape(app):
    gabarit = _image(*GABARIT)
    atlas = _image((60, 60, 60), (400.0, 400.0, 400.0))
    assert FilesPage._physical_containment_fraction(atlas, gabarit) < 0.05


def test_la_difference_de_grille_seule_ne_dit_rien_du_repere(app):
    """Les deux geometries reelles, cosinus directeurs compris.

    L'ancien Brainnetome et le gabarit n'ont ni la meme taille ni la
    meme origine, et pourtant leurs boites se superposent : seul le
    signe de leurs directions differait. C'est pourquoi la
    verification ne regarde pas les grilles.
    """
    gabarit = _image(*GABARIT, direction=(-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0))
    ancien = _image(*AUTRE_MNI, direction=(1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0))

    assert gabarit.GetSize() != ancien.GetSize()
    assert FilesPage._physical_containment_fraction(ancien, gabarit) >= 0.80


# ------------------------------------------------- la table de couleurs


@pytest.mark.parametrize(
    "nom,attendus",
    [
        ("atlas.nii.gz", ["atlas_lut.tsv", "atlas.tsv"]),
        ("atlas.nii", ["atlas_lut.tsv", "atlas.tsv"]),
        ("truc.mgz", ["truc_lut.tsv", "truc.tsv"]),
        ("sans_extension", ["sans_extension_lut.tsv", "sans_extension.tsv"]),
    ],
)
def test_la_table_est_cherchee_a_cote_du_fichier(nom, attendus):
    from pathlib import Path

    trouves = [p.name for p in View3DPage._mni_lut_candidates(Path("/un/dossier") / nom)]
    assert trouves == attendus


def test_sans_chemin_aucune_table_n_est_cherchee():
    assert View3DPage._mni_lut_candidates(None) == []


# ---------------------------------------------------- la case 2 du MNI


class _Page3D:
    """Juste de quoi exercer la pose de l'atlas."""

    set_mni_parcellation2 = View3DPage.set_mni_parcellation2
    _mni_lut_candidates = staticmethod(View3DPage._mni_lut_candidates)
    _load_mni_lut_tsv = View3DPage._load_mni_lut_tsv
    _generate_simple_lut_from_image = View3DPage._generate_simple_lut_from_image

    def __init__(self):
        self.chk_parcel2 = QCheckBox()
        self.chk_parcel2.setChecked(True)
        self._mni_parcel2_img = None
        self._mni_parcel2_lut = {}
        self._mni_parcel2_name = ""
        self.etats = 0
        self.rendus = 0

    def _set_checked(self, case, valeur):
        case.blockSignals(True)
        case.setChecked(bool(valeur))
        case.blockSignals(False)

    def _update_modality_controls_enabled_states(self):
        self.etats += 1

    def _refresh_multiplanar_clipped_scene(self):
        pass

    def _render(self):
        self.rendus += 1


def test_poser_un_atlas_le_retient_avec_son_nom(app, tmp_path):
    chemin = tmp_path / "mon_atlas.nii.gz"
    sitk.WriteImage(_image((8, 8, 8), (0.0, 0.0, 0.0)), str(chemin))

    page = _Page3D()
    page.set_mni_parcellation2(sitk.ReadImage(str(chemin)), str(chemin))

    assert page._mni_parcel2_img is not None
    assert page._mni_parcel2_name == "mon_atlas.nii.gz"
    assert page.etats == 1, "l'etat des cases n'a pas ete rafraichi"


def test_la_table_voisine_est_lue(app, tmp_path):
    chemin = tmp_path / "atlas.nii.gz"
    sitk.WriteImage(_image((6, 6, 6), (0.0, 0.0, 0.0), valeur=3), str(chemin))
    (tmp_path / "atlas_lut.tsv").write_text(
        "index\tname\tcolor\n3\tMa-Region\t#FF8000\n", encoding="utf-8"
    )

    page = _Page3D()
    page.set_mni_parcellation2(sitk.ReadImage(str(chemin)), str(chemin))

    assert 3 in page._mni_parcel2_lut
    assert "Ma-Region" in str(page._mni_parcel2_lut[3])


def test_sans_table_voisine_une_table_est_fabriquee(app, tmp_path):
    """Un atlas se regarde meme sans ses couleurs d'origine."""
    chemin = tmp_path / "nu.nii.gz"
    sitk.WriteImage(_image((6, 6, 6), (0.0, 0.0, 0.0), valeur=7), str(chemin))

    page = _Page3D()
    page.set_mni_parcellation2(sitk.ReadImage(str(chemin)), str(chemin))

    assert page._mni_parcel2_lut, "aucune couleur n'a ete fabriquee"
    assert 7 in page._mni_parcel2_lut


def test_la_case_est_decochee_a_la_pose(app, tmp_path):
    """Comme pour les parcellations natives : charger n'affiche pas."""
    chemin = tmp_path / "a.nii.gz"
    sitk.WriteImage(_image((4, 4, 4), (0.0, 0.0, 0.0)), str(chemin))
    page = _Page3D()
    page.set_mni_parcellation2(sitk.ReadImage(str(chemin)), str(chemin))
    assert not page.chk_parcel2.isChecked()


def test_retirer_l_atlas_vide_la_case(app):
    page = _Page3D()
    page._mni_parcel2_img = object()
    page.set_mni_parcellation2(None, None)
    assert page._mni_parcel2_img is None
    assert page._mni_parcel2_lut == {}


# -------------------------------------------------------- le cockpit


@pytest.fixture(scope="module")
def ui(app):
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly)
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    return w


@pytest.mark.parametrize(
    "nom",
    [
        "pill_FilesCoreg_MniParcel2",
        "label_FilesCoreg_MniParcel2",
        "status_FilesCoreg_MniParcel2",
    ],
)
def test_la_ligne_de_cockpit_existe(ui, nom):
    assert ui.findChild(QLabel, nom) is not None, nom


def test_la_ligne_porte_un_nom_qui_la_distingue_du_natif(ui):
    texte = ui.findChild(QLabel, "label_FilesCoreg_MniParcel2").text()
    assert "MNI" in texte
    assert texte != ui.findChild(QLabel, "label_FilesCoreg_Parcel2").text()


def test_le_cockpit_sait_ou_est_le_fichier(app):
    """La ligne montre le chemin au survol, comme les autres."""
    etat = AppState()
    etat.mni_parcel2_path = "C:/atlas/x.nii.gz"

    class _Faux:
        state = etat
        _cockpit_path_for = FilesPage._cockpit_path_for

    assert _Faux()._cockpit_path_for("MniParcel2") == "C:/atlas/x.nii.gz"
    etat.mni_parcel2_path = None
    assert _Faux()._cockpit_path_for("MniParcel2") is None


# --------------------------------------------- ce que le texte annonce


def test_le_texte_nomme_le_gabarit_et_la_parcellation_fournie():
    """C'est la demande : savoir quel MNI, et ce qui est deja en place."""
    assert FilesPage.MNI_SPACE_NAME == "MNI152NLin2009cAsym"
    assert "Schaefer" in FilesPage.MNI_BUNDLED_PARCELLATION
    assert "400" in FilesPage.MNI_BUNDLED_PARCELLATION


def test_la_parcellation_fournie_porte_bien_400_regions():
    """Le texte annonce un compte : il doit correspondre au fichier."""
    chemin = resource_path("tools/templates/template_parcellation1.nii.gz")
    if not chemin.exists():
        pytest.skip("le gabarit de parcellation n'est pas installe")
    # Une copie, et non une vue : une vue sur une image temporaire
    # pointe vers une memoire deja rendue, et le lecteur s'effondre.
    volume = sitk.GetArrayFromImage(sitk.ReadImage(str(chemin)))
    etiquettes = set(np.unique(volume)) - {0}
    assert len(etiquettes) == 400, len(etiquettes)


# ------------------------------------------------- le projet s'en souvient


def test_le_projet_retient_le_chemin(tmp_path):
    from neuxelec.project_io import (
        apply_project_dict_to_state,
        build_project_dict_from_state,
    )

    etat = AppState()
    etat.mni_parcel2_path = str(tmp_path / "atlas.nii.gz")
    donnees = build_project_dict_from_state(etat)
    assert donnees["files"]["mni_parcel2"]["path"] == etat.mni_parcel2_path

    relu = AppState()
    apply_project_dict_to_state(relu, donnees, tmp_path / "projet.json")
    assert relu.mni_parcel2_path == etat.mni_parcel2_path


def test_un_projet_ancien_n_a_pas_de_chemin_mni(tmp_path):
    """Les projets ecrits avant cette case doivent s'ouvrir."""
    from neuxelec.project_io import apply_project_dict_to_state

    etat = AppState()
    apply_project_dict_to_state(etat, {"files": {}}, tmp_path / "projet.json")
    assert etat.mni_parcel2_path is None
