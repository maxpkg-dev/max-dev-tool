"""Remember how far the tool's start got, so a start that took 3ds Max down is noticed the next time.

Users whose Max crashes at start can usually send only MaxPkg's log, which mirrors the MAXScript Listener. The guard
writes the current start step to logs/start-<host>.json before every step, and "ready" once the window works. When the
next start finds a step that never finished, Max died during it: that start runs in safe mode (optional native extras
off, see qt_compat.SAFE) and prints the step and the end of the crash log to the Listener, where MaxPkg's log shows it.

A crash whose faulthandler dump says "Garbage-collecting" died inside Python's garbage collector (3ds Max 2024,
PySide2 5.15.1 on Python 3.10): the next starts also hold the collector while the tool runs (controller.hold_gc).
Safe mode and the collector hold stay on for this tool version; a new version tries the normal start again.
"""

import io
import json
import os
import time

DONE = ("ready", "failed", "stopped")  # A start that got here did not take Max down.
SESSION_MARK = "=== session start ==="  # Written by logs.enable_crash_log at every start.
GC_MARK = "Garbage-collecting"  # faulthandler's frame line when Max died inside a garbage collection.


class StartGuard(object):
    def __init__(self, folder, host, version):
        name = "{}-{}".format("{}", host) if host else "{}"
        self.path = os.path.join(folder, "logs", name.format("start") + ".json")
        self.crash_path = os.path.join(folder, "logs", name.format("crash") + ".log")
        self.probe_path = os.path.join(folder, "logs", name.format("gc-probe") + ".txt")  # gcprobe.run()
        self.version = version
        self.previous = self._read()
        step = self.previous.get("step")
        self.crashed_at = step if step and step not in DONE else None
        kept = self.previous.get("version") == version  # Modes stay for the version they were found with.
        self.crash_tail = self._crash_tail() if self.crashed_at else ""
        self.gc_crash = GC_MARK in self.crash_tail
        self.gc_hold = self.gc_crash or bool(self.previous.get("gc_hold") and kept)
        self.safe = bool(self.crashed_at) or bool(self.previous.get("safe") and kept)
        self.details = {}  # Facts about this start (versions, OpenGL, ...) kept in the file for the next report.

    def _read(self):
        try:
            with io.open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _crash_tail(self, lines=30):
        """What faulthandler wrote for the session that died: the text after the last session mark."""
        try:
            with io.open(self.crash_path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            return ""
        last = text.rsplit(SESSION_MARK, 1)[-1].strip()
        return "\n".join(last.splitlines()[-lines:])

    def note(self, key, value):
        """Keep a fact about this start; it is written with the next step."""
        self.details[key] = value

    def step(self, name):
        """Record that the start is now at `name` (written before the step runs). Never raises."""
        data = {"version": self.version, "step": name, "safe": self.safe, "gc_hold": self.gc_hold,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "details": self.details}
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temporary = self.path + ".tmp"
            with io.open(temporary, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(data))
            os.replace(temporary, self.path)
        except OSError:
            pass

    def report(self, tool_name="The tool"):
        """Lines for the Listener (and so MaxPkg's log) about a start that took Max down; empty when none did."""
        if not self.crashed_at:
            return ""
        prefix = tool_name + ": "
        lines = [prefix + "the last start in this 3ds Max ended unexpectedly at step '{}' (version {}{}). This start "
                 "is in safe mode{}.".format(self.crashed_at, self.previous.get("version", "?"),
                                             ", inside Python's garbage collector" if self.gc_crash else "",
                                             " with the garbage collector held" if self.gc_hold else ""),
                 prefix + "please send this text to the developer."]
        details = self.previous.get("details") or {}
        if details:
            lines.append(prefix + "that start: " + "; ".join("{}={}".format(k, details[k]) for k in sorted(details)))
        try:
            with io.open(self.probe_path, encoding="utf-8", errors="replace") as handle:
                probe = handle.read().split("\x00", 1)[0].strip()
        except OSError:
            probe = ""
        if probe:
            lines.append(prefix + "garbage collector probe: " + probe)
        if self.crash_tail:
            lines.append(prefix + "crash log of that start:")
            lines.extend("  " + line for line in self.crash_tail.splitlines())
        return "\n".join(lines)
