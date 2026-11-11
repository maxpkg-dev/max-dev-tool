"""Settings, Logs and About. All compose the shared controls and the shared stylesheet."""

import os
import platform
import sys

from .. import DEVELOPER, DISPLAY_NAME, DONATE_URL, LINKS, SUBTITLE, __version__, logs, settings, themes, ui_scale
from ..qt_compat import (BINDING, QtCore, QtGui, QtWidgets, Qt, exec_dialog, inherit_fonts, qt_version,
                         round_window_corners, work_area)
from ..ui_scale import pt, px
from . import controls
from .switch import Switch

DESCRIPTION = ("Builds clean MaxPkg-compatible .mzp packages for 3ds Max from your script project: package information, files, "
               "release notes and a verified archive ready to upload to maxpkg.dev.")
DISCLAIMER = ""  # A warning block in About (third-party data, unofficial sources); "" leaves it out.
USE_STEPS = (  # Help markup (controls.help_html): **bold**, `code`, [label](address). Shared with the installer.
    "Run `maxpkg-packager.ms` from the root folder of your script project: drag it into a viewport or use "
    "**Scripting › Run Script**.",
    "Fill in **Info**, add your files, choose the entry file and write the changelog.",
    "Press **Build**. The `.mzp` appears in `max-package\\dist`: test it in 3ds Max.",
    "Open [maxpkg.dev › Packages](https://maxpkg.dev/dashboard/packages) and drop the `.mzp` into the upload area.",
)
USE_NOTE = ("The installer (`MaxPkgPackager.mzp`) puts `maxpkg-packager.ms` into a project; you can also copy the file "
            "yourself. Everything the packager keeps for a project is in its `max-package` folder.")
CREDITS = "Lucide icons (ISC)."


class Veil(QtWidgets.QWidget):
    """Translucent cover over a tool window while a modal tool dialog is open."""

    def __init__(self, target, theme):
        QtWidgets.QWidget.__init__(self, target)
        self.target = target
        self.theme = theme
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        target.installEventFilter(self)
        self.setGeometry(target.rect())
        self.raise_()
        self.show()

    def eventFilter(self, watched, event):
        if watched is self.target and event.type() == QtCore.QEvent.Resize:
            self.setGeometry(watched.rect())
        return False

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        shade = QtGui.QColor(self.theme.color("recessed"))
        shade.setAlpha(150)
        painter.fillRect(self.rect(), shade)
        painter.end()

    def dispose(self):
        self.target.removeEventFilter(self)
        self.hide()
        self.deleteLater()


