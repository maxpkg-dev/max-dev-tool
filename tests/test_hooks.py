"""The two files every package carries: _install.ms (the whole installer: MaxScript + its Python part) and
_uninstall.ms (asks _install.ms to remove the package). Their Python part runs here against a stand-in for 3ds Max:
no Qt is started (the window itself is tested inside 3ds Max)."""

import configparser
import io
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INSTALL = os.path.join(ROOT, "_install.ms")
UNINSTALL = os.path.join(ROOT, "_uninstall.ms")
RUNNER = os.path.join(ROOT, "maxpkg-src", "python", "maxpkgpackager", "core", "templates", "mzp.run.ms")
GUID = "918e4a77-034c-4e5d-b0de-3f8bf3bd27fb"


def engine_source():
    with io.open(INSTALL, encoding="utf-8-sig") as handle:
        text = handle.read()
    return text.split("#@maxpkg" + "-python")[1].split("#@end" + "-maxpkg-python")[0]


class FakeMax(object):
    """What the installer asks of 3ds Max: INI reading, folders, the version, fileIn and execute."""

    def __init__(self, root, year=2022):
        self.dirs = {name: os.path.join(root, name) for name in ("temp", "userMacros", "userIcons", "userStartupScripts")}
        for folder in self.dirs.values():
            os.makedirs(folder)
        self.year = year
        self.loaded = []
        self.executed = []

    def Name(self, text):  # noqa: N802
        return text

    def getDir(self, name):  # noqa: N802
        return self.dirs[name]

    def maxVersion(self):  # noqa: N802
        return [(self.year - 2000 + 2) * 1000, 0, 0, 0, 0, 0, 0, self.year, ""]

    def getINISetting(self, path, section, key):  # noqa: N802
        if not os.path.isfile(path):
            return ""
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.read(path, encoding="utf-8")
        return parser.get(section, key, fallback="")

    def fileIn(self, path):  # noqa: N802
        self.loaded.append(path)

    def execute(self, text):
        self.executed.append(text)
        return True


MANIFEST = """[package]
packageGuid={guid}
name=Pivot To Bottom
buttonName=Pivot To Bottom
version=1.2.0
entry=pivot-to-bottom.mse
icon=icons/icon.svg
license=Free
developerName=Demo Studio
min3dsMax={min}
max3dsMax=2027
createMacroButton=true
customInstallScript={custom}
customUninstallScript=

[extraMacros]
count=1
1_file=tools/centre.mse
1_button=Pivot To Centre
1_macro=PivotToCentre
1_quad={quad}

[changelog]
count=2
1_type=Added
1_text=Pivot to the centre
2_type=Fixed
2_text=Groups keep their pivot
"""


