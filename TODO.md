# AnyDaf study aids — checklist

Covers the study-outline work (outlines, charts, pictures, key terms), the saved Gemara text, the
AnyDafWeb web app, and bringing all of it to the phone apps. Details and history live in
CLAUDE.md ("Study outline pass", "Key conceptual terms", "Saved Bavli text", "AnyDafWeb") and
`AnyDafWeb/DESIGN.md`. Anything that calls the Anthropic API needs the author's go-ahead for that
specific run.

Last updated 2026-09-27.

## Where we are, and the plan to the full run

The outline prompt is essentially final (Opus 5.5, Batch API). 71 outlines exist: 11 test dafim
plus Chagigah 6's example, and the continuous 30-daf batch at both Medium and High. Readers can
see them at https://anydaf-outlines.vercel.app, and testers compare Medium vs High blind at
https://anydaf-outline-test.vercel.app. Nothing is in the apps yet.

Order agreed 2026-09-27 (every step that calls the API needs its own go-ahead):
1. A/B votes from the testers -> choose the effort level (leaning Medium).
2. Settle what changes the prompt, because the full run is paid for once:
   - [x] Sages named by the outline pass (done 2026-09-27).
   - [ ] Summaries and quizzes in the same call: decided yes; design open (see below).
   - [ ] How key terms connect to the master glossary (see "Master glossary" below).
   - [ ] Prompt caching for the full run (see below).
3. Regenerate the 12 test dafim with the final prompt (~$8), author review.
4. ~50-daf sample across daf types (~$35 at Medium, more with summaries/quizzes), author review.
5. Master glossary draft from the sample's terms + the AskAnyDaf taxonomy; author reviews the core
   definitions; the full run gets the standard spellings and senses.
6. Full run (all of Shas, ~2,710 dafim): ~$1,750–1,950 at Medium before summaries/quizzes.
7. Upload to Supabase; then the web app and the phone apps.

Independent of the run, any time: the live-text daf image review, and the author reviews listed
below (glossary pilot, Chagigah 6 key terms, Sages panel).

### Summaries and quizzes: design questions for the author (before step 3)
- [ ] Unit: one summary + question set per top-level outline section, or per section at every level?
- [ ] Summary: reuse the outline's gists + standard-view bullets (lean cost), or separate prose
      (the app today has "facts" and "conceptual" summaries)?
- [ ] Quiz: one question bank serving all four app formats (multiple choice, flashcard,
      fill-in-blank, short answer)? Grading short answers stays a live call, since it depends
      on what the user typed.
- Cost ballpark (2026-09-27, from the 30-daf batch's measured tokens; Opus 5.5 batch output
  ~$12.50/M): lean +$0.04/daf (~$110 for Shas), middle +$0.10 (~$270, ~+15%), rich +$0.19 (~$500).
  Today the app makes these on demand with Haiku per section, per user.

### Master glossary: tie it to the run (proposed 2026-09-27)
Today each daf picks and spells its key terms on its own, and consistency across Shas would be
repaired afterwards by clustering 15,000+ terms. Proposed instead: build the master draft from
the 50-daf sample's terms (~400) + the AskAnyDaf taxonomy, have the author review the core
definitions, then give the full run a compact list of standard spellings and senses so each
daf's terms link to master entries from the start. Not built; awaiting the author's OK.

## For the author

- [x] **Model review finished** (2026-09-24): Opus 5.5. Findings so far are recorded in CLAUDE.md and will go into the prompt together.
      Review page: https://claude.ai/artifact/Er6eCeed7H8dEUTef61RPH
- [ ] **Review the glossary pilot**: are the definitions accurate enough to become master
      definitions, and are 6–8 terms per daf too many?
      https://claude.ai/artifact/Xqa5a7rhaK7EFUg6THCHz9
- [x] Revised Chagigah 6 example headings approved and applied, with s5 split (2026-09-24).
- [ ] **Review the Chagigah 6 key-terms example** (8 terms; the model copies its style).
      Shown in the prototype's glossary panel: https://claude.ai/artifact/VyEhmmkY9siDtWvA6F2WbH
- [x] **Run `daf-text-migration.sql`** in the Supabase SQL editor (done 2026-09-24).
- [ ] Decide: keep or undo the flip of the Beit Shammai / Beit Hillel chart in the Chagigah 6
      example? (You said one of the two flipped charts was already correct.)
- [x] **Run `study-aids-migration.sql`** in the Supabase SQL editor (done 2026-09-24).
- [ ] Decide: dedications on the web app, yes or no?
- [ ] Later: review the master glossary's core definitions (a few hundred core concepts, once).

## Outline generation (daf-processor)

