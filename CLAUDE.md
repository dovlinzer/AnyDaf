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
| Bava Batra 153 | Fabricated tail after the real ending ("let's go on to daf 154 amud bet...") | Corrupted region needs identifying/trimming |
| Bava Batra 174 | Same pattern — fabricated `והלכתא`/next-mishna tail | Corrupted region needs identifying/trimming |

Once each daf's SRT is fixed, that daf needs pass 1 (segmentation) + pass 2 (rewrite) rerun —
**both call the Anthropic API, requiring explicit authorization per the standing rule above**
(state which dafim/passes and the API call count before running) — followed by v10 on that
daf specifically. Don't fold these three into the corpus-wide v10 pass until their SRTs are
fixed; v10 already contains guards against exactly this failure mode (the guarded search
correctly excludes BB153/174's existing corrupted tails today), but starting from a corrected
SRT should also fix the underlying pass 1/2 content rather than just papering over it at the
matching stage.

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

### Menachot 79 — the one SRT with zero Hebrew (open, 2026-07-29)

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

### Daf processing procedure — pass 2.5 → pass 3 → audit → fix → upload

The end-to-end procedure for bringing a daf (or batch of dafs) up to current quality, whether processing fresh or reprocessing older output:

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

Planned corpus-wide order (confirmed 2026-08-02, extends the "Corpus-wide run order when B goes live" checklist above): **header fix → wall-of-text flag/fix → v10 assembly → relocate**. Header fix must come first — v10 copies heading text verbatim into the final output.

**v10 assembly has NOT been run corpus-wide yet — confirmed still outstanding, 2026-08-03.** The `sefaria_next.md` widening fix (`widen_sefaria_next.py --all`, see "Amud-b relabeling" section below and the original fix earlier in this file) only updated the *cached Sefaria text files* on disk. Verified on `yevamot_33` — the daf that originally motivated the widening fix — that its `03_text_first_prototype_v10.md` (and `_wallpatched` variant) both predate the corpus-wide widening run (v10 output last written 2026-07-30/08-02 10:57, widening completed 2026-08-02 14:08) and, as expected, still have no Sefaria blockquote at all for the Rava/Rav Nachman/Er v'Onan passage that spills into 34b — the essay prose discusses it (pass 2 doesn't depend on `sefaria_next.md`), but the sourced quote was never inserted, because v10 hasn't re-read the now-wider pool. **The widening fix doesn't take effect anywhere until v10 is actually rerun** — this applies to all ~1,481 widened dafim, not just Yevamot 33. Needs a corpus-wide (or at least widened-subset) v10 rerun before this step of the checklist can be marked done.

**Header fix**
- [x] 2,251 aligned dafim — `apply_display_titles.py`, applied 2026-07-29.
- [x] 108 mismatched dafim — `title_string_pass.py`, run 2026-08-02. Partial by nature, not a full resolution: 58 of ~226 problem headings fixed (19 on Berakhot 31b + 39 across the rest); 134 had no scoring candidate at all, 53 scored too low to trust — both left untouched (they'll keep silently misreporting `prose=0` for those specific sections in `wall_of_text2.py` until fixed some other way). See the script's own section above for the full breakdown.
- [x] 4 dafim with unreadable segmentation JSON (`arakhin_3`, `bava_batra_128`, `bekhorot_25`, `zevachim_36`) — fixed 2026-08-02, same leftover-markdown-code-fence pattern already documented for `hullin_101` above (stripped the fence, verified the JSON parses). Header-synced 2026-08-02: `arakhin_3`, `bava_batra_128`, `zevachim_36` were already count-aligned and already had correct headings (nothing to change); `bekhorot_25` has a micro-count mismatch (105 vs 104) and one residual low-confidence case after `title_string_pass.py` (`"Why Chiya Wouldn't Adopt Rav Assi's Position" -> "Chiya's Counterpoint"`, score 1.00 — plausibly correct on inspection, left unapplied per the confidence gate; a manual call if wanted). None of the 4 are on `title_pass_aligned.txt`/`title_pass_mismatched.txt` yet — regenerate those snapshots before the corpus-wide push so these 4 aren't silently skipped.

**SRT corruption — needs pass 1 + pass 2 rerun (API calls, needs authorization) before v10**
- [x] Bava Batra 153 — SRT fixed by user, 2026-08-02. **Still pending:** pass 1 + pass 2 rerun, then redo wall-of-text fix + v10 + relocate — this session's work on BB153 (wall-of-text patch, v10 assembly, relocation) was done against the *old*, corrupted-SRT-derived content and needs to be regenerated from the fixed SRT, not kept.
- [x] Bava Batra 174 — same status as BB153.
- [ ] Menachot 79 — SRT still pending re-transcription (0% Hebrew, see "Menachot 79" section above). Held out of the corpus batch until fixed, same as BB153/174 were.

**Data-identity issues — user investigating/fixing directly, not a processing-pipeline task**
- [ ] 19 "severe" mislabeled-audio dafim (see list above) — user reviewing.
- [ ] `pesachim_19` (segmentation content is actually Gittin 18b) — user fixing.
- [ ] `eiruvin_33`/`eruvin_33`, `eiruvin_82`/`eruvin_82` duplicate directories — user fixing.

**12 "mechanical-fix-only" dafim** (`avodah_zarah_2/58/67/70`, `bava_batra_111`, `bava_kamma_76`, `ketubot_18/29/55`, `nedarim_53`, `sukkah_13/36`) — **no separate action planned.** Since Approach B/v10 fully replaces pass 2.5+3, these get properly reprocessed by the same corpus-wide v10 push as every other daf — the original "needs a real pass-3 rerun" framing is obsolete now that pass 3 itself is being retired. Just confirm none of these 12 ends up on an exclusion/held-out list (like BB153/174/Menachot 79) when the batch actually runs.

**Dropped**
- ~~271-daf stale flagged list from the old `check_anchor_section_mismatch.py` scan~~ — dropped by user request, 2026-08-02. (Also likely moot on its own merits: that checker targets fabrication/dropped-content defects specific to the old LLM-reproduction pass 3; v10 asserts completeness invariants and structurally can't fabricate or drop content, so this whole defect class may not transfer to v10 output — unverified, but not worth chasing now that it's dropped.)

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
`DedicationService.swift`/`.kt`) — columns `date`, `dedicated_by`, `honoree_name`, `period`
(`"today"`/`"week"`/`"month"`), `preposition`, `occasion`, `display_text` (optional override),
`photo_url`, `status` (`"approved"`).

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
  checkboxes (AnyDaf / AnyTorah / AnyTorah Web) instead of the old three-way radio group.
  `getAppFlags()`/`appLabel()` work identically against either live form state or a stored DB row.
- **Known quirk (not a bug):** the `date` column has no timezone, and `isActiveToday` compares in
  UTC (`Calendar.current`/`LocalDate.now()`, both effectively local — but the stored `date` itself
  has no offset). A `period: "today"` dedication can roll out of its window before local midnight
  for users west of UTC.

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
