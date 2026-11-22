"""Tests for the in-process clipboard readers on the native event path."""

from __future__ import annotations

import ctypes
import os
import platform

import pytest

from copyboard_extension import native_clipboard
from copyboard_extension.native_clipboard import (
    NativeReadUnavailable,
    NativeWriteUnavailable,
    X11ClipboardReader,
    X11ClipboardWriter,
    create_native_reader,
    read_macos_snapshot,
    read_macos_text,
    read_windows_snapshot,
    read_windows_text,
    write_macos_text,
    write_windows_text,
)


class FakeX11Session:
    """Scripted stand-in for the ctypes X11 connection."""

    def __init__(self, targets=None, reads=None, events=None, sensitive=False):
        self.incr = 900
        self._atoms = {
            b"CLIPBOARD": 100,
            b"COPYBOARD_SELECTION": 101,
            b"UTF8_STRING": 102,
            b"STRING": 103,
            b"INCR": 900,
            b"x-kde-passwordManagerHint": 104,
        }
        self.hint = self._atoms[b"x-kde-passwordManagerHint"]
        self._targets = dict(targets or {})
        if sensitive:
            self._targets[self.hint] = 888
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
        if target != self.hint:
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


def test_x11_reader_marks_a_kde_password_hint():
    session = FakeX11Session(
        targets={102: 555},
        sensitive=True,
        reads=[
            (888, 8, b"", 6),
            (888, 8, b"secret", 0),
            (102, 8, b"", 2),
            (102, 8, b"pw", 0),
        ],
    )

    snapshot = _reader(session).read_snapshot()

    assert snapshot.text == "pw"
    assert snapshot.sensitive is True


def test_x11_reader_does_not_mark_ordinary_text():
    session = FakeX11Session(
        targets={102: 555}, reads=[(102, 8, b"", 2), (102, 8, b"hi", 0)]
    )

    snapshot = _reader(session).read_snapshot()

    assert snapshot.text == "hi"
    assert snapshot.sensitive is False


class SensitiveUser32(FakeUser32):
    """Clipboard stub that can expose Windows sensitive-content formats."""

    def __init__(self, marker_values):
        super().__init__([1])
        self.formats = {
            "Clipboard Viewer Ignore": 49,
            "ExcludeClipboardContentFromMonitorProcessing": 50,
            "CanIncludeInClipboardHistory": 51,
        }
        self.marker_values = marker_values

    def RegisterClipboardFormatW(self, name):
        return self.formats.get(name, 0)

    def IsClipboardFormatAvailable(self, fmt):
        if fmt == native_clipboard.CF_UNICODETEXT:
            return 1
        return int(fmt in self.marker_values)

    def GetClipboardData(self, fmt):
        if fmt == native_clipboard.CF_UNICODETEXT:
            return self.handle
        return self.marker_values.get(fmt, 0)


class MarkerKernel32(FakeKernel32):
    def __init__(self, pointer, markers):
        super().__init__(pointer)
        self.markers = markers

    def GlobalLock(self, handle):
        if handle in self.markers:
            return self.markers[handle]
        return super().GlobalLock(handle)


def test_windows_snapshot_marks_include_history_zero():
    _buffer, pointer = _unicode_pointer("password")
    marker = ctypes.c_uint(0)
    user32 = SensitiveUser32({51: 700})
    kernel32 = MarkerKernel32(pointer, {700: ctypes.addressof(marker)})

    snapshot = read_windows_snapshot(user32=user32, kernel32=kernel32)

    assert snapshot.text == "password"
    assert snapshot.sensitive is True
    assert _buffer  # keep the text buffer alive for ctypes


def test_windows_snapshot_allows_include_history_one():
    _buffer, pointer = _unicode_pointer("ordinary")
    marker = ctypes.c_uint(1)
    user32 = SensitiveUser32({51: 700})
    kernel32 = MarkerKernel32(pointer, {700: ctypes.addressof(marker)})

    snapshot = read_windows_snapshot(user32=user32, kernel32=kernel32)

    assert snapshot.text == "ordinary"
    assert snapshot.sensitive is False


def test_windows_snapshot_marks_the_exclude_format():
    _buffer, pointer = _unicode_pointer("secret")
    user32 = SensitiveUser32({50: 701})
    kernel32 = MarkerKernel32(pointer, {})

    snapshot = read_windows_snapshot(user32=user32, kernel32=kernel32)

    assert snapshot.text == "secret"
    assert snapshot.sensitive is True


def test_windows_snapshot_marks_clipboard_viewer_ignore():
    _buffer, pointer = _unicode_pointer("secret")
    user32 = SensitiveUser32({49: 702})
    kernel32 = MarkerKernel32(pointer, {})

    snapshot = read_windows_snapshot(user32=user32, kernel32=kernel32)

    assert snapshot.sensitive is True


