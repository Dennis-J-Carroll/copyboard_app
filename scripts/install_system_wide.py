#!/usr/bin/env python3
"""
Cross-platform system-wide installer for Copyboard

This script installs Copyboard to run system-wide on Linux, macOS, and Windows.
It handles:
1. Autostart configuration
2. File manager integration
3. Browser extension native messaging host
4. Global hotkeys setup
"""

import os
import sys
import shutil
import subprocess
import json
import platform
from pathlib import Path

def get_platform():
    """Detect the current platform"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"

def install_linux():
    """Install system-wide on Linux"""
    print("Installing Copyboard system-wide on Linux...")
    
    # Get user home directory
    home_dir = Path.home()
    
    # 1. Create autostart entry
    autostart_dir = home_dir / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    
    desktop_entry = """[Desktop Entry]
Name=Copyboard
Comment=Multi-clipboard utility
Exec=copyboard-gui
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
    
    with open(autostart_dir / "copyboard.desktop", "w") as f:
        f.write(desktop_entry)
    
    # 2. Install file manager integration
    try:
        # Try to detect the file manager
        if os.path.exists("/usr/bin/nautilus"):
            subprocess.run(["scripts/install-nautilus-extension.sh"], check=True)
        elif os.path.exists("/usr/bin/thunar"):
            # Install Thunar custom actions
            from copyboard_extension.system_integration import install_thunar_custom_actions
            install_thunar_custom_actions()
        elif os.path.exists("/usr/bin/dolphin"):
            subprocess.run(["scripts/install-kde-service.sh"], check=True)
    except Exception as e:
        print(f"Warning: Failed to install file manager integration: {e}")
    
    # 3. Install browser extension native messaging host
    try:
        subprocess.run(["python3", "scripts/install_browser_extension.py"], check=True)
    except Exception as e:
        print(f"Warning: Failed to install browser extension: {e}")
    
    # 4. Set up global hotkeys
    try:
        # Check if we're using X11 or Wayland
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        
        if session_type == "x11":
            subprocess.run(["python3", "scripts/x11_shortcuts.py", "--install"], check=True)
        else:
            # For Wayland, we'll use the global_hotkeys.py script
            # Create systemd user service
            service_dir = home_dir / ".config" / "systemd" / "user"
            service_dir.mkdir(parents=True, exist_ok=True)
            
            service_content = """[Unit]
Description=Copyboard Global Hotkeys
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 {script_path}
Restart=on-failure
Environment=DISPLAY=:0

[Install]
WantedBy=graphical-session.target
"""
            script_path = os.path.abspath("scripts/global_hotkeys.py")
            
            with open(service_dir / "copyboard-hotkeys.service", "w") as f:
                f.write(service_content.format(script_path=script_path))
            
            # Enable and start the service
            subprocess.run(["systemctl", "--user", "enable", "copyboard-hotkeys.service"], check=True)
            subprocess.run(["systemctl", "--user", "start", "copyboard-hotkeys.service"], check=True)
    except Exception as e:
        print(f"Warning: Failed to set up global hotkeys: {e}")
    
    print("Linux installation complete!")

