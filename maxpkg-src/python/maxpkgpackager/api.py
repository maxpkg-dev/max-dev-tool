"""MaxPkgPackerApi: automation of MaxPkg Packager for AI agents and scripts, without clicks.

In 3ds Max the launcher exposes this module as the MAXScript global `MaxPkgPackerApi` (python.import), so the calls of
the MaxScript packager 1.x keep working:

    MaxPkgPackerApi.ping()
    MaxPkgPackerApi.setOption "license" "Free"
    MaxPkgPackerApi.build()

Every call returns one JSON string: {"ok", "operation", "data", "warnings", "errors"}; an error is
{"code", "message"}. Collection indexes are 1-based. Every mutation saves at once. When the packager window is open
on the same project, the API edits that project and the window shows the change; otherwise it works on the project
files directly (no window needed). See docs/ai-agents.md.
"""

import copy
import json
import os
import re
import shutil
import sys

from . import DISPLAY_NAME, UPDATE_URL, __version__
from .core import build as core_build
from .core import project as core
from .core import store, svgcheck, validate as core_validate

API_VERSION = "2.0.0"
_state = {"root": None, "project": None, "log": []}


class ApiError(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code, self.message = code, message


def _envelope(operation, ok, data=None, errors=None, warnings=None):
    return json.dumps({"ok": ok, "operation": operation, "data": data if data is not None else {},
                       "warnings": warnings or [], "errors": errors or []}, ensure_ascii=False)


def _operation(name):
    def wrap(function):
        def call(*args, **kwargs):
            try:
                result = function(*args, **kwargs)
                if isinstance(result, tuple):  # (ok, data, errors, warnings) from validate / build
                    ok, data, errors, warnings = result
                    return _envelope(name, ok, data, errors, warnings)
                return _envelope(name, True, result)
            except ApiError as error:
                return _envelope(name, False, errors=[{"code": error.code, "message": error.message}])
            except Exception as error:  # Never raise into MAXScript: report it in the envelope.
                return _envelope(name, False, errors=[{"code": "INTERNAL_ERROR", "message": "{}: {}".format(
                    type(error).__name__, error)}])
        call.__name__ = function.__name__
        call.__doc__ = function.__doc__
        return call
    return wrap


# ---- which project ----------------------------------------------------------------------------------------------
def _session():
    owner = getattr(sys.modules.get("_maxpkgpackager_session"), "owner", None)
    if owner is not None and getattr(owner, "state", "") == "running" and getattr(owner, "model", None) is not None:
        return owner
    return None


def _same(first, second):
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


def _target():
    """(project, model or None). The open window's project when it is the requested one, else the files on disk."""
    owner = _session()
    root = _state["root"]
    if owner is not None and (root is None or _same(owner.project_root, root)):
        return owner.model.project, owner.model
    root = root or os.environ.get("MAXPKG_PACKAGER_PROJECT")
    if not root:
        raise ApiError("NO_PROJECT", "No project is open. Call openProject with the project folder first.")
    if _state["project"] is None or not _same(_state["project"].root, root):
        _state["project"] = store.load(root)
    return _state["project"], None


def _commit(project, model):
    """Save now. With the window open: the window refreshes and revalidates as after a click."""
    if model is not None:
        model.touch(structural=True)
        model.save_now()
        model.validate_now()
    else:
        store.save(project)


# ---- options ----------------------------------------------------------------------------------------------------
# public name -> (attribute, kind). Kinds: text, bool, path. Aliases are the INI names of the packager 1.x.
OPTIONS = {
    "packageName": ("package_name", "text"), "buttonName": ("button_name", "text"), "packageGuid": ("guid", "text"),
    "description": ("description", "text"), "developerName": ("developer", "text"), "license": ("license", "text"),
    "licenseUrl": ("license_url", "text"), "documentationUrl": ("documentation", "text"),
    "homepageUrl": ("homepage", "text"), "purchaseUrl": ("purchase", "text"),
    "purchaseButtonLabel": ("purchase_label", "text"), "createMacroButton": ("create_button", "bool"),
    "showInToolbar": ("show_toolbar", "bool"), "customInstallScript": ("custom_install", "path"),
    "customUninstallScript": ("custom_uninstall", "path"), "outputFolder": ("output_folder", "path"),
    "svgIconFile": ("svg_icon", "path"), "entryFile": ("entry", "text"), "compileEntry": ("compile_entry", "bool"),
    "version": ("version", "text"), "releaseChannel": (None, "text"), "releaseDate": (None, "text"),
    "min3dsMax": (None, "text"),
}
ALIASES = {"svgIcon": "svgIconFile", "entry": "entryFile", "documentation": "documentationUrl",
           "homepage": "homepageUrl", "purchase": "purchaseUrl"}


def _option_name(name):
    name = ALIASES.get(str(name), str(name))
    if name not in OPTIONS:
        raise ApiError("UNKNOWN_OPTION", "Unknown option '{}'. Writable options: {}".format(name, ", ".join(OPTIONS)))
    return name


def _get_option(project, name):
    release = project.release()
    if name == "releaseChannel":
        return release.channel
    if name == "releaseDate":
        return release.date
    if name == "min3dsMax":
        return release.min_max
    return getattr(project, OPTIONS[name][0])


def _as_bool(name, value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off", ""):
        return False
    raise ApiError("INVALID_VALUE", "{} must be true or false".format(name))


def _set_option(project, name, value):
    """Validate one value and apply it. Raises ApiError with the reason."""
    value = "" if value is None else value
    text = str(value).strip() if not isinstance(value, bool) else value
    release = project.release()
    if name in ("packageName", "buttonName"):
        if text and not core.is_safe_display(text):
            raise ApiError("INVALID_VALUE", "{} allows only A-Z, a-z, 0-9, space, hyphen and underscore".format(name))
    elif name == "packageGuid":
        if text and not core.is_valid_guid(text):
            raise ApiError("INVALID_VALUE", "packageGuid must be empty or a UUID")
        text = text.lower()
    elif name == "description":
        text = str(value).strip()
        if len(text) > 500:
            raise ApiError("INVALID_VALUE", "description must be 500 characters or less")
    elif name in ("licenseUrl", "documentationUrl", "homepageUrl", "purchaseUrl"):
        text = core.complete_url(text)
        problem = core.url_problem(text)
        if problem:
            raise ApiError("INVALID_VALUE", "{} {}".format(name, problem))
    elif name == "license":
        if text and text not in core.LICENSES:
            raise ApiError("INVALID_VALUE", "license must be one of: " + ", ".join(core.LICENSES))
    elif name == "purchaseButtonLabel":
        if text not in core.PURCHASE_LABELS:
            raise ApiError("INVALID_VALUE", "purchaseButtonLabel must be one of: " + ", ".join(core.PURCHASE_LABELS))
    elif name in ("createMacroButton", "showInToolbar", "compileEntry"):
        text = _as_bool(name, value)
    elif name in ("customInstallScript", "customUninstallScript"):
        if text:
            text = core.norm(os.path.abspath(text))
            if not os.path.isfile(text) or not text.lower().endswith(".ms"):
                raise ApiError("FILE_NOT_FOUND", "{} must be an existing .ms file".format(name))
            if not project.is_inside_root(text):
                raise ApiError("OUTSIDE_PROJECT", "{} must be inside the project folder".format(name))
    elif name == "outputFolder":
        text = core.norm(os.path.abspath(text)) if text else os.path.join(project.support_dir, "dist")
    elif name == "svgIconFile":
        if text:
            report = svgcheck.inspect(text)
            if not report.ok:
                raise ApiError("INVALID_VALUE", "svgIconFile: " + report.errors[0])
            target = os.path.join(project.support_dir, core.ICON_FILE)
            os.makedirs(project.support_dir, exist_ok=True)
            if not _same(text, target):
                shutil.copyfile(text, target)  # The icon lives in max-package like everything else
            text = core.norm(target)
    elif name == "entryFile":
        text = core.norm(text)
        if text and project.find_file(text) is None:
            raise ApiError("FILE_NOT_IN_PACKAGE", "entryFile must be a file already added with addFile")
        if text and not text.lower().endswith(core.ENTRY_EXTENSIONS):
            raise ApiError("INVALID_VALUE", "entryFile must end in .ms, .mse or .py")
    elif name == "version":
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$", text):
            raise ApiError("INVALID_VALUE", "version must be major.minor.patch with numbers 0-999")
        project.version = core.version_text(core.parse_version(text))
        project.release()  # Opens the version's own release data (date, channel, changelog)
        return
    elif name == "releaseChannel":
        if text not in core.CHANNELS:
            raise ApiError("INVALID_VALUE", "releaseChannel must be stable, beta or alpha")
        release.channel = text
        return
    elif name == "releaseDate":
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", text) or store.normalize_date(text) != text:
            raise ApiError("INVALID_VALUE", "releaseDate must be YYYY-MM-DD")
        release.date = text
        return
    elif name == "min3dsMax":
        if text not in core.max_years():
            raise ApiError("INVALID_VALUE", "min3dsMax must be one of: " + ", ".join(core.max_years()))
        release.min_max = text
        return
    setattr(project, OPTIONS[name][0], text)


def _options(project):
    return dict((name, _get_option(project, name)) for name in OPTIONS)


# ---- state ------------------------------------------------------------------------------------------------------
def _files(project):
    return [{"index": index, "relativePath": relative, "absolutePath": absolute, "exists": os.path.isfile(absolute),
             "isEntry": relative == project.entry} for index, (absolute, relative) in enumerate(project.files, 1)]


def _changelog(project):
    return [{"index": index, "type": kind, "text": body} for index, (kind, body) in enumerate(project.changelog, 1)]


def _rules(project):
    return [{"index": index, "sourceFolder": source, "targetFolder": target}
            for index, (source, target) in enumerate(project.rules, 1)]


def _macros(project):
    return [{"index": index, "file": m.file, "buttonName": m.button, "compileScript": m.compile,
             "showInQuadMenu": m.quad, "outputFile": project.macro_output(m)}
            for index, m in enumerate(project.macros, 1)]


def _full_state(project, model):
    return {
        "projectRoot": project.root,
        "supportFolder": project.support_dir,
        "settingsFile": store.settings_path(project.root),
        "changelogFile": store.changelog_path(project.root),
        "outputFile": os.path.join(project.output_folder, project.output_name()),
        "windowOpen": model is not None,
        "options": _options(project),
        "files": _files(project),
        "changelog": _changelog(project),
        "buildPathRules": _rules(project),
        "extraMacros": _macros(project),
        "standardHooks": {"_install.ms": bool(project.hook_path("_install.ms")),
                          "_uninstall.ms": bool(project.hook_path("_uninstall.ms"))},
        "versions": sorted(project.releases),
    }


def _index(items, index, what):
    try:
        number = int(index)
    except (TypeError, ValueError):
        raise ApiError("INVALID_INDEX", "{} index must be a number (1-based)".format(what))
    if not 1 <= number <= len(items):
        raise ApiError("INVALID_INDEX", "{} index {} is out of range 1..{}".format(what, number, len(items)))
    return number - 1


def _pairs(value):
    """setOptions input: a MAXScript array of #(name, value) pairs, a list of pairs, a dict or a JSON object string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ApiError("INVALID_VALUE", "setOptions expects pairs, an object or a JSON object string")
    if isinstance(value, dict):
        return list(value.items())
    pairs = []
    for item in value:
        item = list(item)
        if len(item) != 2:
            raise ApiError("INVALID_VALUE", "Every setOptions item must be a pair: #(name, value)")
        pairs.append((str(item[0]), item[1]))
    return pairs


# ---- discovery --------------------------------------------------------------------------------------------------
@_operation("api.ping")
def ping():
    """API and packager versions, and the project the next calls will use."""
    owner = _session()
    root = _state["root"] or (owner.project_root if owner else os.environ.get("MAXPKG_PACKAGER_PROJECT", ""))
    return {"apiVersion": API_VERSION, "packagerVersion": __version__, "packager": DISPLAY_NAME,
            "projectRoot": root or "", "windowOpen": owner is not None}


@_operation("api.schema")
def getSchema():
    """Methods, writable options with allowed values, response shape and index base."""
    values = {"license": list(core.LICENSES) + [""], "purchaseButtonLabel": list(core.PURCHASE_LABELS),
              "releaseChannel": list(core.CHANNELS), "min3dsMax": core.max_years()}
    return {"apiVersion": API_VERSION, "indexBase": 1, "methods": sorted(PUBLIC),
            "options": dict((name, {"type": OPTIONS[name][1], "values": values.get(name)}) for name in OPTIONS),
            "changelogTypes": list(core.CHANGELOG_TYPES),
            "response": {"ok": "bool", "operation": "str", "data": "object", "warnings": "list",
                         "errors": "list of {code, message}"}}


@_operation("project.open")
def openProject(projectFolder):
    """Use this project folder for the next calls (the folder that holds maxpkg-packager.ms)."""
    folder = os.path.abspath(str(projectFolder))
    if not os.path.isdir(folder):
        raise ApiError("FOLDER_NOT_FOUND", "Project folder does not exist: " + folder)
    _state["root"], _state["project"] = folder, None
    project, model = _target()
    return _full_state(project, model)


@_operation("state.get")
def getState():
    """The complete current state of the project."""
    project, model = _target()
    return _full_state(project, model)


@_operation("state.save")
def save():
    project, model = _target()
    _commit(project, model)
    return _full_state(project, model)


@_operation("state.reload")
def reload():
    """Read the project files again (unsaved changes in the window are discarded)."""
    project, model = _target()
    fresh = store.load(project.root)
    if model is not None:
        project.__dict__.update(fresh.__dict__)
        model.structure_changed.emit()
        model.validate_now()
    else:
        _state["project"] = project = fresh
    return _full_state(project, model)


# ---- options ----------------------------------------------------------------------------------------------------
@_operation("options.get")
def getOption(optionName):
    project, _model = _target()
    name = _option_name(optionName)
    return {"name": name, "value": _get_option(project, name)}


@_operation("options.set")
def setOption(optionName, optionValue):
    """Validate, apply and save one option."""
    project, model = _target()
    name = _option_name(optionName)
    _set_option(project, name, optionValue)
    _commit(project, model)
    return {"name": name, "value": _get_option(project, name)}


@_operation("options.setMany")
def setOptions(optionPairs):
    """Validate every pair first, then apply them (version first) and save once."""
    project, model = _target()
    pairs = [(_option_name(name), value) for name, value in _pairs(optionPairs)]
    pairs.sort(key=lambda pair: 0 if pair[0] == "version" else 1)  # Release data belongs to the version
    trial = copy.deepcopy(project)  # A rejected batch leaves the project as it was
    for name, value in pairs:
        _set_option(trial, name, value)
    project.__dict__.update(trial.__dict__)
    _commit(project, model)
    return {"options": _options(project)}


@_operation("guid.generate")
def generateGuid(replaceExisting=False):
    """A new package GUID. An existing GUID is the package identity: replacing it needs replaceExisting=true."""
    project, model = _target()
    if project.guid.strip() and not _as_bool("replaceExisting", replaceExisting):
        raise ApiError("GUID_EXISTS", "The package already has a GUID. Pass replaceExisting: true to replace it "
                                      "(this creates a new package identity on maxpkg.dev).")
    project.guid = core.new_guid()
    _commit(project, model)
    return {"packageGuid": project.guid}


# ---- files ------------------------------------------------------------------------------------------------------
@_operation("files.list")
def listFiles():
    project, _model = _target()
    return {"files": _files(project)}


@_operation("files.add")
def addFile(sourceFilePath):
    project, model = _target()
    path = os.path.abspath(str(sourceFilePath))
    if not os.path.isfile(path):
        raise ApiError("FILE_NOT_FOUND", "File does not exist: " + path)
    if not project.is_inside_root(path):
        raise ApiError("OUTSIDE_PROJECT", "Package files must be inside the project folder: " + project.root)
    if project.is_excluded(path) or project.is_custom_hook(path):
        raise ApiError("FILE_EXCLUDED", "This file is a packager or temporary file and is never packaged: " + path)
    project.add_file(path)
    _commit(project, model)
    return {"files": _files(project)}


@_operation("files.addFolder")
def addFolder(sourceFolderPath):
    project, model = _target()
    folder = os.path.abspath(str(sourceFolderPath))
    if not os.path.isdir(folder):
        raise ApiError("FOLDER_NOT_FOUND", "Folder does not exist: " + folder)
    if not project.is_inside_root(os.path.join(folder, "x")):
        raise ApiError("OUTSIDE_PROJECT", "The folder must be inside the project folder: " + project.root)
    added = project.add_folder(folder)
    _commit(project, model)
    return {"added": added, "files": _files(project)}


def _file_relative(project, identifier):
    if isinstance(identifier, (int, float)) and not isinstance(identifier, bool):
        return project.files[_index(project.files, identifier, "File")][1]
    relative = core.norm(str(identifier))
    if os.path.isabs(relative):
        relative = project.relative_to_root(relative)
    if project.find_file(relative) is None:
        raise ApiError("FILE_NOT_IN_PACKAGE", "Not in the files list: " + relative)
    return relative


@_operation("files.remove")
def removeFile(fileIdentifier, force=False):
    """Remove by 1-based index or relative path. A file used as entry or by an extra macro needs force=true."""
    project, model = _target()
    relative = _file_relative(project, fileIdentifier)
    used = relative == project.entry or any(m.file == relative for m in project.macros)
    if used and not _as_bool("force", force):
        raise ApiError("FILE_IN_USE", "File is used by entryFile or Extra Macros. Pass force: true to clear "
                                      "dependent references.")
    project.remove_file(relative)
    _commit(project, model)
    return {"files": _files(project)}


@_operation("files.clear")
def clearFiles(force=False):
    project, model = _target()
    if (project.entry or project.macros) and not _as_bool("force", force):
        raise ApiError("FILE_IN_USE", "Files are used by entryFile or Extra Macros. Pass force: true to clear them.")
    project.files, project.entry, project.macros = [], "", []
    _commit(project, model)
    return {"files": []}


@_operation("files.setEntry")
def setEntry(relativeFilePath, compileEntry=None):
    """Choose the entry file (the script the 3ds Max button runs); optionally set compileEntry too."""
    project, model = _target()
    _set_option(project, "entryFile", relativeFilePath)
    if compileEntry is not None:
        _set_option(project, "compileEntry", compileEntry)
    _commit(project, model)
    return {"entryFile": project.entry, "compileEntry": project.effective_compile_entry,
            "manifestEntry": project.manifest_entry()}


# ---- changelog --------------------------------------------------------------------------------------------------
def _kind(itemType):
    text = str(itemType).strip().lower()
    aliases = {"deleted": "Removed", "bugfix": "Fixed", "fix": "Fixed", "add": "Added", "change": "Changed",
               "improve": "Improved"}
    for name in core.CHANGELOG_TYPES:
        if text == name.lower():
            return name
    if text in aliases:
        return aliases[text]
    raise ApiError("INVALID_VALUE", "Changelog type must be one of: " + ", ".join(core.CHANGELOG_TYPES))


def _text(itemText):
    text = " ".join(str(itemText).split())
    if not text:
        raise ApiError("INVALID_VALUE", "Changelog text must not be empty")
    return text


@_operation("changelog.list")
def listChangelog():
    """Items of the current version (set the version first: every version has its own changelog)."""
    project, _model = _target()
    return {"version": project.version, "items": _changelog(project)}


@_operation("changelog.add")
def addChangelog(itemType, itemText):
    project, model = _target()
    project.changelog.append((_kind(itemType), _text(itemText)))
    _commit(project, model)
    return {"version": project.version, "items": _changelog(project)}


@_operation("changelog.update")
def updateChangelog(itemIndex, itemType, itemText):
    project, model = _target()
    position = _index(project.changelog, itemIndex, "Changelog")
    project.changelog[position] = (_kind(itemType), _text(itemText))
    _commit(project, model)
    return {"version": project.version, "items": _changelog(project)}


@_operation("changelog.remove")
def removeChangelog(itemIndex):
    project, model = _target()
    del project.changelog[_index(project.changelog, itemIndex, "Changelog")]
    _commit(project, model)
    return {"version": project.version, "items": _changelog(project)}


@_operation("changelog.clear")
def clearChangelog():
    project, model = _target()
    del project.changelog[:]
    _commit(project, model)
    return {"version": project.version, "items": []}


# ---- build path rules -------------------------------------------------------------------------------------------
def _rule(sourceFolder, targetFolder):
    source = core.normalize_rule_folder(str(sourceFolder))
    target = core.normalize_rule_folder(str(targetFolder or ""), True)
    if not core.is_safe_rule_folder(source):
        raise ApiError("INVALID_VALUE", "Source folder must be a relative folder inside the project")
    if not core.is_safe_rule_folder(target, True):
        raise ApiError("INVALID_VALUE", "Target folder must be relative ('' or '/' for the package root)")
    return source, target


@_operation("buildPathRules.list")
def listBuildPathRules():
    project, _model = _target()
    return {"rules": _rules(project)}


@_operation("buildPathRules.add")
def addBuildPathRule(sourceFolder, targetFolder=""):
    project, model = _target()
    project.rules.append(_rule(sourceFolder, targetFolder))
    _commit(project, model)
    return {"rules": _rules(project)}


@_operation("buildPathRules.update")
def updateBuildPathRule(ruleIndex, sourceFolder, targetFolder=""):
    project, model = _target()
    project.rules[_index(project.rules, ruleIndex, "Rule")] = _rule(sourceFolder, targetFolder)
    _commit(project, model)
    return {"rules": _rules(project)}


@_operation("buildPathRules.remove")
def removeBuildPathRule(ruleIndex):
    project, model = _target()
    del project.rules[_index(project.rules, ruleIndex, "Rule")]
    _commit(project, model)
    return {"rules": _rules(project)}


@_operation("buildPathRules.clear")
def clearBuildPathRules():
    project, model = _target()
    project.rules = []
    _commit(project, model)
    return {"rules": []}


# ---- extra macros -----------------------------------------------------------------------------------------------
def _macro(project, relativeFilePath, buttonName, compileScript, showInQuadMenu, ignore=None):
    relative = _file_relative(project, relativeFilePath)
    if not relative.lower().endswith(core.ENTRY_EXTENSIONS):
        raise ApiError("INVALID_VALUE", "An extra macro runs a .ms, .mse or .py file")
    title = str(buttonName).strip()
    if not core.SAFE_MACRO_TITLE.match(title):
        raise ApiError("INVALID_VALUE", "Extra macro button names allow only letters, spaces and underscores")
    compile_script = _as_bool("compileScript", compileScript)
    if compile_script and not relative.lower().endswith(".ms"):
        raise ApiError("INVALID_VALUE", "compileScript is available only for .ms files")
    macro = core.MacroItem(relative, title, compile_script, _as_bool("showInQuadMenu", showInQuadMenu))
    for index, other in enumerate(project.macros):
        if index != ignore and other.identifier.lower() == macro.identifier.lower():
            raise ApiError("DUPLICATE", "An extra macro with this button name already exists")
    return macro


@_operation("extraMacros.list")
def listExtraMacros():
    project, _model = _target()
    return {"macros": _macros(project)}


@_operation("extraMacros.add")
def addExtraMacro(relativeFilePath, buttonName, compileScript=False, showInQuadMenu=False):
    project, model = _target()
    project.macros.append(_macro(project, relativeFilePath, buttonName, compileScript, showInQuadMenu))
    _commit(project, model)
    return {"macros": _macros(project)}


@_operation("extraMacros.update")
def updateExtraMacro(macroIndex, relativeFilePath, buttonName, compileScript=False, showInQuadMenu=False):
    project, model = _target()
    position = _index(project.macros, macroIndex, "Macro")
    project.macros[position] = _macro(project, relativeFilePath, buttonName, compileScript, showInQuadMenu, position)
    _commit(project, model)
    return {"macros": _macros(project)}


@_operation("extraMacros.remove")
def removeExtraMacro(macroIndex):
    project, model = _target()
    del project.macros[_index(project.macros, macroIndex, "Macro")]
    _commit(project, model)
    return {"macros": _macros(project)}


@_operation("extraMacros.clear")
def clearExtraMacros():
    project, model = _target()
    project.macros = []
    _commit(project, model)
    return {"macros": []}


# ---- standard installer windows ---------------------------------------------------------------------------------
@_operation("hooks.add")
def addStandardHook(hookFileName):
    """Download the standard _install.ms or _uninstall.ms into the project's max-package folder (needs internet)."""
    from .core import updater
    project, model = _target()
    name = str(hookFileName).strip()
    if name not in core.HOOK_FILES:
        raise ApiError("INVALID_VALUE", "hookFileName must be _install.ms or _uninstall.ms")
    entry = (updater.fetch_manifest(UPDATE_URL).get("hooks") or {}).get(name)
    if not entry:
        raise ApiError("NOT_PUBLISHED", "{} is not published".format(name))
    os.makedirs(project.support_dir, exist_ok=True)
    updater.replace_file(entry["url"], entry.get("sha256", ""), os.path.join(project.support_dir, name))
    _commit(project, model)
    return {"standardHooks": {hook: bool(project.hook_path(hook)) for hook in core.HOOK_FILES}}


# ---- validation and build ---------------------------------------------------------------------------------------
def _issue(issue):
    return {"code": "VALIDATION", "level": issue.level, "message": issue.message, "tab": issue.tab,
            "field": issue.field, "where": issue.where()}


@_operation("package.validate")
def validate():
    """ok is true only when the package can be built; every problem is an error item with the field to fix."""
    project, model = _target()
    issues = core_validate.validate(project)
    if model is not None:
        model.validate_now()
    errors = [_issue(issue) for issue in issues if issue.level == core_validate.ERROR]
    warnings = [_issue(issue) for issue in issues if issue.level == core_validate.WARNING]
    _state["log"] = [(issue.level, str(issue)) for issue in issues] + [
        ("OK" if not errors else "ERROR", "Validation passed" if not errors else "Validation failed")]
    return not errors, {"valid": not errors, "issues": [_issue(i) for i in issues]}, errors, warnings


@_operation("package.build")
def build():
    """Validate and build the .mzp. Require ok == true and data.exists == true."""
    project, model = _target()
    if model is not None:
        model.save_now()
    result = core_build.build(project, DISPLAY_NAME, __version__)
    _state["log"] = list(result.messages)
    if model is not None:
        model.validate_now()
        window = getattr(_session(), "window", None)
        if window is not None:  # The window shows what this build did (log, green banner), as after a click
            window.show_build_result(result)
    exists = bool(result.output_file) and os.path.isfile(result.output_file)
    data = {"exists": exists, "outputFile": result.output_file, "size": result.size, "files": result.members,
            "messages": [{"level": level, "message": text} for level, text in result.messages]}
    errors = [{"code": "BUILD_FAILED", "message": text} for level, text in result.messages if level == "ERROR"]
    return result.ok and exists, data, errors, []


@_operation("log.get")
def getLog():
    """Messages of the last validate() or build()."""
    return {"entries": [{"level": level, "message": text} for level, text in _state["log"]]}


@_operation("log.clear")
def clearLogEntries():
    _state["log"] = []
    return {"entries": []}


PUBLIC = ["ping", "getSchema", "openProject", "getState", "save", "reload", "getOption", "setOption", "setOptions",
          "generateGuid", "listFiles", "addFile", "addFolder", "removeFile", "clearFiles", "setEntry",
          "listChangelog", "addChangelog", "updateChangelog", "removeChangelog", "clearChangelog",
          "listBuildPathRules", "addBuildPathRule", "updateBuildPathRule", "removeBuildPathRule",
          "clearBuildPathRules", "listExtraMacros", "addExtraMacro", "updateExtraMacro", "removeExtraMacro",
          "clearExtraMacros", "addStandardHook", "validate", "build", "getLog", "clearLogEntries"]
