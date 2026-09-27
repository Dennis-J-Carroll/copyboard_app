"""
Copyboard Core - The core functionality of the multi-clipboard utility
"""
import pyperclip
import subprocess
import sys
import os
import json
import threading
import time
from typing import List, Optional, Dict, Union, Tuple
from . import paste_helper
from .chambers import (  # chamber_* are re-exported as part of the board API
    DEFAULT_CHAMBERS,
    chamber_index,
    chamber_label,
    chamber_number,
    is_chamber_index,
    normalize_chamber_count,
)
from .config_manager import config

# Maximum items to store in the clipboard history (read from config).
# The revolver supports 10–16 chambers; anything else in a legacy config is
# clamped into that range so every surface agrees on one capacity.
MAX_BOARD_SIZE = normalize_chamber_count(
    config.get("board", "max_items", DEFAULT_CHAMBERS)
)

# File to store the clipboard board
USER_HOME = os.path.expanduser("~")
BOARD_DIR = os.path.join(USER_HOME, ".config", "copyboard")
BOARD_FILE = os.path.join(BOARD_DIR, "board.json")

# Performance settings
AUTO_SAVE_DELAY = 2.0  # seconds to wait before auto-saving
SAVE_BATCH_SIZE = 3    # number of changes before force saving

# In-memory cache settings
_board: List[str] = []
_board_modified = False
_last_saved_time = 0
_changes_since_save = 0
_board_loaded = False

# Clipboard writes made by CopyBoard itself.  The GUI's polling loop consults
# this so that firing a chamber is never mistaken for a fresh external copy
# (which would wrongly move the fired item back into chamber 01).
_APP_WRITE_TTL = 6.0  # seconds a pending self-write stays recognisable
_app_clipboard_writes: Dict[str, float] = {}
_app_clipboard_lock = threading.Lock()

# Ensure the config directory exists
if not os.path.exists(BOARD_DIR):
    os.makedirs(BOARD_DIR)

def _load_board(force: bool = False) -> List[str]:
    """Load the clipboard board from file only if not already loaded or force=True"""
    global _board, _board_loaded
    
    if not _board_loaded or force:
        if os.path.exists(BOARD_FILE):
            try:
                with open(BOARD_FILE, 'r') as f:
                    loaded = json.load(f)
                # board.json is a plain JSON list of strings.  Tolerate a
                # damaged file by keeping only the entries we understand.
                if isinstance(loaded, list):
                    _board = [item for item in loaded if isinstance(item, str)]
                else:
                    _board = []
                _board_loaded = True
            except Exception as e:
                print(f"Error loading clipboard board: {e}")
                _board = []
        else:
            _board = []
            _board_loaded = True
    
    return _board

def _save_board(force: bool = False) -> None:
    """
    Save the clipboard board to file only if modified or force=True.
    Uses a delayed-write strategy to avoid frequent disk I/O.
    """
    global _board_modified, _last_saved_time, _changes_since_save
    
    current_time = time.time()
    
    # Skip saving if not modified and not forced
    if not _board_modified and not force:
        return
        
    # Save if forced, enough changes accumulated, or enough time passed
    if (force or 
        _changes_since_save >= SAVE_BATCH_SIZE or 
        (current_time - _last_saved_time > AUTO_SAVE_DELAY and _board_modified)):
        try:
            with open(BOARD_FILE, 'w') as f:
                json.dump(_board, f)
            _board_modified = False
            _last_saved_time = current_time
            _changes_since_save = 0
        except Exception as e:
            print(f"Error saving clipboard board: {e}")

def _mark_modified():
    """Mark the board as modified and increment the change counter"""
    global _board_modified, _changes_since_save
    _board_modified = True
    _changes_since_save += 1

# Load the board at module import time (but only once)
_load_board()


# ---------------------------------------------------------------------------
# Clipboard boundary
# ---------------------------------------------------------------------------
def set_clipboard_text(text: str) -> None:
    """Write ``text`` to the system clipboard on behalf of CopyBoard.

    The write is recorded *before* it reaches the clipboard so a concurrent
    poll can never observe the new text without also finding it flagged as
    app-originated.  If the clipboard rejects the write the record is removed.
    """
    now = time.time()
    with _app_clipboard_lock:
        _purge_expired_app_writes(now)
        _app_clipboard_writes[text] = now
    try:
        pyperclip.copy(text)
    except Exception:
        with _app_clipboard_lock:
            _app_clipboard_writes.pop(text, None)
        raise


