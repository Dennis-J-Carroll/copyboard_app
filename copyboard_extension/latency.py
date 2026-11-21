"""Content-free latency tracing for CopyBoard's capture and fire paths.

The recorder is deliberately small: it keeps a bounded in-memory ring of
samples, can append newline-delimited JSON to a private log, and never accepts
clipboard text.  Fields are diagnostic metadata such as the backend name, the
chamber index, or the character count.

All durations are measured with ``time.perf_counter_ns``.  Wall-clock time is
recorded only so a sample can be correlated with a user report.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, Iterator, List, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_SAMPLES = 512


def _owner_only(path: str) -> None:
    """Keep diagnostic output readable only by its owner (POSIX)."""
    if os.name != "posix":
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class LatencyRecorder:
    """Thread-safe recorder for a small number of named latency stages."""

    def __init__(
        self,
        log_path: Optional[str] = None,
        *,
        max_samples: int = DEFAULT_MAX_SAMPLES,
        enabled: bool = True,
        clock=time.perf_counter_ns,
    ) -> None:
        self._log_path = log_path
        self._max_samples = max(1, int(max_samples))
        self._enabled = bool(enabled)
        self._clock = clock
        self._samples: Deque[Dict[str, Any]] = deque(maxlen=self._max_samples)
        self._lock = threading.Lock()
        self._sequence = 0
        self._log_ready = False
        if self._log_path and self._enabled:
            self._prepare_log()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def log_path(self) -> Optional[str]:
        return self._log_path

    def mark(self, name: str = "mark", **_fields: Any) -> int:
        """Return a monotonic timestamp for a span start.

        ``mark`` does not create a sample; use :meth:`record` with the returned
        value, or :meth:`span`, when the stage is complete.
        """
        return self._clock() if self._enabled else 0

    def record(
        self,
        name: str,
        start_ns: Optional[int],
        end_ns: Optional[int] = None,
        **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        """Record one completed stage, in milliseconds."""
        if not self._enabled:
            return None
        if start_ns is None or start_ns <= 0:
            start_ns = self._clock()
        if end_ns is None:
            end_ns = self._clock()
        duration_ns = max(0, int(end_ns) - int(start_ns))
        sample = {
            "name": str(name),
            "ms": round(duration_ns / 1_000_000.0, 3),
            "at": time.time(),
            "fields": dict(fields),
        }
        with self._lock:
            self._sequence += 1
            sample["seq"] = self._sequence
            self._samples.append(sample)
            if self._log_path:
                self._append_locked(sample)
        return sample

    def event(self, name: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Record a zero-duration event (a skip, a state change, an error)."""
        now = self._clock()
        return self.record(name, now, now, **fields)

    @contextmanager
    def span(self, name: str, **fields: Any) -> Iterator[Dict[str, Any]]:
        """Context manager that records a stage even when the body raises."""
        start = self.mark(name)
        try:
            yield {"start_ns": start}
        finally:
            self.record(name, start, **fields)

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the newest samples, oldest first, as copies."""
        with self._lock:
            samples = list(self._samples)
        if limit <= 0:
            return []
        return [dict(sample, fields=dict(sample.get("fields", {}))) for sample in samples[-limit:]]

    def snapshot(self) -> Dict[str, Any]:
        """Return count/min/mean/p50/p95/max per stage."""
        with self._lock:
            samples = list(self._samples)
        grouped: Dict[str, List[float]] = {}
        for sample in samples:
            grouped.setdefault(sample["name"], []).append(float(sample["ms"]))
        stages: Dict[str, Dict[str, float]] = {}
        for name, values in grouped.items():
            ordered = sorted(values)
            count = len(ordered)
            stages[name] = {
                "count": count,
                "min_ms": round(ordered[0], 3),
                "mean_ms": round(sum(ordered) / count, 3),
                "p50_ms": round(ordered[int(count * 0.50)], 3),
                "p95_ms": round(ordered[min(count - 1, int(count * 0.95))], 3),
                "max_ms": round(ordered[-1], 3),
                "last_ms": round(values[-1], 3),
            }
        return {
            "samples": len(samples),
            "max_samples": self._max_samples,
            "stages": stages,
        }

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()
            self._sequence = 0

    def _prepare_log(self) -> None:
        path = self._log_path
        if not path:
            return
        directory = os.path.dirname(os.path.abspath(path))
        try:
            os.makedirs(directory, exist_ok=True)
            # Create with owner-only permissions before any content is written.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.close(fd)
            _owner_only(path)
            self._log_ready = True
        except OSError as exc:
            LOGGER.warning("Could not prepare latency log %s: %s", path, exc)
            self._log_ready = False

    def _append_locked(self, sample: Dict[str, Any]) -> None:
        if not self._log_ready or not self._log_path:
            return
        try:
            line = json.dumps(sample, ensure_ascii=False, default=str) + "\n"
            fd = os.open(
                self._log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
            )
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
        except OSError as exc:
            LOGGER.warning("Could not append latency sample: %s", exc)
            self._log_ready = False
