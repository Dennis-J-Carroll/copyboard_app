#!/bin/bash
# Install global integration for Copyboard

echo "Setting up global integration for Copyboard..."

# Ensure we have the required dependencies
echo "Installing required dependencies..."
pip install keyboard pyperclip

# Copy the desktop entry to autostart
echo "Setting up autostart for global hotkeys..."
mkdir -p ~/.config/autostart
cp "$(dirname "$0")/copyboard-hotkeys.desktop" ~/.config/autostart/

# Make the desktop entry executable
chmod +x ~/.config/autostart/copyboard-hotkeys.desktop

# Set up a global shortcut for copyboard GUI
if command -v gsettings &> /dev/null; then
    echo "Setting up GNOME keyboard shortcut for Copyboard GUI..."
    # This is a bit tricky as gsettings doesn't easily let us add new shortcuts
    # In a real installation, we might need to write a more complex script
    # For now, just inform the user
    echo "To set up a global keyboard shortcut in GNOME:"
    echo "1. Open Settings > Keyboard > Keyboard Shortcuts"
    echo "2. Scroll to the bottom and click the '+' button"
    echo "3. Set Name to 'Copyboard' and Command to 'copyboard-gui'"
    echo "4. Click 'Set Shortcut' and press Ctrl+Alt+C (or your preferred shortcut)"
fi

# Create executable script in PATH for launching hotkeys
SCRIPT_PATH="$HOME/.local/bin/copyboard-hotkeys"
mkdir -p "$HOME/.local/bin"

cat > "$SCRIPT_PATH" << 'EOF'
#!/bin/bash
python3 "$HOME/CascadeProjects/windsurf-project/copyboard_extension/global_hotkeys.py"
EOF

chmod +x "$SCRIPT_PATH"

echo ""
echo "Global integration setup complete!"
echo "To enable system-wide hotkeys, run: copyboard-hotkeys"
echo ""
echo "Default keyboard shortcuts:"
echo "  Show GUI: Ctrl+Alt+C"
echo "  Copy to board: Ctrl+Alt+X"
echo "  Paste from board: Ctrl+Alt+V"
echo "  Paste combination: Ctrl+Alt+B"
echo ""
echo "You can edit these shortcuts in ~/.config/copyboard/hotkeys.json"
