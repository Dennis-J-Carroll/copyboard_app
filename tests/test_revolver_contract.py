"""
Acceptance contract for the clipboard revolver.

Covers chamber numbering, the 10–16 capacity rule, newest-first insertion
and eviction, read-only firing, suppression of CopyBoard's own clipboard
writes, direct shortcut mapping, widget geometry, and wheel selection.

The Tk-backed tests build the real widget/editor under whatever display is
available (Xvfb in CI) and skip cleanly when none is.
"""
import json
import os
import time

import pytest

from copyboard_extension import chambers, core, hotkeys
from copyboard_extension.chambers import (
    DEFAULT_CHAMBERS,
    MAX_CHAMBERS,
    MIN_CHAMBERS,
    ChamberDial,
    chamber_index,
    chamber_label,
    chamber_number,
    normalize_chamber_count,
)
from copyboard_extension.widget_mode import (
    next_loaded_index,
    wheel_step,
    widget_layout,
)


# ── Chamber numbering ────────────────────────────────────────────────────
class TestChamberNumbering:
    @pytest.mark.parametrize("index, number, label", [(0, 1, "01"), (9, 10, "10"), (15, 16, "16")])
    def test_index_number_label_round_trip(self, index, number, label):
        assert chamber_number(index) == number
        assert chamber_index(number) == index
        assert chamber_label(index) == label
        assert chamber_index(chamber_number(index)) == index

    def test_is_chamber_index_respects_count(self):
        assert chambers.is_chamber_index(0, 10)
        assert chambers.is_chamber_index(9, 10)
        assert not chambers.is_chamber_index(10, 10)
        assert chambers.is_chamber_index(15, 16)
        assert not chambers.is_chamber_index(-1, 16)
        assert not chambers.is_chamber_index(True, 16)
        assert not chambers.is_chamber_index("3", 16)


class TestCapacityNormalisation:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (10, 10),
            (16, 16),
            (12, 12),
            (9, 10),
            (0, 10),
            (-5, 10),
            (17, 16),
            (42, 16),
            ("14", 14),
            (13.0, 13),
            ("lots", DEFAULT_CHAMBERS),
            (None, DEFAULT_CHAMBERS),
            (True, DEFAULT_CHAMBERS),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_chamber_count(raw) == expected

    def test_bounds(self):
        assert MIN_CHAMBERS == 10 and MAX_CHAMBERS == 16 and DEFAULT_CHAMBERS == 10
        assert chambers.is_valid_chamber_count(10)
        assert chambers.is_valid_chamber_count(16)
        assert not chambers.is_valid_chamber_count(17)
        assert not chambers.is_valid_chamber_count("12")


class TestChamberDial:
    def _dial(self, count, clock):
        return ChamberDial(lambda: count, window=0.5, clock=clock)

    def test_single_digits_select_immediately(self):
        now = [0.0]
        dial = self._dial(10, lambda: now[0])
        assert dial.press("1") == 0
        assert dial.press("9") == 8
        assert dial.press("0") == 9

    def test_two_quick_digits_reach_chambers_11_to_16(self):
        now = [0.0]
        dial = self._dial(16, lambda: now[0])
        assert dial.press("1") == 0
        now[0] += 0.2
        assert dial.press("6") == 15
        assert dial.press("1") == 0
        now[0] += 0.2
        assert dial.press("0") == 9

    def test_slow_second_digit_is_a_new_selection(self):
        now = [0.0]
        dial = self._dial(16, lambda: now[0])
        assert dial.press("1") == 0
        now[0] += 2.0
        assert dial.press("4") == 3

    def test_combination_beyond_capacity_is_ignored(self):
        now = [0.0]
        dial = self._dial(10, lambda: now[0])
        assert dial.press("1") == 0
        now[0] += 0.1
        assert dial.press("2") == 1  # 12 does not exist on a 10-chamber cylinder


# ── Core: capacity, rotation, read-only fire ─────────────────────────────
@pytest.fixture()
def board_with_config(isolated_board, fresh_config, monkeypatch):
    monkeypatch.setattr(core, "config", fresh_config)
    core._reset_app_clipboard_writes()
    yield isolated_board
    core._reset_app_clipboard_writes()


