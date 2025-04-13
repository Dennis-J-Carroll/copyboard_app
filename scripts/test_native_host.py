#!/usr/bin/env python3
"""
Test script for the native messaging host.
This simulates what the browser would do.
"""

import sys
import json
import struct
import subprocess
import os

def send_message(proc, message):
    """Send a message to the native messaging host"""
    content = json.dumps(message).encode('utf-8')
    length = struct.pack('@I', len(content))
    proc.stdin.write(length)
    proc.stdin.write(content)
    proc.stdin.flush()

def read_message(proc):
    """Read a message from the native messaging host"""
    # Read the message length (first 4 bytes)
    length_bytes = proc.stdout.read(4)
    if not length_bytes:
        print("Error: No data received from host")
        return None
    
    # Unpack the message length as an unsigned int
    message_length = struct.unpack('@I', length_bytes)[0]
    
    # Read the JSON message
    message_json = proc.stdout.read(message_length).decode('utf-8')
    
    # Parse JSON
    try:
        return json.loads(message_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None

def main():
    """Main test function"""
    # Path to the native messaging host script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    host_script = os.path.join(script_dir, "copyboard_extension", "native_messaging_host.py")
    
    # Make sure the script is executable
    os.chmod(host_script, os.stat(host_script).st_mode | 0o755)
    
    # Run the host script
    proc = subprocess.Popen(
        [host_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Add an item to the clipboard board
    send_message(proc, {
        "action": "add",
        "content": "Test item from native messaging test"
    })
    response = read_message(proc)
    print(f"Add response: {response}")
    
    # List the clipboard board
    send_message(proc, {
        "action": "list"
    })
    response = read_message(proc)
    print(f"List response: {response}")
    
    # Clean up
    proc.stdin.close()
    
    # Check for any errors
    stderr = proc.stderr.read()
    if stderr:
        print(f"Error output: {stderr.decode('utf-8')}")
    
    proc.terminate()
    print("Test complete")

if __name__ == "__main__":
    main()