class HookFileTests(unittest.TestCase):
    """Rules every installed copy and packager 1.x rely on: plain ASCII, CRLF, the same two names, no extra files."""

    def test_both_files_are_ascii_with_crlf(self):
        for path in (INSTALL, UNINSTALL):
            with open(path, "rb") as handle:
                data = handle.read()
            body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
            body.decode("ascii")
            self.assertNotIn(b"\n", body.replace(b"\r\n", b""), path)

    def test_python_part_compiles_and_never_ends_the_comment(self):
        source = engine_source()
        self.assertNotIn("*/", source)
        compile(source, INSTALL, "exec")

    def test_uninstaller_and_runner_hand_over_to_the_installer(self):
        with io.open(UNINSTALL, encoding="utf-8-sig") as handle:
            uninstall = handle.read()
        self.assertIn('"_install.ms"', uninstall)
        self.assertIn('global MaxPkgHookRequest = "uninstall"', uninstall)
        with io.open(RUNNER, encoding="utf-8") as handle:
            runner = handle.read()
        self.assertIn('global MaxPkgHookRequest = "install"', runner)

    def test_no_local_hides_a_global(self):
        """MaxScript names ignore case: a local spelled like a global (maxPkgHookRequest / MaxPkgHookRequest) hides
        it, and the request from _uninstall.ms was lost that way."""
        import re
        for path in (INSTALL, UNINSTALL, RUNNER):
            with io.open(path, encoding="utf-8-sig") as handle:
                text = handle.read().split("#@maxpkg" + "-python")[0]
            locals_ = {name.lower() for name in re.findall(r"\blocal\s+(\w+)", text)}
            globals_ = {name.lower() for name in re.findall(r"\bglobal\s+(\w+)", text)}
            globals_ |= {"maxpkg", "maxpkghookrequest", "maxpkghookarguments"}
            self.assertEqual(locals_ & globals_, set(), path)

    def test_older_max_gets_a_plain_message(self):
        with io.open(INSTALL, encoding="utf-8-sig") as handle:
            head = handle.read().split("#@maxpkg" + "-python")[0]
        self.assertIn("(maxVersion())[1] < 24000", head)  # 3ds Max older than 2022: no Python is run

    def test_start_leaves_no_names_behind(self):
        """python.Execute shares one namespace: a second run while a window is open (the package dragged in again)
        once deleted the first run's names, and its own `del` failed with a NameError."""
        import re
        with io.open(INSTALL, encoding="utf-8-sig") as handle:
            head = handle.read().split("#@maxpkg" + "-python")[0]
        start = re.search(r'python\.Execute "(.*)"', head).group(1)
        statements = start.split("\\n")
        self.assertEqual(statements[0], "import io, pymxs")
        self.assertEqual(len(statements), 2)
        self.assertNotRegex(statements[1], r"^\w+\s*=")  # One expression, nothing assigned
        self.assertNotIn("del ", start)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="maxpkg-hooks-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.max = FakeMax(self.root)
        self.engine = {"__name__": "test", "HOOK_FILE": INSTALL, "HOOK_REQUEST": None}
        exec(compile(engine_source(), INSTALL, "exec"), self.engine)
        self.engine["_rt"] = lambda: self.max

    def package(self, folder=None, minimum=2022, quad="false", custom=""):
        folder = folder or os.path.join(self.max.dirs["temp"], GUID)
        os.makedirs(os.path.join(folder, "icons"), exist_ok=True)
        with io.open(os.path.join(folder, "manifest.ini"), "w", encoding="utf-8") as handle:
            handle.write(MANIFEST.format(guid=GUID, min=minimum, quad=quad, custom=custom))
        with io.open(os.path.join(folder, "icons", "icon.svg"), "w", encoding="utf-8") as handle:
            handle.write("<svg/>")
        if quad == "true":
            with io.open(os.path.join(folder, "maxpkg-quad.ms"), "w", encoding="utf-8") as handle:
                handle.write("-- quad")
        return self.engine["Package"](folder)

    def test_manifest_is_read(self):
        package = self.package()
        self.assertTrue(package.valid)
        self.assertEqual((package.name, package.version, package.min_max, package.max_max), ("Pivot To Bottom", "1.2.0", 2022, 2027))
        self.assertEqual(package.changelog, [("Added", "Pivot to the centre"), ("Fixed", "Groups keep their pivot")])
        self.assertEqual([macro["button"] for macro in package.macros], ["Pivot To Centre"])

    def test_this_max_must_be_new_enough(self):
        package = self.package(minimum=2025)
        kind, text = package.compatibility(2022)
        self.assertEqual(kind, "block")
        self.assertIn("needs 3ds Max 2025", text)
        self.assertEqual(package.compatibility(2025), ("", ""))
        self.assertEqual(package.compatibility(2028)[0], "note")  # Newer than the package knows: a note, no block

    def test_only_the_extracted_folder_is_changed(self):
        self.assertTrue(self.engine["is_installed_folder"](self.package()))
        other = self.package(folder=os.path.join(self.root, "project", "dist"))
        self.assertFalse(self.engine["is_installed_folder"](other))  # A preview: files are never touched

    def test_install_writes_buttons_with_guid_and_version(self):
        package = self.package()
        problems = []
        for _caption, step in self.engine["install_steps"](package):
            problems += step()
        self.assertEqual(problems, [])
        macros = sorted(os.listdir(self.max.dirs["userMacros"]))
        self.assertEqual(macros, ["maxpkg-" + GUID + "-PivotToCentre.mcr", "maxpkg-" + GUID + ".mcr"])
        with io.open(os.path.join(self.max.dirs["userMacros"], "maxpkg-" + GUID + ".mcr"), encoding="utf-8-sig") as handle:
            text = handle.read()
        for line in ("macroScript MaxPkg_" + GUID.replace("-", ""), 'category: "MaxPkg"', "-- Package GUID: " + GUID,
                     "-- Package version: 1.2.0"):
            self.assertIn(line, text)
        self.assertTrue(os.path.isfile(os.path.join(self.max.dirs["userIcons"], GUID + ".svg")))
        self.assertEqual(self.engine["installed_state"](package), (True, "1.2.0"))

    def test_quad_items_get_their_startup_script(self):
        package = self.package(quad="true")
        captions = [caption for caption, _step in self.engine["install_steps"](package)]
        self.assertIn("Adding its quad menu items", captions)
        for _caption, step in self.engine["install_steps"](package):
            step()
        startup = os.path.join(self.max.dirs["userStartupScripts"], "maxpkg-" + GUID + "-quad-startup.ms")
        self.assertTrue(os.path.isfile(startup))
        self.assertTrue(any(".install()" in command for command in self.max.executed))

    def test_custom_script_must_stay_inside_the_package(self):
        package = self.package(custom="..\\outside.ms")
        with self.assertRaises(RuntimeError):
            self.engine["run_custom"](package, "install")

    def test_uninstall_removes_what_install_made(self):
        package = self.package(quad="true")
        for _caption, step in self.engine["install_steps"](package):
            step()
        problems = []
        for _caption, step in self.engine["remove_steps"](package):
            problems += step()
            if problems:
                break
        self.assertEqual(problems, [])
        self.assertEqual(os.listdir(self.max.dirs["userMacros"]), [])
        self.assertEqual(os.listdir(self.max.dirs["userIcons"]), [])
        self.assertEqual(os.listdir(self.max.dirs["userStartupScripts"]), [])
        self.assertFalse(os.path.isdir(package.folder))
        self.assertEqual(self.engine["installed_state"](package), (False, ""))

    def test_buttons_of_an_older_installer_are_found(self):
        package = self.package()
        older = os.path.join(self.max.dirs["userMacros"], "MaxPkg-MaxPkg_" + GUID.replace("-", "") + ".mcr")
        with io.open(older, "w", encoding="utf-8") as handle:
            handle.write("-- Package GUID: " + GUID + "\n")  # Made before the version line existed
        self.assertEqual(self.engine["installed_state"](package), (True, ""))
        self.engine["remove_buttons"](package)
        self.assertFalse(os.path.isfile(older))


if __name__ == "__main__":
    unittest.main()
