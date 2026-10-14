# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ce qu'une modalite laisse derriere elle, et ce qu'on en efface.

LA CHAINE

Un CT arrive en dossier DICOM, devient un NIfTI, puis une copie nettoyee,
et seulement ensuite le volume rééchantillonné dans l'IRM 1 que l'on
enregistre. Au moment de cet enregistrement, les trois premiers ne
servent generalement plus, et ce sont eux qui rendent le dossier
illisible.

CE QUE CES TESTS PROTEGENT

Trois choses. Que le fichier qu'on vient d'enregistrer ne figure jamais
parmi ce qu'on propose d'effacer. Que rien ne soit coche d'avance, parce
que ces fichiers appartiennent a l'utilisateur, le DICOM le premier. Et
qu'apres une suppression le projet ne pointe plus sur du vide : la
modalite devient le volume enregistre, sinon la prochaine ouverture
reclamerait des fichiers disparus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuxelec.utils import modality_files as mf


class _State:
    """Un projet reduit a ce que la chaine regarde."""

    def __init__(self, **champs):
        for groupe in mf.CHAIN_FIELDS.values():
            for champ, _libelle in groupe:
                setattr(self, champ, None)
        self.converted_nifti_by_role = {}
        for nom, valeur in champs.items():
            setattr(self, nom, str(valeur) if isinstance(valeur, Path) else valeur)


@pytest.fixture
def patient(tmp_path):
    """Un CT comme NeuXelec l'a traverse, du DICOM au volume recale."""
    dicom = tmp_path / "DICOM_CT"
    (dicom / "serie").mkdir(parents=True)
    for i in range(4):
        (dicom / "serie" / f"IM{i}.dcm").write_bytes(b"x" * 25)
    (tmp_path / "CT.nii.gz").write_bytes(b"x" * 100)
    (tmp_path / "CT_neuxelec.nii.gz").write_bytes(b"x" * 200)
    (tmp_path / "CT_to_T1.nii.gz").write_bytes(b"x" * 300)
    return tmp_path


def _etat_ct(patient):
    return _State(
        ct_source_path=patient / "DICOM_CT",
        ct_path=patient / "CT_neuxelec.nii.gz",
        ct_coreg_path=None,
        converted_nifti_by_role={"CT": str(patient / "CT.nii.gz")},
    )


# ------------------------------------------------------------- la chaine


def test_la_chaine_dit_toute_l_histoire_dans_l_ordre(patient):
    chaine = mf.chain_for("CT", _etat_ct(patient), keep=patient / "CT_to_T1.nii.gz")

    assert [f.name for f in chaine] == [
        "DICOM_CT",
        "CT.nii.gz",
        "CT_neuxelec.nii.gz",
    ]
    assert chaine[0].is_folder and chaine[0].file_count == 4
    assert chaine[0].size == 100


def test_le_fichier_enregistre_n_est_jamais_propose(patient):
    """Il est la raison de la fenetre: le proposer serait absurde, et
    l'effacer perdrait le seul fichier que l'utilisateur voulait garder."""
    etat = _etat_ct(patient)
    etat.ct_coreg_path = str(patient / "CT_to_T1.nii.gz")

    chaine = mf.chain_for("CT", etat, keep=patient / "CT_to_T1.nii.gz")

    assert all(f.name != "CT_to_T1.nii.gz" for f in chaine)


def test_un_recalage_precedent_est_propose(patient):
    """Celui-la peut partir: un nouveau vient d'etre enregistre."""
    ancien = patient / "CT_to_T1_du_mois_dernier.nii.gz"
    ancien.write_bytes(b"x" * 42)
    etat = _etat_ct(patient)
    etat.ct_coreg_path = str(ancien)

    chaine = mf.chain_for("CT", etat, keep=patient / "CT_to_T1.nii.gz")

    assert ancien.name in [f.name for f in chaine]


def test_un_fichier_disparu_ne_figure_pas(patient):
    etat = _etat_ct(patient)
    etat.ct_path = str(patient / "jamais_ecrit.nii.gz")

    chaine = mf.chain_for("CT", etat, keep=patient / "CT_to_T1.nii.gz")

    assert all("jamais_ecrit" not in f.name for f in chaine)