- [x] Review findings applied to `outline_pass.py`'s prompt (2026-09-24; previous version kept as
      `outline_pass.before_review.py`): summary headings with key terms; large-parent gists name
      their sub-discussions; transliteration standard + exceptions; charts two to four, conceptual,
      complex Mishnah, rows/columns restated at the output step, runners-up; pictures 4–7 with the
      priority order, revisits, left to right, runners-up; key terms folded into the call. Local
      checks after each run: sages as chart column headers, picture count, key terms, spellings.
- [x] Effort test run (2026-09-24, $3.13): comparison https://claude.ai/artifact/1gpH815jJnVCTTFnDFQM6K
- [x] Author: medium as good as high, sometimes better (first two dafim).
- [x] Second round: Shabbat 21, Niddah 60, Bava Batra 84 at medium and high ($4.71), with the ruling
      colors and permitted/forbidden wording.
- [x] Round 3 rules in the prompt (Hebrew only for terms of art, "Mishnah:" headings, labels clear
      of drawings, computed daf boundaries) and the fix-up mechanism (Flag buttons + `fixup_pass.py`).
- [x] Round 3: a continuous 30-daf batch at Medium and High (Bekhorot 10–19, BM 2–11,
      Kiddushin 3–12; 60 requests). Fixes it prompted (text-only neighbours, next-daf lines, extra
      bracket, parent widening) are in CLAUDE.md "Effort round 3".
- [x] **Blind A/B page for the daf yomi testers** (`build_ab_review.py`):
      https://claude.ai/artifact/PouYt4zKeJaESnUXUKrap2 (private until the author shares it).
      Which effort is A on each daf is only in `daf-processor/outline/ab_key_round3.json`.
- [x] A/B test hosted on Vercel with votes to Supabase: https://anydaf-outline-test.vercel.app
- [x] `outline-ab-votes-migration.sql` run by the author (2026-09-25).
- [x] Tested: public insert works; bad values and public reads refused; test row deleted.
- [ ] Author: share the A/B link with the testers; later `daf-processor/fetch_ab_votes.py --notes` tallies and unblinds.
- [x] Key terms in the original: prompt rule + local repair of all 71 outlines (CLAUDE.md "Key terms in
      the original"). Next outline run should show it: check a few dafim for English stand-ins.
- [ ] Optional: a local check in `check_output()` for English stand-ins of key terms (the dictionary
      test in `fix_key_term_english.py` works for this).
- [ ] Optional, not planned: rerun BM 3 and Kiddushin 7 with the widened next-daf lines (4
      requests, ~$3). Not needed for the A/B test (both versions share the same gap) and the full
      run regenerates them. If a tester flags the last section of either daf, this is the likely cause.
- [ ] **Author: finalize the effort level** after the testers' comparison (leaning medium).
- [x] **Outline preview site for outside readers**: https://anydaf-outlines.vercel.app (Vercel
      project `dovlinzers-projects/anydaf-outlines`, deployed 2026-09-25):
      the prototype with the 12 test dafim + the 30-daf batch as "Daf N (M)" / "Daf N (H)", and a
      Flag button on every section. Notes go straight to Supabase `outline_feedback` (insert-only
      for the public key). Build: `AnyDafWeb/prototype/build_prototype.py --feedback --out ../site`.
    - [x] `outline-feedback-migration.sql` run by the author (2026-09-25).
    - [x] Deploy approved by the author; live, public, noindex. Redeploy: rebuild into
          `AnyDafWeb/site/` without deleting its `.vercel/` folder (or rerun `vercel link --yes
          --project anydaf-outlines --scope dovlinzers-projects`), then `vercel deploy --prod --yes`.
    - [x] Tested end to end: public insert works; public reads and non-open status refused; test row deleted.
    - [ ] Read notes: `daf-processor/fetch_feedback.py` (`--write` for `fixup_pass.py --from-flags`).
- [ ] Check the 100 dafim whose boundaries fall back to page boundaries before the full run.
- [ ] Optional: a free local check for labels overlapping drawings (render each SVG, compare boxes).
- [ ] Regenerate the 12 test dafim with the final prompt, now with line anchors and key terms.
- [ ] Larger run: ~50 dafim across tractates and daf types (halakhic, aggadic, Mishnah-heavy,
      no shiur), reviewed before going further.
- [ ] Full run, once the output is right. Cost with the revised prompt (Opus 5.5, batch, measured
      2026-09-24): Medium $0.64–0.72/daf, High $0.75–0.97/daf. All of Shas (~2,340 dafim with a
      shiur + ~370 text-only) is ~$1,750–1,950 at Medium, ~$2,000–2,600 at High. The 50-daf
      sample is ~$35 (Medium) or ~$45 (High).
- [ ] Section summaries and quizzes in the same pre-generated call: **decided yes** (author,
      2026-09-27); not built. Needs a design (study units, formats, whether the outline's gists and
      standard bullets replace the summary) before the regeneration of the 12 test dafim.
      Ballpark +$0.04–0.19/daf (+$110–500 for Shas), middle case ~+$0.10 (~+15%).
