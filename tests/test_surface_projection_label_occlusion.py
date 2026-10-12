"""L'etiquette de la projection de surface doit passer derriere le cerveau.

Ces tests rendent pour de vrai, hors ecran, et comptent des pixels. C'est
le seul moyen de verifier une occlusion : le test de profondeur se joue
dans la carte graphique, pas dans un attribut qu'on pourrait interroger.

Les trois situations qui comptent :
  - la projection face a la camera, etiquette visible ;
  - le cerveau entre les deux, etiquette cachee ;
  - le cerveau retire, etiquette de nouveau visible, car plus rien ne
    l'occulte. C'est ce qui doit arriver quand on decoche l'hemisphere.
"""

from __future__ import annotations

import numpy as np
import pytest

pv = pytest.importorskip("pyvista")

#: Couleur de l'etiquette, choisie pour ne figurer ni dans le fond ni dans
#: la sphere qui tient lieu de cerveau.
ETIQUETTE = (1.0, 0.0, 1.0)
RAYON = 20.0


def _compter_magenta(image) -> int:
    a = np.asarray(image, dtype=int)
    return int(((a[..., 0] > 140) & (a[..., 1] < 110) & (a[..., 2] > 140)).sum())


def _rendre(avec_cerveau: bool, cote: float, always_visible: bool) -> int:
    """Rendre une etiquette posee a la surface, vue d'un cote ou de l'autre.

    ``cote`` vaut +1 quand la camera est du meme cote que l'etiquette, -1
    quand le cerveau se trouve entre les deux.
    """
    pl = pv.Plotter(off_screen=True, window_size=(320, 320))
    if avec_cerveau:
        pl.add_mesh(pv.Sphere(radius=RAYON, theta_resolution=60, phi_resolution=60),
                    color="lightgray")

    # L'etiquette est posee 2 mm au-dessus du pole x positif, comme le fait
    # la projection de surface : au-dessus de la surface, le long de sa
    # normale.
    pl.add_point_labels(
        np.asarray([[RAYON + 2.0, 0.0, 0.0]], dtype=np.float32),
        ["XX"],
        font_size=40,
        text_color=ETIQUETTE,
        shape_opacity=0.0,
        show_points=False,
        always_visible=always_visible,
    )
    pl.camera_position = [
        (cote * 120.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    ]
    image = pl.screenshot(return_img=True)
    pl.close()
    return _compter_magenta(image)


def test_l_etiquette_se_voit_quand_elle_fait_face_a_la_camera():
    assert _rendre(avec_cerveau=True, cote=+1.0, always_visible=False) > 0


def test_le_cerveau_cache_l_etiquette_quand_elle_passe_derriere():
    """Le defaut signale : l'etiquette se lisait a travers le cerveau."""
    assert _rendre(avec_cerveau=True, cote=-1.0, always_visible=False) == 0


def test_l_etiquette_revient_quand_le_cerveau_n_est_plus_affiche():
    """Decocher l'hemisphere ne doit pas faire disparaitre l'etiquette."""
    assert _rendre(avec_cerveau=False, cote=-1.0, always_visible=False) > 0


def test_l_ancien_reglage_laissait_bien_passer_l_etiquette():
    """Pour que le test dise quelque chose : avec always_visible, elle
    traversait. Si ce test tombait, c'est la scene qui serait en cause et
    non le reglage, et les trois tests ci-dessus ne prouveraient rien."""
    assert _rendre(avec_cerveau=True, cote=-1.0, always_visible=True) > 0


def test_la_projection_de_surface_utilise_bien_le_test_de_profondeur():
    """Et c'est bien ce reglage-la que la vue 3D emploie pour son etiquette."""
    import inspect

    from neuxelec.pages.view3d import View3DPage

    source = inspect.getsource(View3DPage)
    debut = source.index('name=f"surface_proj_label_')
    appel = source[max(0, debut - 600):debut]
    assert "always_visible=False" in appel
    assert "always_visible=True" not in appel.split("add_point_labels")[-1]
