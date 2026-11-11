"""The packager's mini log: the current state of the project, never a history.

It is rebuilt on every check: the problems in red (errors) and yellow (warnings), or green lines when everything is
fine; after a Build, the build report until the next edit. Nothing piles up, so there is nothing to clear or copy.
One row per message in a monospaced font: a rounded level pill (OK green, ERROR red, WARNING yellow, INFO blue) and
the message; long messages wrap under the message, not under the pill. A row that points at a field is clickable as
a whole: on hover it is tinted in its level's colour from one edge of the box to the other, and a click goes to the
field.
"""

import math

from ..qt_compat import QtCore, QtGui, QtWidgets, Qt, Signal
from ..ui_scale import pt, px
from . import controls
from .controls import Themed

MAX_ENTRIES = 30
LEVELS = {  # level -> (label, colour role)
    "OK": ("OK", "log_success"),
    "ERROR": ("ERROR", "log_error"),
    "WARNING": ("WARN", "log_warning"),
    "INFO": ("INFO", "log_info"),
}
PILL_CHARS = 8  # Every pill has the same width, so the messages start in one column; ERROR has room to breathe
LINE_HEIGHT = 100  # percent: the room between rows comes from ROW_PADDING, so it is the same above and below
ROW_PADDING = 5  # Above and below the text of a row, inside its hover tint
SIDE_PADDING = 8
FONT_FAMILIES = ("Cascadia Mono", "Consolas", "Courier New")


def _monospace(size):
    font = QtGui.QFont()
    font.setStyleHint(QtGui.QFont.TypeWriter)
    try:
        families = set(QtGui.QFontDatabase.families())  # Qt 6: static
    except TypeError:
        families = set(QtGui.QFontDatabase().families())  # Qt 5 (3ds Max 2022-2024)
    for family in FONT_FAMILIES:
        if family in families:
            font.setFamily(family)
            break
    font.setPointSizeF(size)
    return font


def _text_x(line, position):
    x = line.cursorToX(position)  # A number, or an (x, position) pair in some Qt for Python versions
    return x[0] if isinstance(x, tuple) else x


def pill_box(line, cap_height):
    """Top (within the block) and height of a level pill on `line`, centred on the capital letters, so the label
    sits in the middle of its pill. Every text line is measured the same way for even rows."""
    height = cap_height + px(6)
    return line.y() + line.ascent() - (cap_height + height) / 2.0, height


def paint_pills(view, painter, offset):
    """Every level pill of `view`: a rounded box over the blank cells kept for it in the text, and its label painted
    exactly in the middle, across and up and down (centred on the capital letters), whatever the label's length.
    `view.pills`: block -> (start, length, colour, label, label colour)."""
    document = view.document()
    layout = document.documentLayout()
    metrics = QtGui.QFontMetricsF(view.pill_font)
    ratio = view.devicePixelRatioF() or 1.0

    def snap(value):  # To a whole screen pixel (also at 125 % and 150 %): sharp text. Down, never up: round()
        return math.floor(value * ratio + 0.5) / ratio  # goes to the even pixel and shifts some labels right
    painter.setFont(view.pill_font)
    for number, (start, length, color, label, text_color) in view.pills.items():
        block = document.findBlockByNumber(number)
        line = block.layout().lineForTextPosition(start)
        if not line.isValid():
            continue
        origin = layout.blockBoundingRect(block).topLeft() + offset
        left, right = _text_x(line, start), _text_x(line, start + length)
        top, height = pill_box(line, view.cap_height)
        rect = QtCore.QRectF(origin.x() + left, origin.y() + top, right - left, height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, height / 2.0, height / 2.0)
        painter.setPen(text_color)
        painter.drawText(QtCore.QPointF(snap(rect.center().x() - metrics.horizontalAdvance(label) / 2.0),
                                        snap(rect.center().y() + view.cap_height / 2.0)), label)
    painter.setPen(Qt.NoPen)


def _visual_span(document, number, cap_height):
    block = document.findBlockByNumber(number)
    layout = block.layout()
    origin = document.documentLayout().blockBoundingRect(block).top()
    first, last = layout.lineAt(0), layout.lineAt(max(0, layout.lineCount() - 1))
    if not first.isValid():
        return origin, origin
    last_top, height = pill_box(last, cap_height)
    return origin + pill_box(first, cap_height)[0], origin + last_top + height


