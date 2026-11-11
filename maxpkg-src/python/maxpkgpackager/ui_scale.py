"""Interface size: one factor for every size in MaxPkg Packager's windows.

3ds Max turns Qt's own high-DPI scaling off (QT_ENABLE_HIGHDPI_SCALING=0), so sizes written in pixels never grow
on large screens and only point-size fonts follow Windows scaling. MaxPkg Packager picks a target scale at start-up -
the larger of Windows (or Max) scaling and a step for the screen's resolution - and multiplies its pixel sizes
(style sheet, sizes set in code) and font sizes by what Qt does not scale already. Pure code: the
window code passes in what it measured.
"""

import re

# Screen size steps for "auto" (physical pixels against Full HD, the smaller of the two ratios): (below, scale).
STEPS = ((1.15, 1.0), (1.6, 1.25), (2.4, 1.5))
LARGEST = 2.0  # 5K and above.
CHOICES = (1.0, 1.25, 1.5, 1.75, 2.0)  # Settings > Interface size, besides "auto".

# The factors in use (set once at start-up by `apply`): target = how much larger than at 100 % on Full HD,
# px = factor for sizes written in pixels, font = factor for sizes written in points.
current = {"target": 1.0, "px": 1.0, "font": 1.0, "auto": 1.0}


def resolution_step(width, height):
    """Scale for a screen of `width` x `height` physical pixels: 1.0 up to Full HD, 1.25 for 2K, 1.5 for 4K."""
    ratio = min(width / 1920.0, height / 1080.0)
    for below, scale in STEPS:
        if ratio < below:
            return scale
    return LARGEST


def auto_target(width, height, windows_scale=1.0, host_scale=None):
    """The target for "auto": Windows / Max scaling or the resolution step, whichever is larger."""
    return max(resolution_step(width, height), windows_scale or 1.0, host_scale or 1.0)


def apply(width, height, qt_ratio=1.0, dpi_scale=1.0, host_scale=None, choice="auto"):
    """Set `current` for a screen of `width` x `height` logical pixels.

    `qt_ratio`: the screen's device pixel ratio (Qt's own scaling, 1 inside Max); `dpi_scale`: logical DPI / 96
    (what point sizes already follow); `host_scale`: 3ds Max's UI scale; `choice`: "auto" or one of CHOICES.
    """
    qt_ratio = qt_ratio or 1.0
    dpi_scale = dpi_scale or 1.0
    windows_scale = dpi_scale * qt_ratio
    auto = auto_target(width * qt_ratio, height * qt_ratio, windows_scale, host_scale)
    try:
        target = float(choice)
    except (TypeError, ValueError):
        target = auto
    target = max(0.5, min(3.0, target))
    current.update(target=target, auto=auto, px=max(0.5, target / qt_ratio),
                   font=max(0.5, target / windows_scale))
    return dict(current)


def px(value):
    """A size in pixels at the current scale (0 and negative "defaults" stay as they are)."""
    if value <= 0:
        return value
    return max(1, int(round(value * current["px"])))


def pt(value):
    """A font size in points at the current scale."""
    return value * current["font"]


_PX = re.compile(r"(?<![\w.#-])(\d+(?:\.\d+)?)px\b")
_PT = re.compile(r"(?<![\w.#-])(\d+(?:\.\d+)?)pt\b")


def _number(value):
    return "{:g}".format(round(value, 2))


def scale_sheet(sheet, px_factor=None, font_factor=None):
    """A style sheet with every "Npx" and "Npt" size scaled (borders of 1 px stay at least 1 px)."""
    px_factor = current["px"] if px_factor is None else px_factor
    font_factor = current["font"] if font_factor is None else font_factor
    if px_factor != 1.0:
        sheet = _PX.sub(lambda m: "{}px".format(
            0 if float(m.group(1)) == 0 else max(1, int(round(float(m.group(1)) * px_factor)))), sheet)
    if font_factor != 1.0:
        sheet = _PT.sub(lambda m: "{}pt".format(_number(float(m.group(1)) * font_factor)), sheet)
    return sheet


def percent(scale):
    return "{}%".format(int(round(scale * 100)))
