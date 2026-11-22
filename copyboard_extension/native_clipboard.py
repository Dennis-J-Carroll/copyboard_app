"""In-process clipboard reads and writes for the native capture path.

The watcher already knows when the clipboard changed, so it does not need to
start a clipboard utility to read the new value.  The same primitives also
let CopyBoard write a chamber without spawning ``xclip`` on every fire.

* X11 requests ``CLIPBOARD`` with ``ConvertSelection`` (including INCR
  transfers) and owns the selection with a small request-serving thread.
* Windows opens the clipboard for ``CF_UNICODETEXT`` and
  ``SetClipboardData``.
* macOS reads and replaces ``NSPasteboard`` strings with PyObjC.

Windows and macOS also expose their standard confidentiality markers, and X11
exposes KDE's password-manager hint, so marked copies can be kept out of the
board.  Wayland is deliberately absent from the native path: it needs the
data-control protocol, so that backend keeps ``wl-paste``.

Every reader is a callable returning ``str``; readers that can also report a
marker provide ``read_snapshot()``.  ``create_native_reader`` returns ``None``
for platforms without an in-process reader, which leaves the watcher on
``pyperclip`` exactly as before.  ``write_clipboard_text`` raises
``NativeWriteUnavailable`` when the native writer cannot be used, and callers
fall back to ``pyperclip``.
"""

from __future__ import annotations

import atexit
import ctypes
import ctypes.util
import logging
import os
import platform
import select
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pyperclip

LOGGER = logging.getLogger(__name__)

NATIVE_READ_TIMEOUT_S = 1.0
MAX_CLIPBOARD_BYTES = 16 * 1024 * 1024
WINDOWS_RETRY_TIMEOUT_S = 0.5
WINDOWS_RETRY_DELAY_S = 0.01
CF_UNICODETEXT = 13
NSPASTEBOARD_STRING = "public.utf8-plain-text"
# Windows and macOS publish these markers so clipboard-history tools can keep
# passwords and other concealed copies out of their history.
WINDOWS_SENSITIVE_FORMATS = (
    "Clipboard Viewer Ignore",
    "ExcludeClipboardContentFromMonitorProcessing",
    "CanIncludeInClipboardHistory",
)
NSPASTEBOARD_SENSITIVE_TYPES = (
    "org.nspasteboard.ConcealedType",
    "org.nspasteboard.TransientType",
    "application/x-nspasteboard-concealed-type",
    "com.agilebits.onepassword",
)
X11_SENSITIVE_TARGET = b"x-kde-passwordManagerHint"
X11_SENSITIVE_VALUE = b"secret"
# X11's traditional maximum request is 65535 four-byte units.  Stay well
# below it so a direct property write plus the request header cannot overflow.
X11_WRITE_CHUNK_BYTES = 64 * 1024
X11_HINT_TIMEOUT_S = 0.5

# X11 constants from X.h / XFixes.h.
_SELECTION_CLEAR = 29
_SELECTION_REQUEST = 30
_SELECTION_NOTIFY = 31
_PROPERTY_NOTIFY = 28
_PROPERTY_NEW_VALUE = 0
_PROPERTY_DELETE = 1
_ANY_PROPERTY_TYPE = 0
_XA_ATOM = 4
_PROPERTY_CHANGE_MASK = 1 << 22
_MAX_PROPERTY_LONGS = 65536
_XEVENT_SIZE = ctypes.sizeof(ctypes.c_long) * 24


@dataclass(frozen=True)
class ClipboardSnapshot:
    """One clipboard read, with any platform confidentiality marker."""

    text: str = ""
    sensitive: bool = False


class NativeReadUnavailable(RuntimeError):
    """Raised when an in-process clipboard reader cannot be used."""


class NativeWriteUnavailable(RuntimeError):
    """Raised when an in-process clipboard writer cannot be used."""


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


