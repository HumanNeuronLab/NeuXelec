"""Capture the 3D view right-click menu as a figure for the manual.

The menu is built by the application itself, with every option turned on, and
grabbed at twice the screen resolution so the entries stay legible once printed.
Writes ``resources/docs/figures/menu_3d.png``.

    python scripts/capture_menu_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ.setdefault("QT_SCALE_FACTOR", "2")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

OUTPUT = ROOT / "resources" / "docs" / "figures" / "menu_3d.png"
SECTIONS_OUTPUT = ROOT / "resources" / "docs" / "figures" / "menu_3d_sections.png"


def main() -> int:
    app = QApplication(sys.argv)
    from neuxelec.ui import context_menus
    from neuxelec.ui.context_menus import exec_3d_view_menu

    captured = {}

    class GrabbedMenu(QMenu):
        """A menu that paints itself into a pixmap instead of opening.

        Overriding ``exec`` on QMenu itself has no effect from Python, so the
        factory used by the application is redirected to this subclass.
        """

        def exec(self, *args, **kwargs):  # noqa: A003 (Qt naming)
            self.setAttribute(Qt.WA_DontShowOnScreen, True)
            self.show()
            app.processEvents()
            self.adjustSize()
            app.processEvents()
            captured["pixmap"] = self.grab()
            self.hide()
            return None

    base_menu = context_menus.make_base_menu

    def make_grabbed_menu():
        menu = base_menu()
        grabbed = GrabbedMenu(menu.parentWidget())
        grabbed.setMinimumWidth(menu.minimumWidth())
        grabbed.setSeparatorsCollapsible(False)
        grabbed.setStyleSheet(menu.styleSheet())
        return grabbed

    context_menus.make_base_menu = make_grabbed_menu
    exec_3d_view_menu(
        QPoint(0, 0),
        has_lh=True,
        has_rh=True,
        show_lh=True,
        show_rh=True,
        show_pial_options=True,
        show_color_scale_option=True,
        show_keep_electrodes_through_slices_option=True,
        show_siscom_crop_option=True,
        show_slice_plane_frames_option=True,
        can_add_marker=True,
        has_hidden_markers=True,
        show_ictal_color=True,
        show_interictal_color=True,
        show_plan_option=True,
        show_cortex_only_option=True,
        show_fmri_color=True,
        show_fmri_surface=True,
        fmri_blob_on=True,
    )

    pixmap = captured.get("pixmap")
    if pixmap is None or pixmap.isNull():
        print("The menu could not be captured.")
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(OUTPUT))
    print(f"  {OUTPUT.name:28s} {pixmap.width()}x{pixmap.height()}")

    # With every option enabled the menu wraps into two columns. The guided
    # tour card is only 360 px wide, so it gets the left column alone:
    # MARKERS and OVERLAY COLORS, enough to show the labelled sections and
    # still readable once scaled down.
    column = pixmap.width() // 2
    pixmap.copy(0, 0, column, pixmap.height()).save(str(SECTIONS_OUTPUT))
    print(f"  {SECTIONS_OUTPUT.name:28s} {column}x{pixmap.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
