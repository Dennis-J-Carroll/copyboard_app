# Releasing CopyBoard

CopyBoard's Linux release consists of two user-facing downloads:

- `CopyBoard_<version>_amd64.deb` for Debian, Ubuntu, and Linux Mint
- `CopyBoard-x86_64.AppImage` for portable use on x86-64 Linux

The AppImage bundles CopyBoard, Python, and Tk. It intentionally does not
redistribute the external GPL/X11 utilities used for cross-application
clipboard control, so AppImage users still need `xclip` and `xdotool` from
their distribution.

The release workflow deliberately creates a **draft** GitHub release. Nothing
becomes public until the artifacts have been downloaded and tested.

## Local build

Install the runtime and packaging requirements:

```bash
python3 -m pip install . pyinstaller
sudo apt install dpkg-dev xclip xdotool xvfb
```

Build the PyInstaller application and Debian package:

```bash
./packaging/build-linux.sh
```

To build the AppImage too, download `appimagetool` and provide its path:

```bash
APPIMAGETOOL=/path/to/appimagetool-x86_64.AppImage \
  ./packaging/build-linux.sh
```

Artifacts are written to `release-dist/`. The build script also creates
`SHA256SUMS`.

## GitHub release

1. Confirm `pytest -q` and the local packaging smoke tests pass.
2. Update `CHANGELOG.md` and ensure `pyproject.toml` contains the release
   version.
3. Commit the release changes and push the branch for review.
4. Create and push the matching tag, for example `v0.5.0`.
5. The `Release Linux` workflow builds both packages and creates a draft
   GitHub release.
6. Download both assets from the draft and test them on a clean Ubuntu system.
7. Publish the draft release from GitHub only after the clean-system test.

The website can link to a published latest-release asset at:

```text
https://github.com/Dennis-J-Carroll/copyboard_app/releases/latest/download/CopyBoard-x86_64.AppImage
```
