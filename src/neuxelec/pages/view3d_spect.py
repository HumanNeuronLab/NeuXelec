"""Ictal / inter-ictal SPECT overlays for the 3D View page.

This mixin adds two extra scalar overlays (ictal and inter-ictal SPECT) to the
native 3D slice planes, reusing exactly the same machinery as the PET overlay
(ratio-to-brain-median windowing, per-plane textured actors, brain-mask clipping
at display time only). It is completely additive: it never modifies the stored
or saved SPECT volumes, and if anything fails it degrades silently so the rest of
the 3D view keeps working.

The two SPECT volumes are read live from the shared state
(``ictal_spect_in_t1`` / ``interictal_spect_in_t1``), which already holds the
coregistered volumes in T1 space, so no image is ever masked or altered here.
"""
from __future__ import annotations

import numpy as np
import SimpleITK as sitk

try:
    import pyvista as pv

    _PV_OK = True
except Exception:  # pragma: no cover
    _PV_OK = False

from ..utils.pet_visualization import (
    blend_pet_on_rgba,
    compute_pet_reference,
    get_pet_ratio_window,
    get_pet_window,
    normalize_pet_slice,
    pet_norm_to_colormap,
    pick_free_colormap,
)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QCheckBox,
        QDoubleSpinBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QSlider,
        QSpinBox,
        QVBoxLayout,
    )

    _QT_OK = True
except Exception:  # pragma: no cover
    _QT_OK = False


SPECT_LAYERS = ("ictal", "interictal")
_SPECT_TITLE = {"ictal": "Ictal SPECT", "interictal": "Inter-ictal SPECT"}
# The 3D view consumes the coregistered-in-T1 volumes (same as PET, which uses
# pet_coreg_in_t1). We prefer the *_coreg_in_t1 attribute and fall back to the
# *_in_t1 alias for safety.
_SPECT_STATE_ATTR = {
    "ictal": ("ictal_spect_coreg_in_t1", "ictal_spect_in_t1"),
    "interictal": ("interictal_spect_coreg_in_t1", "interictal_spect_in_t1"),
}


