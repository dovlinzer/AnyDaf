# Sages kit (relationship graph and info box)

**Shared by iTalmud and Illustrated Mishna; edit only here.** Each site's build reads these files
from this path on every build, as with the measures kit one folder up. Plan: `AnyDafWeb/SAGES.md`.

| File | What it is |
|---|---|
| `sages.json` | **Generated, never edit by hand.** One record per sage (584): names, kind, generation, region, approximate years, tiers (Bavli and Mishnah), bio, links to teachers / students / colleagues / family (two-way, each with `by` = sefaria / wikipedia / author and an empty `source` for stage 2), mention counts and the tractates that quote them most, stories |
| `quoted.json` | **Generated.** The amudim (Bavli) and mishnayot (Mishnah) where each sage is named; loaded only when a reader opens "where quoted" |
| `sages.js` | The relationship box (graph + info box) and the Shas-wide chart (generations × Eretz Yisrael / Bavel, search, filters), English and Hebrew. No libraries |
| `ANYMISHNA_PROMPT.md` | Instructions for wiring this into Illustrated Mishna |
| `sages.css` | Its styles, on the host's `--card --fg --blue` variables |

**To change the data:** edit the inputs in `daf-processor/outline/sages/` and run
`daf-processor/venv/bin/python daf-processor/sages_kit.py`, then rebuild and redeploy both sites.
- `kit_overrides.json`: the author's picks: `major` (always tier 1), `tier` / `tier_mishnah`
  (`{slug: 1|2|3}`), `drop_links` / `add_links` (`[slug, relation, slug]`).
- `stories.json`: approved stories per sage.
- The facts underneath: `sages.json` (Sefaria, `build_sages.py`), `wiki_facts.json` (Hebrew Wikipedia,
  `sages_wiki.py`), `census_bavli.json` / `census_mishnah.json` (`build_sages.py census`, `census-mishnah`).

**Host contract:**
```js
AnySages.init({base: 'sages/',            // where the site serves sages.json and quoted.json
               corpus: 'bavli',           // or 'mishnah': which counts, tiers and places to show
               lang: 'en',                // or 'he'
               link: (corpus, tractate, place) => url,   // place: '11a' or '3:4'
               tractateName: tractate => label,          // optional
               credit: html});                           // optional: a credit line under the chart (e.g. the site's icon)
AnySages.open('rabbi-akiva');             // the relationship box, for any key of sages.json
AnySages.chart(element);                  // the Shas-wide chart, rendered into a page
AnySages.openChart();                     // or opened over the page
```
The site copies `sages.json` and `quoted.json` to `base` and inlines (or loads) `sages.js` and
`sages.css`. iTalmud: `AnyDafWeb/prototype/build_prototype.py` (`SAGES_KIT`), opened from a
"Relationships" button on each card of the Sages window, "All sages" in its header, and the
page `/sages` (`sages_page()`).

Years are approximate, from the generation (`GEN_YEARS` in `sages_kit.py`, a draft for the author),
unless Wikipedia gives a birth or death year. Only facts are taken from Wikipedia, never its
wording (CC BY-SA); bios are Sefaria's.

## Two views (2026-10-29)
The relationship box has a pill above the chart: **Teachers & students** (the old chart, now without family nodes; a family relation is only a small label under a name, e.g. "Son") and **Family**, a tree up to four generations either way, built from the `links` family relations (father, mother, parents, grandparents, children, grandchildren, spouse, in-laws, sons-in-law; brothers and sisters are the other children of his parents). Parents and children are joined by lines, a spouse stands beside the person, and a relation known only in general (a grandfather, a son-in-law) is a dotted line. The pill shows only when the sage has both; a sage with only one view opens in it. Same code for iTalmud and Illustrated Mishna. Family data is sparse (23 small family groups; the longest is R. Yehudah HaNasi's, five generations): improve it in `kit_overrides.json`.