def test_windows_snapshot_without_markers_is_not_sensitive():
    _buffer, pointer = _unicode_pointer("plain")
    user32 = SensitiveUser32({})
    kernel32 = MarkerKernel32(pointer, {})

    snapshot = read_windows_snapshot(user32=user32, kernel32=kernel32)

    assert snapshot.text == "plain"
    assert snapshot.sensitive is False


class FakeWriteUser32:
    def __init__(self):
        self.emptied = 0
        self.closed = 0
        self.set_calls = []

    def OpenClipboard(self, _owner):
        return 1

    def EmptyClipboard(self):
        self.emptied += 1
        return 1

    def SetClipboardData(self, fmt, handle):
        self.set_calls.append((fmt, handle))
        return handle

    def CloseClipboard(self):
        self.closed += 1
        return 1


class FakeWriteKernel32:
    def __init__(self):
        self.memory = None
        self.allocation = None
        self.freed = []
        self.unlocked = []

    def GlobalAlloc(self, flags, size):
        self.allocation = (flags, size)
        self.memory = ctypes.create_string_buffer(size)
        return 1

    def GlobalLock(self, _handle):
        return ctypes.cast(self.memory, ctypes.c_void_p).value

    def GlobalUnlock(self, handle):
        self.unlocked.append(handle)
        return 1

    def GlobalFree(self, handle):
        self.freed.append(handle)
        return 0


def test_windows_writer_sets_unicode_text_and_closes():
    user32 = FakeWriteUser32()
    kernel32 = FakeWriteKernel32()

    write_windows_text("hello", user32=user32, kernel32=kernel32)

    assert user32.emptied == 1
    assert user32.set_calls == [(native_clipboard.CF_UNICODETEXT, 1)]
    assert user32.closed == 1
    assert kernel32.memory.raw.decode("utf-16-le").rstrip("\x00") == "hello"


class SensitivePasteboard(FakePasteboard):
    def __init__(self, value, offered_types):
        super().__init__(value)
        self._types = offered_types

    def types(self):
        return self._types


def test_macos_snapshot_marks_concealed_content():
    pasteboard = SensitivePasteboard(
        "password", ["public.utf8-plain-text", "org.nspasteboard.ConcealedType"]
    )

    snapshot = read_macos_snapshot(pasteboard)

    assert snapshot.text == "password"
    assert snapshot.sensitive is True


def test_macos_snapshot_marks_transient_content():
    pasteboard = SensitivePasteboard(
        "temporary", ["public.utf8-plain-text", "org.nspasteboard.TransientType"]
    )

    assert read_macos_snapshot(pasteboard).sensitive is True


def test_macos_snapshot_marks_the_legacy_concealed_type():
    pasteboard = SensitivePasteboard(
        "password",
        ["public.utf8-plain-text", "application/x-nspasteboard-concealed-type"],
    )

    assert read_macos_snapshot(pasteboard).sensitive is True


def test_macos_snapshot_without_markers_is_not_sensitive():
    pasteboard = SensitivePasteboard("plain", ["public.utf8-plain-text"])

    snapshot = read_macos_snapshot(pasteboard)

    assert snapshot.text == "plain"
    assert snapshot.sensitive is False


class FakeWritePasteboard:
    def __init__(self, cleared=True, written=True):
        self.cleared = 0
        self.writes = []
        self._cleared = cleared
        self._written = written

    def clearContents(self):
        self.cleared += 1
        return self._cleared

    def setString_forType_(self, text, kind):
        self.writes.append((text, kind))
        return self._written


def test_macos_writer_replaces_the_pasteboard_string():
    pasteboard = FakeWritePasteboard()

    write_macos_text("mac text", pasteboard)

    assert pasteboard.cleared == 1
    assert pasteboard.writes == [("mac text", "public.utf8-plain-text")]


def test_macos_writer_reports_a_failed_write():
    with pytest.raises(NativeWriteUnavailable):
        write_macos_text("text", FakeWritePasteboard(written=False))


