"""Prepare a release of MaxPkg Packager (any Python 3.7+):

    python maxpkg-src/tools/release.py [--base-url URL] [--publish]

It checks the launcher, builds the payload, the installer and the update information:
    maxpkg-packager.ms                     the one file a project needs: checked to be ASCII with CRLF line endings and
                                           to carry the same VERSION as the package (it is the source, not generated)
    release/maxpkg-packager-app-<v>.zip    the application: python/ and assets/ from maxpkg-src/,     (committed)
                                           and the two hooks from the root as assets/hooks/
    release/update.json                    read by installed copies: version, payload URL + SHA-256,  (committed)
                                           launcher, hooks
    release/MaxPkgPackager.mzp             the installer for people: drag it into 3ds Max, choose a project (attached
                                           to the GitHub release; the same name every time, so .../releases/latest/
                                           download/MaxPkgPackager.mzp always gives the newest)
    release/release-notes.md               the text of the GitHub release
    release/maxpkg-packager-1.x.ms         version 1.2.1 for 3ds Max older than 2022, offered there by the launcher and
                                           the installer; its UPDATE points to itself, so it stays on 1.x. Not made
                                           here (a copy of commit 3727cfd), only checked.               (committed)

The installer holds the launcher, the application archive and an update.json that names the archive without a web
address, so it installs without the internet; install.ms runs the launcher in setup mode, which asks for the project.
The version comes from maxpkg-src/python/maxpkgpackager/__init__.py; the release notes from the launcher's [<version>]
section. Nothing is committed, pushed or published.

--publish (what release.bat runs) then shows what would be committed and asks; only after "y" it commits everything,
pushes main and creates the GitHub release v<version> with the installer (gh, the GitHub command line). It stops
without asking when the branch is not main or v<version> is already published.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "maxpkg-src")  # Not "src": a client project may have one
RELEASE = os.path.join(ROOT, "release")
LAUNCHER = os.path.join(ROOT, "maxpkg-packager.ms")
HOOKS = ROOT  # _install.ms and _uninstall.ms stay in the root: packager 1.x updates them from there
HOOK_FILES = ("_install.ms", "_uninstall.ms")
LEGACY = os.path.join(RELEASE, "maxpkg-packager-1.x.ms")
DEFAULT_BASE = "https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/"
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIXES = (".pyc", ".pyo", ".bak", ".tmp", ".log")


def package_version():
    with open(os.path.join(SOURCE, "python", "maxpkgpackager", "__init__.py"), encoding="utf-8") as handle:
        return re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", handle.read(), re.M).group(1)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def check_launcher(version):
    """ASCII (read by MAXScript and by the INI functions of packager 1.x, which updates itself to this file), CRLF,
    and the same version as the package. Returns the release notes of this version."""
    raw = open(LAUNCHER, "rb").read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        sys.exit("maxpkg-packager.ms must contain ASCII characters only")
    normalized = text.replace("\r\n", "\n").replace("\n", "\r\n")
    if normalized != text:
        with open(LAUNCHER, "wb") as handle:
            handle.write(normalized.encode("ascii"))
    found = re.search(r"^VERSION=(\S+)", text, re.M)
    if not found or found.group(1) != version:
        sys.exit("Version mismatch: package {} but launcher VERSION={}".format(version, found and found.group(1)))
    section = re.search(r"^\[" + re.escape(version) + r"\]\s*$(.*?)^\[", normalized, re.M | re.S)
    if not section:
        sys.exit("The launcher has no [{}] release notes section".format(version))
    return [line.strip().rstrip("=").strip() for line in section.group(1).splitlines() if line.strip()]


SERVED = ("maxpkg-packager.ms", "_install.ms", "_uninstall.ms", "release/update.json", "release/maxpkg-packager-1.x.ms",
          "release/maxpkg-packager-app-0.zip")  # The payload's name stands for every release/*.zip


def check_byte_exact():
    """Installed copies check the SHA-256 of what main serves, so Git must store those files byte for byte (-text in
    .gitattributes). With core.autocrlf it would commit them with LF while update.json holds the hashes of the CRLF
    files here: every update would be refused. Stops the release when a rule is missing."""
    for path in SERVED:
        try:
            code, out = _git("check-attr", "text", "--", path)
        except OSError:
            return  # No git here (a copy without history): nothing is committed from it either
        if code != 0:
            return
        if not out.endswith(": text: unset"):
            sys.exit("{} must be stored byte for byte: keep '-text' for it in .gitattributes (now: {})".format(
                path, out.rsplit(":", 1)[-1].strip()))


def check_legacy(base):
    """release/maxpkg-packager-1.x.ms: version 1.x (UTF-16, as 1.x writes it) whose updates come from itself."""
    try:
        with open(LEGACY, "rb") as handle:
            text = handle.read().decode("utf-16")
    except (OSError, UnicodeDecodeError):
        sys.exit("release/maxpkg-packager-1.x.ms is missing or not UTF-16: 3ds Max older than 2022 needs it")
    if not re.search(r"^VERSION=1\.", text, re.M):
        sys.exit("release/maxpkg-packager-1.x.ms must be version 1.x")
    if "UPDATE=" + base + "release/maxpkg-packager-1.x.ms" not in text:
        sys.exit("release/maxpkg-packager-1.x.ms must update from itself (UPDATE={}release/maxpkg-packager-1.x.ms), "
                 "or 1.x users of old 3ds Max get version 2 again".format(base))


def build_payload(version):
    os.makedirs(RELEASE, exist_ok=True)
    for name in os.listdir(RELEASE):  # One payload per release; older ones are in git history.
        if name.startswith("maxpkg-packager-app-") and name.endswith(".zip"):
            os.remove(os.path.join(RELEASE, name))
    target = os.path.join(RELEASE, "maxpkg-packager-app-{}.zip".format(version))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for top in ("python", "assets"):
            for current, directories, names in os.walk(os.path.join(SOURCE, top)):
                directories[:] = sorted(d for d in directories if d not in SKIP_DIRS)
                for name in sorted(names):
                    if name.endswith(SKIP_SUFFIXES):
                        continue
                    full = os.path.join(current, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, SOURCE).replace("\\", "/"), (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as handle:
                        archive.writestr(info, handle.read())  # Fixed timestamps: same sources, same hash.
        for name in HOOK_FILES:  # Part of every package the packager builds (core/hooks.py reads them from here)
            info = zipfile.ZipInfo("assets/hooks/" + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(HOOKS, name), "rb") as handle:
                archive.writestr(info, handle.read())
    return target


INSTALLER = "MaxPkgPackager.mzp"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # Same sources, same archive, same hash
INSTALL_MS = """-- MaxPkg Packager installer, run by MaxPkgPackager.mzp (dragged into a viewport or run with Scripting > Run Script).
-- It installs the packager into your user profile from the files next to this script, without the internet, and then
-- asks which script project gets maxpkg-packager.ms. In 3ds Max older than 2022 it offers version 1.2.1 instead: the
-- launcher put into the chosen project replaces itself with release/maxpkg-packager-1.x.ms (which stays on 1.x).
(
    local maxRelease = (maxVersion())[1]
    if (maxRelease < 24000) then (
        local tooOld = "MaxPkg Packager 2 needs 3ds Max 2022 or newer. This is 3ds Max " + ((1998 + maxRelease / 1000) as string) + "."
        local legacyQuestion = tooOld + "\\n\\nVersion 1.2.1 works in this 3ds Max. Choose your script project to put it there?"
        if (queryBox legacyQuestion title:"MaxPkg Packager") do (
            local projectFolder = getSavePath caption:"Root folder of your script project"
            if (projectFolder != undefined) do (
                local launcherFile = projectFolder + "\\\\maxpkg-packager.ms"
                if (doesFileExist launcherFile) do (
                    setFileAttribute launcherFile #readOnly false
                    deleteFile launcherFile
                )
                if (copyFile ((getFilenamePath (getThisScriptFileName())) + "maxpkg-packager.ms") launcherFile) then (
                    global MaxPkgPackagerLegacyAccepted = true
                    try (fileIn launcherFile) catch ()
                    MaxPkgPackagerLegacyAccepted = false
                ) else (
                    messageBox ("Could not write to " + projectFolder) title:"MaxPkg Packager"
                )
            )
        )
    ) else (
        local folder = getFilenamePath (getThisScriptFileName())
        global MaxPkgPackagerSetup = true
        try (fileIn (folder + "maxpkg-packager.ms")) catch (
            messageBox ("MaxPkg Packager could not be installed.\\n\\nDownload the installer again and drag it into a viewport:\\nhttps://github.com/maxpkg-dev/max-dev-tool/releases/latest/download/MaxPkgPackager.mzp\\nYour projects and their settings (the max-package folder) are kept.\\n\\n" + getCurrentException()) title:"MaxPkg Packager"
        )
        MaxPkgPackagerSetup = false
    )
)
"""
MZP_RUN = """name "MaxPkg Packager"
extract to "$temp\\MaxPkgPackagerSetup-{version}"
drop "install.ms"
run "install.ms"
clear temp on MAX exit
"""


def _crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


def _put(archive, name, data):
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def build_installer(version, payload, data):
    """release/MaxPkgPackager.mzp: installs the packager from inside the archive and asks for the project."""
    offline = dict(data, payload=dict(data["payload"], url=os.path.basename(payload)))  # Installed from the archive
    target = os.path.join(RELEASE, INSTALLER)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        _put(archive, "mzp.run", _crlf(MZP_RUN.format(version=version)))
        _put(archive, "install.ms", _crlf(INSTALL_MS))
        with open(LAUNCHER, "rb") as handle:
            _put(archive, "maxpkg-packager.ms", handle.read())
        _put(archive, "update.json", (json.dumps(offline, indent=2) + "\n").encode("utf-8"))
        with open(payload, "rb") as handle:
            _put(archive, os.path.basename(payload), handle.read())
    return target


def write_notes(version, notes):
    """release/release-notes.md: the text of the GitHub release."""
    lines = ["Drag **MaxPkgPackager.mzp** into a 3ds Max viewport (2022 or newer), choose your script project, "
             "and run `maxpkg-packager.ms` from it.", "", "## {}".format(version), ""]
    for note in notes:  # "+ Added: text" -> "- **Added:** text"
        note = re.sub(r"^[+*\-]+\s*", "", note)
        lines.append("- " + re.sub(r"^(\w+):\s*", r"**\1:** ", note))
    path = os.path.join(RELEASE, "release-notes.md")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


REPOSITORY = "maxpkg-dev/max-dev-tool"


def _git(*arguments):
    result = subprocess.run(("git",) + arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
    return result.returncode, result.stdout.strip()


def _run(*command):
    print("> " + " ".join(command))
    return subprocess.run(command, cwd=ROOT).returncode == 0


def publish(version, installer, notes_file):
    """Commit, push main and create the GitHub release, after the user says yes. True when published."""
    tag = "v" + version
    _code, branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        print("\nInstalled copies update from main, so a release is published from main. This is '{}': merge it "
              "into main, switch to main and run again.".format(branch))
        return False
    _git("fetch", "--tags", "--quiet")
    if _git("tag", "--list", tag)[1]:
        print("\n{} is already published. Raise the version (maxpkg-src/python/maxpkgpackager/__init__.py and VERSION "
              "in maxpkg-packager.ms) and add its notes first.".format(tag))
        return False
    _code, changes = _git("status", "--short")
    print("\nTo be committed:\n" + (changes or "  (nothing: everything is committed already)"))
    answer = input("\nPublish MaxPkg Packager {}: commit, push main and create the GitHub release? [y/N] ".format(version))
    if answer.strip().lower() not in ("y", "yes"):
        print("Nothing was published.")
        return False
    if changes and not (_run("git", "add", "-A") and _run("git", "commit", "-m", "MaxPkg Packager " + version)):
        return False
    if not _run("git", "push", "origin", "main"):
        return False
    title = "MaxPkg Packager " + version
    if shutil.which("gh") and _run("gh", "release", "create", tag, os.path.relpath(installer, ROOT), "--repo", REPOSITORY,
                                   "--target", "main", "--title", title, "--notes-file",
                                   os.path.relpath(notes_file, ROOT)):
        print("\nPublished: https://github.com/{}/releases/tag/{}".format(REPOSITORY, tag))
        return True
    print("\nmain is pushed, but the GitHub release was not created (gh is missing or failed). Create it by hand: "
          "https://github.com/{}/releases/new?tag={} - title '{}', attach {}, text from {}.".format(
              REPOSITORY, tag, title, os.path.relpath(installer, ROOT), os.path.relpath(notes_file, ROOT)))
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--publish", action="store_true", help="commit, push main and create the GitHub release")
    arguments = parser.parse_args()
    base = arguments.base_url.rstrip("/") + "/"
    version = package_version()
    notes = check_launcher(version)
    check_byte_exact()
    if base == DEFAULT_BASE:
        check_legacy(base)
    payload = build_payload(version)
    data = {
        "schema": 1,
        "version": version,
        "payload": {"url": base + "release/" + os.path.basename(payload), "sha256": sha256(payload),
                    "size": os.path.getsize(payload)},
        "launcher": {"url": base + "maxpkg-packager.ms", "sha256": sha256(LAUNCHER)},
        "hooks": {name: {"url": base + name, "sha256": sha256(os.path.join(HOOKS, name))}
                  for name in HOOK_FILES},
        "notes": notes,
    }
    with open(os.path.join(RELEASE, "update.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print("version ", version)
    print("payload ", payload, data["payload"]["sha256"])
    print("update  ", os.path.join(RELEASE, "update.json"))
    installer = build_installer(version, payload, data)
    notes_file = write_notes(version, notes)
    print("mzp     ", installer)
    print("notes   ", notes_file)
    if arguments.publish:
        return 0 if publish(version, installer, notes_file) else 1
    print("publish  release.bat (or this script with --publish) commits, pushes main and creates the GitHub release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
