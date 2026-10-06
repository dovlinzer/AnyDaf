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

## Status (2026-10-05)

Built: `renderer/games.{js,css}` (shared, `AnyDafGames.mount(el, {outline, keyTerms, sages, title}, {lang})`,
scoped `.adg`; build_prototype.py inlines it) and a **Practice** pop-out in `prototype/app.html`
(button under Options > Open, shown only when the daf has a playable game; works right to left).
Games 1 (**Fill in the chart**: drag or tap-then-tap, wrong ones shake, at most 9 blanks per chart)
and 2 (**Term match**: 6 pairs, term + Hebrew against `sense`, definition shown on each match) work
on Chagigah 6 (English and Hebrew) and Bava Metzia 11. Nothing is stored. Game 4 (**Kosher or pasul**) built 2026-10-05: swipe/tap/arrow keys, rounds of 8. It quizzes only *short*
verdict cells (7 words or fewer, tone ok/no from `chart.tones` or `cellTone`), prompt = row label + column
header, buttons named by the chart's vocabulary (Acquires / Valid / Effective / Permitted, else Yes/No).
Longer cells are explanations and their auto-read tone is unreliable. Available on 23 of the 73 site dafim
(needs 4+ verdicts). Game 3 (**Who said it**) built the same day: rounds of 2-5 parties matched (drag/tap) to the position
each holds in one chart column. A chart qualifies when every row label is a party (sage/school name) and the
column's cells are short and all different; 3 rounds per play. Many rounds have only 2 parties (a coin flip),
so it is easy. Game 5 not started. Games 1-4 deployed 2026-10-05 (index.html only; data files untouched).
Cost: none; games are built in the browser from each daf's outline data. The only API cost is making
outlines themselves (outline pass); guaranteeing games on every daf would mean the outline prompt writing
explicit verdict/party items.
Drag was verified with synthetic pointer events; the browser pane's own drag tool doesn't produce them.

### Review feedback, 2026-10-05 (author): cards lacked context and used the wrong answer words

Author found Who said it / Kosher or pasul confusing: a bare chart cell ("What carries over from the get",
"Said 50, not worth 50", "Yes/No") doesn't say under what circumstances, and the Yes/No or
Permitted/Forbidden buttons sometimes named the wrong pair. Each game card should communicate a whole idea.
Done locally (same data, no API): every card shows the section trail and the chart's caption; Kosher uses
"According to <sage>" or the case, then the column; answer buttons are named per item from the cell's own
words, then its column heading, caption and section title (Betrothed / Not betrothed, Valid / Not valid,
Acquired / Not acquired, Takes effect, Permitted / Forbidden, Divorced) and an item with no such pair is
dropped, never Yes/No; cells that open with the verdict and then give a reason now count. Every game can
send the reader to the section in the outline ("See it in the outline": after a miss, at the end of a
round or chart, and a list of missed sections); a wrong Kosher answer now waits for the reader.
Every game except Term match has ‹ › in its bar to skip to the preceding or following chart / round / case (Kosher keeps answers, so going back to re-answer is fine; skipped ones are counted at the end). Term match waits 2.4 s on a mismatch. Deployed 2026-10-05.
**Still limited**: a chart cell is a fragment; "Said 50, not worth 50" is still cryptic without the
Gemara's scenario. The real fix is the outline pass writing explicit practice items (scenario in full
sentences, the answer pair, the section id) rather than the games scraping chart cells. That is an API
cost (extra output per daf) and needs the author's go-ahead; the card layout already has the fields.

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
