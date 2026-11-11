"""Applies one palette to every MaxPkg Packager-owned window and notifies painted controls.

Selection is transactional: a broken palette file leaves the previous theme active and is reported.
"""

import hashlib
import os

from .. import logs, resources, settings, themes, ui_scale
from ..qt_compat import QtWidgets, inherit_fonts, is_valid, scale_font

_log = logs.get("theme")
# Icons referenced from QSS must be files; tinted copies live in the user data folder.
_QSS_ICONS = {
    "icon_check": ("check", "log_badge_text"),
    "icon_check_disabled": ("check", "disabled_text"),
    "icon_minus": ("minus", "log_badge_text"),  # Partly checked groups.
    "icon_minus_disabled": ("minus", "disabled_text"),
    "icon_chevron_down": ("chevron-down", "text"),
    "icon_chevron_down_disabled": ("chevron-down", "disabled_text"),
}
_NATIVE_KEYS = ("background", "window", "text", "windowText", "shadow", "hilight", "itemHilight",
                "hilightText", "rollupTitleFace", "rollupTitleText")


def sample_max_colors():
    """Current 3ds Max UI colors from colorMan (main thread only); {} outside Max."""
    try:
        from pymxs import runtime as rt
    except ImportError:
        return {}
    sampled = {}
    for key in _NATIVE_KEYS:
        try:
            value = rt.colorMan.getColor(rt.Name(key))
            sampled[key] = "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c * 255))))
                                                         for c in (value.x, value.y, value.z)))
        except Exception:
            continue  # Unknown key in this Max version: the palette fallback is used.
    return sampled


def tinted_svg(name, color):
    with open(resources.require(resources.icon_path(name)), "r", encoding="utf-8") as handle:
        return handle.read().replace("currentColor", color)


class ThemeManager(object):
    def __init__(self, root, prefs):
        self.root = root
        self.prefs = prefs
        self.theme_id = None
        self.colors = {}
        self.windows = []
        self.listeners = []
        with open(resources.require(resources.ui_file("style.qss")), "r", encoding="utf-8") as handle:
            self.template = handle.read()
        self.stylesheet = ""

    # Registration -------------------------------------------------------------------------------
    def register(self, window):
        if window not in self.windows:
            self.windows.append(window)
        window.setStyleSheet(self.stylesheet)
        scale_font(window)  # Top-level windows do not inherit the font: interface size per window.
        inherit_fonts(window)

    def unregister(self, window):
        if window in self.windows:
            self.windows.remove(window)

    def subscribe(self, callback):
        self.listeners.append(callback)

    def unsubscribe(self, callback):
        if callback in self.listeners:
            self.listeners.remove(callback)

    def color(self, role):
        return self.colors[role]

    # Loading ------------------------------------------------------------------------------------
    def _build(self, theme_id):
        document = themes.load_document(self.root, theme_id)
        native = sample_max_colors() if "colorMan" in document else {}
        colors = themes.resolve(document, native)
        colors.update(themes.derived(colors))
        colors.update(self._write_qss_icons(theme_id, colors))
        return colors, ui_scale.scale_sheet(themes.render(self.template, colors))  # Interface size.

    def _write_qss_icons(self, theme_id, colors):
        digest = hashlib.sha1(repr(sorted(colors.items())).encode("utf-8")).hexdigest()[:10]
        folder = os.path.join(settings.user_data_dir(), "runtime", "icons", theme_id + "-" + digest)
        os.makedirs(folder, exist_ok=True)
        paths = {}
        for token, (name, role) in _QSS_ICONS.items():
            path = os.path.join(folder, token + ".svg")
            if not os.path.isfile(path):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(tinted_svg(name, colors[role]))
            paths[token] = path.replace("\\", "/")  # QSS url() needs forward slashes.
        return paths

    def load_initial(self):
        wanted = self.prefs.get("theme") or themes.DEFAULT_THEME
        try:
            self.colors, self.stylesheet = self._build(wanted)
            self.theme_id = wanted
        except (themes.ThemeError, OSError) as error:
            _log.warning("Saved theme %r unusable (%s); using %s", wanted, error, themes.DEFAULT_THEME)
            self.colors, self.stylesheet = self._build(themes.DEFAULT_THEME)
            self.theme_id = themes.DEFAULT_THEME

    def select(self, theme_id):
        """Apply a theme everywhere. Returns an error string, or None on success."""
        try:
            colors, stylesheet = self._build(theme_id)
        except (themes.ThemeError, OSError, KeyError) as error:
            _log.warning("Theme %s rejected: %s", theme_id, error)
            return "Theme could not be loaded: {}".format(error)
        previous = (self.theme_id, self.colors, self.stylesheet)
        self.theme_id, self.colors, self.stylesheet = theme_id, colors, stylesheet
        try:
            self._apply()
        except Exception as error:
            _log.exception("Applying theme %s failed", theme_id)
            self.theme_id, self.colors, self.stylesheet = previous
            self._apply()
            return "Theme could not be applied: {}".format(error)
        self.prefs.set("theme", theme_id)
        try:
            self.prefs.save()
        except OSError as error:
            return "Theme applied but not saved: {}".format(error)
        return None

    def _apply(self):
        live = [window for window in self.windows if is_valid(window)]
        self.windows = live
        for window in live:
            window.setUpdatesEnabled(False)
        try:
            for window in live:
                window.setStyleSheet(self.stylesheet)
                inherit_fonts(window)  # The new sheet re-polishes the widgets: they get the interface size back
            for callback in list(self.listeners):
                callback(self.colors)
        finally:
            for window in live:
                window.setUpdatesEnabled(True)
                QtWidgets.QWidget.update(window)

    def dispose(self):
        self.listeners = []
        self.windows = []
