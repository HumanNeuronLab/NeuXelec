"""Le wmparc voisin doit arriver sur la grille de la parcellation.

LE DEFAUT QUE CES TESTS FIGENT

FreeSurfer ecrit ``wmparc.mgz`` en LIA, et la conversion ``.nii.gz`` posee
a cote est en RAS. Les deux font 256x256x256. La garde ne comparait que la
taille : elle les declarait compatibles, aucun reechantillonnage n'avait
lieu, et ``build_parcellation_volume`` fusionnait ensuite les deux
tableaux voxel a voxel dans deux ordres d'axes differents.

Le symptome n'avait rien d'un plantage. Les contacts de substance blanche
d'une electrode gauche ressortaient ``wm-rh-...``, donc dans l'hemisphere
oppose, aussi bien dans le tableau de la coupe oblique que dans l'export
BIDS, qui partagent cette fonction. Une taille ne dit rien d'une
orientation : il faut l'origine, l'espacement et la direction.
"""

from __future__ import annotations

import numpy as np
import pytest
import SimpleITK as sitk

from neuxelec.seeg2parc import build_parcellation_volume
from neuxelec.utils.wmparc import find_sibling_wmparc

#: Substance blanche generique de l'aparc+aseg : gauche, puis droite.
WM_GAUCHE, WM_DROITE = 2, 41
#: Etiquettes detaillees du wmparc, du meme cote chacune.
DETAIL_GAUCHE, DETAIL_DROITE = 3030, 4030


def _volume_de_reference():
    """Un volume ou la gauche et la droite sont separees sans ambiguite.

    La direction est celle des conversions FreeSurfer que lit NeuXelec :
    x decroit avec l'indice, donc la colonne 0 est la gauche du patient.
    """
    taille = 8
    arr = np.full((taille, taille, taille), WM_DROITE, dtype=np.int32)
    arr[:, :, : taille // 2] = WM_GAUCHE  # colonnes de gauche
    img = sitk.GetImageFromArray(arr)
    img.SetSpacing((1.0, 1.0, 1.0))
    img.SetOrigin((4.0, 4.0, -4.0))
    img.SetDirection((-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0))
    return img


def _wmparc_assorti(ref):
    """Le wmparc qui correspond a ``ref``, etiquette par etiquette."""
    arr = sitk.GetArrayFromImage(ref).copy()
    detail = np.where(arr == WM_GAUCHE, DETAIL_GAUCHE, DETAIL_DROITE).astype(np.int32)
    img = sitk.GetImageFromArray(detail)
    img.CopyInformation(ref)
    return img


@pytest.fixture
def dossier(tmp_path):
    """Un aparc+aseg et son wmparc, tels que FreeSurfer les laisse."""
    ref = _volume_de_reference()
    sitk.WriteImage(ref, str(tmp_path / "aparc.DKTatlas+aseg.nii.gz"))
    return tmp_path, ref


def test_un_wmparc_deja_sur_la_grille_passe_tel_quel(dossier):
    tmp_path, ref = dossier
    sitk.WriteImage(_wmparc_assorti(ref), str(tmp_path / "wmparc.nii.gz"))

    wm = find_sibling_wmparc(tmp_path / "aparc.DKTatlas+aseg.nii.gz", ref)

    assert wm is not None
    assert wm.GetDirection() == ref.GetDirection()
    assert wm.GetOrigin() == ref.GetOrigin()


@pytest.mark.parametrize("orientation", ["LIA", "RAS", "LPS", "ASL"])
def test_un_wmparc_dans_une_autre_orientation_est_remis_sur_la_grille(
    dossier, orientation
):
    """Meme taille, autre ordre d'axes : c'est le cas du .mgz de FreeSurfer."""
    tmp_path, ref = dossier
    tourne = sitk.DICOMOrient(_wmparc_assorti(ref), orientation)
    sitk.WriteImage(tourne, str(tmp_path / "wmparc.nii.gz"))

    wm = find_sibling_wmparc(tmp_path / "aparc.DKTatlas+aseg.nii.gz", ref)

    assert wm is not None, "le wmparc voisin n'a pas ete trouve"
    assert wm.GetSize() == ref.GetSize()
    assert np.allclose(wm.GetDirection(), ref.GetDirection())
    assert np.allclose(wm.GetOrigin(), ref.GetOrigin())


@pytest.mark.parametrize("orientation", ["LIA", "RAS", "LPS", "ASL"])
def test_la_fusion_ne_change_jamais_un_contact_de_cote(dossier, orientation):
    """Le test qui compte : aucune etiquette ne doit traverser la ligne mediane."""
    tmp_path, ref = dossier
    tourne = sitk.DICOMOrient(_wmparc_assorti(ref), orientation)
    sitk.WriteImage(tourne, str(tmp_path / "wmparc.nii.gz"))

    wm = find_sibling_wmparc(tmp_path / "aparc.DKTatlas+aseg.nii.gz", ref)
    brut = sitk.GetArrayFromImage(ref)
    fusion = build_parcellation_volume(brut, sitk.GetArrayFromImage(wm))

    assert set(np.unique(fusion[brut == WM_GAUCHE])) == {DETAIL_GAUCHE}
    assert set(np.unique(fusion[brut == WM_DROITE])) == {DETAIL_DROITE}


def test_sans_wmparc_voisin_rien_n_est_invente(dossier):
    tmp_path, ref = dossier
    assert find_sibling_wmparc(tmp_path / "aparc.DKTatlas+aseg.nii.gz", ref) is None
