"""La geometrie des tetrodes doit redonner le tableau de reference.

Le tableau Electrodes_Parameters donne, par reference, les distances entre
sept points nommes A a G. Ces tests reconstruisent ces distances a partir
des trois seuls chiffres du constructeur, 2 mm, 30 degres et 0,9 mm. Si le
module redonne le tableau, c'est qu'il decrit la meme electrode.

Les valeurs attendues ci-dessous sont lues dans le tableau, pas calculees
ici : un test qui recalculerait l'implementation ne prouverait rien.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from neuxelec.utils.micro_tetrodes import (
    TETRODE_COUNT,
    exit_offset_from_first_contact_mm,
    has_tetrodes,
    normalise_reference,
    ring_offset_from_first_contact_mm,
    ring_radius_mm,
    shaft_axis,
    tetrode_count,
    tetrode_ring,
)

#: reference, pas, AE et FA lus dans Electrodes_Parameters.pdf.
TABLEAU = [
    ("MM08-09A33D08", 3.9, 3.0, 1.62),
    ("MM08-09A40D08", 4.8, 3.9, 2.39),
    ("MM08-09A51D08", 6.1, 5.2, 3.64),
    ("MM08-06B33D12", 4.0, 3.1, 1.70),
]


@pytest.mark.parametrize("ref,pas,AE,FA", TABLEAU)
def test_l_orifice_tombe_ou_le_tableau_le_dit(ref, pas, AE, FA):
    """AE, la distance de la pointe a l'orifice, doit sortir du seul pas."""
    apex_a_orifice = exit_offset_from_first_contact_mm(pas) + 1.0
    assert apex_a_orifice == pytest.approx(AE, abs=0.005)


@pytest.mark.parametrize("ref,pas,AE,FA", TABLEAU)
def test_le_bout_tombe_ou_le_tableau_le_dit(ref, pas, AE, FA):
    """FA, de la pointe au bout de la tetrode, croise l'axial et le radial.

    C'est le test qui compte : FA melange les deux composantes, donc il ne
    peut tomber juste que si la longueur, l'angle et la position de
    l'orifice sont tous les trois bons.
    """
    axial = ring_offset_from_first_contact_mm(pas) + 1.0
    radial = ring_radius_mm() - 0.4  # hauteur au-dessus de la surface
    assert math.hypot(axial, radial) == pytest.approx(FA, abs=0.04)


def test_le_rayon_vaut_un_virgule_quatre():
    """1 mm hors d'une tige de 0,8 mm de diametre."""
    assert ring_radius_mm() == pytest.approx(1.4, abs=1e-9)


def test_les_six_references_sont_connues_et_les_autres_non():
    assert len(TETRODE_COUNT) == 6
    assert tetrode_count("DIXI-MM08-09A33D08") == 2
    assert tetrode_count("DIXI-MM08-06B51D12") == 3
    assert tetrode_count("DIXI-D08-15AM") == 0
    assert not has_tetrodes("DIXI-D08-12AM")
    assert not has_tetrodes(None)


def test_les_projets_anciens_sans_prefixe_marchent_aussi():
    """Un projet reconstruit avant l'ajout du prefixe stocke 'MM08-...'."""
    assert normalise_reference("MM08-09A33D08") == "MM08-09A33D08"
    assert normalise_reference("dixi-mm08-09a33d08") == "MM08-09A33D08"
    assert tetrode_count("MM08-09A40D08") == 2


def _chaine(depart, direction, pas, n):
    """Une electrode droite, contact 1 en premier."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    return [tuple(np.asarray(depart, dtype=float) - d * pas * i) for i in range(n)]


def test_l_axe_pointe_vers_la_pointe():
    """Du dernier contact vers le premier, pas l'inverse."""
    contacts = _chaine((10.0, 0.0, 0.0), (1.0, 0.0, 0.0), 3.9, 9)
    axe = shaft_axis(contacts)
    assert axe == pytest.approx(np.array([1.0, 0.0, 0.0]), abs=1e-9)


def test_l_anneau_recule_derriere_le_contact_un():
    """Pour un pas de 3,9 mm, 0,27 mm derriere le centre du contact 1."""
    contacts = _chaine((10.0, 0.0, 0.0), (1.0, 0.0, 0.0), 3.9, 9)
    anneau = tetrode_ring("DIXI-MM08-09A33D08", 3.9, contacts)
    assert anneau is not None
    assert anneau.n_tetrodes == 2
    assert anneau.radius_mm == pytest.approx(1.4)
    recul = float(np.dot(np.asarray(contacts[0]) - anneau.center, anneau.axis))
    assert recul == pytest.approx(0.268, abs=0.005)


