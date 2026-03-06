"""
Tests for the CLI module – verifying all subcommands produce correct output
and return codes, with the board and clipboard fully mocked.
"""
import io
import pytest
from unittest import mock

from copyboard_extension import core
from copyboard_extension.cli import main, create_parser


class TestCLIParser:
    """Argument parser validation."""

    def test_parser_has_all_subcommands(self):
        parser = create_parser()
        # Attempt to parse each known subcommand to verify it exists
        for cmd in ["list", "copy", "copyall", "add", "remove", "clear", "paste-combo", "monitor"]:
            try:
                if cmd == "add":
                    parser.parse_args([cmd, "text"])
                elif cmd == "remove":
                    parser.parse_args([cmd, "0"])
                elif cmd == "paste-combo":
                    parser.parse_args([cmd, "0", "1"])
                elif cmd == "monitor":
                    parser.parse_args([cmd, "--seconds", "1"])
                else:
                    parser.parse_args([cmd])
            except SystemExit:
                pytest.fail(f"Parser rejected subcommand '{cmd}'")

    def test_no_command_prints_help(self, capsys):
        result = main([])
        assert result == 1


class TestListCommand:
    """The `list` subcommand."""

    def test_list_empty_board(self, isolated_board, capsys):
        result = main(["list"])
        assert result == 0
        out = capsys.readouterr().out
        assert "empty" in out.lower()

    def test_list_populated_board(self, isolated_board, capsys):
        isolated_board["add"]("item-a")
        isolated_board["add"]("item-b")
        result = main(["list"])
        assert result == 0
        out = capsys.readouterr().out
        assert "2 items" in out


class TestAddCommand:
    """The `add` subcommand."""

    def test_add_text(self, isolated_board, capsys):
        result = main(["add", "hello world"])
        assert result == 0
        assert isolated_board["size"]() >= 1
        out = capsys.readouterr().out
        assert "Added" in out

    def test_add_preserves_order(self, isolated_board):
        main(["add", "first"])
        main(["add", "second"])
        board = isolated_board["get"]()
        assert board[0] == "second"


class TestCopyCommand:
    """The `copy` subcommand."""

    def test_copy_default_index(self, isolated_board, capsys):
        isolated_board["add"]("only-item")
        result = main(["copy"])
        assert result == 0
        out = capsys.readouterr().out
        assert "Copied" in out

    def test_copy_specific_index(self, isolated_board, capsys):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        result = main(["copy", "1"])
        assert result == 0

    def test_copy_invalid_index(self, isolated_board, capsys):
        result = main(["copy", "99"])
        assert result == 1
        out = capsys.readouterr().out
        assert "Error" in out


class TestCopyAllCommand:
    """The `copyall` subcommand."""

    def test_copyall(self, isolated_board, capsys):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        result = main(["copyall"])
        assert result == 0

    def test_copyall_empty(self, isolated_board, capsys):
        result = main(["copyall"])
        assert result == 1


class TestRemoveCommand:
    """The `remove` subcommand."""

    def test_remove_valid_index(self, isolated_board, capsys):
        isolated_board["add"]("target")
        isolated_board["add"]("keep")
        result = main(["remove", "1"])
        assert result == 0
        assert isolated_board["size"]() == 1

    def test_remove_invalid_index(self, isolated_board, capsys):
        result = main(["remove", "99"])
        assert result == 1


class TestClearCommand:
    """The `clear` subcommand."""

    def test_clear(self, isolated_board, capsys):
        isolated_board["add"]("a")
        isolated_board["add"]("b")
        result = main(["clear"])
        assert result == 0
        assert isolated_board["size"]() == 0


class TestPasteComboCommand:
    """The `paste-combo` subcommand."""

    def test_paste_combo_valid(self, isolated_board, capsys):
        isolated_board["add"]("x")
        isolated_board["add"]("y")
        isolated_board["add"]("z")
        result = main(["paste-combo", "0", "2"])
        assert result == 0

    def test_paste_combo_invalid_index(self, isolated_board, capsys):
        isolated_board["add"]("only")
        result = main(["paste-combo", "0", "5"])
        assert result == 1
