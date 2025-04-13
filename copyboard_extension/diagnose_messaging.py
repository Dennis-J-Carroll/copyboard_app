#!/usr/bin/env python3
"""
Diagnostic tool for native messaging problems
"""
import os
import sys
import json
import struct
import tempfile
import time

# Set up logging
log_file = os.path.expanduser("~/copyboard_diagnostic.log")
with open(log_file, "w") as f:
    f.write(f"Diagnostic started at {time.ctime()}\n\n")

def log(message):
    """Log a message to the log file"""
    with open(log_file, "a") as f:
        f.write(f"{message}\n")

# Check Chrome manifest location
chrome_manifest_path = os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts/com.copyboard.extension.json")
log(f"Checking Chrome manifest at: {chrome_manifest_path}")
if os.path.exists(chrome_manifest_path):
    try:
        with open(chrome_manifest_path, "r") as f:
            manifest = json.load(f)
            log(f"Manifest content: {json.dumps(manifest, indent=2)}")
            
        host_path = manifest.get("path", "")
        if os.path.exists(host_path):
            log(f"Host script exists: {host_path}")
            if os.access(host_path, os.X_OK):
                log(f"Host script is executable")
            else:
                log(f"ERROR: Host script is NOT executable")
        else:
            log(f"ERROR: Host script does not exist: {host_path}")
            
        allowed_origins = manifest.get("allowed_origins", [])
        log(f"Allowed origins: {allowed_origins}")
    except Exception as e:
        log(f"ERROR reading manifest: {e}")
else:
    log(f"ERROR: Chrome manifest file does not exist")

# Check host script
try:
    simple_host_path = os.path.expanduser("~/CascadeProjects/windsurf-project/copyboard_extension/simple_host.py")
    log(f"\nChecking simple_host.py at: {simple_host_path}")
    if os.path.exists(simple_host_path):
        log(f"Simple host exists")
        if os.access(simple_host_path, os.X_OK):
            log(f"Simple host is executable")
        else:
            log(f"ERROR: Simple host is NOT executable")
            
        # Check python interpreter
        with open(simple_host_path, "r") as f:
            first_line = f.readline().strip()
            log(f"First line: {first_line}")
            
            if first_line.startswith("#!"):
                interpreter = first_line[2:]
                if os.path.exists(interpreter.split()[0]):
                    log(f"Interpreter exists: {interpreter}")
                else:
                    log(f"ERROR: Interpreter not found: {interpreter}")
    else:
        log(f"ERROR: Simple host does not exist")
except Exception as e:
    log(f"Error checking simple host: {e}")

# Try to run the script
log("\nAttempting to run the host script directly...")
try:
    import subprocess
    result = subprocess.run(
        ["/home/dennisjcarroll/CascadeProjects/windsurf-project/copyboard_extension/simple_host.py"], 
        capture_output=True, 
        timeout=1
    )
    log(f"Exit code: {result.returncode}")
    log(f"Stdout: {result.stdout}")
    log(f"Stderr: {result.stderr}")
except Exception as e:
    log(f"Error running script: {e}")

# Summary
log("\n=== DIAGNOSIS SUMMARY ===")
log(f"Diagnostic log created at: {log_file}")
log("Check this log for detailed information about your native messaging setup")
log("If you see any 'ERROR' messages above, those need to be fixed")
log("\nNext steps:")
log("1. Check the Chrome extension ID matches what's in your manifest")
log("2. Make sure the host script path in the manifest is correct")
log("3. Ensure the host script has execute permissions (chmod +x)")
log("4. Restart Chrome completely and reload the extension")

print(f"Diagnostic complete! Check the log at: {log_file}")