def is_app_clipboard_write(text: str) -> bool:
    """Report (and consume) whether ``text`` is a clipboard write we made.

    Intended for the clipboard poller: when it sees new clipboard content it
    asks this question first, and only captures the text when the answer is
    False.  Each recorded write answers True once, and unanswered records
    expire after a few seconds so a later genuine copy of identical text is
    still captured.
    """
    with _app_clipboard_lock:
        _purge_expired_app_writes(time.time())
        return _app_clipboard_writes.pop(text, None) is not None


def _purge_expired_app_writes(now: float) -> None:
    stale = [key for key, at in _app_clipboard_writes.items() if now - at > _APP_WRITE_TTL]
    for key in stale:
        del _app_clipboard_writes[key]


def _reset_app_clipboard_writes() -> None:
    """Test helper: forget every recorded self-write."""
    with _app_clipboard_lock:
        _app_clipboard_writes.clear()


def copy_to_board(content: Optional[str] = None) -> str:
    """
    Add content to the clipboard board.
    If content is None, gets the current clipboard content.
    The newest item is added to the top of the list (index 0).
    
    Args:
        content: Content to add to board. If None, uses current clipboard.
        
    Returns:
        The content that was added
    """
    # Get the content to add
    if content is None:
        # Get the current clipboard content
        content = pyperclip.paste()
    
    # If the content is already at the top of the board, don't add a duplicate
    if _board and _board[0] == content:
        return content
    
    # Add the content to the top of the board
    _board.insert(0, content)
    
    # Keep only the most recent MAX_BOARD_SIZE items
    if len(_board) > MAX_BOARD_SIZE:
        _board.pop()
    
    # Mark as modified and schedule a save
    _mark_modified()
    
    # Perform a non-blocking save operation if needed
    _save_board(force=False)
    
    return content

def paste_from_board(index: int = 0, auto_paste: bool = True) -> bool:
    """
    Copy the item at the specified index from the board to the clipboard and paste it.
    Default is the most recent item (index 0).
    
    Args:
        index: The index of the item to paste
        auto_paste: Whether to automatically paste after copying to clipboard
        
    Returns:
        True if successful, False if index is out of range
    """
    if not _board or index < 0 or index >= len(_board):
        return False
        
    # Fast-path: copy the selected item to the clipboard.  This is a read of
    # the board; the item stays exactly where it is.
    set_clipboard_text(_board[index])
    
    # Attempt to paste it automatically if requested
    if auto_paste:
        paste_helper.paste_current_clipboard()
    
    return True

def paste_all(auto_paste: bool = True) -> bool:
    """
    Concatenate all items in the board, copy to clipboard, and paste.
    
    Args:
        auto_paste: Whether to automatically paste after copying to clipboard
        
    Returns:
        True if successful, False if the board is empty
    """
    if not _board:
        return False
        
    all_content = '\n'.join(_board)
    set_clipboard_text(all_content)
    
    if auto_paste:
        paste_helper.paste_current_clipboard()
    
    return True

def paste_combination(indices: List[int], auto_paste: bool = True) -> bool:
    """
    Paste a specific combination of board items.
    
    Args:
        indices: List of board indices to combine and paste
        auto_paste: Whether to automatically paste after copying to clipboard
        
    Returns:
        True if successful, False if any index is invalid or board is empty
    """
    if not _board:
        return False
        
    # Validate all indices
    for idx in indices:
        if idx < 0 or idx >= len(_board):
            return False
    
    # Get the selected items
    selected_items = [_board[idx] for idx in indices]
    
    # Combine and paste
    combined = ''.join(selected_items)
    set_clipboard_text(combined)
    
    if auto_paste:
        paste_helper.paste_current_clipboard()
    
    return True

def drop_item(index: Optional[int] = None) -> bool:
    """
    Remove an item from the board.
    
    Args:
        index: Index of item to remove. If None, removes the oldest item.
        
    Returns:
        True if successful, False if the board is empty or index is out of range
    """
    if not _board:
        return False
        
    if index is None:
        # Remove the oldest item (last in the list)
        _board.pop()
    elif 0 <= index < len(_board):
        # Remove the specified item
        _board.pop(index)
    else:
        return False
    
    # Mark as modified and schedule a save
    _mark_modified()
    _save_board(force=False)
        
    return True

def clear_board() -> List[str]:
    """
    Clear all items from the clipboard board.
    
    Returns:
        The empty board
    """
    global _board
    _board = []
    
    # Save the empty board immediately
    _mark_modified()
    _save_board(force=True)
    
    return _board

def get_board() -> List[str]:
    """
    Get the current clipboard board.
    
    Returns:
        A copy of the current clipboard board
    """
    return _board.copy()

