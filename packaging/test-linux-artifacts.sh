#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/release-build"
DIST_ROOT="$PROJECT_ROOT/release-dist"

cd "$PROJECT_ROOT"

VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)"
DEB_PATH="$DIST_ROOT/CopyBoard_${VERSION}_amd64.deb"
APPIMAGE_PATH="$DIST_ROOT/CopyBoard-x86_64.AppImage"
TEMP_ROOT="$(mktemp -d)"

cleanup() {
    rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

for command_name in dpkg-deb desktop-file-validate appstreamcli timeout xvfb-run xdpyinfo; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required test command is missing: %s\n' "$command_name" >&2
        exit 1
    fi
done

if [[ ! -f "$DEB_PATH" ]]; then
    printf 'Debian package is missing: %s\n' "$DEB_PATH" >&2
    exit 1
fi

(
    cd "$DIST_ROOT"
    sha256sum --check SHA256SUMS
)

dpkg-deb --info "$DEB_PATH" >/dev/null
dpkg-deb --extract "$DEB_PATH" "$TEMP_ROOT/deb"
desktop-file-validate "$TEMP_ROOT/deb/usr/share/applications/copyboard.desktop"
appstreamcli validate --no-net "$TEMP_ROOT/deb/usr/share/metainfo/io.github.dennisjcarroll.copyboard.metainfo.xml"

smoke_gui() {
    local label="$1"
    shift
    set +e
    xvfb-run -a sh -c 'xdpyinfo >/dev/null && exec timeout 5s "$@"' sh "$@"
    local status=$?
    set -e
    if [[ $status -ne 124 ]]; then
        printf '%s exited during its smoke window (status %s)\n' "$label" "$status" >&2
        exit 1
    fi
    printf '%s stayed healthy for the five-second smoke window.\n' "$label"
}

smoke_gui \
    "Debian package executable" \
    "$TEMP_ROOT/deb/opt/copyboard/copyboard-gui"

if [[ -f "$APPIMAGE_PATH" ]]; then
    smoke_gui \
        "AppImage" \
        env APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE_PATH"
else
    printf 'AppImage is absent; skipping its smoke test.\n'
fi
