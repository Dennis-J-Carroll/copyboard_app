# Implementation and Testing Guide

This guide provides detailed instructions on implementing and testing the Copyboard Extension's rapid-fire clipboard functionality.

## Implementation Steps

### 1. Installation

First, install the necessary packages:

```bash
# Install main package and dependencies
pip install copyboard-extension pyperclip

# For hotkey support (optional but recommended)
pip install keyboard

# Platform-specific dependencies
# Linux (X11)
sudo apt-get install xclip xdotool
# Linux (Wayland)
sudo apt-get install wl-clipboard wtype
# macOS and Windows have no additional dependencies
```

### 2. Basic Implementation

Here's how to implement basic clipboard operations:

```python
# Import the rapid clipboard module
from copyboard_extension.rapid_clipboard import copy, paste, copy_paste

# Function to copy text
def copy_text(text):
    copy(text)
    print(f"Copied: {text}")

# Function to paste from history
def paste_item(index=0):
    success = paste(index)
    print(f"Paste from index {index}: {'Success' if success else 'Failed'}")

# Function for immediate copy-paste
def quick_paste(text):
    success = copy_paste(text)
    print(f"Quick paste: {'Success' if success else 'Failed'}")
```

### 3. Advanced Implementation

For more control over the clipboard functionality:

```python
from copyboard_extension.rapid_clipboard import RapidClipboard
from copyboard_extension import core, hotkeys

# Configure clipboard size
def setup_clipboard(max_items=20):
    RapidClipboard.set_max_items(max_items)
    print(f"Configured clipboard with {max_items} max items")

# Show clipboard contents
def show_clipboard():
    items = RapidClipboard.get_items()
    if not items:
        print("Clipboard is empty")
        return
    
    print("Clipboard contents:")
    for i, item in enumerate(items):
        preview = item[:30] + "..." if len(item) > 30 else item
        preview = preview.replace("\n", "↵")
        print(f"{i}: {preview}")

# Custom hotkey setup
def setup_custom_hotkeys():
    # Only works if keyboard module is installed
    try:
        # Change existing hotkey
        hotkeys.change_hotkey("copy_to_board", "ctrl+alt+c")
        
        # Register custom function hotkey
        def custom_function():
            print("Custom hotkey triggered!")
            # Do something useful here
        
        hotkeys.register_hotkey("ctrl+alt+x", custom_function)
        print("Custom hotkeys configured")
    except Exception as e:
        print(f"Failed to set up hotkeys: {e}")
```

### 4. Creating a Complete Application

```python
import tkinter as tk
from copyboard_extension.rapid_clipboard import RapidClipboard

class ClipboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Clipboard Manager")
        
        # Create widgets
        self.history_listbox = tk.Listbox(root, width=50, height=10)
        self.history_listbox.pack(padx=10, pady=10)
        
        self.copy_entry = tk.Entry(root, width=50)
        self.copy_entry.pack(padx=10, pady=(0, 10))
        
        button_frame = tk.Frame(root)
        button_frame.pack(padx=10, pady=(0, 10))
        
        tk.Button(button_frame, text="Copy", command=self.copy_text).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Paste Selected", command=self.paste_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear History", command=self.clear_history).pack(side=tk.LEFT, padx=5)
        
        # Refresh history on startup
        self.refresh_history()
    
    def copy_text(self):
        text = self.copy_entry.get()
        if text:
            RapidClipboard.copy(text)
            self.copy_entry.delete(0, tk.END)
            self.refresh_history()
    
    def paste_selected(self):
        selected = self.history_listbox.curselection()
        if selected:
            index = selected[0]
            RapidClipboard.paste(index)
    
    def clear_history(self):
        RapidClipboard.clear()
        self.refresh_history()
    
    def refresh_history(self):
        self.history_listbox.delete(0, tk.END)
        items = RapidClipboard.get_items()
        for item in items:
            preview = item[:50] + "..." if len(item) > 50 else item
            preview = preview.replace("\n", "↵")
            self.history_listbox.insert(tk.END, preview)

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = ClipboardApp(root)
    root.mainloop()
```

## Testing Procedures

### 1. Basic Functionality Testing

Create a simple test script to verify core functionality:

```python
# test_clipboard.py
from copyboard_extension.rapid_clipboard import copy, paste, get_items, clear

def test_basic_operations():
    print("Testing basic clipboard operations...")
    
    # Clear clipboard to start fresh
    clear()
    
    # Test copying
    test_items = ["Test item 1", "Test item 2", "Test item 3"]
    for item in test_items:
        copy(item)
    
    # Verify items were copied correctly
    items = get_items()
    assert len(items) == 3, f"Expected 3 items, got {len(items)}"
    assert items[0] == "Test item 3", f"Expected 'Test item 3', got '{items[0]}'"
    assert items[1] == "Test item 2", f"Expected 'Test item 2', got '{items[1]}'"
    assert items[2] == "Test item 1", f"Expected 'Test item 1', got '{items[2]}'"
    
    print("Basic clipboard operations working correctly!")

if __name__ == "__main__":
    test_basic_operations()
```

### 2. Paste Testing

Testing paste functionality requires manual verification:

