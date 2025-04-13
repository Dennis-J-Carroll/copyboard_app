"""
Copyboard Hotkeys - Keyboard shortcut system for rapid-fire clipboard operations
"""
import os
import json
import threading
from typing import Dict, Callable, Optional, Any

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Configuration file
USER_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(USER_HOME, ".config", "copyboard")
HOTKEYS_FILE = os.path.join(CONFIG_DIR, "hotkeys.json")

# Default hotkey configuration
DEFAULT_HOTKEYS = {
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
}

# Active hotkeys with their callbacks
_active_hotkeys: Dict[str, Any] = {}
_current_index = 0

def load_hotkey_config() -> Dict[str, str]:
    """Load hotkey configuration from file, or create default"""
    if os.path.exists(HOTKEYS_FILE):
        try:
            with open(HOTKEYS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return DEFAULT_HOTKEYS
    else:
        # Create default config
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        
        try:
            with open(HOTKEYS_FILE, 'w') as f:
                json.dump(DEFAULT_HOTKEYS, f, indent=4)
        except Exception:
            pass
            
        return DEFAULT_HOTKEYS

def save_hotkey_config(config: Dict[str, str]) -> None:
    """Save hotkey configuration to file"""
    try:
        with open(HOTKEYS_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass

def register_hotkey(key: str, callback: Callable) -> bool:
    """Register a hotkey with a callback function"""
    if not KEYBOARD_AVAILABLE:
        return False
        
    try:
        keyboard.add_hotkey(key, callback)
        _active_hotkeys[key] = callback
        return True
    except Exception:
        return False

def unregister_hotkey(key: str) -> bool:
    """Unregister a hotkey"""
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
    """Unregister all active hotkeys"""
    if not KEYBOARD_AVAILABLE:
        return
        
    for key in list(_active_hotkeys.keys()):
        unregister_hotkey(key)

def setup_default_hotkeys(core_module) -> None:
    """
    Setup default hotkeys for copyboard operations
    
    Args:
        core_module: The copyboard core module with clipboard operations
    """
    if not KEYBOARD_AVAILABLE:
        return
    
    # Load config
    config = load_hotkey_config()
    
    # Setup clipboard operations
    register_hotkey(config["copy_to_board"], lambda: core_module.copy_to_board())
    register_hotkey(config["paste_recent"], lambda: core_module.paste_from_board(0))
    register_hotkey(config["paste_all"], lambda: core_module.paste_all())
    
    # Cycle through clipboard items
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
    
    register_hotkey(config["cycle_forward"], cycle_forward)
    register_hotkey(config["cycle_backward"], cycle_backward)
    
    # Quick paste for specific slots
    for i in range(1, 6):
        key = f"quick_paste_{i}"
        if key in config:
            idx = i - 1  # Convert to 0-based index
            register_hotkey(config[key], lambda idx=idx: core_module.paste_from_board(idx))

def change_hotkey(action: str, new_key: str) -> bool:
    """
    Change a hotkey configuration
    
    Args:
        action: The action name (e.g., "copy_to_board")
        new_key: The new key combination (e.g., "ctrl+shift+c")
        
    Returns:
        True if successful, False otherwise
    """
    if not KEYBOARD_AVAILABLE:
        return False
        
    config = load_hotkey_config()
    
    if action not in config:
        return False
    
    # Unregister existing hotkey
    if config[action] in _active_hotkeys:
        unregister_hotkey(config[action])
    
    # Update config
    config[action] = new_key
    save_hotkey_config(config)
    
    return True 