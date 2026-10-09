# AnyMishnahWeb — design (draft, 2026-10-09)

A web app for learning Mishnah in two layers, modelled on `../AnyDafWeb/` (see its DESIGN.md).
First chapter: **Berakhot 1** (5 mishnayot). Prototype data is in `data/berakhot_1.json`.

## Layers
1. **Simple reading** (the only layer a grade-school audience may use). Plain meaning of the
   mishnah: who says what, the case, the ruling. Short outline, a "who's who" strip, and at least
   one illustration per mishnah, in a consistent graphic-novel style. Reading level ~grade 5-6.
2. **Deeper layer.** How the Gemara explains, expands, limits and reframes the mishnah, as
   distilled in Kehati. Comparison charts, "the Gemara asks" steps, each node citing its source
   (Kehati passage / Gemara sugya). Reviewed like the daf outlines (draft → reviewed → published).

## Sources and licensing
| Source | Use | License |
|---|---|---|
| Sefaria, Mishnah ed. Romm Vilna 1913 | Hebrew text | Public domain |
| Sefaria, Mishnah Yomit (Kulp) translation + "English Explanation of Mishnah" | English text; layer-1 basis | CC-BY (credit Dr. Joshua Kulp) |
| Bartenura (Silverstein tr.) | optional | CC-BY |
| Kehati (Herzog "Mishnayot Kehati Online" / apps) | **research input only**; we publish our own summaries with citations, never his text | Copyrighted |
| Gemara (Sefaria / our `daf_text`) | citations in layer 2 | William Davidson English is CC-BY-NC |

Kehati is not on Sefaria; access to it is still open (see TODO).

## Reuse from AnyDafWeb
`renderer/outline-renderer.{js,css}` (nested outline, charts, pictures), the draft/reviewed/published
status flow, Next.js/Supabase/Vercel stack, pane layout with synced text. New tables:
`mishnah_text(tractate, chapter, mishnah, he, en, kulp jsonb)` and
`mishnah_study_aids(tractate, chapter, mishnah, layer1 jsonb, layer2 jsonb, status, ...)`.

## Illustrations
Not an afterthought: ≥1 per mishnah, more where a scene or comparison helps (e.g. the priests
eating terumah at nightfall; the sons returning from the feast; Rabbi Tarfon and the robbers;
a timeline of the night). Needs a **style bible**: character sheet for recurring sages
(R. Eliezer, R. Yehoshua, Rabban Gamliel, R. Tarfon, Ben Zoma...), fixed palette, a few settings
(beit midrash, road, home). Each image is generated from a written brief stored in the layer-1 JSON
(`illustrations[].brief`), so briefs can be reviewed before any image is made.
Open question: image source (an image model vs. hand-authored SVG). SVG is easy for diagrams and
timelines but weak for characters.

## Pipeline
fetch_sefaria.py → data/*.json → (Claude pass) layer1 → review → illustrations → layer2 from
Kehati notes → review → publish.
