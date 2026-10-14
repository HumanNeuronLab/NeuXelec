# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Le tableau des régions, à droite de l'onglet Parcellation.

CE QU'IL MONTRE

Une ligne par région réellement présente dans la parcellation, avec sa
case et la liste des contacts qui y tombent. Toutes cochées au départ :
on part du cerveau entier et on en retire, plutôt que de partir de rien
et de devoir tout cocher.

POURQUOI UN FILTRE

Un atlas Desikan compte 85 régions, un Schaefer jusqu'à 400. Chercher une
région en faisant défiler quatre cents lignes est inutilisable, alors que
l'on sait presque toujours le nom que l'on cherche.

POURQUOI UN SEUL BOUTON QUI BASCULE

"Tout décocher" et "tout cocher" sont le même geste vu des deux côtés. Un
bouton qui dit lequel des deux il fera occupe une place au lieu de deux,
et ne peut pas être cliqué à contretemps.

CE QUE CE MODULE NE FAIT PAS

Il ne dessine rien. Il dit ce qui est coché et prévient quand cela change ;
la vue 3D décide quoi en faire. Un panneau qui parlerait à PyVista serait
intestable sans carte graphique.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..utils.parcellation_regions import Region

logger = logging.getLogger(__name__)

COL_REGION = 0
COL_CONTACTS = 1

#: Lignes visibles sans defiler. Au-dela, le tableau etirerait le
#: panneau de commande et mangerait la hauteur de la vue 3D.
VISIBLE_ROWS = 4

_STYLE = """
QFrame#card3DRegions {
    background-color: #11131B;
    border: 1px solid #252834;
    border-radius: 11px;
}
QLabel#regionsPanelTitle {
    color: #7E8294;
    font-size: 11px;
    font-weight: 600;
}
QLineEdit#regionsFilter {
    color: #F2F2F5;
    background-color: #151720;
    border: 1px solid #2B2D38;
    border-radius: 8px;
    padding: 5px 9px;
    font-size: 12px;
}
QLineEdit#regionsFilter:focus {
    border: 1px solid #FF487D;
}
QTableWidget#regionsTable {
    color: #D8DAE4;
    background-color: #0E1018;
    border: 1px solid #252834;
    border-radius: 8px;
    gridline-color: #1C1E28;
    font-size: 12px;
}
QTableWidget#regionsTable::item:selected {
    background-color: #3A2132;
    color: white;
}
QHeaderView::section {
    color: #7E8294;
    background-color: #151720;
    border: none;
    border-bottom: 1px solid #252834;
    padding: 4px 6px;
    font-size: 11px;
    font-weight: 600;
}
"""


