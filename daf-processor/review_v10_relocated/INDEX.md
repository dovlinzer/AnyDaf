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

## Not yet built

Process A (pass 2 commentary gaps — see CLAUDE.md) has a calibrated mechanical pre-filter
(`wall_of_text2.py`) but no Claude verify/patch stage yet, unlike this one.
