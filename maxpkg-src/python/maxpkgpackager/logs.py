"""File logging: one file per day, like MaxPkg Runtime Manager. The log is never shown unless the user opens it
from the Logs button.

Every record is appended to logs/maxpkgpackager-YYYY-MM-DD.log and the file is closed again at once, so no file
stays open: Clear Logs can delete every day, and two 3ds Max versions can write the same day's file. Files older than
60 days are removed when the packager starts. The handler is owned by the session and removed on shutdown so
relaunches do not stack handlers.
"""

import datetime
import logging
import os
import re
import threading

LOGGER_NAME = "maxpkgpackager"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"  # No milliseconds.
DAY_FILE = re.compile(r"^maxpkgpackager-(\d{4})-(\d\d)-(\d\d)\.log$")
KEEP_DAYS = 60
READ_LIMIT = 2 * 1024 * 1024  # A day's log larger than this is shown from its last 2 MB
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Host tag such as "max2027": names the crash log of each 3ds Max version and appears in the session line.
_host = ""


def set_host(tag):
    global _host
    _host = "".join(c for c in str(tag) if c.isalnum())


def logs_folder(folder):
    return os.path.join(folder, "logs")


def day_path(folder, date=None):
    date = date or datetime.date.today()
    return os.path.join(logs_folder(folder), "maxpkgpackager-{:%Y-%m-%d}.log".format(date))


def log_path(folder):
    """Today's log file."""
    return day_path(folder)


class DailyFileHandler(logging.Handler):
    """Appends each record to the day's file and closes it again (nothing stays open)."""

    def __init__(self, folder):
        logging.Handler.__init__(self)
        self.folder = folder
        self._write_lock = threading.Lock()

    def emit(self, record):
        try:
            line = self.format(record) + "\n"
            path = day_path(self.folder)
            with self._write_lock:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8") as stream:
                    stream.write(line)
        except Exception:
            self.handleError(record)


def attach(folder):
    """Attach the daily file handler; returns it so the owner can detach exactly this handler."""
    os.makedirs(logs_folder(folder), exist_ok=True)
    prune(folder)
    handler = DailyFileHandler(folder)
    handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Keep MaxPkg Packager output out of Max's listener and other handlers.
    logger.addHandler(handler)
    return handler


