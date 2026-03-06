"""
Tests for Clipboard Board Logic – adding items, enforcing max size,
copying from board to clipboard, clearing, previews, and persistence.
"""
import os
import json
import pytest

from copyboard_extension import core


class TestAddItems:
    """Adding items to the board."""

    def test_add_single_item(self, isolated_board):
        isolated_board["add"]("hello")
        assert isolated_board["get"]() == ["hello"]

    def test_add_multiple_items_ordered_newest_first(self, isolated_board):
        isolated_board["add"]("first")
        isolated_board["add"]("second")
        isolated_board["add"]("third")
        board = isolated_board["get"]()
        assert board == ["third", "second", "first"]

    def test_add_duplicate_at_top_is_noop(self, isolated_board):
        """Consecutive identical adds should NOT create duplicates."""
        isolated_board["add"]("dup")
        isolated_board["add"]("dup")
        assert len(isolated_board["get"]()) == 1

    def test_add_duplicate_not_at_top_is_allowed(self, isolated_board):
        """The same text is allowed if something else is on top."""
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["add"]("a")
        assert isolated_board["get"]() == ["a", "b", "a"]

    def test_add_empty_string(self, isolated_board):
        """Empty strings should still be storable."""
        isolated_board["add"]("")
        assert isolated_board["get"]() == [""]


class TestMaxBoardSize:
    """Enforcing the max-item limit."""

    def test_items_beyond_max_are_evicted(self, isolated_board, monkeypatch):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 3)
        for i in range(6):
            isolated_board["add"](f"item-{i}")

        board = isolated_board["get"]()
        assert len(board) == 3
        # Most recent items kept
        assert board[0] == "item-5"
        assert board[1] == "item-4"
        assert board[2] == "item-3"

    def test_set_max_board_size_trims(self, isolated_board, monkeypatch):
        """Dynamically lowering the max trims the board."""
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 20)
        for i in range(10):
            isolated_board["add"](f"item-{i}")
        assert isolated_board["size"]() == 10

        core.set_max_board_size(5)
        assert isolated_board["size"]() == 5
        # Most recent items survive
        assert isolated_board["get"]()[0] == "item-9"

    def test_set_max_board_size_min_one(self, isolated_board):
        """Max size cannot be set below 1."""
        core.set_max_board_size(0)
        assert core.MAX_BOARD_SIZE == 1


class TestClearBoard:
    """Clearing the board."""

    def test_clear_empties_board(self, isolated_board):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["clear"]()
        assert isolated_board["get"]() == []

    def test_clear_empty_board_is_safe(self, isolated_board):
        isolated_board["clear"]()
        assert isolated_board["get"]() == []


class TestDropItem:
    """Removing individual items."""

    def test_drop_by_index(self, isolated_board):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["add"]("c")
        assert core.drop_item(1)  # remove "b"
        assert isolated_board["get"]() == ["c", "a"]

    def test_drop_oldest_default(self, isolated_board):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        assert core.drop_item(None)  # removes oldest = "a"
        assert isolated_board["get"]() == ["b"]

    def test_drop_out_of_range_returns_false(self, isolated_board):
        isolated_board["add"]("a")
        assert core.drop_item(99) is False

    def test_drop_empty_board_returns_false(self, isolated_board):
        assert core.drop_item(0) is False


class TestGetBoard:
    """Reading the board."""

    def test_get_board_returns_copy(self, isolated_board):
        """Mutations on the returned list must not affect internal state."""
        isolated_board["add"]("item")
        board = isolated_board["get"]()
        board.append("sneaky")
        assert isolated_board["size"]() == 1

    def test_get_board_item_valid(self, isolated_board):
        isolated_board["add"]("hello")
        assert core.get_board_item(0) == "hello"

    def test_get_board_item_out_of_range(self, isolated_board):
        assert core.get_board_item(5) is None


class TestBoardPreview:
    """Preview generation."""

    def test_preview_truncates_long_items(self, isolated_board):
        long_text = "x" * 100
        isolated_board["add"](long_text)
        previews = core.get_board_preview(30)
        assert "..." in previews[0]
        # 30 chars + "..." suffix
        assert len(previews[0]) < len(long_text) + 10

    def test_preview_replaces_newlines(self, isolated_board):
        isolated_board["add"]("line1\nline2")
        previews = core.get_board_preview()
        assert "↵" in previews[0]


class TestPasteFromBoard:
    """Copying from board to system clipboard (mocked)."""

    def test_paste_from_board_index_zero(self, isolated_board, mock_clipboard):
        isolated_board["add"]("hello")
        result = core.paste_from_board(0, auto_paste=False)
        assert result is True
        assert mock_clipboard["content"] == "hello"

    def test_paste_from_board_specific_index(self, isolated_board, mock_clipboard):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        isolated_board["add"]("c")
        result = core.paste_from_board(2, auto_paste=False)
        assert result is True
        assert mock_clipboard["content"] == "a"

    def test_paste_from_board_out_of_range(self, isolated_board):
        assert core.paste_from_board(0, auto_paste=False) is False

    def test_paste_from_board_negative_index(self, isolated_board):
        isolated_board["add"]("hello")
        assert core.paste_from_board(-1, auto_paste=False) is False


class TestPasteAll:
    """Concatenating and pasting all items."""

    def test_paste_all_concatenation(self, isolated_board, mock_clipboard):
        isolated_board["add"]("world")
        isolated_board["add"]("hello")
        result = core.paste_all(auto_paste=False)
        assert result is True
        assert mock_clipboard["content"] == "hello\nworld"

    def test_paste_all_empty_board(self, isolated_board):
        assert core.paste_all(auto_paste=False) is False


class TestPasteCombination:
    """Pasting a subset of items."""

    def test_paste_combination(self, isolated_board, mock_clipboard):
        isolated_board["add"]("c")
        isolated_board["add"]("b")
        isolated_board["add"]("a")
        result = core.paste_combination([0, 2], auto_paste=False)
        assert result is True
        assert mock_clipboard["content"] == "ac"

    def test_paste_combination_invalid_index(self, isolated_board):
        isolated_board["add"]("only")
        assert core.paste_combination([0, 5], auto_paste=False) is False

    def test_paste_combination_empty_board(self, isolated_board):
        assert core.paste_combination([0], auto_paste=False) is False


class TestBoardPersistence:
    """Saving and loading board to/from disk."""

    def test_force_save_creates_file(self, isolated_board):
        isolated_board["add"]("persistent")
        core.force_save()
        board_file = isolated_board["board_file"]
        assert os.path.exists(board_file)
        with open(board_file, "r") as f:
            data = json.load(f)
        assert data == ["persistent"]

    def test_reload_board_from_disk(self, isolated_board):
        board_file = isolated_board["board_file"]
        with open(board_file, "w") as f:
            json.dump(["from-disk"], f)
        reloaded = core.reload_board()
        assert reloaded == ["from-disk"]

    def test_corrupt_board_file_handled(self, isolated_board):
        board_file = isolated_board["board_file"]
        with open(board_file, "w") as f:
            f.write("NOT VALID JSON {{")
        loaded = core._load_board(force=True)
        assert loaded == []


class TestQuickCopyPaste:
    """One-shot copy-paste bypassing the board."""

    def test_quick_copy_paste_sets_clipboard(self, isolated_board, mock_clipboard):
        result = core.quick_copy_paste("quick")
        assert result is True
        assert mock_clipboard["content"] == "quick"
