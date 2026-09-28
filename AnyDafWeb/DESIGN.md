# AnyDafWeb — design (draft, 2026-09-24)

A standalone web app for studying a daf with the AnyDaf study aids: the nested outline, charts,
illustrations and key terms, beside the Gemara text. It is for learners at a desk, so it
has room the phone app doesn't: panes side by side, pop-out windows, the extended-sugya view.
It leaves out most of AnyDaf's app features (audio, quizzes, bookmarks).

**Prototype:** https://claude.ai/artifact/VyEhmmkY9siDtWvA6F2WbH (Chagigah 6, built by
`prototype/build_prototype.py`). The design decisions below are the ones it tests.

## Decisions already made (author, 2026-09-24)

- Lives here, `AnyDaf/AnyDafWeb/`, mirroring `AnyTorah/AnyTorahWeb/`; not with AskAnyDaf.
- **One shared renderer** (`renderer/outline-renderer.{js,css}`), used by this app and embedded
  in the iOS/Android apps through WKWebView / Android WebView. It is framework-free on purpose
  so the apps can load it as-is.
- Content is generated once by the daf-processor batch passes, stored per daf, and read by
  every surface.
- First features: the Gemara text or daf image in a pane that scrolls with the outline, and
  pop-out windows (the glossary first).
- **Pane selector Daf / Gemara / Shiur, defaulting to Gemara**, with the written shiur synced
  like the Gemara. The text pane sits **right of the outline by default** (the outline reads left to right, the
  Gemara right to left, so they meet in the middle), with a swap control, as AnyTorah does for
  the daf image. Language pill **א / אA / A**, as in the other apps.
- Gemara text is served from **our own saved copy** of the Bavli, not fetched live (below).
- **Link-only** access while the outlines are under review.

## Stack

Same as AnyTorahWeb, so the two can share code and conventions: Next.js 16 (App Router),
React 19, Tailwind 4, Supabase (`@supabase/ssr`), deployed on Vercel.

Reused from AnyTorahWeb, copied in with a header naming the source file, until enough is shared
to justify a package:

| AnyTorahWeb file | Use here |
|---|---|
| `components/DafImagePanel.tsx`, `lib/talmudPages.ts`, `app/api/dafImage/route.ts`, `public/pages.json` | The daf page image pane (zoom and pan already done) |
| `lib/sefariaClient.ts` (`fetchBoth`, `talmudAmudRef`) | Live Gemara text, if we don't serve it from our own store (below) |
| `lib/hebrewUtils.ts`, `lib/textModels.ts` (`toHebrewNumeral`) | Hebrew names and folio numbers |
| `components/DedicationBanner.tsx`, `lib/dedicationService.ts` | Dedications, if wanted (would need a `for_anydaf_web` flag) |

## Data

Generated in daf-processor, uploaded to the existing AnyDaf Supabase project:

```sql
create table daf_study_aids (
  tractate       text not null,
  daf            numeric(4,1) not null,        -- same convention as shiur_content
  outline        jsonb not null,               -- 04_outline_*.json (SVG already sanitized); includes
                                               -- `sages` (2026-09-27) and, once built, summaries/quizzes
  key_terms      jsonb,                        -- per-daf terms, each with a glossary_id
  model          text not null,
  prompt_version text not null,
  status         text not null default 'draft',  -- draft | reviewed | published
  generated_at   timestamptz default now(),
  primary key (tractate, daf)
);

create table glossary_entries (             -- the master glossary, one row per sense
  id              text primary key,         -- e.g. chatzer_acquisition
  term            text not null,
  hebrew          text,
  sense           text not null,
  core_definition text,                     -- author-reviewed; null while draft
  variants        text[] default '{}',      -- spellings, for search and highlighting
  taxonomy_id     text,                     -- AskAnyDaf seed_taxonomy link, when confirmed
  status          text not null default 'draft'
);
```

The web app reads rows with `status = 'published'` only; the review tools read all of them.
A per-daf term shows the master `core_definition` once reviewed, and its own draft definition
(marked as a draft) until then.

