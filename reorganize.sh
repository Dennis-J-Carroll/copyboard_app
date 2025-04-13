#!/bin/bash
# Reorganization script for copyboard_extension

# Create directory structure
mkdir -p bin build config copyboard_extension/browser_extension/icons docs scripts tests

# Create __init__.py files
touch copyboard_extension/__init__.py
touch tests/__init__.py

# Move core Python files to copyboard_extension
find . -maxdepth 1 -name "*.py" -not -name "setup.py" -not -name "reorganize.sh" -exec mv {} copyboard_extension/ \;

# Move utility scripts to scripts/
for script in fix_extension.py generate_icons.py global_hotkeys.py install_browser_extension.py simple_host.py test_native_host.py x11_shortcuts.py; do
  if [ -f "$script" ]; then
    mv "$script" scripts/
  elif [ -f "copyboard_extension/$script" ]; then
    mv "copyboard_extension/$script" scripts/
  fi
done

# Move configuration files
for config_file in chrome_manifest.json copyboard-kde-service.desktop nautilus-copyboard.py; do
  if [ -f "$config_file" ]; then
    mv "$config_file" config/
  fi
done

# Move shell scripts
for shell_script in install-kde-service.sh install-nautilus-extension.sh; do
  if [ -f "$shell_script" ]; then
    mv "$shell_script" scripts/
  fi
done

# Move documentation
if [ -f "CONTEXT_MENU_INTEGRATION.md" ]; then
  mv CONTEXT_MENU_INTEGRATION.md docs/
fi

# Create browser_extension structure if it exists
if [ -d "browser_extension" ]; then
  cp -r browser_extension/* copyboard_extension/browser_extension/
fi

# Update imports in Python files
find copyboard_extension -name "*.py" -exec sed -i 's/from copyboard_extension import/from . import/g' {} \;

echo "Reorganization complete. Please check the new structure." 