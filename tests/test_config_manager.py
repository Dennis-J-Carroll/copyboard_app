"""
Tests for ConfigManager – reading/writing config.json, merging defaults,
and handling corrupt/missing files.
"""
import os
import json
import copy
import pytest

from copyboard_extension.config_manager import ConfigManager, DEFAULT_CONFIG


# ── Helpers ──────────────────────────────────────────────────────────────
def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _read_json(path):
    with open(path, "r") as f:
        return json.load(f)


# ── Tests ────────────────────────────────────────────────────────────────
class TestConfigManagerLoad:
    """Loading behaviour for different file states."""

    def test_load_defaults_when_no_file(self, isolated_config_dir, monkeypatch):
        """With no config.json on disk, all sections fall back to defaults."""
        from copyboard_extension import config_manager

        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(
            config_manager,
            "CONFIG_FILE",
            os.path.join(isolated_config_dir, "config.json"),
        )

        mgr = ConfigManager()

        for section, keys in DEFAULT_CONFIG.items():
            for key, expected in keys.items():
                assert mgr.get(section, key) == expected, (
                    f"Default mismatch for [{section}][{key}]"
                )

    def test_load_valid_json(self, isolated_config_dir, monkeypatch):
        """A valid config.json overrides defaults for present keys."""
        from copyboard_extension import config_manager

        cfg_path = os.path.join(isolated_config_dir, "config.json")
        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_path)

        custom = {"window": {"x": 999, "y": 888}}
        _write_json(cfg_path, custom)

        mgr = ConfigManager()

        # Overridden values
        assert mgr.get("window", "x") == 999
        assert mgr.get("window", "y") == 888
        # Merged defaults
        assert mgr.get("window", "width") == DEFAULT_CONFIG["window"]["width"]
        # Untouched sections should still have defaults
        assert mgr.get("hotkeys", "show_gui") == DEFAULT_CONFIG["hotkeys"]["show_gui"]

    def test_load_malformed_json_falls_back(self, isolated_config_dir, monkeypatch):
        """A malformed config.json falls back to defaults instead of crashing."""
        from copyboard_extension import config_manager

        cfg_path = os.path.join(isolated_config_dir, "config.json")
        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_path)

        with open(cfg_path, "w") as f:
            f.write("{this is not: valid json!!! }")

        mgr = ConfigManager()

        # Should have fallen back to defaults
        for section, keys in DEFAULT_CONFIG.items():
            for key, expected in keys.items():
                assert mgr.get(section, key) == expected


class TestConfigManagerSave:
    """Writing behaviour."""

    def test_save_creates_file(self, fresh_config, isolated_config_dir):
        """After save(), a valid JSON file exists."""
        cfg_path = os.path.join(isolated_config_dir, "config.json")
        assert os.path.exists(cfg_path)
        data = _read_json(cfg_path)
        assert "window" in data
        assert "hotkeys" in data
        assert "board" in data

    def test_set_persists_immediately(self, fresh_config, isolated_config_dir):
        """ConfigManager.set() auto-saves to disk."""
        fresh_config.set("board", "max_items", 42)
        cfg_path = os.path.join(isolated_config_dir, "config.json")
        data = _read_json(cfg_path)
        assert data["board"]["max_items"] == 42

    def test_set_creates_new_section(self, fresh_config, isolated_config_dir):
        """Setting a key in a non-existent section creates it."""
        fresh_config.set("custom", "foo", "bar")
        cfg_path = os.path.join(isolated_config_dir, "config.json")
        data = _read_json(cfg_path)
        assert data["custom"]["foo"] == "bar"


class TestConfigManagerMerge:
    """Default-merge behaviour."""

    def test_merge_fills_missing_keys(self, isolated_config_dir, monkeypatch):
        """merge_defaults adds missing keys without overwriting existing ones."""
        from copyboard_extension import config_manager

        cfg_path = os.path.join(isolated_config_dir, "config.json")
        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_path)

        partial = {"window": {"x": 777}}
        _write_json(cfg_path, partial)

        mgr = ConfigManager()

        # Existing value preserved
        assert mgr.get("window", "x") == 777
        # Missing defaults filled in
        assert mgr.get("window", "width") == DEFAULT_CONFIG["window"]["width"]
        assert mgr.get("hotkeys", "show_gui") == DEFAULT_CONFIG["hotkeys"]["show_gui"]

    def test_merge_does_not_overwrite(self, isolated_config_dir, monkeypatch):
        """merge_defaults must NOT overwrite user-customised values."""
        from copyboard_extension import config_manager

        cfg_path = os.path.join(isolated_config_dir, "config.json")
        monkeypatch.setattr(config_manager, "CONFIG_DIR", isolated_config_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_path)

        full = copy.deepcopy(DEFAULT_CONFIG)
        full["board"]["max_items"] = 99
        _write_json(cfg_path, full)

        mgr = ConfigManager()
        assert mgr.get("board", "max_items") == 99  # not the default 10


class TestConfigManagerGetSection:
    """get_section behaviour."""

    def test_get_section_returns_copy(self, fresh_config):
        """Returned dict is a deep-copy, mutations don't affect internal state."""
        section = fresh_config.get_section("hotkeys")
        section["show_gui"] = "CHANGED"
        assert fresh_config.get("hotkeys", "show_gui") != "CHANGED"

    def test_get_unknown_section_returns_empty(self, fresh_config):
        assert fresh_config.get_section("nonexistent") == {}


class TestConfigManagerReset:
    """reset_section behaviour."""

    def test_reset_restores_defaults(self, fresh_config):
        fresh_config.set("board", "max_items", 1000)
        fresh_config.reset_section("board")
        assert fresh_config.get("board", "max_items") == DEFAULT_CONFIG["board"]["max_items"]

    def test_reset_unknown_section_noop(self, fresh_config):
        """Resetting a section that isn't in DEFAULT_CONFIG does nothing."""
        fresh_config.set("custom", "key", "value")
        fresh_config.reset_section("nosuchsection")
        assert fresh_config.get("custom", "key") == "value"


class TestConfigManagerGetFallback:
    """Safe getter fallback chain."""

    def test_get_with_explicit_default(self, fresh_config):
        assert fresh_config.get("nope", "nope", "sentinel") == "sentinel"

    def test_get_returns_none_when_missing(self, fresh_config):
        assert fresh_config.get("nope", "nope") is None
