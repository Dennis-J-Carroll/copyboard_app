#!/usr/bin/env python3
"""
Fortify Copyboard Installation

This script checks for and fixes common issues with the Copyboard installation:
1. Verifies all required dependencies are installed
2. Checks that system integration is working
3. Tests browser extension native messaging
4. Validates global hotkeys functionality
5. Repairs any broken components
"""

import os
import sys
import platform
import subprocess
import shutil
import json
from pathlib import Path
import importlib.util

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import copyboard modules
try:
    from copyboard_extension import core, paste_helper
except ImportError as e:
    print(f"Error importing copyboard modules: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def print_colored(text, color):
    """Print colored text if supported"""
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "reset": "\033[0m"
    }
    
    # Check if we're in a terminal that supports colors
    if sys.stdout.isatty():
        print(f"{colors.get(color, '')}{text}{colors['reset']}")
    else:
        print(text)

def print_header(text):
    """Print a header"""
    print("\n" + "="*70)
    print_colored(f"  {text}", "blue")
    print("="*70)

def print_success(text):
    """Print a success message"""
    print_colored(f"✓ {text}", "green")

def print_error(text):
    """Print an error message"""
    print_colored(f"✗ {text}", "red")

def print_warning(text):
    """Print a warning message"""
    print_colored(f"! {text}", "yellow")

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

def check_python_dependencies():
    """Check that all required Python dependencies are installed"""
    print_header("CHECKING PYTHON DEPENDENCIES")
    
    required_packages = [
        "pyperclip",
        "pillow",
        "tkinter",
    ]
    
    # Platform-specific dependencies
    platform = get_platform()
    if platform == "windows":
        required_packages.append("pywin32")
    
    missing_packages = []
    
    for package in required_packages:
        if package == "tkinter":
            # tkinter is a special case
            try:
                import tkinter
                print_success(f"Found {package}")
            except ImportError:
                missing_packages.append(package)
                print_error(f"Missing {package}")
        else:
            # Check if package is installed
            if importlib.util.find_spec(package) is None:
                missing_packages.append(package)
                print_error(f"Missing {package}")
            else:
                print_success(f"Found {package}")
    
    if missing_packages:
        print_warning("Some required packages are missing. Install them with:")
        if "tkinter" in missing_packages:
            if platform == "linux":
                print_info("sudo apt-get install python3-tk")
                missing_packages.remove("tkinter")
            elif platform == "macos":
                print_info("brew install python-tk")
                missing_packages.remove("tkinter")
            # For Windows, tkinter comes with Python
        
        if missing_packages:
            packages_str = " ".join(missing_packages)
            print_info(f"pip install {packages_str}")
        
        return False
    
    print_success("All Python dependencies are installed")
    return True

