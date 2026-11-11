"""The tool's main window: own title bar, resizable edges, collapse to a small bar, status bar with Settings / Logs /
About / Donate. Subclass it or put the tool's content into `self.body` (a QVBoxLayout).

Window rules (proven in TerraScoop on Max 2022-2027):
* No Windows frame: the title bar moves the window (drag), double-click maximises, minus collapses to a bar, X closes.
  The 4 px edges resize it. Windows 11 rounds the corners through DWM (qt_compat.round_window_corners).
* Place and size come back on the next start; a saved place off every screen falls back to centring on 3ds Max's
  screen. Screens are looked up by position (qt_compat.live_screens), never through widget.screen().
* The collapsed bar: grip (drag), icon, name (click opens again), X. Unplaced, it sits 8 px inside the active
  viewport's bottom-left corner; once dragged it keeps that place. It never goes under the taskbar or off the
  monitors, and it follows 3ds Max's window (moves, maximise, another display) through Qt's own move signals.
"""

from .. import DISPLAY_NAME, DONATE_URL, __version__
from .. import qt_compat
from ..qt_compat import (QtCore, QtGui, QtWidgets, Qt, bounded_window_position, inherit_fonts, is_valid, live_screens,
                         own_keyboard, primary_work_area, round_window_corners, scale_font, work_area)
from ..ui_scale import px
from . import controls


def _global_pos(event):
    """Global cursor position of a mouse event (PySide6 globalPosition, PySide2 globalPos)."""
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


def _on_screen(rect):
    """True when the top strip of `rect` (where its title bar is) is on some screen."""
    top = QtCore.QRect(rect.x(), rect.y(), rect.width(), 30)
    return any(area.intersected(top).width() >= 120 for _screen, area, _geometry in live_screens())