class ToolDialog(QtWidgets.QDialog):
    """Base for every window of the tool besides the main one, in the main window's own style: no Windows frame, a
    title bar with the tool's icon, the title and a round close button (red on hover), the dark header shade and
    rounded corners. Subclasses build into `self.content`. A modal dialog veils the owner window while visible; a
    modeless one (Logs) leaves the owner usable, so it can be watched while working. `resizable` adds a size grip."""

    HEADER_SHADE = 0.7  # As the main window (ToolWindow)

    def __init__(self, controller, title, parent, modal=True, resizable=False):
        QtWidgets.QDialog.__init__(self, parent)
        self.controller = controller
        self.modal = modal
        theme = controller.theme
        self.setObjectName("toolDialog")
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal if modal else Qt.NonModal)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.veil = None
        self._drag = None
        frame = QtWidgets.QVBoxLayout(self)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setSpacing(0)
        self.title_bar = QtWidgets.QFrame()
        self.title_bar.setObjectName("toolTitleBar")
        bar = QtWidgets.QHBoxLayout(self.title_bar)
        bar.setContentsMargins(px(12), px(8), px(8), px(6))  # Where the main window's title bar puts them
        bar.setSpacing(px(4))
        bar.addWidget(controls.BrandIcon(18))
        bar.addSpacing(px(3))
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("toolWindowTitle")
        bar.addWidget(self.title_label)
        bar.addStretch(1)
        close = controls.WindowButton("x", theme, "Close", close=True)
        close.clicked.connect(self.close)
        bar.addWidget(close)
        self.title_bar.installEventFilter(self)  # Dragging it moves the window
        frame.addWidget(self.title_bar)
        self.content = QtWidgets.QWidget()
        frame.addWidget(self.content, 1)
        self.grip = None
        if resizable:
            self.grip = QtWidgets.QSizeGrip(self)
            self.grip.setFixedSize(px(16), px(16))
        theme.register(self)

    # Moving by the title bar --------------------------------------------------------------------------
    @staticmethod
    def _global(event):
        position = getattr(event, "globalPosition", None)
        return position().toPoint() if position else event.globalPos()

    def eventFilter(self, watched, event):
        if watched is self.title_bar:
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                handle = self.windowHandle()
                if handle is not None and hasattr(handle, "startSystemMove") and handle.startSystemMove():
                    return True  # Windows moves it (with snapping), Qt 5.15 and newer
                self._drag = self._global(event) - self.frameGeometry().topLeft()
                return True
            if kind == QtCore.QEvent.MouseMove and self._drag is not None:
                self.move(self._global(event) - self._drag)
                return True
            if kind == QtCore.QEvent.MouseButtonRelease:
                self._drag = None
        return QtWidgets.QDialog.eventFilter(self, watched, event)

    # Painting, showing ----------------------------------------------------------------------------------
    def paintEvent(self, event):
        """The dark shade behind the header, as in the main window."""
        QtWidgets.QDialog.paintEvent(self, event)
        bottom = self.title_bar.geometry().bottom() + px(6)
        shade = QtGui.QLinearGradient(0, 0, 0, bottom)
        dark = QtGui.QColor(0, 0, 0)
        dark.setAlphaF(self.HEADER_SHADE)
        shade.setColorAt(0.0, dark)
        shade.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(self)
        painter.fillRect(QtCore.QRect(0, 0, self.width(), bottom), shade)
        painter.end()

    def resizeEvent(self, event):
        QtWidgets.QDialog.resizeEvent(self, event)
        if self.grip is not None:
            self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())
            self.grip.raise_()

    def showEvent(self, event):
        QtWidgets.QDialog.showEvent(self, event)
        inherit_fonts(self)  # Interface size for what the dialog built after its font was set.
        controls.unify_heights(self)
        round_window_corners(self, self.controller.theme.colors.get("border"))  # Windows 11, as the main window
        if self.modal and self.veil is None and self.parentWidget() is not None:
            self.veil = Veil(self.parentWidget(), self.controller.theme)

    def hideEvent(self, event):
        self._drop_veil()
        QtWidgets.QDialog.hideEvent(self, event)

    def _drop_veil(self):
        if self.veil is not None:
            self.veil.dispose()
            self.veil = None

    def dispose(self):
        self._drop_veil()
        self.controller.theme.unregister(self)
        self.hide()
        self.deleteLater()


def settings_group(layout, title):
    """A titled block of the Settings window (grouped, named controls). Returns its form layout."""
    frame = QtWidgets.QFrame()
    frame.setObjectName("toolSettingsGroup")
    inner = QtWidgets.QVBoxLayout(frame)
    inner.setContentsMargins(px(12), px(8), px(12), px(10))
    inner.setSpacing(px(6))
    caption = QtWidgets.QLabel(title)
    caption.setObjectName("toolGroupTitle")
    inner.addWidget(caption)
    form = QtWidgets.QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(px(12))
    form.setVerticalSpacing(px(6))
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    inner.addLayout(form)
    layout.addWidget(frame)
    return form


def settings_page(tabs, title):
    page = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(page)
    layout.setContentsMargins(px(10), px(12), px(10), px(10))
    layout.setSpacing(px(10))
    tabs.addTab(page, title)
    return layout


