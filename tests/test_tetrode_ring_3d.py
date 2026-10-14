# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le cone des tetrodes tel que la vue 3D le fabrique.

La vue 3D travaille en RAS alors que les contacts sont stockes en LPS. Une
inversion de signe oubliee placerait le cone symetriquement de l'autre cote
du cerveau, sur la bonne coupe et avec le bon rayon : rien ne la trahirait a
part une electrode qui tombe dans le mauvais hemisphere. Ces tests comparent
donc le maillage produit a la position du contact 1, converti pareil.

Deux maillages sortent de la : le tronc de cone, qui couvre les sorties
partielles, et l'anneau de son grand bout, qui est la position nominale.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from neuxelec.pages.view3d import View3DPage, _lps_to_ras_points  # noqa: E402


class _Bouton:
    def __init__(self, coche: bool):
        self._coche = coche

    def isChecked(self):
        return self._coche


class _Plotter:
    def __init__(self):
        self.meshes = []

    def add_mesh(self, mesh, **kwargs):
        self.meshes.append((mesh, kwargs))
        # Rendre le maillage lui-meme: les acteurs sont alors ranges par
        # nom dans la page, et un test lit celui qu'il veut au lieu de
        # compter sur un ordre d'ajout.
        return mesh


class _Page:
    """Les quatre choses que le dessin de l'anneau touche."""

    def __init__(self, coche=True):
        self.btn_micro_tetrodes = _Bouton(coche)
        self.plotter = _Plotter()
        self._elec_actors = {}

    def _apply_electrode_actor_depth_mode(self, actor):
        pass

    _draw_micro_tetrode_cone = View3DPage._draw_micro_tetrode_cone


def _electrode(ref="DIXI-MM08-09A33D08", pas=3.9, n=9):
    """Contact 1 a l'origine, electrode filant vers les x LPS negatifs."""
    return {
        "ref": ref,
        "d_mm": pas,
        "contacts_lps": [(-pas * i, 0.0, 0.0) for i in range(n)],
    }


def test_trois_acteurs_le_cone_et_ses_deux_bouts():
    page = _Page()
    page._draw_micro_tetrode_cone(3, _electrode(), (0.0, 1.0, 0.0))

    assert len(page.plotter.meshes) == 3
    assert set(page._elec_actors) == {
        (3, "tetrodes"),
        (3, "tetrodes_cone"),
        (3, "tetrodes_exit"),
    }


def test_tout_est_translucide_et_le_cone_le_plus():
    """Opaques, ils se liraient comme des objets mesures. Et le cone est
    le plus efface: il dit ce qui est possible, les deux cercles disent
    ou commence et ou finit cette possibilite."""
    page = _Page()
    page._draw_micro_tetrode_cone(0, _electrode(), (0.0, 1.0, 0.0))

    opacites = {}
    for mesh, kwargs in page.plotter.meshes:
        opacites[id(mesh)] = float(kwargs["opacity"])

    cone = opacites[id(page._elec_actors[(0, "tetrodes_cone")])]
    anneau = opacites[id(page._elec_actors[(0, "tetrodes")])]
    orifice = opacites[id(page._elec_actors[(0, "tetrodes_exit")])]

    assert 0.0 < cone < anneau < 1.0
    assert orifice == anneau


def test_les_deux_cercles_ont_presque_le_meme_trait():
    """Ce sont les deux bouts du meme objet. Un gros tube a l'anneau en
    faisait un beignet, qui pesait plus que ce qu'il montrait."""
    page = _Page()
    page._draw_micro_tetrode_cone(0, _electrode(), (0.0, 1.0, 0.0))

    anneau = page._elec_actors[(0, "tetrodes")]
    orifice = page._elec_actors[(0, "tetrodes_exit")]

    # L'electrode suit l'axe x: l'epaisseur du tube se lit le long de x.
    epaisseur_anneau = anneau.bounds[1] - anneau.bounds[0]
    epaisseur_orifice = orifice.bounds[1] - orifice.bounds[0]
    assert epaisseur_anneau == pytest.approx(0.18, abs=0.02)
    assert epaisseur_orifice == pytest.approx(0.14, abs=0.02)


