"""
Edge-case and stress tests – push the app to its limits and verify
graceful behaviour under adversarial inputs.
"""
import os
import json
import time
import tempfile
import threading
import pytest

from copyboard_extension import core


class TestRapidCopying:
    """Performance under rapid sequential additions."""

    @pytest.mark.slow
    def test_add_100_items_no_errors(self, isolated_board, monkeypatch):
        """Adding 100+ items rapidly should not crash."""
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 200)
        for i in range(120):
            isolated_board["add"](f"rapid-{i}")
        assert isolated_board["size"]() == 120

    @pytest.mark.slow
    def test_add_100_items_with_small_max(self, isolated_board, monkeypatch):
        """Adding 100+ items with a small max should trim to max size."""
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 10)
        for i in range(100):
            isolated_board["add"](f"item-{i}")
        assert isolated_board["size"]() == 10
        # Newest items preserved
        assert isolated_board["get"]()[0] == "item-99"


class TestVeryLargeText:
    """Handling enormous clipboard entries."""

    def test_large_text_10kb(self, isolated_board):
        large = "A" * 10_000
        isolated_board["add"](large)
        assert isolated_board["get"]()[0] == large

    @pytest.mark.slow
    def test_large_text_1mb(self, isolated_board):
        """1 MB of text should be storable and retrievable."""
        large = "B" * 1_000_000
        isolated_board["add"](large)
        assert len(isolated_board["get"]()[0]) == 1_000_000

    def test_large_text_preview_truncated(self, isolated_board):
        """Preview of a huge item should be short."""
        large = "C" * 50_000
        isolated_board["add"](large)
        previews = core.get_board_preview(30)
        assert len(previews[0]) < 100  # well under 50k

    @pytest.mark.slow
    def test_large_text_persistence(self, isolated_board):
        """Large text round-trips through save/load."""
        large = "D" * 500_000
        isolated_board["add"](large)
        core.force_save()
        reloaded = core.reload_board()
        assert reloaded[0] == large


class TestSpecialCharacters:
    """Unicode, control characters, and other oddities."""

    def test_unicode_emoji(self, isolated_board):
        isolated_board["add"]("Hello 🌍🔥✨")
        assert "🌍" in isolated_board["get"]()[0]

    def test_null_bytes(self, isolated_board):
        isolated_board["add"]("null\x00byte")
        assert len(isolated_board["get"]()) == 1

    def test_multiline(self, isolated_board):
        text = "line1\nline2\nline3"
        isolated_board["add"](text)
        assert isolated_board["get"]()[0] == text

    def test_tab_characters(self, isolated_board):
        text = "col1\tcol2\tcol3"
        isolated_board["add"](text)
        assert "\t" in isolated_board["get"]()[0]

    def test_json_special_chars(self, isolated_board):
        """Strings with characters that could break JSON encoding."""
        text = '{"key":"value","nested":{"a":1}}'
        isolated_board["add"](text)
        core.force_save()
        reloaded = core.reload_board()
        assert reloaded[0] == text


class TestCorruptFiles:
    """Handling corrupt or unexpected file content."""

    def test_corrupt_board_json(self, isolated_board):
        """Writing garbage to board.json should not crash on load."""
        with open(isolated_board["board_file"], "w") as f:
            f.write("{{{{NOT JSON}}}}")
        loaded = core._load_board(force=True)
        assert loaded == []

    def test_board_json_is_string(self, isolated_board):
        """board.json containing a string instead of a list."""
        with open(isolated_board["board_file"], "w") as f:
            json.dump("just a string", f)
        # core._load_board will load it as-is (it's valid JSON).
        # But it won't be a list, which could cause issues.
        loaded = core._load_board(force=True)
        # The module trusts the file – this test documents that behaviour
        assert loaded is not None

    def test_board_json_is_number(self, isolated_board):
        """board.json containing a number instead of a list."""
        with open(isolated_board["board_file"], "w") as f:
            json.dump(42, f)
        loaded = core._load_board(force=True)
        assert loaded is not None

    def test_empty_board_file(self, isolated_board):
        """An empty file should be handled gracefully."""
        with open(isolated_board["board_file"], "w") as f:
            f.write("")
        loaded = core._load_board(force=True)
        assert loaded == []

    def test_binary_board_file(self, isolated_board):
        """Binary garbage should not crash the loader."""
        with open(isolated_board["board_file"], "wb") as f:
            f.write(os.urandom(256))
        loaded = core._load_board(force=True)
        assert loaded == []


