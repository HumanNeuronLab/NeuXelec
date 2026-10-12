"""Show how the recording's channels were bound to the reconstructed electrodes.

Shown once, when a folder of TRC files is first opened, and again only when the
folder changes or the user asks. It exists because this is the one step of the
EEG reader that can be wrong without looking wrong: a trace labelled with an
electrode in the hippocampus, coming from another shaft entirely.

What it puts in front of someone, per electrode, is the count of BIPOLAR PAIRS
rather than the count of contacts. SEEG is read bipolar, and one contact
missing in the middle of a shaft costs two pairs, which is the number that
decides whether the recording is usable for that electrode.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..utils.eeg_channel_match import MatchReport, bind
from .neuxelec_dialog import BAD, MUTED, OK, WARN, NeuXelecDialog, card, section

_NONE = "none"


class EegMatchDialog(NeuXelecDialog):
    """Review, correct and accept the channel mapping."""

    def __init__(self, report: MatchReport, trc_channels: list[str], folder: str, parent=None):
        super().__init__("EEG channels", folder, parent)
        self.resize(1000, 700)
        self._report = report
        self._channels = list(trc_channels)

        prefixes = sorted(
            {e.trc_prefix for e in report.electrodes if e.trc_prefix}
            | set(report.unused_trc_prefixes)
        )
        self._prefixes = [_NONE] + prefixes

        frame, inside = card()
        inside.addWidget(section("each reconstructed electrode, and the channels standing for it"))
        self.table = QTableWidget(len(report.electrodes), 6, self)
        self.table.setHorizontalHeaderLabels(
            ["ELECTRODE", "CHANNELS", "LOCALISED", "RECORDED", "BIPOLAR PAIRS", ""]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        inside.addWidget(self.table, 1)
        self.body.addWidget(frame, 3)

        frame, inside = card()
        inside.addWidget(section("what to look at before accepting"))
        self.txt_warnings = QPlainTextEdit()
        self.txt_warnings.setReadOnly(True)
        self.txt_warnings.setMinimumHeight(96)
        inside.addWidget(self.txt_warnings)
        self.lbl_ignored = QLabel()
        self.lbl_ignored.setObjectName("dialogSubtitle")
        self.lbl_ignored.setWordWrap(True)
        inside.addWidget(self.lbl_ignored)
        self.body.addWidget(frame, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        self.btn_ok = QPushButton("Accept this mapping")
        self.btn_ok.setObjectName("primaryButton")
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        self.btn_ok.clicked.connect(self.accept)
        buttons.addWidget(self.btn_ok)
        self.body.addLayout(buttons)

        self._fill()
        self._refresh_notes()

    # ------------------------------------------------------------------ table
    def _fill(self) -> None:
        for row, electrode in enumerate(self._report.electrodes):
            item = QTableWidgetItem(electrode.recon_name)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)

            combo = QComboBox()
            combo.addItems(self._prefixes)
            combo.setCurrentText(electrode.trc_prefix or _NONE)
            combo.currentTextChanged.connect(
                lambda text, name=electrode.recon_name: self._rebind(name, text)
            )
            self.table.setCellWidget(row, 1, combo)
            self._set_row_numbers(row, electrode)
        self.table.resizeRowsToContents()

    def _set_row_numbers(self, row: int, electrode) -> None:
        pairs = len(electrode.bipolar_pairs())
        full = max(electrode.recon_contacts - 1, 0)
        for offset, text in enumerate(
            [
                str(electrode.recon_contacts),
                str(len(electrode.trc_contacts)),
                "%d / %d" % (pairs, full) if full else str(pairs),
            ],
            start=2,
        ):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, offset, item)

        if not electrode.matched:
            note, colour = "not found in the recording", BAD
        elif electrode.missing_in_trc:
            note, colour = ("%d contact(s) not recorded" % len(electrode.missing_in_trc), WARN)
        elif electrode.extra_in_trc:
            note, colour = ("%d channel(s) not localised" % len(electrode.extra_in_trc), WARN)
        else:
            note, colour = "complete", OK
        item = QTableWidgetItem(note)
        item.setForeground(QColor(colour))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 5, item)

    def _rebind(self, recon_name: str, text: str) -> None:
        bind(self._report, recon_name, None if text == _NONE else text, self._channels)
        # Binding a prefix releases it from whoever held it, so every row can
        # change, not only the one that was touched.
        for row, electrode in enumerate(self._report.electrodes):
            widget = self.table.cellWidget(row, 1)
            if isinstance(widget, QComboBox):
                wanted = electrode.trc_prefix or _NONE
                if widget.currentText() != wanted:
                    widget.blockSignals(True)
                    widget.setCurrentText(wanted)
                    widget.blockSignals(False)
            self._set_row_numbers(row, electrode)
        self._refresh_notes()

    def _refresh_notes(self) -> None:
        ignored = self._report.ignored
        self.lbl_ignored.setText(
            "Set aside, never in a brain (%d):   %s" % (len(ignored), "   ".join(ignored))
            if ignored
            else "No non-electrode channel in this recording."
        )
        warnings = self._report.warnings()
        self.txt_warnings.setPlainText(
            "\n".join("•  " + w for w in warnings)
            if warnings
            else "Nothing. Every reconstructed electrode is complete in the recording."
        )
        total = self._report.total_pairs
        self.btn_ok.setText(
            "Accept  ·  %d pairs on %d electrodes" % (total, len(self._report.matched))
            if total
            else "Accept this mapping"
        )
        self.btn_ok.setEnabled(total > 0)

    # ----------------------------------------------------------------- result
    def report(self) -> MatchReport:
        return self._report
