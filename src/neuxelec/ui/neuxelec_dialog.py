"""The frameless NeuXelec window: near-black shell, rose border, dragged by its head.

Three dialogs had already each carried their own copy of this stylesheet, which
is how three windows end up almost alike. Anything new builds on this one, and
a change to the look happens once.

Subclasses fill :attr:`body`, a QVBoxLayout inside the shell, and get the title
bar, the close button, the dragging, the resize grip and the app's scrollbars
without writing any of it.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt

from ..utils import i18n
from ..utils.resources import resource_path
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

#: The palette, named once so a trace colour or a status pill can reuse it.
INK = "#06070D"
#: Les trois valeurs des encadres de la fenetre principale, reprises telles
#: quelles: une fenetre qui ne ressemble pas au logiciel n'en fait pas partie.
PANEL = "#11131B"
FIELD = "#151720"
LINE = "#252834"
#: Le contour des champs de saisie, plus clair que celui des encadres, comme
#: dans la fenetre principale.
FIELD_LINE = "#2B2D38"
TEXT = "#F2F2F5"
MUTED = "#9398A8"
FAINT = "#717786"
ROSE = "#FF487D"
OK = "#4ED07A"
WARN = "#FFA23A"
BAD = "#FF6B8A"

#: Width of the band around the shell that resizes the window, in the
#: translucent margin where there is nothing else to click.
RESIZE_BAND = 10

#: La liste d'electrodes de la fenetre principale fait 300 px de large.
#: Les fenetres de stimulation en font deux fois et demie, et sont aussi
#: hautes qu'elle: on les lit a cote d'elle, pas par-dessus la vue.
ELECTRODE_LIST_WIDTH = 300


def _image(name: str) -> str:
    """An absolute URL for a stylesheet: Qt resolves a relative one from
    the working directory, which is not where the images are."""
    return resource_path(f"resources/images/{name}").as_posix()


SPIN_UP = _image("spin_up.svg")
SPIN_DOWN = _image("spin_down.svg")
SPIN_LEFT = _image("spin_left.svg")
SPIN_RIGHT = _image("spin_right.svg")
CHECK_CROSS = _image("neuxelec_checkbox_cross.svg")

STYLE = f"""
QDialog {{ background: transparent; }}
QFrame#dialogShell {{
    background-color: {INK};
    border: 1.5px solid {ROSE};
    border-radius: 16px;
}}
QFrame#customDialogHeader {{ background: transparent; border: none; }}
QPushButton#closeWindowButton {{
    color: #D8DAE4; background: transparent; border: 1px solid transparent;
    border-radius: 8px; font-size: 16px; font-weight: 700; padding: 0px;
}}
QPushButton#closeWindowButton:hover {{
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}}
QLabel {{ color: {TEXT}; background: transparent; border: none; }}
QLabel#dialogTitle {{
    color: #F4D9D0; font-size: 18px; font-weight: 600; letter-spacing: 1px;
}}
QLabel#dialogSubtitle {{ color: {MUTED}; font-size: 12px; }}
QLabel#columnHeader {{
    color: {FAINT}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}}
/* The small caps above one input, saying what it asks for. */
QLabel#fieldLabel {{
    color: {FAINT}; font-size: 9px; font-weight: 700; letter-spacing: 1px;
}}
QLabel#fieldHint {{ color: {FAINT}; font-size: 10px; }}
QComboBox#languageChooser {{
    background-color: #15171F; color: {MUTED}; border: 1px solid {LINE};
    border-radius: 8px; font-size: 11px; min-height: 18px;
}}
QComboBox#languageChooser:hover {{ border: 1px solid {ROSE}; color: {TEXT}; }}
/* A scroll area shows the default light background between its children
   unless both it and its viewport are made transparent. */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > .QWidget {{ background: transparent; }}