class SettingsDialog(ToolDialog):
    """Tabs; the General tab starts with Appearance (theme, interface size). The tool adds its own groups below and
    its own tabs after it."""

    def __init__(self, controller, parent):
        ToolDialog.__init__(self, controller, "{} Settings".format(DISPLAY_NAME), parent)
        theme = controller.theme
        self.resize(px(400), px(330))
        layout = QtWidgets.QVBoxLayout(self.content)
        layout.setContentsMargins(px(16), px(16), px(16), px(16))
        layout.setSpacing(px(8))
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(False)
        layout.addWidget(tabs, 1)
        general = settings_page(tabs, "General")

        form = settings_group(general, "Appearance")
        self.theme_combo = controls.ComboBox()
        for theme_id, name in themes.list_themes(controller.root):
            self.theme_combo.addItem(name, theme_id)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(theme.theme_id)))
        self.theme_combo.currentIndexChanged.connect(self.on_theme_selected)
        form.addRow("Theme", self.theme_combo)
        # Interface size applies while windows are built, so on reopening.
        self.scale_combo = controls.ComboBox()
        self.scale_combo.addItem("Auto ({})".format(ui_scale.percent(ui_scale.current["auto"])), "auto")
        for value in ui_scale.CHOICES:
            self.scale_combo.addItem(ui_scale.percent(value), str(value))
        chosen = str(controller.prefs.get("ui_scale") or "auto")
        self.scale_combo.setCurrentIndex(max(0, self.scale_combo.findData(chosen)))
        self.scale_combo.setToolTip("The size of {}'s text, buttons and windows. Auto follows the screen (larger on "
                                    "2K and 4K) and Windows scaling.".format(DISPLAY_NAME))
        self.scale_combo.currentIndexChanged.connect(self.on_scale_selected)
        form.addRow("Interface size", self.scale_combo)
        note = QtWidgets.QHBoxLayout()
        note.setSpacing(px(8))
        note.addWidget(controls.muted("Applies when {} opens again.".format(DISPLAY_NAME)), 1)
        self.reopen_button = controls.Button("Reopen Now", theme, icon="refresh-cw",
                                             tooltip="Close {} and open it again with the new size".format(DISPLAY_NAME))
        self.reopen_button.clicked.connect(self.on_reopen)
        note.addWidget(self.reopen_button)
        self.scale_note_row = QtWidgets.QWidget()
        self.scale_note_row.setLayout(note)
        self.scale_note_row.hide()
        form.addRow(self.scale_note_row)
        self.theme_error = QtWidgets.QLabel("")
        self.theme_error.setObjectName("toolError")
        self.theme_error.setWordWrap(True)
        self.theme_error.hide()
        form.addRow(self.theme_error)

        form = settings_group(general, "Updates")
        self.auto_update = Switch(theme, "Check for updates automatically and install them in the background")
        self.auto_update.setCursor(Qt.PointingHandCursor)
        self.auto_update.setChecked(bool(controller.prefs.get("auto_update")))
        self.auto_update.toggled.connect(lambda on: controller.set_preference("auto_update", bool(on)))
        form.addRow(self.auto_update)
        check_row = QtWidgets.QHBoxLayout()
        check_row.setSpacing(px(8))
        self.update_button = controls.Button("Check now", theme, icon="refresh-cw")
        self.update_button.clicked.connect(self.on_check_updates)
        self.update_label = controls.muted("Version {}. A new version starts the next time {} opens.".format(
            __version__, DISPLAY_NAME), wrap=True)
        check_row.addWidget(self.update_button)
        check_row.addWidget(self.update_label, 1)
        form.addRow(check_row)
        general.addStretch(1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        close = controls.Button("Close", theme)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)

    def on_theme_selected(self, index):
        theme_id = self.theme_combo.itemData(index)
        error = self.controller.theme.select(theme_id)
        self.theme_error.setVisible(bool(error))
        self.theme_error.setText(error or "")
        if error and "not saved" not in error:  # The previous theme stays: show it in the picker again.
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.controller.theme.theme_id)))
            self.theme_combo.blockSignals(False)

    def on_scale_selected(self, index):
        self.controller.set_preference("ui_scale", self.scale_combo.itemData(index))
        self.reopen_button.setVisible(self.controller.can_reopen())
        self.scale_note_row.setVisible(True)

    def on_reopen(self):
        self.close()
        self.controller.reopen()

    def on_check_updates(self):
        self.update_button.setEnabled(False)
        self.update_label.setText("Checking…")

        def done(result):
            self.update_button.setEnabled(True)
            if result.get("error"):
                self.update_label.setText(result["error"])
            elif not result.get("version"):
                self.update_label.setText("You have the latest version ({}).".format(__version__))
            elif result.get("installed"):
                self.update_label.setText("Version {} installed. It starts the next time {} opens.".format(
                    result["version"], DISPLAY_NAME))
                if self.controller.window is not None:
                    self.controller.window.on_update_result(result, False)
            else:
                self.update_label.setText("Version {} is available (this copy is not installed from the launcher).".format(
                    result["version"]))

        if not self.controller.check_updates(done):
            self.update_button.setEnabled(True)
            self.update_label.setText("An update check is already running.")


