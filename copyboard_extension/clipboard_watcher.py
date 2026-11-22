"""Event-driven clipboard watching with a safe polling fallback.

The GUI must never depend on a native watcher succeeding.  This module probes
for the best platform-specific backend, starts it, and transparently falls back
to a small polling backend if probing or the running backend fails.

Native backends:

* ``linux-wayland`` uses ``wl-paste --watch`` from wl-clipboard.
* ``linux-x11`` uses the XFixes selection-notify event through ctypes.
* ``windows`` uses ``AddClipboardFormatListener`` in a message-only window.
* ``macos`` uses NSPasteboard's native change counter when PyObjC is present.

Every other case, and every failure, uses ``polling`` at a 250 ms cadence.
Native event backends read the clipboard in-process, so a copy does not start
``xclip``/``xsel``/``pbpaste``.  Clipboard text is passed to the callback and
is never logged here.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import platform
import select
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pyperclip

from .native_clipboard import ClipboardSnapshot, create_native_reader

LOGGER = logging.getLogger(__name__)

FALLBACK_INTERVAL_S = 0.25
WAYLAND_DEBOUNCE_S = 0.02
_UNSET = object()


class BackendUnavailable(RuntimeError):
    """Raised when a platform backend cannot be started on this machine."""


@dataclass(frozen=True)
class ClipboardChange:
    """A clipboard change observed by a backend."""

    text: str
    observed_at_ns: int
    backend: str
    sensitive: bool = False


def read_clipboard_snapshot(reader: Callable[[], Any]) -> ClipboardSnapshot:
    """Read text and confidentiality markers through any reader shape."""
    snapshot_reader = getattr(reader, "read_snapshot", None)
    if snapshot_reader is not None:
        return snapshot_reader()
    result = reader()
    if isinstance(result, ClipboardSnapshot):
        return result
    return ClipboardSnapshot(
        text=result if isinstance(result, str) else str(result or "")
    )


ChangeCallback = Callable[[ClipboardChange], None]
FailureCallback = Callable[[str], None]


class ClipboardBackend:
    """Base class for clipboard backends."""

    name = "abstract"
    event_driven = False

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
    ) -> None:
        self._on_change = on_change
        self._read_clipboard = read_clipboard
        self._on_failure = on_failure
        self._failure_reported = False

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def _emit_text(
        self,
        text: Any,
        observed_at_ns: Optional[int] = None,
        *,
        sensitive: bool = False,
    ) -> None:
        if observed_at_ns is None:
            observed_at_ns = time.perf_counter_ns()
        try:
            self._on_change(
                ClipboardChange(
                    text=text if isinstance(text, str) else str(text or ""),
                    observed_at_ns=observed_at_ns,
                    backend=self.name,
                    sensitive=bool(sensitive),
                )
            )
        except Exception:
            # A consumer bug must not take down a native event source and
            # strand the app without clipboard capture.
            LOGGER.exception("Clipboard change callback failed")

    def _emit_current(self) -> None:
        """Read the clipboard and emit one change.

        The observation time is taken before the read so the measured latency
        includes the clipboard read itself.
        """
        observed_at_ns = time.perf_counter_ns()
        try:
            snapshot = read_clipboard_snapshot(self._read_clipboard)
        except Exception as exc:  # clipboard may be locked or empty
            LOGGER.debug("%s clipboard read failed: %s", self.name, exc)
            return
        self._emit_text(
            snapshot.text, observed_at_ns, sensitive=snapshot.sensitive
        )

    def _fail(self, reason: str) -> None:
        if self._failure_reported:
            return
        self._failure_reported = True
        LOGGER.warning("Clipboard backend %s failed: %s", self.name, reason)
        if self._on_failure is not None:
            try:
                self._on_failure(reason)
            except Exception:
                LOGGER.exception("Clipboard fallback handler failed")


class PollingBackend(ClipboardBackend):
    """Portable fallback: read the clipboard on a fixed interval."""

    name = "polling"
    event_driven = False

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
        interval: float = FALLBACK_INTERVAL_S,
        initial_text: Any = _UNSET,
    ) -> None:
        super().__init__(on_change, read_clipboard, on_failure=on_failure)
        self._interval = max(0.05, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._primed = initial_text is not _UNSET
        self._last: Any = initial_text if self._primed else object()

    @property
    def interval(self) -> float:
        """Seconds between fallback polls (for diagnostics and tests)."""
        return self._interval

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="copyboard-clipboard-poll", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.3, self._interval * 2))
        self._thread = None

    def poll_once(self) -> Optional[ClipboardChange]:
        """Perform one deterministic poll (also used by tests)."""
        observed_at_ns = time.perf_counter_ns()
        try:
            snapshot = read_clipboard_snapshot(self._read_clipboard)
            text = snapshot.text
        except Exception as exc:
            LOGGER.debug("polling clipboard read failed: %s", exc)
            return None
        if not self._primed:
            # Match the old startup behavior: the current clipboard is the
            # baseline, not a new capture.
            self._primed = True
            self._last = text
            return None
        if text == self._last:
            return None
        self._last = text
        return ClipboardChange(
            text=text if isinstance(text, str) else str(text or ""),
            observed_at_ns=observed_at_ns,
            backend=self.name,
            sensitive=snapshot.sensitive,
        )

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            change = self.poll_once()
            if change is not None:
                try:
                    self._on_change(change)
                except Exception:
                    LOGGER.exception("Clipboard polling callback failed")


class WaylandBackend(ClipboardBackend):
    """Wayland changes via ``wl-paste --watch`` (wl-clipboard)."""

    name = "linux-wayland"
    event_driven = True

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
    ) -> None:
        super().__init__(on_change, read_clipboard, on_failure=on_failure)
        self._stop = threading.Event()
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if platform.system().lower() != "linux":
            raise BackendUnavailable("Wayland backend is Linux-only")
        if not os.environ.get("WAYLAND_DISPLAY"):
            raise BackendUnavailable("WAYLAND_DISPLAY is not set")
        if shutil.which("wl-paste") is None:
            raise BackendUnavailable("wl-paste is not installed")
        self._stop.clear()
        try:
            self._process = subprocess.Popen(
                [
                    "wl-paste",
                    "--watch",
                    "sh",
                    "-c",
                    "cat >/dev/null; printf x",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except OSError as exc:
            raise BackendUnavailable(f"could not start wl-paste: {exc}") from exc
        # A missing data-control protocol makes wl-paste exit immediately.
        time.sleep(0.12)
        if self._process.poll() is not None:
            code = self._process.returncode
            self._process = None
            raise BackendUnavailable(f"wl-paste --watch exited with status {code}")
        self._thread = threading.Thread(
            target=self._run, name="copyboard-clipboard-wayland", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        self._process = None
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass
            try:
                process.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass
            if process.stdout is not None:
                try:
                    process.stdout.close()
                except OSError:
                    pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            while not self._stop.is_set():
                data = process.stdout.read(1)
                if not data:
                    if not self._stop.is_set():
                        self._fail("wl-paste --watch exited")
                    return
                # Coalesce owner-change bursts into one capture.
                time.sleep(WAYLAND_DEBOUNCE_S)
                if self._stop.is_set():
                    return
                self._emit_current()
        except Exception as exc:
            if not self._stop.is_set():
                self._fail(str(exc))


class X11Backend(ClipboardBackend):
    """X11 changes via the XFixes selection-notify event, without a toolkit."""

    name = "linux-x11"
    event_driven = True

    XFIXES_SET_SELECTION_OWNER_NOTIFY_MASK = 1
    XFIXES_SELECTION_WINDOW_DESTROY_MASK = 2
    XFIXES_SELECTION_CLIENT_CLOSE_MASK = 4

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
    ) -> None:
        super().__init__(on_change, read_clipboard, on_failure=on_failure)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._error: Optional[str] = None

    def start(self) -> None:
        if platform.system().lower() != "linux":
            raise BackendUnavailable("X11 backend is Linux-only")
        if not os.environ.get("DISPLAY"):
            raise BackendUnavailable("DISPLAY is not set")
        self._stop.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run, name="copyboard-clipboard-x11", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout=2.0):
            self.stop()
            raise BackendUnavailable("timed out opening the X11 display")
        if self._error:
            self.stop()
            raise BackendUnavailable(self._error)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        display = None
        try:
            x11_name = ctypes.util.find_library("X11")
            xfixes_name = ctypes.util.find_library("Xfixes")
            if not x11_name or not xfixes_name:
                raise BackendUnavailable("libX11 or libXfixes is not available")
            xlib = ctypes.CDLL(x11_name)
            xfixes = ctypes.CDLL(xfixes_name)

            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            xlib.XDefaultRootWindow.restype = ctypes.c_ulong
            xlib.XInternAtom.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_int,
            ]
            xlib.XInternAtom.restype = ctypes.c_ulong
            xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
            xlib.XConnectionNumber.restype = ctypes.c_int
            xlib.XPending.argtypes = [ctypes.c_void_p]
            xlib.XPending.restype = ctypes.c_int
            xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            xlib.XNextEvent.restype = ctypes.c_int
            xlib.XFlush.argtypes = [ctypes.c_void_p]
            xlib.XFlush.restype = ctypes.c_int
            xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xlib.XCloseDisplay.restype = ctypes.c_int
            xfixes.XFixesQueryExtension.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ]
            xfixes.XFixesQueryExtension.restype = ctypes.c_int
            xfixes.XFixesSelectSelectionInput.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
            ]
            xfixes.XFixesSelectSelectionInput.restype = None

            display = xlib.XOpenDisplay(None)
            if not display:
                raise BackendUnavailable("XOpenDisplay returned NULL")
            event_base = ctypes.c_int(0)
            error_base = ctypes.c_int(0)
            if not xfixes.XFixesQueryExtension(
                display, ctypes.byref(event_base), ctypes.byref(error_base)
            ):
                raise BackendUnavailable("the X server does not support XFixes")
            root = xlib.XDefaultRootWindow(display)
            clipboard = xlib.XInternAtom(display, b"CLIPBOARD", 0)
            mask = (
                self.XFIXES_SET_SELECTION_OWNER_NOTIFY_MASK
                | self.XFIXES_SELECTION_WINDOW_DESTROY_MASK
                | self.XFIXES_SELECTION_CLIENT_CLOSE_MASK
            )
            xfixes.XFixesSelectSelectionInput(display, root, clipboard, mask)
            xlib.XFlush(display)
            fd = xlib.XConnectionNumber(display)
            event_type = event_base.value
            self._ready.set()

            event_buffer = ctypes.create_string_buffer(256)
            while not self._stop.is_set():
                if xlib.XPending(display):
                    while xlib.XPending(display):
                        xlib.XNextEvent(display, event_buffer)
                        if (
                            ctypes.c_int.from_buffer(event_buffer).value
                            == event_type
                        ):
                            self._emit_current()
                    xlib.XFlush(display)
                    continue
                try:
                    select.select([fd], [], [], 0.2)
                except (OSError, ValueError) as exc:
                    if not self._stop.is_set():
                        self._fail(str(exc))
                    return
        except Exception as exc:
            if not self._ready.is_set():
                self._error = str(exc)
            elif not self._stop.is_set():
                self._fail(str(exc))
        finally:
            self._ready.set()
            if display:
                try:
                    xlib.XCloseDisplay(display)
                except Exception:
                    pass


class WindowsBackend(ClipboardBackend):
    """Windows clipboard changes via AddClipboardFormatListener."""

    name = "windows-listener"
    event_driven = True
    WM_CLIPBOARDUPDATE = 0x031D
    WM_QUIT = 0x0012

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
    ) -> None:
        super().__init__(on_change, read_clipboard, on_failure=on_failure)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._thread_id = 0
        self._hwnd: Optional[int] = None

    def start(self) -> None:
        if os.name != "nt":
            raise BackendUnavailable("Windows backend requires Windows")
        self._stop.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run, name="copyboard-clipboard-windows", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout=2.0):
            self.stop()
            raise BackendUnavailable("timed out creating the clipboard window")
        if self._error:
            self.stop()
            raise BackendUnavailable(self._error)

    def stop(self) -> None:
        self._stop.set()
        if self._thread_id:
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostThreadMessageW(
                    self._thread_id, self.WM_QUIT, 0, 0
                )
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None

    def _run(self) -> None:
        user32 = None
        kernel32 = None
        hwnd = None
        class_name = None
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_ssize_t,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            )

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", ctypes.c_uint),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p),
                    ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p),
                    ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", ctypes.c_wchar_p),
                    ("lpszClassName", ctypes.c_wchar_p),
                ]

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_size_t),
                    ("lParam", ctypes.c_ssize_t),
                    ("time", ctypes.c_uint),
                    ("pt", POINT),
                    ("lPrivate", ctypes.c_uint),
                ]

            user32.DefWindowProcW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            user32.DefWindowProcW.restype = ctypes.c_ssize_t
            user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
            user32.RegisterClassW.restype = ctypes.c_ushort
            user32.UnregisterClassW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
            user32.UnregisterClassW.restype = ctypes.c_int
            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            user32.CreateWindowExW.restype = ctypes.c_void_p
            user32.DestroyWindow.argtypes = [ctypes.c_void_p]
            user32.DestroyWindow.restype = ctypes.c_int
            user32.AddClipboardFormatListener.argtypes = [ctypes.c_void_p]
            user32.AddClipboardFormatListener.restype = ctypes.c_int
            user32.RemoveClipboardFormatListener.argtypes = [ctypes.c_void_p]
            user32.RemoveClipboardFormatListener.restype = ctypes.c_int
            user32.GetMessageW.argtypes = [
                ctypes.POINTER(MSG),
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            user32.GetMessageW.restype = ctypes.c_int
            user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
            user32.TranslateMessage.restype = ctypes.c_int
            user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
            user32.DispatchMessageW.restype = ctypes.c_ssize_t
            user32.PostThreadMessageW.argtypes = [
                ctypes.c_ulong,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            user32.PostThreadMessageW.restype = ctypes.c_int
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            kernel32.GetCurrentThreadId.argtypes = []
            kernel32.GetCurrentThreadId.restype = ctypes.c_ulong

            def wndproc(hwnd_, message, wparam, lparam):
                if message == self.WM_CLIPBOARDUPDATE:
                    self._emit_current()
                    return 0
                return user32.DefWindowProcW(hwnd_, message, wparam, lparam)

            self._wndproc = WNDPROC(wndproc)
            hinstance = kernel32.GetModuleHandleW(None)
            class_name = f"CopyBoardClipboardWatcher_{os.getpid()}"
            wc = WNDCLASSW()
            wc.lpfnWndProc = self._wndproc
            wc.hInstance = hinstance
            wc.lpszClassName = class_name
            if not user32.RegisterClassW(ctypes.byref(wc)):
                raise BackendUnavailable("RegisterClassW failed")
            hwnd = user32.CreateWindowExW(
                0,
                class_name,
                "CopyBoard Clipboard Watcher",
                0,
                0,
                0,
                0,
                0,
                ctypes.c_void_p(-3),  # HWND_MESSAGE
                None,
                hinstance,
                None,
            )
            if not hwnd:
                raise BackendUnavailable("CreateWindowExW failed")
            self._hwnd = hwnd
            if not user32.AddClipboardFormatListener(hwnd):
                raise BackendUnavailable("AddClipboardFormatListener failed")
            self._thread_id = kernel32.GetCurrentThreadId()
            self._ready.set()

            msg = MSG()
            while not self._stop.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    if not self._stop.is_set():
                        self._fail("GetMessageW failed")
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            if not self._ready.is_set():
                self._error = str(exc)
            elif not self._stop.is_set():
                self._fail(str(exc))
        finally:
            self._ready.set()
            if hwnd and user32 is not None:
                try:
                    user32.RemoveClipboardFormatListener(hwnd)
                    user32.DestroyWindow(hwnd)
                except Exception:
                    pass
            if class_name and user32 is not None and kernel32 is not None:
                try:
                    user32.UnregisterClassW(
                        class_name, kernel32.GetModuleHandleW(None)
                    )
                except Exception:
                    pass


class MacOSChangeCountBackend(ClipboardBackend):
    """macOS native change counter, when PyObjC is installed.

    NSPasteboard has no notification API.  The native change counter avoids a
    ``pbpaste`` subprocess on every sample, but it is still a timer.  If PyObjC
    is absent the watcher uses the portable polling fallback instead.
    """

    name = "macos-changecount"
    event_driven = False

    def __init__(
        self,
        on_change: ChangeCallback,
        read_clipboard: Callable[[], Any],
        *,
        on_failure: Optional[FailureCallback] = None,
    ) -> None:
        super().__init__(on_change, read_clipboard, on_failure=on_failure)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pasteboard = None

    def start(self) -> None:
        if platform.system().lower() != "darwin":
            raise BackendUnavailable("macOS backend requires macOS")
        try:
            from AppKit import NSPasteboard
        except Exception as exc:
            raise BackendUnavailable("PyObjC AppKit is not installed") from exc
        try:
            self._pasteboard = NSPasteboard.generalPasteboard()
            self._last_count = int(self._pasteboard.changeCount())
        except Exception as exc:
            raise BackendUnavailable(f"could not read NSPasteboard: {exc}") from exc
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="copyboard-clipboard-macos", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        try:
            while not self._stop.wait(0.1):
                pasteboard = self._pasteboard
                if pasteboard is None:
                    return
                count = int(pasteboard.changeCount())
                if count == self._last_count:
                    continue
                self._last_count = count
                # Go through the backend reader so a transient pasteboard
                # error falls back per event instead of demoting the backend.
                self._emit_current()
        except Exception as exc:
            if not self._stop.is_set():
                self._fail(str(exc))


def detect_backend_kind(
    system: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> str:
    """Return the preferred backend kind without starting it."""
    system = (system or platform.system()).lower()
    env = os.environ if env is None else env
    which = shutil.which if which is None else which
    if system == "linux":
        if env.get("WAYLAND_DISPLAY") and which("wl-paste"):
            return "wayland"
        if env.get("DISPLAY"):
            return "x11"
    elif system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    return "polling"


def create_backend(
    kind: str,
    on_change: ChangeCallback,
    read_clipboard: Callable[[], Any],
    *,
    on_failure: Optional[FailureCallback] = None,
    initial_text: Any = _UNSET,
) -> ClipboardBackend:
    """Build one backend by kind.  Raises BackendUnavailable if unsupported."""
    if kind == "wayland":
        return WaylandBackend(on_change, read_clipboard, on_failure=on_failure)
    if kind == "x11":
        return X11Backend(on_change, read_clipboard, on_failure=on_failure)
    if kind == "windows":
        return WindowsBackend(on_change, read_clipboard, on_failure=on_failure)
    if kind == "macos":
        return MacOSChangeCountBackend(
            on_change, read_clipboard, on_failure=on_failure
        )
    if kind == "polling":
        return PollingBackend(
            on_change,
            read_clipboard,
            on_failure=on_failure,
            initial_text=initial_text,
        )
    raise BackendUnavailable(f"unknown clipboard backend: {kind}")


class _ReaderWithFallback:
    """Use an in-process reader, but never lose a copy to a failed read.

    A native read can fail transiently (a slow selection owner, a locked
    clipboard, a display restart).  Falling back to ``pyperclip`` for that one
    event keeps capture working; the warning is logged once so a persistent
    failure does not flood the log.
    """

    def __init__(self, native: Callable[[], str]) -> None:
        self._native = native
        self.name = getattr(native, "name", "native")
        self._warned = False

    def read_snapshot(self) -> ClipboardSnapshot:
        try:
            return read_clipboard_snapshot(self._native)
        except Exception as exc:
            if not self._warned:
                LOGGER.warning(
                    "Native clipboard read failed (%s); using pyperclip", exc
                )
                self._warned = True
            return ClipboardSnapshot(text=pyperclip.paste())

    def __call__(self) -> Any:
        return self.read_snapshot().text


class ClipboardWatcher:
    """Own one clipboard backend and fall back safely when it fails."""

    def __init__(
        self,
        on_change: ChangeCallback,
        *,
        read_clipboard: Optional[Callable[[], Any]] = None,
        backend: Optional[ClipboardBackend] = None,
        fallback_factory: Optional[Callable[[], ClipboardBackend]] = None,
        backend_kind: Optional[str] = None,
        initial_text: Any = _UNSET,
    ) -> None:
        self._on_change = on_change
        self._initial_text = initial_text
        self._lock = threading.Lock()
        self._started = False
        self._stopped = False
        self._fallback_active = False
        self._fallback_reason: Optional[str] = None
        self._retired: list[ClipboardBackend] = []

        def make_fallback() -> ClipboardBackend:
            return PollingBackend(
                self._on_change,
                self._read_clipboard,
                on_failure=self._handle_failure,
                initial_text=self._initial_text,
            )

        self._fallback_factory = fallback_factory or make_fallback
        self._backend: Optional[ClipboardBackend] = None
        kind = backend_kind or detect_backend_kind()
        self._read_clipboard, self._reader_name = self._select_reader(
            read_clipboard, kind
        )
        if backend is not None:
            self._backend = backend
            return

        try:
            self._backend = create_backend(
                kind,
                self._on_change,
                self._read_clipboard,
                on_failure=self._handle_failure,
                initial_text=self._initial_text,
            )
        except Exception as exc:
            LOGGER.warning("Could not create clipboard backend %s: %s", kind, exc)
            self._fallback_reason = str(exc)
            self._fallback_active = True
            self._backend = self._fallback_factory()

    @property
    def backend_name(self) -> str:
        backend = self._backend
        return backend.name if backend is not None else "none"

    @property
    def event_driven(self) -> bool:
        backend = self._backend
        return bool(backend is not None and backend.event_driven)

    @property
    def fallback_reason(self) -> Optional[str]:
        return self._fallback_reason

    @property
    def reader_name(self) -> str:
        """How the event path reads clipboard text (native, pyperclip, custom)."""
        return self._reader_name

    @staticmethod
    def _reader_kind(kind: str) -> str:
        """Pick a reader independently of the event backend.

        ``polling`` exists because the event backend failed, not because the
        platform lacks a native reader.  Keeping the native reader on that
        path avoids spawning a clipboard utility four times a second and
        preserves confidentiality markers during a fallback.
        """
        if kind in {"x11", "windows", "macos"}:
            return kind
        if kind != "polling":
            return kind
        if os.name == "nt":
            return "windows"
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        if system == "linux" and os.environ.get("DISPLAY"):
            return "x11"
        return kind

    @staticmethod
    def _select_reader(
        read_clipboard: Optional[Callable[[], Any]], kind: str
    ):
        if read_clipboard is not None:
            return read_clipboard, "custom"
        try:
            native = create_native_reader(ClipboardWatcher._reader_kind(kind))
        except Exception as exc:
            LOGGER.warning("Could not create a native clipboard reader: %s", exc)
            native = None
        if native is None:
            return pyperclip.paste, "pyperclip"
        return _ReaderWithFallback(native), getattr(native, "name", "native")

    def start(self) -> None:
        backend = self._backend
        if backend is None or self._stopped:
            return
        if self._started:
            return
        self._started = True
        try:
            backend.start()
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            LOGGER.warning("Clipboard backend %s unavailable: %s", backend.name, reason)
            self._fallback_reason = reason
            self._switch_to_fallback()

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            backends = list(self._retired)
            if self._backend is not None:
                backends.append(self._backend)
            self._retired.clear()
            self._backend = None
        seen = set()
        for backend in backends:
            if id(backend) in seen:
                continue
            seen.add(id(backend))
            try:
                backend.stop()
            except Exception:
                LOGGER.exception("Could not stop clipboard backend %s", backend.name)

    def _handle_failure(self, reason: str) -> None:
        with self._lock:
            if self._stopped or self._fallback_active:
                return
            self._fallback_active = True
            self._fallback_reason = reason
            if self._backend is not None:
                self._retired.append(self._backend)
        self._switch_to_fallback(reason)

    def _switch_to_fallback(self, reason: Optional[str] = None) -> None:
        stopped = False
        with self._lock:
            if self._stopped:
                return
            old = self._backend
            if old is not None and old not in self._retired:
                self._retired.append(old)
            try:
                fallback = self._fallback_factory()
            except Exception as exc:
                LOGGER.exception("Could not create the clipboard fallback: %s", exc)
                self._backend = None
                return
            self._backend = fallback
            self._fallback_active = True
            if reason:
                self._fallback_reason = reason
            stopped = self._stopped
        if stopped:
            try:
                fallback.stop()
            except Exception:
                pass
            return
        try:
            fallback.start()
        except Exception:
            LOGGER.exception("Could not start the clipboard fallback")


def watch_clipboard(on_change: ChangeCallback, **kwargs: Any) -> ClipboardWatcher:
    """Convenience factory used by the GUI and by small integrations."""
    return ClipboardWatcher(on_change, **kwargs)
