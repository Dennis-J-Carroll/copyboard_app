#!/usr/bin/env python3
"""
Simplified native messaging host for clipboard functionality
"""
import sys
import json
import struct
import os
import time

# Create log directory
log_dir = os.path.expanduser('~/.config/copyboard')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Set up logging to file
log_file = os.path.join(log_dir, 'simple_host.log')
with open(log_file, 'a') as f:
    f.write(f"Simple host started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

def log_message(message):
    """Log a message to the log file"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

# Board file for storing clipboard items
board_file = os.path.join(log_dir, 'clipboard_board.json')

# Initialize board with empty list if not exists
if not os.path.exists(board_file):
    with open(board_file, 'w') as f:
        json.dump([], f)

def get_board():
    """Get the clipboard board items"""
    try:
        with open(board_file, 'r') as f:
            return json.load(f)
    except:
        return []

def save_board(board):
    """Save the clipboard board items"""
    try:
        with open(board_file, 'w') as f:
            json.dump(board, f)
        return True
    except Exception as e:
        log_message(f"Error saving board: {e}")
        return False

def add_to_board(content):
    """Add content to clipboard board"""
    board = get_board()
    
    # Remove item if it already exists
    if content in board:
        board.remove(content)
    
    # Add item to the top
    board.insert(0, content)
    
    # Keep only top 10 items
    if len(board) > 10:
        board = board[:10]
    
    # Save board
    return save_board(board)

def read_message():
    """Read a message from stdin"""
    log_message("Trying to read message")
    
    # Read the message length (first 4 bytes)
    length_bytes = sys.stdin.buffer.read(4)
    if not length_bytes:
        log_message("No data received")
        return None
    
    # Unpack the message length
    message_length = struct.unpack('@I', length_bytes)[0]
    log_message(f"Message length: {message_length}")
    
    # Read the JSON message
    message_json = sys.stdin.buffer.read(message_length).decode('utf-8')
    log_message(f"Received message: {message_json}")
    
    # Parse JSON
    return json.loads(message_json)

def send_message(message):
    """Send a message to stdout"""
    log_message(f"Sending message: {json.dumps(message)}")
    
    # Encode the message
    message_json = json.dumps(message).encode('utf-8')
    
    # Write the message length
    sys.stdout.buffer.write(struct.pack('@I', len(message_json)))
    
    # Write the message
    sys.stdout.buffer.write(message_json)
    sys.stdout.buffer.flush()

def handle_action(message):
    """Handle different clipboard actions"""
    action = message.get('action', '')
    log_message(f"Handling action: {action}")
    
    if action == 'add':
        content = message.get('content', '')
        if not content:
            return {"success": False, "error": "No content provided"}
            
        success = add_to_board(content)
        return {"success": success}
    
    elif action == 'list':
        board = get_board()
        return {"success": True, "items": board}
    
    elif action == 'clear':
        success = save_board([])
        return {"success": success}
    
    elif action == 'paste':
        index = message.get('index', 0)
        board = get_board()
        if 0 <= index < len(board):
            return {"success": True, "content": board[index]}
        return {"success": False, "error": "Invalid index"}
    
    elif action == 'ping':
        return {
            "success": True,
            "message": "Pong from Copyboard!",
            "received": message
        }
    
    return {
        "success": True,
        "message": "Action not specifically handled, but received",
        "received": message
    }

def main():
    """Main function"""
    log_message("Main function started")
    
    try:
        # Read the message
        message = read_message()
        if message is None:
            log_message("No message received")
            return
        
        log_message(f"Processing message: {json.dumps(message)}")
        
        # Handle action
        response = handle_action(message)
        
        # Send the response
        send_message(response)
        log_message(f"Response sent: {json.dumps(response)}")
    
    except Exception as e:
        log_message(f"Error: {str(e)}")
        # Try to send error
        try:
            send_message({"success": False, "error": str(e)})
            log_message("Error response sent")
        except Exception as e2:
            log_message(f"Failed to send error message: {str(e2)}")

if __name__ == "__main__":
    main()
