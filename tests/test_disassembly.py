"""Tests for tag-driven scene disassembly and the `disassemble` command."""
import io
import json

import pytest

from copyboard_extension import core, disassembly
from copyboard_extension.cli import create_parser, main


SCENE = """A rain-soaked street at midnight.

@ALICE: You're late.
@BOB: The road was long.

@ALICE:
It always is.
The rain never stopped.

@BOB: Typical.
"""


def _write_scene(tmp_path, text=SCENE):
    path = tmp_path / "scene.txt"
    path.write_text(text, encoding="utf-8")
    return path


class TestParsing:
    def test_inline_and_block_cues(self):
        cues, preamble_lines, preamble_characters, total_lines = (
            disassembly.parse_tagged_text(SCENE)
        )
        assert [cue.tag for cue in cues] == ["ALICE", "BOB", "ALICE", "BOB"]
        assert preamble_lines == 2
        assert preamble_characters == len("A rain-soaked street at midnight.") + 2
        assert total_lines == len(SCENE.splitlines())

    def test_transcript_joins_blocks_with_a_blank_line(self):
        plan = disassembly.plan_disassembly(SCENE, 10)
        alice = plan.voices[0]
        assert alice.tag == "ALICE"
        assert alice.text == (
            "You're late.\n\n"
            "It always is.\nThe rain never stopped."
        )
        assert alice.cues == 2
        assert alice.lines == 4
        assert alice.first_line == 3

    def test_tags_group_case_insensitively(self):
        plan = disassembly.plan_disassembly(
            "@ALICE: One.\n@alice: Two.\n@Alice: Three.\n", 10
        )
        assert len(plan.voices) == 1
        assert plan.voices[0].tag == "ALICE"
        assert plan.voices[0].text == "One.\n\nTwo.\n\nThree."

    def test_tag_may_contain_spaces(self):
        plan = disassembly.plan_disassembly("@Old Man: Mind the step.\n", 10)
        assert plan.voices[0].tag == "Old Man"

    def test_colons_inside_content_are_preserved(self):
        plan = disassembly.plan_disassembly('@ALICE: He said: "no".\n', 10)
        assert plan.voices[0].text == 'He said: "no".'

    def test_crlf_is_accepted(self):
        plan = disassembly.plan_disassembly("@A: one\r\n@B: two\r\n", 10)
        assert [voice.tag for voice in plan.voices] == ["A", "B"]

    def test_empty_tag_is_rejected(self):
        with pytest.raises(disassembly.DisassemblyError, match="empty tag"):
            disassembly.parse_tagged_text("@: text\n")

    def test_overlong_tag_is_rejected(self):
        tag = "A" * (disassembly.MAX_TAG_LENGTH + 1)
        with pytest.raises(disassembly.DisassemblyError, match="longer"):
            disassembly.parse_tagged_text(f"@{tag}: text\n")

    def test_text_without_cues_is_rejected(self):
        with pytest.raises(disassembly.DisassemblyError, match="no @TAG"):
            disassembly.plan_disassembly("just prose\n", 10)

    def test_empty_cues_are_rejected(self):
        with pytest.raises(disassembly.DisassemblyError, match="empty"):
            disassembly.plan_disassembly("@ALICE:\n\n@BOB:\n", 10)

    def test_voice_order_is_first_appearance(self):
        plan = disassembly.plan_disassembly(
            "@BOB: b\n@ALICE: a\n@BOB: b2\n@CAROL: c\n", 10
        )
        assert [voice.tag for voice in plan.voices] == ["BOB", "ALICE", "CAROL"]

    def test_capacity_overflow_is_rejected_with_tag_names(self):
        with pytest.raises(disassembly.DisassemblyError, match="A, B, C"):
            disassembly.plan_disassembly("@A: a\n@B: b\n@C: c\n", 2)

    def test_plan_to_dict_is_json_ready(self):
        plan = disassembly.plan_disassembly(SCENE, 10)
        payload = json.loads(json.dumps(disassembly.plan_to_dict(plan)))
        assert [voice["tag"] for voice in payload["voices"]] == ["ALICE", "BOB"]
        assert payload["voices"][0]["chamber"] == 1
        assert payload["voices"][0]["label"] == "01"
        assert payload["voices"][0]["text"].startswith("You're late.")


