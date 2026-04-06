# AnyDaf — Project Guide

AnyDaf is a Talmud study app with parallel iOS (Swift/SwiftUI) and Android (Kotlin/Compose) codebases that must be kept in sync for every feature.

## Repository Layout

```
AnyDaf/
  AnyDaf/                    # iOS app (Swift/SwiftUI)
  android/app/src/main/
    java/com/anydaf/
      data/
        api/                 # Network clients (SefariaClient, FeedManager, DafYomiService, YCTLibraryClient)
        prefs/               # AppPreferences.kt — DataStore persistence
      model/                 # Shared data models (StudyModels.kt, Tractate.kt, Bookmark.kt)
      ui/                    # Composable screens + theme/
      viewmodel/             # ViewModels
    res/                     # XML resources, colors, themes
```

## iOS Key Files

| File | Purpose |
|------|---------|
| `ContentView.swift` | Main screen: tractate/daf pickers, daf page view, audio controls |
| `StudyModeView.swift` | Study mode tab UI (Facts / Summary / Quiz / Resources) |
| `SettingsView.swift` | Settings sheet |
| `StudyModels.swift` | All enums: `QuizMode`, `QuizSource`, `SourceDisplayMode`, `StudyMode` |
| `StudySessionManager.swift` | Orchestrates Claude API calls for study sessions |
| `ClaudeClient.swift` | Anthropic API wrapper |
| `SefariaClient.swift` | Fetches daf text from Sefaria |
| `SplashView.swift` | Splash screen; defines `SplashView.background` (app blue `#1B3A8A`) |
| `AnyDafApp.swift` | App entry point |
| `BookmarkManager.swift` | Bookmark persistence |
| `AudioPlayer.swift` | AVFoundation audio playback |
| `FeedManager.swift` | RSS/podcast feed (audio episode index) |
| `TalmudPageManager.swift` | Daf image assets |

## Android Key Files

| File | Purpose |
|------|---------|
| `MainActivity.kt` | Entry point; creates ViewModels, applies `AnyDafTheme` |
| `ui/ContentScreen.kt` | Main screen composable |
| `ui/StudyModeScreen.kt` | Study mode screen |
| `ui/SettingsScreen.kt` | Settings screen |
| `ui/NavGraph.kt` | Navigation graph |
| `ui/theme/Theme.kt` | `AnyDafTheme` composable; `LightColors`, `DarkColors`, `WhiteColors` |
| `ui/theme/Color.kt` | Color constants (`AppBlue`, `Surface`, etc.) |
| `viewmodel/ContentViewModel.kt` | Main ViewModel; owns tractate/daf selection, quiz prefs, useWhiteBackground |
| `viewmodel/StudySessionViewModel.kt` | Study session state |
| `viewmodel/AudioViewModel.kt` | Audio playback state |
| `data/prefs/AppPreferences.kt` | DataStore; all persisted preferences |
| `model/StudyModels.kt` | Enums mirroring iOS: `QuizMode`, `QuizSource`, `SourceDisplayMode`, `StudyMode` |

## Settings / Preferences

All settings are persisted and must be added in four places when changed:

**iOS:** `@AppStorage` key in both `SettingsView.swift` and wherever it's consumed (usually `ContentView.swift`).

**Android:** `AppPreferences.kt` (DataStore key + Flow + save function) → `ContentViewModel.kt` (StateFlow + init load + setter) → `SettingsScreen.kt` (UI) → wherever consumed.

### Current settings

| Setting | iOS default | Android default | Key |
|---------|-------------|-----------------|-----|
| Quiz mode | `.multipleChoice` | `MULTIPLE_CHOICE` | `quizMode` |
| Quiz source | `.dafText` | `DAF_TEXT` | `quizSource` |
| Source display mode | `.toggle` | `TOGGLE` | `sourceDisplayMode` |
| White background | `false` | `false` | `useWhiteBackground` |

## Theming

**iOS:** `SplashView.background` is the app blue (`Color(red:0.106, green:0.227, blue:0.541)`). `ContentView` uses `appBg`/`appFg` computed properties that switch between blue and white based on `useWhiteBackground`.

**Android:** `AnyDafTheme(useWhiteBackground:)` in `Theme.kt` selects between `LightColors` (blue primary, parchment surface), `DarkColors`, and `WhiteColors` (neutral grey primary, white surface).

## Models

```swift
// iOS (StudyModels.swift)
enum QuizMode:   multipleChoice | flashcard | fillInBlank | shortAnswer
enum QuizSource: summary | dafText
enum SourceDisplayMode: toggle | alwaysShow | alwaysHide
enum StudyMode:  facts | summary | quiz | resources
```

Android enums in `model/StudyModels.kt` mirror these exactly (SCREAMING_SNAKE_CASE).

## Study Session Flow

1. User taps Study → `StudySessionManager` (iOS) / `StudySessionViewModel` (Android) starts a session
2. Fetches daf text via `SefariaClient`
3. Sends text + prompt to Claude API via `ClaudeClient`
4. Returns structured content for Facts / Summary / Quiz tabs
5. `QuizSource` controls whether quiz questions are generated from the summary or the raw daf text

## Audio

- Episodes are indexed by tractate + daf number via RSS/podcast feed (`FeedManager`)
- `AudioPlayer` (iOS AVFoundation) / `AudioViewModel` (Android) handle playback state
- Feed is cached and refreshed lazily on app launch

## Bookmarks

- Identified by `(tractateIndex, daf, amud)`; optionally linked to a study section index
- `BookmarkManager` (iOS) / `BookmarkViewModel` (Android)

## YCT Library / Resources Tab

- `YCTLibraryClient` + `ResourcesManager` fetch articles from YCT Torah Library
- Resources are the 4th tab in study mode
- Filtered by match tier and English-only flag
- Disk-cached with 7-day expiry (`ResourcesDiskCache`)
