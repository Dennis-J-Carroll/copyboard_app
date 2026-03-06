"""
Copyboard ConfigManager - Unified JSON configuration management

Handles reading, writing, and providing defaults for config.json
at ~/.config/copyboard/config.json. Separate from board.json.
"""
import os
import json
import copy
from typing import Any

USER_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(USER_HOME, ".config", "copyboard")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "window": {
        "x": 100,
        "y": 100,
        "width": 300,
        "height": 500,
        "always_on_top": True,
        "mini_mode": False,
        "opacity": 0.95
    },
    "hotkeys": {
        "show_gui": "ctrl+alt+c",
        "copy_to_board": "ctrl+shift+c",
        "paste_recent": "ctrl+shift+v",
        "paste_all": "ctrl+shift+a",
        "cycle_forward": "ctrl+shift+right",
        "cycle_backward": "ctrl+shift+left",
        "quick_paste_1": "ctrl+alt+1",
        "quick_paste_2": "ctrl+alt+2",
        "quick_paste_3": "ctrl+alt+3",
        "quick_paste_4": "ctrl+alt+4",
        "quick_paste_5": "ctrl+alt+5",
        "paste_combo": "ctrl+alt+b"
    },
    "board": {
        "max_items": 10,
        "auto_capture": True,
        "show_previews": True,
        "preview_length": 50
    }
}


class ConfigManager:
    """Unified configuration manager for Copyboard."""

    def __init__(self):
        self._config = {}
        self.load()

    def load(self):
        """Load config from disk. Falls back to defaults if missing or malformed."""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError, OSError):
                self._config = {}

        self.merge_defaults()

    def save(self):
        """Write current config to disk immediately."""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self._config, f, indent=4)
        except (IOError, OSError) as e:
            print(f"Error saving config: {e}")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Safe getter with fallback to defaults then to provided default."""
        if section in self._config and key in self._config[section]:
            return self._config[section][key]
        if section in DEFAULT_CONFIG and key in DEFAULT_CONFIG[section]:
            return DEFAULT_CONFIG[section][key]
        return default

    def get_section(self, section: str) -> dict:
        """Get an entire config section as a dict copy."""
        if section in self._config:
            return copy.deepcopy(self._config[section])
        if section in DEFAULT_CONFIG:
            return copy.deepcopy(DEFAULT_CONFIG[section])
        return {}

    def set(self, section: str, key: str, value: Any):
        """Set a config value and auto-save."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self.save()

    def reset_section(self, section: str):
        """Reset one section to defaults without touching others."""
        if section in DEFAULT_CONFIG:
            self._config[section] = copy.deepcopy(DEFAULT_CONFIG[section])
            self.save()

    def merge_defaults(self):
        """Fill in any missing keys from defaults without overwriting existing values."""
        for section, defaults in DEFAULT_CONFIG.items():
            if section not in self._config:
                self._config[section] = copy.deepcopy(defaults)
            else:
                for key, value in defaults.items():
                    if key not in self._config[section]:
                        self._config[section][key] = copy.deepcopy(value)
        self.save()


# Module-level singleton
config = ConfigManager()
