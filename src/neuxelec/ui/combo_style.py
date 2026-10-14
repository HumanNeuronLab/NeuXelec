# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le menu déroulant de NeuXelec, avec sa flèche en SVG.

Qt dessine la flèche d'un QComboBox avec le thème du système : sur fond sombre
elle sort noire sur noir, donc invisible. Le reste de l'application a déjà
résolu le problème pour les boutons de QSpinBox, avec le chevron
``spin_down.svg``, et c'est celui-là qu'on réemploie plutôt que d'en dessiner
un second qui finirait par diverger.
"""

from __future__ import annotations

from ..utils.resources import resource_path

#: Les couleurs de la fenêtre principale, pas celles des boîtes de dialogue.
_ENCRE = "#0B0D14"
_CHAMP = "#10121A"
_TRAIT = "#242734"
_TEXTE = "#D5D7E1"
_ROSE = "#FF487D"


def combo_style() -> str:
    """Feuille de style d'un QComboBox, flèche comprise.

    Le chemin de l'icône passe par ``resource_path`` pour valoir aussi bien
    depuis les sources que depuis l'exécutable, où les ressources sont
    dépliées ailleurs.
    """
    fleche = (resource_path("resources/images") / "spin_down.svg").as_posix()
    return f"""
    QComboBox {{
        background-color: {_CHAMP};
        color: {_TEXTE};
        border: 1px solid {_TRAIT};
        border-radius: 7px;
        padding: 2px 6px 2px 8px;
        min-height: 20px;
    }}
    QComboBox:hover {{ border: 1px solid {_ROSE}; }}
    QComboBox:disabled {{ color: #5A6070; border: 1px solid #1A1D27; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 18px;
        border: none;
        background: transparent;
    }}
    QComboBox::down-arrow {{
        image: url({fleche});
        width: 10px;
        height: 7px;
    }}
    QComboBox::down-arrow:disabled {{ image: none; }}
    QComboBox QAbstractItemView {{
        background-color: {_CHAMP};
        color: {_TEXTE};
        border: 1px solid {_ROSE};
        border-radius: 7px;
        selection-background-color: #1C1F2A;
        selection-color: white;
        outline: none;
        padding: 2px;
    }}
    """


def style_combo(widget) -> None:
    """Appliquer le style à un menu déroulant, sans échouer s'il est absent."""
    if widget is None:
        return
    try:
        widget.setStyleSheet(combo_style())
    except Exception:  # pragma: no cover - une feuille de style ne doit rien casser
        pass
