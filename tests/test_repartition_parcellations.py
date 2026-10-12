"""Deux parcellations chargees ensemble vont dans deux cases.

LE DEFAUT SIGNALE

Charger les deux sorties de FreeSurfer les mettait toutes deux dans
Parcellation 1, la seconde effacant la premiere sans un mot.

La suggestion se faisait fichier par fichier, et sa derniere ligne
rendait "PARCEL1" pour tout ce qu'elle ne reconnaissait pas. Prise
isolement, chacune des deux sorties se lit comme une parcellation :
les deux recevaient donc la meme case, et la fenetre d'affectation
proposait ce choix comme s'il allait de soi.

CE QUI CHANGE

La suggestion regarde le lot entier. Un nom qui ne designe rien rend
desormais une chaine vide plutot que la premiere case, et le lot est
reparti sans collision. Et si l'utilisateur impose quand meme deux
fichiers a une seule case, l'import le dit au lieu d'en perdre un.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuxelec.pages.files_page import FilesPage


def _roles(noms):
    """Les cases suggerees, par nom de fichier."""
    chemins = ["C:/un/dossier/" + n for n in noms]
    rendu = FilesPage._guess_parcellation_roles(chemins)
    return {Path(c).name: r for c, r in rendu.items()}


# ----------------------------------------------- le cas signale


def test_les_deux_sorties_de_freesurfer_vont_dans_deux_cases():
    """Le defaut exact : aparc et wmparc atterrissaient ensemble."""
    rendu = _roles(["aparc.DKTatlas+aseg.nii.gz", "wmparc.nii.gz"])
    assert rendu["aparc.DKTatlas+aseg.nii.gz"] == "PARCEL1"
    assert rendu["wmparc.nii.gz"] == "PARCEL2"


def test_l_ordre_de_selection_ne_change_pas_le_resultat():
    """Choisir le wmparc en premier ne doit pas le promouvoir."""
    rendu = _roles(["wmparc.nii.gz", "aparc+aseg.nii.gz"])
    assert rendu["aparc+aseg.nii.gz"] == "PARCEL1"
    assert rendu["wmparc.nii.gz"] == "PARCEL2"


# --------------------------------------- jamais deux fois la meme


@pytest.mark.parametrize(
    "noms",
    [
        ["aparc.DKTatlas+aseg.nii.gz", "wmparc.nii.gz"],
        ["atlas_a.nii.gz", "atlas_b.nii.gz"],
        ["aparc+aseg.nii.gz", "aparc.a2009s+aseg.nii.gz"],
        ["wmparc.nii.gz", "wmparc.DKTatlas.mapped.nii.gz"],
        ["mon_parcellation2.nii.gz", "aparc+aseg.nii.gz"],
        ["truc.nii.gz", "machin.mgz"],
    ],
)
def test_deux_fichiers_ne_recoivent_jamais_la_meme_case(noms):
    rendu = _roles(noms)
    assert sorted(rendu.values()) == ["PARCEL1", "PARCEL2"], rendu


def test_un_seul_fichier_prend_la_premiere_case():
    assert _roles(["aparc+aseg.nii.gz"]) == {"aparc+aseg.nii.gz": "PARCEL1"}


def test_aucun_fichier_ne_rend_rien():
    assert FilesPage._guess_parcellation_roles([]) == {}
    assert FilesPage._guess_parcellation_roles(None) == {}


# ------------------------------------- les noms explicites priment


def test_un_nom_qui_dit_sa_case_est_respecte():
    rendu = _roles(["mon_atlas_parcel2.nii.gz", "autre_atlas.nii.gz"])
    assert rendu["mon_atlas_parcel2.nii.gz"] == "PARCEL2"
    assert rendu["autre_atlas.nii.gz"] == "PARCEL1"


def test_un_nom_explicite_passe_avant_une_convention_freesurfer():
    """parcel1 l'emporte sur wmparc, qui irait en case 2."""
    rendu = _roles(["wmparc_parcel1.nii.gz", "aparc+aseg.nii.gz"])
    assert rendu["wmparc_parcel1.nii.gz"] == "PARCEL1"
    assert rendu["aparc+aseg.nii.gz"] == "PARCEL2"


# --------------------------- ce que dit un nom, pris isolement


@pytest.mark.parametrize(
    "nom,attendu",
    [
        ("aparc+aseg.nii.gz", "PARCEL1"),
        ("aparc.DKTatlas+aseg.mgz", "PARCEL1"),
        ("wmparc.nii.gz", "PARCEL2"),
        ("mon_parcellation1.nii.gz", "PARCEL1"),
        ("mon_parcellation2.nii.gz", "PARCEL2"),
    ],
)
def test_un_nom_reconnu_designe_sa_case(nom, attendu):
    assert FilesPage._guess_parcellation_role(nom) == attendu


def test_un_nom_muet_ne_designe_aucune_case():
    """C'est la ligne qui causait tout : elle rendait PARCEL1."""
    assert FilesPage._guess_parcellation_role("atlas_maison.nii.gz") == ""


# ------------------------------------- plus de trois fichiers


def test_au_dela_de_deux_fichiers_les_cases_se_repetent():
    """Il n'y en a que deux : le troisieme retombe sur la premiere,
    et l'import le signalera plutot que de l'avaler."""
    rendu = _roles(["a.nii.gz", "b.nii.gz", "c.nii.gz"])
    assert len(rendu) == 3
    assert set(rendu.values()) == {"PARCEL1", "PARCEL2"}
    assert list(rendu.values()).count("PARCEL1") == 2
