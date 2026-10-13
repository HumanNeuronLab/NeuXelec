"""Ranger le dossier d'un patient sans jamais toucher a ses donnees.

CE QUE CES TESTS PROTEGENT

Un seul defaut compte vraiment ici : classer comme jetable un fichier qui
ne l'est pas. Le dossier DICOM est la piece d'archive, parfois la seule
trace de l'acquisition, et une image envoyee par le service ne se
reconstruit pas.

La regle est donc une liste d'autorisation et non d'interdiction : un
fichier n'appartient a NeuXelec que si son nom correspond a ce que
NeuXelec ecrit, ou si le projet l'enregistre comme une de ses sorties.
Tout le reste est a l'utilisateur, y compris ce qu'on n'a pas prevu.

LE CAS QUI FAIT TOUT BASCULER

``CT_neuxelec.nii.gz`` porte un nom de chez nous. Mais rien n'empeche de
le rouvrir comme source a la session suivante, et il devient alors la
donnee de depart. Le projet le dit, et le projet l'emporte sur le nom :
c'est le premier test du fichier, et le plus important.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuxelec.utils import folder_tidy as ft


class _State:
    """Un projet reduit a ce que le rangement regarde."""

    def __init__(self, **champs):
        for nom in (
            ft.SOURCE_FIELDS + ft.PRODUCED_FIELDS + ft.IN_USE_FIELDS
        ):
            setattr(self, nom, None)
        for nom, valeur in champs.items():
            setattr(self, nom, str(valeur) if valeur is not None else None)


@pytest.fixture
def dossier(tmp_path):
    """Un dossier patient comme on en trouve apres quelques seances."""
    (tmp_path / "DICOM_CT" / "serie").mkdir(parents=True)
    (tmp_path / "DICOM_CT" / "serie" / "IM0001.dcm").write_bytes(b"x" * 10)
    (tmp_path / "CT.nii.gz").write_bytes(b"x" * 100)
    (tmp_path / "CT_neuxelec.nii.gz").write_bytes(b"x" * 200)
    (tmp_path / "CT_to_T1.nii.gz").write_bytes(b"x" * 300)
    (tmp_path / "T1.nii.gz").write_bytes(b"x" * 400)
    (tmp_path / "brainmask_0GenericAffine.mat").write_bytes(b"x" * 50)
    (tmp_path / "deface_1Warp.nii.gz").write_bytes(b"x" * 60)
    (tmp_path / "notes_du_chef.txt").write_bytes(b"x" * 5)
    return tmp_path


# --------------------------------------------------- le nom ne decide pas seul


def test_une_copie_importee_comme_source_redevient_une_source(tmp_path):
    """Le cas decrit en tete de fichier : le projet l'emporte sur le nom."""
    chemin = tmp_path / "CT_neuxelec.nii.gz"
    chemin.write_bytes(b"x")
    etat = _State(ct_source_path=chemin, ct_path=chemin)

    categorie, raison, _champ = ft.classify(chemin, etat)

    assert categorie == ft.SOURCE
    assert "your own data" in raison


def test_une_sortie_au_nom_libre_reste_reconnue(tmp_path):
    """Le nom du recalage est choisi par l'utilisateur dans la fenetre
    d'enregistrement : seul le projet sait que c'est une sortie."""
    chemin = tmp_path / "mon_scanner_recale.nii.gz"
    chemin.write_bytes(b"x")
    etat = _State(ct_coreg_path=chemin)

    categorie, _raison, champ = ft.classify(chemin, etat)

    assert categorie == ft.USED
    assert champ == "ct_coreg_path"


def test_un_fichier_inconnu_est_a_l_utilisateur(tmp_path):
    chemin = tmp_path / "compte_rendu.docx"
    chemin.write_bytes(b"x")

    categorie, raison, _champ = ft.classify(chemin, _State())

    assert categorie == ft.SOURCE
    assert "did not write" in raison


# --------------------------------------------------- le classement du dossier


