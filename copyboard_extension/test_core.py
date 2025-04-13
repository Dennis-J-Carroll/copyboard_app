#!/usr/bin/env python3
"""
Test script for the copyboard core functionality.
"""

import sys
import os
import time
from . import core

def test_clipboard_board():
    """Test the clipboard board functionality"""
    print("Testing clipboard board functionality...")
    
    # Clear the board
    print("Clearing board...")
    core.clear_board()
    board = core.get_board()
    print(f"Board has {len(board)} items after clearing")
    
    # Add a test item via the clipboard
    test_text = "Test clipboard item " + str(time.time())
    print(f"Adding test item: {test_text}")
    
    # Use pyperclip directly to simulate copying
    import pyperclip
    pyperclip.copy(test_text)
    
    # Now call copy_to_board to add it to the board
    core.copy_to_board()
    
    # Get the board again
    board = core.get_board()
    print(f"Board has {len(board)} items after adding")
    
    # Check if the item was added
    if len(board) > 0 and board[0] == test_text:
        print("✓ Test item was successfully added to the board")
    else:
        print("✗ Test item was not added to the board correctly")
        if len(board) > 0:
            print(f"First item is: {board[0]}")
    
    # Get board preview
    preview = core.get_board_preview()
    print("Board preview:")
    for idx, text in preview.items():
        print(f"  {idx}: {text}")
    
    return len(board) > 0

if __name__ == "__main__":
    print("\n=== Copyboard Core Test ===\n")
    
    # Test clipboard board
    if test_clipboard_board():
        print("\n✓ Core functionality test passed!")
    else:
        print("\n✗ Core functionality test failed!")
    
    print("\nTest complete")
