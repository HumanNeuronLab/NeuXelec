"""La fenetre de rangement montre ce qu'elle fera, et rien d'autre.

La logique est testee a cote, dans test_rangement_dossier.py. Ce qui se
joue ici est l'autre moitie du probleme : ce que l'utilisateur peut
cocher. Une case a cocher sur un fichier qui lui appartient serait une
promesse que le plan refuserait ensuite, et une fenetre qui propose puis
refuse est pire que celle qui ne propose pas.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.ui.folder_tidy_dialog import FolderTidyDialog  # noqa: E402
from neuxelec.utils import folder_tidy as ft  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _State:
    def __init__(self, **champs):
        for nom in ft.SOURCE_FIELDS + ft.PRODUCED_FIELDS + ft.IN_USE_FIELDS:
            setattr(self, nom, None)
        for nom, valeur in champs.items():
            setattr(self, nom, str(valeur) if valeur is not None else None)


@pytest.fixture
def dossier(tmp_path):
    (tmp_path / "CT.nii.gz").write_bytes(b"x" * 100)
    (tmp_path / "CT_neuxelec.nii.gz").write_bytes(b"x" * 200)
    (tmp_path / "brainmask_1Warp.nii.gz").write_bytes(b"x" * 300)
    return tmp_path


@pytest.fixture
def fenetre(app, dossier):
    etat = _State(
        ct_source_path=dossier / "CT.nii.gz",
        ct_path=dossier / "CT_neuxelec.nii.gz",
    )
    f = FolderTidyDialog(dossier, etat)
    yield f
    f.deleteLater()


def _lignes(fenetre):
    """{nom du fichier: item}, tous groupes confondus."""
    out = {}
    racine = fenetre.tree.invisibleRootItem()
    for g in range(racine.childCount()):
        groupe = racine.child(g)
        for i in range(groupe.childCount()):
            item = groupe.child(i)
            out[item.text(0)] = item
    return out


def test_les_trois_groupes_sont_la(fenetre):
    racine = fenetre.tree.invisibleRootItem()
    titres = [racine.child(i).text(0) for i in range(racine.childCount())]

    assert len(titres) == 3
    assert titres[0].startswith("Yours")
    assert "still used" in titres[1]
    assert "nothing uses them" in titres[2]


def test_un_fichier_a_l_utilisateur_n_a_pas_de_case(fenetre):
    """Pas de case du tout : ce qui ne peut pas etre choisi ne doit pas
    avoir l'air de pouvoir l'etre."""
    item = _lignes(fenetre)["CT.nii.gz"]

    assert not (item.flags() & Qt.ItemIsUserCheckable)
    assert item.isDisabled()


def test_un_orphelin_est_coche_d_avance(fenetre):
    item = _lignes(fenetre)["brainmask_1Warp.nii.gz"]

    assert item.checkState(0) == Qt.Checked


def test_un_fichier_encore_utilise_ne_l_est_pas(fenetre):
    """Le deplacer est propose, pas impose : c'est un fichier dont le
    projet se sert encore."""
    item = _lignes(fenetre)["CT_neuxelec.nii.gz"]

    assert item.checkState(0) == Qt.Unchecked


def test_le_resume_dit_ce_qui_va_se_passer(fenetre):
    texte = fenetre.lbl_preview.text()

    assert "delete 1 file(s)" in texte
    assert "300 B" in texte


def test_cocher_un_fichier_utilise_annonce_un_deplacement(fenetre):
    _lignes(fenetre)["CT_neuxelec.nii.gz"].setCheckState(0, Qt.Checked)

    texte = fenetre.lbl_preview.text()

    assert "move 1 file(s)" in texte
    assert ft.DEFAULT_SUBFOLDER in texte


def test_une_serie_dicom_ne_remplit_pas_la_fenetre(app, tmp_path):
    """Une serie compte volontiers cinq mille coupes. Les etaler ne dit
    rien de plus que leur total, et rend la fenetre inutilisable."""
    from neuxelec.ui.folder_tidy_dialog import LIGNES_MAX_SOURCE

    serie = tmp_path / "DICOM"
    serie.mkdir()
    combien = LIGNES_MAX_SOURCE + 37
    for i in range(combien):
        (serie / f"IM{i:05d}.dcm").write_bytes(b"x" * 10)

    f = FolderTidyDialog(tmp_path, _State())
    groupe = f.tree.invisibleRootItem().child(0)

    assert groupe.text(0).endswith(f"({combien})"), "le total doit rester exact"
    assert groupe.childCount() == LIGNES_MAX_SOURCE + 1, "une ligne de resume"
    derniere = groupe.child(groupe.childCount() - 1)
    assert derniere.text(0) == "and 37 more file(s)"
    assert not (derniere.flags() & Qt.ItemIsUserCheckable)

    f.deleteLater()


def test_sans_rien_de_coche_le_bouton_ne_fait_rien(app, tmp_path):
    (tmp_path / "T1.nii.gz").write_bytes(b"x" * 10)
    f = FolderTidyDialog(tmp_path, _State(t1_source_path=tmp_path / "T1.nii.gz"))

    assert f.lbl_preview.text() == "Nothing selected."
    assert not f.btn_apply.isEnabled()

    f.deleteLater()
