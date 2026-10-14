# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Stimulation Result mode of the 3D view.

WHAT THE MODE IS FOR

A stimulation result is about a PAIR, and a brain full of electrodes in
their own colours is the worst possible background for reading one: the
coloured result competes with twenty coloured shafts.

So the mode draws its own background: every contact in light grey, with no
shaft between them, and the labels that were switched on in grey as well.
On top of that it draws the stimulations the filters let through, as a
coloured tube from one contact to the other. The grey says where the
electrodes are without competing with the one thing worth reading.

Nothing else is touched. Slice planes, overlays, the parcellation, the
pial surface and the camera all keep working, because the mode only
switches the visibility of the electrode actors.

LEAVING IT PUTS BACK WHAT WAS THERE

The visibility of every electrode actor is remembered on the way in and
restored on the way out, rather than recomputed: the user may have hidden
one electrode by hand before entering, and coming back to a view they did
not leave would be worse than not having the mode.

THE ELECTRODES ARE REBUILT BEHIND OUR BACK

Changing a slice, loading a file or editing a contact rebuilds the
electrode actors, and a rebuilt actor is visible. So the mode re-applies
itself at the end of every rebuild, which is why
``apply_stimulation_mode_visibility`` is called from the two places that
create those actors.
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QPushButton

from ..ui.neuxelec_message_dialog import NeuXelecMessageDialog
from ..utils import stimulation as st
from ..utils import stimulation_display as sd

logger = logging.getLogger(__name__)

try:
    import pyvista as pv

    _PV_OK = True
except Exception:  # pragma: no cover - PyVista missing is handled elsewhere
    pv = None
    _PV_OK = False

#: How many sides a tube has. Twenty reads as round and costs nothing.
TUBE_SIDES = 20

#: The badge the mode shows, so that a view missing its electrodes is never
#: mistaken for a view that lost them.
BADGE_TEXT = "STIMULATION RESULTS"

BADGE_STYLE = """
QLabel#stimulationBadge {
    background-color: #FFFFFF;
    color: #000000;
    border: none;
    border-radius: 6px;
    padding: 5px 12px 5px 12px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
}
"""

ESCAPE_STYLE = """
QPushButton#stimulationEscape {
    background-color: rgba(18, 19, 25, 190);
    color: #FFFFFF;
    border: 1px solid #FF487D;
    border-radius: 6px;
    padding: 5px 10px 5px 10px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#stimulationEscape:hover {
    background-color: #FF487D;
    color: #FFFFFF;
}
"""

#: La bordure est posee sur le conteneur de la vue, et la vue retrecie
#: d'autant. Un calque plein cadre par-dessus paraissait transparent dans
#: la feuille de style, mais au-dessus d'une fenetre OpenGL native un
#: widget qui recouvre ne laisse rien passer: il peignait un rectangle
#: opaque, et le cerveau disparaissait avec le reste de la scene.
FRAME_WIDTH_PX = 2
FRAME_COLOUR = "#FF487D"