class TestReplaceBoard:
    def test_replaces_in_chamber_order_and_persists(self, isolated_board):
        isolated_board["add"]("old")
        core.replace_board(["alice", "bob"])
        assert isolated_board["get"]() == ["alice", "bob"]
        with open(isolated_board["board_file"], "r", encoding="utf-8") as handle:
            assert json.load(handle) == ["alice", "bob"]

    def test_drops_items_beyond_capacity(self, isolated_board, monkeypatch):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 2)
        core.replace_board(["a", "b", "c"])
        assert isolated_board["get"]() == ["a", "b"]

    def test_empty_list_clears(self, isolated_board):
        isolated_board["add"]("old")
        core.replace_board([])
        assert isolated_board["get"]() == []


class TestDisassembleCommand:
    def test_parser_accepts_the_command(self):
        args = create_parser().parse_args(["disassemble", "scene.txt", "--dry-run"])
        assert args.command == "disassemble"
        assert args.dry_run is True
        assert args.source == "scene.txt"

    def test_dry_run_leaves_the_cylinder_untouched(
        self, isolated_board, tmp_path, capsys
    ):
        isolated_board["add"]("existing")
        result = main(
            ["disassemble", str(_write_scene(tmp_path)), "--dry-run"]
        )
        assert result == 0
        assert isolated_board["get"]() == ["existing"]
        out = capsys.readouterr().out
        assert "ALICE" in out and "BOB" in out
        assert "Dry run" in out

    def test_apply_refuses_to_discard_rounds_without_replace(
        self, isolated_board, tmp_path, capsys
    ):
        isolated_board["add"]("existing")
        result = main(["disassemble", str(_write_scene(tmp_path))])
        assert result == 1
        assert isolated_board["get"]() == ["existing"]
        assert "--replace" in capsys.readouterr().out

    def test_apply_with_replace_loads_one_chamber_per_tag(
        self, isolated_board, tmp_path
    ):
        isolated_board["add"]("existing")
        result = main(
            ["disassemble", str(_write_scene(tmp_path)), "--replace"]
        )
        assert result == 0
        board = isolated_board["get"]()
        assert len(board) == 2
        assert board[0].startswith("You're late.")
        assert board[1].startswith("The road was long.")
        assert "@ALICE" not in board[0]

    def test_apply_on_an_empty_cylinder_needs_no_replace(
        self, isolated_board, tmp_path
    ):
        result = main(["disassemble", str(_write_scene(tmp_path))])
        assert result == 0
        assert isolated_board["size"]() == 2

    def test_json_reports_chamber_assignments(
        self, isolated_board, tmp_path, capsys
    ):
        result = main(
            ["--json", "disassemble", str(_write_scene(tmp_path)), "--dry-run"]
        )
        assert result == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["applied"] is False
        assert payload["source"].endswith("scene.txt")
        assert [voice["tag"] for voice in payload["voices"]] == ["ALICE", "BOB"]
        assert payload["voices"][0]["chamber"] == 1

    def test_stdin_source(self, isolated_board, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("@A: one\n@B: two\n"))
        result = main(["disassemble", "-", "--dry-run"])
        assert result == 0
        assert "2 tag" in capsys.readouterr().out

    def test_clipboard_is_the_default_source(
        self, isolated_board, mock_clipboard, capsys
    ):
        mock_clipboard["content"] = "@A: one\n@B: two\n"
        result = main(["disassemble", "--dry-run"])
        assert result == 0
        assert "2 tag" in capsys.readouterr().out

    def test_missing_file_returns_an_error(self, isolated_board, capsys):
        result = main(["disassemble", "/no/such/scene.txt", "--dry-run"])
        assert result == 1
        assert "could not read" in capsys.readouterr().out

    def test_untagged_text_returns_an_error(
        self, isolated_board, tmp_path, capsys
    ):
        path = tmp_path / "plain.txt"
        path.write_text("just prose\n", encoding="utf-8")
        result = main(["disassemble", str(path), "--dry-run"])
        assert result == 1
        assert "no @TAG" in capsys.readouterr().out

    def test_too_many_tags_is_reported(
        self, isolated_board, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(core, "MAX_BOARD_SIZE", 2)
        path = tmp_path / "many.txt"
        path.write_text("@A: a\n@B: b\n@C: c\n", encoding="utf-8")
        result = main(["disassemble", str(path), "--dry-run"])
        assert result == 1
        assert "3 tags" in capsys.readouterr().out
