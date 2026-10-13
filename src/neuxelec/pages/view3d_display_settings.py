"""The 3D view remembers how its overlays were set.

Finding the right PET window, the right SISCOM threshold or the right CT
opacity takes a minute and it was thrown away at every closing. These
values now travel with the project.

The list below is the whole of it: a name per setting, read from the
widget that already drives the rendering. The check boxes come last on
purpose, so the scene is drawn once with the values in place instead of
being drawn at the defaults and corrected afterwards.
"""

from __future__ import annotations

from ..utils.display_settings import (
    apply_attributes,
    apply_widgets,
    read_attributes,
    read_widgets,
)

#: Les valeurs d'abord, les cases qui montrent un calque en dernier.
VIEW3D_DISPLAY_WIDGETS: tuple[str, ...] = (
    # CT
    "sld_3d_ctTreshold",
    "sld_3d_ctOpacity",
    # PET
    "sld_3d_petMin",
    "sld_3d_petMax",
    "sld_3d_petGamma",
    "sld_3d_petOpacity",
    "sb_3d_petMin",
    "sb_3d_petMax",
    "dsb_3d_petGamma",
    # SPECT ictal
    "sld_3d_petMin_ictal",
    "sld_3d_petMax_ictal",
    "sld_3d_petGamma_ictal",
    "sld_3d_petOpacity_ictal",
    "sb_3d_petMin_ictal",
    "sb_3d_petMax_ictal",
    "dsb_3d_petGamma_ictal",
    # SPECT inter-ictal
    "sld_3d_petMin_interictal",
    "sld_3d_petMax_interictal",
    "sld_3d_petGamma_interictal",
    "sld_3d_petOpacity_interictal",
    "sb_3d_petMin_interictal",
    "sb_3d_petMax_interictal",
    "dsb_3d_petGamma_interictal",
    # SISCOM
    "dsb_3d_siscomZthr",
    "sld_3d_siscomOpacity",
    # fMRI
    "dsb_3d_fmriThr",
    "sld_3d_fmriOpacity",
    "sb_3d_fmriMinCluster",
    # Les calques se montrent une fois leurs valeurs posees.
    "chk_3d_showCT",
    "chk_3d_showPET",
    "chk_3d_showPET_ictal",
    "chk_3d_showPET_interictal",
    "chk_3d_showSISCOM",
    "chk_3d_showfMRI",
)

#: Ce qui ne vit pas dans un widget: les palettes, et ce que l'on a choisi
#: soi-meme plutot que laisse deviner.
VIEW3D_DISPLAY_ATTRIBUTES: tuple[str, ...] = (
    "_pet_colormap_name",
    "_siscom_colormap_name",
    "_siscom_fixed_zmax",
    "_fmri_cmap_name",
    "_fmri_cmap_user_set",
    "_fmri_min_cluster_mm3",
    "_fmri_opacity",
    "_fmri_threshold",
    "_fmri_vmax",
    "_fmri_diverging",
    "_fmri_plane_on",
    "_fmri_surface_shown",
    "_fmri_pial_shown",
)


class View3DDisplaySettingsMixin:
    """Lire et reposer les reglages d'affichage de la vue 3D."""

    def display_settings_dict(self) -> dict:
        """What this page wants to find again when the project reopens."""
        try:
            return {
                "widgets": read_widgets(self, VIEW3D_DISPLAY_WIDGETS),
                "attributes": read_attributes(self, VIEW3D_DISPLAY_ATTRIBUTES),
            }
        except Exception:
            return {}

    def apply_display_settings(self, data) -> list[str]:
        """Put them back, values before the check boxes that use them.

        Best effort: a setting that no longer exists, or a project written
        before it did, is skipped rather than refused.
        """
        if not isinstance(data, dict):
            return []

        applique: list[str] = []

        try:
            applique += apply_attributes(
                self, data.get("attributes"), VIEW3D_DISPLAY_ATTRIBUTES
            )
        except Exception:
            pass

        try:
            applique += apply_widgets(
                self, data.get("widgets"), VIEW3D_DISPLAY_WIDGETS
            )
        except Exception:
            pass

        # Les attributs ne passent par aucun signal: sans cela, une palette
        # relue resterait invisible jusqu'au prochain geste. Les widgets,
        # eux, ont deja declenche ce qu'il fallait.
        try:
            self._render()
        except Exception:
            pass

        return applique
