# Copyboard Changelog

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