class View3DSpectMixin:
    """Adds ictal / inter-ictal SPECT overlays to View3DPage."""

    # ------------------------------------------------------------------ setup
    def _spect_setup(self) -> None:
        """Initialize state, build the SPECT UI card and wire signals (once)."""
        if getattr(self, "_spect_ready", False):
            return
        self._spect_ready = True

        # Per-layer runtime state.
        self._spect_widgets: dict = {ly: {} for ly in SPECT_LAYERS}
        self._spect_cache: dict = {ly: None for ly in SPECT_LAYERS}
        self._spect_ref_key: dict = {ly: None for ly in SPECT_LAYERS}
        self._spect_ref_value: dict = {ly: None for ly in SPECT_LAYERS}
        self._spect_actors: dict = {
            ly: {"coronal": None, "axial": None, "sagittal": None}
            for ly in SPECT_LAYERS
        }
        self._spect_source_mesh: dict = {
            ly: {"coronal": None, "axial": None, "sagittal": None}
            for ly in SPECT_LAYERS
        }
        self._spect_scalar_bar_actor: dict = {ly: None for ly in SPECT_LAYERS}

        # Distinct default colormaps, avoiding those already used by SISCOM/PET.
        used = [
            getattr(self, "_siscom_colormap_name", "hot"),
            getattr(self, "_pet_colormap_name", "hot"),
        ]
        self._spect_colormap = {}
        for ly in SPECT_LAYERS:
            cmap = pick_free_colormap(used)
            self._spect_colormap[ly] = cmap
            used.append(cmap)

        try:
            self._spect_build_card()
        except Exception:
            pass
        try:
            self._spect_update_checkbox_availability()
        except Exception:
            pass

    def _spect_build_card(self) -> None:
        """Bind the SPECT card defined in the .ui (card3DSPECT, cloned from the
        3D PET card) and configure ranges / defaults / signals per layer."""
        if not _QT_OK:
            return
        for ly in SPECT_LAYERS:
            chk = self.ui.findChild(QCheckBox, f"chk_3d_showPET_{ly}")
            if chk is None:
                continue
            sld_min = self.ui.findChild(QSlider, f"sld_3d_petMin_{ly}")
            sb_min = self.ui.findChild(QSpinBox, f"sb_3d_petMin_{ly}")
            sld_max = self.ui.findChild(QSlider, f"sld_3d_petMax_{ly}")
            sb_max = self.ui.findChild(QSpinBox, f"sb_3d_petMax_{ly}")
            sld_gamma = self.ui.findChild(QSlider, f"sld_3d_petGamma_{ly}")
            sb_gamma = self.ui.findChild(QDoubleSpinBox, f"dsb_3d_petGamma_{ly}")
            sld_op = self.ui.findChild(QSlider, f"sld_3d_petOpacity_{ly}")

            # Ratio-to-brain-median windowing: min/max sliders run 0..300 (x100).
            for wdg in (sld_min, sb_min, sld_max, sb_max):
                if wdg is not None:
                    wdg.setRange(0, 300)
            for wdg, dv in ((sld_min, 40), (sb_min, 40), (sld_max, 160), (sb_max, 160)):
                if wdg is not None:
                    wdg.setValue(dv)
            if sld_gamma is not None:
                sld_gamma.setRange(10, 300)
                sld_gamma.setValue(100)
            if sb_gamma is not None:
                sb_gamma.setRange(0.1, 3.0)
                sb_gamma.setSingleStep(0.05)
                sb_gamma.setValue(1.0)
            if sld_op is not None:
                sld_op.setRange(0, 100)
                sld_op.setValue(55)

            self._spect_widgets[ly] = {
                "chk": chk,
                "min": sld_min,
                "max": sld_max,
                "gamma": sld_gamma,
                "opacity": sld_op,
                "sb_min": sb_min,
                "sb_max": sb_max,
                "sb_gamma": sb_gamma,
            }

            # Keep sliders and spin boxes in sync (not wired in the .ui).
            if sld_min is not None and sb_min is not None:
                sld_min.valueChanged.connect(sb_min.setValue)
                sb_min.valueChanged.connect(sld_min.setValue)
            if sld_max is not None and sb_max is not None:
                sld_max.valueChanged.connect(sb_max.setValue)
                sb_max.valueChanged.connect(sld_max.setValue)
            if sld_gamma is not None and sb_gamma is not None:
                sld_gamma.valueChanged.connect(lambda v, b=sb_gamma: b.setValue(v / 100.0))
                sb_gamma.valueChanged.connect(
                    lambda v, s=sld_gamma: s.setValue(int(round(v * 100)))
                )

            self._update_spect_controls_enabled(ly)
            chk.toggled.connect(lambda _c, l=ly: self._on_spect_toggled(l))
            for key in ("min", "max", "gamma"):
                w = self._spect_widgets[ly].get(key)
                if w is not None:
                    w.valueChanged.connect(lambda _v, l=ly: self._refresh_spect_layer(l))
            if sld_op is not None:
                sld_op.valueChanged.connect(
                    lambda _v, l=ly: self._update_spect_opacity_only(l)
                )

    # ------------------------------------------------------------- data access
    def _spect_layer_img(self, layer: str):
        state = getattr(self, "state", None)
        for attr in _SPECT_STATE_ATTR[layer]:
            img = getattr(state, attr, None)
            if img is not None:
                return img
        return None

    def _spect_is_on(self, layer: str) -> bool:
        w = self._spect_widgets.get(layer, {})
        chk = w.get("chk")
        return bool(chk is not None and chk.isChecked() and self._spect_layer_img(layer) is not None)

    def _spect_gamma(self, layer: str) -> float:
        w = self._spect_widgets.get(layer, {})
        s = w.get("gamma")
        try:
            return max(0.1, float(s.value()) / 100.0) if s is not None else 1.0
        except Exception:
            return 1.0

    def _spect_alpha(self, layer: str) -> float:
        w = self._spect_widgets.get(layer, {})
        s = w.get("opacity")
        try:
            return float(np.clip(float(s.value()) / 100.0, 0.0, 1.0)) if s is not None else 0.55
        except Exception:
            return 0.55

    def _spect_reference(self, layer: str):
        img = self._spect_layer_img(layer)
        if img is None:
            return None
        key = id(img)
        if self._spect_ref_key.get(layer) == key:
            return self._spect_ref_value.get(layer)
        ref = None
        try:
            arr = sitk.GetArrayFromImage(img).astype(np.float32)
            vals = None
            mask_img = getattr(getattr(self, "state", None), "brainmask_sitk", None)
            if mask_img is not None:
                try:
                    m = sitk.Resample(
                        mask_img, img, sitk.Transform(3, sitk.sitkIdentity),
                        sitk.sitkNearestNeighbor, 0.0, sitk.sitkUInt8,
                    )
                    m_np = sitk.GetArrayFromImage(m)
                    sel = (m_np > 0) & np.isfinite(arr) & (arr > 0)
                    if np.any(sel):
                        vals = arr[sel]
                except Exception:
                    vals = None
            if vals is None:
                vals = arr[np.isfinite(arr) & (arr > 0)]
            ref = compute_pet_reference(vals)
        except Exception:
            ref = None
        self._spect_ref_key[layer] = key
        self._spect_ref_value[layer] = ref
        return ref

    def _spect_window(self, layer: str, fallback_values=None):
        w = self._spect_widgets.get(layer, {})
        try:
            rmin = float(w["min"].value()) / 100.0
            rmax = float(w["max"].value()) / 100.0
        except Exception:
            rmin, rmax = 0.40, 1.60
        if rmax <= rmin:
            rmax = rmin + 0.01
        ref = self._spect_reference(layer)
        if ref is not None:
            lo, hi = get_pet_ratio_window(ref, rmin, rmax)
            return lo, hi
        return get_pet_window(fallback_values, 2.0, 98.0)

    # ----------------------------------------------------------------- caching
    def _build_slice_spect_rgba_cache(self, layer: str):
        if not self._spect_is_on(layer):
            return None
        ref_img = self._get_3d_plane_reference_img()
        img = self._spect_layer_img(layer)
        if ref_img is None or img is None:
            return None
        res = self._resample_image_for_slice_cache(
            img, ref_img, sitk.sitkLinear, 0.0, sitk.sitkFloat32
        )
        if res is None:
            return None
        try:
            arr = sitk.GetArrayFromImage(res).astype(np.float32)
        except Exception:
            return None
        mask_np = self._get_slice_cache_mask_np(ref_img)
        if mask_np is None:
            mask_np = np.ones(arr.shape, dtype=bool)
        valid = np.isfinite(arr) & (arr > 0) & mask_np
        vals = arr[valid]
        if vals.size == 0:
            return None
        lo, hi = self._spect_window(layer, vals)
        gamma = self._spect_gamma(layer)
        norm = normalize_pet_slice(arr, lo, hi, gamma=gamma, mask=mask_np.astype(np.uint8))
        rgb = pet_norm_to_colormap(norm, self._spect_colormap.get(layer, "hot"))
        rgba = np.zeros(arr.shape + (4,), dtype=np.uint8)
        rgba = blend_pet_on_rgba(rgba, rgb, norm, 1.0)
        return np.ascontiguousarray(rgba)

    def _get_or_build_spect_cache(self, layer: str):
        if self._spect_cache.get(layer) is None:
            self._spect_cache[layer] = self._build_slice_spect_rgba_cache(layer)
        return self._spect_cache.get(layer)

    def _spect_invalidate_caches(self) -> None:
        if not getattr(self, "_spect_ready", False):
            return
        for ly in SPECT_LAYERS:
            self._spect_cache[ly] = None

    # ---------------------------------------------------------------- rendering
    def _spect_plane_geometry(self, plane: str):
        if plane == "coronal":
            return self._build_coronal_plane_geometry()
        if plane == "axial":
            return self._build_axial_plane_geometry()
        if plane == "sagittal":
            return self._build_sagittal_plane_geometry()
        return None

    def _spect_plane_checkbox_on(self, plane: str) -> bool:
        chk = getattr(self, f"chk_{plane}_plane", None)
        return bool(chk is not None and chk.isChecked())

    def _spect_remove_plane_actor(self, layer: str, plane: str) -> None:
        """Remove a SPECT plane actor. The shared ``_remove_actor`` only knows
        the hard-coded PET/SISCOM actors, so SPECT actors are removed here by
        their stored reference and by name."""
        actor_name = f"{plane}_{layer}"
        actor = self._spect_actors.get(layer, {}).get(plane)
        try:
            if actor is not None and self.plotter is not None:
                self.plotter.remove_actor(actor, reset_camera=False)
        except Exception:
            pass
        try:
            if self.plotter is not None:
                self.plotter.remove_actor(actor_name, reset_camera=False)
        except Exception:
            pass
        self._spect_actors[layer][plane] = None

    def _render_plane_spect_overlay(self, layer: str, plane: str) -> None:
        actor_name = f"{plane}_{layer}"
        self._spect_remove_plane_actor(layer, plane)
        if not self._spect_plane_checkbox_on(plane) or not self._spect_is_on(layer):
            return
        geom = self._spect_plane_geometry(plane)
        if geom is None:
            return
        cache = self._get_or_build_spect_cache(layer)
        if cache is None:
            return
        rgba = self._extract_rgba_slice_from_volume_cache(cache, geom)
        if rgba is None:
            return
        actor_attr = f"_spect_actor_{layer}_{plane}"
        mesh_attr = f"_spect_mesh_{layer}_{plane}"
        self._render_textured_plane_actor(actor_attr, actor_name, mesh_attr, plane, geom, rgba)
        actor = getattr(self, actor_attr, None)
        self._spect_actors[layer][plane] = actor
        # Apply the per-layer opacity (the shared renderer only knows pet/siscom).
        try:
            if actor is not None:
                actor.GetProperty().SetOpacity(float(self._spect_alpha(layer)))
        except Exception:
            pass

    def _render_visible_spect_overlays_only(self) -> None:
        if not getattr(self, "_spect_ready", False):
            return
        for ly in SPECT_LAYERS:
            for plane in ("coronal", "axial", "sagittal"):
                try:
                    self._render_plane_spect_overlay(ly, plane)
                except Exception:
                    pass

    def _render_plane_spect_overlays(self, plane: str) -> None:
        """Render both SPECT layers for one plane. Safe to call from the slice
        plane refresh loop (no-op until the SPECT card is set up)."""
        if not getattr(self, "_spect_ready", False):
            return
        for ly in SPECT_LAYERS:
            try:
                self._render_plane_spect_overlay(ly, plane)
            except Exception:
                pass

    # ------------------------------------------------------------- refresh/slots
    def _refresh_spect_only(self) -> None:
        if not getattr(self, "_spect_ready", False):
            return
        self._spect_invalidate_caches()
        try:
            self._render_visible_spect_overlays_only()
        except Exception:
            pass
        try:
            self._update_spect_scalar_bars()
        except Exception:
            pass
        try:
            self._render()
        except Exception:
            pass

    # ------------------------------------------------------------- scalar bars
    def _spect_display_bounds(self, layer: str):
        """Ratio bounds shown on the color scale (slider value / 100)."""
        w = self._spect_widgets.get(layer, {})
        try:
            rmin = float(w["min"].value()) / 100.0
            rmax = float(w["max"].value()) / 100.0
        except Exception:
            rmin, rmax = 0.40, 1.60
        if rmax <= rmin:
            rmax = rmin + 0.01
        return rmin, rmax

    def _remove_spect_scalar_bar(self, layer: str) -> None:
        actor = self._spect_scalar_bar_actor.get(layer)
        name = f"spect_bar_{layer}"
        # Remove the invisible dummy mesh actor.
        try:
            if actor is not None and self.plotter is not None:
                self.plotter.remove_actor(actor, reset_camera=False)
        except Exception:
            pass
        try:
            if self.plotter is not None:
                self.plotter.remove_actor(name, reset_camera=False)
        except Exception:
            pass
        # PyVista scalar bars are keyed by their TITLE, so the bar itself must be
        # removed by title (its prefix), not by the mesh name.
        try:
            if self.plotter is not None:
                prefix = _SPECT_TITLE[layer]
                for key in list(getattr(self.plotter, "scalar_bars", {}).keys()):
                    if str(key).startswith(prefix):
                        try:
                            self.plotter.remove_scalar_bar(key)
                        except Exception:
                            pass
        except Exception:
            pass
        self._spect_scalar_bar_actor[layer] = None

    def _update_spect_scalar_bars(self) -> None:
        if not getattr(self, "_spect_ready", False) or not _PV_OK:
            return
        if self.plotter is None:
            return
        show_scales = bool(getattr(self, "_show_color_scales", True))
        # SPECT bars sit to the LEFT of PET (0.84) and SISCOM (0.91).
        slot_x = {"ictal": 0.70, "interictal": 0.77}
        y, w, h = 0.12, 0.055, 0.76
        for layer in SPECT_LAYERS:
            if not (show_scales and self._spect_is_on(layer)):
                self._remove_spect_scalar_bar(layer)
                continue
            self._remove_spect_scalar_bar(layer)
            try:
                rmin, rmax = self._spect_display_bounds(layer)
                gamma = self._spect_gamma(layer)
                cmap = self._spect_colormap.get(layer, "hot")
                title = f"{_SPECT_TITLE[layer]} / brain median (γ={gamma:.2f})"
                dummy = pv.PolyData(np.array([[0.0, 0.0, 0.0]], dtype=np.float32))
                dummy["v"] = np.array([rmin], dtype=np.float32)
                actor = self.plotter.add_mesh(
                    dummy,
                    scalars="v",
                    cmap=cmap,
                    clim=[float(rmin), float(rmax)],
                    opacity=0.0,
                    show_scalar_bar=True,
                    scalar_bar_args={
                        "title": title,
                        "vertical": True,
                        "position_x": slot_x[layer],
                        "position_y": y,
                        "width": w,
                        "height": h,
                        "fmt": "%.2f",
                        "title_font_size": 12,
                        "label_font_size": 10,
                        "color": "white",
                        "n_labels": 5,
                    },
                    name=f"spect_bar_{layer}",
                )
                self._spect_scalar_bar_actor[layer] = actor
            except Exception:
                self._spect_scalar_bar_actor[layer] = None

    def _refresh_spect_layer(self, layer: str) -> None:
        self._spect_cache[layer] = None
        self._spect_ref_key[layer] = None  # force ref recompute is not needed, ref is per-image
        self._refresh_spect_only()

    def _choose_spect_colormap(self, layer: str) -> None:
        """Right-click colormap chooser for a SPECT overlay (like PET/SISCOM)."""
        try:
            from ..ui.neuxelec_message_dialog import NeuXelecSelectionDialog
        except Exception:
            return
        # Same colormap set as PET / SISCOM, for consistency.
        options = ["hot", "inferno", "plasma", "jet", "turbo", "viridis", "gray"]
        current = self._spect_colormap.get(layer, "hot")
        current_index = options.index(current) if current in options else 0
        cmap = NeuXelecSelectionDialog.select_item(
            self._dialog_parent(),
            f"{_SPECT_TITLE[layer]} colormap",
            f"Choose the color scale used for the {_SPECT_TITLE[layer]} overlay:",
            options=options,
            current_index=current_index,
            accept_text="Apply",
            reject_text="Cancel",
        )
        if not cmap:
            return
        self._spect_colormap[layer] = str(cmap)
        self._remove_spect_scalar_bar(layer)
        self._refresh_spect_only()

    def _spect_layer_available(self, layer: str) -> bool:
        """A SPECT layer is usable in native mode only once its coregistration is
        validated and the coregistered volume exists."""
        state = getattr(self, "state", None)
        validated = bool(getattr(state, f"{layer}_spect_validated", False))
        return validated and (self._spect_layer_img(layer) is not None)

    def _spect_update_checkbox_availability(self) -> None:
        """Enable/disable the SPECT checkboxes like the other native overlays:
        disabled and unchecked in MNI mode, and in native mode enabled only when
        the coregistration has been validated."""
        if not getattr(self, "_spect_ready", False):
            return
        mni = False
        try:
            mni = bool(self._mni_mode_is_active())
        except Exception:
            mni = False
        for ly in SPECT_LAYERS:
            chk = self._spect_widgets.get(ly, {}).get("chk")
            if chk is None:
                continue
            available = (not mni) and self._spect_layer_available(ly)
            try:
                if available:
                    chk.setEnabled(True)
                else:
                    chk.blockSignals(True)
                    if chk.isChecked():
                        chk.setChecked(False)
                    chk.setEnabled(False)
                    chk.blockSignals(False)
                self._update_spect_controls_enabled(ly)
            except Exception:
                try:
                    chk.blockSignals(False)
                except Exception:
                    pass

    def _update_spect_controls_enabled(self, layer: str) -> None:
        """Grey out a layer's sliders/spin boxes when its checkbox is unchecked,
        exactly like the other modalities."""
        w = self._spect_widgets.get(layer, {})
        chk = w.get("chk")
        on = bool(chk is not None and chk.isChecked())
        for key in ("min", "max", "gamma", "opacity", "sb_min", "sb_max", "sb_gamma"):
            widget = w.get(key)
            if widget is not None:
                try:
                    widget.setEnabled(on)
                except Exception:
                    pass

    def _on_spect_toggled(self, layer: str) -> None:
        w = self._spect_widgets.get(layer, {})
        chk = w.get("chk")
        if chk is not None and chk.isChecked():
            # Match PET/SISCOM: enabling a layer re-enables the colour scales.
            self._show_color_scales = True
        self._update_spect_controls_enabled(layer)
        self._refresh_spect_only()

    def _update_spect_opacity_only(self, layer: str) -> None:
        if not getattr(self, "_spect_ready", False):
            return
        try:
            for plane in ("coronal", "axial", "sagittal"):
                actor = self._spect_actors[layer].get(plane)
                if actor is not None:
                    actor.GetProperty().SetOpacity(float(self._spect_alpha(layer)))
            self._render()
        except Exception:
            pass
