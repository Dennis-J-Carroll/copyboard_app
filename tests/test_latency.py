"""Tests for the content-free latency recorder and its GUI wiring."""

from __future__ import annotations

import json
import os
import queue
import stat
import time
from types import SimpleNamespace

from copyboard_extension import copyboard_gui, core, paste_helper
from copyboard_extension.clipboard_watcher import (
    ClipboardBackend,
    ClipboardChange,
    ClipboardWatcher,
)
from copyboard_extension.copyboard_gui import CopyboardGUI, FIRE_PASTE_DELAY_MS
from copyboard_extension.latency import LatencyRecorder


def _headless_gui(recorder):
    gui = object.__new__(CopyboardGUI)
    gui._last_clipboard = ""
    gui.auto_capture_var = SimpleNamespace(get=lambda: True)
    gui._watcher = SimpleNamespace(backend_name="fake")
    gui._latency = recorder
    gui._ui_actions = queue.SimpleQueue()
    gui._closing = False
    gui._widget = None
    gui._hotkey_report = {}
    gui.refresh = lambda **_kwargs: None
    gui._set_status = lambda *_args, **_kwargs: None
    return gui


class ManualClipboardBackend(ClipboardBackend):
    """A started/stopped-aware backend the test can fire on demand."""

    name = "manual"
    event_driven = True

    def __init__(self, on_change, read_clipboard):
        super().__init__(on_change, read_clipboard)
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1

    def fire(self):
        if self.started and not self.stopped:
            self._emit_current()


def test_span_records_monotonic_duration():
    ticks = iter([1_000_000, 4_000_000])
    recorder = LatencyRecorder(clock=lambda: next(ticks))

    with recorder.span("capture"):
        pass

    sample = recorder.recent()[-1]
    assert sample["name"] == "capture"
    assert sample["ms"] == 3.0


def test_snapshot_reports_per_stage_percentiles():
    recorder = LatencyRecorder()
    recorder.record("capture", 1_000_000, 2_000_000)
    recorder.record("capture", 1_000_000, 3_000_000)
    recorder.record("capture", 1_000_000, 4_000_000)
    recorder.record("fire", 1_000_000, 2_000_000)

    snapshot = recorder.snapshot()
    assert snapshot["samples"] == 4
    assert snapshot["stages"]["capture"]["count"] == 3
    assert snapshot["stages"]["capture"]["min_ms"] == 1.0
    assert snapshot["stages"]["capture"]["max_ms"] == 3.0
    assert snapshot["stages"]["capture"]["last_ms"] == 3.0
    assert snapshot["stages"]["fire"]["count"] == 1


def test_ring_buffer_is_bounded_and_clearable():
    recorder = LatencyRecorder(max_samples=3)
    for value in range(5):
        recorder.record("capture", 1, 1_000_000 + value)
    assert len(recorder.recent(limit=99)) == 3
    assert recorder.snapshot()["samples"] == 3
    recorder.clear()
    assert recorder.recent() == []


def test_log_is_content_free_and_owner_only(tmp_path):
    secret = "TOP_SECRET_CLIPBOARD_TEXT"
    log_path = tmp_path / "latency.jsonl"
    recorder = LatencyRecorder(str(log_path))
    recorder.record("capture", 1, 2, chars=len(secret), backend="test")

    raw = log_path.read_text(encoding="utf-8")
    assert secret not in raw
    payload = json.loads(raw.strip())
    assert payload["fields"] == {"chars": len(secret), "backend": "test"}
    if os.name == "posix":
        assert stat.S_IMODE(log_path.stat().st_mode) & 0o077 == 0


def test_disabled_recorder_is_a_no_op(tmp_path):
    recorder = LatencyRecorder(str(tmp_path / "latency.jsonl"), enabled=False)
    assert recorder.mark("capture") == 0
    assert recorder.record("capture", 1, 2) is None
    assert recorder.event("skip") is None
    assert recorder.recent() == []
    assert not (tmp_path / "latency.jsonl").exists()


def test_gui_observe_records_backend_and_observed_timestamp(isolated_board):
    core._reset_app_clipboard_writes()
    gui = _headless_gui(LatencyRecorder())

    observed_at = time.perf_counter_ns()
    assert gui._observe_clipboard(
        "external text", observed_at_ns=observed_at, backend="linux-x11"
    )
    sample = gui._latency.recent()[-1]
    assert sample["name"] == "capture_to_chamber"
    assert sample["fields"]["backend"] == "linux-x11"
    assert sample["fields"]["chars"] == len("external text")
    assert sample["ms"] >= 0


def test_gui_observe_keeps_app_writes_out_of_the_board(isolated_board):
    core._reset_app_clipboard_writes()
    gui = _headless_gui(LatencyRecorder())

    core.set_clipboard_text("copyboard's own round")
    assert gui._observe_clipboard("copyboard's own round") is False
    assert core.get_board() == []
    assert gui._latency.snapshot()["stages"] == {}


