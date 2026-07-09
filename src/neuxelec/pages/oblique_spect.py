"""Ictal / inter-ictal SPECT overlays for the Oblique Slice page.

Additive and isolated: it never touches the existing slice tuple, caches or
compositing signatures. It samples the ictal / inter-ictal volumes on the same
oblique plane (using the plane geometry already computed for the slice) and
blends them onto the already-composited RGB image, right after the PET overlay,
with the same ratio-to-brain-median windowing used elsewhere. No colour scale is
drawn (as agreed for the oblique view). If anything fails it degrades silently.
"""
from __future__ import annotations

import numpy as np
import SimpleITK as sitk
from scipy.ndimage import map_coordinates

from ..utils.pet_visualization import (
    blend_pet_on_rgb,
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
_SPECT_STATE_ATTR = {
    "ictal": ("ictal_spect_coreg_in_t1", "ictal_spect_in_t1"),
    "interictal": ("interictal_spect_coreg_in_t1", "interictal_spect_in_t1"),
}


class ObliqueSpectMixin:
    """Adds ictal / inter-ictal SPECT overlays to the Oblique Slice page."""

    # ------------------------------------------------------------------ setup
    def _oblique_spect_setup(self) -> None:
        if getattr(self, "_ospect_ready", False):
            return
        self._ospect_ready = True
        self._ospect_widgets = {ly: {} for ly in SPECT_LAYERS}
        self._ospect_ref_key = {ly: None for ly in SPECT_LAYERS}
        self._ospect_ref_value = {ly: None for ly in SPECT_LAYERS}
        used = [
            getattr(self, "_siscom_colormap_name", "hot"),
            getattr(self, "_pet_colormap_name", "hot"),
        ]
        self._ospect_colormap = {}
        for ly in SPECT_LAYERS:
            cmap = pick_free_colormap(used)
            self._ospect_colormap[ly] = cmap
            used.append(cmap)
        try:
            self._oblique_spect_build_card()
        except Exception:
            pass
        try:
            self._oblique_spect_update_availability()
        except Exception:
            pass

    def _oblique_spect_build_card(self) -> None:
        """Bind the SPECT card defined in the .ui (cardObliqueSPECT, cloned from
        the oblique PET card) and configure ranges / defaults / signals."""
        if not _QT_OK:
            return
        for ly in SPECT_LAYERS:
            chk = self.ui.findChild(QCheckBox, f"chk_obliqueSlice_PET_{ly}")
            if chk is None:
                continue
            sld_min = self.ui.findChild(QSlider, f"horizontalSlider_obliqueSlice_petMin_{ly}")
            sb_min = self.ui.findChild(QSpinBox, f"sb_obliqueSlice_petMin_{ly}")
            sld_max = self.ui.findChild(QSlider, f"horizontalSlider_obliqueSlice_petMax_{ly}")
            sb_max = self.ui.findChild(QSpinBox, f"sb_obliqueSlice_petMax_{ly}")
            sld_gamma = self.ui.findChild(QSlider, f"horizontalSlider_obliqueSlice_petGamma_{ly}")
            sb_gamma = self.ui.findChild(QDoubleSpinBox, f"dsb_obliqueSlice_petGamma_{ly}")
            sld_op = self.ui.findChild(QSlider, f"horizontalSlider_obliqueSlice_petOpacity_{ly}")
            sb_op = self.ui.findChild(QSpinBox, f"spinBox_obliqueSlice_petOpacity_{ly}")

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
            for wdg, dv in ((sld_op, 55), (sb_op, 55)):
                if wdg is not None:
                    wdg.setRange(0, 100)
                    wdg.setValue(dv)

            self._ospect_widgets[ly] = {
                "chk": chk,
                "min": sld_min,
                "max": sld_max,
                "gamma": sld_gamma,
                "opacity": sld_op,
                "sb_min": sb_min,
                "sb_max": sb_max,
                "sb_gamma": sb_gamma,
                "sb_opacity": sb_op,
            }

            # Keep sliders and spin boxes in sync (not wired in the .ui).
            for sl, sp in ((sld_min, sb_min), (sld_max, sb_max), (sld_op, sb_op)):
                if sl is not None and sp is not None:
                    sl.valueChanged.connect(sp.setValue)
                    sp.valueChanged.connect(sl.setValue)
            if sld_gamma is not None and sb_gamma is not None:
                sld_gamma.valueChanged.connect(lambda v, b=sb_gamma: b.setValue(v / 100.0))
                sb_gamma.valueChanged.connect(
                    lambda v, s=sld_gamma: s.setValue(int(round(v * 100)))
                )

            self._oblique_spect_update_enabled(ly)
            chk.toggled.connect(lambda _c, l=ly: self._on_oblique_spect_toggled(l))
            for key in ("min", "max", "gamma", "opacity"):
                w = self._ospect_widgets[ly].get(key)
                if w is not None:
                    w.valueChanged.connect(
                        lambda _v: self._schedule_refresh(slices=True, brain=False)
                    )

    def _oblique_spect_update_availability(self) -> None:
        """Enable a SPECT checkbox only when its coregistration is validated."""
        if not getattr(self, "_ospect_ready", False):
            return
        for ly in SPECT_LAYERS:
            chk = self._ospect_widgets.get(ly, {}).get("chk")
            if chk is None:
                continue
            validated = bool(getattr(self.state, f"{ly}_spect_validated", False))
            available = validated and (self._ospect_layer_img(ly) is not None)
            try:
                if available:
                    chk.setEnabled(True)
                else:
                    chk.blockSignals(True)
                    if chk.isChecked():
                        chk.setChecked(False)
                    chk.setEnabled(False)
                    chk.blockSignals(False)
                self._oblique_spect_update_enabled(ly)
            except Exception:
                try:
                    chk.blockSignals(False)
                except Exception:
                    pass

    def _oblique_spect_update_enabled(self, layer: str) -> None:
        w = self._ospect_widgets.get(layer, {})
        chk = w.get("chk")
        on = bool(chk is not None and chk.isChecked())
        for key in ("min", "max", "gamma", "opacity",
                    "sb_min", "sb_max", "sb_gamma", "sb_opacity"):
            widget = w.get(key)
            if widget is not None:
                try:
                    widget.setEnabled(on)
                except Exception:
                    pass

    def _on_oblique_spect_toggled(self, layer: str) -> None:
        self._oblique_spect_update_enabled(layer)
        self._schedule_refresh(slices=True, brain=False)

    def _choose_oblique_spect_colormap(self, layer: str) -> None:
        """Right-click colormap chooser for a SPECT overlay (same set as PET)."""
        try:
            from ..ui.neuxelec_message_dialog import NeuXelecSelectionDialog
        except Exception:
            return
        options = ["hot", "inferno", "plasma", "jet", "turbo", "viridis", "gray"]
        current = self._ospect_colormap.get(layer, "hot")
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
        self._ospect_colormap[layer] = str(cmap)
        self._schedule_refresh(slices=True, brain=False)

    # ------------------------------------------------------------- data access
    def _ospect_layer_img(self, layer: str):
        state = getattr(self, "state", None)
        for attr in _SPECT_STATE_ATTR[layer]:
            img = getattr(state, attr, None)
            if img is not None:
                return img
        return None

    def _ospect_is_on(self, layer: str) -> bool:
        w = self._ospect_widgets.get(layer, {})
        chk = w.get("chk")
        return bool(
            chk is not None and chk.isChecked() and self._ospect_layer_img(layer) is not None
        )

    def _ospect_gamma(self, layer: str) -> float:
        s = self._ospect_widgets.get(layer, {}).get("gamma")
        try:
            return max(0.1, float(s.value()) / 100.0) if s is not None else 1.0
        except Exception:
            return 1.0

    def _ospect_alpha(self, layer: str) -> float:
        s = self._ospect_widgets.get(layer, {}).get("opacity")
        try:
            return float(np.clip(float(s.value()) / 100.0, 0.0, 1.0)) if s is not None else 0.55
        except Exception:
            return 0.55

    def _ospect_reference(self, layer: str):
        img = self._ospect_layer_img(layer)
        if img is None:
            return None
        key = id(img)
        if self._ospect_ref_key.get(layer) == key:
            return self._ospect_ref_value.get(layer)
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
        self._ospect_ref_key[layer] = key
        self._ospect_ref_value[layer] = ref
        return ref

    def _ospect_window(self, layer: str, fallback_values=None):
        w = self._ospect_widgets.get(layer, {})
        try:
            rmin = float(w["min"].value()) / 100.0
            rmax = float(w["max"].value()) / 100.0
        except Exception:
            rmin, rmax = 0.40, 1.60
        if rmax <= rmin:
            rmax = rmin + 0.01
        ref = self._ospect_reference(layer)
        if ref is not None:
            return get_pet_ratio_window(ref, rmin, rmax)
        return get_pet_window(fallback_values, 2.0, 98.0)

    # -------------------------------------------------------------- sampling
    def _ospect_sample_on_plane(self, img, center, u, w_axis,
                                s_min, s_max, t_min, t_max, H, W):
        """Sample ``img`` on the oblique plane defined by the given geometry.
        Same math as the page's internal _sample_image, in physical LPS space."""
        try:
            s_vals = np.linspace(s_min, s_max, int(H), dtype=np.float64)
            t_vals = np.linspace(t_min, t_max, int(W), dtype=np.float64)
            S, T = np.meshgrid(s_vals, t_vals, indexing="ij")
            pts = (
                np.asarray(center, dtype=np.float64)[None, None, :]
                + S[..., None] * np.asarray(u, dtype=np.float64)[None, None, :]
                + T[..., None] * np.asarray(w_axis, dtype=np.float64)[None, None, :]
            )
            vol = sitk.GetArrayFromImage(img).astype(np.float32)  # z, y, x
            origin = np.asarray(img.GetOrigin(), dtype=np.float64)
            spacing = np.asarray(img.GetSpacing(), dtype=np.float64)
            direction = np.asarray(img.GetDirection(), dtype=np.float64).reshape(3, 3)
            inv_direction = np.linalg.inv(direction)

            pts_flat = pts.reshape(-1, 3)
            idx_xyz = ((pts_flat - origin[None, :]) @ inv_direction.T) / spacing[None, :]
            x = idx_xyz[:, 0]
            y = idx_xyz[:, 1]
            z = idx_xyz[:, 2]
            size = np.asarray(img.GetSize(), dtype=np.float64)
            inside = (
                (x >= -0.5) & (x <= size[0] - 0.5)
                & (y >= -0.5) & (y <= size[1] - 0.5)
                & (z >= -0.5) & (z <= size[2] - 0.5)
            )
            arr = np.full((int(H) * int(W),), np.nan, dtype=np.float32)
            if np.any(inside):
                coords = np.vstack([z[inside], y[inside], x[inside]])
                sampled = map_coordinates(vol, coords, order=1, mode="constant", cval=np.nan)
                arr[inside] = sampled.astype(np.float32)
            return arr.reshape(int(H), int(W))
        except Exception:
            return None

    # -------------------------------------------------------------- blending
    def _blend_spect_on_oblique_rgb(self, rgb, center, u, w_axis,
                                    s_min, s_max, t_min, t_max, H, W):
        """Blend the active SPECT layers onto the composited RGB slice image."""
        if not getattr(self, "_ospect_ready", False) or rgb is None:
            return rgb
        out = rgb
        for layer in SPECT_LAYERS:
            try:
                if not self._ospect_is_on(layer):
                    continue
                img = self._ospect_layer_img(layer)
                arr = self._ospect_sample_on_plane(
                    img, center, u, w_axis, s_min, s_max, t_min, t_max, H, W
                )
                if arr is None:
                    continue
                finite = arr[np.isfinite(arr)]
                finite = finite[finite > 0]
                if finite.size == 0:
                    continue
                lo, hi = self._ospect_window(layer, finite)
                gamma = self._ospect_gamma(layer)
                norm = normalize_pet_slice(arr, lo, hi, gamma=gamma)
                layer_rgb = pet_norm_to_colormap(norm, self._ospect_colormap.get(layer, "hot"))
                out = blend_pet_on_rgb(out, layer_rgb, norm, alpha_scale=self._ospect_alpha(layer))
            except Exception:
                continue
        return out
