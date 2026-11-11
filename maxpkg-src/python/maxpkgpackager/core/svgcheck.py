"""Checks of the package icon: a well-formed, safe, square SVG.

The icon is shown inside 3ds Max (buttons, toolbar) and on maxpkg.dev, so it must not carry scripts or references to
other files or sites, and it should be square so it is never stretched or cropped.
"""

import os
import re
import xml.etree.ElementTree as ElementTree

MAX_BYTES = 1024 * 1024  # 1 MB: an icon is a few KB; more means embedded images or a wrong file
LARGE_BYTES = 20 * 1024  # The icons of real MaxPkg packages are 0.4 to 3 KB
SVGOMG_URL = "https://jakearchibald.github.io/svgomg/"
# Data editors leave in exported SVG files: not needed by an icon, removed by SVGOMG.
EDITOR_MARKERS = (("inkscape", "Inkscape data"), ("sodipodi", "Inkscape data"), ("adobe", "Illustrator data"),
                  ("illustrator", "Illustrator data"), ("xmlns:i=", "Illustrator data"), ("xmpmeta", "XMP metadata"),
                  ("xmlns:serif", "Affinity data"), ("sketch", "Sketch data"), ("figma", "Figma data"),
                  ("<metadata", "metadata"), ("<!--", "comments"), ("xml:space", "xml:space"),
                  ("enable-background", "enable-background"))
BLOCKED_TAGS = {"script", "foreignobject", "iframe", "embed", "object", "audio", "video", "handler", "listener"}
_NUMBER = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(px)?\s*$")


class SvgReport(object):
    def __init__(self):
        self.errors = []  # The icon cannot be used
        self.warnings = []  # Usable, but it will not look right or carries what an icon does not need
        self.extras = []  # Editor leftovers found; SVGOMG removes them
        self.width = self.height = None

    @property
    def needs_cleanup(self):
        return bool(self.extras)

    @property
    def ok(self):
        return not self.errors

    def summary(self):
        if self.errors:
            return self.errors[0]
        size = "{:g} x {:g}".format(self.width, self.height) if self.width else "size unknown"
        if self.warnings:
            return "{} ({})".format(self.warnings[0], size)
        return "Square SVG, {}, clean".format(size)


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _number(value):
    found = _NUMBER.match(value or "")
    return float(found.group(1)) if found else None


def inspect(path):
    report = SvgReport()
    if not path or not os.path.isfile(path):
        report.errors.append("The SVG icon file does not exist")
        return report
    if not path.lower().endswith(".svg"):
        report.errors.append("The icon must be an .svg file")
        return report
    size = os.path.getsize(path)
    if size == 0:
        report.errors.append("The SVG icon file is empty")
        return report
    if size > MAX_BYTES:
        report.errors.append("The SVG icon is larger than 1 MB")
        return report
    with open(path, "rb") as handle:
        raw = handle.read()
    if b"\x00" in raw:
        report.errors.append("The icon is not a text SVG file")
        return report
    lowered = raw.lower()
    text_lower = lowered.decode("utf-8", "ignore")
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        report.errors.append("The SVG must not contain DOCTYPE or ENTITY declarations")
        return report
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        report.errors.append("The SVG is not valid XML ({})".format(error))
        return report
    if _local(root.tag) != "svg":
        report.errors.append("The file's root element is not <svg>")
        return report

    for element in root.iter():
        tag = _local(element.tag)
        if tag in BLOCKED_TAGS:
            report.errors.append("The SVG contains <{}>, which is not allowed in an icon".format(tag))
            break
        for name, value in element.attrib.items():
            attribute = _local(name)
            text = (value or "").strip().lower()
            if attribute.startswith("on"):
                report.errors.append("The SVG contains a script attribute ({})".format(attribute))
                break
            if "javascript:" in text:
                report.errors.append("The SVG contains a javascript: link")
                break
            if attribute == "href" and text and not text.startswith("#") and not text.startswith("data:image/"):
                report.errors.append("The SVG refers to another file or site ({}); embed everything".format(value[:60]))
                break
            if attribute == "style" and ("url(http" in text or "@import" in text):
                report.errors.append("The SVG style loads something from outside")
                break
        if report.errors:
            break
        if tag == "image":
            report.warnings.append("The SVG contains an embedded raster image; a vector icon stays sharper")
    if report.errors:
        return report

    view_box = [part for part in re.split(r"[\s,]+", root.get("viewBox", "").strip()) if part]
    if len(view_box) == 4 and all(_number(part) is not None for part in view_box):
        report.width, report.height = _number(view_box[2]), _number(view_box[3])
    else:
        report.width, report.height = _number(root.get("width")), _number(root.get("height"))
    if not report.width or not report.height:
        report.width = report.height = None
        report.warnings.append("The SVG has no viewBox; add one, for example viewBox=\"0 0 64 64\"")
    elif abs(report.width - report.height) > 0.01 * max(report.width, report.height):
        report.warnings.append("The icon is not square; it will look stretched or cropped")
    for marker, label in EDITOR_MARKERS:
        if marker in text_lower and label not in report.extras:
            report.extras.append(label)
    if size > LARGE_BYTES:
        report.extras.append("{} KB of data (an icon is a few KB)".format(size // 1024))
    if report.extras:
        report.warnings.append("The SVG carries extra data ({})".format(
            ", ".join(report.extras)))
    return report
