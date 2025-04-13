#!/usr/bin/env python3
"""
Test script for the radial menu with custom theme support
"""

import sys
import time
import json
import os
import pyperclip
from . import core, radial_menu

def create_example_theme():
    """Create an example theme file if it doesn't exist"""
    config_dir = os.path.join(os.path.expanduser("~"), ".config", "copyboard")
    os.makedirs(config_dir, exist_ok=True)
    
    theme_file = os.path.join(config_dir, "theme.json")
    
    if not os.path.exists(theme_file):
        example_theme = {
            "background": "#F0F0F0",          # Transparent background
            "center_fill": "#222222",         # Dark center
            "center_outline": "#4444FF",      # Blue outline
            "center_text": "#FFFFFF",         # White text
            "arm_color": "#444444",           # Dark gray arms
            "arm_selected": "#0088FF",        # Blue selected arm
            "arm_width": 2,                   # Arm width
            "arm_selected_width": 4,          # Selected arm width
            "node_fill": "#333333",           # Dark node
            "node_selected": "#0088FF",       # Blue selected node
            "node_text": "#FFFFFF",           # White text
            "label_text": "#000000",          # Black label text
            "label_selected": "#0088FF",      # Blue selected label
            "font_family": "Arial",           # Font family
        }
        
        with open(theme_file, 'w') as f:
            json.dump(example_theme, f, indent=2)
        
        print(f"Created example theme file at {theme_file}")
    
    return theme_file

def main():
    """Main function"""
    print("Testing Radial Menu with Custom Theme")
    print("-----------------------------------")
    
    # Clear the clipboard board
    core.clear_board()
    
    # Add some test items to the clipboard board
    test_items = [
        "Item 1: This is the first test item",
        "Item 2: This is the second test item",
        "Item 3: This is the third test item",
        "Item 4: This is the fourth test item",
        "Item 5: This is the fifth test item",
    ]
    
    for item in test_items:
        pyperclip.copy(item)
        core.copy_to_board()
        time.sleep(0.1)
    
    # Show the items in the clipboard board
    print("Clipboard Board Items:")
    board = core.get_board()
    for i, item in enumerate(board):
        print(f"{i}: {item}")
    
    # Create example theme if it doesn't exist
    theme_file = create_example_theme()
    print(f"\nUsing theme from {theme_file}")
    
    # Load the theme
    custom_theme = radial_menu.load_custom_theme()
    
    print("\nShowing radial menu in 3 seconds...")
    time.sleep(3)
    
    # Get the center of the screen
    import tkinter as tk
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    
    # Show the radial menu with custom theme
    radial_menu.show_radial_menu(screen_width // 2, screen_height // 2, custom_theme)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
