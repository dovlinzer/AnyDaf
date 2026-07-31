# v9 review set — generated 2026-07-29

13 dafim assembled by `prototype_text_first_v9.py` (Approach B: Sefaria text as the backbone,
the shiur spliced into it). Regenerated *after* tonight's display-title and navigation-sentence
cleanups, so these are current.

Every file passed the completeness assertion: **sections in = sections out, Sefaria segments in
= segments out.** Nothing here can be missing content — the only thing under review is whether
the Gemara is placed in the *right* spot.

| Daf | Matched segs | Sefaria span | Sections | Anchored | Splits blocked | Note |
|---|---|---|---|---|---|---|
| [Bava Batra 103](bava_batra_103.md) | 14 | 9–30 | 47 | 10 | 4 | nav sentence reworded, not deleted — see note |
| [Bava Batra 153a](bava_batra_153.md) | 19 | 9–36 | 42 | 16 | 2 |  |
| [Bava Batra 174b](bava_batra_174.md) | 22 | 15–62 | 31 | 13 | 2 | the 6-segments-before-the-opening case |
| [Bava Batra 84a-b](bava_batra_84.md) | 20 | 7–35 | 34 | 13 | 4 |  |
| [Bava Metzia 11b](bava_metzia_11.md) | 32 | 9–46 | 50 | 16 | 3 |  |
| [Berakhot 31b](berakhot_31b.md) | 56 | 51–111 | 42 | 23 | 3 | reference daf — regression check |
| [Gittin 18b](gittin_18.md) | 27 | 8–38 | 37 | 17 | 3 | reference daf — v6/v9 identical, tuning baseline |
| [Hullin 88b](hullin_88.md) | 21 | 10–31 | 31 | 12 | 1 | original loss case |
| [Nazir 59b](nazir_59.md) | 16 | 19–39 | 33 | 6 | 3 | lowest anchor rate (6/33) |
| [Niddah 60b](niddah_60.md) | 40 | 20–65 | 76 | 25 | 2 | nav sentence deleted |
| [Niddah 67a](niddah_67.md) | 29 | 0–29 | 66 | 21 | 3 |  |
| [Yevamot 33a-b](yevamot_33.md) | 29 | 5–47 | 41 | 19 | 1 |  |
| [Zevachim 29a-b](zevachim_29.md) | 28 | 9–60 | 51 | 26 | 2 | the daf v7/v8 collapsed to 2 sections |

## What to look for

The known-imperfect behaviours, so you can judge whether they're tolerable:

1. **Header placement** — a heading can sit just before Gemara that belongs to the previous
   section's discussion.
2. **Mid-discussion placement** — where the lecturer circles back, the insertion point can land
   a beat early or late. Worse in aggadic stretches than halakhic ones.
3. **Unanchored sections** — the "Anchored" column is how many sections matched an anchor
   directly; the rest are placed by interpolation. `nazir_59` is the weakest (6 of 33).

## What is *not* under review

- Content loss — mathematically excluded by the assertion above.
- Truncated `…` headings — fixed corpus-wide tonight; 0 remain in these 13.
- Third-person "the lecturer" references — all 116 removed corpus-wide.

## Two edits I made by hand tonight

- `niddah_60` — deleted the opening `Today's daf is Niddah 60b, and we pick up at the Mishnah
  toward the bottom of the amud.`
- `bava_batra_103` — **not a pure deletion.** The original read `Today's daf is 103. We pick up
  immediately after the *mishnah* on 102b, beginning the seventh *perek* of the *masechta*.`
  The tail is the kind of orienting detail you asked to keep, so I reduced it to
  `We begin the seventh *perek* of the *masechta*.` Three words are mine. Say if you'd rather
  the whole sentence went.

## Provenance

Source of each file: `daf-processor/output/<daf>/03_text_first_prototype_v9.md`.
These are copies — editing them changes nothing. Regenerate with:

    python3 prototype_text_first_v9.py output/<daf>