def test_l_anneau_fait_bien_deux_virgule_huit_millimetres_de_large():
    """Deux fois 1,4 mm, plus l'epaisseur du tube de part et d'autre."""
    page = _Page()
    page._draw_micro_tetrode_cone(0, _electrode(), (0.0, 1.0, 0.0))
    mesh = page._elec_actors[(0, "tetrodes")]
    x0, x1, y0, y1, z0, z1 = mesh.bounds

    # L'electrode suit l'axe x, donc l'anneau s'etale en y et en z.
    assert (y1 - y0) == pytest.approx(2.8, abs=0.5)
    assert (z1 - z0) == pytest.approx(2.8, abs=0.5)
    # et reste mince le long de l'axe : c'est un anneau, pas une sphere.
    assert (x1 - x0) < 0.6


def test_le_cone_va_de_l_orifice_a_l_anneau():
    """0,8 mm de large a un bout, 2,8 a l'autre, 1,73 mm entre les deux."""
    page = _Page()
    page._draw_micro_tetrode_cone(0, _electrode(), (0.0, 1.0, 0.0))
    cone = page._elec_actors[(0, "tetrodes_cone")]
    x0, x1, y0, y1, z0, z1 = cone.bounds

    assert (x1 - x0) == pytest.approx(2.0 * np.cos(np.radians(30.0)), abs=1e-3)
    assert (y1 - y0) == pytest.approx(2.8, abs=1e-2)
    assert (z1 - z0) == pytest.approx(2.8, abs=1e-2)

    # Un bout a le rayon de la tige et l'autre celui de l'anneau: la
    # tetrode sort de la surface, pas du centre. Le sens de l'axe x change
    # entre LPS et RAS, donc on mesure les deux bouts sans presumer lequel
    # est a gauche.
    points = np.asarray(cone.points, dtype=float)
    ordre = np.argsort(points[:, 0])
    moitie = len(points) // 2
    rayons = []
    for bout in (points[ordre[:moitie]], points[ordre[moitie:]]):
        rayons.append(
            float(np.linalg.norm(bout[:, 1:] - bout[:, 1:].mean(axis=0), axis=1).mean())
        )
    assert sorted(rayons) == pytest.approx([0.4, 1.4], abs=1e-6)


def test_le_cone_est_du_bon_cote_du_cerveau():
    """Le piege : les contacts sont en LPS, la vue 3D dessine en RAS."""
    contacts = [(-40.0 - 3.9 * i, 12.0, 30.0) for i in range(9)]
    elec = {"ref": "DIXI-MM08-09A33D08", "d_mm": 3.9, "contacts_lps": contacts}

    page = _Page()
    page._draw_micro_tetrode_cone(0, elec, (0.0, 1.0, 0.0))
    mesh = page._elec_actors[(0, "tetrodes")]
    centre = np.asarray(mesh.center, dtype=float)

    contact1_ras = _lps_to_ras_points(np.asarray([contacts[0]], dtype=np.float32))[0]
    assert float(np.linalg.norm(centre - contact1_ras)) == pytest.approx(0.268, abs=0.05)


def test_rien_quand_le_bouton_est_relache():
    page = _Page(coche=False)
    page._draw_micro_tetrode_cone(0, _electrode(), (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []
    assert page._elec_actors == {}


def test_rien_pour_une_electrode_sans_tetrodes():
    page = _Page()
    page._draw_micro_tetrode_cone(0, _electrode(ref="DIXI-D08-12AM", pas=3.5, n=12),
                                  (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []


def test_une_electrode_mal_formee_ne_fait_pas_tomber_le_rendu():
    page = _Page()
    for elec in (
        {"ref": "DIXI-MM08-09A33D08", "d_mm": 3.9},
        {"ref": "DIXI-MM08-09A33D08", "d_mm": None, "contacts_lps": []},
        {"ref": "DIXI-MM08-09A33D08", "d_mm": "trois", "contacts_lps": []},
    ):
        page._draw_micro_tetrode_cone(0, elec, (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []
