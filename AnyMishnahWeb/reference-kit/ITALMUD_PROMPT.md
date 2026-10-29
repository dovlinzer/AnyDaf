# Paste this into the iTalmud session

Port the interactive "Reference" system (weights, measures, money, distance, eating sizes) from Illustrated Mishna into iTalmud.

Source kit: `/Users/dovlinzer/claudecode/AnyDaf/AnyMishnahWeb/reference-kit/` (read its README.md first). The live source of truth is `/Users/dovlinzer/claudecode/AnyDaf/AnyMishnahWeb` (`data/measures.json`, the measure IIFE and CSS in `scripts/build_site.py`, `site/img/measures/`, and the stand-alone page generator at the end of `build_site.py`). Live example: https://www.imishna.com/reference

## What it is
- A popup that opens when a measure in the text is tapped, and a stand-alone Reference page/box with tabs: Volume, Eating sizes, Length, Distance, Land area, Weight, Money.
- Each tab draws the units to scale (cube root for volume, money, weight and eating; linear for length and distance; square root for area). Tapping any unit makes it "1" and recomputes every ratio. Each unit shows modern equivalents (U.S. by default, metric switchable), and a short "In the Mishnah and Talmud" list of what it is used for.
- Pictures: photographs for real objects (vessels, coins, maneh stack, stone weight, ruler, olive/egg/fig/bread), clay illustrations for people, body and places (arm and hand with brackets for etzba/tefach/zeret/amah, road, walker, plowed field).
- Eating sizes has a Rashi/Rambam switch (zayit 1/2 or 1/3 egg; peras 4 or 3 eggs). Distance shows the walking time. The Reference button sits in the header beside the settings gear.

## Rules to keep
- Shiur: R. Chaim Naeh throughout. Never invent values; every number and "used for" line must be sourced or flagged.
- Marker syntax in the text: `[[key|text]]` becomes `<span class="mu" data-m="key">`. Keys are the ids in `measures.json` (log, kav, seah, ephah, kor, dinar, shekel, sela, maneh, amah, tefach, beitseah, mil, ...).
- The data is embedded as `<script type="application/json" id="ms">` on every page that has markers; the JS is a plain IIFE with no libraries.
- Hebrew UI strings go through the existing translation flow (the reference UI strings are English only so far).
- Money is a hierarchy: perutah, issar, pundion, ma'ah, dinar (zuz), shekel (= half a sela = 2 dinar), sela (= 4 dinar), gold dinar (= 25 silver dinar, about twice the size of a silver one), maneh (25 sela = 100 dinar).

## What iTalmud differs on
- The audience is more advanced and the text is long. Do not add technical-term treatment. Mark a measure only at its first occurrence in a passage, and only where the number matters.
- iTalmud already underlines glossary terms and links them in its outline. Decide with the author whether a measure marker should look like a glossary term (same underline) or like the Mishna one (dotted underline); use whichever the existing UI makes consistent.
- Tag the measures in the Bavli text (Berakhot, Shabbat, Eruvin, Pesachim, Yoma ...) by searching for the unit names in the English and the Hebrew; confirm each tag.

## Steps
1. Copy the kit (json, js, css, images) into iTalmud and wire the embed, the popup, the header Reference button and a stand-alone Reference page.
2. Match iTalmud's theme variables (`--bg --fg --blue --card`) and its settings gear (add a U.S./Metric choice).
3. Tag the units in the text, build, and check in the browser at a narrow (phone) width and a wide one.
4. Keep `measures.json` as one shared file if the two projects can share it; otherwise note which copy is the master.

## Still open (do not present these as settled)
- Kotevet (a large date, somewhat less than an egg), grogeret and melo lugmav: sizes under review by the author. The kotevet is not in the chart yet.
- Naeh values to be checked against Shiurei Torah; sela = shekel source; beit kor = 30 beit se'ah (implied); ris = 1/15 mil (single source); 12:1 gold to silver; pundion metal; the zeret drawing is approximate.
