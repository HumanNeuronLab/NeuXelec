"""Ce que l'anneau des tetrodes devient une fois projete sur la coupe.

La coupe oblique contient l'axe de l'electrode, par construction. L'anneau
lui est perpendiculaire, donc il est toujours vu par la tranche : il se
projette en un segment de 2,8 mm en travers de la tige, et non en cercle.
C'est la bonne lecture, et c'est ce que ces tests fixent, parce qu'un
cercle dessine la serait une invention.

La vue 3D, elle, montre l'anneau entier. Les deux vues disent la meme
chose vue d'ailleurs.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402

#: 20 mm de part et d'autre, 201 pixels : un millimetre vaut dix pixels.
S_MIN, S_MAX, T_MIN, T_MAX = -10.0, 10.0, -10.0, 10.0
H = W = 201
PX_PAR_MM = (H - 1) / (S_MAX - S_MIN)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Case:
    def __init__(self, cochee: bool):
        self._cochee = cochee

    def isChecked(self):
        return self._cochee


class _Page:
    """Juste de quoi appeler la projection."""

    def __init__(self, cochee=True):
        self.chk_micro_tetrodes = _Case(cochee)

    _project_tetrode_ring_for_cached_slice = (
        ObliqueSlicePage._project_tetrode_ring_for_cached_slice
    )


def _electrode(ref="DIXI-MM08-09A33D08", pas=3.9, n=9):
    """Contact 1 a l'origine, electrode filant vers les x negatifs."""
    return {
        "ref": ref,
        "d_mm": pas,
        "contacts_lps": [(-pas * i, 0.0, 0.0) for i in range(n)],
    }


def _projeter(page, elec, center=(0.0, 0.0, 0.0)):
    return page._project_tetrode_ring_for_cached_slice(
        elec,
        np.asarray(center, dtype=float),
        np.array([1.0, 0.0, 0.0]),  # lignes, le long de l'electrode
        np.array([0.0, 1.0, 0.0]),  # colonnes, en travers
        S_MIN,
        S_MAX,
        T_MIN,
        T_MAX,
        H,
        W,
    )


def test_l_anneau_traverse_la_tige_sur_deux_virgule_huit_millimetres(app):
    """Deux fois le rayon de 1,4 mm, et pas davantage."""
    pts = _projeter(_Page(), _electrode())
    assert pts, "aucun point projete"

    cols = np.array([c for _, c in pts], dtype=float)
    largeur_mm = (cols.max() - cols.min()) / PX_PAR_MM
    assert largeur_mm == pytest.approx(2.8, abs=0.05)


def test_l_anneau_tombe_a_la_profondeur_du_contact_un(app):
    """Pour un pas de 3,9 mm, 0,27 mm derriere, soit moins d'un demi-pixel."""
    pts = _projeter(_Page(), _electrode())
    rows = np.array([r for r, _ in pts], dtype=float)

    # Le contact 1 est au centre du plan, donc a la ligne (H - 1) / 2.
    # L'anneau recule vers l'arriere de l'electrode, donc vers les lignes
    # decroissantes : le recul est compte positif dans ce sens.
    recul_mm = -(rows.mean() - (H - 1) / 2.0) / PX_PAR_MM
    assert recul_mm == pytest.approx(0.268, abs=0.06)
    assert rows.max() - rows.min() <= 1, "l'anneau doit etre vu par la tranche"


def test_un_pas_plus_grand_recule_l_anneau(app):
    """Le 09A51 a un pas de 6,1 mm : son anneau recule de 2,47 mm."""
    pts = _projeter(_Page(), _electrode(ref="DIXI-MM08-09A51D08", pas=6.1))
    rows = np.array([r for r, _ in pts], dtype=float)
    recul_mm = -(rows.mean() - (H - 1) / 2.0) / PX_PAR_MM
    assert recul_mm == pytest.approx(6.1 - 3.63, abs=0.06)


def test_rien_quand_la_case_est_decochee(app):
    assert _projeter(_Page(cochee=False), _electrode()) == []


def test_rien_pour_une_electrode_sans_tetrodes(app):
    assert _projeter(_Page(), _electrode(ref="DIXI-D08-12AM", pas=3.5, n=12)) == []


def test_rien_quand_la_coupe_a_glisse_loin_de_l_electrode(app):
    """Comme les contacts, l'anneau disparait au-dela de deux millimetres."""
    assert _projeter(_Page(), _electrode(), center=(0.0, 0.0, 3.0)) == []
    assert _projeter(_Page(), _electrode(), center=(0.0, 0.0, 1.0)) != []


def test_une_electrode_mal_formee_ne_fait_pas_tomber_le_rendu(app):
    """Un rendu qui leve laisse la page vide, ce qui est pire que rien."""
    page = _Page()
    assert _projeter(page, {"ref": "DIXI-MM08-09A33D08", "d_mm": 3.9}) == []
    assert _projeter(page, {"ref": None, "d_mm": None, "contacts_lps": []}) == []
    assert _projeter(page, {"ref": "DIXI-MM08-09A33D08", "d_mm": "trois"}) == []
