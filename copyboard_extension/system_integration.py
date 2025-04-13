"""
System integration utilities for Copyboard
"""
import os
import platform
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

def get_desktop_environment() -> str:
    """Detect the current desktop environment"""
    desktop_env = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    if desktop_env:
        if 'gnome' in desktop_env:
            return 'gnome'
        elif 'kde' in desktop_env:
            return 'kde'
        elif 'xfce' in desktop_env:
            return 'xfce'
        elif 'mate' in desktop_env:
            return 'mate'
        elif 'cinnamon' in desktop_env:
            return 'cinnamon'
        else:
            return desktop_env
    
    # Fallback detection
    if os.environ.get('GNOME_DESKTOP_SESSION_ID'):
        return 'gnome'
    elif os.environ.get('KDE_FULL_SESSION'):
        return 'kde'
    
    return 'unknown'

def install_context_menu_integration() -> Dict[str, Any]:
    """
    Install the appropriate context menu integration based on the detected desktop environment
    
    Returns:
        A dictionary with the status and details of the installation
    """
    system = platform.system().lower()
    
    if system != 'linux':
        return {
            'success': False,
            'message': f"Context menu integration is not yet supported on {system}. " 
                      "Only Linux is currently supported."
        }
    
    desktop_env = get_desktop_environment()
    
    if desktop_env == 'gnome':
        return install_nautilus_extension()
    elif desktop_env == 'kde':
        return install_kde_service_menu()
    elif desktop_env in ('xfce', 'mate', 'cinnamon'):
        return install_thunar_or_caja_extension()
    else:
        return {
            'success': False,
            'message': f"Context menu integration for {desktop_env} is not yet supported."
        }

def install_nautilus_extension() -> Dict[str, Any]:
    """Install the Nautilus extension for GNOME"""
    try:
        # Get the package directory
        package_dir = Path(__file__).resolve().parent.parent
        source_file = package_dir / 'nautilus-copyboard.py'
        
        if not source_file.exists():
            return {
                'success': False,
                'message': "Nautilus extension file not found. Make sure the package is correctly installed."
            }
            
        # Create the target directory
        target_dir = Path.home() / '.local' / 'share' / 'nautilus-python' / 'extensions'
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        target_file = target_dir / 'nautilus-copyboard.py'
        shutil.copy2(source_file, target_file)
        
        # Make it executable
        target_file.chmod(0o755)
        
        # Restart Nautilus
        try:
            subprocess.run(['nautilus', '-q'], check=False)
        except Exception:
            pass
            
        return {
            'success': True,
            'message': "Nautilus extension installed successfully. "
                      "If it doesn't appear in the context menu, try logging out and back in."
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to install Nautilus extension: {str(e)}"
        }

def install_kde_service_menu() -> Dict[str, Any]:
    """Install the KDE service menu"""
    try:
        # Get the package directory
        package_dir = Path(__file__).resolve().parent.parent
        service_file = package_dir / 'copyboard-kde-service.desktop'
        script_file = package_dir / 'install-kde-service.sh'
        
        if not service_file.exists() or not script_file.exists():
            return {
                'success': False,
                'message': "KDE service menu files not found. Make sure the package is correctly installed."
            }
        
        # Run the installation script
        result = subprocess.run(['bash', str(script_file)], 
                               capture_output=True, text=True, check=False)
                               
        if result.returncode != 0:
            return {
                'success': False,
                'message': f"Failed to install KDE service menu: {result.stderr}"
            }
            
        return {
            'success': True,
            'message': "KDE service menu installed successfully. "
                      "If it doesn't appear in the context menu, try logging out and back in."
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to install KDE service menu: {str(e)}"
        }

def install_thunar_or_caja_extension() -> Dict[str, Any]:
    """Install integration for Thunar (XFCE) or Caja (MATE)"""
    try:
        # Check which file manager is available
        thunar_available = shutil.which('thunar') is not None
        caja_available = shutil.which('caja') is not None
        
        if not thunar_available and not caja_available:
            return {
                'success': False,
                'message': "Neither Thunar nor Caja file managers were found."
            }
        
        # For these file managers, we'll use custom actions
        if thunar_available:
            return install_thunar_custom_actions()
        elif caja_available:
            return install_caja_actions()
            
    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to install extension: {str(e)}"
        }

def install_thunar_custom_actions() -> Dict[str, Any]:
    """Install Thunar custom actions"""
    try:
        # Create the actions directory
        actions_dir = Path.home() / '.config' / 'Thunar' / 'uca.xml'
        actions_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # If the file doesn't exist, create it
        if not actions_dir.exists():
            with open(actions_dir, 'w') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<actions>\n</actions>')
        
        # Read the current actions
        with open(actions_dir, 'r') as f:
            content = f.read()
        
        # Check if our actions are already there
        if 'Copyboard' in content:
            return {
                'success': True,
                'message': "Thunar custom actions already installed."
            }
        
        # Add our actions
        new_actions = """
  <action>
    <icon>edit-copy</icon>
    <name>Copy to Clipboard Board</name>
    <command>bash -c 'copyboard add "%f"'</command>
    <description>Add the selected file path to the clipboard board</description>
    <patterns>*</patterns>
    <audio-files/>
    <image-files/>
    <other-files/>
    <text-files/>
    <video-files/>
  </action>
  <action>
    <icon>edit-paste</icon>
    <name>Open Copyboard</name>
    <command>copyboard-gui</command>
    <description>Open the Copyboard GUI</description>
    <patterns>*</patterns>
    <directories/>
    <audio-files/>
    <image-files/>
    <other-files/>
    <text-files/>
    <video-files/>
  </action>
</actions>
"""
        # Insert our actions before the closing tag
        content = content.replace('</actions>', new_actions)
        
        # Write the updated file
        with open(actions_dir, 'w') as f:
            f.write(content)
            
        return {
            'success': True,
            'message': "Thunar custom actions installed successfully. "
                      "You can access Copyboard from the right-click menu in Thunar."
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to install Thunar custom actions: {str(e)}"
        }

def install_caja_actions() -> Dict[str, Any]:
    """Install Caja actions"""
    # Implementation similar to Thunar but for Caja
    # This is a simpler implementation since Caja uses .desktop files
    try:
        # Create the actions directory
        actions_dir = Path.home() / '.local' / 'share' / 'caja' / 'actions'
        actions_dir.mkdir(parents=True, exist_ok=True)
        
        # Create action files
        copy_action = actions_dir / 'copyboard-copy.desktop'
        with open(copy_action, 'w') as f:
            f.write("""[Desktop Entry]
Type=Action
Name=Copy to Clipboard Board
Comment=Add the selected item to the clipboard board
Exec=bash -c 'copyboard add "%f"'
Icon=edit-copy
Selection=Any
Extensions=any;
""")
        
        open_action = actions_dir / 'copyboard-open.desktop'
        with open(open_action, 'w') as f:
            f.write("""[Desktop Entry]
Type=Action
Name=Open Copyboard
Comment=Open the Copyboard GUI
Exec=copyboard-gui
Icon=edit-paste
Selection=Any
Extensions=any;
""")
        
        return {
            'success': True,
            'message': "Caja actions installed successfully. "
                      "You can access Copyboard from the right-click menu in Caja."
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to install Caja actions: {str(e)}"
        }
