"""Shared pickers in the tool's own look: a number stepper and a date field with a themed calendar.

They are built from the shared Button and the style sheet rules in style.qss (rounded fields, accent for the
selection), so they sit next to the other controls without looking different.
"""

from ..qt_compat import QtCore, QtGui, QtWidgets, Qt, Signal, inherit_fonts, repolish, scale_font, work_area
from ..ui_scale import px
from .controls import Button, round_popup


class Stepper(QtWidgets.QFrame):
    """A whole-number field in one rounded frame: the value, and small up / down arrows stacked at the right edge.
    The arrow keys step it too; the wheel does not (it scrolls the page)."""

    valueChanged = Signal(int)

    def __init__(self, theme, minimum=0, maximum=999, value=0, parent=None):
        QtWidgets.QFrame.__init__(self, parent)
        self.setObjectName("toolStepper")
        self._minimum, self._maximum, self._value = minimum, maximum, value
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, px(3), 0)
        layout.setSpacing(0)
        self.edit = QtWidgets.QLineEdit(str(value))
        self.edit.setObjectName("toolStepValue")
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.setFixedWidth(px(40))
        self.edit.setValidator(QtGui.QIntValidator(minimum, maximum, self))
        self.edit.editingFinished.connect(self._from_text)
        self.edit.installEventFilter(self)
        arrows = QtWidgets.QVBoxLayout()
        arrows.setContentsMargins(0, px(2), 0, px(2))
        arrows.setSpacing(0)
        self.up = Button("", theme, icon="chevron-up", tooltip="Increase")
        self.down = Button("", theme, icon="chevron-down", tooltip="Decrease")
        for button, delta in ((self.up, 1), (self.down, -1)):
            button.setObjectName("toolStepArrow")
            button.icon_px = 10
            button._on_theme(theme.colors)
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoRepeat(True)
            button.clicked.connect(lambda _=False, d=delta: self.step(d))
            arrows.addWidget(button)
        layout.addWidget(self.edit)
        layout.addLayout(arrows)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    def value(self):
        return self._value

    def setValue(self, value):
        value = max(self._minimum, min(self._maximum, int(value)))
        self.edit.setText(str(value))
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    def step(self, delta):
        self.setValue(self._value + delta)

    def _from_text(self):
        try:
            self.setValue(int(self.edit.text()))
        except ValueError:
            self.edit.setText(str(self._value))

    def eventFilter(self, watched, event):
        if watched is self.edit:
            kind = event.type()
            if kind in (QtCore.QEvent.FocusIn, QtCore.QEvent.FocusOut):
                self.setProperty("focused", kind == QtCore.QEvent.FocusIn)
                repolish(self)
            elif kind == QtCore.QEvent.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down):
                self.step(1 if event.key() == Qt.Key_Up else -1)
                return True
            # The wheel is left to the page: scrolling never changes the number
        return QtWidgets.QFrame.eventFilter(self, watched, event)