def band_span(document, number, cap_height, to_edges=False):
    """Top and bottom (document coordinates) of the band behind a block: halfway to the block above and halfway to
    the block below, so the text has the same room above and below and neighbouring bands meet. The first and the
    last block reach the ends of the document (`to_edges`) or get the same room as between blocks."""
    count = document.blockCount()
    top, bottom = _visual_span(document, number, cap_height)
    above = _visual_span(document, number - 1, cap_height)[1] if number > 0 else None
    below = _visual_span(document, number + 1, cap_height)[0] if number + 1 < count else None
    half = ((below - bottom) if below is not None else (top - above) if above is not None else px(8)) / 2.0
    if above is not None:
        start = (above + top) / 2.0
    else:
        start = 0.0 if to_edges else top - half
    if below is not None:
        end = (bottom + below) / 2.0
    else:
        end = document.documentLayout().documentSize().height() if to_edges else bottom + half
    return start, end


class _LogView(QtWidgets.QTextEdit):
    """Read-only text whose blocks are rows. `rows`: block -> target ("tab|field" or ""); `pills`: block ->
    (start, length, colour). Pills and the hover tint are painted under the text (a character background has no
    rounded ends)."""

    row_clicked = Signal(str)

    def __init__(self):
        QtWidgets.QTextEdit.__init__(self)
        self.rows, self.pills = {}, {}
        self.hover = -1
        self.hover_colors = {}  # row -> the tint of its level (red for an error row)
        self.cap_height = 8.0
        self.pill_font = QtGui.QFont()
        self.setObjectName("toolStatusView")  # No style sheet padding: the hover tint goes from edge to edge
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.setWordWrapMode(QtGui.QTextOption.WordWrap)  # Breaks at spaces only: web addresses stay whole
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)

    def apply_margins(self):
        """Text inset from the box: SIDE_PADDING on the sides, ROW_PADDING above the first and below the last row."""
        document = self.document()
        document.setDocumentMargin(0)
        root = document.rootFrame()
        frame = root.frameFormat()
        frame.setLeftMargin(px(SIDE_PADDING))
        frame.setRightMargin(px(SIDE_PADDING))
        frame.setTopMargin(px(ROW_PADDING))
        frame.setBottomMargin(px(ROW_PADDING))
        root.setFrameFormat(frame)

    # ---- rows --------------------------------------------------------------------------------------------------
    def row_band(self, number):
        """The rectangle a row's tint fills: the full width of the box, the same room above and below the text."""
        top, bottom = band_span(self.document(), number, self.cap_height, to_edges=True)
        shift = self.verticalScrollBar().value()
        return QtCore.QRectF(0, top - shift, self.viewport().width(), bottom - top)

    def row_at(self, point):
        for number in self.rows:
            if self.row_band(number).contains(QtCore.QPointF(point)):
                return number
        return -1

    @staticmethod
    def _point(event):
        position = getattr(event, "position", None)
        return position().toPoint() if position else event.pos()

    # ---- mouse -------------------------------------------------------------------------------------------------
    def mouseMoveEvent(self, event):
        number = self.row_at(self._point(event))
        hover = number if self.rows.get(number) else -1
        if hover != self.hover:
            self.hover = hover
            self.viewport().setCursor(Qt.PointingHandCursor if hover >= 0 else Qt.ArrowCursor)
            self.viewport().update()
        event.accept()

    def leaveEvent(self, event):
        if self.hover >= 0:
            self.hover = -1
            self.viewport().update()
        QtWidgets.QTextEdit.leaveEvent(self, event)

    def mousePressEvent(self, event):
        target = self.rows.get(self.row_at(self._point(event)))
        if event.button() == Qt.LeftButton and target:
            self.row_clicked.emit(target)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    # ---- painting ----------------------------------------------------------------------------------------------
    def _box_shape(self):
        """The inside of the rounded box in viewport coordinates: the tint never covers the rounded corners."""
        box = self.parentWidget()
        path = QtGui.QPainterPath()
        if box is None:
            path.addRect(QtCore.QRectF(self.viewport().rect()))
            return path
        inner = QtCore.QRectF(box.contentsRect())
        inner.translate(QtCore.QPointF(self.viewport().mapFrom(box, QtCore.QPoint(0, 0))))
        path.addRoundedRect(inner, px(5), px(5))
        return path

    def paintEvent(self, event):
        offset = QtCore.QPointF(0, -self.verticalScrollBar().value())
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if self.hover >= 0:
            painter.save()
            painter.setClipPath(self._box_shape())
            painter.setBrush(self.hover_colors.get(self.hover, QtGui.QColor(0, 0, 0, 0)))
            painter.drawRect(self.row_band(self.hover))
            painter.restore()
        paint_pills(self, painter, offset)
        painter.end()
        QtWidgets.QTextEdit.paintEvent(self, event)


