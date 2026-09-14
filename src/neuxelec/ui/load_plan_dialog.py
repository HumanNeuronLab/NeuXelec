from __future__ import annotations

"""Dialog shown after reading a NeuroInspire ``.nip`` implantation plan.

Styled like the other NeuXelec dialogs (frameless rounded shell, rose accent).
It lists the planned trajectories and asks how to bring the plan coordinates
into MRI 1 space:

* MRI 1 *is* the planning MRI (detected from the SeriesInstanceUID, or stated by
  the user)  -> coordinates used directly;
* otherwise the user points to the planning MRI (DICOM folder or NIfTI) and a
  rigid registration onto MRI 1 is run by the caller.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .brain_render_dialog import NeuXelecDialogHeader

_QSS = """
QDialog { background: transparent; }
QFrame#dialogShell {
    background-color: #06070D;
    border: 1.5px solid #FF487D;
    border-radius: 16px;
}
QFrame#customDialogHeader { background-color: transparent; border: none; }
QPushButton#closeWindowButton {
    color: #D8DAE4; background-color: transparent; border: 1px solid transparent;
    border-radius: 8px; font-size: 16px; font-weight: 700;
}
QPushButton#closeWindowButton:hover {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}
QLabel { color: #F2F2F5; background: transparent; border: none; }
QLabel#dialogTitle { color: #F4D9D0; font-size: 18px; font-weight: 500; letter-spacing: 1px; padding-bottom: 2px; }
QLabel#subtle { color: #9A9DAE; font-size: 12px; }
QLabel#okLabel { color: #7CE38B; font-size: 12px; }
QLabel#warnLabel { color: #FFB454; font-size: 12px; }
QLabel#errLabel { color: #FF6B8A; font-size: 12px; }
QLineEdit {
    background-color: #10121A; border: 1px solid #2B2D38; border-radius: 8px;
    color: #F2F2F5; padding: 6px 8px; min-height: 20px; font-size: 12px;
    selection-background-color: #FF008F;
}
QLineEdit:focus { border: 1px solid #FF487D; }
QCheckBox { color: #F2F2F5; font-size: 12px; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #3A3D4A; background: #10121A; }
QCheckBox::indicator:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0); border: 1px solid #FF487D; }
QTableWidget {
    background-color: #0B0D15; alternate-background-color: #10121A; color: #F2F2F5;
    border: 1px solid #2B2D38; border-radius: 8px; gridline-color: #1E2029; font-size: 12px;
    selection-background-color: #3A1F33;
}
QHeaderView::section {
    background-color: #151722; color: #C9CBD8; border: none; border-bottom: 1px solid #2B2D38;
    padding: 5px 6px; font-size: 11px; font-weight: 600;
}
QTableCornerButton::section { background-color: #151722; border: none; }
QPushButton#cancelBtn {
    background-color: transparent; border: 1px solid #2B2D38; border-radius: 9px;
    color: #D8DAE4; padding: 7px 16px;
}
QPushButton#cancelBtn:hover { border: 1px solid #4A4D5C; color: #FFFFFF; }
QPushButton#browseBtn {
    background-color: transparent; border: 1px solid #FF487D; border-radius: 9px;
    color: #F2F2F5; padding: 6px 12px;
}
QPushButton#browseBtn:hover { background-color: #1A0F17; }
QPushButton#okBtn {
    border: none; border-radius: 9px; color: #FFFFFF; font-weight: 600; padding: 7px 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}
QPushButton#okBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF9420, stop:1 #FF33B4); }
QPushButton#okBtn:disabled { background: #2B2D38; color: #7A7D8C; }
"""


class LoadPlanDialog(QDialog):
    """Show the plan and let the user choose how coordinates reach MRI 1 space."""

    def __init__(self, plan: dict, parent=None, mri1_uid: str | None = None, mri1_label: str = "MRI 1",
                 start_dir: str | None = None):
        super().__init__(parent)
        self._plan = plan
        self._start_dir = start_dir or ""
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setMinimumWidth(680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("dialogShell")
        outer.addWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(22, 6, 22, 20)
        root.setSpacing(10)
        root.addWidget(NeuXelecDialogHeader(self, parent=shell))

        title = QLabel("Import implantation plan")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        info = plan.get("plan_info", {}) or {}
        cs = plan.get("coordinate_system", {}) or {}
        ref_name = cs.get("reference_series_name") or "unknown series"
        ref_uid = cs.get("reference_series_uid") or ""
        n = plan.get("n_trajectories", len(plan.get("trajectories", []) or []))
        head = QLabel(
            f"{plan.get('source', 'Plan')} {info.get('software_version') or ''}  ·  "
            f"patient {info.get('patient_id') or '?'}  ·  planned {str(info.get('created') or '')[:10]}  ·  "
            f"{n} trajectories"
        )
        head.setObjectName("subtle")
        head.setWordWrap(True)
        root.addWidget(head)
        ref_lbl = QLabel(f"Coordinates are in the space of the planning MRI:  {ref_name}")
        ref_lbl.setWordWrap(True)
        root.addWidget(ref_lbl)
        uid_lbl = QLabel(f"SeriesInstanceUID  {ref_uid}")
        uid_lbl.setObjectName("subtle")
        uid_lbl.setWordWrap(True)
        root.addWidget(uid_lbl)

        # ---- trajectories table ----
        trajs = plan.get("trajectories", []) or []
        table = QTableWidget(len(trajs), 5)
        table.setHorizontalHeaderLabels(["Electrode", "Reference", "Contacts", "Length (mm)", "Hemisphere"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.NoFocus)
        for r, t in enumerate(trajs):
            x = float(t.get("entry_mm", [0, 0, 0])[0])
            hemi = "L" if x > 5 else ("R" if x < -5 else "?")
            cells = [
                t.get("name", ""),
                t.get("reference_key") or t.get("reference") or "?",
                str(t.get("contact_count") or "?"),
                f"{float(t.get('length_mm') or 0):.1f}",
                hemi,
            ]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(Qt.AlignCenter if c else Qt.AlignVCenter | Qt.AlignLeft)
                table.setItem(r, c, it)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        table.setMinimumHeight(min(60 + 24 * max(1, len(trajs)), 300))
        root.addWidget(table)

        # ---- coordinate space ----
        self._auto_match = bool(mri1_uid and ref_uid and mri1_uid.strip() == ref_uid.strip())
        if self._auto_match:
            st = QLabel(f"✓  {mri1_label} is the planning MRI (same SeriesInstanceUID). Coordinates will be used directly.")
            st.setObjectName("okLabel")
            st.setWordWrap(True)
            root.addWidget(st)
        else:
            st = QLabel(
                f"{mri1_label} does not match the planning series"
                + (" (no DICOM UID available)." if not mri1_uid else ".")
                + " Choose how to bring the plan into MRI 1 space:"
            )
            st.setObjectName("warnLabel")
            st.setWordWrap(True)
            root.addWidget(st)

        self.chk_same = QCheckBox(f"{mri1_label} IS the planning MRI (use the coordinates directly)")
        self.chk_same.setChecked(self._auto_match)
        self.chk_same.setVisible(not self._auto_match)
        root.addWidget(self.chk_same)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.le_mri = QLineEdit()
        self.le_mri.setPlaceholderText("Planning MRI (DICOM folder or NIfTI), rigidly registered onto MRI 1")
        self.le_mri.setReadOnly(True)
        self.btn_browse_file = QPushButton("NIfTI…")
        self.btn_browse_file.setObjectName("browseBtn")
        self.btn_browse_file.setCursor(Qt.PointingHandCursor)
        self.btn_browse_dir = QPushButton("DICOM folder…")
        self.btn_browse_dir.setObjectName("browseBtn")
        self.btn_browse_dir.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.le_mri, 1)
        row.addWidget(self.btn_browse_file)
        row.addWidget(self.btn_browse_dir)
        self._row_widgets = [self.le_mri, self.btn_browse_file, self.btn_browse_dir]
        root.addLayout(row)
        for w in self._row_widgets:
            w.setVisible(not self._auto_match)

        self.err = QLabel("")
        self.err.setObjectName("errLabel")
        self.err.setWordWrap(True)
        root.addWidget(self.err)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_ok = QPushButton("Import plan")
        self.btn_ok.setObjectName("okBtn")
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_validate)
        self.btn_browse_file.clicked.connect(self._browse_file)
        self.btn_browse_dir.clicked.connect(self._browse_dir)
        self.chk_same.toggled.connect(self._on_same_toggled)
        self.setStyleSheet(_QSS)
        self._on_same_toggled(self.chk_same.isChecked())

    # ------------------------------------------------------------------ slots
    def _on_same_toggled(self, checked: bool) -> None:
        for w in self._row_widgets:
            w.setEnabled(not checked)
        self.err.setText("")

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Planning MRI (NIfTI)", self._start_dir, "NIfTI image (*.nii *.nii.gz);;All files (*.*)"
        )
        if path:
            self.le_mri.setText(path)
            self.err.setText("")

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Planning MRI (DICOM folder)", self._start_dir)
        if path:
            self.le_mri.setText(path)
            self.err.setText("")

    def _on_validate(self) -> None:
        if self._auto_match or self.chk_same.isChecked():
            self.accept()
            return
        if not self.le_mri.text().strip():
            self.err.setText("Select the planning MRI, or tick the box if MRI 1 is the planning MRI.")
            return
        self.accept()

    # ------------------------------------------------------------------ result
    def values(self) -> dict:
        """``{"mode": "identity" | "register", "planning_mri_path": str | None}``"""
        if self._auto_match or self.chk_same.isChecked():
            return {"mode": "identity", "planning_mri_path": None}
        return {"mode": "register", "planning_mri_path": self.le_mri.text().strip() or None}
