"""The changelog editor of the Release page, built for quick typing.

* One line on top: type, text, add. Enter adds and keeps the cursor there, so many items go in quickly.
* Lines may start with the release-note prefixes ("+ " Added, "- " Fixed, "* " Changed, "** " Improved) or with
  "Added:"; pasting several lines adds one item per line.
* Items show a coloured type badge; the type dropdowns (here and in the edit window) show the same badges, closed
  and open. Drag to reorder, Delete removes the selection.
* Double-click opens a small edit window (type, text, OK / Cancel), so adding and editing are never confused.
"""

import math

from ..core import project as core
from ..qt_compat import QtCore, QtGui, QtWidgets, Qt
from ..ui_scale import px
from ..qt_compat import exec_dialog


def exec_menu(menu, point):
    menu.popup_at(point)  # controls.Menu: gets the interface-size font first
from . import controls
from .dialogs import ToolDialog

KIND_COLORS = {"Added": "log_success", "Fixed": "log_warning", "Changed": "log_info", "Removed": "log_error",
               "Improved": "log_system"}
KIND_ROLE = Qt.UserRole


def _badge_font(base):
    font = QtGui.QFont(base)
    font.setBold(True)
    font.setPointSizeF(font.pointSizeF() * 0.85)
    return font


def badge_width(base):
    """Every badge is as wide as the longest type, so the texts after them start in one column."""
    metrics = QtGui.QFontMetricsF(_badge_font(base))
    return max(metrics.horizontalAdvance(name) for name in core.CHANGELOG_TYPES) + px(12)


def draw_badge(painter, left, center_y, kind, colors, base):
    """The coloured badge of a changelog type with its name in the middle (centred on the capital letters).
    Returns its rectangle."""
    font = _badge_font(base)
    metrics = QtGui.QFontMetricsF(font)
    height = metrics.capHeight() + px(9)
    badge = QtCore.QRectF(left, center_y - height / 2.0, badge_width(base), height)
    role = KIND_COLORS.get(kind, "log_info")
    painter.save()
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QtGui.QColor(colors[role + "_background"]))
    painter.drawRoundedRect(badge, height / 2.0, height / 2.0)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(colors[role]))
    painter.drawText(QtCore.QPointF(math.floor(badge.center().x() - metrics.horizontalAdvance(kind) / 2.0),
                                    round(badge.center().y() + metrics.capHeight() / 2.0)), kind)
    painter.restore()
    return badge


class KindBadge(QtWidgets.QWidget, controls.Themed):
    """The badge of a changelog type as a widget of its own, for a list of notes outside the editor."""

    def __init__(self, kind, theme, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._kind = kind
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.bind_theme(theme)

    def _on_theme(self, colors):
        self._colors = colors
        self.update()

    def sizeHint(self):
        height = QtGui.QFontMetricsF(_badge_font(self.font())).capHeight() + px(9)
        return QtCore.QSize(int(math.ceil(badge_width(self.font()))), int(math.ceil(height)) + 1)

    minimumSizeHint = sizeHint

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        draw_badge(painter, 0, self.height() / 2.0, self._kind, self._colors, self.font())
        painter.end()


class KindDelegate(QtWidgets.QStyledItemDelegate):
    """The rows of the type dropdown: the badge of each type, as it will look in the list."""

    def __init__(self, theme, parent=None):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)
        self.theme = theme

    def sizeHint(self, option, index):
        return QtCore.QSize(int(badge_width(option.font)) + px(18), option.fontMetrics.height() + px(12))

    def paint(self, painter, option, index):
        colors = self.theme.colors
        rect = QtCore.QRectF(option.rect).adjusted(px(3), px(1), -px(3), -px(1))
        if option.state & (QtWidgets.QStyle.State_Selected | QtWidgets.QStyle.State_MouseOver):
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(colors["hover"]))
            painter.drawRoundedRect(rect, px(5), px(5))
            painter.restore()
        draw_badge(painter, rect.left() + px(6), rect.center().y(), index.data(Qt.UserRole), colors, option.font)


