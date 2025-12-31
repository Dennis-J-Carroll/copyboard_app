# CopyBoard Mobile

A mobile multi-clipboard app with intuitive hold-and-drag gesture for selecting items to paste.

## Features

- 📋 **Multi-Clipboard Storage**: Store 5-20 clipboard items (user configurable)
- 👆 **Hold & Drag Selection**: Hold and drag down to visually select which item to paste
- 🔄 **Persistent Storage**: Items saved across app restarts
- ⚡ **Haptic Feedback**: Feel the selection as you drag
- 🎨 **Clean UI**: Dark theme with beautiful animations
- 📱 **Cross-Platform**: Works on Android and iOS

## How It Works

### Basic Usage

1. **Copy** something anywhere on your phone (Ctrl+C / long-press → Copy)
2. Open **CopyBoard** app
3. Tap **"Add from Clipboard"** to save the item
4. Repeat to build your clipboard history (up to 10+ items)

### Paste from Board

**Method 1: Quick Tap**
- Tap any item to copy it to clipboard
- Switch to your app and paste normally

**Method 2: Hold & Drag** (Unique Feature!)
- Hold and drag down on the first item
- As you drag, items highlight showing what will be pasted
- Release to automatically copy that item to clipboard
- Provides haptic feedback as you select

### Settings

- Tap the ⚙️ icon to change max items (5-20)
- Choose how many clipboard items to store

## Installation

### React Native Version

```bash
cd copyboard_mobile

# Install dependencies
npm install

# Run on Android
npm run android

# Run on iOS
npm run ios
```

### Flutter Version (Simpler Alternative)

```bash
cd copyboard_mobile_flutter

# Get dependencies
flutter pub get

# Run on connected device
flutter run
```

## Tech Stack

### React Native Version
- **React Native** 0.73
- **@react-native-clipboard/clipboard** - Clipboard access
- **@react-native-async-storage/async-storage** - Persistent storage
- **react-native-gesture-handler** - Gesture support
- **react-native-haptic-feedback** - Haptic vibrations

### Flutter Version
- **Flutter** 3.x
- **shared_preferences** - Storage
- **flutter_clipboard_manager** - Clipboard
- **vibration** - Haptics

## Screenshots

```
┌─────────────────────────┐
│  📋 CopyBoard           │
│  3/10 items         ⚙️  │
├─────────────────────────┤
│ 👆 Tap item to copy     │
│ 👇 Hold & drag to select│
├─────────────────────────┤
│ ➕ Add from Clipboard   │
├─────────────────────────┤
│ ┌───────────────────┐   │
│ │ 1 📌 Most Recent  │   │
│ │ Hello World!      │   │
│ └───────────────────┘   │
│ ┌───────────────────┐   │
│ │ 2 Item 2          │   │
│ │ Python code...    │   │
│ └───────────────────┘   │
│ ┌───────────────────┐   │
│ │ 3 Item 3          │   │
│ │ https://...       │   │
│ └───────────────────┘   │
└─────────────────────────┘
```

## UI/UX Design

### Color Scheme
- **Background**: Dark navy (#1a1a2e)
- **Cards**: Dark blue (#16213e)
- **Accent**: Pink/Red (#e94560)
- **Text**: White/Gray

### Interactions
- **Tap item**: Copy to clipboard
- **Long press item**: Remove from board
- **Hold & drag first item**: Gesture-based selection
- **Tap ⚙️**: Open settings
- **Tap ➕**: Add current clipboard

### Haptic Feedback
- **Light**: When selecting items while dragging
- **Medium**: When removing items
- **Success**: When copying to clipboard
- **Warning**: When clearing all items

## Platform-Specific Features

### Android
- Uses Android's native clipboard manager
- Material Design components
- System share integration (future)

### iOS
- Uses iOS UIPasteboard
- Native iOS gestures
- Share Sheet integration (future)

## Future Enhancements

### Integration with System
- [ ] **Clipboard Monitor**: Auto-add copied items
- [ ] **Floating Widget**: Quick access overlay
- [ ] **Keyboard Extension**: Paste from custom keyboard
- [ ] **Share Extension**: "Share to CopyBoard" option

### Features
- [ ] **Search**: Find items in clipboard history
- [ ] **Categories**: Tag/organize items
- [ ] **Sync**: Cloud sync across devices
- [ ] **Rich Content**: Images, files, links
- [ ] **Smart Paste**: Format based on context

### UI/UX
- [ ] **Swipe to Delete**: Swipe left to remove
- [ ] **Drag to Reorder**: Change item order
- [ ] **Custom Themes**: Light/dark/custom colors
- [ ] **Widgets**: Home screen widgets

## Architecture

```
App.js
├── State Management
│   ├── clipboardItems (array of strings)
│   ├── maxItems (configurable limit)
│   ├── selectedIndex (drag selection)
│   └── isDragging (gesture state)
│
├── Storage Layer
│   ├── AsyncStorage for persistence
│   └── Auto-save on changes
│
├── Clipboard Layer
│   ├── Read from system clipboard
│   └── Write to system clipboard
│
└── UI Components
    ├── Header (title, count, settings)
    ├── Settings Panel (max items selector)
    ├── Instructions
    ├── Action Buttons (add, clear)
    ├── Item List (scrollable)
    └── Drag Indicator (selection feedback)
```

## Data Flow

```
Copy externally
    ↓
System Clipboard
    ↓
User taps "Add from Clipboard"
    ↓
App reads clipboard
    ↓
Add to board (newest first)
    ↓
Save to AsyncStorage
    ↓
Update UI

---

User holds & drags
    ↓
PanResponder detects gesture
    ↓
Calculate selected index from drag distance
    ↓
Haptic feedback on selection change
    ↓
User releases
    ↓
Copy selected item to system clipboard
    ↓
User pastes in other app
```

## Development

### Running Locally

```bash
# Clone the repo
git clone <repo-url>
cd copyboard_app/copyboard_mobile

# Install dependencies
npm install

# Start Metro bundler
npm start

# In another terminal, run on device
npm run android  # or npm run ios
```

### Building for Production

**Android:**
```bash
cd android
./gradlew assembleRelease
# APK at: android/app/build/outputs/apk/release/app-release.apk
```

**iOS:**
```bash
cd ios
pod install
# Open in Xcode and archive
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file

## Author

CopyBoard Mobile - Making multi-clipboard accessible on mobile devices