```python
# test_paste.py
from copyboard_extension.rapid_clipboard import copy, paste, copy_paste, clear
import time

def test_paste_operations():
    print("Testing paste operations...")
    
    # Clear clipboard to start fresh
    clear()
    
    # Add test items
    test_items = ["First item", "Second item", "Third item"]
    for item in test_items:
        copy(item)
    
    print("\nManual verification required:")
    
    # Open a text editor or input field before continuing
    input("Open a text editor or input field, then press Enter to continue...")
    
    # Test basic paste
    print("Testing paste from index 0 (should paste 'Third item')...")
    paste(0)
    input("Did 'Third item' paste correctly? Press Enter to continue...")
    
    # Test paste from different index
    print("Testing paste from index 1 (should paste 'Second item')...")
    paste(1)
    input("Did 'Second item' paste correctly? Press Enter to continue...")
    
    # Test quick copy-paste
    print("Testing quick copy-paste (should paste 'DIRECT PASTE TEST')...")
    copy_paste("DIRECT PASTE TEST")
    input("Did 'DIRECT PASTE TEST' paste correctly? Press Enter to continue...")
    
    print("Paste testing complete!")

if __name__ == "__main__":
    test_paste_operations()
```

### 3. Hotkey Testing

Testing hotkeys also requires manual verification:

```python
# test_hotkeys.py
from copyboard_extension import hotkeys, core
import time

def test_hotkey_setup():
    print("Testing hotkey functionality...")
    
    # Configure hotkeys
    try:
        hotkeys.setup_default_hotkeys(core)
        print("Default hotkeys configured.")
        print("\nTo test hotkeys, try the following combinations:")
        print("- Ctrl+Shift+C: Copy current selection")
        print("- Ctrl+Shift+V: Paste most recent item")
        print("- Ctrl+Shift+Left/Right: Cycle through clipboard history")
        print("- Ctrl+Alt+1 through Ctrl+Alt+5: Quick paste items 1-5")
        
        # Keep script running to test hotkeys
        print("\nScript will run for 60 seconds. Try the hotkeys...")
        for i in range(60):
            print(f"Time remaining: {60-i} seconds", end="\r")
            time.sleep(1)
        
        print("\nHotkey testing complete!")
    except Exception as e:
        print(f"Failed to set up hotkeys: {e}")

if __name__ == "__main__":
    test_hotkey_setup()
```

### 4. Performance Testing

Test the rapid-fire performance:

```python
# test_performance.py
from copyboard_extension.rapid_clipboard import copy, paste, copy_paste, clear
import time

def test_rapid_fire_performance():
    print("Testing rapid-fire clipboard performance...")
    
    # Clear clipboard to start fresh
    clear()
    
    # Test rapid-fire copy operations
    print("Testing rapid copy operations...")
    start_time = time.time()
    for i in range(100):
        copy(f"Test item {i}")
    end_time = time.time()
    copy_time = end_time - start_time
    print(f"Time to copy 100 items: {copy_time:.4f} seconds ({copy_time/100:.6f} seconds per item)")
    
    # Open a text editor for paste testing
    input("\nOpen a text editor or input field, then press Enter to continue...")
    
    # Test rapid-fire paste operations
    print("Testing rapid paste operations...")
    print("Will paste 10 items with 1-second intervals...")
    
    for i in range(10):
        print(f"Pasting item {i}...")
        paste(i)
        time.sleep(1)
    
    # Test rapid-fire copy-paste operations
    print("\nTesting rapid copy-paste operations...")
    input("Press Enter when ready...")
    
    start_time = time.time()
    for i in range(10):
        print(f"Copy-pasting item {i}...")
        copy_paste(f"Quick item {i}")
        time.sleep(1)
    end_time = time.time()
    
    print("Performance testing complete!")

if __name__ == "__main__":
    test_rapid_fire_performance()
```

## Troubleshooting Common Issues

### 1. Paste Not Working

If paste operations aren't working:

1. Check if you have the required platform dependencies:
   - Linux: `xclip` and `xdotool` for X11, `wl-clipboard` and `wtype` for Wayland
   - macOS: Ensure script has accessibility permissions
   - Windows: No special requirements

2. Try using delayed paste:
   ```python
   from copyboard_extension.rapid_clipboard import RapidClipboard
   
   # Use a longer delay (500ms)
   RapidClipboard.delayed_paste(0, 500)
   ```

3. Check if the target application blocks programmatic paste:
   - Some secure applications (password managers, banking sites) may block this
   - Try manually pressing Ctrl+V after the copy operation

### 2. Hotkeys Not Working

If hotkeys aren't working:

1. Ensure the `keyboard` package is installed:
   ```bash
   pip install keyboard
   ```

2. On Linux, the script may need root privileges:
   ```bash
   sudo python your_script.py
   ```

3. Check for conflicting hotkeys with other applications

4. Try different key combinations:
   ```python
   from copyboard_extension import hotkeys
   
   hotkeys.change_hotkey("paste_recent", "ctrl+alt+v")  # Change to non-conflicting hotkey
   ```

### 3. Performance Optimization

If you need to optimize performance:

1. Increase save delay to reduce disk I/O:
   ```python
   # Access core module directly to modify performance settings
   from copyboard_extension import core
   
   # Modify save delay (in seconds)
   core.AUTO_SAVE_DELAY = 5.0  # Default is 2.0
   
   # Modify batch size
   core.SAVE_BATCH_SIZE = 10  # Default is 3
   ```

2. Reduce maximum history size for memory optimization:
   ```python
   from copyboard_extension.rapid_clipboard import RapidClipboard
   
   # Set smaller history size
   RapidClipboard.set_max_items(5)  # Default is 10
   ``` 