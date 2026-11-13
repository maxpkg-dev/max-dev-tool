"""The install and uninstall windows of a package: _install.ms and _uninstall.ms.

They ship with the packager and go into every package it builds. A project keeps its copies in max-package: the
packager puts them there when it opens the project and keeps them the same as its own.
"""

import os
import shutil

from .project import HOOK_FILES, SUPPORT_DIR

# <app>/python/maxpkgpackager/core/hooks.py: an installed version (v<version>) or maxpkg-src in the repository
_APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def shipped(name):
    """The file that ships with this packager, or "" when it is missing. An installed copy has it in assets/hooks
    (release.py puts it into the application archive); in the repository it is in the root, where packager 1.x
    updates it from."""
    for path in (os.path.join(_APP, "assets", "hooks", name), os.path.join(os.path.dirname(_APP), name)):
        if os.path.isfile(path):
            return path
    return ""


def _same(first, second):
    try:
        with open(first, "rb") as one, open(second, "rb") as two:
            return one.read() == two.read()
    except OSError:
        return False


def sync(root):
    """Put the shipped files into the project's max-package folder, replacing copies that differ. Returns the names
    written. A folder that cannot be written is left as it is: a build takes the shipped files themselves."""
    folder = os.path.join(root, SUPPORT_DIR)
    written = []
    for name in HOOK_FILES:
        source = shipped(name)
        target = os.path.join(folder, name)
        if not source or _same(source, target):
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            shutil.copyfile(source, target)
            written.append(name)
        except OSError:
            pass
    return written
