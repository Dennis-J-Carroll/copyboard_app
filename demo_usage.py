#!/usr/bin/env python3
"""
CopyBoard Usage Demo

This demonstrates how to use CopyBoard's fast copy/paste features,
including the radial menu widget concept.
"""

import sys
import os

sys.path.insert(0, '/home/user/copyboard_app')

from copyboard_extension import core
from copyboard_extension import rapid_clipboard

def demo_basic_usage():
    """Demonstrate basic CopyBoard usage"""
    print("=" * 70)
    print("CopyBoard Usage Demo")
    print("=" * 70)

    # Clear the board for fresh start
    print("\n1. Starting with a clean board...")
    core.clear_board()

    # Scenario: User is researching and copying multiple snippets
    print("\n2. Simulating user workflow - copying multiple items:")
    print("   (In real usage, these would come from Ctrl+C in different apps)")

    research_data = [
        "Python 3.11 introduced several performance improvements",
        "https://github.com/anthropics/claude-code",
        "pip install pyperclip pillow",
        "Multi-clipboard utilities improve productivity by 40%",
        "CopyBoard stores up to 10 items automatically",
    ]

    for i, data in enumerate(research_data, 1):
        rapid_clipboard.copy(data)
        print(f"   [{i}] Copied: {data[:50]}...")

    # Show current board state
    print(f"\n3. Current board has {core.get_board_size()} items")
    print("\n   Board Preview:")
    preview = core.get_board_preview(40)
    for idx, item in preview.items():
        print(f"   {item}")

    # Demonstrate pasting
    print("\n4. Accessing items from board:")
    print(f"   Most recent: {core.get_board_item(0)[:50]}...")
    print(f"   Second item: {core.get_board_item(1)[:50]}...")
    print(f"   Third item:  {core.get_board_item(2)[:50]}...")

    # Demonstrate item management
    print("\n5. Managing items:")
    print("   Removing item at index 1...")
    core.drop_item(1)
    print(f"   Board now has {core.get_board_size()} items")

    # Show persistence
    print("\n6. Persistence:")
    print(f"   Board automatically saved to: {core.BOARD_FILE}")
    core.force_save()
    print("   ✓ Data persisted to disk")

    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)

def demo_radial_widget_concept():
    """Explain the radial widget concept"""
    print("\n" + "=" * 70)
    print("Radial Menu Widget Concept (The 'Realized Widget')")
    print("=" * 70)

    print("""
The Radial Menu is the KEY FEATURE for fast copy/paste:

┌─────────────────────────────────────────────────────────┐
│                                                         │
│                        Item 3                           │
│                          │                              │
│                 Item 2 ──┼── Item 4                     │
│                          │                              │
│         Item 1 ──────────●──────── Item 5               │
│                    (cursor)                             │
│                          │                              │
│                Item 10 ──┼── Item 6                     │
│                          │                              │
│                      Item 7-9                           │
│                                                         │
└─────────────────────────────────────────────────────────┘

HOW IT WORKS:
1. Press hotkey (Ctrl+Alt+V) or right-click CopyBoard icon
2. Radial menu appears centered on your cursor
3. Move mouse toward the item you want
4. Item highlights and shows preview
5. Release mouse to paste

BENEFITS:
✓ Visual selection - see all items at once
✓ Muscle memory - items in same positions
✓ Fast - select in one mouse gesture
✓ No typing - pure visual/motor action
✓ Preview - see content before pasting

EXAMPLE WORKFLOW:

Researching a topic:
  [Copy] "Introduction to Python"       → Board[0]
  [Copy] "https://python.org"           → Board[1]
  [Copy] "pip install requests"         → Board[2]
  [Copy] "Python 3.11 features"         → Board[3]

Now writing a document:
  1. Trigger radial menu (Ctrl+Alt+V)
  2. Move cursor toward "Introduction..."
  3. Release → Pastes Board[0]
  4. Trigger menu again
  5. Move toward "https://python.org"
  6. Release → Pastes Board[1]

NO need to:
  ❌ Switch windows to re-copy
  ❌ Remember what you copied
  ❌ Lose clipboard when copying something else
  ❌ Use complex keyboard shortcuts

THEME CUSTOMIZATION:
You can customize colors, fonts, sizes in:
  ~/.config/copyboard/theme.json

PLATFORM SUPPORT:
  ✓ Linux (X11 with xdotool)
  ✓ Linux (Wayland with wl-clipboard)
  ✓ macOS (with accessibility permissions)
  ✓ Windows (with pywin32)
""")

    print("=" * 70)

def demo_rapid_api():
    """Demonstrate the Rapid Clipboard API"""
    print("\n" + "=" * 70)
    print("Rapid Clipboard API Demo")
    print("=" * 70)

    print("""
The Rapid Clipboard API provides simplified access:

EXAMPLE 1: Quick Copy/Paste Workflow
────────────────────────────────────""")

    # Example code
    code1 = '''
from copyboard_extension import rapid_clipboard as cb

# Copy items during research
cb.copy("First important fact")
cb.copy("Second important fact")
cb.copy("https://example.com")

# Later, get them back
items = cb.get_items()
print(f"I have {len(items)} items saved")

# Paste a specific item
cb.paste(0)  # Pastes most recent
cb.paste(2)  # Pastes third item
'''

    print(code1)

    print("""
EXAMPLE 2: One-Step Copy/Paste (Fastest)
─────────────────────────────────────────""")

    code2 = '''
from copyboard_extension import rapid_clipboard as cb

# Instantly copy and paste without storing
cb.copy_paste("This text is copied and pasted immediately")
# Bypasses board for maximum speed
'''

    print(code2)

    print("""
EXAMPLE 3: Managing the Board
──────────────────────────────""")

    code3 = '''
from copyboard_extension import rapid_clipboard as cb

# Get preview of all items
items = cb.get_items()
for i, item in enumerate(items):
    print(f"[{i}] {item[:40]}...")

# Remove specific item
cb.remove(index=3)

# Clear everything
cb.clear()

# Set max items
cb.set_max_items(15)  # Default is 10
'''

    print(code3)

    print("=" * 70)

if __name__ == "__main__":
    demo_basic_usage()
    demo_radial_widget_concept()
    demo_rapid_api()

    print("\n" + "=" * 70)
    print("🎯 CopyBoard: Multi-Clipboard Made Easy!")
    print("=" * 70)
    print("""
KEY TAKEAWAYS:

1. STORE MULTIPLE ITEMS
   ✓ Keep up to 10 clipboard items at once
   ✓ Never lose important copied text

2. RADIAL MENU WIDGET (The "Realized Widget")
   ✓ Visual pie menu for selection
   ✓ Fast mouse-gesture based pasting
   ✓ See all items at once

3. SIMPLE API
   ✓ rapid_clipboard for quick operations
   ✓ core module for full control
   ✓ Automatic persistence

4. CROSS-PLATFORM
   ✓ Linux, macOS, Windows
   ✓ GUI and CLI modes
   ✓ Hotkey support

Try it yourself:
  python3 test_core_storage.py     # Test core features
  python3 demo_usage.py             # This demo
  python3 -m copyboard_extension.gui  # GUI (requires display)

Documentation:
  README.md        - Overview
  SETUP_GUIDE.md   - Detailed setup and architecture
""")
