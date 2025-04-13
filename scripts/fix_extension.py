#!/usr/bin/env python3
"""
Fix Chrome extension configuration script.
This script helps diagnose and fix common issues with the Copyboard Chrome extension.
"""
import os
import json
import subprocess
import shutil
import sys

def print_colored(text, color):
    """Print colored text."""
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")

def print_header(text):
    """Print a header."""
    print_colored("\n" + "="*70, "blue")
    print_colored(f"  {text}", "blue")
    print_colored("="*70, "blue")

def print_success(text):
    """Print a success message."""
    print_colored(f"✓ {text}", "green")

def print_error(text):
    """Print an error message."""
    print_colored(f"✗ {text}", "red")

def print_warning(text):
    """Print a warning message."""
    print_colored(f"! {text}", "yellow")

def print_info(text):
    """Print an info message."""
    print(f"  {text}")

def fix_native_messaging_host():
    """Fix the native messaging host configuration."""
    print_header("FIXING NATIVE MESSAGING HOST")
    
    # Get the base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)  # Move up one level from scripts directory
    
    # Chrome manifest path
    chrome_dir = os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts")
    chrome_manifest = os.path.join(chrome_dir, "com.copyboard.extension.json")
    
    # Check if the directory exists
    if not os.path.exists(chrome_dir):
        print_info(f"Creating directory: {chrome_dir}")
        os.makedirs(chrome_dir, exist_ok=True)
    
    # Source manifest path
    source_manifest = os.path.join(project_root, "config", "chrome_manifest.json")
    
    # Host script path
    host_script_path = os.path.join(project_root, "copyboard_extension", "native_messaging_host.py")
    simple_host_path = os.path.join(base_dir, "simple_host.py")
    
    # Load the manifest template
    try:
        with open(source_manifest, "r") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print_error(f"Failed to load manifest template: {e}")
        # Create a new manifest
        manifest = {
            "name": "com.copyboard.extension",
            "description": "Copyboard Native Messaging Host",
            "path": host_script_path if os.path.exists(host_script_path) else simple_host_path,
            "type": "stdio",
            "allowed_origins": [
                "chrome-extension://clioppbhoiokpphkobjjkfchcdfaafdn/",
                "chrome://extensions/"
            ]
        }
    
    # Update the host path
    if os.path.exists(host_script_path):
        manifest["path"] = host_script_path
        print_success(f"Using host script: {host_script_path}")
    elif os.path.exists(simple_host_path):
        manifest["path"] = simple_host_path
        print_success(f"Using simple host script: {simple_host_path}")
    else:
        print_error("Could not find host script")
        return False
    
    # Make the script executable
    os.chmod(manifest["path"], 0o755)
    print_success("Made host script executable")
    
    # Save the manifest
    try:
        with open(chrome_manifest, "w") as f:
            json.dump(manifest, f, indent=2)
        print_success(f"Saved manifest to: {chrome_manifest}")
    except Exception as e:
        print_error(f"Failed to save manifest: {e}")
        return False
    
    return True

def fix_extension_files():
    """Fix the extension files."""
    print_header("FIXING EXTENSION FILES")
    
    # Get the base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)  # Move up one level from scripts directory
    
    # Extension directory
    extension_dir = os.path.join(project_root, "copyboard_extension", "browser_extension")
    
    # Check if the extension directory exists
    if not os.path.exists(extension_dir):
        print_error(f"Extension directory not found: {extension_dir}")
        return False
    
    # Check if the manifest exists
    manifest_path = os.path.join(extension_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print_error(f"Manifest not found: {manifest_path}")
        return False
    
    print_success("Extension files are in place")
    
    # Build the extension
    print_info("Building extension...")
    build_dir = os.path.join(project_root, "build")
    os.makedirs(build_dir, exist_ok=True)
    
    # Create zip file
    zip_path = os.path.join(build_dir, "copyboard_extension.zip")
    try:
        # Change directory to extension dir
        os.chdir(extension_dir)
        subprocess.run(["zip", "-r", zip_path, "."], check=True)
        print_success(f"Created extension package: {zip_path}")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create extension package: {e}")
        return False
    
    return True

def main():
    """Main function."""
    print_header("COPYBOARD EXTENSION FIXER")
    print_info("This script will fix common issues with the Copyboard Chrome extension.")
    
    # Fix native messaging host
    if fix_native_messaging_host():
        print_success("Fixed native messaging host configuration")
    else:
        print_error("Failed to fix native messaging host configuration")
    
    # Fix extension files
    if fix_extension_files():
        print_success("Fixed extension files")
    else:
        print_error("Failed to fix extension files")
    
    # Print instructions
    print_header("NEXT STEPS")
    print_info("1. Open Chrome and go to chrome://extensions")
    print_info("2. Enable Developer mode (toggle in the top-right)")
    print_info("3. Click 'Load unpacked' and select the following directory:")
    print_info(f"   {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'copyboard_extension', 'browser_extension')}")
    print_info("4. Note the extension ID that appears under the extension name")
    print_info("5. Make sure this ID matches the one in your native messaging host manifest:")
    print_info(f"   {os.path.expanduser('~/.config/google-chrome/NativeMessagingHosts/com.copyboard.extension.json')}")
    print_info("6. If they don't match, run this script again with the correct ID:")
    print_info("   python3 fix_extension.py <extension_id>")
    print_info("7. Restart Chrome completely (close all windows and reopen)")
    
    print_header("TROUBLESHOOTING")
    print_info("If you still have issues:")
    print_info("1. Check Chrome's console for errors: chrome://extensions -> Inspect views")
    print_info("2. Check native messaging host logs: ~/.config/copyboard/native_messaging.log")
    print_info("3. Run the diagnose script: python3 diagnose_messaging.py")

if __name__ == "__main__":
    main()
