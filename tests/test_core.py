"""
Smoke tests for core module – ensures the module loads and basic operations
function.  Detailed logic tests live in test_board_logic.py.
"""
import pytest
from copyboard_extension import core


class TestCoreModuleLoads:
    """Verify the module can be imported and basic state is valid."""

    def test_board_is_list(self, isolated_board):
        assert isinstance(isolated_board["get"](), list)

    def test_board_starts_empty(self, isolated_board):
        assert isolated_board["size"]() == 0

    def test_max_board_size_positive(self):
        assert core.MAX_BOARD_SIZE >= 1


class TestCoreRoundTrip:
    """Quick add-then-read sanity check."""

    def test_add_and_retrieve(self, isolated_board):
        isolated_board["add"]("smoke-test")
        assert isolated_board["get"]()[0] == "smoke-test"

    def test_add_and_clear(self, isolated_board):
        isolated_board["add"]("clear-me")
        isolated_board["clear"]()
        assert isolated_board["size"]() == 0


class TestClipboardWriteBoundary:
    """Native writes are preferred, with pyperclip as the safety net."""

    def test_native_write_is_preferred(self, monkeypatch):
        core._reset_app_clipboard_writes()
        calls = []
        monkeypatch.setattr(
            core.native_clipboard,
            "write_clipboard_text",
            lambda text: calls.append(text),
        )
        monkeypatch.setattr(
            core.pyperclip,
            "copy",
            lambda _text: pytest.fail("pyperclip should not be used"),
        )

        core.set_clipboard_text("native text")

        assert calls == ["native text"]
        assert core.is_app_clipboard_write("native text") is True

    def test_native_failure_falls_back_to_pyperclip(self, monkeypatch):
        core._reset_app_clipboard_writes()
        copies = []

        def unavailable(_text):
            raise core.native_clipboard.NativeWriteUnavailable("no display")

        monkeypatch.setattr(
            core.native_clipboard, "write_clipboard_text", unavailable
        )
        monkeypatch.setattr(
            core.pyperclip, "copy", lambda text: copies.append(text)
        )

        core.set_clipboard_text("fallback text")

        assert copies == ["fallback text"]
        assert core.is_app_clipboard_write("fallback text") is True

    def test_total_failure_forgets_the_self_write(self, monkeypatch):
        core._reset_app_clipboard_writes()

        def unavailable(_text):
            raise core.native_clipboard.NativeWriteUnavailable("no display")

        def broken_copy(_text):
            raise RuntimeError("clipboard is gone")

        monkeypatch.setattr(
            core.native_clipboard, "write_clipboard_text", unavailable
        )
        monkeypatch.setattr(core.pyperclip, "copy", broken_copy)

        with pytest.raises(RuntimeError):
            core.set_clipboard_text("lost text")

        assert core.is_app_clipboard_write("lost text") is False


class TestShutdownPersistence:
    """Shutdown must not rewrite the user's board when nothing changed."""

    def test_clean_board_is_not_force_saved(self, monkeypatch):
        save_calls = []
        monkeypatch.setattr(core, "_board_modified", False)
        monkeypatch.setattr(
            core, "_save_board", lambda force=False: save_calls.append(force)
        )

        core._save_pending_board()

        assert save_calls == []

    def test_dirty_board_is_force_saved(self, monkeypatch):
        save_calls = []
        monkeypatch.setattr(core, "_board_modified", True)
        monkeypatch.setattr(
            core, "_save_board", lambda force=False: save_calls.append(force)
        )

        core._save_pending_board()

        assert save_calls == [True]
