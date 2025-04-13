#!/bin/bash
# Copyboard Installation Script

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_HOME="$HOME"

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}              Copyboard Installation Script                     ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Check for dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

MISSING_DEPS=0
for cmd in python3 pip3; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is not installed.${NC}"
        MISSING_DEPS=1
    fi
done

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${RED}Please install the missing dependencies and try again.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip3 install --user pyperclip

# Check desktop environment
echo -e "${YELLOW}Detecting desktop environment...${NC}"
if [ "$XDG_CURRENT_DESKTOP" = "GNOME" ]; then
    DESKTOP_ENV="GNOME"
    echo -e "Detected ${GREEN}GNOME${NC} desktop environment."
    
    # Check for xdotool
    if ! command -v xdotool &> /dev/null; then
        echo -e "${YELLOW}Warning: xdotool is not installed. It's required for clipboard pasting.${NC}"
        echo -e "Installing xdotool..."
        sudo apt-get install -y xdotool || {
            echo -e "${RED}Failed to install xdotool. Please install it manually:${NC}"
            echo "sudo apt-get install xdotool"
        }
    fi
    
    # Install Nautilus extension
    echo -e "${YELLOW}Installing Nautilus extension...${NC}"
    NAUTILUS_EXT_DIR="$USER_HOME/.local/share/nautilus-python/extensions"
    mkdir -p "$NAUTILUS_EXT_DIR"
    
    # Copy the extension
    cp "$BASE_DIR/nautilus-copyboard.py" "$NAUTILUS_EXT_DIR/"
    
    # Check if successful
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Nautilus extension installed successfully.${NC}"
    else
        echo -e "${RED}Failed to install Nautilus extension.${NC}"
    fi
    
elif [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
    DESKTOP_ENV="KDE"
    echo -e "Detected ${GREEN}KDE${NC} desktop environment."
    
    # TODO: Add KDE-specific installation
    echo -e "${YELLOW}KDE integration will be added in a future update.${NC}"
else
    DESKTOP_ENV="UNKNOWN"
    echo -e "${YELLOW}Unknown desktop environment. Will install basic functionality only.${NC}"
fi

# Install Copyboard Python package
echo -e "${YELLOW}Installing Copyboard Python package...${NC}"
pip3 install --user -e "$BASE_DIR"

# Create executable scripts
echo -e "${YELLOW}Creating executable scripts...${NC}"
SCRIPTS_DIR="$USER_HOME/.local/bin"
mkdir -p "$SCRIPTS_DIR"

# Create the copyboard script
cat > "$SCRIPTS_DIR/copyboard" << 'EOF'
#!/bin/bash
python3 -m copyboard_extension.cli "$@"
EOF
chmod +x "$SCRIPTS_DIR/copyboard"

# Create the copyboard-gui script
cat > "$SCRIPTS_DIR/copyboard-gui" << 'EOF'
#!/bin/bash
python3 -c "import sys; sys.path.insert(0, '$BASE_DIR'); from copyboard_extension import copyboard_gui; copyboard_gui.main()"
EOF
chmod +x "$SCRIPTS_DIR/copyboard-gui"

# Install the desktop file
echo -e "${YELLOW}Installing desktop launcher...${NC}"
DESKTOP_DIR="$USER_HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/copyboard.desktop" << EOF
[Desktop Entry]
Name=Copyboard
Comment=Multi-clipboard utility
Exec=copyboard-gui
Terminal=false
Type=Application
Icon=edit-paste
Categories=Utility;
EOF

# Install the global hotkeys
echo -e "${YELLOW}Installing global hotkeys...${NC}"

# Copy the desktop entry to autostart
AUTOSTART_DIR="$USER_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cp "$BASE_DIR/copyboard-hotkeys.desktop" "$AUTOSTART_DIR/"

# Set the correct paths
sed -i "s|Exec=python3.*|Exec=python3 $BASE_DIR/global_hotkeys.py|g" "$AUTOSTART_DIR/copyboard-hotkeys.desktop"

# Final steps
echo -e "${YELLOW}Finishing installation...${NC}"

# Restart Nautilus if it's running
if [ "$DESKTOP_ENV" = "GNOME" ]; then
    if pgrep -x "nautilus" > /dev/null; then
        echo -e "${YELLOW}Restarting Nautilus...${NC}"
        nautilus -q
    fi
fi

# Print completion message
echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}              Copyboard Installation Complete                  ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo -e "You can now use Copyboard in the following ways:"
echo -e "  ${BLUE}* Command line:${NC} copyboard [add|paste|list|clear]"
echo -e "  ${BLUE}* GUI:${NC} copyboard-gui"
echo -e "  ${BLUE}* File manager:${NC} Right-click on files and use the Copyboard menu"
echo -e "  ${BLUE}* Global hotkeys:${NC}"
echo -e "      - ${YELLOW}Ctrl+Alt+X${NC}: Copy current clipboard to board"
echo -e "      - ${YELLOW}Ctrl+Alt+V${NC}: Paste from board"
echo -e "      - ${YELLOW}Ctrl+Alt+B${NC}: Paste combination"
echo -e "      - ${YELLOW}Ctrl+Alt+C${NC}: Show Copyboard GUI"
echo ""
echo -e "To start the global hotkeys service now, run:"
echo -e "  ${BLUE}$BASE_DIR/global_hotkeys.py${NC}"
echo ""
echo -e "To add Copyboard to startup applications:"
echo -e "  ${BLUE}It should already be added to your startup applications.${NC}"
echo -e "  ${BLUE}If not, add '$SCRIPTS_DIR/copyboard-hotkeys' to your startup applications.${NC}"
echo ""

# Exit
exit 0
