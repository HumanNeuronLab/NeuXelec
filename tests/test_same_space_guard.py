# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Refuser d'estimer une transformation entre deux volumes déjà superposés.

Mesuré sur une carte de z-score et le T1 dont elle sortait, affines
rigoureusement identiques : ANTs a rendu une rotation de 56 degrés, une mise à
l'échelle de 0,77 et une translation de 4 mm, soit plus de 30 mm d'erreur au
bord du cerveau. Rien n'a échoué et rien n'a prévenu.

Deux raisons, chacune suffisante. Il n'y avait rien à estimer. Et une carte
statistique n'a aucune correspondance d'intensité avec une anatomie, donc la
métrique n'a pas de maximum à trouver et l'optimiseur s'arrête où le hasard le
mène.
"""

from __future__ import annotations

import numpy as np
import pytest
import SimpleITK as sitk

from neuxelec.coregistration import (
    same_physical_space,
    write_identity_affine,
)


def volume(size=(8, 9, 10), spacing=(1.0, 1.0, 1.0), origin=(0.0, 0.0, 0.0),
           direction=None, valeur=1.0):
    img = sitk.GetImageFromArray(
        np.full((size[2], size[1], size[0]), valeur, dtype=np.float32)
    )
    img.SetSpacing(spacing)
    img.SetOrigin(origin)
    if direction is not None:
        img.SetDirection(direction)
    return img


def test_un_volume_partage_son_espace_avec_lui_meme():
    a = volume()
    assert same_physical_space(a, a) is True


def test_deux_volumes_de_meme_geometrie_partagent_leur_espace():
    """Le cas réel : une carte statistique et l'anatomie dont elle sort."""
    a = volume(valeur=1.0)
    b = volume(valeur=7.0)   # contenu différent, géométrie identique
    assert same_physical_space(a, b) is True


@pytest.mark.parametrize(
    "ecart, attendu",
    [
        ({"size": (8, 9, 11)}, False),
        ({"spacing": (1.0, 1.0, 2.0)}, False),
        ({"origin": (0.0, 0.0, 5.0)}, False),
    ],
)
def test_toute_difference_de_geometrie_est_vue(ecart, attendu):
    assert same_physical_space(volume(), volume(**ecart)) is attendu


def test_une_orientation_differente_est_vue():
    """Même grille, axes retournés : ce n'est pas le même espace."""
    couche = (-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0)
    assert same_physical_space(volume(), volume(direction=couche)) is False


def test_un_ecart_de_flottant_ne_compte_pas():
    """La tolérance sert à cela : un dixième de micron ne déplace rien."""
    a = volume()
    b = volume(origin=(1e-9, 0.0, 0.0), spacing=(1.0 + 1e-9, 1.0, 1.0))
    assert same_physical_space(a, b) is True


def test_un_dixieme_de_millimetre_compte():
    """Au-delà de la tolérance, la différence est réelle et doit être vue."""
    assert same_physical_space(volume(), volume(origin=(0.1, 0.0, 0.0))) is False


def test_la_comparaison_ne_leve_jamais():
    """Appelée avant chaque coregistration, elle ne doit jamais interrompre."""
    assert same_physical_space("fichier_qui_nexiste_pas.nii", volume()) is False


def test_la_matrice_identite_est_ecrite_et_relisible(tmp_path):
    chemin = write_identity_affine(str(tmp_path / "id_0GenericAffine.mat"))
    t = sitk.ReadTransform(chemin)
    p = np.array(t.GetParameters())
    assert np.allclose(p[:9], np.eye(3).ravel(), atol=1e-12)
    assert np.allclose(p[9:12], 0.0, atol=1e-12)


def test_la_matrice_identite_cree_son_dossier(tmp_path):
    cible = tmp_path / "pas" / "encore" / "la" / "id.mat"
    assert write_identity_affine(str(cible)) == str(cible)
    assert cible.is_file()


def test_le_moteur_sait_reemployer_une_matrice():
    """Le paramètre existe et court-circuite l'estimation."""
    import inspect

    from neuxelec.coregistration import rigid_coreg_to_fixed

    signature = inspect.signature(rigid_coreg_to_fixed)
    assert "existing_affine_mat" in signature.parameters
    source = inspect.getsource(rigid_coreg_to_fixed)
    assert "apply_existing_affine" in source


def test_le_worker_transmet_la_matrice():
    """Sinon le choix de l'utilisateur serait perdu entre l'écran et le moteur."""
    import inspect

    from neuxelec.workers.coreg_workers import CoregWorker

    assert "existing_affine_mat" in inspect.signature(CoregWorker.__init__).parameters
    assert "existing_affine_mat=self.existing_affine_mat" in inspect.getsource(CoregWorker.run)
