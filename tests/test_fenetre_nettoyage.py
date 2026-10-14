# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La fenetre qui suit l'enregistrement d'une modalite.

Elle s'ouvre sur un fichier qui vient d'etre ecrit et propose d'effacer
ceux qui y ont mene. Deux regles s'y voient a l'oeil nu, et ces tests les
tiennent : le fichier enregistre n'a pas de case, et aucune case n'est
cochee d'avance.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.ui.modality_cleanup_dialog import ModalityCleanupDialog  # noqa: E402
from neuxelec.utils import modality_files as mf  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _State:
    def __init__(self, **champs):
        for groupe in mf.CHAIN_FIELDS.values():
            for champ, _libelle in groupe:
                setattr(self, champ, None)
        self.converted_nifti_by_role = {}
        for nom, valeur in champs.items():
            setattr(self, nom, valeur)


@pytest.fixture
def fenetre(app, tmp_path):
    (tmp_path / "CT.nii.gz").write_bytes(b"x" * 100)
    (tmp_path / "CT_neuxelec.nii.gz").write_bytes(b"x" * 200)
    garde = tmp_path / "CT_to_T1.nii.gz"
    garde.write_bytes(b"x" * 300)

    etat = _State(
        ct_source_path=str(tmp_path / "CT.nii.gz"),
        ct_path=str(tmp_path / "CT_neuxelec.nii.gz"),
    )
    chaine = mf.chain_for("CT", etat, keep=garde)
    f = ModalityCleanupDialog("CT", "CT", chaine, garde, etat)
    yield f
    f.deleteLater()


def _lignes(fenetre):
    racine = fenetre.tree.invisibleRootItem()
    return [racine.child(i) for i in range(racine.childCount())]


def test_le_fichier_enregistre_ouvre_la_liste_sans_case(fenetre):
    premiere = _lignes(fenetre)[0]

    assert premiere.text(0) == "CT_to_T1.nii.gz"
    assert premiere.text(2) == "just saved"
    assert not (premiere.flags() & Qt.ItemIsUserCheckable)


def test_rien_n_est_coche_d_avance(fenetre):
    """Ces fichiers sont a l'utilisateur, le DICOM le premier."""
    for item in _lignes(fenetre)[1:]:
        assert item.checkState(0) == Qt.Unchecked


def test_tant_que_rien_n_est_coche_le_bouton_dort(fenetre):
    assert not fenetre.btn_delete.isEnabled()
    assert fenetre.lbl_preview.text() == "Nothing ticked"


def test_cocher_annonce_ce_qui_part(fenetre):
    _lignes(fenetre)[1].setCheckState(0, Qt.Checked)

    assert fenetre.btn_delete.isEnabled()
    assert fenetre.lbl_preview.text() == "1 ticked, 100 B"


def test_l_entete_nomme_la_modalite_et_le_fichier_enregistre(fenetre):
    assert "CT" in fenetre.header.lbl_title.text()
    assert "CT_to_T1.nii.gz" in fenetre.header.lbl_subtitle.text()


def test_un_dossier_se_voit_comme_un_dossier(app, tmp_path):
    dicom = tmp_path / "DICOM_CT"
    dicom.mkdir()
    for i in range(3):
        (dicom / f"IM{i}.dcm").write_bytes(b"x" * 10)
    garde = tmp_path / "CT_to_T1.nii.gz"
    garde.write_bytes(b"x")

    etat = _State(ct_source_path=str(dicom))
    chaine = mf.chain_for("CT", etat, keep=garde)
    f = ModalityCleanupDialog("CT", "CT", chaine, garde, etat)

    ligne = _lignes(f)[1]
    assert ligne.text(0).endswith("\\")
    assert "3 files" in ligne.text(2)

    f.deleteLater()
