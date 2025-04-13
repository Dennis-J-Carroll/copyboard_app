"""
Copyboard CLI - Command-line interface for the multi-clipboard utility
"""
import argparse
import sys
import textwrap
from typing import List, Optional

from . import core


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI"""
    parser = argparse.ArgumentParser(
        description='Copyboard - A multi-clipboard utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
            Examples:
              copyboard list              # List all items in the clipboard board
              copyboard copy 2            # Copy item at index 2 to the clipboard
              copyboard add "text"        # Add text to the clipboard board
              copyboard remove 1          # Remove item at index 1
              copyboard clear             # Clear the clipboard board
              copyboard paste-combo 0 2 3 # Paste combination of items 0, 2, and 3
        ''')
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all items in the clipboard board')
    
    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy an item to the clipboard')
    copy_parser.add_argument('index', type=int, nargs='?', default=0, 
                            help='Index of the item to copy (default: 0)')
    
    # Copy all command
    copy_all_parser = subparsers.add_parser('copyall', help='Copy all items to the clipboard')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add text to the clipboard board')
    add_parser.add_argument('text', type=str, help='Text to add to the clipboard board')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove an item from the clipboard board')
    remove_parser.add_argument('index', type=int, help='Index of the item to remove')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear the clipboard board')
    
    # Paste combination command
    paste_combo_parser = subparsers.add_parser('paste-combo', help='Paste a combination of clipboard items')
    paste_combo_parser.add_argument('indices', type=int, nargs='+', 
                               help='Indices of items to combine and paste')
    
    # Monitor command (for capturing clipboard changes)
    monitor_parser = subparsers.add_parser('monitor', help='Monitor clipboard for changes')
    monitor_parser.add_argument('--seconds', type=int, default=60,
                              help='Number of seconds to monitor (default: 60)')
    
    return parser


def handle_list() -> int:
    """Handle the list command"""
    if core.get_board_size() == 0:
        print("Clipboard board is empty.")
        return 0
    
    print(f"Clipboard Board ({core.get_board_size()} items):")
    print("----------------")
    
    board_previews = core.get_board_preview()
    for idx in range(core.get_board_size()):
        print(board_previews[idx])
        print("----------------")
    
    return 0


def handle_copy(index: int) -> int:
    """Handle the copy command"""
    if core.paste_from_board(index):
        print(f"Copied item {index} to clipboard.")
        return 0
    else:
        print(f"Error: No item at index {index}.")
        return 1


def handle_copy_all() -> int:
    """Handle the copy all command"""
    if core.paste_all():
        print("Copied all items to clipboard.")
        return 0
    else:
        print("Error: Clipboard board is empty.")
        return 1


def handle_add(text: str) -> int:
    """Handle the add command"""
    # Set clipboard content and add to board
    import pyperclip
    pyperclip.copy(text)
    core.copy_to_board()
    print(f"Added text to clipboard board at index 0.")
    return 0


def handle_remove(index: int) -> int:
    """Handle the remove command"""
    if core.drop_item(index):
        print(f"Removed item {index} from clipboard board.")
        return 0
    else:
        print(f"Error: No item at index {index}.")
        return 1


def handle_clear() -> int:
    """Handle the clear command"""
    core.clear_board()
    print("Cleared clipboard board.")
    return 0


def handle_paste_combo(indices: List[int]) -> int:
    """Handle the paste-combo command"""
    # Verify we have indices
    if not indices:
        print("Error: No indices provided.")
        return 1
        
    # Verify they are all valid
    for idx in indices:
        if idx < 0 or idx >= core.get_board_size():
            print(f"Error: Invalid index {idx}.")
            return 1
    
    # Get the items
    try:
        if core.paste_combination(indices):
            print(f"Pasted combination of items: {', '.join(map(str, indices))}")
            return 0
        else:
            print("Error: Failed to paste combination.")
            return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def handle_monitor(seconds: int) -> int:
    """Handle the monitor command"""
    import time
    import pyperclip
    
    print(f"Monitoring clipboard for {seconds} seconds...")
    print("Press Ctrl+C to stop.")
    
    try:
        last_content = pyperclip.paste()
        end_time = time.time() + seconds
        
        while time.time() < end_time:
            current_content = pyperclip.paste()
            
            if current_content != last_content:
                last_content = current_content
                core.copy_to_board()
                print(f"Added new clipboard content to board at index 0.")
                
            time.sleep(0.5)
            
        print("\nMonitoring finished. Current board:")
        handle_list()
        return 0
        
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user. Current board:")
        handle_list()
        return 0


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI"""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command:
        parser.print_help()
        return 1
    
    # Execute the appropriate command
    if parsed_args.command == 'list':
        return handle_list()
    elif parsed_args.command == 'copy':
        return handle_copy(parsed_args.index)
    elif parsed_args.command == 'copyall':
        return handle_copy_all()
    elif parsed_args.command == 'add':
        return handle_add(parsed_args.text)
    elif parsed_args.command == 'remove':
        return handle_remove(parsed_args.index)
    elif parsed_args.command == 'clear':
        return handle_clear()
    elif parsed_args.command == 'paste-combo':
        return handle_paste_combo(parsed_args.indices)
    elif parsed_args.command == 'monitor':
        return handle_monitor(parsed_args.seconds)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
