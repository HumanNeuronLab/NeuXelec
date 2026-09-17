"""Ask the user where the project's missing files went.

Opened only when a file the project actually needs could not be found by
:mod:`neuxelec.project_paths`. Everything the cascade resolved on its own is
already bound by then, so this window lists what is left: usually one line, or
one line per folder that moved.

The window follows the NeuXelec frameless style used by the file assignment
dialog: no native title bar, rose border, the app's own scrollbar.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..project_paths import (
    Resolution,
    ResolutionReport,
    relocate_into_folder,
    set_manual_path,
)

#: Every image format the file pickers offer, so relocating never fights the
#: filter. Surfaces and transforms are in there too.
_FILE_FILTER = (
    "Project files (*.nii *.nii.gz *.mgz *.mgh *.nrrd *.nhdr *.mha *.mat *.pial *.gii);;"
    "All files (*.*)"
)


class _RelocateHeader(QFrame):
    """Frameless NeuXelec header, draggable, with the close button."""

    def __init__(self, dialog: QDialog, parent=None):
        super().__init__(parent)
        self.dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setObjectName("customDialogHeader")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        self.btn_close_window = QPushButton("✕")
        self.btn_close_window.setObjectName("closeWindowButton")
        self.btn_close_window.setCursor(Qt.PointingHandCursor)
        self.btn_close_window.setFixedSize(30, 30)
        self.btn_close_window.clicked.connect(self.dialog.reject)
        layout.addWidget(self.btn_close_window, 0, Qt.AlignRight | Qt.AlignTop)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and bool(event.buttons() & Qt.LeftButton):
            self.dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class RelocateFilesDialog(QDialog):
    """One row per file the project needs and nobody could find."""

    def __init__(
        self,
        report: ResolutionReport,
        parent=None,
        *,
        offer_project_update: bool = True,
    ):
        super().__init__(parent)
        self.report = report
        self._rows: list[tuple[Resolution, QLabel, QPushButton]] = []
        self._positioned_once = False
        self._last_browse_dir = str(Path(report.project_path).parent)
        self._offer_project_update = bool(offer_project_update)

        self.setWindowTitle("Files not found")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setSizeGripEnabled(False)
        self.setMinimumSize(620, 320)

        self._build_ui()
        self._apply_style()
        self._refresh()
        self._set_adapted_initial_size()

    # -- building ---------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.dialog_shell = QFrame()
        self.dialog_shell.setObjectName("dialogShell")
        outer.addWidget(self.dialog_shell)

        root = QVBoxLayout(self.dialog_shell)
        root.setContentsMargins(14, 8, 14, 14)
        root.setSpacing(10)

        self.custom_header = _RelocateHeader(self)
        root.addWidget(self.custom_header)

        self.lbl_title = QLabel("FILES NOT FOUND")
        self.lbl_title.setObjectName("dialogTitle")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(
            "These files are no longer where the project expects them. "
            "Point NeuXelec at one of them and the others in the same folder follow."
        )
        self.lbl_subtitle.setObjectName("dialogSubtitle")
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle.setWordWrap(True)
        root.addWidget(self.lbl_subtitle)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("assignmentScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("assignmentScrollContent")
        grid = QGridLayout(self.scroll_content)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        for column, text in enumerate(("WHAT", "FILE", "STATUS", "")):
            header = QLabel(text)
            header.setObjectName("columnHeader")
            grid.addWidget(header, 0, column)

        for row, resolution in enumerate(self._listed_resolutions(), start=1):
            what = QLabel(resolution.entry.describe())
            what.setObjectName("whatLabel")
            what.setMinimumHeight(34)

            name = QLabel(resolution.entry.name)
            name.setObjectName("fileNameLabel")
            name.setToolTip(resolution.entry.stored)
            name.setMinimumHeight(34)

            status = QLabel()
            status.setWordWrap(False)
            status.setMinimumHeight(34)

            button = QPushButton("Locate…")
            button.setObjectName("secondaryButton")
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(34)
            button.setMinimumWidth(96)
            button.clicked.connect(lambda _checked=False, r=resolution: self._locate(r))

            grid.addWidget(what, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(status, row, 2)
            grid.addWidget(button, row, 3)
            self._rows.append((resolution, status, button))

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 4)
        grid.setColumnStretch(3, 0)
        grid.setRowStretch(len(self._rows) + 1, 1)

        self.scroll_area.setWidget(self.scroll_content)
        root.addWidget(self.scroll_area, 1)

        self.lbl_footer = QLabel()
        self.lbl_footer.setObjectName("dialogFooter")
        self.lbl_footer.setAlignment(Qt.AlignCenter)
        self.lbl_footer.setWordWrap(True)
        root.addWidget(self.lbl_footer)

        self.chk_update_project = QCheckBox("Save the new locations in the project file")
        self.chk_update_project.setObjectName("updateProjectCheck")
        self.chk_update_project.setCursor(Qt.PointingHandCursor)
        self.chk_update_project.setChecked(True)
        self.chk_update_project.setVisible(self._offer_project_update)
        root.addWidget(self.chk_update_project, 0, Qt.AlignCenter)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(12, 0, 12, 4)
        buttons.setSpacing(10)

        self.btn_locate_folder = QPushButton("Search a folder…")
        self.btn_locate_folder.setObjectName("secondaryButton")
        self.btn_locate_folder.setCursor(Qt.PointingHandCursor)
        self.btn_locate_folder.setMinimumHeight(42)
        self.btn_locate_folder.setMinimumWidth(150)
        self.btn_locate_folder.setToolTip("Look for every missing file under a folder you choose.")
        self.btn_locate_folder.clicked.connect(self._locate_folder)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setMinimumWidth(112)
        self.btn_cancel.setToolTip("Do not open this project.")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_open = QPushButton("Open")
        self.btn_open.setObjectName("primaryButton")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.setMinimumHeight(42)
        self.btn_open.setMinimumWidth(130)
        self.btn_open.clicked.connect(self.accept)

        buttons.addWidget(self.btn_locate_folder)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_open)
        root.addLayout(buttons)

        self.resize_grip = QSizeGrip(self.dialog_shell)
        self.resize_grip.setObjectName("dialogResizeGrip")
        self.resize_grip.setFixedSize(16, 16)
        self.resize_grip.raise_()

    def _listed_resolutions(self) -> list[Resolution]:
        """What nobody found and the user could actually go and find.

        Essentials first. Files that belong to the installation rather than to
        the patient, such as the MNI template, are left out: asking the user to
        locate those would be asking for a file that is not theirs.
        """
        missing = [r for r in self.report.resolutions if not r.found and r.entry.user_locatable]
        return sorted(missing, key=lambda r: (not r.entry.essential, r.entry.section))

    # -- state ------------------------------------------------------------

    def _refresh(self) -> None:
        for resolution, status, button in self._rows:
            status.setText(self._status_text(resolution))
            status.setObjectName(self._status_style(resolution))
            status.setToolTip(resolution.resolved or resolution.candidate or "")
            button.setText("Change…" if resolution.found else "Locate…")
            # Re-apply the sheet so the new objectName takes effect.
            status.style().unpolish(status)
            status.style().polish(status)

        remaining = len(self.report.missing_essential)
        relocated = len(self.report.relocated)

        notes = []
        if relocated:
            notes.append(
                f"{relocated} other file{'s' if relocated > 1 else ''} " "relocated automatically."
            )
        if remaining:
            notes.append(
                f"{remaining} file{'s' if remaining > 1 else ''} still missing: "
                "the matching features will be unavailable."
            )
        self.lbl_footer.setText("  ".join(notes))
        self.btn_open.setText("Open" if not remaining else "Open anyway")

    def _status_text(self, resolution: Resolution) -> str:
        if resolution.found:
            folder = os.path.dirname(str(resolution.resolved))
            if resolution.verified is False:
                return f"Replaced · {folder}"
            if resolution.verified is None:
                return f"Found, not verified · {folder}"
            return f"Found · {folder}"
        if resolution.candidate:
            return "A different file of this name was found"
        return f"Not found · was in {resolution.entry.folder or 'an unknown folder'}"

    def _status_style(self, resolution: Resolution) -> str:
        if resolution.found:
            return "statusOk" if resolution.verified is not False else "statusWarn"
        return "statusWarn" if resolution.candidate else "statusBad"

    # -- actions ----------------------------------------------------------

    def _locate(self, resolution: Resolution) -> None:
        want_dir = bool((resolution.entry.fingerprint or {}).get("dir"))
        start = resolution.candidate or self._last_browse_dir

        if want_dir:
            chosen = QFileDialog.getExistingDirectory(
                self, f"Locate {resolution.entry.describe()}", start
            )
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                f"Locate {resolution.entry.name}",
                str(Path(start) / resolution.entry.name) if os.path.isdir(start) else start,
                _FILE_FILTER,
            )

        if not chosen:
            return
        self._last_browse_dir = os.path.dirname(str(chosen)) or self._last_browse_dir
        set_manual_path(self.report, resolution, str(chosen))
        self._refresh()

    def _locate_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Search for the project files in", self._last_browse_dir
        )
        if not folder:
            return
        self._last_browse_dir = folder
        relocate_into_folder(self.report, folder)
        self._refresh()

    @property
    def update_project_requested(self) -> bool:
        return bool(self._offer_project_update and self.chk_update_project.isChecked())

    # -- geometry ---------------------------------------------------------

    def _set_adapted_initial_size(self) -> None:
        rows = max(1, len(self._rows))
        try:
            screen = self.parentWidget().screen() if self.parentWidget() else None
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            available = screen.availableGeometry() if screen is not None else None
            max_width = max(620, int(available.width()) - 140) if available else 1200
            max_height = max(320, int(available.height()) - 140) if available else 800
        except Exception:
            max_width, max_height = 1200, 800

        preferred_height = min(max(360, 300 + 44 * rows), int(max_height * 0.82))
        self.resize(min(940, max_width), preferred_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        try:
            margin = 4
            self.resize_grip.move(
                self.dialog_shell.width() - self.resize_grip.width() - margin,
                self.dialog_shell.height() - self.resize_grip.height() - margin,
            )
            self.resize_grip.raise_()
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._positioned_once:
            return
        self._positioned_once = True
        try:
            parent = self.parentWidget()
            screen = parent.screen() if parent is not None else self.screen()
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            geometry = self.frameGeometry()
            if parent is not None:
                geometry.moveCenter(parent.frameGeometry().center())
            elif screen is not None:
                geometry.moveCenter(screen.availableGeometry().center())
            self.move(geometry.topLeft())
        except Exception:
            pass

    # -- style ------------------------------------------------------------

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QDialog { background: transparent; }
            QFrame#dialogShell {
                background-color: #06070D;
                border: 1.5px solid #FF487D;
                border-radius: 16px;
            }
            QFrame#customDialogHeader { background: transparent; border: none; }
            QPushButton#closeWindowButton {
                color: #D8DAE4;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton#closeWindowButton:hover {
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
            }
            QLabel { color: #F2F2F5; background: transparent; border: none; }
            QLabel#dialogTitle {
                color: #F4D9D0;
                font-size: 18px;
                font-weight: 600;
                letter-spacing: 1px;
            }
            QLabel#dialogSubtitle { color: #9398A8; font-size: 12px; }
            QLabel#dialogFooter { color: #717786; font-size: 11px; }
            QLabel#columnHeader {
                color: #717786;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#whatLabel { color: #F2F2F5; font-size: 12px; font-weight: 600; }
            QLabel#fileNameLabel {
                color: #D5D7E1;
                background-color: #10121A;
                border: 1px solid #242734;
                border-radius: 8px;
                padding-left: 10px;
                padding-right: 10px;
            }
            QLabel#statusOk { color: #4ED07A; font-size: 11px; }
            QLabel#statusWarn { color: #FFA23A; font-size: 11px; }
            QLabel#statusBad { color: #FF6B8A; font-size: 11px; }
            /* Copied from MainWindow.ui so the box is the app's own checkbox. */
            QCheckBox#updateProjectCheck { color: #9398A8; font-size: 11px; spacing: 8px; }
            QCheckBox#updateProjectCheck::indicator {
                width: 16px;
                height: 16px;
                background-color: #151720;
                border: 1px solid #353844;
                border-radius: 4px;
            }
            QCheckBox#updateProjectCheck::indicator:hover {
                border: 1px solid #FF487D;
            }
            QCheckBox#updateProjectCheck::indicator:checked {
                border: 1px solid #FF487D;
                background-color: #151720;
                image: url(resources/images/neuxelec_checkbox_cross.svg);
            }
            QCheckBox#updateProjectCheck::indicator:checked:hover {
                border: 1px solid #FF487D;
                background-color: #181A24;
                image: url(resources/images/neuxelec_checkbox_cross.svg);
            }
            QScrollArea#assignmentScrollArea,
            QWidget#assignmentScrollContent {
                background: transparent;
                border: none;
            }
            QPushButton#secondaryButton,
            QPushButton#primaryButton {
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                padding-left: 18px;
                padding-right: 18px;
            }
            QPushButton#secondaryButton {
                color: white;
                background-color: #17181F;
                border: 1px solid #2B2D38;
            }
            QPushButton#secondaryButton:hover {
                background-color: #20222B;
                border: 1px solid #FF487D;
            }
            QPushButton#primaryButton {
                color: white;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
            }
            QPushButton#primaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF922B, stop:1 #FF33B8);
            }
            QScrollBar:vertical {
                background-color: transparent;
                border: none;
                width: 10px;
                margin: 5px 2px 5px 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                min-height: 28px;
                background-color: #3B3E48;
                border: 1px solid #FF487D;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0px; border: none; background: transparent; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: transparent; border: none; }
            QSizeGrip#dialogResizeGrip { background: transparent; border: none; image: none; }
            """)
