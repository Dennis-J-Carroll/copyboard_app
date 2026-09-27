"""
Copyboard Hotkeys - Keyboard shortcut system for rapid-fire clipboard operations

Uses ConfigManager for unified configuration instead of separate hotkeys.json.

Global shortcuts are provided by the optional ``keyboard`` library.  Its
callbacks run on the library's own listener thread, never on Tk's thread, so
anything that must touch the UI is handed to a listener (see
:func:`set_quick_paste_listener`) which the GUI drains from its event loop.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chambers import MAX_CHAMBERS, chamber_index, chamber_label, normalize_chamber_count
from .config_manager import DEFAULT_CONFIG, config

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    keyboard = None
    KEYBOARD_AVAILABLE = False

# Active hotkeys with their callbacks
_active_hotkeys: Dict[str, Any] = {}
_current_index = 0

# Callback registry: maps action names to their callback functions
_action_callbacks: Dict[str, Callable] = {}

# Outcome of the last setup_default_hotkeys() run, keyed by action name.
# Values are one of the STATUS_* constants below.
_registration_report: Dict[str, str] = {}

# Optional listener told about direct chamber pastes: (index, success).
_quick_paste_listener: Optional[Callable[[int, bool], None]] = None

STATUS_REGISTERED = "registered"
STATUS_FAILED = "failed"          # the keyboard backend refused the combo
STATUS_DUPLICATE = "duplicate"    # the same combo is bound to another action
STATUS_UNAVAILABLE = "unavailable"  # keyboard library missing / no permission
STATUS_DISABLED = "disabled"      # combo left blank by the user
STATUS_INACTIVE = "inactive"      # chamber beyond the current cylinder size

QUICK_PASTE_PREFIX = "quick_paste_"

# Human-readable labels for the settings UI, in display order.
ACTION_LABELS: Tuple[Tuple[str, str], ...] = (
    ("show_gui", "Open / close the quick-paste widget"),
    ("copy_to_board", "Capture the current clipboard"),
    ("paste_recent", "Paste chamber 01"),
    ("paste_all", "Paste every chamber joined by newlines"),
    ("cycle_forward", "Paste the next chamber"),
    ("cycle_backward", "Paste the previous chamber"),
    ("paste_combo", "Paste a combination (dialog)"),
)


def quick_paste_action(number: int) -> str:
    """Config key for the direct shortcut of one-based chamber ``number``."""
    return f"{QUICK_PASTE_PREFIX}{int(number)}"


def parse_quick_paste_action(action: str) -> Optional[int]:
    """Return the one-based chamber number encoded in ``action``, if any."""
    if not action.startswith(QUICK_PASTE_PREFIX):
        return None
    try:
        number = int(action[len(QUICK_PASTE_PREFIX):])
    except ValueError:
        return None
    return number if 1 <= number <= MAX_CHAMBERS else None


def default_combo(action: str) -> str:
    """The shipped default for ``action`` ('' when there is none)."""
    return DEFAULT_CONFIG["hotkeys"].get(action, "")


def load_hotkey_config() -> Dict[str, str]:
    """Load hotkey configuration from ConfigManager."""
    return config.get_section("hotkeys")


def save_hotkey_config(hotkey_config: Dict[str, str]) -> None:
    """Save hotkey configuration via ConfigManager."""
    for action, combo in hotkey_config.items():
        config.set("hotkeys", action, combo)


def normalize_combo(combo: object) -> str:
    """Canonical form of a user-typed combo ('Ctrl + Alt+1' -> 'ctrl+alt+1')."""
    if not isinstance(combo, str):
        return ""
    parts = [part.strip().lower() for part in combo.split("+")]
    return "+".join(part for part in parts if part)


def find_duplicate_combos(hotkey_config: Dict[str, str]) -> Dict[str, List[str]]:
    """Map each combo bound to more than one action -> the conflicting actions."""
    owners: Dict[str, List[str]] = {}
    for action, combo in hotkey_config.items():
        key = normalize_combo(combo)
        if key:
            owners.setdefault(key, []).append(action)
    return {combo: actions for combo, actions in owners.items() if len(actions) > 1}


def register_hotkey(key: str, callback: Callable, trigger_on_release: bool = False) -> bool:
    """Register a hotkey with a callback function."""
    if not KEYBOARD_AVAILABLE:
        return False

    try:
        if trigger_on_release:
            keyboard.add_hotkey(key, callback, trigger_on_release=True)
        else:
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


def set_quick_paste_listener(listener: Optional[Callable[[int, bool], None]]) -> None:
    """Install a callable told ``(index, success)`` after each direct paste.

    The callable runs on the keyboard listener thread.  A GUI must forward
    the notification to its own thread (CopyBoard queues it) rather than
    touching widgets directly.
    """
    global _quick_paste_listener
    _quick_paste_listener = listener


def _notify_quick_paste(index: int, success: bool) -> None:
    listener = _quick_paste_listener
    if listener is None:
        return
    try:
        listener(index, success)
    except Exception:
        # A misbehaving listener must never break the hotkey thread.
        pass


def _make_quick_paste(core_module, index: int) -> Callable[[], None]:
    def fire() -> None:
        # Read-only with respect to the board: paste_from_board copies the
        # chamber's text to the clipboard and synthesises a paste keystroke.
        try:
            success = bool(core_module.paste_from_board(index))
        except Exception:
            success = False
        _notify_quick_paste(index, success)

    return fire


def setup_default_hotkeys(core_module, chamber_count: Optional[int] = None) -> Dict[str, str]:
    """
    Setup default hotkeys for copyboard operations.
    Reads from ConfigManager instead of a separate hotkeys.json.

    Args:
        core_module: The copyboard core module with clipboard operations
        chamber_count: How many chambers currently exist (10–16).  Direct
            shortcuts are registered only for chambers that exist so unused
            combos are left to the operating system.  Defaults to the core
            module's ``get_chamber_count()`` when it has one.

    Returns:
        The registration report (action -> STATUS_* string).
    """
    _registration_report.clear()
    # Build the callback registry even when the keyboard backend is missing
    # so the settings UI can still describe every action.
    _action_callbacks.clear()

    if chamber_count is None:
        getter = getattr(core_module, "get_chamber_count", None)
        chamber_count = getter() if callable(getter) else MAX_CHAMBERS
    chamber_count = normalize_chamber_count(chamber_count)

    hotkey_config = load_hotkey_config()

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

    for number in range(1, chamber_count + 1):
        _action_callbacks[quick_paste_action(number)] = _make_quick_paste(
            core_module, chamber_index(number)
        )

    if not KEYBOARD_AVAILABLE:
        for action in hotkey_config:
            _registration_report[action] = STATUS_UNAVAILABLE
        return dict(_registration_report)

    # Unregister any existing hotkeys first
    unregister_all_hotkeys()

    duplicates = find_duplicate_combos(hotkey_config)
    for action, combo in hotkey_config.items():
        number = parse_quick_paste_action(action)
        if number is not None and number > chamber_count:
            _registration_report[action] = STATUS_INACTIVE
            continue
        callback = _action_callbacks.get(action)
        if callback is None:
            continue  # show_gui and similar are registered by the GUI itself
        combo = normalize_combo(combo)
        if not combo:
            _registration_report[action] = STATUS_DISABLED
            continue
        if combo in duplicates:
            _registration_report[action] = STATUS_DUPLICATE
            continue
        registered = register_hotkey(
            combo, callback, trigger_on_release=number is not None
        )
        _registration_report[action] = (
            STATUS_REGISTERED if registered else STATUS_FAILED
        )
    return dict(_registration_report)


def register_action(action: str, callback: Callable, trigger_on_release: bool = False) -> str:
    """Register a GUI-owned action (e.g. ``show_gui``) from its configured combo.

    Returns the STATUS_* outcome and records it in the registration report so
    the settings table can show it next to the core actions.
    """
    _action_callbacks[action] = callback
    hotkey_config = load_hotkey_config()
    combo = normalize_combo(hotkey_config.get(action, ""))
    if not KEYBOARD_AVAILABLE:
        status = STATUS_UNAVAILABLE
    elif not combo:
        status = STATUS_DISABLED
    elif combo in find_duplicate_combos(hotkey_config):
        status = STATUS_DUPLICATE
    elif register_hotkey(combo, callback, trigger_on_release=trigger_on_release):
        status = STATUS_REGISTERED
    else:
        status = STATUS_FAILED
    _registration_report[action] = status
    return status


def get_registration_report() -> Dict[str, str]:
    """Outcome of the last setup run, keyed by action name."""
    return dict(_registration_report)


def describe_hotkeys(chamber_count: Optional[int] = None) -> List[Tuple[str, str, str, str]]:
    """Rows of (action, label, combo, status) for a settings table.

    Direct chamber shortcuts are listed first, 01 upward, so the mapping the
    user cares about most is never hidden below the generic actions.
    """
    hotkey_config = load_hotkey_config()
    report = get_registration_report()
    count = normalize_chamber_count(chamber_count) if chamber_count else MAX_CHAMBERS
    rows: List[Tuple[str, str, str, str]] = []
    for number in range(1, MAX_CHAMBERS + 1):
        action = quick_paste_action(number)
        label = f"Fire chamber {chamber_label(chamber_index(number))}"
        status = report.get(action)
        if status is None:
            status = STATUS_INACTIVE if number > count else STATUS_UNAVAILABLE
        rows.append((action, label, hotkey_config.get(action, ""), status))
    for action, label in ACTION_LABELS:
        status = report.get(action, STATUS_UNAVAILABLE)
        rows.append((action, label, hotkey_config.get(action, ""), status))
    return rows


def apply_hotkey_change(action: str, old_combo: str, new_combo: str) -> bool:
    """
    Change a single hotkey at runtime without full re-registration.

    The new combo is always persisted so a change made while the keyboard
    backend is unavailable still takes effect on the next launch.

    Args:
        action: The action name (e.g., "copy_to_board")
        old_combo: The current key combination to unregister
        new_combo: The new key combination to register

    Returns:
        True if the combo is now registered (or intentionally blank)
    """
    new_combo = normalize_combo(new_combo)
    callback = _action_callbacks.get(action)
    if not callback:
        return False

    if not KEYBOARD_AVAILABLE:
        config.set("hotkeys", action, new_combo)
        _registration_report[action] = STATUS_UNAVAILABLE
        return False

    # Unregister old
    if old_combo and old_combo in _active_hotkeys:
        unregister_hotkey(old_combo)

    # Register new
    registered = True
    if new_combo:
        registered = register_hotkey(
            new_combo, callback, trigger_on_release=parse_quick_paste_action(action) is not None
        )
        _registration_report[action] = STATUS_REGISTERED if registered else STATUS_FAILED
    else:
        _registration_report[action] = STATUS_DISABLED

    # Persist
    config.set("hotkeys", action, new_combo)
    return registered


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
