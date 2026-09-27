# Copyboard Changelog

## Unreleased

### Added
- Configurable cylinder of 10–16 chambers with one source of truth in `core`
  (`get_chamber_count` / `set_chamber_count`) shared by the editor, widget,
  hotkeys, labels, and `config.json`; shrinking asks first and ejects only the
  oldest rounds
- Direct global shortcuts for chambers 11–16 (`Ctrl+Alt+Shift+1…6`), an
  editable shortcut table with per-combo registration/conflict status, and a
  thread-safe fired-chamber notification routed through the Tk event loop
- Mouse-wheel and arrow-key aiming in the quick-paste widget (never fires),
  Enter/Space to fire, digit dialling up to chamber 16, and a two-press eject
- Quick-paste widget redesigned as a brushed-steel plate with a blue glow
  ring, violet-to-navy recessed chambers, a bolt-hole hub showing the loaded
  count, and COPY / PASTE tabs (capture the clipboard / fire the aimed round);
  the plate itself drags, and it stays hidden after a fire whenever a global
  shortcut can bring it back (`window.widget_reopen_after_fire` overrides)
- Chamber numbering helpers (`copyboard_extension.chambers`) as the single
  conversion point between board indexes and the `01`–`16` labels

### Changed
- Firing or pasting a chamber is read-only for the cylinder; CopyBoard's own
  clipboard writes are recorded before they land so the poller never re-loads
  a fired round into chamber 01
- Fire & Hide and widget fires only synthesise a paste after focus provably
  returned to the previous window; otherwise the round stays on the clipboard
  with a visible fallback message
- The editor's cylinder and the widget's ring now derive their geometry from
  the chamber count and the available canvas, so 16 chambers fit without
  clipping or overlapping targets
- Linux paste keystroke now clears held modifiers (`xdotool --clearmodifiers`)

## Version 0.5.0 (2026-08-15)

### Added
- Ten-chamber MK II desktop interface with automatic clipboard capture
- Compact quick-paste widget with click and drag gestures
- Purpose-built CopyBoard application icon and desktop launcher
- Flutter mobile foundation for Android and iOS
- Reproducible Linux packaging for AppImage and Debian packages
- Tag-driven GitHub Actions workflow that prepares draft releases

### Fixed
- Replaced launchers that referenced obsolete machine-specific paths
- Prevented clean shutdowns and test imports from overwriting clipboard history
- Corrected Linux fallback paste escaping

### Changed
- Standardized desktop package metadata and versioning on 0.5.0
- Declared the project license in a distributable MIT license file

## Version 0.4.0 (2025-03-04)

### Added
- **Browser Extension Integration**
  - Chrome and Firefox extensions with native messaging support
  - Context menu options to copy and paste from web pages
  - Radial menu interface for selecting clipboard items in browser
  - Real-time clipboard syncing between browser and desktop app
  - Visual feedback for clipboard operations in browser extension icon

### Fixed
- Fixed native messaging host communication issues
- Improved error handling in browser extension
- Added better feedback for clipboard operations
- Fixed Firefox extension configuration
- Added robust error logging for native messaging

## Version 0.3.0 (2025-03-04)

### Added
- **Radial Menu Interface**
  - Innovative radial/pie menu for quick clipboard item selection
  - Hold right-click on "Paste" option to activate
  - Visual selection of clipboard items by moving cursor
  - Intuitive directional selection mechanism

## Version 0.2.0 (2025-03-04)

### Added
- **System-Wide Integration**
  - Global hotkeys for clipboard operations (Ctrl+Alt+X, Ctrl+Alt+V)
  - Custom combination dialog accessible from any application
  - System-wide paste functionality using keyboard simulation

- **Context Menu Enhancements**
  - Added support for pasting multiple clipboard items as combinations
  - Hierarchical menus for better organization of clipboard items
  - Custom combination dialog from right-click menu
  - "Paste All" option to paste all clipboard items at once

- **Core Functionality**
  - Added paste_helper module for cross-platform paste simulation
  - Enhanced clipboard combination features
  - Improved error handling and logging

### Changed
- Refactored clipboard pasting to use platform-specific utilities
- Improved context menu structure for better usability
- Enhanced logging for extension debugging

### Fixed
- Fixed issues with Nautilus extension not loading properly
- Added proper error handling for clipboard operations
- Improved path handling for system integration

## Version 0.1.0 (2025-03-01)

### Added
- Initial implementation of Copyboard
- Basic clipboard board functionality
- Nautilus extension for file manager integration
- KDE service menu for Dolphin integration
- Command-line interface for clipboard operations
- Graphical user interface for clipboard management
