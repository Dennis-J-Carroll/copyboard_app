"""
Shared pytest fixtures for Copyboard testing.

Provides isolated temporary file systems, mock clipboard, and
pre-configured board/config instances for every test module.
"""
import os
import sys
import json
import copy
import pytest
from unittest import mock

# ---------------------------------------------------------------------------
#  Ensure the project root is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
#  Fixture: isolated config directory (tmp_path backed)
# ---------------------------------------------------------------------------
@pytest.fixture()
def isolated_config_dir(tmp_path):
    """Create a fresh config directory in tmp_path and monkeypatch the paths
    used by config_manager and core so they never touch the real home dir."""
    config_dir = tmp_path / "copyboard"
    config_dir.mkdir()
    return str(config_dir)


@pytest.fixture()
def fresh_config(isolated_config_dir, monkeypatch):
    """Return a brand-new ConfigManager that reads/writes inside tmp_path."""
    from copyboard_extension import config_manager

    monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
    monkeypatch.setattr(
        config_manager,
        "CONFIG_FILE",
        os.path.join(isolated_config_dir, "config.json"),
    )
    mgr = config_manager.ConfigManager()
    return mgr


# ---------------------------------------------------------------------------
#  Fixture: isolated board (core module patched)
# ---------------------------------------------------------------------------
@pytest.fixture()
def isolated_board(isolated_config_dir, monkeypatch):
    """Patch core module globals to use a temp directory and return a helper
    that can manipulate the board without touching the real filesystem.

    Yields a dict with convenience keys:
        board_file  – path to transient board.json
        add(text)   – shortcut to core.copy_to_board(text)
        get()       – shortcut to core.get_board()
        clear()     – shortcut to core.clear_board()
        size()      – shortcut to core.get_board_size()
    """
    from copyboard_extension import core

    board_file = os.path.join(isolated_config_dir, "board.json")

    monkeypatch.setattr(core, "BOARD_DIR", isolated_config_dir)
    monkeypatch.setattr(core, "BOARD_FILE", board_file)

    # Reset in-memory state (handle case where _board was reassigned to non-list)
    core._board = []
    core._board_modified = False
    core._board_loaded = False
    core._changes_since_save = 0
    # Restore MAX_BOARD_SIZE to a safe default (tests like set_max_board_size
    # mutate the module-level global and monkeypatch doesn't catch it)
    original_max = core.MAX_BOARD_SIZE
    core.MAX_BOARD_SIZE = 10

    # Force reload from the (empty) temp dir
    core._load_board(force=True)

    yield {
        "board_file": board_file,
        "add": lambda text: core.copy_to_board(text),
        "get": core.get_board,
        "clear": core.clear_board,
        "size": core.get_board_size,
    }

    # Cleanup: reset state again (safe assignment, not .clear())
    core._board = []
    core._board_modified = False
    core._board_loaded = False
    core.MAX_BOARD_SIZE = original_max


# ---------------------------------------------------------------------------
#  Fixture: mock clipboard (prevents touching system clipboard)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_clipboard(monkeypatch):
    """Replace pyperclip.copy / pyperclip.paste with an in-memory buffer so
    tests never touch the real system clipboard."""
    _clipboard_buf = {"content": ""}

    def _mock_copy(text):
        _clipboard_buf["content"] = text

    def _mock_paste():
        return _clipboard_buf["content"]

    monkeypatch.setattr("pyperclip.copy", _mock_copy)
    monkeypatch.setattr("pyperclip.paste", _mock_paste)

    return _clipboard_buf


# ---------------------------------------------------------------------------
#  Fixture: mock paste helper (no-op key simulation)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_paste_helper(monkeypatch):
    """Prevent paste_helper from actually simulating keystrokes."""
    from copyboard_extension import paste_helper

    monkeypatch.setattr(paste_helper, "paste_current_clipboard", lambda: True)
    monkeypatch.setattr(paste_helper, "paste_with_delay", lambda delay_ms=100: True)


# ---------------------------------------------------------------------------
#  Fixture: mock keyboard library
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_keyboard(monkeypatch):
    """Provide a fake keyboard module for hotkey tests."""
    from copyboard_extension import hotkeys

    # Clean up any leaked state from previous tests
    hotkeys._active_hotkeys.clear()
    hotkeys._action_callbacks.clear()

    registered = {}

    class FakeKeyboard:
        @staticmethod
        def add_hotkey(key, callback, **kwargs):
            registered[key] = callback

        @staticmethod
        def remove_hotkey(key):
            if key in registered:
                del registered[key]
            else:
                raise KeyError(f"Hotkey {key!r} not registered")

        @staticmethod
        def press_and_release(key):
            if key in registered:
                registered[key]()

    fake_kb = FakeKeyboard()

    from copyboard_extension import hotkeys
    monkeypatch.setattr(hotkeys, "KEYBOARD_AVAILABLE", True)
    monkeypatch.setattr(hotkeys, "keyboard", fake_kb)

    return {"registered": registered, "keyboard": fake_kb}
