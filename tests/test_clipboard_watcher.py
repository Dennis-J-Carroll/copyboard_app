"""Tests for the clipboard watcher abstraction, fallback, and selection."""

from __future__ import annotations

import time

import pytest

from copyboard_extension.clipboard_watcher import (
    FALLBACK_INTERVAL_S,
    BackendUnavailable,
    ClipboardBackend,
    ClipboardWatcher,
    PollingBackend,
    detect_backend_kind,
)
from copyboard_extension.native_clipboard import (
    ClipboardSnapshot,
    NativeReadUnavailable,
)


class FakeBackend:
    name = "fake"
    event_driven = True

    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class BrokenBackend:
    name = "broken"
    event_driven = True

    def start(self):
        raise BackendUnavailable("no native watcher here")

    def stop(self):
        pass


class ManualBackend(ClipboardBackend):
    name = "manual"
    event_driven = True

    def start(self):
        pass

    def stop(self):
        pass

    def fire(self):
        self._emit_current()


def test_polling_backend_primes_then_emits_only_changes():
    value = {"text": "first"}
    changes = []
    backend = PollingBackend(changes.append, lambda: value["text"])

    assert backend.poll_once() is None
    value["text"] = "second"
    change = backend.poll_once()
    assert change is not None
    assert change.text == "second"
    assert change.backend == "polling"
    assert backend.poll_once() is None
    assert changes == []


def test_polling_backend_can_use_the_gui_startup_baseline():
    backend = PollingBackend(
        lambda _change: None, lambda: "changed after startup", initial_text="startup value"
    )
    change = backend.poll_once()
    assert change is not None and change.text == "changed after startup"


def test_polling_backend_survives_a_clipboard_read_error():
    values = iter([RuntimeError("clipboard busy"), "baseline", "changed"])

    def read():
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value

    backend = PollingBackend(lambda _change: None, read)
    assert backend.poll_once() is None  # failed baseline
    assert backend.poll_once() is None  # recovered and primed
    change = backend.poll_once()
    assert change is not None and change.text == "changed"


def test_change_timestamp_is_taken_before_the_read():
    changes = []
    backend = ManualBackend(changes.append, lambda: "text")
    before = time.perf_counter_ns()
    backend.fire()
    after = time.perf_counter_ns()

    assert len(changes) == 1
    assert before <= changes[0].observed_at_ns <= after
    assert changes[0].backend == "manual"


def test_detects_wayland_before_x11():
    kind = detect_backend_kind(
        system="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
        which=lambda name: "/usr/bin/wl-paste" if name == "wl-paste" else None,
    )
    assert kind == "wayland"


def test_detects_x11_when_wl_paste_is_missing():
    kind = detect_backend_kind(
        system="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
        which=lambda _name: None,
    )
    assert kind == "x11"


def test_unknown_platform_uses_polling():
    assert detect_backend_kind(system="FreeBSD", env={}, which=lambda _name: None) == "polling"
    assert detect_backend_kind(system="Windows", env={}, which=lambda _name: None) == "windows"
    assert detect_backend_kind(system="Darwin", env={}, which=lambda _name: None) == "macos"


def test_watcher_starts_and_stops_its_backend():
    backend = FakeBackend()
    watcher = ClipboardWatcher(
        lambda _change: None, backend=backend, read_clipboard=lambda: ""
    )
    watcher.start()
    assert backend.started is True
    watcher.stop()
    assert backend.stopped is True


def test_watcher_falls_back_when_start_fails():
    fallback = FakeBackend()
    fallback.name = "fallback"
    watcher = ClipboardWatcher(
        lambda _change: None,
        backend=BrokenBackend(),
        read_clipboard=lambda: "",
        fallback_factory=lambda: fallback,
    )

    watcher.start()
    assert fallback.started is True
    assert watcher.backend_name == "fallback"
    assert "no native watcher here" in watcher.fallback_reason
    watcher.stop()
    assert fallback.stopped is True


def test_watcher_falls_back_after_a_runtime_failure():
    fallback = FakeBackend()
    fallback.name = "fallback"
    primary = FakeBackend()
    watcher = ClipboardWatcher(
        lambda _change: None,
        backend=primary,
        read_clipboard=lambda: "",
        fallback_factory=lambda: fallback,
    )
    watcher.start()

    watcher._handle_failure("native event source died")
    assert fallback.started is True
    assert watcher.backend_name == "fallback"
    assert watcher.fallback_reason == "native event source died"
    watcher.stop()
    assert fallback.stopped is True


