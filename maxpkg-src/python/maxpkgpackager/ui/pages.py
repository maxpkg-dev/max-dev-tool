"""The four pages of the packager: Info, Setup, Files, Release. Each reads from and writes to the open project."""

import datetime
import os
import shutil

from ..core import project as core
from ..qt_compat import QShortcut, QtCore, QtGui, QtWidgets, Qt, Signal
from ..ui_scale import px
from . import controls
from .changelog import ChangelogEditor
from .dialogs import ask
from .pickers import DateField, Stepper
from .switch import Switch


SCROLL_GAP = 4  # Between the panels and the vertical scroll bar, only while the bar shows


def scroll_page(widget):
    """A tab's page in a scroll area. Its panels line up with the tabs and the Build button (no side margin); when the
    page is taller than the window, the scroll bar gets a small gap so it does not touch the panels."""
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(widget)
    layout = widget.layout()

    def fit_gap(minimum, maximum):
        # The bar shows exactly while its range is not empty. A gap only makes the page narrower (never shorter), so
        # adding or removing it cannot make the bar come and go.
        margins = layout.contentsMargins()
        right = px(SCROLL_GAP) if maximum > minimum else 0
        if margins.right() != right:
            layout.setContentsMargins(margins.left(), margins.top(), right, margins.bottom())

    if layout is not None:
        area.verticalScrollBar().rangeChanged.connect(fit_gap)
    return area


def required_mark():
    """The red * after the name of something that must be filled in before a build."""
    star = QtWidgets.QLabel("*")
    star.setObjectName("toolRequired")
    star.setToolTip("Required")
    return star


def panel(title, theme, help_title=None, help_text=None, required=False):
    """A rounded panel with a section title (a red * when it must be filled in, and a "?" balloon). Returns (frame,
    content layout)."""
    frame = QtWidgets.QFrame()
    frame.setObjectName("toolPanel")
    outer = QtWidgets.QVBoxLayout(frame)
    outer.setContentsMargins(px(10), px(6), px(10), px(8))
    outer.setSpacing(px(5))
    head = QtWidgets.QHBoxLayout()
    head.setSpacing(px(6))
    name = QtWidgets.QHBoxLayout()
    name.setSpacing(px(2))  # The * as close to the title as to a field's name
    name.addWidget(controls.section(title), 0, Qt.AlignVCenter)  # The "?" sits on the title's centre line
    if required:
        name.addWidget(required_mark(), 0, Qt.AlignVCenter)
    head.addLayout(name)
    if help_text:
        head.addWidget(controls.HelpButton(theme, help_title or title, help_text), 0, Qt.AlignVCenter)
    head.addStretch(1)
    outer.addLayout(head)
    return frame, outer


def caption(text, required=False):
    """The name above a field; a field that must be filled in gets a red * after it."""
    label = QtWidgets.QLabel(text)
    label.setObjectName("toolCaption")
    if not required:
        return label
    row = QtWidgets.QWidget()
    line = QtWidgets.QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(px(2))
    line.addWidget(label)
    line.addWidget(required_mark())
    line.addStretch(1)
    return row


def labeled(text, widget, hint=None, required=False):
    box = QtWidgets.QVBoxLayout()
    box.setSpacing(px(2))
    box.addWidget(caption(text, required))
    box.addWidget(widget) if isinstance(widget, QtWidgets.QWidget) else box.addLayout(widget)
    if hint:
        box.addWidget(controls.muted(hint))
    return box


def field_with_button(edit, button):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(px(6))
    row.addWidget(edit, 1)
    row.addWidget(button)
    return row


class Page(QtWidgets.QWidget):
    """Base class: `refresh()` copies the project into the widgets without triggering edits."""

    def __init__(self, ctx):
        QtWidgets.QWidget.__init__(self)
        self.ctx = ctx
        self.model = ctx.model
        self.project = ctx.model.project
        self.theme = ctx.theme
        self.column = QtWidgets.QVBoxLayout(self)
        self.column.setContentsMargins(0, px(2), 0, px(2))  # Sides flush with the tabs and Build (scroll_page)
        self.column.setSpacing(px(6))

    def touch(self, structural=False):
        self.model.touch(structural)

    def line(self, getter, setter, placeholder="", readonly=False):
        edit = QtWidgets.QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setReadOnly(readonly)
        edit.setText(getter())
        edit.textEdited.connect(lambda text: (setter(text), self.touch()))
        edit._getter = getter
        return edit

    def sync(self, edit):
        text = edit._getter()
        if edit.text() != text:
            edit.blockSignals(True)
            edit.setText(text)
            edit.blockSignals(False)

    def short_path(self, path):
        if path and self.project.is_inside_root(path):
            return self.project.relative_to_root(path)
        return path or ""

    def icon_button(self, icon, tooltip, text=""):
        return controls.Button(text, self.theme, icon=icon, tooltip=tooltip)


