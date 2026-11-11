"""Executed by the launcher .ms inside 3ds Max's Python. Starts or restarts the MaxPkg Packager session.

The session anchor lives in sys.modules["_maxpkgpackager_session"], outside the reloadable package, so a
relaunch can find the previous owner, ask it to stop, wait for it on a Qt timer (never sleeping on the
main thread), then import fresh code and start exactly one replacement.
"""

import importlib
import importlib.util
import os
import sys
import time
import traceback
import types

PACKAGE = "maxpkgpackager"
ANCHOR = "_maxpkgpackager_session"
STOP_TIMEOUT = 15.0


def _qtcore():
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6 import QtCore
    else:
        from PySide2 import QtCore
    return QtCore


def _report(message):
    print("MaxPkg Packager: " + message)


def _load_package(root):
    """Import a fresh copy of the package from `root` (no window, no Qt yet)."""
    for name in list(sys.modules):
        if name == PACKAGE or name.startswith(PACKAGE + "."):
            del sys.modules[name]
    importlib.invalidate_caches()
    folder = os.path.join(root, "python", PACKAGE)
    spec = importlib.util.spec_from_file_location(PACKAGE, os.path.join(folder, "__init__.py"),
                                                  submodule_search_locations=[folder])
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the MaxPkg Packager package from " + folder)
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    spec.loader.exec_module(package)
    return package


def _import_fresh(root):
    _load_package(root)
    return importlib.import_module(PACKAGE + ".controller")


def _install_api():
    """MAXScript reaches the API through this small module (python.import "maxpkgpackager_api"). It lives outside the
    reloadable package and forwards every name to the current maxpkgpackager.api, so the MAXScript global
    MaxPkgPackerApi keeps working after a relaunch or an update."""
    proxy = types.ModuleType("maxpkgpackager_api")

    def forward(name):
        return getattr(importlib.import_module(PACKAGE + ".api"), name)
    proxy.__getattr__ = forward
    sys.modules["maxpkgpackager_api"] = proxy


def launch_headless(root):
    """Load only the API (agents and scripts). A packager window that is open stays as it is and is used by the API."""
    _install_api()
    state = sys.modules.get(ANCHOR)
    owner = getattr(state, "owner", None)
    if owner is not None and not owner.is_stopped():
        return
    if PACKAGE not in sys.modules:
        _load_package(root)


def _roll_back(root):
    """A freshly updated version that cannot start: switch back to the previous installed version, if there is one.

    Returns the folder of the version that is current again (to start it right away), or None."""
    try:
        home = os.path.dirname(root)
        if not os.path.isfile(os.path.join(home, "current.json")):
            return None  # A repository checkout or an unusual layout: nothing to roll back.
        spec = importlib.util.spec_from_file_location(
            "_maxpkg_rollback", os.path.join(root, "python", PACKAGE, "core", "updater.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        state = module.read_current(home)
        if not state or state.get("dir") != os.path.basename(root):
            return None  # Only the version that is current and failed is rolled back.
        if module.rollback(home):
            _report("this version could not start; going back to the previous version.")
            return os.path.join(home, module.read_current(home)["dir"])
    except Exception:
        _report("rollback failed:\n" + traceback.format_exc())
    return None


def _start_new(state, root):
    candidate = None
    try:
        controller = _import_fresh(root)
        candidate = controller.Controller(root)
        state.owner = candidate
        candidate.start()
    except Exception:
        _report("start failed:\n" + traceback.format_exc())
        previous_root = _roll_back(root)
        if candidate is not None:
            try:
                candidate.request_stop()
                candidate.poll_stop()
            except Exception:
                _report("cleanup after failed start also failed:\n" + traceback.format_exc())
        if previous_root:
            _start_new(state, previous_root)  # The previous version has no previous of its own: no loop.


def launch(root):
    state = sys.modules.get(ANCHOR)
    if state is None:
        state = types.ModuleType(ANCHOR)
        sys.modules[ANCHOR] = state
    if getattr(state, "transitioning", False):
        return  # A relaunch is already in progress; repeated clicks coalesce.
    old = getattr(state, "owner", None)
    if old is not None:
        try:
            old.poll_stop()  # Finish a cleanup left over from an earlier close, if any.
        except Exception:
            pass
    if old is None or old.is_stopped():
        state.transitioning = True
        try:
            _start_new(state, root)
        finally:
            state.transitioning = False
        return

    # A running build is not interrupted silently: the old session asks first (older versions have no
    # confirm_stop and stop as before).
    confirm = getattr(old, "confirm_stop", None)
    if confirm is not None:
        try:
            if not confirm("relaunch"):
                return
        except Exception:
            _report("could not ask the previous session:\n" + traceback.format_exc())

    state.transitioning = True
    try:
        old.request_stop()
    except Exception:
        state.transitioning = False
        _report("could not stop the previous session:\n" + traceback.format_exc())
        return

    QtCore = _qtcore()
    timer = QtCore.QTimer()
    state.poll_timer = timer  # Strong reference on the anchor, outside the reloadable package.
    deadline = time.monotonic() + STOP_TIMEOUT

    def tick():
        try:
            old.poll_stop()
            if old.is_stopped():
                timer.stop()
                state.poll_timer = None
                try:
                    _start_new(state, root)
                finally:
                    state.transitioning = False
            elif time.monotonic() > deadline:
                timer.stop()
                state.poll_timer = None
                state.transitioning = False
                _report("the previous session did not stop in time. Run MaxPkg Packager again to retry.")
        except Exception:
            timer.stop()
            state.poll_timer = None
            state.transitioning = False
            _report("restart failed:\n" + traceback.format_exc())

    timer.timeout.connect(tick)
    timer.start(50)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("MAXPKG_PACKAGER_HEADLESS") == "1":
    launch_headless(_ROOT)
else:
    _install_api()
    launch(_ROOT)
