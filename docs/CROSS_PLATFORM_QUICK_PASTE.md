# Cross-platform quick-paste architecture

CopyBoard uses one ten-round mental model but different operating-system
surfaces. A floating desktop window, a phone home-screen widget, and a phone
keyboard do not receive the same privileges, so treating them as one feature
would produce unreliable or store-ineligible behavior.

## Product surfaces

| Surface | Desktop | iOS / iPadOS | Android |
| --- | --- | --- | --- |
| Full board editor | Python/Tkinter today | Flutter | Flutter |
| Compact revolver | Always-on-top quick-paste window | In-app compact view | In-app compact view; overlay can be optional later |
| One-tap insertion in another app | Restore target window, then synthesize paste | Native keyboard extension calls `insertText` | Native IME calls `commitText` |
| Cross-app drag | Native Flutter drag in the future | Supported by the Flutter drag bridge; best on iPad/multitasking | Supported in multi-window mode |
| Home-screen widget | Not applicable | WidgetKit launcher/status surface | Jetpack Glance launcher/status surface |

The keyboard is the dependable phone equivalent of the desktop quick-paste
widget. A home-screen widget can display rounds and launch or copy an action,
but it cannot insert text into the field of an unrelated foreground app.

## Platform constraints that shape the design

- Android 10 and later prevents ordinary background apps from reading the
  foreground clipboard. Capture therefore stays explicit in the mobile app;
  CopyBoard must not claim continuous background clipboard monitoring.
- iOS custom keyboards insert text through `textDocumentProxy.insertText`.
  They cannot appear in secure fields, phone-pad fields, or apps that reject
  third-party keyboards.
- Android input methods insert through the active `InputConnection` and
  `commitText`.
- An iOS keyboard can read the containing app's shared App Group container
  without requesting Full Access. CopyBoard should keep keyboard storage
  read-only and offline so Full Access is unnecessary for the initial release.
- Cross-app drag is system-mediated. Flutter's `super_drag_and_drop` bridges
  the native iOS, Android, macOS, Windows, and Linux drag APIs. Android
  cross-app drops require multi-window; iOS cross-app drag is available on
  iPhone from iOS 15 and is most natural on iPad.

## Repository direction

`copyboard_mobile_flutter` is the canonical phone client. The React Native
prototype remains reference material and should not receive parallel feature
work. Flutter owns the reusable revolver view and mobile board editor; the two
small text-insertion surfaces remain native because they are operating-system
extensions:

```text
Flutter containing app
    ├── shared ten-round store
    ├── revolver editor
    ├── explicit clipboard capture
    └── native cross-app drag bridge

iOS Keyboard Extension (Swift/UIKit)
    ├── read App Group board snapshot
    ├── render ten compact chamber buttons
    └── textDocumentProxy.insertText(round.text)

Android IME (Kotlin)
    ├── read shared board snapshot
    ├── render ten compact chamber buttons
    └── currentInputConnection.commitText(round.text, 1)
```

The containing app writes an atomic, versioned JSON snapshot after every board
change. Extensions only read it. A future sync service can replace the local
writer without changing the extension contract.

## Delivery sequence

1. Ship and test the desktop quick-paste overlay.
2. Finish the Flutter project scaffolding for Android and iOS, then validate
   the revolver and native cross-app text drag on devices.
3. Add the shared, versioned board snapshot and migration from the current
   string-list storage.
4. Add the iOS keyboard extension with an App Group and no Full Access.
5. Add the Android `InputMethodService` using the same snapshot contract.
6. Add optional WidgetKit and Glance home widgets as quick launch/status
   surfaces, not as the primary paste mechanism.

## Primary references

- [Apple: Creating a custom keyboard](https://developer.apple.com/documentation/uikit/creating-a-custom-keyboard)
- [Apple: Configuring open access for a custom keyboard](https://developer.apple.com/documentation/uikit/configuring-open-access-for-a-custom-keyboard)
- [Apple: Drag and drop](https://developer.apple.com/documentation/uikit/drag-and-drop)
- [Apple: Adding interactivity to widgets](https://developer.apple.com/documentation/widgetkit/adding-interactivity-to-widgets-and-live-activities)
- [Android: Create an input method](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method)
- [Android: Secure clipboard handling](https://developer.android.com/privacy-and-security/risks/secure-clipboard-handling)
- [Android: Drag and drop in multi-window mode](https://developer.android.com/develop/ui/views/touch-and-input/drag-drop/multi-window)
- [Flutter: Drag outside an app](https://docs.flutter.dev/ui/interactivity/gestures/drag-outside)
- [Flutter: Adding iOS app extensions](https://docs.flutter.dev/platform-integration/ios/app-extensions)
