"""In-process clipboard reads for the native watcher event path.

The watcher already knows when the clipboard changed, so it does not need to
start a clipboard utility to read the new value.  These readers use the
platform APIs directly:

* X11 requests ``CLIPBOARD`` with ``ConvertSelection``, including INCR
  transfers for large payloads.
* Windows opens the clipboard and reads ``CF_UNICODETEXT`` with
  ``GetClipboardData``.
* macOS reads ``NSPasteboard`` with PyObjC when it is installed.

Wayland is deliberately absent: an in-process Wayland read needs the
data-control protocol, so that backend keeps ``wl-paste``.

Every reader is a callable returning ``str``.  ``create_native_reader``
returns ``None`` for platforms without an in-process reader, which leaves the
watcher on ``pyperclip`` exactly as before.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import platform
import select
import time
from typing import Any, Callable, Dict, Optional

LOGGER = logging.getLogger(__name__)

NATIVE_READ_TIMEOUT_S = 1.0
MAX_CLIPBOARD_BYTES = 16 * 1024 * 1024
WINDOWS_RETRY_TIMEOUT_S = 0.5
WINDOWS_RETRY_DELAY_S = 0.01
CF_UNICODETEXT = 13
NSPASTEBOARD_STRING = "public.utf8-plain-text"

# X11 constants from X.h / XFixes.h.
_SELECTION_NOTIFY = 31
_PROPERTY_NOTIFY = 28
_PROPERTY_NEW_VALUE = 0
_ANY_PROPERTY_TYPE = 0
_PROPERTY_CHANGE_MASK = 1 << 22
_MAX_PROPERTY_LONGS = 65536
_XEVENT_SIZE = ctypes.sizeof(ctypes.c_long) * 24


class NativeReadUnavailable(RuntimeError):
    """Raised when an in-process clipboard reader cannot be used."""


class _XSelectionEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("requestor", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("target", ctypes.c_ulong),
        ("property", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
    ]


class _XPropertyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("atom", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("state", ctypes.c_int),
    ]


class _X11Session:
    """One X11 connection and requestor window, opened per read."""

    def __init__(self) -> None:
        library = ctypes.util.find_library("X11")
        if not library:
            raise NativeReadUnavailable("libX11 is not available")
        self._xlib = ctypes.CDLL(library)
        self._configure()
        self.display = self._xlib.XOpenDisplay(None)
        if not self.display:
            raise NativeReadUnavailable("XOpenDisplay returned NULL")
        self.root = self._xlib.XDefaultRootWindow(self.display)
        self.incr = self.intern(b"INCR")
        self._window: Optional[int] = None

    def _configure(self) -> None:
        xlib = self._xlib
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        xlib.XInternAtom.restype = ctypes.c_ulong
        xlib.XCreateSimpleWindow.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        xlib.XCreateSimpleWindow.restype = ctypes.c_ulong
        xlib.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
        xlib.XSelectInput.restype = ctypes.c_int
        xlib.XConvertSelection.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        xlib.XConvertSelection.restype = ctypes.c_int
        xlib.XFlush.argtypes = [ctypes.c_void_p]
        xlib.XFlush.restype = ctypes.c_int
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XSync.restype = ctypes.c_int
        xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        xlib.XConnectionNumber.restype = ctypes.c_int
        xlib.XPending.argtypes = [ctypes.c_void_p]
        xlib.XPending.restype = ctypes.c_int
        xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        xlib.XNextEvent.restype = ctypes.c_int
        xlib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        xlib.XGetWindowProperty.restype = ctypes.c_int
        xlib.XDeleteProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        xlib.XDeleteProperty.restype = ctypes.c_int
        xlib.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XDestroyWindow.restype = ctypes.c_int
        xlib.XFree.argtypes = [ctypes.c_void_p]
        xlib.XFree.restype = ctypes.c_int
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.restype = ctypes.c_int

    def intern(self, name: bytes) -> int:
        return int(self._xlib.XInternAtom(self.display, name, 0))

    def create_window(self) -> int:
        window = int(
            self._xlib.XCreateSimpleWindow(
                self.display, self.root, 0, 0, 1, 1, 0, 0, 0
            )
        )
        if not window:
            raise NativeReadUnavailable("could not create an X11 requestor window")
        self._xlib.XSelectInput(self.display, window, _PROPERTY_CHANGE_MASK)
        self._xlib.XFlush(self.display)
        self._window = window
        return window

    def destroy_window(self, window: int) -> None:
        if self._window is None or self.display is None:
            return
        try:
            self._xlib.XDestroyWindow(self.display, window)
        except Exception:
            pass
        self._window = None

    def convert(
        self, selection: int, target: int, property_atom: int, window: int
    ) -> None:
        self._xlib.XConvertSelection(
            self.display, selection, target, property_atom, window, 0
        )
        self._xlib.XFlush(self.display)

    def next_event(self, timeout: float) -> Optional[Dict[str, int]]:
        if self.display is None:
            return None
        deadline = time.monotonic() + max(0.0, timeout)
        xlib = self._xlib
        while not xlib.XPending(self.display):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                ready, _writable, _errors = select.select(
                    [xlib.XConnectionNumber(self.display)], [], [], remaining
                )
            except (OSError, ValueError):
                return None
            if not ready and time.monotonic() >= deadline:
                return None
        if not xlib.XPending(self.display):
            return None
        event = ctypes.create_string_buffer(_XEVENT_SIZE)
        xlib.XNextEvent(self.display, event)
        event_type = ctypes.c_int.from_buffer(event).value
        if event_type == _SELECTION_NOTIFY:
            selection = ctypes.cast(
                event, ctypes.POINTER(_XSelectionEvent)
            ).contents
            return {
                "type": event_type,
                "requestor": int(selection.requestor),
                "selection": int(selection.selection),
                "target": int(selection.target),
                "property": int(selection.property),
            }
        if event_type == _PROPERTY_NOTIFY:
            prop = ctypes.cast(event, ctypes.POINTER(_XPropertyEvent)).contents
            return {
                "type": event_type,
                "window": int(prop.window),
                "atom": int(prop.atom),
                "state": int(prop.state),
            }
        return {"type": event_type}

    def read_property(
        self,
        window: int,
        atom: int,
        *,
        offset: int = 0,
        length: int = _MAX_PROPERTY_LONGS,
        delete: bool = False,
    ):
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.POINTER(ctypes.c_ubyte)()
        status = self._xlib.XGetWindowProperty(
            self.display,
            window,
            atom,
            offset,
            length,
            int(bool(delete)),
            _ANY_PROPERTY_TYPE,
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(nitems),
            ctypes.byref(bytes_after),
            ctypes.byref(prop),
        )
        if status != 0:
            raise NativeReadUnavailable(
                f"XGetWindowProperty returned status {status}"
            )
        per_item = max(1, int(actual_format.value) // 8)
        data = b""
        if prop and nitems.value:
            data = ctypes.string_at(prop, int(nitems.value) * per_item)
        if prop:
            self._xlib.XFree(prop)
        return (
            int(actual_type.value),
            int(actual_format.value),
            data,
            int(bytes_after.value),
        )

    def delete_property(self, window: int, atom: int) -> None:
        self._xlib.XDeleteProperty(self.display, window, atom)
        self._xlib.XFlush(self.display)

    def close(self) -> None:
        display = self.display
        self.display = None
        if display is not None:
            try:
                self._xlib.XCloseDisplay(display)
            except Exception:
                pass


class X11ClipboardReader:
    """Read clipboard text through X11 ConvertSelection, including INCR."""

    name = "x11-convert-selection"

    def __init__(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
        timeout: float = NATIVE_READ_TIMEOUT_S,
    ) -> None:
        self._session_factory = session_factory or _X11Session
        self._timeout = float(timeout)

    def __call__(self) -> str:
        session = self._session_factory()
        try:
            return self._read(session)
        finally:
            session.close()

    def _read(self, session) -> str:
        window = session.create_window()
        clipboard = session.intern(b"CLIPBOARD")
        property_atom = session.intern(b"COPYBOARD_SELECTION")
        try:
            # UTF-8 is the modern X11 text target; STRING is the Latin-1
            # fallback for older owners that refuse the former.
            for target_name in (b"UTF8_STRING", b"STRING"):
                target = session.intern(target_name)
                session.convert(clipboard, target, property_atom, window)
                notify = self._wait_for_selection(
                    session, window, clipboard, target
                )
                if notify is None or not notify.get("property"):
                    continue
                data, fmt = self._read_property(
                    session, window, notify["property"]
                )
                return _decode_x11_text(data, fmt, target_name)
            return ""
        finally:
            session.destroy_window(window)

    def _read_property(self, session, window: int, prop: int):
        # Ask for the type first so an INCR transfer is acknowledged before
        # any payload is read.  A non-INCR property is fetched in chunks and
        # deleted only after the last chunk.
        actual_type, fmt, _data, _remaining = session.read_property(
            window, prop, length=0
        )
        if actual_type == session.incr:
            session.read_property(window, prop, delete=True)
            return self._read_incremental(session, window, prop), 8
        if not actual_type:
            return b"", fmt

        chunks = []
        offset = 0
        remaining = 1
        while remaining:
            _chunk_type, fmt, chunk, remaining = session.read_property(
                window, prop, offset=offset
            )
            if not chunk and remaining:
                raise NativeReadUnavailable(
                    "X11 clipboard property did not advance"
                )
            chunks.append(chunk)
            offset += (len(chunk) + 3) // 4
        session.delete_property(window, prop)
        return b"".join(chunks), fmt

    def _read_incremental(self, session, window: int, prop: int) -> bytes:
        chunks = []
        total = 0
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeReadUnavailable(
                    "timed out receiving an INCR clipboard transfer"
                )
            event = session.next_event(remaining)
            if event is None:
                raise NativeReadUnavailable(
                    "timed out receiving an INCR clipboard transfer"
                )
            if (
                event.get("type") != _PROPERTY_NOTIFY
                or event.get("atom") != prop
                or event.get("state") != _PROPERTY_NEW_VALUE
            ):
                continue
            _type, _fmt, chunk, _remaining = session.read_property(
                window, prop, delete=True
            )
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > MAX_CLIPBOARD_BYTES:
                raise NativeReadUnavailable(
                    "clipboard text exceeds the in-process read limit"
                )
            chunks.append(chunk)

    def _wait_for_selection(
        self, session, window: int, clipboard: int, target: int
    ) -> Optional[Dict[str, int]]:
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            event = session.next_event(remaining)
            if event is None:
                return None
            if (
                event.get("type") == _SELECTION_NOTIFY
                and event.get("requestor") == window
                and event.get("selection") == clipboard
                and event.get("target") == target
            ):
                return event


def _decode_x11_text(data: bytes, fmt: int, target_name: bytes) -> str:
    if not data:
        return ""
    if fmt == 16:
        return data.decode("utf-16-le", "replace")
    if fmt == 32:
        return data.decode("utf-32-le", "replace")
    if target_name == b"UTF8_STRING":
        return data.decode("utf-8", "replace")
    return data.decode("latin-1")


def _configure_windows(user32, kernel32) -> None:
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    user32.IsClipboardFormatAvailable.restype = ctypes.c_int
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int


def read_windows_text(
    user32=None,
    kernel32=None,
    retry_timeout: float = WINDOWS_RETRY_TIMEOUT_S,
) -> str:
    """Read ``CF_UNICODETEXT`` from the Windows clipboard in-process."""
    if user32 is None or kernel32 is None:
        if os.name != "nt":
            raise NativeReadUnavailable("Windows clipboard reads require Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure_windows(user32, kernel32)

    deadline = time.monotonic() + max(0.0, float(retry_timeout))
    while not user32.OpenClipboard(None):
        if time.monotonic() >= deadline:
            raise NativeReadUnavailable(
                "the clipboard is locked by another application"
            )
        time.sleep(WINDOWS_RETRY_DELAY_S)
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def read_macos_text(pasteboard=None) -> str:
    """Read the UTF-8 string from NSPasteboard when PyObjC is available."""
    if pasteboard is None:
        if platform.system() != "Darwin":
            raise NativeReadUnavailable("macOS clipboard reads require macOS")
        try:
            from AppKit import NSPasteboard
        except Exception as exc:
            raise NativeReadUnavailable(
                "PyObjC AppKit is not installed"
            ) from exc
        pasteboard = NSPasteboard.generalPasteboard()
    try:
        text = pasteboard.stringForType_(NSPASTEBOARD_STRING)
    except Exception as exc:
        raise NativeReadUnavailable(
            f"could not read NSPasteboard: {exc}"
        ) from exc
    return text if isinstance(text, str) else ""


class WindowsClipboardReader:
    name = "windows-getclipboarddata"

    def __call__(self) -> str:
        return read_windows_text()


class MacOSClipboardReader:
    name = "macos-nspasteboard"

    def __call__(self) -> str:
        return read_macos_text()


_READER_FACTORIES = {
    "x11": X11ClipboardReader,
    "windows": WindowsClipboardReader,
    "macos": MacOSClipboardReader,
}


def create_native_reader(kind: str) -> Optional[Callable[[], str]]:
    """Return an in-process reader for ``kind``, or None to keep pyperclip."""
    factory = _READER_FACTORIES.get(kind)
    return factory() if factory is not None else None
