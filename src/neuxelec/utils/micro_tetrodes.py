# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Où tombent les tétrodes d'une électrode micro-macro DIXI MICRODEEP.

CE QUE LE SCANNER NE MONTRE PAS

Les tétrodes sont quatre microfils de tungstène de 20 µm réunis dans 70 à
80 µm. La fiche DIXI annonce neuf contacts visibles à l'imagerie pour les
modèles à neuf macros : les tétrodes n'en font pas partie. Leur position ne
peut donc venir que de la géométrie du produit, pas d'une reconstruction.

CE QUE LE CONSTRUCTEUR DONNE

Les tétrodes sortent d'un orifice situé entre les macros 1 et 2, à
l'extrémité distale, puis se déploient sur 2 mm à 30 degrés de l'axe. Trois
chiffres, et tout le reste en découle :

    composante le long de l'axe  : 2 x cos(30°) = 1,732 mm
    composante perpendiculaire   : 2 x sin(30°) = 1,000 mm

L'orifice est à 0,9 mm du bord distal du macro 2, quel que soit le modèle.
Seul le pas change d'un modèle à l'autre, et il déplace l'orifice avec lui.

POURQUOI UN ANNEAU ET NON DES POINTS

L'électrode tourne librement autour de son axe pendant l'implantation, et
cette rotation n'est enregistrée nulle part. La profondeur des bouts est
donc connue, leur azimut ne l'est pas. Le lieu honnête est le cercle, et
poser deux points dessus reviendrait à inventer une orientation.

CE QUE L'ON MONTRE : UN TRONC DE CONE

Les tétrodes sont rétractables. Déployées à fond, le bout est sur
l'anneau ; à moitié sorties, il est quelque part entre l'orifice et lui.
Sur toutes les sorties possibles et tous les azimuts possibles, ces bouts
couvrent la surface latérale d'un tronc de cône : petit bout le cercle
des orifices, à la surface de la tige, grand bout l'anneau.

Un cône pointu sur l'axe dirait que la tétrode peut se trouver au centre
de la tige, ce qui est faux : elle en sort. Le petit bout a donc le rayon
de la tige, 0,4 mm, et il se confond avec elle à l'écran.

Sources : DIXI medical, MICRODEEP Micro-Macro Depth Electrode, fiche
produit et présentation Genève du 13.07.2021, pages 4 et 11.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

#: Longueur de la tétrode déployée, en millimètres.
TETRODE_LENGTH_MM = 2.0

#: Angle de la tétrode déployée par rapport à l'axe de la tige, en degrés.
TETRODE_ANGLE_DEG = 30.0

#: Distance de l'orifice de sortie au bord distal du macro 2, en millimètres.
#: Constante sur les six références, ce qui est la signature d'un orifice
#: usiné à une position fixe.
EXIT_TO_NEXT_CONTACT_MM = 0.9

#: Longueur d'un contact macro platine-iridium, en millimètres.
CONTACT_LENGTH_MM = 2.0

#: Rayon de la tige, en millimètres. Le diamètre annoncé est de 0,8 mm.
SHAFT_RADIUS_MM = 0.4

#: Nombre de tétrodes par référence. Les quatre fils d'une tétrode tiennent
#: dans 80 µm, donc une tétrode est un point et non quatre.
TETRODE_COUNT = {
    "MM08-09A33D08": 2,
    "MM08-09A40D08": 2,
    "MM08-09A51D08": 2,
    "MM08-06B33D12": 3,
    "MM08-06B40D12": 3,
    "MM08-06B51D12": 3,
}


@dataclass(frozen=True)
class TetrodeRing:
    """Le cercle sur lequel tombent les bouts des tétrodes.

    ``center`` et ``axis`` sont en millimètres LPS, comme les contacts.
    ``axis`` est unitaire et pointe vers la pointe de l'électrode, donc vers
    le fond du cerveau.
    """

    center: np.ndarray
    axis: np.ndarray
    radius_mm: float
    n_tetrodes: int
    exit_center: np.ndarray


def normalise_reference(ref: str | None) -> str:
    """Rendre une référence comparable, préfixe constructeur retiré.

    Les projets reconstruits avant l'ajout du préfixe stockent 'MM08-...',
    les suivants 'DIXI-MM08-...'. Les deux désignent la même électrode.
    """
    if not ref:
        return ""
    return re.sub(r"^DIXI-", "", str(ref).strip(), flags=re.IGNORECASE).upper()


def tetrode_count(ref: str | None) -> int:
    """Nombre de tétrodes de cette référence, zéro si elle n'en a pas."""
    return TETRODE_COUNT.get(normalise_reference(ref), 0)


def has_tetrodes(ref: str | None) -> bool:
    return tetrode_count(ref) > 0


def ring_radius_mm() -> float:
    """Rayon de l'anneau, mesuré depuis l'axe de la tige."""
    return SHAFT_RADIUS_MM + TETRODE_LENGTH_MM * math.sin(math.radians(TETRODE_ANGLE_DEG))


def ring_offset_from_first_contact_mm(pitch_mm: float) -> float:
    """Recul de l'anneau derrière le centre du contact 1, en millimètres.

    Compté depuis la pointe, l'orifice est à ``pitch - 0,9`` et l'anneau à
    1,732 mm plus loin vers la pointe. Le centre du contact 1 est lui à
    1 mm de la pointe, le contact faisant 2 mm et commençant à la pointe.
    """
    apex_to_exit = float(pitch_mm) - EXIT_TO_NEXT_CONTACT_MM
    apex_to_ring = apex_to_exit - TETRODE_LENGTH_MM * math.cos(
        math.radians(TETRODE_ANGLE_DEG)
    )
    return apex_to_ring - CONTACT_LENGTH_MM / 2.0