def test_un_fichier_designe_deux_fois_ne_sort_qu_une_fois(patient):
    """Mais les deux champs sont retenus, car effacer doit vider les deux."""
    etat = _etat_ct(patient)
    etat.ct_source_path = str(patient / "CT_neuxelec.nii.gz")

    chaine = mf.chain_for("CT", etat, keep=patient / "CT_to_T1.nii.gz")
    nettoyee = [f for f in chaine if f.name == "CT_neuxelec.nii.gz"]

    assert len(nettoyee) == 1
    assert set(nettoyee[0].fields) == {"ct_source_path", "ct_path"}


def test_sans_conversion_dicom_la_chaine_a_un_maillon_de_moins(patient):
    """Un projet ecrit avant que la conversion ne soit retenue, ou une
    image deja en NIfTI: il n'y a simplement pas d'intermediaire."""
    etat = _etat_ct(patient)
    etat.converted_nifti_by_role = {}

    chaine = mf.chain_for("CT", etat, keep=patient / "CT_to_T1.nii.gz")

    assert [f.name for f in chaine] == ["DICOM_CT", "CT_neuxelec.nii.gz"]


def test_chaque_modalite_de_la_liste_a_sa_chaine():
    """Celles que l'utilisateur a nommees, pas une de moins."""
    for modalite in (
        "T2",
        "fMRI",
        "CT",
        "PET",
        "ictalSPECT",
        "interictalSPECT",
        "SISCOM",
        "brainmask",
    ):
        assert modalite in mf.CHAIN_FIELDS
        assert modalite in mf.KEEPER_FIELDS


# ------------------------------------------------------------- la suppression


def test_effacer_laisse_le_projet_sur_le_volume_enregistre(patient):
    """Sinon la prochaine ouverture reclamerait des fichiers disparus."""
    etat = _etat_ct(patient)
    garde = patient / "CT_to_T1.nii.gz"
    chaine = mf.chain_for("CT", etat, keep=garde)

    rapport = mf.delete_chosen(chaine, etat, "CT", garde, use_recycle_bin=False)

    assert not (patient / "DICOM_CT").exists()
    assert not (patient / "CT.nii.gz").exists()
    assert not (patient / "CT_neuxelec.nii.gz").exists()
    assert garde.exists(), "le volume enregistre a ete emporte"
    assert etat.ct_path == str(garde)
    assert etat.ct_source_path == str(garde)
    assert rapport["bytes"] == 100 + 100 + 200


def test_n_effacer_qu_une_partie_ne_touche_pas_au_reste(patient):
    etat = _etat_ct(patient)
    garde = patient / "CT_to_T1.nii.gz"
    chaine = mf.chain_for("CT", etat, keep=garde)
    copie = [f for f in chaine if f.name == "CT_neuxelec.nii.gz"]

    mf.delete_chosen(copie, etat, "CT", garde, use_recycle_bin=False)

    assert (patient / "DICOM_CT").exists(), "le DICOM n'etait pas coche"
    assert (patient / "CT.nii.gz").exists()
    assert etat.ct_path == str(garde), "le champ vide a ete repointe"
    assert etat.ct_source_path == str(patient / "DICOM_CT"), "celui-la ne bouge pas"


def test_rien_de_choisi_ne_change_rien(patient):
    etat = _etat_ct(patient)
    avant = dict(vars(etat))

    rapport = mf.delete_chosen([], etat, "CT", patient / "CT_to_T1.nii.gz")

    assert rapport["deleted"] == []
    assert rapport["fields"] == []
    assert vars(etat) == avant
    assert (patient / "CT_neuxelec.nii.gz").exists()


def test_un_echec_est_rapporte_et_n_arrete_pas_le_reste(patient, monkeypatch):
    etat = _etat_ct(patient)
    garde = patient / "CT_to_T1.nii.gz"
    chaine = mf.chain_for("CT", etat, keep=garde)

    vrai = mf._delete

    def _capricieux(path, use_recycle_bin):
        if Path(path).name == "CT.nii.gz":
            raise PermissionError("file in use")
        return vrai(path, use_recycle_bin)

    monkeypatch.setattr(mf, "_delete", _capricieux)
    rapport = mf.delete_chosen(chaine, etat, "CT", garde, use_recycle_bin=False)

    assert (patient / "CT.nii.gz").exists()
    assert not (patient / "CT_neuxelec.nii.gz").exists()
    assert len(rapport["failed"]) == 1
    assert "file in use" in rapport["failed"][0][1]


def test_la_taille_se_lit():
    assert mf.human_size(0) == "0 B"
    assert mf.human_size(1536) == "1.5 KB"
    assert mf.human_size(3 * 1024**3) == "3.0 GB"