QScrollArea > .QWidget > .QWidget {{ background: transparent; }}
QTabWidget > .QWidget {{ background: transparent; }}
QLabel#statusOk {{ color: {OK}; font-size: 11px; }}
QLabel#statusWarn {{ color: {WARN}; font-size: 11px; }}
QLabel#statusBad {{ color: {BAD}; font-size: 11px; }}
QFrame#card {{
    background-color: {PANEL}; border: 1px solid {LINE}; border-radius: 12px;
}}
/* Un bloc a l'interieur d'un encadre: plus sombre que lui, et marque a
   gauche, pour qu'on voie d'un coup d'oeil ou il commence et ou il finit. */
QFrame#responseBlock {{
    background-color: #0C0E15; border: 1px solid {LINE};
    border-left: 2px solid {ROSE}; border-radius: 10px;
}}
QPushButton#secondaryButton, QPushButton#primaryButton {{
    border-radius: 10px; font-size: 13px; font-weight: 600;
    padding: 6px 18px 6px 18px;
}}
QPushButton#secondaryButton {{
    color: white; background-color: #17181F; border: 1px solid #2B2D38;
}}
QPushButton#secondaryButton:hover {{
    background-color: #20222B; border: 1px solid {ROSE};
}}
QPushButton#primaryButton {{
    color: white; border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
}}
QPushButton#primaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF922B, stop:1 #FF33B8);
}}
QPushButton#stepButton {{
    color: #D8DAE4; background-color: #15171F; border: 1px solid #2B2D38;
    border-radius: 8px; font-size: 14px; font-weight: 700;
}}
QPushButton#stepButton:hover {{ border: 1px solid {ROSE}; color: white; }}
QTreeWidget, QListWidget, QPlainTextEdit, QTableWidget {{
    background-color: {FIELD}; border: 1px solid {LINE}; border-radius: 10px;
    color: #D5D7E1; outline: none;
}}
QTreeWidget::item, QListWidget::item {{ padding: 3px 4px 3px 2px; border: none; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: #1C1F2A; color: white;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{ background-color: #171A23; }}
QHeaderView::section {{
    background-color: transparent; color: {FAINT}; border: none;
    border-bottom: 1px solid {LINE}; padding: 4px; font-size: 10px;
    font-weight: 700; letter-spacing: 1px;
}}
QTreeWidget::indicator, QListWidget::indicator, QCheckBox::indicator {{
    width: 15px; height: 15px; background-color: #151720;
    border: 1px solid #353844; border-radius: 4px;
}}
QTreeWidget::indicator:hover, QCheckBox::indicator:hover {{ border: 1px solid {ROSE}; }}
QTreeWidget::indicator:checked, QCheckBox::indicator:checked {{
    border: 1px solid {ROSE}; background-color: {FIELD};
    image: url({CHECK_CROSS}); 
}}
QTreeWidget::indicator:checked:hover, QCheckBox::indicator:checked:hover {{
    background-color: #181A24;
}}
QTreeWidget::indicator:indeterminate {{
    border: 1px solid {ROSE}; background-color: #4A2233;
}}
QCheckBox {{ color: {MUTED}; font-size: 11px; spacing: 7px; }}
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {{
    background-color: {FIELD}; color: #D5D7E1; border: 1px solid {FIELD_LINE};
    border-radius: 8px; padding: 3px 8px 3px 8px; min-height: 20px;
}}
QComboBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{ border: 1px solid {ROSE}; }}
QComboBox::drop-down {{ border: none; width: 16px; }}
QComboBox QAbstractItemView {{
    background-color: {FIELD}; color: #D5D7E1;
    border: 1px solid {ROSE}; selection-background-color: #1C1F2A;
}}
QSlider::groove:horizontal {{
    height: 4px; background: #23262F; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF8000, stop:1 #FF00A0);
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 12px; margin: -5px 0; border-radius: 6px;
    background: #F2F2F5; border: 1px solid {ROSE};
}}
QTabWidget::pane {{
    background: transparent; border: 1px solid {LINE};
    border-radius: 12px; top: -1px;
}}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    color: {MUTED}; background-color: #15171F;
    border: 1px solid {LINE}; border-bottom: none;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
    padding: 6px 16px 6px 16px; margin-right: 3px;
    font-size: 12px; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {TEXT}; border: 1px solid {ROSE}; border-bottom: none; }}
