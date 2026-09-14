from __future__ import annotations

"""Dialog to create a custom electrode reference (name + contacts + spacing).

Styled like the other NeuXelec dialogs (frameless rounded shell, rose accent,
SVG spin arrows). The created reference is persisted to the user's writable
references file so it is available on every subsequent launch.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
    QWidget,
)

from neuxelec.utils.resources import resource_path

from .brain_render_dialog import NeuXelecDialogHeader


class _ElectrodeSchematic(QWidget):
    """Simple dots-and-line preview of the electrode being defined.

    Contact 1 (deepest) is on the left. Connected contacts are filled (rose),
    unconnected contacts are hollow. Inter-contact distances are labelled above
    each segment, spaced proportionally so a variable-pitch shaft is visible.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(92)
        self._n = 0
        self._gaps: list[float] = []
        self._skip: set[int] = set()

    def set_layout(self, n_shaft: int, gaps, skip) -> None:
        self._n = int(n_shaft)
        self._gaps = [float(g) for g in gaps]
        self._skip = {int(s) for s in skip}
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        n = self._n
        if n < 2:
            return
        gaps = self._gaps if len(self._gaps) == n - 1 else [1.0] * (n - 1)
        pos = [0.0]
        for g in gaps:
            pos.append(pos[-1] + max(float(g), 0.01))
        total = pos[-1] or 1.0
        mx, my = 24.0, h / 2.0 + 4
        span = max(1.0, w - 2 * mx)
        xs = [mx + (px / total) * span for px in pos]

        p.setPen(QPen(QColor("#3A3D4A"), 2))
        p.drawLine(int(xs[0]), int(my), int(xs[-1]), int(my))

        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor("#9A9DAE"))
        for i, g in enumerate(gaps):
            xmid = (xs[i] + xs[i + 1]) / 2.0
            p.drawText(QRectF(xmid - 18, my - 26, 36, 12), Qt.AlignCenter, f"{g:.1f}")

        for i, x in enumerate(xs):
            connected = (i + 1) not in self._skip
            if connected:
                p.setBrush(QColor("#FF487D"))
                p.setPen(QPen(QColor("#FF487D"), 1))
            else:
                # Unconnected contacts: solid grey.
                p.setBrush(QColor("#6A6E7A"))
                p.setPen(QPen(QColor("#565A66"), 1))
            p.drawEllipse(QPointF(x, my), 5.0, 5.0)
            p.setPen(QColor("#CDD3DF"))
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(QRectF(x - 11, my + 9, 22, 12), Qt.AlignCenter, str(i + 1))
        p.end()

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
        self.setMinimumWidth(470)

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
        self.sp_contacts.setToolTip(
            "Total number of contacts physically present on the shaft "
            "(including any that are not connected)."
        )

        self.sp_spacing = QDoubleSpinBox()
        self.sp_spacing.setRange(0.1, 50.0)
        self.sp_spacing.setSingleStep(0.1)
        self.sp_spacing.setDecimals(2)
        self.sp_spacing.setValue(3.5)
        self.sp_spacing.setSuffix(" mm")

        self.le_skip = QLineEdit()
        self.le_skip.setPlaceholderText("e.g. 5, 8-9   (leave empty if all connected)")
        self.le_skip.setToolTip(
            "Hybrid electrodes (some DIXI models) have shaft contacts that are NOT "
            "connected / recorded.\nList their positions along the shaft, with "
            "contact 1 = the deepest.\nUse ranges like a print dialog: 5, 8-9, 12."
        )

        self.le_profile = QLineEdit()
        self.le_profile.setPlaceholderText("e.g. 7x2, 10x3.5   (leave empty for uniform)")
        self.le_profile.setToolTip(
            "For mixed-pitch electrodes (DIXI '...PIX'), the spacing changes along "
            "the shaft.\nGive the successive inter-contact distances from the "
            "deepest end, either as segments 'count x mm' (e.g. 7x2, 10x3.5) or an "
            "explicit list (2, 2, 2, 3.5, ...).\nThere must be exactly (contacts on "
            "the shaft - 1) values. Leave empty to use the uniform spacing above."
        )

        form.addRow("Reference name", self.le_name)
        form.addRow("Number of contacts (on the shaft)", self.sp_contacts)
        form.addRow("Spacing between contacts", self.sp_spacing)
        form.addRow("Variable spacing (optional)", self.le_profile)
        form.addRow("Unconnected contacts", self.le_skip)
        root.addLayout(form)

        preview_lbl = QLabel("Preview (contact 1 = deepest, distances in mm)")
        preview_lbl.setObjectName("subtle")
        root.addWidget(preview_lbl)
        self.schematic = _ElectrodeSchematic()
        root.addWidget(self.schematic)

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
        # Grey out the uniform spacing as soon as a variable profile is entered.
        self.le_profile.textChanged.connect(self._sync_spacing_enabled)
        self._sync_spacing_enabled()

        # Live preview schematic. A variable profile implies the shaft contact
        # count (n_shaft = number of gaps + 1), so entering one auto-fills it.
        self.sp_contacts.valueChanged.connect(self._update_schematic)
        self.sp_spacing.valueChanged.connect(self._update_schematic)
        self.le_profile.textChanged.connect(self._on_profile_changed)
        self.le_skip.textChanged.connect(self._update_schematic)
        self._update_schematic()

        self._apply_style()
        self.le_name.setFocus()

    def _sync_spacing_enabled(self) -> None:
        variable = bool(self.le_profile.text().strip())
        self.sp_spacing.setEnabled(not variable)
        self.sp_spacing.setToolTip(
            "Ignored while a variable spacing profile is set."
            if variable
            else ""
        )

    def _on_profile_changed(self) -> None:
        """When a valid variable profile is typed, derive the shaft contact count."""
        txt = self.le_profile.text().strip()
        if txt:
            try:
                profile = self._parse_profile(txt)
            except Exception:
                profile = []
            if profile:
                want = min(256, max(2, len(profile) + 1))
                if self.sp_contacts.value() != want:
                    self.sp_contacts.blockSignals(True)
                    self.sp_contacts.setValue(want)
                    self.sp_contacts.blockSignals(False)
        self._update_schematic()

    def _update_schematic(self) -> None:
        n = int(self.sp_contacts.value())
        try:
            profile = self._parse_profile(self.le_profile.text())
        except Exception:
            profile = []
        gaps = profile if len(profile) == n - 1 else [float(self.sp_spacing.value())] * (n - 1)
        try:
            skip = self._parse_positions(self.le_skip.text(), n)
        except Exception:
            skip = []
        self.schematic.set_layout(n, gaps, skip)

    def _apply_style(self) -> None:
        icon_dir = resource_path("resources/images")
        up = (icon_dir / "spin_up.svg").as_posix()
        down = (icon_dir / "spin_down.svg").as_posix()
        self.setStyleSheet(_QSS.replace("__SPIN_UP__", up).replace("__SPIN_DOWN__", down))

    @staticmethod
    def _parse_positions(text: str, n: int) -> list[int]:
        """Parse a print-dialog-style position list ('5, 8-9') into 1..n ints."""
        text = (text or "").strip()
        if not text:
            return []
        out: set[int] = set()
        for tok in text.replace(";", ",").split(","):
            tok = tok.strip()
            if not tok:
                continue
            if "-" in tok:
                a_s, b_s = tok.split("-", 1)
                a, b = int(a_s.strip()), int(b_s.strip())
                if a > b:
                    a, b = b, a
                out.update(range(a, b + 1))
            else:
                out.add(int(tok))
        for v in out:
            if v < 1 or v > n:
                raise ValueError(f"Contact position {v} is outside 1..{n}.")
        return sorted(out)

    @staticmethod
    def _parse_profile(text: str) -> list[float]:
        """Parse a spacing profile: 'count x mm' segments and/or an explicit list.

        Examples: '7x2, 10x3.5' -> [2]*7 + [3.5]*10 ; '2, 2, 3.5' -> [2, 2, 3.5].
        """
        text = (text or "").strip()
        if not text:
            return []
        out: list[float] = []
        for tok in text.replace("×", "x").replace(";", ",").split(","):
            tok = tok.strip()
            if not tok:
                continue
            if "x" in tok.lower():
                c_s, v_s = tok.lower().split("x", 1)
                count = int(c_s.strip())
                val = float(v_s.strip().replace(",", "."))
                if count < 1 or val <= 0:
                    raise ValueError("Segments must be positive, e.g. 7x2.")
                out.extend([val] * count)
            else:
                val = float(tok.replace(",", "."))
                if val <= 0:
                    raise ValueError("Spacing values must be positive.")
                out.append(val)
        return out

    def _on_validate(self) -> None:
        name = self.le_name.text().strip()
        if not name:
            self.err.setText("Please enter a reference name.")
            return
        if name.lower() == "other" or name.lower() in self._existing:
            self.err.setText("This reference name already exists.")
            return
        n = int(self.sp_contacts.value())
        try:
            skip = self._parse_positions(self.le_skip.text(), n)
        except ValueError as e:
            self.err.setText(str(e))
            return
        except Exception:
            self.err.setText(
                "Unconnected contacts: use positions like 5, 8-9 (1 = deepest)."
            )
            return
        if n - len(skip) < 2:
            self.err.setText("At least 2 contacts must remain connected.")
            return
        try:
            profile = self._parse_profile(self.le_profile.text())
        except ValueError as e:
            self.err.setText(str(e))
            return
        except Exception:
            self.err.setText("Variable spacing: use e.g. 7x2, 10x3.5 or 2, 2, 3.5.")
            return
        if profile and len(profile) != n - 1:
            self.err.setText(
                f"Variable spacing needs exactly {n - 1} values "
                f"({n} contacts on the shaft - 1); you gave {len(profile)}."
            )
            return
        self._skip = skip
        self._profile = profile
        self.accept()

    def values(self) -> tuple[str, int, float, list, list]:
        """Return (name, contacts on the shaft, spacing mm, unconnected, profile)."""
        return (
            self.le_name.text().strip(),
            int(self.sp_contacts.value()),
            float(self.sp_spacing.value()),
            list(getattr(self, "_skip", [])),
            list(getattr(self, "_profile", [])),
        )
