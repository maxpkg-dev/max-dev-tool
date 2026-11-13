"""Load and save a project in the same files the MaxScript packager used (maxpkg-packager.ini + maxpkg-changelog.ini)."""

import datetime
import os
import shutil

from . import hooks
from .inifile import IniFile, escape_value, unescape_value
from .project import (CHANGELOG_FILE, CHANNELS, ICON_FILE, clamp_min_max, LEGACY_FILES, SETTINGS_FILE, SUPPORT_DIR, MacroItem,
                      Project, Release, is_safe_rule_folder,
                      is_safe_relative, max_years, norm, normalize_rule_folder, parse_version, version_text)

S = "settings"


def _bool(text, default):
    text = (text or "").strip().lower()
    return default if text == "" else text == "true"


def _int(text, default=0):
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def support_dir(root):
    return os.path.join(root, SUPPORT_DIR)


def settings_path(root):
    return os.path.join(support_dir(root), SETTINGS_FILE)


def changelog_path(root):
    return os.path.join(support_dir(root), CHANGELOG_FILE)


def migrate_legacy(root):
    """Move the files of the MaxScript packager (1.x) from the project root into the max-package folder.

    All files are copied first and the originals are removed only when every copy succeeded, so an interruption
    never loses data. Returns the list of moved file names (empty when there was nothing to do)."""
    folder = support_dir(root)
    found = [name for name in LEGACY_FILES if os.path.isfile(os.path.join(root, name))]
    if not found or os.path.isfile(os.path.join(folder, SETTINGS_FILE)):
        return []
    try:
        os.makedirs(folder, exist_ok=True)
        for name in found:
            target = os.path.join(folder, LEGACY_FILES[name])
            if not os.path.exists(target):
                shutil.copy2(os.path.join(root, name), target)
    except OSError:
        return []
    if os.path.isfile(os.path.join(root, "maxpkg-src", "python", "maxpkgpackager", "__init__.py")) or \
            os.path.isfile(os.path.join(root, "python", "maxpkgpackager", "__init__.py")):
        return found  # The packager's own repository: its root _install.ms / _uninstall.ms are sources, keep them
    for name in found:
        try:
            os.remove(os.path.join(root, name))
        except OSError:
            pass
    return found


def _ensure_ignore_file(root):
    """Builds should not end up in version control by accident: the folder ignores its own dist."""
    path = os.path.join(support_dir(root), ".gitignore")
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("dist/\n")
        except OSError:
            pass


