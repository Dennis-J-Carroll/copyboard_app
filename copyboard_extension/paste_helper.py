"""
Cross-platform paste helper for Copyboard

This module provides platform-specific paste functionality for Linux, macOS, and Windows.
"""

import os
import sys
import subprocess
import platform
import time
import threading
from dataclasses import dataclass
from typing import Optional

# Platform detection
PLATFORM = platform.system().lower()


@dataclass(frozen=True)
class FocusTarget:
    """Opaque handle for the window that should receive a quick paste."""

    platform: str
    token: int


def capture_active_window() -> Optional[FocusTarget]:
    """Capture the foreground window without changing focus."""
    system = get_platform()
    try:
        if system == "windows":
            import ctypes

            handle = int(ctypes.windll.user32.GetForegroundWindow())
            return FocusTarget(system, handle) if handle else None
        if system == "macos":
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get unix id of first process whose frontmost is true',
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return FocusTarget(system, int(result.stdout.strip()))

        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            check=True,
        )
        return FocusTarget(system, int(result.stdout.strip()))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def restore_active_window(target: Optional[FocusTarget]) -> bool:
    """Return focus to a window captured before the widget was used."""
    if target is None or target.platform != get_platform():
        return False
    try:
        if target.platform == "windows":
            import ctypes

            return bool(ctypes.windll.user32.SetForegroundWindow(target.token))
        if target.platform == "macos":
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    (
                        'tell application "System Events" to set frontmost of '
                        f"first process whose unix id is {target.token} to true"
                    ),
                ],
                check=True,
            )
            return True

        subprocess.run(
            ["xdotool", "windowactivate", "--sync", str(target.token)], check=True
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False

def get_platform():
    """Detect the current platform"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"

def paste_text_linux(text):
    """Paste text on Linux using xdotool or wl-paste"""
    # Check if we're using X11 or Wayland
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    
    if session_type == "wayland":
        # For Wayland, use wl-clipboard
        try:
            # First, copy the text to clipboard
            process = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            process.communicate(input=text.encode())
            
            # Then simulate Ctrl+V to paste
            subprocess.run(["wtype", "-k", "ctrl+v"], check=True)
            return True
        except Exception as e:
            print(f"Error pasting with wl-clipboard: {e}")
            return False
    else:
        # For X11, use xdotool
        try:
            # First, copy the text to clipboard
            process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            process.communicate(input=text.encode())
            
            # Then simulate Ctrl+V to paste
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True)
            return True
        except Exception as e:
            print(f"Error pasting with xdotool: {e}")
            return False

def paste_text_macos(text):
    """Paste text on macOS using osascript"""
    try:
        # Escape double quotes in the text
        escaped_text = text.replace('"', '\\"')
        
        # Use AppleScript to paste the text
        script = f'''
        tell application "System Events"
            set the clipboard to "{escaped_text}"
            keystroke "v" using command down
        end tell
        '''
        
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception as e:
        print(f"Error pasting with osascript: {e}")
        return False

def paste_text_windows(text):
    """Paste text on Windows using pywin32"""
    try:
        import win32clipboard
        import win32con
        import win32api
        import win32gui
        
        # Copy text to clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        
        # Simulate Ctrl+V keystroke
        win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        win32api.keybd_event(0x56, 0, 0, 0)  # V down
        win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)  # V up
        win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)  # Ctrl up
        
        return True
    except Exception as e:
        print(f"Error pasting with win32api: {e}")
        return False

def paste_text(text):
    """Paste text using platform-specific method"""
    platform = get_platform()
    
    if platform == "linux":
        return paste_text_linux(text)
    elif platform == "macos":
        return paste_text_macos(text)
    elif platform == "windows":
        return paste_text_windows(text)
    else:
        print(f"Unsupported platform: {platform}")
        return False

def paste_current_clipboard() -> bool:
    """
    Automatically paste the current clipboard content at the cursor position
    Uses platform-specific key simulation to trigger paste
    
    Returns:
        True if paste command was sent, False if platform is unsupported
    """
    # Use a separate thread to avoid blocking the main operation
    paste_thread = threading.Thread(target=_paste_async)
    paste_thread.daemon = True
    paste_thread.start()
    return True

def _paste_async() -> None:
    """Internal function to perform paste operation asynchronously"""
    if PLATFORM == 'linux':
        _paste_linux()
    elif PLATFORM == 'darwin':
        _paste_macos()
    elif PLATFORM == 'windows':
        _paste_windows()

def _paste_linux() -> None:
    """Paste on Linux using xdotool"""
    try:
        # First check if xdotool is installed
        subprocess.run(['which', 'xdotool'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Use xdotool to simulate Ctrl+V
        subprocess.run(['xdotool', 'key', 'ctrl+v'], check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        try:
            # Try alternative method using xvkbd
            subprocess.run(['which', 'xvkbd'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['xvkbd', '-text', r'\Cv'], check=False)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

def _paste_macos() -> None:
    """Paste on macOS using AppleScript"""
    try:
        # Use AppleScript to simulate Command+V
        applescript = '''
        tell application "System Events"
            keystroke "v" using command down
        end tell
        '''
        subprocess.run(['osascript', '-e', applescript], check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

def _paste_windows() -> None:
    """Paste on Windows using SendKeys or PowerShell"""
    try:
        # Try PowerShell method
        ps_script = '''
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.SendKeys]::SendWait("^v");
        '''
        subprocess.run(['powershell', '-Command', ps_script], check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

def paste_with_delay(delay_ms: int = 100) -> bool:
    """
    Paste with a specified delay (useful for some applications)
    
    Args:
        delay_ms: Delay in milliseconds before pasting
        
    Returns:
        True if paste command was scheduled
    """
    def delayed_paste():
        import time
        time.sleep(delay_ms / 1000.0)
        _paste_async()
    
    paste_thread = threading.Thread(target=delayed_paste)
    paste_thread.daemon = True
    paste_thread.start()
    return True

# Try to import optional dependencies for better platform support
try:
    import keyboard as kb
    
    def paste_using_keyboard() -> bool:
        """Use the keyboard library for more reliable pasting"""
        kb.press_and_release('ctrl+v')
        return True
        
except ImportError:
    def paste_using_keyboard() -> bool:
        """Fallback when keyboard library is not available"""
        return paste_current_clipboard()

def paste_combination(items: list) -> bool:
    """
    Concatenate multiple clipboard items and paste them.
    
    Args:
        items: List of strings to concatenate and paste
        
    Returns:
        True if successful, False otherwise
    """
    import pyperclip
    
    if not items:
        return False
        
    # Concatenate all items
    combined_content = ''.join(items)
    
    # Copy to clipboard
    pyperclip.copy(combined_content)
    
    # Paste
    return paste_current_clipboard()
