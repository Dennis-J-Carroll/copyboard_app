# Copyboard Browser Extension

## Overview

This browser extension integrates with the Copyboard clipboard manager application, allowing you to:

1. Copy text from web pages to your Copyboard clipboard history
2. Paste items from your clipboard history into web pages
3. Use a radial menu for quick visual selection of clipboard items

## Installation

### 1. Install the Native Messaging Host

First, you need to install the native messaging host to allow the browser extension to communicate with Copyboard:

```bash
# Navigate to the copyboard_extension directory
cd /path/to/copyboard_extension

# Run the installation script
python install_browser_extension.py
```

This will install the necessary files for Chrome/Chromium and Firefox.

### 2. Install the Browser Extension

#### Chrome/Chromium

1. Open Chrome/Chromium and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top-right corner
3. Click "Load unpacked" and select the `browser_extension` directory
4. The extension should now appear in your toolbar

#### Firefox

1. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on..."
3. Navigate to the `browser_extension` directory and select any file
4. The extension should now appear in your toolbar

## Usage

### Copy Text

1. Select text on any webpage
2. Right-click and select "Copyboard > Copy to Clipboard Board"
3. The text is now saved in your Copyboard clipboard history

### Paste from Clipboard

1. Right-click in any text field
2. Select "Copyboard > Paste from Clipboard Board"
3. Select the item you want to paste from the submenu

### Paste with Radial Menu

1. Right-click in any text field
2. Select "Copyboard > Paste with Radial Menu"
3. A radial menu will appear with your clipboard items
4. Click an item to paste it or press the number key (1-9) that corresponds to the item

## Troubleshooting

### Native Messaging Issues

If the extension isn't communicating with Copyboard:

1. Check the error badge on the extension icon
2. Look at the browser console (F12) for error messages
3. Check the native messaging log at `~/.config/copyboard/native_messaging.log`
4. Try reinstalling the native messaging host with `python install_browser_extension.py`

### Clipboard Issues

If copying or pasting isn't working:

1. Make sure the Copyboard application is running
2. Check if the clipboard items appear in the extension popup
3. Try using the test tools: `python test_core.py` and `python test_native_host.py`

## Development

The extension consists of:

- `manifest.json`: Extension configuration
- `background.js`: Handles context menus and native messaging
- `content.js`: Handles copying/pasting in web pages
- `popup.html/js`: Provides a UI for viewing clipboard items

For debugging:
- Enable verbose logging in the browser console
- Monitor the native messaging log

## License

This extension is part of the Copyboard project.