def test_le_dicom_et_les_images_importees_sont_intouchables(dossier):
    etat = _State(
        ct_source_path=dossier / "CT.nii.gz",
        ct_path=dossier / "CT_neuxelec.nii.gz",
        t1_source_path=dossier / "T1.nii.gz",
        t1_path=dossier / "T1.nii.gz",
        ct_coreg_path=dossier / "CT_to_T1.nii.gz",
    )

    par_nom = {e.path.name: e for e in ft.scan(dossier, etat)}

    assert par_nom["IM0001.dcm"].category == ft.SOURCE
    assert par_nom["CT.nii.gz"].category == ft.SOURCE
    assert par_nom["T1.nii.gz"].category == ft.SOURCE
    assert par_nom["notes_du_chef.txt"].category == ft.SOURCE


def test_les_sous_produits_encore_utilises_sont_deplacables(dossier):
    etat = _State(
        ct_source_path=dossier / "CT.nii.gz",
        ct_path=dossier / "CT_neuxelec.nii.gz",
        ct_coreg_path=dossier / "CT_to_T1.nii.gz",
    )

    par_nom = {e.path.name: e for e in ft.scan(dossier, etat)}

    assert par_nom["CT_neuxelec.nii.gz"].category == ft.USED
    assert par_nom["CT_to_T1.nii.gz"].category == ft.USED


def test_les_restes_d_ants_dont_plus_personne_ne_veut(dossier):
    par_nom = {e.path.name: e for e in ft.scan(dossier, _State())}

    assert par_nom["brainmask_0GenericAffine.mat"].category == ft.ORPHAN
    assert par_nom["deface_1Warp.nii.gz"].category == ft.ORPHAN


def test_le_sous_dossier_de_rangement_n_est_pas_rescanne(dossier):
    """Un fichier deja range n'est plus de l'encombrement: le proposer a
    nouveau ferait grossir la liste a chaque passage."""
    range = dossier / ft.DEFAULT_SUBFOLDER
    range.mkdir()
    (range / "deja_range.nii.gz").write_bytes(b"x" * 999)

    chemins = {e.path for e in ft.scan(dossier, _State())}

    assert range / "deja_range.nii.gz" not in chemins
    assert all(ft.DEFAULT_SUBFOLDER not in e.parts for e in chemins)


# --------------------------------------------------- ce que le plan refuse


def test_supprimer_une_source_est_refuse(dossier):
    etat = _State(t1_source_path=dossier / "T1.nii.gz")
    entrees = ft.scan(dossier, etat)

    _moves, suppressions, refus = ft.plan(
        entrees, dossier, move=[], delete=[dossier / "T1.nii.gz"]
    )

    assert suppressions == []
    assert len(refus) == 1
    assert "yours" in refus[0][1]


def test_supprimer_un_fichier_encore_utilise_est_refuse(dossier):
    etat = _State(ct_coreg_path=dossier / "CT_to_T1.nii.gz")
    entrees = ft.scan(dossier, etat)

    moves, suppressions, refus = ft.plan(
        entrees, dossier, move=[], delete=[dossier / "CT_to_T1.nii.gz"]
    )

    assert moves == [] and suppressions == []
    assert "moved, not deleted" in refus[0][1]


def test_le_rangement_garde_l_arborescence(dossier):
    (dossier / "ants").mkdir()
    cible = dossier / "ants" / "brainmask_1Warp.nii.gz"
    cible.write_bytes(b"x" * 7)
    entrees = ft.scan(dossier, _State())

    moves, _s, _r = ft.plan(entrees, dossier, move=[cible], delete=[])

    assert moves[0][1] == dossier / ft.DEFAULT_SUBFOLDER / "ants" / "brainmask_1Warp.nii.gz"


# --------------------------------------------------- l'execution


