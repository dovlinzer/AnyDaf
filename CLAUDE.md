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

## AskAnyDaf — Talmudic Knowledge Base

**Public name: AskAnyDaf.** Internal/subtitle: *Mafteach haDaf* (מַפְתֵּחַ הַדַּף, "Key of the Daf"). The AI basis is intentionally not foregrounded — this is a scholarly reference tool where accuracy and citation precision are the value proposition.

**The goal**: A public-facing web app where a user can ask nuanced natural-language questions about the Talmud and receive grounded, cited answers — drawn only from processed shiur transcripts, never from the LLM's training knowledge.

Example queries the system must handle well:
- "Where does the Talmud talk about sheidim and give them names?"
- "Where is sheidim discussed in ways that aren't simply about their danger?"
- "Where is migo used in a non-monetary context?"
- "Please provide the full passages in the original Aramaic and/or English translation."

### Why No Hallucination

At query time, Claude reads only verbatim stored texts — no external Talmud knowledge is used. Tractate/daf/segment identification comes from database metadata, not LLM extraction. The system prompt explicitly forbids drawing on training knowledge. If a topic doesn't appear in the corpus, the system says so.

### Strategy

**The knowledge-base query feature is the primary goal. The taxonomy/index is secondary.**

A user typing a nuanced question gets a synthesized answer with precise citations. Taxonomy browsing (browse by topic category) is a future enhancement — useful but not the core value. This pivot means the expensive taxonomy re-tagging pass (~$300) is deferred; the knowledge-base can launch with embeddings alone.

### How Queries Work

**Stage 1 — Retrieval (embeddings)**: The user's question is embedded as a vector and matched semantically against all segments. Finds conceptually relevant content even when exact words differ — "sheidim given names" finds segments discussing named demons without requiring the word "name."

**Stage 2 — Synthesis (Claude)**: Retrieved segments are passed verbatim to Claude along with the user's exact question. Claude applies the specific nuanced filter to what it's reading and returns organized results with citations. It cannot invent a reference that doesn't appear in the passed text.

**The nuance lives in Stage 2, not Stage 1.** This is why complex, interpretive questions work — "non-threatening sheidim," "migo in non-monetary contexts" — Claude filters from real source material.

Users can also request full passages in Hebrew/Aramaic and English translation; these are stored from `03_final.md` and Sefaria files.

### Data

**Source**: 99,436 segments across 40 tractates, previously stored in Supabase `shiur_sections` table. Downloaded as `daf-processor/shiur_sections_rows.csv` (freed from Supabase to save space). To be restored to Supabase with added fields.

**Output folders**: 2,363 daf folders under `daf-processor/output/`. Each contains:
- `03_final.md` — English commentary with Hebrew/Aramaic + English translation blockquotes embedded
- `sefaria.md`, `sefaria_prev.md`, `sefaria_next.md` — raw Sefaria passages

The `03_final.md` files are the source for both `talmudic_text` (extracted blockquotes) and `source_type` classification.

### source_type Field

Each segment is classified automatically by inspecting its corresponding section in `03_final.md`:

| Value | Meaning | Detection |
|---|---|---|
| `talmudic` | Segment directly explains a Gemara passage | Section contains `> **Hebrew/Aramaic:**` blockquote |
| `mishnah` | Segment explains a Mishnah | Section title contains "Mishnah" or blockquote cites a Mishnah |
| `shiur_discussion` | Shiur commentary — Rishonim, Acharonim, conceptual analysis without a direct Talmudic passage | No embedded blockquote |

At query time, `shiur_discussion` results are flagged in the UI (e.g., "Shiur analysis" label) so users know the content comes from the Rav's discussion rather than the Talmudic text itself.

### Supabase

**Infrastructure**: Upgrade existing AnyDaf Supabase project to Pro ($25/month, 8GB storage). New tables live alongside `shiur_content`, `episode_audio`, `app_config` — same URL and keys.

**Embeddings**: `text-embedding-3-small` at 512 dimensions (not 1536). Quality is nearly identical for this domain; storage is 2/3 smaller. Cost to embed all 99K segments: ~$2 total.

**`shiur_sections` table** (restoring and extending the old table):

