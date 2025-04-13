# Copyboard Extension

A rapid-fire clipboard manager that enables fast and efficient copy-paste operations across applications.

## Features

- **Rapid-fire Copy-Paste**: Optimized for speed with minimal latency
- **Multi-Clipboard History**: Store and access multiple clipboard items
- **Keyboard Shortcuts**: Quick access to clipboard history via hotkeys
- **Cross-Platform**: Works on Linux, macOS, and Windows
- **Background Saving**: Automatic persistence of clipboard history

## Installation

```bash
# Install from PyPI
pip install copyboard-extension

# Install dependencies for enhanced functionality
# Linux (X11)
sudo apt-get install xclip xdotool
# Linux (Wayland)
sudo apt-get install wl-clipboard wtype
```

## Quick Start

```python
# Import the rapid clipboard module for fastest operations
from copyboard_extension.rapid_clipboard import copy, paste, copy_paste

# One-step copy-paste (fastest)
copy_paste("Quick text")

# Copy to clipboard history
copy("Item 1")
copy("Item 2")

# Paste from history (index 0 is most recent)
paste(0)  # Pastes "Item 2"
paste(1)  # Pastes "Item 1"
```

## Using Keyboard Shortcuts

Default keyboard shortcuts (can be customized):

- `Ctrl+Shift+C` - Copy current selection to clipboard history
- `Ctrl+Shift+V` - Paste most recent item 
- `Ctrl+Shift+A` - Paste all items concatenated
- `Ctrl+Shift+Left/Right` - Cycle through clipboard history
- `Ctrl+Alt+1` through `Ctrl+Alt+5` - Quick paste items 1-5

## Advanced Usage

```python
from copyboard_extension import core, hotkeys
from copyboard_extension.rapid_clipboard import RapidClipboard

# Get clipboard history
items = RapidClipboard.get_items()

# Preview clipboard contents
previews = RapidClipboard.preview_items(max_length=40)
for idx, preview in previews.items():
    print(preview)

# Clear clipboard history
RapidClipboard.clear()

# Configure max history size
RapidClipboard.set_max_items(20)

# Use delayed paste for applications that need it
RapidClipboard.delayed_paste(index=0, delay_ms=200)

# Customize hotkeys
hotkeys.change_hotkey("paste_recent", "alt+v")
```

## Performance Optimization

The extension is optimized for rapid-fire operations:
- In-memory caching minimizes disk access
- Delayed saving prevents I/O bottlenecks
- Asynchronous paste operations avoid blocking
- Background thread ensures persistence

## Requirements

- Python 3.6+
- pyperclip
- keyboard (optional, for hotkey support)

## Platform-Specific Notes

### Linux
- Requires X11 utilities (xclip, xdotool) or Wayland equivalents (wl-clipboard, wtype)
- May require `sudo apt-get install python3-dev` for some dependencies

### macOS
- Uses AppleScript for paste operations
- May require accessibility permissions

### Windows
- Uses win32api or PowerShell for paste operations
- No additional requirements

## Troubleshooting

If paste operations aren't working:
1. Ensure platform-specific dependencies are installed
2. Check application permissions
3. Try using `delayed_paste()` with longer delay for some applications

## License

MIT 