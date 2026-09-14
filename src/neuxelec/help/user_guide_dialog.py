"""The User guide window: the whole manual, inside the application.

Same text as the PDF published on the website, so a user who forgot how
something works finds the answer without leaving NeuXelec (F1, or the
``User guide`` button in the left menu).

The window follows the NeuXelec frameless style: no native title bar, a rounded
shell with the rose border, its own close button, dragged by its header and
resized from its edges.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from .content import MANUAL_SECTIONS

_ACCENT = "#FF487D"

_QSS = """
QDialog { background: transparent; }

QFrame#guideShell {
    background-color: #06070D;
    border: 1.5px solid %(a)s;
    border-radius: 16px;
}
QFrame#guideHeader { background-color: transparent; border: none; }

QPushButton#closeWindowButton {
    color: #D8DAE4; background-color: transparent;
    border: 1px solid transparent; border-radius: 8px;
    font-size: 16px; font-weight: 700; padding: 0px;
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;
}
QPushButton#closeWindowButton:hover {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #FF8000, stop:1 #FF00A0);
}
QPushButton#closeWindowButton:pressed {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #E56F00, stop:1 #E0008C);
}

QLabel { background-color: transparent; border: none; }
QLabel#guideTitle { color: #F4D9D0; font-size: 16px; font-weight: 700;
                    letter-spacing: 0.6px; }
QLabel#guideSub { color: #7E8294; font-size: 11px; }

QLineEdit {
    background-color: #11131B; border: 1px solid #2B2D38; border-radius: 8px;
    color: #F2F2F5; padding: 6px 10px; font-size: 12px;
}
QLineEdit:focus { border: 1px solid %(a)s; }

QListWidget {
    background-color: #0E1017; border: 1px solid #2B2D38; border-radius: 10px;
    color: #C9CCDA; font-size: 12px; padding: 6px; outline: none;
}
QListWidget::item { padding: 8px 10px; border-radius: 7px; }
QListWidget::item:selected { background-color: #17181F; color: white;
                             border: 1px solid %(a)s; }

QTextBrowser {
    background-color: #0E1017; border: 1px solid #2B2D38; border-radius: 10px;
    color: #C9CCDA; font-size: 13px; padding: 14px;
}

QPushButton {
    color: #C9CCDA; background-color: #11131B; border: 1px solid #2B2D38;
    border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600;
}
QPushButton:hover { color: white; border: 1px solid %(a)s; }
QPushButton#guideClose { color: white; border: 1px solid %(a)s;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                      stop:0 #FF7A3D, stop:1 %(a)s); }

/* Same scroll bars as the rest of NeuXelec (MainWindow.ui). */
QScrollBar:vertical {
    background-color: #111218;
    width: 12px;
    margin: 4px 2px 4px 2px;
    border: none;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF8000,
        stop:1 #FF00A0
    );
    border-radius: 5px;
    min-height: 25px;
}
QScrollBar:horizontal {
    background-color: #111218;
    height: 12px;
    margin: 2px 4px 2px 4px;
    border: none;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF8000,
        stop:1 #FF00A0
    );
    border-radius: 5px;
    min-width: 25px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
