"""L'anneau des tetrodes tel que la vue 3D le fabrique.

La vue 3D travaille en RAS alors que les contacts sont stockes en LPS. Une
inversion de signe oubliee placerait l'anneau symetriquement de l'autre cote
du cerveau, sur la bonne coupe et avec le bon rayon : rien ne la trahirait a
part une electrode qui tombe dans le mauvais hemisphere. Ces tests comparent
donc le maillage produit a la position du contact 1, converti pareil.
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
        return object()


class _Page:
    """Les quatre choses que le dessin de l'anneau touche."""

    def __init__(self, coche=True):
        self.btn_micro_tetrodes = _Bouton(coche)
        self.plotter = _Plotter()
        self._elec_actors = {}

    def _apply_electrode_actor_depth_mode(self, actor):
        pass

    _draw_micro_tetrode_ring = View3DPage._draw_micro_tetrode_ring


def _electrode(ref="DIXI-MM08-09A33D08", pas=3.9, n=9):
    """Contact 1 a l'origine, electrode filant vers les x LPS negatifs."""
    return {
        "ref": ref,
        "d_mm": pas,
        "contacts_lps": [(-pas * i, 0.0, 0.0) for i in range(n)],
    }


def test_un_seul_acteur_et_il_est_range_sous_tetrodes():
    page = _Page()
    page._draw_micro_tetrode_ring(3, _electrode(), (0.0, 1.0, 0.0))
    assert len(page.plotter.meshes) == 1
    assert list(page._elec_actors.keys()) == [(3, "tetrodes")]


def test_l_anneau_est_translucide():
    """Opaque, il se lirait comme un objet mesure."""
    page = _Page()
    page._draw_micro_tetrode_ring(0, _electrode(), (0.0, 1.0, 0.0))
    _, kwargs = page.plotter.meshes[0]
    assert 0.0 < float(kwargs["opacity"]) < 1.0


def test_le_maillage_fait_bien_deux_virgule_huit_millimetres_de_large():
    """Deux fois 1,4 mm, plus l'epaisseur du tube de part et d'autre."""
    page = _Page()
    page._draw_micro_tetrode_ring(0, _electrode(), (0.0, 1.0, 0.0))
    mesh, _ = page.plotter.meshes[0]
    x0, x1, y0, y1, z0, z1 = mesh.bounds

    # L'electrode suit l'axe x, donc l'anneau s'etale en y et en z.
    assert (y1 - y0) == pytest.approx(2.8, abs=0.5)
    assert (z1 - z0) == pytest.approx(2.8, abs=0.5)
    # et reste mince le long de l'axe : c'est un anneau, pas une sphere.
    assert (x1 - x0) < 0.6


def test_l_anneau_est_du_bon_cote_du_cerveau():
    """Le piege : les contacts sont en LPS, la vue 3D dessine en RAS."""
    contacts = [(-40.0 - 3.9 * i, 12.0, 30.0) for i in range(9)]
    elec = {"ref": "DIXI-MM08-09A33D08", "d_mm": 3.9, "contacts_lps": contacts}

    page = _Page()
    page._draw_micro_tetrode_ring(0, elec, (0.0, 1.0, 0.0))
    mesh, _ = page.plotter.meshes[0]
    centre = np.asarray(mesh.center, dtype=float)

    contact1_ras = _lps_to_ras_points(np.asarray([contacts[0]], dtype=np.float32))[0]
    assert float(np.linalg.norm(centre - contact1_ras)) == pytest.approx(0.268, abs=0.05)


def test_rien_quand_le_bouton_est_relache():
    page = _Page(coche=False)
    page._draw_micro_tetrode_ring(0, _electrode(), (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []
    assert page._elec_actors == {}


def test_rien_pour_une_electrode_sans_tetrodes():
    page = _Page()
    page._draw_micro_tetrode_ring(0, _electrode(ref="DIXI-D08-12AM", pas=3.5, n=12),
                                  (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []


def test_une_electrode_mal_formee_ne_fait_pas_tomber_le_rendu():
    page = _Page()
    for elec in (
        {"ref": "DIXI-MM08-09A33D08", "d_mm": 3.9},
        {"ref": "DIXI-MM08-09A33D08", "d_mm": None, "contacts_lps": []},
        {"ref": "DIXI-MM08-09A33D08", "d_mm": "trois", "contacts_lps": []},
    ):
        page._draw_micro_tetrode_ring(0, elec, (0.0, 1.0, 0.0))
    assert page.plotter.meshes == []
