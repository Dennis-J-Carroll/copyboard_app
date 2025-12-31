# CopyBoard Mobile - Complete Setup Guide

**Transform your mobile clipboard experience with hold-and-drag multi-clipboard management!**

---

## 🎯 What is CopyBoard Mobile?

A **mobile multi-clipboard app** that lets you store and manage **multiple clipboard items** (1-20, user configurable) with an intuitive **hold-and-drag gesture** for quick selection and pasting.

### Key Features

✨ **Multi-Clipboard Storage**: Store up to 20 items (configurable: 5, 6, 7, 8, 9, 10, 12, 15, 20)
👆 **Hold & Drag Selection**: Unique gesture-based interface for item selection
📱 **Cross-Platform**: Works on Android and iOS
🔄 **Persistent Storage**: Items saved across app restarts
⚡ **Haptic Feedback**: Feel the selection as you drag
🎨 **Beautiful Dark Theme**: Clean, modern UI with animations

---

## 🚀 Quick Start

### The Hold & Drag Experience

This is the **unique feature** that makes CopyBoard Mobile special:

```
1. Hold your finger on the FIRST item
2. Drag down slowly
3. As you drag, items highlight one by one
4. You FEEL each selection (haptic vibration)
5. Release on the item you want
6. It's automatically copied to clipboard!
```

**Visual:**
```
┌─────────────────────┐
│ Item 1 ◄── Hold here
└─────────────────────┘
       ↓ Drag down
┌─────────────────────┐
│ Item 2 ◄── Selected!
└─────────────────────┘
       ↓ Keep dragging
┌─────────────────────┐
│ Item 3 ◄── Selected!
└─────────────────────┘
     Release = Paste!
```

---

## 📱 Two Versions Available

### Option 1: Flutter (Recommended)
**Easier to install, better performance, simpler**

### Option 2: React Native
**More features, larger ecosystem**

Choose based on your preference or use both!

---

## 🛠️ Installation

### Prerequisites

**For Flutter:**
```bash
# Install Flutter SDK
# Visit: https://flutter.dev/docs/get-started/install

# Verify installation
flutter doctor
```

**For React Native:**
```bash
# Install Node.js (18+)
# Visit: https://nodejs.org

# Install React Native CLI
npm install -g react-native-cli
```

**For Android:**
```bash
# Install Android Studio
# Visit: https://developer.android.com/studio

# Install Android SDK and emulator
```

**For iOS (macOS only):**
```bash
# Install Xcode from App Store
# Install CocoaPods
sudo gem install cocoapods
```

---

## 🏃 Running the App

### Flutter Version

```bash
cd copyboard_app/copyboard_mobile_flutter

# Get dependencies
flutter pub get

# Connect your device or start emulator

# Run the app
flutter run

# Build APK (Android)
flutter build apk

# Build for iOS
flutter build ios
```

### React Native Version

```bash
cd copyboard_app/copyboard_mobile

# Install dependencies
npm install

# Android
npm run android

# iOS (macOS only)
npm run ios
```

---

## 📖 How to Use

### Step 1: Add Items to Your Board

```
1. Copy something anywhere on your phone
   (Ctrl+C, long-press → Copy, etc.)

2. Open CopyBoard app

3. Tap "➕ Add from Clipboard"

4. Your item is now saved!

5. Repeat up to 10+ times
```

### Step 2: Paste from Board

**Method A: Quick Tap** (Simple)
```
1. Tap any item in the list
2. It's copied to clipboard
3. Switch to another app
4. Paste normally (Ctrl+V or long-press → Paste)
```

**Method B: Hold & Drag** (Advanced)
```
1. Hold finger on FIRST item
2. Drag down slowly
3. Feel haptic feedback as items highlight
4. Release on desired item
5. It's automatically copied!
6. Switch to another app and paste
```

### Step 3: Manage Your Board

**Configure Max Items:**
```
1. Tap ⚙️ (settings icon)
2. Choose max items: 5, 6, 7, 8, 9, 10, 12, 15, or 20
3. Your choice is saved
```

**Remove Items:**
```
1. Long-press any item
2. Confirm removal
```

**Clear All:**
```
1. Tap "🗑️ Clear All" button
2. Confirm
```

---

## 🎨 UI Overview

### Main Screen Layout

