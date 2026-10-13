"""Make a patient folder readable again, without touching the data.

The window shows the folder in three groups, with a size on every line,
and nothing happens before the user has seen exactly what will happen.
The groups come from :mod:`neuxelec.utils.folder_tidy`, which decides by
an allow-list of the names NeuXelec itself writes: what it does not
recognise is yours, and yours is displayed greyed out and unselectable.

Moving is the default because the stated problem is a folder one cannot
read any more, not a disk one cannot fill. A move is undone with a drag,
a deletion is not, so deletion is offered only for what nothing points
at any more.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..utils import folder_tidy as tidy
from .neuxelec_dialog import MUTED, NeuXelecDialog, explain
from .neuxelec_message_dialog import NeuXelecMessageDialog

#: Au-dela, le groupe de vos fichiers se resume au lieu de s'etaler. Une
#: serie DICOM compte volontiers cinq mille coupes, et cinq mille lignes
#: ne disent rien de plus que leur total. Les deux autres groupes ne sont
#: pas plafonnes: NeuXelec ecrit quelques fichiers par modalite, et il
#: faut pouvoir decocher chacun.
LIGNES_MAX_SOURCE = 200

#: Ce que chaque groupe dit, et ce qu'on y fait.
GROUPES = (
    (
        tidy.SOURCE,
        "Yours. Never moved, never deleted",
        "listed only so you can see where the volume goes",
        "DICOM folders, the images you imported, anything NeuXelec did not "
        "write. Listed with their size so you can see where the volume goes.",
    ),
    (
        tidy.USED,
        "Made by NeuXelec, still used by the project",
        f"ticked files move into {tidy.DEFAULT_SUBFOLDER}/",
        "Ticked files move into the subfolder below, and the project is "
        "pointed at their new place straight away.",
    ),
    (
        tidy.ORPHAN,
        "Made by NeuXelec, nothing uses them any more",
        "ticked files are deleted",
        "Superseded ANTs output, the result of a registration that was run "
        "again. Ticked files are deleted, through the recycle bin when "
        "Windows allows it.",
    ),
)


class FolderTidyDialog(NeuXelecDialog):
    """Le rangement d'un dossier patient, en trois groupes."""

    def __init__(self, folder, state, parent=None):
        super().__init__(
            "Tidy up the patient folder",
            str(folder),
            parent=parent,
        )
        self.folder = Path(folder)
        self.state = state
        self._entries: list[tidy.Entry] = []

        self.body.addWidget(
            explain(
                "NeuXelec only ever proposes what it wrote itself. Everything "
                "else is yours and stays where it is."
            )
        )

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File", "Size", "Why"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.body.addWidget(self.tree, 1)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.body.addWidget(self.lbl_preview)

        row = QHBoxLayout()
        self.btn_refresh = QPushButton("Rescan")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.clicked.connect(self.rescan)

        self.btn_apply = QPushButton("Tidy up")
        self.btn_apply.setObjectName("primaryButton")
        self.btn_apply.clicked.connect(self._apply)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("secondaryButton")
        self.btn_close.clicked.connect(self.accept)

        row.addWidget(self.btn_refresh)
        row.addStretch(1)
        row.addWidget(self.btn_apply)
        row.addWidget(self.btn_close)
        self.body.addLayout(row)

        self.size_like_electrode_list(3.0)
        self.rescan()

    # ----------------------------------------------------------- le contenu
    def rescan(self) -> None:
        """Relire le dossier et reconstruire les trois groupes.

        Un dossier pose sur un partage reseau se parcourt en quelques
        secondes: le curseur le dit plutot que de laisser croire a un
        blocage.
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._entries = tidy.scan(self.folder, self.state)
        finally:
            QApplication.restoreOverrideCursor()
        comptes = tidy.totals(self._entries)

        self.tree.blockSignals(True)
        self.tree.clear()

        for categorie, titre, resume, aide in GROUPES:
            lot = [e for e in self._entries if e.category == categorie]
            compte = comptes.get(categorie, {"files": 0, "bytes": 0})
            groupe = QTreeWidgetItem(
                self.tree,
                [
                    f"{titre}  ({compte['files']})",
                    tidy.human_size(compte["bytes"]),
                    resume,
                ],
            )
            for colonne in range(3):
                groupe.setToolTip(colonne, aide)
            groupe.setExpanded(categorie != tidy.SOURCE)

            montres = lot
            if categorie == tidy.SOURCE and len(lot) > LIGNES_MAX_SOURCE:
                montres = lot[:LIGNES_MAX_SOURCE]

            for entry in montres:
                item = QTreeWidgetItem(
                    groupe,
                    [
                        self._display_name(entry),
                        tidy.human_size(entry.size),
                        entry.reason,
                    ],
                )
                item.setData(0, Qt.UserRole, entry)
                if entry.category == tidy.SOURCE:
                    # Pas de case: ce qui ne peut pas etre choisi ne doit
                    # pas avoir l'air de pouvoir l'etre.
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setDisabled(True)
                else:
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(
                        0,
                        Qt.Checked if entry.category == tidy.ORPHAN else Qt.Unchecked,
                    )

            reste = lot[len(montres):]
            if reste:
                octets = sum(int(e.size) for e in reste)
                resumee = QTreeWidgetItem(
                    groupe,
                    [
                        f"and {len(reste)} more file(s)",
                        tidy.human_size(octets),
                        "a DICOM series says no more in five thousand lines "
                        "than in its total",
                    ],
                )
                resumee.setFlags(Qt.ItemIsEnabled)
                resumee.setDisabled(True)

        self.tree.blockSignals(False)
        self._update_preview()

    def _display_name(self, entry: tidy.Entry) -> str:
        try:
            return str(entry.path.relative_to(self.folder))
        except ValueError:
            return str(entry.path)

    # ----------------------------------------------------------- le resume
    def _checked(self) -> tuple[list, list]:
        """(a deplacer, a supprimer), tels que les cases le disent."""
        move: list = []
        delete: list = []
        racine = self.tree.invisibleRootItem()
        for g in range(racine.childCount()):
            groupe = racine.child(g)
            for i in range(groupe.childCount()):
                item = groupe.child(i)
                entry = item.data(0, Qt.UserRole)
                if entry is None or item.checkState(0) != Qt.Checked:
                    continue
                if entry.category == tidy.ORPHAN:
                    delete.append(entry.path)
                elif entry.category == tidy.USED:
                    move.append(entry.path)
        return move, delete

    def _on_item_changed(self, *_args) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        move, delete = self._checked()
        moves, deletions, _refused = tidy.plan(self._entries, self.folder, move, delete)

        octets_deplaces = sum(int(e.size) for e, _d in moves)
        octets_supprimes = sum(int(e.size) for e in deletions)

        morceaux = []
        if moves:
            morceaux.append(
                f"move {len(moves)} file(s), {tidy.human_size(octets_deplaces)}, "
                f"into {tidy.DEFAULT_SUBFOLDER}/"
            )
        if deletions:
            morceaux.append(
                f"delete {len(deletions)} file(s), {tidy.human_size(octets_supprimes)}"
            )

        self.btn_apply.setEnabled(bool(morceaux))
        self.lbl_preview.setText(
            "Nothing selected." if not morceaux else "Will " + ", and ".join(morceaux) + "."
        )

    # ----------------------------------------------------------- l'execution
    def _apply(self) -> None:
        move, delete = self._checked()
        moves, deletions, refused = tidy.plan(self._entries, self.folder, move, delete)

        if not moves and not deletions:
            return

        lignes = []
        if moves:
            lignes.append(f"{len(moves)} file(s) move into {tidy.DEFAULT_SUBFOLDER}/.")
            lignes.append("The project is pointed at their new place.")
        if deletions:
            lignes.append(f"{len(deletions)} file(s) are deleted.")
            lignes.append(
                "They go to the recycle bin when Windows allows it, and are "
                "removed for good otherwise."
            )
        if refused:
            lignes.append("")
            lignes.append(f"{len(refused)} selection(s) will not be acted on:")
            for entry, raison in refused[:5]:
                lignes.append(f"  {entry.path.name}: {raison}")

        if not NeuXelecMessageDialog.question(
            self._dialog_parent(),
            "Tidy up the patient folder",
            "\n".join(lignes),
            accept_text="Tidy up",
        ):
            return

        rapport = tidy.apply_plan(moves, deletions, self.state)
        self._show_report(rapport)
        self.rescan()

    def _dialog_parent(self):
        return self

    def _show_report(self, rapport: dict) -> None:
        lignes = []
        if rapport["moved"]:
            lignes.append(
                f"Moved {len(rapport['moved'])} file(s), "
                f"{tidy.human_size(rapport['bytes_moved'])}."
            )
        if rapport["deleted"]:
            ou = "to the recycle bin" if rapport["recycle_bin"] else "for good"
            lignes.append(
                f"Deleted {len(rapport['deleted'])} file(s), "
                f"{tidy.human_size(rapport['bytes_deleted'])}, {ou}."
            )
        if rapport["fields"]:
            lignes.append("")
            lignes.append(
                "The session now points at the new locations. Save the project "
                "to record them."
            )
        if rapport["failed"]:
            lignes.append("")
            lignes.append("Left alone:")
            for chemin, raison in rapport["failed"][:8]:
                lignes.append(f"  {Path(chemin).name}: {raison}")

        if not lignes:
            return

        if rapport["failed"]:
            NeuXelecMessageDialog.warning(self, "Tidy up", "\n".join(lignes))
        else:
            NeuXelecMessageDialog.information(self, "Tidy up", "\n".join(lignes))