# ---- Info ------------------------------------------------------------------------------------------------------
class InfoPage(Page):
    def __init__(self, ctx):
        Page.__init__(self, ctx)
        p = self.project
        frame, lay = panel("Package", self.theme, "Package identity",
                           "**Package name**: the public name on maxpkg.dev and in MaxPkg Manager.\n\n"
                           "**Button text**: the name of the 3ds Max button.\n\n"
                           "Both allow `A-Z a-z 0-9`, space, `-` and `_`.\n\n"
                           "**GUID**: identifies the package on maxpkg.dev. Generate it once and never change it.")
        self.name = self.line(lambda: p.package_name, lambda t: setattr(p, "package_name", t), "Public name, e.g. Bitmap Collector")
        self.button = self.line(lambda: p.button_name, lambda t: setattr(p, "button_name", t), "Text of the 3ds Max button")
        names = QtWidgets.QHBoxLayout()
        names.setSpacing(px(10))
        names.addLayout(labeled("Package name", required=True, widget=self.name), 1)
        names.addLayout(labeled("Button name", required=True, widget=self.button), 1)
        lay.addLayout(names)

        self.guid = self.line(lambda: p.guid, lambda t: None, "Generate once and keep it", readonly=True)
        self.guid_generate = controls.Button("Generate", self.theme, icon="refresh-cw",
                                             tooltip="Create the package GUID (its identity on maxpkg.dev)")
        self.guid_generate.clicked.connect(self.on_generate)
        copy = self.icon_button("copy", "Copy the GUID")
        copy.clicked.connect(self.on_copy)
        self.guid_copy = copy
        # Rare actions go into a menu, so the GUID itself stays fully readable in a narrow window.
        self.guid_menu = controls.Menu(self.theme, self)
        self.guid_menu.add_item("Paste GUID from clipboard", "clipboard-paste", self.on_paste)
        self.guid_menu.addSeparator()
        self.guid_menu.add_item("Generate a new GUID…", "refresh-cw", self.on_generate)
        more = self.icon_button("chevron-down", "Paste or generate a GUID")
        more.clicked.connect(lambda: self.guid_menu.popup_at(more.mapToGlobal(QtCore.QPoint(0, more.height() + 2))))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(6))
        row.addWidget(self.guid, 1)
        row.addWidget(self.guid_generate)
        row.addWidget(copy)
        row.addWidget(more)
        self.guid_more = more
        lay.addLayout(labeled("GUID", row, required=True))

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setFixedHeight(px(52))
        self.description.setPlainText(p.description)
        self.description.textChanged.connect(self.on_description)
        self.counter = controls.muted("", wrap=False)
        self.description_box = controls.boxed(self.description)
        lay.addLayout(labeled("Description", self.description_box, required=True))
        lay.addWidget(self.counter)
        self.column.addWidget(frame)

        frame, lay = panel("Author and license", self.theme, "Author and license",
                           "Shown on maxpkg.dev and in the installer.\n\n"
                           "**Developer** and **license** carry over to your next project.\n\n"
                           "**Links** are optional.")
        self.developer = self.line(lambda: p.developer, lambda t: setattr(p, "developer", t), "Name users will see")
        self.license = controls.ComboBox()
        self.license.addItem("Choose a license…", "")
        for name in core.LICENSES:
            self.license.addItem(name, name)
        self.license.currentIndexChanged.connect(self.on_license)
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(px(10))
        top.addLayout(labeled("Developer name", self.developer, required=True), 1)
        top.addLayout(labeled("License", self.license, required=True), 1)
        lay.addLayout(top)
        self.license_url = self.line(lambda: p.license_url, lambda t: setattr(p, "license_url", t), "https://")
        self.documentation = self.line(lambda: p.documentation, lambda t: setattr(p, "documentation", t), "https://")
        self.homepage = self.line(lambda: p.homepage, lambda t: setattr(p, "homepage", t), "https://")
        for text, edit in (("License URL", self.license_url), ("Documentation URL", self.documentation),
                           ("Homepage URL", self.homepage)):
            lay.addLayout(labeled(text, edit))
        self.column.addWidget(frame)

        # Optional, so closed until it is used (like Extra macros); open when the project has a link
        self.purchase_group = Collapsible("Purchase or support link", self.theme)
        lay = self.purchase_group.inner
        lay.addWidget(controls.muted("Optional: a page for a paid license, a donation, sponsors or support. Pick the "
                                     "button label that matches the page."))
        self.purchase = self.line(lambda: p.purchase, lambda t: setattr(p, "purchase", t), "https://")
        for edit, attribute in ((self.license_url, "license_url"), (self.documentation, "documentation"),
                                (self.homepage, "homepage"), (self.purchase, "purchase")):
            edit.editingFinished.connect(lambda e=edit, a=attribute: self.complete_link(e, a))
        self.purchase.textChanged.connect(lambda text: self.purchase_label.setEnabled(bool(text.strip())))
        self.purchase_label = controls.ComboBox()
        for name in core.PURCHASE_LABELS:
            self.purchase_label.addItem(name, name)
        self.purchase_label.currentIndexChanged.connect(self.on_purchase_label)
        lay.addLayout(labeled("URL", self.purchase))
        lay.addLayout(labeled("Button label", self.purchase_label))
        self.column.addWidget(self.purchase_group)
        self.column.addStretch(1)
        self.refresh()
        if p.purchase.strip():
            self.purchase_group.header.setChecked(True)

    def complete_link(self, edit, attribute):
        """A site typed without https:// gets it when the field is left: '3dground.net' -> 'https://3dground.net'."""
        value = getattr(self.project, attribute)
        completed = core.complete_url(value)
        if completed != value:
            setattr(self.project, attribute, completed)
            self.sync(edit)
            self.touch()

    def on_description(self):
        text = self.description.toPlainText()
        if len(text) > 500:  # The limit is enforced where it is typed, not only when building.
            cursor = self.description.textCursor()
            self.description.blockSignals(True)
            self.description.setPlainText(text[:500])
            self.description.setTextCursor(cursor)
            self.description.blockSignals(False)
            text = text[:500]
        self.project.description = text
        self.counter.setText(self.description_count(text))
        self.touch()

    @staticmethod
    def description_count(text):
        lines = len(text.strip().splitlines()) if text.strip() else 0
        return "{} / 500 characters · {} / 3 lines".format(len(text), lines)

    def on_license(self, index):
        self.project.license = self.license.itemData(index) or ""
        self.touch()

    def on_purchase_label(self, index):
        self.project.purchase_label = self.purchase_label.itemData(index)
        self.touch()

    def on_generate(self):
        if self.project.guid.strip():
            if not ask(self.ctx.controller, self.window(), "Change GUID", "Generate a new GUID?",
                       "Changing the GUID creates a **new package identity** on maxpkg.dev. Only do this for a "
                       "different package.", "Generate", "Keep it"):
                return
        self.project.guid = core.new_guid()
        self.sync(self.guid)
        self.sync_guid_buttons()
        self.touch()

    def on_copy(self):
        QtWidgets.QApplication.clipboard().setText(self.project.guid)
        self.ctx.status("GUID copied.")

    def on_paste(self):
        text = QtWidgets.QApplication.clipboard().text().strip()
        if not core.is_valid_guid(text):
            self.ctx.status("The clipboard does not contain a valid GUID.")
            return
        if self.project.guid.strip() and text.lower() != self.project.guid.lower():
            if not ask(self.ctx.controller, self.window(), "Replace GUID", "Replace the GUID?",
                       "Replacing the GUID changes the **package identity** on maxpkg.dev.", "Replace", "Keep it"):
                return
        self.project.guid = text.lower()
        self.sync(self.guid)
        self.sync_guid_buttons()
        self.touch()

    def refresh(self):
        for edit in (self.name, self.button, self.guid, self.developer, self.license_url, self.documentation,
                     self.homepage, self.purchase):
            self.sync(edit)
        self.description.blockSignals(True)
        if self.description.toPlainText() != self.project.description:
            self.description.setPlainText(self.project.description)
        self.description.blockSignals(False)
        self.counter.setText(self.description_count(self.project.description))
        self.license.blockSignals(True)
        self.license.setCurrentIndex(max(0, self.license.findData(self.project.license)))
        self.license.blockSignals(False)
        self.purchase_label.blockSignals(True)
        self.purchase_label.setCurrentIndex(max(0, self.purchase_label.findData(self.project.purchase_label)))
        self.purchase_label.blockSignals(False)
        self.purchase_label.setEnabled(bool(self.project.purchase.strip()))
        self.sync_guid_buttons()

    def sync_guid_buttons(self):
        """No GUID yet: one Generate button. A GUID: copy it, and the menu for the rare paste or replace."""
        has_guid = bool(self.project.guid.strip())
        self.guid_generate.setVisible(not has_guid)
        self.guid_copy.setVisible(has_guid)
        self.guid_more.setVisible(has_guid)



