"""After saving a modality, offer to remove what led to it.

A CT arrives as a DICOM folder, becomes a NIfTI, then a cleaned copy,
and only then the volume resampled into MRI 1 that the user saves. Once
that last file exists, the other three are usually of no further use,
and they are what makes a patient folder unreadable.

The window therefore opens on the save, lists exactly those files with
their size, and ticks nothing: they belong to the user, the DICOM above
all, and what is deleted here is deleted on their say-so alone.
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
from .neuxelec_dialog import MUTED, NeuXelecDialog, explain
from .neuxelec_message_dialog import NeuXelecMessageDialog


class ModalityCleanupDialog(NeuXelecDialog):
    """Ce que la modalite laisse derriere elle, et ce qu'on en fait."""

    def __init__(self, modality: str, display_name: str, chain, kept, state, parent=None):
        super().__init__(
            f"Clean up the {display_name} files",
            f"Saved: {kept}",
            parent=parent,
        )
        self.modality = str(modality)
        self.display_name = str(display_name)
        self.chain = list(chain)
        self.kept = kept
        self.state = state
        self.report: dict | None = None

        self.body.addWidget(
            explain(
                f"These files were used to produce the {display_name} you have "
                "just saved. Tick the ones to delete: nothing is ticked for you, "
                "and the saved volume is never touched."
            )
        )

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File", "Size", "What it is"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(lambda *_a: self._update_preview())
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.body.addWidget(self.tree, 1)

        self._fill()

        self.lbl_preview = QLabel("")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.body.addWidget(self.lbl_preview)

        row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete the ticked files")
        self.btn_delete.setObjectName("primaryButton")
        self.btn_delete.clicked.connect(self._delete)

        self.btn_keep = QPushButton("Keep everything")
        self.btn_keep.setObjectName("secondaryButton")
        self.btn_keep.clicked.connect(self.reject)

        row.addStretch(1)
        row.addWidget(self.btn_delete)
        row.addWidget(self.btn_keep)
        self.body.addLayout(row)

        self.size_like_electrode_list(2.6)
        self._update_preview()

    # ----------------------------------------------------------- le contenu
    def _fill(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()

        # Le fichier garde, en premier et sans case: il est la raison de
        # cette fenetre, et il ne doit pas pouvoir partir avec les autres.
        garde = QTreeWidgetItem(
            self.tree,
            [
                str(getattr(self.kept, "name", self.kept)),
                "",
                "kept: the volume you have just saved",
            ],
        )
        garde.setFlags(Qt.ItemIsEnabled)
        garde.setDisabled(True)

        for fichier in self.chain:
            nom = fichier.name
            quoi = fichier.label
            if fichier.is_folder:
                nom = nom + "\\"
                quoi = f"{quoi}, {fichier.file_count} file(s)"

            item = QTreeWidgetItem(self.tree, [nom, mf.human_size(fichier.size), quoi])
            item.setData(0, Qt.UserRole, fichier)
            item.setToolTip(0, str(fichier.path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)

        self.tree.blockSignals(False)

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
            "Nothing ticked: closing this window changes nothing."
            if not choisis
            else f"Will delete {len(choisis)} item(s), {mf.human_size(octets)}."
        )

    # ----------------------------------------------------------- l'execution
    def _delete(self) -> None:
        choisis = self._ticked()
        if not choisis:
            return

        lignes = [f"{len(choisis)} item(s) will be deleted:"]
        for fichier in choisis[:10]:
            lignes.append(f"  {fichier.name}   {mf.human_size(fichier.size)}")
        if len(choisis) > 10:
            lignes.append(f"  and {len(choisis) - 10} more")
        lignes.append("")
        lignes.append(
            "They go to the recycle bin when Windows allows it, and are removed "
            "for good otherwise."
        )
        lignes.append(
            f"The {self.display_name} of this project then points at the volume "
            "you have just saved."
        )

        if not NeuXelecMessageDialog.question(
            self,
            f"Clean up the {self.display_name} files",
            "\n".join(lignes),
            accept_text="Delete",
        ):
            return

        self.report = mf.delete_chosen(choisis, self.state, self.modality, self.kept)
        self._show_report(self.report)
        self.accept()

    def _show_report(self, rapport: dict) -> None:
        lignes = []
        if rapport["deleted"]:
            ou = "to the recycle bin" if rapport["recycle_bin"] else "for good"
            lignes.append(
                f"Deleted {len(rapport['deleted'])} item(s), "
                f"{mf.human_size(rapport['bytes'])}, {ou}."
            )
        if rapport["fields"]:
            lignes.append("")
            lignes.append(
                "Save the project so it records that this modality is now the "
                "volume you saved."
            )
        if rapport["failed"]:
            lignes.append("")
            lignes.append("Left alone:")
            for chemin, raison in rapport["failed"][:8]:
                lignes.append(f"  {chemin}: {raison}")

        if not lignes:
            return

        if rapport["failed"]:
            NeuXelecMessageDialog.warning(self, "Clean up", "\n".join(lignes))
        else:
            NeuXelecMessageDialog.information(self, "Clean up", "\n".join(lignes))
