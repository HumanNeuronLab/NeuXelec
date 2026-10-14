# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fondre deux IRM anatomiques en une seule image affichable.

POURQUOI MÉLANGER LES VOLUMES ET NON LES COUPES

Les coupes obliques comme la vue 3D sont écrites pour une seule image
anatomique : l'échantillonnage, les caches et le compositeur la supposent
unique. Mélanger en amont laisse tout cet aval intact, et c'est fondé puisque
MRI 2 est coregistrée dans l'espace de MRI 1 avant de pouvoir être affichée :
les deux volumes décrivent les mêmes millimètres.

POURQUOI NORMALISER CHACUNE SÉPARÉMENT

Un T1 et un T2 ne partagent pas leur échelle d'intensité. Mélanger les valeurs
brutes laisserait celle qui porte les plus grands nombres recouvrir l'autre,
quelles que soient les opacités réglées. Chacune est donc ramenée entre 0 et 1
sur ses propres centiles avant d'être composée.

L'ORDRE COMPTE

La première de la liste est le fond, les suivantes passent par-dessus. L'opacité
de la seconde se lit alors comme un fondu entre les deux, qui est le geste réel
quand on compare un avant et un après.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import SimpleITK as sitk

logger = logging.getLogger(__name__)


def to_unit(img: sitk.Image) -> np.ndarray | None:
    """Ramener une image entre 0 et 1 sur ses centiles 1 et 99.

    Les centiles plutôt que le minimum et le maximum : un seul voxel aberrant,
    et un étirement sur les extrêmes écraserait tout le reste vers le noir.
    """
    a = sitk.GetArrayFromImage(img).astype(np.float32)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return None
    lo = float(np.percentile(finite, 1.0))
    hi = float(np.percentile(finite, 99.0))
    if hi <= lo:
        lo, hi = float(finite.min()), float(finite.max()) + 1.0
    return np.clip((a - lo) / max(1e-6, hi - lo), 0.0, 1.0)


def blend_mri_volumes(
    sources: Sequence[tuple[sitk.Image, int]],
    *,
    always_normalise: bool = False,
) -> sitk.Image | None:
    """Composer ``[(image, opacité en pour cent), ...]`` en une seule image.

    Zéro source donne ``None``. Une seule est rendue telle quelle, avec ses
    valeurs d'origine, sauf si ``always_normalise``.

    ``always_normalise`` sert l'affichage, et il est indispensable là-bas. Le
    compositeur des coupes ré-étire ce qu'il reçoit sur ses centiles 1 et 99 :
    une image assombrie de 40 % lui revient donc à pleine échelle, et l'opacité
    n'a aucun effet visible. En normalisant ici, l'appelant peut dire au
    compositeur de ne plus le faire, et le réglage redevient visible.
    """
    visible = [(img, int(pct)) for img, pct in sources if img is not None]
    if not visible:
        return None
    if len(visible) == 1 and not always_normalise:
        return visible[0][0]
    if len(visible) == 1:
        img, pct = visible[0]
        unit = to_unit(img)
        if unit is None:
            return img
        out = sitk.GetImageFromArray(
            (unit * (float(np.clip(pct, 0, 100)) / 100.0)).astype(np.float32)
        )
        out.CopyInformation(img)
        return out

    base = visible[0][0]
    try:
        blend = None
        for index, (img, pct) in enumerate(visible):
            if index > 0 and (
                tuple(img.GetSize()) != tuple(base.GetSize())
                or not np.allclose(img.GetOrigin(), base.GetOrigin(), atol=1e-3)
            ):
                # Ne devrait pas arriver, MRI 2 étant coregistrée, mais une
                # grille différente doit produire une image et non une
                # exception au milieu d'un rendu.
                img = sitk.Resample(
                    img, base, sitk.Transform(), sitk.sitkLinear, 0.0, img.GetPixelID()
                )
            unit = to_unit(img)
            if unit is None:
                continue
            a = float(np.clip(pct, 0, 100)) / 100.0
            blend = unit * a if blend is None else blend * (1.0 - a) + unit * a

        if blend is None:
            return base
        out = sitk.GetImageFromArray(blend.astype(np.float32))
        out.CopyInformation(base)
        return out
    except Exception:
        logger.exception("Could not blend the anatomical MRIs")
        return base