def test_l_anneau_suit_une_electrode_de_travers():
    """Le recul se mesure le long de l'axe, pas le long d'un axe du monde."""
    direction = np.array([0.3, -0.5, 0.81])
    contacts = _chaine((-20.0, 14.0, 30.0), direction, 4.8, 9)
    anneau = tetrode_ring("DIXI-MM08-09A40D08", 4.8, contacts)
    assert anneau is not None
    recul = float(np.dot(np.asarray(contacts[0]) - anneau.center, anneau.axis))
    assert recul == pytest.approx(4.8 - 0.9 - 1.7320508 - 1.0, abs=1e-6)
    lateral = np.asarray(contacts[0]) - anneau.center - recul * anneau.axis
    assert float(np.linalg.norm(lateral)) == pytest.approx(0.0, abs=1e-9)


def test_une_electrode_sans_tetrodes_ne_donne_pas_d_anneau():
    contacts = _chaine((10.0, 0.0, 0.0), (1.0, 0.0, 0.0), 3.5, 12)
    assert tetrode_ring("DIXI-D08-12AM", 3.5, contacts) is None


def test_les_entrees_impossibles_ne_levent_pas():
    """Un rendu ne doit jamais s'arreter sur une electrode mal formee."""
    bonne = _chaine((10.0, 0.0, 0.0), (1.0, 0.0, 0.0), 3.9, 9)
    assert tetrode_ring("DIXI-MM08-09A33D08", None, bonne) is None
    assert tetrode_ring("DIXI-MM08-09A33D08", 0.0, bonne) is None
    assert tetrode_ring("DIXI-MM08-09A33D08", float("nan"), bonne) is None
    assert tetrode_ring("DIXI-MM08-09A33D08", 3.9, []) is None
    assert tetrode_ring("DIXI-MM08-09A33D08", 3.9, [(0.0, 0.0, 0.0)]) is None
    assert tetrode_ring("DIXI-MM08-09A33D08", 3.9, [(0.0, 0.0), (1.0, 1.0)]) is None
    assert shaft_axis([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]) is None
    assert shaft_axis([(0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0)]) is None


def test_l_orifice_est_entre_les_macros_un_et_deux():
    """Et non ailleurs : DIXI place les tetrodes a l'extremite distale."""
    for ref, pas, _, _ in TABLEAU:
        depuis_la_pointe = exit_offset_from_first_contact_mm(pas) + 1.0
        assert 2.0 < depuis_la_pointe < pas, ref


def test_l_anneau_echantillonne_est_bien_un_cercle():
    """Chaque point a 1,4 mm du centre, et tous dans le plan perpendiculaire."""
    from neuxelec.utils.micro_tetrodes import ring_points

    direction = np.array([0.3, -0.5, 0.81])
    contacts = _chaine((-20.0, 14.0, 30.0), direction, 3.9, 9)
    anneau = tetrode_ring("DIXI-MM08-09A33D08", 3.9, contacts)
    pts = ring_points(anneau, n=64)

    assert pts.shape == (64, 3)
    rayons = np.linalg.norm(pts - anneau.center, axis=1)
    assert rayons == pytest.approx(np.full(64, 1.4), abs=1e-9)
    hors_plan = (pts - anneau.center) @ anneau.axis
    assert hors_plan == pytest.approx(np.zeros(64), abs=1e-9)


def test_un_axe_aligne_sur_un_axe_du_monde_ne_casse_pas_la_base():
    """Le produit vectoriel s'effondre si le vecteur de depart est colineaire."""
    from neuxelec.utils.micro_tetrodes import perpendicular_basis

    for axe in (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])):
        u, v = perpendicular_basis(axe)
        assert np.linalg.norm(u) == pytest.approx(1.0)
        assert np.linalg.norm(v) == pytest.approx(1.0)
        assert float(u @ axe) == pytest.approx(0.0, abs=1e-12)
        assert float(v @ axe) == pytest.approx(0.0, abs=1e-12)
        assert float(u @ v) == pytest.approx(0.0, abs=1e-12)
