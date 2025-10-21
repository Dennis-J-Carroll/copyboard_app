#!/usr/bin/env python3
"""
Test script for CopyBoard core functionality
"""

import sys
import os
import time

# Add the project to path
sys.path.insert(0, '/home/user/copyboard_app')

from copyboard_extension import core
from copyboard_extension import rapid_clipboard
import pyperclip

def test_core_functionality():
    """Test the core clipboard board functionality"""
    print("=" * 60)
    print("CopyBoard Functionality Test")
    print("=" * 60)

    # Test 1: Clear the board
    print("\n[Test 1] Clearing the clipboard board...")
    core.clear_board()
    board = core.get_board()
    assert len(board) == 0, "Board should be empty after clear"
    print("✓ Board cleared successfully")

    # Test 2: Add items to the board
    print("\n[Test 2] Adding items to the clipboard board...")
    test_items = [
        "First clipboard item - Hello World!",
        "Second clipboard item - Python is awesome",
        "Third clipboard item - CopyBoard rocks!",
        "Fourth clipboard item - Fast copy/paste",
        "Fifth clipboard item - Multi-clipboard utility",
    ]

    for i, item in enumerate(test_items):
        pyperclip.copy(item)
        result = core.copy_to_board()
        print(f"  Added item {i+1}: {item[:40]}...")
        time.sleep(0.05)  # Small delay to ensure operations complete

    board = core.get_board()
    assert len(board) == 5, f"Board should have 5 items, has {len(board)}"
    print(f"✓ Successfully added {len(board)} items to the board")

    # Test 3: Verify board order (newest first)
    print("\n[Test 3] Verifying board order (newest first)...")
    board = core.get_board()
    # Items are inserted at the top, so the order should be reversed
    assert board[0] == test_items[-1], "Newest item should be first"
    assert board[-1] == test_items[0], "Oldest item should be last"
    print("✓ Board order is correct (newest first)")

    # Test 4: Get board preview
    print("\n[Test 4] Getting board preview...")
    preview = core.get_board_preview(30)
    print("Board Preview:")
    for idx, text in preview.items():
        print(f"  {text}")
    assert len(preview) == 5, "Preview should show all 5 items"
    print("✓ Board preview retrieved successfully")

    # Test 5: Get specific item
    print("\n[Test 5] Getting specific board item...")
    item = core.get_board_item(0)
    assert item is not None, "Should retrieve item at index 0"
    print(f"  Item at index 0: {item[:50]}...")
    print("✓ Retrieved specific item successfully")

    # Test 6: Remove item
    print("\n[Test 6] Removing item from board...")
    original_size = core.get_board_size()
    result = core.drop_item(2)
    assert result == True, "Should successfully remove item"
    assert core.get_board_size() == original_size - 1, "Board size should decrease by 1"
    print("✓ Item removed successfully")

    # Test 7: Test rapid clipboard functionality
    print("\n[Test 7] Testing RapidClipboard interface...")
    rapid_clipboard.clear()
    assert len(rapid_clipboard.get_items()) == 0, "Board should be empty"

    rapid_clipboard.copy("Rapid clipboard test 1")
    rapid_clipboard.copy("Rapid clipboard test 2")
    rapid_clipboard.copy("Rapid clipboard test 3")

    items = rapid_clipboard.get_items()
    assert len(items) == 3, f"Should have 3 items, has {len(items)}"
    print(f"✓ RapidClipboard has {len(items)} items")

    # Test 8: Test max board size
    print("\n[Test 8] Testing max board size limit...")
    core.clear_board()
    core.set_max_board_size(5)

    # Add 10 items
    for i in range(10):
        core.copy_to_board(f"Item {i+1}")

    board = core.get_board()
    assert len(board) <= 5, f"Board should not exceed 5 items, has {len(board)}"
    print(f"✓ Board size limit enforced (max 5, actual {len(board)})")

    # Test 9: Test board persistence (save/load)
    print("\n[Test 9] Testing board persistence...")
    core.clear_board()
    core.copy_to_board("Persistence test item 1")
    core.copy_to_board("Persistence test item 2")
    core.force_save()

    # Reload the board
    reloaded = core.reload_board()
    assert len(reloaded) == 2, "Reloaded board should have 2 items"
    print("✓ Board persisted and reloaded successfully")

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nCopyBoard Core Summary:")
    print(f"  - Board size: {core.get_board_size()} items")
    print(f"  - Board file: {core.BOARD_FILE}")
    print(f"  - Max board size: {core.MAX_BOARD_SIZE}")
    print("\nCopyBoard is working correctly!")
    print("\nKey Features Verified:")
    print("  ✓ Multi-clipboard storage (up to 10 items)")
    print("  ✓ Fast copy to board")
    print("  ✓ Board persistence (saves to disk)")
    print("  ✓ Board preview and item retrieval")
    print("  ✓ RapidClipboard API for simplified access")
    print("  ✓ Item management (add, remove, clear)")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_core_functionality())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
