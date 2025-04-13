#!/bin/bash

# Copyboard KDE Service Menu Installer
echo "Installing Copyboard KDE service menu..."

# Create the KDE service menu directory if it doesn't exist
KDE_SERVICES_DIR="$HOME/.local/share/kservices5/ServiceMenus"
mkdir -p "$KDE_SERVICES_DIR"

# Copy the service menu file
cp "$(dirname "$0")/copyboard-kde-service.desktop" "$KDE_SERVICES_DIR/"

echo "Creating dynamic menu generator script..."
MENU_GENERATOR="$HOME/.local/bin/copyboard-kde-menu-generator.sh"
mkdir -p "$HOME/.local/bin"

cat > "$MENU_GENERATOR" << 'EOF'
#!/bin/bash

# Generate dynamic KDE service menu for Copyboard
# This is called whenever the menu is opened

MENU_FILE="$HOME/.local/share/kservices5/ServiceMenus/copyboard-dynamic.desktop"

# Get clipboard items from Copyboard
ITEMS=$(python3 -c "from copyboard_extension import core; items = core.get_board(); print('\n'.join([f'{idx}|{item[:30].replace(\"\n\", \"↵\")}' for idx, item in enumerate(items)]))")

# Create the menu file header
cat > "$MENU_FILE" << 'HEADER'
[Desktop Entry]
Type=Service
X-KDE-ServiceTypes=KonqPopupMenu/Plugin
MimeType=all/all;
Actions=CopyboardHeader;
X-KDE-AuthorizeAction=shell_access

[Desktop Action CopyboardHeader]
Name=Paste from Clipboard Board
Icon=edit-paste
HEADER

# Add each clipboard item as an action
if [ -n "$ITEMS" ]; then
    echo "Actions=CopyboardHeader;" >> "$MENU_FILE"
    
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            IDX=$(echo "$line" | cut -d'|' -f1)
            PREVIEW=$(echo "$line" | cut -d'|' -f2-)
            
            echo "[Desktop Action PasteItem$IDX]" >> "$MENU_FILE"
            echo "Name=Item $IDX: $PREVIEW" >> "$MENU_FILE"
            echo "Exec=python3 -c \"from copyboard_extension import core; core.paste_from_board($IDX)\"" >> "$MENU_FILE"
            echo "Icon=edit-paste" >> "$MENU_FILE"
            echo "" >> "$MENU_FILE"
        fi
    done <<< "$ITEMS"
else
    echo "[Desktop Action NoItems]" >> "$MENU_FILE"
    echo "Name=No items in clipboard board" >> "$MENU_FILE"
    echo "Icon=edit-paste" >> "$MENU_FILE"
fi
EOF

chmod +x "$MENU_GENERATOR"

echo "Installation complete."
echo "The Copyboard options should now appear in your right-click menu in KDE Dolphin."
echo "You may need to log out and log back in for the changes to take effect."
