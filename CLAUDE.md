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
  daf-processor/             # SRT → shiur processing pipeline (THE CORRECT DIRECTORY)
```

## Daf Processor (`AnyDaf/daf-processor/`)

**This is the canonical daf-processor.** Do NOT use `old-dp/` (a retired copy kept for reference only).

Key scripts:

| Script | Purpose |
|--------|---------|
| `main.py` | Entry point — processes SRT files through all passes |
| `pipeline.py` | Orchestrates passes 1 / 2 / 2.5 / 3 + amud B detection |
| `prompts.py` | All Claude prompt templates |
| `find_amud_b.py` | Detects amud B boundary; auto-called by pipeline after pass 3 |
| `upload_to_supabase.py` | Uploads `output/` dirs to Supabase `shiur_content` + optionally `shiur_sections` |

`pipeline.py` imports from `prompts.py` (not `prompts2.py`) and `find_amud_b.py`. **Never reference `prompts2.py` or `pipeline2.py`** — those files no longer exist.

Output dirs live in `daf-processor/output/<masechta>_<daf>/` with files:
- `01_segmentation.json` — macro/micro segments + amud_b fields (written by find_amud_b)
- `02_rewrite.md` — pass 2 essay
- `025_cleanup.md` — pass 2.5 cleaned essay (note: filename is `025_`, not `02.5_`)
- `03_final.md` — final essay with Sefaria blockquotes
- `sefaria.md` — cached Sefaria text for the full daf
- `sefaria_prev.md` — b-side of preceding daf (context for pass 3)
- `sefaria_next.md` — a-side of following daf (context for pass 3)

### Pipeline Passes (pipeline.py)

Passes run in sequence: 1 → 2 → 2.5 → 3 → amud B detection. Use `--passes <N>` to run a single pass; use `--resume` to skip passes whose output files already exist.

**Pass 1 — Segmentation** (Haiku): SRT timestamped text → `01_segmentation.json`
- Prompt: `segmentation_prompt()`. Accepts `--amud a|b` when a shiur covers only one amud.
- Post-processing `repair_segmentation()` runs automatically on every pass 1 output:
  1. Sorts micro-segments within each macro by timestamp
  2. Re-anchors each macro's timestamp to its first micro
  3. Sorts macros chronologically
  4. Splits non-contiguous macros (Claude sometimes groups thematically across time gaps) by inserting a `(continued)` segment at the correct chronological position — iterates until no overlaps remain
  5. Enforces 25-char `display_title` limit on all macro and micro segments
- Retries once if output JSON is invalid.

**Pass 2 — Rewrite** (Sonnet): raw SRT text + segmentation JSON → `02_rewrite.md`
- Prompt: `rewrite_prompt()`. Produces a written essay; inline Aramaic is translated to English.

**Pass 2.5 — Cleanup** (Sonnet): `02_rewrite.md` → `025_cleanup.md`
- Prompt: `cleanup_prompt()`. Preserves Aramaic direct quotes hidden in HTML comments; strips inline re-citations and other artifacts. This output feeds pass 3.

**Pass 3 — Source Insertion** (Haiku): `025_cleanup.md` + Sefaria text → `03_final.md`
- Prompt: `source_insertion_prompt()`. Inserts Sefaria Hebrew/Aramaic + English translation blockquotes after each `##` macro header where relevant. Strips the HTML comments from pass 2.5.
- Fetches (and caches) three Sefaria texts: current daf, b-side of preceding daf, a-side of following daf — all three are passed as context so the insertion model knows where the daf begins and ends.
- Skips gracefully if Sefaria text is unavailable.
- Uses `025_cleanup.md` if it exists; falls back to `02_rewrite.md`.

**Amud B Detection** (local, no API): runs after all passes via `find_amud_b.process_dir()`
- Reads `01_segmentation.json` and `sefaria.md`/`03_final.md` to locate the amud B boundary
- Writes `amud_b_segment_index`, `amud_b_timestamp`, `amud_b_micro_title` into `01_segmentation.json`
- Runs with `force=True` so it always re-detects (the segmentation may have been repaired)

### upload_to_supabase.py

Uploads to two Supabase tables. **Always uploads `shiur_content`; only uploads `shiur_sections` when `--sections` is passed.**

```
python upload_to_supabase.py                              # shiur_content for all output/
python upload_to_supabase.py --dir output/menachot_80    # single daf, shiur_content only
python upload_to_supabase.py --sections                  # all dafs, both tables
python upload_to_supabase.py --dir output/berakhot_11 --sections
python upload_to_supabase.py --dry-run --sections        # preview, no writes
python upload_to_supabase.py --tractates "Berakhot,Shabbat"  # filter by tractate
```

#### shiur_content table

One row per daf. Fields uploaded: `tractate`, `daf` (float), `segmentation` (full JSON from `01_segmentation.json`), `rewrite` (text of `02_rewrite.md`), `final` (text of `03_final.md`). Upserted on `(tractate, daf)` conflict.

#### shiur_sections table (--sections only)

**What is stored:** only `talmudic` and `mishnah` segments — rows where a Sefaria blockquote exists after the `##` header in `03_final.md`. `shiur_discussion` segments (pure rabbi commentary with no blockquote) are **skipped entirely** — their text lives in `shiur_content.final`.

**What is NOT stored:** the shiur lecture text (`content`) is not included in uploaded rows. No embeddings — the embedding column was dropped from this table.