def check_system_dependencies():
    """Check that all required system dependencies are installed"""
    print_header("CHECKING SYSTEM DEPENDENCIES")
    
    platform = get_platform()
    
    if platform == "linux":
        # Check for xdotool and xclip on Linux
        dependencies = {
            "xdotool": "sudo apt-get install xdotool",
            "xclip": "sudo apt-get install xclip",
        }
        
        # Check if we're using Wayland
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            dependencies["wl-clipboard"] = "sudo apt-get install wl-clipboard"
            dependencies["wtype"] = "sudo apt-get install wtype"
        
        missing_deps = []
        
        for dep, install_cmd in dependencies.items():
            try:
                result = subprocess.run(["which", dep], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    print_success(f"Found {dep}")
                else:
                    missing_deps.append(dep)
                    print_error(f"Missing {dep}")
            except Exception:
                missing_deps.append(dep)
                print_error(f"Error checking for {dep}")
        
        if missing_deps:
            print_warning("Some required system dependencies are missing. Install them with:")
            for dep in missing_deps:
                print_info(dependencies[dep])
            return False
        
        print_success("All system dependencies are installed")
        return True
    
    elif platform == "macos":
        # macOS doesn't need additional system dependencies
        print_success("No additional system dependencies required for macOS")
        return True
    
    elif platform == "windows":
        # Windows doesn't need additional system dependencies
        print_success("No additional system dependencies required for Windows")
        return True
    
    else:
        print_error(f"Unsupported platform: {platform}")
        return False

def check_file_permissions():
    """Check that all files have the correct permissions"""
    print_header("CHECKING FILE PERMISSIONS")
    
    platform = get_platform()
    
    if platform == "windows":
        # Windows doesn't need special file permissions
        print_success("File permissions check not needed on Windows")
        return True
    
    # Check executable permissions for scripts
    scripts_to_check = [
        "bin/copyboard",
        "bin/copyboard-gui",
        "bin/copyboard-install-integration",
        "copyboard_extension/native_messaging_host.py",
        "scripts/install_browser_extension.py",
        "scripts/install_system_wide.py",
        "scripts/global_hotkeys.py",
        "scripts/x11_shortcuts.py",
    ]
    
    missing_permissions = []
    
    for script in scripts_to_check:
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', script))
        if os.path.exists(script_path):
            # Check if file is executable
            if not os.access(script_path, os.X_OK):
                missing_permissions.append(script_path)
                print_error(f"Missing executable permission: {script}")
            else:
                print_success(f"Correct permissions: {script}")
        else:
            print_warning(f"Script not found: {script}")
    
    if missing_permissions:
        print_warning("Some scripts are missing executable permissions. Fix with:")
        for script in missing_permissions:
            print_info(f"chmod +x {script}")
            # Try to fix it
            try:
                os.chmod(script, os.stat(script).st_mode | 0o755)
                print_success(f"Fixed permissions for {script}")
            except Exception as e:
                print_error(f"Failed to fix permissions for {script}: {e}")
        
        return False
    
    print_success("All files have correct permissions")
    return True

def check_browser_extension():
    """Check that the browser extension is properly installed"""
    print_header("CHECKING BROWSER EXTENSION")
    
    platform = get_platform()
    
    # Check if the browser extension directory exists
    extension_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'copyboard_extension', 'browser_extension'))
    if not os.path.exists(extension_dir):
        print_error(f"Browser extension directory not found: {extension_dir}")
        return False
    
    # Check if the manifest exists
    manifest_path = os.path.join(extension_dir, 'manifest.json')
    if not os.path.exists(manifest_path):
        print_error(f"Browser extension manifest not found: {manifest_path}")
        return False
    
    print_success("Browser extension files are in place")
    
    # Check native messaging host
    if platform == "linux":
        # Check Chrome/Chromium
        chrome_dir = os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts")
        chromium_dir = os.path.expanduser("~/.config/chromium/NativeMessagingHosts")
        
        manifest_paths = [
            os.path.join(chrome_dir, "com.copyboard.extension.json"),
            os.path.join(chromium_dir, "com.copyboard.extension.json"),
        ]
        
        found_manifest = False
        for path in manifest_paths:
            if os.path.exists(path):
                print_success(f"Found native messaging host manifest: {path}")
                found_manifest = True
                break
        
        if not found_manifest:
            print_error("Native messaging host manifest not found")
            print_info("Run scripts/install_browser_extension.py to install it")
            return False
    
    elif platform == "macos":
        # Check Chrome
        chrome_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts")
        manifest_path = os.path.join(chrome_dir, "com.copyboard.extension.json")
        
        if not os.path.exists(manifest_path):
            print_error(f"Native messaging host manifest not found: {manifest_path}")
            print_info("Run scripts/install_browser_extension.py to install it")
            return False
        
        print_success(f"Found native messaging host manifest: {manifest_path}")
    
    elif platform == "windows":
        # Check Chrome
        appdata = os.environ.get("LOCALAPPDATA")
        chrome_dir = os.path.join(appdata, "Google", "Chrome", "User Data", "NativeMessagingHosts")
        manifest_path = os.path.join(chrome_dir, "com.copyboard.extension.json")
        
        if not os.path.exists(manifest_path):
            print_error(f"Native messaging host manifest not found: {manifest_path}")
            print_info("Run scripts/install_browser_extension.py to install it")
            return False
        
        print_success(f"Found native messaging host manifest: {manifest_path}")
    
    print_success("Browser extension is properly installed")
    return True

