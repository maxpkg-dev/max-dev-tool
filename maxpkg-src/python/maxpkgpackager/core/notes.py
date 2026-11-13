"""Release notes of the packager and when to show them (no Qt).

The notes of every version are kept in assets/release-notes.json, which release.py fills from the launcher's header
at each release. The "Updated" window (ui/whatsnew.py) shows them once after an update: to someone whose project
came from version 1.x, and to someone whose installed copy moved to a newer version.
"""

import json
import os
import re

from .project import CHANGELOG_TYPES
from .updater import is_newer

# <app>/python/maxpkgpackager/core/notes.py: an installed version (v<version>) or maxpkg-src in the repository
_APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HISTORY_FILE = os.path.join(_APP, "assets", "release-notes.json")
FIRST_VERSION_2 = "2.0.0"  # Its notes say what version 2 is: shown to everyone who comes from 1.x

_SECTION = re.compile(r"^\[(\d+\.\d+\.\d+)\]\s*$")
_PREFIX = re.compile(r"^[+*\-]+\s*")
_KIND = re.compile(r"^(" + "|".join(CHANGELOG_TYPES) + r")\s*:\s*(.+)$", re.I)
_PREFIX_KINDS = (("** ", "Improved"), ("* ", "Changed"), ("+ ", "Added"), ("- ", "Fixed"))


def parse_line(line):
    """("Added", "text") of one note as the launcher's header has it: "+ Added: text=" (the "=" is for the INI
    reader of packager 1.x)."""
    line = (line or "").strip().rstrip("=").strip()
    kind = next((name for prefix, name in _PREFIX_KINDS if line.startswith(prefix)), "Changed")
    line = _PREFIX.sub("", line)
    found = _KIND.match(line)
    if found:
        kind, line = found.group(1).capitalize(), found.group(2).strip()
    return kind, line


def header_sections(text):
    """{version: [note line, ...]} of the version sections in a launcher's header (up to [SCRIPT]), lines as written
    but without the closing "="."""
    sections, current = {}, None
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line == "[SCRIPT]":
            break
        found = _SECTION.match(line)
        if found:
            current = sections.setdefault(found.group(1), [])
        elif line.startswith("["):
            current = None
        elif current is not None and line:
            current.append(line.rstrip("=").strip())
    return sections


def history(path=None):
    """{version: [(kind, text), ...]} of every version whose notes are known; {} when the file is missing or broken."""
    try:
        with open(path or HISTORY_FILE, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(stored, dict):
        return {}
    return {version: [parse_line(line) for line in lines if str(line).strip()]
            for version, lines in stored.items() if isinstance(lines, list)}


def _key(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (0,)


def notice(current, seen="", previous="", migrated=False):
    """What to tell the user at this start, or None: {"kind": "welcome"} for a project that has just come from
    version 1.x, {"kind": "update", "previous": "2.0.1"} when this copy is newer than the last one the user saw.

    seen: the version stored in the settings when the window was last decided on ("" before 2.0.2, which did not
    store it); previous: the version the installed copy replaced (current.json), which covers those copies."""
    if migrated:
        return {"kind": "welcome", "previous": ""}
    before = seen or previous
    if before and is_newer(current, before):
        return {"kind": "update", "previous": before}
    return None


def to_show(current, found, notes=None):
    """[(version, [(kind, text), ...]), ...], newest first, for a notice from notice(): the versions after the one the
    user had, or, coming from 1.x, what version 2 is and the current version."""
    notes = history() if notes is None else notes
    if found["kind"] == "welcome":
        versions = [version for version in (current, FIRST_VERSION_2) if version in notes]
        versions = sorted(set(versions), key=_key, reverse=True)
    else:
        versions = sorted((version for version in notes
                           if is_newer(version, found["previous"]) and not is_newer(version, current)),
                          key=_key, reverse=True)
    return [(version, notes[version]) for version in versions if notes[version]]
