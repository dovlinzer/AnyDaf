# Weights, measures and money: plan (draft, 2026-10-28; nothing built yet)

## Goal
Like the iTalmud "Sages" box: tap a measure in the text (se'a, beit se'a, beit kor, maneh, sela, tefach, log...) and a box opens showing (1) what it is, (2) how it relates to the units around it, (3) a picture at true relative scale, (4) a modern equivalent. The same data and component should port to iTalmud.

## What the box shows
1. Name (transliteration, translation, Hebrew), type (volume dry / volume liquid / length / area / weight / coin).
2. A scale picture: nested containers, piles or coins drawn at true relative size (for example log < hin < kav < se'a < ephah/bath < kor), with the tapped unit highlighted. Inspiration from the four pictures you sent: the three-cup log set, the container ladder with measurements, the coin stacks on scales, the table with U.S. and metric columns.
3. Relation line: "1 se'a = 6 kavim = 24 lugin" (computed from the table, so it stays consistent).
4. Modern equivalent: a range, not a single number, with a toggle "shiur: Chazon Ish / R. Chaim Naeh" for the two standard opinions (and the unit conversion to liters, ounces, grams, inches). The range is shown honestly: the disagreement is part of the information.
5. Where it comes up in this tractate (mishnah links) and one line on why it matters there (for example beit se'a in BK 6:2 appraising the damaged field).

## Data (one file, data/measures.json, reused by iTalmud)
Each unit: id, he, transliteration, English, type, parent/child ratios, modern value per shiur (min/max), the drawing spec (shape, relative size), and the mishnayot it appears in. Ratios come from the text of the Mishnah/Gemara (and Kehati where he states them); the modern numbers are a published reference and are labeled with their source. I will not fill modern values from memory: each needs a cited source for you to approve.

## Units needed for what we have so far (from the text search)
- Dry/liquid volume: se'a (BK 6:2), kor, ephah, kav, log (and beit se'a, beit kor, which are areas defined by the seed they take).
- Money: maneh (100 zuz), sela (4 zuz), zuz/dinar, perutah, as in BK 4:5 (kofer values) and 3:9 (dinars).
- Length/area: tefach, amah (BK 5:5 pit depth), the four amot / beit kor of BK 6:4.
- Weight: litra if needed later.

## Visual design
- One SVG per unit family (not photos), in the site's flat clay-neutral style: containers as simple pot/basket/cup silhouettes, coins as discs at relative diameter, piles as stacks, lengths as hand/forearm outlines (as in your Logos picture). All drawn from the ratios so sizes are exact, not eyeballed.
- Highlight the tapped unit; others dimmed. Tap another to switch.
- A "see them side by side" link opens the full ladder for that family.

## How it opens
Same popup mechanism as glossary terms ({{key|i}} marker with a data-k), but a richer panel. Measures that appear only incidentally open the measures box; units central to a chapter also get a glossary entry. Works on the Hebrew pages.

## Build steps (proposed order)
1. Agree the unit list and sources for modern values (your call).
2. Build measures.json with ratios from the text; you check the ratios.
3. Build one family end to end (volume: log to kor) with the scale SVG and the box, review.
4. Add money, then length/area.
5. Mark the units in the English text (all chapters), then the Hebrew pages.
6. Extract the component and data so iTalmud can use it.

## Decisions (author, 2026-10-28)
- Shiur: R. Chaim Naeh throughout (no Chazon Ish toggle).
- Modern units: U.S. by default, metric switchable in the settings gear.
- Images: photo style.
- Money: purchasing power from what the Talmud tells us (a worker's wage, the price of bread and the like), not today's price of silver, gold or copper.
- Start: author has no preference. Families: dry and liquid volume, weight, length, area, money, probably more.

## Still open
- Which printed or online sources to use for the Naeh values and for the Talmudic prices (options sent to the author).
- Where the photos come from (licensed photos, commissioned, or generated).

## Progress (2026-10-28)
- Volume box built and live on BK 6:2 (se'ah): interactive (tap any vessel to make it 1), US/metric in settings, R. Chaim Naeh note global.
- One photo serves the whole family: the code scales the same vessel for each unit (prompts: data/measures_prompts_volume.md; author to run).
- Ratios checked against Rashi, Steinsaltz and Rambam (see data/measures.json); Naeh figures still to be checked in Shiurei Torah; modern values cross-checked only against Halachipedia/Wikipedia.
- Next: photos in, then dry vs liquid volume, length, area (beit se'ah, beit kor), weight, money with Talmud-based purchasing power.

## Flagged for author review (2026-10-28)
- kotevet: a large date, somewhat less than an egg. Not yet in the Eating chart (no value or source). Photo prompt eat05-kotevet written.
- grogeret (dried fig) and melo lugmav (derived ~41 cc, more than half a revi'it): sizes to be reviewed.
