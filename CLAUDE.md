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
  dedication-form.html       # Standalone admin tool for submitting/editing dedication rows
  dedication-app-targeting-migration.sql  # One-time Supabase migration (run manually in SQL editor)
```

## Daf Processor (`AnyDaf/daf-processor/`)

**This is the canonical daf-processor.** Do NOT use `old-dp/` (a retired copy kept for reference only).

**Anthropic API usage policy — always follow:**
- **Never run `main.py` (or anything else that calls the Anthropic API) without first getting explicit authorization from the user for that specific run.** State what will run (which dafs/passes) and roughly how many API calls that means before starting.
- **Default to the Batch API, not `--no-batch`.** Batch mode gets a 50% cost discount; only use `--no-batch` (direct/synchronous calls) when the user has explicitly said they need faster turnaround for that run and has accepted paying full price for it. Don't default to `--no-batch` just because it's easier to monitor progress.

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

**Open, deferred — micro-segment thematic grouping can override chronology (2026-07-31).**
`repair_segmentation()` already guards against this at the macro level (item 4 above), but
found a micro-level instance on Bava Batra 84: the "*im hayah pikeach, socher es mekoman*"
mishna clause was spoken at 28:08, inside "Meshicha Rule"'s own window (26:48–28:49) — well
before "Flax Hagbaha" (28:49) and "Attached Items" (28:59) — but segmentation assigned it to
"Attached Items" anyway (its generated micro-title literally reads "...Smart Buyer Can Rent
Space for Alternative Kinyan," grouping it with "attached items" as a shared theme). Pass 2
then wrote it in that position, faithfully following segmentation's order — pass 2 is not at
fault here, unlike the aggada-scoping gap above. Confirmed against both the SRT and the
Mishna's own text (this clause is textually part of the *first* teaching, before the
separate flax teaching begins), so this wasn't a borderline call. User-assessed as minor and
not worth chasing alone; noted here in case a pattern shows up across more dafim later.

**Pass 2 — Rewrite** (Sonnet): raw SRT text + segmentation JSON → `02_rewrite.md`
- Prompt: `rewrite_prompt()`. Produces a written essay; inline Aramaic is translated to English.

**Pass 2.5 — Cleanup** (Sonnet): `02_rewrite.md` → `025_cleanup.md`
- Prompt: `cleanup_prompt()`. Preserves Aramaic direct quotes hidden in HTML comments; strips inline re-citations and other artifacts. This output feeds pass 3.

**Pass 3 — Source Insertion** (Sonnet — see model-choice note below): `025_cleanup.md` + Sefaria text → `03_final.md`
- Prompt: `source_insertion_prompt()`. Inserts Sefaria Hebrew/Aramaic + English translation blockquotes after each `##` macro header where relevant. Strips the HTML comments from pass 2.5.
- Fetches (and caches) three Sefaria texts: current daf, b-side of preceding daf, a-side of following daf — all three are passed as context so the insertion model knows where the daf begins and ends.
- Skips gracefully if Sefaria text is unavailable.
- Uses `025_cleanup.md` if it exists; falls back to `02_rewrite.md`.
- **Why Sonnet, not Haiku:** Haiku unreliably preserved `##`/`###` document structure on dense, quote-heavy dafs (silently merging or fabricating headings) — on a 10-daf test set Sonnet was 10/10 clean where Haiku was 5/10. `SOURCE_INSERTION_MODEL` in `config.py` was switched accordingly.
- **Structure/bold audit runs automatically after pass 3** — see below.

**Amud B Detection** (local, no API): runs after all passes via `find_amud_b.process_dir()`
- Reads `01_segmentation.json` and `sefaria.md`/`03_final.md` to locate the amud B boundary
- Writes `amud_b_segment_index`, `amud_b_timestamp`, `amud_b_micro_title` into `01_segmentation.json`
- Runs with `force=True` so it always re-detects (the segmentation may have been repaired)

### Section headers are deliberately `display_title`, not `title` — and why

**Read this before "fixing" short or truncated `##`/`###` headers.** They are short on purpose.

Each macro/micro segment in `01_segmentation.json` carries two labels from pass 1:

| Field | Length | Used for |
|---|---|---|
| `title` | unlimited | full descriptive title (pass 1 output; largely unused downstream) |
| `display_title` | ≤25 chars | **navigation pill in the app AND the `##`/`###` header in the essay** |

The essay header and the nav pill must be the *same string* so a user tapping a pill lands
on a heading they recognise. That correspondence is enforced **after pass 2**, not by it:

| Script | What it does |
|---|---|
| `apply_display_titles.py` | Overwrites `##`/`###` headings in `02_rewrite.md` and `03_final.md` with `display_title` values, **matched by position**. This is why 2,356 of 2,359 dafim have short headers. |
| `sync_md_headers.py` | Propagates `display_title` *renames* into the `.md` files by targeted search-and-replace (safer than positional matching when the segmentation was re-run after the `.md` was generated) |
| `check_segmentation.py --fix` | Repairs duplicate/near-duplicate `display_title`s in the JSON (appends " (II)", " (III)") |
| `fix_h2_mismatch.py` | Demotes excess `##` headings to `###` when a daf has more `##` than macro segments |

`rewrite_prompt()` also tells pass 2 to use `display_title` directly, so the essay is right
the first time; `apply_display_titles.py` remains the corpus-wide normaliser. **The prompt
previously referenced a `heading_title` field that exists in 0 of 2,359 segmentations** —
pass 2 then guessed between `title` and `display_title`, which is harmless only because
`apply_display_titles.py` overwrites the result. Fixed to name the real field.

**Known open defect — mid-word truncation.** `pipeline.py`'s `_truncate_display_title()`
hard-cuts anything over 25 chars at character 24 and appends "…", producing headers like
`Arevim: Concept & Obliga…`. As of 2026-07-29 this affects **2,131 of 98,885 display_titles
(2.2%) across 752 dafim** (worst: `avodah_zarah_36` 26, `sotah_3` 24, `bekhorot_22` 20).
The fix is to regenerate a clean ≤25-char label from the segment's full `title` rather than
chopping — not to lengthen the headers, which would break pill↔header correspondence.

**Gotcha:** re-running pass 2 on a daf *after* `apply_display_titles.py` has run reverts
that daf to whatever pass 2 wrote, silently breaking the correspondence. Re-run
`apply_display_titles.py` for any daf whose `02_rewrite.md` is regenerated.

### Pass 3 prompt reliability — two known failure modes, both fixed