def enable_crash_log(folder):
    """Dump Python stacks of all threads to logs/crash[-host].log if Max dies from a native fault.

    Returns a release function. Does nothing if another component already enabled faulthandler.
    """
    import faulthandler
    if faulthandler.is_enabled():
        return lambda: None
    path = os.path.join(logs_folder(folder), "crash-{}.log".format(_host) if _host else "crash.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stream = open(path, "a", encoding="utf-8")
    stream.write("\n=== session start ===\n")
    stream.flush()
    faulthandler.enable(file=stream, all_threads=True)

    def release():
        faulthandler.disable()
        stream.close()

    return release


def detach(handler):
    logger = logging.getLogger(LOGGER_NAME)
    if handler in logger.handlers:
        logger.removeHandler(handler)
    handler.close()


def get(name=None):
    return logging.getLogger(LOGGER_NAME if not name else LOGGER_NAME + "." + name)


# Days ----------------------------------------------------------------------------------------------------------
class LogDay(object):
    __slots__ = ("date", "file_path", "size")

    def __init__(self, date, file_path, size):
        self.date, self.file_path, self.size = date, file_path, size


def log_days(folder):
    """[LogDay] of the daily log files, newest first."""
    days = []
    try:
        names = os.listdir(logs_folder(folder))
    except OSError:
        return days
    for name in names:
        match = DAY_FILE.match(name)
        if not match:
            continue
        try:
            date = datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            path = os.path.join(logs_folder(folder), name)
            days.append(LogDay(date, path, os.path.getsize(path)))
        except (ValueError, OSError):
            continue
    days.sort(key=lambda day: day.date, reverse=True)
    return days


def day_label(date, today=None):
    """'Today', 'Yesterday' or 'Thu 29 Oct 2026' (English, whatever the Windows language)."""
    today = today or datetime.date.today()
    if date == today:
        return "Today"
    if date == today - datetime.timedelta(days=1):
        return "Yesterday"
    return "{} {} {} {}".format(WEEKDAYS[date.weekday()], date.day, MONTHS[date.month - 1], date.year)


def prune(folder, keep_days=KEEP_DAYS):
    """Remove day files older than `keep_days` (they are never shown again)."""
    limit = datetime.date.today() - datetime.timedelta(days=keep_days)
    for day in log_days(folder):
        if day.date < limit:
            try:
                os.remove(day.file_path)
            except OSError:
                pass


def log_files(folder):
    """Every log file of the packager: the day files and the files of version 2.0 before daily logs."""
    try:
        names = os.listdir(logs_folder(folder))
    except OSError:
        return []
    return sorted(os.path.join(logs_folder(folder), name) for name in names
                  if name.startswith("maxpkgpackager") and ".log" in name)


def clear_logs(folder, handler=None):
    """Delete the log files of every day. Nothing is kept open, so they can all go; a file that is being written by
    another 3ds Max at this moment is skipped. Returns (removed, kept, freed bytes). `handler` is unused (API kept)."""
    removed, kept, freed = 0, 0, 0
    for path in log_files(folder):
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        try:
            os.remove(path)
            removed, freed = removed + 1, freed + size
        except OSError:
            kept += 1
    return removed, kept, freed


def read_text(file_path, limit=READ_LIMIT):
    """A day's log text; a file over `limit` is read from its end (the cut first line is dropped)."""
    try:
        with open(file_path, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            data = stream.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")  # Windows line ends
    return text.split("\n", 1)[-1] if size > limit else text


def tail(folder, max_bytes=256 * 1024):
    """Last part of today's log as text (Copy Diagnostics)."""
    return read_text(log_path(folder), max_bytes)


def size_text(size):
    if size < 1024:
        return "{} B".format(size)
    if size < 1024 * 1024:
        return "{:.0f} KB".format(size / 1024.0)
    return "{:.1f} MB".format(size / (1024.0 * 1024.0))


def summary_text(records):
    """'35 records · 1 warning · 2 errors' (warnings and errors only when there are any)."""
    warnings = sum(1 for r in records if r["level"] == "WARNING")
    errors = sum(1 for r in records if r["level"] in ("ERROR", "CRITICAL"))

    def count(number, noun):
        return "{:,} {}{}".format(number, noun, "" if number == 1 else "s")
    parts = [count(len(records), "record")]
    if warnings:
        parts.append(count(warnings, "warning"))
    if errors:
        parts.append(count(errors, "error"))
    return " · ".join(parts)


def record_text(record):
    """A record as it stands in the file (for Copy and Export)."""
    head = "{} {} {:<7} {}: {}".format(record["date"], record["time"], record["level"], record["source"],
                                       record["message"])
    return "\n".join([head] + record["extra"])


# Log viewer model (pure; ui/dialogs.LogDialog renders it with theme colours) ---------------------------
_RECORD = re.compile(r"^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)(?:,\d{3})? "
                     r"(DEBUG|INFO|WARNING|ERROR|CRITICAL) +(\S+?): ?(.*)$")
LEVEL_ROLES = {"DEBUG": "debug", "INFO": "info", "WARNING": "warning", "ERROR": "error", "CRITICAL": "error"}
SUCCESS_PREFIXES = ("Started",)
SESSION_PREFIX = "Starting MaxPkgPackager"
SOURCE_WIDTH = 15
FILTERS = {"all": ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), "warnings": ("WARNING", "ERROR", "CRITICAL"),
           "errors": ("ERROR", "CRITICAL")}


def parse_records(text):
    """Log text -> [dict(date, time, level, source, message, extra=[continuation lines])].

    Accepts lines with or without milliseconds; lines without a header (tracebacks) belong to the
    record above them. Text before the first header is dropped (a partial record from tail()).
    """
    records = []
    for line in text.splitlines():
        match = _RECORD.match(line)
        if match:
            date, time, level, source, message = match.groups()
            if source.startswith(LOGGER_NAME + "."):
                source = source[len(LOGGER_NAME) + 1:]
            elif source == LOGGER_NAME:
                source = "core"
            records.append(dict(date=date, time=time, level=level, source=source, message=message, extra=[]))
        elif records and line.strip():
            records[-1]["extra"].append(line.rstrip())
    return records


def counts(records):
    warnings = sum(1 for r in records if r["level"] == "WARNING")
    errors = sum(1 for r in records if r["level"] in ("ERROR", "CRITICAL"))
    return len(records), warnings, errors


def view_rows(records, level_filter="all", query=""):
    """Rows of (text, role) runs for the viewer, after filtering by level and a case-insensitive query.

    Roles: day, session, time, level-<debug|info|warning|error>, source, text, message-<warning|error|
    success>, extra-<warning|error|info>, gap.
    """
    levels = FILTERS.get(level_filter, FILTERS["all"])
    needle = query.strip().lower()
    rows = []
    day = None
    indent = " " * (8 + 2 + 9 + 2 + SOURCE_WIDTH + 2)
    for record in records:
        if record["level"] not in levels:
            continue
        haystack = " ".join([record["source"], record["message"]] + record["extra"]).lower()
        if needle and needle not in haystack:
            continue
        if record["date"] != day:
            day = record["date"]
            rows.append([(" {} ".format(day), "day")])
        if record["message"].startswith(SESSION_PREFIX):
            rows.append([("", "gap")])
            rows.append([("▸ Session started {}".format(record["time"]), "session"),
                         ("  " + record["message"][len(SESSION_PREFIX):].strip(), "source")])
            continue
        role = LEVEL_ROLES[record["level"]]
        if role in ("warning", "error"):
            message_role = "message-" + role
        elif record["message"].startswith(SUCCESS_PREFIXES):
            message_role = "message-success"
        else:
            message_role = "text"
        source = record["source"]
        if len(source) > SOURCE_WIDTH:
            source = source[:SOURCE_WIDTH - 1] + "…"
        rows.append([(record["time"], "time"), ("  ", "text"), (" {:<7} ".format(record["level"]), "level-" + role),
                     ("  ", "text"), (source.ljust(SOURCE_WIDTH), "source"), ("  ", "text"),
                     (record["message"], message_role)])
        extra_role = "extra-" + (role if role in ("warning", "error") else "info")
        for line in record["extra"]:
            rows.append([(indent + line, extra_role)])
    return rows
