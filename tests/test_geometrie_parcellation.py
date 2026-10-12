"""Quand NeuXelec doit prevenir qu'une parcellation tombe a cote.

LE DEFAUT SIGNALE

Charger une parcellation FreeSurfer affichait a chaque fois un long
avertissement de geometrie, alors que la parcellation etait exactement
a sa place.

La mesure etait l'intersection **sur l'union** des deux boites
physiques. Elle punit une difference de champ de vue, meme entre deux
images parfaitement alignees : une parcellation FreeSurfer est
conformee en 256^3, soit un cube de 256 mm, quand un T1 clinique en
couvre souvent moins. Le T1 tient alors entierement dans la
parcellation, donc rien ne cloche, et pourtant le rapport tombait vers
0,68, sous le seuil de 0,80.

CE QUI REMPLACE

La contenance du plus petit volume dans l'autre. Elle repond a la
question reellement posee : ces deux images decrivent-elles le meme
endroit du monde. Un volume entierement contenu dans l'autre y repond
oui, quelle que soit la taille de la boite qui l'entoure.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from neuxelec.pages.files_page import FilesPage  # noqa: E402

#: Le seuil au-dessus duquel NeuXelec se tait.
SEUIL = 0.80

#: La grille conforme de FreeSurfer, et un T1 clinique realiste :
#: champ de vue plus serre, voxels anisotropes.
CONFORME = dict(taille=(256, 256, 256), pas=(1.0, 1.0, 1.0), origine=(130.0, 134.0, -126.0))
CLINIQUE = dict(taille=(256, 256, 180), pas=(0.9, 0.9, 1.2), origine=(115.0, 118.0, -100.0))

#: La direction des conversions FreeSurfer que lit NeuXelec.
DIRECTION = (-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0)


def _image(taille, pas, origine, direction=DIRECTION):
    arr = np.zeros(tuple(reversed(taille)), dtype=np.int16)
    img = sitk.GetImageFromArray(arr)
    img.SetSpacing(pas)
    img.SetOrigin(origine)
    img.SetDirection(direction)
    return img


# ------------------------------------------------- le defaut signale


def test_une_parcellation_conforme_sur_un_t1_clinique_ne_previent_plus():
    """Le cas qui declenchait l'avertissement a chaque chargement."""
    parcellation = _image(**CONFORME)
    t1 = _image(**CLINIQUE)

    assert FilesPage._physical_containment_fraction(parcellation, t1) >= SEUIL


def test_c_est_bien_l_ancienne_mesure_qui_se_trompait():
    """Sans cette ligne, on ne saurait pas que le cas etait reel."""
    parcellation = _image(**CONFORME)
    t1 = _image(**CLINIQUE)

    ancienne = FilesPage._physical_overlap_fraction(parcellation, t1)
    assert ancienne < SEUIL, ancienne


# ------------------------------------------- ce qui doit encore prevenir


def test_un_volume_pose_ailleurs_previent_toujours():
    t1 = _image(**CLINIQUE)
    ailleurs = _image((60, 60, 60), (1.0, 1.0, 1.0), (400.0, 400.0, 400.0))

    assert FilesPage._physical_containment_fraction(ailleurs, t1) < SEUIL


def test_un_volume_a_moitie_dehors_previent():
    """Un decalage franc reste un decalage."""
    t1 = _image((200, 200, 200), (1.0, 1.0, 1.0), (100.0, 100.0, -100.0))
    decale = _image((200, 200, 200), (1.0, 1.0, 1.0), (100.0, 100.0, 60.0))

    part = FilesPage._physical_containment_fraction(decale, t1)
    assert part < SEUIL, part


# --------------------------------------------- ce que la mesure promet


def test_deux_images_identiques_se_contiennent_entierement():
    img = _image(**CONFORME)
    assert FilesPage._physical_containment_fraction(img, img) == pytest.approx(1.0)


def test_la_mesure_est_symetrique():
    """L'ordre des arguments ne doit rien changer a la reponse."""
    a = _image(**CONFORME)
    b = _image(**CLINIQUE)
    assert FilesPage._physical_containment_fraction(a, b) == pytest.approx(
        FilesPage._physical_containment_fraction(b, a)
    )


def test_la_mesure_ne_depasse_jamais_un():
    a = _image(**CONFORME)
    b = _image((10, 10, 10), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    assert FilesPage._physical_containment_fraction(b, a) <= 1.0


@pytest.mark.parametrize("pas", [1.0, 2.0, 4.0])
def test_la_taille_des_voxels_ne_change_rien(pas):
    """Deux grilles du meme endroit decrivent le meme endroit.

    C'est le coeur du changement : la mesure parle d'espace physique,
    pas de voxels.
    """
    reference = _image((193, 229, 193), (1.0, 1.0, 1.0), (96.0, 132.0, -78.0))
    n = [int(round(192 / pas)) + 1, int(round(228 / pas)) + 1, int(round(192 / pas)) + 1]
    autre = _image(tuple(n), (pas, pas, pas), (96.0, 132.0, -78.0))

    assert FilesPage._physical_containment_fraction(autre, reference) >= 0.99


# ------------------------------------- la boite tient compte de la direction


def test_la_boite_suit_les_cosinus_directeurs():
    """Un x qui decroit avec l'indice ne doit pas inverser la boite.

    C'est ce qui separe une comparaison juste d'une comparaison qui
    declarerait deux images disjointes alors qu'elles se superposent.
    """
    img = _image((100, 100, 100), (1.0, 1.0, 1.0), (50.0, 50.0, 0.0))
    bas, haut = FilesPage._world_bounding_box(img)

    assert bas[0] == pytest.approx(-49.0), bas
    assert haut[0] == pytest.approx(50.0), haut
    assert (haut >= bas).all()