```sql
CREATE TABLE shiur_sections (
  id                 serial primary key,
  tractate           text not null,
  daf                numeric(4,1) not null,
  segment_index      integer not null,
  parent_segment_index integer,
  title              text,
  timestamp_mm_ss    text,
  timestamp_secs     numeric,
  content            text,           -- lecture text (from shiur_sections_rows.csv)
  talmudic_text      text,           -- Hebrew/Aramaic + English translation (from 03_final.md blockquotes)
  source_type        text not null default 'talmudic',  -- 'talmudic' | 'mishnah' | 'shiur_discussion'
  embedding          vector(512),
  updated_at         timestamptz default now(),
  UNIQUE (tractate, daf, segment_index)
);
CREATE INDEX ON shiur_sections (tractate, daf);
CREATE INDEX ON shiur_sections USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

Existing table `shiur_content` (unchanged): `tractate`, `daf` (float), `segmentation` (jsonb), `rewrite` (text), `final` (text)

`segmentation` structure:
```json
{
  "topical_tags": [{"term": "string", "timestamps": ["00:00"]}],
  "macro_segments": [{"title": "", "timestamp": "", "micro_segments": [{"title": "", "timestamp": ""}]}]
}
```

### upload_to_supabase.py — `--sections` Flag

The segment upload logic is being re-integrated into `upload_to_supabase.py` with a `--sections` flag (off by default, so existing `--dir` / bulk runs are unaffected).

When `--sections` is passed:
1. Delete existing `shiur_sections` rows for the daf's `(tractate, daf)`
2. Load the daf's rows from the CSV (or re-parse from segmentation JSON if CSV not available)
3. Parse `03_final.md` for that daf — extract talmudic blockquotes per section, detect `source_type`
4. Call OpenAI `text-embedding-3-small` (512d) for each segment's `content`
5. Upsert all rows to `shiur_sections`

Usage:
```bash
python upload_to_supabase.py --sections                          # all dafs
python upload_to_supabase.py --dir output/berakhot_11 --sections # single daf
python upload_to_supabase.py --dry-run --sections                # preview
```

Requires `OPENAI_API_KEY` in `.env` when `--sections` is active.

### Phases of Work

| Phase | Description | Status |
|---|---|---|
| A1 | Add `--sections` flag to `upload_to_supabase.py` | 🔄 In progress |
| A2 | Bulk load: run `--sections` across all 2,363 output folders | Not started |
| A3 | Build AskAnyDaf query API (Next.js route: embed query → vector search → Claude synthesis) | Not started |
| A4 | Build AskAnyDaf web UI — search box, results with citations, full-passage toggle, source_type labels | Not started |
| B1 | Taxonomy: complete seed_taxonomy.xlsx review (was in progress) | Deferred |
| B2 | Taxonomy: generate aliases, map canonical terms, subcategory enrichment | Deferred |
| B3 | Re-tagging pass — assign taxonomy_ids to each segment (~$300, Batch API) | Deferred |
| B4 | Add taxonomy browse UI to AskAnyDaf | Deferred |

### Query API Design (Phase A3)

Next.js API route at `/api/ask`:
1. Embed user question via OpenAI `text-embedding-3-small`
2. pgvector cosine similarity search → top 40–60 segments
3. Build prompt: system instructions (no hallucination, cite only what's provided) + retrieved segments with metadata + user question
4. Stream Claude Sonnet response
5. Return: synthesized answer + list of source citations (tractate, daf, segment title, timestamp, source_type)

Users can request full passages (Hebrew/Aramaic + English) — these are returned from the `talmudic_text` field of matched segments.

### Scripts in `daf-processor/`

All scripts: `load_dotenv(Path(__file__).parent / ".env", override=True)` — required, relative path without `override=True` fails.

| Script | Purpose |
|---|---|
| `upload_to_supabase.py` | Uploads shiur_content rows + (with `--sections`) shiur_sections rows with embeddings |
| `extract_topics.py` | Extracts `topical_tags` from `shiur_content.segmentation` → `topic_analysis/topics_raw.json` (51,671 raw terms) |
| `normalize_topics.py` | Batch API: normalizes raw terms → canonical forms. **Config: `BATCH_SIZE=100, MAX_TOKENS=8192`** |
| `consolidate_topics.py` | Batch API: deduplicates 28,982 canonical forms by alphabetical grouping |
| `build_taxonomy.py` | Multi-segment Claude Sonnet calls → `seed_taxonomy.json`. Supports `--segment N`, `--merge`, `--save-partial` |

### Taxonomy Files (`topic_analysis/taxonomy/`)

| File | Content |
|---|---|
| `webshas_entries_raw.txt` | ~1,400 WebShas entries (primary source, A-Z) |
| `segment_1-4.json` | Raw segment outputs (segments 1+2 were truncated and salvaged) |
| `seed_taxonomy.json` | Merged final taxonomy (1,222 entries, 30 categories) |
| `seed_taxonomy.xlsx` | Excel version for human review — color-coded by category, auto-filter, frozen header |

### Taxonomy Design (for Phase B)

**Four levels total:**
```
Category          "SHABBAT AND HOLIDAYS"                    — UI folder only, no passages tagged
  Main entry      "Muktzeh"                                 — real index entry (general discussions)
    Sub-entry     "Muktzeh Machmat Mi'us"                   — real index entry (specific category)
      Sub-sub     "Muktzeh Machmat Mi'us vs. Chisaron Kis"  — real index entry (recognized sub-question)