class TestCapacityInCore:
    def test_set_chamber_count_bounds_and_persistence(self, board_with_config, fresh_config):
        assert core.set_chamber_count(16) == 16
        assert core.get_chamber_count() == 16
        assert fresh_config.get("board", "max_items") == 16
        assert core.set_chamber_count(10) == 10
        assert fresh_config.get("board", "max_items") == 10

    @pytest.mark.parametrize("bad", [0, 9, 17, 99, -1, "nope", None])
    def test_invalid_capacities_do_not_crash(self, board_with_config, bad):
        applied = core.set_chamber_count(bad)
        assert MIN_CHAMBERS <= applied <= MAX_CHAMBERS

    def test_growing_keeps_every_item(self, board_with_config):
        core.set_chamber_count(10)
        for i in range(10):
            board_with_config["add"](f"r{i}")
        before = board_with_config["get"]()
        core.set_chamber_count(16)
        assert board_with_config["get"]() == before

    def test_shrinking_ejects_only_the_oldest(self, board_with_config):
        core.set_chamber_count(16)
        for i in range(16):
            board_with_config["add"](f"r{i}")
        assert core.rounds_lost_when_resized(12) == 4
        core.set_chamber_count(12)
        board = board_with_config["get"]()
        assert len(board) == 12
        assert board[0] == "r15"        # newest keeps chamber 01
        assert board[-1] == "r4"        # r0..r3 were the oldest and are gone


class TestRotationAndEviction:
    def test_new_copy_loads_chamber_01_and_rotates(self, board_with_config):
        core.set_chamber_count(10)
        board_with_config["add"]("first")
        board_with_config["add"]("second")
        board_with_config["add"]("third")
        assert core.get_chamber(0) == "third"
        assert core.get_chamber(1) == "second"
        assert core.get_chamber(2) == "first"

    def test_eviction_only_when_full_at_16(self, board_with_config):
        core.set_chamber_count(16)
        for i in range(16):
            board_with_config["add"](f"r{i}")
        assert core.get_board_size() == 16
        assert core.get_chamber(15) == "r0"
        board_with_config["add"]("r16")
        assert core.get_board_size() == 16
        assert core.get_chamber(0) == "r16"
        assert core.get_chamber(15) == "r1"  # r0 evicted, everything shifted one chamber

    def test_duplicate_policy_preserved(self, board_with_config):
        board_with_config["add"]("same")
        board_with_config["add"]("same")
        assert core.get_board_size() == 1
        board_with_config["add"]("other")
        board_with_config["add"]("same")
        assert board_with_config["get"]() == ["same", "other", "same"]


class TestFiringIsReadOnly:
    @pytest.mark.parametrize("index", [0, 9, 15])
    def test_paste_chambers_01_10_16_do_not_mutate(self, board_with_config, mock_clipboard, index):
        core.set_chamber_count(16)
        for i in range(16):
            board_with_config["add"](f"round-{i}")
        before = board_with_config["get"]()
        assert core.fire_chamber(index, auto_paste=False) is True
        assert mock_clipboard["content"] == before[index]
        assert board_with_config["get"]() == before
        assert core.get_board_size() == 16

    def test_fire_empty_or_out_of_range_chamber(self, board_with_config, mock_clipboard):
        core.set_chamber_count(10)
        board_with_config["add"]("only")
        mock_clipboard["content"] = "untouched"
        assert core.fire_chamber(1, auto_paste=False) is False   # empty chamber 02
        assert core.fire_chamber(10, auto_paste=False) is False  # beyond a 10-chamber cylinder
        assert core.fire_chamber(-1, auto_paste=False) is False
        assert core.fire_chamber("0", auto_paste=False) is False
        assert mock_clipboard["content"] == "untouched"
        assert core.get_chamber(1) is None
        assert core.get_chamber(15) is None

    def test_eject_and_clear_are_explicit(self, board_with_config):
        for i in range(3):
            board_with_config["add"](f"r{i}")
        assert core.fire_chamber(1, auto_paste=False)
        assert core.get_board_size() == 3           # firing never ejects
        assert core.drop_item(1) is True
        assert board_with_config["get"]() == ["r2", "r0"]
        core.clear_board()
        assert board_with_config["get"]() == []