class CalendarPopup(QtWidgets.QWidget):
    """A small month calendar: rounded frame, themed days, Monday first, the wheel changes the month."""

    picked = Signal(object)  # QDate

    def __init__(self, theme, parent):
        QtWidgets.QWidget.__init__(self, parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("toolCalendar")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._month = QtCore.QDate.currentDate()
        self._selected = QtCore.QDate.currentDate()
        self._dates = []
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QtWidgets.QFrame()
        frame.setObjectName("toolCalendarFrame")
        outer.addWidget(frame)
        body = QtWidgets.QVBoxLayout(frame)
        body.setContentsMargins(px(8), px(8), px(8), px(8))
        body.setSpacing(px(4))
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(px(4))
        previous = Button("", theme, icon="chevron-left", variant="ghost", tooltip="Previous month")
        following = Button("", theme, icon="chevron-right", variant="ghost", tooltip="Next month")
        previous.clicked.connect(lambda: self.move_month(-1))
        following.clicked.connect(lambda: self.move_month(1))
        self.title = QtWidgets.QLabel("")
        self.title.setObjectName("toolCalendarTitle")
        self.title.setAlignment(Qt.AlignCenter)
        head.addWidget(previous)
        head.addWidget(self.title, 1)
        head.addWidget(following)
        body.addLayout(head)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(px(2))
        grid.setContentsMargins(0, 0, 0, 0)
        for column, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            label = QtWidgets.QLabel(name)
            label.setObjectName("toolCalendarWeekday")
            label.setAlignment(Qt.AlignCenter)
            grid.addWidget(label, 0, column)
        self.days = []
        for index in range(42):
            button = QtWidgets.QPushButton("")
            button.setObjectName("toolDay")
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _=False, i=index: self._pick(i))
            grid.addWidget(button, 1 + index // 7, index % 7)
            self.days.append(button)
        body.addLayout(grid)
        today = Button("Today", theme, icon="calendar", variant="ghost")
        today.clicked.connect(self._today)
        body.addWidget(today, 0, Qt.AlignHCenter)

    def move_month(self, delta):
        self._month = self._month.addMonths(delta)
        self._fill()

    def wheelEvent(self, event):
        self.move_month(-1 if event.angleDelta().y() > 0 else 1)

    def _fill(self):
        first = QtCore.QDate(self._month.year(), self._month.month(), 1)
        start = first.addDays(-(first.dayOfWeek() - 1))
        today = QtCore.QDate.currentDate()
        self.title.setText("{} {}".format(QtCore.QLocale.c().monthName(first.month()), first.year()))
        self._dates = []
        for index, button in enumerate(self.days):
            date = start.addDays(index)
            self._dates.append(date)
            button.setText(str(date.day()))
            if date == self._selected:
                state = "selected"
            elif date == today:
                state = "today"
            elif date.month() != first.month():
                state = "other"
            else:
                state = ""
            if button.property("state") != state:
                button.setProperty("state", state)
                repolish(button)

    def _pick(self, index):
        self.picked.emit(self._dates[index])
        self.close()

    def _today(self):
        self.picked.emit(QtCore.QDate.currentDate())
        self.close()

    def show_for(self, field, date):
        self._selected = QtCore.QDate(date)
        self._month = QtCore.QDate(date)
        self._fill()
        scale_font(self)
        inherit_fonts(self)
        self.adjustSize()
        below = field.mapToGlobal(QtCore.QPoint(0, field.height() + 4))
        area = work_area(field.mapToGlobal(QtCore.QPoint(0, 0)))
        x, y = below.x(), below.y()
        if area is not None:
            if y + self.height() > area.bottom():
                y = field.mapToGlobal(QtCore.QPoint(0, 0)).y() - self.height() - 4
            x = max(area.left(), min(x, area.right() - self.width()))
            y = max(area.top(), y)
        self.move(x, y)
        self.show()
        round_popup(self, 8)  # The frame's own radius; corners are cut by a mask, not a translucent window


class DateField(Button):
    """A field showing a date; clicking it opens the themed calendar."""

    changed = Signal(object)  # QDate

    def __init__(self, theme, date=None, parent=None):
        Button.__init__(self, "", theme, icon="calendar", variant="field", parent=parent)
        self._date = QtCore.QDate(date) if date is not None else QtCore.QDate.currentDate()
        self._popup = None
        self.clicked.connect(self._open)
        self._sync()

    def date(self):
        return QtCore.QDate(self._date)

    def setDate(self, date):
        self._date = QtCore.QDate(date)
        self._sync()

    def _sync(self):
        self.setText(self._date.toString("yyyy-MM-dd"))

    def _open(self):
        if self._popup is None:
            self._popup = CalendarPopup(self._theme, self)
            self._popup.picked.connect(self._picked)
        self._popup.show_for(self, self._date)

    def _picked(self, date):
        if date != self._date:
            self._date = QtCore.QDate(date)
            self._sync()
            self.changed.emit(QtCore.QDate(date))