def test_deplacer_met_le_projet_a_jour(dossier):
    etat = _State(
        ct_path=dossier / "CT_neuxelec.nii.gz",
        ct_coreg_path=dossier / "CT_to_T1.nii.gz",
    )
    entrees = ft.scan(dossier, etat)
    moves, suppressions, _r = ft.plan(
        entrees,
        dossier,
        move=[dossier / "CT_neuxelec.nii.gz", dossier / "CT_to_T1.nii.gz"],
        delete=[],
    )

    rapport = ft.apply_plan(moves, suppressions, etat)

    attendu = dossier / ft.DEFAULT_SUBFOLDER / "CT_neuxelec.nii.gz"
    assert attendu.exists()
    assert not (dossier / "CT_neuxelec.nii.gz").exists()
    assert etat.ct_path == str(attendu)
    assert set(rapport["fields"]) == {"ct_path", "ct_coreg_path"}
    assert rapport["bytes_moved"] == 500


def test_un_deplacement_qui_ecraserait_un_fichier_est_refuse(dossier):
    etat = _State(ct_path=dossier / "CT_neuxelec.nii.gz")
    destination = dossier / ft.DEFAULT_SUBFOLDER / "CT_neuxelec.nii.gz"
    destination.parent.mkdir()
    destination.write_bytes(b"deja la")

    entrees = ft.scan(dossier, etat)
    moves, _s, _r = ft.plan(entrees, dossier, move=[dossier / "CT_neuxelec.nii.gz"], delete=[])
    rapport = ft.apply_plan(moves, [], etat)

    assert rapport["moved"] == []
    assert "already exists" in rapport["failed"][0][1]
    assert destination.read_bytes() == b"deja la", "le fichier en place a ete ecrase"
    assert (dossier / "CT_neuxelec.nii.gz").exists(), "la source a disparu malgre l'echec"


def test_supprimer_un_orphelin_le_retire_vraiment(dossier):
    entrees = ft.scan(dossier, _State())
    cible = dossier / "brainmask_0GenericAffine.mat"
    _m, suppressions, _r = ft.plan(entrees, dossier, move=[], delete=[cible])

    # Sans corbeille, pour que le test dise la meme chose sur toute machine.
    rapport = ft.apply_plan([], suppressions, _State(), use_recycle_bin=False)

    assert not cible.exists()
    assert rapport["bytes_deleted"] == 50


# --------------------------------------------------- les comptes affiches


def test_les_totaux_separent_les_trois_familles(dossier):
    etat = _State(
        ct_source_path=dossier / "CT.nii.gz",
        ct_path=dossier / "CT_neuxelec.nii.gz",
    )

    comptes = ft.totals(ft.scan(dossier, etat))

    assert comptes[ft.USED]["files"] == 1
    assert comptes[ft.ORPHAN]["files"] == 2, "seuls les deux restes d'ANTs"
    # CT_to_T1.nii.gz compte parmi les fichiers de l'utilisateur : voir le
    # test suivant, qui dit pourquoi.
    assert comptes[ft.SOURCE]["bytes"] == 10 + 100 + 400 + 5 + 300


def test_un_recalage_au_nom_libre_et_oublie_du_projet_reste_a_l_utilisateur(dossier):
    """La limite assumee de la liste d'autorisation.

    Le nom d'un volume recale est choisi dans la fenetre d'enregistrement.
    Si le projet ne le designe plus, par exemple parce que le recalage a
    ete refait et enregistre ailleurs, rien ne permet de savoir qu'il
    sortait de NeuXelec. Il est donc laisse tranquille.

    C'est le bon sens de l'erreur : proposer de ranger moins que ce qu'on
    pourrait n'a jamais fait perdre un fichier a personne.
    """
    categorie, _raison, _champ = ft.classify(dossier / "CT_to_T1.nii.gz", _State())

    assert categorie == ft.SOURCE


def test_la_taille_se_lit(dossier):
    assert ft.human_size(0) == "0 B"
    assert ft.human_size(1536) == "1.5 KB"
    assert ft.human_size(3 * 1024**3) == "3.0 GB"
