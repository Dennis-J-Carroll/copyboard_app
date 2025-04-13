#!/usr/bin/env python3
"""
Global hotkeys for Copyboard

This script adds system-wide keyboard shortcuts for Copyboard operations.
It uses the keyboard library to register global hotkeys.
"""

import os
import sys
import subprocess
import threading
import json
import time
import pyperclip

# Try to import keyboard
try:
    import keyboard
except ImportError:
    print("Error: The keyboard module is not installed. Install it with 'pip install keyboard'")
    print("Note: You may need to run this script as root (or with sudo) for global hotkey access")
    sys.exit(1)

# Add the project path to import copyboard modules
user_home = os.path.expanduser("~")
project_path = os.path.join(user_home, "CascadeProjects", "windsurf-project", "copyboard_extension")
if project_path not in sys.path:
    sys.path.insert(0, project_path)

try:
    from copyboard_extension import core
except ImportError as e:
    print(f"Error importing copyboard module: {e}")
    sys.exit(1)

# Configuration
CONFIG_FILE = os.path.join(user_home, ".config", "copyboard", "hotkeys.json")
DEFAULT_CONFIG = {
    "show_copyboard_gui": "ctrl+alt+c",
    "copy_to_board": "ctrl+alt+x",
    "paste_from_board": "ctrl+alt+v",
    "paste_combination": "ctrl+alt+b",
}

def ensure_config_dir():
    """Make sure config directory exists"""
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

def load_config():
    """Load hotkey configuration"""
    ensure_config_dir()
    
    if not os.path.exists(CONFIG_FILE):
        # Create default config if it doesn't exist
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def show_gui():
    """Open the Copyboard GUI"""
    try:
        subprocess.Popen(['copyboard-gui'])
    except Exception as e:
        print(f"Error opening GUI: {e}")

def copy_to_board():
    """Copy current clipboard to board"""
    try:
        core.copy_to_board()
        print("Copied to clipboard board")
    except Exception as e:
        print(f"Error copying to board: {e}")

def paste_from_board():
    """Show paste dialog to select item from board"""
    try:
        # Get board items
        board_items = core.get_board()
        if not board_items:
            print("No items in clipboard board")
            return
            
        # Create a dialog to select item
        import tkinter as tk
        from tkinter import simpledialog
        
        # Build message
        msg = "Select item to paste (0-" + str(len(board_items)-1) + "):"
        
        # Create window but hide it
        root = tk.Tk()
        root.withdraw()
        
        # Show dialog
        answer = simpledialog.askstring("Copyboard", msg)
        root.destroy()
        
        if answer and answer.isdigit():
            idx = int(answer)
            if 0 <= idx < len(board_items):
                core.paste_from_board(idx)
                print(f"Pasted item {idx}")
            else:
                print(f"Invalid index: {idx}")
    except Exception as e:
        print(f"Error pasting from board: {e}")
        
        # Fallback to command line
        try:
            # Let user select from terminal
            print("Available items:")
            board_items = core.get_board()
            for idx, item in enumerate(board_items):
                preview = item[:30] + "..." if len(item) > 30 else item
                print(f"{idx}: {preview}")
                
            # Try to paste selected item
            idx = input("Enter index to paste: ")
            if idx.isdigit():
                core.paste_from_board(int(idx))
        except Exception as fallback_error:
            print(f"Fallback error: {fallback_error}")

def paste_combination():
    """Show dialog to paste combination of items"""
    try:
        # Get board items
        board_items = core.get_board()
        if not board_items:
            print("No items in clipboard board")
            return
            
        # Create a dialog to select combination
        import tkinter as tk
        from tkinter import simpledialog
        
        # Build message
        msg = "Available clipboard items:\n\n"
        for idx, item in enumerate(board_items):
            preview = item[:30] + "..." if len(item) > 30 else item
            preview = preview.replace("\n", " ")
            msg += f"{idx}: {preview}\n"
            
        msg += "\nEnter numbers separated by commas (e.g., 0,2,5):"
        
        # Create window but hide it
        root = tk.Tk()
        root.withdraw()
        
        # Show dialog
        answer = simpledialog.askstring("Copyboard", msg)
        root.destroy()
        
        if answer:
            try:
                # Parse and validate indices
                indices = [int(idx.strip()) for idx in answer.split(',')]
                
                # Check that all indices are valid
                for idx in indices:
                    if idx < 0 or idx >= len(board_items):
                        print(f"Invalid index: {idx}")
                        return
                
                # Get combined content
                content = ''
                for idx in indices:
                    content += board_items[idx]
                
                # Copy to clipboard and paste
                pyperclip.copy(content)
                core.paste_current_clipboard()
                print(f"Pasted combination: {answer}")
            except ValueError as e:
                print(f"Invalid input: {e}")
    except Exception as e:
        print(f"Error pasting combination: {e}")

def register_hotkeys():
    """Register all hotkeys"""
    config = load_config()
    
    keyboard.add_hotkey(config["show_copyboard_gui"], show_gui)
    keyboard.add_hotkey(config["copy_to_board"], copy_to_board)
    keyboard.add_hotkey(config["paste_from_board"], paste_from_board)
    keyboard.add_hotkey(config["paste_combination"], paste_combination)
    
    print(f"Copyboard hotkeys registered:")
    print(f"  Show GUI: {config['show_copyboard_gui']}")
    print(f"  Copy to board: {config['copy_to_board']}")
    print(f"  Paste from board: {config['paste_from_board']}")
    print(f"  Paste combination: {config['paste_combination']}")

def main():
    """Main entry point"""
    try:
        register_hotkeys()
        print("Copyboard global hotkeys active. Press Ctrl+C to exit.")
        
        # Keep the script running
        keyboard.wait()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
