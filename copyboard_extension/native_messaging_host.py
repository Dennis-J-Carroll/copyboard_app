#!/usr/bin/env python3
"""
Native messaging host for the Copyboard browser extension.
This allows the browser to communicate with the native Copyboard application.
"""

import sys
import json
import struct
import os
import logging
from typing import Dict, Any, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.expanduser('~/.config/copyboard/native_messaging.log')
)
logger = logging.getLogger('copyboard_native_messaging')

# Import core functionality
try:
    from . import core
except ImportError:
    logger.error("Failed to import copyboard_extension.core")
    sys.exit(1)

def get_message() -> Dict[str, Any]:
    """
    Read a message from stdin using the native messaging protocol.
    
    Returns:
        Dict containing the message data
    """
    try:
        # Read the message length (first 4 bytes)
        length_bytes = sys.stdin.buffer.read(4)
        if not length_bytes:
            logger.error("No data received from browser")
            sys.exit(0)
        
        # Unpack the message length as an unsigned int
        message_length = struct.unpack('@I', length_bytes)[0]
        logger.info(f"Reading message of length: {message_length} bytes")
        
        # Read the JSON message
        message_json = sys.stdin.buffer.read(message_length).decode('utf-8')
        logger.info(f"Received raw message: {message_json}")
        
        # Parse JSON
        try:
            message = json.loads(message_json)
            logger.info(f"Parsed message: {message}")
            return message
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            return {}
    except Exception as e:
        logger.error(f"Error in get_message: {e}")
        return {}

def send_message(message: Dict[str, Any]) -> None:
    """
    Send a message to stdout using the native messaging protocol.
    
    Args:
        message: Dict containing the message data
    """
    try:
        # Encode the message as JSON
        message_json = json.dumps(message).encode('utf-8')
        logger.info(f"Sending message: {message}")
        
        # Write the message length as a 4-byte unsigned int
        sys.stdout.buffer.write(struct.pack('@I', len(message_json)))
        
        # Write the JSON message
        sys.stdout.buffer.write(message_json)
        sys.stdout.buffer.flush()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        # Try to send error message if possible
        try:
            error_msg = json.dumps({"success": False, "error": str(e)}).encode('utf-8')
            error_len = struct.pack('@I', len(error_msg))
            sys.stdout.buffer.write(error_len)
            sys.stdout.buffer.write(error_msg)
            sys.stdout.buffer.flush()
        except:
            pass

def handle_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a message from the browser extension.
    
    Args:
        message: Dict containing the message data
        
    Returns:
        Dict containing the response data
    """
    # Get the action from the message
    action = message.get('action', '')
    
    logger.info(f"Received action: {action}")
    
    if action == 'add':
        # Add content to the clipboard board
        content = message.get('content', '')
        if content:
            try:
                # We know core.py has copy_to_board() but not add_to_board()
                # First set the clipboard content
                import pyperclip
                pyperclip.copy(content)
                # Then call copy_to_board() to add current clipboard to board
                core.copy_to_board()
                logger.info(f"Successfully added content to clipboard board")
                return {'success': True}
            except Exception as e:
                logger.error(f"Error adding to board: {e}")
                return {'success': False, 'error': str(e)}
        else:
            return {'success': False, 'error': 'No content provided'}
    
    elif action == 'list':
        # Get the clipboard board items
        try:
            board = core.get_board()
            logger.info(f"Retrieved board with {len(board)} items")
            return {'success': True, 'items': board}
        except Exception as e:
            logger.error(f"Error getting board: {e}")
            return {'success': False, 'error': str(e)}
    
    elif action == 'paste':
        # Paste a specific item
        try:
            index = message.get('index', -1)
            if index >= 0:
                content = core.get_board_item(index)
                if content:
                    logger.info(f"Retrieved content for index {index}: {content[:30]}...")
                    return {'success': True, 'content': content}
            
            return {'success': False, 'error': 'Invalid index or item not found'}
        except Exception as e:
            logger.error(f"Error getting board item: {e}")
            return {'success': False, 'error': str(e)}
    
    elif action == 'paste_direct':
        # Paste directly using paste_from_board
        try:
            index = message.get('index', 0)
            result = core.paste_from_board(index)
            return {'success': result}
        except Exception as e:
            logger.error(f"Error pasting from board: {e}")
            return {'success': False, 'error': str(e)}
    
    elif action == 'clear':
        # Clear the clipboard board
        try:
            core.clear_board()
            return {'success': True}
        except Exception as e:
            logger.error(f"Error clearing board: {e}")
            return {'success': False, 'error': str(e)}
    
    # Unknown action
    return {'success': False, 'error': f'Unknown action: {action}'}

def main() -> None:
    """
    Main function for the native messaging host.
    """
    try:
        # Read the message from stdin
        message = get_message()
        
        # Handle the message
        response = handle_message(message)
        
        # Send the response
        send_message(response)
    
    except Exception as e:
        logger.exception(f"Error in native messaging host: {e}")
        # Send error response
        send_message({
            'success': False,
            'error': str(e)
        })

if __name__ == "__main__":
    main()
