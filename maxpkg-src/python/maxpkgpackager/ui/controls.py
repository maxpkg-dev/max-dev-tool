"""Shared controls. Every dialog composes these; none re-implements their painting or behavior."""

import html
import math
import re
import time

from ..qt_compat import (QtCore, QtGui, QtSvg, QtWidgets, Qt, Signal, device_pixel_ratio, inherit_fonts, repolish,
                         work_area)
from ..ui_scale import pt, px
from .theme_manager import tinted_svg


_icon_cache = {}
_URL = re.compile(r"(?:https?://|www\.)[^\s,;)]+[^\s,;.)]")
_WORD_JOINER = "\u2060"  # Zero width, forbids a line break between the characters it joins


def keep_urls_whole(text):
    """Web addresses never break across lines (Qt would break after "/" or "."): a wrap moves the whole address to
    the next line. For text shown with word wrap; copy the original text, not this."""
    return _URL.sub(lambda match: _WORD_JOINER.join(match.group(0)), text or "")


_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
PARAGRAPH_GAP = 7  # Logical px between the blocks of a help text
LINE_HEIGHT = 120  # Percent: wrapped lines of a help text get air between them


def _plain_html(text, colors):
    text = html.escape(keep_urls_whole(text), quote=False)
    return _BOLD.sub(lambda match: '<b style="color:{}">{}</b>'.format(colors["heading_text"], match.group(1)), text)


def _inline_html(text, colors):
    """**bold** and [label](address) in text without code; the address itself never gets the word joiners."""
    result, last = "", 0
    for match in _LINK.finditer(text):
        result += _plain_html(text[last:match.start()], colors)
        result += '<a href="{}" style="color:{}; text-decoration:none">{}</a>'.format(
            html.escape(match.group(2)), colors["link"], _plain_html(match.group(1), colors))
        last = match.end()
    return result + _plain_html(text[last:], colors)


def help_html(text, colors, text_role="tooltip_text"):
    """Help text with a little markup, as rich text that is quick to scan: blocks split by a blank line get room
    between them, **term** is bold, `code` (file names, characters) is a small monospaced chip, [label](address) is
    a link, a single line break stays a line break."""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", (text or "").strip()) if block.strip()]
    result = []
    for index, block in enumerate(blocks):
        body = ""
        for number, piece in enumerate(_CODE.split(block)):  # Odd pieces are code
            if number % 2:  # A chip never breaks inside (maxpkg-packager.ms stays on one line)
                body += ('<span style="font-family:Consolas,\'Courier New\'; background-color:{}; color:{}">'
                         '&nbsp;{}&nbsp;</span>').format(colors["field"], colors["heading_text"],
                                                          html.escape(_WORD_JOINER.join(piece), quote=False))
            else:
                body += _inline_html(piece, colors)
        result.append('<p style="margin-top:{}px; margin-bottom:0px; line-height:{}%; color:{}">{}</p>'.format(
            0 if index == 0 else px(PARAGRAPH_GAP), LINE_HEIGHT, colors[text_role], body.replace("\n", "<br>")))
    return "".join(result)

CONTROL_HEIGHT = 30  # One height (logical px) for every single-line control: fields, dropdowns, buttons, steppers.
# Parts and small special buttons that keep their own size.
_OWN_SIZE = {"toolMenuItem", "toolDay", "toolStepArrow", "toolStepValue", "toolIconButton", "toolFieldButton", "toolFieldClear",
             "toolSmallAction", "toolChevron", "toolMiniTitle", "toolSoftButton", "toolLogView"}


class _BoxFocus(QtCore.QObject):
    """Outlines a box in the focus colour while the field inside it has the keyboard focus."""

    def __init__(self, box):
        QtCore.QObject.__init__(self, box)
        self.box = box

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.FocusIn, QtCore.QEvent.FocusOut):
            self.box.setProperty("focused", event.type() == QtCore.QEvent.FocusIn)
            repolish(self.box)
        return False


def boxed(inner, margin=1):
    """A list or multi-line text box inside a rounded field frame.

    In the tool's frameless window inside 3ds Max, Qt does not paint the style sheet border of scroll areas (lists,
    text boxes), while plain frames are painted. The frame therefore draws the field's border, focus and invalid
    outline; the widget inside has none. `margin` 0 puts the widget right against the border (rows highlighted from
    edge to edge)."""
    box = QtWidgets.QFrame()
    box.setObjectName("toolBox")
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(px(margin), px(margin), px(margin), px(margin))
    layout.setSpacing(0)
    inner.setFrameShape(QtWidgets.QFrame.NoFrame)
    layout.addWidget(inner)
    box.setFocusProxy(inner)
    inner.installEventFilter(_BoxFocus(box))
    return box


def holder(layout):
    """A plain widget around a layout (no margins), so a layout can be a part of a Reflow."""
    widget = QtWidgets.QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


class Reflow(QtWidgets.QWidget):
    """Parts side by side while the row has room for all of them, one under the other when it has not (a narrow
    window). Its minimum width is the widest part's, so a narrow window never cuts the row off: it stacks instead.

    `parts`: (widget, stretch) pairs, left to right. Stacked, every part takes the full width."""

    def __init__(self, parts, spacing=8, stacked_spacing=6, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._parts = [part for part, _stretch in parts]
        self._row_spacing, self._stacked_spacing = px(spacing), px(stacked_spacing)
        self.box = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(self._row_spacing)
        for part, stretch in parts:
            self.box.addWidget(part, stretch)

    def row_width(self):
        """The narrowest width at which every part still fits in one row."""
        return (sum(part.minimumSizeHint().width() for part in self._parts if not part.isHidden())
                + self._row_spacing * max(0, len([p for p in self._parts if not p.isHidden()]) - 1))

    def stacked(self):
        return self.box.direction() == QtWidgets.QBoxLayout.TopToBottom

    def minimumSizeHint(self):
        width = max([part.minimumSizeHint().width() for part in self._parts if not part.isHidden()] or [0])
        return QtCore.QSize(width, self.box.minimumSize().height())

    def resizeEvent(self, event):
        QtWidgets.QWidget.resizeEvent(self, event)
        self._arrange(event.size().width())

    def _arrange(self, width):
        stack = width < self.row_width()
        if stack != self.stacked():
            # Width decides, height follows: stacking never makes the row narrower or wider, so this cannot flip back.
            self.box.setDirection(QtWidgets.QBoxLayout.TopToBottom if stack else QtWidgets.QBoxLayout.LeftToRight)
            self.box.setSpacing(self._stacked_spacing if stack else self._row_spacing)
            self.updateGeometry()


def round_popup(widget, radius=6):
    """Rounded corners for a popup window by a window mask (no translucent windows inside 3ds Max)."""
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(widget.rect()), px(radius), px(radius))
    widget.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))


