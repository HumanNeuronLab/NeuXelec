# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Une seule entree de menu pour la couleur de tous les calques.

POURQUOI

Le clic droit de la vue 3D portait une entree par calque : Color PET, Color
SISCOM, Color fMRI, Color CT, Color Ictal SPECT, Color Inter-ictal SPECT.
Six lignes qui disent la meme chose et qui repoussent vers le bas tout ce
qui vient apres. Une seule entree, et le calque devient un choix dans la
fenetre plutot qu'un choix dans le menu.

POURQUOI DEUX CONTROLES ET NON UN

Le CT n'a pas d'echelle de couleurs, il a une couleur. Les cinq autres
calques portent une valeur par voxel et ont donc besoin d'une echelle. Un
seul controle pour les deux forcerait l'un des deux a mentir. La fenetre
montre donc l'echelle pour les calques qui en ont une, et un bouton de
couleur pour le CT.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QDialog, QPushButton

from .neuxelec_message_dialog import NeuXelecSelectionDialog

#: Les calques tels que la fenetre les presente. ``kind`` vaut "colormap"
#: quand le calque porte une echelle, "solid" quand il porte une couleur.
Layer = dict


class OverlayColorDialog(NeuXelecSelectionDialog):
    """Choisir un calque, puis sa couleur ou son echelle."""

    def __init__(self, layers: list[Layer], parent=None):
        if not layers:
            raise ValueError("au moins un calque est attendu")

        self._layers = list(layers)
        # Normalisé à l'entrée : la couleur de départ arrive telle que
        # l'appelant l'a écrite, celle que l'on choisit ensuite sort de
        # QColor.name(). Sans cela, la même couleur ressortirait sous deux
        # formes selon qu'on y a touché ou non.
        self._solid_values = {
            layer["key"]: self._normalise(layer.get("current"))
            for layer in self._layers
            if layer.get("kind") == "solid"
        }

        premier = self._layers[0]
        super().__init__(
            title="Overlay color",
            message="Pick the overlay, then its colour.",
            options=list(premier.get("options") or []),
            current_index=self._index_courant(premier),
            parent=parent,
            accept_text="Apply",
            reject_text="Cancel",
        )
        self.setMinimumSize(470, 330)

        # Le meme nom d'objet que le combo herite, pour que la feuille de
        # style du parent habille les deux sans etre recopiee.
        self.combo_layer = QComboBox()
        self.combo_layer.setObjectName("selectionCombo")
        self.combo_layer.setMinimumHeight(40)
        self.combo_layer.addItems([str(layer["label"]) for layer in self._layers])

        self.btn_solid_color = QPushButton()
        self.btn_solid_color.setObjectName("solidColorButton")
        self.btn_solid_color.setMinimumHeight(40)
        self.btn_solid_color.clicked.connect(self._pick_solid_color)

        try:
            layout = self.message_frame.layout()
            index = layout.indexOf(self.combo_selection)
            layout.insertWidget(index, self.combo_layer)
            layout.insertSpacing(index + 1, 8)
            layout.addWidget(self.btn_solid_color)
        except Exception:
            pass

        self.combo_layer.currentIndexChanged.connect(self._on_layer_changed)
        self._on_layer_changed(0)

    # ------------------------------------------------------------------
    # Etat
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(valeur) -> str | None:
        """Une couleur sous une seule forme, ou ``None`` si elle n'en est pas une."""
        if valeur is None:
            return None
        couleur = QColor(str(valeur))
        return couleur.name() if couleur.isValid() else None

    @staticmethod
    def _index_courant(layer: Layer) -> int:
        options = list(layer.get("options") or [])
        courant = layer.get("current")
        return options.index(courant) if courant in options else 0

    def current_layer(self) -> Layer:
        index = max(0, min(self.combo_layer.currentIndex(), len(self._layers) - 1))
        return self._layers[index]

    def _on_layer_changed(self, _index: int) -> None:
        layer = self.current_layer()
        solide = layer.get("kind") == "solid"

        self.combo_selection.setVisible(not solide)
        self.btn_solid_color.setVisible(solide)

        if solide:
            self._refresh_solid_button(layer)
            return

        self.combo_selection.blockSignals(True)
        self.combo_selection.clear()
        self.combo_selection.addItems([str(o) for o in (layer.get("options") or [])])
        self.combo_selection.setCurrentIndex(self._index_courant(layer))
        self.combo_selection.blockSignals(False)

    def _refresh_solid_button(self, layer: Layer) -> None:
        valeur = self._solid_values.get(layer["key"]) or "#808080"
        couleur = QColor(str(valeur))
        if not couleur.isValid():
            couleur = QColor("#808080")

        # Du texte sombre sur un fond clair, et l'inverse : le nom de la
        # couleur doit rester lisible quelle qu'elle soit.
        texte = "#101119" if couleur.lightness() > 140 else "#F2F2F5"
        self.btn_solid_color.setText(couleur.name().upper())
        self.btn_solid_color.setStyleSheet(
            "QPushButton#solidColorButton {"
            f" color: {texte};"
            f" background-color: {couleur.name()};"
            " border: 1px solid #2B2D38; border-radius: 9px;"
            " font-size: 12px; font-weight: 600; }"
            "QPushButton#solidColorButton:hover { border: 1px solid #FF487D; }"
        )

    def _pick_solid_color(self) -> None:
        from .neuxelec_color_dialog import NeuXelecColorDialog

        layer = self.current_layer()
        depart = QColor(str(self._solid_values.get(layer["key"]) or "#808080"))

        choisi = NeuXelecColorDialog.get_color(
            initial_color=depart if depart.isValid() else QColor("#808080"),
            parent=self,
            title=f"Choose {layer['label']} color",
        )
        if choisi is None:
            return

        couleur = QColor(str(choisi))
        if not couleur.isValid():
            return

        self._solid_values[layer["key"]] = couleur.name()
        self._refresh_solid_button(layer)

    # ------------------------------------------------------------------
    # Resultat
    # ------------------------------------------------------------------

    def selection(self) -> tuple[str, str] | None:
        """``(cle du calque, echelle ou couleur)``, ou ``None``."""
        layer = self.current_layer()
        if layer.get("kind") == "solid":
            valeur = self._solid_values.get(layer["key"])
            return (str(layer["key"]), str(valeur)) if valeur else None
        texte = self.combo_selection.currentText()
        return (str(layer["key"]), str(texte)) if texte else None

    @classmethod
    def choose(cls, parent, layers: list[Layer]) -> tuple[str, str] | None:
        dlg = cls(layers, parent=parent)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.selection()