class TestSelfWriteSuppression:
    def test_app_write_is_recognised_once(self, board_with_config, mock_clipboard):
        core.set_clipboard_text("fired text")
        assert mock_clipboard["content"] == "fired text"
        assert core.is_app_clipboard_write("fired text") is True
        assert core.is_app_clipboard_write("fired text") is False  # consumed
        assert core.is_app_clipboard_write("external") is False

    def test_paste_from_board_registers_self_write(self, board_with_config):
        board_with_config["add"]("older")
        board_with_config["add"]("newest")
        assert core.paste_from_board(1, auto_paste=False)
        assert core.is_app_clipboard_write("older") is True

    def test_pending_writes_expire(self, board_with_config, monkeypatch):
        core.set_clipboard_text("stale")
        monkeypatch.setattr(core, "_APP_WRITE_TTL", 0.0)
        time.sleep(0.01)
        assert core.is_app_clipboard_write("stale") is False

    def test_failed_clipboard_write_is_not_recorded(self, board_with_config, monkeypatch):
        import pyperclip

        def boom(_text):
            raise pyperclip.PyperclipException("no clipboard")

        monkeypatch.setattr("pyperclip.copy", boom)
        with pytest.raises(pyperclip.PyperclipException):
            core.set_clipboard_text("never landed")
        assert core.is_app_clipboard_write("never landed") is False


class TestBoardFileCompatibility:
    def test_plain_list_board_json_still_loads(self, board_with_config):
        with open(board_with_config["board_file"], "w") as fh:
            json.dump(["a", "b", 3, None, "c"], fh)
        assert core.reload_board() == ["a", "b", "c"]

    def test_non_list_board_json_is_ignored(self, board_with_config):
        with open(board_with_config["board_file"], "w") as fh:
            json.dump({"not": "a list"}, fh)
        assert core.reload_board() == []

    def test_saved_format_is_unchanged(self, board_with_config):
        board_with_config["add"]("kept")
        core.force_save()
        with open(board_with_config["board_file"]) as fh:
            assert json.load(fh) == ["kept"]


# ── Hotkeys: direct chamber shortcuts ─────────────────────────────────────
class _FakeCore:
    def __init__(self, count=16, size=16):
        self.count = count
        self.size = size
        self.pasted = []

    def copy_to_board(self):
        pass

    def paste_from_board(self, idx):
        self.pasted.append(idx)
        return idx < self.size

    def paste_all(self):
        pass

    def get_board_size(self):
        return self.size

    def get_chamber_count(self):
        return self.count


@pytest.fixture()
def hotkey_env(mock_keyboard, fresh_config, monkeypatch):
    monkeypatch.setattr(hotkeys, "config", fresh_config)
    hotkeys.set_quick_paste_listener(None)
    yield mock_keyboard
    hotkeys.set_quick_paste_listener(None)
    hotkeys.unregister_all_hotkeys()