def test_core_shortcut_fire_records_both_stages(isolated_board):
    recorder = LatencyRecorder()
    core.set_latency_recorder(recorder)
    try:
        core.copy_to_board("shortcut payload")
        assert core.paste_from_board(0, auto_paste=True) is True
    finally:
        core.set_latency_recorder(None)

    stages = recorder.snapshot()["stages"]
    assert "fire_clipboard_written" in stages
    assert "fire_to_paste_dispatch" in stages
    assert stages["fire_to_paste_dispatch"]["count"] == 1


def test_target_poll_does_not_read_the_clipboard(monkeypatch):
    gui = _headless_gui(LatencyRecorder())
    gui._copyboard_unfocused = lambda: False
    gui.root = SimpleNamespace(after=lambda _delay, _callback: "job")
    clipboard_reads = []
    monkeypatch.setattr(
        "copyboard_extension.copyboard_gui.pyperclip.paste",
        lambda: clipboard_reads.append(True) or "text",
    )

    gui._poll_target()
    assert clipboard_reads == []
    assert gui._poll_job == "job"


def test_watcher_change_goes_through_the_tk_action_queue(isolated_board):
    gui = _headless_gui(LatencyRecorder())
    gui._on_clipboard_change(ClipboardChange("queued text", 123_456, "fake"))

    action = gui._ui_actions.get_nowait()
    assert action == ("clipboard", "queued text", 123_456, "fake")
    gui._handle_ui_action(action)
    sample = gui._latency.recent()[-1]
    assert sample["name"] == "capture_to_chamber"
    assert sample["fields"]["backend"] == "fake"


def test_gui_watcher_start_stop_and_queue_skip_copyboard_writes(
    isolated_board, monkeypatch
):
    """Exercise the GUI's watcher lifecycle and Tk queue without a display.

    ``object.__new__`` builds a real ``CopyboardGUI`` instance while bypassing
    its Tk-only ``__init__``, the same headless seam the other GUI wiring tests
    use.  The watcher itself is real; only its platform backend is manual.
    """
    core._reset_app_clipboard_writes()
    clipboard = {"text": ""}
    gui = _headless_gui(LatencyRecorder())
    gui.root = SimpleNamespace(after=lambda _delay, _callback: "job")
    created = {}

    def make_watcher(on_change, initial_text=None):
        backend = ManualClipboardBackend(on_change, lambda: clipboard["text"])
        created["backend"] = backend
        created["watcher"] = ClipboardWatcher(on_change, backend=backend)
        return created["watcher"]

    monkeypatch.setattr(copyboard_gui, "ClipboardWatcher", make_watcher)
    gui._start_clipboard_watcher()

    backend = created["backend"]
    assert gui._watcher is created["watcher"]
    assert backend.started == 1
    assert gui._latency.recent()[-1]["name"] == "watcher_started"
    assert gui._latency.recent()[-1]["fields"]["backend"] == "manual"

    # An external copy travels backend -> queue -> chamber 01.
    clipboard["text"] = "external copy"
    backend.fire()
    assert gui._ui_actions.qsize() == 1
    gui._poll_ui_actions()
    assert core.get_board() == ["external copy"]

    # A CopyBoard-originated write reaches the queue but is not captured.
    core.set_clipboard_text("CopyBoard's own round")
    backend.fire()
    assert gui._ui_actions.qsize() == 1
    gui._poll_ui_actions()
    assert core.get_board() == ["external copy"]

    gui._stop_clipboard_watcher()
    assert gui._watcher is None
    assert backend.stopped == 1

    # A stopped backend can no longer enqueue anything.
    backend.fire()
    assert gui._ui_actions.empty()


def test_fire_dispatch_records_full_span(monkeypatch):
    gui = _headless_gui(LatencyRecorder())
    pasted = []

    class FakeRoot:
        def __init__(self):
            self.calls = []

        def after(self, delay, callback):
            self.calls.append((delay, callback))
            return "job"

        def deiconify(self):
            pass

        def lift(self):
            pass

    gui.root = FakeRoot()
    monkeypatch.setattr(paste_helper, "restore_active_window", lambda _target: True)
    monkeypatch.setattr(
        paste_helper,
        "paste_current_clipboard",
        lambda: pasted.append(True) or True,
    )
    started = time.perf_counter_ns()

    gui._deliver_fire(0, object(), from_widget=False, trace_start_ns=started)
    callback = next(
        callback
        for delay, callback in gui.root.calls
        if delay == FIRE_PASTE_DELAY_MS
    )
    callback()

    assert pasted == [True]
    stages = gui._latency.snapshot()["stages"]
    assert "fire_focus_restored" in stages
    assert "fire_to_paste_dispatch" in stages
