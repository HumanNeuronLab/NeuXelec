from __future__ import annotations

"""Dialog to create a custom electrode reference (name + contacts + spacing).

Styled like the other NeuXelec dialogs (frameless rounded shell, rose accent,
SVG spin arrows). The created reference is persisted to the user's writable
references file so it is available on every subsequent launch.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from neuxelec.utils.resources import resource_path

from .brain_render_dialog import NeuXelecDialogHeader

_QSS = """
QDialog {
    background: transparent;
}
QFrame#dialogShell {
    background-color: #06070D;
    border: 1.5px solid #FF487D;
    border-radius: 16px;
}
QFrame#customDialogHeader {
    background-color: transparent;
    border: none;
}
QPushButton#closeWindowButton {
    color: #D8DAE4;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#closeWindowButton:hover {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}
QLabel {
    color: #F2F2F5;
    background: transparent;
    border: none;
}
QLabel#dialogTitle {
    color: #F4D9D0;
    font-size: 18px;
    font-weight: 500;
    letter-spacing: 1px;
    padding-bottom: 2px;
}
QLabel#errLabel {
    color: #FF6B8A;
    font-size: 12px;
}
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #10121A;
    border: 1px solid #2B2D38;
    border-radius: 8px;
    color: #F2F2F5;
    padding: 6px 8px;
    padding-right: 27px;
    min-height: 20px;
    selection-background-color: #FF008F;
    font-size: 12px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #FF487D;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #3A3D4A;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 17px;
    background-color: #24262F;
    border: none;
    border-left: 1px solid #2B2D38;
    border-top-right-radius: 7px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 17px;
    background-color: #24262F;
    border: none;
    border-left: 1px solid #2B2D38;
    border-bottom-right-radius: 7px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #353844;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #191B22;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(__SPIN_UP__);
    width: 12px;
    height: 8px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(__SPIN_DOWN__);
    width: 12px;
    height: 8px;
}
QPushButton#cancelBtn {
    background-color: transparent;
    border: 1px solid #2B2D38;
    border-radius: 9px;
    color: #D8DAE4;
    padding: 7px 16px;
}
QPushButton#cancelBtn:hover {
    border: 1px solid #4A4D5C;
    color: #FFFFFF;
}
QPushButton#okBtn {
    border: none;
    border-radius: 9px;
    color: #FFFFFF;
    font-weight: 600;
    padding: 7px 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}
QPushButton#okBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF9420, stop:1 #FF33B4);
}
"""


class AddElectrodeRefDialog(QDialog):
    """Ask for a reference name, its number of contacts and inter-contact spacing."""

    def __init__(self, parent=None, existing_names=None):
        super().__init__(parent)
        self._existing = {str(n).strip().lower() for n in (existing_names or [])}

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setMinimumWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        outer.addWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(22, 6, 22, 20)
        root.setSpacing(12)

        root.addWidget(NeuXelecDialogHeader(self, parent=shell))

        title = QLabel("Add electrode reference")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.le_name = QLineEdit()
        self.le_name.setPlaceholderText("e.g. MyLab-08")

        self.sp_contacts = QSpinBox()
        self.sp_contacts.setRange(2, 256)
        self.sp_contacts.setValue(8)

        self.sp_spacing = QDoubleSpinBox()
        self.sp_spacing.setRange(0.1, 50.0)
        self.sp_spacing.setSingleStep(0.1)
        self.sp_spacing.setDecimals(2)
        self.sp_spacing.setValue(3.5)
        self.sp_spacing.setSuffix(" mm")

        form.addRow("Reference name", self.le_name)
        form.addRow("Number of contacts", self.sp_contacts)
        form.addRow("Spacing between contacts", self.sp_spacing)
        root.addLayout(form)

        self.err = QLabel("")
        self.err.setObjectName("errLabel")
        self.err.setWordWrap(True)
        root.addWidget(self.err)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_ok = QPushButton("Validate")
        self.btn_ok.setObjectName("okBtn")
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_validate)
        self.le_name.returnPressed.connect(self._on_validate)

        self._apply_style()
        self.le_name.setFocus()

    def _apply_style(self) -> None:
        icon_dir = resource_path("resources/images")
        up = (icon_dir / "spin_up.svg").as_posix()
        down = (icon_dir / "spin_down.svg").as_posix()
        self.setStyleSheet(_QSS.replace("__SPIN_UP__", up).replace("__SPIN_DOWN__", down))

    def _on_validate(self) -> None:
        name = self.le_name.text().strip()
        if not name:
            self.err.setText("Please enter a reference name.")
            return
        if name.lower() == "other" or name.lower() in self._existing:
            self.err.setText("This reference name already exists.")
            return
        self.accept()

    def values(self) -> tuple[str, int, float]:
        """Return (reference name, number of contacts, spacing in mm)."""
        return (
            self.le_name.text().strip(),
            int(self.sp_contacts.value()),
            float(self.sp_spacing.value()),
        )
