# Sages chart for all of Shas: plan (draft, 2026-10-29)

Part of the planned Reference Tools button (see TODO.md). The daf's own Sages window stays as it
is: it shows only the sages on that daf, so it is small. This plan is for the Shas-wide chart, and
for the relationship view, which serves both.

## The problem

There are too many names. A cell like "Amora'im, generations 1–2, Eretz Yisrael" is still a crowd,
and any rule that hides the minor sages fails the reader who comes looking for one of them.

**The answer in short:** never show everyone at once, and never make anyone unreachable. Each view
shows the most-quoted sages first. Anyone else is one search or one "+12 more" away, and when you
find a minor sage they appear in place, among the major ones, so you can see where they belong.

## What we have (measured 2026-10-29, `daf-processor/outline/sages/sages.json`)

- **1,032 people from Sefaria.** 352 of them are classed as tanna, amora or zug, with a generation
  and region. The other 680 have no class. Most of these are Yerushalmi names pulled in as someone's
  teacher or student (Rebbi Yose b. Rebbi Abun), plus a few non-sages (King Shapur).
- **The relationships are thin.** 188 of the 352 have any teacher or student. There are only 2
  colleague links in the whole set. Rabbi Akiva has 3 teachers, 18 students and no colleagues; Rav
  has the most students, 21.
- **Prominence:** Sefaria's `num_sources` (how often each person is cited across its library). Only
  153 of the 352 are cited 50 times or more.

**So the graph view needs better data before it is worth much.** Rava and Abaye, the classic pair
of colleagues, aren't even linked.

## Who counts as "major": tiers, not a cutoff

We count each sage's mentions across the whole Bavli from `daf_text`. This is local and free: it
uses the same name matcher `build_sages.py mentions` already runs on one daf, applied to all 5,407
amudim. That count is more relevant to us than Sefaria's, which also counts the Yerushalmi and
midrash. It sorts everyone into three tiers:

| Tier | Roughly | Shown |
|---|---|---|
| 1 | the ~60 most-quoted (Rabbi Akiva, Rabbi Meir, Rav, Shmuel, Abaye, Rava…) | always |
| 2 | the next ~200 | when you zoom into a generation, or open "+N more" |
| 3 | everyone else | only through search, or as a teacher/student in the graph |

These sizes are a starting point. We'll set them once we have the counts. The author can pin or
hide anyone with an override, in the same `overrides.json` that already fixes regions.

## View 1: the timeline (the map)

A Shas-wide version of the daf window's timeline: generations across, Eretz Yisrael and Bavel as
two bands.

- **Three zoom levels:** era (Zugot / Tanna'im / Amora'im), then generation, then one cell. At the
  era level each cell shows only its tier-1 names plus a count ("+23 more"); the count opens the
  cell.
- **Search box always on top**, in Hebrew or English, matching every spelling we have
  (`titles_en`, `titles_he`). Picking a minor sage zooms to their cell and shows them there,
  highlighted, among that cell's tier-1 names. That is the "I'm interested in a minor one" path.
- **A filter, Tanna'im only / Amora'im only,** for readers who know which they want.
- Clicking any name opens the relationship view centred on them.

## View 2: the relationship graph (the author's design)

```
          [Rabbi Eliezer]   [Rabbi Yehoshua]   [Nachum Ish Gamzu]      teachers
                    \             |              /
                     v            v             v
   [Rabbi Tarfon] · · · ·  ( RABBI AKIVA )  · · · · [Rabbi Yishmael]   colleagues
                     /     /      |      \      \
                    v     v       v       v      v
          [R. Meir] [R. Shimon] [R. Yehuda] [R. Yose]  [+14 more]     students
 ┌──────────────────────────────────────────────────────────────────┐
 │ Rabbi Akiva · רבי עקיבא · Tanna, 3rd generation, Eretz Yisrael     │
 │ bio … · most quoted in: Sanhedrin, Bava Kamma … · Sefaria · Wiki  │
 └──────────────────────────────────────────────────────────────────┘
```

