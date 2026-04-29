# AnyDaf — Project Guide

AnyDaf is a Talmud study app with parallel iOS (Swift/SwiftUI) and Android (Kotlin/Compose) codebases that must be kept in sync for every feature.

> **Maintenance note for Claude:** After any session that changes codebase architecture, update the relevant section(s) of this file before finishing. Do not wait to be asked.

## How to Navigate This Codebase

**Before reading any file, consult the Key Files tables below.** Most bugs and features touch exactly one file listed there. Go directly to that file — do not explore the codebase broadly first.

1. **Identify the right file from the tables.** The user's description (e.g. "nav buttons in Study mode", "translation toggle", "DataStore preference") should map to a specific row.
2. **Read only that file** (or the two files involved if the fix spans iOS + Android).
3. **Only search broadly** (Grep/Glob/Explore agent) when the right file genuinely isn't clear from the tables or the user's description — and even then, ask the user which file is involved before doing a full codebase scan.
4. **Targeted Grep is fine** inside a known file to jump to the right line quickly.

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
| `ContentView.swift` | Main screen: all layout (iPad + iPhone), pickers, daf page view, audio controls |
| `ZoomableAsyncImage.swift` | Pinch-to-zoom + pan + swipe-to-advance image view used inside DafPageView |
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

### Android Tablet Layout (ContentScreen.kt)

`collapsedSide` ("NONE" | "LEFT" | "RIGHT") is hoisted **before** `Scaffold` so the `TopAppBar` title lambda can read it.

Picker placement mirrors iOS:

| State | Pickers location |
|-------|-----------------|
| Split screen (`collapsedSide != "RIGHT"`) | `CompactTabletPickers` in outlined border box at top of left column |
| Right panel collapsed (`collapsedSide == "RIGHT"`) | `CompactTabletPickers` in `TopAppBar` title slot |
| Phone | `CompactTabletPickers` in outlined border box at top of phone column |

`CompactTabletPickers` (private composable in `ContentScreen.kt`) uses `OutlinedButton` + `DropdownMenu` for tractate/daf and `FilterChip` A/B for amud. `TabletPickerRow` (wheel-picker card style) is dead code — kept in the file but no longer called.

---

## iPad Layout Architecture (ContentView.swift)

This is the most complex part of the codebase. Read this before touching any iPad layout code.

### Top-level structure

`body` → `NavigationStack` → `ZStack` containing:
- A zero-height `GeometryReader` that captures `safeAreaInsets.top` into `@State var navBarSafeArea` **before** the safe area is ignored. This is the only reliable way to know the nav bar height from inside a view that uses `.ignoresSafeArea`.
- `iPadLayout` with `.ignoresSafeArea(.all, edges: .top)` — this makes the daf image extend behind the navigation bar.

The nav bar uses `.toolbarBackground(.ultraThinMaterial)` on iPad so the daf image blurs through behind the toolbar items.

### Split-panel state

`@AppStorage("iPadCollapsedSide") var collapsedSide: String` — `"none"` | `"left"` | `"right"`. Persisted.
`@State var splitFraction: CGFloat` — fraction of width given to the left column (default 0.5).
`@GestureState var splitDragDelta` — live drag offset; combined with `splitFraction` on end.

Collapsing happens by dragging past 20%/80% or a fast flick (≥60pt movement + predicted end past 15%/85%).

### Left column — VStack + inner ZStack

```
VStack(spacing: 0) {
    // visible only in split mode (collapsedSide != "right")
    compactPickers               // pill-bordered menu-style dropdowns
    ZStack(alignment: .bottom) {
        dafOnlyView              // fills maxHeight: .infinity
        bottomControls           // 120pt pill with appBg.opacity(0.92) background
    }
}
.frame(width: leftWidth)
.clipped()
```

- `dafOnlyView` → `DafPageView` → `ZoomableAsyncImage` (pinch/pan/swipe). Image uses `.aspectRatio(contentMode: .fit)` so it centers in the frame.
- The left/right navigation chevrons are also overlaid inside `DafPageView`.
- Image fills `maxHeight: .infinity` — no fixed height cap.

### Picker placement rules