class KindComboBox(controls.ComboBox):
    """The changelog type: a dropdown that shows the type as its coloured badge, closed and open."""

    def __init__(self, theme, parent=None):
        controls.ComboBox.__init__(self, parent)
        self.theme = theme
        for name in core.CHANGELOG_TYPES:
            self.addItem(name, name)
        self.view().setItemDelegate(KindDelegate(theme, self))
        self._fit_width()

    def _fit_width(self):
        """Exactly the badge, a small gap and the arrow (style sheet: 8 px padding left, 26 px right, 1 px borders);
        the open list takes the same width. Again whenever the font changes: the field is built before its window
        gives it the interface-size font."""
        self.setFixedWidth(int(badge_width(self.font())) + px(40))

    def changeEvent(self, event):
        controls.ComboBox.changeEvent(self, event)
        if event.type() == QtCore.QEvent.FontChange:
            self._fit_width()

    def paintEvent(self, event):
        painter = QtWidgets.QStylePainter(self)
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = ""  # The badge takes the place of the text
        painter.drawComplexControl(QtWidgets.QStyle.CC_ComboBox, option)
        field = self.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, option,
                                            QtWidgets.QStyle.SC_ComboBoxEditField, self)
        draw_badge(painter, field.left() + px(2), QtCore.QRectF(field).center().y(), self.currentData(),
                   self.theme.colors, self.font())


class ItemDelegate(QtWidgets.QStyledItemDelegate):
    """A coloured type badge, then the text in one line (elided; the full text is in the tooltip)."""

    def __init__(self, theme, parent=None):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)
        self.theme = theme

    def sizeHint(self, option, index):
        return QtCore.QSize(0, option.fontMetrics.height() + px(12))

    def paint(self, painter, option, index):
        colors = self.theme.colors
        kind, body = index.data(KIND_ROLE)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = option.rect.adjusted(px(2), px(1), -px(2), -px(1))
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(colors["selected"]))
            painter.drawRoundedRect(rect, px(5), px(5))
        elif option.state & QtWidgets.QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(colors["hover"]))
            painter.drawRoundedRect(rect, px(5), px(5))
        badge = draw_badge(painter, rect.left() + px(6), QtCore.QRectF(rect).center().y(), kind, colors, option.font)
        painter.setFont(option.font)
        selected = bool(option.state & QtWidgets.QStyle.State_Selected)
        painter.setPen(QtGui.QColor(colors["selected_text"] if selected else colors["field_text"]))
        text_rect = QtCore.QRectF(badge.right() + px(8), rect.top(), rect.right() - badge.right() - px(12), rect.height())
        painter.drawText(text_rect, int(Qt.AlignVCenter | Qt.AlignLeft),
                         option.fontMetrics.elidedText(body, Qt.ElideRight, int(text_rect.width())))
        painter.restore()


