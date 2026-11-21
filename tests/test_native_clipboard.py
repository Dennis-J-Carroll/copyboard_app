"""Tests for the in-process clipboard readers on the native event path."""

from __future__ import annotations

import ctypes
import os
import platform

import pytest

from copyboard_extension import native_clipboard
from copyboard_extension.native_clipboard import (
    NativeReadUnavailable,
    X11ClipboardReader,
    create_native_reader,
    read_macos_text,
    read_windows_text,
)


class FakeX11Session:
    """Scripted stand-in for the ctypes X11 connection."""

    def __init__(self, targets=None, reads=None, events=None):
        self.incr = 900
        self._atoms = {
            b"CLIPBOARD": 100,
            b"COPYBOARD_SELECTION": 101,
            b"UTF8_STRING": 102,
            b"STRING": 103,
            b"INCR": 900,
        }
        self._targets = dict(targets or {})
        self._reads = list(reads or [])
        self._events = list(events or [])
        self.converted = []
        self.read_calls = []
        self.deleted = []
        self.closed = False
        self.destroyed = []
        self.window = None

    def intern(self, name):
        return self._atoms.setdefault(name, 500 + len(self._atoms))

    def create_window(self):
        self.window = 7
        return 7

    def destroy_window(self, window):
        self.destroyed.append(window)
        self.window = None

    def close(self):
        self.closed = True

    def convert(self, selection, target, property_atom, window):
        self.converted.append(target)
        self._events.insert(
            0,
            {
                "type": 31,
                "requestor": window,
                "selection": selection,
                "target": target,
                "property": self._targets.get(target, 0),
            },
        )

    def next_event(self, timeout):
        return self._events.pop(0) if self._events else None

    def read_property(
        self, window, atom, *, offset=0, length=65536, delete=False
    ):
        self.read_calls.append(
            {"offset": offset, "length": length, "delete": bool(delete)}
        )
        if not self._reads:
            return 0, 0, b"", 0
        return self._reads.pop(0)

    def delete_property(self, window, atom):
        self.deleted.append(atom)


def _reader(session, timeout=1.0):
    return X11ClipboardReader(session_factory=lambda: session, timeout=timeout)


def test_x11_reader_uses_convert_selection_for_utf8_text():
    session = FakeX11Session(
        targets={102: 555},
        reads=[(102, 8, b"", 5), (102, 8, b"hello", 0)],
    )

    assert _reader(session)() == "hello"
    assert session.converted == [102]
    assert session.deleted == [555]
    assert session.destroyed == [7]
    assert session.closed is True


def test_x11_reader_assembles_chunked_properties():
    session = FakeX11Session(
        targets={102: 555},
        reads=[
            (102, 8, b"", 6),
            (102, 8, b"abc", 3),
            (102, 8, b"def", 0),
        ],
    )

    assert _reader(session)() == "abcdef"
    assert [call["offset"] for call in session.read_calls] == [0, 0, 1]


def test_x11_reader_handles_an_incr_transfer():
    session = FakeX11Session(
        targets={102: 555},
        reads=[
            (900, 32, b"\x05\x00\x00\x00", 4),  # type probe: INCR
            (900, 32, b"\x05\x00\x00\x00", 0),  # acknowledge the INCR property
            (102, 8, b"he", 0),
            (102, 8, b"llo", 0),
            (102, 8, b"", 0),  # zero-length chunk ends the transfer
        ],
        events=[
            {"type": 28, "atom": 555, "state": 0},
            {"type": 28, "atom": 555, "state": 0},
            {"type": 28, "atom": 555, "state": 0},
        ],
    )

    assert _reader(session)() == "hello"
    assert session.read_calls[1]["delete"] is True
    assert session.deleted == []  # INCR chunks are consumed with delete=True


def test_x11_reader_falls_back_to_string_target():
    session = FakeX11Session(
        targets={102: 0, 103: 555},  # UTF8 refused, STRING accepted
        reads=[
            (103, 8, b"", 4),
            (103, 8, b"caf\xe9", 0),
        ],
    )

    assert _reader(session)() == "café"
    assert session.converted == [102, 103]


def test_x11_reader_decodes_wide_text_formats():
    utf16 = "wide".encode("utf-16-le")
    session = FakeX11Session(
        targets={102: 555},
        reads=[(102, 16, b"", len(utf16)), (102, 16, utf16, 0)],
    )
    assert _reader(session)() == "wide"


def test_x11_reader_times_out_an_incomplete_incr_transfer():
    session = FakeX11Session(
        targets={102: 555},
        reads=[(900, 32, b"\x05\x00\x00\x00", 4), (900, 32, b"", 0)],
    )

    with pytest.raises(NativeReadUnavailable):
        _reader(session, timeout=0.01)()


