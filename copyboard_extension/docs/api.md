# Copyboard Extension API Documentation

This document provides detailed information about the Copyboard Extension API.

## RapidClipboard

The `RapidClipboard` class provides a simplified interface for fast copy-paste operations.

### Methods

#### `copy(content: Optional[str] = None) -> str`
Copy content to clipboard and add to history.
- `content`: Text to copy. If None, uses current clipboard content.
- Returns: The content that was copied.

#### `paste(index: int = 0) -> bool`
Paste content from clipboard history.
- `index`: Index of item to paste (0 = most recent).
- Returns: True if successful, False otherwise.

#### `copy_paste(content: str) -> bool`
One-step copy and immediate paste operation (fastest method).
- `content`: Text to copy and paste.
- Returns: True if successful.

#### `get_items() -> List[str]`
Get all items from clipboard history.
- Returns: List of clipboard items.

#### `get_item(index: int) -> Optional[str]`
Get specific item from clipboard history.
- `index`: Index of item to retrieve.
- Returns: Item content or None if index is invalid.

#### `clear() -> None`
Clear all items from clipboard history.

#### `remove(index: Optional[int] = None) -> bool`
Remove item from clipboard history.
- `index`: Index of item to remove. If None, removes oldest item.
- Returns: True if successful.

#### `paste_all() -> bool`
Concatenate and paste all items from clipboard history.
- Returns: True if successful.

#### `set_max_items(count: int) -> None`
Set maximum number of items to store in history.
- `count`: Maximum number of items.

#### `preview_items(max_length: int = 30) -> Dict[int, str]`
Get preview of all clipboard items.
- `max_length`: Maximum characters in preview.
- Returns: Dictionary mapping index to preview text.

#### `delayed_paste(index: int = 0, delay_ms: int = 100) -> bool`
Paste with delay (useful for some applications).
- `index`: Index of item to paste.
- `delay_ms`: Delay in milliseconds.
- Returns: True if scheduled.

## Module-Level Functions

The rapid_clipboard module provides these convenience functions:

- `copy(content=None)`: Copy content to clipboard history.
- `paste(index=0)`: Paste from clipboard history.
- `copy_paste(content)`: One-step copy and paste.
- `get_items()`: Get all clipboard history items.
- `clear()`: Clear clipboard history.

## Core Module

The core module provides the underlying clipboard management functionality.

### Key Functions

#### `copy_to_board(content=None) -> str`
Add content to clipboard history.

#### `paste_from_board(index=0, auto_paste=True) -> bool`
Copy item from history to clipboard and optionally paste it.

#### `paste_all(auto_paste=True) -> bool`
Paste all items from history concatenated.

#### `paste_combination(indices, auto_paste=True) -> bool`
Paste specific combination of history items.

#### `drop_item(index=None) -> bool`
Remove item from clipboard history.

#### `clear_board() -> List[str]`
Clear all items from clipboard history.

#### `get_board() -> List[str]`
Get all clipboard history items.

#### `get_board_item(index) -> Optional[str]`
Get specific item from clipboard history.

#### `get_board_preview(preview_max=30) -> Dict[int, str]`
Get preview of all clipboard items.

## Hotkeys Module

The hotkeys module provides keyboard shortcut functionality.

### Key Functions

#### `setup_default_hotkeys(core_module) -> None`
Setup default keyboard shortcuts for clipboard operations.

#### `change_hotkey(action, new_key) -> bool`
Change keyboard shortcut for specific action.
- `action`: Action name (e.g., "copy_to_board").
- `new_key`: New key combination (e.g., "ctrl+shift+c").

#### `register_hotkey(key, callback) -> bool`
Register custom keyboard shortcut.

#### `unregister_hotkey(key) -> bool`
Unregister keyboard shortcut.

## Paste Helper Module

The paste_helper module provides platform-specific paste functionality.

### Key Functions

#### `paste_current_clipboard() -> bool`
Paste current clipboard content using platform-specific method.

#### `paste_with_delay(delay_ms=100) -> bool`
Paste with specified delay.

#### `paste_text(text) -> bool`
Directly paste text without changing clipboard.

#### `paste_combination(items) -> bool`
Concatenate and paste multiple items. 