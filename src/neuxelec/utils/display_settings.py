# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Remember how the overlays were set, and put them back.

A project reopened used to come back with every functional overlay at
its default: the PET window reset, the SISCOM threshold reset, the CT
opacity reset. The work of finding the right values was done again at
every opening.

HOW THE VALUES ARE TAKEN

By widget name, not by attribute. The settings live in the sliders,
spin boxes and check boxes of the two pages, each already wired to the
rendering, so reading their value and writing it back costs one list per
page and nothing else. Adding a setting later is adding a name to that
list.

ORDER MATTERS ON THE WAY BACK

A check box that shows an overlay is applied after the values it
depends on, so the scene is drawn once, with the settings already in
place, instead of being drawn with the defaults and corrected after.
Each page therefore declares its check boxes last.

WHAT IS MISSING IS NOT AN ERROR

A project written before a setting existed does not carry it, and a
widget that is not in the interface any more is skipped. Restoring is
best effort by design: an overlay at its default is a detail, a project
that refuses to open is not.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
    QWidget,
)


def _widget(owner, name: str) -> QWidget | None:
    ui = getattr(owner, "ui", None)
    if ui is None:
        return None
    try:
        return ui.findChild(QWidget, str(name))
    except Exception:
        return None


def value_of(widget) -> object | None:
    """What this widget holds, in a form JSON can carry."""
    if isinstance(widget, QAbstractButton) and widget.isCheckable():
        return bool(widget.isChecked())
    if isinstance(widget, (QSlider, QSpinBox)):
        return int(widget.value())
    if isinstance(widget, QDoubleSpinBox):
        return float(widget.value())
    if isinstance(widget, QComboBox):
        return str(widget.currentText())
    return None


def apply_value(widget, value) -> bool:
    """Put a value back. Returns False when it does not fit the widget."""
    try:
        if isinstance(widget, QAbstractButton) and widget.isCheckable():
            widget.setChecked(bool(value))
            return True
        if isinstance(widget, (QSlider, QSpinBox)):
            widget.setValue(int(value))
            return True
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
            return True
        if isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index < 0:
                return False
            widget.setCurrentIndex(index)
            return True
    except Exception:
        return False
    return False


def read_widgets(owner, names) -> dict:
    """{name: value} for the widgets that exist and hold something."""
    out: dict[str, object] = {}
    for name in names:
        widget = _widget(owner, name)
        if widget is None:
            continue
        value = value_of(widget)
        if value is not None:
            out[str(name)] = value
    return out


def apply_widgets(owner, data, names=None) -> list[str]:
    """Write the values back, in the order the page declared.

    ``names`` is that order; without it the stored order is used, which
    is only as good as the file. Returns the names actually applied, for
    tests and for the log.
    """
    if not isinstance(data, dict):
        return []

    ordre = list(names) if names else list(data.keys())
    appliques: list[str] = []

    for name in ordre:
        if name not in data:
            continue
        widget = _widget(owner, name)
        if widget is None:
            continue
        if apply_value(widget, data[name]):
            appliques.append(str(name))

    return appliques


def read_attributes(owner, names) -> dict:
    """The few settings that live on the page rather than in a widget."""
    out: dict[str, object] = {}
    for name in names:
        if not hasattr(owner, name):
            continue
        value = getattr(owner, name)
        if isinstance(value, (bool, int, float, str)) or value is None:
            out[str(name)] = value
    return out


def apply_attributes(owner, data, names) -> list[str]:
    if not isinstance(data, dict):
        return []

    appliques: list[str] = []
    for name in names:
        if name not in data:
            continue
        try:
            setattr(owner, name, data[name])
            appliques.append(str(name))
        except Exception:
            continue
    return appliques
