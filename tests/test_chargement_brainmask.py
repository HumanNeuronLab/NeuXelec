# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Charger un brain mask FreeSurfer.

LE DEFAUT SIGNALE

Un brainmask.mgz ne se chargeait pas. Trois causes se cumulaient, et
aucune ne se voyait :

  - les deux filtres de dialogue ne proposaient que .nii et .nii.gz,
    donc le fichier n'apparaissait meme pas dans la liste ;
  - choisi par "All files", sitk.ReadImage l'aurait refuse de toute
    facon : SimpleITK n'a pas de lecteur MGH. read_image_any passe par
    nibabel pour .mgz et .mgh, et c'est deja ce que font les
    parcellations et l'imagerie ;
  - le bouton dedie avalait l'echec. Il retenait le chemin, posait
    l'image a None et ne disait rien : le fichier paraissait charge et
    rien ne s'affichait.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages import files_page as module_page  # noqa: E402
from neuxelec.pages.files_page import FilesPage  # noqa: E402
from neuxelec.utils.image_ingest import read_image_any  # noqa: E402

#: Les extensions qu'un brain mask peut porter chez un utilisateur de
#: FreeSurfer ou de FastSurfer.
ATTENDUES = (".nii", ".nii.gz", ".mgz", ".mgh")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ecrire_mgz(dossier, nom="brainmask.mgz"):
    """Un volume MGH minimal, ecrit par nibabel comme FreeSurfer le fait."""
    import nibabel as nib

    chemin = dossier / nom
    donnees = np.zeros((8, 8, 8), dtype=np.uint8)
    donnees[2:6, 2:6, 2:6] = 100
    nib.save(nib.MGHImage(donnees, np.eye(4)), str(chemin))
    return chemin


# ------------------------------------------------- lire le fichier


def test_simpleitk_ne_sait_pas_lire_un_mgz(tmp_path):
    """La raison de fond, qu'il vaut mieux figer que redecouvrir."""
    chemin = _ecrire_mgz(tmp_path)
    with pytest.raises(Exception):
        sitk.ReadImage(str(chemin))


def test_read_image_any_le_lit(tmp_path):
    chemin = _ecrire_mgz(tmp_path)
    image = read_image_any(str(chemin))
    assert image is not None
    assert image.GetSize() == (8, 8, 8)


# ------------------------------------- les filtres de dialogue


@pytest.mark.parametrize("extension", ATTENDUES)
def test_le_bouton_dedie_propose_l_extension(extension):
    """Un filtre qui ne la cite pas cache le fichier sans rien dire."""
    import inspect

    source = inspect.getsource(FilesPage.load_brainmask)
    debut = source.index("Select Brain Mask file")
    filtre = source[debut : source.index(")", debut)]
    assert "*" + extension in filtre, filtre


@pytest.mark.parametrize("extension", ATTENDUES)
def test_le_lot_surfaces_propose_l_extension(extension):
    import inspect

    source = inspect.getsource(FilesPage.load_surfaces_bundle)
    debut = source.index("Surfaces and masks")
    filtre = source[debut : source.index(";;", debut)]
    assert "*" + extension in filtre, filtre


# ------------------------------- le bouton dedie, de bout en bout


class _Page:
    """Juste de quoi exercer load_brainmask."""

    load_brainmask = FilesPage.load_brainmask

    def __init__(self, state):
        self.state = state
        self.le_load_brainmask = None
        self.btn_save_brainmask = None
        self.boutons = 0

    def _t1_preferred_dir(self):
        return ""

    def _dialog_parent(self):
        return None

    def _view3d(self):
        return None

    def _update_buttons(self):
        self.boutons += 1


class _Etat:
    def __init__(self):
        self.brainmask_path = None
        self.brainmask_sitk = None
        self.brainmask_generated = False
        self.brainmask_saved = False
        self.brainmask_generated_path = None
        self.oblique_page = None


@pytest.fixture
def pose(monkeypatch):
    """Remplacer la boite de fichiers et celle des erreurs."""
    erreurs = []

    def _critical(parent, titre, message):
        erreurs.append((titre, message))

    monkeypatch.setattr(
        module_page.NeuXelecMessageDialog, "critical", staticmethod(_critical)
    )

    def choisir(chemin):
        monkeypatch.setattr(
            module_page.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(chemin), "")),
        )

    return choisir, erreurs


def test_un_mgz_se_charge(app, tmp_path, pose):
    """Le defaut signale."""
    choisir, erreurs = pose
    choisir(_ecrire_mgz(tmp_path))

    etat = _Etat()
    page = _Page(etat)
    page.load_brainmask()

    assert erreurs == [], erreurs
    assert etat.brainmask_sitk is not None, "l'image n'a pas ete chargee"
    assert etat.brainmask_sitk.GetSize() == (8, 8, 8)
    assert etat.brainmask_path.endswith("brainmask.mgz")


def test_un_nifti_se_charge_toujours(app, tmp_path, pose):
    """Ne pas casser ce qui marchait."""
    chemin = tmp_path / "mask.nii.gz"
    image = sitk.GetImageFromArray(np.zeros((6, 6, 6), dtype=np.uint8))
    sitk.WriteImage(image, str(chemin))

    choisir, erreurs = pose
    choisir(chemin)
    etat = _Etat()
    _Page(etat).load_brainmask()

    assert erreurs == []
    assert etat.brainmask_sitk is not None


def test_un_fichier_illisible_est_annonce(app, tmp_path, pose):
    """L'echec etait muet : le chemin etait retenu, l'image a None."""
    chemin = tmp_path / "casse.nii.gz"
    chemin.write_bytes(b"ceci n'est pas une image")

    choisir, erreurs = pose
    choisir(chemin)
    etat = _Etat()
    _Page(etat).load_brainmask()

    assert len(erreurs) == 1, "aucun message n'a ete affiche"
    assert "Load brain mask failed" in erreurs[0][0]
    assert "casse.nii.gz" in erreurs[0][1]


def test_un_echec_ne_touche_pas_a_l_etat(app, tmp_path, pose):
    """Sinon le fichier parait charge et rien ne s'affiche."""
    chemin = tmp_path / "casse.mgz"
    chemin.write_bytes(b"pas davantage")

    choisir, _ = pose
    choisir(chemin)
    etat = _Etat()
    etat.brainmask_path = "ancien.nii.gz"
    etat.brainmask_sitk = "ancienne image"

    _Page(etat).load_brainmask()

    assert etat.brainmask_path == "ancien.nii.gz"
    assert etat.brainmask_sitk == "ancienne image"


def test_renoncer_ne_fait_rien(app, monkeypatch):
    monkeypatch.setattr(
        module_page.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    etat = _Etat()
    _Page(etat).load_brainmask()
    assert etat.brainmask_path is None
    assert etat.brainmask_sitk is None


# ------------------------- plus aucun lecteur aveugle au format


def test_aucun_chemin_de_brainmask_ne_passe_plus_par_sitk_directement():
    """Quatre endroits lisaient le fichier choisi par l'utilisateur."""
    import inspect

    from neuxelec import main_window

    for module in (module_page, main_window):
        source = inspect.getsource(module)
        for ligne in source.splitlines():
            if ligne.strip().startswith("#"):
                continue  # un commentaire peut nommer les deux
            if "brainmask" in ligne.lower() and "sitk.ReadImage" in ligne:
                # Seul le fichier que NeuXelec vient d'ecrire lui-meme
                # est toujours un .nii.gz, donc lisible par SimpleITK.
                assert "out_path" in ligne, ligne
