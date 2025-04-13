#!/usr/bin/env python3
"""
Install script for the Copyboard browser extension native messaging host.
This script installs the native messaging host manifest and makes the
host executable.
"""

import os
import sys
import json
import shutil
import stat
import platform
import argparse
import subprocess
from pathlib import Path

def get_chrome_dir() -> str:
    """
    Get the directory for Chrome/Chromium native messaging hosts.
    
    Returns:
        Path to Chrome's native messaging hosts directory
    """
    system = platform.system()
    
    if system == "Linux":
        # For Chrome/Chromium
        chrome_dir = os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts")
        chromium_dir = os.path.expanduser("~/.config/chromium/NativeMessagingHosts")
        
        # Try Chrome first, then Chromium
        for d in [chrome_dir, chromium_dir]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            return d
    
    elif system == "Darwin":  # macOS
        # For Chrome/Chromium
        chrome_dir = os.path.expanduser(
            "~/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        )
        if not os.path.exists(chrome_dir):
            os.makedirs(chrome_dir, exist_ok=True)
        return chrome_dir
    
    elif system == "Windows":
        # For Chrome (registry-based on Windows, but we need dir for the json)
        chrome_dir = os.path.expanduser(
            "~\\AppData\\Local\\Google\\Chrome\\User Data\\NativeMessagingHosts"
        )
        if not os.path.exists(chrome_dir):
            os.makedirs(chrome_dir, exist_ok=True)
        return chrome_dir
    
    print(f"Unsupported platform: {system}")
    sys.exit(1)

def get_firefox_dir() -> str:
    """
    Get the directory for Firefox native messaging hosts.
    
    Returns:
        Path to Firefox's native messaging hosts directory
    """
    system = platform.system()
    
    if system == "Linux":
        # For Firefox
        firefox_dir = os.path.expanduser("~/.mozilla/native-messaging-hosts")
        if not os.path.exists(firefox_dir):
            os.makedirs(firefox_dir, exist_ok=True)
        return firefox_dir
    
    elif system == "Darwin":  # macOS
        # For Firefox
        firefox_dir = os.path.expanduser(
            "~/Library/Application Support/Mozilla/NativeMessagingHosts"
        )
        if not os.path.exists(firefox_dir):
            os.makedirs(firefox_dir, exist_ok=True)
        return firefox_dir
    
    elif system == "Windows":
        # For Firefox
        firefox_dir = os.path.expanduser(
            "~\\AppData\\Roaming\\Mozilla\\NativeMessagingHosts"
        )
        if not os.path.exists(firefox_dir):
            os.makedirs(firefox_dir, exist_ok=True)
        return firefox_dir
    
    print(f"Unsupported platform: {system}")
    sys.exit(1)

def create_manifest(host_path: str) -> dict:
    """
    Create the native messaging host manifest.
    
    Args:
        host_path: Path to the native messaging host script
        
    Returns:
        Dict containing the manifest data
    """
    # Chrome extension ID for the Copyboard extension
    # This is derived from the key in the manifest.json file
    extension_id = "ckhambjmhhinampfpogbjkflkgimdjio"
    
    return {
        "name": "com.copyboard.extension",
        "description": "Copyboard Native Messaging Host",
        "path": host_path,
        "type": "stdio",
        "allowed_origins": [
            f"chrome-extension://{extension_id}/",
            "chrome://extensions/"
        ]
    }

def main() -> None:
    """
    Main installation function.
    """
    parser = argparse.ArgumentParser(
        description="Install Copyboard browser extension native messaging host"
    )
    parser.add_argument(
        "--browser", choices=["chrome", "firefox", "all"], default="all",
        help="Browser to install for (default: all)"
    )
    args = parser.parse_args()
    
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Go up one directory level to get the project root
    project_root = os.path.dirname(script_dir)
    
    # Path to the native messaging host script
    host_script = os.path.join(
        project_root, "copyboard_extension", "native_messaging_host.py"
    )
    
    # Make sure the script is executable
    os.chmod(host_script, os.stat(host_script).st_mode | stat.S_IEXEC)
    
    # Create the native messaging host manifest
    manifest = create_manifest(host_script)
    
    # Install for Chrome/Chromium
    if args.browser in ["chrome", "all"]:
        chrome_dir = get_chrome_dir()
        manifest_path = os.path.join(chrome_dir, "com.copyboard.extension.json")
        
        # Make sure Chrome manifest has allowed_origins
        chrome_manifest = manifest.copy()
        
        with open(manifest_path, "w") as f:
            json.dump(chrome_manifest, f, indent=2)
        
        print(f"Installed Chrome/Chromium native messaging host to {manifest_path}")
    
    # Install for Firefox
    if args.browser in ["firefox", "all"]:
        firefox_dir = get_firefox_dir()
        manifest_path = os.path.join(firefox_dir, "com.copyboard.extension.json")
        
        # Firefox uses a different manifest format
        firefox_manifest = manifest.copy()
        firefox_manifest["allowed_extensions"] = ["copyboard@example.com", "{27bd49e5-7ad9-4847-9c3a-b5d0a5a6c177}"]
        if "allowed_origins" in firefox_manifest:
            del firefox_manifest["allowed_origins"]
        
        with open(manifest_path, "w") as f:
            json.dump(firefox_manifest, f, indent=2)
        
        print(f"Installed Firefox native messaging host to {manifest_path}")
    
    print("\nInstallation complete!")
    print("\nNext steps:")
    print("1. Install the browser extension from the browser_extension directory")
    print("2. Test the extension by right-clicking on a webpage")

if __name__ == "__main__":
    main()