class ToolWindow(QtWidgets.QWidget):
    EDGE = 4  # Logical pixels around the window that resize it.
    MINI_GAP = 8  # Logical pixels between the collapsed bar and the viewport's corner.
    SETTLE_MS = 250  # After 3ds Max's window stops moving, the bar takes its final place once.
    PARKED = -30000  # Windows puts a minimised window at (-32000, -32000).

    def __init__(self, controller, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.controller = controller
        theme = controller.theme
        scale_font(self)  # Interface size, before any child exists (polished children keep their font).
        self.setObjectName("toolWindow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)  # The window background comes from the style sheet.
        self.setMouseTracking(True)
        self.setWindowTitle("{} {}".format(DISPLAY_NAME, __version__))
        self.setMinimumSize(px(340), px(300))
        self.resize(px(400), px(560))  # Opens narrow; the user may make it as wide as needed (remembered)
        self.geometry_restored = False
        self._resizing = None
        self._drag = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(px(self.EDGE), px(self.EDGE), px(self.EDGE), px(self.EDGE))  # Free edges.
        outer.setSpacing(0)

        # Title bar: icon, "Name version", optional pills, stretch, minimise (collapse), close.
        self.title_bar = QtWidgets.QFrame()
        self.title_bar.setObjectName("toolTitleBar")
        bar = QtWidgets.QHBoxLayout(self.title_bar)
        bar.setContentsMargins(px(8), px(4), px(4), px(2))
        bar.setSpacing(px(4))
        bar.addWidget(controls.BrandIcon(18))
        bar.addSpacing(px(3))
        title = QtWidgets.QLabel("{} {}".format(DISPLAY_NAME, __version__))
        title.setObjectName("toolWindowTitle")
        bar.addWidget(title)
        self.title_row = bar  # Status pills can join it, right of the name.
        bar.addStretch(1)
        for icon, tip, slot in (("minus", "Collapse to a small bar (click its name to open again)", self.minimise),
                                ("x", "Close " + DISPLAY_NAME, self.close)):
            button = controls.WindowButton(icon, theme, tip, close=(icon == "x"))
            button.clicked.connect(slot)
            bar.addWidget(button)
        self.title_bar.installEventFilter(self)
        outer.addWidget(self.title_bar)

        # Collapsed bar: grip (drag), icon, name (click opens again), close.
        self.mini_bar = QtWidgets.QFrame()
        self.mini_bar.setObjectName("toolMiniBar")
        mini = QtWidgets.QHBoxLayout(self.mini_bar)
        mini.setContentsMargins(px(2), px(1), px(1), px(1))  # Compact: as small as the bar of Max Ultra MCP
        mini.setSpacing(px(2))
        self.mini_grip = QtWidgets.QLabel()
        self.mini_grip.setFixedSize(px(14), px(22))
        self.mini_grip.setAlignment(Qt.AlignCenter)
        self.mini_grip.setCursor(Qt.SizeAllCursor)
        self.mini_grip.setToolTip("Drag to move")
        self.mini_grip.installEventFilter(self)
        mini.addWidget(self.mini_grip)
        mini.addWidget(controls.BrandIcon(14))
        self.mini_title = QtWidgets.QPushButton(DISPLAY_NAME)
        self.mini_title.setObjectName("toolMiniTitle")
        self.mini_title.setCursor(Qt.PointingHandCursor)
        self.mini_title.setToolTip("Open {} {} again".format(DISPLAY_NAME, __version__))
        self.mini_title.installEventFilter(self)  # A click opens the window, a drag moves the bar.
        mini.addWidget(self.mini_title, 1)
        mini_close = controls.WindowButton("x", theme, "Close " + DISPLAY_NAME, close=True, small=True)
        mini_close.clicked.connect(self.close)
        mini.addWidget(mini_close)
        self.mini_bar.hide()
        self.mini_bar.installEventFilter(self)  # Enter clears the edge cursor (eventFilter)
        outer.addWidget(self.mini_bar)
        self._mini = None  # While collapsed: (geometry, minimum size, visible parts) to come back to.
        self._host_window = None  # While collapsed: 3ds Max's window (QWindow) whose moves the bar follows.
        self._host_widget = None
        self._host_rect = None
        self._followed = False
        self._settle_timer = None

        # Content and status bar.
        self.full_view = QtWidgets.QWidget()
        outer.addWidget(self.full_view, 1)
        self.full_view.installEventFilter(self)  # Enter clears the edge cursor (eventFilter)
        root = QtWidgets.QVBoxLayout(self.full_view)
        root.setContentsMargins(px(8), px(6), px(8), px(6))
        root.setSpacing(px(6))
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(px(8))
        root.addLayout(self.body, 1)
        status = QtWidgets.QHBoxLayout()
        status.setSpacing(px(6))
        self.status_label = controls.ElidedLabel("")  # Long messages end with an ellipsis instead of being cut
        self.status_label.setObjectName("toolMuted")
        status.addWidget(self.status_label, 1)
        self.status_row = status  # Pills (left of the message) or more buttons can be inserted.
        for text, icon, tip, slot in (("Settings", "settings", "Theme, interface size and options",
                                       controller.show_settings),
                                      ("Logs", "logs", "Show the log", controller.show_logs),
                                      ("About", "info", "About " + DISPLAY_NAME, controller.show_about)):
            button = controls.Button("", theme, icon=icon, variant="ghost", tooltip=tip)  # Icon only: saves width
            button.clicked.connect(slot)
            status.addWidget(button)
        if DONATE_URL:  # Only with a destination the owner gave; the last button on the right.
            self.donate_button = controls.Button("Donate", theme, icon="heart", variant="donate",
                                                 tooltip="Support {} development".format(DISPLAY_NAME))
            self.donate_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(DONATE_URL)))
            status.addWidget(self.donate_button)
        root.addLayout(status)

    # Header shade ------------------------------------------------------------------------------------
    HEADER_SHADE = 0.7  # Opacity of the black at the very top; it fades to nothing where the content starts

    def header_bottom(self):
        """Where the header ends, in window coordinates: the shade fades out there. Below the title bar here;
        windows with more header (the packager's tabs) say where theirs ends."""
        return self.title_bar.geometry().bottom() + px(6)

    def paintEvent(self, event):
        """A dark shade from the top of the window to the start of the content sets the header apart. It is painted
        on the window's own background, under the title bar and the tabs."""
        QtWidgets.QWidget.paintEvent(self, event)
        if self._mini is not None or not self.title_bar.isVisible():
            return
        bottom = self.header_bottom()
        shade = QtGui.QLinearGradient(0, 0, 0, bottom)
        dark = QtGui.QColor(0, 0, 0)
        dark.setAlphaF(self.HEADER_SHADE)
        shade.setColorAt(0.0, dark)
        shade.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(self)
        painter.fillRect(QtCore.QRect(0, 0, self.width(), bottom), shade)
        painter.end()

    # Status ---------------------------------------------------------------------------------------
    def set_status(self, text):
        self.status_label.setText(text)

    # Title bar drag, collapsed bar drag / click ------------------------------------------------------
    def eventFilter(self, watched, event):
        # The resize arrows belong to the free edge only. Children inherit the window's cursor, and the window gets no
        # event when the pointer moves from the edge onto a child (title bar, content), so entering one clears it:
        # inside the window the pointer is the ordinary arrow.
        if event.type() == QtCore.QEvent.Enter and self._resizing is None and                 watched in (getattr(self, "title_bar", None), getattr(self, "full_view", None),
                            getattr(self, "mini_bar", None)):
            self.unsetCursor()
        if watched in (getattr(self, "mini_grip", None), getattr(self, "mini_title", None)):
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag = _global_pos(event) - self.frameGeometry().topLeft()
                self._drag_from = _global_pos(event)
                self._dragged = False
                return True
            if kind == QtCore.QEvent.MouseMove and self._drag is not None:
                if (_global_pos(event) - self._drag_from).manhattanLength() > 4:
                    self._dragged = True
                if self._dragged:  # Never below the taskbar or off the screens.
                    self.move(bounded_window_position(_global_pos(event) - self._drag, self.frameGeometry().size(),
                                                      _global_pos(event)))
                return True
            if kind == QtCore.QEvent.MouseButtonRelease and self._drag is not None:
                self._drag = None
                if self._dragged:
                    self.controller.set_preference("mini_position", [self.x(), self.y()])
                elif watched is self.mini_title:
                    QtCore.QTimer.singleShot(0, self.restore_from_mini)
                return True
        if watched is getattr(self, "title_bar", None):
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.showNormal() if self.isMaximized() else self.showMaximized()
                return True
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag = _global_pos(event) - self.frameGeometry().topLeft()
                return True
            if kind == QtCore.QEvent.MouseMove and self._drag is not None:
                if self.isMaximized():  # Dragging a maximised window restores it under the cursor.
                    ratio = float(self._drag.x()) / max(1, self.width())
                    self.showNormal()
                    self._drag = QtCore.QPoint(int(self.width() * ratio), self._drag.y())
                self.move(_global_pos(event) - self._drag)
                return True
            if kind == QtCore.QEvent.MouseButtonRelease:
                self._drag = None
        return QtWidgets.QWidget.eventFilter(self, watched, event)

    # Resizing by the edges ---------------------------------------------------------------------------
    def _edges(self, pos):
        if self._mini is not None or self.isMaximized():
            return 0
        x, y, w, h, e = pos.x(), pos.y(), self.width(), self.height(), px(self.EDGE) + 2
        return (1 if x <= e else 0) | (2 if x >= w - e else 0) | (4 if y <= e else 0) | (8 if y >= h - e else 0)

    _CURSORS = {1: Qt.SizeHorCursor, 2: Qt.SizeHorCursor, 4: Qt.SizeVerCursor, 8: Qt.SizeVerCursor,
                5: Qt.SizeFDiagCursor, 10: Qt.SizeFDiagCursor, 6: Qt.SizeBDiagCursor, 9: Qt.SizeBDiagCursor}

    def mousePressEvent(self, event):
        edges = self._edges(event.pos())
        if edges and event.button() == Qt.LeftButton:
            self._resizing = (edges, _global_pos(event), self.geometry())
            return
        QtWidgets.QWidget.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if self._resizing is not None:
            edges, start, geometry = self._resizing
            delta = _global_pos(event) - start
            rect = QtCore.QRect(geometry)
            minimum = self.minimumSize()
            if edges & 1:
                rect.setLeft(min(rect.left() + delta.x(), rect.right() - minimum.width()))
            if edges & 2:
                rect.setRight(max(rect.right() + delta.x(), rect.left() + minimum.width()))
            if edges & 4:
                rect.setTop(min(rect.top() + delta.y(), rect.bottom() - minimum.height()))
            if edges & 8:
                rect.setBottom(max(rect.bottom() + delta.y(), rect.top() + minimum.height()))
            self.setGeometry(rect)
            return
        cursor = self._CURSORS.get(self._edges(event.pos()))
        if cursor is not None:
            self.setCursor(cursor)
        else:
            self.unsetCursor()
        QtWidgets.QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        self._resizing = None
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def leaveEvent(self, event):
        if self._resizing is None:
            self.unsetCursor()
        QtWidgets.QWidget.leaveEvent(self, event)

    # Window position and size ----------------------------------------------------------------------
    def geometry_state(self):
        state = self._mini[0] if self._mini is not None else self.saveGeometry()  # Collapsed: the full window's.
        return bytes(state.toBase64()).decode("ascii")

    def restore_geometry_state(self, encoded):
        """Restore the saved position/size; fall back to centred on 3ds Max's screen when it is off every screen."""
        restored = False
        if encoded:
            try:
                restored = bool(self.restoreGeometry(QtCore.QByteArray.fromBase64(encoded.encode("ascii"))))
            except (ValueError, TypeError):
                restored = False
        frame = self.geometry()
        visible = any(area.intersected(frame).width() >= 160 and area.intersected(frame).height() >= 120
                      for _screen, area, _geometry in live_screens())
        if restored and visible:
            self.geometry_restored = True
            return
        area = None
        if self.parentWidget() is not None:  # By position: never parentWidget().screen() (a dead QScreen in Max 2024).
            area = work_area(self.parentWidget().frameGeometry().center())
        area = area or primary_work_area()
        width, height = min(self.width(), area.width()), min(self.height(), area.height())
        self.setGeometry(area.x() + (area.width() - width) // 2, area.y() + (area.height() - height) // 2,
                         width, height)

    # Collapsed bar -----------------------------------------------------------------------------------
    def minimise(self):
        """Collapse to the small bar; restore_from_mini() brings back the same place and size."""
        if self._mini is not None:
            return
        if self.isMaximized():
            self.showNormal()
        parts = [part for part in (self.title_bar, self.full_view) if part.isVisible()]
        self._mini = (self.saveGeometry(), self.minimumSize(), parts)
        for part in parts:
            part.hide()
        self.mini_grip.setPixmap(controls.icon_pixmap("grip-vertical", self.controller.theme.color("muted_text"),
                                                      px(14), controls.device_pixel_ratio(self)))
        self.mini_bar.show()
        self.setMinimumSize(0, 0)
        size = QtCore.QSize(self.mini_bar.sizeHint().width() + 2 * px(self.EDGE),
                            self.mini_bar.sizeHint().height() + 2 * px(self.EDGE))
        self.resize(size)
        saved = self.controller.prefs.get("mini_position") or []
        if len(saved) == 2 and _on_screen(QtCore.QRect(int(saved[0]), int(saved[1]), size.width(), size.height())):
            self.move(int(saved[0]), int(saved[1]))  # Where the user last put it.
        else:
            self.move(self._mini_home(size))
        self.confine_mini()
        self.follow_host(True)
        if not getattr(self, "_watching_screens", False):  # Taskbar moved, screen added or removed.
            self._watching_screens = True
            application = QtGui.QGuiApplication.instance()
            application.screenAdded.connect(self._watch_screen)
            application.screenRemoved.connect(lambda *_: self.confine_mini())
            for screen, _area, _geometry in live_screens():
                self._watch_screen(screen)

    def _mini_home(self, size):
        """Top-left for an unplaced bar: inside the active viewport's bottom-left corner; without a viewport (outside
        Max), bottom-left of the host window above its time slider."""
        viewport = qt_compat.active_viewport_rect()
        if viewport is not None and viewport.width() > size.width() and viewport.height() > size.height():
            gap = px(self.MINI_GAP)
            return QtCore.QPoint(viewport.left() + gap, viewport.top() + viewport.height() - gap - size.height())
        widget = self._host_widget if self._host_widget is not None else self.parentWidget()
        host = widget.frameGeometry() if widget is not None else None
        if host is None or host.width() < size.width():
            host = primary_work_area()
        return QtCore.QPoint(host.left() + 12, host.bottom() - size.height() - 110)

    def _watch_screen(self, screen):
        try:
            screen.availableGeometryChanged.connect(lambda *_: self.confine_mini())
        except RuntimeError:  # A screen whose wrapper is already dead (qt_compat.live_screens).
            pass
        self.confine_mini()

    def confine_mini(self):
        """The collapsed bar stays inside a screen's work area (above the taskbar)."""
        if self._mini is None or not is_valid(self):
            return
        bounded = bounded_window_position(self.pos(), self.frameGeometry().size())
        if bounded != self.pos():
            self.move(bounded)

    def follow_host(self, on, host=None):
        """While collapsed, the bar moves with 3ds Max's main window (also to another display).

        Driven only by Qt's own "window moved / resized" signals of Max's window: nothing polls and nothing runs while
        Max stands still. Connected on collapse, disconnected on restore and close. `host` replaces Max's window in a
        standalone test. In safe mode, or when Max's window cannot be reached, the bar simply stays.
        """
        handle, self._host_window = self._host_window, None
        if handle is not None:
            for signal in (handle.xChanged, handle.yChanged, handle.widthChanged, handle.heightChanged):
                try:
                    signal.disconnect(self._host_moved)
                except (RuntimeError, TypeError):  # Max's window or its wrapper is gone.
                    pass
        if self._settle_timer is not None:
            self._settle_timer.stop()
        self._host_widget, self._followed = None, False
        widget = host if host is not None else self.parentWidget()
        if not on or widget is None or qt_compat.SAFE["on"]:
            return
        try:
            handle = widget.windowHandle()
            if handle is None:
                return
            self._host_rect = QtCore.QRect(handle.frameGeometry())
            for signal in (handle.xChanged, handle.yChanged, handle.widthChanged, handle.heightChanged):
                signal.connect(self._host_moved)
        except (RuntimeError, AttributeError):
            return
        self._host_window, self._host_widget = handle, widget

    def _host_moved(self, *_args):
        """3ds Max's window moved or changed size: the bar keeps its distance to Max's nearest edges."""
        handle = self._host_window
        if self._mini is None or handle is None or not is_valid(self):
            return
        try:
            new = QtCore.QRect(handle.frameGeometry())
            # Windows hides the bar with its owner and brings it back where it was. A minimised window is parked at
            # -32000 before (or without) its state saying so: never follow it there.
            if handle.visibility() == QtGui.QWindow.Minimized or new.left() <= self.PARKED or new.top() <= self.PARKED:
                return
        except RuntimeError:
            self.follow_host(False)
            return
        old, self._host_rect = self._host_rect, new
        bar = self.frameGeometry()
        if old is None or new == old or not old.intersects(bar):
            return  # The user put the bar away from 3ds Max: it stays there.
        left, right = bar.left() - old.left(), old.right() - bar.right()
        top, bottom = bar.top() - old.top(), old.bottom() - bar.bottom()
        x = new.left() + left if left <= right else new.right() - right - bar.width() + 1
        y = new.top() + top if top <= bottom else new.bottom() - bottom - bar.height() + 1
        self.move(x, y)
        self._followed = True
        if self._settle_timer is None:
            self._settle_timer = QtCore.QTimer(self)
            self._settle_timer.setSingleShot(True)  # Started by a move only; never runs on its own.
            self._settle_timer.timeout.connect(self._host_settled)
        self._settle_timer.start(self.SETTLE_MS)

    def _host_settled(self):
        if self._mini is None or not self._followed or not is_valid(self):
            return
        self._followed = False
        if self.controller.prefs.get("mini_position"):
            self.confine_mini()
            self.controller.set_preference("mini_position", [self.x(), self.y()])  # Placed by the user: its new place.
        else:
            self.move(self._mini_home(self.size()))  # The active viewport's corner on the new display.
            self.confine_mini()

    def restore_from_mini(self):
        if self._mini is None:
            return
        self.follow_host(False)
        geometry, minimum, parts = self._mini
        self._mini = None
        self.mini_bar.hide()
        for part in parts:
            part.show()
        self.setMinimumSize(minimum)
        self.restoreGeometry(geometry)  # Its own place and size, wherever the bar was.

    # Showing, corners, keys, closing ----------------------------------------------------------------
    RADIUS = 8  # Corner radius of the fallback mask; Windows 11's own rounding is 8 px too.

    def showEvent(self, event):
        QtWidgets.QWidget.showEvent(self, event)
        # Children are polished now: a widget matched by a style sheet rule (lists, tables) got the application's font
        # back at polish time, not the window's interface-size font. Give it the window's size again.
        inherit_fonts(self)
        # Rounded corners: Windows 11 DWM rounds them smoothly and draws the thin border in the theme's border
        # colour. Where DWM cannot (Windows 10, remote sessions), a rounded window mask does it (hard edges).
        self._dwm_round = round_window_corners(self, self.controller.theme.colors.get("border"))
        self._mask_corners()
        self.own_keyboard()

    def resizeEvent(self, event):
        QtWidgets.QWidget.resizeEvent(self, event)
        self._mask_corners()

    def _mask_corners(self):
        if getattr(self, "_dwm_round", True) or qt_compat.SAFE["on"]:
            return  # DWM rounds them, or safe mode keeps native extras off.
        if self.isMaximized() or self.isFullScreen():
            self.clearMask()  # A maximised window has square corners, as everywhere in Windows.
            return
        radius = px(self.RADIUS)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), radius, radius)
        self.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))

    def own_keyboard(self):
        """Max's hotkeys stay off while any of the tool's widgets has the focus, so Esc, Delete and letters reach it.
        Run again when widgets are created later (a web page's focus proxy, rebuilt rows)."""
        own_keyboard([self] + self.findChildren(QtWidgets.QWidget))

    def closeEvent(self, event):
        # Closing the window ends the session (the controller asks first while work runs).
        if not self.controller.confirm_stop("close"):
            event.ignore()
            return
        QtWidgets.QWidget.closeEvent(self, event)
        if event.isAccepted():
            self.controller.request_stop()

    def dispose(self):
        self.follow_host(False)