def exit_offset_from_first_contact_mm(pitch_mm: float) -> float:
    """Recul de l'orifice de sortie derrière le centre du contact 1."""
    return (float(pitch_mm) - EXIT_TO_NEXT_CONTACT_MM) - CONTACT_LENGTH_MM / 2.0


def shaft_axis(contacts_lps) -> np.ndarray | None:
    """Direction de la tige, unitaire, pointant vers la pointe.

    Ajustée sur toute la chaîne plutôt que sur les deux premiers contacts :
    deux points voisins sont séparés de quelques millimètres seulement, et
    le bruit de reconstruction y pèse bien plus que sur une droite ajustée
    sur dix. Une électrode SEEG est droite, l'ajustement global est donc
    fidèle jusqu'à la pointe.
    """
    try:
        pts = np.asarray(contacts_lps, dtype=float)
    except Exception:
        return None
    if pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] != 3:
        return None
    if not np.all(np.isfinite(pts)):
        return None

    centered = pts - pts.mean(axis=0)
    try:
        _, valeurs, vh = np.linalg.svd(centered, full_matrices=False)
    except Exception:
        return None

    # Des contacts tous confondus n'ont pas d'axe, mais la decomposition rend
    # quand meme un vecteur unitaire arbitraire. Seule la valeur singuliere
    # dit que la droite n'est appuyee sur rien.
    if float(valeurs[0]) <= 1e-6:
        return None

    direction = np.asarray(vh[0], dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-9:
        return None
    direction = direction / norm

    # Orienter vers la pointe, c'est-a-dire du dernier contact vers le premier.
    if float(np.dot(pts[0] - pts[-1], direction)) < 0.0:
        direction = -direction
    return direction


def perpendicular_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Deux vecteurs unitaires orthogonaux à ``axis`` et entre eux.

    Le vecteur de départ est choisi selon la plus petite composante de
    l'axe : prendre toujours le même risquerait de le trouver colinéaire à
    l'axe, et le produit vectoriel s'effondrerait.
    """
    axis = np.asarray(axis, dtype=float)
    depart = np.zeros(3, dtype=float)
    depart[int(np.argmin(np.abs(axis)))] = 1.0

    u = np.cross(axis, depart)
    u = u / float(np.linalg.norm(u))
    v = np.cross(axis, u)
    return u, v / float(np.linalg.norm(v))


def _circle_points(center, axis, radius_mm: float, n: int) -> np.ndarray:
    u, v = perpendicular_basis(axis)
    angles = np.linspace(0.0, 2.0 * np.pi, int(n), endpoint=False)
    return (
        np.asarray(center, dtype=float)[None, :]
        + float(radius_mm) * (np.cos(angles)[:, None] * u[None, :])
        + float(radius_mm) * (np.sin(angles)[:, None] * v[None, :])
    )


def ring_points(ring: TetrodeRing, n: int = 64) -> np.ndarray:
    """Échantillonner l'anneau en ``n`` points, en millimètres LPS."""
    return _circle_points(ring.center, ring.axis, ring.radius_mm, n)


def exit_points(ring: TetrodeRing, n: int = 64) -> np.ndarray:
    """Le cercle des orifices, à la surface de la tige.

    L'azimut de l'orifice n'est pas connu, pas plus que celui du bout :
    c'est la même rotation qui les emporte tous les deux.
    """
    return _circle_points(ring.exit_center, ring.axis, SHAFT_RADIUS_MM, n)


def cone_surface(ring: TetrodeRing, n: int = 96) -> tuple[np.ndarray, np.ndarray]:
    """La surface latérale du tronc de cône : sommets et triangles.

    Les sommets sont en millimètres LPS, les ``n`` premiers sur le cercle
    des orifices et les ``n`` suivants sur l'anneau. Les faces sont au
    format de PyVista, chaque triangle précédé de son nombre de sommets.
    """
    n = max(3, int(n))
    petit = exit_points(ring, n)
    grand = ring_points(ring, n)
    sommets = np.vstack([petit, grand])

    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend([3, i, j, n + j])
        faces.extend([3, i, n + j, n + i])
    return sommets, np.asarray(faces, dtype=np.int64)


def tetrode_ring(
    ref: str | None,
    pitch_mm: float | None,
    contacts_lps,
) -> TetrodeRing | None:
    """L'anneau de cette électrode, ou ``None`` si elle n'a pas de tétrodes.

    ``pitch_mm`` est le pas réellement utilisé pour placer les contacts, et
    non celui du catalogue : si les deux diffèrent, l'anneau doit suivre les
    contacts qui sont à l'écran, sinon il flotterait à côté d'eux.
    """
    n = tetrode_count(ref)
    if n <= 0:
        return None

    try:
        pitch = float(pitch_mm)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(pitch) or pitch <= 0.0:
        return None

    axis = shaft_axis(contacts_lps)
    if axis is None:
        return None

    first = np.asarray(contacts_lps, dtype=float)[0]
    center = first - axis * ring_offset_from_first_contact_mm(pitch)
    exit_center = first - axis * exit_offset_from_first_contact_mm(pitch)

    return TetrodeRing(
        center=center,
        axis=axis,
        radius_mm=ring_radius_mm(),
        n_tetrodes=n,
        exit_center=exit_center,
    )