# ---- Setup -----------------------------------------------------------------------------------------------------
class SetupPage(Page):
    def __init__(self, ctx):
        Page.__init__(self, ctx)
        p = self.project
        frame, lay = panel("Installation", self.theme, "Installation",
                           "What the package does when it is installed in 3ds Max.")
        self.create_button = Switch(self.theme, "Create a 3ds Max button that runs the entry file")
        self.show_toolbar = Switch(self.theme, "Show in the MaxPkg toolbar")
        for box, attr in ((self.create_button, "create_button"), (self.show_toolbar, "show_toolbar")):
            box.setCursor(Qt.PointingHandCursor)
            box.toggled.connect(lambda on, a=attr: (setattr(self.project, a, on), self.touch()))
            lay.addWidget(box)
        self.column.addWidget(frame)

        frame, lay = panel("Installer windows", self.theme, "Standard hooks",
                           "`_install.ms`: the standard MaxPkg install window.\n\n"
                           "`_uninstall.ms`: the standard removal window.\n\n"
                           "A file in the max-package folder is included automatically.")
        self.hook_pills, self.hook_buttons = {}, {}
        for name, text in (("_install.ms", "Install window"), ("_uninstall.ms", "Uninstall window")):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(px(8))
            label = QtWidgets.QLabel(text)
            label.setFixedWidth(px(108))
            row.addWidget(label)
            pill = controls.Pill(self.theme, "", "neutral")
            self.hook_pills[name] = pill
            row.addWidget(pill)
            row.addStretch(1)
            get = controls.Button("Add", self.theme, icon="download",
                                  tooltip="Download {} into the project folder".format(name))
            get.clicked.connect(lambda _=False, n=name: self.ctx.fetch_hook(n, self.refresh))
            self.hook_buttons[name] = get
            row.addWidget(get)
            lay.addLayout(row)
        self.column.addWidget(frame)

        frame, lay = panel("Custom scripts", self.theme, "Custom scripts",
                           "Optional: a short, non-interactive `.ms` file for project-specific work.\n\n"
                           "**Install** runs at the end of installation.\n"
                           "**Uninstall** runs before removal.\n\n"
                           "Keep it inside the project folder. It is included automatically: do not add it to Files.\n\n"
                           "Needs the matching standard file.")
        self.custom = {}
        for attr, text in (("custom_install", "Custom install script"), ("custom_uninstall", "Custom uninstall script")):
            edit = self.line(lambda a=attr: getattr(self.project, a), lambda t, a=attr: setattr(self.project, a, t),
                             "Not used", readonly=True)
            browse = self.icon_button("folder-open", "Choose a .ms file in the project folder")
            clear = self.icon_button("x", "Do not use a custom script")
            browse.clicked.connect(lambda _=False, a=attr, e=edit: self.choose_custom(a, e))
            clear.clicked.connect(lambda _=False, a=attr, e=edit: self.clear_custom(a, e))
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(px(6))
            row.addWidget(edit, 1)
            row.addWidget(browse)
            row.addWidget(clear)
            lay.addLayout(labeled(text, row))
            self.custom[attr] = (edit, browse, clear)
        self.column.addWidget(frame)
        self.column.addStretch(1)
        self.refresh()

    def choose_custom(self, attr, edit):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Choose a script", self.project.root,
                                                              "MAXScript (*.ms)")
        if path:
            setattr(self.project, attr, core.norm(os.path.abspath(path)))
            self.sync(edit)
            self.touch()

    def clear_custom(self, attr, edit):
        setattr(self.project, attr, "")
        self.sync(edit)
        self.touch()

    def refresh(self):
        p = self.project
        for box, value in ((self.create_button, p.create_button), (self.show_toolbar, p.show_toolbar)):
            box.blockSignals(True)
            box.setChecked(value)
            box.blockSignals(False)
        present = {}
        for name, pill in self.hook_pills.items():
            found = bool(p.hook_path(name))
            present[name] = found
            pill.set_status("Included" if found else "Not added", "success" if found else "neutral",
                            "max-package\\{} is included in every build".format(name) if found else
                            "Click Add to download the standard {} into max-package".format(name))
            self.hook_buttons[name].setVisible(not found)
        for attr, (edit, browse, clear) in self.custom.items():
            self.sync(edit)
            standard = "_install.ms" if attr == "custom_install" else "_uninstall.ms"
            browse.setEnabled(present[standard])
            browse.setToolTip("Choose a .ms file in the project folder" if present[standard] else
                              "Add the {} window first: the custom script runs from it".format(
                                  "install" if standard == "_install.ms" else "uninstall"))
            clear.setVisible(bool(getattr(p, attr)))


