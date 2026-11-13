"""Session owner. Owns every window, worker, timer and handler of one tool lifecycle.

Contract used by bootstrap.py: Controller(root) is passive; start() acquires resources; request_stop() begins shutdown;
poll_stop() advances it; is_stopped() is True when nothing is left.
"""

import gc
import os
import platform
import sys
import time

from . import DISPLAY_NAME, TOOL_NAME, UPDATE_URL, __version__, logs, qt_compat, settings, startguard
from .core import notes as core_notes, project as core_project, store, updater
from .qt_compat import QtCore, QtWidgets, Signal, is_valid, max_main_window
from .workers import JobRunner

_log = logs.get("controller")

# 3ds Max 2024 (PySide2 5.15.1 on Python 3.10) died inside Python's garbage collector as soon as one ran after the
# tool's window was built; the same Python and PySide2 outside Max did not (TerraScoop users' logs, 2026-10-27).
GC_HOLD = qt_compat.BINDING == "PySide2" and sys.version_info >= (3, 10)


def hold_gc():
    """Turn Python's automatic garbage collection off while the tool runs; None when it was off already.

    Returns the release for Cleanup: everything alive then is frozen first (gc.freeze, permanent), so no later
    collection walks over the broken object, and then collection runs again for whatever is made after that.
    """
    if not gc.isenabled():
        return None
    gc.disable()

    def release():
        gc.freeze()
        gc.enable()
    return release


def _in_max():
    try:
        import pymxs  # noqa: F401
    except ImportError:
        return False
    return True


class _Poster(QtCore.QObject):
    """Moves callables from worker threads to the main thread through a queued signal."""

    posted = Signal(object)

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.posted.connect(self._run)

    def _run(self, function):
        try:
            function()
        except Exception:
            _log.exception("Main-thread callback failed")


class _GilPump(object):
    """Lets worker threads run inside 3ds Max.

    Max keeps Python's GIL on its main thread while idle, so background threads only advance while main-thread Python
    runs. While jobs are active this timer briefly releases the GIL with a short sleep; the Qt event loop still runs
    between ticks, so the UI stays responsive. It stops as soon as no job is running.
    """

    INTERVAL_MS = 16
    YIELD_S = 0.010

    def __init__(self, runner):
        self.runner = runner
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self._tick)

    def kick(self):
        if not self.timer.isActive():
            self.timer.start()

    def _tick(self):
        if self.runner.active_count() == 0:
            self.timer.stop()
            return
        time.sleep(self.YIELD_S)

    def dispose(self):
        self.timer.stop()


class Cleanup(object):
    """Reverse-order release ledger; failed releases are kept for a retry."""

    def __init__(self):
        self.entries = []

    def own(self, label, release):
        self.entries.append((label, release))

    def release_all(self):
        failed, errors = [], []
        for label, release in reversed(self.entries):
            try:
                release()
            except Exception as error:
                failed.append((label, release))
                errors.append("{}: {}".format(label, error))
        self.entries = list(reversed(failed))
        if errors:
            raise RuntimeError("Cleanup incomplete: " + "; ".join(errors))