Pass 3 juggles several sub-tasks in one call (insert blockquotes, preserve every `##`/`###` heading verbatim, strip HTML comments, preserve Sefaria's own `**bold**` markup, and produce nothing but the final document). Two silent-failure modes were found and fixed via `prompts.py`:

1. **Reasoning-preamble leak.** The prompt walks the model through 4 internal "STEP" labels (Alignment, Insertion, Comment Removal, Verification) as a private reasoning scaffold — but nothing told the model these labels and any narration around them shouldn't appear in the actual response. On some dafs the model echoed its own step-by-step analysis (`# STEP 1: ALIGNMENT`, "I will now insert Sefaria blockquotes...", etc.) as literal leading text in `03_final.md` — the "Claude talking to itself" artifact. Found live on 12 already-processed dafs (not just the one reported), 8 of them already uploaded to production Supabase. **Fix:** the prompt now states up front and again right before the essay input that the response must contain nothing but the final document, starting directly with its own first heading — no step labels, no narration.

2. **Bold-markup drop.** Sefaria's source text (`sefaria.md`) already carries `**bold**` markup distinguishing literal Talmudic words (bold) from Sefaria's own interpolated Rashi-style clarifications (plain) — this is what drives the amber highlighting in Shiur mode (`ShiurTextView.swift`'s `translationAttributedString`). The old prompt phrased this as "translation... with **bold** for Talmudic source text," which invited the model to *re-derive* the bolding rather than copy it verbatim, and it sometimes dropped it entirely while transcribing. Found on ~250 of 2,362 processed dafs (54 with zero bold anywhere in the daf). Text mode was unaffected because it renders Sefaria's translation live from the API, not from `03_final.md`. **Fix:** the prompt now explicitly instructs verbatim character-for-character preservation of the `**` markers from the source Sefaria segment.

Both fixes were verified on random samples to not regress the other (a random 18-daf sample, not pre-selected for known defects, came back 18/18 genuinely defect-free on both headings and bold markup after the fix — the 2 flags the audit script raised on that sample were both confirmed false positives of the pattern below).

### check_anchor_section_mismatch.py — free local pass-3 audit, wired into the pipeline

Runs automatically after pass 3 for every processed daf (`pipeline.py`, gated on `_should_run(3)`, after the amud-B-detection loop) — purely local text comparison, no API cost, logs a `WARNING` with flag count for anything suspicious or an `INFO` "clean" line otherwise. Can also be run standalone: `python check_anchor_section_mismatch.py [output/some_daf ...]` (defaults to the whole corpus).

**Rewritten (2026-07-22) to check actual content instead of structural presence.** The original version compared *structure* only — does this section have an HTML-comment anchor in `025_cleanup.md`, does it have a blockquote in `03_final.md`. That heuristic had two well-documented false-positive modes, both arising because it can't tell "several sections legitimately share one blockquote" or "one long passage legitimately splits across many headers with no anchor of their own" (both correct, prompt-instructed behavior) apart from a real bug. On the Hullin batch this produced 10-30 flags per daf on the large majority of dafs — noise, not signal. Replaced with real text-matching against the actual Sefaria source, reusing `find_sefaria_indices.py`'s parsing/matching (`parse_sefaria_items`, `match_hebrew`, `strip_nikud`). Result on the same Hullin batch: 113 dafs checked, 41 flagged, 58 total flags — the large majority of remaining noise is now concentrated in one still-imperfect category (see below) rather than spread across nearly every daf.

Checks:
- **Content fidelity** (`check_content_fidelity`) — every blockquote's Hebrew/Aramaic text is matched against a combined, ordered pool built from `sefaria_prev.md` + `sefaria.md` + `sefaria_next.md`:
  - `FABRICATED` — blockquote text not found anywhere in the source pool. No known false-positive mode.
  - `DUPLICATE` — two blockquotes share a long *contiguous* run of text (measured via `difflib.SequenceMatcher.find_longest_match`, as a fraction of the shorter blockquote's length — **not** a simple prefix/suffix or aggregate-similarity check, both of which false-positived on Talmudic text's formulaic parallel clauses, e.g. "three log of water minus a kortov, into which fell a kortov of *wine*..." vs "...of *milk*..." shares a long template but is a genuinely different ruling). Caught a real bug this way: Hullin 126 quotes the exact same passage verbatim under two different headers ("Daf & Opening" and "Bed Ropes & Lattice") — not yet fixed as of this writing.
  - `OUT OF ORDER` — a blockquote matches an earlier position in the source pool than the previous blockquote did. **Residual false-positive mode**: the Gemara itself sometimes makes a deliberate backward cross-reference to an earlier Mishna (confirmed case: Sefaria's own translation says "the mishna stated (89b)" for text discussing something ~80 daf-segments earlier) — a faithful shiur legitimately follows that same non-linear structure, and this check can't distinguish that from a genuine reordering bug using text position alone. This is the majority of remaining flags (43 of 58 in the Hullin batch) — spot-check the source Sefaria text around the flagged passage before concluding it's a real defect.
- **Heading structure** — heading text + order comparison against `025_cleanup.md` (or `02_rewrite.md` for older, pre-pass-2.5 dafs). Catches dropped/merged/reordered headings. No known false-positive mode.
- **Missing bold markup** — flags any blockquote whose Translation line has zero `**` spans. No known false-positive mode.

Only `OUT OF ORDER` still needs a skeptical read; the other four flag types (`FABRICATED`, `DUPLICATE`, header structure, bold markup) can be trusted directly.

### Approach B — Sefaria-first assembly, replacing passes 2.5 and 3 (prototype, 2026-07-29)

**Status: candidate is `prototype_text_first_v9.py`, under human review. Not yet wired into
`pipeline.py`. Nothing uploaded.**

**The problem it solves.** Pass 3 asks an LLM to reproduce the whole essay while inserting
Sefaria blockquotes. LLMs are unreliable at lossless reproduction under volume, so text
silently vanishes: measured across the 200 dafim that have all three files, **24 (12%) lose
entire `##`/`###` sections between pass 2 and pass 3** (pass 2.5 loses none — pass 3 is
where it happens). On a 5-daf sample pass 3 carried only **55% of the daf's Sefaria
segments**; the same dafim assembled by B carried **77%**, with commentary retention at
100% versus A's 99%.

**The inversion.** Instead of inserting Sefaria text into the essay, make the Sefaria text
the backbone and splice the essay's sections into it. The Gemara is then copied verbatim by
Python string slicing and *cannot* be dropped or fabricated. Both invariants are asserted
numerically before any file is written:
  - every essay section emitted exactly once, in document order
  - every in-span Sefaria segment emitted exactly once, in text order

**Why it costs nothing.** Placement needs no LLM because three sequences are already
time-indexed: the SRT carries timestamps, pass 1 timestamps every essay section, and the
SRT itself contains the Hebrew the lecturer reads aloud — so "when was segment N recited"
is local text matching, not comprehension. A full corpus run is ~5 minutes and $0. Pass 2
(Sonnet) still runs; **2.5 and 3 disappear entirely** (2.5 exists only to plant HTML-comment
anchors for 3, and only 201 of 2,363 dafim ever had it).

**Pass 2's drops mostly stop mattering.** Of 24 confirmed pass-2 drops examined, **23 (96%)
are Gemara recitation that B restores verbatim from Sefaria**. Only dropped *analysis* stays
lost. `check_pass2_coverage.py` remains the detector for that residue — it is the one piece
of the old repair machinery still worth keeping (`fix_pass2_gaps.py` is superseded).

**Version lineage — each step came from a specific reported defect. Do not "simplify" these
away; every one is a fix for something a reader actually hit:**

| Version | Fix |
|---|---|
| v3 | Pool `sefaria_prev`/`sefaria.md`/`sefaria_next` into one index space — a shiur routinely runs past its own daf (Sanhedrin 6b continues into 7a; 10 of its 11 "missing" passages were there). Replace greedy forward matching with best-match-per-segment + longest chronologically-consistent run — one bad early guess had truncated 82% of bekhorot_10 |
| v4 | Emit `heading -> Gemara -> commentary`, not `Gemara -> heading -> commentary`. Also fixes the downstream parser contract, since `upload_to_supabase.py` expects the blockquote right after the heading |
| v5 | Assign segments to sections by monotonic DP over content agreement, replacing timestamp windows — pass 1's micro timestamps are approximate topic markers (two adjacent ones 8 seconds apart covering minutes of material) |
| v6 | Never split a block mid-sentence; prefer starting a block at Sefaria's own `§` topic marker |
| v7/v8 | Lateness penalty (place a passage where its discussion *starts*). **Rejected** — fixed Berakhot 31b's header-traversal problem but pulled unrelated Gemara into Gittin 18b's opening and stripped its tail |
| v9 | v6 + the colon fix. |
| **v10** | **v9 + three fixes from human review of Bava Batra 174/153/103. The candidate.** See "v10 fixes" below. |

**Two calibration decisions, both from human review:**
- **v9 over v8.** Reviewer rated v6 "almost perfect" on halakhic Gittin 18b and 90-95% on
  aggadic Berakhot 31b with "not so noticeable" misses. v7's traversal fix was a bonus on
  aggada that cost real damage on halakha. Aggadic dafim carry little lecture content
  anyway, so v9 is the right trade.
- **No auto-selector exists.** Four separate metrics all ranked Gittin-v6 *worse* than
  Berakhot-v6 — the opposite of the reviewer's judgment. Content-overlap scores do not track
  reading experience. Do not build a per-daf v6/v8 switch without many more labelled
  examples.

**v10 fixes (2026-07-29/30), each calibrated against a corpus sample before shipping — do
not re-tune these thresholds without recalibrating the same way:**

- **Guarded search, `guarded_consistent_run()`.** `longest_consistent_run()`'s LIS only
  enforces non-decreasing time; nothing stops one isolated, marginal-score match at a much
  later INDEX from becoming `span_end`/`span_start` and dragging every unrecited segment
  between it and the true boundary into the essay (assembly emits the full span,
  matched or not). A transition jumping more than `JUMP_GAP=3` indices without clearing
  `HIGH_CONFIDENCE=0.85` is now unreachable in the search itself, not filtered from its
  output after the fact — the distinction matters: a post-hoc filter tried first and lost
  Bava Batra 103's own mishna text as collateral damage, because it could only delete from
  whichever chain the plain LIS's tie-break happened to pick, not recover the one it
  discarded. Fixed: BB174's 22-segment drift into the next daf's mishna; BB153's
  three-way identical-timestamp tie (physically impossible — one lecturer can't recite
  three passages simultaneously). Symmetric: also trims spurious opening matches into the
  *previous* daf (found on Yevamot 33, Zevachim 29 — unreviewed, flag if you get to them).
- **Singleton rescue, `rescue_homeless_singletons()`.** A section whose entire block is
  one segment scoring both LOW (`LOW_SCORE_FLOOR=0.45`) and AMBIGUOUS
  (`LOW_MARGIN_FLOOR=0.01` ahead of the runner-up) merges onto whichever section already
  owns the segment before it, rather than sitting under whatever heading won a
  near-coin-flip. Either signal alone is common even on CORRECT placements (11-26% of all
  singleton sections in a 180-daf sample) — neighboring sections in a continuous sugya
  share vocabulary — so only their conjunction (~2.6%) is used. Fixed: BB174's Rabban
  Shimon ben Gamliel aside, previously stranded under "Level 5" though the essay never
  discusses it there; now correctly lands as a coda to the Mishna material it actually
  glosses.
- **Head extension, `extend_head_to_confident_neighbor()`.** `span_start` pulls back by
  one segment if excluded only because it was paraphrased in English rather than recited
  (scores just under `DEFAULT_THRESHOLD`), provided the CURRENT opening is itself
  near-certain (`HEAD_ANCHOR_CONFIDENCE=0.90`) and the excluded neighbor still clears
  `HEAD_NEIGHBOR_FLOOR=0.40` on its own. Fixed: BB103 opened mid-sentence at "*ein
  nimdadin imah*" because "*tnan hatam: hamakdish sadeihu...*" scored 0.41 (explained in
  English, not recited) one segment before a 1.00 match. **Deliberately head-only** — a
  180-daf sample found tail candidates (`span_end+1`) at 2-3x the head rate with no
  signal yet to distinguish a real recitation from an echo of the fabricated-tail problem
  the guarded search exists to reject. Do not add the symmetric tail rule without that
  signal; it risks re-opening exactly what the guard fixed.

Full corpus diagnose (`--all --diagnose`, ~2:30, no files written) confirmed 0 completeness
assertion failures across all 2,343 processable dafim after each of the three fixes above.

**Tried and rejected: "section opening sentence" bonus (2026-07-30).** Motivated by a BB174
case where a section opens with Gemara that actually belongs elsewhere ("no strong home,"
distinct from the singleton-rescue case above — this was a *confident* but wrong opening
match, not a weak/ambiguous one). Built a DP bonus rewarding a section's own opening
sentence for landing at the start of its block, calibrated on a corpus sample (restricting to
nearby misattachment, `|owner - section| <= 2`, to avoid the same long-range false-positive
trap v1 hit — see v1's entry above). Tested against 7 confirmed nearby-misattachment cases:
fixed only 1/7 (shabbat_61). Failed on its own motivating BB174 case (the essay's opening uses
transliterated Hebrew, e.g. "the *ibayu lehu*," while Sefaria's English translation uses
different words — zero word overlap, a blind spot no bonus tuning fixes) and was blocked
outright on sukkah_10 by the pre-existing `is_continuation` hard constraint (the candidate
segment has no terminal punctuation, so it's categorically barred from starting any block).

**Tried and rejected: transliteration matching + IDF word-rarity reweighting (2026-07-31).**
Motivated by BB84, where two Gemara blocks *confidently* open the wrong section (not a
near-tie, not weak/ambiguous — same "confident wrong opening" class as the case above, found
independently): `content_words_en()` overlap rewards generic recurring domain vocabulary
(buyer/seller/sale) over the section that actually discusses the quote, because that
section's own prose paraphrases it in different English words than Sefaria's translation.
Built two candidate signals:
- **Transliteration skeleton match** — compare the essay's own italicized Aramaic/Hebrew
  transliteration against each candidate segment's actual Hebrew (nikud-aware consonant
  skeleton, `SequenceMatcher` edit-distance ratio, essay-local stopwording for terms
  recurring across >2 sections of the same essay). This one **works** as a signal — cleanly
  separates the correct section from the wrong one on BB84's two confirmed cases (e.g. 0.82
  vs 0.68), and correctly stays neutral on BB174's `ibayu lehu` case (a genuine near-tie
  even under this signal, consistent with rejecting a fix there above).
- **IDF-weighted content overlap** (down-weight English words that recur across many of the
  essay's own sections) — tested alone, in isolation, across several thresholds: never
  recovers BB84's two confirmed cases. The two sections' prose just uses different English
  words for the same content; there's no rare-vs-common signal to rescue, because there's
  barely any shared vocabulary at all. Not a substitute for the transliteration signal —
  a different, weaker one that doesn't cover this failure mode.

**Both were rejected regardless**, because wiring either into `align_constrained`'s DP —
even gated to block-opening positions only, even behind a hard absolute-score floor —
destabilized dense, argumentative dafim (bava_metzia_11, niddah_60, berakhot_31b,
zevachim_29: 84%+ of section boundaries shifted) while barely moving clean narrative ones.
Root cause: the DP assigns one contiguous, *monotonic* block per section across the whole
span, so a single new signal anywhere can pull the globally-optimal partition everywhere
else, and dafim whose base content-word signal is already thin/ambiguous throughout are the
most exposed. Verified concretely on BB84 itself (the motivating daf): the gated version
fixed the 2 target cases but also broke a previously-correct placement (segments 15–18,
the wine/vinegar mishna text, pulled from "Consumer Preference" — where the essay literally
quotes that passage — into "Rabbi vs Rabbanan," which doesn't quote it at all).

Also surfaced, independent of the above and worth remembering on its own: `content_words_en()`
filters any word of length ≤3, which silently drops short-but-meaningful English words like
"red" and "sun" from every content-overlap comparison in the corpus, not just this case.

**Conclusion:** "confident wrong opening" (this case and the BB174 one above) is accepted as
inherent imprecision of word-overlap-based section assignment without semantic
comprehension — not fixed by v10, not scheduled for further work absent a new idea.
Reverted in full — constants, `section_opening_words()`, and the DP wiring — rather than
ship a fix with a 1/7 success rate. If revisited, the real blocker is scoring by English-word
overlap when the essay quotes Hebrew/transliteration directly — see the still-open "confident
wrong opening" problem this was meant to solve, and the transliteration-vs-Hebrew idea under
consideration as of 2026-07-31 (BB84 review).

**Two subtle bugs worth remembering:**
- **`:` is not a sentence terminator in Talmudic text** — it introduces quoted speech
  ("*amar leih:*" then the reply). Treating it as terminal split quotations from their
  speakers. 1.1% of segments.
- **`WINDOW_ENTRIES` was 40, spanning a median of 2.0 minutes.** Two minutes of the lecturer
  *reviewing* a sugya accumulates enough of its shared Hebrew vocabulary to "cover" segments
  never recited. On Bava Batra 174b, whose opening recaps the previous daf, five separate
  segments matched inside one minute (two at a perfect 1.00), putting six unrelated passages
  ahead of the lecturer's first words. Now 20 (~1 minute), which requires the tight burst
  that real recitation produces.

#### What must be re-pointed when B replaces pass 3 — DO NOT SKIP

Two post-pass-3 steps read `03_final.md` and **skip outright if it is missing**
(`find_amud_b.py:134`, `find_sefaria_indices.py:143`). They write the fields that drive the
amud A/B marker and the Text-view pill navigation, and both apps decode them
(`ShiurClient.swift:93-96`, `ShiurClient.kt`). Dropping pass 3 without re-pointing these
silently removes both features:

| Script | Writes | Feature it powers |
|---|---|---|
| `find_amud_b.py` | `amud_b_segment_index`, `amud_b_timestamp`, `amud_b_micro_title` | the A/B marker in Shiur mode |
| `find_sefaria_indices.py` | `sefaria_index` per macro, `amud_b_sefaria_index` | Text-view segment pills + Shiur↔Text position sync |

**Verified 2026-07-29: both run correctly against B's output with no code change** — only
the input filename differs. This works because v4 made B emit `heading -> blockquote`, the
same shape these parsers expect. Tested on gittin_18, hullin_88, bava_batra_174: all `OK`.

**`amud_b_sefaria_index` is unchanged** by the switch (16/10/15 under both) — it derives
from `sefaria.md`'s own amud-A count, not from the essay. **`amud_b_segment_index` does
shift** on some dafim (hullin_88: 4 → 6, gittin_18: 6 → 5) because it names the essay
*section* containing the boundary, and B places blockquotes differently. Expected, not a
regression — but spot-check the A/B marker on a familiar daf after the switch.

Full wiring checklist: (1) `find_amud_b.py` input, (2) `find_sefaria_indices.py` input,
(3) `upload_to_supabase.py`'s `final` source, (4) `pipeline.py` calls B instead of 2.5 + 3.

#### Corpus-wide run order when B goes live — strict sequence

No API cost at any step: everything below reads existing `02_rewrite.md` output.

| # | Step | Why it sits here |
|---|---|---|
| 0 | `apply_display_titles.py --rewrite-only --only daf-processor/title_pass_aligned.txt` | **Must precede v10.** v10 copies `02_rewrite.md` headings verbatim, so a stale `…` heading gets baked into the final |
| 1 | Back up `03_final.md` corpus-wide (`.bak_pass3`) | Step 3 overwrites 2,362 files |
| 2 | `prototype_text_first_v10.py --all` (~2:30) | Watch for `COMPLETENESS ASSERTION FAILED`; confirmed 0 across the full corpus as of 2026-07-30 |
| 3 | Promote `03_text_first_prototype_v10.md` → `03_final.md` | v10's filename is read by nothing downstream |
| 4 | `find_sefaria_indices.py` | order-independent of step 5 |
| 5 | `find_amud_b.py` | order-independent of step 4 |
| 6 | `upload_to_supabase.py` | |

The easy mistake is running v10 first because it looks like step 1. It is step 2, and getting
that wrong means redoing the whole corpus. (v9 is superseded — see "v10 fixes" above — do not
run v9 corpus-wide.)

**Exception: three dafim need pass 1 + pass 2 rerun FIRST, not just the v10 pass above.**
The corpus-wide steps above only touch `02_rewrite.md` onward — they cannot fix a source SRT
problem, since passes 1 and 2 already ran on the bad transcript. Before or separately from the
corpus-wide run:

| Daf | SRT problem | Status |
|---|---|---|
| Menachot 79 | 0 Hebrew characters — see "Menachot 79" section below | Author re-transcribing audio |
| Bava Batra 153 | Fabricated tail after the real ending ("let's go on to daf 154 amud bet...") | **Patched 2026-08-07** — SRT already fixed by the author; fabricated `## Found Document` macro section (heading + 3 sub-headings + prose) manually deleted from `02_rewrite.md` and `02_rewrite_wall_patched.md` in place of a full pass 1+2 rerun. Clean removal, no orphaned headings. Cleared for the normal corpus-wide v10 pass. |
| Bava Batra 174 | Same pattern — fabricated `והלכתא`/next-mishna tail | **Patched 2026-08-07** — same manual fix: fabricated `### Final Halakha & Shtar` section deleted from both essay files. Clean removal, no orphaned headings. Cleared for the normal corpus-wide v10 pass. |

Once each daf's SRT is fixed, that daf needs pass 1 (segmentation) + pass 2 (rewrite) rerun —
**both call the Anthropic API, requiring explicit authorization per the standing rule above**
(state which dafim/passes and the API call count before running) — followed by v10 on that
daf specifically. Don't fold these three into the corpus-wide v10 pass until their SRTs are
fixed; v10 already contains guards against exactly this failure mode (the guarded search
correctly excludes BB153/174's existing corrupted tails today), but starting from a corrected
SRT should also fix the underlying pass 1/2 content rather than just papering over it at the
matching stage.

BB153 and BB174 took a manual-patch shortcut instead of the full pass 1+2 rerun (same
philosophy as the Hullin 88 fix): since the downstream pipeline reads its section list from
`02_rewrite.md`'s own headings rather than asserting against `01_segmentation.json`, a clean
whole-section deletion is functionally equivalent to a rerun for everything that matters —
the only residual is stale, functionally-inert entries for the deleted titles left behind in
each daf's `01_segmentation.json`. Only Menachot 79 still needs the full SRT-fix +
pass 1+2 rerun before it can join the corpus-wide pass.

#### Post-run manual check: prev-daf-boundary drops (Hullin 88 class, found 2026-08-06)

`best_match_times`/`guarded_consistent_run` can silently drop a shiur's own opening when it
genuinely spans into the prior daf's amud b: prev-daf items scoring just under
`DEFAULT_THRESHOLD` (0.5) never enter the matched chain and vanish from v10's output, even
though pass 2's prose already covers them (it doesn't depend on v10's matching). Confirmed on
Hullin 88 — manually fixed in its `03_text_first_prototype_v10*.md` already — and, via a
corpus-wide dry-run scan (no API cost), 43 more dafim that would hit the identical pattern
once actually run through v10.

A structural fix (multi-step head-extension into `sefaria_prev.md`, gated on anchor confidence
+ time-consistency) was built and safety-tested 2026-08-06, then **rejected as a bad
cost/benefit and reverted** (not shipped, not in the current `prototype_text_first_v10.py`):
it only cleanly rescues 3 of these 44 dafim (Hullin 88, Pesachim 47, Shabbat 11), and a more
permissive version tested to reach further helped only ~12 more total while reintroducing the
same category of same-daf scope creep already caught and rejected once during that same
investigation. See git history on `prototype_text_first_v10.py` around that date if
reconsidering — the diff and reasoning (including two real bugs found and fixed in the
process, one of which is a latent same-daf timing bug in the *already-shipped* single-step
mechanism, `extend_head_to_confident_neighbor`, that was never actually fixed since the whole
feature was reverted) are fully documented there.

**Hand-patches to derived v10/wallpatched files do not survive pipeline reruns — this bit us
on Hullin 88 itself, 2026-08-07.** Hullin 88 was hand-patched (restored the missing opening
blockquote directly into `03_text_first_prototype_v10_wallpatched.md`) around 2026-08-02.
On 2026-08-06 the neighbor-aware wall-of-text fix (see below) was re-run on the 12-daf test
batch, which regenerates `02_rewrite_wall_patched.md` and then re-runs v10 assembly on it —
silently overwriting Hullin 88's hand-patched file and erasing the restored blockquote, with
no warning. It stayed missing through every subsequent rerun that touched that daf (the
`apply_moves.py` fix, the rescue-starved-headings pass) since nothing re-checks for it.
**Any rerun of `fix_wall_of_text.py`, `prototype_text_first_v10.py`, `apply_moves.py`, or
`relocate_run_all.py` on a daf will silently destroy a hand-patch previously applied to that
daf's derived output** — these scripts have no awareness that the file they're about to
overwrite contains a manual fix, and there is no diff/warning step. **Consequence: this check
must be the very last content-touching step for each daf, run only after every other pipeline
step has finished and nothing further will regenerate that daf's `03_text_first_prototype_v10*.md`
— never mid-batch, and re-verify/reapply after any later rerun that touches the same daf for
an unrelated reason** (as just happened here).

**Action once the full corpus-wide v10 run (step 2 above) completes**: manually check all 44
dafim's (43 below + Hullin 88, re-added since its earlier fix was lost) new v10 output for a
dropped opening (compare against the old `03_final.md`'s content or the SRT directly) and
hand-patch — restore the missing blockquote(s) at the correct position from the pre-v10 text —
**as the last step before promoting that daf to `03_final.md`/uploading**, per the fragility
note above. Re-running `find_amud_b.py --dry-run --force` and checking `shiur_starts_on_prev`
directly (see its 2026-08-06 investigation notes on why the stored `shiur_start_amud` field
itself undercounts ~4x) is a good starting point for re-deriving this list against the actual
post-run output rather than trusting this pre-run snapshot as exhaustive — it only checked a
5-item window per daf.

The 43 (plus Hullin 88, whose fix must be redone — see above):
bava_batra_172, bava_batra_88, bava_kamma_56, bava_metzia_18, bava_metzia_3, bava_metzia_63,
bava_metzia_7, bekhorot_51, hullin_135, hullin_39, hullin_47, hullin_73, kiddushin_28,
meilah_8, moed_katan_24, nazir_52, nazir_8, nedarim_8, nedarim_90, niddah_41, pesachim_110,
pesachim_47, pesachim_68, pesachim_89, rosh_hashanah_6, sanhedrin_67, sanhedrin_85, shabbat_11,
shekalim_14, sotah_16, sukkah_31, sukkah_51, yoma_3, yoma_59, zevachim_110, zevachim_18,
zevachim_20, zevachim_34, zevachim_45, zevachim_48, zevachim_77, zevachim_82, zevachim_83

A further ~213 dafim have a milder version of the same pattern (the matched chain already
reaches into `sefaria_prev.md` on its own, but with a smaller 1-2 item gap alongside) — lower
priority, not enumerated here; re-derive via the same near-miss scan if pursuing further.

#### Wall-patch placement drift (Gittin 18 class, investigated 2026-08-06 — no fix, closed)

`fix_wall_of_text.py`'s explanatory prose insertions can shift `align_constrained`'s placement
DP for OTHER, unrelated nearby items — not just the section being patched. Mechanism: the DP
scores placement mainly by word-overlap between an item and each candidate heading's own prose
(3:1 over timing); a prose insertion written to explain one topic by contrast with another (e.g.
"For Rav... For Shmuel, the reverse is true...") can pull in vocabulary from the topic it's
contrasting against, making that heading look like a false match for content that actually
belongs elsewhere. Confirmed on Gittin 18 (original report) and independently on Bava Batra 153
(Rav's own ruling pulled under a "Shmuel Position" heading whose new prose happened to restate
Rav's view for contrast).

`scan_wallpatch_placement_drift.py` (flag-only, zero API cost, kept in the repo) diffs
`align_constrained`'s plain-vs-wall-patched item→heading assignment. Run across the 12 dafim
with both variants: 29 placement changes total. Manually spot-checked 9 of those clusters — 5
were genuine improvements (the patch's new prose was a *better* match), 2 were confirmed
regressions of the above kind (Gittin 18, Bava Batra 153), 1 was a false alarm already corrected
downstream by `relocate_check.py`, 1 was ambiguous.

**Decision: not worth fixing.** On direct user review, the confirmed Bava Batra 153 regression
was "almost imperceptible from a user perspective." Given that and the small sample size, this
was closed without a structural fix or a shipped detector — `relocate_check.py`'s existing
quote-placement review already covers some of this class incidentally (it caught Gittin 18,
though only after a manual placement fix, so it's not confirmed to catch this class unaided).
Revisit only if a future review surfaces a case where the drift is actually user-visible; the
diagnostic script is already there to quantify it again on a fresh sample if needed.

#### Missing-preceding-heading-candidate class (architectural gap) — tracked instances, revisit for a targeted fix

**Running tracker, per user request 2026-08-07** — every confirmed case of the shared root
cause below, kept in one place so a future targeted-fix attempt has the full evidence base
instead of re-deriving it per daf. Do not close/delete this section when a new instance is
found; add a row.

| Daf | Heading / content | Never-offered heading | Disposition |
|---|---|---|---|
| Bava Metzia 11 | "Tosafot Question" (6-item run: Ravina's answer, a challenge, Rav Samma's answer, second *mai beinaihu*) | "Resolving Mai Beinaihu" (immediately preceding, emptied by round 1) | **Fixed** 2026-08-07 — caught by the starved-heading rescue (this instance happened to also be starved; see below) |
| Bava Batra 174 | "Rav Huna: Tzrari Issue" run | its immediately-preceding heading (emptied by round 1) | **Fixed** 2026-08-07 — also caught by the starved-heading rescue |
| Hullin 88 | אמר רב מרי quote, single-block run under "Rashi & Tosafot" | "Klal Tzarich l'Prat" (immediately preceding, NOT starved — keeps its own 4 quotes) | **Left as-is** — investigated, narrow "abutting" gate tried and rejected (89 false-positive matches across 12 dafim, see below), closed same disposition as Berakhot 31b |
| Sotah 16 | Rav Pappa's "supersedes and adds" quote, item 1 of a 4-item run under "Rabbi Akiva Hermeneutics" | "Shaving Metzora Adds" (immediately preceding, NOT starved — keeps its own 2 quotes) | **Fixed** 2026-08-07 — hand-patched split after manual content verification (Rav Pappa's quote is paraphrased almost verbatim in that heading's own prose); items 2-4 (Rav Ashi's own continuous statement) correctly stay at "Rabbi Akiva Hermeneutics" |

The first two rows are the "starved heading" sub-case, mechanically fixable because the
preceding heading's quote-count genuinely drops to zero — that's what `relocate_rescue_starved.py`
detects and fixes automatically, corpus-wide, no manual step needed. **The Hullin 88 and
Sotah 16 rows are the harder sub-case**: the preceding heading is never emptied (it keeps its
own quotes), so there's no zero-quotes signal to gate on — each one so far has needed a human
to read both headings' prose against the quote's actual content and judge it directly. Two of
these harder cases have now been found by manual review in just 18 dafim (Hullin 88, Sotah
16) — both hand-patchable once found, but with no cheap automated way to *find* them short of
reading every run's placement, which is what the 12+6-daf manual review batches were already
doing. Worth another look at a targeted fix once a few more instances accumulate, since two
data points confirmed both directions (Hullin 88: left as-is / Sotah 16: fixed) rather than
one clean story — see the abandoned "abutting" gate below for what's already been ruled out.

Same root architectural cause as the starved-heading fix (`build_windows()`'s static
per-window candidate list never offers a run its own immediately-preceding run's heading —
see relocate_rescue_starved.py's docstring). **Hullin 88** was the first non-starved instance
found: its אמר רב מרי quote (single-block run) sits directly under `### Rashi & Tosafot` with
zero prose before it, yet its content is the concluding answer to a challenge raised in the
*preceding* heading's ("Klal Tzarich l'Prat") own prose. relocate scored "Rashi & Tosafot" as
high-confidence correct — genuinely, since that heading's prose does discuss this quote — but
was structurally never offered "Klal Tzarich l'Prat" as an alternative to weigh it against.

**Investigated fix, rejected before spending any API budget on it.** The natural narrow gate
— "offer the previous run's heading as an extra candidate whenever the current run is a
single quote block landing immediately after its own heading, with no prose in between" —
was checked with a static (no-API) scan across the same 12-daf batch first. Result: **89
matches across 12 dafim**, not the handful expected. A single quote opening a heading with no
lead-in prose turns out to be the *normal* shape for a large fraction of sections in this
pipeline (a heading states its defining quote, then explains it) — not a rare tell specific to
the Hullin 88 case. Applied as literally scoped, this gate would have re-litigated nearly every
section boundary in the essay against its predecessor, i.e. it collapses into the general
"always offer neighboring headings" expansion already rejected once during the BM11
investigation for the same reason (unpredictable ripple effects, no longer a bounded search).
**Abandoned without running the dry run** — no fix shipped, `relocate_rescue_abutting.py` was
written, statically scanned, and then deleted rather than left as dead code. Hullin 88's Rav
Mari placement is left as-is, same disposition as Berakhot 31b's "Judging favorably" case:
known, understood, not fixed.

If revisited, the real blocker is the same one noted in the starved-heading section: telling
this case apart from the other 88 requires actually reading whether the *preceding* heading's
prose leaves a question open, which is exactly the judgment call an LLM check would need to
make per-candidate anyway — there's no cheap structural signal left to gate on short of that.

#### Wall-patch duplicate-content pileup (Bava Batra 84 class, fixed 2026-08-07)

A more severe variant of the drift above: `fix_wall_of_text.py` flags/patches sections by
raw-transcript TIME WINDOW, not topic. If the lecturer verbally previews an upcoming point
while still inside an earlier heading's time window, Stage A correctly says that content is
"missing" from that section's prose, and Stage B faithfully writes it in — duplicating
material a LATER heading already treats in full. On Bava Batra 84's "Resolution Vessels",
this duplicated paragraph made that heading's prose narrate the *entire* downstream arc,
so `relocate_check.py`'s split judge (correctly, given the corrupted prose) merged 5 quote
items under one heading — the exact pileup class `relocate_check.py` exists to prevent, just
caused by a corrupted essay rather than a placement-logic bug. The same signature (items
from multiple original headings pulled into one) was confirmed on 4 of the 12 test dafim,
worst on Bava Metzia 11 (9-item merge).

**Fix shipped:** `fix_wall_of_text.py`'s Stage A and Stage B prompts now receive the
previous/next section's prose as context, with an explicit rule not to flag or duplicate
content a neighboring section already covers in full — at most a brief one-clause
forward/backward reference. Re-run on the 12 test dafim: BB 84's and BM 11's pileups are
gone (BB 84 now cleanly splits 2/3 across the right two headings); the fix reproduces the
same placement `relocate_check.py` already made on the never-patched plain baseline for the
one adjacent-heading judgment call left in BB 84, so it isn't inventing new behavior. One
side effect: Niddah 60's marker-gated 3-way split (see above) no longer fires on the same
window because the cleaner prose lets ordinary placement get it right without the special
case — verified the resulting output is still correct, just reached via a different path.
Promoted to the canonical `02_rewrite_wall_patched.md` / `03_text_first_prototype_v10_wallpatched.md`
for all 12 test dafim; will apply automatically to the corpus-wide run.

#### `apply_moves.py` inserted relocated content at the WRONG position (found+fixed 2026-08-07)

Found while re-reviewing Bava Batra 174 after the fix above: under "Amoraim Debate: Labels",
Rav Chisda's and Rava's quotes appeared BEFORE the dilemma + Rabbi Yitzchak's resolution,
reversing their true order in the daf (the dilemma/resolution have a lower pool index — they
were the tail of "Rav Huna: Language Test", moved forward into this heading by a `split`).
Root cause: `move_subrun()` always spliced relocated content at the fixed END-of-heading
insert point, with no regard for where it belongs relative to that heading's own untouched
native content. This is not new to this session's work — it's been live since `split`
support was added — and it isn't cosmetic: it silently reorders which Gemara text a reader
sees first whenever a moved sub-run has a lower pool index than content already sitting at
its target heading, which is inherent to how splits work (the moved half is, by definition,
adjacent to the boundary with the neighboring heading).

**Fix shipped:** `apply()` now interleaves every insertion by original pool/block index
against the target heading's surviving native content, instead of always appending at the
end (see the docstring on `apply()` for the mechanism). Re-ran move application for all 12
test dafim: **every single one** changed output (confirmed via `git diff`), meaning this bug
was silently misordering content across the entire test batch, not just Bava Batra 174.
Verified no content was lost or duplicated anywhere: quote-block count in the final
relocated output matches the raw (pre-relocate) v10 file exactly, daf by daf. Given this
touched all 12 already-reviewed dafim (not just the ones patched by the wall-of-text fix
above), **the 4 previously-reviewed dafim (Nazir 59, Niddah 60, Hullin 88, Gittin 18) are
worth a fresh look**, superseding the earlier "no need to re-review" guidance, which
predates this fix.

#### Starved-heading rescue: `build_windows()` candidates are computed from a stale snapshot (found+fixed 2026-08-07)

Found while reviewing Bava Metzia 11's "Tosafot Question": 6 quote items (Ravina's answer,
a challenge, Rav Samma's competing answer, and the second *mai beinaihu* distinguishing
them) sat under "Tosafot Question" — an unrelated heading about a completely different
question — instead of "Resolving Mai Beinaihu", the heading immediately before it whose own
prose is precisely what these items answer.

Root cause, confirmed against the raw transcript and the relocate JSON directly:
`build_windows()`/`quote_runs()` compute every window's candidate list ONCE, upfront, from
the static v10 assembly, before any relocate verdict exists. "Resolving Mai Beinaihu"
originally owned exactly one quote-run (a single item restating the *chatzer*/*shlichus*
puzzle) — round 1 correctly relocated that lone item away to "Ein Shaliach Aveirah" (8
headings earlier, where the puzzle is first posed), which is a defensible call in isolation
but empties "Resolving Mai Beinaihu" of quotes entirely. The very next window (the 6-item
run) was never offered "Resolving Mai Beinaihu" as a candidate in the first place — by
construction, `build_windows()` never offers a run's own immediately-preceding heading,
since that heading owns the "previous run" that bounds the search — so it had nowhere to go
but the only other option, "Tosafot Question". Two compounding gaps: relocate judges each
quote-run in total isolation with no model of "this is the direct continuation of the
previous run's content", and `build_windows()`'s candidate snapshot never gets revisited in
light of round 1's own moves.

A broader fix (always offer a run's preceding heading, or merge pool-adjacent runs across a
heading boundary into one combined decision) was considered and explicitly rejected as too
large a blast-radius change for this stage — pool-adjacency across a heading boundary is the
*normal* case throughout the corpus, so either approach would reopen the search space
almost everywhere, not just here.

**Fix shipped — narrow and evidence-gated only:** a second relocate pass
(`relocate_rescue_starved.py`, wired into `relocate_run_all.py` via `apply_rescue_pass()`,
runs automatically as part of every relocate pass including the corpus-wide one). A heading
H counts as **starved** only if it natively owned at least one quote-run in the original v10
assembly AND ends up with zero quote blocks after round 1's confidence-gated moves are
applied — a heading that simply never had any quotes to begin with (e.g. BM11's "Two Reasons
Explained", which sits between "Ein Shaliach Aveirah" and "Mai Beinaihu" but was never a
`current_heading` for any run) does **not** qualify; there's no before/after transition to
detect. For each starved H, the one window whose own current heading is the very next h3
after H (no other h3 in between) gets a round-2 re-check with H added as an extra candidate;
round 2's verdict always wins over round 1's once it exists (same candidates plus one more,
so it's strictly better-informed).

Dry-run across the 12 test dafim: 19 starved-heading rescue opportunities found, only **2**
actually changed the verdict (Bava Metzia 11's "Tosafot Question" run and Bava Batra 174's
"Rav Huna: Tzrari Issue" run, both moving to the heading immediately before them where they
belong) — the other 17 confirmed the existing placement even with the new option on the
table, evidence the mechanism doesn't over-fire. Both changes reviewed directly by the user
and confirmed correct; applied to the canonical `bava_batra_174`/`bava_metzia_11`
`_wallpatched_split.json` and `_wallpatched_split_relocated.md`. Verified no content lost:
quote-block count in the final output matches the raw v10 file exactly for both.

**Known, explicitly out of scope:** this does not fully solve "keep one continuous Gemara
exchange together" — in the BM11 case, the single item that started the whole chain (the
*chatzer*/*shlichus* puzzle, relocated to "Ein Shaliach Aveirah") is still separated from its
own direct answer (the rescued 6-item run, now at "Resolving Mai Beinaihu") by one heading's
distance, just less badly than before. A more complete fix (evaluating pool-adjacent runs as
one combined decision, gated on the preceding run being suspiciously small) was scoped and
deliberately deferred — same blast-radius concern as above, not validated.

#### Pass 2 self-invents a "see above" placeholder for a duplicate heading (found 2026-08-07, corpus-wide scan done, not yet fixed)

Found reviewing the 6-daf pre-corpus validation batch: `avodah_zarah_17`'s `02_rewrite.md` has
"Proverbs Interpretation", "Physical Contact Rules", and "Leech's Daughters" each written out
in FULL, correctly, in their right structural position — and then a second time, much later
(right after "Elazar Durdaya", before "Crossroads Story"), as bare empty `## ` headings whose
only content is a self-invented placeholder line: `*(continued — see above)*`. That exact
phrase appears nowhere in any prompt in this codebase (checked) — the model invents it live.

**Confirmed origin: Pass 2 (the essay-rewrite pass) itself**, upstream of everything else —
present already in `025_cleanup.md` (pass 2.5's own output, which reads pass 2's output as
input), so wall-of-text/v10/relocate all just passed it through unchanged. Checked and ruled
out a chronological-ordering-confusion theory (segmentation's macro timestamps are in perfect
order, no inversion) using the actual segmentation data rather than assuming. The likely
(not fully certain) trigger: "Rabbi's Reflection", the section immediately before the
duplicate block, makes a genuine backward textual cross-reference ("the gemara connects the
bas kol's answer to the earlier question: what about Rav Padat's position...") — Pass 2 may
be trying to also mark that callback structurally by resurfacing the referenced heading, even
though it has no new content to add there. Doesn't fully explain the pattern on its own
("Woman's Confession" gets the same kind of callback in that same sentence and wasn't
duplicated) — likely compounded by ordinary long-generation drift on an 11-macro/40-micro daf.

**Corpus-wide scan (mechanical, zero API cost, run over all ~2,364 `02_rewrite.md` files):**
21 dafim have some exact-duplicate `## ` title. Splitting that by what it actually is:
- **13 are `(II)`/`(III)`-suffixed titles** (e.g. `bava_batra_39`'s "Two vs Three Witness
  (II)") — a separate, already-documented, likely-intentional convention (see the 161-daf
  "(II)"-style part-number note under "Corpus reprocessing status" below). Not this bug.
- **4 have a substantial, comparable-or-larger second occurrence** (`sanhedrin_85`,
  `sanhedrin_40`, `niddah_44`, `zevachim_67`) — almost certainly two genuinely different
  passages that happened to share a short auto-generated title, not a defect. Left alone.
- **4 match this bug cleanly** — second occurrence is a near-empty, differently-worded
  self-invented "see above" note each time (confirming it's not a fixed template):
  `avodah_zarah_17` (3 duplicates), `berakhot_39` (2: "Blessing Priority", "Processing
  Vegetables"), `menachot_20` (2: "Blood Question", "Ashbanat Tamei"), `sanhedrin_72` (1:
  "Mishnah Teaching"). Mechanical fix is safe for all of these — delete the empty duplicate
  block (heading + placeholder + divider), zero content loss since the real material already
  exists correctly earlier in the essay.
- **1 borderline case**: `bava_metzia_77`'s "Mid-Job Departure" duplicate (308 chars) has one
  real, new sentence (a ruling) mixed in with the pattern — needs a manual look, not a blind
  mechanical delete.

**Not yet fixed** — found late in the 6-daf validation review, flagged here so it isn't lost
before the corpus-wide push. Detection recipe for re-deriving this list if `02_rewrite.md`
changes: for each daf, find `## ` titles appearing more than once (excluding `(II)`/`(III)`
suffixes), split the essay on H2 boundaries, and flag any duplicate whose LATER occurrence is
under ~350 characters — that threshold cleanly separated the 5 genuine hits from the 4
false-positive "different content, same title" cases in this scan.

#### "Hadran" item swallow bug — `ITEM_RE` boundary failure on empty-translation Sefaria items (found+fixed 2026-08-07, corpus-wide)

Found on Meilah 8: the essay's first inserted quote was the chapter-closing "*Hadran*"
formula (הדרן עלך קדשי קדשים) with a garbled `**Translation:** **3.**` followed by bare,
un-blockquoted raw markdown dumped into the essay body — the literal next Sefaria item's
`**N.**` label, its Hebrew, and its real translation, all mis-attributed as if they were the
Hadran line's own translation. The real content that got swallowed (the Chatas Ha'of Mishna)
was, as a result, unavailable as its own quotable pool item at all — not just cosmetically
garbled, a genuine content-availability loss.

**Root cause**, confirmed by testing the regex directly against real data: `ITEM_RE` in
`prototype_text_first.py` (the shared parser `build_pool()` in `prototype_text_first_v3.py`
uses to read `sefaria.md`/`sefaria_prev.md`/`sefaria_next.md` back into matchable items) used
`\s*(.+?)` for the translation group — `\s*` also matches newlines, and `.+?` requires at
least one character. Sefaria genuinely has no English translation for some items — chapter
boundary markers like "Hadran" aren't organic Talmudic text, so Sefaria's own translation
field is empty for them (confirmed: `sefaria.md` itself is correct/faithful here, this is a
pure parsing bug, not a data problem). Faced with a zero-length translation, the greedy `\s*`
ate past the intended boundary (the blank line before the next item), and the one-or-more
group was then forced to consume the ENTIRE next item searching for the next `\n\n**`
boundary, silently merging two pool items into one garbage-translation entry.

**Fix shipped**: `ITEM_RE` changed from `\*Hebrew/Aramaic:\*\s*(.+?)\n\*Translation:\*\s*(.+?)(?=\n\n\*\*\d|\Z)`
to `\*Hebrew/Aramaic:\*[ \t]*(.+?)\n\*Translation:\*[ \t]*(.*?)(?=\n\n\*\*\d|\Z)` — `[ \t]*`
(not `\s*`) keeps each label's own line separate from the next, and `(.*?)` (zero-or-more,
not one-or-more) lets a genuinely empty translation match zero characters instead of forcing
a search past the boundary. Verified directly against Meilah 8's real data (old regex: 5
items parsed for amud a, missing one; new regex: 6, correct) and regression-checked against a
random 60-file sample from the corpus: 0 regressions (byte-identical output on every
unaffected file), 3 files correctly recovered a previously-swallowed item.

**Corpus-wide scope, scanned (zero API cost — a static regex scan, not a rerun)**: **416
`sefaria*.md` files / 420 items** across the corpus hit the empty-translation case that
triggers this. Of the 18 dafim already manually reviewed this session, 4 have it in their
pool (`bava_batra_103`, `hullin_88`, `sanhedrin_67`, `meilah_8`) — checked each with the
fixed parser for whether the swallowed item actually got matched into that daf's essay (only
that has visible impact): only **Meilah 8**'s did; the essay has been regenerated and
verified clean (no content lost, `raw==final` quote-block count). The other three have the
same pool-level corruption but the transcript never happened to match onto that specific
item, so nothing was visibly wrong — no action needed for those, and the fix already protects
any future rerun.

**Permanent safety net added** (`prototype_text_first_v10.py`, right after `build_pool()`):
an assertion that no pool item's translation contains the literal strings
`*Hebrew/Aramaic:*` or `*Translation:*` — the unambiguous signature of this corruption class
recurring in any form, on any daf, for any reason, without needing a human to spot a garbled
blockquote. Verified it doesn't false-positive: ran in `--diagnose` mode (no API cost) against
4 more affected-but-unprocessed dafim (`gittin_31`, `yevamot_66b`, `sotah_14`, `zevachim_47`)
— all clean with the fix in place.

**What's still needed before the corpus-wide push**: the 416-file prevalence count is a
*pre-run* (pool-level) scan — it can't yet say how many of those items will actually get
matched into a final essay, since that depends on `best_match_times()`'s per-daf transcript
matching, not just presence in the pool. Re-run the same "was the empty-translation item's
Hebrew found in the essay" check (used above for the 4 reviewed dafim) against the full
corpus **after** the real corpus-wide v10 run completes — same "post-run manual check"
pattern already used for the Hullin-88-class prev-daf-boundary drops. Given the safety net is
now in place, this post-run check only needs to look for *cosmetic* follow-up (e.g. whether a
correctly-empty `**Translation:**` line reads oddly to an end user in the app) rather than
corruption — the assertion means corruption itself can no longer land silently.

#### Relocate's retry loop didn't retry on a `None` result (found+fixed 2026-08-07)

`relocate_check.py`'s `check_window()` catches its own malformed-JSON/unparseable-response
failures internally and returns `None` rather than raising — a valid, expected return value,
not an error. `relocate_run_all.py`'s retry loop was `for attempt in range(3): try: result =
check_window(w); break except Exception: ...` — the `break` fired unconditionally after any
call that didn't raise, so a `None` result (a bad model response, not a network/API error)
permanently escaped the retry loop on the first attempt. `apply_moves.py` treats a `None`
result as "no move" (silent no-op), so the affected quote-run was just left wherever v10
assembly's own (unrelated, and not necessarily correct) initial placement put it — no retry,
no visibility, nothing to catch it short of a human noticing the placement looked wrong.

**Found via**: scanning all `review_v10_relocated/*_wallpatched_split.json` files from the
18-daf reviewed batch for `"result": null` — found 3 (`avodah_zarah_17` 1-item run,
`sanhedrin_67` 4-item run, `meilah_8`'s 8-item mega-run, see below). **Fix shipped**: the
loop now retries whenever `result` comes back `None`, not just on a raised exception. Two of
the three were transient — retried cleanly on the first extra attempt, verdicts applied,
regenerated, verified lossless. The third (Meilah 8) is not transient; see next section.

#### Censored-source insertion landed in the wrong place (Sanhedrin 67 "ben Setada" passage, found+hand-patched 2026-08-07)

Sanhedrin 67's ben Setada/ben Pandeira passage (a passage some printed editions censor) was
inserted by v10's Sefaria-matching under `### Akiva Example` (a *Mechashef*/witchcraft section
several headings later) — content-unrelated to its actual home. Per the user, who gave this
shiur: the printed text they read from had this passage censored out entirely, so it isn't
recited in the transcript in its usual position; v10 still matched and inserted it (likely a
low-confidence/partial match), just in the wrong place. Correct position, per the user's own
knowledge of the daf: immediately after the "Rav Pappa says... license to use the entrapment
method" paragraph, right before `## Mechashef Category`. **Hand-patched** — moved to the
correct position in `review_v10_relocated/sanhedrin_67_wallpatched_split_relocated.md`;
verified the passage now appears exactly once, quote-block count unchanged (43, a pure
reposition of already-present content, not new insertion).

**Same fragility as Hullin 88/Meilah 8 — this patch is in a DERIVED file, not the source, and
will NOT survive a rerun.** Unlike Meilah 8 (a relocate-schema limitation) or Hullin 88 (a
matching-threshold drop), this one originates in v10's own Sefaria-matching step
(`best_match_times`/`align_constrained`) inserting real content at a low-confidence position —
rerunning v10 assembly for this daf will very likely reproduce the identical misplacement,
since the matching is deterministic given the same inputs. **Action required when the
corpus-wide push reaches Sanhedrin 67**: reapply this same move to the final promoted output,
sequenced last, same as the other two — immediately before `promote_to_final.py`, after every
other step has already run for this daf.

#### Beyond-2-way-split ceiling: relocate has no schema for a run spanning >2-3 headings (Meilah 8 "Shtei Halechem" mega-block, found 2026-08-07, diagnosed, not fixed)

Meilah 8's `## Bread & Menachos` > `### Shtei Halechem` had an 8-item quote-run that is
actually one continuous Mishnah reciting *seven* distinct cases (olat ha'of, parim/se'irim
hanisrafim, olah, chatas/asham/zivchei shalmei tzibbur, shtei halechem, lechem hapanim,
menachos) — each belonging under a *different* one of six headings, all of which were
correctly present in the candidate list (this is NOT the missing-candidate class above; every
right answer was on offer). `relocate_check.py`'s response schema only supports FORM 1
(single target) or FORM 2 (exactly one 2-way split, itself narrowly scoped in-prompt to "one
wrap-up sentence glued to the start of the next topic" — explicitly not this shape). Facing a
7-way problem with only those two options, the model — reproduced live, twice, with different
API calls — recognized the passage "contains items from multiple different headings...
spanning the entire list of candidates" but had no way to say so, and fell back to FORM 1,
sometimes with a response malformed enough to trigger the `None`-result bug above instead.

FORM 3 (marker-gated 3-way split, already shipped for Nazir 59/Niddah 60) doesn't help here:
it requires exactly two literal `MISHNA:`/`GEMARA:` markers on items 2+, and this run has
zero (it's a single continuous Mishnah with no internal markers, even though item 1 itself
opens with "MISHNA:" — a marker on item 1 has no "before" boundary to split at, so it isn't
counted).

**Hand-patched 2026-08-07** (applied to `review_v10_relocated/meilah_8_wallpatched_split_relocated.md`,
verified lossless — 35/35 quote blocks match the raw v10 file, headings intact). Mapping (verified
against each target heading's own prose): item 1→Olat Ha'Of, item 2→Burned Offerings, item
3→Olah Me'ilah, item 4→Chatas & Asham, item 5→Shtei Halechem (stays), items 6-7→Lechem
Hapanim, item 8→Menachos (before its own existing quote). Confirmed via mechanical check that
none of the 4 non-current target headings already have a quote of their own, so no
duplication risk. **Note the mapping is not monotonic** — item 2's target heading comes later
in document order than item 3's target.

**Same fragility as the Hullin 88 lesson — this patch is applied to a DERIVED review file,
not the source, and WILL be silently wiped if Meilah 8's wall-of-text/v10/relocate/apply_moves
pipeline reruns for any reason before the real corpus-wide push reaches it.** Unlike the BB153/
BB174 SRT patches (fixed at the `02_rewrite.md` source, survives any rerun), this fix can't
live upstream — the mega-block only exists as a single quote-run *because* v10 assembly and
relocate both, independently, failed to separate it; there's no earlier pipeline stage to fix
it at. **Action required when the corpus-wide push reaches Meilah 8**: reapply this exact
mapping to the final promoted output, sequenced the same as the Hullin-88-class hand-patches
— last, immediately before `promote_to_final.py`, after every other step has already run for
this daf. Treat it as a second, one-entry version of that same post-run checklist.

**A narrow, evidence-gated fix was investigated and tested against real data 2026-08-07 —
it does not work, closed.** The natural candidate: reuse the existing zero-cost local
word-overlap scoring (`content_words`/`normalize`/`phonetic_key`, the same machinery
`prototype_text_first.py`'s own `score_overlap` and `check_pass2_coverage.py` already use) as
a cheap pre-filter — only offer the LLM an expanded multi-way FORM when local scoring already
shows strong evidence of genuine multi-target spread (≥3 distinct per-item best-matches).
Tested corpus-wide-style across all 18 reviewed dafim's runs with ≥4 items and ≥3 candidates
(22 such runs found): the gate flagged 3 runs, and **Meilah 8's own motivating case was not
one of them.** Root cause, found by inspecting the actual per-item scores directly: this
Mishnah's seven clauses share heavy templatic boilerplate ("mo'alin," "huchsharu l'hipasel
bitvul yom uvimechusar kippurim," "chayavin mishum piggul nosar ve-tamei" — the very
repetition that makes it "a list of parallel cases" in the first place), so raw word-overlap
scoring gets swamped by shared vocabulary and picks the longest/most-detailed candidate
("Shtei Halechem" itself) as the top match for literally every item, missing the actual
distinguishing nouns entirely (parim, olah, chatas, menachos...). Tried a TF-IDF-style
refinement next — downweighting words that repeat across more than half the run's own items,
keeping only each item's "distinctive" vocabulary. Better (2-3 of 8 items got a correct
unambiguous top match) but still not reliable enough to gate on: several items still scored
ties or wrong winners. **Conclusion: no cheap, local, structural signal reliably discriminates
this case from an ordinary large single-heading run** — unlike FORM 3's marker gate (a literal
`MISHNA:`/`GEMARA:` string is unambiguous), there's no comparably cheap tell here.

The only fix that would actually work reliably requires asking the LLM directly, per item
("which candidate does this specific item belong to?" — a per-item independent assignment
naturally handles the non-monotonic case too, no split-point math needed). That's not more
complex to specify than the current FORM 2, but it means rewriting the schema every relocate
call goes through today, not adding a narrow, opt-in extra path the way the starved-heading
rescue and FORM 3 both did — a materially bigger blast-radius change than anything shipped
this session, touching the already-validated common path rather than sitting beside it.

**Disposition, per direct user discussion 2026-08-07: accepted as a known, rare, documented
limitation — same status as Berakhot 31b and Hullin 88's Rashi & Tosafot case, not pursued
further.** Grounds: exactly 1 occurrence in 18 dafim reviewed, and even that one is an extreme
case (a single Mishnah enumerating seven parallel cases in one breath — most Mishnayot aren't
this shape); the investigated narrow fix was tested against the real motivating case and
concretely failed, so there is no available fix that doesn't mean rewriting the core relocate
schema; and review quality across the corpus sample to date has been uniformly excellent
without it. Revisit only if a future review batch surfaces this shape more than a couple more
times — the per-item independent-assignment schema above is the concrete path if that happens,
not something to build speculatively now.

#### Pass 2 duplicates substantial content into a "brief return-visit" macro (Shabbat 11 "Gov't Complexity"/"Kings' Hearts" class, found+scanned 2026-08-07, corpus-wide, not yet fixed)

Found on Shabbat 11: `### Gov't Complexity` (under macro `## Governance`, 08:03 in the
transcript) has a full, substantive paragraph on the "if all seas were ink" statement and its
Proverbs proof-text — but the user checked the transcript directly and confirmed the lecturer
says nothing about this at 08:03. The real, correctly-sourced content (an actual quoted
blockquote, not just prose) sits 9 minutes later at `### Kings' Hearts` (macro `## Governance
(II)`), with two unrelated macro topics (`Political Authority`, `Afflictions`) in between.

**Root cause, confirmed via segmentation's own data**: `01_segmentation.json`'s raw `title`
for the second macro is literally `"...Difficulty of Royal Administration (continued)"` —
Pass 1 itself recorded that the lecturer briefly touched this topic at 08:03 (one single
micro-segment — a genuinely short mention) and returned to give it full treatment at 17:32.
Pass 2, when writing the brief 08:03 section, wrote the FULL explanation anyway — duplicating
content that only actually belongs, with its source quote, at the later occurrence. **Pure
Pass 2 defect**: confirmed byte-identical in the original `02_rewrite.md`, predating
wall-of-text/v10/relocate entirely — none of this session's other fixes touch it.

**Corpus-wide scan, three narrowing passes (all zero API cost — static/local only):**
1. Any segmentation macro with `(continued)` in its raw title: **1,210 hits** — far too broad,
   mostly ordinary same-topic continuations sitting immediately adjacent to each other (split
   only for length), not this bug.
2. Narrowed to Shabbat 11's actual shape — the *first* occurrence has exactly one
   micro-segment (a brief mention) AND at least one *other*, unrelated macro sits between the
   two occurrences (a genuine return-to-topic-later pattern, not just adjacent chunking):
   **330 structural candidates**.
3. Content-confirmed via word-overlap (jaccard) similarity between the first occurrence's
   prose and the second occurrence's prose — using the same `content_words`/`normalize`
   machinery already used elsewhere in this codebase (`prototype_text_first.py`'s
   `score_overlap`, `check_pass2_coverage.py`). Threshold calibrated directly against Shabbat
   11's own confirmed case (jaccard 0.238) rather than picked arbitrarily; used 0.20 to leave
   margin: **32 dafim confirmed** — `nedarim_16`, `sotah_2`, `bava_batra_11`, `shevuot_49`,
   `temurah_21`, `temurah_6`, `yevamot_23b` (x2 — two separate pairs), `bekhorot_23`,
   `nedarim_88`, `bava_metzia_13`, `yoma_16` (x2), `avodah_zarah_23`, `sanhedrin_27`,
   `shabbat_11`, `kiddushin_15`, `shekalim_6`, `bava_kamma_112`, `pesachim_6`,
   `rosh_hashanah_24`, `hullin_78`, `shekalim_4`, `menachot_26`, `chagigah_24b`, `horayot_13`,
   `meilah_3`, `shabbat_90`, `nazir_44`, `gittin_87`. **This is a lower bound, not the final
   count** — 0.20 was chosen to sit safely below the one confirmed calibration point (0.238),
   but there's real margin for true cases scoring even lower that this threshold misses.

**Not fixed. Fix mechanism, proposed but not yet built** — a two-stage tool mirroring
`fix_wall_of_text.py`'s already-proven architecture, operating on `02_rewrite.md` directly (a
source-level fix, so — unlike the Hullin-88-class hand-patches — it's durable by construction
and needs no reapply-after-rerun tracking):
- **Stage A (verify, cheap model)**: per candidate, feed the transcript segment covering the
  first occurrence's time window, the essay's current prose there, and the second
  occurrence's prose. Ask whether the transcript actually supports this content at the first
  point. This is exactly the check the user did by hand for Shabbat 11, at scale.
- **Stage B (patch, confirmed duplicates only)**: trim the first occurrence to whatever the
  transcript actually shows there (often nothing) — never touch the second, correctly-sourced
  occurrence. Unlike the "see above" placeholder bug (safe to mechanically delete outright,
  since that content was provably empty filler), this needs the verify step first — the jaccard
  scan finds *candidates*, not proof; a legitimately distinct discussion that happens to share
  vocabulary with a later topic is a possible false positive this class doesn't rule out on its
  own.

**Does not need to wait for the corpus-wide v10 push** — only needs `01_segmentation.json` +
`02_rewrite.md`, both already present for nearly the whole corpus (pass 1+2 already ran on
~all of it). Same standalone-prepass category as the lecturer-removal/truncated-title cleanups
under "Corpus text cleanups applied 2026-07-29" — could run independently, any time, ahead of
or alongside the v10 push rather than gated by it.

#### `apply_display_titles.py` matches POSITIONALLY — two flags exist to contain that

It zips headings against segments by index, so on any daf whose counts differ it silently
mislabels every heading after the first divergence. Added 2026-07-29:

- `--only FILE` — restrict to daf directory names listed in `FILE`, one per line.
- `--rewrite-only` — touch `02_rewrite.md` and leave `03_final.md` alone.

`--rewrite-only` is not a nicety. Counting `02_rewrite.md` alone, **2,251 of 2,363** dafim are
aligned; counting `03_final.md` too, only **1,458** are. The ~900 difference is *legitimate* —
pass 3 split and merged sections, so the final's heading count is supposed to differ. Since
step 3 above regenerates `03_final.md` anyway, its alignment is irrelevant and touching it
would corrupt those 900. Regenerate the aligned list rather than trusting a stale one; 4
dafim (`arakhin_3`, `bava_batra_128`, `bekhorot_25`, `zevachim_36`) have unreadable
segmentation JSON and drop out of every count.

The two lists are checked in as `daf-processor/title_pass_aligned.txt` (2,251) and
`daf-processor/title_pass_mismatched.txt` (108, with each daf's counts). They are a snapshot
— regenerate if `02_rewrite.md` or the segmentation changes.

Applied 2026-07-29 to the 2,251 aligned set (863 changed, backups `.bak_before_titles`).
Truncated headings in `02_rewrite.md`: **739 → 31**. Of the remaining 31, 30 are in the
108-daf count-mismatched set and need a title-*string* pass, not a positional one;
`sukkah_54` is the lone aligned holdout, carrying `Yom Tov & Shabbat… (II)` in the
segmentation itself — the relabel job appears to skip rank-suffixed duplicates.

### `title_string_pass.py` — the title-string pass for the 108-daf mismatched set (built and run, 2026-08-02)

Found live: `wall_of_text2.py` silently reported **zero prose for every section** on
Berakhot 31b — its essay headings are independently-written full sentences, never derived
from `display_title` at all (`h2 10/10  h3 32/33` per `title_pass_mismatched.txt` — one
segmentation micro-topic evidently got folded into a neighbor's heading with no separate
label). Neither existing header tool fit: `apply_display_titles.py` is positional (unsafe
here by definition — the count differs); `sync_md_headers.py` only handles a stale
`"(II)"`-suffix rename via exact-string search, not a fully reworded heading with nothing
to search for.

`title_string_pass.py` aligns the two ordered label sequences (segmentation
`display_title`s, essay `##`/`###` headings, per level) by content-word overlap — exact,
`phonetic_key`-folded, and shared-prefix (≥4 chars) tiers, reusing
`check_pass2_coverage.py`'s `normalize`/`content_words`/`phonetic_key` — via a monotonic DP
allowing skips on either side (a segmentation topic with no separate heading; a stray
essay heading with no segmentation counterpart), same structural shape as
`align_constrained()` in `prototype_text_first_v10.py` one level up (labels instead of
text). Dry-run by default; matches scoring below `MIN_CONFIDENCE=2` are flagged and never
auto-applied, since a wrong rewrite here is exactly the silent-mislabeling failure mode
`apply_display_titles.py`'s own positional-matching gotcha warns about. Backs up to
`.bak_before_title_string_pass` before writing.

**Run across the full 108-daf mismatched set 2026-08-02 — a genuine but partial fix, not a
full resolution.** The set is not homogeneous like Berakhot: many entries are a single
already-short-label heading that's simply orphaned (segmentation was renamed/regenerated
after the essay was written, so the heading's own words no longer overlap with *any*
current `display_title` — no content-matching approach can safely reconnect these; correctly
left as `[unmatched]`, not guessed at). Across all 108: **134 headings had no scoring
candidate at all** (left untouched), **92 had a candidate** (39 confident enough to apply,
53 flagged low-confidence and left untouched). Berakhot 31b itself: 19 of 32 fixed. The
residual — both the 134 unmatched and the 53 low-confidence — will keep silently misreporting
`prose=0` in `wall_of_text2.py` for those specific sections (not the whole daf) until
resolved some other way (manual correction, or a stronger matching signal). Reusable:
`python title_string_pass.py --mismatched-file title_pass_mismatched.txt --apply`.

### Corpus text cleanups applied 2026-07-29 (local, no reprocessing)

All reversible via the noted backup files; all operate on `02_rewrite.md`, which is the
point of departure for any future rerun.

| Cleanup | Scope | Backup |
|---|---|---|
| Third-person "the lecturer" removed | 116 occurrences, 78 dafim — 44 regex deletions, 69 Haiku rewrites, 23 hand-corrections where Haiku produced stilted first person ("as I candidly note") | `.bak_before_lecturer_fix` |
| Truncated `display_title`s regenerated | 2,131 across 752 dafim; now **0** ellipsis labels and **0** over 25 chars | `.bak_before_relabel` |
| Pure page-navigation sentences deleted | 55 ("Today's daf is 174, and we pick up at the bottom of 173b at the two dots.") + 2 later stragglers, `niddah_60` and `bava_batra_103` | `.bak_before_nav_strip` |

**Deliberately NOT removed: ~1,400 *embedded* location clauses** ("The Gemara, two lines
from the top of 22a, asks:"). The author wants these — they orient a reader to where the
passage sits. Only sentences that are *purely* a pointer were removed, since the inserted
Gemara already anchors the reader. Three successive filter tightenings were needed to stop
the script destroying content-bearing sentences like "The Gemara turns to a *baraita* at the
top of 48a" — **if you rerun this, verify the match list before applying.**

**`upload_to_supabase.py` timestamp bug (fixed).** Section headers are `display_title`, but
the timestamp lookup keyed on the segmentation's `title` — matching **0 of 19,378 macros and
0 of 79,507 micros**. Macros survived on a positional fallback; micros had none, so *every*
micro row would have uploaded with a NULL timestamp. Now indexes both labels and gives
micros the same positional fallback. Only affects `--sections` (AskAnyDaf), which has not
been bulk-loaded yet.

**Known corpus identity defects (not fixed):**
- `output/pesachim_19` contains a segmentation labelled **Gittin 18b** — content and
  directory disagree. Uploads under Pesachim 19.0, so no key collision, but the content is
  wrong. Not in the documented "19 severe" list.
- `eiruvin_33`/`eruvin_33` and `eiruvin_82`/`eruvin_82` are byte-identical duplicates from
  the spelling migration and collide on the upload key. Harmless (same content) but the
  `eruvin_*` copies are dead and can be deleted.
- The `X`/`Xb` directory pairs (~27) do **not** collide: `parse_dir_name()` reads the amud
  from the directory suffix, giving 40.0 vs 40.5. Do not "fix" this by reading the
  segmentation's `amud` field — that field is the unreliable one (see `find_amud_b.py`).

### Menachot 79 — the one SRT with zero Hebrew (re-transcribed, verified 2026-08-07 — needs pass 1+2 rerun)

**Resolved:** the author supplied a new `srt/processed/Menachot 79.srt` (on disk as of
2026-08-03, confirmed containing real Hebrew 2026-08-07 — `grep -c '[֐-׿]'` finds Hebrew on
170 of 7,060 lines, opens "עין ט' עמוד ב'"). No longer the 0%-Hebrew singleton described
below. **Still needs pass 1 + pass 2 rerun** (both API calls, requires authorization) before
it can join the corpus-wide v10 pass, same as any daf whose SRT changed — the old
`01_segmentation.json`/`02_rewrite.md` were both derived from the broken transcript and are
stale. Once reprocessed, remove it from the corpus-wide exclusion list.

Original finding, kept for reference:

`srt/processed/Menachot 79.srt` contains **0 Hebrew characters**. Scanning all 2,363 SRTs
confirms it is a true singleton, not the tail of a distribution:

| Hebrew density | Files |
|---|---|
| 0.00% | 1 — `Menachot 79.srt` |
| 0.01–4.90% | **0** |
| 4.91% (next lowest) | `Bava Batra 102.srt` |
| median | 9.94% |

The transcript is otherwise complete — 1,752 entries, 58 min, ends "Alright, we finished the
daf." Transcription simply emitted Latin script throughout, including the Gemara
recitations: it opens `Yes, it is Ayin-Tet, starting with some things on the bottom of
Ayin-Tet Amud Bet.` Most likely a language-detection flip on this one file.

The healthy pattern, for comparison (`Menachot 80.srt`, entry 43): conversational Hebrew
terms stay transliterated (`einah teunah lechem`, `shene'emar`) and only the **recitation**
switches to Hebrew script (`הקריב על זבח התודה...`). `best_match_times()` consumes only the
recitations, so restoring those is what matters — terminology inside the English is invisible
to it.

**Consequences, all three passes affected:**
- `01_segmentation.json` and `02_rewrite.md` are also at 0 Hebrew, and the rewrite lost the
  italic transliteration convention (bare `Toda`, `Pasul` where other dafim have `*arevim*`).
- v9 reports **`matched 0 segs`** and falls back to the full-daf span: the first two sections
  get no Gemara and all 74 segments dump under one unrelated heading. Completeness still
  holds (26/26, 74/74) — nothing is lost, it is only misplaced.

**Fix path:** re-transcribe the audio, then rerun pass 1 + pass 2 + v9 for that daf.
Repairing the SRT alone does *not* avoid the pass 1/2 API cost, since both ran on the
Hebrew-free transcript. **After re-transcribing, verify Hebrew is actually present**
(`grep -c '[֐-׿]' "Menachot 79.srt"`) — the same settings may reproduce the fault.

Fallback if re-transcription fails: substitute the recitation runs by hand against
`sefaria.md` (grounded in the real text, not invented), preserving each entry's timestamps.
Success is measurable — `matched` should go 0 → ~20–30. Pilot on the first ten minutes before
committing to all 1,752 entries. A wrong Hebrew word fails to match rather than mismatching,
so the downside is bounded.

### Daf processing procedure — pass 2.5 → pass 3 → audit → fix → upload (SUPERSEDED by Approach B/v10 — kept for historical/forensic reference only)

**Superseded, 2026-07-29 onward.** Approach B (v10 assembly) fully replaces passes 2.5 and 3
— see "Approach B — Sefaria-first assembly" above. `prototype_text_first_v10.py` reads
`02_rewrite.md` directly and never touches `025_cleanup.md`/`03_final.md`; the live
"Corpus-wide run order" and "Corpus-wide push checklist" sections above are the current
procedure. Do not run pass 2.5 or pass 3 on anything going forward — the steps below describe
the pre-v10 pipeline that produced the corpus's existing `025_cleanup.md`/`03_final.md` files
(inert leftovers now, unread by the current pipeline) and are kept only because they're
occasionally useful for forensics (e.g. confirming whether a defect predates a given fix by
checking if an older pass's output already had it).

The old end-to-end procedure for bringing a daf (or batch of dafs) up to *then*-current quality, whether processing fresh or reprocessing older output:

1. **Pass 2.5** (if `025_cleanup.md` doesn't already exist — check first, most of the corpus predates it): `python main.py --passes 2.5 --resume <srt files>`. Safe to run even if you're not sure — cheap, and `--resume` only touches dafs missing the file.
2. **Pass 3**: `python main.py --passes 3 --resume <srt files>`. If redoing a daf that already has a `03_final.md` you want replaced, back it up and delete it first — `--resume` skips any pass whose output file already exists, so a stale `03_final.md` silently blocks a rerun otherwise.
3. **Audit**: `check_anchor_section_mismatch.py` runs automatically after step 2 for every daf (wired into `pipeline.py`), logging clean/flagged status. Can also be run manually — `python check_anchor_section_mismatch.py [output/some_daf ...]` (defaults to the whole corpus) — to re-check without reprocessing.
4. **Review and fix flagged dafs** (currently a Claude-driven manual step, not automated): for each flag, read the actual content (blockquote text, headers) against the source files before deciding it's real — see the checker's own docstring and the "known false-positive mode" notes below for what to expect. Two fix strategies depending on what's actually wrong:
   - **Mechanical edit** (safe, no API cost) — appropriate only when the defect is a single, isolable structural element (e.g. one clearly-fabricated heading *line*, confirmed absent from `025_cleanup.md` in its entirety) and the surrounding prose is otherwise correct.
   - **Fresh pass-3 rerun** (back up + delete `03_final.md`, redo step 2 for just that daf) — the safer default whenever the defect involves actual content (fabricated blockquote text, duplicated passages, dropped headings, anything where prose itself might be affected) or when you're not fully certain a mechanical edit is safe.

   **A mechanical-edit mistake made 2026-07-22, worth learning from:** a heading that appears once in `03_final.md` but is "missing" from a naive positional diff against `025_cleanup.md` is not necessarily fabricated — it can be a heading that's *present in both files but reordered*, which a simple line-by-line diff misrepresents as a pure insertion (and, symmetrically, a pure deletion at the position it "should" have been). Deleting it as "fabricated" in that case destroys the only copy of a real heading. **Before deleting anything as fabricated, verify the full header list matches `025_cleanup.md` exactly (same text, same order) after the edit — not just that the count now matches** — that check catches a reordering being misdiagnosed as insertion/deletion immediately (mismatched count-but-still-False on the full-list comparison is the tell). This exact mistake happened on `Hullin_27` and `hullin_68`; both needed a fresh pass-3 rerun to recover since the mid-edit state was never committed to git.
5. **Re-audit** the fixed dafs to confirm clean (or at least no new issues).
6. **Upload**: `python upload_to_supabase.py --tractates "<Tractate>"` (or `--dir output/<daf>` for a single one).

**Session strategy for corpus-wide reprocessing**: do this tractate-by-tractate (or similarly-sized batch), not the whole ~2,362-daf corpus in one run — each batch needs the manual review step above, and doing it in bounded chunks keeps that tractable. Prefer the manual audit-and-fix workflow above (a Claude Code session doing steps 3-5 interactively) over a fully-scripted/API-automated fixer — slower and costs Claude Code usage rather than nothing, but produces more careful, accurate fixes; today's Hullin batch (114 dafs) needed real judgment calls (see the mistake noted above) that a blind script would likely have gotten wrong. **Start a fresh conversation per tractate/batch rather than continuing in one long-running one** — the practical knowledge needed (false-positive patterns, fix strategies, the procedure itself) is captured here in CLAUDE.md, so a new conversation gets full context for a fixed, small cost (reading this file) instead of resending an ever-growing transcript of unrelated prior work every turn. Compaction (`/compact` or automatic) is the right tool for continuing deep in the *same* task past a context limit when relevant state hasn't been externalized yet; it's not a substitute for starting fresh on genuinely separate work once the state that matters is written down here.

### Corpus reprocessing status (as of 2026-07-21) — what's done, what still needs pass 2.5+3

**Key finding: pass 2.5 has never been run on any of the original 2,363 processed dafs.** It's recent infrastructure — every sampled daf across many different tractates this session (not just old/problematic ones) was missing `025_cleanup.md` entirely. Since pass 3 strongly prefers HTML-comment anchors (which only pass 2.5 produces) over its weaker inline-text fallback, a full-corpus rerun almost certainly needs to be **pass 2.5 + pass 3 together**, not pass 3 alone, for nearly the whole corpus.

**28 dafs fully reprocessed under the current (final) prompt — confirmed clean, safe to skip on a future full-corpus rerun:**
- 10-daf bold-markup test batch: `avodah_zarah_18`, `avodah_zarah_27`, `avodah_zarah_37`, `avodah_zarah_8`, `bava_kamma_56`, `bava_metzia_4`, `bava_metzia_40`, `bava_metzia_55`, `gittin_61`, `gittin_71`
- 18-daf unbiased random sample: `bava_batra_116`, `bava_batra_62`, `bava_kamma_12`, `bava_metzia_105`, `bekhorot_53`, `berakhot_49`, `ketubot_8`, `nazir_28`, `nedarim_68`, `pesachim_116`, `shabbat_119`, `shabbat_131`, `shabbat_153`, `sotah_33`, `sotah_37`, `sotah_47`, `yevamot_97`, `zevachim_25`
- 114 of 116 Hullin dafs (all except `hullin_70`/`hullin_136`, held out — see below): pass 2.5 + pass 3 complete, uploaded to Supabase (2026-07-22). Fully audited and hand-fixed daf-by-daf (not just spot-checked) with the rewritten `check_anchor_section_mismatch.py`: final state is 113 checked, 31 flagged, 44 total flags, of which 42 are `OUT OF ORDER` (the checker's known residual false-positive category — see below) and 2 are confirmed non-issues (`hullin_81`: pass 2.5's own duplicated block, self-corrected by pass 3, `03_final.md` is clean; `hullin_129`: a chapter-ending liturgical phrase with no real content to bold-mark, same pattern as an earlier Yevamot 97 false positive). Real defects found and fixed: `hullin_126` (same passage duplicated under two headers — the "shared indivisible segment" rule not applied; removed the duplicate blockquote, kept the prose), `hullin_135`/`hullin_29b` (fabricated blockquote text not present in any Sefaria source — reprocessed via fresh pass 3), `hullin_103`/`hullin_50` (a heading silently dropped — `hullin_50` needed a second, mechanical fix after a fresh pass-3 rerun still dropped the same heading; inserted it back by hand at the correct content boundary), `hullin_15`/`hullin_46`/`hullin_74`/`hullin_101` (a fabricated extra heading — removed mechanically, verified full header list then matched `025_cleanup.md` exactly), `hullin_27`/`hullin_68` (see the mechanical-edit mistake note above — these were misdiagnosed as fabricated when actually reordered, wrongly deleted, then recovered via fresh pass-3 rerun), `hullin_53` (a heading's spelling drifted from "Amemar" to "Ameimar" between the two files — corrected to match the source exactly). `hullin_101`'s `01_segmentation.json` separately had a leftover markdown code fence wrapping otherwise-valid JSON (fixed by stripping it, no reprocessing needed — check for this pattern if `find_amud_b`/JSON parsing ever crashes on a daf that otherwise looks processed).
  - **Process note for next time:** the first attempt at this batch ran via direct API (`--no-batch`) as a local background process; the underlying Claude Code session died overnight (machine sleep/app restart) and killed it mid-run with no completion record, after only 5/114 dafs. Restarting the remaining 109 via the Batch API worked correctly and is resilient to local process death (batch runs server-side; `--resume` reattaches to the saved `batch_id` in `output/.batch_phaseN.json` rather than resubmitting) — another concrete reason batch is the required default per the policy above, beyond just cost.

**12 dafs that only got a mechanical text-surgery fix, NOT a real pass-3 rerun — still need one:** `avodah_zarah_2`, `avodah_zarah_58`, `avodah_zarah_67`, `avodah_zarah_70`, `bava_batra_111`, `bava_kamma_76`, `ketubot_18`, `ketubot_29`, `ketubot_55`, `nedarim_53`, `sukkah_13`, `sukkah_36`. These were the ones caught leaking their own "STEP 1/2/3" reasoning as literal output text — the leaked preamble was stripped directly from `03_final.md` without regenerating the underlying content, so they predate the bold-markup-preservation fix. Confirmed still-real issues on re-check: `ketubot_55` has a genuine missing-bold-markup blockquote, `bava_kamma_76` has a real header-count mismatch, `sukkah_13` has two swapped header titles. Do not count these as done.

**19 "severe" dafs — wrong audio filed under the wrong daf label. Reprocessing does NOT fix these; they need the correct source recording identified first, upstream of the Claude pipeline entirely:**
- 3 are duplicates of an adjacent daf's real content (the neighbor itself is fine): `nazir_36` (contains `nazir_35`'s content), `megillah_30` (contains `megillah_31`'s content), `nazir_33` (contains `nazir_32`'s content) — each needs its own correct source audio located.
- 1 pair are mutual duplicates of each other: `nedarim_86` / `nedarim_86b` — can't tell from text alone which (if either) is correctly labeled; needs manual knowledge of whether a genuine separate "86b" episode exists.
- 14 have no match anywhere in the 2,363-daf corpus (content is for some daf/tractate not in the corpus, or from outside it): `hullin_136`, `ketubot_35`, `megillah_24`, `nedarim_3`, `pesachim_15`, `rosh_hashanah_14`, `shabbat_91`, `sukkah_54`, `moed_katan_27`, `hullin_70`, `shabbat_90`, `avodah_zarah_7`, `moed_katan_28`, `yevamot_59b`.
- **`hullin_70` and `hullin_136`** are being held out of the current Hullin reprocessing batch for exactly this reason — do not run pass 3 on them until their correct source is found, or the daily Hullin reviewer will hit a polished-looking essay about the wrong topic.

**271 dafs flagged in an earlier corpus-wide scan** (before pass 2.5 existed) as legitimate Claude-quality issues on otherwise-correct source material — 102 with dropped/merged headers, 24 with silently reordered topics, 161 with mislabeled "(II)"-style part numbers. These are a real reprocessing target, though likely substantially explained/fixed by the "everyone needs pass 2.5" finding above rather than needing separate handling. The exact list of 271 daf names was not preserved in current notes — rerun the corpus-wide `check_anchor_section_mismatch.py` scan before the full rerun to get a fresh, current list rather than relying on this stale count.

**Everything else in the ~2,362-daf corpus** (roughly 2,362 − 28 − 12 − 19 ≈ 2,303 dafs) has not been touched by any of this session's fixes and, per the finding above, most likely lacks `025_cleanup.md` entirely.

### Corpus-wide push checklist (live tracker, started 2026-08-02 — update this, don't let it go stale)

**Corpus-wide run started 2026-08-08.** Menachot 79's pass 1+2 rerun completed (new SRT
confirmed to contain Hebrew and produce real, matching prose — "Todah...hybrid...kodashim
kalim" content, distinct from the old stale essay); it's now included in the corpus-wide set,
no longer held out. Step 2 (`03_final.md` corpus-wide backup, 2,362 files → `.bak_pass3`) done.

**Step 3 (`fix_wall_of_text.py`, corpus-wide) — three real bugs found and fixed getting it to
run, all before/without extra API cost:**
1. `output/bava_batra_153/01_segmentation.json` had a stray trailing comma (leftover from an
   earlier hand-edit) breaking JSON parsing — fixed; all 2,339 segmentation files validated
   clean before resubmitting.
2. **`custom_id` collision bug (the serious one).** `run_batch()` keyed its internal `daf_data`
   map by the human-readable display label (e.g. `"Berakhot 24b"`) instead of the directory
   path. Directory pairs like `berakhot_24`/`berakhot_24b` — where the plain `berakhot_24`'s
   own `01_segmentation.json` has a stale `amud: "b"` field — computed the *same* label, so the
   second directory processed silently overwrote the first's entry in `daf_data`. Since patches
   are looked up by `(label, flag_index)` at apply time, this could have spliced a patch
   verified against one daf's transcript into a *different* daf's essay at the wrong text
   offset. 122 such collisions found across ~20 directory pairs corpus-wide (same general
   class as the already-documented amud-b directory-identity ambiguity — see "Amud-b
   relabeling" below — but manifesting as a data-corruption risk in this script specifically,
   not just a labeling question). **Fixed**: `daf_data`, `flag_index`, `confirmed`, and
   `patches_by_dir` are now all keyed by the directory string (guaranteed unique — it's the
   glob/arg source itself), not the label; label is display-only now. Also hardened the
   `custom_id` sanitizer itself (was `.replace(" ", "_").replace("'", "")`, which choked on a
   literal `/` in `"Hullin 122a/b"` and a stray Hebrew `א` in Pesachim 31's `amud` field —
   `output/pesachim_31/01_segmentation.json` has `amud: "א"` instead of `"a"`, a harmless-so-far
   data quirk, not chased further) — now a blanket `re.sub(r"[^a-zA-Z0-9_-]", "_", ...)`.
3. **Passthrough-write gap, corpus scale.** The "write a passthrough copy when nothing needed
   patching" logic (added for Sanhedrin 67 during the 6-daf batch) was gated on a *global*
   `if not confirmed:` check — correct only when literally zero dafim across the whole run had
   any confirmed patch. At corpus scale, most runs have SOME dafim with confirmed patches and
   others without, so every daf in the latter group got no `02_rewrite_wall_patched.md` at all.
   Silently left 246 of 2,278 scannable dafim with no output file after the run completed (found
   by diffing the requested dir list against actual file presence, not by anything the script
   logged). **Fixed** in `fix_wall_of_text.py`: passthrough-or-patched output is now guaranteed
   per-daf, unconditionally, covering (a) dafim with flags but none confirmed, (b) dafim with
   zero flags to begin with, (c) dafim that never entered `daf_data` at all because
   `get_flags_with_context` itself failed (e.g. "no matching SRT") but whose `02_rewrite.md`
   still exists and is still valid v10 input. The already-completed run's 246 missing dafim were
   **backfilled locally with plain `cp` (zero API cost)** rather than re-running the batch, since
   by construction none of them had an unwritten confirmed patch — they were exhaustively either
   zero-flag, false-positive-only, or SKIP cases.

**Update 2026-08-08, later same session — the 36 "missing SRT" Taanit/Megillah dafim weren't
actually missing.** User caught it: `find_srt` was searching for spellings that don't match
the actual files on disk. `Ta’anit` (RIGHT SINGLE QUOTATION MARK, U+2019 — not a plain
apostrophe) for all 19 Taanit dafim, `Megilah` (single L) for 17 of 18 Megillah dafim (the
18th, `megillah_5b`, already had a correctly-spelled `Megillah 5b.srt`, which is why it alone
succeeded on the first pass). This is the reverse of the `_NORMALIZE` dict's direction — there
the *JSON* has the variant spelling and the *file* has the canonical one (Chullin/Eruvin/etc);
here the JSON already says `"Taanit"`/`"Megillah"` (canonical) but the *file on disk* uses the
variant. Fixed with a new `_FILENAME_ALIASES` dict in `check_pass2_coverage.py`, tried after
the canonical name fails. All 36 confirmed found and successfully reprocessed through v10 —
**the full 2,339-daf corpus now has `03_text_first_prototype_v10.md`, zero gaps.**

**Also found while investigating the SKIP list: 18 Hullin dafim (`Hullin_13`, `_15`–`_18`,
`_22`–`_27`, `_3`–`_9`, `_5b` — directory names capitalized, unlike the rest of the corpus's
lowercase `hullin_*` convention) have `masechta: "Chullin"` in their own `01_segmentation.json`**
— an alternate transliteration spelling, not in `find_srt()`'s `_NORMALIZE` dict, so every
script that calls `find_srt(masechta, daf, amud)` (this one, `fix_premature_duplication.py`,
others) silently fails to locate their SRT (`Hullin 13.srt` etc. — which exist, correctly
named) and treats them as SKIP. Confirmed harmless for Supabase upload — `upload_to_supabase.py`
derives tractate from the *directory* name via `parse_dir_name()`, not this JSON field. **Fixed
the general case**: added `"Chullin": "Hullin"` to `_NORMALIZE` in `check_pass2_coverage.py`
(2026-08-08) — the same shared mechanism already handling `Eruvin`→`Eiruvin`,
`Megilah`/`Megila`→`Megillah`. Not retroactively rerun for these 18 dafim's wall-of-text pass —
they got a safe passthrough copy via the backfill above; worth a targeted rerun later now that
`find_srt` will succeed for them, but not blocking the corpus-wide push.

**Wall-of-text corpus run result**: 12,994 candidate flags across 2,278 scannable dafim (61 of
the 2,339 included dirs SKIPped — no matching SRT or similar, mostly the 18 Chullin-spelling
dafim above), 6,542 confirmed as real gaps (~50%, higher than the 6-daf batch's ~32% rate —
plausible corpus-wide variance, not investigated further), 2,091 dafim patched, 248 passthrough
(246 backfilled + 2 from the run itself). Every one of the 2,339 included dirs now has
`02_rewrite_wall_patched.md`. Next: step 4, `prototype_text_first_v10.py --all` (v10 assembly,
zero API cost).

Planned corpus-wide order (confirmed 2026-08-02, extends the "Corpus-wide run order when B goes live" checklist above): **header fix → wall-of-text flag/fix → v10 assembly → relocate → hand-patches (Hullin-88-class prev-daf-boundary list, see "Post-run manual check" below; Meilah 8's "Shtei Halechem" mega-block, see "Beyond-2-way-split ceiling" above; Sanhedrin 67's censored-source "ben Setada" reposition, see "Censored-source insertion" above) → `promote_to_final.py`**. Header fix must come first — v10 copies heading text verbatim into the final output. All hand-patches must come **last**, after every other step above has finished for a given daf and nothing further will regenerate its output — same fragility reasoning in both sections, and the same rule: reapply after any later rerun that touches that daf for an unrelated reason.

**Corpus-scale tooling gaps — closed 2026-08-07:**
- **`relocate_run_all.py`'s sequential-only design was the bigger of the two gaps, not just the missing `--dafim`/`--all` flag.** It makes one direct, synchronous API call per window (~83 sec/daf measured on the 6-daf validation batch) — extrapolates to **~54 hours of continuous sequential execution for the full corpus**, confirmed when asked directly why a 6-daf run was taking so long. New script `relocate_run_batch.py` submits every window across every requested daf as one Batch API job (same `submit_and_wait` pattern `fix_wall_of_text.py` already uses), with the starved-heading rescue pass as a second batch. Supports `--all` (every daf under `output/` with the given `--v10-file`). **Validated against a known synchronous run** (`zevachim_110`): 23 of 24 window verdicts identical; the one difference is ordinary model-response variance (same window, two separate calls, non-zero temperature), not a pipeline bug — confirmed by inspecting both raw verdicts. `relocate_check.py` was refactored to expose `parse_response`/`parse_response_split3`/`split3_points` as pure functions so the batch path reuses the exact same parsing logic as the synchronous path rather than duplicating it.
- `apply_moves.py` is still single-daf CLI itself, but `apply_moves_batch.py` (built earlier this session for the 6-daf batch) now supports `--all` too, and a new `promote_to_final.py` copies its output (`review_v10_relocated/{daf}{suffix}_relocated.md`) to `output/{daf}/03_final.md` — the file the app and `upload_to_supabase.py` actually read. **Promotion is a deliberately separate, explicit script, not an automatic last step of apply_moves_batch.py** — per the corpus-wide order below, it must run AFTER the Hullin-88-class hand-patch check, never before, or that check's entire purpose (catching a dropped opening before it ships) is moot. Backs up any existing `03_final.md` to `.bak_before_v10_promotion` before overwriting.

**Cost estimate for the corpus-wide relocate + wall-of-text push (Batch API pricing), computed 2026-08-07 from real measured data, not guesses:** input/output token counts came from `client.messages.count_tokens()` against real prompts pulled from the 6-daf validation batch (15-20 samples per prompt type) plus a small number of live calibration calls for real output-token usage; calls-per-daf came from the same batch's actual totals (123 relocate calls incl. rescue / 6 dafim = 20.5/daf; 34 wall-of-text Stage A flags / 6 = 5.7/daf; 11 confirmed Stage B patches / 6 = 1.8/daf).

| Stage | Model | Calls/daf | Cost/daf (batch) |
|---|---|---|---|
| relocate (+ rescue) | Sonnet 4.6 | 20.5 | $0.0801 |
| wall-of-text Stage A (verify) | Haiku 4.5 | 5.7 | $0.0078 |
| wall-of-text Stage B (patch) | Sonnet 4.6 | 1.8 | $0.0145 |
| **Total** | | | **$0.1023/daf** |

**~2,300 dafim (core corpus, known exclusions removed) → ≈$235 at Batch API pricing** (≈$483 at
standard synchronous pricing, for comparison — batch is the ~50% discount already the
codebase's standing default). Does not include: pass 1/2 (already sunk for nearly the whole
corpus, except Menachot 79's pending rerun — separately small), header-fix/`title_string_pass`
(already done), v10 assembly / `find_sefaria_indices` / `find_amud_b` / upload (all zero API
cost, confirmed elsewhere in this file). Small-sample caveat: the 6-daf rate is the freshest
and most representative available, but it's still 6 dafim, not a corpus-wide sample — treat
this as a solid order-of-magnitude estimate, not a guaranteed final number.

**v10 assembly has NOT been run corpus-wide yet — confirmed still outstanding, 2026-08-03.** The `sefaria_next.md` widening fix (`widen_sefaria_next.py --all`, see "Amud-b relabeling" section below and the original fix earlier in this file) only updated the *cached Sefaria text files* on disk. Verified on `yevamot_33` — the daf that originally motivated the widening fix — that its `03_text_first_prototype_v10.md` (and `_wallpatched` variant) both predate the corpus-wide widening run (v10 output last written 2026-07-30/08-02 10:57, widening completed 2026-08-02 14:08) and, as expected, still have no Sefaria blockquote at all for the Rava/Rav Nachman/Er v'Onan passage that spills into 34b — the essay prose discusses it (pass 2 doesn't depend on `sefaria_next.md`), but the sourced quote was never inserted, because v10 hasn't re-read the now-wider pool. **The widening fix doesn't take effect anywhere until v10 is actually rerun** — this applies to all ~1,481 widened dafim, not just Yevamot 33. Needs a corpus-wide (or at least widened-subset) v10 rerun before this step of the checklist can be marked done.

**Header fix**
- [x] 2,251 aligned dafim — `apply_display_titles.py`, applied 2026-07-29.
- [x] 108 mismatched dafim — `title_string_pass.py`, run 2026-08-02. Partial by nature, not a full resolution: 58 of ~226 problem headings fixed (19 on Berakhot 31b + 39 across the rest); 134 had no scoring candidate at all, 53 scored too low to trust — both left untouched (they'll keep silently misreporting `prose=0` for those specific sections in `wall_of_text2.py` until fixed some other way). See the script's own section above for the full breakdown.
- [x] 4 dafim with unreadable segmentation JSON (`arakhin_3`, `bava_batra_128`, `bekhorot_25`, `zevachim_36`) — fixed 2026-08-02, same leftover-markdown-code-fence pattern already documented for `hullin_101` above (stripped the fence, verified the JSON parses). Header-synced 2026-08-02: `arakhin_3`, `bava_batra_128`, `zevachim_36` were already count-aligned and already had correct headings (nothing to change); `bekhorot_25` has a micro-count mismatch (105 vs 104) and one residual low-confidence case after `title_string_pass.py` (`"Why Chiya Wouldn't Adopt Rav Assi's Position" -> "Chiya's Counterpoint"`, score 1.00 — plausibly correct on inspection, left unapplied per the confidence gate; a manual call if wanted). None of the 4 are on `title_pass_aligned.txt`/`title_pass_mismatched.txt` yet — regenerate those snapshots before the corpus-wide push so these 4 aren't silently skipped.

**SRT corruption**
- [x] Bava Batra 153 — SRT fixed by user, 2026-08-02. **Superseded 2026-08-07:** the pass 1+2 rerun noted below as "still pending" was never done — instead the fabricated tail was manually deleted from `02_rewrite.md`/`02_rewrite_wall_patched.md` directly (see the "Exception: three dafim" table above), judged functionally equivalent to a rerun since the downstream pipeline reads its section list from `02_rewrite.md`'s own headings. Cleared for the normal corpus-wide v10 pass — no rerun needed.
- [x] Bava Batra 174 — same status/resolution as BB153, same date.
- [ ] Menachot 79 — SRT re-transcribed and verified to contain Hebrew, 2026-08-07 (see "Menachot 79" section above). Still needs pass 1 + pass 2 rerun (API calls, needs authorization) before it can join the corpus-wide v10 pass — not yet done. Remains held out until that rerun completes.

**Data-identity issues — user investigating/fixing directly, not a processing-pipeline task**
- [ ] 19 "severe" mislabeled-audio dafim (see list above) — user reviewing.
- [ ] `pesachim_19` (segmentation content is actually Gittin 18b) — user fixing.
- [ ] `eiruvin_33`/`eruvin_33`, `eiruvin_82`/`eruvin_82` duplicate directories — user fixing.

**12 "mechanical-fix-only" dafim** (`avodah_zarah_2/58/67/70`, `bava_batra_111`, `bava_kamma_76`, `ketubot_18/29/55`, `nedarim_53`, `sukkah_13/36`) — **no separate action planned.** Since Approach B/v10 fully replaces pass 2.5+3, these get properly reprocessed by the same corpus-wide v10 push as every other daf — the original "needs a real pass-3 rerun" framing is obsolete now that pass 3 itself is being retired. Just confirm none of these 12 ends up on an exclusion/held-out list (like BB153/174/Menachot 79) when the batch actually runs.

**Dropped**
- ~~271-daf stale flagged list from the old `check_anchor_section_mismatch.py` scan~~ — dropped by user request, 2026-08-02. (Also likely moot on its own merits: that checker targets fabrication/dropped-content defects specific to the old LLM-reproduction pass 3; v10 asserts completeness invariants and structurally can't fabricate or drop content, so this whole defect class may not transfer to v10 output — unverified, but not worth chasing now that it's dropped.)

**CORPUS-WIDE PUSH COMPLETE — 2026-08-09.** All remaining steps (relocate → hand-patches →
promote → indices → upload) ran overnight in one extended session. Summary below; this closes
out the checklist above.

**Step 5 (`relocate_run_batch.py --all`) — three crashes, all recovered, no data loss in the
end, but one came close:**
1. **256MB request-size cap.** Submitting all ~36,432 phase-1 requests in one batch hit the
   Batch API's request-size ceiling at 36,432 (i.e. immediately). `CHUNK_SIZE` dropped
   5000→1500 to stay well under it.
2. **A misdiagnosed hang that was actually working correctly.** Killed a long-running submission
   believing it had stalled — the real cause was buffered stdout hiding progress output, not a
   stuck process. Cost: lost time re-submitting, not money (nothing had been charged yet at that
   point). My own design bug (should have used unbuffered/flushed output from the start).
3. **Three genuine network outages** (`httpx.ReadError`/`ReadTimeout`/`ConnectError`) during the
   run, verified via `ping`/`nslookup` as real connectivity drops, not code bugs. `RETRY_BACKOFF`
   widened from `[10,30,60,120,300]` to `[10,30,60,120,300,300,300,300,300,300]` in both
   `relocate_run_batch.py` and `fix_pass2_gaps.py`'s `submit_and_wait`; a `harvest_results()`
   wrapper added around `client.messages.batches.results()` specifically because that call is a
   streaming iterator that raises raw `httpx` exceptions unwrapped (unlike `.create()`/`.retrieve()`,
   which wrap into `anthropic.APIConnectionError`) — needed its own retry handling.
4. **The serious one: a 67-daf silent data-loss bug, found by spot-checking suspiciously many
   "0/0 moves applied" results.** Chunk state files were named positionally (`_part{ci}`), so a
   stale state file left over from an earlier crashed attempt (with a different chunk count) got
   wrongly "resumed" instead of a fresh chunk being submitted — meaning 932 requests across all of
   Zevachim plus `shekalim_11` were never actually sent to the API, silently leaving
   `result: None` for all of them despite the run reporting success. **No double-billing for
   these 67** — the stale-resume meant the true submission never happened the first time, so
   there was nothing to double-charge (some small, unquantified duplicate billing likely happened
   elsewhere in the broader crash/retry cycle, flagged transparently to the user and accepted).
   Fixed: chunk state filenames are now content-addressed (keyed on the chunk's first/last
   `custom_id`, not chunk position); the 67 stale JSONs deleted and relocate rerun for just those
   — 66 succeeded immediately, `shekalim_11` hit a second, unrelated bug (below).
5. **`shekalim_11` truncation.** `stop_reason: "max_tokens"` on an 18-quote-index relocate window
   produced unparseable truncated JSON. Fixed by raising `max_tokens` 800→1500 in
   `relocate_run_batch.py` (the original synchronous `relocate_check.py` untouched, not part of
   this run). Reran clean.

All 36,432 phase-1 + 2,923 phase-2 (rescue) requests completed successfully after these fixes.

**Step 6 (`apply_moves_batch.py --all`)** ran clean once step 5's data was actually complete.

**Hand-patch reapplication.** Patches to `review_v10_relocated/*_relocated.md` files don't
survive pipeline reruns (they're on derived output, not source) and must be reapplied as the
last step before promotion, every time the pipeline runs. Both previously-known patches —
Meilah 8's "Shtei Halechem" mega-block reposition and Sanhedrin 67's censored "ben Setada"
passage reposition — were reapplied to the fresh `_corpus`-suffixed files and verified as pure
content-preserving repositions (35 and 43 blockquotes respectively, unchanged before/after).

**Hullin-88-class prev-daf-boundary check — all 44 tracked dafim reviewed, 2026-08-09.**
Confirmed mechanically first that the automatic head-extension rescue feature (built and
deliberately reverted in an earlier session for poor cost/benefit — see below) is inactive for
all 44 (`extended_into_prev=False` uniformly), so none of them get auto-fixed; each needed a real
per-daf read of the SRT against `sefaria_prev.md` to tell a genuine dropped-opening-quote defect
apart from an innocent English-paraphrase recap of the prior daf (the expected, correct pattern).
Dispatched across 5 parallel sub-agents (~9 dafim each). **9 of 44 confirmed genuine drops,
patched and verified** (blockquote count checked before/after each): `bava_batra_88`,
`hullin_47`, `nazir_52`, `pesachim_47` (a mid-sentence fragment prepend, not a new blockquote —
the only one of the 9 that wasn't a clean insert), `shabbat_11`, `sotah_16`, `zevachim_18`,
`zevachim_20`, `hullin_88` (this last one a known, previously-flagged instance — see "Diagnose
Hullin 88" in session history). **35 of 44 were false positives from the original static
near-miss scan** — the lecturer's own explicit navigational cue ("we pick up N lines from the
top of daf X") correctly located the real recitation within the current daf, with only English
review of the prior daf preceding it. Two Hebrew-anchor edits (`sotah_16`, `pesachim_47`) failed
on first attempt due to Unicode normalization mismatches between hand-typed Hebrew and the file's
actual encoding — same known issue as the ASCII-anchor rule below; fixed by locating insertion
points via line-index/heading position instead of matching the Hebrew string itself.

**Promotion, indices, upload — all corpus-wide, all clean:**
- `promote_to_final.py --all --suffix _corpus`: 2,339/2,339 promoted, 0 skipped.
- `find_sefaria_indices.py --force`: 2,363 written, 0 missed. **`--force` was required, not
  optional** — a non-force run skipped 2,357/2,363 as "already set," but those values were
  computed against `03_final.md` content from *before* tonight's promotion overwrote it
  corpus-wide, so they'd have shipped stale.
- `find_amud_b.py --force`: 2,240 written, 112 "misses," 11 skipped. **The 112 are not
  failures** — verified on `Hullin_6` (`01_segmentation.json` has top-level `"amud": "a"`,
  confirming that shiur only covers amud aleph and structurally has no amud-bet content to find).
  These are single-amud shiurim, expected and harmless.
- `upload_to_supabase.py --sections`: **first attempt crashed on the very first job** — a real
  ~3.5-minute network outage (DNS failure, then "no route to host") exhausted the script's
  built-in retry budget (6 attempts, exponential backoff) before anything uploaded, and the
  unhandled exception crashed the whole run. Zero rows had gone through, so no partial-upload
  cleanup was needed. Verified connectivity recovered (`curl` to the Supabase REST endpoint
  returned clean `401`s), retried: **2,363/2,363 succeeded**, absorbing several more transient
  network blips along the way without crashing this time (same retry logic, just didn't run out
  of budget on any single blip).

**New, non-blocking finding: `shiur_sections` blockquote-position gap for Mishnah-only
tractates.** `build_section_rows`'s section splitter (`upload_to_supabase.py`,
`_extract_talmudic_block`) only recognizes a section as `talmudic`/`mishnah` if the Hebrew/Aramaic
blockquote is the *very first* thing after its `##`/`###` heading; if any prose precedes the
quote, the section is classified `shiur_discussion` and excluded from `shiur_sections` (by
design — `shiur_discussion` content lives in `shiur_content.final` instead). Six dafim ended up
with **zero** `shiur_sections` rows because every section in them hit this case: `Hullin 136`,
`Kinnim 23`, `Kinnim 25b`, `Middot 34`, `Middot 37`, `Shekalim 13` (plus `Shekalim 7`, a related
but distinct "no sections with content" case, not separately investigated). Root cause for the
Kinnim/Middot ones specifically: these are Mishnah-only tractates (no Gemara), and their shiurim
tend to explain-then-quote rather than quote-then-explain, which this heuristic doesn't handle.
**Confirmed no current user-facing impact** — grepped both the iOS and Android app source trees
for any reference to `shiur_sections`/`shiurSections`/`ShiurSection` and found none; navigation
pills read from `shiur_content.segmentation` instead (`AnyDaf/ShiurClient.swift`), which uploaded
fine for all 2,363 dafim including these 6. `shiur_sections` itself looks like a table being
rebuilt for a not-yet-wired-up future feature (see the "Source: 99,436 segments..." note above).
Worth fixing `_extract_talmudic_block` if/when that feature ships.

**Deferred cleanup, not urgent:** `promote_to_final.py`'s `review_v10_relocated/` is a whole
separate top-level directory paralleling `output/`, existing purely so there's an explicit
"reviewed and hand-patched, ready to ship" checkpoint between relocate and promotion — which is
exactly the mechanism that caught the 9 dropped-opening patches above, so the checkpoint itself
should stay. But the *implementation* could be tighter: have relocate/apply_moves write
`output/{daf}/03_relocated.md` directly (same directory as everything else for that daf) instead
of a parallel tree, with `promote_to_final.py` doing an in-directory rename/copy to `03_final.md`
after the hand-patch check. Same safety gate, one directory tree instead of two. Not done
tonight — didn't want to touch scripts the corpus-wide run was actively depending on.

**Tried and rejected: `find_amud_b.py`'s `nearest_heading` walk-back extension, 2026-08-09.**
User caught a real placement issue on `bava_batra_174`: the amud-b marker landed under
`### Rav Pappa: Two Readings` (the heading containing the first-matched amud-B blockquote), but
the immediately preceding `### Orphans Case: Rav Pappa` was already an English paraphrase of that
exact same passage — the marker should have landed one heading earlier. Built a bounded "one-hop"
extension: if the found `###` heading's immediately preceding sibling (same parent `##`, so it
never crosses a macro boundary) has zero blockquotes of its own, use that one instead — capped at
one hop, no chaining. Corpus-wide `--dry-run` comparison against the last real run: **740 of 2,240
dafim would shift** — far more than expected for a narrow case. Spot-checked 5 by reading the
actual content on both sides of the shift: 3 were genuine improvements (clean paraphrase-then-quote
of the identical passage, same shape as BB174), 1 was a real regression (`Hullin_13`'s
`"### Objection to Intent"` is a *separate* Gemara point in the same sugya, not a preview of what
follows — the tweak pulled the marker back into unrelated amud-A content), 1 was ambiguous. **"No
blockquote in the preceding section" isn't reliable evidence that it's thematically a preview of
what's next** — most no-blockquote sections are ordinary commentary/discussion unrelated to the
upcoming quote, and a heading-position heuristic can't tell the two apart from structure alone.
Reverted (`git checkout -- daf-processor/find_amud_b.py`), nothing written to any daf. A real fix
would need actual content/topic matching between the candidate section and the upcoming quote —
plausible via an LLM call per candidate, not attempted.

### Amud-b relabeling — analyzed and applied, 2026-08-03

**Conclusion: the existing directory-suffix-driven `.5` numbering system (see `parse_dir_name()`/`daf_to_float()` in `upload_to_supabase.py`) was already correct for the large majority of the corpus.** Only a small number of "Xb" directories turned out to be mislabeled full dapim.

**Method — `analyze_amud_b_promotion.py`** (dry-run, no writes; report at `review_v10_relocated/amud_b_promotion_analysis.csv`): for every "Xb" directory, matches each individual Sefaria item of (a) its own amud b and (b) the next daf's amud a against `03_final.md` (same anchor-matching approach as `find_amud_b.py`'s own prev-daf check), giving a content-weighted coverage percentage for both sides of the boundary — not a text-position heuristic, and not dependent on `shiur_start_amud`/`amud_b_segment_index` (both were considered and rejected as the primary signal — too fragile to a one-line boundary-detection miss; see git history of this file's own discussion for the reasoning). `room_for_promotion` (no existing plain `X+1` directory to collide with) is computed separately from coverage, since the two questions are independent.

**Decision rule** (user-set, 2026-08-03): promote "Xb" → plain "X+1" only when there is room AND next-daf-amud-a coverage is ≥70% with high combined total-daf coverage. Otherwise leave as "Xb".

**Applied — 7 directories renamed** (physical `mv`, `output/` only — Supabase not yet touched, see below):
- `hullin_29b` → `hullin_30`
- `nazir_26b` → `nazir_27`
- `hullin_44b` → `hullin_45`
- `niddah_72b` → `niddah_73`
- `bekhorot_36b` → `bekhorot_37`
- `bekhorot_45b` → `bekhorot_46`
- `bekhorot_40b` → `bekhorot_41`

**Stale metadata from this rename — fixed, 2026-08-03.** Each renamed directory's `01_segmentation.json` still had the OLD `daf` number and `amud: "b"` internally right after the `mv`. Corrected for all 7: `daf` incremented to match the new directory (e.g. `hullin_30`'s `daf` field is now `30`, not `29`), `amud` set to `"a"` (coverage data shows these substantially cover the new daf's amud a, not its amud b — see the coverage table above). Also cleared the now-invalid derived fields that `find_amud_b.py`/`find_sefaria_indices.py` had computed relative to the *old* identity (`shiur_start_daf`, `shiur_start_amud`, `amud_b_segment_index`, `amud_b_timestamp`, `amud_b_micro_title`, `amud_b_sefaria_index`) rather than leave stale/misleading values sitting in the file — they'll be regenerated correctly the next time those scripts run on these directories (which needs to happen anyway once v10 is rerun on them, since their content also needs re-assembling around the new daf identity — see the v10-not-yet-rerun-corpus-wide note above). Original JSONs backed up as `01_segmentation.json.bak_before_promotion_fix` in each of the 7 directories.

**Left as "Xb" (no room for promotion) — needs separate investigation, not yet resolved:**
- `menachot_35b` (90.0% total coverage, blocked by existing `menachot_36`)
- `menachot_36b` (89.2%, blocked by `menachot_37`)
- `menachot_50b` (89.0%, blocked by `menachot_51`)
- `menachot_59b` (79.2%, blocked by `menachot_60`)
- `menachot_64b` (87.5%, blocked by `menachot_65`)

These 5 look like they should also be full dapim by the same coverage rule, but a plain `X+1` directory already exists for each, so promoting would collide. **Punch-list item: investigate what's actually in `menachot_36`/`37`/`51`/`60`/`65` — is that pre-existing content legitimate and distinct, or is there a data-identity problem here (duplicate/overlapping/mislabeled audio, same class of issue as the "19 severe" list above) — and figure out how to make room before these 5 can be promoted.** (Three other Menachot "Xb" dafim — 28b/29b/49b — were also blocked but scored lower, 51.9%/63.9%/71.7% total coverage; left as-is, not part of this follow-up.)

**Punch-list item, after the Menachot investigation above is resolved:** rerun `upload_to_supabase.py` for the affected tractates (Hullin, Nazir, Niddah, Bekhorot, and Menachot once fixed) so Supabase's `shiur_content` rows pick up the corrected `.0`/`.5` daf numbers from the new directory names — not done automatically by the rename itself.

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
| `DedicationService.swift` | Fetches + decodes the daily/weekly/monthly learning dedication banner |

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
| `data/api/DedicationService.kt` | Fetches + decodes the daily/weekly/monthly learning dedication banner |

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

## Dedications (daily/weekly/monthly learning banner)

Shown once per day on app launch when an active row exists. Data source: public Supabase table
`dedications` (project `zewdazoijdpakugfvnzt`, readable with the anon key already embedded in
`DedicationService.swift`/`.kt`) — columns `date`, `end_date`, `dedicated_by`, `honoree_name`,
`period` (`"today"`/`"week"`/`"month"`), `preposition`, `occasion`, `display_text` (optional
override), `photo_url`, `status` (`"approved"`).

- **Date range (`date` → `end_date`)**: `end_date` (added via `dedication-date-range-migration.sql`,
  this repo's root — run manually in the Supabase SQL editor, same reason as the app-targeting
  migration below) is the actual source of truth for whether a dedication is active — a plain
  `date <= today <= end_date` range, which lets a dedication cover any arbitrary span, not just a
  calendar week/month. `period` no longer determines the active window at all — it now controls
  **only the display wording** ("Today's Learning" / "This Week's Learning" / "This Month's
  Learning"), decoupled from how long the range actually is. `DedicationService.fetch()` on every
  platform filters this directly in the Supabase query (`date=lte.<today>&end_date=gte.<today>`)
  rather than fetching a lookback window and filtering client-side — the old `isActiveToday`
  calendar-window computation (which used to compare `Calendar.current`'s `weekOfYear`/`month`
  granularity) is gone entirely on every platform; there's nothing left to keep in sync with the
  admin form's own week/month math (see below). `end_date` is `NOT NULL` in the DB (defaults to
  `date` for a single day) and is asserted `>= date` by a check constraint.
- **Conflict handling**: multiple dedications can be simultaneously active (their ranges overlap).
  `dedication-form.html` warns the admin at approval time (submitting with "Publish immediately"
  checked, or clicking "Approve" in the pending queue) if the row being approved overlaps another
  *already-approved* row that shares at least one app flag — `findOverlaps()`/
  `confirmNoBlockingOverlap()` — via a `confirm()` dialog listing the conflicting row(s). This is a
  warning, not a hard block; the admin can still save. If more than one dedication ends up active
  on the same day regardless, `fetch()` picks one deterministically: `period`'s display tier
  (today > week > month) first, then most recently created (`order=date.desc,id.desc`) as the
  tie-break — unchanged from before this feature, just no longer the *only* line of defense against
  silently dropping one.
- **App targeting**: three independent boolean columns — `for_anydaf`, `for_anytorah`,
  `for_anytorah_web` — replacing an older single `app` text column (`"anydaf"`/`"anytorah"`/`"both"`)
  that couldn't target AnyTorah Web independently of native AnyTorah. `DedicationService.swift`/`.kt`
  here filter `for_anydaf=eq.true`; AnyTorah's native services filter `for_anytorah=eq.true`;
  AnyTorahWeb's `app/api/dedication/route.ts` filters `for_anytorah_web=eq.true`. Migrated via
  `dedication-app-targeting-migration.sql` (this repo's root) — run manually in the Supabase SQL
  editor, since no service-role key is available to any of these codebases to run DDL
  programmatically. The old `app` column is left in place, unused, after the migration.
- **Admin submission form**: `dedication-form.html` (this repo's root) — a standalone HTML/JS tool
  (not part of either app build) for creating/editing dedication rows, with three independent
  checkboxes (AnyDaf / AnyTorah / AnyTorah Web) instead of the old three-way radio group, plus a
  Start date/End date pair (with a "Auto-fill end date from this" button that fills End date from
  the Period selector's week/month convention — Sunday-start week, last day of the calendar month —
  purely as an editing convenience; the admin can always type any End date directly).
  `getAppFlags()`/`appLabel()` work identically against either live form state or a stored DB row.
- **Known quirk (not a bug):** the `date`/`end_date` columns have no timezone, and the active-range
  query compares against each platform's local "today" (`Calendar.current`/`LocalDate.now()` —
  effectively local time — against columns with no stored offset). A dedication can roll into or
  out of its window up to a day early/late for users far from UTC, depending on which side of UTC
  midnight they're on relative to the stored dates.

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

### ForEach(id: \.element.id) with a timestamp-based id — duplicate-pill bug (iOS)

`ShiurSegment.id` and `ShiurMicroSegment.id` are both defined as `var id: String { timestamp }` (`ShiurClient.swift`). Timestamps are not guaranteed unique — `repair_segmentation()`'s non-contiguous-macro splitting (`pipeline.py`) can legitimately produce two adjacent macro segments sharing the exact same timestamp (confirmed case: Avodah Zarah 2's "Judgment Midrash (II)" and "Persia & Nations" both at `62:48`).

All three iOS pill strips that iterate `shiurClient.segments`/`audioSegments` used `ForEach(Array(...enumerated()), id: \.element.id)` — when two adjacent elements share an `id`, SwiftUI's diffing can conflate their rendered state, producing the exact reported symptom: two consecutive pills, both showing the *first* segment's label, both lighting up together. Confirmed via a full trace: data was verified duplicate-free both locally and in Supabase before the bug was found in the rendering layer.

**Fix:** all three sites (`ContentView.swift`'s `shiurNavigationStrip` and `chapterStrip`, `StudyModeView.swift`'s `textNavigationStrip`) now use `id: \.offset` (the enumerated array index — always unique) instead of `id: \.element.id`. The separate `.id(idx)` modifier used for `ScrollViewReader`/`proxy.scrollTo` at each site was already index-based and untouched.

**Android does not have this bug** — `itemsIndexed(shiurSegments)`/`itemsIndexed(audioSegments)` (`StudyModeScreen.kt`, `ContentScreen.kt`) pass no explicit `key`, so Compose defaults to positional identity, which is inherently immune to timestamp collisions.

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

### Audio Resources (Iggros Moshe A to Z podcast)

**Important caveat found after this was built (see "WordPress Audio Posts (Blocked)" below): the ~45 real current episodes of this podcast live in a separate `audio` custom post type that is not exposed via REST at all, so they will not appear in the app no matter how much reference-tagging happens on them, until that's fixed on the WordPress side.** Everything below works correctly for any post that *is* reachable via `/wp/v2/posts` (which includes a small 2018–2020 legacy duplicate set of this same podcast, currently untagged) — it just isn't the full current episode catalog yet.

The `reference` taxonomy on library.yctorah.org was extended to audio content — the reachable posts are **plain WordPress `post` entries**, so they flow through the exact same bulk `/wp/v2/posts?reference=<ids>` query as articles with zero query changes once WP-side tagging reaches one.

- `YCTArticle.isAudio: Bool`/`Boolean` (`StudyModels.swift`/`.kt`) — set in `YCTLibraryClient.fetchBulkArticles` by checking the post's raw `content.rendered` for an `<audio` tag (PowerPress plugin embeds `<audio class="wp-audio-shortcode">` with a `<source src="...">` child). Back-compat decode pattern (`decodeIfPresent(...) ?? false` / `optBoolean(..., false)`) matches the existing `additionalDafs`/`source` fields — **no disk cache version bump needed**.
- Excerpt fallback for audio posts strips the PowerPress `<div class="powerpress_player">...</div>` and `<p class="powerpress_links...">...</p>` boilerplate (`stripAudioPlayerBoilerplate` in both `YCTLibraryClient` files) before falling back to a content-derived excerpt, so cards show the real episode blurb instead of "Podcast: Play in new window | Download ... Subscribe: RSS".
- **HTTP → HTTPS rewrite**: embedded audio `src` URLs are `http://`, which both iOS App Transport Security (no `NSAppTransportSecurity` exception exists in `Info.plist`) and Android WebView cleartext blocking would silently reject. `fetchArticleContent` on both platforms rewrites `src="http://` → `src="https://"` before returning — verified via curl that the HTTPS versions of the actual SoundCloud/library.yctorah.org URLs resolve correctly. Applies to any embedded media, not just audio.
- **No custom audio player was built.** `ArticleReaderView` (iOS) / `ArticleReaderScreen` (Android) already render a post's full HTML in a WKWebView/WebView, which renders `<audio controls>` as a fully working native player for free.
- **JS↔native pause bridge**: a `<script>` injected into the reader's styled HTML (`ArticleWebView.styledHTML()` / `ArticleReaderScreen.buildStyledHtml()`) attaches a `play` listener to every `<audio>` element and posts to a native bridge (`webkit.messageHandlers.audioBridge` via `WKUserContentController`/`WKScriptMessageHandler` on iOS; `window.AudioBridge` via `addJavascriptInterface` on Android — the Android callback arrives off the main thread and must be posted back via `Handler(Looper.getMainLooper())` before touching player state). When an episode starts playing, this pauses the main daf/shiur `AudioPlayer`/`AudioViewModel` if it's currently playing (`onEpisodeAudioPlay`/`onAudioPlay`, threaded down from `ContentView.swift`'s two `StudyModeView(...)` call sites / `ContentScreen.kt` + `StudyModeScreen.kt`'s three `StudyModeContent(...)` call sites, guarded by `if isPlaying { togglePlayPause() }`). **One-directional only** — the reverse (main audio interrupting an already-open episode) isn't handled, since dismissing the reader tears down the WebView (and its audio) anyway.

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

### WordPress Audio Posts (Unblocked and verified working — 2026-07-30)

library.yctorah.org has audio posts (the ~45-episode "Iggros Moshe A to Z" podcast, among others — actually 795 total `audio` posts across all shiur types on the site) at `/audio/[slug]/` URLs, a custom WordPress post type. **The webmaster enabled `show_in_rest` and it is now confirmed live and fully working end-to-end**, verified 2026-07-30 via direct curl against production:

- `/wp-json/wp/v2/types` now lists `audio` with `rest_base: "audio"` — **the guessed `restBase: "audio"` in `YCTLibraryClient.swift`/`.kt` was correct; no code change needed.**
- `reference` taxonomy is registered on the `audio` post type (confirmed via `/wp-json/wp/v2/taxonomies/reference`), and the exact query shape the app uses (`/wp/v2/audio?reference=<comma-joined-daf-term-ids>&per_page=100&...`) returns real results — e.g. querying all of Avodah Zarah's daf-level term IDs returned 10 real tagged episodes, including "Episode 32: Jewish Identity – The Kippah, Part 2" (post 14918) with an exact match on Avodah Zarah 18/19/20 (it's tagged with daf terms 3203/3205/1981 respectively, among many other refs).
- As of 2026-07-30, **33 episodes are tagged so far** (out of ~45+), with tags spanning most of Shas. Many of those 33 include both tractate-root-level tags (e.g. "Avodah Zarah" generally) and specific daf-level tags (e.g. "Avodah Zarah 18") in the same post's `reference` array.
- **`fetchesTractateLevel` flipped to `true` (2026-07-30)**, matching `psak`. It was originally `false` (copied from `library`), which would have made episodes tagged *only* at the tractate-root level (no specific daf) permanently invisible — the client would never query the root term ID, only its daf-level children. A full census of all 33 tagged episodes (as of 2026-07-30) found none were actually affected — every tagged episode already carries at least one daf-level tag alongside any general/root-level ones — so the flip is a forward-looking safety net rather than a fix for an observed problem. Root-only-tagged episodes now land in the "tractate-wide" bucket at daf 0, same as psak.
- **Verified concrete in-app test case**: open Avodah Zarah daf 18, 19, or 20 in Study mode → Resources tab should show "Episode 32: Jewish Identity – The Kippah, Part 2" as an exact match, with the headphones badge.
- If results don't appear in the app despite this: the audio client's results are session-memory-only (never disk-cached, see below) — a **full app restart** (force-quit, not just backgrounding) is required to clear any empty result cached from before the WP fix went live, since revisiting the same tractate/daf reuses the in-memory cache without refetching.

**Bug found and fixed 2026-07-30 — real hits were being silently dropped by the parser**: after the WP fix landed, in-app testing on Avodah Zarah 18a still showed zero results despite the raw endpoint genuinely returning hits. A temporary debug banner (added to the Resources tab, both platforms — see below) proved the request itself was fine: `HTTP 200, raw array length=10` for the exact URL the app builds. The bug was downstream, in `fetchBulkArticles`'s per-post parsing:

- The `audio` custom post type's `register_post_type()` doesn't declare excerpt support, so its REST response **omits the `excerpt` key entirely** — confirmed via curl: `keys present: [_embedded, _links, content, date, id, link, reference, slug, title]`, no `excerpt`.
- Both platforms required `excerpt` as part of a single guard/get-chain per post (Swift: `guard let excerptObj = post["excerpt"] as? [String: Any], let excerptRaw = excerptObj["rendered"] as? String ... else { continue }`; Kotlin: `post.getJSONObject("excerpt").getString("rendered")`, which throws `JSONException` when the key is absent). Since every audio post lacks this key, every single one silently failed to parse and was dropped — 10 real hits in, 0 articles out, no error surfaced anywhere.
- **Fix**: `excerpt` is now optional on both platforms, defaulting to `""` when the key is missing (Swift: `((post["excerpt"] as? [String: Any])?["rendered"] as? String) ?? ""`; Kotlin: `post.optJSONObject("excerpt")?.optString("rendered", "") ?? ""`). The existing content-derived-excerpt fallback (strip PowerPress boilerplate, truncate to 200 chars) already handles the "excerpt is empty" case, so this was the only change needed. Both platforms rebuilt clean.
- **This was a pure app-side bug, not a WordPress config issue** — no further WP-side change needed for it. (Excerpt support *could* be added to the CPT registration too, but isn't necessary now that the app tolerates its absence.)

**Debug banner (temporary, still in the code as of 2026-07-30 — remove once confirmed stable)**: `ResourcesManager`/`ResourcesViewModel` publish `audioDebugInfo` (a `@Published`/`StateFlow<String>`), rendered as a small orange monospace banner at the top of the Resources tab. It reports tractate-term resolution, daf-term count, raw hit count, and post-dedup count for the audio fetch specifically. On zero raw hits, it automatically re-runs the identical request through `fetchBulkArticlesDebugInfo` (a new diagnostic-only method added to `YCTLibraryClient` on both platforms) to report the true HTTP status and raw response array length/snippet — bypassing Android's `fetchString()`, which otherwise silently swallows all exceptions to `null` with no logging. This is what caught the excerpt-parsing bug above; without it the failure would have looked identical to a network problem from the outside.

Historical context (now resolved) — as of 2026-07-22 this post type was confirmed via the full `/wp-json/` route index to have zero REST exposure at all, which is what originally blocked this feature:

**Do not confuse these with the older regular-`post`-type entries** titled "Episode 1" through "Episode 15", "BONUS: Intro Episode", "Why Iggros Moshe A to Z?" (WordPress post IDs 14614–14630, living at plain `/2018/11/episode-N-.../` URLs, last modified 2020-02-27). Those are a separate, apparently-abandoned duplicate/legacy set from when the podcast launched — same episode content, different (and queryable) post type, but as of this writing **not** reference-tagged (confirmed empty `reference` array on all 17, freshly re-checked). Any reference-tagging effort aimed at surfacing this podcast in the app needs to target the real current episodes at `/audio/` — which the REST API cannot reach at all yet, tagged or not.

**What actually unblocks this**: someone with access to the WordPress site's theme/plugin code needs to add `'show_in_rest' => true` (and ideally an explicit `'rest_base'`) to wherever this "audio" post type is registered (`register_post_type()` call, likely in a theme functions file or a custom plugin) — this is outside the AnyDaf codebase entirely. As of 2026-07-22 the user wasn't sure whether they have that access and needed to check.

**Update 2026-07-22 — the app-side follow-up is now already built, ahead of the WP fix**, so results appear the moment REST access is turned on (no app release needed to test it):

- `YCTLibraryClient` (both platforms) gained a `restBase` parameter (default `"posts"`) generalizing the previously-hardcoded `/posts` path in `fetchBulkArticles`/`fetchArticleContent`.
- A third static client instance, `YCTLibraryClient.audio` (source `.audio`/`YCTSource.AUDIO`), points at the same `library.yctorah.org` host with `restBase: "audio"` and `talmudTermID: 1899` (same taxonomy tree as `library`, since it's the same site).
- **`restBase: "audio"` is a guess**, matching the CPT's URL slug (`library.yctorah.org/audio/[slug]/`) and WordPress's default of using the post type slug as the REST base when none is explicitly set. Once REST access is enabled, check `/wp-json/wp/v2/types` for the real `rest_base` and update the constant in both `YCTLibraryClient.swift` and `.kt` if it differs from `"audio"`.
- `ResourcesManager`/`ResourcesViewModel` now fetch all three clients (library, psak, audio) in parallel per tractate. The audio fetch uses a **non-throwing wrapper** (`fetchAllFromClientSafely`) so its current 404 (route doesn't exist yet) can't take down the library/psak fetch it runs alongside — verified this doesn't regress existing behavior by rebuilding both platforms clean (`xcodebuild` / `./gradlew assembleDebug`) after wiring it in.
- **The audio client's results are deliberately NOT disk-cached** (`ResourcesDiskCache` is skipped for it on both platforms) — everything else is disk-cached with a 7-day TTL, which would otherwise prime an empty result for up to a week after the WP fix lands. Audio is re-fetched live every `loadResources` call instead (still deduplicated per-session via the in-memory `allArticlesCache`), so the very next app launch after `show_in_rest` goes live will show real results with no waiting and no cache-clearing needed.
- The audio-detection, excerpt-cleanup, HTTPS-rewrite, badge UI, and JS pause-bridge work described below under "Audio Resources" was already generic (keys off `<audio` in the content, not off which post type or site it came from) — it needed no changes to handle this third source.