# ---- Files -----------------------------------------------------------------------------------------------------
class _GroupHeader(controls.Button):
    """The title of a Collapsible. It looks like the title of any other panel, not like a button: on hover only the
    colour of the text and the arrow changes."""

    def __init__(self, title, theme):
        controls.Button.__init__(self, title, theme, icon="chevron-right", variant="ghost", icon_role="heading_text")
        self.setObjectName("toolGroupHeader")
        self.setCursor(Qt.PointingHandCursor)

    GAP = 1  # Between the arrow's icon and the title; the arrow's picture adds about 6 px of air of its own

    def _tint(self, role):
        self.icon_role = role
        self._on_theme(self._theme.colors)

    def paintEvent(self, event):
        """The arrow, a small gap and the title, both centred on the button's height. No background or frame."""
        painter = QtGui.QPainter(self)
        size = self.iconSize()
        left = px(4)
        self.icon().paint(painter, QtCore.QRect(left, (self.height() - size.height()) // 2, size.width(), size.height()))
        painter.setFont(self.font())
        painter.setPen(QtGui.QColor(self._theme.colors[self.icon_role or "heading_text"]))
        title = QtCore.QRect(left + size.width() + px(self.GAP), 0, self.width(), self.height())
        painter.drawText(title, int(Qt.AlignVCenter | Qt.AlignLeft), self.text())
        painter.end()

    def enterEvent(self, event):
        self._tint("text")
        controls.Button.enterEvent(self, event)

    def leaveEvent(self, event):
        self._tint("heading_text")
        controls.Button.leaveEvent(self, event)


class Collapsible(QtWidgets.QFrame):
    """A titled group that opens and closes, drawn as a panel like every other group of the window."""

    toggled = Signal(bool)

    def __init__(self, title, theme, parent=None):
        QtWidgets.QFrame.__init__(self, parent)
        self.setObjectName("toolPanel")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(px(6), px(5), px(10), px(5))  # Same room above and below: a closed group is centred
        lay.setSpacing(px(6))
        self.header = _GroupHeader(title, theme)
        self.header.setCheckable(True)
        self.header.setFocusPolicy(Qt.NoFocus)
        self.header.toggled.connect(self.set_open)
        lay.addWidget(self.header, 0, Qt.AlignLeft)
        self.content = QtWidgets.QWidget()
        self.inner = QtWidgets.QVBoxLayout(self.content)
        self.inner.setContentsMargins(px(4), 0, 0, 0)
        self.inner.setSpacing(px(8))
        self.content.setVisible(False)
        lay.addWidget(self.content)

    def set_open(self, on):
        self.content.setVisible(on)
        self.header.icon_name = "chevron-down" if on else "chevron-right"
        self.header._on_theme(self.header._theme.colors)  # Re-tint the new icon
        self.toggled.emit(on)


class FilesPage(Page):
    PREVIEW = 64  # The icon preview, 64 x 64: about as tall as the icon field and its check below it

    def __init__(self, ctx):
        Page.__init__(self, ctx)
        p = self.project
        frame, lay = panel("Output", self.theme, "Output and icon",
                           "**Output folder**: where the built `.mzp` goes.\n\n"
                           "**Icon**: a square SVG. It is copied into the max-package folder.")
        self.output = self.line(lambda: self.short_path(p.output_folder), lambda t: None, "Output folder", readonly=True)
        browse = self.icon_button("folder-open", "Choose the output folder")
        browse.clicked.connect(self.on_output)
        lay.addLayout(labeled("Output folder", field_with_button(self.output, browse)))
        self.icon_edit = self.line(lambda: self.short_path(p.svg_icon), lambda t: None, "Choose a square .svg file",
                                   readonly=True)
        pick = self.icon_button("folder-open", "Choose a square SVG icon")
        pick.clicked.connect(self.on_icon)
        # A large preview on the left, as tall as the field and the check together; the field and the check on its right
        self.icon_preview = QtWidgets.QLabel()
        self.icon_preview.setObjectName("toolIconPreview")
        self.icon_preview.setFixedSize(px(self.PREVIEW), px(self.PREVIEW))
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_pill = controls.Pill(self.theme, "", "neutral")
        side = QtWidgets.QVBoxLayout()
        side.setSpacing(px(6))
        side.addLayout(field_with_button(self.icon_edit, pick))
        pill_row = QtWidgets.QHBoxLayout()
        pill_row.addWidget(self.icon_pill)
        pill_row.addStretch(1)
        side.addLayout(pill_row)
        side.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(8))
        row.addWidget(self.icon_preview, 0, Qt.AlignTop)
        row.addLayout(side, 1)
        lay.addLayout(labeled("SVG icon", row, required=True))
        self.icon_advice = controls.muted("", wrap=True)  # What to do when the icon has a problem, under all of it
        self.icon_advice.setTextFormat(Qt.RichText)
        self.icon_advice.setOpenExternalLinks(True)
        lay.addWidget(self.icon_advice)
        self.column.addWidget(frame)

        frame, lay = panel("Package files", self.theme, "Files list", required=True, help_text=
                           "Every file your tool needs once installed. Common temporary files are skipped.\n\n"
                           "**Entry file**: the script the 3ds Max button runs.")
        self.files = QtWidgets.QListWidget()
        self.files.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.files.setMinimumHeight(px(84))
        self.files.setMaximumHeight(px(150))
        self.files_box = controls.boxed(self.files)
        self.files.itemSelectionChanged.connect(self.sync_buttons)
        self.files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self.files_menu)
        delete_key = QShortcut(QtGui.QKeySequence(Qt.Key_Delete), self.files)
        delete_key.setContext(Qt.WidgetShortcut)
        delete_key.activated.connect(self.on_remove)
        lay.addWidget(self.files_box)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(px(6))
        add_files = controls.Button("Add files", self.theme, icon="box", tooltip="Add files from the project folder")
        add_files.clicked.connect(self.on_add_files)
        add_folder = controls.Button("Add folder", self.theme, icon="folder-open", tooltip="Add a folder with its files")
        add_folder.clicked.connect(self.on_add_folder)
        self.remove = controls.Button("", self.theme, icon="trash-2", variant="danger", tooltip="Remove the selected files (Delete)")
        self.remove.clicked.connect(self.on_remove)
        self.file_count = controls.muted("", wrap=False)
        for widget in (add_files, add_folder):
            buttons.addWidget(widget)
        buttons.addStretch(1)
        buttons.addWidget(self.file_count)
        buttons.addWidget(self.remove)
        lay.addLayout(buttons)
        self.entry = controls.ComboBox()
        self.entry.currentIndexChanged.connect(self.on_entry)
        self.compile = Switch(self.theme, "Compile the entry .ms into .mse")
        self.compile.setCursor(Qt.PointingHandCursor)
        self.compile.toggled.connect(self.on_compile)
        lay.addLayout(labeled("Entry file", self.entry, required=True))
        lay.addWidget(self.compile)
        self.column.addWidget(frame)

        self.remap = Collapsible("Build path remap", self.theme)
        self.remap.inner.addWidget(controls.muted("Keep files in one folder in your project but place them in another "
                                                  "inside the package. Leave the target empty for the package root."))
        self.rules = QtWidgets.QListWidget()
        self.rules.setMaximumHeight(px(110))
        self.rules_box = controls.boxed(self.rules)
        self.remap.inner.addWidget(self.rules_box)
        self.rule_source = QtWidgets.QLineEdit()
        self.rule_source.setPlaceholderText("From folder")
        self.rule_target = QtWidgets.QLineEdit()
        self.rule_target.setPlaceholderText("To (empty = root)")
        add_rule = controls.Button("", self.theme, icon="plus", tooltip="Add the rule")
        add_rule.clicked.connect(self.on_add_rule)
        del_rule = controls.Button("", self.theme, icon="trash-2", variant="danger", tooltip="Remove the selected rule")
        del_rule.clicked.connect(self.on_remove_rule)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(6))
        row.addWidget(self.rule_source, 1)
        row.addWidget(self.rule_target, 1)
        row.addWidget(add_rule)
        row.addWidget(del_rule)
        self.remap.inner.addLayout(row)
        self.column.addWidget(self.remap)

        self.extra = Collapsible("Extra macros", self.theme)
        self.extra.inner.addWidget(controls.muted("More 3ds Max buttons that run other scripts of the package. "
                                                  "Names allow letters, spaces and underscores."))
        self.macros = QtWidgets.QListWidget()
        self.macros.setMaximumHeight(px(120))
        self.macros_box = controls.boxed(self.macros)
        self.extra.inner.addWidget(self.macros_box)
        self.macro_file = controls.ComboBox()
        self.macro_file.setPlaceholderText("Script to run")
        self.macro_name = QtWidgets.QLineEdit()
        self.macro_name.setPlaceholderText("Button name")
        # Two equal halves, however long the file names in the list are
        self.macro_file.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.macro_file.setMinimumContentsLength(6)
        for half in (self.macro_file, self.macro_name):
            half.setSizePolicy(QtWidgets.QSizePolicy.Ignored, half.sizePolicy().verticalPolicy())
        pick = QtWidgets.QHBoxLayout()
        pick.setSpacing(px(6))
        pick.addWidget(self.macro_file, 1)
        pick.addWidget(self.macro_name, 1)
        self.extra.inner.addLayout(pick)
        self.macro_compile = Switch(self.theme, "Compile")
        self.macro_quad = Switch(self.theme, "Quad menu")
        for box in (self.macro_compile, self.macro_quad):
            box.setCursor(Qt.PointingHandCursor)
        add_macro = controls.Button("", self.theme, icon="plus", tooltip="Add the macro")
        add_macro.clicked.connect(self.on_add_macro)
        del_macro = controls.Button("", self.theme, icon="trash-2", variant="danger", tooltip="Remove the selected macro")
        del_macro.clicked.connect(self.on_remove_macro)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(10))
        row.addWidget(self.macro_compile)
        row.addWidget(self.macro_quad)
        row.addStretch(1)
        row.addWidget(add_macro)
        row.addWidget(del_macro)
        self.extra.inner.addLayout(row)
        self.column.addWidget(self.extra)
        self.column.addStretch(1)
        self.refresh()

    # -- handlers
    def on_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder", self.project.output_folder or self.project.root)
        if path:
            self.project.output_folder = core.norm(path)
            self.sync(self.output)
            self.touch()

    def on_icon(self):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Choose a square SVG icon", self.project.root, "SVG (*.svg)")
        if not path:
            return
        from ..core import svgcheck
        report = svgcheck.inspect(path)
        if not report.ok:
            self.ctx.status("This icon cannot be used: {}.".format(report.errors[0]), "error")
            return
        if report.warnings:
            self.ctx.status(report.warnings[0] + (". Clean it with SVGOMG (link under the icon)." if report.needs_cleanup
                                                  else "."), "warning")
        target = os.path.join(self.project.support_dir, core.ICON_FILE)
        try:
            os.makedirs(self.project.support_dir, exist_ok=True)
            if os.path.abspath(path).lower() != os.path.abspath(target).lower():
                shutil.copyfile(path, target)
        except OSError as error:
            self.ctx.status("Could not copy the icon: {}".format(error))
            return
        self.project.svg_icon = core.norm(target)
        self.sync(self.icon_edit)
        self.refresh_icon()
        self.touch()

    def refresh_icon(self):
        path = self.project.svg_icon
        shown = bool(path and os.path.isfile(path))
        self.icon_preview.setVisible(shown)  # No empty box before an icon is chosen
        if shown:  # Sharp on scaled screens: drawn at the screen's pixels
            ratio = controls.device_pixel_ratio(self) or 1.0
            size = int(px(self.PREVIEW) * ratio)  # The icon fills the preview
            pixmap = QtGui.QIcon(path).pixmap(size, size)
            pixmap.setDevicePixelRatio(ratio)
            self.icon_preview.setPixmap(pixmap)
        self.icon_edit.setToolTip(path or "")
        self.output.setToolTip(self.project.output_folder)
        self.refresh_icon_check(path if shown else "")

    def refresh_icon_check(self, path):
        """The icon check in one line under the field: a pill, and what to do when something is wrong."""
        from ..core import svgcheck
        if not path:
            self.icon_pill.hide()
            self.icon_advice.hide()
            return
        report = svgcheck.inspect(path)
        self.icon_pill.show()
        if report.errors:
            self.icon_pill.set_status("Cannot be used", "error")
            advice = report.errors[0] + ". Choose another SVG."
        elif report.warnings:
            self.icon_pill.set_status("Needs attention", "warning")
            advice = " ".join(message + "." for message in report.warnings)
            if report.needs_cleanup:
                advice += (' Open <a href="{0}">SVGOMG</a>, drop the icon there, download the result and choose it '
                           'here again.').format(svgcheck.SVGOMG_URL)
        else:
            size = "{:g} x {:g}".format(report.width, report.height)
            self.icon_pill.set_status("Square SVG {}, clean".format(size), "success")
            advice = ""
        self.icon_advice.setText(advice)
        self.icon_advice.setVisible(bool(advice))

    def on_add_files(self):
        paths, _filter = QtWidgets.QFileDialog.getOpenFileNames(self, "Add package files", self.project.root)
        skipped = 0
        for path in paths:
            if not self.project.add_file(path):
                skipped += 1
        if skipped:
            self.ctx.status("{} file(s) skipped: excluded, outside the project or not found.".format(skipped))
        if paths:
            self.after_files()

    def on_add_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Add a folder", self.project.root)
        if path:
            added = self.project.add_folder(path)
            self.ctx.status("{} file(s) added.".format(added))
            self.after_files()

    def on_remove(self):
        for item in self.files.selectedItems():
            self.project.remove_file(item.data(Qt.UserRole))
        self.after_files()

    def files_menu(self, position):
        item = self.files.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.files.setCurrentItem(item)
        relative = item.data(Qt.UserRole)
        menu = controls.Menu(self.theme, self)
        if relative.lower().endswith(core.ENTRY_EXTENSIONS):
            menu.add_item("Use as entry file", "play",
                          lambda: self.entry.setCurrentIndex(max(0, self.entry.findData(relative))))
            menu.addSeparator()
        count = len(self.files.selectedItems())
        menu.add_item("Remove" if count == 1 else "Remove {} files".format(count), "trash-2", self.on_remove,
                      danger=True)
        menu.popup_at(self.files.viewport().mapToGlobal(position))

    def after_files(self):
        if not self.project.entry:  # A single script is almost always the entry.
            scripts = [rel for rel in self.project.macro_candidates() if "\\" not in rel]
            if len(scripts) == 1:
                self.project.entry = scripts[0]
        self.touch(structural=True)

    def sync_buttons(self):
        self.remove.setEnabled(bool(self.files.selectedItems()))

    def on_entry(self, index):
        entry = self.entry.itemData(index) or ""
        if entry != self.project.entry:
            self.project.entry = entry
            self.refresh_compile()
            self.touch()

    def on_compile(self, on):
        self.project.compile_entry = on
        self.touch()

    def on_add_rule(self):
        source, target = self.rule_source.text(), self.rule_target.text()
        if not core.is_safe_rule_folder(source) or not core.is_safe_rule_folder(target, True):
            self.ctx.status("Invalid folder: use a relative path inside the project.")
            return
        self.project.rules.append((core.normalize_rule_folder(source), core.normalize_rule_folder(target, True)))
        self.rule_source.clear()
        self.rule_target.clear()
        self.touch(structural=True)

    def on_remove_rule(self):
        row = self.rules.currentRow()
        if row >= 0:
            del self.project.rules[row]
            self.touch(structural=True)

    def on_add_macro(self):
        file = self.macro_file.currentData()
        title = self.macro_name.text().strip()
        if not file or not title:
            self.ctx.status("Choose a script and type a button name.")
            return
        if not core.SAFE_MACRO_TITLE.match(title):
            self.ctx.status("Button name allows only letters, spaces and underscores.")
            return
        macro = core.MacroItem(file, title, self.macro_compile.isChecked(), self.macro_quad.isChecked())
        if any(m.identifier.lower() == macro.identifier.lower() for m in self.project.macros):
            self.ctx.status("A macro with this name already exists.")
            return
        self.project.macros.append(macro)
        self.macro_name.clear()
        self.touch(structural=True)

    def on_remove_macro(self):
        row = self.macros.currentRow()
        if row >= 0:
            del self.project.macros[row]
            self.touch(structural=True)

    # -- refresh
    def refresh_compile(self):
        can = self.project.can_compile_entry
        self.compile.setEnabled(can)
        self.compile.blockSignals(True)
        self.compile.setChecked(can and self.project.compile_entry)
        self.compile.blockSignals(False)

    def refresh(self):
        p = self.project
        self.sync(self.output)
        self.sync(self.icon_edit)
        self.refresh_icon()
        self.files.clear()
        missing = 0
        for absolute, relative in p.files:
            exists = os.path.isfile(absolute)
            item = QtWidgets.QListWidgetItem(relative if exists else "[missing] " + relative)
            item.setData(Qt.UserRole, relative)
            self.files.addItem(item)
            missing += 0 if exists else 1
        self.file_count.setText("{} files{}".format(len(p.files), ", {} missing".format(missing) if missing else ""))
        self.entry.blockSignals(True)
        self.entry.clear()
        self.entry.addItem("Choose the entry file…", "")
        for relative in p.macro_candidates():
            self.entry.addItem(relative, relative)
        self.entry.setCurrentIndex(max(0, self.entry.findData(p.entry)))
        self.entry.blockSignals(False)
        self.refresh_compile()
        self.rules.clear()
        for source, target in p.rules:
            self.rules.addItem("{}  →  {}".format(source, target or "/"))
        self.rules_box.setVisible(bool(p.rules))
        self.macros.clear()
        self.macros_box.setVisible(bool(p.macros))
        for macro in p.macros:
            flags = ", ".join(x for x, on in (("compiled", macro.compile), ("quad menu", macro.quad)) if on)
            self.macros.addItem("{}  ·  {}{}".format(macro.button, macro.file, "  ({})".format(flags) if flags else ""))
        self.macro_file.clear()
        for relative in p.macro_candidates():
            self.macro_file.addItem(relative, relative)
        if p.rules:
            self.remap.header.setChecked(True)
        if p.macros:
            self.extra.header.setChecked(True)
        self.sync_buttons()


