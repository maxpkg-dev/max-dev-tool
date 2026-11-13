"""Validation of a project. Same rules and wording as the MaxScript packager, plus the field the problem is in."""

import os

from . import project as core_project
from . import svgcheck

from .project import (CHANNELS, ENTRY_EXTENSIONS, LICENSES, MIN_MAX_YEAR, SAFE_MACRO_TITLE, compiled_path,
                      is_safe_display, is_safe_relative, is_safe_rule_folder, is_valid_guid, max_year_plus_one, norm)

ERROR, WARNING, OK = "ERROR", "WARNING", "OK"
DESCRIPTION_CHARS = 500
DESCRIPTION_LINES = 3  # Short and to the point: the description is a summary, not documentation


class Issue(object):
    def __init__(self, level, message, tab="", field=""):
        self.level, self.message, self.tab, self.field = level, message, tab, field

    def where(self):
        names = {"info": "1. Info", "setup": "2. Setup", "files": "3. Files", "release": "4. Release"}
        return "{} -> {}".format(names.get(self.tab, self.tab), self.field) if self.tab else ""

    def __str__(self):
        place = self.where()
        return "[{}] {}{}".format(self.level, self.message, " ({})".format(place) if place else "")


def is_safe_svg(path):
    """True when the icon can be used (see core.svgcheck for the checks and the warnings)."""
    return svgcheck.inspect(path).ok


def validate(project):
    """List of Issue. The project is buildable when no issue has level ERROR."""
    issues = []

    def error(message, tab, field):
        issues.append(Issue(ERROR, message, tab, field))

    name, button = project.package_name.strip(), project.button_name.strip()
    description = project.description.strip()
    release = project.release()
    entry = norm(project.entry).strip()

    if not name:
        error("Package name: type the public name of your tool, for example Bitmap Collector", "info", "Package Name")
    elif not is_safe_display(name):
        error("Package name: use only letters A-Z, digits, spaces, - and _ (no dots, slashes or accents)", "info", "Package Name")
    if not button:
        error("Button name: type the text of the 3ds Max button, for example Collect Bitmaps", "info", "Button Name")
    elif not is_safe_display(button):
        error("Button name: use only letters A-Z, digits, spaces, - and _ (no dots, slashes or accents)", "info", "Button Name")
    if not description:
        error("Description: say in 1 to 3 short lines what the tool does for the user", "info", "Description")
    elif len(description) > DESCRIPTION_CHARS:
        error("Description: shorten it to {} characters at most (now {})".format(DESCRIPTION_CHARS, len(description)),
              "info", "Description")
    elif len(description.splitlines()) > DESCRIPTION_LINES:
        error("Description: keep it short and to the point, {} lines at most (now {})".format(
            DESCRIPTION_LINES, len(description.splitlines())), "info", "Description")
    for attribute, label in core_project.URL_FIELDS:
        problem = core_project.url_problem(getattr(project, attribute))
        if problem:  # Says what to do: the same text is the field's tooltip and the log line
            detail = " (no spaces)" if "spaces" in problem else ""
            error("{}: enter a correct web address, like https://example.com, or clear the field{}".format(
                label, detail), "info", label)
    if not project.developer.strip():
        error("Developer name: type the name users will see, your studio or your own name", "info", "Developer Name")
    if not project.guid.strip():
        error("GUID: press Generate; it is the package identity on maxpkg.dev, keep it for every version",
              "info", "GUID")
    elif not is_valid_guid(project.guid):
        error("GUID: this is not a valid GUID; paste the right one or generate a new one", "info", "GUID")
    if project.license not in LICENSES:
        error("License: choose how the tool is licensed: Free, Shareware, Commercial, Open source or Trial", "info", "License")
    if release.channel not in CHANNELS:
        error("Channel: choose Stable, Beta or Alpha", "release", "Channel")
    elif release.channel != "stable":  # Allowed, but the author should know where the version will be seen
        issues.append(Issue(WARNING, "Channel: " + core_project.CHANNEL_WARNING.format(release.channel.capitalize()),
                            "release", "Channel"))
    if not release.date.strip():
        error("Release date: choose the date of this version", "release", "Release Date")
    if not any(body.strip() for _kind, body in release.changelog):
        error("Changelog: add at least one item for version {}, for example: Added - First release".format(
            project.version), "release", "Changelog")
    try:
        if int(release.min_max) > max_year_plus_one():
            error("Min 3ds Max: choose a year up to {}".format(max_year_plus_one()), "release", "Min 3ds Max")
        if int(release.min_max) < MIN_MAX_YEAR:
            error("Min 3ds Max: choose {} or newer; MaxPkg works with 3ds Max {}+".format(MIN_MAX_YEAR, MIN_MAX_YEAR),
                  "release", "Min 3ds Max")
    except ValueError:
        error("Min 3ds Max: choose a year from the list", "release", "Min 3ds Max")

    if not project.files:
        error("Files: add the files your tool needs with Add files or Add folder", "files", "Files")
    if not entry:
        error("Entry file: choose the script the 3ds Max button runs", "files", "Entry File")
    else:
        item = project.find_file(entry)
        extension = os.path.splitext(entry)[1].lower()
        if item is None:
            error("Entry file: add it to the package files first, then choose it", "files", "Entry File")
        else:
            if not os.path.isfile(item[0]):
                error("Entry file: the file is missing on disk; restore it or choose another", "files", "Entry File")
            if extension not in ENTRY_EXTENSIONS:
                error("Entry file: choose a .ms, .mse or .py script", "files", "Entry File")

    icon = norm(project.svg_icon).strip()
    if not icon:
        error("SVG icon: choose a square .svg icon for the button and the maxpkg.dev page", "files", "SVG Icon")
    else:
        report = svgcheck.inspect(icon)
        for message in report.errors:
            error("SVG icon: {}. Choose another SVG".format(message), "files", "SVG Icon")
        for message in report.warnings:
            issues.append(Issue(WARNING, "SVG icon: " + message, "files", "SVG Icon"))

    _check_hooks(project, error)
    targets = _check_files(project, entry, error)
    _check_custom_targets(project, targets, error)

    for source, target in project.rules:
        if not is_safe_rule_folder(source):
            error("Build path remap: '{}' must be a folder inside the project, for example COMPILE".format(source),
                  "files", "Build Path Remap")
        if not is_safe_rule_folder(target, True):
            error("Build path remap: target '{}' must be a relative folder (leave it empty for the package root)".format(
                target), "files", "Build Path Remap")

    _check_macros(project, entry, error)

    output = project.output_folder.strip()
    if not output:
        error("Output folder: choose where the .mzp is saved", "files", "Output Folder")
    else:
        parent = os.path.abspath(output)
        while parent and not os.path.isdir(parent) and os.path.dirname(parent) != parent:
            parent = os.path.dirname(parent)  # The folder itself is created when building
        if not os.path.isdir(parent) or not os.access(parent, os.W_OK):
            error("Output folder: this folder cannot be created here; choose another one", "files", "Output Folder")
    return issues


