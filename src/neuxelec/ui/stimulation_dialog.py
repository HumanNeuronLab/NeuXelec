"""Enter one electrical stimulation result.

WHAT MAKES THIS WINDOW USABLE RATHER THAN EXHAUSTIVE

The record behind it carries some thirty fields, because that is what it
takes for a card to still be readable in six months. Asking for thirty
fields would mean nobody fills one in. So:

- every input carries a label saying what it asks for, and the question
  changes with the answer above it: under <i>Motor</i> the localisation
  asks WHERE ON THE BODY, under <i>Visual</i> it asks WHICH PART OF THE
  VISUAL FIELD, and under <i>Language</i> it does not appear at all;
- choosing a frequency fills the pulse width, the train duration and the
  current with the ACNS Table 2 values for that protocol, and only a field
  the user has actually typed into is left alone afterwards;
- the second contact is proposed as the adjacent one, which is what
  bipolar stimulation almost always means, while staying free to type;
- the after-discharge details appear only once a discharge or a seizure is
  ticked;
- a free text box appears beside OTHER only when OTHER is chosen.

Nothing is refused except a contact stimulated against itself. An unusual
pair warns and is recorded: non-adjacent pairs, pairs across electrodes
and monopolar stimulation are all practised.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..utils import i18n
from ..utils import stimulation as st
from .neuxelec_dialog import (
    SPIN_LEFT,
    SPIN_RIGHT,
    WARN,
    NeuXelecDialog,
    card,
    explain,
    field,
    section,
)

#: One click on the arrows beside the current.
CURRENT_STEP_MA = 0.5

#: The question the localisation asks, for each way of localising.
LOCALISATION_LABELS = {
    st.LOC_BODY: "where on the body",
    st.LOC_VISUAL_FIELD: "which part of the visual field",
    st.LOC_EAR: "which ear",
}


def _arrow_button(image: str, tip: str, on_click) -> QPushButton:
    """A step button carrying the application's own arrow, not a glyph.

    A character arrow depends on the font having it, and some do not:
    the button then looks empty.
    """
    button = QPushButton("")
    button.setObjectName("stepButton")
    button.setFixedSize(26, 26)
    button.setToolTip(tip)
    button.setCursor(Qt.PointingHandCursor)
    button.setIcon(QIcon(image))
    button.setIconSize(QSize(8, 12))
    button.clicked.connect(on_click)
    return button


def _value_or_not_set(box):
    """La valeur d'un champ, ou NOT_SET quand il affiche NA.

    Qt montre le texte special au minimum de la plage: ce minimum est
    donc la facon de dire "pas note".
    """
    if box.value() == box.minimum() and box.specialValueText():
        return st.NOT_SET

    return box.value()


def _set_value_or_na(box, value) -> None:
    """Remettre une valeur, NA compris."""
    box.setValue(box.minimum() if value is None else value)


def _warn_label() -> QLabel:
    label = QLabel("")
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {WARN}; font-size: 11px;")
    label.setVisible(False)
    return label


def _fill_words(box: QComboBox, values) -> None:
    """Show the words translated, keep the English one as the stored value."""
    box.clear()

    for value in values or ():
        box.addItem(i18n.tr(value), value)


def _word_of(box: QComboBox) -> str:
    """What the combo stands for, in English, whatever it shows."""
    data = box.currentData()
    return str(data if data is not None else box.currentText())


def _select_word(box: QComboBox, value: str) -> None:
    index = box.findData(str(value))

    if index >= 0:
        box.setCurrentIndex(index)


def _shrinkable(box: QComboBox, chars: int = 14) -> QComboBox:
    """Let a combo be narrower than its longest entry.

    By default a QComboBox is as wide as the widest item it holds, and one
    long descriptor would then set the width of the whole window.
    """
    box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(chars)
    return box


def _combo(pairs, current: str = "", chars: int = 14) -> QComboBox:
    """A combo over (key, label) pairs, carrying the key as item data.

    The label is translated, the key never is: what gets stored must not
    depend on the language the window was filled in.
    """
    box = QComboBox()

    for key, label in pairs:
        box.addItem(i18n.tr(label), key)

    if current:
        index = box.findData(current)

        if index >= 0:
            box.setCurrentIndex(index)

    return _shrinkable(box, chars)


class _ResponseRow(QFrame):
    """One response block: category, descriptor, sign, place, note.

    A block rather than a flat list of words, so that two responses to the
    same stimulation each keep their own localisation, and so that every
    input can carry the question it answers. A bare combo under <i>Motor</i>
    could be the descriptor, the body part or the side, and nothing on
    screen would say which.
    """

    def __init__(
        self,
        response: dict | None = None,
        on_remove=None,
        index: int = 1,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("responseBlock")
        self._on_remove = on_remove

        response = response or {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.lbl_index = section(f"{i18n.tr('response')} {index}")
        head.addWidget(self.lbl_index)
        head.addStretch(1)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setObjectName("closeWindowButton")
        self.btn_remove.setFixedSize(22, 22)
        self.btn_remove.setToolTip("Remove this response")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.clicked.connect(self._remove)
        head.addWidget(self.btn_remove)
        outer.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.cmb_category = _combo(
            [(c.key, c.label) for c in st.CATEGORIES],
            str(response.get("category", "")) or st.CATEGORIES[0].key,
            11,
        )
        self.cmb_descriptor = _shrinkable(QComboBox(), 14)
        self.cmb_sign = _combo(
            st.MOTOR_SIGNS, str(response.get("sign", "")) or "positive", 11
        )
        self.cmb_location = _shrinkable(QComboBox(), 11)
        self.cmb_laterality = _combo(
            st.LATERALITIES, str(response.get("laterality", "")) or "unspecified", 11
        )
        self.txt_other = QLineEdit(str(response.get("other", "")))
        self.txt_other.setPlaceholderText(i18n.tr("in your own words"))
        self.txt_note = QLineEdit(str(response.get("note", "")))
        self.txt_note.setPlaceholderText(
            i18n.tr("latency, how long it lasted, what the patient said")
        )

        self.fld_category = field("kind of response", self.cmb_category)
        self.fld_descriptor = field("what exactly", self.cmb_descriptor)
        self.fld_sign = field("movement", self.cmb_sign)
        self.fld_location = field("where", self.cmb_location)
        self.fld_laterality = field("which side", self.cmb_laterality)
        self.fld_other = field("describe it", self.txt_other)
        self.fld_note = field("note on this response", self.txt_note)

        # Deux colonnes, et une ligne par question qui s'applique: avec
        # trois colonnes, celles qui disparaissent laissaient un vide a
        # droite et tassaient le reste a gauche.
        grid.addWidget(self.fld_category, 0, 0)
        grid.addWidget(self.fld_descriptor, 0, 1)
        grid.addWidget(self.fld_location, 1, 0)
        grid.addWidget(self.fld_laterality, 1, 1)
        grid.addWidget(self.fld_sign, 2, 0)
        grid.addWidget(self.fld_other, 2, 1)
        grid.addWidget(self.fld_note, 3, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)

        self.cmb_category.currentIndexChanged.connect(self._on_category_changed)
        self.cmb_descriptor.currentIndexChanged.connect(self._refresh_other)

        self._on_category_changed()

        _select_word(self.cmb_descriptor, str(response.get("descriptor", "")))
        _select_word(self.cmb_location, str(response.get("location", "")))

        self._refresh_other()

    # ---------------------------------------------------- what is shown

    def set_index(self, index: int) -> None:
        self.lbl_index.setText(f"{i18n.tr('response').upper()} {int(index)}")

    def category_key(self) -> str:
        return str(self.cmb_category.currentData() or "")

    def _on_category_changed(self) -> None:
        """Refill the descriptors, and ask the question that now applies."""
        cat = st.category(self.category_key())

        self.cmb_descriptor.blockSignals(True)
        _fill_words(self.cmb_descriptor, cat.descriptors if cat is not None else ())
        self.cmb_descriptor.blockSignals(False)

        # The sign is a motor question only: a movement appeared, or an
        # ongoing one stopped.
        self.fld_sign.setVisible(bool(cat is not None and cat.signed))

        values = st.localisation_values(self.category_key())
        _fill_words(self.cmb_location, values)

        if values:
            self.fld_location.set_label(
                LOCALISATION_LABELS.get(cat.localisation, "where")
            )

        self.fld_location.setVisible(bool(values))
        self.fld_laterality.setVisible(bool(values))

        self._refresh_other()

    def _refresh_other(self) -> None:
        self.fld_other.setVisible(_word_of(self.cmb_descriptor) == st.OTHER)

    def _remove(self) -> None:
        if callable(self._on_remove):
            self._on_remove(self)

    # ---------------------------------------------------- the value

    def response(self) -> dict:
        cat = st.category(self.category_key())

        return st.new_response(
            self.category_key(),
            _word_of(self.cmb_descriptor),
            sign=str(self.cmb_sign.currentData() or "") if (cat and cat.signed) else "",
            location=(
                _word_of(self.cmb_location)
                if self.cmb_location.isVisibleTo(self)
                else ""
            ),
            laterality=str(self.cmb_laterality.currentData() or "unspecified"),
            other=self.txt_other.text().strip(),
            note=self.txt_note.text().strip(),
        )


class StimulationDialog(NeuXelecDialog):
    """Add or edit one stimulation result."""

    def __init__(
        self,
        electrodes: list[dict],
        elec_id: int,
        contact_idx: int,
        *,
        record: dict | None = None,
        anatomy_lookup: Callable[[str, int], str | None] | None = None,
        parent=None,
    ):
        self._electrodes = list(electrodes or [])
        self._elec_id = int(elec_id)
        self._contact_idx = int(contact_idx)
        self._record = dict(record or {})
        self._anatomy_lookup = anatomy_lookup
        #: Fields the user typed into: the frequency must not overwrite them.
        self._touched: set[str] = set()
        self._rows: list[_ResponseRow] = []

        name = str(self._electrodes[self._elec_id].get("name", "")) if self._electrodes else ""
        self._name_a = name
        label = st.contact_name(name, self._contact_idx)

        super().__init__(
            i18n.tr("Stimulation result"),
            f"{i18n.tr('pair stimulated from')} {label}",
            parent,
            with_language=True,
        )
        self.size_like_electrode_list()

        self._build()
        self._load()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        column = QVBoxLayout(inner)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(12)
        scroll.setWidget(inner)
        self.body.addWidget(scroll, 1)

        column.addWidget(self._build_pair())
        column.addWidget(self._build_protocol())
        column.addWidget(self._build_context())
        column.addWidget(self._build_events())
        column.addWidget(self._build_responses())
        column.addWidget(self._build_notes())
        column.addStretch(1)

        self.body.addLayout(self._build_buttons())

    def _build_pair(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("the stimulated pair"))

        row = QHBoxLayout()
        row.setSpacing(10)

        # Le contact de depart se choisit ici aussi: la fenetre peut etre
        # ouverte sans en designer un, depuis la liste des fiches.
        self.cmb_first = _shrinkable(QComboBox(), 10)
        self.cmb_first.setEditable(True)
        self.cmb_first.addItems(self._all_contact_names())
        self.cmb_first.setEditText(st.contact_name(self._name_a, self._contact_idx))
        self.cmb_first.currentTextChanged.connect(self._on_first_contact_changed)
        row.addWidget(field("stimulated from", self.cmb_first))

        self.cmb_polarity = _combo(st.POLARITIES, "bipolar", 10)
        self.cmb_polarity.currentIndexChanged.connect(self._on_polarity_changed)
        row.addWidget(field("polarity", self.cmb_polarity))

        # Editable so a contact can be typed, as asked, while the adjacent
        # one is already proposed.
        self.cmb_second = _shrinkable(QComboBox(), 10)
        self.cmb_second.setEditable(True)
        self.cmb_second.addItems(self._contact_choices())
        self.cmb_second.setEditText(self._adjacent_name())
        self.cmb_second.currentTextChanged.connect(self._on_pair_changed)
        self.fld_second = field("stimulated against", self.cmb_second)
        row.addWidget(self.fld_second)

        self.txt_reference = QLineEdit()
        self.txt_reference.setPlaceholderText(i18n.tr("e.g. scalp Fz"))
        self.fld_reference = field("remote reference", self.txt_reference)
        self.fld_reference.setVisible(False)
        row.addWidget(self.fld_reference)

        row.addStretch(1)
        inside.addLayout(row)

        self.lbl_pair_problem = _warn_label()
        inside.addWidget(self.lbl_pair_problem)

        self.lbl_anatomy = QLabel("")
        self.lbl_anatomy.setObjectName("fieldHint")
        self.lbl_anatomy.setWordWrap(True)
        self.lbl_anatomy.setVisible(False)
        inside.addWidget(self.lbl_anatomy)

        return frame

    def _build_protocol(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("stimulation protocol"))
        inside.addWidget(
            explain(
                "Choosing the frequency fills the rest with the usual values."
            )
        )

        row = QHBoxLayout()
        row.setSpacing(10)

        self.cmb_frequency = _shrinkable(QComboBox(), 5)
        self.cmb_frequency.setEditable(True)
        self.cmb_frequency.addItems([f"{hz:g}" for hz in st.FREQUENCY_PRESETS])
        self.cmb_frequency.addItem(st.NOT_AVAILABLE)
        self.cmb_frequency.setCurrentText(f"{st.LOW_FREQUENCY_HZ:g}")
        self.cmb_frequency.currentTextChanged.connect(self._on_frequency_changed)
        row.addWidget(field("frequency", self.cmb_frequency, unit="Hz"))

        current_box = QWidget()
        current_row = QHBoxLayout(current_box)
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row.setSpacing(4)

        btn_down = _arrow_button(
            SPIN_LEFT, f"{CURRENT_STEP_MA:g} mA less", lambda: self._step_current(-1)
        )
        current_row.addWidget(btn_down)

        self.spn_current = QDoubleSpinBox()
        self.spn_current.setDecimals(1)
        # Le minimum veut dire NA: un protocole non note n'est pas un
        # protocole a zero, et inventer un chiffre ferait croire a une
        # mesure.
        self.spn_current.setRange(0.0, 50.0)
        self.spn_current.setSpecialValueText(st.NOT_AVAILABLE)
        self.spn_current.setSingleStep(CURRENT_STEP_MA)
        self.spn_current.setValue(st.PROTOCOL_LOW["intensity_ma"])
        self.spn_current.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spn_current.setFixedWidth(64)
        self.spn_current.setAlignment(Qt.AlignCenter)
        self.spn_current.valueChanged.connect(self._on_current_changed)
        current_row.addWidget(self.spn_current)

        btn_up = _arrow_button(
            SPIN_RIGHT, f"{CURRENT_STEP_MA:g} mA more", lambda: self._step_current(1)
        )
        current_row.addWidget(btn_up)
        current_row.addStretch(1)

        row.addWidget(field("current", current_box, unit="mA"))

        self.spn_pulse = QSpinBox()
        self.spn_pulse.setRange(0, 5000)
        self.spn_pulse.setSpecialValueText(st.NOT_AVAILABLE)
        self.spn_pulse.setSingleStep(50)
        self.spn_pulse.setValue(st.PROTOCOL_LOW["pulse_width_us"])
        self.spn_pulse.valueChanged.connect(lambda _v: self._mark("pulse"))
        self.spn_pulse.valueChanged.connect(lambda _v: self._refresh_charge_warning())
        row.addWidget(field("pulse width", self.spn_pulse, unit="µs"))

        self.spn_train = QDoubleSpinBox()
        self.spn_train.setDecimals(1)
        self.spn_train.setRange(0.0, 300.0)
        self.spn_train.setSpecialValueText(st.NOT_AVAILABLE)
        self.spn_train.setValue(st.PROTOCOL_LOW["train_duration_s"])
        self.spn_train.valueChanged.connect(lambda _v: self._mark("train"))
        row.addWidget(field("train duration", self.spn_train, unit="s"))

        row.addStretch(1)
        inside.addLayout(row)

        second = QHBoxLayout()
        second.setSpacing(10)

        self.txt_threshold = QLineEdit()
        self.txt_threshold.setPlaceholderText("mA")
        self.txt_threshold.setFixedWidth(70)
        second.addWidget(
            field("response threshold", self.txt_threshold, unit="mA")
        )

        self.chk_ad_threshold = QCheckBox(
            i18n.tr("the current was at the after-discharge threshold")
        )
        second.addWidget(self.chk_ad_threshold, 0, Qt.AlignBottom)
        second.addStretch(1)
        inside.addLayout(second)

        self.lbl_charge = _warn_label()
        inside.addWidget(self.lbl_charge)

        return frame

    def _build_context(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("conditions of the examination"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.cmb_state = _combo(st.BEHAVIOURAL_STATES, "awake", 10)
        row.addWidget(field("patient was", self.cmb_state), 1)

        self.cmb_asm = _combo(st.ASM_STATES, "unspecified", 11)
        row.addWidget(field("medication", self.cmb_asm), 1)

        self.txt_since = QLineEdit()
        self.txt_since.setPlaceholderText(i18n.tr("e.g. 2 days"))
        row.addWidget(field("since the last seizure", self.txt_since), 1)

        inside.addLayout(row)

        # Sur sa propre ligne: c'est du texte libre, et quatre champs sur une
        # seule ligne imposaient leur largeur a toute la fenetre.
        self.txt_task = QLineEdit()
        self.txt_task.setPlaceholderText(i18n.tr("counting, naming, reading, holding a posture"))
        inside.addWidget(field("task performed during the stimulation", self.txt_task))

        return frame

    def _build_events(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("what happened on the trace"))
        inside.addWidget(
            explain(
                "Leave it all empty for a pair tested that stayed silent."
            )
        )

        self.chk_events: dict[str, QCheckBox] = {}

        inside.addWidget(section("discharges"))
        discharges = QHBoxLayout()
        discharges.setSpacing(18)

        for key, label in st.EVENT_DISCHARGES:
            box = QCheckBox(i18n.tr(label))
            box.toggled.connect(self._refresh_discharge_detail)
            self.chk_events[key] = box
            discharges.addWidget(box)

        discharges.addStretch(1)
        inside.addLayout(discharges)

        inside.addWidget(section("seizure"))

        for key, label in st.EVENT_SEIZURES:
            box = QCheckBox(i18n.tr(label))
            box.toggled.connect(self._refresh_discharge_detail)
            self.chk_events[key] = box
            inside.addWidget(box)

        other = QCheckBox(i18n.tr("Something else, described in the notes"))
        other.toggled.connect(self._refresh_discharge_detail)
        self.chk_events[st.OTHER] = other
        inside.addWidget(other)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.cmb_habitual = _combo(st.HABITUAL, "unspecified", 18)
        row.addWidget(
            field("was the patient's own event reproduced", self.cmb_habitual),
            1,
        )

        self.cmb_reproducibility = _combo(st.REPRODUCIBILITY, "single_trial", 18)
        row.addWidget(
            field("seen again on repeat stimulation", self.cmb_reproducibility),
            1,
        )

        inside.addLayout(row)

        # Shown only once there is a discharge or a seizure to describe.
        self.frm_discharge = QWidget()
        detail = QVBoxLayout(self.frm_discharge)
        detail.setContentsMargins(0, 6, 0, 0)
        detail.setSpacing(8)
        detail.addWidget(section("about that discharge"))

        where = QHBoxLayout()
        where.setSpacing(10)

        self.txt_ad_location = QLineEdit()
        self.txt_ad_location.setPlaceholderText(
            i18n.tr("the stimulated contacts, and any contact it spread to")
        )
        where.addWidget(field("where it was seen", self.txt_ad_location), 1)

        self.chk_ad_remote = QCheckBox(i18n.tr("away from the stimulated contacts"))
        where.addWidget(self.chk_ad_remote, 0, Qt.AlignBottom)
        detail.addLayout(where)

        self.txt_ad_evolution = QLineEdit()
        self.txt_ad_evolution.setPlaceholderText(
            i18n.tr("morphology, frequency, how far it spread")
        )
        detail.addWidget(field("how it evolved", self.txt_ad_evolution))

        self.chk_aborted = QCheckBox(i18n.tr("the stimulation had to be interrupted"))
        detail.addWidget(self.chk_aborted)

        inside.addWidget(self.frm_discharge)
        self.frm_discharge.setVisible(False)

        return frame

    def _build_responses(self) -> QFrame:
        frame, inside = card()

        head = QHBoxLayout()
        head.addWidget(section("clinical responses"))
        head.addStretch(1)
        self.btn_add_response = QPushButton(i18n.tr("+ add a response"))
        self.btn_add_response.setObjectName("secondaryButton")
        self.btn_add_response.clicked.connect(lambda: self._add_response())
        head.addWidget(self.btn_add_response)
        inside.addLayout(head)


        self.lay_responses = QVBoxLayout()
        self.lay_responses.setSpacing(10)
        inside.addLayout(self.lay_responses)

        self.lbl_no_response = explain("Tested and silent, unless you add one.")
        inside.addWidget(self.lbl_no_response)

        return frame

    def _build_notes(self) -> QFrame:
        frame, inside = card()
        inside.addWidget(section("notes and provenance"))

        self.txt_notes = QPlainTextEdit()
        self.txt_notes.setPlaceholderText(
            i18n.tr(
                "anything that bears on reading this card later: pain, "
                "distraction, what the patient said in their own words"
            )
        )
        self.txt_notes.setFixedHeight(74)
        inside.addWidget(field("free notes", self.txt_notes))

        self.txt_operator = QLineEdit()
        self.txt_operator.setPlaceholderText(i18n.tr("initials"))
        self.txt_operator.setFixedWidth(120)
        row = QHBoxLayout()
        row.addWidget(field("interpreted by", self.txt_operator))
        row.addStretch(1)
        inside.addLayout(row)

        return frame

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)

        self.btn_cancel = QPushButton(i18n.tr("Cancel"))
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(i18n.tr("Save"))
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self.accept)
        row.addWidget(self.btn_save)

        return row

    # ------------------------------------------------------- the choices

    def _contact_choices(self) -> list[str]:
        """Every contact, those of the same electrode first.

        The second contact of a bipolar pair is nearly always a neighbour,
        so the neighbours come first and the rest stays reachable.
        """
        same: list[str] = []
        others: list[str] = []

        for index, electrode in enumerate(self._electrodes):
            name = str(electrode.get("name", "")).strip()
            count = len(electrode.get("contacts_lps") or [])
            target = same if index == self._elec_id else others

            for contact in range(count):
                if index == self._elec_id and contact == self._contact_idx:
                    continue

                target.append(st.contact_name(name, contact))

        return same + others

    def _all_contact_names(self) -> list[str]:
        """Tous les contacts de l'implantation, dans l'ordre."""
        noms: list[str] = []

        for electrode in self._electrodes:
            name = str(electrode.get("name", "")).strip()

            for contact in range(len(electrode.get("contacts_lps") or [])):
                noms.append(st.contact_name(name, contact))

        return noms

    def _on_first_contact_changed(self, *_args) -> None:
        """Suivre le contact de depart: la paire et l'anatomie en dependent."""
        found = st.parse_contact_name(self.cmb_first.currentText(), self._electrodes)

        if found is not None:
            self._elec_id, self._contact_idx = found
            self._name_a = str(self._electrodes[self._elec_id].get("name", ""))

            # Le second contact suit: changer le depart invalide la paire,
            # et garder l'ancien second laisserait une paire a cheval sans
            # que personne l'ait demandee.
            self.cmb_second.blockSignals(True)
            self.cmb_second.clear()
            self.cmb_second.addItems(self._contact_choices())
            self.cmb_second.setEditText(self._adjacent_name())
            self.cmb_second.blockSignals(False)

        self._on_pair_changed()

    def _adjacent_name(self) -> str:
        """The contact just above, or just below for the last one."""
        if not self._electrodes:
            return ""

        electrode = self._electrodes[self._elec_id]
        count = len(electrode.get("contacts_lps") or [])
        name = str(electrode.get("name", "")).strip()

        if self._contact_idx + 1 < count:
            return st.contact_name(name, self._contact_idx + 1)

        if self._contact_idx > 0:
            return st.contact_name(name, self._contact_idx - 1)

        return ""

    # ------------------------------------------------------- reacting

    def _mark(self, field_name: str) -> None:
        self._touched.add(field_name)

    def _on_current_changed(self, _value) -> None:
        self._mark("current")
        self._refresh_charge_warning()

    def _step_current(self, direction: int) -> None:
        self.spn_current.setValue(
            float(self.spn_current.value()) + direction * CURRENT_STEP_MA
        )

    def _on_frequency_changed(self, _text) -> None:
        """Refill the protocol, without touching what was typed by hand."""
        frequence = self.frequency_hz()

        if frequence is st.NOT_SET:
            # Frequence inconnue: rien a deduire, on ne remplit rien.
            self._refresh_charge_warning()
            return

        defaults = st.default_protocol(frequence)

        if "current" not in self._touched:
            self.spn_current.blockSignals(True)
            self.spn_current.setValue(float(defaults["intensity_ma"]))
            self.spn_current.blockSignals(False)

        if "pulse" not in self._touched:
            self.spn_pulse.blockSignals(True)
            self.spn_pulse.setValue(int(defaults["pulse_width_us"]))
            self.spn_pulse.blockSignals(False)

        if "train" not in self._touched:
            self.spn_train.blockSignals(True)
            self.spn_train.setValue(float(defaults["train_duration_s"]))
            self.spn_train.blockSignals(False)

        self._refresh_charge_warning()

    def _refresh_charge_warning(self) -> None:
        message = st.charge_warning(
            _value_or_not_set(self.spn_current)
            if _value_or_not_set(self.spn_current) is not st.NOT_SET
            else None,
            _value_or_not_set(self.spn_pulse)
            if _value_or_not_set(self.spn_pulse) is not st.NOT_SET
            else None,
        )
        self.lbl_charge.setText(message or "")
        self.lbl_charge.setVisible(bool(message))

    def _on_polarity_changed(self) -> None:
        monopolar = self.polarity() == "monopolar"
        self.fld_second.setVisible(not monopolar)
        self.fld_reference.setVisible(monopolar)
        self._on_pair_changed()

    def _on_pair_changed(self, *_args) -> None:
        """Say what is wrong or unusual, and name the anatomy of the pair."""
        problem = self.pair_problem()
        self.lbl_pair_problem.setText(problem or "")
        self.lbl_pair_problem.setVisible(bool(problem))
        self._refresh_anatomy()

        if self.first_contact_problem() is None:
            self.set_subtitle(
                f"{i18n.tr('pair stimulated from')} "
                f"{st.contact_name(self._name_a, self._contact_idx)}"
            )

    def _refresh_discharge_detail(self) -> None:
        wanted = any(
            box.isChecked()
            for key, box in self.chk_events.items()
            if key != st.OTHER
        )
        self.frm_discharge.setVisible(bool(wanted))

    def _refresh_response_hint(self) -> None:
        self.lbl_no_response.setVisible(not self._rows)

        for position, row in enumerate(self._rows, start=1):
            row.set_index(position)

    def _add_response(self, response: dict | None = None) -> _ResponseRow:
        row = _ResponseRow(
            response, on_remove=self._remove_response, index=len(self._rows) + 1
        )
        self._rows.append(row)
        self.lay_responses.addWidget(row)
        self._refresh_response_hint()
        return row

    def _remove_response(self, row: _ResponseRow) -> None:
        if row in self._rows:
            self._rows.remove(row)

        row.setParent(None)
        row.deleteLater()
        self._refresh_response_hint()

    def _refresh_anatomy(self) -> None:
        """Name both contacts of the pair, from the parcellation if loaded.

        A bipolar pair often straddles two regions, and grey and white
        matter, so both are named rather than one.
        """
        if not callable(self._anatomy_lookup):
            self.lbl_anatomy.setVisible(False)
            return

        bits: list[str] = []

        for name, index in self._pair_contacts():
            if name is None or index is None:
                continue

            try:
                label = self._anatomy_lookup(name, index)
            except Exception:
                label = None

            if label:
                bits.append(f"{st.contact_name(name, index)} {label}")

        self.lbl_anatomy.setText("   ".join(bits))
        self.lbl_anatomy.setVisible(bool(bits))

    # ------------------------------------------------------- reading it

    def polarity(self) -> str:
        return str(self.cmb_polarity.currentData() or "bipolar")

    def frequency_hz(self):
        """La frequence, ou NOT_SET quand elle n'a pas ete notee."""
        texte = str(self.cmb_frequency.currentText()).strip()

        if texte.upper() == st.NOT_AVAILABLE:
            return st.NOT_SET

        try:
            return float(texte.replace(",", "."))
        except ValueError:
            return st.LOW_FREQUENCY_HZ

    def second_contact(self) -> tuple[int, int] | None:
        """The typed second contact, or None when there is none or it is unknown."""
        if self.polarity() == "monopolar":
            return None

        return st.parse_contact_name(self.cmb_second.currentText(), self._electrodes)

    def _pair_contacts(self) -> list[tuple[str | None, int | None]]:
        pair: list[tuple[str | None, int | None]] = [(self._name_a, self._contact_idx)]
        second = self.second_contact()

        if second is not None:
            elec_id, index = second
            pair.append((str(self._electrodes[elec_id].get("name", "")), index))

        return pair

    def first_contact_problem(self) -> str | None:
        """Ce qui cloche avec le contact de depart, ou None."""
        typed = str(self.cmb_first.currentText()).strip()

        if not typed:
            return "Name the contact the current was applied from."

        if st.parse_contact_name(typed, self._electrodes) is None:
            return f"No contact named {typed}."

        return None

    def pair_problem(self) -> str | None:
        """The sentence shown under the pair: an error, or an unusual choice."""
        premier = self.first_contact_problem()

        if premier is not None:
            return premier

        if self.polarity() == "monopolar":
            return None

        typed = str(self.cmb_second.currentText()).strip()

        if not typed:
            return "Name the second contact of the pair."

        second = st.parse_contact_name(typed, self._electrodes)

        if second is None:
            return f"No contact named {typed}."

        elec_b, idx_b = second

        error = st.pair_error(self._elec_id, self._contact_idx, elec_b, idx_b)

        if error is not None:
            return error

        return st.pair_warning(
            self._electrodes, self._elec_id, self._contact_idx, elec_b, idx_b
        )

    def pair_is_impossible(self) -> bool:
        """Only this blocks saving."""
        if self.first_contact_problem() is not None:
            return True

        if self.polarity() == "monopolar":
            return False

        second = st.parse_contact_name(self.cmb_second.currentText(), self._electrodes)

        if second is None:
            return True

        return (
            st.pair_error(self._elec_id, self._contact_idx, second[0], second[1]) is not None
        )

    def _threshold_ma(self) -> float | None:
        raw = str(self.txt_threshold.text()).strip().replace(",", ".")

        if not raw:
            return None

        try:
            return float(raw)
        except ValueError:
            return None

    def record(self) -> dict:
        """The stimulation as it will be stored."""
        second = self.second_contact()
        name_b = ""
        idx_b = None

        if second is not None:
            name_b = str(self._electrodes[second[0]].get("name", ""))
            idx_b = second[1]

        anatomy = [
            t
            for t in (
                str(self.lbl_anatomy.text()).split("   ") if self.lbl_anatomy.text() else []
            )
            if t
        ]

        return st.new_record(
            electrode=self._name_a,
            contact=self._contact_idx,
            electrode_b=name_b,
            contact_b=idx_b,
            polarity=self.polarity(),
            reference=self.txt_reference.text().strip(),
            frequency_hz=self.frequency_hz(),
            intensity_ma=_value_or_not_set(self.spn_current),
            pulse_width_us=_value_or_not_set(self.spn_pulse),
            train_duration_s=_value_or_not_set(self.spn_train),
            threshold_ma=self._threshold_ma(),
            at_ad_threshold=self.chk_ad_threshold.isChecked(),
            behavioural_state=str(self.cmb_state.currentData() or "unspecified"),
            asm=str(self.cmb_asm.currentData() or "unspecified"),
            time_since_last_seizure=self.txt_since.text().strip(),
            task=self.txt_task.text().strip(),
            events=[key for key, box in self.chk_events.items() if box.isChecked()],
            habitual=str(self.cmb_habitual.currentData() or "unspecified"),
            reproducibility=str(self.cmb_reproducibility.currentData() or "single_trial"),
            ad_location=self.txt_ad_location.text().strip(),
            ad_remote=self.chk_ad_remote.isChecked(),
            ad_evolution=self.txt_ad_evolution.text().strip(),
            aborted=self.chk_aborted.isChecked(),
            responses=[row.response() for row in self._rows],
            anatomy=anatomy,
            operator=self.txt_operator.text().strip(),
            notes=self.txt_notes.toPlainText().strip(),
            record_id=str(self._record.get("id", "")),
            created=str(self._record.get("created", "")),
        )

    # ------------------------------------------------------- editing one

    def _load(self) -> None:
        """Put an existing card back into the window, to be corrected."""
        record = self._record

        if not record:
            self._on_pair_changed()
            self._refresh_response_hint()
            return

        self.cmb_first.setEditText(
            st.contact_name(record.get("electrode", ""), record.get("contact", 0))
        )

        index = self.cmb_polarity.findData(str(record.get("polarity", "bipolar")))

        if index >= 0:
            self.cmb_polarity.setCurrentIndex(index)

        self.txt_reference.setText(str(record.get("reference", "")))

        if record.get("contact_b") is not None:
            self.cmb_second.setEditText(
                st.contact_name(record.get("electrode_b", ""), record.get("contact_b", 0))
            )

        # Set the protocol so the frequency cannot overwrite it.
        frequence = record.get("frequency_hz")
        self.cmb_frequency.setCurrentText(
            st.NOT_AVAILABLE if frequence is None else f"{float(frequence):g}"
        )
        self._touched.update({"current", "pulse", "train"})
        _set_value_or_na(self.spn_current, record.get("intensity_ma"))
        _set_value_or_na(self.spn_pulse, record.get("pulse_width_us"))
        _set_value_or_na(self.spn_train, record.get("train_duration_s"))

        if record.get("threshold_ma") is not None:
            self.txt_threshold.setText(f"{float(record['threshold_ma']):g}")

        self.chk_ad_threshold.setChecked(bool(record.get("at_ad_threshold", False)))

        for box, key in (
            (self.cmb_state, "behavioural_state"),
            (self.cmb_asm, "asm"),
            (self.cmb_habitual, "habitual"),
            (self.cmb_reproducibility, "reproducibility"),
        ):
            index = box.findData(str(record.get(key, "")))

            if index >= 0:
                box.setCurrentIndex(index)

        self.txt_since.setText(str(record.get("time_since_last_seizure", "")))
        self.txt_task.setText(str(record.get("task", "")))

        for key in record.get("events", []):
            box = self.chk_events.get(str(key))

            if box is not None:
                box.setChecked(True)

        self.txt_ad_location.setText(str(record.get("ad_location", "")))
        self.chk_ad_remote.setChecked(bool(record.get("ad_remote", False)))
        self.txt_ad_evolution.setText(str(record.get("ad_evolution", "")))
        self.chk_aborted.setChecked(bool(record.get("aborted", False)))

        for response in record.get("responses", []):
            self._add_response(response)

        self.txt_operator.setText(str(record.get("operator", "")))
        self.txt_notes.setPlainText(str(record.get("notes", "")))

        self._on_pair_changed()
        self._refresh_discharge_detail()
        self._refresh_response_hint()

    # ------------------------------------------------------- language

    def retranslate(self) -> None:
        """Rebuild in the new language, keeping everything already filled in.

        The card is read out first and put back after: changing language
        in the middle of an examination must not cost what was typed.
        """
        kept = self.record()
        kept["id"] = str(self._record.get("id", ""))
        kept["created"] = str(self._record.get("created", ""))

        self._record = kept
        self._rows = []
        self._touched = set()

        self.clear_body()
        self._build()
        self._load()

        self.set_title(i18n.tr("Stimulation result"))
        label = st.contact_name(self._name_a, self._contact_idx)
        self.set_subtitle(f"{i18n.tr('pair stimulated from')} {label}")

    # ------------------------------------------------------- accepting

    def accept(self) -> None:
        """Refuse only the impossible: a contact against itself, or no pair."""
        if self.pair_is_impossible():
            problem = self.pair_problem()
            self.lbl_pair_problem.setText(problem or "Name the second contact of the pair.")
            self.lbl_pair_problem.setVisible(True)
            return

        super().accept()
