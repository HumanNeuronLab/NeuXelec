"""L'export vectoriel d'une coupe oblique.

CE QUI PEUT L'ETRE, ET CE QUI NE LE PEUT PAS

L'anatomie ne deviendra jamais du trace: ce sont des voxels, et aucun
format ne transforme une image en polygones. Les contacts, leurs noms,
le curseur et les barres de couleur, eux, sont des objets geometriques
que le PNG ecrasait en pixels.

Ces tests protegent donc la separation: dans le fichier produit, une
seule image, l'anatomie, et tout le reste en objets. Si quelqu'un
revenait a un rendu qui aplatit tout, le compte d'images passerait a
zero ou le compte de cercles tomberait, et le test le dirait.

POURQUOI LA VUE 3D N'EST PAS ICI

Mesure faite avant d'ecrire ce code: l'exportateur gl2ps de VTK rend la
scene en image, meme avec la rasterisation desactivee, sur une scene
simple comme sur une scene de 257 000 triangles. Un SVG de la vue 3D ne
contient qu'un PNG encode. Promettre du vectoriel la-bas serait mentir,
donc la vue 3D garde ses formats raster.
"""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFontDatabase, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Page:
    """Juste ce qu'il faut pour tracer une coupe et l'ecrire."""

    CONTACT_RADIUS_PX = 4

    _save_oblique_slice_vector = ObliqueSlicePage._save_oblique_slice_vector
    _paint_oblique_slice_onto = ObliqueSlicePage._paint_oblique_slice_onto
    _paint_scalar_bars_onto = ObliqueSlicePage._paint_scalar_bars_onto
    _scalar_bar_specs = ObliqueSlicePage._scalar_bar_specs
    _paint_vertical_scalar_bar = ObliqueSlicePage._paint_vertical_scalar_bar
    _crop_source_pixmap_for_zoom = ObliqueSlicePage._crop_source_pixmap_for_zoom
    _fit_source_rect_to_target = ObliqueSlicePage._fit_source_rect_to_target
    _draw_contacts_on_transformed_canvas = (
        ObliqueSlicePage._draw_contacts_on_transformed_canvas
    )
    _get_oblique_slice_background_removed = (
        ObliqueSlicePage._get_oblique_slice_background_removed
    )
    _get_oblique_slice_rotation = ObliqueSlicePage._get_oblique_slice_rotation

    def __init__(self, contacts=3, trace=True):
        self.image1 = QLabel()
        self.image1.resize(480, 360)
        self.image2 = None

        self._slice_background = None
        self._flip_lr_oblique = False
        self._zoom1 = 1.0
        self._pan1 = [0.0, 0.0]
        self._display_rotation1 = 0.0
        self._slice_background_removed1 = False
        self._show_color_scales = True
        self._last_canvas_args = {}

        if trace:
            source = QPixmap(200, 200)
            source.fill(QColor(40, 40, 48))
            self._last_canvas_args[1] = dict(
                pm_source=source,
                slot_index=1,
                zoom=1.0,
                pan_xy=[0.0, 0.0],
                contact_rows=[40.0 + 12 * i for i in range(contacts)],
                contact_cols=[100.0] * contacts,
                contact_names=[f"A{i + 1}" for i in range(contacts)],
                ring_rc=None,
                elec_name="A",
            )

    def _get_electrode_rgb(self, name):
        return (255, 72, 125)


def _ecrire(page, dossier, nom):
    chemin = str(dossier / nom)
    ok = page._save_oblique_slice_vector(1, chemin)
    return ok, chemin


def _compter(chemin):
    s = open(chemin, encoding="utf-8", errors="replace").read()
    return {
        "cercles": len(re.findall(r"<circle|<ellipse", s)),
        "images": len(re.findall(r"<image", s)),
        "textes": len(re.findall(r"<text", s)),
        "rectangles": len(re.findall(r"<rect|<path", s)),
    }


# ------------------------------------------------- l'anatomie reste une image


def test_une_seule_image_dans_le_svg(app, tmp_path):
    """Celle de l'anatomie. S'il y en avait zero, le fond aurait disparu;
    s'il y en avait plusieurs, le trace aurait ete aplati par morceaux."""
    page = _Page()
    ok, chemin = _ecrire(page, tmp_path, "coupe.svg")

    assert ok
    assert _compter(chemin)["images"] == 1


# ------------------------------------------------- les contacts sont des objets


def test_chaque_contact_est_un_cercle(app, tmp_path):
    page = _Page(contacts=5)
    ok, chemin = _ecrire(page, tmp_path, "coupe.svg")

    assert ok
    assert _compter(chemin)["cercles"] == 5


def test_les_noms_sortent_en_texte(app, tmp_path):
    """Donc modifiables dans un logiciel de dessin, et nets a l'impression."""
    if not QFontDatabase.families():
        pytest.skip("aucune police: le texte ne peut pas etre mesure ici")

    page = _Page(contacts=3)
    ok, chemin = _ecrire(page, tmp_path, "coupe.svg")

    assert ok
    assert _compter(chemin)["textes"] == 3


# ------------------------------------------------- la barre de couleur suit


def test_la_barre_de_couleur_est_tracee_et_non_pixelisee(app, tmp_path):
    """Le degrade et ses chiffres sont decrits, pas echantillonnes: le
    fichier ne gagne donc pas une seconde image."""
    page = _Page(contacts=1)
    page._pet_scalar_bar_spec = lambda: {
        "title": "PET",
        "lo": 0.5,
        "hi": 2.0,
        "cmap_name": "hot",
        "x_frac": 0.70,
    }

    ok, chemin = _ecrire(page, tmp_path, "coupe.svg")
    compte = _compter(chemin)

    assert ok
    assert compte["images"] == 1, "la barre a ete rendue en pixels"
    assert compte["rectangles"] >= 2, "le degrade et son cadre manquent"


# ------------------------------------------------- le PDF


def test_le_pdf_s_ecrit(app, tmp_path):
    page = _Page()
    ok, chemin = _ecrire(page, tmp_path, "coupe.pdf")

    assert ok
    assert os.path.getsize(chemin) > 1000
    assert open(chemin, "rb").read(5) == b"%PDF-"


# ------------------------------------------------- sans trace prealable


def test_sans_coupe_affichee_l_export_renonce(app, tmp_path):
    """Rien n'a encore ete dessine: mieux vaut rendre False et le dire que
    d'ecrire un fichier vide que l'utilisateur croira bon."""
    page = _Page(trace=False)
    chemin = str(tmp_path / "coupe.svg")

    assert page._save_oblique_slice_vector(1, chemin) is False
    assert not os.path.exists(chemin)