**Gemara text.** The outline's anchors are Sefaria segment labels (`6a.8` = amud 6a, segment 8,
1-based), the numbering in daf-processor's `sefaria*.md`. Two options:
1. Fetch live from Sefaria per amud, as AnyTorahWeb does. Nothing to store; segment *i* of the
   amud's text array is label `amud.(i+1)`. (Checked: `sefaria.py` numbers by Sefaria's own
   index and skips empty segments without renumbering, so the labels do match.)
2. Serve the cached `sefaria*.md` text from our own table. Guaranteed to match the anchors, and
   works offline for the apps. About 2,300 × ~60 KB.

**Decided: option 2.** A `daf_text` table (tractate, daf, amud, segments jsonb of
`{he, en}`, Sefaria version ids), filled once from Sefaria for the whole Bavli; the existing
cached files already cover most of it. Sefaria's English (William Davidson) is CC BY-NC, so
the page needs an attribution line.

## Pages

| Route | What it shows |
|---|---|
| `/` | Tractate and daf picker; recently studied dafim |
| `/[tractate]/[daf]` | The study page (below) |
| `/glossary` | The master glossary: search, browse by category, each entry listing the dafim that use it |
| `/glossary/[id]` | One term, with each daf's usage line and links |
| `/popout/[kind]` | A pop-out window's contents (glossary, chart, picture, mind map) |