def paint_bubble(painter, shape, fill, border, width=1.0):
    """Fills a masked popup's shape (a bubble with its arrow) and outlines it on the whole perimeter. The outline is
    drawn twice as wide and clipped to the shape, so it runs along the inside: a stroke centred on the edge loses its
    outer half to the window mask (and to the widget's right and bottom edges), and the bubble looks open there."""
    painter.save()
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setClipPath(shape)
    painter.fillPath(shape, QtGui.QColor(fill))
    pen = QtGui.QPen(QtGui.QColor(border), 2.0 * width)
    pen.setJoinStyle(Qt.MiterJoin)  # The arrow's point keeps its outline too
    painter.strokePath(shape, pen)
    painter.restore()


class Menu(QtWidgets.QMenu):
    """A context or button menu with rounded corners like every other popup of the tool. Items have a Lucide icon;
    a destructive item (Delete, Remove) is red."""

    def __init__(self, theme, parent=None):
        QtWidgets.QMenu.__init__(self, parent)
        self.theme = theme
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

    def add_item(self, text, icon, slot, danger=False, enabled=True):
        button = Button(text, self.theme, icon=icon, variant="menu", icon_role="log_error" if danger else None)
        button.setObjectName("toolMenuItem")
        button.setProperty("danger", "true" if danger else "false")
        button.setEnabled(enabled)
        button.setFocusPolicy(Qt.NoFocus)
        action = QtWidgets.QWidgetAction(self)
        action.setDefaultWidget(button)
        action.setEnabled(enabled)
        button.clicked.connect(lambda: (self.close(), slot()))
        self.addAction(action)
        return action

    def showEvent(self, event):
        QtWidgets.QMenu.showEvent(self, event)
        round_popup(self)

    def resizeEvent(self, event):
        QtWidgets.QMenu.resizeEvent(self, event)
        round_popup(self)

    def prepare(self):
        """A menu is a window of its own and does not inherit its window's font: give it the interface size."""
        owner = self.parentWidget()
        if owner is not None:
            self.setFont(owner.window().font())
        inherit_fonts(self)

    def popup_at(self, point):
        self.prepare()
        (getattr(self, "exec_", None) or getattr(self, "exec"))(point)


def unify_heights(root):
    """Give every field, dropdown and button under `root` the same height; a button without text becomes a square.

    One rule in one place: a button can never be taller than the field next to it. Call it after a window or dialog
    has built its widgets (and again after adding widgets later)."""
    height = px(CONTROL_HEIGHT)
    for widget in root.findChildren(QtWidgets.QWidget):
        name = widget.objectName()
        if name in _OWN_SIZE:
            continue
        if isinstance(widget, QtWidgets.QPushButton):
            widget.setFixedHeight(height)
            if not widget.text().strip() and widget.property("segment") is None:
                widget.setFixedWidth(height)  # Icon-only: a square
        elif isinstance(widget, (QtWidgets.QComboBox, QtWidgets.QLineEdit)):
            if isinstance(widget.parentWidget(), QtWidgets.QAbstractSpinBox):
                continue
            widget.setFixedHeight(height)
        elif name == "toolStepper":
            widget.setFixedHeight(height)