class TestDirectShortcuts:
    def test_defaults_cover_all_sixteen_chambers(self):
        for number in range(1, 17):
            assert hotkeys.default_combo(hotkeys.quick_paste_action(number))
        assert hotkeys.default_combo("quick_paste_10") == "ctrl+alt+0"
        assert hotkeys.default_combo("quick_paste_11") == "ctrl+alt+shift+1"
        assert hotkeys.default_combo("quick_paste_16") == "ctrl+alt+shift+6"
        assert hotkeys.parse_quick_paste_action("quick_paste_16") == 16
        assert hotkeys.parse_quick_paste_action("quick_paste_17") is None
        assert hotkeys.parse_quick_paste_action("show_gui") is None

    @pytest.mark.parametrize("number", [1, 10, 16])
    def test_shortcut_fires_exactly_the_displayed_chamber(self, hotkey_env, number):
        fake = _FakeCore(count=16)
        report = hotkeys.setup_default_hotkeys(fake)
        combo = hotkeys.default_combo(hotkeys.quick_paste_action(number))
        assert report[hotkeys.quick_paste_action(number)] == hotkeys.STATUS_REGISTERED
        hotkey_env["keyboard"].press_and_release(combo)
        assert fake.pasted == [chamber_index(number)]
        assert chamber_label(fake.pasted[0]) == f"{number:02d}"

    def test_quick_paste_triggers_on_release(self, hotkey_env):
        hotkeys.setup_default_hotkeys(_FakeCore())
        assert hotkey_env["registered_kwargs"]["ctrl+alt+1"] == {"trigger_on_release": True}
        assert hotkey_env["registered_kwargs"]["ctrl+shift+c"] == {}

    def test_only_existing_chambers_are_registered(self, hotkey_env):
        report = hotkeys.setup_default_hotkeys(_FakeCore(count=12))
        assert report["quick_paste_12"] == hotkeys.STATUS_REGISTERED
        assert report["quick_paste_13"] == hotkeys.STATUS_INACTIVE
        assert "ctrl+alt+shift+3" not in hotkey_env["registered"]

    def test_listener_is_told_index_and_outcome(self, hotkey_env):
        fake = _FakeCore(count=16, size=3)
        seen = []
        hotkeys.set_quick_paste_listener(lambda index, ok: seen.append((index, ok)))
        hotkeys.setup_default_hotkeys(fake)
        hotkey_env["keyboard"].press_and_release("ctrl+alt+2")
        hotkey_env["keyboard"].press_and_release("ctrl+alt+shift+6")
        assert seen == [(1, True), (15, False)]

    def test_duplicate_combos_are_reported_not_registered(self, hotkey_env, fresh_config):
        fresh_config.set("hotkeys", "quick_paste_2", "ctrl+alt+1")
        report = hotkeys.setup_default_hotkeys(_FakeCore())
        assert report["quick_paste_1"] == hotkeys.STATUS_DUPLICATE
        assert report["quick_paste_2"] == hotkeys.STATUS_DUPLICATE
        assert "ctrl+alt+1" not in hotkey_env["registered"]
        assert hotkeys.find_duplicate_combos(hotkeys.load_hotkey_config()) == {
            "ctrl+alt+1": ["quick_paste_1", "quick_paste_2"]
        }

    def test_backend_failure_is_reported(self, hotkey_env, monkeypatch):
        def refuse(key, callback, **kwargs):
            if key == "ctrl+alt+3":
                raise ValueError("taken by the OS")
            hotkey_env["registered"][key] = callback

        monkeypatch.setattr(hotkey_env["keyboard"], "add_hotkey", refuse)
        report = hotkeys.setup_default_hotkeys(_FakeCore())
        assert report["quick_paste_3"] == hotkeys.STATUS_FAILED
        assert report["quick_paste_4"] == hotkeys.STATUS_REGISTERED

    def test_register_action_for_show_gui(self, hotkey_env):
        status = hotkeys.register_action("show_gui", lambda: None)
        assert status == hotkeys.STATUS_REGISTERED
        assert "ctrl+alt+c" in hotkey_env["registered"]
        assert hotkeys.get_registration_report()["show_gui"] == status

    def test_describe_rows_list_every_chamber_first(self, hotkey_env):
        hotkeys.setup_default_hotkeys(_FakeCore(count=10))
        rows = hotkeys.describe_hotkeys(10)
        assert [row[0] for row in rows[:16]] == [f"quick_paste_{n}" for n in range(1, 17)]
        assert rows[0][1] == "Fire chamber 01"
        assert rows[15][3] == hotkeys.STATUS_INACTIVE
        assert rows[0][3] == hotkeys.STATUS_REGISTERED

    def test_change_persists_even_without_backend(self, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        monkeypatch.setattr(hotkeys, "KEYBOARD_AVAILABLE", False)
        hotkeys.setup_default_hotkeys(_FakeCore())
        assert hotkeys.apply_hotkey_change("quick_paste_11", "", "Ctrl + Alt + F9") is False
        assert fresh_config.get("hotkeys", "quick_paste_11") == "ctrl+alt+f9"

    def test_legacy_config_gains_new_defaults(self, isolated_config_dir, monkeypatch):
        from copyboard_extension import config_manager

        cfg_path = os.path.join(isolated_config_dir, "config.json")
        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_path)
        with open(cfg_path, "w") as fh:
            json.dump({"hotkeys": {"quick_paste_1": "ctrl+alt+q"}, "board": {"max_items": 10}}, fh)
        mgr = config_manager.ConfigManager()
        assert mgr.get("hotkeys", "quick_paste_1") == "ctrl+alt+q"      # user value kept
        assert mgr.get("hotkeys", "quick_paste_16") == "ctrl+alt+shift+6"  # new default filled in
        assert mgr.get("board", "max_items") == 10


