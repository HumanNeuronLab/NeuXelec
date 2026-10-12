"""Les regions d'une parcellation, et les contacts qu'elles contiennent.

Ce qui doit tenir :

  - l'attribution d'un contact est celle de SEEG2parc, le cube 3x3x3
    pondere, et non le voxel sous le contact. Sinon le tableau des regions
    contredirait celui de la coupe oblique et l'export BIDS sur le meme
    contact ;
  - seules les etiquettes presentes dans le volume sont listees, une table
    FreeSurfer en comptant plus de mille pour quelques dizaines utilisees ;
  - la boite englobante est juste, puisque c'est elle qui decide du
    maillage trace en 3D.
"""

from __future__ import annotations

import numpy as np
import pytest
import SimpleITK as sitk

from neuxelec.utils.parcellation_regions import (
    build_regions,
    contact_region_labels,
    cropped_region_mask,
    lut_entry,
    mni_contact_points,
    native_contact_points,
    region_bounds,
)

#: Trois etiquettes, dont une absente de la table des couleurs.
LUT = {
    3: ("ctx-lh-superiortemporal", (140, 20, 20)),
    4: ("Left-Hippocampus", (220, 20, 100)),
    9: "nom-sans-couleur",
}


def _volume():
    """[z, y, x] : la region 3 en bas, la 4 en bloc, et un voxel isole.

    Le bloc fait 4 x 4 x 4. Plus petit, le cube pondere de SEEG2parc
    autour d'un contact central contiendrait surtout du fond et le contact
    ne tomberait dans aucune region : c'est la vraie regle, fixee a part
    par test_un_contact_noye_dans_le_fond_n_est_dans_aucune_region.
    """
    vol = np.zeros((10, 10, 10), dtype=np.int32)
    vol[0:5, :, :] = 3
    vol[6:10, 1:5, 5:9] = 4
    vol[9, 9, 9] = 8
    return vol


def _image(vol):
    """Une image dont la geometrie est l'identite, en millimetres."""
    img = sitk.GetImageFromArray(vol)
    img.SetSpacing((1.0, 1.0, 1.0))
    img.SetOrigin((0.0, 0.0, 0.0))
    return img


def _electrode(nom, points):
    return {"name": nom, "contacts_lps": points}


def _pts(*electrodes):
    """Les couples (nom, point) que les fonctions attendent desormais."""
    return native_contact_points(list(electrodes))


# ------------------------------------------------------------- nommage


def test_une_etiquette_absente_du_lut_garde_son_numero():
    """Elle existe dans le volume, donc elle a droit a une ligne."""
    assert lut_entry(LUT, 3) == ("ctx-lh-superiortemporal", (140, 20, 20))
    assert lut_entry(LUT, 9) == ("nom-sans-couleur", (255, 255, 255))
    assert lut_entry(LUT, 77) == ("label-77", (255, 255, 255))
    assert lut_entry({}, 5) == ("label-5", (255, 255, 255))


# -------------------------------------------------- attribution des contacts


def test_le_contact_va_dans_la_region_qui_domine_son_cube():
    vol = _volume()
    # Point physique (x, y, z) = (5, 5, 2) -> voxel [z=2, y=5, x=5], region 3.
    labels = contact_region_labels(_image(vol), vol, _pts(_electrode("TB", [(5.0, 5.0, 2.0)])))
    assert labels == {"TB1": 3}


def test_le_cube_pondere_l_emporte_sur_le_voxel_du_contact():
    """Le point qui compte : un contact pose sur un voxel isole revient a
    la region qui l'entoure, exactement comme dans la coupe oblique."""
    vol = _volume()
    vol[2, 5, 5] = 4          # un voxel 4 seul, noye dans la region 3
    assert int(vol[2, 5, 5]) == 4
    labels = contact_region_labels(_image(vol), vol, _pts(_electrode("TB", [(5.0, 5.0, 2.0)])))
    assert labels == {"TB1": 3}, "le voxel isole ne doit pas l'emporter"


def test_un_contact_hors_du_volume_n_est_dans_aucune_region():
    """Et non dans la region zero, qui n'existe pas."""
    vol = _volume()
    labels = contact_region_labels(_image(vol), vol, _pts(_electrode("X", [(99.0, 99.0, 99.0)])))
    assert labels == {}


def test_un_contact_noye_dans_le_fond_n_est_dans_aucune_region():
    """La regle de SEEG2parc, deja appliquee par la coupe oblique : le fond
    gagne le vote quand la region est plus petite que le cube pondere."""
    vol = _volume()
    assert int(vol[9, 9, 9]) == 8, "le voxel isole doit bien etre la"
    labels = contact_region_labels(_image(vol), vol, _pts(_electrode("Z", [(9.0, 9.0, 9.0)])))
    assert labels == {}


def test_les_contacts_sont_numerotes_depuis_un():
    vol = _volume()
    elec = _electrode("TB", [(5.0, 5.0, 2.0), (5.0, 5.0, 3.0)])
    assert sorted(contact_region_labels(_image(vol), vol, _pts(elec))) == ["TB1", "TB2"]


def test_une_electrode_mal_formee_ne_fait_pas_tomber_le_calcul():
    vol = _volume()
    bancales = [
        {"name": "A"},
        {"name": "B", "contacts_lps": [("x", "y", "z")]},
        {"name": "C", "contacts_lps": [(5.0, 5.0)]},
    ]
    assert contact_region_labels(_image(vol), vol, native_contact_points(bancales)) == {}


# ------------------------------------------------------------ le tableau