class _XSelectionRequestEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("owner", ctypes.c_ulong),
        ("requestor", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("target", ctypes.c_ulong),
        ("property", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
    ]


class _XSelectionClearEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("selection", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
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
        xlib.XSetSelectionOwner.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        xlib.XSetSelectionOwner.restype = ctypes.c_int
        xlib.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XGetSelectionOwner.restype = ctypes.c_ulong
        xlib.XChangeProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        xlib.XChangeProperty.restype = ctypes.c_int
        xlib.XSendEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_long,
            ctypes.c_void_p,
        ]
        xlib.XSendEvent.restype = ctypes.c_int
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

    def set_selection_owner(
        self, selection: int, window: int, timestamp: int = 0
    ) -> None:
        self._xlib.XSetSelectionOwner(
            self.display, selection, window, int(timestamp)
        )
        self._xlib.XFlush(self.display)

    def get_selection_owner(self, selection: int) -> int:
        return int(self._xlib.XGetSelectionOwner(self.display, selection))

    def select_property_changes(self, window: int) -> None:
        self._xlib.XSelectInput(self.display, window, _PROPERTY_CHANGE_MASK)
        self._xlib.XFlush(self.display)

    def change_property(
        self,
        window: int,
        atom: int,
        type_atom: int,
        fmt: int,
        data: Any,
    ) -> None:
        """Replace a property with bytes (format 8) or atoms (format 32)."""
        if fmt == 32:
            values = [int(value) for value in data]
            array = (ctypes.c_ulong * len(values))(*values)
            pointer = ctypes.cast(array, ctypes.c_void_p)
            count = len(values)
        else:
            payload = bytes(data)
            if payload:
                buffer = ctypes.create_string_buffer(payload, len(payload))
            else:
                buffer = ctypes.create_string_buffer(1)
            pointer = ctypes.cast(buffer, ctypes.c_void_p)
            count = len(payload)
        self._xlib.XChangeProperty(
            self.display,
            window,
            atom,
            type_atom,
            int(fmt),
            0,  # PropModeReplace
            pointer,
            count,
        )
        self._xlib.XFlush(self.display)

    def send_selection_notify(
        self,
        requestor: int,
        selection: int,
        target: int,
        property_atom: int,
        timestamp: int = 0,
    ) -> None:
        event = _XSelectionEvent()
        event.type = _SELECTION_NOTIFY
        event.send_event = 1
        event.display = self.display
        event.requestor = requestor
        event.selection = selection
        event.target = target
        event.property = property_atom
        event.time = int(timestamp)
        self._xlib.XSendEvent(
            self.display, requestor, False, 0, ctypes.byref(event)
        )
        self._xlib.XFlush(self.display)

    def pending(self) -> bool:
        return bool(self._xlib.XPending(self.display)) if self.display else False

    def connection_number(self) -> int:
        return int(self._xlib.XConnectionNumber(self.display))

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
                "time": int(selection.time),
            }
        if event_type == _SELECTION_REQUEST:
            request = ctypes.cast(
                event, ctypes.POINTER(_XSelectionRequestEvent)
            ).contents
            return {
                "type": event_type,
                "owner": int(request.owner),
                "requestor": int(request.requestor),
                "selection": int(request.selection),
                "target": int(request.target),
                "property": int(request.property),
                "time": int(request.time),
            }
        if event_type == _SELECTION_CLEAR:
            clear = ctypes.cast(
                event, ctypes.POINTER(_XSelectionClearEvent)
            ).contents
            return {
                "type": event_type,
                "window": int(clear.window),
                "selection": int(clear.selection),
                "time": int(clear.time),
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
        # Xlib expands 32-bit properties into native ``long`` elements, so
        # their stride is sizeof(long), not four bytes.
        if int(actual_format.value) == 32:
            per_item = ctypes.sizeof(ctypes.c_long)
        else:
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
        return self.read_snapshot().text

    def read_snapshot(self) -> ClipboardSnapshot:
        session = self._session_factory()
        try:
            return self._read_snapshot(session)
        finally:
            session.close()

    def _read_snapshot(self, session) -> ClipboardSnapshot:
        window = session.create_window()
        clipboard = session.intern(b"CLIPBOARD")
        property_atom = session.intern(b"COPYBOARD_SELECTION")
        try:
            sensitive = self._read_sensitive_hint(
                session, window, clipboard, property_atom
            )
            text = self._read_text(session, window, clipboard, property_atom)
            return ClipboardSnapshot(text=text, sensitive=sensitive)
        finally:
            session.destroy_window(window)

    def _read_text(self, session, window: int, clipboard: int, property_atom: int) -> str:
        # UTF-8 is the modern X11 text target; STRING is the Latin-1
        # fallback for older owners that refuse the former.
        for target_name in (b"UTF8_STRING", b"STRING"):
            target = session.intern(target_name)
            session.convert(clipboard, target, property_atom, window)
            notify = self._wait_for_selection(session, window, clipboard, target)
            if notify is None or not notify.get("property"):
                continue
            data, fmt = self._read_property(session, window, notify["property"])
            return _decode_x11_text(data, fmt, target_name)
        return ""

    def _read_sensitive_hint(
        self, session, window: int, clipboard: int, property_atom: int
    ) -> bool:
        """Read KDE's password-manager hint without failing the capture.

        A slow or non-conforming owner must not add a full second to every
        copy, so the hint gets a shorter budget and any error means "not
        marked" rather than a failed read.
        """
        hint = session.intern(X11_SENSITIVE_TARGET)
        # A separate property keeps a late hint reply from overwriting the
        # text transfer that follows it.
        hint_property = session.intern(b"COPYBOARD_HINT")
        session.convert(clipboard, hint, hint_property, window)
        notify = self._wait_for_selection(
            session,
            window,
            clipboard,
            hint,
            timeout=min(self._timeout, X11_HINT_TIMEOUT_S),
        )
        if notify is None or not notify.get("property"):
            return False
        try:
            data, _fmt = self._read_property(session, window, notify["property"])
        except NativeReadUnavailable:
            return False
        return X11_SENSITIVE_VALUE in data.lower()

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
        self,
        session,
        window: int,
        clipboard: int,
        target: int,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, int]]:
        deadline = time.monotonic() + (
            self._timeout if timeout is None else max(0.0, timeout)
        )
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
    user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    user32.RegisterClipboardFormatW.restype = ctypes.c_uint
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int


