"""The EEG window: bipolar traces, in the colour of their own electrode.

Everything is drawn bipolar, contact N against N+1, because that is how SEEG is
read: a common reference contaminates every channel at once, so a monopolar
trace says as much about the reference as about the brain.

Each electrode keeps the colour it has in the 3D view. That is not decoration:
when six shafts are on screen at once, the colour is what tells you which
discharge belongs to which electrode without reading a label, and it is the
same colour you are looking at in the 3D scene next to it.

Navigation has two ways in, and the second is the one that gets used. A
twelve-day recording has no interesting instant you could find by scrolling;
what you look for is where someone wrote something. On one recorded session
that is 346 notes among 565,221 events, fifteen of them seizures, the rest
stimulations and bedside observations. The marker list is therefore a main
control, and the slider is for looking around what it lands on.

Nothing is loaded. The window is read from the memory-mapped files on every
move, which costs a seek: a tenth of a second for ten seconds of 198 channels.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..utils.eeg_channel_match import MatchReport
from ..utils.trc_reader import TrcRecording
from .neuxelec_dialog import FAINT, INK, LINE, MUTED, NeuXelecDialog, card, section

#: Above this many traces the window stops being readable; it still draws, and
#: says so, rather than refusing or silently dropping some.
CROWDED = 48

#: The pages an EEG is read at. A reader thinks in seconds per screen, ten or
#: fifteen most of the time, one or two to look closely at a spike.
WINDOWS = (1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 60.0, 120.0)

#: Half the spacing between two traces, in microvolts. SEEG runs an order of
#: magnitude above scalp EEG, hence a range reaching 5000.
AMPLITUDES = (10.0, 25.0, 50.0, 100.0, 200.0, 300.0, 500.0, 1000.0, 2000.0, 5000.0)

AUTO = "auto"

FLECHE_GAUCHE = "\u2190"
FLECHE_DROITE = "\u2192"
FLECHE_HAUT = "\u2191"
FLECHE_BAS = "\u2193"
SIGNE_MOINS = "\u2212"

#: Fallback palette for an electrode the project gave no colour to.
_FALLBACK = ["#9FD3FF", "#FFB36B", "#7ED6A5", "#FF8FB1", "#C4A7FF", "#FFE08A"]


def _hex_colour(electrode: dict, index: int) -> str:
    rgb = electrode.get("color")
    try:
        r, g, b = (int(v) for v in rgb[:3])
        return "#%02X%02X%02X" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    except Exception:
        return _FALLBACK[index % len(_FALLBACK)]


def _swatch(colour: str) -> QIcon:
    pixmap = QPixmap(11, 11)
    pixmap.fill(QColor(colour))
    return QIcon(pixmap)


class EegViewerDialog(NeuXelecDialog):
    """Bipolar traces of the chosen electrodes, with the recording's markers."""

    def __init__(
        self,
        recording: TrcRecording,
        report: MatchReport,
        electrodes: list[dict] | None = None,
        electrode_name: str | None = None,
        contact: int | None = None,
        labels: dict[tuple[str, int], str] | None = None,
        parent=None,
    ):
        super().__init__("EEG viewer", "", parent)
        self.resize(1320, 820)
        self._recording = recording
        self._report = report
        self._labels = labels or {}
        self._window_s = 10.0
        self._when = recording.start or datetime.now()

        #: {electrode name: colour}, taken from the project so the trace and
        #: the 3D shaft are the same colour.
        by_name = {str(e.get("name") or ""): e for e in (electrodes or [])}
        self._colours = {
            e.recon_name: _hex_colour(by_name.get(e.recon_name, {}), i)
            for i, e in enumerate(report.electrodes)
        }

        self.set_subtitle(
            "%s  ·  %d files  ·  %.0f Hz  ·  %s to %s"
            % (recording.folder.name, len(recording.segments), recording.sampling_rate,
               f"{recording.start:%d/%m %H:%M}" if recording.start else "?",
               f"{recording.stop:%d/%m %H:%M}" if recording.stop else "?")
        )

        self.body.addLayout(self._build_controls())

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_plot_card())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([330, 980])
        splitter.setHandleWidth(10)
        self.body.addWidget(splitter, 1)

        self.lbl_status = QLabel()
        self.lbl_status.setObjectName("dialogSubtitle")
        self.body.addWidget(self.lbl_status)

        self._select_initial(electrode_name, contact)
        self._redraw()

    # --------------------------------------------------------------- controls
    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(section("page"))
        self.cmb_window = QComboBox()
        self.cmb_window.setEditable(True)
        self.cmb_window.addItems(["%g s" % v for v in WINDOWS])
        self.cmb_window.setCurrentText("%g s" % self._window_s)
        self.cmb_window.setFixedWidth(84)
        self.cmb_window.setToolTip("Seconds across the screen.  Keys: + and -")
        self.cmb_window.currentTextChanged.connect(self._on_window_changed)
        row.addWidget(self.cmb_window)

        self.btn_back = QPushButton("‹")
        self.btn_forward = QPushButton("›")
        for button, direction in ((self.btn_back, -1), (self.btn_forward, 1)):
            button.setObjectName("stepButton")
            button.setFixedSize(30, 26)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, d=direction: self._step(d * 0.5))
        row.addWidget(self.btn_back)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.valueChanged.connect(self._on_slider)
        row.addWidget(self.slider, 1)
        row.addWidget(self.btn_forward)

        row.addWidget(section("amplitude"))
        self.cmb_scale = QComboBox()
        self.cmb_scale.setEditable(True)
        self.cmb_scale.addItem(AUTO)
        self.cmb_scale.addItems(["%g uV" % v for v in AMPLITUDES])
        self.cmb_scale.setCurrentText(AUTO)
        self.cmb_scale.setFixedWidth(96)
        self.cmb_scale.setToolTip(
            "Half the spacing between two traces. "
            "auto fits the window.  Keys: up and down"
        )
        self.cmb_scale.currentTextChanged.connect(lambda _: self._redraw())
        row.addWidget(self.cmb_scale)

        hint = QLabel(
            "%s %s  move     %s %s  amplitude     + %s  page     Home End"
            % (FLECHE_GAUCHE, FLECHE_DROITE, FLECHE_HAUT, FLECHE_BAS, SIGNE_MOINS)
        )
        hint.setObjectName("dialogSubtitle")
        row.addWidget(hint)
        return row

    # ------------------------------------------------------------- left panel
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        frame, inside = card()
        head = QHBoxLayout()
        head.addWidget(section("electrodes and pairs"))
        head.addStretch(1)
        for text, checked in (("all", True), ("none", False)):
            button = QPushButton(text)
            button.setObjectName("secondaryButton")
            button.setFixedHeight(22)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, c=checked: self._check_everything(c))
            head.addWidget(button)
        inside.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.itemChanged.connect(self._on_item_changed)
        inside.addWidget(self.tree, 1)
        self._fill_tree()
        layout.addWidget(frame, 3)

        frame, inside = card()
        head = QHBoxLayout()
        head.addWidget(section("markers"))
        head.addStretch(1)
        self.chk_notes_only = QCheckBox("notes only")
        self.chk_notes_only.setChecked(True)
        self.chk_notes_only.toggled.connect(self._fill_markers)
        head.addWidget(self.chk_notes_only)
        inside.addLayout(head)

        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("filter, for instance  crise")
        self.ed_filter.textChanged.connect(self._fill_markers)
        inside.addWidget(self.ed_filter)

        self.list_markers = QListWidget()
        self.list_markers.itemSelectionChanged.connect(self._on_marker_selected)
        inside.addWidget(self.list_markers, 1)
        self._fill_markers()
        layout.addWidget(frame, 2)
        return panel

    def _fill_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._items: dict[str, QTreeWidgetItem] = {}
        for electrode in self._report.electrodes:
            pairs = electrode.bipolar_pairs()
            if not electrode.matched or not pairs:
                continue
            colour = self._colours.get(electrode.recon_name, _FALLBACK[0])
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, "%s      %d pairs" % (electrode.recon_name, len(pairs)))
            parent.setIcon(0, _swatch(colour))
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            parent.setCheckState(0, Qt.Unchecked)
            parent.setData(0, Qt.UserRole, ("electrode", electrode.recon_name, None))
            for a, b in pairs:
                child = QTreeWidgetItem(parent)
                first, second = electrode.channel_names(a), electrode.channel_names(b)
                anatomy = self._labels.get((electrode.recon_name, a), "")
                child.setText(0, "%s-%s%s" % (first, second, "   " + anatomy if anatomy else ""))
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setForeground(0, QColor(colour))
                child.setData(0, Qt.UserRole, ("pair", electrode.recon_name, (a, b)))
            self._items[electrode.recon_name] = parent
        self.tree.blockSignals(False)

    def _check_everything(self, checked: bool) -> None:
        self.tree.blockSignals(True)
        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            parent.setCheckState(0, state)
            for child_index in range(parent.childCount()):
                parent.child(child_index).setCheckState(0, state)
        self.tree.blockSignals(False)
        self._redraw()

    def _on_item_changed(self, *_args) -> None:
        self._redraw()

    def _select_initial(self, electrode_name: str | None, contact: int | None) -> None:
        """Open on what was right-clicked, and on nothing else.

        Opening with everything ticked would put 168 traces on screen and hide
        the one the click was about.
        """
        self.tree.blockSignals(True)
        chosen = self._items.get(electrode_name or "") or (
            self.tree.topLevelItem(0) if self.tree.topLevelItemCount() else None
        )
        if chosen is not None:
            chosen.setCheckState(0, Qt.Checked)
            for index in range(chosen.childCount()):
                chosen.child(index).setCheckState(0, Qt.Checked)
            chosen.setExpanded(True)
            self.tree.scrollToItem(chosen)
        self.tree.blockSignals(False)

    # ---------------------------------------------------------------- markers
    def _fill_markers(self) -> None:
        markers = (
            self._recording.notes() if self.chk_notes_only.isChecked() else self._recording.markers
        )
        needle = self.ed_filter.text().strip().lower()
        if needle:
            markers = [m for m in markers if needle in m.text.lower()]
        self.list_markers.clear()
        for marker in markers:
            item = QListWidgetItem("%s   %s" % (f"{marker.when:%d/%m %H:%M:%S}", marker.text))
            item.setData(Qt.UserRole, marker.when.isoformat())
            if "crise" in marker.text.lower() or "seizure" in marker.text.lower():
                item.setForeground(QColor("#FF6B8A"))
            self.list_markers.addItem(item)

    def _on_marker_selected(self) -> None:
        items = self.list_markers.selectedItems()
        if not items:
            return
        when = datetime.fromisoformat(items[0].data(Qt.UserRole))
        # A quarter of the window before it, so what led to the marker is on
        # screen and not only what followed.
        self._when = when - timedelta(seconds=self._window_s / 4.0)
        self._sync_slider()
        self._redraw()

    # ------------------------------------------------------------------- time
    @staticmethod
    def _number(text: str, fallback: float) -> float:
        """A value out of a field someone may have typed into."""
        cleaned = "".join(c for c in str(text) if c.isdigit() or c in ".,").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return fallback

    def _on_window_changed(self, text: str) -> None:
        value = self._number(text, self._window_s)
        self._window_s = max(0.5, min(300.0, value))
        self._redraw()

    def _nudge_window(self, direction: int) -> None:
        """Along the usual pages, not by a fixed step: 10 to 15, not 10 to 11."""
        closest = min(range(len(WINDOWS)), key=lambda i: abs(WINDOWS[i] - self._window_s))
        index = max(0, min(len(WINDOWS) - 1, closest + direction))
        self.cmb_window.setCurrentText("%g s" % WINDOWS[index])

    def _scale_setting(self):
        """The imposed amplitude, or None when it is left to the window."""
        text = self.cmb_scale.currentText().strip()
        if not text or text.lower().startswith("auto"):
            return None
        value = self._number(text, 0.0)
        return value if value > 0 else None

    def _nudge_amplitude(self, direction: int) -> None:
        """Up means a bigger trace, so fewer microvolts.

        That inversion is the convention of every EEG reader: what the control
        holds is the gain, not the scale.
        """
        current = self._scale_setting()
        if current is None:
            # Leaving auto, start from what auto had just chosen, so the first
            # key press does not jump somewhere unrelated to what is on screen.
            current = getattr(self, "_last_scale", None) or AMPLITUDES[len(AMPLITUDES) // 2]
            closest = min(range(len(AMPLITUDES)), key=lambda i: abs(AMPLITUDES[i] - current))
            self.cmb_scale.setCurrentText("%g uV" % AMPLITUDES[closest])
            return
        closest = min(range(len(AMPLITUDES)), key=lambda i: abs(AMPLITUDES[i] - current))
        index = closest - direction
        if index < 0:
            self.cmb_scale.setCurrentText(AUTO)
            return
        self.cmb_scale.setCurrentText("%g uV" % AMPLITUDES[min(len(AMPLITUDES) - 1, index)])

    def keyPressEvent(self, event) -> None:
        """The keys an EEG reader expects: a hand on the mouse is slower.

        Not accepting an unknown key matters. Escape has to keep closing the
        window, and the tree has to keep its own arrows while it has the focus.
        """
        key = event.key()
        step = 1.0 if event.modifiers() & Qt.ShiftModifier else 0.5
        if key == Qt.Key_Left:
            self._step(-step)
        elif key == Qt.Key_Right:
            self._step(step)
        elif key == Qt.Key_Up:
            self._nudge_amplitude(1)
        elif key == Qt.Key_Down:
            self._nudge_amplitude(-1)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._nudge_window(1)
        elif key in (Qt.Key_Minus, Qt.Key_Underscore):
            self._nudge_window(-1)
        elif key == Qt.Key_Home and self._recording.start is not None:
            self._when = self._recording.start
            self._sync_slider()
            self._redraw()
        elif key == Qt.Key_End and self._recording.stop is not None:
            self._when = self._recording.stop - timedelta(seconds=self._window_s)
            self._sync_slider()
            self._redraw()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def _on_slider(self, value: int) -> None:
        start, stop = self._recording.start, self._recording.stop
        if start is None or stop is None:
            return
        span = max((stop - start).total_seconds() - self._window_s, 0.0)
        self._when = start + timedelta(seconds=span * value / 10000.0)
        self._redraw()

    def _step(self, direction: float) -> None:
        self._when = self._when + timedelta(seconds=direction * self._window_s)
        self._sync_slider()
        self._redraw()

    def _sync_slider(self) -> None:
        start, stop = self._recording.start, self._recording.stop
        if start is None or stop is None:
            return
        span = max((stop - start).total_seconds() - self._window_s, 1e-6)
        value = int(10000 * (self._when - start).total_seconds() / span)
        self.slider.blockSignals(True)
        self.slider.setValue(max(0, min(10000, value)))
        self.slider.blockSignals(False)

    # ---------------------------------------------------------------- drawing
    def _build_plot_card(self) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        frame, inside = card(margins=(6, 6, 6, 6))
        self.figure = Figure(facecolor=INK)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet("background: transparent;")
        self.axes = self.figure.add_subplot(111)
        inside.addWidget(self.canvas, 1)
        return frame

    def _selected_pairs(self) -> list[tuple[str, tuple[int, int]]]:
        chosen = []
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.checkState(0) != Qt.Checked:
                    continue
                kind, name, pair = child.data(0, Qt.UserRole)
                chosen.append((name, pair))
        return chosen

    def _electrode(self, name: str):
        for electrode in self._report.electrodes:
            if electrode.recon_name == name:
                return electrode
        return None

    def _redraw(self) -> None:
        self.axes.clear()
        self.axes.set_facecolor(INK)
        chosen = self._selected_pairs()
        if not chosen:
            self._empty("Tick an electrode on the left to see its traces")
            return

        wanted: list[str] = []
        plan: list[tuple[str, str, str, str]] = []  # electrode, label, first, second
        for name, (a, b) in chosen:
            electrode = self._electrode(name)
            if electrode is None:
                continue
            first, second = electrode.channel_names(a), electrode.channel_names(b)
            if first is None or second is None:
                continue
            anatomy = self._labels.get((name, a), "")
            label = "%s-%s" % (first, second)
            plan.append((name, label + ("   " + anatomy if anatomy else ""), first, second))
            wanted += [first, second]

        unique = list(dict.fromkeys(wanted))
        try:
            block, rate = self._recording.read(self._when, self._window_s, unique)
        except Exception as error:
            self._empty(str(error), colour="#FF6B8A")
            return

        column = {name: i for i, name in enumerate(unique)}
        data = np.vstack([block[:, column[f]] - block[:, column[s]] for _, _, f, s in plan])

        manual = self._scale_setting()
        scale = manual if manual else (float(np.nanpercentile(np.abs(data), 99)) or 1.0)
        # Kept so that leaving auto with a key starts from what auto was showing.
        self._last_scale = scale
        spacing = 3.0 * scale
        t = np.arange(data.shape[1]) / rate

        ticks, labels, colours = [], [], []
        for index, row in enumerate(data):
            offset = -index * spacing
            name, label, _f, _s = plan[index]
            colour = self._colours.get(name, _FALLBACK[0])
            self.axes.plot(t, row + offset, linewidth=0.65, color=colour, antialiased=True)
            ticks.append(offset)
            labels.append(label)
            colours.append(colour)

        self.axes.set_yticks(ticks)
        self.axes.set_yticklabels(labels, fontsize=7)
        for tick, colour in zip(self.axes.get_yticklabels(), colours):
            tick.set_color(colour)
        self.axes.set_xlabel("seconds", color=MUTED, fontsize=8)
        self.axes.tick_params(colors=FAINT, labelsize=7, length=3)
        for side in self.axes.spines.values():
            side.set_color(LINE)
        self.axes.set_xlim(0, self._window_s)
        self.axes.grid(True, axis="x", color=LINE, linewidth=0.4, alpha=0.6)
        self.figure.tight_layout(pad=0.8)
        self.canvas.draw_idle()

        missing = float(np.isnan(data).mean())
        notes = []
        if missing > 0.001:
            notes.append("%.0f %% of this window was never recorded" % (100 * missing))
        if len(plan) > CROWDED:
            notes.append("%d traces, past what a screen can show clearly" % len(plan))
        self.lbl_status.setText(
            "%s   ·   %d bipolar pairs   ·   %.0f Hz   ·   +/-%.0f uV%s"
            % (f"{self._when:%A %d %B %Y, %H:%M:%S}", len(plan), rate, scale,
               "   ·   " + "   ·   ".join(notes) if notes else "")
        )

    def _empty(self, text: str, colour: str = MUTED) -> None:
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for side in self.axes.spines.values():
            side.set_color(INK)
        self.axes.text(0.5, 0.5, text, ha="center", va="center", color=colour, fontsize=10)
        self.canvas.draw_idle()
        self.lbl_status.setText("")
