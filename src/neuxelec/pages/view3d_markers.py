# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Anatomical 3D markers for the 3D View page.

Isolates the user-created 3D spherical markers and the marker-list dialog of
:class:`View3DPage` as a mixin. Methods are unchanged. ``View3DPage`` inherits
this mixin, so every ``self.*`` reference resolves exactly as before.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import numpy as np
import vtk
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QToolTip

from neuxelec.ui.marker_dialog import MarkerDialog
from neuxelec.ui.marker_list_dialog import MarkerListDialog
from neuxelec.ui.neuxelec_message_dialog import NeuXelecMessageDialog

try:
    import pyvista as pv

    _PV_OK = True
except Exception:
    pv = None
    _PV_OK = False

logger = logging.getLogger(__name__)


class View3DMarkersMixin:
    """Anatomical 3D markers + marker-list dialog for View3DPage."""

    def _current_marker_space(self) -> str:
        """
        Return the coordinate space currently displayed in 3D View.

        Values:
            "native" -> patient T1 / brain mask / pial surface
            "mni"    -> MNI atlas and MNI template slices
        """
        try:
            if self.chk_mni_atlas is not None and self.chk_mni_atlas.isChecked():
                return "mni"
        except Exception:
            pass

        return "native"

    def _all_markers(self) -> list[dict]:
        """
        Return the complete persistent marker list, including native and MNI
        markers.
        """
        markers = getattr(self.state, "markers", None)

        if not isinstance(markers, list):
            markers = []
            self.state.markers = markers

        # Compatibility with projects created before marker spaces existed.
        # Old markers are patient/native markers.
        for marker in markers:
            if isinstance(marker, dict) and not marker.get("space"):
                marker["space"] = "native"

        return markers

    def _markers(self) -> list[dict]:
        """
        Return only markers belonging to the currently displayed coordinate space.

        This function is also used by MarkerListDialog, so the list automatically
        adapts when switching between native and MNI modes.
        """
        active_space = self._current_marker_space()

        return [
            marker
            for marker in self._all_markers()
            if str(marker.get("space", "native")).lower() == active_space
        ]

    def _marker_by_id(self, marker_id: str) -> dict | None:
        marker_id = str(marker_id)

        for marker in self._markers():
            if str(marker.get("id", "")) == marker_id:
                return marker

        return None

    def _save_markers_to_project_json(self) -> None:
        """
        Save markers immediately in the project JSON when a project exists.
        """
        try:
            project_path = getattr(self.state, "project_path", None)

            if project_path:
                from neuxelec.project_io import save_project_json

                save_project_json(self.state, project_path)

        except Exception as e:
            print("[3D markers] Could not save markers to project JSON:", e)

    def _ras_to_t1_voxel(self, ras_xyz) -> list[float] | None:
        """
        Convert a displayed RAS coordinate in millimetres to continuous
        voxel coordinates in the current native T1 reference image.
        """
        img = self._get_3d_plane_reference_img()

        if img is None:
            return None

        try:
            ras = np.asarray(ras_xyz, dtype=np.float64).reshape(3)

            lps = ras.copy()
            lps[0] *= -1.0
            lps[1] *= -1.0

            idx = img.TransformPhysicalPointToContinuousIndex(tuple(float(v) for v in lps))

            return [float(idx[0]), float(idx[1]), float(idx[2])]

        except Exception:
            return None

    def _remove_all_anatomical_marker_actors(self) -> None:
        if self.plotter is None:
            return

        for actor in list(getattr(self, "_anatomical_marker_actors", {}).values()):
            try:
                self.plotter.remove_actor(actor, reset_camera=False)
            except Exception:
                pass

        self._anatomical_marker_actors.clear()

    def _render_anatomical_markers(self) -> None:
        """
        Render visible anatomical markers as colored 3D spheres.
        """
        if not _PV_OK or self.plotter is None:
            return

        self._remove_all_anatomical_marker_actors()

        for marker in self._markers():
            try:
                if not bool(marker.get("visible", True)):
                    continue

                marker_id = str(marker.get("id", "")).strip()

                if not marker_id:
                    marker_id = uuid4().hex
                    marker["id"] = marker_id

                ras = np.asarray(marker.get("ras", []), dtype=np.float32).reshape(3)
                color = str(marker.get("color", "#FF3B30"))
                size_mm = max(1.0, float(marker.get("size_mm", 4.0)))

                # Diameter chosen in the dialog; PyVista uses a radius.
                sphere = pv.Sphere(
                    radius=float(size_mm) / 2.0,
                    center=tuple(float(v) for v in ras),
                    theta_resolution=24,
                    phi_resolution=24,
                )

                actor = self.plotter.add_mesh(
                    sphere,
                    color=color,
                    opacity=1.0,
                    smooth_shading=True,
                    name=f"anatomical_marker_{marker_id}",
                )

                try:
                    actor.PickableOn()
                    actor.ForceOpaqueOn()
                except Exception:
                    pass

                self._anatomical_marker_actors[marker_id] = actor

            except Exception:
                continue

        try:
            self._render()
        except Exception:
            pass

    def _vtk_pick_actor_and_ras_from_qpos(self, qpos):
        """
        Return (picked_actor, ras_point) at a Qt position in the 3D view.
        """
        if self.interactor is None or self.plotter is None or qpos is None:
            return None, None

        try:
            x_qt = float(qpos.x())
            y_qt = float(qpos.y())

            x_vtk = int(round(x_qt))
            y_vtk = int(round(float(self.interactor.height()) - y_qt))

            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.002)

            if not picker.Pick(x_vtk, y_vtk, 0, self.plotter.renderer):
                return None, None

            actor = picker.GetActor()
            position = picker.GetPickPosition()

            if position is None or len(position) != 3:
                return actor, None

            ras = np.asarray(position, dtype=np.float64)

            if not np.all(np.isfinite(ras)):
                return actor, None

            return actor, ras

        except Exception:
            return None, None

    def _marker_id_from_actor(self, picked_actor) -> str | None:
        if picked_actor is None:
            return None

        for marker_id, actor in self._anatomical_marker_actors.items():
            try:
                if picked_actor is actor:
                    return str(marker_id)
            except Exception:
                pass

        return None

    def _pick_marker_id_from_qpos(self, qpos) -> str | None:
        actor, _ras = self._vtk_pick_actor_and_ras_from_qpos(qpos)
        return self._marker_id_from_actor(actor)

    def _pick_visible_slice_ras_from_qpos(self, qpos) -> np.ndarray | None:
        """
        Return the clicked RAS point only when the user clicked a displayed
        anatomical slice or one of its PET/SISCOM overlays.

        Markers are therefore created precisely from coronal, axial or
        sagittal image planes, not accidentally from the brain surface.
        """
        actor, ras = self._vtk_pick_actor_and_ras_from_qpos(qpos)

        if actor is None or ras is None:
            return None

        allowed_actors = {
            getattr(self, "_coronal_plane_actor", None),
            getattr(self, "_axial_plane_actor", None),
            getattr(self, "_sagittal_plane_actor", None),
            getattr(self, "_coronal_pet_actor", None),
            getattr(self, "_axial_pet_actor", None),
            getattr(self, "_sagittal_pet_actor", None),
            getattr(self, "_coronal_siscom_actor", None),
            getattr(self, "_axial_siscom_actor", None),
            getattr(self, "_sagittal_siscom_actor", None),
        }

        if actor not in allowed_actors:
            return None

        return ras

    def _connect_marker_list_auto_close_on_page_change(self) -> None:
        """
        Close the modeless Marker List window when leaving the 3D View page.
        """
        if bool(getattr(self, "_marker_list_page_close_connected", False)):
            return

        try:
            stacked = self.ui.findChild(QObject, "stackedWidget")

            if stacked is None:
                return

            stacked.currentChanged.connect(self._close_marker_list_if_not_3d_page)
            self._marker_list_page_close_connected = True

        except Exception:
            pass

    def _close_marker_list_if_not_3d_page(self, *_args) -> None:
        """
        The marker list is only valid while the user is on page3DView.
        """
        try:
            stacked = self.ui.findChild(QObject, "stackedWidget")

            if stacked is None:
                return

            current = stacked.currentWidget()

            if current is not None and str(current.objectName()) == "page3DView":
                return

            self._close_marker_list_dialog()

        except Exception:
            pass

    def _close_marker_list_dialog(self) -> None:
        try:
            dlg = getattr(self, "_marker_list_dialog", None)

            if dlg is not None:
                dlg.close()

        except Exception:
            pass

        self._marker_list_dialog = None

    def _refresh_marker_list_dialog(self) -> None:
        try:
            dlg = getattr(self, "_marker_list_dialog", None)

            if dlg is not None and hasattr(dlg, "refresh_markers"):
                dlg.refresh_markers()

        except Exception:
            pass

    def _open_marker_list_dialog(self) -> None:
        """
        Open a non-modal floating marker list.

        Important:
        - do not use exec()
        - the 3D View remains interactive
        - the window auto-closes when leaving page3DView
        """
        try:
            existing = getattr(self, "_marker_list_dialog", None)

            if existing is not None and existing.isVisible():
                existing.refresh_markers()
                existing.raise_()
                existing.activateWindow()
                return

            from ..utils.app_mode import is_edit_mode

            dlg = MarkerListDialog(
                markers_provider=self._markers,
                parent=self._dialog_parent(),
                editable=is_edit_mode(self.state),
            )

            dlg.setModal(False)
            dlg.setWindowModality(Qt.NonModal)

            dlg.showMarkerOnSlice.connect(self._show_marker_on_slice)
            dlg.editMarker.connect(self._edit_marker_from_marker_list)
            dlg.hideMarker.connect(self._hide_marker_from_marker_list)
            dlg.showMarker.connect(self._show_marker_from_marker_list)
            dlg.deleteMarker.connect(self._delete_marker_from_marker_list)
            dlg.exportAllMarkers.connect(self._export_all_markers)

            dlg.destroyed.connect(lambda *_: setattr(self, "_marker_list_dialog", None))

            self._marker_list_dialog = dlg

            dlg.show()
            dlg.raise_()
            dlg.activateWindow()

        except Exception as e:
            NeuXelecMessageDialog.warning(
                self._dialog_parent(),
                "Marker list",
                f"Could not open marker list:\n{e}",
            )

    def _edit_marker_from_marker_list(self, marker_id: str) -> None:
        self._edit_marker(marker_id)
        self._refresh_marker_list_dialog()

    def _hide_marker_from_marker_list(self, marker_id: str) -> None:
        self._hide_marker(marker_id)
        self._refresh_marker_list_dialog()

    def _show_marker_from_marker_list(self, marker_id: str) -> None:
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        marker["visible"] = True

        self._render_anatomical_markers()
        self._save_markers_to_project_json()
        self._refresh_marker_list_dialog()

    def _delete_marker_from_marker_list(self, marker_id: str) -> None:
        self._delete_marker(marker_id)
        self._refresh_marker_list_dialog()

    def _show_marker_on_slice(self, marker_id: str, plane_name: str) -> None:
        """
        Show only the requested anatomical slice at the marker position.

        Marker coordinates are stored in RAS millimetres.
        The slice planes use voxel indices:
            sagittal -> x
            coronal  -> y
            axial    -> z

        This intentionally follows the same exclusive-plane and slider-mapping
        logic as show_contact_in_slice().
        """
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        plane_name = str(plane_name).lower().strip()

        if plane_name not in ("coronal", "axial", "sagittal"):
            return

        try:
            ras = marker.get("ras", None)

            if ras is None:
                return

            # Always recompute the voxel position from the marker's RAS position.
            # This avoids using an old or rounded voxel_xyz value and guarantees
            # that the marker is located in the current T1 reference geometry.
            voxel = self._ras_to_t1_voxel(ras)

            if voxel is None or len(voxel) != 3:
                return

            x = int(round(float(voxel[0])))
            y = int(round(float(voxel[1])))
            z = int(round(float(voxel[2])))

            if plane_name == "coronal":
                target_idx = y
                slider = self.sld_coronal_plane

            elif plane_name == "axial":
                target_idx = z
                slider = self.sld_axial_plane

            else:
                target_idx = x
                slider = self.sld_sagittal_plane

            if slider is None:
                return

            # Same logic as contacts:
            # hide the two other planes and keep only the requested plane.
            self._show_only_requested_plane(plane_name)

            # Convert the real voxel index into the corresponding slider value.
            # This is necessary when the plane direction has been reversed with:
            # Start LH / Start Caudal / Start Inf.
            slider_value = self._slider_value_for_plane_index(
                plane_name,
                target_idx,
            )

            if slider_value is None:
                return

            slider_value = int(
                np.clip(
                    slider_value,
                    slider.minimum(),
                    slider.maximum(),
                )
            )

            slider.blockSignals(True)
            slider.setValue(slider_value)
            slider.blockSignals(False)

        except Exception as e:
            print(
                "[3D markers] Could not show marker on slice:",
                marker_id,
                plane_name,
                e,
            )
            return

        try:
            self._update_plane_slider_enabled_states()
        except Exception:
            pass

        try:
            self._refresh_single_plane_full(plane_name)
        except Exception:
            pass

        try:
            self._apply_actor_clipping()
        except Exception:
            pass

        try:
            self._update_planes_info_label()
        except Exception:
            pass

        try:
            self._render_anatomical_markers()
        except Exception:
            pass

        try:
            self._render()
        except Exception:
            pass


    # ------------------------------------------------------------------
    # Placing a marker: the cross follows the mouse, a click leaves it.
    #
    # The old way asked where the marker went by the point of the right
    # click that opened the menu, which meant aiming before knowing that
    # you were aiming. Now the menu arms the placement, the cursor becomes
    # a cross, and the left click settles the marker on the slice under
    # it. The window that asks for the name opens afterwards.
    #
    # A red cross used to be drawn in the scene as well, following the
    # mouse. It was dropped: redrawing the whole scene on every mouse
    # move made it trail behind the cursor, and two crosses one step
    # apart say less than one.
    # ------------------------------------------------------------------

    def marker_placement_active(self) -> bool:
        return bool(getattr(self, "_marker_placing", False))

    def _plane_of_actor(self, actor):
        """Which anatomical plane an actor belongs to, or None.

        The marker has to know the slice it was dropped on: a point in
        space says nothing about which image the user was reading.
        """
        for plane in ("coronal", "axial", "sagittal"):
            for suffix in ("plane", "pet", "siscom"):
                if actor is getattr(self, f"_{plane}_{suffix}_actor", None):
                    return plane

        return None

    def _slice_under_qpos(self, qpos):
        """``(plane, ras)`` under the cursor, or ``(None, None)``.

        Only the anatomical planes and their overlays count: a marker
        dropped on the brain surface would sit on no image at all.
        """
        actor, ras = self._vtk_pick_actor_and_ras_from_qpos(qpos)

        if actor is None or ras is None:
            return None, None

        plane = self._plane_of_actor(actor)

        return (plane, ras) if plane is not None else (None, None)

    def begin_marker_placement(self) -> None:
        """Arm the placement. The next left click leaves the marker."""
        if not _PV_OK or self.plotter is None:
            return

        self._marker_placing = True
        self._marker_moving_id = ""

        try:
            if self.interactor is not None:
                self.interactor.setCursor(Qt.CrossCursor)
        except Exception:
            pass

    def cancel_marker_placement(self) -> None:
        """Give up without leaving anything behind."""
        self._marker_placing = False
        self._marker_moving_id = ""

        try:
            if self.interactor is not None:
                self.interactor.unsetCursor()
        except Exception:
            pass

    def _finish_marker_placement(self, qpos) -> None:
        """Leave the cross where it is, then ask what it is.

        A click outside the slices is not a place: the placement stays
        armed rather than dropping a marker in mid-air.
        """
        plane, ras = self._slice_under_qpos(qpos)

        if plane is None or ras is None:
            return

        self._marker_placing = False

        try:
            if self.interactor is not None:
                self.interactor.unsetCursor()
        except Exception:
            pass

        moving = self.marker_being_moved()
        self._marker_moving_id = ""

        if moving:
            # Moving one does not ask its name again: it already has one.
            self._move_marker_to(moving, ras, plane)
            return

        self._create_marker_at_ras(ras, plane=plane)

    def begin_marker_move(self, marker_id: str) -> None:
        """Pick a marker back up and put it down somewhere else.

        The same gesture as placing one: the cross follows the slice, the
        click settles it. Dragging it directly would fight the camera,
        which turns on exactly the same button.
        """
        if not _PV_OK or self.plotter is None:
            return

        if self._marker_by_id(marker_id) is None:
            return

        self._marker_placing = True
        self._marker_moving_id = str(marker_id)

        try:
            if self.interactor is not None:
                self.interactor.setCursor(Qt.CrossCursor)
        except Exception:
            pass

    def marker_being_moved(self) -> str:
        return str(getattr(self, "_marker_moving_id", "") or "")

    def _move_marker_to(self, marker_id: str, ras, plane: str) -> None:
        """Put the marker down, keeping everything else it says."""
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        marker["ras"] = [float(v) for v in ras]
        marker["plane"] = str(plane)

        self._render_anatomical_markers()
        self._save_markers_to_project_json()
        self._refresh_marker_list_dialog()

    def _handle_marker_placement_event(self, event) -> bool:
        """The whole placement, while it is armed.

        The buttons are consumed, not the plain moves: a drag can only
        start from a press, and the press never reaches the camera. A
        move that changes nothing is left alone, so the view stays as
        responsive as ever while aiming.
        """
        if not self.marker_placement_active():
            return False

        try:
            kind = event.type()

            if kind == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self._finish_marker_placement(event.position())
                    return True

                if event.button() == Qt.RightButton:
                    self.cancel_marker_placement()
                    return True

                return True

            if kind in (QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
                return True

            if kind == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self.cancel_marker_placement()
                return True
        except Exception:
            self.cancel_marker_placement()

        return False

    def _create_marker_at_ras(self, ras_xyz, plane: str = "") -> None:
        """
        Open the marker dialog and create a new persistent 3D marker.
        """
        try:
            ras = np.asarray(ras_xyz, dtype=np.float64).reshape(3)
        except Exception:
            return

        initial_data = {
            "name": f"Marker {len(self._markers()) + 1}",
            "type": "Lesion",
            "color": "#FF3B30",
            "size_mm": 4.0,
            "description": "",
            "ras": [float(v) for v in ras],
            # The slice it was dropped on, so that a marker can be found
            # again on the image its author was reading.
            "plane": str(plane),
        }

        dlg = MarkerDialog(
            initial_data,
            ras_to_voxel=self._ras_to_t1_voxel,
            coordinate_space=self._current_marker_space(),
            parent=self._dialog_parent(),
        )

        if dlg.exec() != QDialog.Accepted:
            return

        marker = dlg.marker_data()
        marker["id"] = uuid4().hex
        marker["visible"] = True
        marker["space"] = self._current_marker_space()
        marker["plane"] = str(plane)

        self._all_markers().append(marker)

        self._render_anatomical_markers()
        self._save_markers_to_project_json()
        self._refresh_marker_list_dialog()

    def _edit_marker(self, marker_id: str) -> None:
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        dlg = MarkerDialog(
            marker,
            ras_to_voxel=self._ras_to_t1_voxel,
            coordinate_space=str(
                marker.get(
                    "space",
                    self._current_marker_space(),
                )
            ),
            parent=self._dialog_parent(),
        )

        if dlg.exec() != QDialog.Accepted:
            return

        updated = dlg.marker_data()

        # Preserve internal fields controlled outside the dialog.
        updated["id"] = marker.get("id", marker_id)
        updated["visible"] = bool(marker.get("visible", True))
        updated["space"] = str(
            marker.get(
                "space",
                self._current_marker_space(),
            )
        )

        marker.clear()
        marker.update(updated)

        self._render_anatomical_markers()
        self._save_markers_to_project_json()

    def _hide_marker(self, marker_id: str) -> None:
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        marker["visible"] = False
        self._render_anatomical_markers()
        self._save_markers_to_project_json()

    def _show_hidden_markers(self) -> None:
        changed = False

        for marker in self._markers():
            if not bool(marker.get("visible", True)):
                marker["visible"] = True
                changed = True

        if changed:
            self._render_anatomical_markers()
            self._save_markers_to_project_json()

    def _delete_marker(self, marker_id: str) -> None:
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        confirm_delete = NeuXelecMessageDialog.question(
            self._dialog_parent(),
            "Delete marker",
            f'Delete marker "{marker.get("name", "Marker")}"?',
            accept_text="Delete",
            reject_text="Cancel",
        )

        if not confirm_delete:
            return

        self.state.markers = [
            marker for marker in self._all_markers() if str(marker.get("id", "")) != str(marker_id)
        ]

        self._render_anatomical_markers()
        self._save_markers_to_project_json()
        self._refresh_marker_list_dialog()

    def _export_marker_text(self, marker_id: str) -> None:
        marker = self._marker_by_id(marker_id)

        if marker is None:
            return

        name = str(marker.get("name", "Marker")).strip() or "Marker"
        default_name = name.replace(" ", "_").replace("/", "_") + ".txt"

        path, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(),
            "Export marker",
            default_name,
            "Text files (*.txt)",
        )

        if not path:
            return

        if not path.lower().endswith(".txt"):
            path += ".txt"

        ras = marker.get("ras", [0.0, 0.0, 0.0])
        voxel = marker.get("voxel_xyz", None)

        marker_space = str(marker.get("space", "native")).lower()

        voxel_space_label = (
            "Voxel coordinates in MNI template:"
            if marker_space == "mni"
            else "Voxel coordinates in MRI 1:"
        )

        lines = [
            "NeuXelec marker information",
            "--------------------------",
            f"Name: {name}",
            f"Type: {marker.get('type', 'Lesion')}",
            f"Color: {marker.get('color', '#FF3B30')}",
            f"Marker size: {float(marker.get('size_mm', 4.0)):.1f} mm",
            "",
            "Description:",
            str(marker.get("description", "") or "None"),
            "",
            "RAS coordinates (mm):",
            f"X: {float(ras[0]):.2f}",
            f"Y: {float(ras[1]):.2f}",
            f"Z: {float(ras[2]):.2f}",
            "",
            voxel_space_label,
        ]

        if not isinstance(voxel, (list, tuple)) or len(voxel) != 3:
            lines.append("Unavailable")
        else:
            lines.extend(
                [
                    f"i: {float(voxel[0]):.2f}",
                    f"j: {float(voxel[1]):.2f}",
                    f"k: {float(voxel[2]):.2f}",
                ]
            )

        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _marker_report_lines(self, marker: dict) -> list[str]:
        """One marker, as the single export already prints it."""
        name = str(marker.get("name", "Marker")).strip() or "Marker"
        ras = marker.get("ras", [0.0, 0.0, 0.0])
        voxel = marker.get("voxel_xyz", None)
        space = str(marker.get("space", "native")).lower()

        lines = [
            f"Name: {name}",
            f"Type: {marker.get('type', 'Lesion')}",
            f"Color: {marker.get('color', '#FF3B30')}",
            f"Marker size: {float(marker.get('size_mm', 4.0)):.1f} mm",
        ]

        plane = str(marker.get("plane", "")).strip()

        if plane:
            lines.append(f"Dropped on the {plane} slice")

        lines += [
            "",
            "Description:",
            str(marker.get("description", "") or "None"),
            "",
            "RAS coordinates (mm):",
            f"X: {float(ras[0]):.2f}",
            f"Y: {float(ras[1]):.2f}",
            f"Z: {float(ras[2]):.2f}",
            "",
            "Voxel coordinates in MNI template:"
            if space == "mni"
            else "Voxel coordinates in MRI 1:",
        ]

        if not isinstance(voxel, (list, tuple)) or len(voxel) != 3:
            lines.append("Unavailable")
        else:
            lines += [
                f"i: {float(voxel[0]):.2f}",
                f"j: {float(voxel[1]):.2f}",
                f"k: {float(voxel[2]):.2f}",
            ]

        return lines

    def _export_all_markers(self) -> None:
        """Every marker of the list, in one file.

        The same text as the single export, one marker after another, so
        a file holding one marker and a file holding twenty read alike.
        """
        markers = self._markers()

        if not markers:
            NeuXelecMessageDialog.warning(
                self._dialog_parent(),
                "Export markers",
                "There is no marker in this list.",
            )
            return

        patient = str(getattr(self.state, "patient_id", "") or "")
        propose = f"{patient}_markers.txt" if patient else "markers.txt"

        path, _filter = QFileDialog.getSaveFileName(
            self._dialog_parent(),
            "Export every marker",
            propose,
            "Text files (*.txt)",
        )

        if not path:
            return

        if not path.lower().endswith(".txt"):
            path += ".txt"

        lines = [
            "NeuXelec marker list",
            "--------------------",
        ]

        if patient:
            lines.append(f"Patient: {patient}")

        lines += [f"{len(markers)} marker(s)", ""]

        for marker in markers:
            lines += self._marker_report_lines(marker)
            lines += ["", "-" * 40, ""]

        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
        except Exception as error:
            NeuXelecMessageDialog.critical(
                self._dialog_parent(),
                "Export every marker",
                f"Could not write the file: {error}",
            )
            return

        NeuXelecMessageDialog.information(
            self._dialog_parent(),
            "Export every marker",
            f"{len(markers)} marker(s) written to\n{path}",
        )

    def _handle_anatomical_marker_hover_event(self, obj, event) -> bool:
        """
        Display the marker name when hovering a visible anatomical marker.
        """
        try:
            if event.type() == QEvent.Leave:
                self._hovered_anatomical_marker_id = None
                QToolTip.hideText()
                return False

            if event.type() != QEvent.MouseMove:
                return False

            qpos = event.position().toPoint() if hasattr(event, "position") else event.pos()

            marker_id = self._pick_marker_id_from_qpos(qpos)

            if marker_id is None:
                self._hovered_anatomical_marker_id = None
                return False

            marker = self._marker_by_id(marker_id)

            if marker is None:
                return False

            self._hovered_anatomical_marker_id = marker_id

            name = str(marker.get("name", "Marker"))
            marker_type = str(marker.get("type", ""))
            text = name if not marker_type else f"{name}\nType: {marker_type}"

            global_pos = obj.mapToGlobal(qpos)
            QToolTip.showText(global_pos, text, self.interactor)

            return True

        except Exception:
            return False
