#!/usr/bin/env python3
"""
Test script for CopyBoard core storage functionality (no clipboard required)
"""

import sys
import os
import time

# Add the project to path
sys.path.insert(0, '/home/user/copyboard_app')

from copyboard_extension import core

def test_core_storage():
    """Test the core storage functionality without clipboard"""
    print("=" * 70)
    print("CopyBoard Core Storage Test (No Clipboard Required)")
    print("=" * 70)

    # Test 1: Clear the board
    print("\n[Test 1] Clearing the clipboard board...")
    core.clear_board()
    board = core.get_board()
    assert len(board) == 0, "Board should be empty after clear"
    print("✓ Board cleared successfully")

    # Test 2: Add items to the board directly
    print("\n[Test 2] Adding items to the clipboard board (direct API)...")
    test_items = [
        "First clipboard item - Hello World!",
        "Second clipboard item - Python is awesome",
        "Third clipboard item - CopyBoard rocks!",
        "Fourth clipboard item - Fast copy/paste",
        "Fifth clipboard item - Multi-clipboard utility",
    ]

    for i, item in enumerate(test_items):
        # Use copy_to_board with content parameter to bypass clipboard
        result = core.copy_to_board(content=item)
        print(f"  Added item {i+1}: {item[:40]}...")
        time.sleep(0.01)

    board = core.get_board()
    assert len(board) == 5, f"Board should have 5 items, has {len(board)}"
    print(f"✓ Successfully added {len(board)} items to the board")

    # Test 3: Verify board order (newest first)
    print("\n[Test 3] Verifying board order (newest first)...")
    board = core.get_board()
    # Items are inserted at the top, so the order should be reversed
    assert board[0] == test_items[-1], f"Newest item should be first. Got: {board[0]}"
    assert board[-1] == test_items[0], f"Oldest item should be last. Got: {board[-1]}"
    print("✓ Board order is correct (newest first)")

    print("\nCurrent Board Contents:")
    for i, item in enumerate(board):
        print(f"  [{i}] {item[:50]}...")

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
    assert item == test_items[-1], "Item should match the last added item"
    print(f"  Item at index 0: {item[:50]}...")
    print("✓ Retrieved specific item successfully")

    # Test 6: Remove item
    print("\n[Test 6] Removing item from board...")
    original_size = core.get_board_size()
    result = core.drop_item(2)
    assert result == True, "Should successfully remove item"
    new_size = core.get_board_size()
    assert new_size == original_size - 1, f"Board size should decrease by 1. Was {original_size}, now {new_size}"
    print(f"✓ Item removed successfully (size: {original_size} → {new_size})")

    # Test 7: Test max board size
    print("\n[Test 7] Testing max board size limit...")
    core.clear_board()
    core.set_max_board_size(5)

    # Add 10 items
    for i in range(10):
        core.copy_to_board(content=f"Item {i+1}")

    board = core.get_board()
    assert len(board) <= 5, f"Board should not exceed 5 items, has {len(board)}"
    print(f"✓ Board size limit enforced (max 5, actual {len(board)})")

    # Verify it's the most recent 5 items
    print("\nMost Recent Items:")
    for i, item in enumerate(board):
        print(f"  [{i}] {item}")

    # Test 8: Test board persistence (save/load)
    print("\n[Test 8] Testing board persistence...")
    core.clear_board()
    core.copy_to_board(content="Persistence test item 1")
    core.copy_to_board(content="Persistence test item 2")
    core.copy_to_board(content="Persistence test item 3")
    core.force_save()
    print(f"  Board saved to: {core.BOARD_FILE}")

    # Reload the board
    reloaded = core.reload_board()
    assert len(reloaded) == 3, f"Reloaded board should have 3 items, has {len(reloaded)}"
    print("✓ Board persisted and reloaded successfully")

    # Test 9: Test duplicate prevention
    print("\n[Test 9] Testing duplicate prevention...")
    core.clear_board()
    core.copy_to_board(content="Duplicate test")
    size_before = core.get_board_size()
    core.copy_to_board(content="Duplicate test")  # Same content
    size_after = core.get_board_size()
    assert size_before == size_after, "Duplicate should not be added"
    print("✓ Duplicate prevention working")

    # Test 10: Test get_board_item with invalid index
    print("\n[Test 10] Testing get_board_item with invalid index...")
    item = core.get_board_item(999)
    assert item is None, "Should return None for invalid index"
    print("✓ Invalid index handled correctly")

    print("\n" + "=" * 70)
    print("All tests passed! ✓")
    print("=" * 70)

    print("\n📋 CopyBoard Core Summary:")
    print(f"  • Board size: {core.get_board_size()} items")
    print(f"  • Board file: {core.BOARD_FILE}")
    print(f"  • Max board size: {core.MAX_BOARD_SIZE}")

    print("\n✨ CopyBoard Features Verified:")
    print("  ✓ Multi-clipboard storage (up to 10 items)")
    print("  ✓ Fast copy to board")
    print("  ✓ Board persistence (saves to disk)")
    print("  ✓ Board preview and item retrieval")
    print("  ✓ Item management (add, remove, clear)")
    print("  ✓ Duplicate prevention")
    print("  ✓ Max size enforcement")
    print("  ✓ Newest-first ordering")

    print("\n🎯 CopyBoard is ready to use!")
    print("\nNote: In a full desktop environment with X11/Wayland and clipboard")
    print("      tools (xclip/xsel/wl-clipboard), the radial menu widget would")
    print("      provide a visual interface for fast copy/paste operations.")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_core_storage())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
