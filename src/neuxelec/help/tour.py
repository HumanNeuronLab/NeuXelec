"""Guided tour: a spotlight over the interface, one step at a time.

A single translucent widget covers the whole window and punches a hole around
the element being explained, so the rest of the interface dims out. A card
next to the hole carries the text and the navigation. Nothing is modal: the
tour can be left at any time and replayed from the User guide.

The steps come from :mod:`neuxelec.help.content`; this module only knows how to
show them.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.resources import resource_path
from .content import TOUR_STEPS

_DIM = QColor(6, 7, 12, 190)          # what covers the interface
_ACCENT = "#FF487D"                   # NeuXelec rose
_HOLE_MARGIN = 8                      # px around the highlighted widget
_CARD_GAP = 16                        # px between the hole and the card


class TourOverlay(QWidget):
    """Full-window overlay showing one tour step at a time."""

    finished = Signal()

    def __init__(self, window: QWidget, switch_page=None, steps=None):
        super().__init__(window)
        self._window = window
        self._switch_page = switch_page
        self._steps = list(steps if steps is not None else TOUR_STEPS)
        self._index = -1
        self._hole = QRect()
        self._target_widget: QWidget | None = None

        self.setObjectName("tourOverlay")
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

        self._build_card()
        window.installEventFilter(self)

    # ------------------------------------------------------------------ card
    def _build_card(self) -> None:
        self._card = QFrame(self)
        self._card.setObjectName("tourCard")
        self._card.setStyleSheet(
            """
            QFrame#tourCard {
                background-color: #0B0B0F;
                border: 1px solid #2B2D38;
                border-radius: 12px;
            }
            QLabel#tourStepCount { color: %(a)s; font-size: 10px; font-weight: 700;
                                   letter-spacing: 1.1px; }
            QLabel#tourTitle { color: #F4D9D0; font-size: 15px; font-weight: 700; }
            QLabel#tourBody  { color: #C9CCDA; font-size: 12px; }
            QPushButton {
                color: #C9CCDA; background-color: #11131B; border: 1px solid #2B2D38;
                border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { color: white; border: 1px solid %(a)s; }
            QPushButton#tourSkip { background-color: transparent; border: none;
                                   color: #7E8294; padding-left: 0px; }
            QPushButton#tourSkip:hover { color: #C9CCDA; }
            QPushButton#tourNext {
                color: white; border: 1px solid %(a)s;
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                  stop:0 #FF7A3D, stop:1 %(a)s);
            }
            """
            % {"a": _ACCENT}
        )
        lay = QVBoxLayout(self._card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        self._lbl_count = QLabel("", self._card)
        self._lbl_count.setObjectName("tourStepCount")
        self._lbl_title = QLabel("", self._card)
        self._lbl_title.setObjectName("tourTitle")
        self._lbl_title.setWordWrap(True)
        self._lbl_body = QLabel("", self._card)
        self._lbl_body.setObjectName("tourBody")
        self._lbl_body.setWordWrap(True)
        self._lbl_image = QLabel(self._card)
        self._lbl_image.setAlignment(Qt.AlignCenter)
        self._lbl_image.hide()

        lay.addWidget(self._lbl_count)
        lay.addWidget(self._lbl_title)
        lay.addWidget(self._lbl_body)
        lay.addWidget(self._lbl_image)

        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(8)
        self._btn_skip = QPushButton("Skip the tour", self._card)
        self._btn_skip.setObjectName("tourSkip")
        self._btn_prev = QPushButton("Back", self._card)
        self._btn_next = QPushButton("Next", self._card)
        self._btn_next.setObjectName("tourNext")
        for b in (self._btn_skip, self._btn_prev, self._btn_next):
            b.setCursor(Qt.PointingHandCursor)
        row.addWidget(self._btn_skip)
        row.addStretch(1)
        row.addWidget(self._btn_prev)
        row.addWidget(self._btn_next)
        lay.addLayout(row)

        self._btn_skip.clicked.connect(self.stop)
        self._btn_prev.clicked.connect(self.previous)
        self._btn_next.clicked.connect(self.next)
        self._card.setMaximumWidth(430)

    # ----------------------------------------------------------- public API
    def start(self) -> None:
        self.setGeometry(self._window.rect())
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self._index = -1
        self.next()

    def stop(self) -> None:
        self._anim.stop()
        self.hide()
        try:
            self._window.removeEventFilter(self)
        except Exception:
            pass
        self.finished.emit()
        self.deleteLater()

    def next(self) -> None:
        self._go(+1)

    def previous(self) -> None:
        self._go(-1)

    # --------------------------------------------------------------- steps
    def _go(self, direction: int) -> None:
        index = self._index + direction
        if index < 0:
            return
        if index >= len(self._steps):
            self.stop()
            return
        self._index = index
        step = self._steps[index]

        if step.page and self._switch_page is not None:
            try:
                self._switch_page(step.page)
            except Exception:
                pass
        delay = max(0, int(getattr(step, "delay_ms", 0)))
        QTimer.singleShot(delay or 0, lambda: self._render(index, direction))

    def _render(self, index: int, direction: int) -> None:
        if index != self._index or not self.isVisible():
            return
        step = self._steps[index]
        widget = self._resolve_target(step.target)

        # A step whose target is gone (page not built, feature not loaded) is
        # skipped rather than shown pointing at nothing.
        if step.target is not None and widget is None:
            self._go(direction or 1)
            return

        self._target_widget = widget
        self._fill_card(step, index)
        target_rect = self._rect_of(step.target)
        if self._hole.isNull():
            self._hole = target_rect
            self.update()
        else:
            self._anim.stop()
            self._anim.setStartValue(self._hole)
            self._anim.setEndValue(target_rect)
            self._anim.start()
        self._place_card(target_rect)

    def _fill_card(self, step, index: int) -> None:
        self._lbl_count.setText(f"STEP {index + 1} OF {len(self._steps)}")
        self._lbl_title.setText(step.title)
        self._lbl_body.setText(step.body)

        image = (step.extra or {}).get("image")
        if image:
            path = resource_path(f"resources/docs/figures/{image}")
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._lbl_image.setPixmap(
                    pix.scaled(360, 380, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self._lbl_image.show()
            else:
                self._lbl_image.hide()
        else:
            self._lbl_image.clear()
            self._lbl_image.hide()

        self._btn_prev.setEnabled(index > 0)
        self._btn_next.setText("Finish" if index == len(self._steps) - 1 else "Next")
        self._card.adjustSize()

    # -------------------------------------------------------------- geometry
    def _resolve_target(self, target) -> QWidget | None:
        names = [target] if isinstance(target, str) else list(target or [])
        for name in names:
            w = self._window.findChild(QWidget, name)
            if w is not None and w.isVisible():
                return w
        return None

    def _rect_of(self, target) -> QRect:
        """Union of the target widgets, in overlay coordinates."""
        names = [target] if isinstance(target, str) else list(target or [])
        rect = QRect()
        for name in names:
            w = self._window.findChild(QWidget, name)
            if w is None or not w.isVisible():
                continue
            top_left = w.mapTo(self._window, QPoint(0, 0))
            r = QRect(top_left, w.size())
            rect = r if rect.isNull() else rect.united(r)
        if rect.isNull():
            # No target: a centred hole of nothing, the card is simply centred.
            c = self.rect().center()
            return QRect(c.x(), c.y(), 0, 0)
        rect = rect.adjusted(-_HOLE_MARGIN, -_HOLE_MARGIN, _HOLE_MARGIN, _HOLE_MARGIN)
        # A column of cards can be taller than the window (it scrolls). Keep the
        # spotlight inside the overlay so the card is placed against what is
        # actually on screen.
        return rect.intersected(self.rect())

    def _place_card(self, hole: QRect) -> None:
        self._card.adjustSize()
        cw, ch = self._card.width(), self._card.height()
        W, H = self.width(), self.height()

        if hole.isEmpty():
            x, y = (W - cw) // 2, (H - ch) // 2
        else:
            below = H - hole.bottom() - _CARD_GAP
            above = hole.top() - _CARD_GAP
            right = W - hole.right() - _CARD_GAP
            if below >= ch:                      # under the hole
                x, y = hole.center().x() - cw // 2, hole.bottom() + _CARD_GAP
            elif above >= ch:                    # above it
                x, y = hole.center().x() - cw // 2, hole.top() - _CARD_GAP - ch
            elif right >= cw:                    # to its right
                x, y = hole.right() + _CARD_GAP, hole.center().y() - ch // 2
            else:                                # to its left
                x, y = hole.left() - _CARD_GAP - cw, hole.center().y() - ch // 2

        x = max(16, min(x, W - cw - 16))
        y = max(16, min(y, H - ch - 16))
        self._card.move(int(x), int(y))
        self._card.raise_()

    def _on_anim(self, value) -> None:
        self._hole = value if isinstance(value, QRect) else self._hole
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        if not self._hole.isEmpty():
            path.addRoundedRect(QRectF(self._hole), 12, 12)
        painter.fillPath(path, _DIM)

        if not self._hole.isEmpty():
            pen = QPen(QColor(_ACCENT))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self._hole), 12, 12)
        painter.end()

    # ------------------------------------------------------------- behaviour
    def mousePressEvent(self, event) -> None:  # noqa: N802
        # A click anywhere on the dimmed area moves on, like every tour.
        self.next()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key_Escape,):
            self.stop()
        elif key in (Qt.Key_Right, Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.next()
        elif key in (Qt.Key_Left, Qt.Key_Backspace):
            self.previous()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._window and event.type() in (QEvent.Resize, QEvent.Move):
            self.setGeometry(self._window.rect())
            if 0 <= self._index < len(self._steps):
                rect = self._rect_of(self._steps[self._index].target)
                self._hole = rect
                self._place_card(rect)
                self.update()
        return False


def run_tour(window: QWidget, switch_page=None, steps=None) -> TourOverlay:
    """Start the guided tour on ``window`` and return the overlay."""
    overlay = TourOverlay(window, switch_page=switch_page, steps=steps)
    overlay.start()
    return overlay
