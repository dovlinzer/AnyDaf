# Study games — design brief

Start here when picking up the games work in a new session. Background on the web prototype
(where the games will live) is in CLAUDE.md, under "AnyDafWeb — design + prototype" and the
sections after it; the site is https://anydaf-outlines.vercel.app, built by
`AnyDafWeb/prototype/build_prototype.py` from `app.html` and the shared renderer
`AnyDafWeb/renderer/outline-renderer.{js,css}`.

## The aim (author, 2026-10-05)

Make studying a daf a good experience for kids and adults, in the spirit of the apps'
multiple-choice self-test: quick, immediate feedback (the right answer lights up), a little fun,
and nothing at stake.

## Decided

**Focus on the bottom line and the themes, not the shakla ve'tarya.** No games about who asked
which question or gave which answer, and no "put the steps of the sugya in order" or
"match the kushya to its teirutz".

Build these first, on one test daf:

1. **Fill in the chart.** A chart from the outline with its cells empty; the cell contents are
   cards to drag into place. Right ones snap in (green), wrong ones bounce back.
2. **Term match.** Match the daf's key terms to their definitions (flip cards / memory style).
3. **Who said it — halakhic positions only.** Drag a sage or school onto the position they hold
   (Beit Shammai / Beit Hillel; R. Akiva / R. Yishmael), never onto a question or an answer.
4. **Kosher or pasul.** Swipe left or right on each case: permitted / forbidden, valid / invalid.
   Quick rounds; good for kids.
5. **Label the picture.** One of the outline's drawings with its labels removed; drag them back.
   The author wants to see it working before deciding whether it is worth keeping, so build it
   last.

Still to do and already planned: **multiple-choice quizzes**. The plan is for the outline pass to
write them (with section summaries) rather than a separate pass; see TODO.md.

## Where each game's material comes from (no new API calls for 1–5)

| Game | Source in each daf's data |
|---|---|
| Fill in the chart | `chart` on outline sections (`columns`, `rows`, optional `tones`). Charts are now at most 4 columns of sentences, with several items in one cell as a numbered list ("1. …\n2. …") |
| Term match | `keyTerms` (term, hebrew, sense, definition, on_this_daf) |
| Who said it | `sages` (with `sections`), and chart rows whose label is a party (rows = parties, by the chart rules). Needs a way to tell positions from questions/answers: chart rows are positions; bullets are not reliable for this |
| Kosher or pasul | chart cells with `tones` "ok" / "no" (newer outlines), else the renderer's `cellTone()` reading for older ones |
| Label the picture | `illustration.svg`: its `<text>` labels can be lifted out and their positions kept as drop targets |

## Ideas mentioned, not chosen yet

Daf yomi streaks; a quick review of earlier dafim's terms; a two-player mode on one link (the
artifact `room` capability, or Supabase realtime on the Vercel site); a kids' level with fewer
cards and the Headlines view; "find it on the daf" (tap the line on the Vilna page, using the
live-text layouts).

## Open questions to settle at the start

- Where the games sit in the page: a "Practice" button per section, a games panel per daf, or
  both.
- Hebrew version: the Hebrew outlines (`lang: "he"`) need the games right to left too.
- Whether results are kept (per reader, in the browser) or nothing is stored.
