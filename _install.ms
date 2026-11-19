/*

	MAXPKG PACKAGE INSTALLER

	Every package built by MaxPkg Packager carries this file and _uninstall.ms. Together they install and remove
	the package, with or without MaxPkg Manager:

	- With MaxPkg Manager (the MaxPkg global exists), they work silently and the Manager reports the result.
	- Without it, they show the package's own installer window: what the package is, what is new, Install,
	  Uninstall, and a clear message when this 3ds Max is not supported.

	The whole installer is this one file: a short MaxScript part (below) and its Python + Qt part (the comment
	block after it), which the MaxScript part runs in 3ds Max's own Python (3ds Max 2022 and newer).
	_uninstall.ms runs the same file to remove the package.

	For work that is special to your tool, choose a Custom Install Script and a Custom Uninstall Script in
	MaxPkg Packager instead of editing this file: they run from the package folder, before Install finishes and
	before the package files are removed.

	Run directly from a folder that is not an installed package ($temp\<GUID>), this file only shows a preview:
	nothing is installed or removed.

*/

(
	-- MaxScript names ignore case: a local here must never be spelled like a global it reads
	local hookFile = getSourceFileName()
	local hookMode = if (MaxPkgHookRequest == undefined) then "" else (MaxPkgHookRequest as string)
	global MaxPkgHookRequest = undefined
	if ((maxVersion())[1] < 24000) then (
		-- 3ds Max older than 2022: its Python cannot run the installer window
		local maxPkgHookMessage = "This package needs 3ds Max 2022 or newer.\n\nNothing was installed."
		if (MaxPkg != undefined) then throw maxPkgHookMessage else messageBox maxPkgHookMessage title: "MaxPkg"
	) else (
		global MaxPkgHookArguments = #(hookFile, hookMode)
		-- One expression, no names left in Python's shared namespace: a second run while a window is open
		-- (the package dragged in again) must not touch the first one's names
		python.Execute "import io, pymxs\n(lambda a: exec(compile(io.open(a[0], encoding='utf-8-sig').read().split('#@maxpkg' + '-python')[1].split('#@end' + '-maxpkg-python')[0], a[0], 'exec'), {'__name__': '__maxpkg_hook__', 'HOOK_FILE': a[0], 'HOOK_REQUEST': a[1]}))(list(pymxs.runtime.MaxPkgHookArguments))"
	)
)

