# AnyMishnahWeb — project guide (started 2026-10-09)

A web app for learning Mishnah in two layers, modelled on `../AnyDafWeb/` (read its DESIGN.md).
**Layer 1, simple reading** (plain meaning; may be the only layer for a grade-school audience): short
outline, who's-who, charts, and at least one picture per mishnah. **Layer 2, deeper reading**: how the
Gemara explains, expands and reframes the mishnah, distilled from Kehati. Other files: `DESIGN.md`
(architecture), `STYLE_BIBLE.md` (illustration rules and results, the single source for prompting
lessons), `BRIEF_TEMPLATE.md` (picture briefs). First chapters: Berakhot 1 (prototype page built),
Bava Kamma 5 (briefs drafted, clay prompts next).

## Working rules (from the author)
- **Source first, never my own understanding.** Content comes from the source text (Kulp on Sefaria;
  Kehati pages for layer 2) and every outline line carries a source tag. My memory is not a source:
  my first draft had the Eliezer/anonymous opinions in Berakhot 1:2 backwards. Anything beyond the
  sources is flagged as mine and not published without approval.
- **Do not invent citations.** Kehati passages say "the Gemara explains" without folios; write "folio TBD".
- Kehati is copyrighted: use it as research input only; publish our own summaries with citations.
- The author reviews pictures by hand; ask for specifics on what they should look for.

## Sources and licensing
Hebrew: Mishnah ed. Romm Vilna 1913 (public domain). English + explanation: Mishnah Yomit by Dr. Joshua
Kulp via Sefaria, **CC-BY** (credit him; Sefaria refs `Mishnah_Yomit` version, commentary title
"English Explanation of Mishnah"). Bartenura (Silverstein) CC-BY. Kehati is NOT on Sefaria; the author
has page photos and expects PDFs. Sefaria's API is slow and flaky (retry; some tractate counts differ:
its index gave 62 tractates/519 chapters/4,084 mishnayot vs standard 63/524-525/~4,187).

## Files and scripts
`scripts/fetch_sefaria.py <Tractate> <chapter>` -> `data/<tractate>_<n>.json`; `scripts/build_page.py`
-> `prototype/berakhot_1.html` (static page: Hebrew, Kulp, outline, charts, picture slots, layer 2);
`scripts/sample_mishnah_types.py` (60-mishnah sample; uses ANTHROPIC_API_KEY from
`../../AnyYCTorah/scripts/content_index/.env`, never print it); `data/*_layer1_draft.json`,
`data/*_briefs.json`. Per CLAUDE.md model rule: Haiku for classification, Sonnet for briefs/judgment.

## Pictures: what we learned (details in STYLE_BIBLE.md)
- Picture = the case plus the **stake**: thought bubbles showing the alternatives ("Which came first?",
  blue/white vs blue/green) with "?" or check/cross; labels are added later as live text. Mishnayot split
  roughly (60-sample): case 37%, sequence 17%, object 18%, list/definition 22%; ~45-60% suit a generated
  scene, ~a third are really SVG tables/diagrams, ~10% have no sensible picture.
- **Style decision: plasticine clay (generic, not copying any creator), Gemini image model (Nano Banana),
  reference image attached per recurring character, full rule block in EVERY request** (a new chat
  carries nothing over). Round 1 ranking by the author's taste: Gemini, Flux, OpenAI. Toy-brick looks
  great but reads as Lego (trademark risk; never say LEGO). Teen tier = graphic-novel direction (not built).
- Rules that worked: no text/letters in the image; scrolls never bound books; show the needed time of
  day (dawn in the window); label space is plain wall/sky inside the scene, not a white band; every
  figure has a full face; **bubbles must differ: say how many figures each holds and what they do**;
  describe recurring characters from their reference image (the model follows the written text over the
  image); give each recurring character one distinguishing feature; no speech bubbles with words.