class AboutDialog(ToolDialog):
    """Full-bleed hero (icon, name, subtitle), full-width accent divider, body with About insets (24/18, spacing 12),
    metadata, links, an optional disclaimer block, credits, a 36 px gap and Donate / Close. Header and hero keep a
    fixed vertical policy so extra height goes to the scrollable body. Unknown values are left out, never invented."""

    WIDTH = 460
    ICON_SIZE = 60

    def __init__(self, controller, parent):
        ToolDialog.__init__(self, controller, "About {}".format(DISPLAY_NAME), parent)
        theme = controller.theme
        self.setMinimumWidth(px(320))
        about = QtWidgets.QVBoxLayout(self.content)
        about.setContentsMargins(0, 0, 0, 0)
        about.setSpacing(0)

        hero = QtWidgets.QFrame()
        hero.setObjectName("toolAboutHero")
        hero.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        hero_layout = QtWidgets.QHBoxLayout(hero)
        hero_layout.setContentsMargins(px(24), px(18), px(24), px(18))
        hero_layout.setSpacing(px(12))
        icon = QtWidgets.QLabel()
        icon.setFixedSize(px(self.ICON_SIZE), px(self.ICON_SIZE))
        icon.setPixmap(controls.brand_pixmap(px(self.ICON_SIZE), controls.device_pixel_ratio(self)))
        hero_layout.addWidget(icon, 0, Qt.AlignVCenter)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        title = QtWidgets.QLabel(DISPLAY_NAME)
        title.setObjectName("toolAboutTitle")
        font = title.font()
        font.setPointSizeF(pt(20))
        font.setBold(True)
        title.setFont(font)
        subtitle = QtWidgets.QLabel(SUBTITLE)
        subtitle.setObjectName("toolMuted")
        font = subtitle.font()
        font.setPointSizeF(pt(10))
        subtitle.setFont(font)
        names.addStretch(1)
        names.addWidget(title)
        names.addWidget(subtitle)
        names.addStretch(1)
        hero_layout.addLayout(names, 1)
        about.addWidget(hero)

        divider = QtWidgets.QFrame()
        divider.setObjectName("toolAccentDivider")
        divider.setFixedHeight(px(2))
        divider.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        about.addWidget(divider)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QtWidgets.QWidget()
        body.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        content = QtWidgets.QVBoxLayout(body)
        content.setContentsMargins(px(24), px(18), px(24), px(18))
        content.setSpacing(px(12))
        content.addWidget(_wrapped(DESCRIPTION))
        content.addWidget(how_to_card(theme, USE_STEPS, USE_NOTE))
        meta = QtWidgets.QGridLayout()
        meta.setHorizontalSpacing(px(16))
        meta.setVerticalSpacing(px(4))
        rows = [("Version", __version__)] + ([("Developer", DEVELOPER)] if DEVELOPER else [])
        for row, (label, value) in enumerate(rows):
            meta.addWidget(controls.muted(label, wrap=False), row, 0)
            shown = QtWidgets.QLabel(value)
            shown.setTextInteractionFlags(Qt.TextSelectableByMouse)
            meta.addWidget(shown, row, 1)
        meta.setColumnStretch(1, 1)
        content.addLayout(meta)
        if LINKS:
            links = QtWidgets.QHBoxLayout()
            links.setSpacing(px(16))
            link_color = theme.colors.get("support_link", theme.colors.get("accent"))
            for label, address in LINKS:
                link = QtWidgets.QLabel('<a href="{0}" style="color:{1}; text-decoration:none">{2}</a>'.format(
                    address, link_color, label))
                link.setTextFormat(Qt.RichText)
                link.setOpenExternalLinks(True)
                link.setCursor(Qt.PointingHandCursor)
                links.addWidget(link)
            links.addStretch(1)
            content.addLayout(links)
        if DISCLAIMER:  # A warning block: rounded, warning tint fading down.
            notice = QtWidgets.QFrame()
            notice.setObjectName("toolBanner")
            notice_layout = QtWidgets.QVBoxLayout(notice)
            notice_layout.setContentsMargins(px(12), px(10), px(12), px(10))
            notice_layout.setSpacing(px(4))
            notice_title = QtWidgets.QLabel("Disclaimer")
            notice_title.setObjectName("toolBannerTitle")
            notice_layout.addWidget(notice_title)
            notice_layout.addWidget(_wrapped(DISCLAIMER, muted=True))
            content.addWidget(notice)
        content.addWidget(_rule())  # The footer apart from the rest
        content.addWidget(_wrapped("Credits: " + CREDITS, muted=True))
        content.addStretch(1)
        # The buttons stay at the bottom of the window, outside the scrolling part: always in view
        footer = QtWidgets.QWidget()
        buttons = QtWidgets.QHBoxLayout(footer)
        buttons.setContentsMargins(px(24), px(10), px(24), px(14))
        if DONATE_URL:
            donate = controls.Button("Donate", theme, icon="heart", variant="donate",
                                     tooltip="Support {} development".format(DISPLAY_NAME))
            donate.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(DONATE_URL)))
            buttons.addWidget(donate)
        buttons.addStretch(1)
        close = controls.Button("Close", theme)
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        scroll.setWidget(body)
        about.addWidget(scroll, 1)
        about.setStretchFactor(scroll, 1)
        about.addWidget(footer)
        self._hero, self._body, self._footer, self._scroll = hero, body, footer, scroll
        self._fitted = False
        self._fit_to_screen()

    def showEvent(self, event):
        ToolDialog.showEvent(self, event)
        if not self._fitted:  # Style sheet fonts and paddings apply at polish time: measure again once.
            self._fitted = True
            self._fit_to_screen()
            QtCore.QTimer.singleShot(0, self._grow_to_content)

    def _grow_to_content(self):
        """Rich text measures a little short before its first layout, so the body could still scroll: once it is laid
        out, grow by exactly what is missing (as far as the screen allows)."""
        missing = self._scroll.verticalScrollBar().maximum()
        if missing <= 0:
            return
        height = self.height() + missing + px(2)
        area = work_area(self.frameGeometry().center())
        if area is not None:
            height = min(height, int(area.height() * 0.9))
        self.resize(self.width(), height)

    def _fit_to_screen(self):
        # A scroll area's size hint ignores its content; wrapped labels need the height at the real width.
        for widget in [self, self._body] + self._body.findChildren(QtWidgets.QWidget):
            widget.ensurePolished()
        content = self._body.layout()
        content.invalidate()
        body = content.totalHeightForWidth(px(self.WIDTH)) if content.hasHeightForWidth() else \
            self._body.sizeHint().height()
        height = (self.title_bar.sizeHint().height() + self._hero.sizeHint().height() + 2 + body +
                  self._footer.sizeHint().height() + 4)
        area = work_area(self.frameGeometry().center())  # By position, never self.screen() (qt_compat.live_screens).
        if area is not None:
            height = min(height, int(area.height() * 0.9))
        self.resize(px(self.WIDTH), max(px(360), height))