def icon_pixmap(name, color, size, ratio):
    key = (name, color, size, round(ratio, 2))
    pixmap = _icon_cache.get(key)
    if pixmap is None:
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(tinted_svg(name, color).encode("utf-8")))
        physical = max(1, int(round(size * ratio)))
        image = QtGui.QImage(physical, physical, QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QtGui.QPainter(image)
        renderer.render(painter)
        painter.end()
        pixmap = QtGui.QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(ratio)
        _icon_cache[key] = pixmap
    return pixmap


def brand_pixmap(size, ratio):
    """The MaxPkg Packager brand icon (not a button icon) rendered sharply at the device pixel ratio."""
    from .. import resources
    physical = max(1, int(round(size * ratio)))
    image = QtGui.QImage(physical, physical, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    renderer = QtSvg.QSvgRenderer(resources.asset("maxpkgpackager.svg"))
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap = QtGui.QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


class BrandIcon(QtWidgets.QLabel):
    """The MaxPkg Packager icon beside the tool's name in title bars; rendered when shown (the screen's pixel
    ratio is known then)."""

    def __init__(self, size=18, parent=None):
        QtWidgets.QLabel.__init__(self, parent)
        self._size = px(size)  # Interface size.
        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Drags on the bar pass through.

    def showEvent(self, event):
        self.setPixmap(brand_pixmap(self._size, device_pixel_ratio(self)))
        QtWidgets.QLabel.showEvent(self, event)


def make_icon(name, colors, widget, size=16):
    ratio = device_pixel_ratio(widget)
    size = px(size)  # Rendered at the interface size, so it stays sharp at the button's scaled icon size.
    icon = QtGui.QIcon()
    icon.addPixmap(icon_pixmap(name, colors["text"], size, ratio), QtGui.QIcon.Normal)
    icon.addPixmap(icon_pixmap(name, colors["disabled_text"], size, ratio), QtGui.QIcon.Disabled)
    return icon


class Themed(object):
    """Mixin: re-tint icons and repaint when the theme changes."""

    def bind_theme(self, theme):
        self._theme = theme
        theme.subscribe(self._on_theme)
        self.destroyed.connect(lambda *_: theme.unsubscribe(self._on_theme))
        self._on_theme(theme.colors)

    def _on_theme(self, colors):
        pass


class NumberBadge(QtWidgets.QWidget, Themed):
    """A step number in a round accent outline. Painted here: the digits are centred on their own ink, so they sit
    exactly in the middle of the circle (a label centres the font's line box, which puts digits off centre)."""

    def __init__(self, number, theme, size=20, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._text = str(number)
        self.setFixedSize(px(size), px(size))
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtGui.QColor(self._colors["accent"])
        painter.setPen(QtGui.QPen(color, 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QtCore.QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6))
        font = QtGui.QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(pt(8))
        metrics = QtGui.QFontMetricsF(font)
        ink = metrics.tightBoundingRect(self._text)  # Relative to the baseline origin
        ratio = device_pixel_ratio(self) or 1.0
        # Across: by the advance width. Digits have one width and sit in the middle of it; the ink box differs
        # between Qt 5 and Qt 6 by a pixel. Down, never up: round() goes to the even pixel.
        x = math.floor((self.width() - metrics.horizontalAdvance(self._text)) / 2.0 * ratio) / ratio
        # Up and down: by the ink, so the digit's own height is centred
        y = round((self.height() / 2.0 - ink.top() - ink.height() / 2.0) * ratio) / ratio
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QtCore.QPointF(x, y), self._text)
        painter.end()


class Button(QtWidgets.QPushButton, Themed):
    """Push button with semantic variant (primary, secondary, danger, ghost, donate) and Lucide icon."""

    def __init__(self, text="", theme=None, icon=None, variant="secondary", tooltip="", parent=None,
                 icon_role=None):
        QtWidgets.QPushButton.__init__(self, "", parent)
        self.icon_name = icon
        self.icon_role = icon_role  # A theme colour for the icon instead of the variant's text colour.
        self.setText(text)
        self.setProperty("variant", variant)
        if tooltip:
            self.setToolTip(tooltip)
        if not text and tooltip:
            self.setAccessibleName(tooltip)
        self._sync_cursor()
        if theme is not None:
            self.bind_theme(theme)

    ICON_GAP = " "  # En space before the text of icon buttons.

    def setText(self, text):
        QtWidgets.QPushButton.setText(self, (self.ICON_GAP + text) if text and self.icon_name else text)

    def text(self):
        return QtWidgets.QPushButton.text(self).lstrip(self.ICON_GAP)

    def _on_theme(self, colors):
        if self.icon_name:
            # Same colour as the variant's text in style.qss.
            role = self.icon_role or {"primary": "log_badge_text", "danger": "danger_text",
                                      "donate": "status_button_text"}.get(self.property("variant"), "text")
            local = dict(colors, text=colors[role])
            disabled = {"primary": "accent_disabled_text", "danger": "danger_disabled_text"}.get(
                self.property("variant"))
            if disabled:  # A coloured button keeps a shade of its colour when disabled, never a grey icon
                local["disabled_text"] = colors[disabled]
            self.setIcon(make_icon(self.icon_name, local, self))
            size = getattr(self, "icon_px", 16)  # Small arrow buttons set a smaller icon
            self.setIconSize(QtCore.QSize(px(size), px(size)))

    def _sync_cursor(self):
        self.setCursor(Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.EnabledChange:
            self._sync_cursor()
        QtWidgets.QPushButton.changeEvent(self, event)


class WindowButton(Button):
    """A round 28 px title-bar button (as in MaxPkg Runtime Manager): transparent at rest, a soft circle on hover; the
    close button turns red with a white cross."""

    def __init__(self, icon, theme, tooltip, close=False, parent=None, small=False):
        Button.__init__(self, "", theme, icon=icon, variant="ghost", tooltip=tooltip, parent=parent)
        self._close = close
        self.setObjectName("toolIconButton")
        self.setProperty("role", "close" if close else "")
        self.setProperty("compact", "true" if small else "false")  # 22 px: the collapsed bar ("size" is Qt's own)
        self.setFixedSize(px(22 if small else 28), px(22 if small else 28))
        if small:
            self.icon_px = 14
            self._on_theme(theme.colors)  # Again, with the smaller icon
        self.setFocusPolicy(Qt.NoFocus)  # No focus frame on a round button

    def enterEvent(self, event):
        if self._close and self.isEnabled():
            self.setIcon(make_icon(self.icon_name, dict(self._theme.colors, text="#ffffff"), self))
        Button.enterEvent(self, event)

    def leaveEvent(self, event):
        if self._close:
            self._on_theme(self._theme.colors)
        Button.leaveEvent(self, event)


class Flash(QtWidgets.QWidget):
    """A coloured highlight over a widget that fades out: shows where to look after a jump to a field."""

    def __init__(self, target, color, duration=2000):
        QtWidgets.QWidget.__init__(self, target.parentWidget())
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._color = QtGui.QColor(color)
        self._alpha = 0.0
        self.setGeometry(target.geometry().adjusted(-px(2), -px(2), px(2), px(2)))
        self.animation = QtCore.QVariantAnimation(self)
        self.animation.setDuration(duration)
        self.animation.setKeyValueAt(0.0, 0.0)
        self.animation.setKeyValueAt(0.15, 1.0)  # Lights up smoothly (0.3 s)
        self.animation.setKeyValueAt(0.35, 1.0)  # stays a moment
        self.animation.setKeyValueAt(1.0, 0.0)  # and fades out slowly
        self.animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        self.animation.valueChanged.connect(self._step)
        self.animation.finished.connect(self.deleteLater)
        self.show()
        self.raise_()
        self.animation.start()

    def _step(self, value):
        self._alpha = float(value)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        fill = QtGui.QColor(self._color)
        fill.setAlphaF(0.6 * self._alpha)  # The whole field lights up, not only its outline
        edge = QtGui.QColor(self._color)
        edge.setAlphaF(self._alpha)
        painter.setPen(QtGui.QPen(edge, px(2)))
        painter.setBrush(fill)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1), px(7), px(7))
        painter.end()


class QTipLabel(QtWidgets.QWidget):
    """Base of the tool's own tooltip windows (Qt.ToolTip). The name is on purpose: Qt for Windows gives Windows' small
    soft popup shadow (CS_DROPSHADOW) only to tooltip windows whose class inherits "QTipLabel" (its own tooltip label),
    so the red error bubble gets the same light shadow as every Qt tooltip. The shadow follows the window mask, arrow
    included. Style sheets still match the subclass's own name, never the QToolTip rule."""


class ErrorTip(QTipLabel, Themed):
    """What is wrong with a field, in a red bubble that floats up just above it as soon as the pointer is on the
    field (no system tooltip delay). A small arrow points at the field; it goes away when the pointer leaves. It has
    the light system shadow of tooltips (QTipLabel)."""

    WIDTH = 300
    PAD = 9
    ARROW = 6
    RADIUS = 7

    def __init__(self, theme, parent=None):
        QTipLabel.__init__(self, parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        if parent is not None:
            self.setFont(parent.font())  # A popup does not inherit its window's interface-size font
        self._text, self._below, self._tip = "", False, 0
        self._colors = theme.colors
        self.target = None
        self.fade = QtCore.QVariantAnimation(self)
        self.fade.setDuration(140)
        self.fade.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.fade.valueChanged.connect(self._step)
        self._end = QtCore.QPoint()
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def show_for(self, widget, text):
        self.target = widget
        self._text = text = keep_urls_whole(text)
        inner = px(self.WIDTH) - 2 * px(self.PAD)
        metrics = QtGui.QFontMetrics(self.font())
        text_rect = metrics.boundingRect(0, 0, inner, 10000, int(Qt.TextWordWrap), text)
        width = min(px(self.WIDTH), text_rect.width() + 2 * px(self.PAD) + 2)
        height = text_rect.height() + 2 * px(self.PAD) + px(self.ARROW)
        corner = widget.mapToGlobal(QtCore.QPoint(0, 0))
        area = work_area(corner) or QtCore.QRect(corner.x() - 2000, corner.y() - 2000, 4000, 4000)
        self._below = corner.y() - height - px(2) < area.top()  # No room above: under the field
        x = max(area.left(), min(corner.x(), area.right() - width))
        y = corner.y() + widget.height() + px(2) if self._below else corner.y() - height - px(2)
        self._tip = max(px(self.RADIUS) + px(self.ARROW), min(corner.x() + px(18) - x, width - px(self.RADIUS) - px(self.ARROW)))
        self.setFixedSize(width, height)
        self._end = QtCore.QPoint(x, y)
        shape = self._shape()
        self.setMask(QtGui.QRegion(shape.toFillPolygon().toPolygon()))
        self.fade.stop()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self._step(0.0)
        self.show()
        self.raise_()
        self.fade.start()

    def _step(self, value):
        value = float(value)
        self.setWindowOpacity(value)
        lift = int(round((1.0 - value) * px(6)))  # Floats up into place (down into place when under the field)
        self.move(self._end.x(), self._end.y() + (-lift if self._below else lift))

    def hide_tip(self, widget=None):
        if widget is None or widget is self.target:
            self.fade.stop()
            self.hide()
            self.target = None

    def _shape(self):
        body_h = self.height() - px(self.ARROW)
        top = px(self.ARROW) if self._below else 0
        body = QtGui.QPainterPath()
        body.addRoundedRect(QtCore.QRectF(0, top, self.width(), body_h), px(self.RADIUS), px(self.RADIUS))
        edge = top if self._below else body_h
        point = 0 if self._below else self.height()
        arrow = QtGui.QPainterPath()
        arrow.addPolygon(QtGui.QPolygonF([QtCore.QPointF(self._tip - px(self.ARROW), edge + (1 if self._below else -1)),
                                          QtCore.QPointF(self._tip, point),
                                          QtCore.QPointF(self._tip + px(self.ARROW), edge + (1 if self._below else -1))]))
        return body.united(arrow)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        paint_bubble(painter, self._shape(), self._colors["danger"], self._colors["log_error"], 1.0)
        painter.setPen(QtGui.QColor(self._colors["danger_text"]))
        top = px(self.ARROW) if self._below else 0
        painter.drawText(QtCore.QRectF(px(self.PAD), top + px(self.PAD), self.width() - 2 * px(self.PAD),
                                       self.height() - px(self.ARROW) - 2 * px(self.PAD)),
                         int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter), self._text)
        painter.end()


class ErrorHints(QtCore.QObject):
    """Shows a field's error in an ErrorTip while the pointer is on it. A field has an error while its
    "invalidMessage" property holds text."""

    MOVE = 3  # Pixels the pointer moves on the field before its bubble shows

    def __init__(self, theme, window):
        QtCore.QObject.__init__(self, window)
        self.tip = ErrorTip(theme, window)
        self.cursor_pos = QtGui.QCursor.pos  # Where the pointer is (a test gives its own)
        self._pending, self._origin = None, None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._check)

    def watch(self, widget):
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QtCore.QEvent.Enter:
            if watched.property("invalidMessage"):
                # Not at once: Qt also sends Enter when a dropdown or a menu above the field closes and the pointer
                # simply is there. The bubble waits until the pointer moves on the field.
                self._pending, self._origin = watched, self.cursor_pos()
                self._timer.start()
        elif kind in (QtCore.QEvent.Leave, QtCore.QEvent.Hide, QtCore.QEvent.MouseButtonPress):
            if self._pending is watched:
                self._stop_waiting()
            self.tip.hide_tip(watched)
        return False

    def _stop_waiting(self):
        self._timer.stop()
        self._pending = None

    def _check(self):
        widget = self._pending
        try:
            position = self.cursor_pos()
            inside = widget is not None and widget.isVisible() and widget.rect().contains(widget.mapFromGlobal(position))
        except RuntimeError:  # The field is gone
            inside = False
        if not inside:
            self._stop_waiting()
            return
        if (position - self._origin).manhattanLength() >= self.MOVE:
            self._stop_waiting()
            message = widget.property("invalidMessage")
            if message:
                self.tip.show_for(widget, message)

    def refresh(self, widget):
        """The field's error changed while the pointer is on it: update or remove the bubble."""
        if self.tip.target is widget:
            message = widget.property("invalidMessage")
            if message:
                self.tip.show_for(widget, message)
            else:
                self.tip.hide_tip(widget)

    def dispose(self):
        self._stop_waiting()
        self.tip.hide()
        self.tip.deleteLater()