class EntryDialog(ToolDialog):
    """Edit one changelog item: its type and its text. Enter = OK, Esc = Cancel."""

    def __init__(self, controller, parent, kind, body):
        ToolDialog.__init__(self, controller, "Edit changelog item", parent)
        theme = controller.theme
        self.setMinimumWidth(px(340))
        lay = QtWidgets.QVBoxLayout(self.content)
        lay.setContentsMargins(px(14), px(14), px(14), px(12))
        lay.setSpacing(px(8))
        self.kind = KindComboBox(theme)
        self.kind.setCurrentIndex(max(0, self.kind.findData(kind)))
        self.text = QtWidgets.QLineEdit(body)
        self.text.setPlaceholderText("What changed for users?")
        self.text.textChanged.connect(lambda value: self.ok.setEnabled(bool(value.strip())))
        for caption, widget in (("Type", self.kind), ("Text", self.text)):
            label = QtWidgets.QLabel(caption)
            label.setObjectName("toolCaption")
            lay.addWidget(label)
            lay.addWidget(widget)
        lay.addSpacing(px(4))
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(px(6))
        buttons.addStretch(1)
        cancel = controls.Button("Cancel", theme)
        cancel.clicked.connect(self.reject)
        self.ok = controls.Button("OK", theme, icon="check", variant="primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        self.text.selectAll()

    def entry(self):
        return self.kind.currentData(), self.text.text().strip()


class ChangelogEditor(QtWidgets.QWidget):
    def __init__(self, theme, get_items, on_change, controller=None, parent=None):
        """`get_items()` returns the project's changelog list (edited in place); `on_change()` saves and revalidates."""
        QtWidgets.QWidget.__init__(self, parent)
        self.theme = theme
        self.controller = controller
        self.get_items = get_items
        self.on_change = on_change
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(6))

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(6))
        self.kind = KindComboBox(theme)
        self.text = QtWidgets.QLineEdit()
        self.text.setPlaceholderText("What changed for users?  Enter adds")
        self.text.returnPressed.connect(self.commit)
        self.text.installEventFilter(self)
        self.add = controls.Button("", theme, icon="plus", variant="primary", tooltip="Add (Enter)")
        self.add.clicked.connect(self.commit)
        for widget, stretch in ((self.kind, 0), (self.text, 1), (self.add, 0)):
            top.addWidget(widget, stretch)
        lay.addLayout(top)

        self.items = QtWidgets.QListWidget()
        self.items.setItemDelegate(ItemDelegate(theme, self.items))
        self.items.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.items.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.items.setDefaultDropAction(Qt.MoveAction)
        self.items.setMouseTracking(True)
        self.items.setMinimumHeight(px(110))
        self.items.itemSelectionChanged.connect(self.sync)
        self.items.itemDoubleClicked.connect(self.start_edit)
        self.items.model().rowsMoved.connect(self.reordered)
        self.items.installEventFilter(self)
        self.items.setContextMenuPolicy(Qt.CustomContextMenu)
        self.items.customContextMenuRequested.connect(self.context_menu)
        self.items_box = controls.boxed(self.items)
        lay.addWidget(self.items_box, 1)

        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(px(6))
        self.hint = controls.muted("", wrap=True)  # Wraps: a long hint must never widen the page
        self.delete = controls.Button("", theme, icon="trash-2", variant="danger", tooltip="Remove the selected items (Delete)")
        self.delete.clicked.connect(self.remove_selected)
        bottom.addWidget(self.hint, 1)
        bottom.addWidget(self.delete)
        lay.addLayout(bottom)
        self.refresh()

    # ---- content -------------------------------------------------------------------------------------------------
    def refresh(self):
        self.items.blockSignals(True)
        self.items.clear()
        for kind, body in self.get_items():
            item = QtWidgets.QListWidgetItem("{}: {}".format(kind, body))
            item.setData(KIND_ROLE, (kind, body))
            item.setToolTip(body)
            self.items.addItem(item)
        self.items.blockSignals(False)
        self.sync()

    def sync(self):
        count = len(self.get_items())
        selected = len(self.items.selectedItems())
        self.delete.setEnabled(selected > 0)
        if count:
            self.hint.setText("{} item{} · double-click edits · drag to reorder".format(count, "" if count == 1 else "s"))
        else:
            self.hint.setText("Type a change above. Prefixes: + Added, - Fixed, * Changed, ** Improved")

    # ---- adding and editing --------------------------------------------------------------------------------------
    def commit(self):
        entries = [core.parse_changelog_line(line, self.kind.currentData())
                   for line in self.text.text().splitlines() if line.strip()]
        if not entries or not entries[0][1]:
            return
        self.get_items().extend(entries)
        self.text.clear()
        self.refresh()
        self.items.scrollToBottom()
        self.on_change()
        self.text.setFocus()

    def paste_lines(self):
        """Several pasted lines become several items (the field itself only holds one line)."""
        text = QtWidgets.QApplication.clipboard().text()
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            return False
        items = self.get_items()
        for line in lines:
            items.append(core.parse_changelog_line(line, self.kind.currentData()))
        self.refresh()
        self.on_change()
        return True

    def start_edit(self, item):
        row = self.items.row(item)
        items = self.get_items()
        kind, body = items[row]
        dialog = EntryDialog(self.controller, self.window(), kind, body)
        try:
            if exec_dialog(dialog) and dialog.entry()[1]:
                items[row] = dialog.entry()
                self.refresh()
                self.items.setCurrentRow(row)
                self.on_change()
        finally:
            dialog.dispose()

    def context_menu(self, position):
        item = self.items.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.items.setCurrentItem(item)
        count = len(self.items.selectedItems())
        menu = controls.Menu(self.theme, self)
        menu.add_item("Edit…", "pencil", lambda: self.start_edit(item), enabled=count == 1)
        menu.addSeparator()
        menu.add_item("Delete" if count == 1 else "Delete {} items".format(count), "trash-2", self.remove_selected,
                      danger=True)
        exec_menu(menu, self.items.viewport().mapToGlobal(position))

    def remove_selected(self):
        rows = sorted((self.items.row(item) for item in self.items.selectedItems()), reverse=True)
        items = self.get_items()
        for row in rows:
            del items[row]
        self.text.clear()
        self.refresh()
        self.on_change()

    def reordered(self, *_args):
        order = [self.items.item(row).data(KIND_ROLE) for row in range(self.items.count())]
        self.get_items()[:] = [tuple(entry) for entry in order]
        self.on_change()

    # ---- keys ------------------------------------------------------------------------------------------------------
    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if watched is self.items and event.key() == Qt.Key_Delete:
                self.remove_selected()
                return True
            if watched is self.text:
                pasted = (event.matches(QtGui.QKeySequence.Paste))
                if pasted and self.paste_lines():
                    return True
        return QtWidgets.QWidget.eventFilter(self, watched, event)
