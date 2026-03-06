"""
Tests for Import / Export – JSON structure validity, board serialisation,
config export, and handling of malformed or partial import files.
"""
import os
import json
import pytest

from copyboard_extension import core
from copyboard_extension.config_manager import DEFAULT_CONFIG


# ── Helpers ──────────────────────────────────────────────────────────────
def _export_board(board_file: str) -> dict:
    """Simulate an export operation: read the board from disk and return
    a portable JSON structure with board items and metadata."""
    if os.path.exists(board_file):
        with open(board_file, "r") as f:
            items = json.load(f)
    else:
        items = []
    return {
        "version": "1.0",
        "type": "copyboard_export",
        "board": items,
    }


def _import_board(board_file: str, import_data: dict, merge: bool = False):
    """Simulate an import operation: load JSON data into the board.

    If merge=True, append new items to the existing board.
    Otherwise overwrite.

    Returns:
        (success: bool, message: str)
    """
    if not isinstance(import_data, dict):
        return False, "Import data is not a JSON object"

    if "board" not in import_data or not isinstance(import_data.get("board"), list):
        return False, "Missing or invalid 'board' key"

    new_items = import_data["board"]

    if merge:
        existing = []
        if os.path.exists(board_file):
            with open(board_file, "r") as f:
                existing = json.load(f)
        combined = new_items + [i for i in existing if i not in new_items]
        with open(board_file, "w") as f:
            json.dump(combined, f)
    else:
        with open(board_file, "w") as f:
            json.dump(new_items, f)

    return True, "Import successful"


def _export_full(board_file: str, config_mgr) -> dict:
    """Export both board and preferences in one bundle."""
    board_data = _export_board(board_file)
    return {
        **board_data,
        "preferences": {
            "board": config_mgr.get_section("board"),
            "window": config_mgr.get_section("window"),
            "hotkeys": config_mgr.get_section("hotkeys"),
        },
    }


# ── Tests ────────────────────────────────────────────────────────────────
class TestExportBoard:
    """Exporting the board produces valid JSON."""

    def test_export_contains_required_keys(self, isolated_board):
        isolated_board["add"]("item-a")
        isolated_board["add"]("item-b")
        core.force_save()

        data = _export_board(isolated_board["board_file"])
        assert data["version"] == "1.0"
        assert data["type"] == "copyboard_export"
        assert isinstance(data["board"], list)

    def test_export_items_match_board(self, isolated_board):
        isolated_board["add"]("x")
        isolated_board["add"]("y")
        core.force_save()

        data = _export_board(isolated_board["board_file"])
        assert data["board"] == ["y", "x"]

    def test_export_empty_board(self, isolated_board):
        core.force_save()
        data = _export_board(isolated_board["board_file"])
        assert data["board"] == []


class TestExportFull:
    """Exporting board + preferences."""

    def test_full_export_includes_prefs(self, isolated_board, fresh_config):
        isolated_board["add"]("hello")
        core.force_save()
        data = _export_full(isolated_board["board_file"], fresh_config)
        assert "preferences" in data
        assert "board" in data["preferences"]
        assert "hotkeys" in data["preferences"]
        assert "window" in data["preferences"]

    def test_full_export_prefs_values(self, isolated_board, fresh_config):
        fresh_config.set("board", "max_items", 42)
        core.force_save()
        data = _export_full(isolated_board["board_file"], fresh_config)
        assert data["preferences"]["board"]["max_items"] == 42


class TestImportBoard:
    """Importing board data."""

    def test_import_valid_overwrites(self, isolated_board):
        isolated_board["add"]("existing")
        core.force_save()

        import_data = {
            "version": "1.0",
            "type": "copyboard_export",
            "board": ["imported-a", "imported-b"],
        }
        ok, msg = _import_board(isolated_board["board_file"], import_data)
        assert ok is True

        with open(isolated_board["board_file"], "r") as f:
            loaded = json.load(f)
        assert loaded == ["imported-a", "imported-b"]

    def test_import_merge_adds_new_items(self, isolated_board):
        isolated_board["add"]("existing")
        core.force_save()

        import_data = {"board": ["new-item", "existing"]}
        ok, _ = _import_board(isolated_board["board_file"], import_data, merge=True)
        assert ok is True

        with open(isolated_board["board_file"], "r") as f:
            loaded = json.load(f)
        assert "new-item" in loaded
        assert "existing" in loaded
        # "existing" should not be duplicated
        assert loaded.count("existing") == 1


class TestImportInvalid:
    """Handling malformed import data."""

    def test_import_not_dict(self, isolated_board):
        ok, msg = _import_board(isolated_board["board_file"], "just a string")
        assert ok is False
        assert "not a JSON object" in msg

    def test_import_missing_board_key(self, isolated_board):
        ok, msg = _import_board(isolated_board["board_file"], {"version": "1.0"})
        assert ok is False
        assert "Missing" in msg

    def test_import_board_not_list(self, isolated_board):
        ok, msg = _import_board(
            isolated_board["board_file"],
            {"board": "not a list"},
        )
        assert ok is False

    def test_import_with_extra_keys_succeeds(self, isolated_board):
        """Extra keys in the JSON should be ignored, not cause a failure."""
        import_data = {
            "board": ["a", "b"],
            "unknown_field": 42,
            "metadata": {"author": "test"},
        }
        ok, _ = _import_board(isolated_board["board_file"], import_data)
        assert ok is True

    def test_import_empty_board_list(self, isolated_board):
        import_data = {"board": []}
        ok, _ = _import_board(isolated_board["board_file"], import_data)
        assert ok is True
        with open(isolated_board["board_file"], "r") as f:
            assert json.load(f) == []


class TestImportMissingKeys:
    """Import file with partial preference data uses defaults."""

    def test_import_preferences_partial(self, fresh_config):
        """If an import only has 'board' prefs, other sections keep defaults."""
        import_prefs = {"board": {"max_items": 77}}
        for section, values in import_prefs.items():
            for key, val in values.items():
                fresh_config.set(section, key, val)

        assert fresh_config.get("board", "max_items") == 77
        # Window should still have its defaults
        assert fresh_config.get("window", "width") == DEFAULT_CONFIG["window"]["width"]


class TestRoundTrip:
    """Export → Import round-trip integrity."""

    def test_export_then_import_preserves_data(self, isolated_board):
        items = ["alpha", "beta", "gamma"]
        for item in reversed(items):  # add in reverse so newest is first
            isolated_board["add"](item)
        core.force_save()

        exported = _export_board(isolated_board["board_file"])

        # Clear the board
        isolated_board["clear"]()
        core.force_save()
        assert isolated_board["size"]() == 0

        # Import
        ok, _ = _import_board(isolated_board["board_file"], exported)
        assert ok is True

        with open(isolated_board["board_file"], "r") as f:
            reloaded = json.load(f)
        assert reloaded == items
