#!/usr/bin/env python3
"""
Test All Platforms

This script tests Copyboard functionality across all supported platforms.
It detects the current platform and runs appropriate tests.
"""

import os
import sys
import platform
import subprocess
import tempfile
import time
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import copyboard modules
try:
    from copyboard_extension import core, paste_helper
except ImportError as e:
    print(f"Error importing copyboard modules: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def print_header(text):
    """Print a header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_success(text):
    """Print a success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print an error message"""
    print(f"✗ {text}")

def print_info(text):
    """Print an info message"""
    print(f"  {text}")

def get_platform():
    """Detect the current platform"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"

def test_core_functionality():
    """Test core clipboard board functionality"""
    print_header("TESTING CORE FUNCTIONALITY")
    
    # Test board operations
    try:
        # Save current board
        original_board = core.get_board()
        
        # Clear the board
        core.clear_board()
        
        # Add some test items
        test_items = [
            "Copyboard test item 1",
            "Copyboard test item 2",
            "Copyboard test item 3",
        ]
        
        for item in test_items:
            core.copy_to_board(item)
        
        # Check that they were added in the right order
        board = core.get_board()
        if len(board) != 3:
            print_error(f"Expected 3 items, got {len(board)}")
            return False
        
        if board[0] != test_items[2]:
            print_error(f"Expected '{test_items[2]}', got '{board[0]}'")
            return False
        
        # Test removing an item
        core.drop_item(1)  # Remove the middle item
        
        board = core.get_board()
        if len(board) != 2:
            print_error(f"Expected 2 items after removal, got {len(board)}")
            return False
        
        # Test clearing the board
        core.clear_board()
        
        board = core.get_board()
        if len(board) != 0:
            print_error(f"Expected empty board after clearing, got {len(board)}")
            return False
        
        # Restore original board
        core._board = original_board
        core._save_board()
        
        print_success("Core functionality tests passed")
        return True
    except Exception as e:
        print_error(f"Error testing core functionality: {e}")
        return False

def test_paste_helper():
    """Test paste helper functionality"""
    print_header("TESTING PASTE HELPER")
    
    platform_name = get_platform()
    
    # Test platform detection
    detected_platform = paste_helper.get_platform()
    if detected_platform != platform_name:
        print_error(f"Platform detection failed: expected '{platform_name}', got '{detected_platform}'")
        return False
    
    print_success(f"Platform detection: {detected_platform}")
    
    # Test paste_text function (without actually pasting)
    try:
        # We'll just check if the function runs without errors
        # We can't fully test the paste functionality in an automated test
        
        # Create a test string
        test_string = f"Copyboard test string - {time.time()}"
        
        print_info(f"Testing paste_text with: '{test_string[:20]}...'")
        
        # Call the function but catch any errors
        try:
            # We'll set a timeout to avoid hanging if something goes wrong
            if platform_name == "windows":
                # Windows doesn't support os.fork, so we can't use the timeout approach
                print_info("Skipping actual paste test on Windows")
            else:
                # Use a child process with timeout
                pid = os.fork()
                if pid == 0:  # Child process
                    try:
                        paste_helper.paste_text(test_string)
                        os._exit(0)
                    except Exception as e:
                        print_error(f"Error in paste_text: {e}")
                        os._exit(1)
                else:  # Parent process
                    # Wait for child with timeout
                    start_time = time.time()
                    while time.time() - start_time < 2:  # 2 second timeout
                        pid_result, status = os.waitpid(pid, os.WNOHANG)
                        if pid_result != 0:
                            if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                                print_success("paste_text executed successfully")
                            else:
                                print_error("paste_text failed")
                                return False
                            break
                        time.sleep(0.1)
                    else:
                        # Timeout
                        os.kill(pid, 9)
                        print_error("paste_text timed out")
                        return False
        except Exception as e:
            print_error(f"Error testing paste_text: {e}")
            return False
        
        print_success("Paste helper tests passed")
        return True
    except Exception as e:
        print_error(f"Error testing paste helper: {e}")
        return False

def test_platform_specific():
    """Test platform-specific functionality"""
    print_header("TESTING PLATFORM-SPECIFIC FUNCTIONALITY")
    
    platform_name = get_platform()
    
    if platform_name == "linux":
        return test_linux_specific()
    elif platform_name == "macos":
        return test_macos_specific()
    elif platform_name == "windows":
        return test_windows_specific()
    else:
        print_error(f"Unsupported platform: {platform_name}")
        return False

def test_linux_specific():
    """Test Linux-specific functionality"""
    print_info("Testing Linux-specific functionality")
    
    # Test if xdotool is available
    try:
        result = subprocess.run(["which", "xdotool"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print_success("xdotool is available")
        else:
            print_error("xdotool not found")
            print_info("Install it with: sudo apt-get install xdotool")
            return False
    except Exception as e:
        print_error(f"Error checking for xdotool: {e}")
        return False
    
    # Test if xclip is available
    try:
        result = subprocess.run(["which", "xclip"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print_success("xclip is available")
        else:
            print_error("xclip not found")
            print_info("Install it with: sudo apt-get install xclip")
            return False
    except Exception as e:
        print_error(f"Error checking for xclip: {e}")
        return False
    
    # Check if we're using Wayland
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        print_info("Detected Wayland session")
        
        # Test if wl-clipboard is available
        try:
            result = subprocess.run(["which", "wl-copy"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print_success("wl-clipboard is available")
            else:
                print_error("wl-clipboard not found")
                print_info("Install it with: sudo apt-get install wl-clipboard")
                return False
        except Exception as e:
            print_error(f"Error checking for wl-clipboard: {e}")
            return False
        
        # Test if wtype is available
        try:
            result = subprocess.run(["which", "wtype"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print_success("wtype is available")
            else:
                print_error("wtype not found")
                print_info("Install it with: sudo apt-get install wtype")
                return False
        except Exception as e:
            print_error(f"Error checking for wtype: {e}")
            return False
    else:
        print_info("Detected X11 session")
    
    # Test file manager integration
    if os.path.exists("/usr/bin/nautilus"):
        print_info("Detected Nautilus file manager")
        
        # Check if the Nautilus extension is installed
        nautilus_dir = os.path.expanduser("~/.local/share/nautilus-python/extensions")
        nautilus_file = os.path.join(nautilus_dir, "nautilus-copyboard.py")
        
        if os.path.exists(nautilus_file):
            print_success("Nautilus extension is installed")
        else:
            print_error("Nautilus extension not found")
            print_info("Install it with: scripts/install-nautilus-extension.sh")
            return False
    elif os.path.exists("/usr/bin/thunar"):
        print_info("Detected Thunar file manager")
        
        # Check if Thunar custom actions are installed
        thunar_dir = os.path.expanduser("~/.config/Thunar")
        thunar_file = os.path.join(thunar_dir, "uca.xml")
        
        if os.path.exists(thunar_file):
            # Check if our actions are in the file
            with open(thunar_file, 'r') as f:
                content = f.read()
            
            if "Copyboard" in content:
                print_success("Thunar custom actions are installed")
            else:
                print_error("Thunar custom actions not found")
                print_info("Install them with: copyboard_extension.system_integration.install_thunar_custom_actions()")
                return False
        else:
            print_error("Thunar custom actions file not found")
            return False
    elif os.path.exists("/usr/bin/dolphin"):
        print_info("Detected Dolphin file manager")
        
        # Check if KDE service menu is installed
        kde_dir = os.path.expanduser("~/.local/share/kservices5/ServiceMenus")
        kde_file = os.path.join(kde_dir, "copyboard-kde-service.desktop")
        
        if os.path.exists(kde_file):
            print_success("KDE service menu is installed")
        else:
            print_error("KDE service menu not found")
            print_info("Install it with: scripts/install-kde-service.sh")
            return False
    
    print_success("Linux-specific tests passed")
    return True

def test_macos_specific():
    """Test macOS-specific functionality"""
    print_info("Testing macOS-specific functionality")
    
    # Test if osascript is available
    try:
        result = subprocess.run(["which", "osascript"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print_success("osascript is available")
        else:
            print_error("osascript not found")
            return False
    except Exception as e:
        print_error(f"Error checking for osascript: {e}")
        return False
    
    # Check if Launch Agent is installed
    launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
    launch_agent_file = os.path.join(launch_agents_dir, "com.copyboard.app.plist")
    
    if os.path.exists(launch_agent_file):
        print_success("Launch Agent is installed")
    else:
        print_error("Launch Agent not found")
        print_info("Install it with: scripts/install_system_wide.py")
        return False
    
    # Check if browser extension native messaging host is installed
    chrome_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts")
    manifest_path = os.path.join(chrome_dir, "com.copyboard.extension.json")
    
    if os.path.exists(manifest_path):
        print_success("Browser extension native messaging host is installed")
    else:
        print_error("Browser extension native messaging host not found")
        print_info("Install it with: scripts/install_browser_extension.py")
        return False
    
    print_success("macOS-specific tests passed")
    return True

def test_windows_specific():
    """Test Windows-specific functionality"""
    print_info("Testing Windows-specific functionality")
    
    # Test if pywin32 is available
    try:
        import win32clipboard
        import win32con
        import win32api
        print_success("pywin32 is available")
    except ImportError:
        print_error("pywin32 not found")
        print_info("Install it with: pip install pywin32")
        return False
    
    # Check if autostart registry entry is installed
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Open the registry key
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        
        # Try to get the Copyboard value
        try:
            value, _ = winreg.QueryValueEx(key, "Copyboard")
            print_success("Autostart registry entry is installed")
        except FileNotFoundError:
            print_error("Autostart registry entry not found")
            print_info("Install it with: scripts/install_system_wide.py")
            winreg.CloseKey(key)
            return False
        
        winreg.CloseKey(key)
    except Exception as e:
        print_error(f"Error checking registry: {e}")
        return False
    
    # Check if Explorer context menu is installed
    try:
        import winreg
        key_path = r"*\shell\CopyboardAdd"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path, 0, winreg.KEY_READ)
            print_success("Explorer context menu is installed")
            winreg.CloseKey(key)
        except FileNotFoundError:
            print_error("Explorer context menu not found")
            print_info("Install it with: scripts/install_system_wide.py")
            return False
    except Exception as e:
        print_error(f"Error checking registry: {e}")
        return False
    
    # Check if browser extension native messaging host is installed
    try:
        import winreg
        key_path = r"Software\Google\Chrome\NativeMessagingHosts\com.copyboard.extension"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            print_success("Browser extension native messaging host is installed")
            winreg.CloseKey(key)
        except FileNotFoundError:
            print_error("Browser extension native messaging host not found")
            print_info("Install it with: scripts/install_browser_extension.py")
            return False
    except Exception as e:
        print_error(f"Error checking registry: {e}")
        return False
    
    print_success("Windows-specific tests passed")
    return True

def main():
    """Main function"""
    print_header("COPYBOARD CROSS-PLATFORM TESTS")
    print_info(f"Running tests on {platform.system()} ({get_platform()})")
    
    # Run tests
    core_ok = test_core_functionality()
    paste_ok = test_paste_helper()
    platform_ok = test_platform_specific()
    
    # Print summary
    print_header("TEST SUMMARY")
    
    if core_ok:
        print_success("Core functionality: PASSED")
    else:
        print_error("Core functionality: FAILED")
    
    if paste_ok:
        print_success("Paste helper: PASSED")
    else:
        print_error("Paste helper: FAILED")
    
    if platform_ok:
        print_success("Platform-specific functionality: PASSED")
    else:
        print_error("Platform-specific functionality: FAILED")
    
    # Overall status
    if all([core_ok, paste_ok, platform_ok]):
        print_header("ALL TESTS PASSED")
        return 0
    else:
        print_header("SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 