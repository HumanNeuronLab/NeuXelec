"""The two tabs of the stimulation results: what to show, and what was found.

FILTERS

The first tab decides which stimulations the 3D view draws. Inside one
filter, ticking two boxes means either of them, which is what reaching for
a filter means. Between filters, every active one must be satisfied. So
"50 Hz" plus "above 3 mA" plus "habitual" narrows, while ticking motor and
visual widens.

Silent pairs are kept by default. A pair tested up to 5 mA without a
response is a result, and dropping it silently would make the map say the
opposite of what the examination found.

CARDS

The second tab is one card per stimulation, which can be corrected or
deleted. The card prints only the fields that were filled in: an empty
line on a clinical card is noise, and noise is what stops it being read.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..utils import i18n
from ..utils import stimulation as st
from ..utils import stimulation_display as sd
from .neuxelec_color_dialog import NeuXelecColorDialog
from .neuxelec_dialog import (
    MUTED,
    SPIN_DOWN,
    SPIN_UP,
    NeuXelecDialog,
    card,
    explain,
    field,
    section,
)
from .neuxelec_message_dialog import NeuXelecMessageDialog

ROLE_ID = Qt.UserRole + 1


class StimulationResultsDialog(NeuXelecDialog):
    """Filter what the 3D view shows, and read or correct the cards."""

    def __init__(
        self,
        state,
        *,
        on_filters_changed: Callable[[dict], None] | None = None,
        on_display_changed: Callable[[dict], None] | None = None,
        anatomy_lookup: Callable[[str, int], str | None] | None = None,
        parent=None,
    ):
        from ..utils.app_mode import is_edit_mode

        self.state = state
        # Les reglages d'affichage restent libres en visualisation; ce sont
        # les fiches, donnees du patient, qui ne s'ecrivent plus.
        self._editable = is_edit_mode(state)
        self._on_filters_changed = on_filters_changed
        self._on_display_changed = on_display_changed
        self._anatomy_lookup = anatomy_lookup
        self._rules: list[dict] = []

        super().__init__(
            i18n.tr("Stimulation results"), "", parent, with_language=True
        )
        self.size_like_electrode_list()

        self._build()
        self._load_display_settings()
        self._refresh_cards()
        self._refresh_count()

    # ----------------------------------------------------------- language

    def retranslate(self) -> None:
        """Rebuild in the new language, keeping filters, rules and choice."""
        filters = self.filters()
        settings = self.display_settings()
        chosen = self.selected_id() or ""
        tab = self.tabs.currentIndex()

        self.state.stimulation_display = settings

        self.clear_body()
        self._build()
        self._load_display_settings()
        self._apply_filters(filters)
        self._refresh_cards(keep_id=chosen)
        self._refresh_count()
        self.tabs.setCurrentIndex(tab)

        self.set_title(i18n.tr("Stimulation results"))

    def _apply_filters(self, filters: dict) -> None:
        """Put a set of filters back into the tab, without announcing each."""
        boxes = (
            [self.chk_min, self.chk_max, self.chk_reproduced, self.chk_silent]
            + list(self.chk_frequencies.values())
            + list(self.chk_filter_events.values())
            + list(self.chk_filter_categories.values())
            + list(self.chk_filter_habitual.values())
        )

        for box in boxes:
            box.blockSignals(True)

        try:
            self.chk_min.setChecked(filters.get("min_intensity_ma") is not None)
            self.chk_max.setChecked(filters.get("max_intensity_ma") is not None)

            if filters.get("min_intensity_ma") is not None:
                self.spn_min.setValue(float(filters["min_intensity_ma"]))

            if filters.get("max_intensity_ma") is not None:
                self.spn_max.setValue(float(filters["max_intensity_ma"]))

            for hz, box in self.chk_frequencies.items():
                box.setChecked(hz in (filters.get("frequencies") or set()))

            for key, box in self.chk_filter_events.items():
                box.setChecked(key in (filters.get("events") or set()))

            for key, box in self.chk_filter_categories.items():
                box.setChecked(key in (filters.get("categories") or set()))

            for key, box in self.chk_filter_habitual.items():
                box.setChecked(key in (filters.get("habitual") or set()))

            self.chk_reproduced.setChecked(bool(filters.get("only_reproduced")))
            self.chk_silent.setChecked(bool(filters.get("include_silent", True)))
        finally:
            for box in boxes:
                box.blockSignals(False)

    # ------------------------------------------------------------ records

    def _records(self) -> list[dict]:
        return list(getattr(self.state, "stimulations", []) or [])

    def _set_records(self, records: list[dict]) -> None:
        self.state.stimulations = list(records)

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._build_filters_tab(), i18n.tr("Visualisation filters")
        )
        self.tabs.addTab(self._build_display_tab(), i18n.tr("Appearance"))
        self.tabs.addTab(self._build_cards_tab(), i18n.tr("Stimulation cards"))
        self.body.addWidget(self.tabs, 1)

        row = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("dialogSubtitle")
        row.addWidget(self.lbl_count)
        row.addStretch(1)

        # Dans la barre de la fenetre et non dans un onglet: il emporte
        # toutes les stimulations, pas la fiche choisie a cote de
        # Modifier et Supprimer.
        self.btn_export = QPushButton(i18n.tr("Export all"))
        self.btn_export.setObjectName("secondaryButton")
        self.btn_export.setToolTip(
            i18n.tr("Every stimulation of this patient, in one file")
        )
        self.btn_export.clicked.connect(self.export_stimulations)
        row.addWidget(self.btn_export)

        self.btn_close = QPushButton(i18n.tr("Close"))
        self.btn_close.setObjectName("primaryButton")
        self.btn_close.clicked.connect(self.accept)
        row.addWidget(self.btn_close)
        self.body.addLayout(row)

    # ---------------------------------------------------------- filters tab

    def _build_filters_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        column = QVBoxLayout(inner)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        column.addWidget(self._build_current_card())
        column.addWidget(self._build_event_card())
        column.addWidget(self._build_category_card())
        column.addWidget(self._build_habitual_card())
        column.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_reset = QPushButton(i18n.tr("Show everything"))
        self.btn_reset.setObjectName("secondaryButton")
        self.btn_reset.clicked.connect(self.reset_filters)
        row.addWidget(self.btn_reset)
        outer.addLayout(row)

        return page

    def _build_current_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("current and protocol"))

        row = QHBoxLayout()
        row.setSpacing(8)

        self.chk_min = QCheckBox(i18n.tr("from"))
        self.chk_min.toggled.connect(self._filters_changed)
        row.addWidget(self.chk_min)

        self.spn_min = QDoubleSpinBox()
        self.spn_min.setDecimals(1)
        self.spn_min.setRange(0.0, 50.0)
        self.spn_min.setValue(1.0)
        self.spn_min.valueChanged.connect(self._filters_changed)
        row.addWidget(self.spn_min)

        self.chk_max = QCheckBox(i18n.tr("up to"))
        self.chk_max.toggled.connect(self._filters_changed)
        row.addWidget(self.chk_max)

        self.spn_max = QDoubleSpinBox()
        self.spn_max.setDecimals(1)
        self.spn_max.setRange(0.0, 50.0)
        self.spn_max.setValue(5.0)
        self.spn_max.valueChanged.connect(self._filters_changed)
        row.addWidget(self.spn_max)

        row.addWidget(QLabel("mA"))
        row.addStretch(1)
        inside.addLayout(row)

        frequencies = QHBoxLayout()
        frequencies.setSpacing(14)
        frequencies.addWidget(self._muted(i18n.tr("frequency")))
        self.chk_frequencies: dict[float, QCheckBox] = {}

        for hz in st.FREQUENCY_PRESETS:
            box = QCheckBox(f"{hz:g} Hz")
            box.toggled.connect(self._filters_changed)
            self.chk_frequencies[float(hz)] = box
            frequencies.addWidget(box)

        frequencies.addStretch(1)
        inside.addLayout(frequencies)

        self.chk_silent = QCheckBox(i18n.tr("include pairs tested without a response"))
        self.chk_silent.setChecked(True)
        self.chk_silent.toggled.connect(self._filters_changed)
        inside.addWidget(self.chk_silent)

        self.chk_reproduced = QCheckBox(
            i18n.tr("only responses reproduced on repeat stimulation")
        )
        self.chk_reproduced.toggled.connect(self._filters_changed)
        inside.addWidget(self.chk_reproduced)

        return frame

    def _build_event_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("show only the pairs where this happened"))
        inside.addWidget(explain("Nothing ticked means every pair."))

        # Une seule colonne: ces libelles sont longs, et deux colonnes
        # imposaient leur largeur a toute la fenetre.
        self.chk_filter_events: dict[str, QCheckBox] = {}

        for key, label in st.EVENTS:
            box = QCheckBox(i18n.tr(label))
            box.toggled.connect(self._filters_changed)
            self.chk_filter_events[key] = box
            inside.addWidget(box)
        return frame

    def _build_category_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("show only the pairs that gave this response"))

        self.chk_filter_categories: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        for index, cat in enumerate(st.CATEGORIES):
            box = QCheckBox(i18n.tr(cat.label))
            box.toggled.connect(self._filters_changed)
            self.chk_filter_categories[cat.key] = box
            grid.addWidget(box, index // 3, index % 3)

        inside.addLayout(grid)
        return frame

    def _build_habitual_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("show only the pairs that reproduced the habitual event"))

        self.chk_filter_habitual: dict[str, QCheckBox] = {}

        for key, label in st.HABITUAL:
            if key == "unspecified":
                continue

            box = QCheckBox(i18n.tr(label))
            box.toggled.connect(self._filters_changed)
            self.chk_filter_habitual[key] = box
            inside.addWidget(box)

        return frame

    def _build_legend_card(self) -> QFrame:
        """What the colours in the 3D view mean.

        Without it the map cannot be read, and a map that cannot be read is
        worse than no map.
        """
        frame, inside = card()
        inside.addWidget(section("colour of a marker in the 3D view"))

        for colour, text in st.COLOUR_LEGEND:
            label = QLabel(
                f'<span style="color:{colour}; font-size:15px;">&#9679;</span>'
                f'&nbsp;&nbsp;{i18n.tr(text)}'
            )
            label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            inside.addWidget(label)

        inside.addWidget(
            self._muted(
                "A bipolar pair is drawn midway between its two contacts, "
                "where the current density peaks."
            )
        )

        return frame


    # -------------------------------------------------------- appearance tab

    def _build_display_tab(self) -> QWidget:
        """How a stimulation is drawn, and the rules that decide it."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        column = QVBoxLayout(inner)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(12)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        column.addWidget(self._build_colour_card())
        column.addWidget(self._build_shape_card())
        column.addWidget(self._build_rules_card())
        column.addStretch(1)

        return page

    def _build_colour_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("what the colour means"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.cmb_colour_mode = QComboBox()

        for key, label in sd.COLOUR_MODES:
            self.cmb_colour_mode.addItem(i18n.tr(label), key)

        self.cmb_colour_mode.currentIndexChanged.connect(self._display_changed)
        self.cmb_colour_mode.setFixedWidth(210)
        row.addWidget(field("colour decided by", self.cmb_colour_mode))
        row.addStretch(1)

        self.btn_fixed_colour = self._colour_button()
        self.fld_fixed_colour = field("that one colour", self.btn_fixed_colour)
        row.addWidget(self.fld_fixed_colour)

        inside.addLayout(row)

        self.lay_legend = QVBoxLayout()
        self.lay_legend.setSpacing(2)
        inside.addLayout(self.lay_legend)

        return frame

    def _build_shape_card(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("where it is drawn, and how big"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.cmb_where = QComboBox()

        for key, label in sd.WHERE_CHOICES:
            self.cmb_where.addItem(i18n.tr(label), key)

        self.cmb_where.currentIndexChanged.connect(self._display_changed)
        self.cmb_where.setFixedWidth(210)
        row.addWidget(field("draw the result as", self.cmb_where))

        self.spn_line_width = QDoubleSpinBox()
        self.spn_line_width.setDecimals(1)
        self.spn_line_width.setRange(0.2, 8.0)
        self.spn_line_width.setSingleStep(0.2)
        self.spn_line_width.valueChanged.connect(self._display_changed)
        row.addWidget(field("tube thickness", self.spn_line_width, unit="mm"))

        self.spn_contact_radius = QDoubleSpinBox()
        self.spn_contact_radius.setDecimals(1)
        self.spn_contact_radius.setRange(0.2, 6.0)
        self.spn_contact_radius.setSingleStep(0.2)
        self.spn_contact_radius.valueChanged.connect(self._display_changed)
        row.addWidget(field("contact size", self.spn_contact_radius, unit="mm"))

        second = QHBoxLayout()
        second.setSpacing(10)

        self.spn_opacity = QDoubleSpinBox()
        self.spn_opacity.setDecimals(2)
        self.spn_opacity.setRange(0.05, 1.0)
        self.spn_opacity.setSingleStep(0.05)
        self.spn_opacity.valueChanged.connect(self._display_changed)
        second.addWidget(field("opacity", self.spn_opacity))

        self.btn_grey_colour = self._colour_button()
        second.addWidget(field("colour of every contact", self.btn_grey_colour))

        second.addStretch(1)

        # Deux lignes: cinq champs cote a cote ne tiennent pas dans une
        # fenetre large comme deux listes d'electrodes et demie.
        inside.addLayout(row)
        inside.addLayout(second)

        return frame

    def _build_rules_card(self) -> QFrame:
        frame, inside = card()

        head = QHBoxLayout()
        head.addWidget(section("my rules"))
        head.addStretch(1)

        self.cmb_preset = QComboBox()

        for key, label in sd.PRESETS:
            self.cmb_preset.addItem(i18n.tr(label), key)

        head.addWidget(self.cmb_preset)

        self.btn_load_preset = QPushButton(i18n.tr("Load this set"))
        self.btn_load_preset.setObjectName("secondaryButton")
        self.btn_load_preset.clicked.connect(self._load_preset)
        head.addWidget(self.btn_load_preset)
        inside.addLayout(head)

        inside.addWidget(
            explain("The first rule that matches wins, so the order counts.")
        )

        self.btn_add_rule = QPushButton(i18n.tr("+ make a rule from the current filters"))
        self.btn_add_rule.setObjectName("secondaryButton")
        self.btn_add_rule.clicked.connect(self._add_rule_from_filters)
        inside.addWidget(self.btn_add_rule)

        self.lay_rules = QVBoxLayout()
        self.lay_rules.setSpacing(6)
        inside.addLayout(self.lay_rules)

        self.lbl_no_rule = explain("No rule yet.")
        inside.addWidget(self.lbl_no_rule)

        return frame

    # ------------------------------------------------------ colour buttons

    def _colour_button(self) -> QPushButton:
        """A swatch that opens the colour window of the application."""
        button = QPushButton("")
        button.setFixedSize(54, 24)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _c=False, b=button: self._pick_colour(b))
        return button

    @staticmethod
    def _paint_swatch(button: QPushButton, colour: str) -> None:
        button.setProperty("colour", str(colour))
        button.setStyleSheet(
            f"background-color: {colour}; border: 1px solid #2B2D38; "
            "border-radius: 6px;"
        )

    def _swatch_colour(self, button: QPushButton) -> str:
        return str(button.property("colour") or sd.DEFAULT_GREY)

    def _pick_colour(self, button: QPushButton) -> None:
        chosen = NeuXelecColorDialog.get_color(
            self._swatch_colour(button), self, "Choose a colour"
        )

        if not chosen:
            return

        self._paint_swatch(button, chosen)
        self._display_changed()

    # ------------------------------------------------------ the rule rows

    def _add_rule_from_filters(self) -> None:
        """Turn what the filters tab currently asks for into a rule."""
        rule = sd.new_rule(
            self._describe_filters(),
            when=self.filters(),
            colour=st.COLOUR_HABITUAL,
            rule_id=sd.next_rule_id(self._rules),
        )
        self._rules.append(rule)
        self._rebuild_rule_rows()
        self._display_changed()

    def _describe_filters(self) -> str:
        """A name for a rule, read off the filters that made it."""
        filters = self.filters()
        bits: list[str] = []

        for key in sorted(filters.get("habitual") or []):
            bits.append(st.label_of(st.HABITUAL, key))

        for key in sorted(filters.get("events") or []):
            bits.append(st.EVENT_LABELS.get(key, key))

        for key in sorted(filters.get("categories") or []):
            found = st.category(key)
            bits.append(found.label if found is not None else key)

        for key in sorted(filters.get("frequencies") or []):
            bits.append(f"{float(key):g} Hz")

        low = filters.get("min_intensity_ma")
        high = filters.get("max_intensity_ma")

        if low is not None:
            bits.append(f"from {float(low):g} mA")

        if high is not None:
            bits.append(f"up to {float(high):g} mA")

        if filters.get("only_reproduced"):
            bits.append("reproduced")

        if not filters.get("include_silent", True):
            bits.append("not silent")

        return ", ".join(bits) if bits else "Every stimulation"

    def _rebuild_rule_rows(self) -> None:
        while self.lay_rules.count():
            item = self.lay_rules.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for position, rule in enumerate(self._rules):
            self.lay_rules.addWidget(self._build_rule_row(position, rule))

        self.lbl_no_rule.setVisible(not self._rules)
        self._refresh_legend()

    def _build_rule_row(self, position: int, rule: dict) -> QWidget:
        row_widget = QFrame()
        row_widget.setObjectName("responseBlock")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)

        enabled = QCheckBox()
        enabled.setChecked(bool(rule.get("enabled", True)))
        enabled.setToolTip("Use this rule")
        enabled.toggled.connect(
            lambda on, r=rule: self._set_rule_value(r, "enabled", bool(on))
        )
        row.addWidget(enabled)

        name = QLineEdit(str(rule.get("name", "")))
        name.setPlaceholderText(i18n.tr("name of this rule"))
        name.textChanged.connect(
            lambda text, r=rule: self._rename_rule(r, str(text))
        )
        row.addWidget(name, 1)

        # Apres le nom, et non avant: collee a la case cochee, la pastille
        # de couleur se confondait avec elle.
        swatch = QPushButton("")
        swatch.setFixedSize(34, 20)
        swatch.setCursor(Qt.PointingHandCursor)
        swatch.setToolTip(i18n.tr("Colour of this rule"))
        self._paint_swatch(swatch, str(rule.get("colour") or sd.DEFAULT_GREY))
        swatch.clicked.connect(
            lambda _c=False, r=rule, b=swatch: self._pick_rule_colour(r, b)
        )
        row.addWidget(swatch)

        width = QDoubleSpinBox()
        width.setDecimals(1)
        width.setRange(0.2, 8.0)
        width.setSingleStep(0.2)
        width.setToolTip("Tube thickness for this rule, in mm")
        width.setValue(float(rule.get("line_width_mm") or 1.4))
        width.valueChanged.connect(
            lambda value, r=rule: self._set_rule_value(r, "line_width_mm", float(value))
        )
        row.addWidget(width)

        up = self._arrow_button(
            SPIN_UP,
            "Earlier: the first rule that matches wins",
            lambda _c=False, i=position: self._move_rule(i, -1),
        )
        row.addWidget(up)

        down = self._arrow_button(
            SPIN_DOWN,
            "Later",
            lambda _c=False, i=position: self._move_rule(i, 1),
        )
        row.addWidget(down)

        remove = QPushButton("✕")
        remove.setObjectName("closeWindowButton")
        remove.setFixedSize(24, 24)
        remove.setToolTip("Remove this rule")
        remove.clicked.connect(lambda _c=False, i=position: self._remove_rule(i))
        row.addWidget(remove)

        return row_widget

    @staticmethod
    def _arrow_button(image: str, tip: str, on_click) -> QPushButton:
        """A step button carrying the application's own arrow.

        A character arrow depends on the font having it, and some do not:
        the button then looks empty.
        """
        button = QPushButton("")
        button.setObjectName("stepButton")
        button.setFixedSize(24, 24)
        button.setToolTip(tip)
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(QIcon(image))
        button.setIconSize(QSize(10, 7))
        button.clicked.connect(on_click)
        return button

    def _set_rule_value(self, rule: dict, key: str, value) -> None:
        rule[key] = value
        self._display_changed()

    def _rename_rule(self, rule: dict, name: str) -> None:
        rule["name"] = name
        self._refresh_legend()

    def _pick_rule_colour(self, rule: dict, swatch: QPushButton) -> None:
        chosen = NeuXelecColorDialog.get_color(
            self._swatch_colour(swatch), self, "Colour of this rule"
        )

        if not chosen:
            return

        rule["colour"] = str(chosen)
        self._paint_swatch(swatch, chosen)
        self._display_changed()

    def _move_rule(self, position: int, step: int) -> None:
        target = position + step

        if not (0 <= position < len(self._rules)):
            return

        if not (0 <= target < len(self._rules)):
            return

        self._rules[position], self._rules[target] = (
            self._rules[target],
            self._rules[position],
        )
        self._rebuild_rule_rows()
        self._display_changed()

    def _remove_rule(self, position: int) -> None:
        if 0 <= position < len(self._rules):
            self._rules.pop(position)

        self._rebuild_rule_rows()
        self._display_changed()

    def _load_preset(self) -> None:
        """Replace the rules with one of the sets that come with the app."""
        self._rules = sd.preset_rules(str(self.cmb_preset.currentData() or ""))

        index = self.cmb_colour_mode.findData(sd.BY_RULES)

        if index >= 0:
            self.cmb_colour_mode.blockSignals(True)
            self.cmb_colour_mode.setCurrentIndex(index)
            self.cmb_colour_mode.blockSignals(False)

        self._rebuild_rule_rows()
        self._display_changed()

    # ------------------------------------------------------ the settings

    def display_settings(self) -> dict:
        """What the appearance tab currently asks for."""
        settings = sd.default_settings()
        settings.update(
            {
                "colour_mode": str(self.cmb_colour_mode.currentData() or sd.BY_FINDING),
                "where": str(self.cmb_where.currentData() or sd.WHERE_LINE),
                "line_width_mm": float(self.spn_line_width.value()),
                "contact_radius_mm": float(self.spn_contact_radius.value()),
                "opacity": float(self.spn_opacity.value()),
                "fixed_colour": self._swatch_colour(self.btn_fixed_colour),
                "grey_colour": self._swatch_colour(self.btn_grey_colour),
                "rules": list(self._rules),
            }
        )
        return settings

    def _load_display_settings(self) -> None:
        """Put the settings saved with the patient back into the tab."""
        stored = getattr(self.state, "stimulation_display", None)
        settings = sd.default_settings()

        if isinstance(stored, dict):
            settings.update(stored)

        for box, key, fallback in (
            (self.cmb_colour_mode, "colour_mode", sd.BY_FINDING),
            (self.cmb_where, "where", sd.WHERE_LINE),
        ):
            index = box.findData(str(settings.get(key) or fallback))
            box.blockSignals(True)
            box.setCurrentIndex(index if index >= 0 else 0)
            box.blockSignals(False)

        for spin, key, fallback in (
            (self.spn_line_width, "line_width_mm", 1.4),
            (self.spn_contact_radius, "contact_radius_mm", 1.2),
            (self.spn_opacity, "opacity", 1.0),
        ):
            spin.blockSignals(True)

            try:
                spin.setValue(float(settings.get(key, fallback)))
            except (TypeError, ValueError):
                spin.setValue(float(fallback))

            spin.blockSignals(False)

        self._paint_swatch(self.btn_fixed_colour, str(settings.get("fixed_colour")))
        self._paint_swatch(self.btn_grey_colour, str(settings.get("grey_colour")))

        self._rules = [dict(r) for r in settings.get("rules") or []]
        self._rebuild_rule_rows()
        self._refresh_display_visibility()

    def _refresh_display_visibility(self) -> None:
        mode = str(self.cmb_colour_mode.currentData() or sd.BY_FINDING)
        self.fld_fixed_colour.setVisible(mode == sd.FIXED)

    def _display_changed(self, *_args) -> None:
        self._refresh_display_visibility()
        self._refresh_legend()

        if callable(self._on_display_changed):
            try:
                self._on_display_changed(self.display_settings())
            except Exception:
                pass

    def _refresh_legend(self) -> None:
        """What the colours mean right now, under the choice that decides them."""
        while self.lay_legend.count():
            item = self.lay_legend.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for colour, text in sd.legend_entries(self.display_settings()):
            label = QLabel(
                f'<span style="color:{colour}; font-size:20px;">&#9632;</span>'
                f"&nbsp;&nbsp;{i18n.tr(text)}"
            )
            label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            self.lay_legend.addWidget(label)

    # ----------------------------------------------------------- cards tab

    def _build_cards_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        self.lst_cards = QListWidget()
        # Une ligne trop longue se coupe plutot que d'imposer une barre
        # de defilement horizontale a toute la colonne.
        self.lst_cards.setTextElideMode(Qt.ElideRight)
        self.lst_cards.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lst_cards.currentItemChanged.connect(lambda *_a: self._show_selected_card())
        self.lst_cards.itemDoubleClicked.connect(lambda _i: self.edit_selected())
        splitter.addWidget(self.lst_cards)

        right = QWidget()
        detail = QVBoxLayout(right)
        detail.setContentsMargins(0, 0, 0, 0)
        detail.setSpacing(8)

        self.card_frame, self.card_inside = card()
        detail.addWidget(self.card_frame, 1)

        self.lbl_card = QLabel("")
        self.lbl_card.setWordWrap(True)
        self.lbl_card.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_card.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.card_inside.addWidget(self.lbl_card, 1)

        buttons = QHBoxLayout()

        # Ajouter depuis ici: une fenetre qui s'appelle "resultats de
        # stimulation" et ou l'on ne peut pas en creer un oblige a
        # ressortir pour faire le geste ailleurs.
        self.btn_add = QPushButton(i18n.tr("+ Add a stimulation"))
        self.btn_add.setObjectName("secondaryButton")
        self.btn_add.clicked.connect(self.add_stimulation)
        buttons.addWidget(self.btn_add)
        # En visualisation, les fiches se lisent. Les trois boutons qui les
        # creent, corrigent ou effacent disparaissent plutot que de rester
        # la, grises, a promettre quelque chose.
        self.btn_add.setVisible(self._editable)

        buttons.addStretch(1)
        self.btn_edit = QPushButton(i18n.tr("Edit"))
        self.btn_edit.setObjectName("secondaryButton")
        self.btn_edit.clicked.connect(self.edit_selected)
        buttons.addWidget(self.btn_edit)

        self.btn_edit.setVisible(self._editable)

        self.btn_delete = QPushButton(i18n.tr("Delete"))
        self.btn_delete.setObjectName("secondaryButton")
        self.btn_delete.clicked.connect(self.delete_selected)
        buttons.addWidget(self.btn_delete)
        self.btn_delete.setVisible(self._editable)
        detail.addLayout(buttons)

        splitter.addWidget(right)
        splitter.setSizes([320, 560])
        outer.addWidget(splitter, 1)

        return page

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        return label

    # ------------------------------------------------------------ filters

    def filters(self) -> dict:
        """What the first tab currently asks for."""
        out = st.empty_filters()

        if self.chk_min.isChecked():
            out["min_intensity_ma"] = float(self.spn_min.value())

        if self.chk_max.isChecked():
            out["max_intensity_ma"] = float(self.spn_max.value())

        out["frequencies"] = {
            hz for hz, box in self.chk_frequencies.items() if box.isChecked()
        }
        out["events"] = {
            key for key, box in self.chk_filter_events.items() if box.isChecked()
        }
        out["categories"] = {
            key for key, box in self.chk_filter_categories.items() if box.isChecked()
        }
        out["habitual"] = {
            key for key, box in self.chk_filter_habitual.items() if box.isChecked()
        }
        out["only_reproduced"] = bool(self.chk_reproduced.isChecked())
        out["include_silent"] = bool(self.chk_silent.isChecked())

        return out

    def reset_filters(self) -> None:
        boxes = (
            [self.chk_min, self.chk_max, self.chk_reproduced]
            + list(self.chk_frequencies.values())
            + list(self.chk_filter_events.values())
            + list(self.chk_filter_categories.values())
            + list(self.chk_filter_habitual.values())
        )

        for box in boxes:
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)

        self.chk_silent.blockSignals(True)
        self.chk_silent.setChecked(True)
        self.chk_silent.blockSignals(False)

        self._filters_changed()

    def _filters_changed(self, *_args) -> None:
        self._refresh_count()

        if callable(self._on_filters_changed):
            try:
                self._on_filters_changed(self.filters())
            except Exception:
                pass

    def _refresh_count(self) -> None:
        records = self._records()
        shown = st.filter_records(records, self.filters())

        if not records:
            self.lbl_count.setText(i18n.tr("No stimulation recorded yet."))
            return

        self.lbl_count.setText(
            f"{len(shown)} / {len(records)} "
            + i18n.tr("stimulations shown in the 3D view")
        )

    # -------------------------------------------------------------- cards

    def _refresh_cards(self, keep_id: str = "") -> None:
        wanted = keep_id or self.selected_id() or ""

        self.lst_cards.blockSignals(True)
        self.lst_cards.clear()

        for record in self._records():
            item = QListWidgetItem(st.summary_line(record))
            item.setData(ROLE_ID, str(record.get("id", "")))
            self.lst_cards.addItem(item)

        self.lst_cards.blockSignals(False)

        if self.lst_cards.count():
            row = 0

            for index in range(self.lst_cards.count()):
                if str(self.lst_cards.item(index).data(ROLE_ID)) == wanted:
                    row = index
                    break

            self.lst_cards.setCurrentRow(row)

        self._show_selected_card()

    def reload(self) -> None:
        """Reread the records, keeping the card that was being read.

        Called when a stimulation is entered from the electrode list while
        this window is open: a list that silently goes stale is worse than
        a list that is not there.
        """
        self._refresh_cards()
        self._refresh_count()

    def selected_id(self) -> str | None:
        item = self.lst_cards.currentItem()

        if item is None:
            return None

        return str(item.data(ROLE_ID))

    def selected_record(self) -> dict | None:
        wanted = self.selected_id()

        if not wanted:
            return None

        for record in self._records():
            if str(record.get("id", "")) == wanted:
                return record

        return None

    def _show_selected_card(self) -> None:
        record = self.selected_record()
        has = record is not None

        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)

        if not has:
            self.lbl_card.setText(i18n.tr("Select a stimulation on the left."))
            return

        lines = [
            f"<b>{i18n.tr(label)}</b>&nbsp;&nbsp;{value}"
            for label, value in st.card_fields(record)
        ]
        self.lbl_card.setText("<br>".join(lines))

    # ------------------------------------------------------------ editing

    def add_stimulation(self) -> None:
        """Saisir une stimulation sans quitter la fenetre.

        Le contact de depart se choisit dans la fenetre de saisie, donc
        il n'y a rien a demander avant de l'ouvrir.
        """
        from .stimulation_dialog import StimulationDialog

        electrodes = list(getattr(self.state, "electrodes", []) or [])

        if not electrodes:
            NeuXelecMessageDialog.warning(
                self,
                i18n.tr("Stimulation results"),
                i18n.tr("No electrode is reconstructed yet."),
            )
            return

        dialog = StimulationDialog(
            electrodes,
            0,
            0,
            anatomy_lookup=self._anatomy_lookup,
            parent=self,
        )

        if int(dialog.exec()) != int(QDialog.DialogCode.Accepted):
            return

        records = self._records()
        record = dialog.record()
        record["id"] = st.next_id(records)
        records.append(record)
        self._set_records(records)

        self._refresh_cards(keep_id=record["id"])
        self._filters_changed()

    def export_stimulations(self) -> None:
        """Write the stimulations out, in the format the file name asks for.

        One dialog and no format question: the extension decides, as it
        does for the coordinates.
        """
        from ..utils import stimulation_export as se

        records = self._records()

        if not records:
            NeuXelecMessageDialog.warning(
                self,
                i18n.tr("Stimulation results"),
                i18n.tr("There is nothing to export yet."),
            )
            return

        patient = str(getattr(self.state, "patient_id", "") or "")
        propose = f"{patient}_stimulations.csv" if patient else "stimulations.csv"

        chosen, _filter = QFileDialog.getSaveFileName(
            self,
            i18n.tr("Export every stimulation result"),
            propose,
            i18n.tr(
                "Table (*.csv);;Table, tab separated (*.tsv);;"
                "Report (*.txt);;Records (*.json)"
            ),
        )

        if not chosen:
            return

        try:
            written = se.write_any(
                chosen,
                records,
                list(getattr(self.state, "electrodes", []) or []),
                patient=patient,
            )
        except Exception as error:
            NeuXelecMessageDialog.critical(
                self,
                i18n.tr("Export every stimulation result"),
                f"{i18n.tr('Could not write the file')}: {error}",
            )
            return

        NeuXelecMessageDialog.information(
            self,
            i18n.tr("Export every stimulation result"),
            f"{len(records)} {i18n.tr('stimulation(s) written to')}\n{written}",
        )

    def edit_selected(self) -> None:
        record = self.selected_record()

        if record is None:
            return

        from .stimulation_dialog import StimulationDialog

        electrodes = list(getattr(self.state, "electrodes", []) or [])
        found = self._contact_of(record, electrodes)

        if found is None:
            NeuXelecMessageDialog.warning(
                self,
                "Stimulation result",
                "The electrode this stimulation was recorded on no longer "
                "exists, so the card cannot be reopened.",
            )
            return

        elec_id, contact_idx = found

        dialog = StimulationDialog(
            electrodes,
            elec_id,
            contact_idx,
            record=record,
            anatomy_lookup=self._anatomy_lookup,
            parent=self,
        )

        if int(dialog.exec()) != int(QDialog.DialogCode.Accepted):
            return

        updated = dialog.record()
        updated["id"] = str(record.get("id", ""))

        self._set_records(
            [
                updated if str(r.get("id", "")) == updated["id"] else r
                for r in self._records()
            ]
        )

        self._refresh_cards(keep_id=updated["id"])
        self._filters_changed()

    def delete_selected(self) -> None:
        record = self.selected_record()

        if record is None:
            return

        confirmed = NeuXelecMessageDialog.question(
            self,
            i18n.tr("Delete this stimulation"),
            f"{i18n.tr('Delete the stimulation')} {st.pair_label(record)} ? "
            + i18n.tr("It was entered by hand and cannot be recomputed."),
            accept_text=i18n.tr("Delete"),
        )

        if not confirmed:
            return

        wanted = str(record.get("id", ""))
        self._set_records(
            [r for r in self._records() if str(r.get("id", "")) != wanted]
        )

        self._refresh_cards()
        self._filters_changed()

    @staticmethod
    def _contact_of(record: dict, electrodes: list[dict]) -> tuple[int, int] | None:
        """Find the electrode a card was recorded on, by name.

        By name and not by index: an electrode deleted in between would
        otherwise silently move the card to its neighbour.
        """
        wanted = str((record or {}).get("electrode", "")).strip()

        for index, electrode in enumerate(electrodes or []):
            if str(electrode.get("name", "")).strip() != wanted:
                continue

            contacts = electrode.get("contacts_lps") or []
            contact_idx = int(record.get("contact", 0))

            if 0 <= contact_idx < len(contacts):
                return index, contact_idx

            return None

        return None
