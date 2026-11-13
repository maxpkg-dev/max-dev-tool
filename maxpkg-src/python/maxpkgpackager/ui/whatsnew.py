"""The "Updated" window: what is new, shown once after an update (core/notes.py decides when).

Two forms. After an update of the installed packager: the version it had and the version it has, and the notes of
every version in between. For a project that has just come from version 1.x (whose own plain window announced the
update): the same, and a green block saying what happened to the project's files.
"""

from .. import DISPLAY_NAME, LINKS, __version__
from ..qt_compat import QtWidgets, Qt
from ..ui_scale import pt, px
from . import controls
from .changelog import KindBadge
from .dialogs import HeroDialog, _rich, link_label

MOVED = ("Its settings, changelog and icon moved into the `max-package` folder. Your own files were not touched.\n\n"
         "Run `maxpkg-packager.ms` as before.")
RELEASES_URL = next((address for label, address in LINKS if label == "GitHub"), "")


def version_row(theme, previous, current):
    """The version the user had, an arrow, the version they have now."""
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(0, px(6), 0, 0)
    layout.setSpacing(px(4))
    layout.addWidget(controls.Pill(theme, previous, "neutral"))
    arrow = QtWidgets.QLabel()
    size = px(14)
    arrow.setFixedSize(size, size)
    arrow.setPixmap(controls.icon_pixmap("chevron-right", theme.colors["muted_text"], size,
                                         controls.device_pixel_ratio(row)))
    layout.addWidget(arrow)
    layout.addWidget(controls.Pill(theme, current, "success"))
    layout.addStretch(1)
    return row


def notes_block(theme, version, items, show_version):
    """The notes of one version: its number (when several versions are listed) and a badge and a line per note."""
    block = QtWidgets.QWidget()
    grid = QtWidgets.QGridLayout(block)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(px(10))
    grid.setVerticalSpacing(px(8))
    row = 0
    if show_version:
        caption = controls.muted("Version {}".format(version), wrap=False)
        grid.addWidget(caption, row, 0, 1, 2)
        row += 1
    for kind, body in items:
        grid.addWidget(KindBadge(kind, theme), row, 0, Qt.AlignTop)
        text = _rich(body, theme)
        text.setContentsMargins(0, px(1), 0, 0)  # The first line on the badge's centre line
        grid.addWidget(text, row, 1)
        row += 1
    grid.setColumnStretch(1, 1)
    return block


class UpdateDialog(HeroDialog):
    MIN_HEIGHT = 240

    def __init__(self, controller, parent, found, versions):
        """found: what core.notes.notice() returned; versions: core.notes.to_show() for it."""
        theme = controller.theme
        welcome = found["kind"] == "welcome"
        heading = "Welcome to version 2" if welcome else "Updated to {}".format(__version__)
        under = version_row(theme, "1.x" if welcome else found["previous"], __version__)
        HeroDialog.__init__(self, controller, "{} updated".format(DISPLAY_NAME), parent, heading, under)
        content, buttons = self.body_layout, self.footer_layout
        if welcome:
            banner = QtWidgets.QFrame()
            banner.setObjectName("toolSuccess")
            inner = QtWidgets.QVBoxLayout(banner)
            inner.setContentsMargins(px(12), px(10), px(12), px(12))
            inner.setSpacing(px(6))
            title = QtWidgets.QLabel("Your project is ready")
            title.setObjectName("toolSuccessTitle")
            inner.addWidget(title)
            inner.addWidget(_rich(MOVED, theme))
            content.addWidget(banner)
        if versions:
            heading_label = QtWidgets.QLabel("What is new")
            heading_label.setObjectName("toolSection")
            font = heading_label.font()
            font.setPointSizeF(pt(10))
            heading_label.setFont(font)
            content.addWidget(heading_label)
            for version, items in versions:
                content.addWidget(notes_block(theme, version, items, len(versions) > 1))
        content.addStretch(1)
        if RELEASES_URL:
            buttons.addWidget(link_label(theme, "All versions", RELEASES_URL + "/releases"))
        buttons.addStretch(1)
        done = controls.Button("Got it", theme, icon="check", variant="primary")
        done.clicked.connect(self.close)
        done.setDefault(True)
        buttons.addWidget(done)
        self.fit()