- [x] Sages named by the outline pass (2026-09-27): `sages` list in the output, chosen from a local
      candidate list in each prompt; `check_sages()` at harvest; the Sages panel uses it. ~+$0.01/daf.
- [ ] Full run: consider a 1-hour prompt-cache TTL. In the 30-daf batch the ~34K-token system
      prompt was cache-written on 47 of 60 requests and read on only 13 (~$0.10/daf of writes,
      ~$270 over Shas). Test on the 50-daf sample: a 1-hour write costs more, so it pays only if
      hits go up.
- [ ] Optional: redeploy anydaf-outlines so its renderer has the chart `tones` support (no
      outline has `tones` yet; matters only once new outlines are on the site).
- [ ] Master glossary: cluster all terms (`build_master_glossary.py`), author reviews the core
      definitions, per-daf terms link to master entries.

## Data (Supabase)

- [x] Saved copy of the whole Bavli: 5,407 amudim in `daf-processor/daf_text/`.
- [x] Loaded into Supabase `daf_text`: 5,407 rows (2026-09-24).
- [x] `daf_study_aids`: 12 test dafim uploaded; the prototype is now built from Supabase
      (`--source supabase`), identical to the local build (2026-09-24).
- [ ] `glossary_entries` table (schema in `AnyDafWeb/DESIGN.md`).
- [ ] Store each shiur quote's Sefaria labels at upload, for the shiur pane's sync.
- [ ] Store each Sefaria segment's audio time. v10 assembly already computes when each segment
      was recited; saving it links the text, outline and audio by the same labels.

## Web app (AnyDafWeb)

- [x] Design doc, shared renderer, Chagigah 6 prototype (Daf / Gemara / Shiur, synced, glossary
      pop-out).
- [x] Prototype covers all 12 test dafim: daf picker, Vilna page images, per-daf data files.
- [x] "At a glance" contents list (top two levels) in the shared renderer.
- [x] Size sliders on both sides (daf page: zoom) and draggable dividers between the panels.
- [x] Contents depth selector (1–5), inside the contents list; the outline itself always shows everything.
- [x] Line anchors added to the 11 test outlines (`anchor_pass.py`, Sonnet 5, $0.26); all pass
      the local checks after parents are widened to span their children.
- [ ] Scaffold the Next.js app (same stack as AnyTorahWeb); study page for the 12 test dafim
      from static JSON.
- [ ] Daf image pane (borrow AnyTorahWeb's `DafImagePanel`); Gemara from `daf_text`; credit line
      for Sefaria's English.
- [ ] Shiur pane: handle the places where the shiur leaves text order (reviews of the previous
      daf, back-references).
- [ ] Pop-outs in their own window (BroadcastChannel sync); then charts, pictures, mind map.
- [ ] Daf picker, glossary pages, link-only access.
- [ ] Extended-sugya / mind-map view (the original third study aid).
- [x] (2026-09-29) Prototype: navigation over all of Shas, Today's daf yomi, Resources pop-out,
      shiur audio with outline/text following and play-from-a-line, phone layout.
- [x] Section pills in the audio panel and the Gemara window; audio panel under the Gemara,
      light blue (2026-09-29).
- [ ] **Print** the outline with its pictures and charts (author, 2026-09-29): a print
      stylesheet that lays out the outline at the chosen detail level, keeps charts and pictures
      whole on a page, drops the controls and text side; maybe options for which parts to include.
- [ ] **Export as a Google Doc** (author, 2026-09-29): the outline, charts as tables, pictures
      as images. Needs a way to write to the reader's Google Drive (Google sign-in + Docs API, or
      a .docx the reader uploads); decide which.
- [ ] Niddah 60 / Berakhot 31: check by ear whether the SoundCloud audio has an intro that
      throws the line timing off (their recordings run 28 s / 61 s longer than the transcripts).

## Phone apps (iOS + Android)

- [ ] Gemara text from `daf_text` instead of live Sefaria, with offline caching. Do this together
      with the outline feature, since the outline's line references must match the text shown.
- [ ] Embed the shared renderer: a bundled `outline.html` in WKWebView / Android WebView, with a
      message bridge for term taps and section changes (the pattern the article reader's audio
      bridge already uses).
- [ ] Outline UI in the apps: detail level, shiur / charts / pictures toggles, glossary sheet,
      and syncing with the existing Text and Shiur views.

## Later

- [ ] Apply the transliteration standard to the shiur essays (2,363 dafim; they mostly write kaf as
      "ch"). Start with the glossary's key terms, which a known-spelling list can fix for free;
      respelling every Hebrew word is a much larger job. Author: wanted, not urgent.
- [ ] Keep adding to `transliteration_exceptions.json` as conventional spellings come up.