# ---- Release ---------------------------------------------------------------------------------------------------
class ReleasePage(Page):
    def __init__(self, ctx):
        Page.__init__(self, ctx)
        frame, lay = panel("Version", self.theme, "Release",
                           "Each version has its own date, channel, minimum 3ds Max and changelog.\n\n"
                           "Change the version first, then write its changelog.")
        self.spins = []
        row = QtWidgets.QGridLayout()  # Each number with its own caption above it: Major . Minor . Patch
        row.setHorizontalSpacing(px(4))
        row.setVerticalSpacing(px(2))
        for index, name in enumerate(("Major", "Minor", "Patch")):
            spin = Stepper(self.theme, 0, 999)
            spin.valueChanged.connect(lambda value, i=index: self.on_version(i))
            self.spins.append(spin)
            row.addWidget(caption(name), 0, index * 2)
            row.addWidget(spin, 1, index * 2)
            if index < 2:
                dot = QtWidgets.QLabel(".")
                dot.setAlignment(Qt.AlignCenter)
                row.addWidget(dot, 1, index * 2 + 1)
        self.channel = controls.ComboBox()
        for key, name in (("stable", "Stable"), ("beta", "Beta"), ("alpha", "Alpha")):
            self.channel.addItem(name, key)
        self.channel.currentIndexChanged.connect(self.on_channel)
        numbers = QtWidgets.QHBoxLayout()  # The numbers keep to the left; the free room goes to the right of them
        numbers.addLayout(row)
        numbers.addStretch(1)
        channel_box = QtWidgets.QVBoxLayout()
        channel_box.setSpacing(px(2))
        caption_row = QtWidgets.QHBoxLayout()
        caption_row.setSpacing(px(4))
        caption_row.addWidget(caption("Channel"), 0, Qt.AlignVCenter)
        caption_row.addWidget(controls.HelpButton(self.theme, "Release channel", core.CHANNEL_HELP), 0,
                              Qt.AlignVCenter)
        caption_row.addStretch(1)
        channel_box.addLayout(caption_row)
        channel_box.addWidget(self.channel)
        # The version numbers and the channel share a row; in a narrow window the channel goes under the numbers
        # instead of pushing the page wider than the window (which cut off the right edge of every panel).
        self.version_row = controls.Reflow([(controls.holder(numbers), 1), (controls.holder(channel_box), 0)],
                                           spacing=10)
        lay.addWidget(self.version_row)
        self.channel_note = QtWidgets.QLabel("")  # Beta / Alpha: where the version will (not) be seen
        self.channel_note.setObjectName("toolWarningNote")
        self.channel_note.setWordWrap(True)
        self.channel_note.hide()
        lay.addWidget(self.channel_note)
        self.date = DateField(self.theme)
        self.date.changed.connect(self.on_date)
        self.min_max = controls.ComboBox()
        for year in core.max_years():
            self.min_max.addItem(year, year)
        self.min_max.currentIndexChanged.connect(self.on_min_max)
        info = QtWidgets.QHBoxLayout()
        info.setSpacing(px(8))
        info.addLayout(labeled("Release date", self.date, required=True), 1)
        info.addLayout(labeled("Min 3ds Max", self.min_max), 1)
        lay.addLayout(info)
        self.column.addWidget(frame)

        frame, lay = panel("Changelog for this version", self.theme, "Changelog", required=True, help_text=
                           "At least one item is required.\n\n"
                           "Type a line and press Enter, or paste several lines at once.\n\n"
                           "A sign at the start sets the type:\n"
                           "`+` Added   `-` Fixed   `*` Changed   `**` Improved")
        self.editor = ChangelogEditor(self.theme, lambda: self.project.changelog, lambda: self.touch(structural=False),
                                      self.ctx.controller)
        lay.addWidget(self.editor)
        self.column.addWidget(frame, 1)  # The changelog list takes the free height of the page
        self.refresh()

    # -- version
    def on_version(self, index):
        numbers = [spin.value() for spin in self.spins]
        old = core.parse_version(self.project.version)
        if numbers[index] > old[index]:
            for later in range(index + 1, 3):  # A new major or minor starts its lower numbers from zero.
                numbers[later] = 0
        version = core.version_text(tuple(numbers))
        if version != self.project.version:
            self.project.version = version
            self.touch(structural=True)

    def on_channel(self, index):
        key = self.channel.itemData(index)
        if key and key != self.project.release().channel:
            self.project.release().channel = key
            self.sync_channel_note()
            self.touch()

    def sync_channel_note(self):
        channel = self.project.release().channel
        self.channel_note.setVisible(channel != "stable")
        if channel != "stable":
            self.channel_note.setText(core.CHANNEL_WARNING.format(channel.capitalize()) + ".")

    def on_date(self, date):
        self.project.release().date = date.toString("yyyy-MM-dd")
        self.touch()

    def on_min_max(self, index):
        self.project.release().min_max = self.min_max.itemData(index)
        self.touch()

    def refresh(self):
        p = self.project
        release = p.release()
        numbers = core.parse_version(p.version)
        for spin, value in zip(self.spins, numbers):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self.channel.blockSignals(True)
        self.channel.setCurrentIndex(max(0, self.channel.findData(release.channel)))  # Stable when unknown
        self.sync_channel_note()
        self.channel.blockSignals(False)
        try:
            parsed = datetime.datetime.strptime(release.date, "%Y-%m-%d").date()
        except ValueError:
            parsed = datetime.date.today()
        self.date.setDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
        self.min_max.blockSignals(True)
        self.min_max.setCurrentIndex(max(0, self.min_max.findData(release.min_max)))
        self.min_max.blockSignals(False)
        self.editor.refresh()
