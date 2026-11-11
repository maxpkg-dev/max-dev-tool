"""Minimal INI reader/writer compatible with the files 3ds Max writes (UTF-16 LE with BOM, CRLF).

The project files of the previous MaxScript packager (maxpkg-packager.ini, maxpkg-changelog.ini) are read and
written in exactly this format, so a project can move between the old and the new packager.
"""

import os
import tempfile


def decode_bytes(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


class IniFile(object):
    """Ordered sections of ordered keys. Key lookup is case-insensitive like getINISetting."""

    def __init__(self):
        self.sections = {}  # lower section name -> (display name, {lower key: (display key, value)})
        self.order = []

    @classmethod
    def read(cls, path):
        ini = cls()
        if not os.path.isfile(path):
            return ini
        with open(path, "rb") as handle:
            text = decode_bytes(handle.read())
        section = None
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1]
                ini._section(section)
            elif section is not None and "=" in line:
                key, value = line.split("=", 1)
                ini.set(section, key.strip(), value)
        return ini

    def _section(self, name):
        lowered = name.lower()
        if lowered not in self.sections:
            self.sections[lowered] = (name, {})
            self.order.append(lowered)
        return self.sections[lowered][1]

    def has_section(self, name):
        return name.lower() in self.sections

    def get(self, section, key, default=""):
        entry = self.sections.get(section.lower())
        if entry is None:
            return default
        found = entry[1].get(key.lower())
        return default if found is None else found[1]

    def set(self, section, key, value):
        self._section(section)[key.lower()] = (key, str(value))

    def delete_section(self, name):
        lowered = name.lower()
        if lowered in self.sections:
            del self.sections[lowered]
            self.order.remove(lowered)

    def section_names(self):
        return [self.sections[lowered][0] for lowered in self.order]

    def to_text(self):
        lines = []
        for lowered in self.order:
            name, values = self.sections[lowered]
            lines.append("[{}]".format(name))
            for key, value in values.values():
                lines.append("{}={}".format(key, value))
            lines.append("")
        return "\r\n".join(lines)

    def write(self, path):
        """Atomic write: the old file stays intact if anything fails."""
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".ini-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(b"\xff\xfe" + self.to_text().encode("utf-16-le"))
            os.replace(temporary, path)
        except BaseException:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise


def escape_value(text):
    """Multi-line text on one INI line, as the old packager did."""
    return (text or "").strip().replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def unescape_value(text):
    return (text or "").replace("\\n", "\n")
