"""Project model and the pure rules around it (paths, names, build path remap, extra macros)."""

import datetime
import hashlib
import os
import re
import uuid

LICENSES = ("Free", "Shareware", "Commercial", "Open source", "Trial")
CHANNELS = ("stable", "alpha", "beta")
CHANNEL_HELP = ("**Stable**: the release for everyone, in the MaxPkg Manager catalog inside 3ds Max and on "
                "maxpkg.dev.\n\n"
                "**Beta** and **Alpha**: test versions. They are only on maxpkg.dev, marked as not recommended, and "
                "never in the Manager catalog.\n\n"
                "Use them to let testers try a version before it becomes Stable.")  # Help markup: ui.controls.help_html
CHANNEL_WARNING = ("{} versions are not shown in the MaxPkg Manager catalog; they are only on maxpkg.dev and not "
                   "recommended for download. Choose Stable for a release for everyone")
CHANGELOG_TYPES = ("Added", "Fixed", "Changed", "Removed", "Improved")
PURCHASE_LABELS = ("Buy", "Purchase", "Get license", "Donate", "Support", "Sponsor")
ENTRY_EXTENSIONS = (".ms", ".mse", ".py")
SAFE_DISPLAY = re.compile(r"^[A-Za-z0-9 _-]+$")
SAFE_MACRO_TITLE = re.compile(r"^[A-Za-z _]+$")
GUID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SUPPORT_DIR = "max-package"  # Everything the packager keeps in a project lives in this one folder.
SETTINGS_FILE = "project.ini"
CHANGELOG_FILE = "changelog.ini"
ICON_FILE = "icon.svg"
# Where the MaxScript packager (1.x) kept these files, next to the launcher. They are moved on first open.
LEGACY_FILES = {"maxpkg-packager.ini": SETTINGS_FILE, "maxpkg-changelog.ini": CHANGELOG_FILE,
                "maxpkg-icon.svg": ICON_FILE, "_install.ms": "_install.ms", "_uninstall.ms": "_uninstall.ms"}
HOOK_FILES = ("_install.ms", "_uninstall.ms")
SUPPORT_FILES = {"maxpkg-packager.ms", "maxpkg-packager.ini", "maxpkg-changelog.ini", "maxpkg-button.mcr", "mzp.run",
                 "mzp.run.ms", "maxpkg-quad.ms", "_install.ms", "_uninstall.ms"}


def norm(path):
    """Windows separators, the form every path takes inside a project and manifest."""
    return (path or "").replace("/", "\\")


_HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
URL_FIELDS = (("license_url", "License URL"), ("documentation", "Documentation URL"), ("homepage", "Homepage URL"),
              ("purchase", "Purchase URL"))


def url_problem(text):
    """None for an empty or valid web link, else what is wrong with it (links are optional)."""
    from urllib.parse import urlsplit
    text = (text or "").strip()
    if not text:
        return None
    if any(char.isspace() for char in text):
        return "must not contain spaces"
    try:
        parts = urlsplit(text)
    except ValueError:
        return "is not a web address"
    if parts.scheme.lower() not in ("http", "https"):
        return "must start with https://"
    host = (parts.hostname or "")
    if not _HOST.match(host):
        return "needs a site name like example.com"
    return None


def complete_url(text):
    """'example.com/page' -> 'https://example.com/page'; anything else unchanged."""
    text = (text or "").strip()
    if text and "://" not in text and not any(char.isspace() for char in text) and \
            _HOST.match(text.split("/", 1)[0].split(":", 1)[0]):
        return "https://" + text
    return text


def max_year_plus_one():
    return datetime.date.today().year + 1


MIN_MAX_YEAR = 2022  # MaxPkg runs on 3ds Max 2022 and newer (its installer needs the embedded Python 3.7+)


def max_years():
    return [str(year) for year in range(MIN_MAX_YEAR, max_year_plus_one() + 1)]


def clamp_min_max(text):
    """A usable "Min 3ds Max" value: a year from 2022 to next year; older or broken values become 2022."""
    try:
        year = int(str(text).strip())
    except ValueError:
        return str(MIN_MAX_YEAR)
    return str(max(MIN_MAX_YEAR, min(year, max_year_plus_one())))


_PREFIXES = (("** ", "Improved"), ("* ", "Changed"), ("+ ", "Added"), ("- ", "Fixed"))
_KIND_WORD = re.compile(r"^(Added|Fixed|Changed|Removed|Improved)\s*:\s*(.+)$", re.I)