/*
#@maxpkg-python
"""MaxPkg package installer: install, reinstall and remove a package built by MaxPkg Packager (3ds Max 2022+).

Runs in 3ds Max's Python. HOOK_FILE is this file, HOOK_REQUEST is "install" (from the package's mzp.run.ms),
"uninstall" (from _uninstall.ms) or "" (this file run on its own, or by an older mzp.run.ms).
"""

import io
import os
import re
import shutil
import sys
import time
import traceback

ENGINE = 1  # The installer protocol: mzp.run.ms and _uninstall.ms hand over to this file.
DEVELOPER = "Vasyl Lukianenko"  # Shown in About, with the site
SITE = "https://maxpkg.dev"
PACKAGER = "https://github.com/maxpkg-dev/max-dev-tool/releases/latest"
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TYPES = {"added": "success", "fixed": "warning", "improved": "info", "changed": "system", "removed": "error"}

THEME = {  # Warm Graphite, the default theme of MaxPkg tools
    "window": "#242320", "panel": "#292823", "surface": "#302e29", "field": "#1c1c1a", "recessed": "#191916",
    "hover": "#41382d", "pressed": "#35312a", "border": "#514b42", "group_border": "#62594c",
    "active_border": "#8e7455", "accent": "#dc9b57", "focus": "#e3a363", "heading": "#efb577", "text": "#e8e3da",
    "muted": "#b8b0a3", "dark_text": "#29232c", "link": "#efa35c", "tooltip": "#39342c",
    "success": "#78e196", "success_bg": "#35473a", "warning": "#ffc350", "warning_bg": "#4c4330",
    "error": "#ff7d7d", "error_bg": "#4c3633", "info": "#8ed0e0", "info_bg": "#38464a", "system": "#bea5ff",
    "system_bg": "#43404a", "danger": "#8f3a3a", "danger_hover": "#a54444", "danger_border": "#b85c5c",
    "danger_edge": "#bb5650", "danger_hover_edge": "#cf6a62",  # A lighter red than the fill: glass
    "danger_text": "#ffe1e1", "close_hover": "#9f3636",
}

ICONS = {  # Lucide (ISC license), stroke icons drawn in one colour
    "package": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "book": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    "cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "chevronRight": '<path d="m9 18 6-6-6-6"/>',
    "chevronDown": '<path d="m6 9 6 6 6-6"/>',
    "dot": '<circle cx="12" cy="12" r="5"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
}


# ---- 3ds Max ---------------------------------------------------------------------------------------------------------
def _rt():
    import pymxs
    return pymxs.runtime


def max_dir(name):
    rt = _rt()
    return str(rt.getDir(rt.Name(name)))


def global_value(name):
    """A MaxScript global, or None when it does not exist."""
    try:
        return getattr(_rt(), name)
    except Exception:  # noqa: BLE001
        return None


def run_modal(dialog):
    return (getattr(dialog, "exec", None) or getattr(dialog, "exec_"))()


def max_year():
    """The year of this 3ds Max (2022, 2025, ...)."""
    version = _rt().maxVersion()
    try:
        return int(version[7])
    except (IndexError, TypeError, ValueError):
        return 2000 + int(version[0]) // 1000 - 2


def ini(path, section, key, default=""):
    value = _rt().getINISetting(path, section, key)
    return str(value) if value else default


def to_int(text, default=0):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return default


def literal(text):
    """A MaxScript string literal."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def forward_literal(path):
    return '"' + str(path).replace("\\", "/").replace('"', '\\"') + '"'


def same_path(first, second):
    return os.path.normcase(os.path.abspath(first)).rstrip("\\/") == os.path.normcase(os.path.abspath(second)).rstrip("\\/")


def inside(path, folder):
    path = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder)).rstrip("\\/") + os.sep
    return path.startswith(folder)


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8-sig", newline="\r\n") as handle:
        handle.write(text)


def remove_file(path):
    """Delete a file; True when it is gone."""
    if not os.path.isfile(path):
        return True
    try:
        os.chmod(path, 0o666)
        os.remove(path)
    except OSError:
        return False
    return not os.path.isfile(path)


def pump(seconds):
    """Let 3ds Max handle its messages for a while (a custom uninstall script may need them)."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            QtWidgets().QApplication.processEvents()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.02)


# ---- The package ----------------------------------------------------------------------------------------------------
class Package(object):
    """A package as its manifest.ini describes it (written by MaxPkg Packager)."""

    def __init__(self, folder):
        self.folder = os.path.abspath(folder)
        self.manifest = os.path.join(self.folder, "manifest.ini")
        get = lambda key, default="": ini(self.manifest, "package", key, default)  # noqa: E731
        self.guid = get("packageGuid").strip()
        self.name = get("name") or "Package"
        self.button = get("buttonName") or self.name
        self.description = get("description")
        self.version = get("version") or "1.0.0"
        self.developer = get("developerName")
        self.license = get("license")
        self.license_url = get("licenseUrl")
        self.homepage = get("homepage")
        self.documentation = get("documentation")
        self.purchase = get("purchase")
        self.purchase_label = get("purchaseButtonLabel") or "Buy"
        self.entry = get("entry")
        self.icon = get("icon")
        self.create_button = get("createMacroButton").lower() == "true"
        self.min_max = to_int(get("min3dsMax"))
        self.max_max = to_int(get("max3dsMax"))
        self.custom_install = get("customInstallScript")
        self.custom_uninstall = get("customUninstallScript")
        self.macros = []
        for index in range(1, to_int(ini(self.manifest, "extraMacros", "count")) + 1):
            item = lambda key: ini(self.manifest, "extraMacros", "{}_{}".format(index, key))  # noqa: E731
            if item("file") and item("button"):
                self.macros.append({"file": item("file"), "button": item("button"),
                                    "macro": item("macro") or item("button").replace(" ", ""),
                                    "quad": item("quad").lower() == "true"})
        self.changelog = []
        for index in range(1, to_int(ini(self.manifest, "changelog", "count")) + 1):
            kind = ini(self.manifest, "changelog", "{}_type".format(index))
            text = ini(self.manifest, "changelog", "{}_text".format(index))
            if kind and text:
                self.changelog.append((kind, text.replace("\\n", "\n")))
        if not self.changelog:  # Packages of MaxPkg Packager 1.x keep their changelog next to the manifest
            older = os.path.join(self.folder, "maxpkg-changelog.ini")
            section = "version_" + self.version
            for index in range(1, to_int(ini(older, section, "count")) + 1):
                kind = ini(older, section, "{}_type".format(index))
                text = ini(older, section, "{}_text".format(index))
                if kind and text:
                    self.changelog.append((kind, text.replace("\\n", "\n")))

    @property
    def valid(self):
        return os.path.isfile(self.manifest) and bool(GUID.match(self.guid))

    @property
    def quad(self):
        return any(macro["quad"] for macro in self.macros)

    def icon_file(self):
        path = os.path.join(self.folder, "icons", "icon.svg")
        return path if self.icon and os.path.isfile(path) else ""

    def compatibility(self, year):
        """("block", text) when this 3ds Max is too old, ("note", text) when it is newer than the package knows,
        or ("", "")."""
        if self.min_max and year < self.min_max:
            return "block", "{} {} needs 3ds Max {} or newer. This is 3ds Max {}.".format(
                self.name, self.version, self.min_max, year)
        if self.max_max and year > self.max_max:
            return "note", "Made for 3ds Max {} to {}. It may also work in 3ds Max {}.".format(
                self.min_max or 2022, self.max_max, year)
        return "", ""


def is_installed_folder(package):
    """True when the package sits where MaxPkg extracts it ($temp\\<GUID>): only then are files changed."""
    if not package.valid:
        return False
    return same_path(package.folder, os.path.join(max_dir("temp"), package.guid))


def own_macro(path, guid):
    """True when a macro file was made for this package."""
    guid = guid.lower()
    name = os.path.basename(path).lower()
    if name.startswith("maxpkg-" + guid):
        return True
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as handle:
            return ("-- package guid: " + guid) in handle.read().lower()
    except OSError:
        return False


def macro_files(guid):
    folder = max_dir("userMacros")
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [os.path.join(folder, name) for name in names
            if name.lower().endswith(".mcr") and own_macro(os.path.join(folder, name), guid)]


def installed_state(package):
    """(installed, version) of this package in this 3ds Max: version "" when an older installer made it."""
    found = macro_files(package.guid)
    extra = [os.path.join(max_dir("userIcons"), package.guid + ".svg"),
             os.path.join(max_dir("userStartupScripts"), "maxpkg-" + package.guid + "-quad-startup.ms")]
    if not found and not any(os.path.isfile(path) for path in extra):
        return False, ""
    for path in found:
        try:
            with io.open(path, encoding="utf-8-sig", errors="replace") as handle:
                match = re.search(r"-- Package version: (\S+)", handle.read())
        except OSError:
            match = None
        if match:
            return True, match.group(1)
    return True, ""


# ---- Install and remove ---------------------------------------------------------------------------------------------
def macro_script(package, macro_name, button, run_line, comment):
    icon = os.path.join(max_dir("userIcons"), package.guid + ".svg")
    lines = ["macroScript " + macro_name, 'category: "MaxPkg"', "buttonText: " + literal(button),
             "tooltip: " + literal("Run " + button)]
    if package.icon:
        lines.append("iconName: " + forward_literal(icon))
    lines += ["(", "    on execute do", "    (", "        -- Generated by MaxPkg. https://maxpkg.dev",
              "        -- " + comment, "        -- Package GUID: " + package.guid,
              "        -- Package version: " + package.version, "        try", "        (",
              "            local packageGuid = " + literal(package.guid),
              '            local packageDir = (getDir #temp) + "\\\\" + packageGuid + "\\\\"'] + run_line + [
              "        )", "        catch", "        (",
              '            messageBox ("Could not run " + ' + literal(button) + ' + ".\\n" + getCurrentException()) title: "MaxPkg"',
              "        )", "    )", ")", ""]
    return "\n".join(lines)


def run_lines(entry_expression, missing):
    return ["            local entryPath = packageDir + " + entry_expression,
            "            local entryExt = toLower (getFilenameType entryPath)",
            "            if (not (doesFileExist entryPath)) do throw (" + literal(missing) + " + entryPath)",
            '            if (entryExt == ".py") then python.ExecuteFile entryPath else if (entryExt == ".ms" or '
            'entryExt == ".mse") then fileIn entryPath else throw ("Unsupported file type: " + entryExt)']


def install_icon(package):
    if not package.icon_file():
        return []
    try:
        target = os.path.join(max_dir("userIcons"), package.guid + ".svg")
        remove_file(target)
        shutil.copyfile(package.icon_file(), target)
    except OSError as error:
        return ["The icon could not be copied: {}".format(error)]
    return []


def install_macros(package):
    """The package's buttons (macroScripts in the MaxPkg group). A reinstall starts clean: buttons that the new
    version dropped go."""
    rt = _rt()
    problems = []
    for path in macro_files(package.guid):
        remove_file(path)
    macros = max_dir("userMacros")
    compact = package.guid.replace("-", "")
    scripts = []
    if package.create_button:
        manifest_lines = ['            local manifestIni = packageDir + "manifest.ini"',
                          '            local entry = getINISetting manifestIni "package" "entry"',
                          '            if (entry == "") do throw "The package has no entry file."']
        scripts.append((os.path.join(macros, "maxpkg-" + package.guid + ".mcr"),
                        macro_script(package, "MaxPkg_" + compact, package.button,
                                     manifest_lines + run_lines("entry", "The package file was not found: "),
                                     "This button was created when the package was installed.")))
    for macro in package.macros:
        suffix = macro["macro"]
        scripts.append((os.path.join(macros, "maxpkg-" + package.guid + "-" + suffix + ".mcr"),
                        macro_script(package, "MaxPkg_" + compact + "_" + suffix, macro["button"],
                                     run_lines(literal(macro["file"]), "The package file was not found: "),
                                     "This extra button was created when the package was installed.")))
    for path, text in scripts:
        try:
            write_text(path, text)
            rt.fileIn(path)
        except Exception as error:  # noqa: BLE001
            problems.append("A button could not be created ({}): {}".format(os.path.basename(path), error))
    return problems


def install_quad(package):
    rt = _rt()
    startup = os.path.join(max_dir("userStartupScripts"), "maxpkg-" + package.guid + "-quad-startup.ms")
    helper = os.path.join(package.folder, "maxpkg-quad.ms")
    if not package.quad:
        remove_file(startup)
        return []
    if not os.path.isfile(helper):
        return ["The quad menu helper is missing from the package."]
    command = "(MaxPkgQuadMenuManagerData packageFolder: " + literal(package.folder + "\\") + ").install()"
    try:
        write_text(startup, "(\n    try (\n        local helperFilePath = " + literal(helper) + "\n"
                   "        if (doesFileExist helperFilePath) do (\n            fileIn helperFilePath\n"
                   "            execute " + literal(command) + "\n        )\n    ) catch()\n)\n")
        rt.fileIn(helper)
        if rt.execute(command) is not True:
            return ["3ds Max did not accept the quad menu items."]
    except Exception as error:  # noqa: BLE001
        return ["The quad menu items could not be added: {}".format(error)]
    return []


def install_steps(package):
    """The steps of an install, in order: (what the window shows, a function returning a list of problems). The
    package's own install script, when it has one, comes last and raises when it fails."""
    steps = [("Copying its icon", lambda: install_icon(package)),
             ("Creating its buttons", lambda: install_macros(package) + ([] if package.quad else install_quad(package)))]
    if package.quad:
        steps.append(("Adding its quad menu items", lambda: install_quad(package)))
    if package.custom_install:
        steps.append(("Running its install script", lambda: run_custom(package, "install") or []))
    return steps


def run_custom(package, key, wait=0.0):
    """Run the package's Custom Install / Uninstall Script (a .ms inside the package folder). Raises on failure."""
    relative = package.custom_install if key == "install" else package.custom_uninstall
    if not relative:
        return
    path = os.path.abspath(os.path.join(package.folder, relative))
    if not path.lower().endswith(".ms") or not inside(path, package.folder):
        raise RuntimeError("The custom {} script must be a .ms file inside the package.".format(key))
    if not os.path.isfile(path):
        raise RuntimeError("The custom {} script is missing: {}".format(key, relative))
    _rt().fileIn(path)
    if wait:
        pump(wait)


def remove_quad(package):
    rt = _rt()
    problems = []
    helper = os.path.join(package.folder, "maxpkg-quad.ms")
    if os.path.isfile(helper):
        try:
            rt.fileIn(helper)
            command = "(MaxPkgQuadMenuManagerData packageFolder: " + literal(package.folder + "\\") + ").uninstall()"
            if rt.execute(command) is not True:
                problems.append("3ds Max kept the quad menu items.")
        except Exception as error:  # noqa: BLE001
            problems.append("The quad menu items could not be removed: {}".format(error))
    startup = os.path.join(max_dir("userStartupScripts"), "maxpkg-" + package.guid + "-quad-startup.ms")
    if not remove_file(startup):
        problems.append("A file is in use: {}. Restart 3ds Max and try again.".format(os.path.basename(startup)))
    return problems


def remove_buttons(package):
    problems = []
    for path in macro_files(package.guid) + [os.path.join(max_dir("userIcons"), package.guid + ".svg")]:
        if not remove_file(path):
            problems.append("A file is in use: {}. Restart 3ds Max and try again.".format(os.path.basename(path)))
    return problems


def remove_steps(package):
    """The steps of an uninstall, in order (as install_steps). The package's own uninstall script runs first and
    raises when it fails; any problem stops the steps that follow."""
    steps = []
    if package.custom_uninstall:
        steps.append(("Running its uninstall script", lambda: run_custom(package, "uninstall", wait=2.0) or []))
    steps += [("Removing its quad menu items", lambda: remove_quad(package)),
              ("Removing its buttons and icon", lambda: remove_buttons(package)),
              ("Removing the package files", lambda: remove_folder(package))]
    return steps


def remove_folder(package):
    if not is_installed_folder(package) or not os.path.isdir(package.folder):
        return []

    def unlock(function, path, _info):
        try:
            os.chmod(path, 0o777)
            function(path)
        except OSError:
            pass
    shutil.rmtree(package.folder, onerror=unlock)
    return [] if not os.path.isdir(package.folder) else ["The package folder could not be removed completely."]


def run_entry(package):
    path = os.path.join(package.folder, package.entry)
    rt = _rt()
    if not package.entry or not os.path.isfile(path):
        raise RuntimeError("The package file was not found: {}".format(package.entry or "(none)"))
    if path.lower().endswith(".py"):
        rt.python.ExecuteFile(path)
    else:
        rt.fileIn(path)


# ---- Silent mode (MaxPkg Manager) -----------------------------------------------------------------------------------
def manager_install(package):
    kind, text = package.compatibility(max_year())
    if kind == "block":
        raise RuntimeError(text)
    problems = []
    for _caption, step in install_steps(package):  # The package's own install script raises when it fails
        problems += step()
    if problems:
        raise RuntimeError("\n".join(problems))
    manager = global_value("MaxPkg")
    try:
        if manager is not None and _rt().isProperty(manager, _rt().Name("packageInstalled")):
            manager.packageInstalled(package.guid)
    except Exception:  # noqa: BLE001
        pass


def manager_uninstall(package):
    """MaxPkg Manager removes the files itself; the package's own cleanup runs here first."""
    run_custom(package, "uninstall", wait=2.0)


# ---- Qt ---------------------------------------------------------------------------------------------------------------
_QT = {}


def QtWidgets():  # noqa: N802 (a module-like accessor)
    _load_qt()
    return _QT["QtWidgets"]


def _load_qt():
    if _QT:
        return
    try:
        from PySide6 import QtCore, QtGui, QtSvg, QtWidgets as Widgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtSvg, QtWidgets as Widgets
    _QT.update(QtCore=QtCore, QtGui=QtGui, QtSvg=QtSvg, QtWidgets=Widgets)


def max_window():
    try:
        import qtmax
        return qtmax.GetQMaxMainWindow()
    except Exception:  # noqa: BLE001
        return None


SCALE = {"px": 1.0, "font": 1.0}


def measure_scale(anchor):
    """Interface size: 100 %, or Windows scaling when it is larger (3ds Max turns Qt's own scaling off, so sizes in
    pixels follow it here; fonts in points follow it by themselves)."""
    QtGui = _QT["QtGui"]
    screen = None
    if anchor is not None:
        center = anchor.frameGeometry().center()
        screen = QtGui.QGuiApplication.screenAt(center)
    screen = screen or QtGui.QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() or 1.0
    dpi = (screen.logicalDotsPerInch() or 96.0) / 96.0
    target = max(1.0, dpi * ratio)
    SCALE["px"] = max(0.5, target / ratio)
    SCALE["font"] = max(0.5, target / (dpi * ratio))


def px(value):
    return max(1, int(round(value * SCALE["px"])))


def pt(value):
    return value * SCALE["font"]


def icon_pixmap(name, color, size, file_path=""):
    QtCore, QtGui, QtSvg = _QT["QtCore"], _QT["QtGui"], _QT["QtSvg"]
    if file_path:
        renderer = QtSvg.QSvgRenderer(file_path)
    else:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
               'stroke="{}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
               ).format(color, ICONS[name])
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    image = QtGui.QImage(size * 2, size * 2, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    renderer.render(painter, QtCore.QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap = QtGui.QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


SHEET = """
QWidget#maxpkgWindow, QDialog#maxpkgWindow { background: @window; }
QWidget { color: @text; font-family: "Segoe UI"; font-size: 9pt; }
QLabel { background: transparent; }
QLabel#title { color: @accent; font-weight: bold; font-size: 10pt; }
QLabel#name { font-size: 15pt; font-weight: bold; color: @text; }
QLabel#muted { color: @muted; }
QLabel#heading { color: @heading; font-weight: bold; }
QLabel#bigText { font-size: 11pt; font-weight: bold; }
QFrame#iconTile { background: @field; border: 1px solid @border; border-radius: 10px; }
QFrame#card { background: @panel; border: 1px solid @group_border; border-radius: 8px; }
QFrame#success { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 @success_bg, stop: 1 transparent);
  border: 1px solid @success; border-radius: 6px; }
QFrame#warning { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 @warning_bg, stop: 1 transparent);
  border: 1px solid @warning; border-radius: 6px; }
QFrame#danger { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 @error_bg, stop: 1 transparent);
  border: 1px solid @error; border-radius: 6px; }
QFrame#info { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 @info_bg, stop: 1 transparent);
  border: 1px solid @info; border-radius: 6px; }
QLabel#successTitle { color: @success; font-weight: bold; }
QLabel#warningTitle { color: @warning; font-weight: bold; }
QLabel#dangerTitle { color: @error; font-weight: bold; }
QLabel#infoTitle { color: @info; font-weight: bold; }
QLabel#heroName { font-size: 16pt; font-weight: bold; color: @heading; }
QLabel#pageTitle { font-size: 12pt; font-weight: bold; color: @text; }
QLabel#caption { color: @muted; font-size: 8pt; }
QLabel#installedNote { color: @warning; font-size: 8pt; }
QLabel#tileValue { font-weight: bold; font-size: 10pt; }
QLabel#tileCaption { color: @muted; font-size: 8pt; }
QFrame#tile { background: @panel; border: 1px solid @border; border-radius: 8px; }
QFrame#notes { background: @panel; border: 1px solid @group_border; border-radius: 8px; }
QPushButton#fold { background: @panel; border: 1px solid @group_border; border-radius: 8px; padding: 0px;
  min-height: 36px; max-height: 36px; text-align: left; }
QPushButton#fold:hover { background: @surface; border-color: @active_border; }
QPushButton#fold[open="true"] { border-bottom-left-radius: 0px; border-bottom-right-radius: 0px; }
QFrame#drawer { background: @panel; border: 1px solid @group_border; border-top: none;
  border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px; }
QPushButton[variant="hero"] { background: @accent; color: @dark_text; border: 1px solid @focus; border-radius: 21px;
  min-height: 42px; max-height: 42px; padding: 0px 26px; font-size: 11pt; font-weight: bold; }
QPushButton[variant="hero"]:hover { background: @focus; }
QPushButton[variant="heroDanger"] { background: @danger; color: @danger_text; border: 1px solid @danger_edge;
  border-radius: 21px; min-height: 42px; max-height: 42px; padding: 0px 26px; font-size: 11pt; font-weight: bold; }
QPushButton[variant="heroDanger"]:hover { background: @danger_hover; border-color: @danger_hover_edge; }
QPushButton[variant="linkDanger"] { background: transparent; border: 1px solid transparent; color: @error;
  padding: 0px 10px; min-height: 26px; max-height: 26px; border-radius: 13px; }
QPushButton[variant="linkDanger"]:hover { background: @error_bg; border-color: @danger_border; }
QLabel#number { color: @accent; border: 1px solid @accent; border-radius: 9px; font-weight: bold; font-size: 8pt;
  min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; }
QPushButton { background: @surface; color: @text; border: 1px solid @border; border-radius: 15px; padding: 0px 14px;
  min-height: 28px; max-height: 28px; }
QPushButton:hover { background: @hover; border-color: @active_border; }
QPushButton:pressed { background: @pressed; }
QPushButton:focus { outline: none; }
QPushButton[variant="primary"] { background: @accent; color: @dark_text; border-color: @accent; font-weight: bold; }
QPushButton[variant="primary"]:hover { background: @focus; border-color: @focus; }
QPushButton[variant="danger"] { background: @danger; color: @danger_text; border-color: @danger_edge; }
QPushButton[variant="danger"]:hover { background: @danger_hover; border-color: @danger_hover_edge; }
QPushButton[variant="link"] { background: transparent; border: 1px solid transparent; color: @link; padding: 0px 8px;
  min-height: 24px; max-height: 24px; border-radius: 12px; }
QPushButton[variant="link"]:hover { background: @surface; border-color: @border; }
QPushButton[variant="support"] { background: transparent; border: 1px solid @success; color: @success; padding: 0px 10px;
  min-height: 24px; max-height: 24px; border-radius: 12px; font-weight: bold; }
QPushButton[variant="support"]:hover { background: @success_bg; }
QPushButton#close { background: transparent; border: 1px solid transparent; border-radius: 14px; padding: 0px;
  min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; }
QPushButton#close:hover { background: @close_hover; border-color: rgba(230, 120, 120, 150); }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: @group_border; border-radius: 2px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none;
  height: 0px; }
QToolTip { background: @tooltip; color: @text; border: 1px solid @active_border; padding: 4px 6px; }
"""


def style_sheet():
    text = SHEET
    for key in sorted(THEME, key=len, reverse=True):
        text = text.replace("@" + key, THEME[key])
    text = re.sub(r"(\d+(?:\.\d+)?)px", lambda m: "{}px".format(px(float(m.group(1)))), text)
    return re.sub(r"(\d+(?:\.\d+)?)pt", lambda m: "{:g}pt".format(round(pt(float(m.group(1))), 2)), text)


def round_corners(widget):
    """Windows 11 rounds a frameless window and gives it the system shadow (DWM)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = wintypes.HWND(int(widget.winId()))
        preference = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
        color = ctypes.c_uint(0x42 << 16 | 0x4b << 8 | 0x51)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(color), ctypes.sizeof(color))
    except (AttributeError, OSError, ValueError):
        pass


def open_url(address):
    if re.match(r"^https?://", address or "", re.I):
        QtGui = _QT["QtGui"]
        QtGui.QDesktopServices.openUrl(_QT["QtCore"].QUrl(address))


def accelerators(on):
    try:
        _rt().enableAccelerators = bool(on)
    except Exception:  # noqa: BLE001
        pass


def build_classes():
    """The window classes, made once Qt is loaded (PySide2 or PySide6)."""
    QtCore, QtGui, QtWidgets = _QT["QtCore"], _QT["QtGui"], _QT["QtWidgets"]
    Qt = QtCore.Qt

    def label(text="", name="", wrap=False, center=False):
        item = QtWidgets.QLabel(text)
        if name:
            item.setObjectName(name)
        item.setWordWrap(wrap)
        item.setTextFormat(Qt.PlainText)
        if center:
            item.setAlignment(Qt.AlignCenter)
        return item

    def button(text, icon="", variant="", tip=""):
        item = QtWidgets.QPushButton(text)
        item.setCursor(Qt.PointingHandCursor)
        if variant:
            item.setProperty("variant", variant)
        if icon:
            color = {"primary": THEME["dark_text"], "hero": THEME["dark_text"], "danger": THEME["danger_text"],
                     "heroDanger": THEME["danger_text"], "link": THEME["link"], "linkDanger": THEME["error"],
                     "support": THEME["success"]}.get(variant, THEME["text"])
            size = px(18) if variant in ("hero", "heroDanger") else px(15)
            # Segoe UI sits a pixel low in a button: the icon goes down as much, so their middles meet
            drop = px(1)
            pixmap = QtGui.QPixmap(size * 2, (size + 2 * drop) * 2)
            pixmap.setDevicePixelRatio(2.0)
            pixmap.fill(Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.drawPixmap(0, 2 * drop, icon_pixmap(icon, color, size))
            painter.end()
            item.setIcon(QtGui.QIcon(pixmap))
            item.setIconSize(QtCore.QSize(size, size + 2 * drop))
        if tip:
            item.setToolTip(tip)
        return item

    def frame(name, spacing=6, margins=(12, 9, 12, 10)):
        item = QtWidgets.QFrame()
        item.setObjectName(name)
        layout = QtWidgets.QVBoxLayout(item)
        layout.setContentsMargins(*[px(value) for value in margins])
        layout.setSpacing(px(spacing))
        return item, layout

    def banner(kind, title, text=""):
        item, layout = frame(kind, spacing=3)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(px(10))
        row.addWidget(StatusSign(kind, px(26), duration=550), 0, Qt.AlignTop)
        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(px(2))
        texts.addWidget(label(title, kind + "Title", wrap=True))
        if text:
            texts.addWidget(label(text, wrap=True))
        row.addLayout(texts, 1)
        layout.addLayout(row)
        return item

    def pill(text, color, background, width=0):
        item = QtWidgets.QLabel(text)
        item.setAlignment(Qt.AlignCenter)
        item.setStyleSheet("background: {}; color: {}; border-radius: {}px; padding: {}px {}px; font-size: {:g}pt;"
                           " font-weight: bold;".format(background, color, px(5), px(2), px(7), round(pt(8), 2)))
        if width:
            item.setFixedWidth(px(width))
        return item

    def centered(widget):
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(widget)
        row.addStretch(1)
        return row

    def short(text, size):
        return text if len(text) <= size else text[:size - 1].rstrip() + "\u2026"

    class IconTile(QtWidgets.QWidget):
        """The package's icon on a rounded tile with a soft glow behind it."""

        def __init__(self, package, color):
            QtWidgets.QWidget.__init__(self)
            self.color = QtGui.QColor(color)
            self.setFixedSize(px(78), px(78))
            self.pixmap = icon_pixmap("package", color, px(42), package.icon_file())

        def paintEvent(self, _event):  # noqa: N802
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            glow = QtGui.QRadialGradient(QtCore.QPointF(self.width() / 2.0, self.height() / 2.0), self.width() / 2.0)
            soft = QtGui.QColor(self.color)
            soft.setAlpha(70)
            glow.setColorAt(0.0, soft)
            glow.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), glow)
            tile = QtCore.QRectF(px(10), px(10), self.width() - px(20), self.height() - px(20))
            painter.setPen(QtGui.QPen(QtGui.QColor(THEME["border"]), 1))
            painter.setBrush(QtGui.QColor(THEME["field"]))
            painter.drawRoundedRect(tile, px(10), px(10))
            size = self.pixmap.width() / self.pixmap.devicePixelRatio()
            painter.drawPixmap(QtCore.QPointF((self.width() - size) / 2.0, (self.height() - size) / 2.0), self.pixmap)
            painter.end()

    class Hero(QtWidgets.QWidget):
        """The top of every page: the package's icon, name and one line, then what it is (`extra`), on a darker band
        that dissolves below them: no hard edge between it and the page."""

        def __init__(self, package, danger=False):
            QtWidgets.QWidget.__init__(self)
            self.danger = danger
            column = QtWidgets.QVBoxLayout(self)
            column.setContentsMargins(0, 0, 0, px(22))  # The band fades out in this room
            column.setSpacing(0)
            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(px(10), 0, px(16), px(8))
            layout.setSpacing(px(6))
            column.addLayout(layout)
            self.extra = QtWidgets.QVBoxLayout()
            self.extra.setContentsMargins(px(16), px(2), px(16), 0)
            self.extra.setSpacing(px(8))
            column.addLayout(self.extra)
            layout.addWidget(IconTile(package, THEME["error"] if danger else THEME["accent"]), 0, Qt.AlignVCenter)
            texts = QtWidgets.QVBoxLayout()
            texts.setSpacing(px(3))
            texts.addStretch(1)
            texts.addWidget(label(package.name, "heroName", wrap=True))
            byline = "Version " + package.version + ("  \xb7  " + package.developer if package.developer else "")
            texts.addWidget(label(byline, "muted", wrap=True))
            texts.addStretch(1)
            layout.addLayout(texts, 1)

        def paintEvent(self, _event):  # noqa: N802
            painter = QtGui.QPainter(self)
            height = float(max(1, self.height()))
            fade = min(0.95, 1.0 - px(34) / height)  # Where the band starts to dissolve, just under the badges
            band = QtGui.QLinearGradient(0, 0, 0, height)
            band.setColorAt(0.0, QtGui.QColor(0, 0, 0, 0))
            band.setColorAt(0.3, QtGui.QColor(0, 0, 0, 58))
            band.setColorAt(fade, QtGui.QColor(0, 0, 0, 46))
            band.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), band)
            if self.danger:  # Removing: the band takes a faint red
                tint = QtGui.QColor(THEME["error"])
                glow = QtGui.QLinearGradient(0, 0, 0, height)
                for stop, alpha in ((0.0, 0), (0.3, 20), (fade, 14), (1.0, 0)):
                    tint.setAlpha(alpha)
                    glow.setColorAt(stop, tint)
                painter.fillRect(self.rect(), glow)
            painter.end()

    class Ring(QtWidgets.QWidget):
        """Progress as a ring (0..1) with the share in the middle, or a full ring with a check when done."""

        def __init__(self, color, done=False):
            QtWidgets.QWidget.__init__(self)
            self.color = QtGui.QColor(color)
            self.value = 1.0 if done else 0.0
            self.done = done
            self.setFixedSize(px(84), px(84))

        def set_value(self, value):
            self.value = max(0.0, min(1.0, value))
            self.update()

        def paintEvent(self, _event):  # noqa: N802
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            width = px(6)
            box = QtCore.QRectF(width, width, self.width() - 2 * width, self.height() - 2 * width)
            glow = QtGui.QRadialGradient(box.center(), box.width() / 2.0)
            soft = QtGui.QColor(self.color)
            soft.setAlpha(45 if self.done else 25)
            glow.setColorAt(0.0, soft)
            glow.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(box)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(THEME["border"]), width, Qt.SolidLine, Qt.RoundCap))
            painter.drawEllipse(box)
            painter.setPen(QtGui.QPen(self.color, width, Qt.SolidLine, Qt.RoundCap))
            if self.value >= 1.0:
                painter.drawEllipse(box)
            elif self.value > 0:
                painter.drawArc(box, 90 * 16, -int(self.value * 360 * 16))
            if self.done:
                tick = QtGui.QPainterPath()
                center = box.center()
                unit = box.width() / 10.0
                tick.moveTo(center.x() - 2.2 * unit, center.y() + 0.1 * unit)
                tick.lineTo(center.x() - 0.6 * unit, center.y() + 1.7 * unit)
                tick.lineTo(center.x() + 2.4 * unit, center.y() - 1.6 * unit)
                painter.setPen(QtGui.QPen(self.color, px(5), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawPath(tick)
            else:
                font = painter.font()
                font.setPointSizeF(pt(11))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QtGui.QColor(THEME["text"]))
                painter.drawText(box, Qt.AlignCenter, "{}%".format(int(round(self.value * 100))))
            painter.end()

    class StatusSign(QtWidgets.QWidget):
        """An animated sign: its outline draws itself (circle, or a triangle for a warning), then its mark (check,
        cross, exclamation, i), with a soft glow. Plays once when shown."""

        COLORS = {"success": "success", "danger": "error", "warning": "warning", "info": "info"}

        def __init__(self, kind, size, duration=750, delay=0):
            QtWidgets.QWidget.__init__(self)
            self.kind = kind
            self.color = QtGui.QColor(THEME[self.COLORS[kind]])
            self.duration = duration
            self.setFixedSize(size, size)
            self.progress = 0.0
            self.clock = QtCore.QElapsedTimer()
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(16)
            self.timer.timeout.connect(self.tick)
            QtCore.QTimer.singleShot(delay, self.start)

        def start(self):
            self.clock.start()
            self.timer.start()

        def tick(self):
            self.progress = min(1.0, self.clock.elapsed() / float(self.duration))
            self.update()
            if self.progress >= 1.0:
                self.timer.stop()

        def shapes(self):
            """(pen width, ring path, mark paths) in this widget's coordinates: the tools' sign is a thin ring with a
            check, an exclamation mark or an i, on a tinted disc."""
            side = float(self.width())
            pen = max(1.4, side / 26.0)
            inset = side * 0.2
            box = QtCore.QRectF(inset, inset, side - 2 * inset, side - 2 * inset)
            center = box.center()
            unit = box.width() / 10.0
            ring = QtGui.QPainterPath()
            ring.moveTo(center.x(), box.top())
            ring.arcTo(box, 90, -360)
            if self.kind == "success":
                tick = QtGui.QPainterPath()
                tick.moveTo(center.x() - 2.6 * unit, center.y() + 0.1 * unit)
                tick.lineTo(center.x() - 0.8 * unit, center.y() + 1.9 * unit)
                tick.lineTo(center.x() + 2.7 * unit, center.y() - 1.8 * unit)
                return pen, ring, [tick]
            line, dot = QtGui.QPainterPath(), QtGui.QPainterPath()
            if self.kind == "info":
                line.moveTo(center.x(), center.y() - 0.2 * unit)
                line.lineTo(center.x(), center.y() + 2.4 * unit)
                dot.moveTo(center.x(), center.y() - 2.4 * unit)
                dot.lineTo(center.x(), center.y() - 2.35 * unit)
                return pen, ring, [dot, line]
            line.moveTo(center.x(), center.y() - 2.6 * unit)
            line.lineTo(center.x(), center.y() + 0.6 * unit)
            dot.moveTo(center.x(), center.y() + 2.4 * unit)
            dot.lineTo(center.x(), center.y() + 2.45 * unit)
            return pen, ring, [line, dot]

        @staticmethod
        def partial(path, share):
            """The first `share` (0..1) of a path, as a polyline."""
            if share <= 0:
                return None
            points = [path.pointAtPercent(min(1.0, share) * index / 40.0) for index in range(41)]
            return QtGui.QPolygonF(points)

        def paintEvent(self, _event):  # noqa: N802
            ease = lambda value: 1.0 - (1.0 - max(0.0, min(1.0, value))) ** 3  # noqa: E731
            pen_width, ring, marks = self.shapes()
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            grow = ease(self.progress / 0.35)  # The tinted disc swells in first
            if grow > 0:
                disc = QtGui.QColor(self.color)
                disc.setAlpha(int(48 * grow))
                radius = self.width() / 2.0 * (0.7 + 0.3 * grow)
                painter.setPen(Qt.NoPen)
                painter.setBrush(disc)
                painter.drawEllipse(QtCore.QPointF(self.width() / 2.0, self.height() / 2.0), radius, radius)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(self.color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            drawn = self.partial(ring, ease((self.progress - 0.1) / 0.5))
            if drawn is not None:
                painter.drawPolyline(drawn)
            share = ease((self.progress - 0.5) / 0.5)
            for index, mark in enumerate(marks):
                part = self.partial(mark, min(1.0, share * len(marks) - index))
                if part is not None:
                    painter.drawPolyline(part)
            painter.end()


    class Shimmer(QtWidgets.QWidget):
        """A light diagonal band that sweeps across a button every few seconds to draw the eye (as in MaxPkg
        Manager). Painted over the button, clipped to its rounded corners; clicks pass through."""

        SWEEP_MS = 900
        PAUSE_MS = 2600
        SLANT = 0.45

        def __init__(self, target, radius):
            QtWidgets.QWidget.__init__(self, target)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.radius = radius
            self.clock = QtCore.QElapsedTimer()
            self.clock.start()
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(33)
            self.timer.timeout.connect(self.tick)
            target.installEventFilter(self)
            self.follow()

        def tick(self):
            self.update()
            elapsed = self.clock.elapsed() % (self.SWEEP_MS + self.PAUSE_MS)
            self.timer.setInterval(33 if elapsed < self.SWEEP_MS else self.SWEEP_MS + self.PAUSE_MS - elapsed)

        def follow(self):
            target = self.parentWidget()
            if target is not None and target.isVisible():
                self.setGeometry(target.rect())
                self.raise_()
                self.show()
                self.timer.start()
            else:
                self.timer.stop()
                self.hide()

        def eventFilter(self, _watched, event):  # noqa: N802
            if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.Hide, QtCore.QEvent.Resize):
                self.follow()
            return False

        def paintEvent(self, _event):  # noqa: N802
            elapsed = self.clock.elapsed() % (self.SWEEP_MS + self.PAUSE_MS)
            if elapsed >= self.SWEEP_MS:
                return
            progress = elapsed / float(self.SWEEP_MS)
            progress = progress * progress * (3.0 - 2.0 * progress)
            width, height = float(self.width()), float(self.height())
            band = max(28.0, width * 0.35)
            x = -band - self.SLANT * height + progress * (width + 2.0 * band + 2.0 * self.SLANT * height)
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            clip = QtGui.QPainterPath()
            clip.addRoundedRect(QtCore.QRectF(self.rect()), self.radius, self.radius)
            painter.setClipPath(clip)
            gradient = QtGui.QLinearGradient(x - band / 2.0, 0.0, x + band / 2.0, self.SLANT * band)
            for stop, alpha in ((0.0, 0), (0.42, 46), (0.5, 80), (0.58, 46), (1.0, 0)):
                gradient.setColorAt(stop, QtGui.QColor(255, 255, 255, alpha))
            painter.fillRect(self.rect(), QtGui.QBrush(gradient))
            painter.end()

    class Confetti(QtWidgets.QWidget):
        """A burst of confetti from under the success sign when the package is installed: up and out to the sides,
        a little past the window, then the pieces flutter down and fade just below its bottom edge. A see-through
        layer over the screen around the window: no clicks, no focus, gone after a moment."""

        LIFE_MS = 5000

        def __init__(self, window, origin):
            flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
            if hasattr(Qt, "WindowTransparentForInput"):
                flags |= Qt.WindowTransparentForInput
            QtWidgets.QWidget.__init__(self, window, flags)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            frame = window.frameGeometry()
            area = frame.adjusted(-int(frame.width() * 0.55), -int(frame.height() * 0.45),
                                  int(frame.width() * 0.55), px(110))
            screen = QtGui.QGuiApplication.screenAt(frame.center()) or QtGui.QGuiApplication.primaryScreen()
            area = area.intersected(screen.availableGeometry())
            self.setGeometry(area)
            self.floor = frame.bottom() - area.top()  # Below the window's bottom edge the pieces fade out
            start = origin - area.topLeft()
            import math
            import random
            colors = [THEME[name] for name in ("accent", "success", "info", "system", "warning")]
            scale = SCALE["px"]
            self.pieces = []
            for index in range(90):
                angle = math.radians(random.uniform(-160, -20))  # A fan up and out to both sides
                speed = random.uniform(460, 860) * scale
                self.pieces.append({
                    "x": start.x() + random.uniform(-14, 14) * scale, "y": start.y(),
                    "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                    "tilt": random.uniform(-30, 30), "flip": random.uniform(0, 6.28), "rate": random.uniform(4, 7),
                    "w": 8 * scale, "h": 4.5 * scale, "color": QtGui.QColor(colors[index % len(colors)]),
                    # Each piece goes at its own moment: some early, some linger; most twinkle out in a flash
                    "life": max(0.6, (1.3 + 3.3 * random.random() ** 0.7) *
                                (1.0 - 0.75 * min(1.0, abs(math.cos(angle)) * speed / (700 * scale)) ** 1.4)),
                    "fade": random.uniform(0.12, 0.5),
                    "sparkle": random.random() < 0.7})
            self.clock = QtCore.QElapsedTimer()
            self.clock.start()
            self.last = 0
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(16)
            self.timer.timeout.connect(self.tick)
            self.timer.start()
            self.show()

        def tick(self):
            import math
            now = self.clock.elapsed()
            step = (now - self.last) / 1000.0
            self.last = now
            if now > self.LIFE_MS:
                self.timer.stop()
                self.close()
                self.deleteLater()
                return
            gravity = 650 * SCALE["px"]
            for piece in self.pieces:
                air = 0.985 ** (step * 60)
                piece["vx"] *= 0.963 ** (step * 60)  # The burst opens, then the pieces only fall
                piece["vy"] = min(piece["vy"] * air + gravity * step, 140 * SCALE["px"])  # A gentle fall
                piece["x"] += piece["vx"] * step
                piece["y"] += piece["vy"] * step
                piece["flip"] += piece["rate"] * step
            self.update()

        def paintEvent(self, _event):  # noqa: N802
            import math
            now = self.clock.elapsed()
            seconds = now / 1000.0
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            reach = 100.0 * SCALE["px"]  # Gone 100 px below the window
            for piece in self.pieces:
                below = (piece["y"] - self.floor) / reach
                if below >= 1.0:
                    continue
                left = (piece["life"] - seconds) / piece["fade"]  # Its last moments: it shrinks away
                if left <= 0:
                    flash = -left * piece["fade"] / 0.32  # Then, for most, a little star flashes where it was
                    if piece["sparkle"] and flash < 1.0:
                        self.twinkle(painter, piece, flash, 1.0 if below <= 0 else 1.0 - below)
                    continue
                own = min(1.0, left)
                painter.setOpacity(own * (1.0 if below <= 0 else 1.0 - below))
                painter.save()
                painter.translate(piece["x"], piece["y"])
                painter.scale(0.4 + 0.6 * own, 0.4 + 0.6 * own)
                painter.rotate(piece["tilt"] + 15 * math.sin(piece["flip"] * 0.5))
                painter.scale(1.0, max(0.2, abs(math.cos(piece["flip"]))))  # It turns over as it flutters
                painter.setBrush(piece["color"])
                painter.drawRoundedRect(QtCore.QRectF(-piece["w"] / 2, -piece["h"] / 2, piece["w"], piece["h"]), 1, 1)
                painter.restore()
            painter.end()

        @staticmethod
        def twinkle(painter, piece, flash, fade):
            """A four-pointed star in the piece's colour, white at its heart: it grows, turns a little and is gone."""
            size = (3.0 + 9.0 * (1.0 - (1.0 - flash) ** 2)) * SCALE["px"]
            waist = size * 0.18
            star = QtGui.QPainterPath()
            star.moveTo(0, -size)
            for x, y in ((waist, -waist), (size, 0), (waist, waist), (0, size), (-waist, waist), (-size, 0),
                         (-waist, -waist)):
                star.lineTo(x, y)
            star.closeSubpath()
            painter.save()
            painter.translate(piece["x"], piece["y"])
            painter.rotate(45 * flash)
            painter.setOpacity(fade * (1.0 - flash) ** 1.5)
            painter.setBrush(piece["color"].lighter(135))
            painter.drawPath(star)
            painter.setBrush(QtGui.QColor(255, 255, 255, 230))
            painter.drawEllipse(QtCore.QPointF(0, 0), waist * 0.9, waist * 0.9)
            painter.restore()

    class CloseButton(QtWidgets.QAbstractButton):
        """The round close button of the title bar: a true circle that turns red under the pointer, with a light
        edge, and the cross exactly in its middle (painted, so no style can move it)."""

        def __init__(self, size):
            QtWidgets.QAbstractButton.__init__(self)
            self.setFixedSize(size, size)
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Close")
            self.setAttribute(Qt.WA_Hover, True)

        def paintEvent(self, _event):  # noqa: N802
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            hovered = self.underMouse()
            if hovered:
                painter.setPen(QtGui.QPen(QtGui.QColor(230, 120, 120, 150), 1))
                painter.setBrush(QtGui.QColor("#842d2d" if self.isDown() else THEME["close_hover"]))
                painter.drawEllipse(box)
            arm = self.width() * 0.17
            center = box.center()
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff" if hovered else THEME["text"]), max(1.4, self.width() / 16.0),
                                      Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QtCore.QPointF(center.x() - arm, center.y() - arm), QtCore.QPointF(center.x() + arm, center.y() + arm))
            painter.drawLine(QtCore.QPointF(center.x() + arm, center.y() - arm), QtCore.QPointF(center.x() - arm, center.y() + arm))
            painter.end()

        def enterEvent(self, event):  # noqa: N802
            self.update()
            QtWidgets.QAbstractButton.enterEvent(self, event)

        def leaveEvent(self, event):  # noqa: N802
            self.update()
            QtWidgets.QAbstractButton.leaveEvent(self, event)

    class InfoButton(CloseButton):
        """The round "i" of the title bar that opens About: lit in the accent under the pointer."""

        def __init__(self, size):
            CloseButton.__init__(self, size)
            self.setToolTip("About this installer")

        def paintEvent(self, _event):  # noqa: N802
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            hovered = self.underMouse()
            if hovered:
                painter.setPen(QtGui.QPen(QtGui.QColor(THEME["active_border"]), 1))
                painter.setBrush(QtGui.QColor(THEME["pressed"] if self.isDown() else THEME["hover"]))
                painter.drawEllipse(box)
            color = QtGui.QColor(THEME["heading"] if hovered else THEME["text"])
            center = box.center()
            unit = self.width() / 28.0
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(color, max(1.4, self.width() / 18.0), Qt.SolidLine, Qt.RoundCap))
            painter.drawEllipse(center, 8.5 * unit, 8.5 * unit)
            painter.drawLine(QtCore.QPointF(center.x(), center.y() - 0.6 * unit),
                             QtCore.QPointF(center.x(), center.y() + 4.0 * unit))
            painter.drawPoint(QtCore.QPointF(center.x(), center.y() - 4.0 * unit))
            painter.end()

    class Window(QtWidgets.QDialog):
        """A frameless window in the look of MaxPkg tools: own title bar, round red close, rounded corners."""

        def __init__(self, title, parent, width, height, modal=False):
            QtWidgets.QDialog.__init__(self, parent)
            self.setObjectName("maxpkgWindow")
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setModal(modal)
            self.setWindowTitle(title)
            self.setStyleSheet(style_sheet())
            self.setFixedSize(px(width), px(height))
            self._drag = None
            self.busy = False
            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(px(1), px(1), px(1), px(1))
            outer.setSpacing(0)
            self.title_bar = QtWidgets.QWidget()
            bar = QtWidgets.QHBoxLayout(self.title_bar)
            bar.setContentsMargins(px(12), px(7), px(7), px(3))
            bar.setSpacing(px(8))
            mark = QtWidgets.QLabel()
            mark.setPixmap(icon_pixmap("package", THEME["accent"], px(18)))
            bar.addWidget(mark)
            self.title_label = label(title, "title")
            bar.addWidget(self.title_label, 1)
            close = CloseButton(px(28))
            close.clicked.connect(self.close)
            self.close_button = close
            bar.addWidget(close, 0, Qt.AlignVCenter)
            self.title_bar.installEventFilter(self)
            outer.addWidget(self.title_bar)
            self.header = QtWidgets.QVBoxLayout()
            self.header.setContentsMargins(0, 0, 0, 0)
            self.header.setSpacing(0)
            outer.addLayout(self.header)
            self.content = QtWidgets.QWidget()
            self.body = QtWidgets.QVBoxLayout(self.content)
            self.body.setContentsMargins(px(16), px(12), px(16), px(4))
            self.body.setSpacing(px(8))
            outer.addWidget(self.content, 1)
            self.footer = QtWidgets.QHBoxLayout()
            self.footer.setContentsMargins(px(16), px(8), px(16), px(14))
            self.footer.setSpacing(px(8))
            outer.addLayout(self.footer)

        def set_title(self, text):
            self.title_label.setText(text)
            self.setWindowTitle(text)

        def showEvent(self, event):  # noqa: N802
            QtWidgets.QDialog.showEvent(self, event)
            round_corners(self)

        def changeEvent(self, event):  # noqa: N802
            if event.type() == QtCore.QEvent.ActivationChange:
                accelerators(not self.isActiveWindow())  # 3ds Max keys stay off while the window has focus
            QtWidgets.QDialog.changeEvent(self, event)

        def keyPressEvent(self, event):  # noqa: N802
            if event.key() == Qt.Key_Escape:
                self.close()
                return
            QtWidgets.QDialog.keyPressEvent(self, event)

        def closeEvent(self, event):  # noqa: N802
            if self.busy:  # Never in the middle of installing or removing
                event.ignore()
                return
            accelerators(True)
            QtWidgets.QDialog.closeEvent(self, event)

        def paintEvent(self, event):  # noqa: N802
            QtWidgets.QDialog.paintEvent(self, event)
            painter = QtGui.QPainter(self)
            bottom = self.title_bar.geometry().bottom() + px(12)
            shade = QtGui.QLinearGradient(0, 0, 0, bottom)
            shade.setColorAt(0.0, QtGui.QColor(0, 0, 0, 80))
            shade.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, self.width(), bottom, shade)
            painter.setPen(QtGui.QColor(THEME["border"]))
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
            painter.end()

        def eventFilter(self, watched, event):  # noqa: N802
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag = self._global(event) - self.frameGeometry().topLeft()
                return True
            if kind == QtCore.QEvent.MouseMove and self._drag is not None:
                self.move(self._global(event) - self._drag)
                return True
            if kind == QtCore.QEvent.MouseButtonRelease:
                self._drag = None
            return False

        @staticmethod
        def _global(event):
            return event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()

        def center_on(self, anchor):
            if anchor is None:
                return
            area = anchor.frameGeometry()
            self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)

        def clear(self):
            for layout in (self.header, self.body, self.footer):
                _drop_layout(layout)

    def _drop_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout() is not None:
                _drop_layout(item.layout())

    class Message(Window):
        """The installer's own message: a large sign, a title, a text and its buttons (the last is the main one)."""

        def __init__(self, parent, title, heading, text, kind="warning", buttons=(("Close", None),)):
            Window.__init__(self, title, parent, 420, 260, modal=True)
            color = THEME["warning" if kind == "warning" else "error" if kind == "danger" else "info"]
            self.body.addSpacing(px(4))
            self.body.addLayout(centered(StatusSign(kind, px(60))))
            self.body.addWidget(label(heading, "pageTitle", wrap=True, center=True))
            self.body.addWidget(label(text, "muted", wrap=True, center=True))
            self.body.addStretch(1)
            self.footer.addStretch(1)
            for index, (caption, action) in enumerate(buttons):
                item = button(caption, variant="primary" if index == len(buttons) - 1 else "")
                item.setMinimumWidth(px(110))
                item.clicked.connect(self._make(action))
                self.footer.addWidget(item)
                if index == len(buttons) - 1:
                    item.setDefault(True)
                    item.setFocus()
            self.footer.addStretch(1)

        def _make(self, action):
            def run():
                self.accept()
                if action:
                    action()
            return run

    class About(Window):
        """What this installer is, who made it and where it comes from."""

        def __init__(self, parent):
            Window.__init__(self, "About MaxPkg Installer", parent, 380, 300, modal=True)
            tile, tile_layout = frame("iconTile", margins=(10, 10, 10, 10))
            mark = QtWidgets.QLabel()
            mark.setPixmap(icon_pixmap("package", THEME["accent"], px(36)))
            tile_layout.addWidget(mark)
            self.body.addSpacing(px(2))
            self.body.addLayout(centered(tile))
            self.body.addWidget(label("MaxPkg Package Installer", "pageTitle", center=True))
            self.body.addWidget(label("Installs, updates and removes packages for 3ds Max.", "muted", wrap=True,
                                      center=True))
            card, layout = frame("notes", spacing=6, margins=(14, 11, 14, 12))
            layout.addWidget(label("Every package built with MaxPkg Packager brings this installer. It shows what the "
                                   "package is and what is new, adds its buttons and icon on Install, and takes "
                                   "everything away again on Uninstall. With MaxPkg Manager the same files work "
                                   "silently.", wrap=True))
            self.body.addWidget(card)
            facts = QtWidgets.QGridLayout()
            facts.setHorizontalSpacing(px(14))
            facts.setVerticalSpacing(px(3))
            for row, (caption, value, address) in enumerate((("Developer", DEVELOPER, ""),
                                                             ("Made with", "MaxPkg Packager", PACKAGER))):
                facts.addWidget(label(caption, "muted"), row, 0)
                shown = label(value)
                if address:  # The packager's newest release, where it is downloaded
                    shown.setText('<a href="{}" style="color: {}; text-decoration: none;">{}</a>'.format(
                        address, THEME["link"], value))
                    shown.setTextFormat(Qt.RichText)
                    shown.setCursor(Qt.PointingHandCursor)
                    shown.setToolTip(address)
                    shown.linkActivated.connect(open_url)
                facts.addWidget(shown, row, 1)
            facts.setColumnStretch(1, 1)
            self.body.addLayout(facts)
            self.body.addWidget(label("Icons: Lucide (ISC).", "caption"))
            self.body.addStretch(1)
            site = button("maxpkg.dev", "globe", "link", SITE)
            site.clicked.connect(lambda: open_url(SITE))
            self.footer.addWidget(site)
            self.footer.addStretch(1)
            close = button("Close", variant="primary")
            close.setMinimumWidth(px(110))
            close.clicked.connect(self.accept)
            close.setDefault(True)
            self.footer.addWidget(close)
            # As tall as it needs: laid out once off screen (wrapped text needs the real width)
            self.setAttribute(Qt.WA_DontShowOnScreen, True)
            self.show()
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            self.layout().activate()
            self.setFixedHeight(self.layout().totalHeightForWidth(self.width()) + px(6))
            self.hide()
            self.setAttribute(Qt.WA_DontShowOnScreen, False)

    class Installer(Window):
        """The package's installer: install, reinstall, uninstall, each with its progress and result."""

        def __init__(self, package, mode, real, parent):
            Window.__init__(self, "Install " + package.name, parent, 440, 560)
            self.package = package
            self.real = real  # False: a preview (this file outside an installed package): nothing is changed
            self.installed, self.installed_version = installed_state(package)
            self.did_install = False
            self.did_remove = False
            self.expanded = False
            self.year = max_year()
            if not real:
                note = pill("Preview", THEME["info"], THEME["info_bg"])
                note.setFixedHeight(px(20))
                note.setToolTip("This file runs outside an installed package: nothing is installed or removed.")
                self.title_bar.layout().insertWidget(2, note, 0, Qt.AlignVCenter)
            info = InfoButton(px(28))
            info.clicked.connect(self.show_about)
            bar = self.title_bar.layout()
            bar.insertWidget(bar.indexOf(self.close_button), info, 0, Qt.AlignVCenter)
            self.first_page = (lambda: self.show_uninstall(from_main=False)) if mode == "uninstall" else self.show_main
            self.first_page()

        def anchor(self, widget):
            """Start the page's main element (Install, the ring, the result sign, Uninstall), the first thing under
            the header: a gap above it puts it at the height every page shares. The caller adds the element right
            after, then the page's details, then calls anchor_end(): the free space collects there, at the bottom."""
            self.anchor_widget = widget
            self.anchor_gap = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            self.body.addItem(self.anchor_gap)

        def anchor_end(self):
            self.anchor_free = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum,
                                                     QtWidgets.QSizePolicy.Expanding)
            self.body.addItem(self.anchor_free)

        def relayout(self):
            """Lay the window out now. Twice: wrapped text gets its height only once its width is known."""
            for _round in range(2):
                self.body.invalidate()
                self.layout().invalidate()
                self.layout().activate()

        def anchor_centre(self):
            return self.anchor_widget.mapTo(self, QtCore.QPoint(0, self.anchor_widget.height() // 2)).y()

        def anchor_range(self):
            """(lowest, highest) centre of the main element on this page, in window pixels."""
            self.anchor_gap.changeSize(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            self.relayout()
            low = self.anchor_centre()
            return low, low + self.anchor_free.geometry().height()

        def place_anchor(self):
            """Put the page's main element at the height every page shares (as far as this page lets it). The open
            notes give way to it: they scroll in what is left."""
            if getattr(self, "anchor_widget", None) is None:
                return
            low, high = self.anchor_range()
            target = getattr(self, "anchor_target", low)
            gap = int(max(0, (target if self.expanded else min(target, high)) - low))
            self.anchor_gap.changeSize(0, gap, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            self.relayout()

        def settle(self):
            """New children show on the next event loop: place the main element then, before it is painted."""
            self.content.setUpdatesEnabled(False)

            def done():
                try:
                    self.place_anchor()
                finally:
                    self.content.setUpdatesEnabled(True)
            QtCore.QTimer.singleShot(0, done)

        def fit_height(self):
            """As tall as its tallest page needs, then fixed: no page is cut, the window never jumps, and the
            notes open inside it. Measured on screen (wrapped text needs the real width)."""
            state = self.installed, self.installed_version, self.expanded
            tallest = 0
            pages = [self.show_main, lambda: self.show_progress("install"), lambda: self.show_done([]),
                     lambda: self.show_uninstall(True), self.show_removed]
            for page in pages:  # With the notes closed: open, they take the free space and scroll in it
                for installed in (False, True):
                    self.installed, self.installed_version, self.expanded = installed, "0.0.0" if installed else "", False
                    page()
                    # New children of a shown window appear on the next event loop: only then are they measured
                    QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                    self.layout().activate()
                    need = self.layout().totalHeightForWidth(self.width())
                    if page == self.show_main and self.package.changelog:
                        need += px(110)  # Room for a few notes when they are open
                    tallest = max(tallest, need)
            self.setFixedHeight(max(px(380), min(px(660), tallest + px(16))))  # Room to breathe
            # The main element of every page (Install, the ring, the result) at one height, so nothing jumps
            ranges = []
            for page in pages:
                for installed in (False, True):
                    self.installed, self.installed_version, self.expanded = installed, "0.0.0" if installed else "", False
                    page()
                    QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                    ranges.append(self.anchor_range())
            # Where the page that needs it lowest has it, plus a little air under the header
            low, high = max(r[0] for r in ranges), min(r[1] for r in ranges)
            self.anchor_target = min(low + px(10), high) if low <= high else high
            self.installed, self.installed_version, self.expanded = state
            self.first_page()

        def measure(self):
            """Lay the pages out once off screen (styles applied, real width), then fix the height."""
            self.setAttribute(Qt.WA_DontShowOnScreen, True)
            self.show()
            self.fit_height()
            self.hide()
            self.setAttribute(Qt.WA_DontShowOnScreen, False)

        # Parts ------------------------------------------------------------------------------------------------
        def preview_note(self):
            """A preview says so in the title bar (set once); the pages stay as the real ones."""

        def about(self):
            """What the package is, in the header band of every page (only what is below it changes)."""
            hero = self.header.itemAt(0).widget()
            if self.package.description:
                hero.extra.addWidget(label(self.package.description, "muted", wrap=True))
            hero.extra.addLayout(self.facts())

        def facts(self):
            package = self.package
            kind, _text = package.compatibility(self.year)
            years = "{}\u2013{}".format(package.min_max or 2022, package.max_max) if package.max_max else \
                "{}+".format(package.min_max or 2022)
            items = [("Version", package.version, ""), ("3ds Max", years, "warning" if kind == "note" else "success")]
            if package.license:
                items.append(("License", package.license, ""))
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(px(8))
            for caption, value, tone in items:
                tile, layout = frame("tile", spacing=1, margins=(10, 6, 10, 7))
                shown = label(short(value, 18), "tileValue")
                if tone:
                    shown.setStyleSheet("color: {};".format(THEME[tone]))
                shown.setToolTip(value)
                layout.addWidget(shown)
                layout.addWidget(label(caption, "tileCaption"))
                row.addWidget(tile, 1)
            return row

        def links(self):
            package = self.package
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(px(4))
            row.addStretch(1)
            support = "heart" if re.search(r"donat|support|tip", package.purchase_label, re.I) else "cart"
            for text, icon, address in (("Website", "globe", package.homepage), ("Docs", "book", package.documentation),
                                        ("License", "file", package.license_url),
                                        (package.purchase_label, support, package.purchase)):
                if re.match(r"^https?://", address or "", re.I):
                    # Buy or Donate stands out: green, in its outline
                    item = button(text, icon, "support" if address == package.purchase else "link", address)
                    item.clicked.connect(lambda _checked=False, url=address: open_url(url))
                    row.addWidget(item)
            row.addStretch(1)
            return row if row.count() > 2 else None

        def notes(self):
            """'What's new' as a row that opens the notes below it (closed until it is clicked)."""
            package = self.package
            toggle = QtWidgets.QPushButton()
            toggle.setObjectName("fold")
            toggle.setCursor(Qt.PointingHandCursor)
            row = QtWidgets.QHBoxLayout(toggle)
            row.setContentsMargins(px(12), 0, px(12), 0)
            row.setSpacing(px(8))
            chevron = QtWidgets.QLabel()
            chevron.setPixmap(icon_pixmap("chevronDown" if self.expanded else "chevronRight", THEME["heading"], px(15)))
            row.addWidget(chevron)
            row.addWidget(label("What's new in " + package.version, "heading"))
            row.addStretch(1)
            count = len(package.changelog)
            if count:
                badge = pill("{} change{}".format(count, "" if count == 1 else "s"), THEME["muted"], THEME["surface"])
                badge.setFixedHeight(px(20))
                row.addWidget(badge, 0, Qt.AlignVCenter)
            toggle.clicked.connect(self.toggle_notes)
            toggle.setProperty("open", "true" if self.expanded else "false")
            drawer = QtWidgets.QVBoxLayout()  # The row and its notes read as one block
            drawer.setSpacing(0)
            drawer.addWidget(toggle)
            self.body.addLayout(drawer, 1 if self.expanded else 0)  # Open, it grows into the free space
            if not self.expanded:
                return
            panel, outer = frame("drawer", spacing=0, margins=(1, 6, 1, 6))  # The border stays still
            holder = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(holder)
            layout.setContentsMargins(px(11), px(4), px(10), px(4))  # Room for the scroll bar on the right
            layout.setSpacing(px(8))
            for kind, text in package.changelog or [("", "No notes for this version.")]:
                line = QtWidgets.QHBoxLayout()
                line.setSpacing(px(10))
                if kind:
                    role = TYPES.get(kind.strip().lower(), "")
                    line.addWidget(pill(kind.strip().capitalize(), THEME.get(role, THEME["text"]),
                                        THEME.get(role + "_bg", THEME["surface"]), 74), 0, Qt.AlignTop)
                line.addWidget(label(text, wrap=True, name="" if kind else "muted"), 1)
                layout.addLayout(line)
            layout.addStretch(1)
            area = QtWidgets.QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QtWidgets.QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(holder)
            holder.adjustSize()
            area.setMinimumHeight(min(holder.sizeHint().height(), px(90)))  # Long notes scroll inside the border
            area.setMaximumHeight(holder.sizeHint().height())
            area.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
            panel.setMaximumHeight(holder.sizeHint().height() + px(12) + 2)
            outer.addWidget(area)
            drawer.addWidget(panel)

        def toggle_notes(self):
            self.expanded = not self.expanded
            self.show_main()

        def what_it_adds(self):
            package = self.package
            parts = []
            if package.create_button:
                parts.append("a button in the MaxPkg group")
            if package.macros:
                parts.append("{} more button{}".format(len(package.macros), "" if len(package.macros) == 1 else "s"))
            quad = sum(1 for macro in package.macros if macro["quad"])
            if quad:
                parts.append("{} quad menu item{}".format(quad, "" if quad == 1 else "s"))
            if not parts:
                return ""
            text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
            return "Adds " + text + "."

        # Pages ----------------------------------------------------------------------------------------------------
        def show_main(self, problem=""):
            self.clear()
            package = self.package
            same = self.installed and self.installed_version == package.version
            self.set_title(("Reinstall " if same else "Update " if self.installed else "Install ") + package.name)
            self.header.addWidget(Hero(package))
            self.preview_note()
            self.about()
            caption = "Reinstall" if same else "Update" if self.installed else "Install"
            main = button(caption, "refresh" if same else "download", "hero")
            self.anchor(main)
            main.setMinimumWidth(px(250))
            main.clicked.connect(self.install)
            main.setDefault(True)
            main.shimmer = Shimmer(main, px(21))  # A light that sweeps across it now and then
            self.body.addLayout(centered(main))
            if self.installed:
                note = ("Version {} is installed here.".format(self.installed_version) if self.installed_version
                        else "An earlier version is installed here.")
                self.body.addWidget(label(note, "installedNote", wrap=True, center=True))
            else:
                adds = self.what_it_adds()
                if adds:
                    self.body.addWidget(label(adds, "caption", wrap=True, center=True))
            if self.installed:
                remove = button("Uninstall", "trash", "linkDanger", "Remove {} from this 3ds Max".format(package.name))
                remove.clicked.connect(lambda: self.show_uninstall(from_main=True))
                self.body.addLayout(centered(remove))
            self.body.addSpacing(px(6))
            if problem:
                self.body.addWidget(banner("danger", "Not installed", problem))
            kind, text = package.compatibility(self.year)
            if kind == "note":
                self.body.addWidget(banner("warning", "Not marked for 3ds Max {}".format(self.year), text))
            self.anchor_end()
            self.notes()
            links = self.links()
            if links is not None:
                self.footer.addLayout(links, 1)
            self.settle()

        def show_progress(self, kind):
            self.clear()
            package = self.package
            removing = kind == "remove"
            self.set_title(("Removing " if removing else "Installing ") + package.name)
            self.header.addWidget(Hero(package, danger=removing))
            self.preview_note()
            self.about()
            self.ring = Ring(THEME["error"] if removing else THEME["accent"])
            self.anchor(self.ring)
            self.body.addLayout(centered(self.ring))
            self.step_label = label("Getting ready", "pageTitle", wrap=True, center=True)
            self.body.addWidget(self.step_label)
            steps = remove_steps(package) if removing else install_steps(package)
            panel, layout = frame("notes", spacing=6, margins=(14, 10, 14, 11))
            self.step_rows = []
            for caption, _function in steps:
                line = QtWidgets.QHBoxLayout()
                line.setSpacing(px(10))
                mark = QtWidgets.QLabel()
                mark.setPixmap(icon_pixmap("dot", THEME["border"], px(14)))
                line.addWidget(mark)
                text = label(caption, "muted")
                line.addWidget(text, 1)
                layout.addLayout(line)
                self.step_rows.append((mark, text))
            self.body.addSpacing(px(6))
            self.body.addWidget(panel)
            self.anchor_end()
            self.steps = steps
            self.settle()

        def show_done(self, problems, celebrate=False):
            self.clear()
            package = self.package
            self.set_title(package.name + " is installed")
            self.header.addWidget(Hero(package))
            self.preview_note()
            self.about()
            sign = StatusSign("success", px(84))
            self.anchor(sign)
            self.body.addLayout(centered(sign))
            self.body.addWidget(label("Installed", "pageTitle", center=True))
            self.body.addWidget(label("{} {} is ready in this 3ds Max.".format(package.name, package.version),
                                      "muted", wrap=True, center=True))
            self.body.addSpacing(px(6))
            for problem in problems:
                self.body.addWidget(banner("warning", "Installed with a problem", problem))
            if package.create_button or package.macros:
                panel, layout = frame("notes", spacing=8, margins=(14, 11, 14, 12))
                layout.addWidget(label("Put its button on a toolbar", "heading"))
                for index, text in enumerate(("Customize \u203a Customize User Interface",
                                              "Group: MaxPkg",
                                              "Drag {} onto a toolbar".format(package.button))):
                    line = QtWidgets.QHBoxLayout()
                    line.setSpacing(px(10))
                    number = label(str(index + 1), "number")
                    number.setAlignment(Qt.AlignCenter)
                    line.addWidget(number)
                    line.addWidget(label(text, wrap=True), 1)
                    layout.addLayout(line)
                self.body.addWidget(panel)
            self.anchor_end()
            if package.create_button or package.macros:
                customize = button("Customize UI", "settings", tip="Open Customize User Interface")
                customize.clicked.connect(self.open_customize)
                self.footer.addWidget(customize)
            self.footer.addStretch(1)
            close = button("Close")
            close.clicked.connect(self.close)
            self.footer.addWidget(close)
            if package.entry:
                run = button("Run it now", "play", "primary", "Close this window and run " + package.name)
                run.clicked.connect(self.run_now)
                run.setDefault(True)
                self.footer.addWidget(run)
            self.settle()
            if celebrate:  # A burst from under the success sign
                QtCore.QTimer.singleShot(80, lambda: setattr(self, "confetti", Confetti(
                    self, sign.mapToGlobal(QtCore.QPoint(sign.width() // 2, sign.height() // 2)))))

        def show_uninstall(self, from_main, problem=""):
            self.clear()
            package = self.package
            self.set_title("Uninstall " + package.name)
            self.header.addWidget(Hero(package, danger=True))
            self.preview_note()
            self.about()
            remove = button("Uninstall", "trash", "heroDanger")
            remove.setMinimumWidth(px(250))
            remove.clicked.connect(lambda: self.uninstall(from_main))
            self.anchor(remove)
            self.body.addLayout(centered(remove))
            cancel = button("Back" if from_main else "Cancel", variant="link")
            cancel.clicked.connect(self.show_main if from_main else self.close)
            self.body.addLayout(centered(cancel))
            self.body.addSpacing(px(6))
            if problem:
                self.body.addWidget(banner("danger", "Not removed", problem))
            if not self.installed:
                self.body.addWidget(banner("info", "{} is not installed here".format(package.name),
                                           "Uninstall still removes whatever it finds of it."))
            lines = ["Its buttons and icon"]
            quad = sum(1 for macro in package.macros if macro["quad"])
            if quad:
                lines.append("{} quad menu item{}".format(quad, "" if quad == 1 else "s"))
            lines.append("The package files")
            if package.custom_uninstall:
                lines.insert(0, "Runs its own uninstall script first")
            panel, layout = frame("danger", spacing=6, margins=(14, 11, 14, 12))
            layout.addWidget(label("Uninstall removes", "dangerTitle"))
            for line in lines:
                layout.addWidget(label("\u2022  " + line, wrap=True))
            self.body.addWidget(panel)
            self.anchor_end()
            self.settle()

        def show_removed(self):
            self.clear()
            package = self.package
            self.set_title(package.name + " is removed")
            self.header.addWidget(Hero(package, danger=True))
            self.preview_note()
            self.about()
            sign = StatusSign("success", px(84))
            self.anchor(sign)
            self.body.addLayout(centered(sign))
            self.body.addWidget(label("Removed", "pageTitle", center=True))
            self.body.addWidget(label("{} is gone from this 3ds Max. Its buttons leave Customize User Interface "
                                      "when 3ds Max restarts.".format(package.name), "muted", wrap=True, center=True))
            self.anchor_end()
            self.footer.addStretch(1)
            close = button("Close", variant="primary")
            close.setMinimumWidth(px(110))
            close.clicked.connect(self.close)
            close.setDefault(True)
            self.footer.addWidget(close)
            self.footer.addStretch(1)
            self.settle()

        # Actions --------------------------------------------------------------------------------------------------
        def run_steps(self, kind, finish, fail):
            """Run the steps one by one with the ring following them. Installing goes on after a problem (it is
            shown at the end); removing stops at the first one."""
            self.show_progress(kind)
            self.busy = True
            steps = list(enumerate(self.steps))
            total = float(len(steps)) or 1.0
            problems = []

            def next_step():
                if not steps:
                    self.ring.set_value(1.0)
                    self.step_label.setText("Done")
                    QtCore.QTimer.singleShot(450, lambda: (setattr(self, "busy", False), finish(problems)))
                    return
                index, (caption, function) = steps.pop(0)
                mark, text = self.step_rows[index]
                mark.setPixmap(icon_pixmap("dot", THEME["accent"] if kind == "install" else THEME["error"], px(14)))
                text.setObjectName("")
                text.setStyleSheet("color: {};".format(THEME["text"]))
                self.step_label.setText(caption)
                QtWidgets.QApplication.processEvents()
                try:
                    found = function() if self.real else []
                except Exception as error:  # noqa: BLE001
                    report(error)
                    self.busy = False
                    fail(error)
                    return
                if found and kind == "remove":
                    self.busy = False
                    fail(RuntimeError(" ".join(found)))
                    return
                problems.extend(found or [])
                mark.setPixmap(icon_pixmap("check", THEME["success"], px(14)))
                self.ring.set_value((index + 1) / total)
                QtCore.QTimer.singleShot(260, next_step)
            QtCore.QTimer.singleShot(200, next_step)

        def install(self):
            def finish(problems):
                self.did_install = True
                self.installed, self.installed_version = True, self.package.version
                self.show_done(problems, celebrate=True)

            def fail(error):
                self.show_main("Its install script stopped: {}. The MaxScript Listener shows the details."
                               .format(first_line(error)))
            self.run_steps("install", finish, fail)

        def uninstall(self, from_main):
            def finish(_problems):
                self.did_remove = True
                self.installed, self.installed_version = False, ""
                self.show_removed()

            def fail(error):
                self.show_uninstall(from_main, "{} Nothing more was removed.".format(first_line(error)))
            self.run_steps("remove", finish, fail)

        def open_customize(self):
            try:
                _rt().actionMan.executeAction(0, "59226")  # Customize > Customize User Interface
            except Exception as error:  # noqa: BLE001
                report(error)

        def run_now(self):
            package = self.package
            self.close()

            def run():
                if not self.real:
                    return
                try:
                    run_entry(package)
                except Exception as error:  # noqa: BLE001
                    report(error)
                    message = Message(max_window(), package.name, "{} could not start".format(package.name),
                                      first_line(error), kind="danger")
                    message.center_on(max_window())
                    run_modal(message)
            QtCore.QTimer.singleShot(0, run)

        def show_about(self):
            about = About(self)
            about.center_on(self)
            run_modal(about)

        def closeEvent(self, event):  # noqa: N802
            if self.busy:
                event.ignore()
                return
            if self.real and not self.did_install and not self.installed and not self.did_remove:
                remove_folder(self.package)  # Closed without installing: nothing of it stays behind
            _WINDOWS.pop(self.package.guid, None)
            Window.closeEvent(self, event)

    return Window, Message, Installer


_WINDOWS = sys.__dict__.setdefault("_maxpkg_installer_windows", {})  # One window per package, kept alive here


def first_line(error):
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


def report(error):
    print("-- MaxPkg installer: {}".format(error))
    traceback.print_exc()


def interactive(package, mode, real):
    _load_qt()
    anchor = max_window()
    measure_scale(anchor)
    _window, Message, Installer = build_classes()
    old = _WINDOWS.pop(package.guid, None)
    if old is not None:
        try:
            old.close()
        except Exception:  # noqa: BLE001
            pass
    kind, text = package.compatibility(max_year())
    if kind == "block":
        page = package.homepage if re.match(r"^https?://", package.homepage or "", re.I) else ""
        buttons = ((("Package page", lambda: open_url(page)),) if page else ()) + (("Close", None),)
        message = Message(anchor, "Cannot install " + package.name,
                          "Needs 3ds Max {} or newer".format(package.min_max), text + " Nothing was installed.",
                          buttons=buttons)
        message.center_on(anchor)
        run_modal(message)
        installed, _version = installed_state(package)
        if real and not installed:
            remove_folder(package)
        return
    window = Installer(package, mode, real, anchor)
    _WINDOWS[package.guid] = window
    window.measure()
    window.center_on(anchor)
    window.show()
    window.raise_()
    window.activateWindow()


def main(hook_file, request):
    folder = os.path.dirname(os.path.abspath(hook_file))
    package = Package(folder)
    mode = "uninstall" if request == "uninstall" else "install"
    real = is_installed_folder(package)
    if real and global_value("MaxPkg") is not None:  # MaxPkg Manager installs and removes; no window
        if mode == "install":
            manager_install(package)
        else:
            manager_uninstall(package)
        return
    if not package.valid:  # This file outside a package: a preview with sample data
        package = sample_package(folder)
    interactive(package, mode, real)  # Outside $temp\<GUID> (real False): a preview that changes nothing


def sample_package(folder):
    """What the preview shows when this file is run outside a package (in a project or in the packager)."""
    package = Package.__new__(Package)
    package.folder = folder
    package.manifest = ""
    package.guid = "00000000-0000-0000-0000-000000000000"
    package.name, package.button, package.version = "Pivot To Bottom", "Pivot To Bottom", "1.2.0"
    # Every field a package can fill, so the preview shows the installer at its fullest
    package.description = ("Puts the pivot of the selected objects at the bottom centre of their bounding box, "
                           "keeps groups and instances as they are, and works in one undo step.")
    package.developer, package.license = "Demo Studio", "Shareware"
    package.license_url = "https://maxpkg.dev/license"
    package.homepage, package.documentation = "https://maxpkg.dev", "https://maxpkg.dev/docs"
    package.purchase, package.purchase_label = "https://maxpkg.dev/buy", "Buy"
    package.entry, package.icon, package.create_button = "", "", True
    package.min_max, package.max_max = 2022, 2027
    package.custom_install = package.custom_uninstall = ""
    package.macros = [{"file": "", "button": "Pivot To Centre", "macro": "PivotToCentre", "quad": True},
                      {"file": "", "button": "Pivot To Top", "macro": "PivotToTop", "quad": False}]
    package.changelog = [("Added", "The package's own installer window, in the look of MaxPkg tools."),
                         ("Added", "A check of the 3ds Max version before anything is installed."),
                         ("Improved", "Install shows each step as it runs, with a ring for the progress."),
                         ("Improved", "Reinstall and Update say which version is installed now."),
                         ("Fixed", "Closing the window before Install leaves no button behind."),
                         ("Changed", "Uninstall lists what it removes and asks first."),
                         ("Removed", "The old installer page drawn in a web browser.")]
    return package


if HOOK_REQUEST is not None and __name__ == "__maxpkg_hook__":  # noqa: F821 (given by the MaxScript part)
    main(HOOK_FILE, HOOK_REQUEST)  # noqa: F821
#@end-maxpkg-python
*/