- **The centre sage**, with teachers in a row above (arrows down to the centre) and students in a
  row below (arrows down from the centre). Colleagues sit on either side, joined by a dotted line
  with no arrows. Of the author's two options this one is recommended: it reads at once as "not
  above or below".
- **The info box below:** names in English and Hebrew, era and region, the bio (English or Hebrew,
  as the daf window does now), where in Shas they are quoted most, and links to Sefaria and
  Wikipedia.
- **Click any sage to make them the centre.** The sages who stay in the picture glide to their new
  places, those who leave fade out and new ones fade in (about 400 ms). Akiva → Rabbi Meir: Akiva
  rises from the centre into the teachers' row, and Meir's other teachers and his students come in
  around him. That movement is what keeps the reader oriented.
- **A trail of past centres** (Akiva › Meir › …) with Back, so a walk through the generations can
  be retraced.
- **Crowded rows:** a row holds about 7, sorted by tier. The rest fold into a "+14 more" node,
  which opens the row in two lines. On a phone, 4 per row.
- **Colour by tier and era**, the same colours as the timeline, so the graph and the map read as
  one system. Tier-3 sages show smaller, but they are still clickable.
- **Later, possibly:** a second, fainter ring (teachers' teachers); family links (father and son,
  as in "Rav Bivi b. Abaye") as a third kind of line; reading the graph aloud for accessibility.

**Build:** hand-placed SVG with no graph library, because the layout is three fixed rows, not a
free-form network. The transitions are CSS `transform`s on each node, keyed by slug. In Hebrew the
rows run right to left. It lives in the shared renderer, so the web page and later the apps get it
alike.

## Fixing the relationships first

1. **Hebrew Wikipedia** (free, already cached for 1,032 pages): many sage articles have infobox
   fields רבותיו / תלמידיו, and the opening lines name colleagues ("בן דורו ובר-פלוגתיה של…"). We
   parse them and match names to slugs with the matcher we already have.
2. **The Talmud itself**, later and only if needed: phrases like "תלמידו של" and "אמר רב X אמר רב Y"
   (which shows transmission, not always discipleship). This is noisier, so we'd only offer
   candidates for review, never write them in directly.
3. **Author review** of the links among tier-1 and tier-2 sages, on a simple Approve / Drop / Add
   page, like the planned glossary review. A wrong "teacher of" is a factual error a learned reader
   will catch.

Other sites checked (2026-10-29): **Torah Tech** (torahtech.co/sages) takes its list of 1,188
people from Sefaria, but its few full pages (about 15) give teachers, students and family each tied
to a passage (Rabbi Akiva: 3 teachers, 5 students, 19 sources), which is the standard to copy; no
license is stated, so ask before reusing. **Bonei aTalmud** (boneiatalmud.co.il) has its own
written profiles (73 on the main page, all rights reserved), with relationships mostly in prose and
not reliable enough to import (Rabbi Yehuda bar Ilai's colleagues include Resh Lakish, a later
Amora). Neither replaces the Wikipedia step.

Each link keeps its source (sefaria / wikipedia / author), so a reviewed link isn't overwritten on
a rebuild.

## Order of work

1. Count mentions across Shas and assign tiers (local, free).
2. Pull relationships from Hebrew Wikipedia and merge them with Sefaria's (local, free).
3. **Build the graph view first, inside today's daf Sages window:** a "Relationships" button on
   each card, centred on that sage. It is useful at once, and it is a small, testable step.
4. Author review of the top two tiers' links.
5. The Shas timeline with tiers, zoom and search, under Reference Tools.

## Questions for the author

- Are "most quoted in the Bavli" tiers the right measure of "major", or should some sages be major
  for other reasons (an important figure the Gemara mentions rarely)? The overrides allow both.
- Should the Yerushalmi-only names (most of the 680 unclassed people) appear at all? The proposal
  is to show them only in the graph, as someone's teacher or student, and in search.
- Colleagues: dotted with no arrows (recommended), or two-way arrows?
- Should the graph also open from a sage's name in the outline, or only from the Sages window?
