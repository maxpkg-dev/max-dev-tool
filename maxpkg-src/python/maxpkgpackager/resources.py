"""Package-relative resource paths. Never depends on the working directory or a developer checkout."""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Layout: <root>/python/<package>/resources.py; assets in <root>/assets.
ROOT = os.path.dirname(os.path.dirname(PACKAGE_DIR))


def asset(*parts):
    return os.path.join(ROOT, "assets", *parts)


def icon_path(name):
    return asset("icons", name + ".svg")


def ui_file(*parts):
    return os.path.join(PACKAGE_DIR, "ui", *parts)


def require(path):
    if not os.path.exists(path):
        raise IOError("Resource is missing: {}. Reinstall the tool.".format(path))
    return path
