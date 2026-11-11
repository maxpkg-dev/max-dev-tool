"""The installer's window, opened by MaxPkgPackager.mzp after the packager itself is installed.

First page: choose the root folder of a script project; it says what installing does there (a new project, version
1.x that is replaced, the same or another version). Install puts maxpkg-packager.ms into that folder, nothing else.
Second page: a green confirmation and how to use the packager from now on; the main button opens it in the project.
The primary button sits where Build sits in the packager, on the right of the bottom strip.
"""

import os

from .. import DISPLAY_NAME, __version__
from ..core import setup as core_setup
from ..qt_compat import QtCore, QtGui, QtWidgets, Qt
from ..ui_scale import px
from . import controls
from .dialogs import USE_STEPS, how_to_card
from .pages import panel
from .tool_window import ToolWindow

INTRO = ("{name} lives in your script project as one file, `maxpkg-packager.ms`. Choose the root folder of the project "
         "you want to package.").format(name=DISPLAY_NAME)
STATES = {  # What Install does in the chosen folder (core.setup.describe)
    "new": "`maxpkg-packager.ms` is added to this folder. Nothing else changes.",
    "old": ("This project has {name} 1.x. Its file is replaced, and its settings move into the `max-package` folder "
            "when you open the packager.").format(name=DISPLAY_NAME),
    "same": "{name} {version} is already in this project. Install puts a fresh copy.".format(name=DISPLAY_NAME,
                                                                                         version=__version__),
    "other": "This project has {name} {{found}}. It is replaced with {version}.".format(name=DISPLAY_NAME,
                                                                                     version=__version__),
}
KEPT = "Its settings in `max-package` stay as they are: Install never changes them."
WHAT_HAPPENS = (
    "The packager is installed once, in your user profile, and updates itself there.",
    "`maxpkg-packager.ms` goes into the project you choose. Nothing else is added.",
    "You run that file whenever you work on the package. Its settings live in `max-package` next to it.",
)
DONE_NOTE = ("To package another project, choose **Install in another project**, or copy `maxpkg-packager.ms` into "
             "it yourself.")


