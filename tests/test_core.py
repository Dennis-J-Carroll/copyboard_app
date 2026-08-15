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