class FakeWriterSession:
    """Owns a real pipe fd so the writer's select loop can run."""

    def __init__(self, fd):
        self._fd = fd
        self.atoms = {}
        self.owner_calls = []
        self.properties = []
        self.notifies = []
        self.selected = []
        self.closed = False
        self.window = 7

    def intern(self, name):
        return self.atoms.setdefault(name, 500 + len(self.atoms))

    def create_window(self):
        return self.window

    def destroy_window(self, _window):
        pass

    def close(self):
        self.closed = True

    def set_selection_owner(self, selection, window, timestamp=0):
        self.owner_calls.append((selection, window, timestamp))

    def pending(self):
        return False

    def connection_number(self):
        return self._fd

    def next_event(self, _timeout):
        return None

    def change_property(self, window, atom, type_atom, fmt, data):
        self.properties.append((window, atom, type_atom, fmt, data))

    def select_property_changes(self, window):
        self.selected.append(window)

    def send_selection_notify(
        self, requestor, selection, target, property_atom, timestamp=0
    ):
        self.notifies.append(
            (requestor, selection, target, property_atom, timestamp)
        )


def _x11_writer(chunk_size=1024):
    read_fd, write_fd = os.pipe()
    session = FakeWriterSession(read_fd)
    writer = X11ClipboardWriter(
        session_factory=lambda: session, chunk_size=chunk_size
    )
    return writer, session, read_fd, write_fd


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_claims_the_selection_and_serves_utf8():
    writer, session, read_fd, write_fd = _x11_writer()
    try:
        writer.write("hello")
        assert session.owner_calls[-1][:2] == (
            session.atoms[b"CLIPBOARD"],
            7,
        )

        writer._handle_event(
            {
                "type": 30,
                "requestor": 99,
                "selection": session.atoms[b"CLIPBOARD"],
                "target": session.atoms[b"UTF8_STRING"],
                "property": 55,
                "time": 123,
            }
        )

        assert session.properties[-1] == (
            99,
            55,
            session.atoms[b"UTF8_STRING"],
            8,
            b"hello",
        )
        assert session.notifies[-1][3] == 55
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_answers_targets():
    writer, session, read_fd, write_fd = _x11_writer()
    try:
        writer.write("hello")
        writer._handle_event(
            {
                "type": 30,
                "requestor": 99,
                "selection": session.atoms[b"CLIPBOARD"],
                "target": session.atoms[b"TARGETS"],
                "property": 56,
                "time": 123,
            }
        )

        _window, _atom, type_atom, fmt, values = session.properties[-1]
        assert type_atom == 4  # XA_ATOM
        assert fmt == 32
        assert session.atoms[b"UTF8_STRING"] in values
        assert session.atoms[b"STRING"] in values
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_chunks_large_text_with_incr():
    writer, session, read_fd, write_fd = _x11_writer(chunk_size=1024)
    try:
        writer.write("x" * 3000)
        request = {
            "type": 30,
            "requestor": 99,
            "selection": session.atoms[b"CLIPBOARD"],
            "target": session.atoms[b"UTF8_STRING"],
            "property": 57,
            "time": 123,
        }
        writer._handle_event(request)

        _window, _atom, type_atom, fmt, values = session.properties[-1]
        assert type_atom == session.atoms[b"INCR"]
        assert fmt == 32
        assert values == [3000]

        for _ in range(4):
            writer._handle_event(
                {"type": 28, "window": 99, "atom": 57, "state": 1}
            )

        assert session.properties[-1][4] == b""
        assert 57 not in writer._transfers
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_refuses_an_unsupported_target():
    writer, session, read_fd, write_fd = _x11_writer()
    try:
        writer.write("hello")
        writer._handle_event(
            {
                "type": 30,
                "requestor": 99,
                "selection": session.atoms[b"CLIPBOARD"],
                "target": 999,
                "property": 58,
                "time": 123,
            }
        )

        assert session.notifies[-1][3] == 0
        assert session.properties == []
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_does_not_steal_the_selection_before_a_write():
    writer, session, read_fd, write_fd = _x11_writer()
    try:
        writer._ensure_started()
        assert session.owner_calls == []
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_hands_the_last_text_off_on_close(monkeypatch):
    copied = []
    monkeypatch.setattr(
        native_clipboard.pyperclip, "copy", lambda text: copied.append(text)
    )
    writer, _session, read_fd, write_fd = _x11_writer()
    try:
        writer.write("handoff")
        writer.close(preserve=True)

        assert copied == ["handoff"]
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes")
def test_x11_writer_does_not_hand_off_after_losing_ownership(monkeypatch):
    copied = []
    monkeypatch.setattr(
        native_clipboard.pyperclip, "copy", lambda text: copied.append(text)
    )
    writer, session, read_fd, write_fd = _x11_writer()
    try:
        writer.write("stale")
        writer._handle_event(
            {
                "type": 29,
                "window": 7,
                "selection": session.atoms[b"CLIPBOARD"],
                "time": 124,
            }
        )
        writer.close(preserve=True)

        assert copied == []
    finally:
        writer.close(preserve=False)
        os.close(read_fd)
        os.close(write_fd)
