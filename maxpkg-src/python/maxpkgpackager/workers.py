"""Background jobs with cooperative cancellation and lifecycle generations.

Pure code. Jobs receive a `threading.Event` that is set when they should stop, and return plain data.
Completion callbacks are handed to `post`, which the controller binds to a Qt queued signal so they run
on the main thread. Results from a stopped runner are dropped.
"""

import concurrent.futures
import itertools
import threading

from . import logs

_log = logs.get("workers")


class JobRunner(object):
    def __init__(self, post, max_workers=4):
        self._post = post
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers,
                                                               thread_name_prefix="maxpkgpackager")
        self._jobs = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._stopping = False
        self.on_submit = None  # Main-thread hook, e.g. to start the GIL pump inside 3ds Max.

    def submit(self, work, on_done=None, on_error=None, name="job"):
        """Run work(cancel_event) in a thread; returns a job id usable with cancel()."""
        if self._stopping:
            raise RuntimeError("Runner is stopping; no new work accepted.")
        job_id = next(self._ids)
        cancel = threading.Event()

        def run():
            try:
                result = work(cancel)
            except Exception as error:  # Reported on the main thread, never raised in the worker.
                if not cancel.is_set():
                    _log.exception("Job %s failed", name)
                self._finish(job_id, cancel, on_error, error)
                return
            self._finish(job_id, cancel, on_done, result)

        with self._lock:
            self._jobs[job_id] = (cancel, self._executor.submit(run))
        if self.on_submit is not None:
            self.on_submit()
        return job_id

    def _finish(self, job_id, cancel, callback, value):
        with self._lock:
            self._jobs.pop(job_id, None)
        if callback is None or cancel.is_set() or self._stopping:
            return
        self._post(lambda: None if (cancel.is_set() or self._stopping) else callback(value))

    def post(self, callback):
        """Run callback() on the main thread soon; dropped if the runner is stopping."""
        if not self._stopping:
            self._post(lambda: None if self._stopping else callback())

    def cancel(self, job_id):
        with self._lock:
            entry = self._jobs.get(job_id)
        if entry is not None:
            entry[0].set()

    def request_stop(self):
        self._stopping = True
        with self._lock:
            entries = list(self._jobs.values())
        for cancel, _future in entries:
            cancel.set()
        # Python 3.7 has no cancel_futures; queued jobs see the cancel event and return at once.
        self._executor.shutdown(wait=False)

    def is_idle(self):
        with self._lock:
            return all(future.done() for _cancel, future in self._jobs.values())

    def active_count(self):
        with self._lock:
            return sum(1 for _cancel, future in self._jobs.values() if not future.done())
