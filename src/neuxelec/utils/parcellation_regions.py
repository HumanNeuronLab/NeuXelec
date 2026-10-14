# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Les régions d'une parcellation, et les contacts qui tombent dedans.

POURQUOI REPRENDRE L'ATTRIBUTION DE SEEG2PARC

NeuXelec attribue déjà une région à chaque contact, dans le tableau de la
coupe oblique et dans l'export BIDS : celle qui domine le cube de 3x3x3
voxels centré sur lui, chaque voisin pesant l'inverse de sa distance. Lire
simplement le voxel sous le contact donnerait parfois une autre réponse,
et deux endroits de l'application se contrediraient sur le même contact.
Ce module appelle donc la même fonction.

POURQUOI NE LISTER QUE LES REGIONS PRESENTES

Une table de couleurs FreeSurfer compte plus de mille entrées, dont la
quasi-totalité n'apparaît dans aucun sujet. Lister le fichier donnerait
mille lignes vides à faire défiler. Seules les étiquettes réellement
présentes dans le volume sont rendues.

POURQUOI UNE BOITE ENGLOBANTE PAR REGION

Un maillage par région veut dire autant de passages de marching cubes. Sur
le volume entier, pour 400 régions, cela revient à parcourir 400 fois
16 millions de voxels. Chaque région n'occupe qu'une petite boîte : la
découper d'abord ramène le travail à sa taille réelle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

#: L'étiquette du fond, jamais une région.
BACKGROUND = 0


@dataclass(frozen=True)
class Region:
    """Une ligne du tableau des régions."""

    label: int
    name: str
    color: tuple[int, int, int]
    contacts: tuple[str, ...]

    @property
    def has_contacts(self) -> bool:
        return bool(self.contacts)


def lut_entry(lut: dict, label: int) -> tuple[str, tuple[int, int, int]]:
    """Nom et couleur d'une étiquette, avec les mêmes replis qu'ailleurs.

    Une entrée est soit un nom, soit ``(nom, (r, g, b))``. Une étiquette
    absente garde son numéro plutôt que de disparaître : elle existe dans
    le volume, donc elle a une ligne.
    """
    entry = (lut or {}).get(int(label))
    if entry is None:
        return (f"label-{int(label)}", (255, 255, 255))
    if isinstance(entry, str):
        return (entry, (255, 255, 255))
    try:
        name, rgb = entry
        return (str(name), tuple(int(c) for c in rgb))
    except Exception:
        return (f"label-{int(label)}", (255, 255, 255))


def native_contact_points(electrodes) -> list[tuple[str, tuple[float, float, float]]]:
    """``[(nom, point LPS), ...]`` depuis les électrodes du patient.

    Les contacts n'y portent pas de nom propre : il se compose du nom de
    l'électrode et du rang du contact, comme partout ailleurs dans
    NeuXelec.
    """
    points: list[tuple[str, tuple[float, float, float]]] = []
    for elec in electrodes or []:
        nom = str((elec or {}).get("name", "E"))
        for i, point in enumerate((elec or {}).get("contacts_lps", []) or [], start=1):
            try:
                points.append(
                    (f"{nom}{i}", (float(point[0]), float(point[1]), float(point[2])))
                )
            except Exception:
                continue
    return points


def mni_contact_points(sets) -> list[tuple[str, tuple[float, float, float]]]:
    """``[(nom, point LPS), ...]`` depuis les jeux d'électrodes MNI.

    Les electrodes.tsv donnent des coordonnées **MNI RAS**, alors qu'une
    image SimpleITK se lit en LPS : x et y changent de signe. Sans cette
    conversion chaque contact atterrirait dans l'hémisphère opposé et une
    région en avant de la sienne, ce que rien ne viendrait signaler.

    Les contacts y portent leur propre nom, qui n'est pas a recomposer.
    """
    points: list[tuple[str, tuple[float, float, float]]] = []
    for jeu in sets or []:
        for contact in (jeu or {}).get("contacts", []) or []:
            try:
                x, y, z = (float(v) for v in contact["mni_ras"])
            except Exception:
                continue
            nom = str(contact.get("name", "") or "").strip()
            if not nom:
                continue
            points.append((nom, (-x, -y, z)))
    return points


