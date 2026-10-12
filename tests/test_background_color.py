"""The background colour of the two views, and what it must not break.

Both views can be painted in a colour of the user's choosing, so a screenshot
or an animation drops straight onto a coloured slide. Two things are easy to
get wrong and are pinned down here:

* in the slice view the black around the head is not a canvas, it is the air of
  the scan. Cutting it at a hard threshold leaves the skin/air transition
  standing as a dark halo against any colour that is not black, so the alpha
  follows the intensity instead - and only outside the head, otherwise the dark
  structures inside it turn into holes;
* in the 3D view two separate places set a background of their own, and the
  second of them used to overwrite whatever had been set before it.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from neuxelec.pages.oblique_slice_page import ObliqueSlicePage  # noqa: E402
from neuxelec.pages.view3d import View3DPage  # noqa: E402

AIR = ObliqueSlicePage.BACKGROUND_AIR_LEVEL
OPAQUE = ObliqueSlicePage.BACKGROUND_OPAQUE_LEVEL
MARGIN = ObliqueSlicePage.BACKGROUND_RAMP_MARGIN


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _pixmap(array):
    """An RGB array as a QPixmap, without going through a file."""
    height, width = array.shape[:2]
    rgba = np.dstack(
        [array[:, :, 2], array[:, :, 1], array[:, :, 0], np.full((height, width), 255, np.uint8)]
    )
    rgba = np.ascontiguousarray(rgba)
    return QPixmap.fromImage(QImage(rgba.data, width, height, width * 4, QImage.Format_ARGB32).copy())


def _alpha(pixmap):
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    width, height = image.width(), image.height()
    stride = image.bytesPerLine()
    raw = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * height)
    return raw.reshape(height, stride)[:, : width * 4].reshape(height, width, 4)[:, :, 3].copy()


def _head_on_air(size=60):
    """A bright disc of "head" on a field of air, with a soft rim."""
    y, x = np.mgrid[0:size, 0:size]
    radius = np.hypot(y - size / 2, x - size / 2)
    level = np.clip((size / 3 - radius) * 40, 0, 200).astype(np.uint8)
    return np.dstack([level] * 3)


def _page():
    return ObliqueSlicePage.__new__(ObliqueSlicePage)


# --------------------------------------------------------------- slice view
def test_the_air_around_the_head_becomes_invisible(qt_app):
    array = _head_on_air()
    alpha = _alpha(_page()._slice_background_alpha_pixmap(_pixmap(array)))
    corners = [alpha[0, 0], alpha[0, -1], alpha[-1, 0], alpha[-1, -1]]
    assert corners == [0, 0, 0, 0]


def test_the_head_itself_stays_opaque(qt_app):
    array = _head_on_air()
    alpha = _alpha(_page()._slice_background_alpha_pixmap(_pixmap(array)))
    assert alpha[array.max(axis=2) >= OPAQUE].min() == 255


def test_the_edge_is_a_ramp_and_not_a_step(qt_app):
    """A hard cut is what left a dark halo on a non-black background."""
    levels = np.linspace(AIR, OPAQUE, MARGIN + 1).astype(np.uint8)
    array = np.zeros((20, 40, 3), dtype=np.uint8)
    array[:, 10 : 10 + len(levels)] = levels[None, :, None]
    array[:, 10 + len(levels) :] = 200

    alpha = _alpha(_page()._slice_background_alpha_pixmap(_pixmap(array)))
    ramp = alpha[10, 10 : 10 + len(levels)]

    assert ramp[0] == 0 and ramp[-1] == 255
    assert all(b > a for a, b in zip(ramp, ramp[1:])), f"doit croitre: {ramp}"
    assert len(np.unique(ramp)) == len(levels)


def test_air_trapped_inside_the_head_stays_black(qt_app):
    """A sinus is anatomy, not background: it must not become a hole."""
    array = _head_on_air()
    array[28:32, 28:32] = 0  # a pocket of air in the middle of the head
    alpha = _alpha(_page()._slice_background_alpha_pixmap(_pixmap(array)))
    assert alpha[28:32, 28:32].min() == 255


def _head_with_a_cavity_open_to_the_outside(size=80):
    """A head with a dark cavity that reaches the outside, like a sinus.

    This is the shape that defeated following the air: the cavity connects to
    the exterior, so labelling the air and keeping what touches a border took
    the cavity for background and punched it out. On a real oblique slice the
    space around the brain reaches the outside through the skull base in
    exactly this way.
    """
    y, x = np.mgrid[0:size, 0:size]
    radius = np.hypot(y - size / 2, x - size / 2)
    level = np.clip((size / 3 - radius) * 40, 0, 200).astype(np.uint8)
    # A channel of air cut from the left edge into the middle of the head.
    level[size // 2 - 3 : size // 2 + 3, : size // 2] = 0
    return np.dstack([level] * 3)


def test_a_cavity_open_to_the_outside_is_not_punched_out(qt_app):
    """The cavity is anatomy, whatever it connects to."""
    array = _head_with_a_cavity_open_to_the_outside()
    alpha = _alpha(_page()._slice_background_alpha_pixmap(_pixmap(array)))

    size = array.shape[0]
    # The far end of the channel, well inside the head and far from any rim.
    interieur = alpha[size // 2, size // 2 - 4]
    assert interieur == 255, f"la cavite a ete percee: alpha={interieur}"
    # And the outside is still gone.
    assert alpha[0, 0] == 0


def test_remove_background_is_the_same_code_as_the_colour_path(qt_app):
    """There used to be two implementations; the weaker one walked every
    pixel in Python and cut on a plain threshold."""
    array = _head_with_a_cavity_open_to_the_outside()
    page = _page()
    page._slice_background_cache = None

    a = _alpha(page._remove_black_background_from_pixmap(_pixmap(array)))
    page._slice_background_cache = None
    b = _alpha(page._slice_background_alpha_pixmap(_pixmap(array)))
    assert np.array_equal(a, b)


# ----------------------------------------------------- GIF without background
class _ExportProbe(ObliqueSlicePage):
    """Watches whether the export gets past the guard."""

    def __init__(self, colour=None):
        self._slice_background = colour
        self._gif_export_active = False
        self.ui = None
        self.got_past = False
        self.warned = False

    def _slice_dialog_parent(self):
        return None

    def _warn_gif_cannot_be_transparent(self):
        self.warned = True
        return False

    def _get_checked_electrode_names(self):
        # First real call after the guard.
        self.got_past = True
        raise RuntimeError("far enough")


def _try_export(probe, remove_background):
    try:
        probe._export_oblique_slice_gif(1, "x.gif", remove_background=remove_background)
    except Exception:
        pass
    return probe


def test_a_gif_without_a_background_is_refused(qt_app):
    """The format cannot do it, so it is said rather than silently produced."""
    probe = _try_export(_ExportProbe(colour=None), remove_background=True)
    assert probe.warned
    assert not probe.got_past


def test_a_chosen_colour_lets_the_gif_through(qt_app):
    """The frame is already composited on it; nothing has to be cut."""
    probe = _try_export(_ExportProbe(colour="#FFFFFF"), remove_background=True)
    assert not probe.warned
    assert probe.got_past


def test_an_ordinary_gif_is_never_interrupted(qt_app):
    probe = _try_export(_ExportProbe(colour=None), remove_background=False)
    assert not probe.warned
    assert probe.got_past


# ------------------------------------------------------------- GIF flattening
def test_a_gif_frame_carries_no_alpha(qt_app):
    """A GIF has one transparent colour, not an alpha channel. Handing the
    encoder a soft ramp leaves it to invent a hard, jagged cut."""
    page = _page()
    page._slice_background = None
    frame = np.zeros((2, 1, 4), np.uint8)
    frame[0] = [200, 100, 50, 255]
    frame[1] = [200, 100, 50, 0]

    out = page._flatten_gif_frame(frame)
    assert out.shape[2] == 3
    assert tuple(out[0, 0]) == (200, 100, 50)
    assert tuple(out[1, 0]) == (0, 0, 0)


def test_a_gif_frame_lands_on_the_chosen_colour(qt_app):
    page = _page()
    page._slice_background = "#404040"
    frame = np.zeros((2, 1, 4), np.uint8)
    frame[0] = [200, 100, 50, 255]
    frame[1] = [200, 100, 50, 0]

    out = page._flatten_gif_frame(frame)
    assert tuple(out[0, 0]) == (200, 100, 50)
    assert tuple(out[1, 0]) == (64, 64, 64)


def test_a_half_transparent_pixel_is_mixed_not_cut(qt_app):
    page = _page()
    page._slice_background = "#FFFFFF"
    frame = np.array([[[0, 0, 0, 128]]], np.uint8)

    out = page._flatten_gif_frame(frame)
    # Halfway between black and white, give or take the rounding.
    assert 120 <= int(out[0, 0, 0]) <= 135


def test_a_null_pixmap_is_handed_back_untouched(qt_app):
    empty = QPixmap()
    assert _page()._slice_background_alpha_pixmap(empty) is empty


def test_the_alpha_is_computed_once_per_slice(qt_app):
    """It depends on the slice alone, but the frame repaints on every zoom.

    Recomputing it each time cost 116 ms per interaction on a 700 px slice, and
    244 ms on a 1024 px one - four frames a second while dragging.
    """
    page = _page()
    page._slice_background_cache = None
    appels = []
    reel = page._slice_background_alpha_pixmap

    def compte(pixmap):
        appels.append(pixmap)
        return reel(pixmap)

    page._slice_background_alpha_pixmap = compte

    pixmap = _pixmap(_head_on_air())
    for _ in range(5):
        page._slice_background_alpha(pixmap)
    assert len(appels) == 1, f"{len(appels)} calculs pour une meme coupe"

    # Une autre coupe doit bien etre recalculee.
    autre = _pixmap(_head_on_air(size=50))
    page._slice_background_alpha(autre)
    assert len(appels) == 2


def test_a_cached_result_is_the_same_picture(qt_app):
    page = _page()
    page._slice_background_cache = None
    pixmap = _pixmap(_head_on_air())
    premier = page._slice_background_alpha(pixmap)
    second = page._slice_background_alpha(pixmap)
    assert premier is second
    assert _alpha(second)[0, 0] == 0


# ------------------------------------------------------------------ 3D view
class _Plotter:
    def __init__(self):
        self.background = None

    def set_background(self, colour):
        self.background = str(colour)


def _view3d():
    page = View3DPage.__new__(View3DPage)
    page.plotter = _Plotter()
    page._view3d_background = None
    page._brain_render_params = {}
    page._render = lambda: None
    return page


def test_without_a_choice_the_scene_is_black():
    page = _view3d()
    page._apply_view3d_background()
    assert page.plotter.background == "black"


def test_a_chosen_colour_wins():
    page = _view3d()
    page._view3d_background = "#404040"
    page._apply_view3d_background()
    assert page.plotter.background == "#404040"


def test_relighting_does_not_undo_the_chosen_colour():
    """_setup_brain_render_lights used to set its own background outright."""
    page = _view3d()
    page._view3d_background = "#404040"
    page._apply_view3d_background()   # initial setup
    page._apply_view3d_background()   # brain-render lighting
    assert page.plotter.background == "#404040"


def test_the_brain_render_lighting_no_longer_imposes_its_grey():
    """It repainted the scene #2b2d31 behind the user's back; black is the default."""
    page = _view3d()
    page._apply_view3d_background()
    assert page.plotter.background == "black"
    assert View3DPage.VIEW3D_DEFAULT_BACKGROUND == "black"


def test_resetting_gives_black_back():
    page = _view3d()
    page._view3d_background = "#404040"
    page._apply_view3d_background()
    page._clear_view3d_background()
    assert page._view3d_background is None
    assert page.plotter.background == "black"


def test_no_plotter_is_not_a_crash():
    page = _view3d()
    page.plotter = None
    page._apply_view3d_background()  # must simply do nothing