def test_seules_les_regions_presentes_sont_listees():
    """Le LUT en declare trois, dont une absente du volume ; le volume en
    contient trois, dont une absente du LUT."""
    vol = _volume()
    regions = build_regions(_image(vol), vol, LUT, [])
    assert [r.name for r in regions] == [
        "ctx-lh-superiortemporal",      # etiquette 3
        "label-8",                      # absente du LUT, gardee quand meme
        "Left-Hippocampus",             # etiquette 4
    ]
    assert all(r.label != 0 for r in regions)


def test_le_tri_est_alphabetique_et_insensible_a_la_casse():
    vol = _volume()
    noms = [r.name.lower() for r in build_regions(_image(vol), vol, LUT, [])]
    assert noms == sorted(noms)


def test_chaque_region_porte_ses_contacts():
    vol = _volume()
    electrodes = [
        _electrode("TB", [(5.0, 5.0, 2.0), (5.0, 5.0, 3.0)]),
        _electrode("HP", [(6.0, 2.0, 7.0)]),
    ]
    par_nom = {r.name: r for r in build_regions(_image(vol), vol, LUT, native_contact_points(electrodes))}
    assert par_nom["ctx-lh-superiortemporal"].contacts == ("TB1", "TB2")
    assert par_nom["Left-Hippocampus"].contacts == ("HP1",)
    assert par_nom["ctx-lh-superiortemporal"].has_contacts


def test_une_region_sans_contact_reste_dans_le_tableau():
    """Il la faut : on veut pouvoir tracer n'importe quelle region."""
    vol = _volume()
    regions = build_regions(_image(vol), vol, LUT, [])
    assert len(regions) == 3
    assert all(r.contacts == () for r in regions)
    assert not regions[0].has_contacts


def test_les_couleurs_de_l_atlas_sont_rendues():
    """Chaque region sera tracee dans sa couleur, pas dans une couleur unie."""
    vol = _volume()
    par_nom = {r.name: r for r in build_regions(_image(vol), vol, LUT, [])}
    assert par_nom["ctx-lh-superiortemporal"].color == (140, 20, 20)
    assert par_nom["Left-Hippocampus"].color == (220, 20, 100)


# ------------------------------------------------------ boite englobante


def test_la_boite_englobante_serre_la_region():
    vol = _volume()
    assert region_bounds(vol, 4, margin=0) == ((6, 10), (1, 5), (5, 9))


def test_la_marge_elargit_d_un_voxel_sans_sortir_du_volume():
    """Sans marge, marching cubes rendrait une surface ouverte."""
    vol = _volume()
    assert region_bounds(vol, 4, margin=1) == ((5, 10), (0, 6), (4, 10))

    # La region 3 touche le bord z = 0 : la marge ne doit pas le franchir.
    (z0, z1), _, _ = region_bounds(vol, 3, margin=1)
    assert z0 == 0
    assert z1 <= vol.shape[0]


def test_une_region_absente_n_a_pas_de_boite():
    assert region_bounds(_volume(), 77) is None
    assert cropped_region_mask(_volume(), 77) is None


def test_le_masque_decoupe_ne_contient_que_sa_region():
    vol = _volume()
    masque, coin = cropped_region_mask(vol, 4, margin=1)
    assert coin == (5, 0, 4)
    assert masque.shape == (5, 6, 6)
    assert int(masque.sum()) == int((vol == 4).sum())
    assert set(np.unique(masque)) <= {0, 1}


@pytest.mark.parametrize("label", [3, 4, 8])
def test_le_masque_decoupe_se_replace_dans_le_volume(label):
    """Le coin rendu doit permettre de retrouver exactement les memes voxels."""
    vol = _volume()
    masque, (z0, y0, x0) = cropped_region_mask(vol, label)
    plein = np.zeros_like(vol, dtype=np.uint8)
    plein[z0:z0 + masque.shape[0], y0:y0 + masque.shape[1], x0:x0 + masque.shape[2]] = masque
    assert np.array_equal(plein.astype(bool), vol == label)


def test_un_volume_absent_ne_fait_rien_lever():
    assert build_regions(None, None, LUT, []) == []
    assert contact_region_labels(None, None, []) == {}
    assert region_bounds(None, 3) is None


# --------------------------------------------------- les contacts MNI


def test_les_contacts_mni_passent_du_ras_au_lps():
    """Le piege : un electrodes.tsv donne du MNI RAS, une image SimpleITK
    se lit en LPS. Sans la conversion, chaque contact atterrit dans
    l'hemisphere oppose et une region en avant de la sienne."""
    jeux = [{"contacts": [{"name": "A1", "mni_ras": [30.0, -20.0, 12.0]}]}]
    assert mni_contact_points(jeux) == [("A1", (-30.0, 20.0, 12.0))]


def test_les_contacts_mni_gardent_leur_propre_nom():
    """Ils en portent un, contrairement aux contacts du patient qui le
    composent avec le rang."""
    jeux = [{"contacts": [
        {"name": "LH-amyg-3", "mni_ras": [1.0, 2.0, 3.0]},
        {"name": "", "mni_ras": [4.0, 5.0, 6.0]},
    ]}]
    assert [n for n, _ in mni_contact_points(jeux)] == ["LH-amyg-3"]


def test_un_jeu_mni_mal_forme_ne_fait_rien_lever():
    assert mni_contact_points(None) == []
    assert mni_contact_points([{}]) == []
    assert mni_contact_points([{"contacts": [{"name": "A"}]}]) == []
    assert mni_contact_points([{"contacts": [{"name": "A", "mni_ras": ["x", 1, 2]}]}]) == []


def test_les_deux_extracteurs_rendent_la_meme_forme():
    """build_regions ne doit pas pouvoir distinguer leur origine."""
    natifs = native_contact_points([_electrode("TB", [(1.0, 2.0, 3.0)])])
    mni = mni_contact_points([{"contacts": [{"name": "TB1", "mni_ras": [-1.0, -2.0, 3.0]}]}])
    assert natifs == mni