class ConfirmDialog(ToolDialog):
    """A question in the tool's own style, never a Windows message box: the question, what it means, a neutral
    button (the default: Enter or Esc keep things as they are) and the action (red when it destroys something)."""

    def __init__(self, controller, parent, title, question, detail="", action="OK", cancel="Cancel", danger=True):
        ToolDialog.__init__(self, controller, title, parent)
        theme = controller.theme
        layout = QtWidgets.QVBoxLayout(self.content)
        layout.setContentsMargins(px(16), px(8), px(16), px(14))
        layout.setSpacing(px(8))
        heading = QtWidgets.QLabel(question)
        heading.setObjectName("toolSection")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        if detail:
            layout.addWidget(_rich(detail, theme))
        layout.addSpacing(px(6))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(6))
        row.addStretch(1)
        keep = controls.Button(cancel, theme)
        keep.clicked.connect(self.reject)
        go = controls.Button(action, theme, variant="danger" if danger else "primary")
        go.clicked.connect(self.accept)
        row.addWidget(keep)
        row.addWidget(go)
        layout.addLayout(row)
        keep.setDefault(True)
        keep.setFocus()
        self.setFixedWidth(px(380))


def ask(controller, parent, title, question, detail="", action="OK", cancel="Cancel", danger=True):
    """Ask in a ConfirmDialog; True when the action was chosen."""
    dialog = ConfirmDialog(controller, parent, title, question, detail, action, cancel, danger)
    try:
        return exec_dialog(dialog) == QtWidgets.QDialog.Accepted
    finally:
        dialog.dispose()