# ── Widget geometry and wheel logic (pure) ───────────────────────────────
class TestWidgetGeometry:
    @pytest.mark.parametrize("count", [10, 11, 12, 13, 14, 15, 16])
    def test_layout_never_overlaps_and_keeps_usable_targets(self, count):
        layout = widget_layout(count)
        assert layout.count == count
        outer = layout.chamber_radius + 5  # chamber plus its rim
        assert layout.neighbour_spacing > 2 * outer + 2
        assert layout.hit_radius * 2 >= 56  # comfortable pointer target
        assert layout.ring_radius + outer + 2 <= layout.size / 2 + 40
        assert layout.ring_radius - outer > layout.hub_radius  # hub never touches the ring

    def test_ten_chambers_keep_the_original_geometry(self):
        layout = widget_layout(10)
        assert (layout.size, layout.ring_radius, layout.chamber_radius) == (390, 128.0, 27.0)

    def test_layout_normalises_bad_counts(self):
        assert widget_layout(3).count == 10
        assert widget_layout(99).count == 16
        assert widget_layout("12").count == 12

    def test_wheel_step_handles_x11_and_delta_forms(self):
        assert wheel_step(num=4, delta=0) == -1
        assert wheel_step(num=5, delta=0) == 1
        assert wheel_step(num=None, delta=120) == -1
        assert wheel_step(num=None, delta=-120) == 1
        assert wheel_step(num=None, delta=0) == 0
        assert wheel_step(num=None, delta="junk") == 0

    def test_next_loaded_index_walks_loaded_chambers_only(self):
        assert next_loaded_index(0, 3, 1) == 1
        assert next_loaded_index(2, 3, 1) == 0
        assert next_loaded_index(0, 3, -1) == 2
        assert next_loaded_index(7, 3, 1) == 0     # highlight was on an empty chamber
        assert next_loaded_index(None, 0, 1) is None


# ── Tk-backed behaviour ──────────────────────────────────────────────────
def _tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no display available
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    return root


def _pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