class _StimulationChromeFilter(QObject):
    """Keep the badge and the frame on the viewport when it changes size."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, event):
        try:
            if event.type() in (QEvent.Resize, QEvent.Show, QEvent.Move):
                self.owner._update_stimulation_chrome_geometry()
        except Exception:
            pass

        return False


class View3DStimulationMixin:
    """Draw, filter and edit the stimulation results of the 3D view."""

    # ------------------------------------------------------------- the data

    def _stimulation_records(self) -> list[dict]:
        return list(getattr(self.state, "stimulations", []) or [])

    def _stimulation_filters(self) -> dict:
        filters = getattr(self, "_stim_filters", None)
        return filters if isinstance(filters, dict) else st.empty_filters()

    def stimulation_display_settings(self) -> dict:
        """The drawing settings of this patient, defaults included."""
        stored = getattr(self.state, "stimulation_display", None)
        settings = sd.default_settings()

        if isinstance(stored, dict):
            settings.update(stored)

        return settings

    def set_stimulation_display_settings(self, settings: dict) -> None:
        """Keep them on the state, where the project file will find them."""
        self.state.stimulation_display = dict(settings or {})
        self.refresh_stimulation_markers()

    def set_stimulation_filters(self, filters: dict) -> None:
        """Called by the filters tab, on every change."""
        self._stim_filters = dict(filters or {})
        self.refresh_stimulation_markers()

    def visible_stimulations(self) -> list[dict]:
        """The records the filters let through, in the order they were entered."""
        return st.filter_records(self._stimulation_records(), self._stimulation_filters())

    # ------------------------------------------------------- entering it

    def stimulation_mode_active(self) -> bool:
        return bool(getattr(self, "_stimulation_mode", False))

    def enter_stimulation_mode(self) -> None:
        """Hide the electrodes, mark the view, and open the results window."""
        if self.stimulation_mode_active():
            self._open_stimulation_results_dialog()
            return

        self._stimulation_mode = True
        self._remember_and_hide_native_electrodes()
        self._show_stimulation_chrome(True)
        self.refresh_stimulation_markers()
        self._open_stimulation_results_dialog()

    def leave_stimulation_mode(self) -> None:
        """Put the view back exactly as it was before entering."""
        if not self.stimulation_mode_active():
            return

        self._stimulation_mode = False
        self._close_stimulation_results_dialog()
        self._remove_stimulation_marker_actors()
        self._restore_native_electrodes()
        self._show_stimulation_chrome(False)
        self._render_safely()

    def toggle_stimulation_mode(self) -> None:
        if self.stimulation_mode_active():
            self.leave_stimulation_mode()
        else:
            self.enter_stimulation_mode()

    # --------------------------------------------- the native electrodes

    def _native_electrode_actors(self) -> list:
        """Every actor that draws an electrode in its own colour."""
        actors = []

        for registry in ("_elec_actors", "_elec_label_actors"):
            for actor in (getattr(self, registry, None) or {}).values():
                if actor is not None:
                    actors.append(actor)

        return actors

    def _remember_and_hide_native_electrodes(self) -> None:
        """Remember what was visible, because it is not always everything."""
        remembered = {}

        for actor in self._native_electrode_actors():
            try:
                remembered[id(actor)] = bool(actor.GetVisibility())
                actor.SetVisibility(False)
            except Exception:
                continue

        self._stim_hidden_electrodes = remembered

    def _restore_native_electrodes(self) -> None:
        remembered = getattr(self, "_stim_hidden_electrodes", None) or {}

        for actor in self._native_electrode_actors():
            try:
                actor.SetVisibility(bool(remembered.get(id(actor), True)))
            except Exception:
                continue

        self._stim_hidden_electrodes = {}

    def apply_stimulation_mode_visibility(self) -> None:
        """Re-hide electrodes that a rebuild has just put back on screen.

        Called at the end of the two places that create electrode actors. A
        rebuilt actor is a new object, so it is not in the remembered map
        and simply counts as visible when the mode ends.
        """
        if not self.stimulation_mode_active():
            return

        for actor in self._native_electrode_actors():
            try:
                actor.SetVisibility(False)
            except Exception:
                continue

    # ------------------------------------------------------- the chrome

    def _build_stimulation_chrome(self) -> None:
        """The rose frame, the badge and the way out, over the viewport."""
        if self.container_3d is None:
            return

        if getattr(self, "_stim_badge", None) is not None:
            return

        self._stim_badge = QLabel(BADGE_TEXT, self.container_3d)
        self._stim_badge.setObjectName("stimulationBadge")
        self._stim_badge.setStyleSheet(BADGE_STYLE)
        self._stim_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._stim_badge.setVisible(False)

        self._stim_escape = QPushButton("Esc", self.container_3d)
        self._stim_escape.setObjectName("stimulationEscape")
        self._stim_escape.setStyleSheet(ESCAPE_STYLE)
        self._stim_escape.setCursor(Qt.PointingHandCursor)
        self._stim_escape.setToolTip("Leave the stimulation mode")
        self._stim_escape.clicked.connect(self.leave_stimulation_mode)
        self._stim_escape.setVisible(False)

        try:
            if self._stim_chrome_filter is None:
                self._stim_chrome_filter = _StimulationChromeFilter(self)

            self.container_3d.installEventFilter(self._stim_chrome_filter)

            if self.interactor is not None:
                self.interactor.installEventFilter(self._stim_chrome_filter)
        except Exception:
            pass

    def _set_viewport_border(self, on: bool) -> None:
        """Put the rose border on the viewport itself, not over it.

        The view shrinks by the width of the border instead of being
        covered by it: nothing is drawn on top of the scene, so nothing
        can hide it.
        """
        if self.container_3d is None:
            return

        try:
            if getattr(self, "_stim_container_style", None) is None:
                self._stim_container_style = str(self.container_3d.styleSheet())
                self._stim_container_margins = None

            if on:
                if self._stim_container_margins is None and self._layout_3d is not None:
                    margins = self._layout_3d.contentsMargins()
                    self._stim_container_margins = (
                        margins.left(),
                        margins.top(),
                        margins.right(),
                        margins.bottom(),
                    )

                name = self.container_3d.objectName() or "frame_17"
                border = (
                    f"QWidget#{name} {{ border: {FRAME_WIDTH_PX}px solid "
                    f"{FRAME_COLOUR}; border-radius: 4px; }}"
                )
                self.container_3d.setStyleSheet(
                    self._stim_container_style + "\n" + border
                )

                if self._layout_3d is not None:
                    self._layout_3d.setContentsMargins(
                        FRAME_WIDTH_PX, FRAME_WIDTH_PX, FRAME_WIDTH_PX, FRAME_WIDTH_PX
                    )
            else:
                self.container_3d.setStyleSheet(self._stim_container_style)

                if self._layout_3d is not None and self._stim_container_margins:
                    self._layout_3d.setContentsMargins(*self._stim_container_margins)
                elif self._layout_3d is not None:
                    self._layout_3d.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass

    def _show_stimulation_chrome(self, on: bool) -> None:
        self._build_stimulation_chrome()
        self._set_viewport_border(on)

        for name in ("_stim_badge", "_stim_escape"):
            widget = getattr(self, name, None)

            if widget is None:
                continue

            widget.setVisible(bool(on))

            if on:
                widget.raise_()

        if on:
            self._update_stimulation_chrome_geometry()
            # The viewport is not always at its final size on the first
            # paint, and a badge in the wrong corner looks broken.
            QTimer.singleShot(0, self._update_stimulation_chrome_geometry)
            QTimer.singleShot(80, self._update_stimulation_chrome_geometry)

    def _update_stimulation_chrome_geometry(self) -> None:
        if self.container_3d is None or not self.stimulation_mode_active():
            return

        try:
            width = int(self.container_3d.width())

            margin = 12
            escape = getattr(self, "_stim_escape", None)
            badge = getattr(self, "_stim_badge", None)

            if escape is not None:
                escape.adjustSize()
                escape.move(width - escape.width() - margin, margin)
                escape.raise_()

            if badge is not None:
                badge.adjustSize()
                right = width - margin

                if escape is not None:
                    right -= escape.width() + 8

                badge.move(right - badge.width(), margin)
                badge.raise_()
        except Exception:
            pass

    # ------------------------------------------------------------- drawing

    def _remove_stimulation_marker_actors(self) -> None:
        if self.plotter is None:
            return

        actors = getattr(self, "_stim_marker_actors", None)

        if not isinstance(actors, dict):
            self._stim_marker_actors = {}
            return

        for actor in list(actors.values()):
            try:
                self.plotter.remove_actor(actor, reset_camera=False)
            except Exception:
                pass

        actors.clear()

    def refresh_stimulation_markers(self) -> None:
        """Redraw every stimulation the filters let through."""
        if not _PV_OK or self.plotter is None:
            return

        self._remove_stimulation_marker_actors()

        if not isinstance(getattr(self, "_stim_marker_actors", None), dict):
            self._stim_marker_actors = {}

        # Outside the mode there is nothing to draw: the electrodes are
        # back in their own colours and a tube among them says nothing.
        if not self.stimulation_mode_active():
            self._render_safely()
            self._refresh_stimulation_dialog()
            return

        # The patient's own stimulations have no place on an MNI template.
        if self._stimulation_markers_are_out_of_place():
            self._render_safely()
            self._refresh_stimulation_dialog()
            return

        electrodes = list(getattr(self.state, "electrodes", []) or [])
        settings = self.stimulation_display_settings()

        visible = self.visible_stimulations()

        # Sans filtre, toute l'implantation en gris. Des qu'on filtre, on
        # ne garde que les contacts des stimulations retenues: c'est ce
        # que filtrer veut dire.
        limite = (
            st.contacts_of(visible)
            if st.filters_are_active(self._stimulation_filters())
            else None
        )

        self._draw_grey_electrodes(electrodes, settings, limit_to=limite)

        for record in visible:
            try:
                self._draw_one_stimulation(record, electrodes, settings)
            except Exception:
                continue

        self._render_safely()
        self._refresh_stimulation_dialog()

    def _draw_grey_electrodes(
        self, electrodes: list[dict], settings: dict, limit_to=None
    ) -> None:
        """Every contact in light grey, with its label if it was switched on.

        This is the background of the mode, and the reason the coloured
        results read at all. No shaft is drawn: a line between contacts
        would compete with the tube that carries the result.

        A contact the user had hidden before entering stays hidden. The
        mode is a way of looking at the implantation, not a way of undoing
        what was asked for.

        ``limit_to`` is the set of contacts to keep, when a filter is set.
        Without a filter it is None and the whole implantation is drawn:
        the grey is the map one reads the results on.

        One actor for every contact and one for every label, rather than
        one per contact: an implantation is two hundred contacts.
        """
        grey = sd.grey_colour(settings)
        radius = max(0.1, float(settings.get("contact_radius_mm", 1.2)))

        points: list[list[float]] = []
        label_points: list[list[float]] = []
        label_texts: list[str] = []

        for elec_id, electrode in enumerate(electrodes):
            if not bool(electrode.get("visible", True)):
                continue

            contacts = electrode.get("contacts_lps") or []
            name = str(electrode.get("name", "E"))
            shown = electrode.get("contacts_visible")

            if not isinstance(shown, (list, tuple)) or len(shown) != len(contacts):
                shown = [True] * len(contacts)

            try:
                labels_on = self._get_local_contact_labels_visible(elec_id, len(contacts))
            except Exception:
                labels_on = [False] * len(contacts)

            first_visible = None

            for index, contact in enumerate(contacts):
                if not bool(shown[index]):
                    continue

                if limit_to is not None and (name, index) not in limit_to:
                    continue

                try:
                    ras = [
                        -float(contact[0]),
                        -float(contact[1]),
                        float(contact[2]),
                    ]
                except Exception:
                    continue

                if not all(np.isfinite(v) for v in ras):
                    continue

                points.append(ras)

                if first_visible is None:
                    first_visible = ras

                if index < len(labels_on) and bool(labels_on[index]):
                    label_points.append([ras[0] + 2.0, ras[1], ras[2] + 2.0])
                    label_texts.append(f"{name}{index + 1}")

            if first_visible is not None and self._electrode_label_is_on(elec_id):
                label_points.append(
                    [first_visible[0] - 3.0, first_visible[1], first_visible[2] - 3.0]
                )
                label_texts.append(name)

        if points:
            spheres = pv.PolyData(np.asarray(points, dtype=np.float32)).glyph(
                geom=pv.Sphere(radius=radius, theta_resolution=14, phi_resolution=14),
                scale=False,
                orient=False,
            )
            self._add_stimulation_actor(
                "stimulation_grey_contacts",
                spheres,
                grey,
                {"opacity": 1.0},
            )

        if label_texts:
            try:
                actor = self.plotter.add_point_labels(
                    np.asarray(label_points, dtype=np.float32),
                    label_texts,
                    font_size=12,
                    text_color=grey,
                    shape_opacity=0.0,
                    show_points=False,
                    always_visible=True,
                    name="stimulation_grey_labels",
                )
                self._stim_marker_actors["stimulation_grey_labels"] = actor
            except Exception:
                pass

    def _electrode_label_is_on(self, elec_id: int) -> bool:
        try:
            return bool(self.is_electrode_label_visible(elec_id))
        except Exception:
            return False

    def _draw_one_stimulation(
        self, record: dict, electrodes: list[dict], settings: dict
    ) -> None:
        ends = self._pair_ends_ras(record, electrodes)

        if ends is None:
            return

        first, second = ends
        style = sd.style_for(record, settings)
        record_id = str(record.get("id", "")) or st.pair_label(record)
        where = str(style.get("where") or sd.WHERE_LINE)

        # A monopolar stimulation has one end: there is no tube to draw.
        if second is None:
            self._add_stimulation_sphere(
                f"{record_id}-a", first, style["colour"], style, settings
            )
            return

        if where in (sd.WHERE_LINE, sd.WHERE_BOTH):
            self._add_stimulation_tube(record_id, first, second, style, settings)

        # The contacts are already drawn in grey, under everything: only
        # paint over them when the colour is meant to sit on the contacts.
        if where in (sd.WHERE_CONTACTS, sd.WHERE_BOTH):
            for suffix, point in (("a", first), ("b", second)):
                self._add_stimulation_sphere(
                    f"{record_id}-{suffix}", point, style["colour"], style, settings
                )

    def _add_stimulation_tube(
        self, record_id: str, first, second, style: dict, settings: dict
    ) -> None:
        radius = max(0.1, float(style.get("line_width_mm", 1.4)) / 2.0)

        tube = pv.Tube(
            pointa=tuple(float(v) for v in first),
            pointb=tuple(float(v) for v in second),
            radius=radius,
            n_sides=TUBE_SIDES,
        )

        self._add_stimulation_actor(f"stimulation_{record_id}_tube", tube, style["colour"], style)

    def _add_stimulation_sphere(
        self, key: str, point, colour: str, style: dict, settings: dict
    ) -> None:
        sphere = pv.Sphere(
            radius=max(0.1, float(style.get("contact_radius_mm", 1.2))),
            center=tuple(float(v) for v in point),
            theta_resolution=18,
            phi_resolution=18,
        )

        self._add_stimulation_actor(f"stimulation_{key}", sphere, colour, style)

    def _add_stimulation_actor(self, name: str, mesh, colour: str, style: dict) -> None:
        opacity = float(style.get("opacity", 1.0))

        actor = self.plotter.add_mesh(
            mesh,
            color=colour,
            opacity=opacity,
            smooth_shading=True,
            name=name,
        )

        try:
            if opacity >= 1.0:
                actor.ForceOpaqueOn()
        except Exception:
            pass

        self._stim_marker_actors[name] = actor

    def _pair_ends_ras(self, record: dict, electrodes: list[dict]):
        """The two ends of the pair in scene coordinates, or None.

        The state keeps contacts in LPS; the scene is in RAS.
        """
        record = record or {}

        first = st._contact_lps(
            record.get("electrode", ""), record.get("contact"), electrodes
        )

        if first is None:
            return None

        monopolar = (
            str(record.get("polarity", "")) == "monopolar"
            or record.get("contact_b") is None
        )
        second = (
            None
            if monopolar
            else st._contact_lps(
                record.get("electrode_b", ""), record.get("contact_b"), electrodes
            )
        )

        def _ras(lps):
            point = (-float(lps[0]), -float(lps[1]), float(lps[2]))
            return point if all(np.isfinite(v) for v in point) else None

        first_ras = _ras(first)

        if first_ras is None:
            return None

        return first_ras, (_ras(second) if second is not None else None)

    def _stimulation_markers_are_out_of_place(self) -> bool:
        try:
            return bool(self._mni_t1_slices_are_visible())
        except Exception:
            return False

    def _render_safely(self) -> None:
        try:
            self._render()
        except Exception:
            pass

    def _refresh_stimulation_dialog(self) -> None:
        """Keep the open results window in step with the records."""
        dialog = getattr(self, "_stim_results_dialog", None)

        if dialog is None:
            return

        try:
            dialog.reload()
        except Exception:
            pass

    # ------------------------------------------------------------- the window

    def _open_stimulation_results_dialog(self) -> None:
        """Open the results window without freezing the scene.

        Not modal, and not through exec(): the whole point of the filters
        tab is to watch the scene change while the filters move, which a
        modal window makes impossible.
        """
        from ..ui.stimulation_results_dialog import StimulationResultsDialog

        try:
            existing = getattr(self, "_stim_results_dialog", None)

            if existing is not None and existing.isVisible():
                # Reduite, elle est toujours visible au sens de Qt: la
                # remonter sans la restaurer ne montrerait rien.
                if existing.isMinimized():
                    existing.showNormal()

                existing.raise_()
                existing.activateWindow()
                return

            dialog = StimulationResultsDialog(
                self.state,
                on_filters_changed=self.set_stimulation_filters,
                on_display_changed=self.set_stimulation_display_settings,
                anatomy_lookup=getattr(self, "contact_region_name", None),
                parent=self._dialog_parent(),
            )

            dialog.setModal(False)
            dialog.setWindowModality(Qt.NonModal)

            # Closing the window leaves the mode: the user asked for one
            # way in and one way out, not two states to keep track of.
            dialog.finished.connect(lambda *_a: self.leave_stimulation_mode())
            dialog.destroyed.connect(
                lambda *_a: setattr(self, "_stim_results_dialog", None)
            )

            self._stim_results_dialog = dialog
            self._connect_stimulation_dialog_auto_close()

            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        except Exception as error:
            NeuXelecMessageDialog.warning(
                self._dialog_parent(),
                "Stimulation results",
                f"Could not open the stimulation results: {error}",
            )

    def _close_stimulation_results_dialog(self) -> None:
        dialog = getattr(self, "_stim_results_dialog", None)

        if dialog is None:
            return

        self._stim_results_dialog = None

        try:
            dialog.close()
        except Exception:
            pass

    def _connect_stimulation_dialog_auto_close(self) -> None:
        if bool(getattr(self, "_stim_dialog_close_connected", False)):
            return

        try:
            stacked = self.ui.findChild(QObject, "stackedWidget")

            if stacked is None:
                return

            stacked.currentChanged.connect(self._leave_stimulation_mode_if_not_3d)
            self._stim_dialog_close_connected = True
        except Exception:
            pass

    def _leave_stimulation_mode_if_not_3d(self, *_args) -> None:
        """The mode belongs to the 3D page and dies with it."""
        try:
            stacked = self.ui.findChild(QObject, "stackedWidget")

            if stacked is None:
                return

            current = stacked.currentWidget()

            if current is not None and str(current.objectName()) == "page3DView":
                return

            self.leave_stimulation_mode()
        except Exception:
            pass