## Sages panel (pilot built 2026-09-24)

- [x] `daf-processor/build_sages.py` (no API cost): 1,032 Sefaria people (generation, teachers,
      students, bio) + Hebrew Wikipedia's categories for Eretz Yisrael / Bavel, merged into
      `outline/sages/sages.json`; names found on each test daf -> `outline/sages/mentions/`.
      Sages pop-out in the prototype (timeline by generation, EY above / Bavel below; a card per
      sage; click a line to jump the Gemara).
- [x] Sages' names highlighted in the outline (shared renderer, `sages`/`onSage`), opening the box
      at that sage; box lists the outline sections each sage is in; A–Z order; line numbers hidden
      from readers (2026-09-24). Names in headings, charts and pictures aren't highlighted (same as
      key terms).
- [ ] **Author: review the panel** on a few dafim (right sages? right facts? useful layout?).
- [ ] Author: confirm the 7 regions filled from general knowledge (`outline/sages/overrides.json`).
- [x] Ambiguous names (R. Elazar tanna/amora, Rav Kahana, ...): the outline pass now names its
      sages (2026-09-27); the era-of-neighbours guess is only the fallback for older outlines.
- [ ] ~700 Sefaria people have no generation or region at all (mostly minor or Yerushalmi-only
      names); the ones that turn up on real dafim need filling.
- [ ] Confirm Sefaria's license terms for the topic bios before publishing more widely.
- [ ] A `sages` table in Supabase (the prototype reads local files even with `--source supabase`).

## Research

- [ ] **Live-text daf image** (`daf-processor/page_layout/`, started 2026-09-24 from the author's POC):
      Sefaria text aligned to the apps' own Vilna scans by word widths (no OCR, no API cost,
      ~1 s/amud). Every word box carries its Sefaria ref, so a Gemara segment ('13a.4') or comment
      maps to the lines it covers on the page. Tested on 62 amudim (Yevamot 2b–3a, BM 2a–11b,
      Kiddushin 3a–12b, Bekhorot 10a–19b): Gemara 99% of words placed, flagged on 3 amudim.
    - [x] Package + CLI (`python -m page_layout.run Tractate 2a-11b`), review viewer
          (`page_layout.viewer`), QC summary (`page_layout.report`), debug drawing.
          Viewer for all 62 amudim: https://claude.ai/artifact/MughvYTo5uHpJA3CCVpL87
    - [ ] **Author: look over the viewer** (Gemara first; Bekhorot's Rashi/Tosafot are known weak).
    - [x] Automatic frame, amud a/b sides, per-page type sizes, header lines, full-width lines
          above/below the Gemara, carry-overs chained between consecutive amudim.
    - [ ] Other commentaries printed in the frame: Rabbenu Gershom (Bekhorot, square type) is
          swallowed by the Rashi stream; Shita Mekubetzet note markers add unmatched words.
    - [ ] Bekhorot 13b, 16a, 17b Gemara; perek endings (Hadran) and openings.
    - [ ] Golden set (~20 hand-checked amudim) + regression test; run a full masechet.
    - [x] Hooked into the web prototype (2026-09-28): layouts for all 131 amudim on the preview
          site; the current section marked on the page (Rashi/Tosafot on its lines in amber),
          tap a line or comment to read it and move the outline. Live on
          https://anydaf-outlines.vercel.app (Daf pane) since 2026-09-28.
    - [ ] Store per-amud JSON in Supabase (today it rides in each daf's data file), for the
          Next.js app and the phone apps; then the audio segment on the page.

## Done recently (2026-09-25 to 27)

- [x] All 60 round-3 outlines on the preview site with "(M)"/"(H)" labels and Flag feedback to Supabase.
- [x] Glossary and Sages boxes close on the hosted site (the page now carries its own base CSS).
- [x] Key terms kept in the original across all 71 outlines (1,030 local edits, no API); opposites
      (*mitztamek ve'yafeh lo* / *ve'ra lo*) as separate entries.
- [x] Glossary order toggle (as they appear / A–Z); Sages box size button and resizable timeline.
- [x] Chart rulings colored: a cell stating one ruling is colored whole, otherwise just the ruling
      words; new outlines mark each cell themselves (`chart.tones`), the word-reading is the fallback.
- [x] Blind A/B test on Vercel with votes to Supabase.
- [x] Outline pass names its sages (`sages` list, local candidates in the prompt, `check_sages()`).

## Done earlier (2026-09-24)

- [x] Outline test run: 12 dafim × 3 models, with the review page.
- [x] Line anchors (`text: {from, to}`) and their validator added to the outline prompt.
- [x] Glossary pilot: Sonnet 5 vs Opus 5.5 ($1.30), with the review page.
- [x] Gemara on the right by default; ⇄ swap; א / אA / A; shiur pane synced (27/27 quotes).