```
┌────────────────────────────────┐
│ 📋 CopyBoard        3/10   ⚙️  │ ← Header
├────────────────────────────────┤
│ Settings Panel (when open)     │ ← Max items selector
├────────────────────────────────┤
│ 👆 Tap to copy                 │ ← Instructions
│ 👇 Hold & drag to select       │
├────────────────────────────────┤
│ ➕ Add from Clipboard  | 🗑️    │ ← Actions
├────────────────────────────────┤
│ ┌──────────────────────────┐   │
│ │ 1 📌 Most Recent         │   │ ← Item 1
│ │ Hello World!             │   │
│ └──────────────────────────┘   │
│ ┌──────────────────────────┐   │
│ │ 2 Item 2                 │   │ ← Item 2
│ │ https://example.com      │   │
│ └──────────────────────────┘   │
│ ┌──────────────────────────┐   │
│ │ 3 Item 3                 │   │ ← Item 3
│ │ Code snippet here...     │   │
│ └──────────────────────────┘   │
│                                │
└────────────────────────────────┘
```

### Color Scheme

- **Background**: Dark Navy `#1a1a2e`
- **Cards**: Dark Blue `#16213e`
- **Accent**: Pink/Red `#e94560`
- **Borders**: Deeper Blue `#0f3460`
- **Text**: White / Gray

---

## 💡 Use Cases

### 1. Research & Note-Taking
```
Copy multiple facts/quotes from different sources
→ Store them all in CopyBoard
→ Paste them selectively into your document
```

### 2. Form Filling
```
Copy: Name, Address, Email, Phone, etc.
→ Fill multiple forms without re-typing
→ Just tap items to paste each field
```

### 3. Code Development
```
Copy: Function names, imports, snippets
→ Build your code by pasting from board
→ No more switching between files
```

### 4. Social Media
```
Copy: Hashtags, links, captions
→ Post to multiple platforms
→ Mix and match saved content
```

### 5. Shopping
```
Copy: Product codes, tracking numbers, coupons
→ Keep everything accessible
→ Paste when needed
```

---

## 🎯 Gestures & Interactions

### Tap
- **Single tap item**: Copy to clipboard
- **Tap ➕ button**: Add current clipboard
- **Tap ⚙️ icon**: Toggle settings
- **Tap number**: Select max items

### Long Press
- **Long press item**: Remove item dialog
- **Hold first item**: Start drag selection

### Drag
- **Hold & drag first item down**: Select items as you drag
- **Drag distance**: Determines which item is selected
- **Haptic feedback**: Feel each item selection

### Release
- **Release after drag**: Copy selected item to clipboard

---

## 🔧 Technical Details

### Data Storage

**Location:**
- **Flutter**: `SharedPreferences` (platform-specific)
- **React Native**: `AsyncStorage` (platform-specific)

**Format:**
```json
{
  "copyboard_items": [
    "Most recent item",
    "Second item",
    "Third item",
    ...
  ],
  "copyboard_max_items": 10
}
```

**Persistence:**
- Automatic save on every change
- Items persist across app restarts
- Max items setting remembered

### Gestures

**Drag Detection:**
```dart
onVerticalDragStart: (details) {
  // User touched first item
  isDragging = true;
  selectedIndex = 0;
}

onVerticalDragUpdate: (details) {
  // User is dragging
  dragDistance += details.delta.dy;
  // Calculate which item based on distance
  selectedIndex = calculateIndex(dragDistance);
  // Haptic feedback on selection change
}

onVerticalDragEnd: (details) {
  // User released
  copyToClipboard(selectedIndex);
  isDragging = false;
}
```

### Haptic Feedback

**Vibration Patterns:**
- **Light (5-10ms)**: Item selection change
- **Medium (15-20ms)**: Item copied
- **Strong (30ms)**: Clear all

---

## 📱 Platform-Specific Notes

### Android

**Clipboard Access:**
- Uses `ClipboardManager` API
- Works on Android 5.0+ (API 21+)

**Permissions:**
- No special permissions required
- Clipboard access is standard

**Build:**
```bash
# Debug APK
flutter build apk --debug

# Release APK
flutter build apk --release

# App Bundle (for Play Store)
flutter build appbundle
```

### iOS

