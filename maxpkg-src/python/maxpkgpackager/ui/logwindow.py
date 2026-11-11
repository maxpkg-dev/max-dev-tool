"""The Logs window, built like the log of MaxPkg Runtime Manager.

A day picker (Today, Yesterday, Thu 29 Oct 2026 ... : one log file per day), the level filter (All / Warnings /
Errors), a search and a summary on top. Records in a monospaced view: each level is a
rounded pill, long messages wrap under the message column, no horizontal scrolling. Whole records are selected with
a click, Shift, Ctrl or a drag, and copied (Ctrl+C) or exported (Ctrl+E); the context menu has the same. Clear Logs
deletes the log files of every day after a confirmation. Live follows new records and new days. F5 reloads, Ctrl+F
searches, Esc clears the selection, then closes.
"""

import os

from .. import DISPLAY_NAME, logs, settings
from ..qt_compat import QtCore, QtGui, QtWidgets, Qt, Signal
from ..ui_scale import pt, px
from . import controls
from .dialogs import ToolDialog, ask, diagnostics, open_folder
from .statuslog import _monospace, band_span, paint_pills
from .switch import Switch

SOURCE_WIDTH = 12
MESSAGE_COLUMN = 8 + 2 + 9 + 2 + SOURCE_WIDTH + 2  # time, level pill and source, each followed by two spaces
SHOWN_LIMIT = 4000
LINE_HEIGHT = 135
LEVEL_ROLES = {"DEBUG": "log_debug", "INFO": "log_info", "WARNING": "log_warning", "ERROR": "log_error",
               "CRITICAL": "log_error"}
SCROLL_KEYS = (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End)


class RecordView(QtWidgets.QTextEdit):
    """Read-only log text with whole-record selection. `rows`: line -> record index; `pills`: line -> (start,
    length, colour, label, label colour). The selection and the pills are painted under the text."""

    selection_changed = Signal()
    menu_requested = Signal(QtCore.QPoint)

    def __init__(self):
        QtWidgets.QTextEdit.__init__(self)
        self.rows, self.pills = {}, {}
        self.count = 0
        self.selected = set()
        self.anchor = None
        self.selection_color = QtGui.QColor(0, 0, 0, 0)
        self.cap_height = 8.0
        self.pill_font = QtGui.QFont()
        self._dragging = False
        self.setReadOnly(True)  # Before the flags: setReadOnly resets them
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.viewport().setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)  # Paths have no spaces to break at
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(px(10))

    @staticmethod
    def _point(event):
        position = getattr(event, "position", None)
        return position().toPoint() if position else event.pos()

    def row_at(self, point):
        block = self.cursorForPosition(point).block()
        rect = self.document().documentLayout().blockBoundingRect(block)
        top = rect.top() - self.verticalScrollBar().value()
        if not top <= point.y() < top + rect.height():
            return -1
        return self.rows.get(block.blockNumber(), -1)

    def set_selection(self, indices, anchor=None):
        self.selected = set(index for index in indices if 0 <= index < self.count)
        self.anchor = anchor if anchor is not None and 0 <= anchor < self.count else None
        self.viewport().update()
        self.selection_changed.emit()

    def select_all(self):
        self.set_selection(range(self.count), 0 if self.count else None)

    def clear_selection(self):
        self.set_selection(())

    def mousePressEvent(self, event):
        self.setFocus()
        index = self.row_at(self._point(event))
        modifiers = event.modifiers()
        if event.button() == Qt.LeftButton:
            if index < 0:
                if not modifiers & (Qt.ShiftModifier | Qt.ControlModifier):
                    self.clear_selection()
            elif modifiers & Qt.ShiftModifier and self.anchor is not None:
                low, high = sorted((self.anchor, index))
                span = set(range(low, high + 1))
                self.set_selection(self.selected | span if modifiers & Qt.ControlModifier else span, self.anchor)
            elif modifiers & Qt.ControlModifier:
                self.set_selection(self.selected ^ {index}, index)
            else:
                self.set_selection({index}, index)
            self._dragging = index >= 0 and not modifiers & (Qt.ShiftModifier | Qt.ControlModifier)
        elif event.button() == Qt.RightButton and index >= 0 and index not in self.selected:
            self.set_selection({index}, index)  # The menu acts on the record under the cursor
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton and self.anchor is not None:
            point = self._point(event)
            index = self.row_at(point)
            if index >= 0:
                low, high = sorted((self.anchor, index))
                if self.selected != set(range(low, high + 1)):
                    self.set_selection(range(low, high + 1), self.anchor)
            if point.y() < 0 or point.y() > self.viewport().height():  # Keep scrolling past an edge
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() + (-20 if point.y() < 0 else 20))
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        self.menu_requested.emit(event.globalPos())
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in SCROLL_KEYS:  # Only scrolling keys are the view's; the window has the shortcuts
            QtWidgets.QTextEdit.keyPressEvent(self, event)
        else:
            event.ignore()

    def paintEvent(self, event):
        document = self.document()
        offset = QtCore.QPointF(0, -self.verticalScrollBar().value())
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if self.selected:  # One rounded band per run of selected lines, the same room above and below the text
            painter.setBrush(self.selection_color)
            run = None
            for number in range(document.blockCount() + 1):
                chosen = number < document.blockCount() and self.rows.get(number, -1) in self.selected
                if chosen:
                    run = (run[0] if run else number, number)
                elif run is not None:
                    top = band_span(document, run[0], self.cap_height)[0] + offset.y()
                    bottom = band_span(document, run[1], self.cap_height)[1] + offset.y()
                    painter.drawRoundedRect(QtCore.QRectF(px(4), top, self.viewport().width() - px(8), bottom - top),
                                            px(6), px(6))
                    run = None
        paint_pills(self, painter, offset)
        painter.end()
        QtWidgets.QTextEdit.paintEvent(self, event)