QTabBar::tab:selected {{
    color: white; background-color: {PANEL};
    border: 1px solid {ROSE}; border-bottom: none;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; background-color: #1D1F29; border: none;
    border-left: 1px solid {FIELD_LINE}; border-bottom: 1px solid {FIELD_LINE};
    border-top-right-radius: 7px; margin: 1px 1px 0px 0px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; background-color: #1D1F29; border: none;
    border-left: 1px solid {FIELD_LINE};
    border-bottom-right-radius: 7px; margin: 0px 1px 1px 0px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #282A34;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({SPIN_UP}); width: 9px; height: 6px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({SPIN_DOWN}); width: 9px; height: 6px;
}}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{
    background-color: transparent; border: none; width: 10px;
    margin: 5px 2px 5px 2px; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    min-height: 28px; background-color: #3B3E48;
    border: 1px solid {ROSE}; border-radius: 5px;
}}
QScrollBar:horizontal {{
    background-color: transparent; border: none; height: 10px;
    margin: 2px 5px 2px 5px; border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    min-width: 28px; background-color: #3B3E48;
    border: 1px solid {ROSE}; border-radius: 5px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px; height: 0px; border: none; background: transparent;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; border: none; }}
QSizeGrip#dialogResizeGrip {{ background: transparent; border: none; image: none; }}
"""


class _Header(QFrame):
    """The title bar: the window has none of its own, so this one drags it."""

    def __init__(
        self,
        dialog: QDialog,
        title: str,
        subtitle: str = "",
        parent=None,
        with_language: bool = False,
    ):
        super().__init__(parent)
        self.dialog = dialog
        self._offset: QPoint | None = None
        self.setObjectName("customDialogHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(0)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setObjectName("dialogTitle")
        texts.addWidget(self.lbl_title)
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setObjectName("dialogSubtitle")
        texts.addWidget(self.lbl_subtitle)
        layout.addLayout(texts)
        layout.addStretch(1)

        # Reduire: la fenetre reste ouverte, hors du chemin. Sans ce
        # bouton, une fenetre sans cadre ne peut que se fermer, et on
        # perd ce qu'on avait pose dedans.
        self.btn_minimise = QPushButton("–")
        self.btn_minimise.setObjectName("closeWindowButton")
        self.btn_minimise.setCursor(Qt.PointingHandCursor)
        self.btn_minimise.setFixedSize(30, 30)
        self.btn_minimise.setToolTip("Put it out of the way")
        self.btn_minimise.clicked.connect(self.dialog.showMinimized)

        # Not everyone at the hospital reads English, and a window nobody
        # can read is a window nobody fills in.
        self.cmb_language = None

        if with_language:
            self.cmb_language = QComboBox()
            self.cmb_language.setObjectName("languageChooser")
            self.cmb_language.setFixedWidth(104)

            for code, label in i18n.LANGUAGES:
                self.cmb_language.addItem(label, code)

            index = self.cmb_language.findData(i18n.language())

            if index >= 0:
                self.cmb_language.setCurrentIndex(index)

            self.cmb_language.currentIndexChanged.connect(
                lambda _i: self.dialog.change_language(
                    str(self.cmb_language.currentData() or i18n.ENGLISH)
                )
            )
            layout.addWidget(self.cmb_language, 0, Qt.AlignRight | Qt.AlignTop)

        layout.addWidget(self.btn_minimise, 0, Qt.AlignRight | Qt.AlignTop)

        # The window has no frame of its own, so it carries its own button
        # to fill the screen. Dragging an edge works too, but a window that
        # can only be grown by a 16 px corner reads as a window that cannot.
        self.btn_maximise = QPushButton("□")
        self.btn_maximise.setObjectName("closeWindowButton")
        self.btn_maximise.setCursor(Qt.PointingHandCursor)
        self.btn_maximise.setFixedSize(30, 30)
        self.btn_maximise.setToolTip("Fill the screen")
        self.btn_maximise.clicked.connect(self.dialog.toggle_maximised)
        layout.addWidget(self.btn_maximise, 0, Qt.AlignRight | Qt.AlignTop)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("closeWindowButton")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.clicked.connect(self.dialog.reject)
        layout.addWidget(self.btn_close, 0, Qt.AlignRight | Qt.AlignTop)

    def set_title(self, text: str) -> None:
        self.lbl_title.setText(str(text).upper())

    def set_subtitle(self, text: str) -> None:
        self.lbl_subtitle.setText(text)

    def set_maximised(self, maximised: bool) -> None:
        self.btn_maximise.setText("❐" if maximised else "□")
        self.btn_maximise.setToolTip(
            "Back to the previous size" if maximised else "Fill the screen"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._offset = event.globalPosition().toPoint() - self.dialog.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._offset is not None and bool(event.buttons() & Qt.LeftButton):
            self.dialog.move(event.globalPosition().toPoint() - self._offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """What a double click on a title bar does everywhere else."""
        if event.button() == Qt.LeftButton:
            self.dialog.toggle_maximised()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)


class NeuXelecDialog(QDialog):
    """Frameless shell. Subclasses add their widgets to ``self.body``."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent=None,
        with_language: bool = False,
    ):
        super().__init__(parent)
        # Une vraie fenetre, pas seulement un dialogue: c'est ce qui lui
        # donne sa place dans la barre des taches, donc le droit d'etre
        # reduite sans etre perdue.
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(STYLE)
        # Without tracking, the cursor would only change while a button is
        # held, which is after the moment it is needed.
        self.setMouseTracking(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        self.shell = QFrame()
        self.shell.setObjectName("dialogShell")
        outer.addWidget(self.shell)

        inner = QVBoxLayout(self.shell)
        inner.setContentsMargins(16, 8, 16, 12)
        inner.setSpacing(10)

        self.header = _Header(self, title, subtitle, with_language=with_language)
        inner.addWidget(self.header)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        inner.addLayout(self.body, 1)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip = QSizeGrip(self.shell)
        grip.setObjectName("dialogResizeGrip")
        grip.setFixedSize(16, 16)
        grip_row.addWidget(grip, 0, Qt.AlignRight | Qt.AlignBottom)
        inner.addLayout(grip_row)

    def size_like_electrode_list(self, times: float = 2.5) -> None:
        """Comme la liste d'electrodes: 2,5 fois sa largeur, sa hauteur.

        Et un minimum assez petit pour qu'on puisse la reduire et
        continuer a se promener dans la page derriere.
        """
        largeur = int(ELECTRODE_LIST_WIDTH * float(times))
        hauteur = 900

        parent = self.parentWidget()

        if parent is not None and parent.window() is not None:
            fenetre = parent.window()

            if fenetre.height() > 300:
                hauteur = int(fenetre.height() * 0.94)

        self.setMinimumSize(360, 260)
        self.resize(largeur, hauteur)

    def set_title(self, text: str) -> None:
        self.header.set_title(text)

    def set_subtitle(self, text: str) -> None:
        self.header.set_subtitle(text)

    # ------------------------------------------------------------ language

    def change_language(self, code: str) -> None:
        """Switch language and rebuild, rather than re-set every label.

        Two hundred widgets would each need a setter, and the one that was
        forgotten would stay in the other language for good. Rebuilding
        cannot forget one; the subclass only has to put its values back.
        """
        if code == i18n.language():
            return

        i18n.set_language(code)
        self.retranslate()

    def retranslate(self) -> None:
        """Rebuild in the current language. Subclasses do the work."""

    def clear_body(self) -> None:
        """Empty the body layout, widgets and nested layouts alike."""
        _clear_layout(self.body)

    # ------------------------------------------------------------ resizing

    def toggle_maximised(self) -> None:
        """Fill the screen, or go back to the size the window had."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

        self.header.set_maximised(self.isMaximized())

    def _resize_edges(self, pos) -> Qt.Edges:
        """Which edges the cursor is on, inside the translucent margin.

        The window is frameless, so nothing resizes it unless this does.
        The band sits in the 10 px margin around the shell, where there is
        nothing else to click.
        """
        edges = Qt.Edges()

        if self.isMaximized():
            return edges

        x, y = pos.x(), pos.y()

        if x <= RESIZE_BAND:
            edges |= Qt.LeftEdge
        elif x >= self.width() - RESIZE_BAND:
            edges |= Qt.RightEdge

        if y <= RESIZE_BAND:
            edges |= Qt.TopEdge
        elif y >= self.height() - RESIZE_BAND:
            edges |= Qt.BottomEdge

        return edges

    @staticmethod
    def _cursor_for_edges(edges) -> Qt.CursorShape | None:
        if edges in (Qt.LeftEdge, Qt.RightEdge):
            return Qt.SizeHorCursor

        if edges in (Qt.TopEdge, Qt.BottomEdge):
            return Qt.SizeVerCursor

        if edges in (
            Qt.TopEdge | Qt.LeftEdge,
            Qt.BottomEdge | Qt.RightEdge,
        ):
            return Qt.SizeFDiagCursor

        if edges in (
            Qt.TopEdge | Qt.RightEdge,
            Qt.BottomEdge | Qt.LeftEdge,
        ):
            return Qt.SizeBDiagCursor

        return None

    def mouseMoveEvent(self, event) -> None:
        shape = self._cursor_for_edges(self._resize_edges(event.position().toPoint()))

        if shape is None:
            self.unsetCursor()
        else:
            self.setCursor(shape)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            edges = self._resize_edges(event.position().toPoint())

            if edges:
                handle = self.windowHandle()

                if handle is not None and handle.startSystemResize(edges):
                    event.accept()
                    return

        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:
        self.unsetCursor()
        super().leaveEvent(event)


def _clear_layout(layout) -> None:
    """Take a layout apart, children included."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()

        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue

        child = item.layout()

        if child is not None:
            _clear_layout(child)
            child.deleteLater()


def card(*, spacing: int = 8, margins: tuple[int, int, int, int] = (12, 10, 12, 10)) -> tuple[QFrame, QVBoxLayout]:
    """A panel in the app's style, with its layout ready to fill."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return frame, layout


def section(text: str) -> QLabel:
    """A card title. It translates itself, so no call site has to."""
    label = QLabel(i18n.tr(text).upper())
    label.setObjectName("columnHeader")
    return label


class Field(QWidget):
    """One input with a label above it saying what it asks for.

    A row of bare combo boxes is unreadable: the second one under
    <i>Motor</i> could be the descriptor, the body part or the side, and
    nothing on screen says which. The label is not decoration, it is what
    makes the input answerable.

    The label can be changed later, for the cases where the question
    itself depends on another field.
    """

    def __init__(
        self,
        label: str,
        widget: QWidget,
        hint: str = "",
        unit: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.widget = widget
        # Translated here rather than at every call site: a label nobody
        # translated is a question nobody can answer.
        label = i18n.tr(label)
        hint = i18n.tr(hint) if hint else hint
        # The unit is not a word: mA uppercased reads MA, which is not
        # a unit at all.
        self._unit = str(unit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.label = QLabel("")
        self.label.setObjectName("fieldLabel")
        self._set_label_text(label)
        layout.addWidget(self.label)
        layout.addWidget(widget)

        self.hint = QLabel(hint)
        self.hint.setObjectName("fieldHint")
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        layout.addWidget(self.hint)

    def _set_label_text(self, text: str) -> None:
        shown = str(text).upper()

        if self._unit:
            shown = f"{shown} ({self._unit})"

        self.label.setText(shown)

    def set_label(self, text: str) -> None:
        self._set_label_text(i18n.tr(str(text)))

    def set_hint(self, text: str) -> None:
        self.hint.setText(str(text))
        self.hint.setVisible(bool(text))


def field(label: str, widget: QWidget, hint: str = "", unit: str = "") -> Field:
    return Field(label, widget, hint, unit)


def explain(text: str) -> QLabel:
    """A sentence under a card, saying what the card is for."""
    label = QLabel(i18n.tr(text))
    label.setObjectName("fieldHint")
    label.setWordWrap(True)
    return label
