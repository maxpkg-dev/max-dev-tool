"""The packager window, kept small: a tab row, one page, and a bottom strip with the status and the Build button."""

import logging
import os

from .. import DISPLAY_NAME, __version__
from ..core import build as core_build
from ..core import validate
from ..qt_compat import QShortcut, QtCore, QtGui, QtWidgets, Qt, repolish, work_area
from ..ui_scale import px
from . import controls
from . import pages as pages_module
from .pages import FilesPage, InfoPage, ReleasePage, SetupPage, scroll_page
from .statuslog import StatusLog
from .tool_window import ToolWindow

_log = logging.getLogger("maxpkgpackager.build")

TABS = (("info", "1  Info", InfoPage), ("setup", "2  Setup", SetupPage), ("files", "3  Files", FilesPage),
        ("release", "4  Release", ReleasePage))
UPLOAD_URL = "https://maxpkg.dev/dashboard/packages"
UPLOAD_HINT = ('Next: test it in 3ds Max, then drop the .mzp into the upload area on '
               '<a href="{url}" style="color:{color}; font-weight:bold">maxpkg.dev</a>.')  # The banner's green


class MainWindow(ToolWindow):
    def __init__(self, controller, parent=None):
        ToolWindow.__init__(self, controller, parent)
        self.model = controller.model
        self.theme = controller.theme
        self.project = self.model.project
        self.build_result = None
        # Compact layout: one tab row on top, the page below, Build and the status in the bottom strip.
        self.tabs = controls.Segmented(tuple((key, title, "") for key, title, _page in TABS), self.theme, "info")
        self.tabs.changed.connect(self.on_tab)
        self.body.addWidget(self.tabs)
        self.stack = QtWidgets.QStackedWidget()
        self.pages = {}
        for key, _title, page_class in TABS:
            page = page_class(self)
            self.pages[key] = page
            self.stack.addWidget(scroll_page(page))
        self.body.addWidget(self.stack, 1)

        self.result_box = QtWidgets.QFrame()
        self.result_box.setObjectName("toolSuccess")  # Green: the package was built
        result = QtWidgets.QVBoxLayout(self.result_box)
        result.setContentsMargins(px(10), px(4), px(6), px(8))
        result.setSpacing(px(2))
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(px(6))
        self.result_title = controls.ElidedLabel("")
        self.result_title.setObjectName("toolSuccessTitle")
        head.addWidget(self.result_title, 1)
        for icon, tip, slot in (("folder-open", "Show the package in its folder", self.on_show_result),
                                ("copy", "Copy the package path", self.on_copy_result),
                                ("x", "Dismiss", self.result_box.hide)):
            button = controls.Button("", self.theme, icon=icon, variant="ghost", tooltip=tip, icon_role="log_success")
            button.clicked.connect(slot)
            head.addWidget(button)
        result.addLayout(head)
        upload = QtWidgets.QLabel()  # How to publish, as in the How to Upload part of version 1.x
        upload.setObjectName("toolSuccessText")
        self._upload_hint = upload
        self._paint_upload_hint(self.theme.colors)
        self.theme.subscribe(self._paint_upload_hint)
        upload.setWordWrap(True)
        upload.setTextFormat(Qt.RichText)
        upload.setOpenExternalLinks(True)
        upload.setToolTip(UPLOAD_URL)
        result.addWidget(upload)
        self.result_box.hide()
        self.body.addWidget(self.result_box)

        self.log = StatusLog(self.theme)
        self.log.setFixedHeight(px(132))  # About five message rows
        self.log.tab_requested.connect(self.go_to_field)
        self.log.hide()
        self.log_wanted = False  # Opens on a click on the status pill and when a Build finds a problem.
        self.showing_build = False  # The log shows the last build until the next edit
        self.body.addWidget(self.log)

        self.state_pill = controls.Pill(self.theme, "Checking…", "neutral")
        self.state_pill.set_clickable(True)
        self.state_pill.clicked.connect(self.toggle_log)
        self.status_row.insertWidget(0, self.state_pill)
        self.build_button = controls.Button("Build", self.theme, icon="box", variant="primary",
                                            tooltip="Validate and build the .mzp (Ctrl+B)")
        self.build_button.clicked.connect(self.on_build)
        self.status_row.addWidget(self.build_button)

        self.update_pill = controls.Pill(self.theme, "", "info")
        self.update_pill.set_clickable(True)
        self.update_pill.clicked.connect(self.on_update_clicked)
        self.update_pill.hide()
        self.status_row.insertWidget(0, self.update_pill)

        self._build_shortcut = QShortcut(QtGui.QKeySequence("Ctrl+B"), self)
        self._build_shortcut.activated.connect(self.on_build)
        self.model.validated.connect(self.on_validated)
        self.model.structure_changed.connect(self.refresh_pages)
        self.model.save_failed.connect(lambda error: self.set_status("Project not saved: " + error))
        controls.unify_heights(self)  # Same height for every field, dropdown and button
        self.error_hints = controls.ErrorHints(self.theme, self)
        for widget in set(self.field_widgets().values()):
            self.error_hints.watch(widget)
        self.on_tab(self.project.last_tab if self.project.last_tab in self.pages else "info")
        self.refresh_title()
        self.model.validate_now()
        self.status_label.hide()  # Messages appear as toasts, never as small text in the bottom strip
        self.status_row.insertStretch(2, 1)  # Pills on the left; Settings, Logs, About and Build on the right
        self.toast = controls.Toast(self.theme, self.full_view)

    ERROR_WORDS = ("could not", "invalid", "not a valid", "does not", "failed", "choose", "allows only",
                   "already exists", "skipped", "not saved", "fix the")

    def set_status(self, text, level=None):
        """Show a message about the last action as a toast. The kind is guessed from the words when not given."""
        if not text:
            return
        if level is None:
            lowered = text.lower()
            level = "error" if any(word in lowered for word in self.ERROR_WORDS) else "success"
        self.toast.show_message(text, level)

    # ---- context for the pages ---------------------------------------------------------------------------------
    def status(self, text, level=None):
        self.set_status(text, level)

    def resizeEvent(self, event):
        ToolWindow.resizeEvent(self, event)
        if self.isVisible():
            self.remember_geometry()
        if self.toast.items:
            self.toast.place()

    @staticmethod
    def _has_icon(name):
        from .. import resources
        return os.path.isfile(resources.icon_path(name))

    # ---- navigation ------------------------------------------------------------------------------------------------
    def on_tab(self, key):
        if key not in self.pages:
            return
        self.stack.setCurrentIndex([tab for tab, _t, _p in TABS].index(key))
        self.tabs.set_value(key)
        if self.project.last_tab != key:
            self.project.last_tab = key
            self.model.touch()

    def go_to(self, key):
        self.on_tab(key)

    def refresh_pages(self):
        for page in self.pages.values():
            page.refresh()
        self.refresh_title()

    def refresh_title(self):
        name = self.project.package_name.strip() or "New package"
        # The title bar shows only the tool's name; the package and the folder are in the system title (taskbar).
        self.setWindowTitle("{} - {} {} - {}".format(DISPLAY_NAME, name, self.project.version, self.project.root))

    # ---- validation ------------------------------------------------------------------------------------------------
    def on_validated(self, issues):
        errors = [issue for issue in issues if issue.level == validate.ERROR]
        counts = {}
        for issue in errors:
            counts[issue.tab] = counts.get(issue.tab, 0) + 1
        for key, title, _page in TABS:
            count = counts.get(key, 0)
            self.tabs.buttons[key].setText("{} ({})".format(title, count) if count else title)
        if errors:
            self.state_pill.set_status("{} to fix".format(len(errors)), "error", "Click to show or hide the list")
        else:
            self.state_pill.set_status("Ready", "success", "Everything required is filled in")
        self.mark_invalid_fields(errors)
        if not self.showing_build:
            self.log.set_entries(self.validation_entries(issues))
        self.set_log_visible(self.log_wanted)
        self.refresh_title()
        self.controller.remember_author()

    def validation_entries(self, issues):
        """The state as statuses only: the errors and warnings, or one green line when nothing blocks a build. The
        details of a build are in the Logs window, never here."""
        entries = [(issue.level, issue.message, "{}|{}".format(issue.tab, issue.field) if issue.tab else "",
                    issue.where()) for issue in issues if issue.level in (validate.ERROR, validate.WARNING)]
        if not any(level == validate.ERROR for level, _m, _t, _p in entries):
            entries.append(("OK", "Ready to build", "", ""))
        return entries

    def field_widgets(self):
        """Validation field name -> the widget that shows it (for the red outline)."""
        info, setup, files, release = (self.pages[key] for key in ("info", "setup", "files", "release"))
        return {
            ("info", "Package Name"): info.name, ("info", "Button Name"): info.button,
            ("info", "GUID"): info.guid, ("info", "Description"): info.description_box,
            ("info", "Developer Name"): info.developer, ("info", "License"): info.license,
            ("info", "License URL"): info.license_url, ("info", "Documentation URL"): info.documentation,
            ("info", "Homepage URL"): info.homepage, ("info", "Purchase URL"): info.purchase,
            ("setup", "Custom Install Script"): setup.custom["custom_install"][0],
            ("setup", "Custom Uninstall Script"): setup.custom["custom_uninstall"][0],
            ("files", "Output Folder"): files.output, ("files", "SVG Icon"): files.icon_edit,
            ("files", "Files"): files.files_box, ("files", "Entry File"): files.entry,
            ("files", "Compile Entry"): files.entry, ("files", "Build Path Remap"): files.rules_box,
            ("files", "Extra Macros"): files.macros_box, ("release", "Channel"): release.channel,
            ("release", "Release Date"): release.date, ("release", "Min 3ds Max"): release.min_max,
            ("release", "Changelog"): release.editor.items_box,
        }

    def mark_invalid_fields(self, errors):
        """Red outline on every field with an error; the tooltip says what is wrong. Cleared as soon as it is fixed."""
        widgets = self.field_widgets()
        messages = {}  # One widget can show several checks (Entry File and Compile Entry): collect them per widget
        for widget in widgets.values():
            messages.setdefault(id(widget), (widget, []))
        for issue in errors:
            widget = widgets.get((issue.tab, issue.field))
            if widget is not None:
                messages[id(widget)][1].append(issue.message)
        for widget, reasons in messages.values():
            message = "\n".join(reasons)
            invalid = "true" if message else "false"
            if widget.property("invalid") != invalid:
                widget.setProperty("invalid", invalid)
                repolish(widget)
            if (widget.property("invalidMessage") or "") != message:
                widget.setProperty("invalidMessage", message)  # Shown by the red bubble on hover (ErrorHints)
                self.error_hints.refresh(widget)

    def go_to_field(self, target):
        """A click on a log line: open its tab, scroll to the field, focus it and flash it so it is found at once."""
        tab, _bar, field = target.partition("|")
        self.go_to(tab)
        widget = self.field_widgets().get((tab, field))
        if widget is None:
            return
        area = self.stack.currentWidget()
        group = widget.parentWidget()
        while group is not None and not isinstance(group, pages_module.Collapsible) and group is not area:
            group = group.parentWidget()
        if isinstance(group, pages_module.Collapsible):
            group.header.setChecked(True)  # A field inside a closed group: open it first
        QtWidgets.QApplication.processEvents()
        if isinstance(area, QtWidgets.QScrollArea):
            area.ensureWidgetVisible(widget, px(20), px(40))
        widget.setFocus(Qt.OtherFocusReason)
        controls.Flash(widget, self.theme.colors["log_error"])

    def toggle_log(self):
        self.log_wanted = not self.log_wanted
        self.set_log_visible(self.log_wanted)

    def header_bottom(self):
        """The packager's header ends where the first panel starts, just below the tabs."""
        return self.tabs.mapTo(self, QtCore.QPoint(0, self.tabs.height())).y() + self.body.spacing()

    def set_log_visible(self, on):
        """Show or hide the log inside the window. The window keeps its size: the log takes its room from the page
        (which scrolls if it must). The window is only ever resized by the user."""
        if self.log.isVisible() != bool(on):
            self.log.setVisible(bool(on))

    def resize_height(self, height):
        """Set the window height within the work area of its screen, keeping the top edge where it is."""
        area = work_area(self.frameGeometry().center())
        if area is not None:
            height = min(height, area.height() - px(8))
            overflow = self.y() + height - (area.bottom() - px(4))
            if overflow > 0:
                self.move(self.x(), max(area.top(), self.y() - overflow))
        self.resize(self.width(), max(self.minimumHeight(), int(height)))

    def fit_height(self):
        """Tall enough for the tallest page, so no page needs a scroll bar (as far as the screen allows)."""
        if self.isMaximized():
            return
        if getattr(self, "_fitting_first", False) and self.geometry_restored:
            return  # The size the user left the window at comes back as it was
        tallest = max(page.sizeHint().height() for page in self.pages.values())
        room = self.stack.height()
        if tallest > room:
            self.resize_height(self.height() + (tallest - room) + px(6))

    def showEvent(self, event):
        ToolWindow.showEvent(self, event)
        controls.unify_heights(self)  # Again after polish: style sheet sizes are applied when widgets first show
        if not getattr(self, "_fitted", False):
            self._fitted = True
            self._fitting_first = True
            QtCore.QTimer.singleShot(0, self._first_fit)

    def _first_fit(self):
        self.fit_min_width()
        self.fit_height()
        self._fitting_first = False

    def fit_min_width(self):
        """Never narrower than the widest page needs: the pages do not scroll sideways, so a page wider than its room
        was cut off on the right. Rows that can stack in a narrow window (Reflow), so this rarely raises the minimum;
        it is the guard for a large interface size or a long text."""
        if self._mini is not None or self.isMaximized():
            return
        area = self.stack.currentWidget()
        chrome = self.width() - area.viewport().width()  # Window edges, margins and a shown scroll bar
        widest = max(page.minimumSizeHint().width() for page in self.pages.values())
        self.setMinimumWidth(max(self.minimumWidth(), widest + chrome))

    def remember_geometry(self):
        """Position and size are saved shortly after every move or resize, not only on close: they survive a
        3ds Max that is closed with the packager still open."""
        if not hasattr(self, "_geometry_timer"):
            self._geometry_timer = QtCore.QTimer(self)
            self._geometry_timer.setSingleShot(True)
            self._geometry_timer.setInterval(600)
            self._geometry_timer.timeout.connect(self._save_geometry)
        self._geometry_timer.start()

    def _save_geometry(self):
        if self.isVisible() and getattr(self, "_mini", None) is None and self.controller.running:
            self.controller.set_preference("window_geometry", self.geometry_state())

    def moveEvent(self, event):
        ToolWindow.moveEvent(self, event)
        if self.isVisible():
            self.remember_geometry()

    # ---- build -----------------------------------------------------------------------------------------------------
    def on_build(self):
        self.showing_build = False
        self.model.validate_now()
        if self.model.errors():
            self.log_wanted = True
            self.set_log_visible(True)  # The log lists the problems: no toast on top of it
            first = self.model.errors()[0]
            self.go_to_field("{}|{}".format(first.tab, first.field))  # Shows the first field to fix
            return
        self.model.save_now()
        self.build_button.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = core_build.build(self.project, DISPLAY_NAME, __version__,
                                      log=lambda level, text: _log.log(logging.ERROR if level == "ERROR" else logging.INFO, text))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.build_button.setEnabled(True)
        self.show_build_result(result)

    def show_build_result(self, result):
        """The build's status in the mini log: its errors and warnings, or one green "Package built" (the steps and
        the path are in the Logs window). No toast either way: a good build shows the green banner, a failed one
        opens the log with its errors."""
        self.build_result = result
        self.showing_build = True  # The status of this build stays in the log until the next edit
        entries = [(level, text, "", "") for level, text in result.messages
                   if level in (validate.ERROR, validate.WARNING)]
        if result.ok:
            entries.append(("OK", "Package built", "", ""))
        self.log.set_entries(entries)
        if not result.ok:  # Opens only for a problem; a good build is told by the banner and the Ready pill
            self.log_wanted = True
            self.set_log_visible(True)
        self.toast.clear()  # Nothing left over on top of the banner or the log
        if result.ok:
            self.result_title.setText("Built {} · {:.1f} KB".format(os.path.basename(result.output_file), result.size / 1024.0))
            self.result_title.setToolTip(result.output_file)
            self.result_box.show()
        else:
            self.result_box.hide()

    def _paint_upload_hint(self, colors):
        self._upload_hint.setText(UPLOAD_HINT.format(url=UPLOAD_URL, color=colors["log_success"]))

    def on_copy_result(self):
        if self.build_result:
            QtWidgets.QApplication.clipboard().setText(self.build_result.output_file)
            self.set_status("Package path copied.")

    def on_show_result(self):
        if self.build_result and self.build_result.output_file:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(self.build_result.output_file)))

    # ---- updates ---------------------------------------------------------------------------------------------------
    def on_update_result(self, result, automatic):
        version = result.get("version")
        if result.get("error") or not version:
            return
        if result.get("installed"):
            self.update_pill.set_status("Version {} installed · restart".format(version), "success",
                                        "Click to restart {} with the new version".format(DISPLAY_NAME))
            self._update_action = "restart"
        else:
            self.update_pill.set_status("Version {} available".format(version), "info",
                                        "Update {} when installed from the MaxPkg launcher".format(DISPLAY_NAME))
            self._update_action = None
        self.update_pill.show()

    def on_update_clicked(self):
        if getattr(self, "_update_action", None) == "restart" and self.controller.can_reopen():
            self.model.save_now()
            self.controller.reopen()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self.on_build()
            return
        ToolWindow.keyPressEvent(self, event)
