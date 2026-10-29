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
- **Later, possibly:** a second, fainter ring (teachers' teachers); reading the graph aloud for accessibility.

**Build:** hand-placed SVG with no graph library, because the layout is three fixed rows, not a
free-form network. The transitions are CSS `transform`s on each node, keyed by slug. In Hebrew the
rows run right to left. It lives in the shared renderer, so the web page and later the apps get it
alike.

## Fixing the relationships first

1. **Hebrew Wikipedia** (free; only its category lists are cached today, so the articles, about
   350 for the classed sages, must be fetched first): many sage articles have infobox
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

## Designing for missing data (author, 2026-10-29)

Many sages appear only a handful of times, and nothing anywhere records their teachers, students
or generation; better data won't fix that. So the chart should show such a sage honestly:

- **Say what isn't known** rather than leave a blank: "No teachers or students are recorded."
- **For a rarely quoted sage, the passages are the content.** When a sage is quoted fewer than
  about ten times, the info box shows every passage in full, Hebrew and English.
- **"Appears with"** (computed, free): the sages quoted in the same passages, such as the one whose
  teaching he passes on ("Rabbi X said in the name of Rabbi Y") or the one he argues with. It is
  shown apart from the graph's teacher/student lines and labelled as what it is, never presented
  as a relationship.
- **An estimated place on the timeline** where the generation is unknown: worked out from whom he
  quotes and who quotes him, and drawn as a faint bar across the possible generations with
  "approximate"; with nothing to go on, a "generation unknown" row at the end of each era.
- **Check coverage where readers look.** After the Wikipedia step, measure how many tier-1 and
  tier-2 sages have teachers, students and a generation. Most readers start there, and the gaps
  are mostly in tier 3.

## Shared with Illustrated Mishna (like the measures kit)

One source for both sites, built the way the Reference kit is: the files live in
`AnyMishnahWeb/reference-kit/sages/`, both sites' builds read them from that path on every build,
and neither site keeps a copy or edits them.

| File | What it is |
|---|---|
| `sages.json` | one record per sage: names (English, Hebrew, spellings), kind, generation, region, approximate dates, tier and the author's "major" picks, teachers / students / colleagues / family (each link with a `source` field, empty until stage 2), bio, stories, and mention counts per corpus (`bavli`, `mishnah`) by tractate |
| `sages.js` | the whole UI, a plain script with no libraries: the relationship graph, the info box, later the timeline and search. English and Hebrew |
| `sages.css` | its styles, on the host site's colour variables |
| `README.md` | the contract, as the measures kit has |

**Written by one script, not by hand:** `daf-processor/build_sages.py kit` writes `sages.json` from
Sefaria, Hebrew Wikipedia, `overrides.json` (the author's corrections and picks) and
`stories.json` (the approved stories), so edits go into those inputs and a rebuild carries them.

**What differs per site is passed in, not built in:** which corpus's counts set the tiers and fill
"where they are quoted" (Bavli for iTalmud, Mishnah for Illustrated Mishna, so the Mishnah site's
major sages are its tanna'im), and how a quotation becomes a link (`#Bava_Metzia/11` in iTalmud, a
chapter page in Illustrated Mishna). The host calls something like
`AnySages.init({corpus:'bavli', link:(tractate, ref) => url, lang:'en'})`.

The Mishnah counts need the whole Mishnah's text; Illustrated Mishna has only the chapters it has
built, so the script fetches it once from Sefaria (free) for counting.

## Status (2026-10-29)

Done: steps 1–4 below. The relationship box is live on iTalmud (Sages window → a card's
"Relationships"), from the shared kit `AnyMishnahWeb/reference-kit/sages/` (see its README).
Dates come from the generation (`GEN_YEARS` in `sages_kit.py`, draft years for the author) unless
Wikipedia gives a year. Tiers can be changed at any time in `kit_overrides.json` and one rebuild.
Still to do: the author's review (tiers, links, stories), stories drafted from Wikipedia's
citations, Illustrated Mishna wiring, then the Shas-wide timeline.

Known data errors seen so far, for the review: Sefaria lists Rabbi Chanina b. Chama (an amora) as
a student of Rabbi Akiva; Sefaria's Wikipedia links for Rabban Gamliel of Yavneh and Gamliel III
were swapped (fixed in `sages_wiki.py`).

## Next steps (all local, no AI calls)

1. **Count mentions across the Bavli and the Mishnah**, using the name matcher we already have, and
   set the tiers. Report: how many sages in each tier, and the top names, for you to check.
2. **Fetch the Hebrew Wikipedia articles** for the classed sages and pull teachers, students,
   colleagues, family and dates. Merge with Sefaria's links. Report coverage for tiers 1 and 2
   (how many have teachers, students, a generation, dates).
3. **Set up the kit folder** and `build_sages.py kit`, writing `sages.json`.
4. **Build the graph and info box** in `sages.js`, and wire it into iTalmud's Sages window (a
   "Relationships" button on each card). Test it on a few dafim.
5. **Your review:** the tier-1 picks, the links among tiers 1 and 2, and stories (I draft each
   major sage's list from Wikipedia's citations; you approve).
6. **Wire it into Illustrated Mishna** (its own Sages box is still to come; the graph can arrive
   with it).
7. Later: the Shas-wide timeline and search under Reference Tools; stage 2.

**Licence note:** facts (who taught whom, dates) are free to use, but Wikipedia's wording is
CC BY-SA. So the bios stay Sefaria's (as now), and nothing is copied from Wikipedia's text.

## Decisions (author, 2026-10-29)

- **Major sages can be hand-picked.** The Bavli mention count sets the tiers, but the author can
  mark any sage as major (tier 1) by judgement, for a figure who matters more than the Gemara's
  count shows. Stored with the other overrides.
- **Yerushalmi sages** show only in the graph (as someone's teacher or student) and in search. No
  switch to add them to the timeline: Sefaria mostly lacks their generation and region.
- **Colleagues: a dotted line, no arrows.**
- **The graph opens from a "Relationships" button on each card in the Sages window.** A sage's
  name in the outline keeps opening the Sages window, as now; a direct way in can come later.

## Ideas taken from the other sites (2026-10-29)

**Order (author, 2026-10-29): the readers are mostly casual learners and high-school students, not
scholars, so what makes a sage vivid comes first: stories, family, dates and where they are quoted in
stage 1; evidence for each link and "what we don't know" in stage 2.** Each link still stores
a source field from the start (empty for now), so stage 2 adds passages without reworking the data.

- **Every link shows its evidence** (Torah Tech): click a line in the graph to see the passage
  that makes them teacher and student, with a note where it is only the usual identification
  rather than what the text says. Links with no passage yet are marked "source not yet found".
- **Where they are quoted:** the info box lists the tractates where the sage is quoted most, with
  counts, and opens a full list of dafim, each a link into iTalmud (any daf opens there, outline or
  not). From the same Shas-wide count that sets the tiers, so no new cost.
- **Stories about them:** a short hand-picked list of the passages that tell us who the sage was
  (Rabbi Akiva's beginnings in Ketubot 62b–63a, his death in Berakhot 61b), separate from the
  places he is merely quoted. Hebrew Wikipedia's articles cite most of these; the author approves.
- **Family links** (Torah Tech lists them) move up from "later": a fourth kind of line, beside the
  centre sage and labelled (father, son, father-in-law).
- **Approximate dates** (Bonei aTalmud, "c. 120–140 CE") under each name in the info box and as a
  date scale on the timeline. Hebrew Wikipedia gives them for many sages.
- **"What we don't know"** (Torah Tech): a line in the info box for disputed identifications, e.g.
  whether two names are one person.

## Questions for the author

- Which of the ideas above to keep.