class SetupWindow(ToolWindow):
    is_setup = True  # Its place and size are not saved as the packager's

    def __init__(self, controller, launcher_source, parent=None):
        ToolWindow.__init__(self, controller, parent)
        self.source = launcher_source
        self.target = ""
        theme = controller.theme
        self.status_label.hide()
        self.stack = QtWidgets.QStackedWidget()
        self.body.addWidget(self.stack, 1)
        self.stack.addWidget(self._choose_page(theme))
        self.stack.addWidget(self._done_page(theme))
        self.action = controls.Button("Install", theme, icon="download", variant="primary",
                                      tooltip="Put maxpkg-packager.ms into this project")
        self.action.clicked.connect(self.on_action)
        self.status_row.insertStretch(0, 1)
        self.status_row.addWidget(self.action)
        controls.unify_heights(self)
        self.resize(px(420), px(560))
        self.folder.setText(controller.prefs.get("setup_folder") or "")
        self.check_folder()

    # ---- pages -------------------------------------------------------------------------------------------------
    def _choose_page(self, theme):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(px(8))
        frame, lay = panel("Your script project", theme, "Where the packager goes",
                           "**One file**: `maxpkg-packager.ms` goes into the root folder of your project.\n\n"
                           "**Settings**: the packager keeps them in a `max-package` folder next to it.\n\n"
                           "**The packager itself** is installed once, in your user profile, and updates there.")
        lay.addWidget(_rich(INTRO, theme))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(6))
        self.folder = QtWidgets.QLineEdit()
        self.folder.setPlaceholderText("Root folder of your script project")
        self.folder.textChanged.connect(lambda *_: self.check_folder())
        row.addWidget(self.folder, 1)
        browse = controls.Button("", theme, icon="folder-open", tooltip="Choose the folder")
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        lay.addLayout(row)
        self.state = QtWidgets.QLabel("")
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.RichText)
        lay.addWidget(self.state)
        layout.addWidget(frame)
        layout.addWidget(how_to_card(theme, WHAT_HAPPENS, title="What happens"))
        layout.addStretch(1)
        return page

    def _done_page(self, theme):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(px(8))
        banner = QtWidgets.QFrame()
        banner.setObjectName("toolSuccess")
        inner = QtWidgets.QVBoxLayout(banner)
        inner.setContentsMargins(px(10), px(6), px(6), px(8))
        inner.setSpacing(px(2))
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(px(6))
        self.done_title = controls.ElidedLabel("")
        self.done_title.setObjectName("toolSuccessTitle")
        head.addWidget(self.done_title, 1)
        show = controls.Button("", theme, icon="folder-open", variant="ghost", tooltip="Show the project folder",
                               icon_role="log_success")
        show.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(os.path.dirname(self.target))))
        head.addWidget(show)
        inner.addLayout(head)
        self.done_path = controls.ElidedLabel("")
        self.done_path.setObjectName("toolSuccessText")
        inner.addWidget(self.done_path)
        layout.addWidget(banner)
        layout.addWidget(how_to_card(theme, USE_STEPS, DONE_NOTE))
        again = QtWidgets.QHBoxLayout()
        another = controls.Button("Install in another project", theme, icon="plus")
        another.clicked.connect(self.another)
        again.addWidget(another)
        again.addStretch(1)
        layout.addLayout(again)
        layout.addStretch(1)
        return page

    # ---- choose ------------------------------------------------------------------------------------------------
    def browse(self):
        start = self.folder.text().strip() or os.path.expanduser("~")
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Root folder of your script project", start)
        if chosen:
            self.folder.setText(os.path.normpath(chosen))

    def check_folder(self):
        folder = self.folder.text().strip()
        problem = core_setup.folder_problem(folder) if folder else ""
        colors = self.controller.theme.colors
        if not folder:
            text, role = "", "muted_text"
        elif problem:
            text, role = problem, "log_error"
        else:
            kind = core_setup.describe(folder)
            found = core_setup.launcher_version(core_setup.launcher_path(folder))
            text = STATES[kind].format(found=found)
            if core_setup.has_settings(folder):  # A project set up before: say plainly that nothing of it changes
                text += "\n\n" + KEPT
            role = "log_warning" if kind == "old" else "muted_text"
        self.state.setText(controls.help_html(text, colors, role) if text else "")
        self.state.setVisible(bool(text))
        self.action.setEnabled(bool(folder) and not problem)

    def on_action(self):
        if self.stack.currentIndex() == 1:
            self.open_packager()
            return
        folder = os.path.abspath(self.folder.text().strip())
        try:
            self.target = core_setup.install_launcher(self.source, folder)
        except (OSError, ValueError) as error:
            self.state.setText(controls.help_html("Not installed: {}".format(error), self.controller.theme.colors,
                                                  "log_error"))
            self.state.show()
            return
        self.controller.set_preference("setup_folder", folder)
        self.done_title.setText("Installed in {}".format(os.path.basename(folder) or folder))
        self.done_path.setText(self.target)
        self.done_path.setToolTip(self.target)
        self.stack.setCurrentIndex(1)
        self._set_action("Open the packager", "box", "Open {} in this project".format(DISPLAY_NAME))

    def _set_action(self, text, icon, tooltip):
        self.action.setText(text)
        self.action.setToolTip(tooltip)
        self.action.icon_name = icon
        self.action._on_theme(self.controller.theme.colors)  # Draws the new icon

    def another(self):
        self.stack.setCurrentIndex(0)
        self._set_action("Install", "download", "Put maxpkg-packager.ms into this project")
        self.folder.selectAll()
        self.folder.setFocus()
        self.check_folder()

    def open_packager(self):
        """Run the launcher that is now in the project: this window closes and the packager opens there."""
        self.controller.open_launcher(self.target)


def _rich(text, theme):
    label = QtWidgets.QLabel(controls.help_html(text, theme.colors, "text"))
    label.setTextFormat(Qt.RichText)
    label.setWordWrap(True)
    return label
