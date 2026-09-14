"""Functional-MRI (activation map) overlay for the Oblique Slice page.

Same integration pattern as the SPECT overlays (``oblique_spect.py``) and the
same user-facing behaviour as SISCOM in this page: a card with show / opacity /
threshold, a colormap chooser in the right-click menu, availability gated on a
validated coregistration, mutual exclusion with the parcellation overlays, and
the shared "cortex only" restriction.

Additive and isolated: it never touches the slice tuple, caches or compositing
signatures. It samples the coregistered fMRI on the very same oblique plane
(geometry already computed for the slice), thresholds it (auto levels unless
the user sets a threshold), colour-maps it and blends it right after the SPECT
layers. If anything fails it degrades silently.
"""
from __future__ import annotations

import numpy as np

from ..utils.fmri_visualization import (
    auto_fmri_levels,
    filter_small_clusters,
    fmri_default_cmap,
)
from ..utils.pet_visualization import blend_pet_on_rgb, pet_norm_to_colormap

try:
    from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QSlider, QSpinBox

    _QT_OK = True
except Exception:  # pragma: no cover
    _QT_OK = False


class ObliqueFmriMixin:
    """Adds the fMRI activation overlay to the Oblique Slice page."""

    # ------------------------------------------------------------------ setup
    def _oblique_fmri_setup(self) -> None:
        if getattr(self, "_ofmri_ready", False):
            return
        self._ofmri_ready = True
        self._ofmri_w = {}
        self._ofmri_levels_key = None
        self._ofmri_levels_val = None
        # None = shared default (same as the 3D View), resolved per map type by
        # _ofmri_cmap(); set by the right-click "Color fMRI" chooser.
        self._ofmri_colormap = None
        try:
            self._oblique_fmri_build_card()
        except Exception:
            pass
        try:
            self._oblique_fmri_update_availability()
        except Exception:
            pass

    def _oblique_fmri_build_card(self) -> None:
        """Bind the fMRI card defined in the .ui (cardObliquefMRI, cloned from
        the oblique SISCOM card) and configure ranges / defaults / signals."""
        if not _QT_OK:
            return
        chk = self.ui.findChild(QCheckBox, "chk_obliqueSlice_fMRI")
        if chk is None:
            return
        sld = self.ui.findChild(QSlider, "horizontalSlider_obliqueSlice_fMRI")
        sb = self.ui.findChild(QSpinBox, "sb_obliqueSlice_fMRI")
        dsb = self.ui.findChild(QDoubleSpinBox, "doubleSpinBox_ObliqueSlices_thrfMRI")
        sb_cl = self.ui.findChild(QSpinBox, "sb_obliqueSlice_fMRIMinCluster")

        for wdg in (sld, sb):
            if wdg is not None:
                wdg.setRange(0, 100)
                wdg.setValue(70)
        if dsb is not None:
            dsb.setRange(0.0, 1e6)
            dsb.setDecimals(2)
            dsb.setSingleStep(0.1)
            dsb.setValue(0.0)
            # 0 (the minimum) means "auto": threshold derived from the map.
            dsb.setSpecialValueText("auto")
        if sb_cl is not None:
            # Extent threshold (minimum cluster size, mm3), shared with the 3D View.
            sb_cl.setRange(0, 5000)
            sb_cl.setSingleStep(50)
            sb_cl.setSpecialValueText("Off")
            # Refresh only once the user is done typing (not on every digit).
            sb_cl.setKeyboardTracking(False)
            sb_cl.setValue(int(round(self._ofmri_min_cluster_mm3())))
        if sld is not None and sb is not None:
            sld.valueChanged.connect(sb.setValue)
            sb.valueChanged.connect(sld.setValue)

        self._ofmri_w = {
            "chk": chk, "opacity": sld, "sb_opacity": sb, "thr": dsb, "cluster": sb_cl,
        }
        # Exposed for the page's overlay-exclusion rules (parcellations).
        self.chk_ofmri = chk

        self._oblique_fmri_update_enabled()
        chk.toggled.connect(lambda _c: self._on_oblique_fmri_toggled())
        for key in ("opacity", "thr"):
            w = self._ofmri_w.get(key)
            if w is not None:
                w.valueChanged.connect(
                    lambda _v: self._schedule_refresh(slices=True, brain=False)
                )
        if sb_cl is not None:
            sb_cl.valueChanged.connect(self._on_oblique_fmri_min_cluster_changed)

    def _oblique_fmri_update_availability(self) -> None:
        """Enable the fMRI checkbox only once its coregistration is validated."""
        if not getattr(self, "_ofmri_ready", False):
            return
        chk = self._ofmri_w.get("chk")
        if chk is None:
            return
        validated = bool(getattr(self.state, "fmri_validated", False))
        available = validated and (self._ofmri_img() is not None)
        # Project load / any refresh: reflect the shared minimum cluster size.
        self._sync_oblique_fmri_min_cluster_widget()
        try:
            if available:
                chk.setEnabled(True)
            else:
                chk.blockSignals(True)
                if chk.isChecked():
                    chk.setChecked(False)
                chk.setEnabled(False)
                chk.blockSignals(False)
            self._oblique_fmri_update_enabled()
        except Exception:
            try:
                chk.blockSignals(False)
            except Exception:
                pass

    def _oblique_fmri_update_enabled(self) -> None:
        chk = self._ofmri_w.get("chk")
        on = bool(chk is not None and chk.isChecked())
        for key in ("opacity", "sb_opacity", "thr", "cluster"):
            widget = self._ofmri_w.get(key)
            if widget is not None:
                try:
                    widget.setEnabled(on)
                except Exception:
                    pass

    def _on_oblique_fmri_toggled(self) -> None:
        self._oblique_fmri_update_enabled()
        # Same rule as CT / PET / SISCOM: an overlay turns the parcellations off.
        try:
            self._turn_off_parcellations_if_other_overlay_selected()
        except Exception:
            pass
        self._schedule_refresh(slices=True, brain=False)

    def _choose_oblique_fmri_colormap(self) -> None:
        """Right-click colormap chooser (same call as PET / SISCOM / SPECT)."""
        try:
            from ..ui.neuxelec_message_dialog import NeuXelecSelectionDialog
        except Exception:
            return
        options = ["hot", "inferno", "plasma", "jet", "turbo", "viridis", "coolwarm", "RdBu_r"]
        current = self._ofmri_cmap(self._ofmri_img())
        current_index = options.index(current) if current in options else 0
        cmap = NeuXelecSelectionDialog.select_item(
            self._dialog_parent(),
            "fMRI colormap",
            "Choose the color scale used for the fMRI overlay:",
            options=options,
            current_index=current_index,
            accept_text="Apply",
            reject_text="Cancel",
        )
        if not cmap:
            return
        self._ofmri_colormap = str(cmap)
        self._schedule_refresh(slices=True, brain=False)

    # ------------------------------------------------------------- data access
    def _ofmri_img(self):
        state = getattr(self, "state", None)
        for attr in ("fmri_coreg_in_t1", "fmri_in_t1"):
            img = getattr(state, attr, None)
            if img is not None:
                return img
        return None

    def _ofmri_min_cluster_mm3(self) -> float:
        try:
            return float(getattr(self.state, "fmri_min_cluster_mm3", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _ofmri_display_img(self, img):
        """The map actually drawn: the source, or the source with clusters
        smaller than the shared minimum size removed (cached per source /
        threshold / size)."""
        if img is None:
            return None
        mm3 = self._ofmri_min_cluster_mm3()
        if mm3 <= 0.0:
            return img
        thr = float(self._ofmri_threshold(img))
        key = (id(img), round(thr, 6), round(mm3, 3))
        cache = getattr(self, "_ofmri_display_cache", None)
        if cache is not None and cache[0] == key:
            return cache[1]
        try:
            import SimpleITK as sitk

            vox = float(np.prod(img.GetSpacing()))
            min_vox = max(1, int(round(mm3 / max(vox, 1e-6))))
            arr = filter_small_clusters(sitk.GetArrayFromImage(img), thr, min_vox)
            out = sitk.GetImageFromArray(arr)
            out.CopyInformation(img)
        except Exception:
            out = img
        self._ofmri_display_cache = (key, out)
        return out

    def _on_oblique_fmri_min_cluster_changed(self, value) -> None:
        """Card spinbox edited: update the shared setting and both views."""
        try:
            value = float(value)
        except Exception:
            return
        if abs(value - self._ofmri_min_cluster_mm3()) < 1e-6:
            return
        self.state.fmri_min_cluster_mm3 = value
        self._on_fmri_display_changed()
        vp = getattr(self.state, "view3d_page", None)
        if vp is not None and hasattr(vp, "_apply_fmri_display_change"):
            try:
                vp._apply_fmri_display_change()
            except Exception:
                pass

    def _sync_oblique_fmri_min_cluster_widget(self) -> None:
        """Show the shared value in the card spinbox without re-triggering it."""
        sb_cl = self._ofmri_w.get("cluster") if getattr(self, "_ofmri_w", None) else None
        if sb_cl is None:
            return
        value = int(round(self._ofmri_min_cluster_mm3()))
        if sb_cl.value() == value:
            return
        sb_cl.blockSignals(True)
        try:
            sb_cl.setValue(value)
        finally:
            sb_cl.blockSignals(False)

    def _on_fmri_display_changed(self) -> None:
        """Shared fMRI display setting changed (from this page or the 3D View)."""
        self._ofmri_display_cache = None
        self._sync_oblique_fmri_min_cluster_widget()
        try:
            self._schedule_refresh(slices=True, brain=False)
        except Exception:
            pass

    def _ofmri_is_on(self) -> bool:
        if not getattr(self, "_ofmri_ready", False):
            return False
        chk = self._ofmri_w.get("chk")
        return bool(chk is not None and chk.isChecked() and self._ofmri_img() is not None)

    def _ofmri_alpha(self) -> float:
        s = self._ofmri_w.get("opacity")
        try:
            return float(np.clip(float(s.value()) / 100.0, 0.0, 1.0)) if s is not None else 0.7
        except Exception:
            return 0.7

    def _ofmri_levels(self, img) -> dict:
        """Auto display levels of the map (cached per image object)."""
        key = id(img)
        if self._ofmri_levels_key == key and self._ofmri_levels_val is not None:
            return self._ofmri_levels_val
        try:
            import SimpleITK as sitk

            lv = auto_fmri_levels(
                sitk.GetArrayFromImage(img),
                kind=getattr(getattr(self, "state", None), "fmri_kind", None),
            )
        except Exception:
            lv = {"diverging": False, "threshold": 0.0, "vmax": 1.0, "cmap": "hot"}
        self._ofmri_levels_key = key
        self._ofmri_levels_val = lv
        return lv

    def _ofmri_cmap(self, img) -> str:
        """User choice if any, else the shared default for this map type."""
        if self._ofmri_colormap:
            return str(self._ofmri_colormap)
        diverging = bool(self._ofmri_levels(img).get("diverging", False)) if img is not None else False
        return fmri_default_cmap(diverging)

    def _ofmri_threshold(self, img) -> float:
        dsb = self._ofmri_w.get("thr")
        try:
            v = float(dsb.value()) if dsb is not None else 0.0
        except Exception:
            v = 0.0
        if v > 0.0:
            return v
        return float(self._ofmri_levels(img).get("threshold", 0.0))  # 0 -> auto

    # ------------------------------------------------------------ scalar bar
    def _overlay_fmri_scalar_bar_on_pixmap(self, pm):
        """Vertical colour bar for the fMRI overlay (same drawer as PET / SISCOM,
        placed left of the PET bar so the three never overlap)."""
        if pm is None or pm.isNull():
            return pm
        try:
            if not self._ofmri_is_on():
                return pm
            img = self._ofmri_img()
            lv = self._ofmri_levels(img)
            thr = self._ofmri_threshold(img)
            vmax = float(lv.get("vmax", 1.0))
            if vmax <= thr:
                vmax = thr + 1.0
            if bool(lv.get("diverging", False)):
                lo, hi = -vmax, vmax
            else:
                lo, hi = thr, vmax
            return self._draw_vertical_scalar_bar_on_pixmap(
                pm=pm,
                title="fMRI activation",
                lo=lo,
                hi=hi,
                cmap_name=self._ofmri_cmap(img),
                x_frac=0.54,
            )
        except Exception:
            return pm

    # -------------------------------------------------------------- blending
    def _blend_fmri_on_oblique_rgb(self, rgb, center, u, w_axis,
                                   s_min, s_max, t_min, t_max, H, W):
        """Blend the fMRI activation onto the composited RGB slice image."""
        if not getattr(self, "_ofmri_ready", False) or rgb is None:
            return rgb
        try:
            if not self._ofmri_is_on():
                return rgb
            img = self._ofmri_img()
            arr = self._ospect_sample_on_plane(
                self._ofmri_display_img(img), center, u, w_axis, s_min, s_max, t_min, t_max, H, W
            )
            if arr is None:
                return rgb

            # Cortex-only restriction (shared toggle): parcellation sampled with
            # NEAREST interpolation on this very plane (labels are never blended).
            try:
                if getattr(self, "_cortex_only_active", None) and self._cortex_only_active():
                    parc = getattr(self, "_parcel1_img", None)
                    if parc is not None:
                        parc_arr = self._ospect_sample_on_plane(
                            parc, center, u, w_axis, s_min, s_max, t_min, t_max, H, W,
                            order=0,
                        )
                        if parc_arr is not None:
                            cortex2d = self._cortex_mask_2d(parc_arr)
                            if cortex2d is not None:
                                arr = np.where(cortex2d, arr, np.nan)
            except Exception:
                pass

            lv = self._ofmri_levels(img)
            thr = self._ofmri_threshold(img)
            vmax = float(lv.get("vmax", 1.0))
            if vmax <= thr:
                vmax = thr + 1.0

            if bool(lv.get("diverging", False)):
                valid = np.isfinite(arr) & (np.abs(arr) >= thr)
                norm = np.clip((arr + vmax) / (2.0 * vmax), 0.0, 1.0)
            else:
                valid = np.isfinite(arr) & (arr >= thr)
                norm = np.clip((arr - thr) / max(1e-6, vmax - thr), 0.0, 1.0)
            if not np.any(valid):
                return rgb

            norm = np.where(valid, norm, 0.0).astype(np.float32)
            layer_rgb = pet_norm_to_colormap(norm, self._ofmri_cmap(img))
            # Per-pixel blend weight: a visible floor for every supra-threshold
            # voxel, growing with the activation; 0 elsewhere.
            weight = np.where(valid, np.clip(0.55 + 0.45 * norm, 0.55, 1.0), 0.0).astype(
                np.float32
            )
            return blend_pet_on_rgb(rgb, layer_rgb, weight, alpha_scale=self._ofmri_alpha())
        except Exception:
            return rgb
