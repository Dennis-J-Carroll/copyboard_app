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
from typing import Optional

# --- Configuration ---
# Choose ONE consistent Firefox ID
FIREFOX_EXTENSION_ID = "copyboard@yourdomain.com" # Replace with your actual ID

# Default Native Host script install location (for system packages)
# This is an *example* path used during packaging. The final package
# determines the actual install location.
DEFAULT_HOST_INSTALL_PATH = "/usr/lib/copyboard_extension/native_messaging_host.py"

# Native Messaging Host Name
NATIVE_HOST_NAME = "com.copyboard.extension"
# --- End Configuration ---

def get_dev_chrome_dir() -> str:
    """
    Get the directory for Chrome/Chromium native messaging hosts *for development*.
    NOTE: System-wide installs for packages use different paths.

    Returns:
        Path to user's Chrome native messaging hosts directory
    """
    system = platform.system()
    paths_to_check = []

    if system == "Linux":
        paths_to_check = [
            "~/.config/google-chrome/NativeMessagingHosts",
            "~/.config/chromium/NativeMessagingHosts",
        ]
    elif system == "Darwin":  # macOS
        paths_to_check = [
            "~/Library/Application Support/Google/Chrome/NativeMessagingHosts",
            "~/Library/Application Support/Chromium/NativeMessagingHosts",
        ]
    elif system == "Windows":
        paths_to_check = [
            "~\\AppData\\Local\\Google\\Chrome\\User Data\\NativeMessagingHosts"
        ] # Others like Edge might be relevant too

    for p in paths_to_check:
        d = os.path.expanduser(p)
        # Return the first one found or the default Chrome one if none exist yet
        if os.path.exists(os.path.dirname(d)):
             os.makedirs(d, exist_ok=True)
             return d
    
    # Fallback if no standard browser config path found yet
    fallback_dir = os.path.expanduser(paths_to_check[0])
    os.makedirs(fallback_dir, exist_ok=True)
    return fallback_dir

def get_dev_firefox_dir() -> str:
    """
    Get the directory for Firefox native messaging hosts *for development*.
    NOTE: System-wide installs for packages use different paths.

    Returns:
        Path to user's Firefox native messaging hosts directory
    """
    system = platform.system()
    path = ""

    if system == "Linux":
        path = "~/.mozilla/native-messaging-hosts"
    elif system == "Darwin":  # macOS
        path = "~/Library/Application Support/Mozilla/NativeMessagingHosts"
    elif system == "Windows":
        path = "~\\AppData\\Roaming\\Mozilla\\NativeMessagingHosts"
    else:
         print(f"Unsupported platform for Firefox dev dir: {system}")
         sys.exit(1)

    firefox_dir = os.path.expanduser(path)
    os.makedirs(firefox_dir, exist_ok=True)
    return firefox_dir

def generate_manifest_data(host_executable_path: str, chrome_extension_id: Optional[str] = None) -> dict:
    """
    Generate the native messaging host manifest data structure.

    Args:
        host_executable_path: Absolute path to the native host script.
        chrome_extension_id: The Chrome extension ID (required for Chrome manifest).

    Returns:
        Dict containing the base manifest data.
    """
    manifest = {
        "name": NATIVE_HOST_NAME,
        "description": "Copyboard Native Messaging Host",
        "path": host_executable_path,
        "type": "stdio",
    }
    # Chrome/Chromium specific part
    if chrome_extension_id:
         manifest["allowed_origins"] = [
            f"chrome-extension://{chrome_extension_id}/",
         ]
    # Firefox specific part (will be added later if needed)
    else:
        manifest["allowed_extensions"] = [FIREFOX_EXTENSION_ID]

    return manifest

def main() -> None:
    """
    Main installation function (primarily for development setup).
    """
    parser = argparse.ArgumentParser(
        description="Install Copyboard browser extension native messaging host (for development)"
    )
    parser.add_argument(
        "--browser", choices=["chrome", "firefox", "all"], default="all",
        help="Browser to install for (default: all)"
    )
    parser.add_argument(
        "--chrome-id", default="ckhambjmhhinampfpogbjkflkgimdjio", # Replace if you use a fixed key
        help="Your Chrome Extension ID (obtain after first upload or from key)"
    )
    parser.add_argument(
        "--host-path", default=None,
        help="Explicit path to the native_messaging_host.py script (optional)"
    )
    args = parser.parse_args()

    # --- Determine Host Script Path ---
    if args.host_path:
        host_script_abs_path = os.path.abspath(args.host_path)
    else:
        # Assume script is run from the 'scripts' directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        host_script_rel_path = os.path.join(
            project_root, "copyboard_extension", "native_messaging_host.py"
        )
        host_script_abs_path = os.path.abspath(host_script_rel_path)

    if not os.path.exists(host_script_abs_path):
        print(f"Error: Native host script not found at {host_script_abs_path}")
        sys.exit(1)

    print(f"Using native host script: {host_script_abs_path}")

    # Make sure the script is executable (important for Linux/macOS)
    try:
        current_mode = os.stat(host_script_abs_path).st_mode
        os.chmod(host_script_abs_path, current_mode | stat.S_IEXEC)
        print(f"Made host script executable.")
    except OSError as e:
        print(f"Warning: Could not set executable flag: {e}")


    # --- Install Manifests (Development Locations) ---
    manifest_filename = f"{NATIVE_HOST_NAME}.json"

    # Install for Chrome/Chromium
    if args.browser in ["chrome", "all"]:
        if not args.chrome_id:
            print("Error: --chrome-id is required when installing for Chrome.")
            sys.exit(1)
        
        chrome_dev_dir = get_dev_chrome_dir()
        manifest_path = os.path.join(chrome_dev_dir, manifest_filename)
        chrome_manifest_data = generate_manifest_data(host_script_abs_path, chrome_extension_id=args.chrome_id)

        try:
            with open(manifest_path, "w") as f:
                json.dump(chrome_manifest_data, f, indent=2)
            print(f"Installed Chrome/Chromium dev manifest to {manifest_path}")
        except IOError as e:
            print(f"Error writing Chrome manifest: {e}")


    # Install for Firefox
    if args.browser in ["firefox", "all"]:
        firefox_dev_dir = get_dev_firefox_dir()
        manifest_path = os.path.join(firefox_dev_dir, manifest_filename)
        # Generate manifest *without* Chrome ID to get the Firefox version
        firefox_manifest_data = generate_manifest_data(host_script_abs_path, chrome_extension_id=None)

        try:
            with open(manifest_path, "w") as f:
                json.dump(firefox_manifest_data, f, indent=2)
            print(f"Installed Firefox dev manifest to {manifest_path}")
        except IOError as e:
            print(f"Error writing Firefox manifest: {e}")

    print("\nDevelopment installation complete!")
    print("NOTE: This script installs to *user* directories for development testing.")
    print("For store distribution (e.g., .deb package), manifests must be placed")
    print("in system-wide locations pointing to the packaged host script path.")

if __name__ == "__main__":
    main()
