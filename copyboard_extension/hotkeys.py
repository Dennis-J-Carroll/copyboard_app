"""
Copyboard Hotkeys - Keyboard shortcut system for rapid-fire clipboard operations

Uses ConfigManager for unified configuration instead of separate hotkeys.json.
"""
from typing import Dict, Callable, Any

from .config_manager import config

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Active hotkeys with their callbacks
_active_hotkeys: Dict[str, Any] = {}
_current_index = 0

# Callback registry: maps action names to their callback functions
_action_callbacks: Dict[str, Callable] = {}


def load_hotkey_config() -> Dict[str, str]:
    """Load hotkey configuration from ConfigManager."""
    return config.get_section("hotkeys")


def save_hotkey_config(hotkey_config: Dict[str, str]) -> None:
    """Save hotkey configuration via ConfigManager."""
    for action, combo in hotkey_config.items():
        config.set("hotkeys", action, combo)


def register_hotkey(key: str, callback: Callable) -> bool:
    """Register a hotkey with a callback function."""
    if not KEYBOARD_AVAILABLE:
        return False

    try:
        keyboard.add_hotkey(key, callback)
        _active_hotkeys[key] = callback
        return True
    except Exception:
        return False


def unregister_hotkey(key: str) -> bool:
    """Unregister a hotkey."""
    if not KEYBOARD_AVAILABLE:
        return False

    try:
        keyboard.remove_hotkey(key)
        if key in _active_hotkeys:
            del _active_hotkeys[key]
        return True
    except Exception:
        return False


def unregister_all_hotkeys() -> None:
    """Unregister all active hotkeys."""
    if not KEYBOARD_AVAILABLE:
        return

    for key in list(_active_hotkeys.keys()):
        unregister_hotkey(key)


def setup_default_hotkeys(core_module) -> None:
    """
    Setup default hotkeys for copyboard operations.
    Reads from ConfigManager instead of a separate hotkeys.json.

    Args:
        core_module: The copyboard core module with clipboard operations
    """
    if not KEYBOARD_AVAILABLE:
        return

    # Unregister any existing hotkeys first
    unregister_all_hotkeys()
    _action_callbacks.clear()

    hotkey_config = load_hotkey_config()

    # Build callback registry
    _action_callbacks["copy_to_board"] = lambda: core_module.copy_to_board()
    _action_callbacks["paste_recent"] = lambda: core_module.paste_from_board(0)
    _action_callbacks["paste_all"] = lambda: core_module.paste_all()

    def cycle_forward():
        global _current_index
        board_size = core_module.get_board_size()
        if board_size > 0:
            _current_index = (_current_index + 1) % board_size
            core_module.paste_from_board(_current_index)

    def cycle_backward():
        global _current_index
        board_size = core_module.get_board_size()
        if board_size > 0:
            _current_index = (_current_index - 1) % board_size
            core_module.paste_from_board(_current_index)

    _action_callbacks["cycle_forward"] = cycle_forward
    _action_callbacks["cycle_backward"] = cycle_backward

    for i in range(1, 6):
        key = f"quick_paste_{i}"
        idx = i - 1
        _action_callbacks[key] = lambda idx=idx: core_module.paste_from_board(idx)

    # Register all hotkeys from config
    for action, combo in hotkey_config.items():
        callback = _action_callbacks.get(action)
        if callback and combo:
            register_hotkey(combo, callback)


def apply_hotkey_change(action: str, old_combo: str, new_combo: str) -> bool:
    """
    Change a single hotkey at runtime without full re-registration.

    Args:
        action: The action name (e.g., "copy_to_board")
        old_combo: The current key combination to unregister
        new_combo: The new key combination to register

    Returns:
        True if successful
    """
    if not KEYBOARD_AVAILABLE:
        return False

    callback = _action_callbacks.get(action)
    if not callback:
        return False

    # Unregister old
    if old_combo and old_combo in _active_hotkeys:
        unregister_hotkey(old_combo)

    # Register new
    if new_combo:
        register_hotkey(new_combo, callback)

    # Persist
    config.set("hotkeys", action, new_combo)
    return True


def change_hotkey(action: str, new_key: str) -> bool:
    """
    Change a hotkey configuration (legacy interface).

    Args:
        action: The action name (e.g., "copy_to_board")
        new_key: The new key combination (e.g., "ctrl+shift+c")

    Returns:
        True if successful
    """
    hotkey_config = load_hotkey_config()
    old_key = hotkey_config.get(action, "")
    return apply_hotkey_change(action, old_key, new_key)


def get_action_callbacks() -> Dict[str, Callable]:
    """Return the current action-to-callback mapping."""
    return dict(_action_callbacks)
