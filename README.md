# CopyBoard

A multi-clipboard utility for copying and pasting multiple items across all major platforms.
As you use you computer for anything, wether it be typical research, or just casually. Have you ever found yourself having to switch between pages or tabs to get all of the segments of information you wanted in one place? 
Here I wanted to create a way that, instead of having one selection pastable from a copied item, the user will have the cchoice of ten items that they have copied. 

This is CopyBoard: 
<p align="center">
  <img src="universal_upscale_0_5c1108bf-7f62-4c4e-bc97-268262d24997_0.jpg" alt="CopyBoard App Preview" width="600"/>
</p>







This is still a work and progress and all contributions are welcome.

## Features

- Store multiple clipboard items
- Paste any item from history with keyboard shortcuts
- Combine multiple clipboard items
- System-wide hotkeys
- File manager integration
- Browser extension
- Cross-platform (Linux, macOS, Windows)

## Installation

### Quick Install

```bash
# Install from PyPI
pip install copyboard-extension

# Install system-wide integration
copyboard-install-integration
```

### Platform-Specific Installation

#### Linux

```bash
# Install dependencies
sudo apt install xdotool xclip python3-tk python3-pip

# Install Copyboard
pip install copyboard-extension

# Install system-wide
python3 scripts/install_system_wide.py
```

#### macOS

```bash
# Install dependencies
brew install python3

# Install Copyboard
pip3 install copyboard-extension

# Install system-wide
python3 scripts/install_system_wide.py
```

#### Windows

```bash
# Install Python from python.org
# Then install Copyboard
pip install copyboard-extension pywin32

# Install system-wide
python scripts/install_system_wide.py
```

## Usage

### GUI Mode

```bash
# Launch the GUI
copyboard-gui
```

### Command-Line Interface

```bash
# Show help
copyboard --help

# List all items in the clipboard board
copyboard list

# Copy an item at a specific index to the clipboard
copyboard copy 2

# Add text directly to the clipboard board
copyboard add "Some text to add"

# Clear the clipboard board
copyboard clear

# Paste a combination of items
copyboard paste-combo 0 2 3
```

### Global Hotkeys

- **Ctrl+Alt+C**: Open Copyboard GUI
- **Ctrl+Alt+X**: Copy current selection to Copyboard
- **Ctrl+Alt+V**: Paste from Copyboard (shows selection dialog)
- **Ctrl+Alt+B**: Paste combination (shows combination dialog)

## Browser Extension

The Copyboard browser extension allows you to use your clipboard board directly in web browsers.

### Installation

```bash
# Install the native messaging host
python3 scripts/install_browser_extension.py
```

Then load the unpacked extension from the `copyboard_extension/browser_extension` directory in Chrome, Firefox, or Edge.

## How It Works

Copyboard uses a simple list-based storage system to keep track of copied items. When you copy something, it's stored at the top of the list. When you paste, you can choose any item from the list.

The extension can run in multiple modes:
1. **GUI mode** - A graphical interface for easy interaction
2. **CLI mode** - Command-line tools for power users and scripting
3. **Library mode** - Import and use in your own Python code
4. **System-wide mode** - Global hotkeys for cross-application functionality
5. **File manager integration** - Integration with file managers on all platforms

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