def _windows_format_id(user32, name: str) -> int:
    register = getattr(user32, "RegisterClipboardFormatW", None)
    if register is None:
        return 0
    try:
        return int(register(name))
    except Exception:
        return 0


def _windows_sensitive(user32, kernel32) -> bool:
    """Honor the Windows clipboard-history exclusion formats."""
    for name in WINDOWS_SENSITIVE_FORMATS[:-1]:
        exclusion = _windows_format_id(user32, name)
        if exclusion and user32.IsClipboardFormatAvailable(exclusion):
            return True

    include = _windows_format_id(user32, "CanIncludeInClipboardHistory")
    if include and user32.IsClipboardFormatAvailable(include):
        handle = user32.GetClipboardData(include)
        if handle:
            pointer = kernel32.GlobalLock(handle)
            if pointer:
                try:
                    if ctypes.c_uint.from_address(pointer).value == 0:
                        return True
                finally:
                    kernel32.GlobalUnlock(handle)
    return False


def read_windows_snapshot(
    user32=None,
    kernel32=None,
    retry_timeout: float = WINDOWS_RETRY_TIMEOUT_S,
) -> ClipboardSnapshot:
    """Read ``CF_UNICODETEXT`` and its confidentiality markers in-process."""
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
        text = ""
        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                pointer = kernel32.GlobalLock(handle)
                if pointer:
                    try:
                        text = ctypes.wstring_at(pointer)
                    finally:
                        kernel32.GlobalUnlock(handle)
        sensitive = _windows_sensitive(user32, kernel32)
        return ClipboardSnapshot(text=text, sensitive=sensitive)
    finally:
        user32.CloseClipboard()


def read_windows_text(
    user32=None,
    kernel32=None,
    retry_timeout: float = WINDOWS_RETRY_TIMEOUT_S,
) -> str:
    """Read ``CF_UNICODETEXT`` from the Windows clipboard in-process."""
    snapshot = read_windows_snapshot(
        user32=user32, kernel32=kernel32, retry_timeout=retry_timeout
    )
    return snapshot.text


def read_macos_snapshot(pasteboard=None) -> ClipboardSnapshot:
    """Read NSPasteboard text plus its confidentiality marker types."""
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

    sensitive = False
    types_method = getattr(pasteboard, "types", None)
    if types_method is not None:
        try:
            offered = types_method() or ()
        except Exception:
            offered = ()
        offered_types = {str(item) for item in offered}
        sensitive = any(
            marker in offered_types for marker in NSPASTEBOARD_SENSITIVE_TYPES
        )

    try:
        text = pasteboard.stringForType_(NSPASTEBOARD_STRING)
    except Exception as exc:
        raise NativeReadUnavailable(
            f"could not read NSPasteboard: {exc}"
        ) from exc
    return ClipboardSnapshot(
        text=text if isinstance(text, str) else "", sensitive=sensitive
    )


def read_macos_text(pasteboard=None) -> str:
    """Read the UTF-8 string from NSPasteboard when PyObjC is available."""
    return read_macos_snapshot(pasteboard).text


