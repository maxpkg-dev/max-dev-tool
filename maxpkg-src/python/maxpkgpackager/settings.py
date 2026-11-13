"""Durable user preferences stored as JSON outside the (possibly read-only) install folder.

Pure code. Unknown keys from newer versions are preserved; a value whose type differs from its default falls back to
the default (store an interface size as text, "1.25", like the default "auto").
"""

import json
import os
import tempfile

from . import TOOL_NAME

DEFAULTS = {
    "theme": "graphite",
    "last_developer": "",  # Prefilled into new projects.
    "last_license": "",
    "auto_update": True,  # Check for a new version at start and install it in the background.
    "ui_scale": "auto",  # Interface size: "auto" (screen and Windows / Max scaling) or a factor as text, "1.25".
    "seen_version": "",  # The version whose "Updated" window was decided on; a newer one shows what is new, once.
    "window_geometry": "",  # saveGeometry() of the full window, base64.
    "mini_position": [],  # [x, y] of the collapsed bar when the user last moved it; [] = active viewport corner.
}


def user_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, TOOL_NAME)


class Settings(object):
    def __init__(self, path=None):
        self.path = path or os.path.join(user_data_dir(), "settings.json")
        self.values = dict(DEFAULTS)
        self.overrides = {}  # Session-only values (tests, fixtures); never written by save().
        self.load_error = None

    def load(self):
        self.values = dict(DEFAULTS)
        self.load_error = None
        if not os.path.isfile(self.path):
            return self
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if not isinstance(stored, dict):
                raise ValueError("settings root is not an object")
        except (OSError, ValueError) as error:
            self.load_error = str(error)
            return self
        for key, value in stored.items():
            default = DEFAULTS.get(key)
            if key in DEFAULTS and default is not None and type(value) is not type(default):
                continue  # Wrong type: keep the default instead of crashing later.
            self.values[key] = value
        return self

    def get(self, key):
        if key in self.overrides:
            return self.overrides[key]
        return self.values.get(key, DEFAULTS.get(key))

    def override(self, key, value):
        """Use a value for this session only; save() keeps writing the user's own value."""
        self.overrides[key] = value

    def set(self, key, value):
        if key in self.overrides:
            self.overrides[key] = value  # Session-only (tests, fixtures): never reaches the settings file.
        else:
            self.values[key] = value

    def save(self):
        """Write atomically. Raises OSError so callers can report an unsaved preference."""
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(self.values, stream, indent=2, sort_keys=True)
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise
