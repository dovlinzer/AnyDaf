# v10 review set — v9 vs v10 side by side, generated 2026-07-29

**Correction to my last message: none of these 13 dafim were "approved."** You reviewed 4
(Gittin 18b, Berakhot 31b as references from an earlier session, plus Bava Batra 174, 153,
103 this session) and found the tail-overrun defect in the last three. The other 9 were
generated for review but you haven't looked at them yet. This folder is for that — v9 and
v10 side by side so you can judge v10's quality fresh, and compare to v9 wherever you want.

## What changed between v9 and v10

v10 adds one guard to the matching stage: a match that jumps far ahead in the text (more
than 3 Sefaria segments past the last accepted one) is only trusted if its confidence score
is high, or it's discarded. Nothing else changed — same rewrite text, same alignment logic,
same completeness guarantee (sections/segments in = sections/segments out, still asserted
before writing).

The guard is symmetric: it can trim an isolated jump at the END of a span (the defect you
found — unrelated next-daf content dragged in) or at the START (an isolated match on the
*previous* daf's review-chatter dragged in before the real opening — the same phenomenon
that motivated the WINDOW_ENTRIES constant, just a case that constant didn't fully catch).

## Per-daf comparison

| Daf | v9 matched | v9 span | v10 matched | v10 span | What moved |
|---|---|---|---|---|---|
| [Bava Batra 103](bava_batra_103_v9.md) / [v10](bava_batra_103_v10.md) | 14 | (9,30) | 14 | (9,24) | tail −6 — the Mishna's own closing words restored after a first attempt lost them, spurious Gemara after them removed |
| [Bava Batra 153](bava_batra_153_v9.md) / [v10](bava_batra_153_v10.md) | 19 | (9,36) | 19 | (9,30) | tail −6 — a same-instant phantom match (physically impossible) swapped for a real, later, distinct match |
| [Bava Batra 174](bava_batra_174_v9.md) / [v10](bava_batra_174_v10.md) | 22 | (15,62) | 21 | (15,40) | tail −22 — next daf's mishna opening no longer dragged in |
| [Bava Batra 84](bava_batra_84_v9.md) / [v10](bava_batra_84_v10.md) | 20 | (7,35) | 20 | (7,28) | tail −7 — same defect pattern as above, **not yet reviewed by you** |
| [Bava Metzia 11b](bava_metzia_11_v9.md) / [v10](bava_metzia_11_v10.md) | 32 | (9,46) | 32 | (9,46) | unchanged |
| [Berakhot 31b](berakhot_31b_v9.md) / [v10](berakhot_31b_v10.md) | 56 | (51,111) | 56 | (51,111) | unchanged (reference daf) |
| [Gittin 18b](gittin_18_v9.md) / [v10](gittin_18_v10.md) | 27 | (8,38) | 27 | (8,38) | unchanged (reference daf) |
| [Hullin 88b](hullin_88_v9.md) / [v10](hullin_88_v10.md) | 21 | (10,31) | 21 | (10,31) | unchanged |
| [Nazir 59b](nazir_59_v9.md) / [v10](nazir_59_v10.md) | 16 | (19,39) | 15 | (19,33) | tail −6, **not yet reviewed by you** |
| [Niddah 60b](niddah_60_v9.md) / [v10](niddah_60_v10.md) | 40 | (20,65) | 39 | (20,65) | span unchanged but one internal match swapped (1 fewer) |
| [Niddah 67a](niddah_67_v9.md) / [v10](niddah_67_v10.md) | 29 | (0,29) | 29 | (0,29) | unchanged |
| [Yevamot 33](yevamot_33_v9.md) / [v10](yevamot_33_v10.md) | 29 | (5,47) | 27 | (14,47) | head +9 — opening isolated match(es) into the *previous* daf trimmed, **not yet reviewed by you** |
| [Zevachim 29](zevachim_29_v9.md) / [v10](zevachim_29_v10.md) | 28 | (9,60) | 24 | (18,60) | head +9 — same as above, **not yet reviewed by you** |

## Suggested order

Start with the 4 marked "not yet reviewed by you" plus Bava Batra 84 — those are where v10
diverges from what you'd be seeing for the first time either way, so reading v10 costs you
nothing extra over reading v9 would have. The 6 "unchanged" and 2 "reference" dafim are
identical in content between v9 and v10 (only the file changed, not the text) — read
whichever copy is convenient, there's no difference to compare.

For the 5 divergent dafim, the interesting question is specifically the boundary that
moved: BB84's ending, and Yevamot 33 / Zevachim 29's openings. Everything else in those
essays is untouched.

## Provenance

Source: `daf-processor/output/<daf>/03_text_first_prototype_v{9,10}.md`. These are copies.
Regenerate with:

    python3 prototype_text_first_v9.py output/<daf>
    python3 prototype_text_first_v10.py output/<daf>