def contact_region_labels(parcel_img, parc_vol: np.ndarray, points) -> dict[str, int]:
    """``{nom du contact: étiquette dominante}``, selon SEEG2parc.

    ``points`` est une suite de ``(nom, point en LPS)``. La fonction ne
    devine plus la forme de ce qu'on lui donne : les contacts du patient
    et ceux d'un jeu MNI n'ont ni la même structure ni le même repère, et
    confondre les deux placerait chacun au mauvais endroit.

    Un contact absent du résultat n'est dans aucune région. Trois cas
    mènent là, et aucun n'est une région : le contact tombe hors du
    volume, sa position est illisible, ou c'est le fond qui domine son
    cube. Le dernier arrive pour de bon, quand la structure est plus
    petite que le cube de 3x3x3 voxels, et le ranger sous l'étiquette zéro
    inventerait une région qui n'existe pas.
    """
    from ..seeg2parc import cube_label_weights

    out: dict[str, int] = {}
    if parcel_img is None or parc_vol is None:
        return out

    for nom, point in points or []:
        try:
            idx = parcel_img.TransformPhysicalPointToIndex(
                tuple(float(v) for v in point)
            )
        except Exception:
            continue
        # L'index SimpleITK est (x, y, z), le tableau numpy est [z, y, x].
        vox = (idx[2], idx[1], idx[0])
        if not all(0 <= v < s for v, s in zip(vox, parc_vol.shape, strict=True)):
            continue
        try:
            poids = cube_label_weights(parc_vol, vox)
        except Exception:
            continue
        if not poids:
            continue
        dominante = int(poids[0][0])
        if dominante == BACKGROUND:
            continue
        out[str(nom)] = dominante
    return out


def build_regions(
    parcel_img,
    parc_vol: np.ndarray,
    lut: dict,
    points,
) -> list[Region]:
    """Toutes les régions du volume, nommées, avec leurs contacts.

    Triées par nom : un tri par numéro d'étiquette éparpillerait les
    hémisphères, alors que les noms FreeSurfer regroupent d'eux-mêmes les
    ``ctx-lh-``, les ``ctx-rh-`` et les structures sous-corticales.
    """
    if parc_vol is None:
        return []

    par_contact = contact_region_labels(parcel_img, parc_vol, points)
    par_region: dict[int, list[str]] = {}
    for contact, label in par_contact.items():
        par_region.setdefault(int(label), []).append(contact)

    presentes = [int(v) for v in np.unique(parc_vol) if int(v) != BACKGROUND]

    regions = []
    for label in presentes:
        nom, couleur = lut_entry(lut, label)
        regions.append(
            Region(
                label=label,
                name=nom,
                color=couleur,
                contacts=tuple(sorted(par_region.get(label, []))),
            )
        )
    regions.sort(key=lambda r: (r.name.lower(), r.label))
    return regions


def region_bounds(parc_vol: np.ndarray, label: int, margin: int = 1):
    """La boîte englobante d'une région, ``None`` si elle est absente.

    ``margin`` élargit d'un voxel pour que marching cubes puisse fermer la
    surface : sans marge, une région qui touche le bord de sa boîte rend un
    maillage ouvert.
    """
    if parc_vol is None:
        return None
    masque = parc_vol == int(label)
    if not masque.any():
        return None

    bornes = []
    for axe in range(3):
        autres = tuple(a for a in range(3) if a != axe)
        presence = masque.any(axis=autres)
        indices = np.flatnonzero(presence)
        debut = max(0, int(indices[0]) - margin)
        fin = min(parc_vol.shape[axe], int(indices[-1]) + 1 + margin)
        bornes.append((debut, fin))
    return tuple(bornes)


def cropped_region_mask(parc_vol: np.ndarray, label: int, margin: int = 1):
    """``(masque binaire découpé, coin de la découpe)``, ou ``None``.

    Le coin est rendu en indices numpy ``(z, y, x)`` : l'appelant en a
    besoin pour replacer le maillage dans le volume complet.
    """
    bornes = region_bounds(parc_vol, label, margin=margin)
    if bornes is None:
        return None
    (z0, z1), (y0, y1), (x0, x1) = bornes
    masque = (parc_vol[z0:z1, y0:y1, x0:x1] == int(label)).astype(np.uint8)
    return masque, (z0, y0, x0)