| State | Tractate/Daf pickers location |
|-------|-------------------------------|
| Split screen (`collapsedSide != "right"`) | `compactPickers` pill at top of left column VStack |
| Right panel collapsed (`collapsedSide == "right"`) | `compactPickers` in toolbar `.principal` slot |
| iPhone | `pickerRow` HStack: pill (`compactPickers`) + daf/shiur toggle (if `shiurRewrite != nil`) + study icon (if audio playing) |

`compactPickers` is the single source of truth for picker UI on all form factors — `.menu` style for tractate/daf, `.segmented` for amud. All `onChange` handlers live inside `compactPickers`. `pickerRow` wraps `compactPickers` in a pill border and places the daf/shiur toggle and study icon inline to the right. The toolbar `.principal` slot shows `compactPickers` directly (no pill border).

**iPhone `pickerRow` overflow:** When all three items are visible simultaneously (long tractate name + high daf + daf/shiur toggle + study icon), the row overflows. Font must stay at `.footnote` and HStack spacing at 8pt to keep total width under 390pt. Do not increase font or spacing without testing the worst-case combination (e.g. Bava Batra 157 + Shiur available + audio playing).

**Do not restore `onChange(of: shiurClient.shiurRewrite)` that resets `showShiurText = false`.** It was removed intentionally — `shiurRewrite` briefly goes `nil` during loading when a new daf is selected, which was resetting the toggle to Daf mode even when the user wanted to stay in Shiur mode.

### Right column

Simple `VStack` with `navBarSafeArea + portraitTopPad` top spacer (to clear the transparent nav bar), then the Shiur/Study segmented picker, then the content panel.

### onChange responsibilities

- `pickerRow` / toolbar pickers: reset `selectedDaf`/`imageDaf`/`imageSide`/`selectedSide` on tractate change; update `imageDaf`/`imageSide`/`selectedSide` on daf/amud change.
- Body-level `onChange(of: selectedTractateIndex/selectedDaf)`: reload shiur segments and restart study session (guarded by `audioPlayer.isStopped`).
- Both fire independently — no conflict.

---

## iOS Picker Gotchas

### `@AppStorage` + Picker snap-back bug

**Never use `@AppStorage` directly as a `Picker` selection binding.** Writing to UserDefaults triggers a SwiftUI re-render that fights UIKit mid-selection — the user sees the list items "fly by" and then the picker snaps back to the previous value.

**Fix (implemented):** `selectedTractateIndex`, `selectedDaf`, and `selectedSide` are `@State` vars initialized directly from `UserDefaults.standard` at declaration (avoids first-render flash), backed by separate `@AppStorage` vars (`storedTractateIndex`, `storedDaf`, `storedSide`) used only for writing. Saves happen in the `onChange` handlers inside `compactPickers`, and also at explicit mutation sites (bookmark navigation, Daf Yomi sync). Pattern:

```swift
@AppStorage("lastDaf") private var storedDaf: Double = 2.0
@State private var selectedDaf: Double = {
    let v = UserDefaults.standard.double(forKey: "lastDaf"); return v > 0 ? v : 2.0
}()
// In onChange: storedDaf = newVal
```

### `.pickerStyle(.menu)` ignores SwiftUI `.font()` and size modifiers

The `.menu` picker style renders as a UIKit `UIButton` + `UIMenu`. SwiftUI's `.font()`, `.controlSize()`, and `.frame(height:)` modifiers are **ignored** for the UIKit button container — they apply to the SwiftUI wrapper but not the UIKit view inside. The custom `label:` closure Text font is rendered by SwiftUI so `.font(.caption)` there does affect the text face, but UIKit still controls button padding and minimum height (~34pt). There is no clean SwiftUI-only way to reduce the menu picker button height. Accepted current behavior: tractate/daf labels use `.font(.caption)`.

### Suppressing the system chevron on `.menu` pickers

`.menuIndicator(.hidden)` suppresses the UIKit-injected chevron. Removing the `Image(systemName: "chevron.up.chevron.down")` from the label closure alone does **not** work — the system adds its own chevron regardless of label content.

### Daf picker minimum width