def test_x11_reader_rejects_an_oversized_transfer(monkeypatch):
    monkeypatch.setattr(native_clipboard, "MAX_CLIPBOARD_BYTES", 4)
    session = FakeX11Session(
        targets={102: 555},
        reads=[
            (900, 32, b"\x05\x00\x00\x00", 4),
            (900, 32, b"", 0),
            (102, 8, b"hello", 0),
        ],
        events=[{"type": 28, "atom": 555, "state": 0}],
    )

    with pytest.raises(NativeReadUnavailable):
        _reader(session)()


class FakeUser32:
    def __init__(self, opens, available=True, handle=123):
        self._opens = list(opens)
        self.available = available
        self.handle = handle
        self.closed = 0

    def OpenClipboard(self, _owner):
        return self._opens.pop(0) if self._opens else 0

    def IsClipboardFormatAvailable(self, _fmt):
        return int(self.available)

    def GetClipboardData(self, _fmt):
        return self.handle

    def CloseClipboard(self):
        self.closed += 1
        return 1


class FakeKernel32:
    def __init__(self, pointer=0):
        self.pointer = pointer
        self.unlocked = []

    def GlobalLock(self, _handle):
        return self.pointer

    def GlobalUnlock(self, handle):
        self.unlocked.append(handle)
        return 1


def _unicode_pointer(text):
    buffer = ctypes.create_unicode_buffer(text)
    return buffer, ctypes.cast(buffer, ctypes.c_void_p).value


def test_windows_reader_decodes_unicode_text_and_closes():
    buffer, pointer = _unicode_pointer("windows text")
    user32 = FakeUser32([1])
    kernel32 = FakeKernel32(pointer)

    assert read_windows_text(user32=user32, kernel32=kernel32) == "windows text"
    assert user32.closed == 1
    assert kernel32.unlocked == [123]
    assert buffer  # keep the source buffer alive while ctypes reads it


def test_windows_reader_retries_a_locked_clipboard(monkeypatch):
    monkeypatch.setattr(native_clipboard.time, "sleep", lambda _delay: None)
    _buffer, pointer = _unicode_pointer("after retry")
    user32 = FakeUser32([0, 0, 1])
    kernel32 = FakeKernel32(pointer)

    assert (
        read_windows_text(user32=user32, kernel32=kernel32, retry_timeout=1.0)
        == "after retry"
    )
    assert user32.closed == 1


def test_windows_reader_times_out_on_a_locked_clipboard():
    with pytest.raises(NativeReadUnavailable):
        read_windows_text(
            user32=FakeUser32([0]),
            kernel32=FakeKernel32(1),
            retry_timeout=0.0,
        )


def test_windows_reader_returns_empty_without_unicode_text():
    user32 = FakeUser32([1], available=False)
    assert read_windows_text(user32=user32, kernel32=FakeKernel32(1)) == ""
    assert user32.closed == 1


def test_windows_reader_returns_empty_when_the_handle_cannot_be_locked():
    user32 = FakeUser32([1])
    assert read_windows_text(user32=user32, kernel32=FakeKernel32(0)) == ""
    assert user32.closed == 1


@pytest.mark.skipif(os.name == "nt", reason="the native Windows path is available")
def test_windows_reader_requires_windows():
    with pytest.raises(NativeReadUnavailable):
        read_windows_text()


class FakePasteboard:
    def __init__(self, value):
        self.value = value
        self.requested = None

    def stringForType_(self, kind):
        self.requested = kind
        return self.value


def test_macos_reader_reads_utf8_plain_text():
    pasteboard = FakePasteboard("mac text")
    assert read_macos_text(pasteboard) == "mac text"
    assert pasteboard.requested == "public.utf8-plain-text"


def test_macos_reader_returns_empty_for_missing_text():
    assert read_macos_text(FakePasteboard(None)) == ""
    assert read_macos_text(FakePasteboard(123)) == ""


def test_macos_reader_reports_a_pasteboard_error():
    class Broken:
        def stringForType_(self, _kind):
            raise RuntimeError("pasteboard unavailable")

    with pytest.raises(NativeReadUnavailable):
        read_macos_text(Broken())


@pytest.mark.skipif(
    platform.system() == "Darwin", reason="the native macOS path is available"
)
def test_macos_reader_requires_macos():
    with pytest.raises(NativeReadUnavailable):
        read_macos_text()


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("x11", "x11-convert-selection"),
        ("windows", "windows-getclipboarddata"),
        ("macos", "macos-nspasteboard"),
    ],
)
def test_create_native_reader_returns_the_platform_reader(kind, expected):
    reader = create_native_reader(kind)
    assert reader is not None
    assert reader.name == expected


@pytest.mark.parametrize("kind", ["wayland", "polling", "unknown"])
def test_create_native_reader_leaves_other_backends_on_pyperclip(kind):
    assert create_native_reader(kind) is None
