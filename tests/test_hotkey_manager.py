"""
Tests for Hotkey Manager – registering/unregistering hotkeys dynamically,
conflict detection, config loading/saving, and runtime hotkey changes.
"""
import pytest

from copyboard_extension import hotkeys
from copyboard_extension.config_manager import DEFAULT_CONFIG


class TestLoadHotkeyConfig:
    """Loading hotkey configuration from ConfigManager."""

    def test_load_returns_all_default_actions(self, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        cfg = hotkeys.load_hotkey_config()
        for action in DEFAULT_CONFIG["hotkeys"]:
            assert action in cfg

    def test_load_returns_customised_combo(self, fresh_config, monkeypatch):
        fresh_config.set("hotkeys", "show_gui", "ctrl+alt+g")
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        cfg = hotkeys.load_hotkey_config()
        assert cfg["show_gui"] == "ctrl+alt+g"


class TestSaveHotkeyConfig:
    """Saving hotkey configuration via ConfigManager."""

    def test_save_persists_values(self, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        new_cfg = {"show_gui": "f12", "copy_to_board": "ctrl+k"}
        hotkeys.save_hotkey_config(new_cfg)
        assert fresh_config.get("hotkeys", "show_gui") == "f12"
        assert fresh_config.get("hotkeys", "copy_to_board") == "ctrl+k"


class TestRegisterHotkey:
    """Registering and unregistering individual hotkeys."""

    def test_register_succeeds(self, mock_keyboard):
        callback = lambda: None
        assert hotkeys.register_hotkey("ctrl+a", callback) is True
        assert "ctrl+a" in mock_keyboard["registered"]

    def test_register_adds_to_active(self, mock_keyboard):
        callback = lambda: None
        hotkeys.register_hotkey("ctrl+b", callback)
        assert "ctrl+b" in hotkeys._active_hotkeys

    def test_unregister_removes_hotkey(self, mock_keyboard):
        callback = lambda: None
        hotkeys.register_hotkey("ctrl+c", callback)
        result = hotkeys.unregister_hotkey("ctrl+c")
        assert result is True
        assert "ctrl+c" not in hotkeys._active_hotkeys
        assert "ctrl+c" not in mock_keyboard["registered"]

    def test_register_without_keyboard_lib(self, monkeypatch):
        """When the keyboard library is unavailable, registration returns False."""
        monkeypatch.setattr(hotkeys, "KEYBOARD_AVAILABLE", False)
        assert hotkeys.register_hotkey("ctrl+x", lambda: None) is False

    def test_unregister_without_keyboard_lib(self, monkeypatch):
        monkeypatch.setattr(hotkeys, "KEYBOARD_AVAILABLE", False)
        assert hotkeys.unregister_hotkey("ctrl+x") is False


class TestUnregisterAll:
    """Unregister all hotkeys at once."""

    def test_unregister_all(self, mock_keyboard):
        hotkeys.register_hotkey("ctrl+1", lambda: None)
        hotkeys.register_hotkey("ctrl+2", lambda: None)
        hotkeys.unregister_all_hotkeys()
        assert len(hotkeys._active_hotkeys) == 0
        assert len(mock_keyboard["registered"]) == 0


class TestApplyHotkeyChange:
    """Changing a single hotkey at runtime."""

    def test_change_hotkey_unregisters_old_registers_new(
        self, mock_keyboard, fresh_config, monkeypatch
    ):
        monkeypatch.setattr(hotkeys, "config", fresh_config)

        # Seed the callback registry
        hotkeys._action_callbacks["test_action"] = lambda: "test"

        # Register old
        hotkeys.register_hotkey("ctrl+old", hotkeys._action_callbacks["test_action"])

        result = hotkeys.apply_hotkey_change("test_action", "ctrl+old", "ctrl+new")
        assert result is True
        assert "ctrl+old" not in hotkeys._active_hotkeys
        assert "ctrl+new" in hotkeys._active_hotkeys

    def test_change_unknown_action_returns_false(
        self, mock_keyboard, fresh_config, monkeypatch
    ):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        result = hotkeys.apply_hotkey_change("no_such_action", "", "ctrl+x")
        assert result is False

    def test_change_hotkey_persists_to_config(
        self, mock_keyboard, fresh_config, monkeypatch
    ):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        hotkeys._action_callbacks["test2"] = lambda: None
        hotkeys.apply_hotkey_change("test2", "", "ctrl+n")
        assert fresh_config.get("hotkeys", "test2") == "ctrl+n"


class TestChangeHotkeyLegacy:
    """Legacy change_hotkey interface."""

    def test_legacy_change(self, mock_keyboard, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        hotkeys._action_callbacks["copy_to_board"] = lambda: None
        # Register the default combo so the old one can be unregistered
        old_combo = fresh_config.get("hotkeys", "copy_to_board")
        hotkeys.register_hotkey(old_combo, hotkeys._action_callbacks["copy_to_board"])

        result = hotkeys.change_hotkey("copy_to_board", "ctrl+shift+k")
        assert result is True
        assert "ctrl+shift+k" in hotkeys._active_hotkeys


class TestSetupDefaultHotkeys:
    """Full default-hotkey setup."""

    def test_setup_registers_known_actions(
        self, mock_keyboard, fresh_config, monkeypatch
    ):
        monkeypatch.setattr(hotkeys, "config", fresh_config)

        # Provide a fake core module
        class FakeCore:
            @staticmethod
            def copy_to_board():
                pass

            @staticmethod
            def paste_from_board(idx):
                pass

            @staticmethod
            def paste_all():
                pass

            @staticmethod
            def get_board_size():
                return 5

        hotkeys.setup_default_hotkeys(FakeCore)
        # At minimum, these actions should have been registered
        assert len(hotkeys._active_hotkeys) > 0
        assert "copy_to_board" in hotkeys._action_callbacks
        assert "paste_recent" in hotkeys._action_callbacks

    def test_setup_clears_previous(self, mock_keyboard, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        # Register a stray hotkey
        hotkeys.register_hotkey("ctrl+stray", lambda: None)

        class FakeCore:
            @staticmethod
            def copy_to_board():
                pass

            @staticmethod
            def paste_from_board(idx):
                pass

            @staticmethod
            def paste_all():
                pass

            @staticmethod
            def get_board_size():
                return 0

        hotkeys.setup_default_hotkeys(FakeCore)
        # The stray should have been cleaned up
        assert "ctrl+stray" not in hotkeys._active_hotkeys


class TestGetActionCallbacks:
    """Action-callback introspection."""

    def test_returns_dict_copy(self, mock_keyboard, fresh_config, monkeypatch):
        monkeypatch.setattr(hotkeys, "config", fresh_config)
        hotkeys._action_callbacks["test"] = lambda: None
        cbs = hotkeys.get_action_callbacks()
        cbs["injected"] = lambda: None
        assert "injected" not in hotkeys._action_callbacks