def get_board_item(index: int) -> Optional[str]:
    """
    Get a specific item from the clipboard board.
    
    Args:
        index: The index of the item to retrieve
        
    Returns:
        The item at the specified index, or None if the index is out of range
    """
    if 0 <= index < len(_board):
        return _board[index]
    return None


def update_board_item(index: int, content: str) -> bool:
    """Replace an existing board item and persist the change immediately."""
    if index < 0 or index >= len(_board):
        return False

    _board[index] = content
    _mark_modified()
    _save_board(force=True)
    return True


def get_board_size() -> int:
    """
    Return the current size of the clipboard board.
    
    Returns:
        Number of items in the board
    """
    return len(_board)

def get_board_preview(preview_max: int = 30) -> Dict[int, str]:
    """
    Get a preview of each item in the clipboard board.
    
    Args:
        preview_max: Maximum number of characters to include in the preview
        
    Returns:
        Dictionary mapping index to preview string
    """
    board_sheet = {}
    
    for index, item in enumerate(_board):
        # Create a preview of the item (truncate if too long)
        if len(item) > preview_max:
            preview = f"{item[:preview_max]}..."
        else:
            preview = item
            
        # Replace newlines for display purposes
        preview = preview.replace('\n', '↵ ')
        
        # Store in dictionary
        board_sheet[index] = f"{index}: {preview}"
    
    return board_sheet

def set_max_board_size(size: int) -> None:
    """
    Set the maximum number of items to store in the clipboard board.
    
    Args:
        size: The new maximum board size
    """
    global MAX_BOARD_SIZE
    
    MAX_BOARD_SIZE = max(1, size)  # Ensure at least 1 item
    
    # Trim the board if it's now larger than the maximum size
    changed = False
    while len(_board) > MAX_BOARD_SIZE:
        _board.pop()
        changed = True
    
    # Save if changed
    if changed:
        _mark_modified()
        _save_board(force=True)

def force_save() -> None:
    """Force an immediate save of the clipboard board"""
    _save_board(force=True)

def reload_board() -> List[str]:
    """Force a reload of the clipboard board from disk"""
    return _load_board(force=True)

def quick_copy_paste(content: str) -> bool:
    """
    One-step operation to copy content and immediately paste it.
    Bypasses board storage for maximum speed.
    
    Args:
        content: The content to copy and paste
        
    Returns:
        True if successful
    """
    set_clipboard_text(content)
    paste_helper.paste_current_clipboard()
    return True


# ---------------------------------------------------------------------------
# Revolver capacity (the user-facing 10–16 chamber contract)
# ---------------------------------------------------------------------------
def get_chamber_count() -> int:
    """Return the number of chambers in the cylinder (10–16)."""
    return MAX_BOARD_SIZE


def set_chamber_count(count: object, persist: bool = True) -> int:
    """Resize the cylinder to ``count`` chambers and return the applied value.

    Invalid or out-of-range values are normalised (clamped into 10–16, or
    the default for non-numeric input) instead of raising.  When the cylinder
    shrinks the *oldest* rounds are ejected so the newest ones stay in their
    low-numbered chambers; growing never changes existing items.  The value is
    written to ``config.json`` so the editor, widget, hotkeys, and CLI all
    read the same capacity next time.
    """
    applied = normalize_chamber_count(count)
    set_max_board_size(applied)
    if persist:
        config.set("board", "max_items", applied)
    return applied


def rounds_lost_when_resized(count: object) -> int:
    """How many rounds a resize to ``count`` would eject (0 if none)."""
    applied = normalize_chamber_count(count)
    return max(0, len(_board) - applied)


def get_chamber(index: int) -> Optional[str]:
    """Read one chamber by zero-based index, or None when empty/out of range."""
    if not is_chamber_index(index, MAX_BOARD_SIZE):
        return None
    return get_board_item(index)


def fire_chamber(index: int, auto_paste: bool = True) -> bool:
    """Paste the chamber at zero-based ``index`` without mutating the board.

    Returns False for an empty or out-of-range chamber.  Alias of
    :func:`paste_from_board` with range validation against the cylinder.
    """
    if not is_chamber_index(index, MAX_BOARD_SIZE):
        return False
    return paste_from_board(index, auto_paste=auto_paste)


def _save_pending_board() -> None:
    """Persist shutdown changes without rewriting an untouched board.

    This guard matters for import-only processes (including the test suite):
    forcing a save there can replace the user's on-disk history with unrelated
    in-memory state.
    """
    if _board_modified:
        _save_board(force=True)


# Make sure genuinely pending changes are saved when the module exits.
import atexit
atexit.register(_save_pending_board)
