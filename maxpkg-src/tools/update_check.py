"""Rehearse a real user's update before publishing (any Python 3.7+):

    python maxpkg-src/tools/update_check.py [--work FOLDER] [--port 8765]

Run release.py (or release.bat) first. This prepares, in --work (default: %TEMP%\\maxpkg-update-check):
    server\\      what main serves after the push (launcher, hooks, release/), every GitHub address replaced by
                  http://127.0.0.1:<port>/ - and serves it until Ctrl+C, printing every request
    project-1x\\  a project of MaxPkg Packager 1.2.1 (the last 1.x, from git history), its settings in the root as 1.x
                  keeps them, its self-update pointing at the server
    profile\\     an empty user profile for the packager (the LOCALAPPDATA of the rehearsal)
    scratch\\     an empty folder for the installer test

Then follow ".codex/how-to-release.md", section "Update rehearsal", in 3ds Max 2022 and 2027. Only addresses differ
from the real files, so what works here works for users once main is pushed.
"""

import argparse
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GITHUB = "https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/"
LEGACY_COMMIT = "3727cfd"  # "Bump packager version to 1.2.1": the last MaxScript packager
LEGACY_PROJECT = os.path.join(ROOT, "tests", "fixtures", "legacy-1.1.1")


def prepare(work, base):
    folders = {name: os.path.join(work, name) for name in ("server", "project-1x", "profile", "scratch")}
    for folder in folders.values():
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder)
    server = folders["server"]
    with open(os.path.join(ROOT, "maxpkg-packager.ms"), "rb") as handle:
        launcher = handle.read().decode("ascii").replace(GITHUB, base)
    with open(os.path.join(server, "maxpkg-packager.ms"), "wb") as handle:
        handle.write(launcher.encode("ascii"))
    for name in ("_install.ms", "_uninstall.ms"):
        shutil.copyfile(os.path.join(ROOT, name), os.path.join(server, name))
    os.makedirs(os.path.join(server, "release"))
    with open(os.path.join(ROOT, "release", "update.json"), encoding="utf-8") as handle:
        data = json.load(handle)
    payload = os.path.basename(data["payload"]["url"])
    shutil.copyfile(os.path.join(ROOT, "release", payload), os.path.join(server, "release", payload))
    with open(os.path.join(server, "release", "update.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2).replace(GITHUB, base))
    with open(os.path.join(ROOT, "release", "maxpkg-packager-1.x.ms"), "rb") as handle:  # 1.2.1 for old 3ds Max
        legacy = handle.read().decode("utf-16").replace(GITHUB, base)
    with open(os.path.join(server, "release", "maxpkg-packager-1.x.ms"), "wb") as handle:
        handle.write(legacy.encode("utf-16"))

    project = folders["project-1x"]
    for name in os.listdir(LEGACY_PROJECT):
        if not name.startswith("expected"):
            shutil.copyfile(os.path.join(LEGACY_PROJECT, name), os.path.join(project, name))
    old = subprocess.run(["git", "-C", ROOT, "show", LEGACY_COMMIT + ":maxpkg-packager.ms"], stdout=subprocess.PIPE,
                         check=True).stdout.decode("utf-16")
    old_update = "UPDATE=" + GITHUB + "maxpkg-packager.ms"
    if old_update not in old:
        sys.exit("The 1.x script has no UPDATE={}".format(GITHUB + "maxpkg-packager.ms"))
    with open(os.path.join(project, "maxpkg-packager.ms"), "wb") as handle:
        handle.write(old.replace(old_update, "UPDATE=" + base + "maxpkg-packager.ms").encode("utf-16"))
    return folders, data["version"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=os.path.join(tempfile.gettempdir(), "maxpkg-update-check"))
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    base = "http://127.0.0.1:{}/".format(arguments.port)
    folders, version = prepare(os.path.abspath(arguments.work), base)
    profile = folders["profile"].replace("\\", "\\\\")
    print("Rehearsal of the update to {} prepared in {}".format(version, os.path.abspath(arguments.work)))
    print("In 3ds Max (2022, then 2027), MAXScript:")
    print('  python.Execute "import os; os.environ[\'LOCALAPPDATA\'] = r\'{}\'"'.format(profile))
    print('  fileIn @"{}"'.format(os.path.join(folders["project-1x"], "maxpkg-packager.ms")))
    print("  -> 1.x opens and updates itself (requests below); press Restart in its notice.")
    print('  fileIn @"{}"   (installer: choose {})'.format(os.path.join(ROOT, "release", "MaxPkgPackager.mzp"),
                                                         folders["scratch"]))
    print("Serving {} - Ctrl+C stops.\n".format(base), flush=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=folders["server"])
    with http.server.ThreadingHTTPServer(("127.0.0.1", arguments.port), handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")


if __name__ == "__main__":
    main()
