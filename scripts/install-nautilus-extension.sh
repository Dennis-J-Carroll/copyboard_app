#!/bin/bash

# Copyboard Nautilus Extension Installer
echo "Installing Copyboard Nautilus extension..."

# Create the nautilus-python extensions directory if it doesn't exist
NAUTILUS_EXTENSIONS_DIR="$HOME/.local/share/nautilus-python/extensions"
mkdir -p "$NAUTILUS_EXTENSIONS_DIR"

# Copy the extension file
cp "$(dirname "$0")/nautilus-copyboard.py" "$NAUTILUS_EXTENSIONS_DIR/"
chmod +x "$NAUTILUS_EXTENSIONS_DIR/nautilus-copyboard.py"

echo "Installation complete. Restarting Nautilus..."
# Restart Nautilus to load the extension
nautilus -q

echo "Done! The Copyboard extension should now appear in your right-click menu in Nautilus."
echo "If it doesn't appear, you may need to log out and log back in."