def _check_hooks(project, error):
    for label, source in (("Custom Install Script", project.custom_install),
                          ("Custom Uninstall Script", project.custom_uninstall)):
        source = norm(source).strip()
        if not source:
            continue
        if not os.path.isfile(source):
            error("{}: the file is missing; choose it again or clear the field".format(label), "setup", label)
        if not source.lower().endswith(".ms"):
            error("{}: choose a .ms script".format(label), "setup", label)
        if project.is_excluded(source):
            error("{}: choose your own script, not a file of the packager".format(label), "setup", label)
        if not project.is_inside_root(source):
            error("{}: choose a script inside the project folder".format(label), "setup", label)
        else:
            relative = project.relative_to_root(source)
            if not is_safe_relative(relative) or not is_safe_relative(project.build_path(relative)):
                error("{}: the path is not valid inside the project; choose the script again".format(label), "setup", label)
            if any(norm(item[0]).lower() == source.lower() or item[1].lower() == relative.lower()
                   for item in project.files):
                error("{}: remove it from the package files; it is included automatically".format(label),
                      "setup", label)


def _check_files(project, entry, error):
    targets = {}
    for absolute, relative in project.files:
        if not is_safe_relative(relative):
            error("Files: '{}' has an invalid path; remove it and add it again".format(relative), "files", "Files")
        if not os.path.isfile(absolute):
            error("Files: '{}' is missing on disk; restore it or remove it from the list".format(relative), "files", "Files")
        built = project.build_path(relative)
        compiled = (project.effective_compile_entry and relative.lower() == entry.lower()) or project.macro_uses_compile(relative)
        target = compiled_path(built) if compiled else built
        lowered = target.lower()
        if lowered in targets:
            error("Files: '{}' and '{}' would both be packaged as '{}'; rename one or change the build path "
                  "remap".format(relative, targets[lowered], target), "files", "Build Path Remap")
        else:
            targets[lowered] = relative
        if lowered.endswith("\\_install.ms") or lowered.endswith("\\_uninstall.ms"):
            error("Files: remove {}; the packager adds its own to every package".format(os.path.basename(lowered)),
                  "files", "Files")
    return targets


def _check_custom_targets(project, targets, error):
    for label, source in (("Custom Install Script", project.custom_install), ("Custom Uninstall Script", project.custom_uninstall)):
        source = norm(source).strip()
        if not source or not project.is_inside_root(source):
            continue
        target = project.build_path(project.relative_to_root(source))
        if target.lower() in targets:
            error("{}: it would be packaged as '{}' like {}; rename one of them".format(label, target,
                  targets[target.lower()]), "setup", label)
        targets[target.lower()] = label


def _check_macros(project, entry, error):
    identifiers, modes = set(), {}
    for macro in project.macros:
        file_key = macro.file.lower()
        if project.find_file(macro.file) is None:
            error("Extra macros: add '{}' to the package files or remove the macro".format(macro.file), "files",
                  "Extra Macros")
        if not macro.file.lower().endswith(ENTRY_EXTENSIONS):
            error("Extra macros: '{}' must be a .ms, .mse or .py script".format(macro.file), "files", "Extra Macros")
        if not SAFE_MACRO_TITLE.match(macro.button.strip()):
            error("Extra macros: the button name '{}' may use only letters, spaces and _".format(macro.button),
                  "files", "Extra Macros")
        if macro.compile and not macro.file.lower().endswith(".ms"):
            error("Extra macros: turn Compile off for '{}'; only .ms scripts can be compiled".format(macro.file),
                  "files", "Extra Macros")
        if entry.lower() == file_key and macro.compile != project.effective_compile_entry:
            error("Extra macros: '{}' is also the entry file; set Compile the same in both places".format(macro.file),
                  "files", "Extra Macros")
        if file_key in modes and modes[file_key] != macro.compile:
            error("Extra macros: '{}' is used twice with different Compile settings; make them the same".format(
                macro.file), "files", "Extra Macros")
        if macro.identifier.lower() in identifiers:
            error("Extra macros: two buttons are named '{}'; rename one".format(macro.button), "files", "Extra Macros")
        identifiers.add(macro.identifier.lower())
        modes[file_key] = macro.compile
