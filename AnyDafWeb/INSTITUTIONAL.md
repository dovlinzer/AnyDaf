# AnyDafWeb — institutional features and on-demand study aids (ideas, 2026-09-27)

Planning notes from a brainstorming session (held in the AnyYCTorah workspace) about how schools
could use AnyDafWeb, and what on-demand chart/illustration generation would cost. Nothing here is
built or decided. It is meant to sit beside `DESIGN.md` so the design and the plans for later
versions live in one place. Figures below were measured against the real outputs in
`daf-processor/outline/results/` (950 illustrations, 615 charts) on 2026-09-27.

## The idea

A paid **institutional subscription** for schools (and possibly shiurim):

- **On-demand study aids.** A teacher clicks an outline section and chooses "Make chart" or
  "Make illustration" where none exists, or "Redo" on one they don't like, with their own
  instructions ("split by amora," "show it as a timeline").
- **Shared within the school.** Everything a teacher generates is visible to the school's
  students, and can be limited to specific classes.
- **Fill-in exercises.** A teacher can blank out a chart (or a diagram's labels); students fill it
  in and are graded automatically (by exact match or AI) or by the teacher.
- **Tests** built from the glossary and the material covered, saved with the school's account and
  reusable by other teachers.
- **A wider library later.** Once institutions have built up enough extra charts and
  illustrations, casual users can get access to them (possibly as a paid tier). Tell institutions
  this will happen, whatever the legal position (see "Rights and privacy").

## Why the current design fits this

- **Charts are already structured data** (`{caption, columns, rows}`, rendered by
  `outline-renderer.js`), not pictures. A fill-in chart is the same chart with some cells hidden,
  and most grading is comparing cells, with no AI needed.
- **Illustrations are Claude-drawn SVG**, not an image model, so there are no raster costs and no
  garbled Hebrew lettering.
- **`status` (draft / reviewed / published) plus `model` and `prompt_version`** on
  `daf_study_aids` already sets up the review process teacher-generated content needs.
- **SVG is cleaned once, before storage, never in the renderer.** On-demand generation must keep
  this rule (below).

## What on-demand generation would need

1. **A separate table for teacher-generated aids**, not rows in `daf_study_aids`. That table has
   one row per daf, which suits reviewed core content. Sketch:

   ```sql
   create table custom_aids (
     id            uuid primary key default gen_random_uuid(),
     tractate      text not null,
     daf           numeric(4,1) not null,
     section_id    text not null,        -- the outline section it is attached to
     kind          text not null,        -- chart | illustration
     body          jsonb not null,       -- chart {caption, columns, rows} or {caption, svg} (SVG cleaned)
     instruction   text,                 -- the teacher's own prompt, if any
     replaces_id   uuid references custom_aids(id),   -- version history for "Redo"
     created_by    uuid not null,        -- the teacher
     org_id        uuid not null,        -- the school
     class_id      uuid,                 -- null = whole school
     scope         text not null default 'class',     -- class | school | public
     status        text not null default 'draft',     -- public needs our review, like core content
     model         text not null,
     prompt_version text not null,
     created_at    timestamptz default now()
   );
   ```

   The renderer merges these into the outline for anyone allowed to see them. Nothing goes public
   without our own review, even if the teacher approved it, since one wrong chart in the shared
   library hurts trust in all of it.

2. **A server route for generation** (a Next.js route or a Supabase Edge Function), replacing the
   daf-processor batch runs for this one case. It should:
   - reuse the same prompt pieces and style rules as the batch passes
   - clean every SVG with the same `clean_svg` + `uniquify_ids` logic, ported or called as a
     service, before storing it. This is a **security requirement** here: a teacher's free-text
     "Redo" instruction goes into the prompt, and the SVG that comes back is shown to a whole
     school.
   - take the existing version as input for "Redo," so it edits rather than starting over.

3. **"Label the diagram" exercises, from a small prompt change.** Right now illustration labels
   are plain `<text>` elements mixed in with everything else. Asking the model to give its labels a
   class and an id (e.g. `<text class="lbl" id="lbl-3">`) would let the renderer hide them for
   students to fill in, graded by exact match like chart cells. **Worth adding to the batch prompt
   before the full Bavli run**, so the core content supports this too.

4. **An optional render-and-look check for illustrations.** The SVG is always valid, but it can
   still come out cluttered, with labels running off the edge or overlapping. For on-demand
   requests (seen immediately, in front of a class): render to an image, have Claude look at it,
   retry once if needed. This roughly doubles an illustration's cost.

5. **Accounts, organizations, classes and roles.** These are "not in the first version" in
   `DESIGN.md`, but every institutional feature depends on them. AnyTorahWeb's accounts are the
   obvious thing to borrow. **This work, plus roster integration (Google Classroom / Clever), will
   outweigh everything AI-related** and matters more for school adoption than any AI feature.

## Cost of on-demand generation

Measured output sizes:
- **Illustration SVG:** about 4,000 characters (up to 9,200), roughly 1.5–3K output tokens.
- **Chart:** about 530 characters, a few hundred tokens.

Current list prices per million tokens (input / output): Opus 5.5 $4 / $20, Sonnet 5 $2 / $10,
Haiku 4.5 $1 / $5. Batch processing is 50% off, and prompt caching makes the repeated style rules
and section context much cheaper to reuse.

Assuming about 10–15K input tokens (section text plus the style rules, which can be cached) and
adaptive thinking on top of the output:

| On-demand request | Opus 5.5 | Sonnet 5 |
|---|---|---|
| New chart | ~$0.05–0.10 | ~$0.03–0.05 |
| New illustration | ~$0.12–0.25 | ~$0.06–0.12 |
| Illustration with the render-and-look check | ~$0.25–0.45 | ~$0.12–0.25 |
| "Redo" with the teacher's instructions | about the same as new | about the same as new |
| Test of 15 questions from a section and its glossary | ~$0.05–0.10 | ~$0.03–0.08 |
| Grading a chart or labeled diagram | $0 for exact-match cells, under $0.01 per submission when AI is needed (Haiku) | same |

The `_low` / `_medium` / `_high` result files already compare effort levels. Those same
comparisons will show whether on-demand requests can run at a lower setting.

**At school scale:** even with heavy use (thousands of requests a year), this comes to a few
hundred to about $1,500 a year per school, well within an institutional subscription. Cost
controls:
- a monthly generation quota per school
- a limit on repeated "Redo" of the same aid
- before generating anything, show what already exists: "3 charts already exist for this
  section; use one?" This saves money, and it's also how the shared library grows.

## Why this suits AnyDaf in particular

- **Heavy reuse.** Everyone in Daf Yomi is on the same daf on the same day, so a chart one school
  or shiur requests today can serve other users on that daf the same day, and repeat requests
  cost almost nothing.
- **Schools go deep, not fast.** A yeshiva or day school may spend a year on a few chapters of
  one tractate. Their aids pile up on a small set of dafim and become some of the most carefully
  developed material there is. They're good candidates to review and fold into the core content
  for everyone.
- **Teacher requests show where the core content is thin.** When several schools request a chart
  for the same section, that's a gap. Generate a polished version for everyone in the cheaper
  overnight batch, review it, and publish it.

## More ideas

- **Three sharing levels:** class, school, public, with ratings and "used by 12 schools" counts to
  help decide what to promote.
- **A question bank tied to outline sections and glossary terms**, not free-standing tests.
  Teachers assemble tests from it, and anything they write or edit goes back into the bank.
- **Glossary flashcards and spaced repetition**, which can be generated from the master glossary
  with no AI at all.
- **Class insights:** "Most of your class missed *migo* and *chazakah*," taken from grading data
  the app already has. This is the feature administrators will actually buy.
- **Printable worksheets (PDF)**, since many yeshiva and day-school classrooms are still largely
  paper-based. This comes almost free because charts are stored as data.
- **Different difficulty levels:** the same chart or diagram with more or fewer cells blanked, or
  with hints.

## Rights and privacy

- **Generated content.** Anthropic's terms give model output to us as the customer. Where a
  teacher wrote a substantial prompt or hand-edited the result, cover it with a clear license grant
  in the institutional terms rather than relying on it being "Claude's work," and tell
  institutions how their aids may be shared. Have a lawyer review this language.
- **Student data is the part with real legal weight.** Students' filled-in charts, answers and
  grades are school records about minors, which brings in privacy rules (FERPA, and COPPA for
  children under 13). Student work never goes into the shared library, not even anonymized,
  without a deliberate policy.
- **Grading.** AI-graded answers should always be something the teacher can override, and
  students should see that the teacher owns the grade.

## Open questions

1. Is the render-and-look check worth doubling an illustration's cost, or only for "public"
   promotions?
2. Should the shared library be for subscribers only, or should reviewed promotions go into the
   free core content?
3. Opus 5.5 or Sonnet 5 for on-demand requests (to test with the existing effort-level results)?
4. Add labeled-text ids to the illustration prompt now, before the full Bavli batch run?
