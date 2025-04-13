#!/usr/bin/env python3
"""
X11 Shortcuts for Copyboard

This script sets up X11 keyboard shortcuts for Copyboard operations
using xbindkeys, which doesn't require root privileges.
"""

import os
import sys
import subprocess
import json

# Configuration
USER_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(USER_HOME, ".config", "copyboard")
XBINDKEYS_CONFIG = os.path.join(USER_HOME, ".xbindkeysrc")

# Default configuration
DEFAULT_CONFIG = {
    "show_copyboard_gui": "Control+Alt + c",
    "copy_to_board": "Control+Alt + x",
    "paste_from_board": "Control+Alt + v",
    "paste_combination": "Control+Alt + b",
}

def ensure_config_dir():
    """Make sure config directory exists"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

def load_config():
    """Load hotkey configuration"""
    config_file = os.path.join(CONFIG_DIR, "hotkeys.json")
    ensure_config_dir()
    
    if not os.path.exists(config_file):
        # Create default config if it doesn't exist
        with open(config_file, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    # Check for xbindkeys
    if subprocess.run(['which', 'xbindkeys'], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE).returncode != 0:
        missing.append("xbindkeys")
    
    # Check for xdotool
    if subprocess.run(['which', 'xdotool'], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE).returncode != 0:
        missing.append("xdotool")
    
    return missing

def create_xbindkeys_config():
    """Create xbindkeys configuration file"""
    config = load_config()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create config content
    content = '# Copyboard keyboard shortcuts\n\n'
    
    # Show GUI
    content += f'"{script_dir}/bin/copyboard-gui"\n'
    content += f'  {config["show_copyboard_gui"]}\n\n'
    
    # Copy to board
    content += f'"{script_dir}/bin/copyboard add $(xclip -o -selection clipboard)"\n'
    content += f'  {config["copy_to_board"]}\n\n'
    
    # Paste from board
    content += f'"{script_dir}/bin/copyboard-dialog paste"\n'
    content += f'  {config["paste_from_board"]}\n\n'
    
    # Paste combination
    content += f'"{script_dir}/bin/copyboard-dialog combo"\n'
    content += f'  {config["paste_combination"]}\n\n'
    
    # Write to file
    with open(XBINDKEYS_CONFIG, 'w') as f:
        f.write(content)
    
    print(f"Created xbindkeys config at {XBINDKEYS_CONFIG}")

def create_dialog_script():
    """Create the dialog script for paste operations"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, "bin")
    
    # Create bin directory if it doesn't exist
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
    
    # Create dialog script
    dialog_script = os.path.join(bin_dir, "copyboard-dialog")
    
    with open(dialog_script, 'w') as f:
        f.write('''#!/bin/bash
# Copyboard dialog script

MODE=$1

if [ "$MODE" = "paste" ]; then
    # Get list of clipboard items
    ITEMS=$(copyboard list | grep -E "^[0-9]+:" | sed 's/----------------//g')
    
    # Create item list for zenity
    ZENITY_ITEMS=""
    while IFS= read -r line; do
        if [[ $line =~ ^([0-9]+): ]]; then
            INDEX="${BASH_REMATCH[1]}"
            ZENITY_ITEMS="$ZENITY_ITEMS $INDEX \"$line\""
        fi
    done <<< "$ITEMS"
    
    # Show dialog
    SELECTED=$(zenity --list --title="Copyboard" --text="Select item to paste:" \\
                     --column="Index" --column="Content" $ZENITY_ITEMS)
    
    # Paste selected item
    if [ -n "$SELECTED" ]; then
        copyboard copy $SELECTED
        xdotool key ctrl+v
    fi
    
elif [ "$MODE" = "combo" ]; then
    # Get list of clipboard items
    ITEMS=$(copyboard list | grep -E "^[0-9]+:" | sed 's/----------------//g')
    
    # Show items
    echo "$ITEMS"
    
    # Ask for combination
    COMBO=$(zenity --entry --title="Copyboard" \\
                  --text="Enter indices separated by spaces (e.g., 0 2 3):")
    
    # Paste combination
    if [ -n "$COMBO" ]; then
        copyboard paste-combo $COMBO
    fi
fi
''')
    
    # Make script executable
    os.chmod(dialog_script, 0o755)
    print(f"Created dialog script at {dialog_script}")

def create_gui_script():
    """Create the GUI launcher script"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, "bin")
    
    # Create bin directory if it doesn't exist
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
    
    # Create GUI script
    gui_script = os.path.join(bin_dir, "copyboard-gui")
    
    with open(gui_script, 'w') as f:
        f.write(f'''#!/bin/bash
# Copyboard GUI launcher

python3 {script_dir}/copyboard_gui.py
''')
    
    # Make script executable
    os.chmod(gui_script, 0o755)
    print(f"Created GUI script at {gui_script}")

def create_cli_script():
    """Create the CLI script"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(script_dir, "bin")
    
    # Create bin directory if it doesn't exist
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
    
    # Create CLI script
    cli_script = os.path.join(bin_dir, "copyboard")
    
    with open(cli_script, 'w') as f:
        f.write(f'''#!/bin/bash
# Copyboard CLI launcher

python3 -m copyboard_extension.cli "$@"
''')
    
    # Make script executable
    os.chmod(cli_script, 0o755)
    print(f"Created CLI script at {cli_script}")

def start_xbindkeys():
    """Start xbindkeys service"""
    # Kill any existing xbindkeys process
    subprocess.run(['killall', 'xbindkeys'], 
                  stdout=subprocess.PIPE, 
                  stderr=subprocess.PIPE)
    
    # Start xbindkeys
    subprocess.Popen(['xbindkeys'])
    print("Started xbindkeys service")

def main():
    """Main function"""
    print("Setting up X11 shortcuts for Copyboard...")
    
    # Check dependencies
    missing = check_dependencies()
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Please install them with:")
        if "xbindkeys" in missing:
            print("  sudo apt-get install xbindkeys")
        if "xdotool" in missing:
            print("  sudo apt-get install xdotool")
        return 1
    
    # Create scripts
    create_dialog_script()
    create_gui_script()
    create_cli_script()
    
    # Create xbindkeys config
    create_xbindkeys_config()
    
    # Start xbindkeys
    start_xbindkeys()
    
    print("\nX11 shortcuts setup complete!")
    print("You can now use the following keyboard shortcuts:")
    config = load_config()
    print(f"  Show GUI: {config['show_copyboard_gui']}")
    print(f"  Copy to board: {config['copy_to_board']}")
    print(f"  Paste from board: {config['paste_from_board']}")
    print(f"  Paste combination: {config['paste_combination']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