def test_watcher_uses_explicit_polling_backend():
    changes = []
    watcher = ClipboardWatcher(
        changes.append, backend_kind="polling", read_clipboard=lambda: "stable"
    )
    watcher.start()
    assert watcher.backend_name == "polling"
    assert watcher.event_driven is False
    watcher.stop()


def test_polling_fallback_runs_every_250ms():
    assert FALLBACK_INTERVAL_S == 0.25
    backend = PollingBackend(lambda _change: None, lambda: "")
    assert backend.interval == 0.25


def test_watcher_uses_an_in_process_reader_for_native_backends(monkeypatch):
    native = lambda: "native text"
    native.name = "fake-native"
    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.create_native_reader",
        lambda kind: native if kind == "x11" else None,
    )

    watcher = ClipboardWatcher(lambda _change: None, backend_kind="x11")

    assert watcher.reader_name == "fake-native"
    assert watcher._read_clipboard() == "native text"


def test_watcher_keeps_an_explicit_reader():
    reader = lambda: "explicit"

    watcher = ClipboardWatcher(
        lambda _change: None, backend_kind="x11", read_clipboard=reader
    )

    assert watcher.reader_name == "custom"
    assert watcher._read_clipboard is reader


def test_polling_uses_the_native_reader_when_available(monkeypatch):
    native = lambda: "text"
    native.name = "fake-native"
    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.create_native_reader",
        lambda kind: native if kind != "polling" else None,
    )
    monkeypatch.setenv("DISPLAY", ":99")

    watcher = ClipboardWatcher(lambda _change: None, backend_kind="polling")

    assert watcher.reader_name == "fake-native"
    assert watcher._read_clipboard() == "text"


def test_watcher_uses_pyperclip_when_there_is_no_native_reader(monkeypatch):
    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.create_native_reader",
        lambda _kind: None,
    )

    watcher = ClipboardWatcher(lambda _change: None, backend_kind="polling")

    assert watcher.reader_name == "pyperclip"


def test_native_read_failure_falls_back_to_pyperclip(monkeypatch):
    def broken():
        raise NativeReadUnavailable("the display went away")

    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.create_native_reader",
        lambda _kind: broken,
    )
    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.pyperclip.paste",
        lambda: "fallback text",
    )

    watcher = ClipboardWatcher(lambda _change: None, backend_kind="x11")

    assert watcher._read_clipboard() == "fallback text"
    assert watcher._read_clipboard.read_snapshot().sensitive is False


def test_native_snapshot_survives_the_fallback_wrapper(monkeypatch):
    class SensitiveNative:
        def __call__(self):
            return "password"

        def read_snapshot(self):
            return ClipboardSnapshot(text="password", sensitive=True)

    monkeypatch.setattr(
        "copyboard_extension.clipboard_watcher.create_native_reader",
        lambda _kind: SensitiveNative(),
    )
    watcher = ClipboardWatcher(lambda _change: None, backend_kind="x11")

    snapshot = watcher._read_clipboard.read_snapshot()

    assert snapshot.text == "password"
    assert snapshot.sensitive is True


def test_backend_change_carries_sensitive_snapshot():
    class SensitiveReader:
        def read_snapshot(self):
            return ClipboardSnapshot(text="password", sensitive=True)

    changes = []
    backend = ManualBackend(changes.append, SensitiveReader())
    backend.fire()

    assert changes[0].text == "password"
    assert changes[0].sensitive is True


def test_polling_backend_carries_sensitive_snapshot():
    values = iter(
        [ClipboardSnapshot("baseline"), ClipboardSnapshot("secret", True)]
    )
    backend = PollingBackend(lambda _change: None, lambda: next(values))

    assert backend.poll_once() is None
    change = backend.poll_once()

    assert change is not None
    assert change.text == "secret"
    assert change.sensitive is True


@pytest.mark.parametrize("kind", ["wayland", "x11", "windows", "macos"])
def test_native_backend_kinds_are_known(kind):
    # Construction is side-effect free; start() is what probes the platform.
    from copyboard_extension.clipboard_watcher import create_backend

    backend = create_backend(kind, lambda _change: None, lambda: "")
    assert backend.name in {
        "linux-wayland",
        "linux-x11",
        "windows-listener",
        "macos-changecount",
    }
