"""Standalone tests of the pure core (no Qt, no 3ds Max). Run with Max's own Python:

    "C:\\Program Files\\Autodesk\\3ds Max 2027\\Python\\python.exe" -I -m unittest discover -s tests -p "test_*.py"
"""

import json
import datetime
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "maxpkg-src", "python"))

from maxpkgpackager import __version__ as VERSION  # noqa: E402
from maxpkgpackager.core import build, project as project_module, store, updater, validate  # noqa: E402
from maxpkgpackager.core.inifile import IniFile  # noqa: E402

ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64"/></svg>'


def manifest_of(archive):
    return json.loads(archive.read("manifest.json").decode("utf-8"))


def fake_compile(path):
    target = os.path.splitext(path)[0] + ".mse"
    with open(target, "wb") as handle:
        handle.write(b"C\x03\x00\x00fake")
    return True


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="maxpkg-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "lib"))
        os.makedirs(os.path.join(self.root, "max-package"))
        for name, text in (("main.ms", "messageBox \"hi\""), ("lib\\util.ms", "-- util"),
                           ("max-package\\_install.ms", "-- hook")):
            path = os.path.join(self.root, name)
            with open(path, "w") as handle:
                handle.write(text)
        with open(os.path.join(self.root, "max-package", "icon.svg"), "w") as handle:
            handle.write(ICON)
        proj = project_module.Project(self.root)
        proj.package_name, proj.button_name = "Test Tool", "Run Test Tool"
        proj.guid = project_module.new_guid()
        proj.description, proj.developer, proj.license = "Line one\nLine two", "Dev", "Free"
        proj.svg_icon = os.path.join(self.root, "max-package", "icon.svg")
        self.assertTrue(proj.add_file(os.path.join(self.root, "main.ms")))
        self.assertTrue(proj.add_file(os.path.join(self.root, "lib", "util.ms")))
        proj.entry = "main.ms"
        proj.compile_entry = True  # These tests build with the entry compiled (as a new project does)
        proj.release().changelog.append(("Added", "First"))
        self.project = proj


