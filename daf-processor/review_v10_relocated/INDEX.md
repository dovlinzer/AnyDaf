# v10 + LLM relocation check — generated 2026-07-31

This is the fix for the "confident wrong opening" placement defect (a Talmud quote landing
under the wrong nearby heading) that v10's algorithmic search couldn't solve without
introducing more regressions than fixes — see CLAUDE.md, "confident wrong opening" and
"Tried and rejected: transliteration matching + IDF word-rarity reweighting."

## What this is

`relocate_check.py` asks Claude (Sonnet, `REWRITE_MODEL`) whether each ambiguous Talmud
quote in a v10 output is under the right heading, restricted to a LOCAL window — every
heading between the previous quote and the next one in the essay, never a daf-wide search.
`apply_moves.py` applies the high-confidence verdicts and writes a patched copy.

Run on the same 13-daf review batch: 204 checks, 62 moves recommended (59 high confidence,
3 medium, 0 low). Spot-checked against every case previously confirmed by hand this
session — all matched, including one (Bava Metzia 11's "Open Questions" segment) that no
algorithmic approach found all day, because the correct section is written in
transliteration with zero shared English words against Sefaria's translation.

## Files

- `{daf}.json` — every ambiguous quote checked, its candidates, and Claude's verdict + reasoning
- `{daf}_relocated.md` — the v10 output with high-confidence moves applied, for direct comparison against `../review_v10/{daf}_v10.md`

## Cost, if this scales corpus-wide

~1,670 input / ~150 output tokens per check. At the 13-daf batch's rate (~15.7 checks/daf)
across the ~2,343 processable dafim: roughly **$270 standard API, ~$130-135 via the Batch
API** (CLAUDE.md's default for anything at that scale). v10 itself has only been run on 20
dafim on disk so far — a corpus-wide `--all` pass (free, script-only) would need to happen
first.

## Process A verify/patch — built and run, 2026-08-02

`fix_wall_of_text.py` is the Claude verify/patch stage for `wall_of_text2.py`'s candidates,
mirroring `fix_pass2_gaps.py`'s two-stage shape (Haiku verify, Sonnet patch). Run on this same
13-daf batch: 87 raw flags → 69 usable (Berakhot 31b's 18 were discarded — its `02_rewrite.md`
headings were never synced to segmentation's `display_title`s, so the ratio check silently
failed on every section there) → 46 confirmed real gaps, patched. Zevachim 29 had 0 confirmed
(all 4 flags were false positives). Cost: ~$0.38 total (Batch API, Haiku + Sonnet).

**`{daf}_wall_patched.md` files here are a different pipeline stage from `{daf}_relocated.md`.**
They patch `02_rewrite.md` (pass 2, before Gemara blockquote insertion) — a separate, upstream
concern from this directory's main content (Approach B / v10's quote-placement fix, which
operates downstream on the assembled essay). Compare a `_wall_patched.md` file against its
daf's plain `02_rewrite.md` in `output/<daf>/`, not against `_relocated.md`, to see what
changed. Not yet promoted to `02_rewrite.md` itself — under human review.

## Berakhot 31b header fix — `title_string_pass.py`, 2026-08-02

Berakhot 31b was in the documented "108 count-mismatched" set (`title_pass_mismatched.txt`:
`h2 10/10 h3 32/33`) — its 32 `###` headings are independently-written full sentences, not
derived from segmentation's `display_title`s, so neither `apply_display_titles.py`
(positional — unsafe when counts differ) nor `sync_md_headers.py` (only handles a stale
"(II)"-suffix rename, not full reworded headings) could fix it. Built `title_string_pass.py`
to align the two ordered label sequences (segmentation display_titles, essay headings, per
level) by content-word overlap (exact + phonetic-key + shared-prefix, scored via a monotonic
DP allowing skips on both sides — same structural idea as `align_constrained()` in
`prototype_text_first_v10.py`, one level up). Dry-run by default; low-confidence matches are
flagged and never auto-applied. Result on Berakhot 31b: 19 of 32 headings confidently relabeled
and applied; 13 left untouched (genuinely weak word-overlap cases — metaphors, heavy
paraphrase — same class of blind spot as the corpus's documented "confident wrong opening"
cases, not something to force). `wall_of_text2.py` then found exactly 1 real candidate
("Three Saving Verses") among the 19 now-working sections — confirmed and patched.
Reusable for the other 107 dafim in the mismatched set via
`python title_string_pass.py --mismatched-file title_pass_mismatched.txt --apply`.

## `{daf}_wallpatched_relocated.md` — full pipeline, both fixes combined, 2026-08-02

These 11 files run the wall-of-text-patched essay (`output/<daf>/02_rewrite_wall_patched.md`)
through v10 assembly (`output/<daf>/03_text_first_prototype_v10_wallpatched.md`) and then
`relocate_check.py`/`apply_moves.py` on top of that — so the wall-of-text prose changes are
reviewable with the actual Gemara blockquotes inserted, not as bare pass-2 text. Same source
files as `{daf}_wall_patched.md`, just carried one and two stages further downstream.

## Divider-splice bug — found and fixed, 2026-08-02

`apply_moves.py`'s `h3_insert_points()` computed where a relocated quote lands as "right
before the next `##`/`###` heading" — but didn't know about bare `---` divider lines (which
`relocate_parse.py` deliberately treats as invisible). Whenever the move target was the last
`###` under its `##` macro, content landed *after* the `---`, misreading as introducing the
next macro section instead of concluding the one it was moved into. Confirmed on Bava Metzia
11's "Reconciliation" and Bava Batra 153's "Ruling & Clarification" (both correctly chosen
targets, wrongly spliced) — and, once fixed, also silently changed Nazir 59 and Niddah 60.
Fixed by having the insert-point scan stop at a `---` if one falls inside the target section's
own span. All 13 `{daf}_relocated.md` files were regenerated with the fix (free — reuses the
cached `.json` verdicts, no new API calls) and the 11 `{daf}_wallpatched_relocated.md` files
above already include it from the start.

