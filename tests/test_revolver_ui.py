"""Unit tests for the pure presentation helpers used by the revolver UI."""

from copyboard_extension.copyboard_gui import classify_clip, compact_preview
from copyboard_extension.widget_mode import is_drag_gesture, radial_centers


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


def test_widget_centers_begin_at_twelve_oclock():
    centers = radial_centers(4, 100, 100, 50)
    assert centers[0] == (100.0, 50.0)
    assert centers[1] == (150.0, 100.0)


def test_widget_centers_handle_empty_board():
    assert radial_centers(0, 100, 100, 50) == []


def test_widget_drag_threshold_ignores_pointer_jitter():
    assert not is_drag_gesture((10, 10), (16, 14), threshold=12)
    assert is_drag_gesture((10, 10), (25, 10), threshold=12)