class CoreTests(Fixture):
    def test_validation_passes_and_fails(self):
        self.assertEqual([i for i in validate.validate(self.project) if i.level == "ERROR"], [])
        self.project.license = ""
        self.project.release().changelog[:] = []
        fields = [i.field for i in validate.validate(self.project) if i.level == "ERROR"]
        self.assertIn("License", fields)
        self.assertIn("Changelog", fields)
        self.project.description = "1\n2\n3\n4"
        self.assertIn("Description", [i.field for i in validate.validate(self.project)])

    def test_excluded_files_not_added(self):
        os.makedirs(os.path.join(self.root, "max-package"), exist_ok=True)
        for name in ("a.bak", "b.mzp", "mzp.run", "maxpkg-packager.ms", "max-package\\project.ini",
                     "max-package\\icon.svg"):
            path = os.path.join(self.root, name)
            open(path, "w").close()
            self.assertFalse(self.project.add_file(path), name)

    def test_build_path_remap_and_conflicts(self):
        self.project.rules.append(("lib", ""))
        self.assertEqual(self.project.build_path("lib\\util.ms"), "util.ms")
        shutil.copy(os.path.join(self.root, "main.ms"), os.path.join(self.root, "util.ms"))
        self.project.add_file(os.path.join(self.root, "util.ms"))
        self.assertTrue(any("would both be packaged" in i.message for i in validate.validate(self.project)))

    def test_store_round_trip_and_old_format(self):
        self.project.macros.append(project_module.MacroItem("lib\\util.ms", "Open Util", True, True))
        self.project.rules.append(("lib", "x"))
        store.save(self.project)
        with open(store.settings_path(self.root), "rb") as handle:
            raw = handle.read()
        self.assertEqual(raw[:2], b"\xff\xfe")  # UTF-16 like 3ds Max writes it
        loaded = store.load(self.root)
        self.assertEqual(loaded.description, "Line one\nLine two")
        self.assertEqual(loaded.entry, "main.ms")
        self.assertEqual([(m.file, m.button, m.compile, m.quad) for m in loaded.macros],
                         [("lib\\util.ms", "Open Util", True, True)])
        self.assertEqual(loaded.rules, [("lib", "x")])
        self.assertEqual(loaded.release().changelog, [("Added", "First")])

    def test_build_archive(self):
        self.project.macros.append(project_module.MacroItem("lib\\util.ms", "Open Util", True, True))
        result = build.build(self.project, "MaxPkg Packager", "9.9.9", compile_script=fake_compile)
        self.assertTrue(result.ok, result.messages)
        self.assertTrue(os.path.basename(result.output_file).startswith("test-tool@1.0.0@"))
        with zipfile.ZipFile(result.output_file) as archive:
            names = archive.namelist()
            for expected in ("manifest.ini", "manifest.json", "mzp.run", "mzp.run.ms", "maxpkg-quad.ms", "main.mse",
                             "lib/util.mse", "_install.ms", "_uninstall.ms", "icons/icon.svg",
                             "maxpkg-changelog.ini"):
                self.assertIn(expected, names)
            for name in project_module.HOOK_FILES:  # The packager's own, whatever the project folder holds
                with open(os.path.join(os.path.dirname(HERE), name), "rb") as handle:
                    self.assertEqual(archive.read(name), handle.read(), name)
            self.assertEqual((manifest_of(archive)["installScript"], manifest_of(archive)["uninstallScript"]),
                             ("_install.ms", "_uninstall.ms"))
            self.assertNotIn("main.ms", names)
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["entry"], "main.mse")
            self.assertEqual(manifest["packagerVersion"], "9.9.9")
            self.assertEqual(manifest["extraMacros"][0]["file"], "lib\\util.mse")
            ini = archive.read("manifest.ini").decode("utf-8")
            self.assertIn("description=Line one\\nLine two", ini)
            self.assertIn("\r\n", ini)
            self.assertEqual(archive.read("mzp.run").decode(), 'name "Test Tool"\r\nextract to "$temp\\%s"\r\n'
                             'drop "mzp.run.ms"\r\nrun "mzp.run.ms"\r\n' % self.project.guid)

    def test_failed_build_keeps_previous_output(self):
        first = build.build(self.project, compile_script=fake_compile)
        self.assertTrue(first.ok)
        with open(first.output_file, "rb") as handle:
            before = handle.read()
        second = build.build(self.project, compile_script=lambda path: False)
        self.assertFalse(second.ok)
        with open(first.output_file, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_stable_guid_matches_maxscript_algorithm(self):
        self.assertEqual(project_module.stable_guid("abc"), "98500190-d23c-b04f-d696-3f7d28e17f72")  # MD5 900150983cd24fb0d6963f7d28e17f72 as a .NET Guid


class ParityWithOldPackager(unittest.TestCase):
    """A project packaged by the MaxScript packager 1.1.1 (tests/fixtures/legacy-1.1.1, GUID anonymised): the new
    packager reads its files and writes the same manifest."""

    def test_manifest_matches_old_archive(self):
        fixture = os.path.join(HERE, "fixtures", "legacy-1.1.1")
        work = tempfile.mkdtemp(prefix="maxpkg-parity-")
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("maxpkg-packager.ini", "maxpkg-changelog.ini", "test.ms", "_install.ms", "_uninstall.ms"):
            shutil.copy(os.path.join(fixture, name), work)
        proj = store.load(work)  # Migrates the 1.x layout into max-package
        self.assertEqual(sorted(os.listdir(work)), ["max-package", "test.ms"])
        proj.version = "1.0.2"
        proj.license, proj.purchase_label = "Trial", "Get license"  # As recorded in the old archive
        with open(os.path.join(fixture, "expected-manifest.ini"), encoding="utf-8") as handle:
            old_ini = handle.read().replace("\r\n", "\n")
        with open(os.path.join(fixture, "expected-mzp.run.ms"), encoding="utf-8") as handle:
            old_run = handle.read().replace("\r\n", "\n")
        new_ini = build.manifest_ini(proj, "MaxPkg Packager", "1.1.1").replace("\r\n", "\n")
        skip = ("max3dsMax", "min3dsMax")  # The new rule: 3ds Max 2022 is the lowest supported version
        self.assertIn("min3dsMax=2022", new_ini)
        self.assertEqual([l for l in new_ini.split("\n") if not l.startswith(skip)],
                         [l for l in old_ini.split("\n") if not l.startswith(skip)])
        # Built by packager 1.1.1, before Quad Menu support: only the shared start of the installer must match.
        self.assertEqual(old_run.split("\n")[:170], build._template("mzp.run.ms").split("\n")[:170])


class SvgCheckTests(unittest.TestCase):
    def check(self, content):
        folder = tempfile.mkdtemp(prefix="maxpkg-svg-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "icon.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        from maxpkgpackager.core import svgcheck
        return svgcheck.inspect(path)

    def test_clean_square_icon(self):
        report = self.check('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient '
                            'id="g"/></defs><rect width="64" height="64" fill="url(#g)"/></svg>')
        self.assertTrue(report.ok)
        self.assertEqual(report.warnings, [])
        self.assertEqual((report.width, report.height), (64, 64))

    def test_unsafe_icons_are_refused(self):
        for body in ('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                     '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"/>',
                     '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
                     '<image xlink:href="http://example.com/a.png"/></svg>',
                     '<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>',
                     '<svg xmlns="http://www.w3.org/2000/svg"><rect></svg>',
                     '<html><body/></html>'):
            self.assertFalse(self.check(body).ok, body)

    def test_warnings_for_shape_and_editor_data(self):
        wide = self.check('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 32"/>')
        self.assertTrue(wide.ok)
        self.assertTrue(any("not square" in message for message in wide.warnings))
        inkscape = self.check('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/'
                              'namespaces/inkscape" viewBox="0 0 64 64"><!-- x --><metadata/></svg>')
        self.assertTrue(inkscape.ok)
        self.assertTrue(inkscape.needs_cleanup)
        self.assertIn("Inkscape data", inkscape.extras)


class UrlTests(unittest.TestCase):
    def test_links(self):
        problem = project_module.url_problem
        for good in ("", "https://3dground.net", "http://maxpkg.dev/dashboard?x=1", "https://sub.domain.co.uk/a#b"):
            self.assertIsNone(problem(good), good)
        for bad in ("dsfsdfsdfds", "https://dsfsdf", "ftp://example.com", "https://exa mple.com", "javascript:x()",
                    "https://", "www"):
            self.assertIsNotNone(problem(bad), bad)
        self.assertEqual(project_module.complete_url("3dground.net/tools"), "https://3dground.net/tools")
        self.assertEqual(project_module.complete_url("dsfsdfsdfds"), "dsfsdfsdfds")

    def test_invalid_link_is_a_validation_error(self):
        proj = project_module.Project(tempfile.gettempdir())
        proj.homepage = "dsfsdfsdfds"
        messages = [(i.field, i.message) for i in validate.validate(proj)]
        self.assertIn(("Homepage URL", "Homepage URL: enter a correct web address, like https://example.com, "
                                       "or clear the field"), messages)


class DailyLogTests(unittest.TestCase):
    def setUp(self):
        from maxpkgpackager import logs
        self.logs = logs
        self.folder = tempfile.mkdtemp(prefix="maxpkg-logs-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def write_day(self, date, text):
        path = self.logs.day_path(self.folder, date)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)
        return path

    def test_records_go_to_the_file_of_the_day(self):
        handler = self.logs.attach(self.folder)
        self.addCleanup(self.logs.detach, handler)
        self.logs.get("test").info("hello")
        with open(self.logs.log_path(self.folder), encoding="utf-8") as stream:
            self.assertIn("INFO    maxpkgpackager.test: hello", stream.read())
        self.assertEqual([day.date for day in self.logs.log_days(self.folder)], [datetime.date.today()])

    def test_days_newest_first_with_labels(self):
        today = datetime.date(2026, 10, 30)
        for days_back in (5, 0, 1):
            self.write_day(today - datetime.timedelta(days=days_back), "x\n")
        dates = [day.date for day in self.logs.log_days(self.folder)]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(self.logs.day_label(today, today), "Today")
        self.assertEqual(self.logs.day_label(today - datetime.timedelta(days=1), today), "Yesterday")
        self.assertEqual(self.logs.day_label(datetime.date(2026, 10, 29), today), "Yesterday")
        self.assertEqual(self.logs.day_label(datetime.date(2026, 10, 25), today), "Sun 25 Oct 2026")

    def test_old_days_are_pruned(self):
        old = self.write_day(datetime.date.today() - datetime.timedelta(days=self.logs.KEEP_DAYS + 1), "old\n")
        recent = self.write_day(datetime.date.today() - datetime.timedelta(days=2), "recent\n")
        self.logs.prune(self.folder)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(recent))

    def test_clear_logs_deletes_every_day_and_logging_goes_on(self):
        handler = self.logs.attach(self.folder)
        self.addCleanup(self.logs.detach, handler)
        self.logs.get("test").info("before clearing")
        self.write_day(datetime.date.today() - datetime.timedelta(days=3), "older day\n")
        legacy = os.path.join(self.logs.logs_folder(self.folder), "maxpkgpackager.log.1")
        with open(legacy, "w") as stream:
            stream.write("2.0 log\n")
        removed, kept, freed = self.logs.clear_logs(self.folder, handler)
        self.assertEqual((removed, kept), (3, 0))
        self.assertGreater(freed, 0)
        self.assertEqual(self.logs.log_days(self.folder), [])
        self.logs.get("test").info("after clearing")
        with open(self.logs.log_path(self.folder), encoding="utf-8") as stream:
            text = stream.read()
        self.assertNotIn("before clearing", text)
        self.assertIn("after clearing", text)

    def test_big_day_is_read_from_its_end(self):
        path = self.write_day(datetime.date.today(), "".join("line {}\n".format(i) for i in range(1000)))
        text = self.logs.read_text(path, limit=100)
        self.assertTrue(text.endswith("line 999\n"))
        self.assertTrue(text.startswith("line "))  # The cut first line is dropped

    def test_summary(self):
        records = [{"level": "INFO"}, {"level": "WARNING"}, {"level": "ERROR"}, {"level": "ERROR"}]
        self.assertEqual(self.logs.summary_text(records), "4 records · 1 warning · 2 errors")
        self.assertEqual(self.logs.summary_text(records[:1]), "1 record")


class ChangelogLineTests(unittest.TestCase):
    def test_prefixes_and_words(self):
        parse = project_module.parse_changelog_line
        self.assertEqual(parse("+ New button"), ("Added", "New button"))
        self.assertEqual(parse("- Crash on start"), ("Fixed", "Crash on start"))
        self.assertEqual(parse("* Faster build"), ("Changed", "Faster build"))
        self.assertEqual(parse("** Smoother UI"), ("Improved", "Smoother UI"))
        self.assertEqual(parse("fixed: wrong path"), ("Fixed", "wrong path"))
        self.assertEqual(parse("Plain text", "Removed"), ("Removed", "Plain text"))
        self.assertEqual(parse("  spaced  ", "Nonsense"), ("Added", "spaced"))

    def test_min_max_is_2022_or_newer(self):
        self.assertEqual(project_module.clamp_min_max("2012"), "2022")
        self.assertEqual(project_module.clamp_min_max("abc"), "2022")
        self.assertEqual(project_module.clamp_min_max("2024"), "2024")
        self.assertEqual(project_module.max_years()[0], "2022")


class SetupTests(unittest.TestCase):
    """The installer (.mzp) puts the launcher into a project: what is there decides what it says and does."""

    def setUp(self):
        from maxpkgpackager.core import setup
        self.setup = setup
        self.root = tempfile.mkdtemp(prefix="maxpkg-setup-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.project = os.path.join(self.root, "My Tool")
        os.makedirs(self.project)
        self.source = os.path.join(self.root, "maxpkg-packager.ms")
        with open(self.source, "wb") as handle:
            handle.write("/*\r\n[INFO]\r\nNAME=MaxPkg Packager\r\nVERSION={}\r\n*/\r\n".format(VERSION).encode("ascii"))

    def test_new_project_gets_only_the_launcher(self):
        self.assertEqual(self.setup.describe(self.project), "new")
        target = self.setup.install_launcher(self.source, self.project)
        self.assertEqual(os.listdir(self.project), ["maxpkg-packager.ms"])
        self.assertEqual(self.setup.launcher_version(target), VERSION)
        self.assertEqual(self.setup.describe(self.project), "same")

    def test_version_1_is_recognised_and_replaced(self):
        old = os.path.join(self.project, "maxpkg-packager.ms")
        with open(old, "wb") as handle:  # 1.x is UTF-16 with a BOM
            handle.write("/*\r\n[INFO]\r\nNAME=MaxPkg Packer\r\nVERSION=1.2.1\r\n*/\r\n".encode("utf-16"))
        self.assertEqual(self.setup.launcher_version(old), "1.2.1")
        self.assertEqual(self.setup.describe(self.project), "old")
        self.setup.install_launcher(self.source, self.project)
        self.assertEqual(self.setup.launcher_version(old), VERSION)
        self.assertEqual(os.listdir(self.project), ["maxpkg-packager.ms"])  # No backup left next to it

    def test_folder_problems(self):
        self.assertTrue(self.setup.folder_problem(""))
        self.assertTrue(self.setup.folder_problem(os.path.join(self.root, "missing")))
        self.assertTrue(self.setup.folder_problem(os.path.splitdrive(self.root)[0] + os.sep))
        self.assertEqual(self.setup.folder_problem(self.project), "")
        with self.assertRaises(ValueError):
            self.setup.install_launcher(self.source, os.path.join(self.root, "missing"))

    def test_project_settings_are_never_touched(self):
        """Installing over a project that is already set up replaces only the launcher."""
        settings = os.path.join(self.project, "max-package")
        os.makedirs(os.path.join(settings, "dist"))
        files = {"project.ini": "[settings]\npackageName=My Tool\n", "changelog.ini": "[1.0.0]\nAdded=First\n",
                 "icon.svg": ICON, "_install.ms": "-- hook", ".gitignore": "dist/\n",
                 os.path.join("dist", "my-tool@1.0.0.mzp"): "built"}
        for name, text in files.items():
            with open(os.path.join(settings, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        with open(os.path.join(self.project, "main.ms"), "w") as handle:
            handle.write("-- the user's script")
        before = {}
        for current, _folders, names in os.walk(self.project):
            for name in names:
                path = os.path.join(current, name)
                with open(path, "rb") as handle:
                    before[path] = (handle.read(), os.path.getmtime(path))
        self.assertTrue(self.setup.has_settings(self.project))
        for _attempt in range(2):  # A second install (the same version again) changes nothing either
            self.setup.install_launcher(self.source, self.project)
        for path, (content, modified) in before.items():
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), content, path)
            self.assertEqual(os.path.getmtime(path), modified, path)
        self.assertEqual(sorted(os.listdir(self.project)), ["main.ms", "max-package", "maxpkg-packager.ms"])


class MigrationTests(unittest.TestCase):
    def test_legacy_files_move_into_max_package(self):
        root = tempfile.mkdtemp(prefix="maxpkg-mig-")
        self.addCleanup(shutil.rmtree, root, True)
        for name, text in (("_install.ms", "-- hook"), ("maxpkg-icon.svg", ICON), ("keep.ms", "-- mine"),
                           ("maxpkg-changelog.ini", "[1.0.0]\nAdded=First release\n")):
            with open(os.path.join(root, name), "w") as handle:
                handle.write(text)
        ini = IniFile()
        ini.set("settings", "packageName", "Old Tool")
        ini.set("settings", "svgIcon", os.path.join(root, "maxpkg-icon.svg"))
        ini.write(os.path.join(root, "maxpkg-packager.ini"))
        proj = store.load(root)
        self.assertEqual(proj.package_name, "Old Tool")
        self.assertEqual(sorted(os.listdir(root)), ["keep.ms", "max-package"])
        self.assertEqual(sorted(os.listdir(os.path.join(root, "max-package"))),
                         ["_install.ms", "_uninstall.ms", "changelog.ini", "icon.svg", "project.ini"])
        self.assertEqual(proj.svg_icon, os.path.join(root, "max-package", "icon.svg"))
        self.assertTrue(proj.hook_path("_install.ms"))
        store.save(proj)
        self.assertEqual(store.migrate_legacy(root), [])  # A second open changes nothing
        self.assertTrue(os.path.isfile(os.path.join(root, "max-package", ".gitignore")))

    def test_old_default_output_folder_moves_into_max_package(self):
        root = tempfile.mkdtemp(prefix="maxpkg-dist-")
        self.addCleanup(shutil.rmtree, root, True)
        ini = IniFile()
        ini.set("settings", "packageName", "Old Tool")
        ini.set("settings", "outputFolder", os.path.join(root, "dist"))
        ini.write(os.path.join(root, "maxpkg-packager.ini"))
        proj = store.load(root)
        self.assertEqual(os.path.normcase(proj.output_folder),
                         os.path.normcase(os.path.join(root, "max-package", "dist")))
        custom = os.path.join(root, "max-package", "builds")
        proj.output_folder = custom
        store.save(proj)
        self.assertEqual(os.path.normcase(store.load(root).output_folder), os.path.normcase(custom))

    def test_compile_entry_is_on_for_a_new_project_and_kept_for_others(self):
        root = tempfile.mkdtemp(prefix="maxpkg-compile-")
        self.addCleanup(shutil.rmtree, root, True)
        self.assertTrue(store.load(root).compile_entry)  # New: the entry .ms is packed as a .mse
        self.assertTrue(project_module.Project(root).compile_entry)
        ini = IniFile()
        ini.set("settings", "packageName", "Old Tool")
        ini.set("settings", "compileEntry", "false")  # A project whose author turned it off
        ini.write(os.path.join(root, "maxpkg-packager.ini"))
        project = store.load(root)
        self.assertFalse(project.compile_entry)
        store.save(project)
        self.assertFalse(store.load(root).compile_entry)  # Their choice stays

    def test_root_gets_only_the_max_package_folder(self):
        root = tempfile.mkdtemp(prefix="maxpkg-clean-")
        self.addCleanup(shutil.rmtree, root, True)
        store.save(store.load(root))
        self.assertEqual(os.listdir(root), ["max-package"])


class HookTests(unittest.TestCase):
    """_install.ms and _uninstall.ms ship with the packager: a project has them in max-package from its first open,
    always the packager's own, and every package is built with them."""

    def setUp(self):
        from maxpkgpackager.core import hooks
        self.hooks = hooks
        self.root = tempfile.mkdtemp(prefix="maxpkg-hooks-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def shipped(self, name):
        with open(os.path.join(os.path.dirname(HERE), name), "rb") as handle:
            return handle.read()

    def in_project(self, name):
        with open(os.path.join(self.root, "max-package", name), "rb") as handle:
            return handle.read()

    def test_a_project_has_them_from_its_first_open(self):
        project = store.load(self.root)
        self.assertEqual(sorted(os.listdir(self.root)), ["max-package"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "max-package"))), ["_install.ms", "_uninstall.ms"])
        for name in project_module.HOOK_FILES:
            self.assertTrue(project.hook_path(name))
            self.assertEqual(self.in_project(name), self.shipped(name), name)
        self.assertEqual(self.hooks.sync(self.root), [])  # Nothing to do the second time: no file is rewritten

    def test_a_changed_or_deleted_copy_is_put_back(self):
        store.load(self.root)
        with open(os.path.join(self.root, "max-package", "_install.ms"), "w") as handle:
            handle.write("-- someone's own installer")
        os.remove(os.path.join(self.root, "max-package", "_uninstall.ms"))
        store.save(store.load(self.root))
        for name in project_module.HOOK_FILES:
            self.assertEqual(self.in_project(name), self.shipped(name), name)

    def test_a_build_fails_without_them(self):
        fixture = Fixture("setUp")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = self.hooks.shipped
        self.hooks.shipped = lambda name: ""  # A broken installation: the packager has lost its own files
        self.addCleanup(setattr, self.hooks, "shipped", original)
        os.remove(os.path.join(fixture.root, "max-package", "_install.ms"))
        result = build.build(fixture.project, compile_script=fake_compile)
        self.assertFalse(result.ok)
        self.assertTrue(any("_install.ms is missing" in text for _level, text in result.messages), result.messages)
        self.assertTrue(any("_uninstall.ms is missing" in text for _level, text in result.messages), result.messages)

    def test_the_application_archive_carries_them(self):
        """What release.py packs: an installed copy reads them from assets/hooks, the repository from its root."""
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "maxpkg-src", "tools"))
        self.addCleanup(sys.path.pop, 0)
        import release
        original = release.RELEASE
        release.RELEASE = self.root
        self.addCleanup(setattr, release, "RELEASE", original)
        with zipfile.ZipFile(release.build_payload("0.0.0")) as archive:
            for name in project_module.HOOK_FILES:
                self.assertEqual(archive.read("assets/hooks/" + name), self.shipped(name), name)


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="maxpkg-upd-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def make_payload(self, version, broken=False):
        path = os.path.join(self.base, "payload-%s.zip" % version)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("python/bootstrap.py", "print('boot')\n")
            archive.writestr("python/maxpkgpackager/__init__.py",
                             "__version__ = %r\n" % version + ("def (:\n" if broken else ""))
            archive.writestr("assets/x.txt", "x")
        return path

    def info(self, version, path):
        return updater.UpdateInfo(version, "file:///" + path.replace("\\", "/"), updater.sha256_file(path), "", [])

    def test_install_switch_and_rollback(self):
        home = os.path.join(self.base, "app")
        first = self.make_payload("2.0.1")
        updater.install_payload(home, self.info("2.0.1", first), first)
        self.assertEqual(updater.read_current(home)["version"], "2.0.1")
        second = self.make_payload("2.0.2")
        updater.install_payload(home, self.info("2.0.2", second), second)
        state = updater.read_current(home)
        self.assertEqual((state["version"], state["previous"]), ("2.0.2", "2.0.1"))
        updater.rollback(home)
        self.assertEqual(updater.read_current(home)["version"], "2.0.1")

    def test_corrupt_payload_leaves_current_untouched(self):
        home = os.path.join(self.base, "app")
        good = self.make_payload("2.0.1")
        updater.install_payload(home, self.info("2.0.1", good), good)
        bad = self.make_payload("2.0.2", broken=True)
        with self.assertRaises(updater.UpdateError):
            updater.install_payload(home, self.info("2.0.2", bad), bad)
        wrong_hash = self.make_payload("2.0.3")
        info = self.info("2.0.3", wrong_hash)
        info.sha256 = "0" * 64
        with self.assertRaises(updater.UpdateError):
            updater.install_payload(home, info, wrong_hash)
        self.assertEqual(updater.read_current(home)["version"], "2.0.1")
        self.assertEqual(sorted(n for n in os.listdir(home) if n.startswith("v")), ["v2.0.1"])

    def test_install_keeps_user_settings_and_logs(self):
        """The packager's own settings and logs live next to the app folder: installing never touches them."""
        root = os.path.join(self.base, "MaxPkgPackager")
        home = os.path.join(root, "app")
        os.makedirs(os.path.join(root, "logs"))
        kept = {os.path.join(root, "settings.json"): '{"theme": "plum", "last_developer": "3DGROUND"}',
                os.path.join(root, "logs", "maxpkgpackager-2026-11-11.log"): "a record\n"}
        for path, text in kept.items():
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        for version in ("2.0.1", "2.0.1", "2.0.2"):  # The same version again, then a newer one
            payload = self.make_payload(version)
            updater.install_payload(home, self.info(version, payload), payload)
        for path, text in kept.items():
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text)
        self.assertEqual(sorted(os.listdir(root)), ["app", "logs", "settings.json"])

    def test_version_compare(self):
        self.assertTrue(updater.is_newer("2.0.10", "2.0.9"))
        self.assertFalse(updater.is_newer("2.0.0", "2.0.0"))
        self.assertFalse(updater.is_newer("1.9.9", "2.0.0"))


class ServedFilesTests(unittest.TestCase):
    """What installed copies download from main is checked against the SHA-256 in release/update.json. With
    core.autocrlf Git commits text files with LF, so the launcher and the hooks served from main would not match the
    CRLF files that were hashed: .gitattributes must keep them byte for byte."""

    def test_served_files_are_stored_byte_for_byte(self):
        with open(os.path.join(os.path.dirname(HERE), ".gitattributes"), encoding="utf-8") as handle:
            rules = {line.split()[0]: line.split()[1:] for line in handle
                     if line.strip() and not line.lstrip().startswith("#")}
        for path in ("/maxpkg-packager.ms", "/_install.ms", "/_uninstall.ms", "/release/**"):
            self.assertIn("-text", rules.get(path, []), path)


if __name__ == "__main__":
    unittest.main()
