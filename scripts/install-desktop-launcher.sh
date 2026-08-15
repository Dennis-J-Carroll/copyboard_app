#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$PROJECT_ROOT/bin/copyboard-gui"
ICON="$PROJECT_ROOT/copyboard_extension/assets/copyboard-icon.png"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
DESKTOP_DIR="${DESKTOP_DIR:-$HOME/Desktop}"
APPLICATION_ENTRY="$APPLICATIONS_DIR/copyboard.desktop"
DESKTOP_ENTRY="$DESKTOP_DIR/CopyBoard.desktop"

if [[ ! -x "$LAUNCHER" || ! -f "$ICON" ]]; then
    printf 'CopyBoard launcher or icon is missing from %s\n' "$PROJECT_ROOT" >&2
    exit 1
fi

mkdir -p "$APPLICATIONS_DIR" "$DESKTOP_DIR"

write_entry() {
    local target="$1"
    printf '%s\n' \
        '[Desktop Entry]' \
        'Version=1.0' \
        'Type=Application' \
        'Name=CopyBoard' \
        'GenericName=Clipboard Manager' \
        'Comment=Ten-chamber clipboard history' \
        "Exec=\"$LAUNCHER\"" \
        "Path=$PROJECT_ROOT" \
        "Icon=$ICON" \
        'Terminal=false' \
        'Categories=Utility;' \
        'Keywords=clipboard;copy;paste;history;' \
        'StartupNotify=true' \
        'StartupWMClass=CopyBoard' \
        >"$target"
    chmod 755 "$target"
}

write_entry "$APPLICATION_ENTRY"
write_entry "$DESKTOP_ENTRY"

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$APPLICATION_ENTRY" "$DESKTOP_ENTRY"
fi

# GNOME uses this metadata in addition to the executable bit for desktop files.
if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_ENTRY" metadata::trusted true >/dev/null 2>&1 || true
fi

printf 'Installed CopyBoard in the app menu and at %s\n' "$DESKTOP_ENTRY"
