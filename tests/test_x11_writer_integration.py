"""Integration tests for the native X11 writer against a real X server.

These tests are skipped when ``Xvfb`` is not installed.  CI can opt in by
installing the ``xvfb`` package (which also brings in ``xkbcomp``); the
fixture starts a private server on a free display and points ``DISPLAY`` at
it, so the tests never touch the developer's clipboard.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from copyboard_extension.native_clipboard import (
    _X11Session,
    X11ClipboardWriter,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name == "nt", reason="X11 writer uses POSIX pipes"),
]

_SELECTION_NOTIFY = 31
_PROPERTY_NEW_VALUE = 0


def _free_display() -> str:
    """Pick a display number that has neither a socket nor a lock file."""
    for number in range(90, 200):
        if not Path(f"/tmp/.X11-unix/X{number}").exists() and not Path(
            f"/tmp/.X{number}-lock"
        ).exists():
            return f":{number}"
    raise RuntimeError("no free X11 display number was found")


def _display_is_usable(display: str) -> bool:
    """Open and close a real X connection without changing global state."""
    previous = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = display
    try:
        session = _X11Session()
        session.close()
        return True
    except Exception:
        return False
    finally:
        if previous is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = previous


@pytest.fixture()
def xvfb_display(tmp_path, monkeypatch):
    """Run a private Xvfb server and make its display the active one."""
    binary = shutil.which("Xvfb")
    if binary is None:
        pytest.skip("Xvfb is not installed")

    display = _free_display()
    log_path = tmp_path / "xvfb.log"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [
                binary,
                display,
                "-screen",
                "0",
                "800x600x24",
                "-nolisten",
                "tcp",
                "-ac",
                "-noreset",
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    try:
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log = log_path.read_text(errors="replace")
                pytest.fail(
                    f"Xvfb exited before becoming ready (exit "
                    f"{process.returncode}):\n{log}"
                )
            if _display_is_usable(display):
                break
            time.sleep(0.05)
        else:
            log = log_path.read_text(errors="replace")
            pytest.fail(f"Xvfb did not become ready on {display}:\n{log}")

        monkeypatch.setenv("DISPLAY", display)
        yield display
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


def _wait_for_selection_notify(session, window, clipboard, target):
    deadline = time.monotonic() + 5.0
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


def _request_text(session, target_name: bytes = b"UTF8_STRING"):
    window = session.create_window()
    clipboard = session.intern(b"CLIPBOARD")
    property_atom = session.intern(b"COPYBOARD_INTEGRATION")
    target = session.intern(target_name)
    session.convert(clipboard, target, property_atom, window)
    notify = _wait_for_selection_notify(session, window, clipboard, target)
    assert notify is not None, "the writer did not answer the selection request"
    assert notify["property"] == property_atom
    return window, clipboard, property_atom, target


def _read_plain_property(session, window, property_atom):
    actual_type, fmt, _data, remaining = session.read_property(
        window, property_atom, length=0
    )
    assert actual_type != session.incr
    assert fmt == 8

    chunks = []
    offset = 0
    while remaining:
        _type, fmt, chunk, remaining = session.read_property(
            window, property_atom, offset=offset
        )
        assert fmt == 8
        chunks.append(chunk)
        offset += (len(chunk) + 3) // 4
    session.delete_property(window, property_atom)
    return b"".join(chunks)


def test_x11_writer_serves_utf8_to_a_real_requestor(xvfb_display):
    payload = "Xvfb says hello — 你好"
    writer = X11ClipboardWriter()
    session = _X11Session()
    try:
        writer.write(payload)
        window, _clipboard, property_atom, target = _request_text(session)

        assert target == session.intern(b"UTF8_STRING")
        assert _read_plain_property(session, window, property_atom) == payload.encode(
            "utf-8"
        )
    finally:
        session.close()
        writer.close(preserve=False)


def test_x11_writer_serves_large_text_with_incr_to_a_real_requestor(xvfb_display):
    payload = "0123456789" * 400
    writer = X11ClipboardWriter(chunk_size=1024)
    session = _X11Session()
    try:
        writer.write(payload)
        window, _clipboard, property_atom, _target = _request_text(session)

        actual_type, fmt, _data, _remaining = session.read_property(
            window, property_atom, length=0
        )
        assert actual_type == session.incr
        assert fmt == 32

        # Deleting the INCR property acknowledges the transfer and asks the
        # writer for the first chunk.
        session.read_property(window, property_atom, delete=True)

        chunks = []
        deadline = time.monotonic() + 5.0
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, "timed out receiving the INCR transfer"
            event = session.next_event(remaining)
            assert event is not None, "timed out waiting for an INCR chunk"
            if (
                event.get("type") != 28
                or event.get("window") != window
                or event.get("atom") != property_atom
                or event.get("state") != _PROPERTY_NEW_VALUE
            ):
                continue
            _type, fmt, chunk, _remaining = session.read_property(
                window, property_atom, delete=True
            )
            assert fmt == 8
            if not chunk:
                break
            assert len(chunk) <= 1024
            chunks.append(chunk)

        assert len(chunks) > 1
        assert b"".join(chunks) == payload.encode("utf-8")
    finally:
        session.close()
        writer.close(preserve=False)