```

**Criterion for creating a deeper level**: Whether the sub-topic has **independent standing in halakhic or Talmudic discourse** — recognized distinct question with its own name or category in the Rishonim.

**Key decisions**:
- No pre-computed summaries or aspect tags — store raw texts, Claude reasons at query time
- Claude Sonnet for re-tagging (not Haiku) — accuracy over cost (~$300 acceptable)
- Subcategories derived from the 28,982 canonical corpus terms, not from training knowledge
- Each taxonomy entry has an `aliases` array for multilingual search (Hebrew script, transliteration, English variants)

### Batch API Critical Config

`BATCH_SIZE=100, MAX_TOKENS=8192` for all haiku batch jobs. After truncation, delete `.normalize_batch_state.json` to force fresh submission. Always check `stop_reason == "max_tokens"` — truncated JSON causes silent failures downstream.

---

## AskYCTorah — YCT Torah Library Knowledge Base

**Public name: AskYCTorah.** A public-facing knowledge base covering R. Linzer's teshuvot, shiurim, articles, and source sheets, plus broader YCT Torah Library content. Hosted as a second tab alongside AskAnyDaf (same Vercel deployment), eventually at a subdomain of yctorah.org.

**The goal**: A smart librarian, not a synthesizer. The system finds and surfaces relevant documents with direct excerpts and links — it does not construct answers or extract conclusions. The user does the intellectual work; the system does the finding.

### Sources

| Source | Type | Access |
|---|---|---|
| library.yctorah.org | Articles, shiurim, dvar Torah | WordPress REST API (`/wp-json/wp/v2/posts`) |
| psak.yctorah.org | Teshuvot, psakim | WordPress REST API (existing integration in YCTLibraryClient) |
| Personal material | Source sheets, lectures, teshuvot by R. Linzer | PDF/Word upload workflow |

### Core Design Principle: The Author Pre-Designates What Stands Alone

Claude never extracts conclusions, paraphrases rulings, or selects "representative" quotes. The only content shown to users is:
1. The retrieved passage most semantically relevant to the query (surfaced by embedding search, not chosen by Claude)
2. An author-approved scope description
3. An author-designated standalone summary, if one exists (Tier 2 only)

This is not a limitation — it is the feature. Users are researchers and serious learners who need to engage with primary sources, not receive pre-digested conclusions.

### The No-Paraphrasing Rule

Even an exact match on a psak question does not trigger a summary. The response shows the document, its scope description, and a link — never Claude's reconstruction of the conclusion. Paraphrasing a halakhic ruling can lose a nuance that changes the psak. Any text shown to the user must be verbatim from the source.

### Three Response Tiers

**Tier 1 — Non-psak / conceptual content**
Show the retrieved passage (the embedding-matched chunk) as a direct excerpt, labeled as from [title]. Add the scope description and a link to the full piece. No Claude selection or summarizing — the retrieval system surfaces the relevant passage naturally.

Example query: *"Does R. Linzer have anything to say about Torah and capitalism?"*
Example response: Shows the shemita/capitalism passage that matched the query, with title and link.

**Tier 2 — Psak with author-designated standalone summary**
R. Linzer has explicitly written a self-contained bottom-line section (e.g., "Practical Ruling" or "Guidelines") that is meant to stand alone. The system displays that text verbatim, with a strong note to read the full article for nuance and context.

**Key**: Only R. Linzer designates a standalone summary — Claude never decides that a passage is safe to quote as a ruling. This is set at ingestion during editorial review.

**Tier 3 — Psak without a standalone summary**
Scope description + link only. No excerpting.

### Honest Gap Reporting

When no exact match exists, the system says so explicitly and shows what does exist:

> *Your question is about second-trimester abortion for reason Y. R. Linzer has not written specifically about this case. The closest relevant material is:*
> *1. [Teshuva title] — Teshuva (link). R. Linzer addresses first-trimester abortion for reason X, examining [sources].*
> *2. [Source sheet title] — Annotated source packet (link). [Scope description.]*

"R. Linzer has not written specifically about this" is always shown when there is no direct match. Users must not walk away thinking they have a psak they don't have.

### Document Schema

Each document in the database has:

```
title              — from WordPress or filename
url                — link to original (required; always shown)
document_type      — teshuva | shiur | source_sheet | article | dvar_torah
author             — R. Linzer or other YCT faculty
description        — scope/approach in 2-4 sentences; Claude draft → author approved
                     Never states or implies a conclusion