def normalize_date(text):
    try:
        return datetime.datetime.strptime((text or "").strip()[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return datetime.date.today().isoformat()


def load(root):
    """Read a project. Missing files give an empty project; broken values fall back to defaults."""
    migrate_legacy(root)
    hooks.sync(root)  # A project has the install and uninstall windows from its first open, and always the current ones
    project = Project(root)
    ini = IniFile.read(settings_path(root))

    def text(key, default=""):
        value = ini.get(S, key, "")
        return unescape_value(value) if value != "" else default

    def path(key, default=""):
        value = ini.get(S, key, "")
        return value if value != "" else default  # Paths never go through the \n unescape.

    project.package_name = text("packageName")
    project.button_name = text("buttonName")
    project.guid = text("packageGuid")
    project.description = text("description")
    project.developer = text("developerName")
    project.license = text("license")
    project.license_url = text("licenseUrl")
    project.documentation = text("documentation")
    project.homepage = text("homepage")
    project.purchase = text("purchase")
    project.purchase_label = text("purchaseButtonLabel", "Buy")
    project.create_button = _bool(ini.get(S, "createMacroButton"), True)
    project.show_toolbar = _bool(ini.get(S, "showInToolbar"), True)
    project.custom_install = path("customInstallScript")
    project.custom_uninstall = path("customUninstallScript")
    project.output_folder = path("outputFolder", os.path.join(project.support_dir, "dist"))
    if norm(project.output_folder).rstrip("\\/").lower() == norm(os.path.join(project.root, "dist")).lower():
        # The default of version 1.x put the packages into <project>\dist; they now go into max-package\dist, so the
        # project root keeps only the max-package folder. A folder the user chose elsewhere is kept.
        project.output_folder = norm(os.path.join(project.support_dir, "dist"))
    project.svg_icon = path("svgIcon")
    legacy_icon = os.path.join(project.root, "maxpkg-icon.svg")
    if project.svg_icon and norm(project.svg_icon).lower() == norm(legacy_icon).lower():
        project.svg_icon = norm(os.path.join(project.support_dir, ICON_FILE))  # Moved with the other files.
    project.entry = path("entry")
    project.compile_entry = _bool(ini.get(S, "compileEntry"), True)  # Every saved project states it; new: on
    project.version = version_text(parse_version(text("version", "1.0.0")))
    project.last_tab = ini.get("ui", "lastTab", "info") or "info"

    for index in range(1, _int(ini.get("files", "count")) + 1):
        absolute = ini.get("files", "{}_abs".format(index))
        relative = norm(ini.get("files", "{}_rel".format(index)))
        if not relative or not is_safe_relative(relative):
            continue
        if not os.path.isfile(absolute):  # The project folder moved: resolve against the current root.
            moved = os.path.join(project.root, relative)
            absolute = moved if os.path.isfile(moved) else absolute
        if not project.is_excluded(absolute):
            project.files.append((norm(absolute), relative))

    for index in range(1, _int(ini.get("buildPathRules", "count")) + 1):
        source = normalize_rule_folder(ini.get("buildPathRules", "{}_source".format(index)))
        target = normalize_rule_folder(ini.get("buildPathRules", "{}_target".format(index)), True)
        if is_safe_rule_folder(source) and is_safe_rule_folder(target, True):
            project.rules.append((source, target))

    for index in range(1, _int(ini.get("extraMacros", "count")) + 1):
        key = "{}_".format(index)
        macro_file = norm(ini.get("extraMacros", key + "file"))
        title = unescape_value(ini.get("extraMacros", key + "button"))
        if macro_file and title.strip():
            project.macros.append(MacroItem(macro_file, title, _bool(ini.get("extraMacros", key + "compile"), False),
                                            _bool(ini.get("extraMacros", key + "quad"), False)))

    _load_releases(project, ini)
    if project.entry and project.find_file(project.entry) is None:
        project.entry = ""
    return project


def _load_releases(project, top_ini):
    changelog = IniFile.read(changelog_path(project.root))
    for section in changelog.section_names():
        if not section.lower().startswith("version_"):
            continue
        version = section[len("version_"):]
        release = Release()
        release.date = normalize_date(changelog.get(section, "releaseDate"))
        channel = changelog.get(section, "releaseChannel").lower()
        release.channel = channel if channel in CHANNELS else "stable"
        release.min_max = clamp_min_max(changelog.get(section, "min3dsMax"))
        for index in range(1, _int(changelog.get(section, "count")) + 1):
            kind = unescape_value(changelog.get(section, "{}_type".format(index)))
            body = unescape_value(changelog.get(section, "{}_text".format(index)))
            if kind and body:
                release.changelog.append((kind, body))
        project.releases[version] = release
    if project.version not in project.releases:  # Older projects keep the values only in the settings file.
        release = Release()
        release.date = normalize_date(top_ini.get(S, "releaseDate"))
        channel = top_ini.get(S, "releaseChannel").lower()
        release.channel = channel if channel in CHANNELS else "stable"
        release.min_max = clamp_min_max(top_ini.get(S, "min3dsMax"))
        project.releases[project.version] = release


def save(project):
    """Write both files atomically. Raises OSError on failure; the old files stay intact."""
    ini = IniFile.read(settings_path(project.root))  # Keep sections this version does not know.
    release = project.release()

    def put(key, value, escaped=True):
        ini.set(S, key, escape_value(value) if escaped else value)

    put("packageName", project.package_name)
    put("buttonName", project.button_name)
    put("packageGuid", project.guid)
    put("description", project.description)
    put("developerName", project.developer)
    put("license", project.license)
    put("licenseUrl", project.license_url)
    put("documentation", project.documentation)
    put("homepage", project.homepage)
    put("purchase", project.purchase)
    put("purchaseButtonLabel", project.purchase_label)
    put("createMacroButton", "true" if project.create_button else "false")
    put("showInToolbar", "true" if project.show_toolbar else "false")
    put("customInstallScript", project.custom_install, False)
    put("customUninstallScript", project.custom_uninstall, False)
    put("outputFolder", project.output_folder, False)
    put("svgIcon", project.svg_icon, False)
    put("entry", project.entry, False)
    put("compileEntry", "true" if project.compile_entry else "false")
    put("version", project.version)
    put("releaseChannel", release.channel)
    put("releaseDate", release.date)
    put("min3dsMax", release.min_max)
    put("max3dsMax", str(datetime.date.today().year + 1))

    for section in ("files", "buildPathRules", "extraMacros"):
        ini.delete_section(section)
    ini.set("files", "count", len(project.files))
    for index, (absolute, relative) in enumerate(project.files, 1):
        ini.set("files", "{}_abs".format(index), absolute)
        ini.set("files", "{}_rel".format(index), relative)
    ini.set("buildPathRules", "count", len(project.rules))
    for index, (source, target) in enumerate(project.rules, 1):
        ini.set("buildPathRules", "{}_source".format(index), source)
        ini.set("buildPathRules", "{}_target".format(index), target)
    ini.set("extraMacros", "count", len(project.macros))
    for index, macro in enumerate(project.macros, 1):
        ini.set("extraMacros", "{}_file".format(index), macro.file)
        ini.set("extraMacros", "{}_button".format(index), escape_value(macro.button))
        ini.set("extraMacros", "{}_compile".format(index), "true" if macro.compile else "false")
        ini.set("extraMacros", "{}_quad".format(index), "true" if macro.quad else "false")
    ini.set("ui", "lastTab", project.last_tab)
    ini.write(settings_path(project.root))
    _ensure_ignore_file(project.root)
    hooks.sync(project.root)
    save_changelog(project)


def save_changelog(project):
    ini = IniFile.read(changelog_path(project.root))
    for version, release in project.releases.items():
        section = "version_" + version
        if version != project.version and not release.changelog and ini.has_section(section):
            continue  # Never wipe an older version's stored data because it was only visited.
        ini.delete_section(section)
        ini.set(section, "version", version)
        ini.set(section, "releaseDate", release.date)
        ini.set(section, "releaseChannel", release.channel)
        ini.set(section, "min3dsMax", release.min_max)
        ini.set(section, "count", len(release.changelog))
        for index, (kind, body) in enumerate(release.changelog, 1):
            ini.set(section, "{}_type".format(index), escape_value(kind))
            ini.set(section, "{}_text".format(index), escape_value(body))
    ini.write(changelog_path(project.root))