class _Event:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture()
def tk_root():
    root = _tk_root()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestQuickPasteWidgetTk:
    def _widget(self, root, items, count=16):
        from copyboard_extension.widget_mode import QuickPasteWidget

        fired, ejected = [], []
        widget = QuickPasteWidget(
            parent=root,
            get_items=lambda: list(items),
            describe_item=lambda text: ("TEXT", "T", text[:20]),
            on_fire=fired.append,
            on_restore=lambda: None,
            get_count=lambda: count,
            on_eject=lambda index: (ejected.append(index), items.pop(index))[0] is None,
        )
        widget.show()
        root.update()
        return widget, fired, ejected

    @pytest.mark.parametrize("count", [10, 12, 16])
    def test_widget_draws_every_chamber_for_count(self, tk_root, count):
        widget, _fired, _ejected = self._widget(tk_root, ["a", "b"], count=count)
        assert widget.layout.count == count
        assert len(widget._centers) == count
        assert widget.canvas.winfo_reqwidth() == widget.layout.size

    def test_wheel_moves_highlight_and_never_fires(self, tk_root):
        items = [f"r{i}" for i in range(5)]
        widget, fired, _ = self._widget(tk_root, items)
        assert widget.selected_index == 0
        widget._on_wheel(_Event(num=5, delta=0))          # X11 wheel down
        widget._on_wheel(_Event(num=5, delta=0))
        assert widget.selected_index == 2
        widget._on_wheel(_Event(num=None, delta=120))     # Windows/macOS wheel up
        assert widget.selected_index == 1
        widget._on_wheel(_Event(num=4, delta=0))
        widget._on_wheel(_Event(num=4, delta=0))
        assert widget.selected_index == 4                # wraps through loaded rounds only
        _pump(tk_root, 0.15)
        assert fired == []
        assert widget.preview_var.get().startswith("05  TEXT")

    def test_click_fires_exactly_that_chamber(self, tk_root):
        items = [f"r{i}" for i in range(16)]
        widget, fired, _ = self._widget(tk_root, items)
        x, y = widget._centers[15]
        widget._on_press(_Event(x=x, y=y, x_root=x, y_root=y))
        widget._on_release(_Event(x=x, y=y, x_root=x, y_root=y))
        _pump(tk_root, 0.2)
        assert fired == [15]
        assert items == [f"r{i}" for i in range(16)]     # board untouched by the widget

    def test_enter_fires_highlighted_chamber_and_digits_select(self, tk_root):
        items = [f"r{i}" for i in range(12)]
        widget, fired, _ = self._widget(tk_root, items)
        widget._on_key(_Event(char="1"))
        widget._on_key(_Event(char="2"))
        assert widget.selected_index == 11
        widget.fire_selected()
        _pump(tk_root, 0.2)
        assert fired == [11]

    def test_empty_chamber_cannot_fire(self, tk_root):
        widget, fired, _ = self._widget(tk_root, ["only"])
        x, y = widget._centers[3]
        widget._on_press(_Event(x=x, y=y, x_root=x, y_root=y))
        widget._on_release(_Event(x=x, y=y, x_root=x, y_root=y))
        _pump(tk_root, 0.15)
        assert fired == []
        assert "empty" in widget.preview_var.get().lower()

    def test_eject_needs_two_deliberate_presses(self, tk_root):
        items = ["a", "b", "c"]
        widget, fired, ejected = self._widget(tk_root, items)
        widget.select(1)
        widget.request_eject()
        assert ejected == [] and items == ["a", "b", "c"]
        assert "EJECT 02?" in widget.preview_var.get()
        widget.request_eject()
        assert ejected == [1] and items == ["a", "c"]
        assert fired == []


@pytest.fixture()
def editor(tk_root, isolated_board, fresh_config, monkeypatch):
    from copyboard_extension import copyboard_gui, paste_helper

    monkeypatch.setattr(core, "config", fresh_config)
    monkeypatch.setattr(hotkeys, "config", fresh_config)
    monkeypatch.setattr(copyboard_gui, "config", fresh_config)
    monkeypatch.setattr(paste_helper, "capture_active_window", lambda: None)
    core._reset_app_clipboard_writes()
    gui = copyboard_gui.CopyboardGUI(tk_root)
    gui.root.withdraw()
    yield gui
    gui._closing = True
    gui._app_icon = None  # release the PhotoImage while the interpreter is alive
    core._reset_app_clipboard_writes()