## The study page

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Chagigah 6  Headlines|Standard|Detailed  ☑Shiur ☑Charts ☑Pictures  Glossary  Daf|Gemara|Shiur  ⇄ │
├───────────────────────────────────────────────┬──────────────────────────────────────┤
│ Key terms: olat re'iyah · chinuch · …          │ א|אA|A   ☑Follow the outline          │
│                                               │ Reading: Positions… · 6a.16–6b.1     │
│ ▌Olat Re'iyah versus Shalmei Chagigah          │ ┃6a.16 תנו רבנן…                      │
│    Beit Hillel and Beit Shammai…              │ ┃      The Sages taught…             │
│      • bullets, charts, pictures              │ ┃6a.17 …                             │
└───────────────────────────────────────────────┴──────────────────────────────────────┘
```

- **Text pane (right by default, ⇄ swaps sides):** Daf (page image), Gemara (א / אA / A), or
  Shiur (the written shiur, its Gemara quotes following the same language pill). Default
  Gemara; the reader's choices are remembered. Below 860px wide the panes stack.
- **Outline pane:** the shared renderer. Key-term chips sit above it, and the first mention of
  each term in a section is highlighted; tapping either opens the glossary at that term.

### Scroll sync

- Every outline section carries `text: {from, to}`. The **current section** is the deepest
  section whose box crosses a reading line about 110px below the top of the outline pane. It
  gets a marker in the outline; its range is highlighted in the Gemara, which scrolls to its
  first line.
- If the reader scrolls the Gemara themselves, it stops following for 1.5 seconds. A "Follow
  the outline" switch turns following off entirely.
- Reverse: clicking a Gemara line jumps the outline to the deepest section that contains it.
- **Daf image:** line-level sync is now possible (2026-09-24). `daf-processor/page_layout/`
  aligns Sefaria's text to the page images the apps already show (word widths, no OCR), and each
  amud's JSON lists, for every Gemara segment label and every Rashi/Tosafot comment, one box per
  printed line it covers. The current section's `text` range then maps to boxes to highlight on
  the page, and a tap on the page maps back to a label, so the outline, Gemara, shiur and audio
  can all follow the image and it can follow them. Boxes are in the full-size scan's pixels
  (store the image size and scale). Not yet stored in Supabase or wired into the prototype; see
  the AnyDaf CLAUDE.md "Live-text daf image" and TODO.md.
- **Written shiur pane (in the prototype):** each Gemara quote in `03_final.md` is verbatim
  Sefaria text (v10 assembly), so it maps to its label by exact match after stripping nikud
  (Chagigah 6: 27 of 27). The pane scrolls to the first quote inside the current section's
  range, else the nearest quote before it (about 23% of lines are never quoted), and those
  quotes are highlighted; clicking a quote moves the outline. In production, store the labels
  per quote at upload. Still to handle: where the shiur leaves text order (reviewing the
  previous daf, back-references), reuse the app's Shiur↔Text range logic (see the AnyDaf
  CLAUDE.md, "Text View Segment Navigation", bugs 1–4).

### Pop-outs

- **In-page panel first** (what the prototype does): a floating, draggable, resizable panel on
  desktop; a bottom sheet on a phone.
- **"Open in its own window"** on the web: `window.open('/popout/glossary?daf=…')`, kept in step
  with the study page through a `BroadcastChannel('anydaf')` carrying `{currentSection}` and
  `{focusTerm}`. The same channel will serve a second monitor showing charts or the mind map.
- **Sages** (built in the prototype, 2026-09-24): a pop-out with a timeline pinned at the top
  (generations left to right, Eretz Yisrael above and Bavel below), a card per sage (generation,
  region, teachers/students/colleagues, bio, the outline sections they appear in), ordered as they
  appear, A–Z or by era. Tapping a sage's name in the outline (linked once per daf, like key
  terms) opens the box at that card and scrolls the timeline to the sage. Data from
  `daf-processor/build_sages.py`; which sage each name means comes from the outline's own
  `sages` list (outline pass, 2026-09-27), with a name-matching guess only for older outlines.
  A `sages` table in Supabase is still to come.
- The glossary is first. Charts, pictures and the extended-sugya mind map are the next
  candidates, since they are worth keeping in view while reading on.

## The shared renderer

`renderer/outline-renderer.js` exposes `AnyDafOutline.render(el, {outline, keyTerms, onTerm,
onSection})` and `AnyDafOutline.glossary(el, keyTerms, {titles, onSection})`. The returned
view has `sections` (id, title, from, to, depth, element), `setLevel`, `setOption`,
`scrollToSection` and `markCurrent`. Everything it draws is scoped under `.ado`, and colors
come from the host page's tokens.

- **Web:** a small React wrapper, `components/OutlineView.tsx`, mounts it on a ref and
  re-renders when the daf changes. Sync, panes and pop-outs are the page's job, not the
  renderer's.
- **Apps:** a bundled `outline.html` (renderer + sprite + tokens), loaded by the native
  WebView with the daf's JSON injected. Callbacks go out through
  `webkit.messageHandlers.anydaf` / `@JavascriptInterface`, the pattern the apps already use for
  the article reader's audio bridge. The apps own their chrome (detail level, toggles) and call
  `setLevel` / `setOption`.
- SVG from the model is sanitized **at build time** (`clean_svg` + `uniquify_ids` in
  daf-processor), never in the renderer, so every surface gets the same safe markup.

## Not in the first version

Accounts, notes and highlights (AnyTorahWeb has these to borrow later); audio; quizzes (the
outline pass will pre-generate them for the apps, decided 2026-09-27; the web app can add them
later from the same data); the
Hebrew/RTL interface mode (follow AnyTorahWeb's rules when it comes); the extended-sugya view.

## Open questions for the author

1. Dedications on the web app: yes or no?

## Milestones

1. Scaffold the Next.js app; the study page for the 12 test dafim from static JSON.
2. Regenerate those dafim with the final prompt, including `text` anchors, key terms, sages and
   (once designed) summaries and quizzes (needs an authorized batch run).
3. Supabase tables and upload script; the daf picker.
4. Written shiur pane.
5. Glossary pages, once the master glossary has a first reviewed batch.
6. The WebView bundle for iOS and Android.
7. Daf image synced by line: per-amud layout JSON in Supabase, the current section highlighted on
   the page, tap the page to move the outline (and, in the apps, the audio). **Working in the
   prototype since 2026-09-28** (layouts carried in each daf's data file); Supabase and the apps
   remain.
