"""Tests of MaxPkgPackerApi without 3ds Max and without a window (the files on disk are edited directly)."""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "maxpkg-src", "python"))

from maxpkgpackager import api  # noqa: E402

ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64"/></svg>'


def call(method, *args, **kwargs):
    return json.loads(getattr(api, method)(*args, **kwargs))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="maxpkg-api-")
        self.addCleanup(shutil.rmtree, self.root, True)
        for name, text in (("main.ms", "-- main"), ("tools\\helper.ms", "-- helper"), ("logo.svg", ICON)):
            path = os.path.join(self.root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as handle:
                handle.write(text)
        api._state.update(root=None, project=None, log=[])
        self.assertTrue(call("openProject", self.root)["ok"])

    def test_envelope_and_discovery(self):
        ping = call("ping")
        self.assertTrue(ping["ok"])
        self.assertEqual(ping["operation"], "api.ping")
        self.assertEqual(ping["data"]["projectRoot"], self.root)
        schema = call("getSchema")["data"]
        self.assertEqual(schema["indexBase"], 1)
        self.assertIn("build", schema["methods"])
        self.assertIn("Commercial", schema["options"]["license"]["values"])

    def test_full_workflow_builds_a_package(self):
        response = call("setOptions", [("packageName", "My Tool"), ("buttonName", "My Tool"),
                                       ("description", "Does things."), ("developerName", "Studio"),
                                       ("license", "Free"), ("releaseChannel", "beta"), ("version", "1.2.0"),
                                       ("svgIconFile", os.path.join(self.root, "logo.svg"))])
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["data"]["options"]["releaseChannel"], "beta")  # Applied after the version
        self.assertTrue(call("generateGuid")["ok"])
        self.assertEqual(call("generateGuid")["errors"][0]["code"], "GUID_EXISTS")
        self.assertTrue(call("addFile", os.path.join(self.root, "main.ms"))["ok"])
        self.assertTrue(call("addFolder", os.path.join(self.root, "tools"))["ok"])
        self.assertTrue(call("setEntry", "main.ms", False)["ok"])
        self.assertTrue(call("addChangelog", "added", "First version")["ok"])
        self.assertTrue(call("addExtraMacro", "tools\\helper.ms", "Open Helper")["ok"])
        validation = call("validate")
        self.assertTrue(validation["ok"], validation)
        result = call("build")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["data"]["exists"])
        self.assertTrue(os.path.isfile(result["data"]["outputFile"]))
        self.assertIn("main.ms", result["data"]["files"])
        for name in ("_install.ms", "_uninstall.ms"):  # In every package, with nothing to add or download
            self.assertIn(name, result["data"]["files"])
        self.assertEqual(sorted(os.listdir(self.root)), ["logo.svg", "main.ms", "max-package", "tools"])
        state = call("getState")["data"]
        self.assertEqual(state["options"]["version"], "1.2.0")
        self.assertEqual(len(state["files"]), 2)

    def test_errors_are_reported_not_raised(self):
        self.assertEqual(call("setOption", "license", "Paid")["errors"][0]["code"], "INVALID_VALUE")
        self.assertEqual(call("setOption", "nonsense", 1)["errors"][0]["code"], "UNKNOWN_OPTION")
        self.assertEqual(call("removeChangelog", 3)["errors"][0]["code"], "INVALID_INDEX")
        self.assertEqual(call("addFile", "C:\\nowhere\\x.ms")["errors"][0]["code"], "FILE_NOT_FOUND")
        rejected = call("setOptions", {"packageName": "Good Name", "license": "Paid"})
        self.assertFalse(rejected["ok"])
        self.assertEqual(call("getOption", "packageName")["data"]["value"], "")  # Nothing of the batch applied
        invalid = call("validate")
        self.assertFalse(invalid["ok"])
        self.assertTrue(any(error["field"] == "License" for error in invalid["errors"]))

    def test_file_in_use_needs_force(self):
        call("addFile", os.path.join(self.root, "main.ms"))
        call("setEntry", "main.ms")
        self.assertEqual(call("removeFile", "main.ms")["errors"][0]["code"], "FILE_IN_USE")
        self.assertTrue(call("removeFile", 1, True)["ok"])
        self.assertEqual(call("listFiles")["data"]["files"], [])

    def test_install_and_uninstall_windows_are_always_there(self):
        state = call("getState")["data"]
        self.assertEqual(state["standardHooks"], {"_install.ms": True, "_uninstall.ms": True})
        added = call("addStandardHook", "_install.ms")  # Kept for older automation
        self.assertTrue(added["ok"], added)
        self.assertEqual(added["data"]["standardHooks"], {"_install.ms": True, "_uninstall.ms": True})
        self.assertEqual(call("addStandardHook", "other.ms")["errors"][0]["code"], "INVALID_VALUE")
        self.assertEqual(call("getSchema")["data"]["apiVersion"], "2.1.0")

    def test_changes_are_saved_at_once(self):
        call("setOption", "packageName", "Saved Tool")
        api._state.update(project=None)  # Forget the in-memory project: the files must hold the value
        self.assertEqual(call("getOption", "packageName")["data"]["value"], "Saved Tool")


if __name__ == "__main__":
    unittest.main()