standalone_summary — verbatim author-written bottom-line (Tier 2 only; null otherwise)
reviewed           — bool: whether editorial pass has been completed
tags               — topics (from WordPress categories or manual)
embedding          — on the full text, for retrieval
```

Unreviewed documents appear in results as title + document_type + link only — no excerpting until reviewed.

### document_type Values

| Value | Meaning |
|---|---|
| `teshuva` | Reaches a halakhic conclusion |
| `shiur` | Educational lecture, may discuss multiple views |
| `source_sheet` | Primarily citations, exploratory, no conclusion |
| `article` | Published piece, may or may not be conclusory |
| `dvar_torah` | Weekly Torah thought |

**document_type must be set by a human at ingestion** — it cannot be reliably auto-detected. A source sheet discussing R. Moshe Feinstein alongside R. Linzer's commentary looks too similar to a teshuva to classify automatically.

### Editorial Workflow

1. Document enters ingestion pipeline (scraped from WordPress API or uploaded)
2. Claude generates drafts: scope description, detection of possible standalone summary section
3. R. Linzer (or research assistant) reviews via a simple approval interface:
   - Confirm document_type
   - Approve or edit scope description
   - For Tier 2 documents: paste in the standalone summary text
4. Document goes live with `reviewed = true`

Target: 2–5 minutes per document for review. Documents can be ingested immediately and sit unreviewed (showing title + type + link only) until the editorial pass catches up.

### Forward-Looking Practice

For future teshuvot: write an explicit **"Practical Ruling"** or **"Bottom Line"** section when a standalone quotable ruling is intended. This disciplines the writing and makes Tier 2 designation straightforward. The system rewards this discipline by displaying the ruling directly to users.

### Response Format

Claude's synthesis role is minimal:
- Determine whether the query is about psak or conceptual content
- Identify the closest match and flag if it is not an exact match
- Order results by relevance
- Frame results using the tier logic above

Claude does **not**:
- Summarize or paraphrase document content
- Select illustrative quotes (retrieval does this)
- Infer conclusions from source sheets or shiurim
- Blend content across documents into a synthesized answer

### Phases of Work

| Phase | Description | Status |
|---|---|---|
| 1 | Design finalized | ✅ Done |
| 2 | WordPress importer (library.yctorah.org + psak.yctorah.org) | Not started |
| 3 | PDF/Word importer for personal material | Not started |
| 4 | Chunking + embedding pipeline | Not started |
| 5 | Editorial review interface | Not started |
| 6 | Query API + response formatting | Not started |
| 7 | Web UI (second tab in AskAnyDaf Vercel deployment) | Not started |

Start with Phase 2 (WordPress content) since it's already accessible via API and represents the largest corpus. Personal material (Phase 3) requires upload infrastructure and is most valuable but most manual.