The daf picker label (`"2"`, `"98"`, etc.) must have `.frame(minWidth: 30)` on the **picker itself** (not on the label's `Text`) and `.lineLimit(1)` on the label `Text`. The minWidth on the Text inside a UIKit-backed picker does not propagate to the button's layout frame.

### Picker scroll-to-selected

`Picker` with a custom `label:` closure (instead of a title string) + `.pickerStyle(.menu)` scrolls the popup to the currently selected item. **Do not replace with `Menu` view** — `UIMenu` always opens at the top of the list, which is unusable for tractates/dafs deep in the list.

### Replacing segmented `Picker` with custom SwiftUI buttons

UIKit-backed segmented controls (`.pickerStyle(.segmented)`) ignore `.frame(height:)`, `.font()`, and `.controlSize()` for sizing purposes. When height or font control is needed, replace with two `Button`s in an `HStack(spacing: 0)` sharing the same pill background as `compactPickers`. The active segment gets a filled inner `RoundedRectangle`. Use `.buttonStyle(.plain)` to suppress default button tap styling. This is how the Daf/Shiur toggle is implemented.

### `pickerRow` layout priority and overflow

`pickerRow` is an `HStack` containing: compactPickers pill, daf/shiur toggle (conditional), study icon (conditional). When multiple elements are visible, SwiftUI may compress the pill:

- Apply `.layoutPriority(1)` to the compactPickers pill so it is sized first.
- Keep `compactPickers` internal `HStack(spacing: 4)` (not 8) to save horizontal room.
- Keep daf/shiur button `.padding(.horizontal, 6)` (not 10) to save horizontal room.
- Study icon in `pickerRow` is 32pt. Do not increase — the row must fit Menachot 98 + daf/shiur + study icon on a 390pt screen.

---

## Split-Panel State Persistence

**iOS:** `collapsedSide` and `splitFraction` are persisted via `@AppStorage("iPadCollapsedSide")` (String) and `@AppStorage("iPadSplitFraction")` (Double). CGFloat casts applied in drag gesture arithmetic.

**Android:** `collapsedSide` and `leftWidthPx` are persisted via `TABLET_COLLAPSED_SIDE` (String) and `TABLET_SPLIT_DP` (Double) in AppPreferences → ContentViewModel → ContentScreen. State is hoisted before `Scaffold`. A `LaunchedEffect(tabletCollapsedSide, tabletSplitDp)` restores persisted state once the ViewModel loads (uses sentinel values `""` and `-1.0` to distinguish "not yet loaded" from defaults). Saves happen only in gesture `onDragEnd` and expand clickable handlers to avoid a race condition on first composition.

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
- On iPad, the audio controls float as a pill overlay at the bottom of the daf image (`appBg.opacity(0.92)` background, `RoundedRectangle(cornerRadius: 16)`)

## Bookmarks

- Identified by `(tractateIndex, daf, amud)`; optionally linked to a study section index
- `BookmarkManager` (iOS) / `BookmarkViewModel` (Android)

---

## Debugging Guidance

**Always ask the user to run with the debugger attached** when investigating a crash or any hard-to-reproduce bug. The Xcode debugger gives the exact exception type, message, call stack, and local variable values at the crash site — far faster than inferring from symptoms. Just say: "Can you run this from Xcode with the debugger on and share the error message?"

---

## Known Pitfalls

### NSNull in Supabase JSON responses (ShiurClient)

When a column exists in a Supabase row but its value is SQL `NULL`, the JSON response includes `"column": null`. In Swift, `JSONSerialization.jsonObject` represents JSON `null` as `NSNull()`, which is a non-nil `Any`. An `if let x = dict["column"]` binding does **not** filter `NSNull` — it succeeds, binding `x` to the `NSNull` instance.

Passing `NSNull` to `JSONSerialization.data(withJSONObject:)` throws an `NSInvalidArgumentException` (Objective-C exception). Swift's `try?` does **not** catch ObjC exceptions — the app crashes.

**Fix:** always guard against `NSNull` before passing dictionary values to `JSONSerialization`:
```swift
if let segJSON = first["segmentation"], !(segJSON is NSNull),
   let segData = try? JSONSerialization.data(withJSONObject: segJSON) { ... }
```

This was the root cause of the Hullin 99 crash. Any daf whose `segmentation` column is `null` (e.g. the processor ran rewrite/final passes but not segmentation) would crash the app. Fixed in `ShiurClient.swift` line 116.

### Crash-loop guard (AnyDafApp)

`@AppStorage`-persisted state (e.g. `lastDaf`, `iPadRightPanel`) survives app termination. If the app crashes on a specific daf every launch, it re-opens on the same daf and crashes again — an unrecoverable loop requiring reinstall.

**Fix implemented in `AnyDafApp.init()`:** a `launchInProgress` boolean in UserDefaults acts as a sentinel. It is set to `true` at init and cleared to `false` when the scene reaches `.active`. If at init it is already `true`, the previous launch crashed → `lastDaf` is reset to `2.0` and `iPadRightPanel` is cleared, so the app opens on a safe default.

### ShiurTextView: parse off the main thread (iOS + Android)

The shiur rewrite text for some dafs is very large. Parsing it synchronously on the main thread (SwiftUI body / Compose composition thread) can block long enough to trigger the iOS watchdog (~8 s) or Android ANR (~5 s).

**iOS fix:** `ShiurTextView` uses `.task(id: rewriteText)` + `Task.detached` to parse on a background thread; results are stored in `@State private var parsedBlocks`.

**Android fix:** `ShiurTextView.kt` uses `produceState` with `withContext(Dispatchers.Default)` instead of `remember { parseShiurBlocks(...) }`.

## YCT Library / Resources Tab

- `YCTLibraryClient` + `ResourcesManager` fetch articles from YCT Torah Library
- Resources are the 4th tab in study mode
- Filtered by match tier and English-only flag
- Disk-cached with 7-day expiry (`ResourcesDiskCache`)

---

## Daf Page Image Quality (Android)

### Current approach
`PdfDafPageView.kt` uses `SubcomposeAsyncImage` (Coil) with `Size.ORIGINAL` + `FilterQuality.High`. The source images are Google Drive JPEG thumbnails at `sz=w3000` (`TalmudPageManager.kt` builds the URL as `https://drive.google.com/thumbnail?id=$fileId&sz=w3000`).

**Known limitation:** At full-page zoom-out, the GPU must downscale 3000px → ~400px using bilinear filtering, which produces blurry text on physical devices. On the emulator this is not visible (software renderer has better filtering). `FilterQuality.High` only enables bicubic on Android 12+; on earlier versions it falls back to bilinear.

### Approaches tried and rejected

| Approach | Result |
|----------|--------|
| `BoxWithConstraints` to compute a target size | Made it worse — `maxHeight` is `Dp.Infinity` inside a `weight(1f)` layout, causing Coil to receive an invalid huge dimension |
| `LocalConfiguration.current.screenWidthDp × density` as Coil target | Also worse — the user preferred `Size.ORIGINAL` |
| `SubsamplingScaleImageView` (SSIV) with OkHttp local cache | No visible improvement — SSIV tiling benefit is for images 10 000 px+; for a 3000 px JPEG it still subsamples the same way. Reverted. |
| PDF rendering via `PdfRenderer` (local asset test) | Marginally better but not worth the infrastructure cost (all pages would need to be stored as PDFs). Reverted. |

**Do not re-attempt BoxWithConstraints or LocalConfiguration sizing** — both were tried and reverted.

### Planned future improvement: PDF rendering
The daf page source files are available as PDFs. Android's built-in `PdfRenderer` (API 21+) renders a PDF page to a `Bitmap` at any resolution, eliminating GPU downscaling entirely. Plan when ready:

1. Store PDFs at a CDN/public URL (not Google Drive thumbnail endpoint — that only serves images)
2. Add `pages_pdf.json` alongside `pages.json` mapping tractate/daf to PDF URLs
3. Download PDF to a temp file; use `PdfRenderer` to render page 0 to a `Bitmap` at `screenWidthPx × screenWidthPx * 2`
4. On pinch-zoom, re-render at `scale × screenWidthPx` for crisp text at any zoom level
5. The existing `DafPageView` composable structure fits cleanly — swap `SubcomposeAsyncImage` for an `Image` drawing the rendered bitmap

**Note:** PDF rendering was tried on iOS and was worse there (PDFKit does not give the same low-level bitmap control). Do not attempt the PDF approach on iOS.

---

## App Blue Color

The app background blue is `#1B3A8A` on both platforms. This was deliberately chosen over the YCT brand blues after testing:
- `#0606BA` (YCT brand blue, RGB 6/6/186) — too bright/saturated on iPhone; also rendered incorrectly (dull/matte) on the tested Android device
- `#0059EA` (YCT alternate blue, RGB 0/89/234) — used for the study mode tab indicator only

**Do not change `AppBlue` / `SplashView.background` to a YCT brand blue** without testing on both physical iOS and Android devices first.

Color locations:
- Android: `ui/theme/Color.kt` (`AppBlue`); also referenced in `ShiurTextView.kt` (local copy)
- iOS: `SplashView.swift` (`SplashView.background`); flows to `ContentView.appBg`, `StudyModeView.studyBg`, `ShiurTextView.appBlue`
- Also hardcoded in: `PDFDafPageView.swift` (UIColor), `ArticleReaderView.swift` (SwiftUI Color + HTML hex), `Launch Screen.storyboard`

---

## Mafteach haDaf (מַפְתֵּחַ הַדַּף) — Talmudic Knowledge Base

*Mafteach haDaf* ("Key of the Daf") is a structured knowledge base and browsable topical index of the Babylonian Talmud, built from 2,350 processed shiur (lecture) transcripts. Name deliberately evokes AnyDaf while distinguishing from the existing *HaMafteach* Talmudic index. The AI basis is intentionally not emphasized — this is a scholarly reference tool where accuracy and precision are the value proposition. Each processed daf has a lecture rewrite and Talmudic source text stored in Supabase.

**The goal**: A web app where a user can:
- Browse by topic (like a traditional Talmud encyclopedia)
- Search by any term — English, Hebrew, transliteration
- Ask natural language questions ("What does the Talmud say about demons harming people?")
- Get answers grounded only in the stored texts — no hallucination, precise tractate/daf/timestamp sourcing

### Why No Hallucination

At query time, the LLM reads only stored verbatim texts — no external knowledge about the Talmud is used. Tractate/daf identification comes from file metadata, not LLM extraction. The system prompt explicitly forbids drawing on training knowledge. If a topic doesn't appear in the corpus, the system says so.

### Three-Layer Architecture

**Layer 1 — Data (Supabase `shiur_segments` table)**

Each daf's rewrite is already divided into micro-segments with timestamps (from the segmentation JSON). Each micro-segment becomes one row:

| Field | Content |
|---|---|
| `tractate`, `daf`, `timestamp` | Precise location |
| `segment_title` | Name of this segment |
| `lecture_text` | Rabbi's explanation (from `rewrite`) |
| `talmudic_text` | Talmudic source text being discussed (from `final` blockquotes) |
| `taxonomy_ids` | Which taxonomy entries this segment relates to (array) |
| `embedding` | Vector for semantic search |

~2,350 dafs × ~20 micro-segments = ~47,000 rows total.

**Why `rewrite` AND `final`**: The lecture (`rewrite`) gives conceptual explanation — unique scholarly value, no traditional index does this. The `final` blockquotes give the actual Talmudic text. Both are stored; both are searched. `source` field distinguishes them at query time.

**Layer 2 — Taxonomy (browsable index)**

1,222-entry hierarchical taxonomy (see `topic_analysis/taxonomy/seed_taxonomy.json`). Provides traditional index browsing: SHABBAT AND HOLIDAYS → Muktzeh → all passages. Each entry accumulates all segments tagged to it via `taxonomy_ids`.

User sees: `name` and `hebrew` fields only. `id` is internal database key — stable, snake_case, never shown to user.

**Layer 3 — Query (LLM synthesis)**

At query time, retrieve relevant segments (by taxonomy, semantic search, or both) and pass verbatim texts to Claude Sonnet. Claude synthesizes, summarizes, compares — but only from what's in front of it. Citations come from metadata, not Claude's memory.

### Web App Navigation — Core UX Principle

**Search is the primary entry point. Browse is secondary.** A user who knows what they want types it directly — "sheidim," "שדים," "demons," "Rabbi Chanina ben Dosa" — and lands on the entry without navigating any hierarchy. The category/parent structure is for exploratory browsing only; it should never be *required* to find a known topic.

Three navigation modes:

| Mode | Use case |
|---|---|
| **Search box** (primary) | Type any term in any language → immediate results |
| **Browse by category** | Exploratory — "what's indexed under Civil Law?" |
| **A-Z index** | Traditional book-index scanning, flat alphabetical view |

For **Rabbinic Authorities** specifically: the taxonomy groups them by period and geography (for users who want to browse that way), but the web app must also offer a flat A-Z list of all authorities — many users know a sage's name without knowing their generation or whether they were Palestinian or Babylonian.

The A-Z view is useful across the whole index, not just authorities.

### Search Design

Each taxonomy entry has an `aliases` array covering all reasonable search formulations:
```json
{
  "id": "biur_chametz",
  "name": "Biur Chametz (Removal of Chametz)",
  "hebrew": "בִּיעוּר חָמֵץ",
  "aliases": ["Biur Chametz", "ביעור חמץ", "Burning Chametz", "Destroying Chametz", "Chametz Removal"]
}
```
Search checks `name + id + hebrew + aliases` simultaneously. No separate "see also" entries needed — aliases handle multilingual and parallel-term lookup. "Destroying chametz," "biur chametz," and "ביעור חמץ" all reach the same entry.

**Embedding/semantic search**: Each segment and each taxonomy entry gets an embedding vector. Natural language queries ("why burn chametz before Pesach?") match by meaning, not keywords, so they find the right passages even without knowing the exact term.

**Taxonomy categories** are UI navigation folders only — users don't search at this level. Category assignments can be changed any time without reprocessing. Entry `id`s are what matter for the database; finalize those before re-tagging.

### Phases of Work

| Phase | Description | Status |
|---|---|---|
| 1a | Seed taxonomy built (1,222 entries, 4 Claude Sonnet calls) | ✅ Done |
| 1b | User reviews `seed_taxonomy.xlsx` — names, Hebrew, parent structure, missing entries, duplicates | 🔄 In progress |
| 1c | Generate aliases for all entries (batch Claude job) | Not started |
| 1d | Map 28,982 canonical terms → seed taxonomy entries; propose subcategory enrichment (e.g., Muktzeh → 10-20 subcategories grounded in what actually appears in the corpus) | Not started |
| 1e | User reviews and approves enriched taxonomy with subcategories | Not started |
| 2 | Build `shiur_segments` table — parse `rewrite` + `final` from Supabase into micro-segment rows (no LLM needed, ~free) | Not started |
| 3 | Re-tagging pass — Claude Sonnet Batch API reads each daf's segments + full taxonomy, assigns `taxonomy_ids` to each segment (~$300-350 total) | Not started |
| 4 | Add pgvector embeddings to each segment row (~$1 total) | Not started |
| 5 | Build web app — taxonomy browser, search, Q&A interface, audio deep-links | Not started |

### Taxonomy Hierarchy

**Four levels total:**
```
Category          "SHABBAT AND HOLIDAYS"                    — UI folder only, no passages tagged
  Main entry      "Muktzeh"                                 — real index entry (general discussions)
    Sub-entry     "Muktzeh Machmat Mi'us"                   — real index entry (specific category)
      Sub-sub     "Muktzeh Machmat Mi'us vs. Chisaron Kis"  — real index entry (recognized sub-question)
```

Maximum depth is sub-sub-entry (3 content levels below category). Anything deeper signals the entry should be reorganized rather than nested further.

**Criterion for creating a deeper level**: Whether the sub-topic has **independent standing in halakhic or Talmudic discourse** — i.e., Chazal, the Rishonim, or standard halakhic literature treat it as a recognized distinct question with its own name or category status.

- ✅ "Muktzeh Machmat Mi'us vs. Machmat Chisaron Kis" — recognized distinct halakhic question → sub-sub-entry even if it appears only twice
- ✅ "Muktzeh — differences between Shabbat and Yom Tov" — recognized distinct question → sub-sub-entry
- ❌ "Muktzeh on a rainy Shabbat" — incidental angle, not a recognized distinct category → stays as a passage under the parent entry even if it appears five times

**Volume is a signal, not the trigger.** Frequency of occurrence suggests a topic may warrant its own entry, but the real test is recognized independent standing in the literature. Interest/significance overrides (promoting a rare but important distinction) are a human judgment call made during review — not automated.

**In the re-tagging prompt**, Claude is told: *"Create a sub-sub-entry only if this is a recognized distinct concept in Talmudic or halakhic literature — one that has its own name or is discussed as a separate category by the Talmud or Rishonim."*

### Key Decisions (with reasoning)

- **No pre-computed summaries or aspect tags**: Store raw texts; Claude reasons over them at query time. Pre-computing "aspects" requires predicting all future query dimensions — impossible. A passage about Ashmodai and King Solomon gets found by reading the text, not by pre-tagging it.
- **Claude Sonnet for re-tagging, not Haiku**: Accuracy over cost. Conceptual connections in Talmudic reasoning require genuine understanding. Cost (~$300) is acceptable.
- **Subcategories come from the corpus**: The 28,982 canonical terms already extracted from the lectures show what subcategories actually appear (e.g., all the muktzeh variants). Don't enumerate subcategories from training knowledge — let the corpus tell you.
- **`rewrite` not `final` as primary lecture source**: `rewrite` is the rabbi's explanation. `final` adds Talmudic text blockquotes. Both are stored, but the lecture text is the unique value no traditional index provides.

### Scripts in `daf-processor/`

All scripts: `load_dotenv(Path(__file__).parent / ".env", override=True)` — required, relative path without `override=True` fails.

| Script | Purpose |
|---|---|
| `extract_topics.py` | Extracts `topical_tags` from `shiur_content.segmentation` → `topic_analysis/topics_raw.json` (51,671 raw terms) |
| `normalize_topics.py` | Batch API: normalizes raw terms → canonical forms. **Config: `BATCH_SIZE=100, MAX_TOKENS=8192`** (Hebrew tokenizes ~2x heavier than ASCII; original 150/4096 caused all 345 chunks to truncate) |
| `consolidate_topics.py` | Batch API: deduplicates 28,982 canonical forms by alphabetical grouping |
| `build_taxonomy.py` | Multi-segment Claude Sonnet calls → `seed_taxonomy.json`. Supports `--segment N`, `--merge`, `--save-partial` |

### Taxonomy Files (`topic_analysis/taxonomy/`)

| File | Content |
|---|---|
| `webshas_entries_raw.txt` | ~1,400 WebShas entries (primary source, A-Z) |
| `segment_1-4.json` | Raw segment outputs (segments 1+2 were truncated and salvaged) |
| `seed_taxonomy.json` | Merged final taxonomy (1,222 entries, 30 categories) |
| `seed_taxonomy.xlsx` | Excel version for human review — color-coded by category, auto-filter, frozen header |

### Supabase Schema

Existing table `shiur_content`: `tractate`, `daf` (float: 5.0=5a, 5.5=5b), `segmentation` (jsonb), `rewrite` (text), `final` (text)

`segmentation` structure:
```json
{
  "topical_tags": [{"term": "string", "timestamps": ["00:00"]}],
  "macro_segments": [{"title": "", "timestamp": "", "micro_segments": [{"title": "", "timestamp": ""}]}]
}
```

Planned new table `shiur_segments`:
```sql
CREATE TABLE shiur_segments (
  id            serial primary key,
  tractate      text not null,
  daf           text not null,
  timestamp     text,
  segment_title text,
  lecture_text  text,
  talmudic_text text,
  taxonomy_ids  text[],
  embedding     vector(1536),
  created_at    timestamptz default now()
);
CREATE INDEX ON shiur_segments (tractate, daf);
CREATE INDEX ON shiur_segments USING gin (taxonomy_ids);
```

Planned updated taxonomy table:
```sql
CREATE TABLE taxonomy (
  id          text primary key,
  name        text not null,
  hebrew      text,
  parent_id   text references taxonomy(id),
  category    text,
  aliases     text[],
  sources     text[]
);
CREATE INDEX ON taxonomy USING gin (aliases);
```

### Batch API Critical Config

`BATCH_SIZE=100, MAX_TOKENS=8192` for all haiku batch jobs. After truncation, delete `.normalize_batch_state.json` to force fresh submission. Always check `stop_reason == "max_tokens"` — truncated JSON causes silent failures downstream.