**Clipboard Access:**
- Uses `UIPasteboard` API
- Works on iOS 12.0+

**Permissions:**
- No special permissions required

**Build:**
```bash
# Debug
flutter build ios --debug

# Release
flutter build ios --release
```

---

## 🚀 Deployment

### Android (Google Play Store)

```bash
# 1. Build release APK
flutter build apk --release

# 2. Or build app bundle (recommended)
flutter build appbundle

# 3. Sign the app
# Use Android Studio or command line signing

# 4. Upload to Google Play Console
# https://play.google.com/console
```

### iOS (Apple App Store)

```bash
# 1. Build for release
flutter build ios --release

# 2. Open in Xcode
open ios/Runner.xcworkspace

# 3. Archive and upload
# Product → Archive → Upload to App Store

# 4. Submit via App Store Connect
# https://appstoreconnect.apple.com
```

---

## 🎓 Development Guide

### Project Structure

```
copyboard_mobile_flutter/
├── lib/
│   └── main.dart              # Main app code
├── android/                   # Android-specific files
├── ios/                       # iOS-specific files
├── pubspec.yaml               # Dependencies
└── README.md

copyboard_mobile/
├── App.js                     # Main React Native code
├── package.json               # Dependencies
├── android/                   # Android-specific
├── ios/                       # iOS-specific
└── README.md
```

### Adding Features

**New gesture:**
```dart
// Add in GestureDetector
onHorizontalDragEnd: (details) {
  // Swipe to delete functionality
}
```

**New storage field:**
```dart
// Add to SharedPreferences
prefs.setString('new_field', value);
```

**New UI component:**
```dart
Widget _buildNewFeature() {
  return Container(
    // Your new UI here
  );
}
```

---

## 🐛 Troubleshooting

### App won't build
```bash
# Flutter
flutter clean
flutter pub get
flutter run

# React Native
cd android && ./gradlew clean && cd ..
npm install
npm run android
```

### Clipboard not working
```
- Ensure app has focus
- Check clipboard has content
- Try on real device (not emulator)
```

### Haptics not working
```
- Only works on real devices
- Check device vibration settings
- iOS: Haptics require physical device
```

### Items not persisting
```
- Check storage permissions
- Verify async/await calls
- Check console for errors
```

---

## 🔮 Future Features

### Planned Enhancements

- [ ] **Clipboard Monitor**: Auto-add copied items
- [ ] **Floating Widget**: Quick access overlay
- [ ] **Share Extension**: "Share to CopyBoard"
- [ ] **Keyboard Extension**: Custom keyboard with board access
- [ ] **Search**: Find items in history
- [ ] **Categories**: Tag and organize items
- [ ] **Cloud Sync**: Sync across devices
- [ ] **Rich Content**: Images, files, formatted text
- [ ] **Swipe to Delete**: Gesture to remove items
- [ ] **Drag to Reorder**: Rearrange item order
- [ ] **Export/Import**: Backup clipboard history
- [ ] **Themes**: Light/dark/custom colors
- [ ] **Widgets**: Home screen widgets

---

## 📊 Comparison: Flutter vs React Native

| Feature | Flutter | React Native |
|---------|---------|--------------|
| **Performance** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Setup Time** | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **File Size** | Smaller | Larger |
| **Hot Reload** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Native Feel** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Learning Curve** | Moderate | Easy (if know JS) |
| **Community** | Growing | Established |

**Recommendation**: Use **Flutter** for this project - it's faster, simpler, and produces smaller apps.

---

## 📝 License

MIT License - Feel free to use, modify, and distribute!

---

## 🤝 Contributing

Contributions welcome! To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on Android and iOS
5. Submit a pull request

---

## 📧 Support

Having issues? Check:
- This guide
- Flutter docs: https://flutter.dev/docs
- React Native docs: https://reactnative.dev/docs

---

## 🎉 Conclusion

**CopyBoard Mobile brings desktop-class multi-clipboard management to your phone with an intuitive hold-and-drag interface!**

Key Advantages:
✅ Never lose clipboard content again
✅ Store up to 20 items
✅ Unique gesture-based selection
✅ Beautiful, responsive UI
✅ Cross-platform (Android & iOS)
✅ Free and open source

**Get started today and transform your mobile clipboard experience!**

---

*Made with ❤️ for better mobile productivity*
