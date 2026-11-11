"""Setting up a script project for MaxPkg Packager (no Qt).

The installer (.mzp) puts one file, the launcher maxpkg-packager.ms, into the root folder of the project the user
chooses. Nothing else is written there: the packager creates the max-package folder itself on its first start and
moves the files of version 1.x into it. A launcher that is already there (1.x or 2.x) is replaced; the old copy is
kept in a temporary folder until the new one is in place, never next to it.
"""

import os
import re
import shutil
import tempfile

LAUNCHER_NAME = "maxpkg-packager.ms"
_VERSION = re.compile(r"^VERSION=(\S+)", re.M)


def launcher_path(folder):
    return os.path.join(folder, LAUNCHER_NAME)


def launcher_version(path):
    """VERSION from the [INFO] header of a launcher (2.x, ASCII) or of the 1.x script (UTF-16); "" when none."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(8192)
    except OSError:
        return ""
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = head.decode("utf-16", errors="ignore")
    else:
        text = head.decode("utf-8", errors="ignore")
    match = _VERSION.search(text.replace("\r", ""))
    return match.group(1) if match else ""


def has_settings(folder):
    """True when the project was set up before (its max-package folder holds its settings). Installing never touches
    that folder: only the launcher next to it is replaced."""
    from .project import SETTINGS_FILE, SUPPORT_DIR
    return os.path.isfile(os.path.join(folder, SUPPORT_DIR, SETTINGS_FILE))


def folder_problem(folder):
    """Why the launcher cannot go into `folder`, or "" when it can."""
    if not folder or not folder.strip():
        return "Choose the root folder of your script project."
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        return "This folder does not exist."
    drive, rest = os.path.splitdrive(folder)
    if rest.strip("\\/") == "":
        return "Choose the folder of your project, not a whole drive."
    if not os.access(folder, os.W_OK):
        return "This folder cannot be written to. Choose another one."
    return ""


def describe(folder):
    """What installing does in `folder`: "new" (no launcher yet), "old" (version 1.x: replaced, its settings move into
    max-package on the first start), "same" (this version is already there) or "other" (another 2.x version)."""
    version = launcher_version(launcher_path(folder))
    if not version and not os.path.isfile(launcher_path(folder)):
        return "new"
    if version.startswith("1.") or not version:
        return "old"
    from .. import __version__
    return "same" if version == __version__ else "other"


def install_launcher(source, folder):
    """Copy the launcher `source` into `folder` (replacing one that is there). Returns the target path."""
    problem = folder_problem(folder)
    if problem:
        raise ValueError(problem)
    target = launcher_path(os.path.abspath(folder))
    if os.path.abspath(source).lower() == target.lower():
        return target  # Run from the project itself: it is already there.
    temp = tempfile.mkdtemp(prefix="maxpkg-setup-")
    try:
        backup = os.path.join(temp, "backup")
        if os.path.isfile(target):
            shutil.copyfile(target, backup)
        try:
            shutil.copyfile(source, target)
        except OSError:
            if os.path.isfile(backup):
                shutil.copyfile(backup, target)
            raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return target