**How sectioning works (`split_final_into_sections`):**
1. Reads `03_final.md` (falls back to `025_cleanup.md`, then `02_rewrite.md` if final doesn't exist)
2. Splits on `## ` (macro) and `### ` (micro) headers; skips top-level `# ` daf title
3. For each section, extracts:
   - `talmudic_text`: the blockquote at the top of the section if it contains `**Hebrew/Aramaic:**` — this is the verbatim Sefaria text (Hebrew/Aramaic + English translation)
   - `content`: the remaining lecture text after the blockquote (extracted but not uploaded)
   - `source_type`: `mishnah` (title matches "mishnah"), `talmudic` (has blockquote), `shiur_discussion` (no blockquote)
4. Timestamps (`timestamp_mm_ss`, `timestamp_secs`) are pulled from `01_segmentation.json` by title match; micro-segment timestamps come from the parent macro's `micro_segments` array
5. `segment_index` is a sequential counter across all sections (including skipped `shiur_discussion` ones, so indices stay aligned with the segmentation JSON)
6. `parent_segment_index` is null for macro rows; for micro rows it's the `segment_index` of the parent macro
7. Rows are deleted for `(tractate, daf)` before re-upserting (delete+insert, not pure upsert), in chunks of 50

**Known issue in filter:** the final content-filter check (`r.get("content")`) always evaluates to None because `content` was removed from the row dict in a refactor. The filter effectively only checks `talmudic_text`, which is fine since `shiur_discussion` rows (no talmudic_text) are already skipped above.

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
| iPhone | `pickerRow` HStack: pill (`compactPickers`) + Daf/Text/Shiur toggle (Shiur only if `shiurRewrite != nil`) |

`compactPickers` is the single source of truth for picker UI on all form factors — `.menu` style for tractate/daf, `.segmented` for amud. All `onChange` handlers live inside `compactPickers`. `pickerRow` wraps `compactPickers` in a pill border and places the Daf/Text/Shiur toggle inline to the right. The toolbar `.principal` slot shows `compactPickers` directly (no pill border).

### iPhone main content mode (iOS: `MainContentMode` enum; Android: `MainContentMode` private enum)

The main content area on iPhone is controlled by `mainContentMode` (`.daf` / `.text` / `.shiur`), replacing the old `showShiurText: Bool`:

- **Daf**: shows the daf image (default)
- **Text**: shows `StudyModeView(textOnly: true)` / `StudyModeContent(textOnly = true)` — Sefaria translation, no tab pill, locked to tab 0. Study button hidden from bottom action row. Session auto-starts when Text mode is selected; restarts on daf/tractate change.
- **Shiur**: shows the shiur rewrite text (only available when `shiurRewrite != nil`)

The Study button at the bottom is hidden when audio is playing (`!audioPlayer.isStopped` / `!isAudioStopped`) **or** when in Text mode (user is already viewing study content).

`StudyModeView` / `StudyModeContent` gains a `textOnly` flag:
- When `true`: hides the header/tab pill, locks to tab 0 (Translation), hides prev/next nav buttons
- When `false && !isInline` (phone full-screen Study mode): hides the Text tab from the tab row, initializes `selectedTab = 1` (Summary)

**Do not restore `onChange(of: shiurClient.shiurRewrite)` that resets mode to `.daf`.** It was removed intentionally — `shiurRewrite` briefly goes `nil` during loading when a new daf is selected, which was resetting the toggle to Daf mode even when the user wanted to stay in Shiur mode. The existing guard `if shiurRewrite == null && mainContentMode == .shiur` handles only the Shiur→Daf fallback.

### Right column

Simple `VStack` with `navBarSafeArea + portraitTopPad` top spacer (to clear the transparent nav bar), then the Shiur/Study segmented picker, then the content panel.

### onChange responsibilities

- `pickerRow` / toolbar pickers: reset `selectedDaf`/`imageDaf`/`imageSide`/`selectedSide` on tractate change; update `imageDaf`/`imageSide`/`selectedSide` on daf/amud change.
- Body-level `onChange(of: selectedTractateIndex/selectedDaf)`: reload shiur segments and restart study session (guarded by `audioPlayer.isStopped`).
- Both fire independently — no conflict.

---

## Study Mode Tab Nav Buttons — Per-Tab, Not Shared (iOS)

**iOS gotcha, source of a recurring bug class.** Each Study Mode tab in `StudyModeView.swift` (Translation, Summary, Quiz) renders its **own** copy of the bottom nav row inside its own tab content view, rather than sharing one component. Each copy independently needs the same boundary logic:

- Section 1: left button must be "Prev Daf" (`onPreviousDaf()`), not a disabled/hidden "Previous".
- Last section: right button must be "Next Daf" (`onNextDaf()`), not a disabled/hidden "Next".

The Translation tab (~line 1214) has always had this correctly. The Summary tab did not — it simply hid the button at each boundary (`if sectionNumber > 1` / `if sectionNumber < totalSections`), silently dropping the ability to cross a daf boundary. Fixed to mirror the Translation tab's pattern. **The Quiz tab's post-answer nav row (~line 763) has the same hide-at-boundary bug and has not been fixed** — check it if quiz nav is ever reported broken.

**Android does not have this bug class** — `StudyModeScreen.kt` uses a single shared bottom nav `Row` (~line 501) for all non-textOnly tabs (Summary/Quiz/Resources), computed once from `isFirst`/`isLast`/`canGoPrevDaf`/`canGoNextDaf`, so the daf-boundary fallback is already correct everywhere on that platform.

**When fixing nav-button logic in Study Mode on iOS, check both the Summary and Quiz tabs for the same pattern — don't assume a fix in one tab covers the others.**

---

## Prev Daf Hangs on Summary/Quiz Tab (iOS, fixed)

**The bug:** pressing "Next Daf" always worked, but "Prev Daf" while already on the Summary or Quiz tab left the UI spinning on the loading skeleton forever, even though the daf text itself (Translation tab) loaded fine.

**Root cause:** `onPreviousDaf` calls `startSession(..., startAtLastSection: true)`, which lands `currentSectionIndex` on the *last* section instead of 0. During `startSession`, `isLoadingText = true` unmounts `SectionStudyView` entirely (`StudyModeView`'s `if manager.isLoadingText { loadingState(...) } else { ... SectionStudyView(...) }`), and it remounts fresh once `isLoadingText` goes back to `false` — already showing the new session's starting index. SwiftUI's `.onChange(of:)` only fires on a *transition* it can observe; it does not fire for a value a freshly-mounted view already holds on first appearance. So `.onChange(of: manager.session?.currentSectionIndex)` (the handler that calls `loadStudyContentForCurrentSection()`) never fires for that landing index, and nothing else does either — `prefetchAllSections()` only prefetched indices 0 and 1, never the actual starting index. "Next Daf" happened to work only because it always lands on index 0, which prefetch already covers regardless of any onChange firing.

**Fix (`StudyModeView.swift`):** the existing `.onChange(of: manager.isLoadingText)` handler (already needed because it's the one place that reliably fires "session finished loading" regardless of whether `SectionStudyView` existed a moment ago — see the comment above it) now also calls `loadStudyContentForCurrentSection()` when `selectedTab` is Summary/Quiz, mirroring what `.onChange(of: selectedTab)` already does for the tab-switch case.

**Fix (`StudySessionManager.swift`):** `prefetchAllSections()` now prefetches the session's actual starting index (`session.currentSectionIndex`, which may be the last section after Prev Daf) in addition to 0 and 1 — otherwise Prev Daf still had to wait for a full uncached Claude call instead of hitting the wait-path for an already-in-flight prefetch. Also hardened `loadStudyContentForCurrentSection()`'s fast-path (`summary != nil`) to explicitly clear `isLoadingStudyContent` rather than leaving it untouched — a stale in-flight call for a since-abandoned index (e.g. rapid section changes) could otherwise strand the flag `true` and keep the skeleton showing even once the current section's content is ready.

**Android does not have this bug** — `StudyModeScreen.kt`'s `LaunchedEffect(session?.currentSectionIndex) { ... }` sits outside any loading-state conditional, and Compose's `LaunchedEffect` runs its block on first composition regardless of whether the key "changed" from a prior value, unlike SwiftUI's `onChange`. No Android fix needed.

---

## Daf Number Went Blank in the Top Picker After Crossing Amud A/B (both platforms, fixed)

**The bug:** navigating to amud b via Study Mode — either Prev Daf landing on the previous daf's last section, or paging Next across the a/b boundary within the same daf — correctly moved the amud pill to "b", but the daf number next to it went blank.

**Root cause:** the picker-sync handler described above (`onChange(of: studySessionDafSide)` on iOS, the equivalent `LaunchedEffect(studySessionSnapshot?.daf, studySessionAmudSide)` on Android) encoded "amud b" by setting `selectedDaf = daf + 0.5` — reusing the same fractional-daf convention that `dafPickerItems` uses for genuine **half-daf audio episodes** (some feeds split content not at the amud boundary; `dafPickerItems` only appends `daf + 0.5` when `feedManager.episodeIndex` actually has an entry there). Study Mode sessions always key on a whole daf (`StudySession.daf: Int` / `daf: Int`); amud is already carried separately via `selectedSide`/`selectedAmud`. Setting `selectedDaf` to an arbitrary `daf + 0.5` that wasn't a real episode entry made it fall outside `dafPickerItems`, and on iOS the UIKit-backed `.menu`-style `Picker` (with its selection now unmatched to any `ForEach` tag) rendered the daf number blank. Android's Compose `DropdownMenu`-based picker doesn't blank out the same way (its button `Text` reads `selectedDaf` directly, not gated on a list match), but the same needless conflation was present there too.

**Fix (both platforms):** the sync handler now always sets `selectedDaf` to the plain whole daf number (`Double(newValue.daf)` on iOS, `s.daf.toDouble()` on Android), never `+ 0.5`. Amud is carried purely via `selectedSide`/`selectedAmud`, as it already was everywhere else in the app. iOS's `dafChanged` detection was updated to compare `newValue.daf != Int(selectedDaf)` so it still works correctly even when `selectedDaf` itself happens to be sitting on a genuine half-daf audio episode value.

---

## Picker Readout Desync from Study Mode Navigation (both platforms)

**The bug:** the top-level tractate/daf/amud picker (`compactPickers` on iOS, the `selectedDaf`/`selectedAmud` picker row on Android) is driven by its own state (`selectedDaf`/`selectedSide` on iOS; `ContentViewModel.selectedDaf`/`selectedAmud` on Android) — separate from the Study Mode session's own `daf`/`currentSectionIndex`. Study Mode's internal header (`StudyModeView.swift`'s `header`, `StudyModeScreen.kt`'s equivalent) reads directly from the session and always updated correctly. But the outer picker readout did **not** follow when Study Mode crossed a daf boundary (Prev Daf/Next Daf) or crossed the amud A/B boundary while paging through sections within the same daf — it silently went stale, e.g. still showing "Bava Kamma 45a" in the picker while the Study panel had already moved to 45b or 46a.

**Root cause:** `onNextDaf`/`onPreviousDaf` (iOS, in `StudyModeView.swift`) and the equivalent nav-row `onClick` handlers (Android, in `StudyModeScreen.kt`) call `manager.startSession(...)` / `studyViewModel.startSession(...)` directly — they never touch the outer picker state, because `StudyModeView`/`StudyModeScreen` don't own it (`ContentView`/`ContentScreen` do).

**Fix (implemented on both platforms):** `ContentView.swift` and `ContentScreen.kt` each now observe the study session's `daf` + derived amud side (`currentSectionIndex >= amudBSectionIndex`) and sync it back into the picker state whenever it changes.

**The trap when implementing this:** both platforms already have a *reactive* handler that fires whenever the picker's `selectedDaf` changes — on iOS, `.onChange(of: selectedDaf)` (restarts the study session or reloads shiur); on Android, `LaunchedEffect(tractate.name, selectedDaf)` (restarts the session **or calls `studyViewModel.endSession()` outside Text mode** — this last part is not obvious and would silently kill the very session you just navigated into, e.g. when Study Mode is showing in an iPad/tablet side panel rather than Text mode). Naively setting `selectedDaf` to mirror the session would immediately trigger this handler and undo/clobber the navigation. Both platforms now use a one-shot guard flag (`suppressDafSessionSync` / `suppressSideSessionSync` on iOS, `suppressDafSessionSync` on Android — Android didn't need a side-specific guard since it has no reactive handler keyed on `selectedAmud` alone) set immediately before the programmatic assignment and cleared the first time the corresponding change-handler observes it. This mirrors the existing `suppressTractateReset` idiom already used in `ContentView.swift` for bookmark navigation — **use a guard flag, don't call the setter and hope the redundant reactive side effects are harmless.**

**Do not have the sync path call through `.onChange(of: selectedSide)` (iOS) / any `selectedAmud`-driven amud-jump logic without checking first** — those handlers also nudge `shiurClient` position and can seek live audio. Study Mode navigation should never move the (independently-tracked) shiur/audio position — see [Audio / Shiur Decoupling Architecture](#audio--shiur-decoupling-architecture-this-is-a-critical-architectural-pattern-read-carefully-before-touching-anything-related-to-audio-segments-shiur-segments-or-the-chapter-strip). The guard flags make this a no-op automatically since the suppressed handler returns before reaching that logic.

**Fixed:** iOS's `onNextDaf`/`onPreviousDaf` (`StudyModeView.swift`) now check tractate start/end boundaries the same way Android's `canGoPrevDaf`/`canGoNextDaf` do (`ContentScreen.kt`/`StudyModeScreen.kt` check `tractateObj.startDaf`/`endDaf`). `onPreviousDaf` used to hardcode `s.daf > 2`, which was wrong for tractates that don't start at daf 2 (`Kinnim` starts at 22, `Tamid` at 25, `Middot` at 34 — see `Tractate.swift`); `onNextDaf` had no upper guard at all. Both closures now look up the session's tractate in `allTractates` and compare against its actual `startDaf`/`endDaf`.

`SectionStudyView` also gained `canGoPrevDaf`/`canGoNextDaf` computed properties (same lookup) so the "Prev Daf"/"Next Daf" buttons are **hidden** (replaced with an empty `Spacer` to keep the two-button row balanced, mirroring Android's `Spacer(Modifier.weight(1f))` pattern) at the tractate's first/last daf — not just disabled-but-visible. Applied to both the Translation tab (~line 1242) and Summary tab (~line 937) nav rows. **The Quiz tab's post-answer nav row does not have "Prev Daf"/"Next Daf" buttons at all yet** (see above) — nothing to hide there until that gap is fixed.

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
| Text display mode | `.translation` | `TRANSLATION` | `textDisplayMode` |
| White background | `false` | `false` | `useWhiteBackground` |

## Theming

**iOS:** `SplashView.background` is the app blue (`Color(red:0.106, green:0.227, blue:0.541)`). `ContentView` uses `appBg`/`appFg` computed properties that switch between blue and white based on `useWhiteBackground`.

**Android:** `AnyDafTheme(useWhiteBackground:)` in `Theme.kt` selects between `LightColors` (blue primary, parchment surface), `DarkColors`, and `WhiteColors` (neutral grey primary, white surface).

## Models

```swift
// iOS (StudyModels.swift)
enum QuizMode:       multipleChoice | flashcard | fillInBlank | shortAnswer
enum QuizSource:     summary | dafText
enum TextDisplayMode: source | translation | both
enum StudyMode:      facts | summary | quiz | resources
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

## Audio / Shiur Decoupling Architecture

This is a critical architectural pattern. Read carefully before touching anything related to audio segments, shiur segments, or the chapter strip.

### The Problem

Content (daf image, text, shiur) follows the selector freely — the user can navigate to any daf at any time. Audio plays independently and does not change when the selected daf changes. When the selected daf differs from the playing daf, audio and shiur/text navigation must be **decoupled**: moving a segment in one must not move the other.

### Two-Layer Segment State (ShiurClient)

`ShiurClient` (iOS) / `ShiurClient.kt` (Android) maintains two independent segment layers:

| State | Purpose |
|-------|---------|
| `segments` / `currentSegmentIndex` | Shiur content for the **currently selected daf** — changes when the user navigates |
| `audioSegments` / `audioCurrentSegmentIndex` | Frozen snapshot for the **currently playing audio daf** — set once at play-start, never changes until audio stops |

Key methods:
- `snapshotAudioSegments()` — copies `segments → audioSegments` at the moment audio starts playing; called from `onChange(of: audioPlayer.isStopped)` when `isStopped` becomes `false`
- `jumpToAudioSegment(idx)` — moves `audioCurrentSegmentIndex` only; does not touch `currentSegmentIndex`
- `updateCurrentSegment(currentTime)` — advances `audioCurrentSegmentIndex` using `audioSegments`; never touches `currentSegmentIndex`

### Audio Locked Daf

At play-start, two state vars are frozen alongside the snapshot:
- iOS: `@State var audioLockedTractateIndex: Int` and `@State var audioLockedDaf: Double`
- Android: `audioLockedTractate: String` and `audioLockedDaf: Double` in ContentScreen

These never change while audio plays. All same-daf guards read from these.

### Same-Daf Sync (the coupling when dafs match)

When the selected daf IS the playing daf, audio and shiur/text stay in sync:

```swift
// iOS — in ContentView body
.onChange(of: shiurClient.audioCurrentSegmentIndex) { _, newIdx in
    guard !audioPlayer.isStopped,
          selectedTractateIndex == audioLockedTractateIndex,
          selectedDaf == audioLockedDaf else { return }
    shiurClient.currentSegmentIndex = newIdx
}
```

```kotlin
// Android — in ContentScreen
LaunchedEffect(audioSegmentIndex) {
    if (!isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf) {
        ShiurClient.jumpToSegment(audioSegmentIndex)
    }
}
```

### Chapter Strip (audio pill bar)

The chapter strip in the audio controls shows `audioSegments` / `audioCurrentSegmentIndex` — the frozen audio snapshot — not `segments`. The strip is shown only when `audioSegments` is non-empty and `audioPlayer.duration > 0`.

Pill tap: calls both `audioPlayer.seek(to: seg.seconds / duration)` and `shiurClient.jumpToAudioSegment(idx)`.

The `onChange` that scrolls the strip to keep the active pill visible watches `audioCurrentSegmentIndex`, not `currentSegmentIndex`.

### Shiur Navigation Strip (shiur text pill bar)

Separate from the chapter strip. Shows `segments` / `currentSegmentIndex` — the selected daf's shiur. Pill tap calls `shiurClient.currentSegmentIndex = idx`. `onSegmentVisible` callback (user scroll detection) calls `shiurClient.jumpToSegment(idx)` always — no audio guard needed there.

### onChange(of: selectedSide) — Audio Seek Guard

Pressing a/b in the picker seeks audio to amud B only when the selected daf matches the playing daf:

```swift
let isSameDaf = !audioPlayer.isStopped
    && selectedTractateIndex == audioLockedTractateIndex
    && selectedDaf == audioLockedDaf
if isSameDaf { /* seek audio */ }
```

### reset() vs loadSegments() — Critical Distinction

`shiurClient.reset()` clears **all** state including `audioSegments` — only call it when audio is stopped.  
`shiurClient.loadSegments()` clears only the content state (`segments`, `shiurRewrite`, etc.) and leaves `audioSegments` intact — safe to call anytime.

In `onChange(of: selectedTractateIndex)` in ContentView: **guard `reset()` with `if audioPlayer.isStopped`** to prevent wiping the audio snapshot when the user navigates to a different tractate while audio plays.

### SwiftUI Scroll Reliability (ShiurTextView)

Several non-obvious timing issues were worked out:

1. **`proxy.scrollTo` called before layout is committed fails silently.** After setting `parsedBlocks`, sleep 50ms before scrolling. No `withAnimation` needed — ShiurTextView uses a regular `VStack` (not `LazyVStack`), so all items are measured before any scroll and `scrollTo` is always exact. Do NOT switch back to `LazyVStack`: it estimates heights for off-screen items, causing `scrollTo` to land mid-section even with `withAnimation`.

2. **GeometryReader fires at scroll=0 when `parsedBlocks` is first assigned**, causing `onPreferenceChange` to report segment 0 and corrupt the active segment. Fix: set `scrollDetectionState.isProgrammaticScrolling = true` *before* `parsedBlocks = computed`, and clear it after 650ms.

3. **`isProgrammaticScrolling` flag** in `ScrollDetectionState` (reference type — intentional, shared across closures): suppresses `onPreferenceChange → onSegmentVisible` during programmatic scrolls to prevent feedback loops. Set before any programmatic `proxy.scrollTo`; clear after 650ms.

4. **`suppressNextScrollTo`**: when `onSegmentVisible` fires (user scroll), it sets `currentSegmentIndex` via callback. This would re-trigger `onChange(of: currentSegmentIndex)` → another `proxy.scrollTo`. Suppress by storing the index in `suppressNextScrollTo` and skipping the scroll in `onChange` when it matches.

## Bookmarks

- Identified by `(tractateIndex, daf, amud)`; optionally linked to a study section index
- `BookmarkManager` (iOS) / `BookmarkViewModel` (Android)

---

## Text View Segment Navigation (implemented)

Extends the shiur segment-pill navigation to the Sefaria text view (Text mode on iPhone / Translation tab on iPad): a pill strip to jump the text to a shiur macro segment, and automatic position hand-off when switching directly between Shiur mode and Text mode.

### Data: `sefaria_index` mapping

`find_sefaria_indices.py` (in `daf-processor/`) matches each shiur macro segment's Hebrew blockquote (from `03_final.md`) against the daf's flat Sefaria segment array (parsed from `sefaria.md`), writing `sefaria_index` into each macro segment of `01_segmentation.json`, plus `amud_b_sefaria_index` (= the count of amud A items, same value as `SefariaClient.fetchFullDaf`'s `a.count`). Purely local text matching — no API calls, free to re-run.

**Carry-forward for unmatched segments**: `shiur_discussion` segments (pure commentary, no direct Talmudic blockquote) have no text to match against Sefaria. These carry forward the most recently matched `sefaria_index` rather than being left unset — landing right after the Talmudic passage they're discussing is more useful than not being jumpable at all. Only segments before the *first* match in a daf are left with no `sefaria_index` (rare — a daf would have to open with discussion before any blockquote). Run across all `output/` dirs: 76.8% direct match, 13.5% carried forward, 9.8% genuinely unset (mostly the 5 dafs with corrupt `01_segmentation.json`, which `process_dir` now skips gracefully instead of crashing the whole batch).

After running, re-upload via `python upload_to_supabase.py` (default path, no `--sections` needed) — pushes the richer `segmentation` JSON blob into the existing `shiur_content` table, no schema change.

### Models

`ShiurSegment.sefariaIndex: Int?` (iOS `ShiurClient.swift`, Android `ShiurClient.kt`) and `ShiurSegmentation.amudBSefariaIndex: Int?` were already in place from an earlier session — decoded from `sefaria_index` / `amud_b_sefaria_index`.

### Segment pill strip

Both platforms reuse the existing `shiurClient.segments` (same shiur, same titles) — no new data source, no prop drilling (it's a singleton on both platforms, same pattern as `ResourcesManager.shared`).

- **iOS**: `SectionStudyView.textNavigationStrip` (`StudyModeView.swift`) — shown above the scrollable content, Translation tab only. Active pill = the shiur segment whose `sefariaIndex` is the closest one ≤ the current section's `firstSegmentIndex` (`activeShiurSegmentIndex`, a reverse scan of the same kind `jumpToSection(containing:)` already did forward). Tap calls a new `onJumpToSefariaIndex` closure threaded from `StudyModeView`, which calls the previously-unused `manager.jumpToSection(containing:)`. Pills for segments with no `sefariaIndex` are shown dimmed and disabled rather than hidden (keeps the strip's segment count/order legible).
- **Android**: `TextNavigationStrip` (`StudyModeScreen.kt`), a `LazyRow` mirroring the existing shiur chip strip pattern in `ContentScreen.kt`. Tap calls `studyViewModel.jumpToSection(sefariaIndex)`.

**Not implemented**: audio-seek-on-tap for text pills (the shiur strip seeks playing audio on a same-daf tap; the text strip does not, to keep the change scoped — `SectionStudyView`/`StudyModeContent` don't have audio-player state threaded in). Also not implemented: pressing the a/b amud picker while already in Text mode does not scroll the text view directly (only the Shiur↔Text mode-switch sync below does).

### Bidirectional Shiur↔Text mode-switch sync

On a **direct** switch between Shiur mode and Text mode (not via the Daf image, and not on launch — those still restore each mode's own last-remembered position, unchanged), position carries across via `sefariaIndex`:

- Shiur → Text: read the shiur's current segment's `sefariaIndex`, call `jumpToSection(containing:)` / `jumpToSection(sefariaIndex)`.
- Text → Shiur: read the current section's `firstSegmentIndex`, reverse-map to the owning shiur segment (same scan as the active-pill calculation), set the shiur's current segment index directly.

**iOS** (`ContentView.swift`): `.onChange(of: mainContentMode)` already received `(oldValue, newValue)` but only used `newValue` — now branches on `oldValue` to detect the direct-switch case, falling back to the existing `lastTextSectionIndex`/`lastShiurSegmentIndex` restore otherwise. The iPad `iPadRightPanel` toggle (`.shiur`/`.study`) gets the same treatment — its Study panel defaults to the Translation tab, so it's the direct equivalent of iPhone's Text mode, and previously had no position sync there at all.

**Android** (`ContentScreen.kt`): a single `mainContentMode` state already covers both phone and tablet layouts (unlike iOS's split `mainContentMode`/`iPadRightPanel`), so one fix covers both form factors. This also **fixed a real bug**: the existing "switching to text mode" `LaunchedEffect` called `studyViewModel.jumpToSection(lastTextSectionIndex)` and `jumpToSection(bIdx)` — passing raw section indices to a function that expects a flat Sefaria index, which would pick the wrong section in general (coincidentally close only for very early sections in a daf). Fixed by adding `jumpToSectionAt(index)` (`StudySessionViewModel.kt`, direct index jump — the Android equivalent of iOS's already-existing `jumpToSectionAt`) and using it for the non-direct-switch restore path, reserving `jumpToSection(sefariaIndex)` for actual Sefaria-index lookups. Also added a `previousMainContentMode` tracker (Compose's `LaunchedEffect(mainContentMode)` doesn't get an old value for free like SwiftUI's `onChange` does) to detect the direct-switch case.

### Two bugs found testing on Kiddushin 2 (both fixed, both platforms)

**Bug 1 — wrong active pill from carried-forward `sefariaIndex` collisions.** Kiddushin 2's segmentation has four consecutive segments (`Ha-Isha Nikneit Mishna`, `Kiddushin vs. Nisu'in`, `Kesef Dispute`, `Intro to Kiddushin (II)`) all carrying `sefaria_index: 0` — only the first of the four actually matched a blockquote; the other three carried forward from it (see the carry-forward rule above). The active-pill scan (find the *last* segment with `sefariaIndex ≤ target`) picked the last of that run — `Intro to Kiddushin (II)` — even while viewing the Mishna itself (`sefariaIndex == 0` exactly), instead of the segment that actually matched there.

**Fix**: `activeShiurSegmentIndex` (iOS `SectionStudyView` in `StudyModeView.swift`), `shiurSegmentIndex(owning:)` (iOS `ContentView.swift`), and the equivalent scans in Android (`TextNavigationStrip` in `StudyModeScreen.kt`, and the Text→Shiur sync in `ContentScreen.kt`) now all check for an **exact** `sefariaIndex` match first (`firstIndex`/`indexOfFirst`, picking the earliest segment with that exact value) before falling back to "last segment strictly before target." This correctly resolves ties in favor of the real anchor; a position strictly *between* two anchors still falls back to the nearest-preceding-segment heuristic, which remains inherently approximate — there's no finer-grained data to resolve those cases better.

**Bug 2 — stale study session shows the wrong daf's text.** Shiur mode does not keep `studyManager`'s / `studyViewModel`'s study session in sync with daf changes — only Text mode's `onChange(of: selectedDaf)` path restarts it (Android additionally calls `endSession()` when leaving Text mode on a daf change, nulling it out). So changing the daf while in Shiur mode, then switching directly to Text mode, ran the new Shiur→Text sync against a **stale session still pointing at whatever daf was last actually visited in Text mode** — while the shiur pill strip (which always reloads correctly per daf via `ShiurClient`) showed the *current* daf's segment titles. The result: correct-looking pills next to text from a completely different daf.

**Fix (both platforms)**: added a `studySessionIsCurrent` guard — checks the loaded session's `tractate`/`daf` actually match the currently selected daf — before trusting the direct-switch jump in both directions (Shiur→Text and Text→Shiur), on both the iPhone/phone path and iOS's iPad `iPadRightPanel` path. When the guard fails, the code falls through to the existing (already-correct) restore-or-fresh-start logic instead of acting on stale data.

### Bug 3 — found testing on Kiddushin 11: title-string matching is fundamentally unreliable (fixed, pipeline)

**The bug:** Kiddushin 11's very first segment (`Terumah: Erusin/Kiddushim`, the real start of the daf, "עד שתכנס לחופה") had `sefaria_index: None` and showed grayed out in the pill strip, even though its blockquote is right there in `03_final.md`.

**Root cause:** `find_sefaria_indices.py` matched macro segments to `## ` headers in `03_final.md` by **exact title string** — but a macro's `title`/`display_title` come from pass 1 (segmentation), while the `## ` header text comes from pass 2/3 (rewrite + source insertion), a **separate Claude call**. The two are never guaranteed to produce identical text. In this case: `display_title` was `"Terumah: Erusin/Kiddushi…"` (pass 1's own 25-char truncation, with an ellipsis) while the actual `03_final.md` header was `"Terumah: Erusin/Kiddushim"` (pass 2/3's independently-written full text, coincidentally also 25 characters but with no ellipsis) — one character of difference was enough to make the dictionary lookup miss entirely, so the segment fell through to "no blockquote found" even though its content was right there.

**Scope**: checked across all 2,363 dafs — 2,256 (95.5%) have the exact same *count* of macro segments as `## ` headers, in the same chronological order (pass 2/3 doesn't reorder or drop segments, just rewrites their titles/prose). Title-string matching was silently failing on some fraction of segments in most dafs, not just the unusual ones.

**Fix**: `find_sefaria_indices.py` now matches **positionally** (macro segment *i* ↔ the *i*-th `## ` header) whenever the counts match, which is far more reliable than joining on independently-generated title text. Only falls back to the old title-based lookup when counts don't match (a genuine pass 2/3 split/merge, where position can't be assumed to line up). Re-running across all dafs improved direct matches from 76.8% → 79.9% and cut unmatched segments from 9.8% → 8.7%.

### Eliminating the remaining unmatched segments (0% unset now)

After the positional-matching fix, 8.7% of segments still had no `sefaria_index` at all. Checked every one of them across the whole corpus: **100% were leading segments before any blockquote match had been found yet in that daf** — typically an "Introduction/Overview" segment discussing the masechta or sugya structure before the Gemara's first direct quote. There were zero cases where carry-forward *should* have kicked in from a real prior match and silently failed to — the mechanism was working correctly, it just had nothing to carry forward from yet in these cases.

**Fix**: `last_idx` now initializes to `0` instead of `None`, so leading unmatched segments carry forward to the start of the daf's own text instead of being left unset. An "introduction to this sugya" segment landing at the very beginning of the daf is the one sensible default available — not a guess, just the natural anchor for material that introduces what follows. This removed the `unset` case entirely (the `else: macro.pop(...)` branch and its now-impossible condition were deleted). Coverage: 79.9% direct match + 20.1% carried forward, 0% unmatched.

### Inline segment-title headers in the Text view (implemented)

Beyond the pill strip, the shiur segment's title now also appears as a small heading directly above the Sefaria text, right where that segment begins — an organizing guidepost while reading, and a much faster way to visually spot a bad `sefariaIndex` match than tapping through pills one at a time (a header appearing in a clearly wrong spot is immediately obvious).

**Where it appears**: since the Translation tab shows one `StudySection` at a time (paged via Next/Previous, not a continuous scroll of the whole daf), the header can only land at *section* granularity, not the exact word a quote begins at. It shows above a section's text only when that section is the **first** one to reach a given shiur segment — computed by comparing the current section's owning segment (via the same "owning segment" scan the pill strip uses) against the previous section's.

**iOS** (`StudyModeView.swift`): `SectionStudyView.activeShiurSegmentIndex` was refactored into a parameterized `owningShiurSegmentIndex(for:)` (later `forRangeStarting:endingBefore:`, see Bug 4 below) so it could be reused for both the current section and (for comparison) the previous one. New `allSections: [StudySection]` property (the full ordered list, passed from `StudyModeView` — used only for this previous-section lookup, not for rendering). `newShiurSegmentHeader: ShiurSegment?` computes the comparison; `segmentTitleHeader` renders it inside `translationCard`, right after the pill/legend divider in both the Hebrew and English-only branches. Uses `displayTitle` (the same brief label already shown in both the Shiur and Text pill strips) — originally used the full `title`, but switched to keep one consistent label per segment across Shiur and Text rather than introducing a third, more verbose variant just for this header.

**Android** (`StudyModeScreen.kt`, `SectionStudyView.kt`): the "owning segment" scan was already duplicated three times across the Android codebase (Text↔Shiur sync in `ContentScreen.kt`, `TextNavigationStrip`'s active-pill computation) — factored into a shared `ShiurClient.owningSegmentIndex(...)` and all three call sites (including this new one) now use it. `StudyModeContent` computes `newSegmentTitle: String?` the same way as iOS and passes it into `TranslationTab`, which renders it just after the pill/legend divider.

### Bug 4 — found testing on Hullin 2: segments anchored mid-section were invisible to the header/active-pill (fixed, both platforms)

**The bug:** tapping a pill (e.g. "Tamei Shochet Reading", `sefariaIndex: 11`) correctly jumped the text to the right section — but no header appeared, and the pill itself never showed as active/highlighted.

**Root cause:** `jumpToSection(containing:)` (the pill-tap handler) finds the *last text section* whose `firstSegmentIndex ≤` the tapped `sefariaIndex` — correct, and sections are coarser than shiur segments, so the section it lands on can easily have a `firstSegmentIndex` well below the tapped segment's own `sefariaIndex` (e.g. a section spanning raw indices 9–15 for a segment anchored at 11). But the "which segment is active here" computation (`activeShiurSegmentIndex` / `TextNavigationStrip`'s `activeIndex`) derived its answer from that section's *own* `firstSegmentIndex` alone (9), not from the tapped segment's `sefariaIndex` (11) — so it re-resolved to whatever *earlier* segment happens to own position 9, not the one just tapped. Any segment whose real anchor begins partway through a section, rather than exactly at its start, was structurally invisible to both the header and the active-pill highlight — a general gap, not specific to this daf.

**Fix (both platforms):** the "owning segment" lookup was changed from a single point to a **range** — a section's full span, from its own `firstSegmentIndex` up to (but excluding) the *next* section's `firstSegmentIndex`. Among shiur segments whose `sefariaIndex` falls inside that range, it now prefers the one with the **largest** `sefariaIndex` (the most specific anchor actually reached within the section) rather than the smallest/earliest. Segments tied at that same largest value (carried-forward duplicates) still resolve to the **first** one in array order, preserving the Bug 1 fix (Kiddushin 2's carried-forward-duplicate collision) without regressing it.

- **iOS**: `owningShiurSegmentIndex(for:)` → `owningShiurSegmentIndex(forRangeStarting:endingBefore:)` in both `StudyModeView.swift` (`SectionStudyView`) and `ContentView.swift` (mode-switch sync, both the iPhone and iPad `iPadRightPanel` call sites). New `sectionRangeEnd(after:)` / `currentSectionRangeEnd()` helpers compute the exclusive upper bound from the next section in `allSections` / `session.sections`.
- **Android**: `ShiurClient.owningSegmentIndex(target:, segments:)` → `owningSegmentIndex(start:, end:, segments:)`, all four call sites (`ContentScreen.kt`'s Text→Shiur sync, `StudyModeScreen.kt`'s header computation ×2, and `TextNavigationStrip`'s `activeIndex`) updated to pass a range. `TextNavigationStrip` gained a new `currentSectionRangeEnd: Int` parameter since it only received the single current `StudySection`, not the full list needed to find the next one.

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

---

## Audio Tagging System

A Supabase-backed tagging system for curated audio content (podcasts, conference recordings) that links episodes to specific Talmud, Shulkhan Arukh, and Rambam references. Displayed in the Resources tab alongside library.yctorah.org articles.

### Files

| File | Location |
|---|---|
| Schema SQL | `AnyDaf/audio_tags_schema.sql` |
| Upload script | `AnyDaf/upload_audio_tags.py` |
| Tagger spreadsheet | `AnyDaf/audio_tagger.xlsx` |

### Spreadsheet Design (`audio_tagger.xlsx`)

- **Episodes tab** — tagger fills in source, episode_number, title, presenter, audio_url, platform. Grey `id` column (`=ROW()-1`) and grey `display_label` column (`=source & " — " & title`) auto-fill; do not edit.
- **Reference tabs (Talmud / SA / Rambam)** — Column A is an **Episode dropdown** sourced from the named range `EpisodeLabels` (points to `Episodes!$I$2:$I$500`). The tagger picks `"source — title"` from the list; the grey `episode_id` column auto-resolves via `INDEX/MATCH`. The tagger never types a source name or episode number in the reference tabs — no typo risk.
- Dropdowns also on `amud` (a/b), `platform` (soundcloud/youtube/direct/website), and `section` (OC/YD/EH/CM).
- Upload script reads the file with `data_only=True` (requires the file was saved from Excel/LibreOffice so formula caches are populated). Run `scripts/recalc.py audio_tagger.xlsx` to recalculate programmatically if needed.

### Supabase Tables

```
audio_episodes        — one row per recording (podcast ep or conference talk)
audio_talmud_refs     — Talmud citations linked to an episode
audio_sa_refs         — Shulkhan Arukh citations linked to an episode
audio_rambam_refs     — Rambam citations linked to an episode
```

#### `audio_episodes`

| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `source` | text | Podcast/event name, e.g. "Iggros Moshe A to Z" |
| `episode_number` | int | Nullable for one-off recordings |
| `title` | text | Episode title |
| `presenter` | text | Speaker name |
| `audio_url` | text | SoundCloud, YouTube, direct mp3, or website URL |
| `platform` | text | `soundcloud` \| `youtube` \| `direct` \| `website` |
| `description` | text | Optional blurb |

Unique constraint on `(source, episode_number)`.

#### `audio_talmud_refs`

| Column | Type | Notes |
|---|---|---|
| `episode_id` | int FK | → `audio_episodes.id` |
| `tractate` | text | AnyDaf canonical name |
| `daf` | int | |
| `amud` | text | `a`, `b`, or null (full daf) |
| `commentary` | text | e.g. "Tosafot", "Rashi" |
| `commentary_ref` | text | e.g. "s.v. Ee Hakhi" / "ד״ה אי הכי" |

#### `audio_sa_refs`

| Column | Type | Notes |
|---|---|---|
| `episode_id` | int FK | |
| `section` | text | `OC` \| `YD` \| `EH` \| `CM` |
| `siman` | int | |
| `seif` | int | Nullable |
| `commentary` | text | e.g. "Mishna Berura" |
| `commentary_ref` | text | e.g. "s.k. 14" |

#### `audio_rambam_refs`

| Column | Type | Notes |
|---|---|---|
| `episode_id` | int FK | |
| `halakhot` | text | e.g. "Nizkei Mamon" |
| `chapter` | int | |
| `halakha` | int | Nullable |
| `commentary` | text | e.g. "Raavad" |
| `commentary_ref` | text | |

### App Query (Talmud)

```sql
SELECT e.id, e.title, e.audio_url, e.platform, e.presenter, e.source,
       r.daf, r.amud, r.commentary, r.commentary_ref
FROM   audio_talmud_refs r
JOIN   audio_episodes e ON e.id = r.episode_id
WHERE  r.tractate = 'Avodah Zarah'
  AND  r.daf IN (2, 3, 4)   -- current daf ± nearby range
ORDER  BY r.daf, r.amud;
```

### Platform Playback Notes

| platform | How the app handles it |
|---|---|
| `soundcloud` | Play in-app via existing SoundCloud audio infrastructure |
| `youtube` | Open in YouTube app / browser (cannot stream natively) |
| `direct` | Stream in-app via AVPlayer / Android MediaPlayer |
| `website` | Open in in-app WebView or browser |

### Upload Script Usage

```bash
pip install openpyxl httpx python-dotenv

# Validate without writing
python upload_audio_tags.py --dry-run

# Upload
python upload_audio_tags.py --file audio_tagger.xlsx
```

Requires `SUPABASE_URL` and `SUPABASE_KEY` (service role) in `.env`.  
Script upserts Episodes first, then resolves `display_label → episode_id` via the `"source — title"` label built in the spreadsheet. Re-running is safe.

### First Source: Iggros Moshe A to Z

- SoundCloud: https://soundcloud.com/iggrosmosheatoz
- 53 episodes
- Tagging project in progress: tagger uses `audio_tagger.xlsx`, uploads via script
- Only `audio_talmud_refs` needed initially; SA and Rambam tables ready for future use

### WordPress Audio Posts (Pending)

library.yctorah.org has audio posts at `/audio/[slug]/` URLs. The post type is a custom WordPress type not currently exposed via the REST API (`show_in_rest` not set). Once enabled, the app can query these posts via `YCTLibraryClient` alongside standard articles. The audio URL format (SoundCloud embed vs direct mp3) needs to be confirmed before implementing in-app playback.