## `{daf}_wallpatched_split_relocated.md` — quote-run splitting, 2026-08-02, UNDER REVIEW

Found on Niddah 60: `relocate_check.py` could only move an entire quote run to ONE destination
heading, even when the run itself spans two genuinely different topics that v10's own
content-density scoring wrongly merged (a short resolution baraita + a full new Mishnah and its
Gemara, all dumped under "Bar Pada Framework" because that heading's long prose out-scored every
shorter candidate for every item in the range — see CLAUDE.md). Fixed by giving `relocate_check.py`
a second response form: split the run at one point and choose a heading for each half (capped at
one split, i.e. two pieces, to limit disruption — see CLAUDE.md). `relocate_parse.py`'s windows now
expose each item's Hebrew/translation individually so the model can name a precise split point;
`apply_moves.py` moves each half independently.

**Re-run against all 13 test-batch dafim; split triggered far more than expected — 21 splits
across 12 of 13 dafim, vs. the single confirmed real bug (Niddah 60) that motivated this. At
least one split's own reasoning is self-contradictory (Bava Batra 153's first split argues for
both 'Rav Position' and 'Shmuel Position' for the same two items, mid-sentence) while still
marked high confidence on both halves.** Likely means the split threshold is currently too easy
to reach — almost any 2+-item run has *some* internal seam if the model looks for one, and the
prompt doesn't yet make clear that isn't sufficient justification. Only apply high-confidence
splits made it into these `_relocated.md` files (same bar as single moves), but treat all of them
as unverified until manually reviewed — this is exploratory output, not a vetted fix.

**Update, same day — two bugs fixed, re-run:** (1) `check_window()`'s `max_tokens` was 400,
too little once the model reasons through a multi-item run before answering — long runs (6-7
items, e.g. Niddah 60's Bar Pada Framework block) hit `stop_reason: max_tokens` mid-JSON and
silently returned `None`, so nothing was applied and the block stayed exactly where it started.
Raised to 800. (2) The split-trigger prompt language was tightened with concrete criteria (a
new Mishnah, a genuinely new/independent case, vs. multiple Sages refining the same point or a
challenge-and-resolution chain, which is NOT grounds to split). Also fixed: applying a split no
longer requires BOTH halves to be high confidence — each half is gated on its own confidence
independently, since a "stays where it is" half scoring only medium shouldn't block a
high-confidence move on the other half (this is what silently dropped Niddah 60's real fix the
first time even after the token fix, until this second gate was corrected too).

Re-run against all 13 test-batch dafim: 196 checks, 1 null (down from the earlier truncation
issue), 22 splits. 11 of the original 21 splits persisted unchanged under the stricter prompt
(a good consistency signal), a handful dropped out (Hullin 88, Nazir 59, one of Yevamot 33's
two), a few new ones appeared. Niddah 60 and Nazir 59 confirmed fixed by manual review. The
`_wallpatched_split_relocated.md` / `zevachim_29_split_relocated.md` files here are this
corrected version — still under manual review for the rest.
