"""The open project as the interface sees it: edits, delayed autosave and delayed validation."""

import logging

from ..core import store, validate
from ..qt_compat import QtCore, Signal

_log = logging.getLogger("maxpkgpackager.project")


class ProjectModel(QtCore.QObject):
    validated = Signal(list)  # list of core.validate.Issue
    save_failed = Signal(str)
    structure_changed = Signal()  # Files, macros, rules or version changed: pages re-read the project.

    SAVE_DELAY_MS = 600
    VALIDATE_DELAY_MS = 150

    def __init__(self, project, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.project = project
        self.issues = []
        self._dirty = False
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self.SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save_now)
        self._validate_timer = QtCore.QTimer(self)
        self._validate_timer.setSingleShot(True)
        self._validate_timer.setInterval(self.VALIDATE_DELAY_MS)
        self._validate_timer.timeout.connect(self.validate_now)

    def touch(self, structural=False):
        """Something was edited: save and validate shortly after the last edit."""
        self._dirty = True
        self._save_timer.start()
        self._validate_timer.start()
        if structural:
            self.structure_changed.emit()

    def validate_now(self):
        self._validate_timer.stop()
        try:
            self.issues = validate.validate(self.project)
        except Exception:
            _log.exception("Validation crashed")
            self.issues = [validate.Issue(validate.ERROR, "Validation failed unexpectedly (see the log)")]
        self.validated.emit(self.issues)
        return self.issues

    def errors(self):
        return [issue for issue in self.issues if issue.level == validate.ERROR]

    def save_now(self):
        self._save_timer.stop()
        if not self._dirty:
            return True
        try:
            store.save(self.project)
        except OSError as error:
            _log.warning("Project not saved: %s", error)
            self.save_failed.emit(str(error))
            return False
        self._dirty = False
        return True

    def dispose(self):
        self._validate_timer.stop()
        self.save_now()