class ToastItem(QtWidgets.QFrame):
    """One message of the stack. A thin bar along its bottom counts down the time it stays; the pointer on it
    pauses the count, a click closes it."""

    ICONS = {"error": "x", "success": "check", "warning": "info", "info": "info"}
    ROLES = {"error": "log_error", "success": "log_success", "warning": "log_warning", "info": "log_info"}

    def __init__(self, stack, text, level, seconds):
        QtWidgets.QFrame.__init__(self, stack)
        self.stack = stack
        self.level = level if level in self.ROLES else "info"
        self.text = text
        self.setObjectName("toolToast")
        self.setProperty("level", self.level)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(px(10), px(7), px(10), px(9))
        layout.setSpacing(px(8))
        self.icon = QtWidgets.QLabel()
        self.icon.setFixedSize(px(16), px(16))
        self.label = QtWidgets.QLabel(keep_urls_whole(text))
        self.label.setObjectName("toolToastText")
        self.label.setWordWrap(True)
        layout.addWidget(self.icon, 0, Qt.AlignTop)
        layout.addWidget(self.label, 1)
        self.remaining = 1.0
        self.countdown = QtCore.QVariantAnimation(self)
        self.countdown.valueChanged.connect(self._tick)
        self.countdown.finished.connect(lambda: self.stack.remove(self))
        self.restart(seconds)
        self.retint()

    def retint(self):
        colors = self.stack.colors
        self.icon.setPixmap(icon_pixmap(self.ICONS[self.level], colors[self.ROLES[self.level]], px(16),
                                        device_pixel_ratio(self)))
        self.update()

    def restart(self, seconds):
        self.countdown.stop()
        self.countdown.setDuration(int(seconds * 1000))
        self.countdown.setStartValue(1.0)
        self.countdown.setEndValue(0.0)
        self.remaining = 1.0
        self.countdown.start()

    def _tick(self, value):
        self.remaining = float(value)
        self.update()

    def enterEvent(self, event):
        if self.countdown.state() == QtCore.QAbstractAnimation.Running:
            self.countdown.pause()  # Time to read: the count waits while the pointer is on the message
        QtWidgets.QFrame.enterEvent(self, event)

    def leaveEvent(self, event):
        if self.countdown.state() == QtCore.QAbstractAnimation.Paused:
            self.countdown.resume()
        QtWidgets.QFrame.leaveEvent(self, event)

    def mousePressEvent(self, event):
        self.stack.remove(self)

    def paintEvent(self, event):
        QtWidgets.QFrame.paintEvent(self, event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        color = QtGui.QColor(self.stack.colors[self.ROLES[self.level]])
        track = QtCore.QRectF(px(10), self.height() - px(5), self.width() - 2 * px(10), px(2))
        dim = QtGui.QColor(color)
        dim.setAlphaF(0.25)
        painter.setBrush(dim)
        painter.drawRoundedRect(track, px(1), px(1))
        painter.setBrush(color)
        painter.drawRoundedRect(QtCore.QRectF(track.x(), track.y(), track.width() * self.remaining, track.height()),
                                px(1), px(1))
        painter.end()


class Toast(QtWidgets.QWidget, Themed):
    """Messages about the last actions, stacked above the bottom of the window (newest at the bottom, at most
    four). Each one disappears when its countdown bar runs out: errors and warnings after 7 s, others after 4 s."""

    MAX_ITEMS = 4

    def __init__(self, theme, parent):
        QtWidgets.QWidget.__init__(self, parent)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.colors = theme.colors
        self.items = []
        self.column = QtWidgets.QVBoxLayout(self)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(px(6))
        self.hide()
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self.colors = colors
        for item in self.items:
            item.retint()

    def show_message(self, text, level="info", seconds=None):
        seconds = seconds or (7 if level in ("error", "warning") else 4)
        for item in self.items:
            if item.text == text and item.level == level:
                item.restart(seconds)  # The same message again: its time starts over, no duplicate
                self.place()
                return
        item = ToastItem(self, text, level, seconds)
        repolish(item)
        self.items.append(item)
        self.column.addWidget(item)
        while len(self.items) > self.MAX_ITEMS:
            self.remove(self.items[0])
        self.show()
        self.raise_()
        self.place()

    def remove(self, item):
        if item in self.items:
            self.items.remove(item)
            item.countdown.stop()
            item.hide()
            item.deleteLater()
        if self.items:
            self.place()
        else:
            self.hide()

    def clear(self):
        for item in list(self.items):
            self.remove(item)

    def place(self):
        """Above the bottom strip of the parent window, as wide as its content; grows upwards."""
        host = self.parentWidget()
        if host is None:
            return
        width = max(px(120), host.width() - 2 * px(8))
        self.setFixedWidth(width)
        self.layout().activate()
        height = sum(item.heightForWidth(width) if item.hasHeightForWidth() else item.sizeHint().height()
                     for item in self.items) + self.column.spacing() * max(0, len(self.items) - 1)
        self.setFixedHeight(max(1, height))
        self.move(px(8), host.height() - self.height() - px(48))


class Pill(QtWidgets.QWidget, Themed):
    """Rounded status capsule. Variants: neutral, info, success, warning, error.

    set_clickable(True) turns it into a button-like control that emits `clicked`.
    """

    clicked = Signal()

    _ROLES = {"neutral": "muted_text", "info": "log_info", "success": "log_success",
              "warning": "log_warning", "error": "log_error"}

    def __init__(self, theme, text="", variant="neutral", parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._text = text
        self._variant = variant
        self._colors = theme.colors
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        self.bind_theme(theme)

    def set_status(self, text, variant=None, tooltip=None):
        self._text = text
        if variant:
            self._variant = variant
        self.setToolTip(tooltip or text)
        self.setAccessibleName(tooltip or text)
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def set_clickable(self, on):
        self._clickable = bool(on)
        self.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if getattr(self, "_clickable", False) and event.button() == Qt.LeftButton \
                and self.rect().contains(event.pos()):
            self.clicked.emit()
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        width = metrics.horizontalAdvance(self._text) if hasattr(metrics, "horizontalAdvance") \
            else metrics.width(self._text)
        return QtCore.QSize(width + px(20), metrics.height() + px(8))

    def minimumSizeHint(self):
        # Never force the parent wider than it is: a pill may shrink, and its text then elides in the
        # middle while the full text stays in the tooltip (callers keep long details out of pills).
        hint = self.sizeHint()
        return QtCore.QSize(min(hint.width(), px(64)), hint.height())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        tone = QtGui.QColor(self._colors[self._ROLES.get(self._variant, "muted_text")])
        fill = QtGui.QColor(tone)
        fill.setAlpha(40)
        painter.setPen(QtGui.QPen(tone, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QtGui.QColor(self._colors["text"]))
        inner = self.rect().adjusted(10, 0, -10, 0)
        painter.drawText(inner, Qt.AlignCenter, self.fontMetrics().elidedText(self._text, Qt.ElideMiddle,
                                                                              inner.width()))
        painter.end()


class ProgressBar(QtWidgets.QWidget, Themed):
    """Pill progress bar with a clipped rounded fill, a caption and elapsed seconds.

    Known work shows real progress; total=None shows an indeterminate sweep. Timers run only while busy.
    `clicked` is emitted on a left click.
    """

    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def __init__(self, theme, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._colors = theme.colors
        self._label = ""
        self._done = 0
        self._total = None
        self._started = None
        self._phase = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.setMinimumHeight(px(22))
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.bind_theme(theme)

    def start(self):
        import time
        self._started = time.monotonic()
        self._done, self._total, self._label = 0, None, "Starting..."
        self._timer.start()
        self.show()
        self.update()

    def set_progress(self, label, done, total):
        self._label, self._done, self._total = label, done, total
        self.update()

    def stop(self):
        self._timer.stop()
        self._started = None
        self.hide()

    def elapsed(self):
        import time
        return 0.0 if self._started is None else time.monotonic() - self._started

    def _tick(self):
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def hideEvent(self, event):
        self._timer.stop()
        QtWidgets.QWidget.hideEvent(self, event)

    def sizeHint(self):
        return QtCore.QSize(px(200), max(px(22), self.fontMetrics().height() + px(8)))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        track = QtGui.QPainterPath()
        track.addRoundedRect(rect, radius, radius)
        painter.fillPath(track, QtGui.QColor(self._colors["recessed"]))
        painter.setClipPath(track)
        fill = QtGui.QColor(self._colors["accent"])
        fill.setAlpha(150)
        if self._total:
            fraction = max(0.0, min(1.0, float(self._done) / self._total))
            painter.fillRect(QtCore.QRectF(rect.left(), rect.top(), rect.width() * fraction, rect.height()), fill)
        else:
            span = rect.width() * 0.3
            x = rect.left() - span + (rect.width() + span) * self._phase
            painter.fillRect(QtCore.QRectF(x, rect.top(), span, rect.height()), fill)
        painter.setClipping(False)
        painter.setPen(QtGui.QPen(QtGui.QColor(self._colors["border"]), 1))
        painter.drawPath(track)
        painter.setPen(QtGui.QColor(self._colors["text"]))
        caption = self._label
        if self._total:
            caption = "{} {}/{}".format(caption, self._done, self._total)
        caption = "{}  {:.0f}s".format(caption, self.elapsed())
        text_rect = self.rect().adjusted(10, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         self.fontMetrics().elidedText(caption, Qt.ElideMiddle, text_rect.width()))
        painter.end()


class Segmented(QtWidgets.QWidget):
    """Exclusive row of checkable buttons, e.g. quality presets."""

    changed = Signal(str)

    OVERLAP = 1  # Neighbouring segments share one border line.

    def __init__(self, options, theme, current=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        # No layout: QBoxLayout treats a negative spacing as "style default" (a visible gap), so the
        # buttons are placed by hand, each overlapping its left neighbour by OVERLAP px.
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        self._order = []
        for index, (key, label, tip) in enumerate(options):
            button = Button(label, theme, tooltip=tip)
            button.setCheckable(True)
            button.setFocusPolicy(Qt.NoFocus)  # No dotted focus frame on a segment
            position = "first" if index == 0 else ("last" if index == len(options) - 1 else "middle")
            button.setProperty("segment", position)
            button.setParent(self)
            self.group.addButton(button)
            self.buttons[key] = button
            self._order.append(button)
            button.toggled.connect(lambda on, k=key: self._on_toggled(k, on))
        self.set_value(current or options[0][0])

    def sizeHint(self):
        hints = [button.sizeHint() for button in self._order]
        return QtCore.QSize(sum(h.width() for h in hints) - self.OVERLAP * (len(hints) - 1),
                            max(h.height() for h in hints))

    def minimumSizeHint(self):
        # Text width plus a small margin only: the buttons' own (padded) minimum made the row wider than a
        # panel with a scroll bar, which cut off the last segment.
        metrics = self.fontMetrics()
        width = sum(metrics.horizontalAdvance(button.text()) + 14 for button in self._order)
        return QtCore.QSize(width, max(button.minimumSizeHint().height() for button in self._order))

    def resizeEvent(self, event):
        QtWidgets.QWidget.resizeEvent(self, event)
        count = len(self._order)
        total = self.width() + self.OVERLAP * (count - 1)
        x = 0
        for index, button in enumerate(self._order):
            # Each segment's right edge, minus the overlaps so far: the last one ends exactly at width().
            right = int(round(total * (index + 1) / float(count))) - index * self.OVERLAP
            button.setGeometry(x, 0, right - x, self.height())
            x = right - self.OVERLAP

    def _on_toggled(self, key, on):
        if on:
            self.buttons[key].raise_()  # Keep the checked segment's border above its neighbours.
            self.changed.emit(key)

    def set_value(self, key):
        self.buttons[key].setChecked(True)
        self.buttons[key].raise_()

    def value(self):
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return None


class ComboBox(QtWidgets.QComboBox):
    """Themed dropdown whose popup is a styled list placed 4px below (or above) the field."""

    def __init__(self, parent=None):
        QtWidgets.QComboBox.__init__(self, parent)
        view = QtWidgets.QListView(self)
        view.setObjectName("toolPopup")
        self.setView(view)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        """The wheel never changes a dropdown's value, focused or not: it scrolls the page under it (scrolling must
        never change a field by accident). The value is chosen in the open list or with the keyboard."""
        event.ignore()

    def showPopup(self):
        # The list is polished by its style sheet rule at its first show (Qt 5: 9 pt item view font). Polish it now and
        # give it the interface size first, so the popup is measured with the right rows.
        self.view().ensurePolished()
        inherit_fonts(self.view().window())
        QtWidgets.QComboBox.showPopup(self)
        popup = self.view().window()
        area = work_area(self.mapToGlobal(QtCore.QPoint(0, 0))) or popup.geometry()
        below = self.mapToGlobal(QtCore.QPoint(0, self.height() + 4))
        y = below.y()
        if y + popup.height() > area.bottom():
            y = self.mapToGlobal(QtCore.QPoint(0, 0)).y() - popup.height() - 4
        x = max(area.left(), min(below.x(), area.right() - popup.width()))
        popup.move(x, max(area.top(), y))
        round_popup(popup)  # Same rounded corners as the field it opens from


class FlowLayout(QtWidgets.QLayout):
    """Left-to-right layout that wraps to new rows (for chips such as the scene layer toggles)."""

    def __init__(self, parent=None, spacing=6, row_spacing=None):
        QtWidgets.QLayout.__init__(self, parent)
        self._items = []
        self._gap = spacing
        self._row_gap = spacing if row_spacing is None else row_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QtCore.QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        QtWidgets.QLayout.setGeometry(self, rect)
        self._arrange(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _arrange(self, rect, apply):
        margins = self.contentsMargins()
        left, top = rect.x() + margins.left(), rect.y() + margins.top()
        right = rect.right() - margins.right()
        x, y, row_height = left, top, 0
        for item in self._items:
            hint = item.sizeHint()
            if x > left and x + hint.width() > right + 1:
                x, y, row_height = left, y + row_height + self._row_gap, 0
            if apply:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x += hint.width() + self._gap
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()


def section(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("toolSection")
    return label


class Balloon(QtWidgets.QWidget, Themed):
    """A help bubble with an arrow pointing at its HelpButton: a bold title, a thin line, then the help in short
    blocks (help_html: blank lines, **terms**, `code`). A click elsewhere or Esc closes it. Painted here and shaped
    with a window mask (translucent popups are risky inside Max, pitfalls.md). Windows' own small popup shadow
    (CS_DROPSHADOW, no NoDropShadowWindowHint) follows the mask: a light shadow right and below, arrow included."""

    WIDTH = 300
    PAD = 10
    ARROW = 7
    RADIUS = 6

    def __init__(self, theme, parent=None):
        QtWidgets.QWidget.__init__(self, parent, Qt.Popup | Qt.FramelessWindowHint)
        if parent is not None:
            self.setFont(parent.font())  # A popup does not inherit its window's (interface-size) font.
        self._title, self._text = "", ""
        self._document = QtGui.QTextDocument(self)
        self._document.setDocumentMargin(0)
        self._shape = QtGui.QPainterPath()
        self.closed_at = 0.0
        self.bind_theme(theme)

    def _fonts(self):
        title = QtGui.QFont(self.font())
        title.setBold(True)
        return title, self.font()

    def _layout_text(self):
        """The help as rich text at the balloon's inner width; returns its height."""
        _title_font, text_font = self._fonts()
        self._document.setDefaultFont(text_font)
        self._document.setHtml(help_html(self._text, self._colors))
        self._document.setTextWidth(px(self.WIDTH) - 2 * px(self.PAD))
        return int(self._document.size().height() + 0.999)

    def _rule_gap(self):
        return px(6)  # Above and below the thin line under the title

    def show_for(self, anchor, title, text):
        self._title, self._text = title, text
        title_font, _text_font = self._fonts()
        inner = px(self.WIDTH) - 2 * px(self.PAD)
        title_h = QtGui.QFontMetrics(title_font).boundingRect(0, 0, inner, 10000, int(Qt.TextWordWrap), title).height()
        text_h = self._layout_text()
        body_h = px(self.PAD) + title_h + 2 * self._rule_gap() + 1 + text_h + px(self.PAD)
        height = body_h + px(self.ARROW)
        # Below the button when it fits on the screen, else above; the arrow points at the button's centre.
        centre = anchor.mapToGlobal(QtCore.QPoint(anchor.width() // 2, anchor.height() // 2))
        area = work_area(centre) or QtCore.QRect(centre.x() - 2000, centre.y() - 2000, 4000, 4000)
        below = centre.y() + anchor.height() // 2 + height <= area.bottom()
        x = max(area.left() + 4, min(centre.x() - px(self.WIDTH) // 2, area.right() - px(self.WIDTH) - 4))
        y = centre.y() + anchor.height() // 2 + 2 if below else centre.y() - anchor.height() // 2 - 2 - height
        tip = max(px(self.RADIUS) + px(self.ARROW), min(centre.x() - x, px(self.WIDTH) - px(self.RADIUS) - px(self.ARROW)))
        top = px(self.ARROW) if below else 0
        body = QtGui.QPainterPath()
        body.addRoundedRect(QtCore.QRectF(0, top, px(self.WIDTH), body_h), px(self.RADIUS), px(self.RADIUS))
        edge = top if below else body_h
        point = 0 if below else height
        arrow = QtGui.QPainterPath()
        arrow.addPolygon(QtGui.QPolygonF([QtCore.QPointF(tip - px(self.ARROW), edge + (1 if below else -1)),
                                          QtCore.QPointF(tip, point), QtCore.QPointF(tip + px(self.ARROW),
                                                                                     edge + (1 if below else -1))]))
        self._shape = body.united(arrow)
        self._body_top = top
        self._title_h = title_h
        self.setFixedSize(px(self.WIDTH), height)
        self.setMask(QtGui.QRegion(self._shape.toFillPolygon().toPolygon()))
        self.move(x, y)
        self.show()

    def _on_theme(self, colors):
        self._colors = colors
        if self._text:
            self._layout_text()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        paint_bubble(painter, self._shape, self._colors["tooltip_background"], self._colors["active_border"], 1.5)
        title_font, text_font = self._fonts()
        inner = px(self.WIDTH) - 2 * px(self.PAD)
        top = self._body_top + px(self.PAD)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor(self._colors["heading_text"]))
        painter.drawText(QtCore.QRect(px(self.PAD), top, inner, self._title_h), int(Qt.TextWordWrap), self._title)
        rule = top + self._title_h + self._rule_gap()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        painter.setPen(QtGui.QPen(QtGui.QColor(self._colors["border"]), 1))
        painter.drawLine(px(self.PAD), rule, px(self.PAD) + inner, rule)  # Separates the title from the help
        painter.translate(px(self.PAD), rule + 1 + self._rule_gap())
        self._document.drawContents(painter)
        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        QtWidgets.QWidget.keyPressEvent(self, event)

    def hideEvent(self, event):
        self.closed_at = time.monotonic()
        QtWidgets.QWidget.hideEvent(self, event)


class HelpButton(QtWidgets.QAbstractButton, Themed):
    """A small round "?" beside a title; a click opens a Balloon with a short description of that part of the
    panel, a second click (or one elsewhere) closes it."""

    SIZE = 16

    def __init__(self, theme, title, text, parent=None):
        QtWidgets.QAbstractButton.__init__(self, parent)
        self._title, self._text, self._balloon_theme = title, text, theme
        self.balloon = None
        self.setFixedSize(px(self.SIZE), px(self.SIZE))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAccessibleName("Help: " + title)
        self.clicked.connect(self.toggle)
        self.bind_theme(theme)

    def toggle(self):
        balloon = self.balloon
        if balloon is not None and balloon.isVisible():
            balloon.close()
            return
        if balloon is not None and time.monotonic() - balloon.closed_at < 0.3:
            return  # This click's press closed the open balloon (a popup closes on any press outside it).
        if balloon is None:
            self.balloon = balloon = Balloon(self._balloon_theme, self.window())
            balloon.destroyed.connect(lambda *_: setattr(self, "balloon", None))
        balloon.show_for(self, self._title, self._text)
        self.update()

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def enterEvent(self, event):
        self.update()
        QtWidgets.QAbstractButton.enterEvent(self, event)

    def leaveEvent(self, event):
        self.update()
        QtWidgets.QAbstractButton.leaveEvent(self, event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        active = self.underMouse() or (self.balloon is not None and self.balloon.isVisible())
        tone = QtGui.QColor(self._colors["accent" if active else "muted_text"])
        rect = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QtGui.QPen(tone, 1.2))
        fill = QtGui.QColor(tone)
        fill.setAlpha(45 if active else 0)
        painter.setBrush(fill)
        painter.drawEllipse(rect)
        font = QtGui.QFont(self.font())
        font.setBold(True)
        font.setPixelSize(px(10))
        painter.setFont(font)
        painter.drawText(self.rect(), int(Qt.AlignCenter), "?")
        painter.end()


class SuggestionDelegate(QtWidgets.QStyledItemDelegate):
    """Rows of the search suggestions: the text starts exactly where the search field's text does (no stair
    step), and hover / selection only colour the background."""

    def __init__(self, field, colors, parent=None):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)
        self.field = field
        self.colors = colors  # A callable returning the theme colours.

    def text_left(self, view):
        """Where the field's text begins, in the list's viewport coordinates."""
        option = QtWidgets.QStyleOptionFrame()
        self.field.initStyleOption(option)
        try:
            contents = self.field.style().subElementRect(QtWidgets.QStyle.SE_LineEditContents, option, self.field)
        except RuntimeError:  # The style's wrapper outlived it (qt_compat.repolish): near enough without it.
            contents = self.field.contentsRect()
        start = self.field.mapToGlobal(QtCore.QPoint(contents.left() + 2, 0))  # Qt's own 2 px inner margin.
        return view.viewport().mapFromGlobal(start).x()

    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), option.fontMetrics.height() + px(10))

    def paint(self, painter, option, index):
        colors = self.colors()
        painter.save()
        selected = option.state & QtWidgets.QStyle.State_Selected or option.state & QtWidgets.QStyle.State_MouseOver
        if selected:
            painter.fillRect(option.rect, QtGui.QColor(colors["selected"]))
        painter.setPen(QtGui.QColor(colors["selected_text"] if selected else colors["field_text"]))
        view = self.parent()
        left = max(4, self.text_left(view)) if view is not None else 8
        rect = option.rect.adjusted(left - option.rect.left(), 0, -left, 0)
        text = option.fontMetrics.elidedText(index.data() or "", Qt.ElideRight, rect.width())
        painter.drawText(rect, int(Qt.AlignLeft | Qt.AlignVCenter), text)
        painter.restore()


class Shimmer(QtWidgets.QWidget):
    """A light diagonal band that sweeps across `target` every few seconds to draw the eye. Painted here over the button, clipped to its rounded corners; mouse events pass through."""

    SWEEP_MS = 900
    PAUSE_MS = 2600
    SLANT = 0.45  # The band leans this much (horizontal per vertical).

    def __init__(self, target):
        QtWidgets.QWidget.__init__(self, target)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._active = False
        self._started = time.monotonic()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        target.installEventFilter(self)
        self.hide()

    def set_active(self, on):
        self._active = bool(on)
        self._started = time.monotonic()
        self._follow()

    def _follow(self):
        target = self.parentWidget()
        running = self._active and target.isVisible()
        if running:
            self.setGeometry(target.rect())
            self.raise_()
            self.show()
            self._timer.start()
        else:
            self._timer.stop()
            self.hide()

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.Hide, QtCore.QEvent.Resize):
            self._follow()
        return False

    def phase(self):
        """0..1 while the band sweeps, None in the pause."""
        elapsed = (time.monotonic() - self._started) * 1000.0 % (self.SWEEP_MS + self.PAUSE_MS)
        return elapsed / self.SWEEP_MS if elapsed < self.SWEEP_MS else None

    def paintEvent(self, event):
        f = self.phase()
        if f is None:
            return
        f = f * f * (3.0 - 2.0 * f)  # Ease in and out.
        width, height = float(self.width()), float(self.height())
        band = max(px(28), width * 0.35)
        x = -band - self.SLANT * height + f * (width + 2.0 * band + 2.0 * self.SLANT * height)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(QtCore.QRectF(self.rect()), px(6), px(6))
        painter.setClipPath(clip)
        # Across the band (perpendicular to its slant): clear, a soft light middle, clear.
        gradient = QtGui.QLinearGradient(x - band / 2.0, 0.0, x + band / 2.0, self.SLANT * band)
        for stop, alpha in ((0.0, 0), (0.42, 46), (0.5, 80), (0.58, 46), (1.0, 0)):
            gradient.setColorAt(stop, QtGui.QColor(255, 255, 255, alpha))
        painter.fillRect(self.rect(), QtGui.QBrush(gradient))
        painter.end()


class Marquee(QtWidgets.QWidget, Themed):
    """One line of text in the normal text colour; when it does not fit it runs from right to left in a loop
   , pausing a moment each time it comes round."""

    GAP = 60       # Pixels between the end of the text and its next start.
    STEP_MS = 30   # One pixel per step.
    PAUSE_MS = 1500

    def __init__(self, theme, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._text, self._offset, self._color = "", 0, QtGui.QColor("#d0d0d0")
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.STEP_MS)
        self.timer.timeout.connect(self._step)
        self._pause = QtCore.QTimer(self)
        self._pause.setSingleShot(True)
        self._pause.timeout.connect(self._restart)
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self._color = QtGui.QColor(colors.get("text", "#d0d0d0"))
        self.update()

    def setText(self, text):
        self._text = text or ""
        self.setToolTip(self._text)
        self._offset = 0
        self._sync()
        self.update()

    def text(self):
        return self._text

    def sizeHint(self):
        return QtCore.QSize(px(100), self.fontMetrics().height() + px(2))

    def _width(self):
        metrics = self.fontMetrics()
        width = getattr(metrics, "horizontalAdvance", None) or metrics.width
        return width(self._text)

    def _running(self):
        return self.isVisible() and self._width() > self.width()

    def _sync(self):
        if self._running():
            if not self.timer.isActive() and not self._pause.isActive():
                self._pause.start(self.PAUSE_MS)
        else:
            self.timer.stop()
            self._pause.stop()
            self._offset = 0

    def _restart(self):
        if self._running():
            self.timer.start()

    def _step(self):
        self._offset += 1
        if self._offset >= self._width() + px(self.GAP):
            self._offset = 0
            self.timer.stop()
            self._pause.start(self.PAUSE_MS)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(self._color)
        rect = self.rect()
        flags = int(Qt.AlignLeft | Qt.AlignVCenter)
        if self._running():
            width = self._width()
            painter.drawText(QtCore.QRect(-self._offset, 0, width, rect.height()), flags, self._text)
            painter.drawText(QtCore.QRect(width + px(self.GAP) - self._offset, 0, width, rect.height()), flags,
                             self._text)
        else:
            painter.drawText(rect, flags, self._text)
        painter.end()

    def resizeEvent(self, event):
        QtWidgets.QWidget.resizeEvent(self, event)
        self._sync()

    def showEvent(self, event):
        QtWidgets.QWidget.showEvent(self, event)
        self._sync()

    def hideEvent(self, event):
        self.timer.stop()
        self._pause.stop()
        QtWidgets.QWidget.hideEvent(self, event)


class ElidedLabel(QtWidgets.QLabel):
    """One line of text that shortens itself with "..." instead of widening its layout; the full text is the
    tooltip."""

    def __init__(self, text="", parent=None):
        QtWidgets.QLabel.__init__(self, parent)
        self._full = ""
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self._full = text or ""
        self.setToolTip(self._full)
        self._elide()

    def text(self):
        return self._full

    def _elide(self):
        width = max(0, self.contentsRect().width())
        QtWidgets.QLabel.setText(self, self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, width)
                                 if width > 0 else self._full)

    def resizeEvent(self, event):
        QtWidgets.QLabel.resizeEvent(self, event)
        self._elide()


def muted(text, wrap=True):
    label = QtWidgets.QLabel(text)
    label.setObjectName("toolMuted")
    label.setWordWrap(wrap)
    return label
