# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""After saving a modality, offer to remove what led to it.

A CT arrives as a DICOM folder, becomes a NIfTI, then a cleaned copy,
and only then the volume resampled into MRI 1 that the user saves. Once
that last file exists the other three are usually of no further use, and
they are what makes a patient folder unreadable.

The window says as little as possible: a line per file, its size, three
words for what it is. The list is the explanation, so there is no
paragraph above it, and the window is only as tall as its rows.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..utils import modality_files as mf
from .neuxelec_dialog import MUTED, NeuXelecDialog
from .neuxelec_message_dialog import NeuXelecMessageDialog


class ModalityCleanupDialog(NeuXelecDialog):
    """Ce que la modalite laisse derriere elle, et ce qu'on en fait."""

    def __init__(self, modality: str, display_name: str, chain, kept, state, parent=None):
        super().__init__(
            f"Clean up {display_name}",
            getattr(kept, "name", str(kept)),
            parent=parent,
        )
        self.modality = str(modality)
        self.display_name = str(display_name)
        self.chain = list(chain)
        self.kept = kept
        self.state = state
        self.report: dict | None = None

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(lambda *_a: self._update_preview())
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.body.addWidget(self.tree)

        self._fill()

        row = QHBoxLayout()
        self.lbl_preview = QLabel("")
        self.lbl_preview.setStyleSheet(f"color: {MUTED}; font-size: 12px;")

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("primaryButton")
        self.btn_delete.clicked.connect(self._delete)

        self.btn_keep = QPushButton("Keep all")
        self.btn_keep.setObjectName("secondaryButton")
        self.btn_keep.clicked.connect(self.reject)

        row.addWidget(self.lbl_preview)
        row.addStretch(1)
        row.addWidget(self.btn_delete)
        row.addWidget(self.btn_keep)
        self.body.addLayout(row)

        self._size_to_content()
        self._update_preview()

    # ----------------------------------------------------------- le contenu
    def _fill(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()

        # Le fichier garde ouvre la liste et n'a pas de case: il est la
        # raison de cette fenetre, pas un candidat au depart.
        garde = QTreeWidgetItem(
            self.tree,
            [str(getattr(self.kept, "name", self.kept)), "", "just saved"],
        )
        garde.setFlags(Qt.ItemIsEnabled)
        garde.setDisabled(True)

        for fichier in self.chain:
            nom = fichier.name + ("\\" if fichier.is_folder else "")
            quoi = fichier.label
            if fichier.is_folder:
                quoi = f"{quoi}, {fichier.file_count} files"

            item = QTreeWidgetItem(self.tree, [nom, mf.human_size(fichier.size), quoi])
            item.setData(0, Qt.UserRole, fichier)
            item.setToolTip(0, str(fichier.path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)

        self.tree.blockSignals(False)

    def _size_to_content(self) -> None:
        """Aussi haute que ses lignes, pas que l'ecran.

        La hauteur d'une ligne est demandee a la liste elle-meme: la
        calculer de tete laissait une barre de defilement pour une ligne
        qui manquait.
        """
        lignes = len(self.chain) + 1
        hauteur_ligne = max(22, self.tree.sizeHintForRow(0))
        # Exacte, et non minimale: le nombre de lignes ne bouge pas, donc
        # une liste plus haute ne serait que du vide.
        self.tree.setFixedHeight(min(380, hauteur_ligne * lignes + 12))
        self.setMinimumSize(420, 200)
        self.adjustSize()
        self.resize(560, self.height())

    def _ticked(self) -> list:
        out = []
        racine = self.tree.invisibleRootItem()
        for i in range(racine.childCount()):
            item = racine.child(i)
            fichier = item.data(0, Qt.UserRole)
            if fichier is not None and item.checkState(0) == Qt.Checked:
                out.append(fichier)
        return out

    def _update_preview(self) -> None:
        choisis = self._ticked()
        octets = sum(int(f.size) for f in choisis)
        self.btn_delete.setEnabled(bool(choisis))
        self.lbl_preview.setText(
            "Nothing ticked"
            if not choisis
            else f"{len(choisis)} ticked, {mf.human_size(octets)}"
        )

    # ----------------------------------------------------------- l'execution
    def _delete(self) -> None:
        choisis = self._ticked()
        if not choisis:
            return

        octets = mf.human_size(sum(int(f.size) for f in choisis))
        if not NeuXelecMessageDialog.question(
            self,
            "Delete",
            f"Delete {len(choisis)} item(s), {octets}?\n"
            "To the recycle bin when Windows allows it.\n"
            f"The project then points at {getattr(self.kept, 'name', self.kept)}.",
            accept_text="Delete",
        ):
            return

        self.report = mf.delete_chosen(choisis, self.state, self.modality, self.kept)

        # Rien a annoncer quand tout s'est passe: les fichiers ne sont plus
        # la, et la fenetre se ferme. Seul un echec merite d'etre dit.
        if self.report["failed"]:
            lignes = ["Left alone:"]
            for chemin, raison in self.report["failed"][:6]:
                lignes.append(f"  {chemin}: {raison}")
            NeuXelecMessageDialog.warning(self, "Delete", "\n".join(lignes))

        self.accept()