class TestEditorTk:
    def test_fired_chamber_never_returns_to_chamber_01(self, editor, mock_clipboard):
        for i in range(4):
            core.copy_to_board(f"r{i}")
        editor.refresh()
        before = core.get_board()
        editor._last_clipboard = mock_clipboard["content"] = "r3"
        # Fire chamber 03 through the same path the widget and shortcuts use.
        assert editor._load_chamber_into_clipboard(2) == "r1"
        assert mock_clipboard["content"] == "r1"
        assert editor._observe_clipboard(mock_clipboard["content"]) is False
        assert core.get_board() == before
        # A genuinely external copy still loads chamber 01.
        assert editor._observe_clipboard("from another app") is True
        assert core.get_chamber(0) == "from another app"
        assert core.get_board()[1:] == before

    def test_shortcut_paste_from_hotkey_thread_is_suppressed(self, editor, mock_clipboard):
        core.copy_to_board("old")
        core.copy_to_board("new")
        editor._last_clipboard = mock_clipboard["content"] = "new"
        assert core.paste_from_board(1, auto_paste=False)   # what a ctrl+alt+2 does
        assert editor._observe_clipboard(mock_clipboard["content"]) is False
        assert core.get_board() == ["new", "old"]

    def test_paused_capture_ignores_external_copies(self, editor):
        editor.auto_capture_var.set(False)
        assert editor._observe_clipboard("ignored while paused") is False
        assert core.get_board() == []
        assert editor.capture_state_var.get() != ""

    def test_capacity_control_is_the_single_source_of_truth(self, editor, fresh_config, monkeypatch):
        from copyboard_extension import copyboard_gui

        monkeypatch.setattr(copyboard_gui.messagebox, "askyesno", lambda *a, **k: True)
        editor._apply_capacity(16)
        assert core.get_chamber_count() == 16
        assert fresh_config.get("board", "max_items") == 16
        assert "16" in editor.subtitle_var.get()
        assert editor.capacity_var.get() == "16"
        editor.select_chamber(15)
        editor.root.update()
        assert editor.slot_var.get() == "CHAMBER 16 / 16"
        for i in range(16):
            core.copy_to_board(f"r{i}")
        editor._apply_capacity(10)
        assert core.get_chamber_count() == 10
        assert core.get_board_size() == 10
        assert core.get_chamber(0) == "r15"
        assert editor.selected_index == 9

    def test_shrink_is_cancelled_when_user_declines(self, editor, monkeypatch):
        from copyboard_extension import copyboard_gui

        editor._apply_capacity(12)
        for i in range(12):
            core.copy_to_board(f"r{i}")
        monkeypatch.setattr(copyboard_gui.messagebox, "askyesno", lambda *a, **k: False)
        editor._apply_capacity(10)
        assert core.get_chamber_count() == 12
        assert core.get_board_size() == 12
        assert editor.capacity_var.get() == "12"

    def test_invalid_capacity_input_is_rejected_without_crash(self, editor):
        editor._apply_capacity("many")
        assert core.get_chamber_count() == 10
        editor._apply_capacity(40)
        assert core.get_chamber_count() == 16

    def test_fire_without_restorable_focus_does_not_paste(self, editor, monkeypatch, mock_clipboard):
        from copyboard_extension import paste_helper

        pasted = []
        monkeypatch.setattr(paste_helper, "restore_active_window", lambda target: False)
        monkeypatch.setattr(paste_helper, "paste_current_clipboard", lambda: pasted.append(True))
        core.copy_to_board("payload")
        editor.refresh()
        editor._deliver_fire(0, None, from_widget=False)
        _pump(editor.root, 0.3)
        assert pasted == []
        assert "press Ctrl+V" in editor.status_var.get()
        assert core.get_board() == ["payload"]

    def test_fire_with_restored_focus_pastes_once(self, editor, monkeypatch):
        from copyboard_extension import paste_helper

        pasted = []
        monkeypatch.setattr(paste_helper, "restore_active_window", lambda target: True)
        monkeypatch.setattr(paste_helper, "paste_current_clipboard", lambda: pasted.append(True))
        core.copy_to_board("payload")
        editor.refresh()
        editor._deliver_fire(0, object(), from_widget=False)
        _pump(editor.root, 0.35)
        assert pasted == [True]
        assert core.get_board() == ["payload"]

    def test_hotkey_notification_is_applied_on_tk_thread(self, editor):
        for i in range(3):
            core.copy_to_board(f"r{i}")
        editor.refresh()
        editor.notify_quick_paste(2, True)      # as the keyboard thread would
        editor.notify_quick_paste(9, False)
        editor._poll_ui_actions()
        assert editor.selected_index == 2
        assert "10" in editor.status_var.get()
        assert core.get_board() == ["r2", "r1", "r0"]
