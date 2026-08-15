#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/release-build"
DIST_ROOT="$PROJECT_ROOT/release-dist"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SPEC_FILE="$SCRIPT_DIR/CopyBoard.spec"
DESKTOP_FILE="$SCRIPT_DIR/linux/copyboard.desktop"
APPSTREAM_FILE="$SCRIPT_DIR/linux/io.github.dennisjcarroll.copyboard.metainfo.xml"
ICON_FILE="$PROJECT_ROOT/copyboard_extension/assets/copyboard-icon.png"

cd "$PROJECT_ROOT"

if [[ "$(uname -m)" != "x86_64" ]]; then
    printf 'This release script currently supports x86-64 Linux only.\n' >&2
    exit 1
fi

VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)"
if [[ -z "$VERSION" ]]; then
    printf 'Unable to read the CopyBoard version from pyproject.toml\n' >&2
    exit 1
fi

case "$BUILD_ROOT" in
    "$PROJECT_ROOT"/release-build) ;;
    *) printf 'Refusing unsafe build directory: %s\n' "$BUILD_ROOT" >&2; exit 1 ;;
esac

for command_name in "$PYTHON_BIN" pyinstaller dpkg-deb desktop-file-validate appstreamcli; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required build command is missing: %s\n' "$command_name" >&2
        exit 1
    fi
done

if [[ ! -f "$ICON_FILE" ]]; then
    printf 'Application icon is missing: %s\n' "$ICON_FILE" >&2
    exit 1
fi

appstreamcli validate --no-net "$APPSTREAM_FILE"

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT" "$DIST_ROOT"

printf 'Building CopyBoard %s with PyInstaller...\n' "$VERSION"
pyinstaller \
    --noconfirm \
    --clean \
    --distpath "$BUILD_ROOT/pyinstaller-dist" \
    --workpath "$BUILD_ROOT/pyinstaller-work" \
    "$SPEC_FILE"

BUNDLE_DIR="$BUILD_ROOT/pyinstaller-dist/CopyBoard"
if [[ ! -x "$BUNDLE_DIR/copyboard-gui" ]]; then
    printf 'PyInstaller did not produce the expected application bundle\n' >&2
    exit 1
fi

printf 'Building Debian package...\n'
DEB_ROOT="$BUILD_ROOT/deb-root"
install -d \
    "$DEB_ROOT/DEBIAN" \
    "$DEB_ROOT/opt/copyboard" \
    "$DEB_ROOT/usr/bin" \
    "$DEB_ROOT/usr/share/applications" \
    "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps" \
    "$DEB_ROOT/usr/share/metainfo" \
    "$DEB_ROOT/usr/share/doc/copyboard"
cp -a "$BUNDLE_DIR/." "$DEB_ROOT/opt/copyboard/"
install -m 0755 "$SCRIPT_DIR/linux/copyboard-deb-launcher" "$DEB_ROOT/usr/bin/copyboard-gui"
install -m 0644 "$DESKTOP_FILE" "$DEB_ROOT/usr/share/applications/copyboard.desktop"
install -m 0644 "$ICON_FILE" "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/copyboard.png"
install -m 0644 "$APPSTREAM_FILE" "$DEB_ROOT/usr/share/metainfo/io.github.dennisjcarroll.copyboard.metainfo.xml"
install -m 0644 "$PROJECT_ROOT/LICENSE" "$DEB_ROOT/usr/share/doc/copyboard/copyright"
desktop-file-validate "$DEB_ROOT/usr/share/applications/copyboard.desktop"

cat >"$DEB_ROOT/DEBIAN/control" <<EOF
Package: copyboard
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Dennis J. Carroll
Depends: xclip, xdotool
Homepage: https://github.com/Dennis-J-Carroll/copyboard_app
Description: Ten-chamber clipboard history for Linux desktops
 CopyBoard captures recent text clipboard entries in a visual ten-chamber
 revolver and lets users copy or paste any loaded entry.
EOF

DEB_PATH="$DIST_ROOT/CopyBoard_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_PATH"

printf 'Preparing AppImage filesystem...\n'
APPDIR="$BUILD_ROOT/CopyBoard.AppDir"
install -d \
    "$APPDIR/usr/lib/copyboard" \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/512x512/apps" \
    "$APPDIR/usr/share/metainfo"
cp -a "$BUNDLE_DIR/." "$APPDIR/usr/lib/copyboard/"
ln -s ../lib/copyboard/copyboard-gui "$APPDIR/usr/bin/copyboard-gui"
install -m 0755 "$SCRIPT_DIR/linux/AppRun" "$APPDIR/AppRun"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/copyboard.desktop"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/usr/share/applications/copyboard.desktop"
install -m 0644 "$ICON_FILE" "$APPDIR/copyboard.png"
install -m 0644 "$ICON_FILE" "$APPDIR/usr/share/icons/hicolor/512x512/apps/copyboard.png"
install -m 0644 "$APPSTREAM_FILE" "$APPDIR/usr/share/metainfo/io.github.dennisjcarroll.copyboard.metainfo.xml"
ln -s copyboard.png "$APPDIR/.DirIcon"

APPIMAGE_PATH="$DIST_ROOT/CopyBoard-x86_64.AppImage"
if [[ -n "${APPIMAGETOOL:-}" ]]; then
    if [[ ! -x "$APPIMAGETOOL" ]]; then
        printf 'APPIMAGETOOL is not executable: %s\n' "$APPIMAGETOOL" >&2
        exit 1
    fi
    rm -f "$APPIMAGE_PATH"
    if [[ "$APPIMAGETOOL" == *.AppImage ]]; then
        ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE_PATH"
    else
        ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_PATH"
    fi
    chmod 0755 "$APPIMAGE_PATH"
else
    printf 'APPIMAGETOOL is not set; AppDir created but AppImage generation skipped.\n'
fi

CHECKSUM_INPUTS=("$DEB_PATH")
if [[ -f "$APPIMAGE_PATH" ]]; then
    CHECKSUM_INPUTS+=("$APPIMAGE_PATH")
fi
(
    cd "$DIST_ROOT"
    sha256sum "${CHECKSUM_INPUTS[@]##*/}" >SHA256SUMS
)

printf '\nRelease artifacts:\n'
for artifact in "$DEB_PATH" "$APPIMAGE_PATH" "$DIST_ROOT/SHA256SUMS"; do
    if [[ -f "$artifact" ]]; then
        printf '  %s\n' "$artifact"
    fi
done