class TestConcurrentAccess:
    """Simulated concurrent usage scenarios."""

    def test_parallel_adds_no_crash(self, isolated_board, monkeypatch):
        """Multiple threads adding items should not corrupt state."""
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 100)
        errors = []

        def adder(prefix, count):
            try:
                for i in range(count):
                    core.copy_to_board(f"{prefix}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=adder, args=(f"t{n}", 25))
            for n in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during parallel adds: {errors}"
        # Board should have items (exact number depends on race conditions
        # and deduplication logic, but should not be zero)
        assert isolated_board["size"]() > 0


class TestBoundaryValues:
    """Edge cases around index boundaries."""

    def test_drop_item_at_boundary(self, isolated_board):
        isolated_board["add"]("only")
        assert core.drop_item(0) is True
        assert isolated_board["size"]() == 0

    def test_paste_from_board_last_item(self, isolated_board, mock_clipboard):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["add"]("c")
        # Index 2 = last item = "a"
        assert core.paste_from_board(2, auto_paste=False) is True
        assert mock_clipboard["content"] == "a"

    def test_paste_combination_single_item(self, isolated_board, mock_clipboard):
        isolated_board["add"]("solo")
        assert core.paste_combination([0], auto_paste=False) is True
        assert mock_clipboard["content"] == "solo"

    def test_paste_combination_all_items(self, isolated_board, mock_clipboard):
        isolated_board["add"]("c")
        isolated_board["add"]("b")
        isolated_board["add"]("a")
        assert core.paste_combination([0, 1, 2], auto_paste=False) is True
        assert mock_clipboard["content"] == "abc"

    def test_set_max_board_size_to_current_size(self, isolated_board, monkeypatch):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 10)
        for i in range(5):
            isolated_board["add"](f"item-{i}")
        core.set_max_board_size(5)
        assert isolated_board["size"]() == 5

    def test_max_board_size_one(self, isolated_board, monkeypatch):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 1)
        isolated_board["add"]("first")
        isolated_board["add"]("second")
        assert isolated_board["size"]() == 1
        assert isolated_board["get"]()[0] == "second"


class TestHotkeySpam:
    """Repeated rapid hotkey triggering (simulated)."""

    def test_rapid_paste_calls(self, isolated_board, mock_clipboard):
        """Calling paste_from_board many times in succession should not crash."""
        isolated_board["add"]("spam")
        for _ in range(50):
            core.paste_from_board(0, auto_paste=False)
        assert mock_clipboard["content"] == "spam"

    def test_rapid_copy_and_paste(self, isolated_board, mock_clipboard, monkeypatch):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 10)
        for i in range(50):
            core.copy_to_board(f"item-{i}")
            core.paste_from_board(0, auto_paste=False)
        assert mock_clipboard["content"].startswith("item-")


class TestConfigEdgeCases:
    """Edge cases around config interactions with board."""

    def test_board_size_from_config_negative(self, isolated_board):
        """Setting a negative max through set_max_board_size should clamp to 1."""
        core.set_max_board_size(-5)
        assert core.MAX_BOARD_SIZE == 1

    def test_board_persists_through_size_change(self, isolated_board, monkeypatch):
        """Items that fit within the new max survive a resize."""
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 10)
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["add"]("c")
        core.set_max_board_size(2)
        assert isolated_board["size"]() == 2
        assert isolated_board["get"]() == ["c", "b"]
