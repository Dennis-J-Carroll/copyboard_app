"""Unit tests for the pure presentation helpers used by the revolver UI."""

from copyboard_extension.copyboard_gui import classify_clip, compact_preview


def test_classifies_links():
    assert classify_clip("https://example.com/path") == ("LINK", "↗")


def test_classifies_code():
    kind, mark = classify_clip("def hello():\n    return 42")
    assert kind == "CODE"
    assert mark == "{ }"


def test_classifies_multiline_plain_text():
    assert classify_clip("first line\nsecond line")[0] == "MULTILINE"


def test_classifies_short_text():
    assert classify_clip("remember the milk") == ("TEXT", "T")


def test_compact_preview_flattens_and_truncates():
    preview = compact_preview("one\n\ntwo   three", limit=12)
    assert preview == "one two thr…"