class LogDialog(ToolDialog):
    FILTERS = (("all", "All", "Every record"), ("warnings", "Warnings", "Warnings and errors"),
               ("errors", "Errors", "Errors only"))

    def __init__(self, controller, parent):
        # Modeless: the packager stays usable while the log is open, and Live shows what it writes
        ToolDialog.__init__(self, controller, "{} Logs".format(DISPLAY_NAME), parent, modal=False, resizable=True)
        theme = controller.theme
        self.resize(px(900), px(520))
        self.folder = settings.user_data_dir()
        self.records, self.shown, self.days = [], [], []
        self._stamp = None
        layout = QtWidgets.QVBoxLayout(self.content)
        layout.setContentsMargins(px(14), px(14), px(14), px(12))
        layout.setSpacing(px(10))

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(10))
        self.day = controls.ComboBox()
        self.day.setToolTip("Each day of 3ds Max work has its own log file")
        self.day.setMinimumWidth(px(160))
        self.day.currentIndexChanged.connect(lambda *_: self.load(to_end=True))
        top.addWidget(self.day)
        self.level = controls.Segmented(self.FILTERS, theme, "all")
        self.level.setFixedWidth(px(260))
        self.level.changed.connect(lambda *_: self.render(to_end=True))
        top.addWidget(self.level)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Filter messages  (Ctrl+F)")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda *_: self.render(to_end=True))
        top.addWidget(self.query, 1)
        self.summary = controls.muted("", wrap=False)
        top.addWidget(self.summary)
        layout.addLayout(top)

        self.view = RecordView()
        self.view.menu_requested.connect(self.show_menu)
        self.view.selection_changed.connect(self.sync_buttons)
        self.mono_font = _monospace(pt(9.0))
        layout.addWidget(controls.boxed(self.view), 1)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(8))
        refresh = controls.Button("Refresh", theme, icon="refresh-cw", tooltip="Read the log again (F5)")
        refresh.clicked.connect(self.reload)
        self.live = Switch(theme, "Live")
        self.live.setToolTip("Show new records as they are written")
        self.copy_button = controls.Button("Copy", theme, icon="copy",
                                           tooltip="Copy the selected records, or every shown record (Ctrl+C)")
        self.copy_button.clicked.connect(self.copy_records)
        self.export_button = controls.Button("Export", theme, icon="download",
                                             tooltip="Save the shown records to a text file (Ctrl+E)")
        self.export_button.clicked.connect(self.export_records)
        folder = controls.Button("Open Folder", theme, icon="folder-open", tooltip="Open the folder with the log files")
        folder.clicked.connect(lambda: open_folder(os.path.dirname(logs.log_path(self.folder))))
        self.clear_button = controls.Button("Clear Logs", theme, icon="trash-2", variant="danger",
                                            tooltip="Delete the log files of every day")
        self.clear_button.clicked.connect(self.clear_logs)
        close = controls.Button("Close", theme)
        close.clicked.connect(self.close)
        for widget in (refresh, self.live):
            row.addWidget(widget)
        row.addStretch(1)
        for widget in (self.copy_button, self.export_button, folder, self.clear_button, close):
            row.addWidget(widget)
        layout.addLayout(row)

        self.flash_timer = QtCore.QTimer(self)  # "Copied" / "Exported" on a button for 2 s
        self.flash_timer.setSingleShot(True)
        self.flash_timer.setInterval(2000)
        self.flash_timer.timeout.connect(self._end_flash)
        self._flashing = None
        self.live_timer = QtCore.QTimer(self)
        self.live_timer.setInterval(2000)
        self.live_timer.timeout.connect(self._poll)
        self.live.toggled.connect(lambda on: self.live_timer.start() if on else self.live_timer.stop())
        theme.subscribe(self._on_theme)
        self._list_days(select_newest=True)  # A fresh open shows today
        self.load(to_end=True)

    # ---- data --------------------------------------------------------------------------------------------------
    @staticmethod
    def _stamp_of(path):
        try:
            status = os.stat(path)
        except OSError:
            return None
        return status.st_size, status.st_mtime

    def _list_days(self, select_newest):
        """Fill the day picker; keeps the chosen day unless `select_newest`."""
        self.days = logs.log_days(self.folder)
        current = None if select_newest else self.day.currentData()
        self.day.blockSignals(True)
        self.day.clear()
        for day in self.days:
            self.day.addItem(logs.day_label(day.date), day.file_path)
        if not self.days:
            self.day.addItem("No logs yet", "")
        self.day.setCurrentIndex(max(0, self.day.findData(current)) if current else 0)
        self.day.blockSignals(False)
        self.day.setEnabled(bool(self.days))

    def load(self, to_end):
        path = self.day.currentData() or ""
        self.records = logs.parse_records(logs.read_text(path)) if path else []
        self._stamp = self._stamp_of(path) if path else None
        self.render(to_end)

    def reload(self):
        """Refresh / F5: the list of days and the chosen day read again."""
        self._list_days(select_newest=False)
        self.load(to_end=False)

    def _poll(self):
        """Live: a new day file or new lines in the shown one are read again."""
        if not self.isVisible():
            return
        if [day.file_path for day in logs.log_days(self.folder)] != [day.file_path for day in self.days]:
            newest = bool(self.days) and self.day.currentData() == self.days[0].file_path
            self._list_days(select_newest=newest)
            self.load(to_end=False)
        elif self.day.currentData() and self._stamp_of(self.day.currentData()) != self._stamp:
            self.load(to_end=False)

    def _on_theme(self, _colors):
        self.render(to_end=False)

    # ---- view --------------------------------------------------------------------------------------------------
    def _shown(self):
        levels = logs.FILTERS.get(self.level.value() or "all", logs.FILTERS["all"])
        needle = self.query.text().strip().lower()
        result = []
        for record in self.records:
            if record["level"] not in levels:
                continue
            if needle and needle not in " ".join([record["source"], record["message"]] + record["extra"]).lower():
                continue
            result.append(record)
        return result

    def render(self, to_end):
        colors = self.controller.theme.colors
        view = self.view
        bar = view.verticalScrollBar()
        at_end = to_end or bar.value() >= bar.maximum() - 4
        position = bar.value()
        chosen = set(id(self.shown[i]) for i in view.selected if i < len(self.shown))
        shown = self._shown()[-SHOWN_LIMIT:]
        self.summary.setText(logs.summary_text(shown) if self.records else "")
        view.setUpdatesEnabled(False)
        view.clear()
        view.rows, view.pills = {}, {}
        accent = QtGui.QColor(colors["accent"])
        accent.setAlphaF(0.22)
        view.selection_color = accent
        bold = QtGui.QFont(self.mono_font)
        bold.setBold(True)
        view.cap_height = QtGui.QFontMetricsF(bold).capHeight()
        view.pill_font = bold
        cursor = QtGui.QTextCursor(view.document())
        hanging = QtGui.QFontMetricsF(self.mono_font).horizontalAdvance(" ") * MESSAGE_COLUMN
        block = QtGui.QTextBlockFormat()
        block.setLineHeight(LINE_HEIGHT, 1)
        block.setLeftMargin(hanging)  # Long lines continue under the message, not under the time
        block.setTextIndent(-hanging)
        cursor.beginEditBlock()
        cursor.setBlockFormat(block)
        first = [True]

        def run(text, role, bold=False, pill=None):
            character = QtGui.QTextCharFormat()
            character.setFont(self.mono_font)
            character.setForeground(QtGui.QColor(colors[role]))
            if bold:
                character.setFontWeight(QtGui.QFont.Bold)
            if pill is not None:  # (colour, label): the label is painted in the middle of the pill
                view.pills[cursor.blockNumber()] = (cursor.positionInBlock(), len(text), pill[0], pill[1],
                                                    QtGui.QColor(colors[role]))
            cursor.insertText(text, character)
            first[0] = False

        def line(record_index=-1):
            if record_index >= 0:
                view.rows[cursor.blockNumber()] = record_index
            cursor.insertBlock(block)

        if not shown:
            if not self.days:
                run("Nothing has been logged yet.", "muted_text")
            elif not self.records:
                run("This day's log is empty.", "muted_text")
            else:
                run("No records match the filter.", "muted_text")
        for index, record in enumerate(shown):
            if record["message"].startswith(logs.SESSION_PREFIX):
                if not first[0] and index:
                    line()  # A gap before every session
                run("Session started {}  ·  {}".format(record["time"], record["message"][len(logs.SESSION_PREFIX):]
                                                      .strip()), "accent", bold=True)
                view.rows[cursor.blockNumber()] = index
                line()
                continue
            role = LEVEL_ROLES.get(record["level"], "log_info")
            pill = QtGui.QColor(colors[role + "_background"])
            if record["level"] in ("WARNING", "ERROR", "CRITICAL"):
                message_role = role
            elif record["message"].startswith(logs.SUCCESS_PREFIXES):
                message_role = "log_success"
            else:
                message_role = "field_text"
            source = record["source"]
            source = source if len(source) <= SOURCE_WIDTH else source[:SOURCE_WIDTH - 1] + "…"
            view.rows[cursor.blockNumber()] = index
            run(record["time"], "muted_text")
            run("  ", "field_text")
            label = "WARN" if record["level"] == "WARNING" else record["level"][:7]
            run(" " * 9, role, True, (pill, label))
            run("  ", "field_text")
            run(source.ljust(SOURCE_WIDTH), "log_system")
            run("  " + record["message"], message_role)
            for extra in record["extra"]:
                line(index)
                run(" " * MESSAGE_COLUMN + extra, message_role if message_role != "field_text" else "muted_text")
            line(index)
        cursor.endEditBlock()
        self.shown = shown
        view.count = len(shown)
        view.set_selection([i for i, record in enumerate(shown) if id(record) in chosen])
        view.setUpdatesEnabled(True)
        if at_end:
            QtCore.QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))
        else:
            bar.setValue(min(position, bar.maximum()))
        self.sync_buttons()

    def sync_buttons(self):
        self.copy_button.setEnabled(bool(self.shown))
        self.export_button.setEnabled(bool(self.shown))
        self.clear_button.setEnabled(bool(logs.log_files(self.folder)))

    # ---- actions -----------------------------------------------------------------------------------------------
    def _selected_records(self):
        if self.view.selected:
            return [self.shown[index] for index in sorted(self.view.selected)]
        return self.shown

    def copy_records(self):
        records = self._selected_records()
        if records:
            QtWidgets.QApplication.clipboard().setText("\n".join(logs.record_text(r) for r in records))
            self._flash(self.copy_button, "Copied")

    def copy_diagnostics(self):
        QtWidgets.QApplication.clipboard().setText(diagnostics() + "\n\n" + logs.tail(self.folder, 64 * 1024))
        self._flash(self.copy_button, "Copied")

    def export_records(self):
        if not self.shown:
            return
        documents = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
        target, _choice = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Log", os.path.join(documents, "MaxPkgPackager.log"), "Log files (*.log);;Text files (*.txt)")
        if not target:
            return
        try:
            with open(target, "w", encoding="utf-8") as stream:
                stream.write("\n".join(logs.record_text(r) for r in self.shown) + "\n")
        except OSError:
            self._flash(self.export_button, "Not saved")
            return
        self._flash(self.export_button, "Exported")

    def clear_logs(self):
        """Delete the log files of every day after a confirmation; the view then shows the empty state."""
        days = logs.log_days(self.folder)
        files = logs.log_files(self.folder)
        if not files:
            return
        size = logs.size_text(sum(os.path.getsize(path) for path in files if os.path.isfile(path)))
        if len(days) > 1:
            text = "The log files of {} days ({}) will be deleted. This cannot be undone.".format(len(days), size)
        else:
            text = "The log file ({}) will be deleted. This cannot be undone.".format(size)
        if not ask(self.controller, self, "Clear Logs", "Clear all logs?", text, "Clear Logs", "Cancel"):
            return
        _removed, kept, _freed = logs.clear_logs(self.folder)
        self.view.clear_selection()
        self._list_days(select_newest=True)
        self.load(to_end=True)
        if kept:
            self.summary.setText("{} file{} in use, kept".format(kept, "" if kept == 1 else "s"))

    def go_to_latest(self):
        """The newest day, scrolled to its last record."""
        if self.days and self.day.currentData() != self.days[0].file_path:
            self.day.setCurrentIndex(0)  # Loads the newest day
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def show_menu(self, global_pos):
        theme = self.controller.theme
        menu = controls.Menu(theme, self)
        selected = bool(self.view.selected)
        menu.add_item("Search / Filter  (Ctrl+F)", "search", lambda: (self.query.setFocus(), self.query.selectAll()))
        menu.add_item("Copy Selected  (Ctrl+C)" if selected else "Copy All Shown  (Ctrl+C)", "copy", self.copy_records,
                      enabled=bool(self.shown))
        menu.add_item("Select All  (Ctrl+A)", "check", self.view.select_all, enabled=bool(self.shown))
        menu.add_item("Export…  (Ctrl+E)", "download", self.export_records, enabled=bool(self.shown))
        menu.add_item("Copy Diagnostics", "info", self.copy_diagnostics)
        menu.add_item("Go to Latest", "chevron-down", self.go_to_latest)
        menu.addSeparator()
        menu.add_item("Clear Logs…", "trash-2", self.clear_logs, danger=True, enabled=self.clear_button.isEnabled())
        menu.popup_at(global_pos)

    def keyPressEvent(self, event):
        key = event.key()
        control = bool(event.modifiers() & Qt.ControlModifier)
        if key == Qt.Key_Escape:
            if self.view.selected:
                self.view.clear_selection()
            else:
                self.close()
        elif key == Qt.Key_F5:
            self.reload()
        elif control and key == Qt.Key_F:
            self.query.setFocus()
            self.query.selectAll()
        elif control and key == Qt.Key_C:
            self.copy_records()
        elif control and key == Qt.Key_A:
            self.view.select_all()
        elif control and key == Qt.Key_E:
            self.export_records()
        else:
            ToolDialog.keyPressEvent(self, event)

    def _flash(self, button, text):
        self._end_flash()
        self._flashing = (button, button.text())
        button.setText(text)
        self.flash_timer.start()

    def _end_flash(self):
        if self._flashing is not None:
            self._flashing[0].setText(self._flashing[1])
            self._flashing = None

    def dispose(self):
        self.live_timer.stop()
        self.controller.theme.unsubscribe(self._on_theme)
        ToolDialog.dispose(self)