class ParcellationRegionPanel:
    """Bâtir le panneau, et dire à l'appelant ce qui est coché."""

    def __init__(
        self,
        ui,
        on_plot_toggled: Callable[[bool], None] | None = None,
        on_regions_changed: Callable[[set[int]], None] | None = None,
    ):
        self.ui = ui
        self._on_plot_toggled = on_plot_toggled
        self._on_regions_changed = on_regions_changed

        self.chk_plot: QCheckBox | None = None
        self.btn_toggle_all: QPushButton | None = None
        self.edit_filter: QLineEdit | None = None
        self.chk_with_contacts: QCheckBox | None = None
        self.table: QTableWidget | None = None

        self._regions: list[Region] = []
        self._checked: set[int] = set()
        self._muet = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self) -> bool:
        """Rendre ``False`` si le cadre n'est pas là, sans rien casser."""
        frame = self.ui.findChild(QFrame, "card3DRegions")
        if frame is None:
            return False

        layout = frame.layout() or QVBoxLayout(frame)
        frame.setStyleSheet(_STYLE)

        # Pas de titre : l'onglet s'appelle deja Parcellation et l'en-tete
        # du tableau dit Region. Une ligne de plus coutait de la hauteur,
        # qui est ce qui manque.
        layout.setSpacing(4)
        layout.setContentsMargins(10, 6, 10, 6)

        rangee = QHBoxLayout()
        rangee.setSpacing(8)
        self.chk_plot = QCheckBox("Plot parcellation in 3D")
        self.chk_plot.setToolTip(
            "Draw one surface per region, instead of the brain mask or the "
            "pial surface. Unticking it restores what was shown before."
        )
        self.chk_plot.toggled.connect(self._on_plot)
        rangee.addWidget(self.chk_plot, 1)

        self.btn_toggle_all = QPushButton("Uncheck all")
        self.btn_toggle_all.clicked.connect(self._toggle_all)
        rangee.addWidget(self.btn_toggle_all)
        layout.addLayout(rangee)

        filtre = QHBoxLayout()
        filtre.setSpacing(8)
        self.edit_filter = QLineEdit()
        self.edit_filter.setObjectName("regionsFilter")
        self.edit_filter.setPlaceholderText("Filter by region or contact…")
        self.edit_filter.setClearButtonEnabled(True)
        self.edit_filter.textChanged.connect(lambda _: self._apply_filter())
        filtre.addWidget(self.edit_filter, 1)

        self.chk_with_contacts = QCheckBox("With contacts only")
        self.chk_with_contacts.setToolTip(
            "Hide the regions where no contact falls."
        )
        self.chk_with_contacts.toggled.connect(lambda _: self._apply_filter())
        filtre.addWidget(self.chk_with_contacts)
        layout.addLayout(filtre)

        self.table = QTableWidget(0, 2)
        self.table.setObjectName("regionsTable")
        self.table.setHorizontalHeaderLabels(["Region", "Contacts"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(COL_REGION, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_CONTACTS, QHeaderView.ResizeToContents
        )
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)
        self._cap_table_height()

        self.set_regions([])
        return True

    def _cap_table_height(self) -> None:
        """Fixer le tableau a VISIBLE_ROWS lignes, ni plus ni moins.

        Un plafond seul ne suffit pas : le panneau de commande se reglait
        sur d'autres contenus et le tableau s'y voyait reduit a deux
        lignes. Une hauteur fixe le fait compter dans le minimum du
        panneau, qui devient donc assez haut pour les quatre.
        """
        if self.table is None:
            return
        try:
            ligne = self.table.verticalHeader().defaultSectionSize()
            entete = self.table.horizontalHeader().sizeHint().height()
            self.table.setFixedHeight(
                entete + VISIBLE_ROWS * ligne + 2 * self.table.frameWidth()
            )
        except Exception:
            logger.exception("Could not size the region table")

    # ------------------------------------------------------------------
    # Données
    # ------------------------------------------------------------------

    def set_regions(self, regions: Sequence[Region]) -> None:
        """Remplir le tableau, tout coché.

        Appelé à chaque changement de parcellation : la table du 1 n'a
        rien à voir avec celle du 2, et garder les cases de l'une pour
        l'autre n'aurait aucun sens, les numéros d'étiquette ne désignant
        pas les mêmes régions.
        """
        self._regions = list(regions)
        self._checked = {r.label for r in self._regions}

        if self.table is None:
            return

        self._muet = True
        try:
            self.table.setRowCount(len(self._regions))
            for ligne, region in enumerate(self._regions):
                nom = QTableWidgetItem(region.name)
                nom.setFlags(
                    (nom.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable
                )
                nom.setCheckState(Qt.Checked)
                nom.setData(Qt.UserRole, int(region.label))
                nom.setToolTip(f"{region.name}  (label {region.label})")

                contacts = QTableWidgetItem(" ".join(region.contacts) or "-")
                contacts.setFlags(contacts.flags() & ~Qt.ItemIsEditable)
                if region.contacts:
                    contacts.setToolTip(
                        f"{len(region.contacts)} contact(s): "
                        + ", ".join(region.contacts)
                    )

                self.table.setItem(ligne, COL_REGION, nom)
                self.table.setItem(ligne, COL_CONTACTS, contacts)
        finally:
            self._muet = False

        self._refresh_toggle_all_text()
        self._apply_filter()
        self._announce()

    def regions(self) -> list[Region]:
        """Les regions actuellement decrites par le tableau."""
        return list(self._regions)

    def checked_labels(self) -> set[int]:
        """Les régions cochées, filtre ou non."""
        return set(self._checked)

    def visible_labels(self) -> set[int]:
        """Les régions que le filtre laisse voir."""
        if self.table is None:
            return set(self._checked)
        vus = set()
        for i, region in enumerate(self._regions):
            if not self.table.isRowHidden(i):
                vus.add(int(region.label))
        return vus

    def plotted_labels(self) -> set[int]:
        """Ce qui doit être tracé : les régions cochées, sans plus.

        La recherche ne commande pas le dessin. Elle sert à retrouver une
        ligne dans un tableau qui en compte des centaines, et taper trois
        lettres pour vérifier où tombe un contact ne doit pas effacer la
        moitié du cerveau au passage.

        "Check all" veut donc dire tout, et "Uncheck all" rien, quel que
        soit ce qui est tapé dans la barre : un bouton dont l'effet
        dépendrait d'un champ de recherche à côté ne serait prévisible
        depuis aucun des deux.
        """
        return set(self._checked)

    def is_plotting(self) -> bool:
        return bool(self.chk_plot is not None and self.chk_plot.isChecked())

    def set_plotting(self, on: bool) -> None:
        """Forcer l'état, sans rejouer la bascule."""
        if self.chk_plot is None:
            return
        self.chk_plot.blockSignals(True)
        self.chk_plot.setChecked(bool(on))
        self.chk_plot.blockSignals(False)

    # ------------------------------------------------------------------
    # Réactions
    # ------------------------------------------------------------------

    def _on_plot(self, checked: bool) -> None:
        if self._on_plot_toggled is None:
            return
        try:
            self._on_plot_toggled(bool(checked))
        except Exception:
            logger.exception("Could not switch the parcellation plot")

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._muet or item is None or item.column() != COL_REGION:
            return
        label = item.data(Qt.UserRole)
        if label is None:
            return
        if item.checkState() == Qt.Checked:
            self._checked.add(int(label))
        else:
            self._checked.discard(int(label))
        self._refresh_toggle_all_text()
        self._announce()

    def _toggle_all(self) -> None:
        """Tout décocher, ou tout recocher si rien ne l'est.

        Sur **toutes** les régions, et non sur les seules lignes
        visibles, et ce qui est tracé suit : soit le cerveau entier, soit
        rien. Pour n'en montrer qu'une partie, on décoche tout puis on
        coche les régions voulues, ce que la recherche aide à trouver
        sans rien changer au dessin.
        """
        if self.table is None:
            return
        lignes = list(range(self.table.rowCount()))
        if not lignes:
            return
        vers = (
            Qt.Unchecked
            if any(
                self.table.item(i, COL_REGION).checkState() == Qt.Checked for i in lignes
            )
            else Qt.Checked
        )

        self._muet = True
        try:
            for i in lignes:
                item = self.table.item(i, COL_REGION)
                item.setCheckState(vers)
                label = int(item.data(Qt.UserRole))
                if vers == Qt.Checked:
                    self._checked.add(label)
                else:
                    self._checked.discard(label)
        finally:
            self._muet = False

        self._refresh_toggle_all_text()
        self._announce()

    def _apply_filter(self) -> None:
        if self.table is None:
            return
        motif = (self.edit_filter.text() if self.edit_filter else "").strip().lower()
        avec_contacts = bool(
            self.chk_with_contacts is not None and self.chk_with_contacts.isChecked()
        )
        for i, region in enumerate(self._regions):
            # Le nom de la region, ou celui d'un de ses contacts : taper
            # TB3 doit montrer la region ou TB3 se trouve, ce qui est la
            # question que l'on se pose devant une electrode.
            trouve = not motif or motif in region.name.lower() or any(
                motif in contact.lower() for contact in region.contacts
            )
            cache = (not trouve) or (avec_contacts and not region.has_contacts)
            self.table.setRowHidden(i, bool(cache))
        # Pas d'annonce : filtrer ne change que les lignes affichees.
        # Le dessin ne depend que des cases, qui n'ont pas bouge.
        self._refresh_toggle_all_text()

    def _refresh_toggle_all_text(self) -> None:
        if self.btn_toggle_all is None or self.table is None:
            return
        # Sur toutes les lignes, comme le bouton lui-meme : il dirait
        # "Check all" sur une liste filtree vide alors que tout est coche.
        rien_coche = not self._checked
        self.btn_toggle_all.setText("Check all" if rien_coche else "Uncheck all")
        self.btn_toggle_all.setEnabled(bool(self.table.rowCount()))

    def _announce(self) -> None:
        if self._on_regions_changed is None:
            return
        try:
            self._on_regions_changed(self.plotted_labels())
        except Exception:
            logger.exception("Could not apply the region selection")
