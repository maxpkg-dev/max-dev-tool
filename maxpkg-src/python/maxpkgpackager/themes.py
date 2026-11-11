"""Theme palettes: load, validate, resolve and render QSS.

Pure code. Palettes are editable JSON files in assets/themes. Values are "#rrggbb",
{"mix": [left, right, ratio]} or "$nativeRole" (a 3ds Max colorMan sample, with a fallback
stored in the file). Widgets never use literal colors; they use the role names below.
"""

import json
import math
import os
import re

DEFAULT_THEME = "graphite"
_HEX = re.compile(r"#[0-9a-fA-F]{6}$")
_TOKEN = re.compile(r"@([a-z][a-z0-9_]*)")

# Palette keys every theme must define (the skill's 83-role files define all of them).
REQUIRED_KEYS = (
    "window_background", "button_background", "field_background", "recessed_background",
    "dropdown_background", "header_background", "tab_pane_background", "active_tab_background",
    "tooltip_background", "text", "muted_text", "selected_text", "disabled_text", "field_text",
    "heading_text", "tooltip_text", "accent", "border", "field_border", "group_border",
    "active_border", "button_hover", "selection_background", "focus_border", "disabled_border",
    "log_info", "log_success", "log_warning", "log_error", "support_link", "scrollbar_thumb",
    "scrollbar_hover", "checkbox_border", "checkbox_hover_border", "delete_background",
    "delete_hover", "delete_pressed", "delete_text", "delete_border", "donate_background",
    "donate_hover", "donate_border",
)

# Semantic aliases used in QSS and code, mapped to palette keys.
ALIASES = {
    "window": "window_background",
    "surface": "button_background",
    "field": "field_background",
    "recessed": "recessed_background",
    "popup": "dropdown_background",
    "hover": "button_hover",
    "selected": "selection_background",
    "focus": "focus_border",
    "pressed": "selection_background",
    "link": "support_link",
    "link_hover": "accent",
    "success": "log_success",
    "warning": "log_warning",
    "danger_text_status": "log_error",
    "danger": "delete_background",
    "danger_hover": "delete_hover",
    "danger_pressed": "delete_pressed",
    "danger_text": "delete_text",
    "scroll_track": "recessed_background",
    "scroll_thumb": "scrollbar_thumb",
    "scroll_hover": "scrollbar_hover",
    "scroll_pressed": "text",
    "disabled_surface": "button_background",
}


class ThemeError(ValueError):
    pass


def theme_dir(root):
    return os.path.join(root, "assets", "themes")


def list_themes(root):
    """[(theme_id, display_name)] for every readable palette file, Warm Graphite first."""
    folder = theme_dir(root)
    found = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        theme_id = name[:-5]
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
                display = json.load(handle).get("name") or theme_id
        except (OSError, ValueError):
            continue
        found.append((theme_id, display))
    found.sort(key=lambda item: (item[0] != DEFAULT_THEME, item[1].lower()))
    return found


def load_document(root, theme_id):
    """Read a palette file by id. Ids are plain names; paths are never accepted."""
    if not re.match(r"^[a-z0-9_-]+$", theme_id or ""):
        raise ThemeError("Invalid theme id: {!r}".format(theme_id))
    path = os.path.join(theme_dir(root), theme_id + ".json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        raise ThemeError("Cannot read theme '{}': {}".format(theme_id, error))
    except ValueError as error:
        raise ThemeError("Theme '{}' is not valid JSON: {}".format(theme_id, error))
    validate(document)
    return document


def validate(document):
    if not isinstance(document, dict) or not isinstance(document.get("colors"), dict):
        raise ThemeError("Theme must be an object with a 'colors' object.")
    if not isinstance(document.get("name"), str) or not document["name"].strip():
        raise ThemeError("Theme needs a non-empty 'name'.")
    missing = [key for key in REQUIRED_KEYS if key not in document["colors"]]
    if missing:
        raise ThemeError("Theme is missing colors: " + ", ".join(missing))
    fallbacks = document.get("colorMan", {})
    if not isinstance(fallbacks, dict) or any(not _HEX.match(str(v)) for v in fallbacks.values()):
        raise ThemeError("Theme 'colorMan' fallbacks must be #rrggbb values.")
    overrides = document.get("light_colors", {})
    if not isinstance(overrides, dict) or any(key not in document["colors"] for key in overrides):
        raise ThemeError("Theme 'light_colors' may only override existing colors.")


def _channels(value):
    return [int(value[i:i + 2], 16) for i in (1, 3, 5)]


def mix(left, right, ratio):
    a, b = _channels(left), _channels(right)
    # int(x + 0.5) rounds half up on both 3.7 and 3.13, unlike round() banker's rounding.
    return "#" + "".join("{:02x}".format(int(x * (1 - ratio) + y * ratio + 0.5)) for x, y in zip(a, b))


def resolve(document, native_colors=None):
    """Return {key: "#rrggbb"} for every palette key plus every alias."""
    validate(document)
    colors = document["colors"]
    fallbacks = document.get("colorMan", {})
    native_colors = native_colors or {}

    def value_of(value, depth=0):
        if depth > 8:
            raise ThemeError("Theme color expression is nested too deeply.")
        if isinstance(value, str):
            if _HEX.match(value):
                return value.lower()
            if value.startswith("$"):
                key = value[1:]
                if key not in fallbacks:
                    raise ThemeError("Unknown native color: " + key)
                return value_of(native_colors.get(key, fallbacks[key]), depth + 1)
        if isinstance(value, dict) and set(value) == {"mix"}:
            parts = value["mix"]
            if isinstance(parts, list) and len(parts) == 3:
                left, right, ratio = parts
                if type(ratio) in (int, float) and math.isfinite(ratio) and 0 <= ratio <= 1:
                    return mix(value_of(left, depth + 1), value_of(right, depth + 1), ratio)
        raise ThemeError("Invalid theme color expression: {!r}".format(value))

    result = {key: value_of(value) for key, value in colors.items()}
    if fallbacks:
        # Host-color themes switch status colors when Max uses a light UI.
        red, green, blue = _channels(result["field_background"])
        if 0.2126 * red + 0.7152 * green + 0.0722 * blue > 150:
            result.update({key: value_of(value) for key, value in document.get("light_colors", {}).items()})
    for alias, key in ALIASES.items():
        result.setdefault(alias, result[key])
    return result


def derived(colors):
    """Colours computed from the palette. A disabled coloured button (primary, danger) is a darker shade of its own
    colour with text and icon in a lighter shade of it: colour is never mixed with grey."""
    base = colors["tab_pane_background"]
    return {
        "accent_disabled": mix(base, colors["accent"], 0.30),
        "accent_disabled_border": mix(base, colors["accent"], 0.45),
        "accent_disabled_text": colors["accent"],
        "danger_disabled": mix(base, colors["danger"], 0.40),
        "danger_disabled_border": mix(base, colors["delete_border"], 0.40),
        "danger_disabled_text": colors["delete_border"],
    }


def render(template, colors):
    """Replace @role tokens. Unknown roles raise KeyError on purpose."""
    return _TOKEN.sub(lambda match: colors[match.group(1)], template)
