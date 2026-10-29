# Reference kit (weights, measures, money, distance, eating sizes)

**This folder is the single source of truth, shared by Illustrated Mishna and iTalmud.** Edit only here.
Illustrated Mishna's `scripts/build_site.py` reads `measures.json`, `measures.js`, `measures.css` and copies `img/` to `site/img/measures/` on every build. iTalmud's build must read the same files from this path (`/Users/dovlinzer/claudecode/AnyDaf/AnyMishnahWeb/reference-kit/`), not a copy. Then a fix or addition made here reaches both sites with one rebuild and deploy of each.

(Original notes follow.)


Built for Illustrated Mishna (AnyMishnahWeb), 2026-10-28. This is a snapshot for porting to iTalmud.
The live source of truth is `/Users/dovlinzer/claudecode/AnyDaf/AnyMishnahWeb`:
`data/measures.json`, `scripts/build_site.py` (the measure IIFE, the CSS, the standalone `reference.html` generator at the end of the file), `site/img/measures/`.

- `measures.json`   units, ladders, image entries, hand brackets, default tabs, family order. All numbers follow R. Chaim Naeh; `_note` records sources and status.
- `measures.js`     the whole popup/reference UI (a plain IIFE, no libraries). Reads `<script type="application/json" id="ms">`. Entry points: `fill(key)`, `open(el)`, `openRef(fam,host)`, `ladder`, `ladderDist`, `handPanel`, `walkPanel`, `refUI`.
- `measures.css`    the measure rules only (`.mu`, `.mpop`, `.mtabs`, `.mvf`, `.refbtn`, ...). Uses the site's CSS variables (`--bg --fg --blue --card`).
- `img/`            cut-out photos and clay illustrations (vessels, coins, maneh stack, stone weight, ruler, road, walker, arms, plowed field, eating photos).
- `prompts.md`      the Gemini prompts used for the pictures.
