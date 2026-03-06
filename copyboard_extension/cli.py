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
              copyboard list                    # List all items in the clipboard board
              copyboard copy 2                  # Copy item at index 2 to the clipboard
              copyboard add "text"              # Add text to the clipboard board
              copyboard remove 1                # Remove item at index 1
              copyboard clear                   # Clear the clipboard board
              copyboard paste-combo 0 2 3       # Paste combination of items

            Code Revolver (snippets):
              copyboard snippet list             # List all chambers and snippets
              copyboard snippet fire 0 2         # Fire snippet 2 from chamber 0
              copyboard snippet search "docker"  # Search snippets
              copyboard snippet chambers         # List just chamber names
              copyboard snippet revolver         # Launch the revolver UI
              copyboard snippet add 0 "label" "code"   # Add snippet to chamber 0
              copyboard snippet export out.copyboard   # Export snippet pack
              copyboard snippet import pack.copyboard  # Import snippet pack
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

    # ── Snippet / Code Revolver commands ──────────────────────────────
    snippet_parser = subparsers.add_parser(
        'snippet', help='Code Revolver – manage and fire code snippets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    snippet_sub = snippet_parser.add_subparsers(dest='snippet_command')

    # snippet list
    snippet_sub.add_parser('list', help='List all chambers and their snippets')

    # snippet chambers
    snippet_sub.add_parser('chambers', help='List chamber names only')

    # snippet fire <chamber> <snippet>
    fire_p = snippet_sub.add_parser('fire', help='Fire (paste) a specific snippet')
    fire_p.add_argument('chamber', type=int, help='Chamber index')
    fire_p.add_argument('snippet', type=int, help='Snippet index within chamber')
    fire_p.add_argument('--no-expand', action='store_true',
                        help='Do not expand template variables')

    # snippet search <query>
    search_p = snippet_sub.add_parser('search', help='Search snippets by keyword')
    search_p.add_argument('query', type=str, help='Search query')

    # snippet add <chamber> <label> <text>
    add_snip_p = snippet_sub.add_parser('add', help='Add a snippet to a chamber')
    add_snip_p.add_argument('chamber', type=int, help='Chamber index')
    add_snip_p.add_argument('label', type=str, help='Snippet label')
    add_snip_p.add_argument('text', type=str, help='Snippet text')

    # snippet remove <chamber> <snippet>
    rm_snip_p = snippet_sub.add_parser('remove', help='Remove a snippet')
    rm_snip_p.add_argument('chamber', type=int, help='Chamber index')
    rm_snip_p.add_argument('snippet', type=int, help='Snippet index')

    # snippet export <filepath>
    export_p = snippet_sub.add_parser('export', help='Export snippet pack')
    export_p.add_argument('filepath', type=str, help='Output .copyboard filepath')

    # snippet import <filepath>
    import_p = snippet_sub.add_parser('import', help='Import snippet pack')
    import_p.add_argument('filepath', type=str, help='Input .copyboard filepath')
    import_p.add_argument('--replace', action='store_true',
                          help='Replace all chambers instead of merging')

    # snippet revolver
    rev_p = snippet_sub.add_parser('revolver', help='Launch the Code Revolver UI')
    rev_p.add_argument('--theme', type=str, default='cyberpunk',
                       choices=['cyberpunk', 'terminal_green', 'synthwave', 'dark'],
                       help='UI theme (default: cyberpunk)')

    # snippet top
    snippet_sub.add_parser('top', help='Show most frequently used snippets')

    # snippet reset
    snippet_sub.add_parser('reset', help='Reset snippets to defaults')

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
    elif parsed_args.command == 'snippet':
        return handle_snippet(parsed_args)
    else:
        parser.print_help()
        return 1


def handle_snippet(args) -> int:
    """Handle all snippet subcommands."""
    from .snippet_manager import snippets, expand_variables

    sub = getattr(args, 'snippet_command', None)
    if not sub:
        print("Usage: copyboard snippet {list|fire|search|chambers|revolver|add|remove|export|import|top|reset}")
        return 1

    if sub == 'list':
        chambers = snippets.get_chambers()
        if not chambers:
            print("No snippet chambers loaded.")
            return 0
        for ci, ch in enumerate(chambers):
            icon = ch.get('icon', '')
            print(f"\n{icon}  Chamber {ci}: {ch['name']}")
            print(f"   {'─' * 40}")
            for si, snip in enumerate(ch.get('snippets', [])):
                label = snip.get('label', 'Untitled')
                preview = snip['text'][:60].replace('\n', ' ↵ ')
                print(f"   {si}: [{label}] {preview}")
        print()
        return 0

    elif sub == 'chambers':
        chambers = snippets.get_chambers()
        for ci, ch in enumerate(chambers):
            icon = ch.get('icon', '')
            count = len(ch.get('snippets', []))
            print(f"  {ci}: {icon}  {ch['name']}  ({count} snippets)")
        return 0

    elif sub == 'fire':
        text = snippets.fire(args.chamber, args.snippet, expand=not args.no_expand)
        if text:
            print(f"🔫 Fired! Copied to clipboard:")
            print(f"   {text[:120]}")
            return 0
        else:
            print(f"Error: Invalid chamber {args.chamber} or snippet {args.snippet}.")
            return 1

    elif sub == 'search':
        results = snippets.search(args.query)
        if not results:
            print(f"No snippets matching '{args.query}'.")
            return 0
        print(f"Found {len(results)} result(s):")
        for r in results:
            preview = r['text'][:60].replace('\n', ' ↵ ')
            print(f"  {r['chamber_icon']} {r['chamber']}[{r['snippet_idx']}]: [{r['label']}] {preview}")
        return 0

    elif sub == 'add':
        if snippets.add_snippet(args.chamber, args.label, args.text):
            print(f"Added snippet '{args.label}' to chamber {args.chamber}.")
            return 0
        else:
            print(f"Error: Invalid chamber index {args.chamber}.")
            return 1

    elif sub == 'remove':
        if snippets.remove_snippet(args.chamber, args.snippet):
            print(f"Removed snippet {args.snippet} from chamber {args.chamber}.")
            return 0
        else:
            print(f"Error: Invalid chamber {args.chamber} or snippet {args.snippet}.")
            return 1

    elif sub == 'export':
        if snippets.export_chambers(args.filepath):
            print(f"Exported snippet pack to {args.filepath}")
            return 0
        else:
            print(f"Error: Failed to export to {args.filepath}")
            return 1

    elif sub == 'import':
        success, msg = snippets.import_chambers(args.filepath, merge=not args.replace)
        if success:
            print(f"✓ {msg}")
            return 0
        else:
            print(f"Error: {msg}")
            return 1

    elif sub == 'revolver':
        try:
            from .revolver_ui import show_revolver
            print("Launching Code Revolver...")
            show_revolver(theme=args.theme)
            return 0
        except Exception as e:
            print(f"Error launching revolver UI: {e}")
            return 1

    elif sub == 'top':
        top = snippets.get_top_snippets(10)
        if not top:
            print("No usage data yet. Start firing snippets!")
            return 0
        print("🏆 Most-used snippets:")
        for i, t in enumerate(top, 1):
            print(f"  {i}. {t['chamber_icon']} {t['chamber']}/{t['label']} ({t['uses']} uses)")
        return 0

    elif sub == 'reset':
        snippets.reset_to_defaults()
        print("Snippets reset to defaults.")
        return 0

    else:
        print("Unknown snippet command.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