def how_to_card(theme, steps, note="", title="How to use"):
    """Steps in a card of their own: a title, numbered steps with room between them, a line and a note."""
    card = QtWidgets.QFrame()
    card.setObjectName("toolHowTo")
    layout = QtWidgets.QVBoxLayout(card)
    layout.setContentsMargins(px(14), px(12), px(14), px(12))
    layout.setSpacing(px(10))
    heading = QtWidgets.QLabel(title)
    heading.setObjectName("toolSection")
    layout.addWidget(heading)
    grid = QtWidgets.QGridLayout()
    grid.setHorizontalSpacing(px(10))
    grid.setVerticalSpacing(px(8))
    for row, step in enumerate(steps):
        grid.addWidget(controls.NumberBadge(row + 1, theme), row, 0, Qt.AlignTop)
        text = _rich(step, theme)
        text.setContentsMargins(0, px(3), 0, 0)  # The first line on the number's centre line
        grid.addWidget(text, row, 1)
    grid.setColumnStretch(1, 1)
    layout.addLayout(grid)
    if note:
        layout.addWidget(_rule())
        layout.addWidget(_rich(note, theme, muted=True))
    return card


def _rich(text, theme, muted=False):
    """A wrapped label from help markup (controls.help_html): bold terms, code chips, links that open."""
    label = QtWidgets.QLabel(controls.help_html(text, theme.colors, "muted_text" if muted else "text"))
    label.setTextFormat(Qt.RichText)
    label.setWordWrap(True)
    label.setOpenExternalLinks(True)
    label.setTextInteractionFlags(Qt.TextBrowserInteraction)
    return label


def _rule():
    """A thin line between parts of a dialog."""
    line = QtWidgets.QFrame()
    line.setObjectName("toolRule")
    line.setFixedHeight(1)
    return line


def _wrapped(text, muted=False):
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if muted:
        label.setObjectName("toolMuted")
    return label


def open_folder(path):
    if path and os.path.isdir(path):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))


def diagnostics():
    try:
        from pymxs import runtime as rt
        max_version = str(rt.maxVersion())
    except Exception:
        max_version = "n/a"
    return "\n".join([
        "{} {}".format(DISPLAY_NAME, __version__),
        "3ds Max: {}".format(max_version),
        "Python: {}".format(sys.version.split()[0]),
        "Qt: {} {}".format(BINDING, qt_version()),
        "OS: {}".format(platform.platform()),
    ])


from .logwindow import LogDialog  # noqa: E402,F401  (the Logs window lives in its own module)
