#!/usr/bin/env python3
"""
Test the native messaging connection
"""
import sys
import json
import struct
import subprocess
import os
import time

# Define the message to send
message = {
    "action": "ping",
    "timestamp": int(time.time())
}

# Encode the message as Native Messaging expects
def encode_message(message_dict):
    json_str = json.dumps(message_dict)
    message_bytes = json_str.encode('utf-8')
    length = struct.pack('@I', len(message_bytes))
    return length + message_bytes

# Run the host process
host_path = "/home/dennisjcarroll/CascadeProjects/windsurf-project/copyboard_extension/simple_host.py"
process = subprocess.Popen(
    [host_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Send the message
encoded_message = encode_message(message)
process.stdin.write(encoded_message)
process.stdin.flush()

# Read the response length (first 4 bytes)
response_length_bytes = process.stdout.read(4)
if not response_length_bytes:
    print("Error: No response received")
    sys.exit(1)

# Unpack the response length
response_length = struct.unpack('@I', response_length_bytes)[0]
print(f"Response length: {response_length} bytes")

# Read the response JSON
response_json = process.stdout.read(response_length).decode('utf-8')
print(f"Response: {response_json}")

# Parse and print the response
try:
    response = json.loads(response_json)
    print("\nParsed response:")
    print(json.dumps(response, indent=2))
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")

# Cleanup
process.terminate()
print("\nTest complete!")