def install_macos():
    """Install system-wide on macOS"""
    print("Installing Copyboard system-wide on macOS...")
    
    # Get user home directory
    home_dir = Path.home()
    
    # 1. Create Launch Agent for autostart
    launch_agents_dir = home_dir / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.copyboard.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/copyboard-gui</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
    
    with open(launch_agents_dir / "com.copyboard.app.plist", "w") as f:
        f.write(plist_content)
    
    # 2. Install Finder integration (using Automator)
    # This requires creating an Automator workflow, which is complex to do programmatically
    print("Note: For Finder integration, create an Automator Service manually:")
    print("1. Open Automator and create a new Service")
    print("2. Set 'Service receives selected' to 'files or folders' in 'Finder'")
    print("3. Add 'Run Shell Script' action with command: /usr/local/bin/copyboard add \"$@\"")
    print("4. Save as 'Copy to Copyboard'")
    
    # 3. Install browser extension native messaging host
    try:
        # Create Chrome native messaging host directory
        chrome_dir = home_dir / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
        chrome_dir.mkdir(parents=True, exist_ok=True)
        
        # Create Firefox native messaging host directory
        firefox_dir = home_dir / "Library" / "Application Support" / "Mozilla" / "NativeMessagingHosts"
        firefox_dir.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = {
            "name": "com.copyboard.extension",
            "description": "Copyboard Native Messaging Host",
            "path": "/usr/local/bin/copyboard-native-host",
            "type": "stdio",
            "allowed_origins": [
                "chrome-extension://clioppbhoiokpphkobjjkfchcdfaafdn/"
            ]
        }
        
        # Write manifest files
        with open(chrome_dir / "com.copyboard.extension.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        with open(firefox_dir / "com.copyboard.extension.json", "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to install browser extension: {e}")
    
    # 4. Set up global hotkeys (using macOS's built-in shortcuts)
    print("Note: For global hotkeys, set up keyboard shortcuts in System Preferences:")
    print("1. Go to System Preferences > Keyboard > Shortcuts > App Shortcuts")
    print("2. Click '+' and add shortcuts for copyboard-gui commands")
    
    print("macOS installation complete!")

def install_windows():
    """Install system-wide on Windows"""
    print("Installing Copyboard system-wide on Windows...")
    
    # 1. Create autostart registry entry
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Get the path to the executable
        exe_path = os.path.abspath("bin/copyboard-gui.exe")
        
        # Open the registry key
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        
        # Set the value
        winreg.SetValueEx(key, "Copyboard", 0, winreg.REG_SZ, exe_path)
        
        # Close the key
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Warning: Failed to create autostart entry: {e}")
    
    # 2. Install Explorer context menu integration
    try:
        import winreg
        
        # Get the path to the executable
        exe_path = os.path.abspath("bin/copyboard.exe")
        
        # Create context menu for files
        key_path = r"*\shell\CopyboardAdd"
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Add to Copyboard")
        winreg.CloseKey(key)
        
        # Create command key
        key_path = r"*\shell\CopyboardAdd\command"
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}" add "%1"')
        winreg.CloseKey(key)
        
        # Create context menu for directories
        key_path = r"Directory\shell\CopyboardAdd"
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Add to Copyboard")
        winreg.CloseKey(key)
        
        # Create command key
        key_path = r"Directory\shell\CopyboardAdd\command"
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}" add "%1"')
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Warning: Failed to install Explorer integration: {e}")
    
    # 3. Install browser extension native messaging host
    try:
        # Create Chrome native messaging host directory
        appdata = os.environ.get("LOCALAPPDATA")
        chrome_dir = Path(appdata) / "Google" / "Chrome" / "User Data" / "NativeMessagingHosts"
        chrome_dir.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = {
            "name": "com.copyboard.extension",
            "description": "Copyboard Native Messaging Host",
            "path": os.path.abspath("bin/copyboard-native-host.exe"),
            "type": "stdio",
            "allowed_origins": [
                "chrome-extension://clioppbhoiokpphkobjjkfchcdfaafdn/"
            ]
        }
        
        # Write manifest file
        with open(chrome_dir / "com.copyboard.extension.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        # Add registry entry for Chrome
        import winreg
        key_path = r"Software\Google\Chrome\NativeMessagingHosts\com.copyboard.extension"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(chrome_dir / "com.copyboard.extension.json"))
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Warning: Failed to install browser extension: {e}")
    
    # 4. Set up global hotkeys
    try:
        # Create a shortcut to run the global hotkeys script
        import win32com.client
        
        # Get the path to the script
        script_path = os.path.abspath("scripts/global_hotkeys.py")
        
        # Create a shortcut in the Startup folder
        startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        shortcut_path = os.path.join(startup_folder, "Copyboard Hotkeys.lnk")
        
        # Create the shortcut
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = sys.executable
        shortcut.Arguments = f'"{script_path}"'
        shortcut.WorkingDirectory = os.path.dirname(script_path)
        shortcut.Description = "Copyboard Global Hotkeys"
        shortcut.Save()
    except Exception as e:
        print(f"Warning: Failed to set up global hotkeys: {e}")
    
    print("Windows installation complete!")

def main():
    """Main function"""
    # Detect platform
    platform = get_platform()
    
    # Install based on platform
    if platform == "linux":
        install_linux()
    elif platform == "macos":
        install_macos()
    elif platform == "windows":
        install_windows()
    else:
        print(f"Error: Unsupported platform: {platform}")
        sys.exit(1)
    
    print("Copyboard has been installed system-wide!")
    print("You may need to restart your computer for all changes to take effect.")

if __name__ == "__main__":
    main() 