""" % {"a": _ACCENT}

_HTML_HEAD = """
<style>
  h2 { color: #F4D9D0; font-size: 16px; margin-bottom: 2px; }
  h3 { color: #E7C6BC; font-size: 13px; margin-top: 14px; margin-bottom: 2px; }
  p, li { color: #C9CCDA; line-height: 150%; }
  b { color: #F2F2F5; }
  code { color: #FFB3C8; }
  th { color: #7E8294; font-size: 11px; border-bottom: 1px solid #2B2D38; }
  td { color: #C9CCDA; font-size: 12px; }
</style>
"""


class _GuideHeader(QFrame):
    """Header of the frameless window: titles, search box, close button.

    Dragging anywhere on it moves the window, exactly like the other NeuXelec
    dialogs.
    """

    def __init__(self, dialog: QDialog):
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setObjectName("guideHeader")

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and bool(event.buttons() & Qt.LeftButton):
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class UserGuideDialog(QDialog):
    """Sections on the left, the manual on the right, a search box on top."""

    def __init__(self, parent=None, on_replay_tour=None):
        super().__init__(parent)
        self._on_replay_tour = on_replay_tour
        self._resize_margin = 8

        self.setWindowTitle("NeuXelec user guide")
        self.setModal(False)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setSizeGripEnabled(False)
        self.setStyleSheet(_QSS)
        self.setMinimumSize(720, 480)
        self.resize(1040, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        shell = QFrame(self)
        shell.setObjectName("guideShell")
        shell.setMouseTracking(True)
        shell.installEventFilter(self)
        self._shell = shell
        outer.addWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(18, 12, 18, 16)
        root.setSpacing(12)

        header = _GuideHeader(self)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("USER GUIDE", header)
        title.setObjectName("guideTitle")
        sub = QLabel("Every page, every right-click menu, every shortcut.", header)
        sub.setObjectName("guideSub")
        titles.addWidget(title)
        titles.addWidget(sub)
        header_lay.addLayout(titles)
        header_lay.addStretch(1)
        self._search = QLineEdit(header)
        self._search.setPlaceholderText("Search the guide")
        self._search.setFixedWidth(260)
        header_lay.addWidget(self._search, 0, Qt.AlignVCenter)
        btn_close_window = QPushButton("✕", header)
        btn_close_window.setObjectName("closeWindowButton")
        btn_close_window.setCursor(Qt.PointingHandCursor)
        btn_close_window.setFixedSize(30, 30)
        btn_close_window.clicked.connect(self.close)
        header_lay.addWidget(btn_close_window, 0, Qt.AlignTop)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(12)
        self._list = QListWidget(shell)
        self._list.setFixedWidth(230)
        for section in MANUAL_SECTIONS:
            item = QListWidgetItem(section.title)
            item.setData(Qt.UserRole, section.id)
            self._list.addItem(item)
        self._text = QTextBrowser(shell)
        self._text.setOpenExternalLinks(True)
        body.addWidget(self._list)
        body.addWidget(self._text, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        self._btn_tour = QPushButton("Replay the guided tour", shell)
        close = QPushButton("Close", shell)
        close.setObjectName("guideClose")
        for b in (self._btn_tour, close):
            b.setCursor(Qt.PointingHandCursor)
        footer.addWidget(self._btn_tour)
        footer.addStretch(1)
        footer.addWidget(close)
        root.addLayout(footer)

        self._list.currentRowChanged.connect(self._show_section)
        self._search.textChanged.connect(self._on_search)
        self._btn_tour.clicked.connect(self._replay_tour)
        close.clicked.connect(self.close)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)

        self._list.setCurrentRow(0)

    # ------------------------------------------------------------------ slots
    def show_section(self, section_id: str) -> None:
        """Open the guide on a given section (used by the tour and F1)."""
        for row, section in enumerate(MANUAL_SECTIONS):
            if section.id == section_id:
                self._search.clear()
                self._list.setCurrentRow(row)
                self._show_section(row)
                return

    def _show_section(self, row: int) -> None:
        if not (0 <= row < len(MANUAL_SECTIONS)):
            return
        section = MANUAL_SECTIONS[row]
        self._text.setHtml(
            f"{_HTML_HEAD}<h2>{section.title}</h2>{section.body}"
        )

    def _on_search(self, text: str) -> None:
        needle = (text or "").strip().lower()
        if not needle:
            self._show_section(self._list.currentRow())
            return
        blocks = []
        for section in MANUAL_SECTIONS:
            if needle in section.title.lower() or needle in section.body.lower():
                blocks.append(f"<h2>{section.title}</h2>{section.body}")
        if not blocks:
            blocks = [f"<p>Nothing in the guide matches <b>{text}</b>.</p>"]
        self._text.setHtml(_HTML_HEAD + "".join(blocks))

    def _replay_tour(self) -> None:
        if callable(self._on_replay_tour):
            self.close()
            self._on_replay_tour()

    # ------------------------------------------------- frameless window resize
    def _resize_edges_at_position(self, pos: QPoint):
        rect = self._shell.rect()
        margin = int(self._resize_margin)
        edges = Qt.Edge(0)
        if pos.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= rect.width() - margin:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= margin:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= rect.height() - margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _update_resize_cursor(self, edges) -> None:
        if edges in (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        ):
            self._shell.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (
            Qt.Edge.RightEdge | Qt.Edge.TopEdge,
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
        ):
            self._shell.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self._shell.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self._shell.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self._shell.unsetCursor()

    def eventFilter(self, obj, event):  # noqa: N802
        try:
            if obj is self._shell:
                if event.type() == QEvent.MouseMove:
                    self._update_resize_cursor(
                        self._resize_edges_at_position(event.position().toPoint())
                    )
                elif event.type() == QEvent.MouseButtonPress:
                    if event.button() == Qt.LeftButton:
                        edges = self._resize_edges_at_position(
                            event.position().toPoint()
                        )
                        handle = self.windowHandle()
                        if edges and handle is not None and handle.startSystemResize(edges):
                            event.accept()
                            return True
                elif event.type() == QEvent.Leave:
                    self._shell.unsetCursor()
        except Exception:
            pass
        return super().eventFilter(obj, event)