class StatusLog(QtWidgets.QWidget, Themed):
    tab_requested = Signal(str)

    def __init__(self, theme, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.entries = []  # [(level, message, target, place)]
        self._colors = theme.colors
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.view = _LogView()
        self.view.row_clicked.connect(self.tab_requested)
        self.mono_font = _monospace(pt(8.5))
        layout.addWidget(controls.boxed(self.view, margin=0), 1)
        self.bind_theme(theme)

    # ---- content -----------------------------------------------------------------------------------------------
    def set_entries(self, entries):
        """Replace the rows with the current state (the log never keeps older messages)."""
        self.entries = [tuple(entry) + ("", "", "")[:4 - len(entry)] for entry in entries][-MAX_ENTRIES:]
        self._render()

    def _on_theme(self, colors):
        self._colors = colors
        self._render()

    def _render(self):
        colors = self._colors
        view = self.view
        view.setUpdatesEnabled(False)
        view.clear()
        view.apply_margins()
        view.rows, view.pills = {}, {}
        view.hover = -1
        view.hover_colors = {}
        bold = QtGui.QFont(self.mono_font)
        bold.setBold(True)
        view.cap_height = QtGui.QFontMetricsF(bold).capHeight()
        view.pill_font = bold
        cursor = QtGui.QTextCursor(view.document())
        indent = QtGui.QFontMetricsF(self.mono_font).horizontalAdvance(" ") * (PILL_CHARS + 2)
        block = QtGui.QTextBlockFormat()
        block.setLineHeight(LINE_HEIGHT, 1)  # 1 = proportional height
        block.setLeftMargin(indent)  # Wrapped lines continue under the message
        block.setTextIndent(-indent)
        block.setTopMargin(px(ROW_PADDING) * 2)  # The space between rows; each tint takes half of it
        cursor.beginEditBlock()
        cursor.setBlockFormat(block)
        if not self.entries:
            muted = QtGui.QTextCharFormat()
            muted.setFont(self.mono_font)
            muted.setForeground(QtGui.QColor(colors["muted_text"]))
            cursor.insertText("Nothing to check yet.", muted)
        for index, (level, message, target, _place) in enumerate(self.entries):
            if index:
                cursor.insertBlock(block)
            label, role = LEVELS.get(level, LEVELS["INFO"])
            number = cursor.blockNumber()
            badge = " " * PILL_CHARS  # Room for the pill; its label is painted in the middle (paint_pills)
            view.pills[number] = (cursor.positionInBlock(), len(badge), QtGui.QColor(colors[role + "_background"]),
                                  label, QtGui.QColor(colors[role]))
            pill_format = QtGui.QTextCharFormat()
            pill_format.setFont(self.mono_font)
            pill_format.setFontWeight(QtGui.QFont.Bold)
            pill_format.setForeground(QtGui.QColor(colors[role]))
            cursor.insertText(badge, pill_format)
            text_format = QtGui.QTextCharFormat()
            text_format.setFont(self.mono_font)
            text_format.setForeground(QtGui.QColor(colors[role]))  # OK rows are green, errors red, warnings yellow
            cursor.insertText("  " + controls.keep_urls_whole(message), text_format)  # Addresses wrap whole
            if target:
                view.rows[number] = target
                tint = QtGui.QColor(colors[role])  # The row's own colour, light enough for the pill to stand out
                tint.setAlphaF(0.12)
                view.hover_colors[number] = tint
        cursor.endEditBlock()
        view.setUpdatesEnabled(True)
        view.moveCursor(QtGui.QTextCursor.Start)  # Else the first show scrolls to the cursor at the end
        view.verticalScrollBar().setValue(0)  # The first problem is in view