def parse_changelog_line(line, default_kind="Added"):
    """(type, text) of a typed or pasted line: "+ text" Added, "- " Fixed, "* " Changed, "** " Improved (the
    release-note prefixes), or "Fixed: text"; anything else gets `default_kind`."""
    line = (line or "").strip()
    for prefix, kind in _PREFIXES:
        if line.startswith(prefix):
            return kind, line[len(prefix):].strip()
    found = _KIND_WORD.match(line)
    if found:
        return found.group(1).capitalize(), found.group(2).strip()
    return default_kind if default_kind in CHANGELOG_TYPES else "Added", line


def new_guid():
    return str(uuid.uuid4())


def is_valid_guid(text):
    return bool(GUID_PATTERN.match((text or "").strip()))


def is_safe_display(text):
    return bool(SAFE_DISPLAY.match(text or ""))


def package_slug(name):
    slug, previous_dash = "", False
    for char in (name or "").strip().lower():
        if char in " -":
            if not previous_dash and slug:
                slug += "-"
                previous_dash = True
        elif char in "abcdefghijklmnopqrstuvwxyz0123456789_":
            slug += char
            previous_dash = False
    return slug.rstrip("-") or "package"


def parse_version(text):
    parts = (text or "").strip().split(".")
    if len(parts) != 3:
        return (1, 0, 0)
    try:
        numbers = tuple(int(part) for part in parts)
    except ValueError:
        return (1, 0, 0)
    if any(number < 0 or number > 999 for number in numbers):
        return (1, 0, 0)
    return numbers


def version_text(version):
    return "{}.{}.{}".format(*version)


def is_safe_relative(path):
    path = norm(path)
    if not path or ":" in path or path.startswith("\\") or path.startswith("..") or "\\.." in path:
        return False
    return True


def normalize_rule_folder(folder, allow_root=False):
    folder = norm(folder).strip()
    if folder in ("/", "\\"):
        folder = ""
    return folder.strip("\\")


def is_safe_rule_folder(folder, allow_root=False):
    folder = normalize_rule_folder(folder, allow_root)
    if folder == "":
        return allow_root
    return ":" not in folder and not folder.startswith("..") and "\\.." not in folder


def compiled_path(path):
    path = norm(path)
    return os.path.splitext(path)[0] + ".mse"


def stable_guid(seed):
    """Same value the MaxScript packager produced: MD5 of the UTF-8 text as a little-endian .NET Guid."""
    return str(uuid.UUID(bytes_le=hashlib.md5(seed.encode("utf-8")).digest()))


class MacroItem(object):
    """An extra macro button running another script of the package."""

    def __init__(self, file, button, compile=False, quad=False):
        self.file = norm(file)
        self.button = button
        self.compile = bool(compile) and self.file.lower().endswith(".ms")
        self.quad = bool(quad)

    @property
    def identifier(self):
        return self.button.strip().replace(" ", "") or "Macro"


class Release(object):
    """Per-version data: date, channel, minimum 3ds Max and the changelog."""

    def __init__(self):
        self.date = datetime.date.today().isoformat()
        self.channel = "stable"
        self.min_max = str(MIN_MAX_YEAR)
        self.changelog = []  # [(type, text)]


