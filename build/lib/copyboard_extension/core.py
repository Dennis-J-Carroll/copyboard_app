"""
Copyboard Core - The core functionality of the multi-clipboard utility
"""
import pyperclip
from typing import List, Optional, Dict, Union

# Maximum items to store in the clipboard history
MAX_BOARD_SIZE = 10
# Initialize the clipboard board as an empty list
_board: List[str] = []

def copy_to_board() -> None:
    """
    Get the current clipboard content and add it to the board.
    The newest item is added to the top of the list (index 0).
    """
    # Get the current clipboard content
    current_clipboard = pyperclip.paste()
    
    # If the content is already at the top of the board, don't add a duplicate
    if _board and _board[0] == current_clipboard:
        return
    
    # Add the current clipboard content to the top of the board
    _board.insert(0, current_clipboard)
    
    # Keep only the most recent MAX_BOARD_SIZE items
    if len(_board) > MAX_BOARD_SIZE:
        _board.pop()

def paste_from_board(index: int = 0) -> bool:
    """
    Copy the item at the specified index from the board to the clipboard.
    Default is the most recent item (index 0).
    
    Args:
        index: The index of the item to paste
        
    Returns:
        True if successful, False if index is out of range
    """
    if not _board or index < 0 or index >= len(_board):
        return False
        
    # Copy the selected item to the clipboard
    pyperclip.copy(_board[index])
    return True

def paste_all() -> bool:
    """
    Concatenate all items in the board and copy to clipboard.
    
    Returns:
        True if successful, False if the board is empty
    """
    if not _board:
        return False
        
    all_content = '\n'.join(_board)
    pyperclip.copy(all_content)
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
        
    return True

def clear_board() -> List[str]:
    """
    Clear all items from the clipboard board.
    
    Returns:
        The empty board
    """
    _board.clear()
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
    while len(_board) > MAX_BOARD_SIZE:
        _board.pop()