class Controller(object):
    def __init__(self, root):
        self.root = root
        self.state = "idle"
        self.cleanup = Cleanup()
        self.prefs = None
        self.theme = None
        self.runner = None
        self.window = None
        self.dialogs = {}
        self.guard = None
        self.log_handler = None
        self.project = None
        self.model = None
        self.updating = False
        self._job = None
        self._finalize_timer = None

    # Lifecycle ----------------------------------------------------------------------------------
    def start(self):
        from .ui.theme_manager import ThemeManager
        from .ui.main_window import MainWindow
        from .ui.project_model import ProjectModel

        self.state = "starting"
        held = hold_gc() if GC_HOLD else None  # Before anything of ours exists.
        host, max_version = "", None
        try:
            from pymxs import runtime as rt
            version = rt.maxVersion()
            host, max_version = "max{}".format(int(version[7])), str(version)
        except Exception:
            pass  # Outside Max (standalone harness).
        logs.set_host(host)  # One log per Max version: two Max versions never share a file.
        # Read what the last start left behind before the crash log opens a new session (startguard).
        self.guard = startguard.StartGuard(settings.user_data_dir(), host, __version__)
        if held is None and self.guard.gc_hold:
            held = hold_gc()
        if held is not None:
            self.cleanup.own("garbage collector", held)  # Registered first, so released last.
        self.guard.note("max", max_version)
        self.guard.note("qt", "{}, Qt {}, Python {}".format(qt_compat.BINDING, qt_compat.qt_version(),
                                                            platform.python_version()))
        qt_compat.SAFE["on"] = self.guard.safe
        handler = logs.attach(settings.user_data_dir())
        self.log_handler = handler  # Logs > Clear Logs empties this file through it
        self.cleanup.own("log handler", lambda: logs.detach(handler))
        release_crash_log = logs.enable_crash_log(settings.user_data_dir())
        self.cleanup.own("crash log", release_crash_log)
        _log.info("Starting %s %s from %s (%s, Qt %s)%s", TOOL_NAME, __version__, self.root, qt_compat.BINDING,
                  qt_compat.qt_version(), " in safe mode" if self.guard.safe else "")
        if self.guard.crashed_at:
            report = self.guard.report(TOOL_NAME)
            print(report)  # The MAXScript Listener: MaxPkg's log shows it to users who cannot find our files.
            _log.warning("%s", report)
        try:
            self._start_steps(ThemeManager, MainWindow, ProjectModel)
        except Exception:
            self.guard.step("failed")  # A Python error, not a crash: the next start is a normal one.
            raise

    def _start_steps(self, ThemeManager, MainWindow, ProjectModel):
        guard = self.guard
        guard.step("settings")
        self.prefs = settings.Settings().load()
        if self.prefs.load_error:
            _log.warning("Settings unreadable, defaults used: %s", self.prefs.load_error)
        guard.step("scale")  # Interface size before any window exists: every size is multiplied by it.
        factors = qt_compat.measure_scale(max_main_window(), self.prefs.get("ui_scale") or "auto")
        _log.info("Interface size %d %% (auto %d %%)", factors["target"] * 100, factors["auto"] * 100)
        guard.step("theme")
        poster = _Poster()
        self.cleanup.own("poster", poster.deleteLater)
        self.runner = JobRunner(post=poster.posted.emit)
        self.cleanup.own("runner", self.runner.request_stop)
        self.pump = _GilPump(self.runner)
        self.cleanup.own("gil pump", self.pump.dispose)
        self.runner.on_submit = self.pump.kick
        self.theme = ThemeManager(self.root, self.prefs)
        self.theme.load_initial()
        self.cleanup.own("theme", self.theme.dispose)
        setup_source = os.environ.get("MAXPKG_PACKAGER_SETUP") or ""
        if setup_source:  # Run by the installer (.mzp): choose a project instead of opening one
            self._start_setup(setup_source)
            return
        guard.step("project")
        self.project_root = os.path.abspath(os.environ.get("MAXPKG_PACKAGER_PROJECT") or os.getcwd())
        migrated = bool(store.migrate_legacy(self.project_root))  # A project of version 1.x: its files move now
        self.project = store.load(self.project_root)
        self._prefill_new_project()
        self.model = ProjectModel(self.project)
        self.cleanup.own("project", self.model.dispose)  # Released after the window: saves the last edits.
        _log.info("Project folder %s", self.project_root)
        guard.step("window")
        self.window = MainWindow(self, max_main_window())
        guard.step("geometry")
        self.window.restore_geometry_state(None if guard.safe else self.prefs.get("window_geometry"))
        self.cleanup.own("main window", self._dispose_window)
        self.theme.register(self.window)
        guard.step("show")
        self.window.show()
        self.state = "running"
        QtCore.QTimer.singleShot(0, self._ready)
        if self.prefs.get("auto_update") and not guard.safe:
            QtCore.QTimer.singleShot(2000, lambda: self.check_updates(None, automatic=True))  # After Qt has shown the window: the start worked.
        if guard.crashed_at:
            self.window.toast.show_message("Safe start: the last start of {} crashed 3ds Max. Please send the logs (Logs "
                                   "button) to the developer.".format(DISPLAY_NAME), "warning", 15)
        found = self._update_notice(migrated)
        if found and not guard.safe:
            QtCore.QTimer.singleShot(300, lambda: self.show_update(found))  # Over the window, once it is on screen
        _log.info("Started")

    def _update_notice(self, migrated):
        """What the "Updated" window says at this start (core.notes.notice), or None. The version is remembered at
        once, so the window comes up one time only, whatever happens to it."""
        state = updater.read_current(self.installed_home()) if self.installed_home() else None
        found = core_notes.notice(__version__, str(self.prefs.get("seen_version") or ""),
                                  (state or {}).get("previous") or "", migrated)
        if self.prefs.get("seen_version") != __version__:
            self.set_preference("seen_version", __version__)
        if found:
            _log.info("Update notice: %s", found)
        return found

    def show_update(self, found):
        """The "Updated" window for a notice from core.notes.notice()."""
        if self.state != "running" or self.window is None or not is_valid(self.window):
            return None
        from .ui.whatsnew import UpdateDialog
        versions = core_notes.to_show(__version__, found)
        return self._show_dialog("update", lambda _dialogs: UpdateDialog(self, self.window, found, versions))

    def _start_setup(self, launcher_source):
        """The installer's window: puts the launcher `launcher_source` into a script project the user chooses."""
        from .ui.setup_window import SetupWindow
        _log.info("Setup: the launcher comes from %s", launcher_source)
        self.guard.step("window")
        self.window = SetupWindow(self, launcher_source, max_main_window())
        self.window.restore_geometry_state(None)  # Centred on 3ds Max's screen; the packager's own place is not used
        self.cleanup.own("setup window", self._dispose_window)
        self.theme.register(self.window)
        self.guard.step("show")
        self.window.show()
        self.state = "running"
        QtCore.QTimer.singleShot(0, self._ready)
        _log.info("Started")

    def open_launcher(self, launcher):
        """Run a project's launcher (after Setup): the packager starts again, in that project."""
        try:
            from pymxs import runtime as rt
        except ImportError:
            return False
        QtCore.QTimer.singleShot(0, lambda: rt.fileIn(launcher))  # After the click that asked for it returns
        return True

    def _prefill_new_project(self):
        """A project that was never configured starts with the obvious values filled in."""
        project = self.project
        if not project.guid.strip():
            project.guid = core_project.new_guid()
        if not project.package_name.strip():
            folder = os.path.basename(project.root.rstrip("\\/"))
            cleaned = "".join(ch if (ch.isalnum() and ord(ch) < 128) or ch in " -_" else " " for ch in folder)
            project.package_name = " ".join(cleaned.split())
            project.button_name = project.button_name or project.package_name
        project.developer = project.developer or self.prefs.get("last_developer")
        project.license = project.license or self.prefs.get("last_license")
        icon = os.path.join(project.support_dir, core_project.ICON_FILE)
        if not project.svg_icon and os.path.isfile(icon):
            project.svg_icon = core_project.norm(icon)

    def remember_author(self):
        """Developer and license carry over to the next project."""
        for key, value in (("last_developer", self.project.developer.strip()), ("last_license", self.project.license)):
            if value and self.prefs.get(key) != value:
                self.set_preference(key, value)

    def _ready(self):
        if self.state == "running":
            self.guard.step("ready")

    def _dispose_window(self):
        for dialog in list(self.dialogs.values()):
            if is_valid(dialog):
                dialog.dispose()
        self.dialogs = {}
        window, self.window = self.window, None
        if window is not None and is_valid(window):
            if not getattr(window, "is_setup", False):
                # Position and size come back on the next launch (also after a relaunch or Max restart).
                self.prefs.set("window_geometry", window.geometry_state())
                self._save_prefs()
            self.theme.unregister(window)
            window.dispose()
            window.hide()
            window.deleteLater()

    running = property(lambda self: self.state == "running")

    def request_stop(self):
        """Idempotent. Stops accepting work, cancels jobs and closes windows."""
        if self.state in ("stopping", "stopped"):
            return
        _log.info("Stopping %s", TOOL_NAME)
        if self.guard is not None and self.state == "running":
            self.guard.step("stopped")  # Closed before it was ready: not a crash.
        self.state = "stopping"
        if self.runner is not None:
            self.runner.request_stop()
        self._dispose_window()  # Windows go now; the log handler and poster stay until workers are idle.
        if self._finalize_timer is None:
            self._finalize_timer = QtCore.QTimer()  # Finishes cleanup after a user close even when no relaunch polls.
            self._finalize_timer.setInterval(100)
            self._finalize_timer.timeout.connect(self.poll_stop)
            self._finalize_timer.start()

    def poll_stop(self):
        if self.state != "stopping":
            return
        if self.runner is not None and not self.runner.is_idle():
            return
        try:
            self.cleanup.release_all()
        except RuntimeError:
            _log.exception("Cleanup failed; it will be retried on the next launch")
            return
        if self._finalize_timer is not None:
            self._finalize_timer.stop()
            self._finalize_timer = None
        self.state = "stopped"

    def is_stopped(self):
        return self.state in ("stopped", "idle")

    # Preferences --------------------------------------------------------------------------------
    def _save_prefs(self):
        try:
            self.prefs.save()
        except OSError as error:
            _log.warning("Settings not saved: %s", error)
            if self.window is not None:
                self.window.set_status("Settings could not be saved: {}".format(error))

    def set_preference(self, key, value):
        if key in self.prefs.overrides:
            self.prefs.override(key, value)  # Session-only value (tests, fixtures): never reaches the file.
        else:
            self.prefs.set(key, value)
            self._save_prefs()

    def reopen(self):
        """Close the tool and open it again through its launcher (inside Max), e.g. for a new interface size, which
        applies while windows are built. False outside Max."""
        try:
            from pymxs import runtime as rt
        except ImportError:
            return False
        script = os.path.join(self.project_root, "maxpkg-packager.ms")
        QtCore.QTimer.singleShot(0, lambda: rt.fileIn(script))  # After the click that asked for it returns.
        return True

    def can_reopen(self):
        return _in_max()

    # Dialogs ------------------------------------------------------------------------------------
    def show_settings(self):
        self._show_dialog("settings", lambda d: d.SettingsDialog(self, self.window))

    def show_logs(self):
        self._show_dialog("logs", lambda d: d.LogDialog(self, self.window))

    def show_about(self):
        self._show_dialog("about", lambda d: d.AboutDialog(self, self.window))

    def _show_dialog(self, key, factory):
        from .ui import dialogs
        dialog = self.dialogs.get(key)
        if dialog is None or not is_valid(dialog):
            dialog = factory(dialogs)
            dialog.finished.connect(lambda *_: self._close_dialog(key))
            self.dialogs[key] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _close_dialog(self, key):
        dialog = self.dialogs.pop(key, None)
        if dialog is not None and is_valid(dialog):
            dialog.dispose()

    # Work ---------------------------------------------------------------------------------------
    def run_job(self, work, on_progress, on_done):
        """Run work(cancel, report) in a worker; report(label, done, total) and on_done(result or error) arrive on
        the main thread. Workers get plain data and never touch pymxs or Qt widgets."""
        def report(label, done, total):
            self.runner.post(lambda: on_progress(label, done, total))

        def finished(value):
            self._job = None
            on_done(value)

        self._job = self.runner.submit(lambda cancel: work(cancel, report), on_done=finished, on_error=finished,
                                       name="job")
        return self._job

    def confirm_stop(self, reason="close"):
        """Ask before a close or relaunch would cancel running work. True = go ahead."""
        if self._job is None:
            return True
        window = self.window if self.window is not None and is_valid(self.window) else None
        action = "Relaunch" if reason == "relaunch" else "Close"
        from .ui.dialogs import ask
        if ask(self, window, DISPLAY_NAME, "Work is running.", "{} {} and cancel it?".format(action, DISPLAY_NAME),
               "Cancel It and {}".format(action), "Keep Working"):
            self.runner.cancel(self._job)
            return True
        return False

    # Updates ------------------------------------------------------------------------------------
    def installed_home(self):
        """The app home when this copy runs from an installed version (updates can be applied), else None."""
        home = os.path.dirname(self.root)
        state = updater.read_current(home)
        if state and state.get("dir") == os.path.basename(self.root):
            return home
        return None

    def check_updates(self, on_done, automatic=False):
        """Check in the background; install a newer version when running from the installed layout.

        on_done(result) gets a dict {"version", "installed", "notes", "error"} on the main thread. The running
        session is never modified: a new version takes effect at the next launch."""
        if self.updating or self.runner is None or self.state != "running":
            return False
        self.updating = True
        home = self.installed_home()
        project_root = self.project_root

        def work(cancel):
            result = {"version": "", "installed": False, "notes": [], "error": ""}
            try:
                data = updater.fetch_manifest(UPDATE_URL)
            except updater.UpdateError as error:  # Offline or not published: an expected, quiet outcome.
                result["error"] = str(error)
                return result
            info = updater.fetch_info(UPDATE_URL, __version__, data=data)
            if home:  # Keep the project's launcher current; verified, with a .bak during replace. The install and
                # uninstall windows come with the application itself (core/hooks.py), not from here.
                entry = data.get("launcher")
                path = os.path.join(project_root, "maxpkg-packager.ms")
                if entry and os.path.isfile(path) and updater.sha256_file(path) != entry.get("sha256", "").lower():
                    updater.replace_file(entry["url"], entry.get("sha256", ""), path)
            if info is None:
                return result
            result.update(version=info.version, notes=info.notes)
            if home and not cancel.is_set():
                updater.download_and_install(home, info)
                result["installed"] = True
            return result

        def finished(value):
            self.updating = False
            if isinstance(value, Exception):
                value = {"version": "", "installed": False, "notes": [], "error": str(value)}
                if not automatic:
                    _log.warning("Update check failed: %s", value["error"])
            elif value.get("version"):
                _log.info("Update %s %s", value["version"], "installed" if value["installed"] else "available")
            if on_done is not None:
                on_done(value)
            elif self.window is not None and is_valid(self.window):
                self.window.on_update_result(value, automatic)

        self.runner.submit(work, on_done=finished, on_error=finished, name="update")
        return True