class WindowsClipboardReader:
    name = "windows-getclipboarddata"

    def __call__(self) -> str:
        return read_windows_text()

    def read_snapshot(self) -> ClipboardSnapshot:
        return read_windows_snapshot()


class MacOSClipboardReader:
    name = "macos-nspasteboard"

    def __call__(self) -> str:
        return read_macos_text()

    def read_snapshot(self) -> ClipboardSnapshot:
        return read_macos_snapshot()


_READER_FACTORIES = {
    "x11": X11ClipboardReader,
    "windows": WindowsClipboardReader,
    "macos": MacOSClipboardReader,
}


def create_native_reader(kind: str) -> Optional[Callable[[], str]]:
    """Return an in-process reader for ``kind``, or None to keep pyperclip."""
    factory = _READER_FACTORIES.get(kind)
    return factory() if factory is not None else None


# ---------------------------------------------------------------------------
# In-process clipboard writes
# ---------------------------------------------------------------------------
def write_windows_text(
    text: str,
    user32=None,
    kernel32=None,
    retry_timeout: float = WINDOWS_RETRY_TIMEOUT_S,
) -> None:
    """Replace the Windows clipboard with ``CF_UNICODETEXT`` in-process."""
    if user32 is None or kernel32 is None:
        if os.name != "nt":
            raise NativeWriteUnavailable("Windows clipboard writes require Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure_windows(user32, kernel32)

    deadline = time.monotonic() + max(0.0, float(retry_timeout))
    while not user32.OpenClipboard(None):
        if time.monotonic() >= deadline:
            raise NativeWriteUnavailable(
                "the clipboard is locked by another application"
            )
        time.sleep(WINDOWS_RETRY_DELAY_S)
    try:
        if not user32.EmptyClipboard():
            raise NativeWriteUnavailable("EmptyClipboard failed")
        payload = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(0x0042, len(payload))  # GMEM_MOVEABLE
        if not handle:
            raise NativeWriteUnavailable("GlobalAlloc failed")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            raise NativeWriteUnavailable("GlobalLock failed")
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise NativeWriteUnavailable("SetClipboardData failed")
    finally:
        user32.CloseClipboard()


def write_macos_text(text: str, pasteboard=None) -> None:
    """Replace the macOS pasteboard string in-process."""
    if pasteboard is None:
        if platform.system() != "Darwin":
            raise NativeWriteUnavailable("macOS clipboard writes require macOS")
        try:
            from AppKit import NSPasteboard
        except Exception as exc:
            raise NativeWriteUnavailable(
                "PyObjC AppKit is not installed"
            ) from exc
        pasteboard = NSPasteboard.generalPasteboard()
    try:
        if not pasteboard.clearContents():
            raise NativeWriteUnavailable("NSPasteboard.clearContents failed")
        if not pasteboard.setString_forType_(text, NSPASTEBOARD_STRING):
            raise NativeWriteUnavailable("NSPasteboard.setString failed")
    except NativeWriteUnavailable:
        raise
    except Exception as exc:
        raise NativeWriteUnavailable(
            f"could not write NSPasteboard: {exc}"
        ) from exc


class X11ClipboardWriter:
    """Own the X11 CLIPBOARD selection and serve text requests.

    The writer thread owns its own display connection and window.  A write
    only hands the new text to that thread and waits until ownership is
    claimed, so the caller can paste immediately afterwards.  Serving happens
    for as long as CopyBoard runs; ``close(preserve=True)`` hands the last
    text to ``pyperclip`` (usually ``xclip``) so the clipboard survives the
    process, matching the old behaviour.
    """

    name = "x11-selection-owner"

    def __init__(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
        chunk_size: int = X11_WRITE_CHUNK_BYTES,
    ) -> None:
        self._session_factory = session_factory or _X11Session
        self._chunk_size = max(1024, int(chunk_size))
        self._condition = threading.Condition(threading.RLock())
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._session = None
        self._window = 0
        self._selection = 0
        self._atoms: Dict[str, int] = {}
        self._text = ""
        self._generation = 0
        self._applied = 0
        self._error: Optional[str] = None
        self._owned = False
        self._transfers: Dict[tuple, Dict[str, Any]] = {}
        self._wake_read, self._wake_write = os.pipe()
        os.set_blocking(self._wake_read, False)
        os.set_blocking(self._wake_write, False)

    def write(self, text: str) -> None:
        self._ensure_started()
        with self._condition:
            if self._error:
                raise NativeWriteUnavailable(self._error)
            self._text = text
            self._generation += 1
            target = self._generation
        self._wake()
        with self._condition:
            applied = self._condition.wait_for(
                lambda: self._applied >= target or self._error is not None,
                timeout=1.5,
            )
            if self._error:
                raise NativeWriteUnavailable(self._error)
            if not applied:
                raise NativeWriteUnavailable(
                    "timed out claiming the X11 clipboard selection"
                )

    def close(self, preserve: bool = False) -> None:
        with self._condition:
            text = self._text
            wrote = self._applied > 0
            owned = self._owned
        if preserve and wrote and owned and text:
            # xclip/xsel keep a copy alive after CopyBoard exits.  This runs
            # once at shutdown, not on every copy.
            try:
                pyperclip.copy(text)
            except Exception as exc:
                LOGGER.debug("Could not hand off the X11 clipboard: %s", exc)
        self._stop.set()
        self._wake()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None
        for descriptor in (self._wake_read, self._wake_write):
            try:
                os.close(descriptor)
            except OSError:
                pass

    def _ensure_started(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            if self._error:
                raise NativeWriteUnavailable(self._error)
            self._ready.clear()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="copyboard-x11-writer", daemon=True
            )
            self._thread.start()
        if not self._ready.wait(timeout=2.0):
            self.close(preserve=False)
            raise NativeWriteUnavailable("timed out opening the X11 display")
        with self._condition:
            if self._error:
                raise NativeWriteUnavailable(self._error)

    def _run(self) -> None:
        session = None
        window = 0
        try:
            session = self._session_factory()
            window = session.create_window()
            selection = session.intern(b"CLIPBOARD")
            atoms = {
                name: session.intern(name.encode("ascii"))
                for name in (
                    "TARGETS",
                    "UTF8_STRING",
                    "STRING",
                    "text/plain;charset=utf-8",
                    "INCR",
                )
            }
            with self._condition:
                self._session = session
                self._window = window
                self._selection = selection
                self._atoms = atoms
            self._ready.set()

            while not self._stop.is_set():
                self._apply_pending()
                while session.pending():
                    event = session.next_event(0)
                    if event is None:
                        break
                    self._handle_event(event)
                if self._stop.is_set():
                    break
                try:
                    ready, _writable, _errors = select.select(
                        [session.connection_number(), self._wake_read],
                        [],
                        [],
                        0.5,
                    )
                except (OSError, ValueError) as exc:
                    with self._condition:
                        self._error = str(exc)
                        self._condition.notify_all()
                    break
                if self._wake_read in ready:
                    self._drain_wake()
        except Exception as exc:
            with self._condition:
                self._error = str(exc)
                self._condition.notify_all()
        finally:
            self._ready.set()
            if session is not None:
                if window:
                    try:
                        session.destroy_window(window)
                    except Exception:
                        pass
                try:
                    session.close()
                except Exception:
                    pass
            with self._condition:
                self._condition.notify_all()

    def _apply_pending(self) -> None:
        with self._condition:
            if self._generation <= self._applied:
                return
            session = self._session
            window = self._window
            selection = self._selection
            generation = self._generation
        if session is None or not window:
            return
        try:
            session.set_selection_owner(selection, window, 0)
        except Exception as exc:
            with self._condition:
                self._error = str(exc)
                self._condition.notify_all()
            return
        with self._condition:
            self._owned = True
            self._applied = generation
            self._condition.notify_all()

    def _handle_event(self, event: Dict[str, int]) -> None:
        event_type = event.get("type")
        if event_type == _SELECTION_REQUEST:
            self._handle_selection_request(event)
        elif event_type == _SELECTION_CLEAR:
            if event.get("selection") == self._selection:
                self._owned = False
                self._transfers.clear()
        elif event_type == _PROPERTY_NOTIFY:
            if event.get("state") != _PROPERTY_DELETE:
                return
            transfer = self._transfers.get(
                (event.get("window"), event.get("atom"))
            )
            if transfer is not None:
                self._send_next_chunk(
                    (event.get("window"), event.get("atom")), transfer
                )

    def _handle_selection_request(self, event: Dict[str, int]) -> None:
        session = self._session
        if session is None or event.get("selection") != self._selection:
            return
        requestor = event.get("requestor", 0)
        target = event.get("target", 0)
        property_atom = event.get("property", 0)
        timestamp = event.get("time", 0)
        if not property_atom:
            session.send_selection_notify(
                requestor, self._selection, target, 0, timestamp
            )
            return

        atoms = self._atoms
        if target == atoms.get("TARGETS"):
            values = [
                atoms.get("TARGETS", 0),
                atoms.get("UTF8_STRING", 0),
                atoms.get("STRING", 0),
                atoms.get("text/plain;charset=utf-8", 0),
            ]
            session.change_property(
                requestor, property_atom, _XA_ATOM, 32, values
            )
            session.send_selection_notify(
                requestor, self._selection, target, property_atom, timestamp
            )
            return

        if target not in (
            atoms.get("UTF8_STRING"),
            atoms.get("STRING"),
            atoms.get("text/plain;charset=utf-8"),
        ):
            session.send_selection_notify(
                requestor, self._selection, target, 0, timestamp
            )
            return

        with self._condition:
            text = self._text
        if target == atoms.get("STRING"):
            payload = text.encode("latin-1", "replace")
        else:
            payload = text.encode("utf-8")
        self._reply_bytes(
            session,
            requestor,
            property_atom,
            target,
            payload,
            timestamp,
        )

    def _reply_bytes(
        self,
        session,
        requestor: int,
        property_atom: int,
        target_type: int,
        payload: bytes,
        timestamp: int,
    ) -> None:
        if len(payload) <= self._chunk_size:
            session.change_property(
                requestor, property_atom, target_type, 8, payload
            )
            session.send_selection_notify(
                requestor,
                self._selection,
                target_type,
                property_atom,
                timestamp,
            )
            return

        session.change_property(
            requestor,
            property_atom,
            self._atoms["INCR"],
            32,
            [len(payload)],
        )
        # Select property changes before notifying: the requestor is allowed
        # to delete the INCR property as soon as it receives the notify, and a
        # missed delete would stall the transfer.
        session.select_property_changes(requestor)
        session.send_selection_notify(
            requestor,
            self._selection,
            target_type,
            property_atom,
            timestamp,
        )
        self._transfers[(requestor, property_atom)] = {
            "data": payload,
            "offset": 0,
            "type": target_type,
        }

    def _send_next_chunk(
        self, key: tuple, transfer: Dict[str, Any]
    ) -> None:
        session = self._session
        if session is None:
            return
        requestor, property_atom = key
        offset = int(transfer.get("offset", 0))
        payload = transfer["data"]
        chunk = payload[offset : offset + self._chunk_size]
        if chunk:
            session.change_property(
                requestor, property_atom, transfer["type"], 8, chunk
            )
            transfer["offset"] = offset + len(chunk)
        else:
            session.change_property(
                requestor, property_atom, transfer["type"], 8, b""
            )
            self._transfers.pop(key, None)

    def _wake(self) -> None:
        try:
            os.write(self._wake_write, b"x")
        except (BlockingIOError, OSError):
            pass

    def _drain_wake(self) -> None:
        while True:
            try:
                if not os.read(self._wake_read, 4096):
                    return
            except (BlockingIOError, OSError):
                return


_x11_writer_lock = threading.Lock()
_x11_writer: Optional[X11ClipboardWriter] = None


def _get_x11_writer() -> X11ClipboardWriter:
    global _x11_writer
    with _x11_writer_lock:
        if _x11_writer is None:
            _x11_writer = X11ClipboardWriter()
        return _x11_writer


def _discard_x11_writer(writer: X11ClipboardWriter) -> None:
    global _x11_writer
    with _x11_writer_lock:
        if _x11_writer is writer:
            _x11_writer = None
    try:
        writer.close(preserve=False)
    except Exception:
        pass


def write_clipboard_text(text: str) -> None:
    """Write clipboard text in-process where the platform allows it.

    Raises ``NativeWriteUnavailable`` so callers can retry with pyperclip and
    keep the old behaviour when a native connection cannot be opened.
    """
    if os.name == "nt":
        write_windows_text(text)
        return
    system = platform.system().lower()
    if system == "darwin":
        write_macos_text(text)
        return
    if system == "linux" and os.environ.get("DISPLAY"):
        writer = _get_x11_writer()
        try:
            writer.write(text)
        except Exception:
            _discard_x11_writer(writer)
            raise
        return
    raise NativeWriteUnavailable("no in-process clipboard writer is available")


def shutdown_clipboard_writer() -> None:
    """Hand the last X11 text off and stop the writer thread at exit."""
    global _x11_writer
    with _x11_writer_lock:
        writer = _x11_writer
        _x11_writer = None
    if writer is not None:
        writer.close(preserve=True)


atexit.register(shutdown_clipboard_writer)