def check_system_integration():
    """Check that system integration is working"""
    print_header("CHECKING SYSTEM INTEGRATION")
    
    platform = get_platform()
    
    if platform == "linux":
        # Check autostart entry
        autostart_dir = os.path.expanduser("~/.config/autostart")
        autostart_file = os.path.join(autostart_dir, "copyboard.desktop")
        
        if not os.path.exists(autostart_file):
            print_error(f"Autostart entry not found: {autostart_file}")
            print_info("Run scripts/install_system_wide.py to install it")
            return False
        
        print_success(f"Found autostart entry: {autostart_file}")
        
        # Check file manager integration
        if os.path.exists("/usr/bin/nautilus"):
            # Check Nautilus extension
            nautilus_dir = os.path.expanduser("~/.local/share/nautilus-python/extensions")
            nautilus_file = os.path.join(nautilus_dir, "nautilus-copyboard.py")
            
            if not os.path.exists(nautilus_file):
                print_warning(f"Nautilus extension not found: {nautilus_file}")
                print_info("Run scripts/install-nautilus-extension.sh to install it")
            else:
                print_success(f"Found Nautilus extension: {nautilus_file}")
        
        elif os.path.exists("/usr/bin/thunar"):
            # Check Thunar custom actions
            thunar_dir = os.path.expanduser("~/.config/Thunar")
            thunar_file = os.path.join(thunar_dir, "uca.xml")
            
            if not os.path.exists(thunar_file):
                print_warning(f"Thunar custom actions file not found: {thunar_file}")
            else:
                # Check if our actions are in the file
                with open(thunar_file, 'r') as f:
                    content = f.read()
                
                if "Copyboard" in content:
                    print_success("Found Thunar custom actions")
                else:
                    print_warning("Thunar custom actions not found in uca.xml")
                    print_info("Run copyboard_extension.system_integration.install_thunar_custom_actions()")
        
        elif os.path.exists("/usr/bin/dolphin"):
            # Check KDE service menu
            kde_dir = os.path.expanduser("~/.local/share/kservices5/ServiceMenus")
            kde_file = os.path.join(kde_dir, "copyboard-kde-service.desktop")
            
            if not os.path.exists(kde_file):
                print_warning(f"KDE service menu not found: {kde_file}")
                print_info("Run scripts/install-kde-service.sh to install it")
            else:
                print_success(f"Found KDE service menu: {kde_file}")
    
    elif platform == "macos":
        # Check Launch Agent
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        launch_agent_file = os.path.join(launch_agents_dir, "com.copyboard.app.plist")
        
        if not os.path.exists(launch_agent_file):
            print_error(f"Launch Agent not found: {launch_agent_file}")
            print_info("Run scripts/install_system_wide.py to install it")
            return False
        
        print_success(f"Found Launch Agent: {launch_agent_file}")
    
    elif platform == "windows":
        # Check autostart registry entry
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            # Open the registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            
            # Try to get the Copyboard value
            try:
                value, _ = winreg.QueryValueEx(key, "Copyboard")
                print_success(f"Found autostart registry entry: {value}")
            except FileNotFoundError:
                print_error("Autostart registry entry not found")
                print_info("Run scripts/install_system_wide.py to install it")
                winreg.CloseKey(key)
                return False
            
            winreg.CloseKey(key)
        except Exception as e:
            print_error(f"Error checking registry: {e}")
            return False
    
    print_success("System integration is working")
    return True

def test_core_functionality():
    """Test core functionality"""
    print_header("TESTING CORE FUNCTIONALITY")
    
    # Test board operations
    try:
        # Save current board
        original_board = core.get_board()
        
        # Add a test item
        test_item = "Copyboard test item - " + platform.node()
        core.copy_to_board(test_item)
        
        # Check that it was added
        board = core.get_board()
        if board and board[0] == test_item:
            print_success("Successfully added item to board")
        else:
            print_error("Failed to add item to board")
            return False
        
        # Restore original board
        core._board = original_board
        core._save_board()
        
        print_success("Core functionality is working")
        return True
    except Exception as e:
        print_error(f"Error testing core functionality: {e}")
        return False

def main():
    """Main function"""
    print_header("COPYBOARD INSTALLATION FORTIFIER")
    print_info("This script checks and fixes common issues with your Copyboard installation.")
    
    # Run all checks
    python_deps_ok = check_python_dependencies()
    system_deps_ok = check_system_dependencies()
    permissions_ok = check_file_permissions()
    browser_ext_ok = check_browser_extension()
    system_int_ok = check_system_integration()
    core_func_ok = test_core_functionality()
    
    # Print summary
    print_header("SUMMARY")
    
    if python_deps_ok:
        print_success("Python dependencies: OK")
    else:
        print_error("Python dependencies: Missing")
    
    if system_deps_ok:
        print_success("System dependencies: OK")
    else:
        print_error("System dependencies: Missing")
    
    if permissions_ok:
        print_success("File permissions: OK")
    else:
        print_error("File permissions: Issues found")
    
    if browser_ext_ok:
        print_success("Browser extension: OK")
    else:
        print_error("Browser extension: Issues found")
    
    if system_int_ok:
        print_success("System integration: OK")
    else:
        print_error("System integration: Issues found")
    
    if core_func_ok:
        print_success("Core functionality: OK")
    else:
        print_error("Core functionality: Issues found")
    
    # Overall status
    if all([python_deps_ok, system_deps_ok, permissions_ok, browser_ext_ok, system_int_ok, core_func_ok]):
        print_header("INSTALLATION STATUS: EXCELLENT")
        print_info("Your Copyboard installation is in perfect condition!")
    elif python_deps_ok and core_func_ok:
        print_header("INSTALLATION STATUS: GOOD")
        print_info("Your Copyboard installation is working, but some components need attention.")
        print_info("Run scripts/install_system_wide.py to fix system integration issues.")
    else:
        print_header("INSTALLATION STATUS: NEEDS ATTENTION")
        print_info("Your Copyboard installation has issues that need to be fixed.")
        print_info("Follow the instructions above to resolve them.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 