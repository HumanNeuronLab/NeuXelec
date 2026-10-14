# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""The oblique page remembers how its overlays were set.

Same idea as the 3D view, and deliberately the same shape, so that a
setting added on one page is added the same way on the other: a name in
a list, read from the widget that already drives the rendering.

The PET block exists three times here, for the PET itself and for the
two SPECT, each with its minimum, its maximum, its gamma and its
opacity. They are listed in full rather than generated, because a name
that is wrong must fail where it is written, not two files away.
"""

from __future__ import annotations

from ..utils.display_settings import (
    apply_attributes,
    apply_widgets,
    read_attributes,
    read_widgets,
)

OBLIQUE_DISPLAY_WIDGETS: tuple[str, ...] = (
    # CT
    "horizontalSlider_obliqueSlice_CT",
    "spinBox_obliqueSlice_CT",
    # PET
    "horizontalSlider_obliqueSlice_petMin",
    "horizontalSlider_obliqueSlice_petMax",
    "horizontalSlider_obliqueSlice_petGamma",
    "horizontalSlider_obliqueSlice_petOpacity",
    "sb_obliqueSlice_petMin",
    "sb_obliqueSlice_petMax",
    "dsb_obliqueSlice_petGamma",
    "spinBox_obliqueSlice_petOpacity",
    # SPECT ictal
    "horizontalSlider_obliqueSlice_petMin_ictal",
    "horizontalSlider_obliqueSlice_petMax_ictal",
    "horizontalSlider_obliqueSlice_petGamma_ictal",
    "horizontalSlider_obliqueSlice_petOpacity_ictal",
    "sb_obliqueSlice_petMin_ictal",
    "sb_obliqueSlice_petMax_ictal",
    "dsb_obliqueSlice_petGamma_ictal",
    "spinBox_obliqueSlice_petOpacity_ictal",
    # SPECT inter-ictal
    "horizontalSlider_obliqueSlice_petMin_interictal",
    "horizontalSlider_obliqueSlice_petMax_interictal",
    "horizontalSlider_obliqueSlice_petGamma_interictal",
    "horizontalSlider_obliqueSlice_petOpacity_interictal",
    "sb_obliqueSlice_petMin_interictal",
    "sb_obliqueSlice_petMax_interictal",
    "dsb_obliqueSlice_petGamma_interictal",
    "spinBox_obliqueSlice_petOpacity_interictal",
    # SISCOM
    "horizontalSlider_obliqueSlice_SISCOM",
    "sb_obliqueSlice_SISCOM",
    # fMRI
    "horizontalSlider_obliqueSlice_fMRI",
    "sb_obliqueSlice_fMRI",
    "sb_obliqueSlice_fMRIMinCluster",
    # Les calques se montrent une fois leurs valeurs posees.
    "chk_obliqueSlice_CT",
    "chk_obliqueSlice_PET",
    "chk_obliqueSlice_PET_ictal",
    "chk_obliqueSlice_PET_interictal",
    "chk_obliqueSlice_SISCOM",
    "chk_obliqueSlice_fMRI",
)

OBLIQUE_DISPLAY_ATTRIBUTES: tuple[str, ...] = (
    "_pet_colormap_name",
    "_siscom_colormap_name",
    "_ofmri_min_cluster_mm3",
    "_show_color_scales",
    "_flip_lr_oblique",
)


class ObliqueDisplaySettingsMixin:
    """Lire et reposer les reglages d'affichage des coupes obliques."""

    def display_settings_dict(self) -> dict:
        try:
            return {
                "widgets": read_widgets(self, OBLIQUE_DISPLAY_WIDGETS),
                "attributes": read_attributes(self, OBLIQUE_DISPLAY_ATTRIBUTES),
            }
        except Exception:
            return {}

    def apply_display_settings(self, data) -> list[str]:
        if not isinstance(data, dict):
            return []

        applique: list[str] = []

        try:
            applique += apply_attributes(
                self, data.get("attributes"), OBLIQUE_DISPLAY_ATTRIBUTES
            )
        except Exception:
            pass

        try:
            applique += apply_widgets(
                self, data.get("widgets"), OBLIQUE_DISPLAY_WIDGETS
            )
        except Exception:
            pass

        try:
            self._schedule_refresh(slices=True, brain=False)
        except Exception:
            pass

        return applique