- **Check every prop and pose for unintended causation** (a dropped basket made the potter, not the cow, the cause in BK 5:2).
- **Be specific; soften by style, not omission** (scene must state the case's facts: gored cow, dead calf,
  smoke from the ox's nostrils; death = stillness + closed eyes; red mark on horns only in teen tier).
  Sensitive topics (e.g. BK 5:4 miscarriage) -> diagram only for kids.
- **Visual vocabulary** (STYLE_BIBLE.md): framed boxes (no icon, no tail) for halakhic alternatives, thought bubbles only for real thoughts; scale+coins vs empty scale for pays/doesn't; open gate vs no-entry for permission; numerals allowed, words not; the '?' floats in the gap BETWEEN the two panels, never inside one; check legal logic of every symbol pair. Round 3 (BK 5, first-time test): all four came out good-looking but the stakes needed these devices.
- Reference-image consistency worked for one and two characters; three+ not yet tested.

## Costs (checked 2026-10-09; third-party and Google pricing page, verify)
Gemini image output at 1K: Nano Banana 2 (`gemini-3.1-flash-image`) $0.067 std / $0.034 batch;
Nano Banana 2.1 (`gemini-nano-banana-2.1`) ~$0.034 / ~$0.017; Lite same as 2.1 but weaker. Whole
Mishnah ~2,300-4,200 pictures: ~$40-$280 (kids tier; double with a teen tier). Which model the Gemini
app used is unknown (Gemini's self-report was contradictory); resolve with a paid API account and a same-
prompt comparison. Text/outline LLM cost for the whole Mishnah not yet measured.

## Open items
1. Author runs clay prompts for BK 5:1, 5:2, 5:5, 5:6 unedited (first-time hit-rate test); then a
   Taharot chapter. 2. Paid Gemini API key in a local .env (author places it) + 2-vs-2.1 comparison.
3. Layer-1 outlines for mishnayot 3-5 of Berakhot 1 were not source-tagged; verify all against Kulp.
4. Kehati PDFs -> layer 2 for the rest of Berakhot 1. 5. Tag each outline line with its source.
6. Missing tractate in Sefaria count. 7. Teen style, three-character consistency, sage-face decision
   made: full but stylized.

## Round 4 lessons (BK 5, v2 prompts)
Layouts: action scene + two boxes (one case, alternatives/outcomes) vs a two-scene diptych (two cases, two rulings; same basic setup, not identical, so two independent prompts work and can be batched; an edit of the first is optional). Pay/not-pay = scale badge in the upper-right corner of the box, coins in the right pan only. Dead animals on their backs with X eyes. Don't say 'tiny'. Keep the case entirely inside its setting. Prompts: data/bava_kamma_5_prompts_v3.md.

## Overlay symbols (2026-10-09)
Pay/does-not-pay badges, the '?' and other outside-the-scene symbols are composited from one master set, not generated. `scripts/detect_boxes.py` finds box corners (works; ~1 cent/image). Use `data/bava_kamma_5_prompts_v4.md` (no badges in prompts) and `data/master_symbols_prompts.md`. v3 prompts are superseded for the next run, but the author's current test run uses v3 (badges generated), which measures drift.

Round 5 (v3 results): see STYLE_BIBLE.md 'Round 5 lessons'. Use data/bava_kamma_5_prompts_v5.md. Payer tag/arrow overlay located by scripts/detect_person.py.

## Automation plan and what is NOT yet proven (2026-10-09)
Rules were learned by iterating on BK 5 (and Berakhot 1); transfer to untouched chapters is unmeasured. Real labor is (1) checking each brief's legal logic (e.g. the BK 5:5 death-at-ten vs death-at-nine mistake was a content error no image check catches) and (2) reviewing thousands of pictures. Plan: Claude writes briefs/prompts from Kulp with the template + rule block + cast + symbol vocabulary; author reviews brief TEXT; automatic vision checklist after each generation (two boxes, no extra people, no text, dead-animal convention, round pits, cast match) with auto-regeneration up to a few tries; author reviews by exception from contact sheets (est. 10-20 s/picture, ~6-13 h for ~2,300 pictures, an estimate); paired scenes = two linked API calls with the first image attached. Deciding experiment: run the unchanged pipeline on a fresh chapter (Zeraim or Taharot) and measure the first-try pass rate and author seconds per picture.

## First deployment (2026-10-09)
Site folder `site/` (static; built by `scripts/build_site.py` from `data/bava_kamma_5.json` + `data/bava_kamma_5_layer1.json`; pictures composited by `scripts/compose_bk5.py` from the author's generated images + clay badges cut out by `scripts/make_badges.py`). Deployed to Vercel project `anymishnah-web` (account dovlinzer): https://anymishnah-web.vercel.app (link-only, X-Robots-Tag noindex; the per-deployment URLs are SSO-protected, the main alias is public). Redeploy: `cd site && vercel deploy --prod --yes`. Contains only Bava Kamma 5 (outlines drafted by Claude from Kulp, source-tagged; AI-generated illustrations disclosed in the footer). Berakhot 1 is deliberately NOT published (its layer 2 paraphrases Kehati from photographed pages). Known blemishes: a faint inset-rectangle artifact in the corner of the 5:1 boxes; crude animal icons in the 5:7 SVG. The generated originals (36, 38-42) are saved in `data/generated_originals/` (38=5:5, 39=5:6, 40=5:2b, 41=5:2a, 42=5:1, 36=the v3 picture the badges were cut from).

## Site revision, same day (2026-10-09, author's seven requests)
Layout is now two panels per mishnah like AnyDafWeb: outline/charts on the LEFT, Mishnah panel on the RIGHT (Hebrew, translation, pictures, then 'Kulp's commentary'; never call it 'explanation'). Sticky 'Jump to mishnah' pills 1-7. No 'Simple reading' or 'Deeper layer' labels and no Kulp references in the outlines (the source tag is still stored per bullet in data/bava_kamma_5_layer1.json, just not displayed; the CC-BY credit stays in the footer). Diagrams (5:3, 5:4, 5:5, 5:7) are drawn in the AnyDaf style: `site/sprite.svg` is a copy of `daf-processor/outline/sprite.svg` (figures via <use href>, 'sky' gradient, Public Sans); matrices use a narrow viewBox (520) so text renders large. `scripts/erase_corner_notch.py` removes the stray inset rectangle from box corners by pixel analysis (vision coordinates alone were ~60px off and smeared the picture). Pipeline order: erase_corner_notch (42, 39) -> compose_bk5 (badges, payer tag) -> build_site -> `cd site && vercel deploy --prod --yes`. Lesson: when a vision model gives coordinates, verify them visually before trusting them for edits.

## Bava Metzia 1 experiment (started 2026-10-09)
Briefs: data/bava_metzia_1_briefs.json (clay for 1:1 diptych, 1:2, 1:3 diptych, 1:4 diptych, 1:5, 1:7; SVG for 1:5 matrix, 1:6, 1:8). Prompts: data/bava_metzia_1_prompts_v1.md (rule block from the BK 5 template, without the corner-empty clause). Checker: scripts/check_picture.py (vision checklist; hard fails = box count, text, numerals, cast, blank faces, scale/coins drawn, scene mismatch; warnings = white background, dead-animal convention) and scripts/run_checks.py (whole chapter; drop images into data/generated_originals/bm1/ named bm1-1a.jpg etc., config in data/bava_metzia_1_checks.json). Tested on BK 5: caught the missing-boxes run, passed the good ones; ~1 cent/picture. Kulp's commentary on 1:1 quotes the oath wording two ways; Sefaria has no Kulp explanation for 1:6 (questions only). New master symbols needed: KEEPS / NO-CLAIM and DO-NOT-RETURN. The first-try pass rate on these 9 pictures is THE measurement for whether the template transfers.

Site conventions (2026-10-09): refer to the commentator as 'R. Kulp' / 'R. Joshua Kulp' on the site (author's request); on phones the Mishnah panel comes first and the outline second (`.grid .text{order:-1}` under 900px).

ABSOLUTE RULE (author): paired scenes are always made in the same chat/call chain as an edit of the first picture ('Using the previous picture as reference, everything is exactly the same except: ...'); see STYLE_BIBLE.md. BM 1 first-try result: 6 of 9 clean; defects were duplicated/extra objects (1:3 purse, 1:5 child) only; the 1:1 outcome boxes are good; rerun prompts in data/bava_metzia_1_prompts_v2.md (1:3 pair and 1:5 only); checker now counts single objects and allows the '?'.

## Bava Metzia 1 finished and posted (2026-10-09)
Site now has two chapters: /bava-kamma-5 and /bava-metzia-1 (build_site.py is multi-chapter: `build(data, layer1, diagrams, title, sub, outfile, legend)`). BM 1: 9 pictures (6 clean first try; the 1:3 pair and 1:5 redone once: now good, 1:5 has a small bound book on the table, redo line: 'Using the previous picture as reference, everything is exactly the same except: replace the book on the table with a rolled scroll'), SVGs for 1:5, 1:6, 1:8. Interim round badges (keeps, noclaim, noreturn, return, hold, follow) were drawn with PIL, NOT clay: replace with clay masters (author to generate) and recompose with scripts/compose_bm1.py. Checker config records the author's accepted verdicts. Decision (author): keep generating pictures by hand in the Gemini app for now; move to the API when a chapter or two pass ~80% first try, symbols are settled, and volume makes hand work the bottleneck; test the API's output against the app's first (the models may differ).

Round 8 (author's review of BM 1): see STYLE_BIBLE.md 'Round 8'. Redo prompts: data/bava_metzia_1_prompts_v3.md (1:2 edit line, 1:4 pair, 1:5 pair as two scenes, 1:7 with distinct cast). Fraction overlays live in scripts/fraction_badge.py and compose_bm1_fractions.py (applied to 1:1a/1:1b). 1:2, 1:4, 1:5, 1:7 pictures are hidden on the site (layer1 keys prefixed _pending_) until the redos arrive; restore by renaming the keys.

RULE (author): read R. Kulp's commentary (and later Kehati) on a mishnah BEFORE writing its brief/prompt; take the condition from the source exactly and add no mechanism it does not state (see STYLE_BIBLE.md). BM 1:4 was wrong for this reason; corrected prompts in data/bava_metzia_1_prompts_v3.md. Status: 1:2 and 1:5a good (1:2 carries half|half overlays); remaining: 1:4 pair, 1:5b, 1:7.

Overlay placement rule (author): symbols go toward the TOP, where least happens; relation symbols (splits) go between the two people. See STYLE_BIBLE.md. scripts/compose_bm1_fractions.py implements it for BM 1:1 and 1:2. BK 5's badges are still in upper-right box corners and BM 1's person tags float above heads: review them against this rule.

BM 1 status: 1:1, 1:2, 1:3, 1:5 pair, 1:7 posted; only the 1:4 pair remains (rerun prompts in data/bava_metzia_1_prompts_v3.md). Write prompt descriptions in plain lowercase, no role labels.

BM 1 COMPLETE (2026-10-09): all pictures posted. Second-try results after author feedback: 1:2, 1:4 pair, 1:5 pair, 1:7 all good. First-try count was 6 of 9; every miss was a count, direction or invented-detail problem fixed by tighter prompt wording, not by style changes.

Hard-set briefs drafted (data/hard_set_briefs.json): 5 SVG-only, 2 clay-possible, 1 mixed; awaiting author review; new symbol pairs: adds up/does not, liable/not, in/out, can become impure/cannot, defiles hands/does not/disputed, obligated/not. Legend label 'follows the attached note' (not 'postscript').

RULE (author, revised): technical Torah she'baal peh terms are WANTED on the site (gloss once, add to a per-chapter glossary and key terms, plus the sages box, as in AnyDafWeb); only captions inside the kids' clay illustrations stay simple. 1:8 uses 'simpon' (the mishnah's סמפונות).

PLAN: add AnyDafWeb's key-terms chips, glossary pop-out and sages box to these pages (reuse renderer/outline-renderer.js and the glossary_entries data model; see AnyDafWeb/DESIGN.md). Candidate terms so far: BK 5: tam, mu'ad (not yet used), shen, pit (bor); BM 1: simpon, shibud (lien), ketubah, halitzah, kinyan, hefker. Verify each against R. Kulp before writing a definition.

Older-audience tier: style test in data/teen_style_test.md (4 styles x 2 scenes); pick a style, then swap the style and dead-animal sentences in the existing BK 5 / BM 1 prompts. See STYLE_BIBLE.md.

DECISION (author, 2026-10-09): glossary definitions come from AnyDaf's master glossary (daf-processor build_master_glossary.py / glossary_entries); do not write competing definitions. Defer the glossary, key-terms chips and sages box until that list is more complete; until then, gloss each technical term once inline in the outline. Check which of the candidate terms (simpon, shibud, ketubah, halitzah, kinyan, hefker, tam, bor) are already in the master glossary when the time comes.

Domain: www.imishna.com is the author's own domain, attached to the Vercel project anymishnah-web (confirmed by the author). The site still sends X-Robots-Tag noindex, nofollow; remove that header in site/vercel.json (and the meta robots tag in scripts/build_site.py) only when the author wants the site public and findable.

## Interactive pictures (2026-10-10)
Badges are no longer baked into the pictures. `scripts/build_overlays.py` writes badge-free pictures to `site/img/clean/` and `data/overlays.json`: per picture, hotspots (click targets in px of the clean image: a box, a person, an animal, a sign, or the whole picture) and the badges each reveals (src, x, y, width, anchor center/bottom), plus an `answer` kind per hotspot. `build_site.py` renders each as a `.stage` (clean picture + transparent `<button class="hot">` + hidden `<img class="ov">` badges, % positioned). Tapping a hotspot toggles its badges; a 'Show all' button reveals all; a 'tap' chip hints on unrevealed hotspots; legends say 'Tap a picture, a box or a person'. `scripts/preview_overlays.py pid...` renders all badges at full size to check placement against the rule (top, clear of faces and hands). To add a picture: put the clean image in data/generated_originals/, add an `add(...)` block to build_overlays.py (vision calls locate boxes, people, animals), run it, then build_site.py, then deploy. The old composed jpgs (compose_bk5.py, compose_bm1*.py) are superseded but kept.
BK 5:1 now shows the ruling: a pay-scale + 1/2 pill on the cow and + 1/4 on the calf (badge-pay-half, badge-pay-quarter). 5:1 caption states the full ruling.
GAME (not built, data ready): the `answer` field per hotspot is the correct badge; a game would hide all badges, show a tray of the chapter's badges, let the learner drag or tap-then-tap a badge onto a hotspot, and mark it right or wrong. Open design points: wrong-answer feedback, scoring, whether the tray includes badges from other pictures as distractors, and a toggle between 'Explore' and 'Quiz'.
Phone fix: `.grid>*{min-width:0}` and wrapping table cells stopped a wide table making the page scroll sideways (check scrollWidth == clientWidth at 375px).

CHAPTER SUMMARY (author request 2026-10-10): each chapter page ends with a 'Chapter summary' section: Key principles, Key terms, Key debates. Data: data/<chapter>_summary.json (items carry mishnah numbers and a source tag: mishnah / Kulp n:m). Rendered by summary_html() in scripts/build_site.py; pill 'Summary' in the jump bar. Written ONLY from the mishnah text and R. Kulp (nothing from memory); anything Kulp leaves as a question is flagged 'to be confirmed from Kehati'. Terms are provisional until AnyDaf's master glossary (daf-processor/outline/glossary/master_draft.json, 91 entries, none of tam/simpon/bor yet) covers them. Terms wanted but with no source definition yet: mu'ad, halitzah, miun, avot nezikin list (BK 1:1 not fetched), reshut harabim/yachid.

QUIZ MODE (built 2026-10-10): toolbar Mode = Static | Explore | Quiz (Explore = the tap-to-reveal interactivity). Quiz: the badges are hidden; a tray under each picture holds this chapter's badges (TRAY_BK / TRAY_BM in build_site.py); drag a badge onto a numbered box/person/picture (or tap a badge, then the target). Right: the badge appears, green outline. Wrong: shake, red flash, retry (unlimited). 'Show answers', 'Try again' per picture; score line in the toolbar counts first-try hits over the visible pictures. The caption (which states the ruling) is hidden in quiz mode. Answers come from overlays.json 'answer' per hotspot (tag-x answers use the badge-x image). Not built: saving scores, per-learner history, quizzes on the outline text. Password gate: /Users/dovlinzer/claudecode/AnyDaf/password-gate (middleware.js + enable.sh), NOT deployed; see its steps.

QUIZ TARGETING (2026-10-10): hotspot rectangles from vision are often tens of px off, so the quiz no longer shows them. Each target is a numbered (or '?') chip at its rectangle's top-left; a drop or tap goes to the NEAREST hotspot (distance to its rectangle, ties to the smaller one; must be inside the picture, within 140px of a target when there are several). Feedback (tick, shake) is on the chip. The rectangles still drive Explore mode; fixing them by eye is optional.

SOURCE WEIGHT (author, 2026-10-10): Kehati outranks R. Kulp for understanding a mishnah. Found wrong in Kulp: BK 3:5 clause 1 (the beam owner is EXEMPT, as the mishnah says and Kehati confirms; Kulp's explanation says liable). Our BK 5 and BM 1 summaries/outlines are Kulp-only and provisional until checked against Kehati; flag any place where Kulp's explanation contradicts the mishnah text.

BK 3 PAGE (2026-10-11): site/bava-kamma-3.html, graphic-novel pictures only (the Younger choice shows them with a note). Data: data/bava_kamma_3.json (fetched), _layer1.json (outlines tagged Mishnah/Kulp; 3:5 clause 1 per mishnah and Kehati, not Kulp), _summary.json, quiz questions in data/quiz_questions.json, overlays in data/overlays_older.json (built by scripts/build_overlays_older.py). Mishnayot 8, 9, 10 have no picture (amounts and comparisons). All 14 pictures in (3:5s and 3:11b added). Prompts: data/graphic-novel_prompts_bk3_v2.md.

## Sources and prompts (author, 2026-10-12)
Use ONLY the mishnah, Kehati and R. Kulp (Kehati outranks Kulp); never general knowledge. Keep mishnah pshat, Gemara additions (Kehati's notes) and halakha separate. Prompts: no unnecessary elements, state every figure's expression, style block has no objects/injuries/negatives, accepted scene text is frozen and changes are shown as a diff first (scripts/prompt_diff.py). See STYLE_BIBLE.md 'RULES: sources, expressions...'. Kehati notes: data/kehati/ (read PDF in 6-page batches; larger batches drop images).

## BK 1, 2, 4, 6 clay pictures: how they are wired (2026-10-13)
Originals: data/generated_originals/clay/bk{1,2,4,6}-*.jpg (rejected tries in rejected/). Order after a regeneration of the chapter data: write_bk_1_2.py, write_bk_4_6.py, add_charts_bk.py, add_pictures_bk.py (captions and the pictures lists in layer1), build_overlays_clay_bk1246.py (person tags; vision calls; LOOK at the baked pictures), then build_site.py. Quiz questions: data/quiz_questions.json (full question per picture); principle lines: data/quiz_principles.json; badge 'pays what it benefited': scripts/make_badge_benefit.py. First scenes of a two-scene case (6:4a, 6:4c) have no ruling or quiz; the outcome pictures (6:4b, 6:4d) do. Prompts: scripts/make_prompts_bk1_2_4_6.py (v2 full sets), check_prompts.py before sending, prompt_diff.py against the accepted version. Graphic-novel pictures are not installed yet (the author is running them).

## RULE (author, 2026-10-14; ALWAYS): READ KEHATI BEFORE WRITING ANY PROMPT
YOU MUST ALWAYS READ KEHATI TO FULLY UNDERSTAND THE TOPIC AND THE RELEVANT FACTS AND DETAILS BEFORE WRITING THE PROMPT. Read the passage closely (the commentary, not only the large-print mishnah), write the melakha's essence and the facts the picture must show into data/melakhot_kehati_notes.md, and only then draft the prompt. If Kehati gives several readings, record them and say which is drawn. Anything in a picture that is not from Kehati (tools, clothing, setting) must be listed as such in the notes. Never draft from a quick skim, from memory, or from general knowledge. The same applies to every other source text this project illustrates (read the source first).

## DECISION (author, 2026-10-28): sources are the mishnah, Kehati and the William Davidson English; NO Kulp
English translation = William Davidson Edition (Koren/Steinsaltz), via Sefaria, CC BY-NC 4.0, shown with the mishnah's own words in amber (<b>) and the editors' added explanation in grey. Kulp (text, commentary and outline bullets) is removed from the pages and data; the 97 Kulp-sourced outline bullets were rewritten from Kehati (own words, never his wording). Danby (Oxford UP, 1933) was considered and NOT used: likely still in US copyright (restored foreign work) until 2029 unless Oxford permits. Gaps in Davidson (Zeraim except Berakhot; Taharot except Niddah; also Eduyot, Avot, Middot, Kinnim) are undecided: candidates Sefaria Community (CC0), Silverstein (CC-BY), Open Mishnah (CC-BY-SA), the 1843 'Eighteen Treatises' (public domain). Data backup before the swap: data/_backup_before_davidson/. Helpers: scripts/fetch_davidson_en.py, edit_bullets.py, edit_summary.py.

## Paragraph rule (author, 2026-10-28)
Start a new paragraph whenever the speaker switches or a different tanna states a position ("They said to him", "He said to them", "Rabbi X says/said", "The Sages say"), in both English and Hebrew. Paragraph spacing is .25em. scripts/split_speakers.py applies this; use it for any new text.

## Sages chart and box for the Mishnah: TO SIMPLIFY (author, 2026-10-29; open, not started)
The shared sages kit (reference-kit/sages, wired in 2026-10-29: sage names in the text open the relationship box, a header button opens the Shas-wide chart, /sages page) shows far too much for young readers: the chart lists the whole Talmudic world and the box shows teachers, students, colleagues, family, bio, counts and where quoted. The Mishnah version must filter it down. The author is open to suggestions. Changes go in the kit's sages.js / sages.css (shared with iTalmud: keep iTalmud working, or add a Mishnah-only mode switched by `corpus: 'mishnah'`), not in this site's copy.
First idea (author): a friendlier box. A clay (claymation) picture of the sage in the middle with his name underneath instead of a highlighted box; 2-3 teachers and 2-3 students around him, also clay but smaller and softer, names under them. Not yet decided: how to choose which 2-3 (candidates: the highest `tier_mishnah`, or those named in the same chapter / tractate, or the most named in the Mishnah); what to do with colleagues and family (probably drop, or show only on request); a "show more" for the rest. Clay figures need pictures: one general sage, plus smaller and softer variants (same Kehati-first and source rules as the other illustrations; check how the existing clay people are made before drafting prompts). The chart for the Mishnah should likewise show only tanna'im, only the sages named in the Mishnah (kit has the Mishnah counts), with fewer cells and no "+N more" crowds.

## HEAD COVERINGS in the mishnah pictures (author, 2026-10-30; open, not started)
Men and women in the sages figures had to be redone because some were bare-headed (the teacher-2 and main figures now wear turbans, the three new students are covered from the start; see data/clay_sage_extra_prompts_v1.md). The same applies to the PICTURES THAT ILLUSTRATE THE MISHNAH (BK 1-6, BM 1, the clay and the older sets): go back and add a head covering to every adult man who is bare-headed (a cap, a wrapped cloth or a turban; women already have a white or coloured covering by the rule in STYLE_BIBLE.md). Needs: (1) audit all pictures for bare-headed men (the 'a man with a white cap' wording is already in the cast text of some sets, others never said it); (2) for the prompts not yet run, put the covering into the cast text and into every edit (state it again in edits, or it disappears); (3) for pictures already accepted, an edit prompt 'same picture, only add a simple cloth head covering' worked well for the sages figures (state: keep everything else identical; no stripes or patterns; hair and beard visible); (4) the overlays (badges, tags, chips) are positioned on the person, so a covering that changes the head's size or position may need the overlay moved: recheck them after each edit. Decide children and the exceptions (a man at his own door, in bed, bathing) on purpose. Not yet decided: whether to also redo the older 'graphic novel' set.

## Older-audience pictures in the sculpted-diorama style (author, 2026-10-30; prompts written, pictures pending)
The author and a chat session designed a new style for the teen/adult track (data/diorama_style.md: sculpted-diorama figures, one shared style-neutral scene plus a framing line per picture). Prompts for the 29 pictures that already have graphic-novel versions (BK 3 x14, BK 5 x5, BM 1 x10) are in data/diorama_prompts_bk3-bk5-bm1_v4.md, built by scripts/make_diorama_prompts.py (fixed parts verbatim; scenes from the approved graphic-novel prompts, style-neutral, fixes folded in, every man with a head covering). Younger-track (claymation) block not yet pasted into the style file. The other BK chapters (1, 2, 4, 6) have no older pictures yet. After the author runs them: compare with the graphic-novel set, then redo the overlays (badges/tags are placed per picture) before swapping site/img/older.