class Project(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.package_name = ""
        self.button_name = ""
        self.guid = ""
        self.description = ""
        self.developer = ""
        self.license = ""
        self.license_url = ""
        self.documentation = ""
        self.homepage = ""
        self.purchase = ""
        self.purchase_label = "Buy"
        self.create_button = True
        self.show_toolbar = True
        self.custom_install = ""
        self.custom_uninstall = ""
        self.output_folder = os.path.join(self.support_dir, "dist")
        self.svg_icon = ""
        self.entry = ""
        self.compile_entry = True  # On for a new project: a .mse is not secure, but it stops plain copying of the code
        self.version = "1.0.0"
        self.files = []  # [(absolute path, relative path)]
        self.rules = []  # [(source folder, target folder)]
        self.macros = []  # [MacroItem]
        self.releases = {}  # version text -> Release
        self.last_tab = "info"

    # ---- release data of the current version -----------------------------------------------------------------
    def release(self, version=None):
        version = version or self.version
        if version not in self.releases:
            self.releases[version] = Release()
        return self.releases[version]

    @property
    def channel(self):
        return self.release().channel

    @property
    def release_date(self):
        return self.release().date

    @property
    def min_max(self):
        return self.release().min_max

    @property
    def changelog(self):
        return self.release().changelog

    # ---- paths -----------------------------------------------------------------------------------------------
    def relative_to_root(self, absolute):
        absolute = norm(os.path.abspath(absolute))
        prefix = norm(self.root).rstrip("\\") + "\\"
        if absolute.lower().startswith(prefix.lower()):
            return absolute[len(prefix):]
        return os.path.basename(absolute)

    def is_inside_root(self, absolute):
        prefix = norm(self.root).rstrip("\\").lower() + "\\"
        return norm(os.path.abspath(absolute)).lower().startswith(prefix)

    @property
    def support_dir(self):
        return os.path.join(self.root, SUPPORT_DIR)

    def hook_path(self, name):
        path = os.path.join(self.support_dir, name)
        return path if os.path.isfile(path) else ""

    def is_excluded(self, absolute):
        lowered = norm(absolute).lower()
        name = os.path.basename(lowered)
        if "\\.git" in lowered or "\\.vscode" in lowered or "\\__pycache__" in lowered:
            return True
        if lowered.startswith(norm(self.support_dir).lower() + "\\"):
            return True  # The packager's own folder is never part of a package.
        if name.endswith((".bak", ".tmp", ".log", ".zip", ".mzp", ".pyc")):
            return True
        if name in SUPPORT_FILES:
            return True
        return bool(re.match(r"^maxpkg-.*-quad-startup\.ms$", name))

    def find_file(self, relative):
        relative = norm(relative)
        for item in self.files:
            if item[1] == relative:
                return item
        return None

    def add_file(self, absolute):
        """True when the file is in the list afterwards."""
        absolute = os.path.abspath(absolute)
        if not os.path.isfile(absolute) or self.is_excluded(absolute) or self.is_custom_hook(absolute):
            return False
        relative = self.relative_to_root(absolute)
        if not is_safe_relative(relative):
            return False
        if self.find_file(relative) is None:
            self.files.append((norm(absolute), relative))
        return True

    def add_folder(self, folder):
        added = 0
        for current, directories, names in os.walk(folder):
            directories[:] = [d for d in directories if not self.is_excluded(os.path.join(current, d, "x"))]
            for name in sorted(names):
                before = len(self.files)
                if self.add_file(os.path.join(current, name)) and len(self.files) > before:
                    added += 1
        return added

    def remove_file(self, relative):
        relative = norm(relative)
        self.files = [item for item in self.files if item[1] != relative]
        if norm(self.entry) == relative:
            self.entry = ""
        self.macros = [macro for macro in self.macros if macro.file != relative]

    def is_custom_hook(self, absolute):
        key = norm(absolute).lower()
        return bool(key) and key in (norm(self.custom_install).lower(), norm(self.custom_uninstall).lower())

    # ---- build path remap -----------------------------------------------------------------------------------
    def build_path(self, relative):
        relative = norm(relative)
        for source, target in self.rules:
            source = normalize_rule_folder(source)
            target = normalize_rule_folder(target, True)
            prefix = source + "\\"
            if source and relative.lower().startswith(prefix.lower()):
                suffix = relative[len(prefix):]
                return suffix if not target else target + "\\" + suffix
        return relative

    # ---- entry and macros ------------------------------------------------------------------------------------
    @property
    def can_compile_entry(self):
        return norm(self.entry).lower().endswith(".ms")

    @property
    def effective_compile_entry(self):
        return self.can_compile_entry and self.compile_entry

    def manifest_entry(self):
        built = self.build_path(self.entry)
        return compiled_path(built) if self.effective_compile_entry else built

    def macro_output(self, macro):
        built = self.build_path(macro.file)
        return compiled_path(built) if macro.compile else built

    def macro_uses_compile(self, relative):
        relative = norm(relative)
        return any(m.file == relative and m.compile for m in self.macros)

    def macro_quad_id(self, macro):
        return stable_guid("{}|{}".format(self.guid.strip(), macro.identifier))

    def uses_quad(self):
        return any(m.quad for m in self.macros)

    def macro_candidates(self):
        return [rel for _abs, rel in self.files if rel.lower().endswith(ENTRY_EXTENSIONS)]

    # ---- names -------------------------------------------------------------------------------------------------
    def output_name(self):
        return "{}@{}@{}.mzp".format(package_slug(self.package_name), self.version, self.guid.strip())
