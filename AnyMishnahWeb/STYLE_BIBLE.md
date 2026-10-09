# Style bible and pilot prompts — draft 2026-10-09

Status: **pilot round 1 done (2026-10-09), Mishnah Berakhot 1:1, Gemini / Flux / OpenAI x styles A-E.**
Result (author's aesthetic order): 1. Gemini ("Nano Banana"), 2. Flux, 3. OpenAI. Clay (E) and toy-brick (D) were the most engaging.
Gemini was also the only one to follow the brief on scroll-not-book, visible dawn in the window, and label space inside the scene.

## Rules for every image
- No text, letters or numerals in the image (labels are added later as live text).
- The picture shows the case *and* what is at stake (bubbles with symbols, side-by-side alternatives, "?").
- Leave clear empty space (top strip and margins) for overlay labels.
- Only what the source supports. Check each brief's `avoid` line.
- Wide format, 3:2.
- **Scrolls, never bound books** (1st-century setting). Flux and OpenAI both drew a codex.
- **Show the time of day the case needs.** For 1:1 the window shows the pale sun just rising while the bubble shows the night moon and "?".
- **Label space is part of the scene** (a plain wall or sky area), never a white or blank band, and never any text. One Flux image printed stray words across the top.
- **Alternatives must look different.** Say how many figures each bubble holds and what each does (round 2: "left bubble two figures, one lying and one standing; right bubble ONE figure, walking" worked; a vaguer wording made both bubbles nearly identical). Use tiny clay figures in bubbles, not abstract icons, for kids.
- **No speech bubbles with words.** Use thought bubbles with symbols or tiny figures only.
- **Every figure has a full face** (eyes, nose, mouth); blank faces look eerie. Ask for simple hooded faces for distant figures.
- **Give each recurring character one distinguishing feature** (hat, beard shape, color) and repeat it; otherwise supporting figures clone the reference character.
- **Do not use the word LEGO** in prompts or on the site. Toy-brick images that read as Lego (studs, yellow minifigure heads) carry trademark risk; clay is the safer toy-like style.
- Setting: Land of Israel, roughly the 1st-2nd century CE. Plain wool/linen tunics and cloaks, sandals, stone houses, oil lamps. No modern objects. No images of God.

## Three style directions to test (pick one)
- **A. Storybook watercolor:** soft edges, warm paper texture, gentle palette, friendly rounded faces.
- **B. Clean comic line-and-flat-color:** bold outlines, flat colors, simple shading; crisp symbols for bubbles.
- **C. Simple cartoon:** rounded, minimal shapes, bright palette, strongly readable at small sizes (closest to the AnyDaf sprite look).

- **D. Toy-brick minifigures** (for a younger audience; added 2026-10-09). Generic "toy building-brick figures with simple printed faces" in a physical diorama; do NOT use the word LEGO or imitate any specific creator's scenes. Check trademark/commercial-use with a lawyer before shipping. Similar alternatives without that risk: wooden peg dolls, clay figures, felt/paper cutouts.
- **E. Plasticine clay figures** (added 2026-10-09; the user's suggestion, inspired by clay-animation Torah material). Generic hand-modelled clay characters (best performer in round 1: Gemini) with exaggerated faces, a few repeatable features per character (headwrap stripes, nose, beard color), fingerprint texture, soft studio lighting, plain colored backdrop. Do NOT copy any specific creator's characters. Allow a per-brief tone from playful to gentle; use gentle for solemn cases.

## Audience
Each brief has an `audience`: `kids` (about 8-12: warm, rounded, clay or storybook styles) or `teen` (graphic-novel direction: muted palette, more realistic proportions, expressive less-cartoonish faces, cinematic lighting). Same brief, different style suffix. Doubles image count wherever both are made.

Base prompt (prepend to every scene): `Illustration for a children's and family Mishnah study site, in style {A|B|C|D|E}, 3:2 wide format, no text or letters anywhere, empty space along the top for labels, Land of Israel 1st-century setting, modest simple clothing.`

## Cast sheet (use the same words in every prompt)
- **Rabban Gamliel:** dignified older man, grey-brown beard, dark-blue cloak over a cream tunic, reads by lamp.
- **His sons (two):** young men in festive clothes (colorful sashes, flower garlands), tired and a bit sheepish.
- **Rabbi Tarfon:** middle-aged man, short dark beard, brown traveling cloak, staff beside him.
- **Ben Zoma:** younger scholar, clean-shaven or light beard, bright eyes, gestures as he explains. *(Age is my assumption; the source gives none.)*
- **Rabbi Elazar ben Azariah:** older scholar, white beard, calm. *(The mishnah says only "almost seventy".)*
- **Beit Shammai / Beit Hillel figures:** generic scholars in plain cloaks, one group in cool colors, one in warm.
- **Approaching strangers (Mishnah 3):** two travelers in dark hooded cloaks, shown at a distance, not menacing in detail.
- **Decision (2026-10-09):** the sages' faces are shown in full but stylized.

## Pilot prompts (scene part; add the base prompt before each)
1. **Mishnah 1 (late return):** `Rabban Gamliel, a dignified older man with grey-brown beard and dark-blue cloak, reads by an oil lamp at a table in a stone house. Two young men in festive sashes and flower garlands burst in through the doorway, tired and apologetic. Through the window the sky is just turning grey before dawn. Above the group, a thought bubble with a moon and a question mark. Space on top.`
2. **Mishnah 2 (dawn colors):** `A man in a plain tunic stands at a window at first light, holding up the fringes (tzitzit) of his garment, one blue thread among white. Two thought bubbles above him: in one a blue thread beside a white thread, in the other a blue thread beside a green thread, each with a question mark. Pale dawn sky outside.`
3. **Mishnah 3 (Rabbi Tarfon):** `Night on a country road under a moon. Rabbi Tarfon, a middle-aged man with a short dark beard and a brown cloak, lies on his side on the ground beside the road, his staff nearby. Two hooded travelers approach at a distance among the trees. Two bubbles beside him: one shows a reclining figure and a standing figure, the other shows a walking figure. A small question mark over him.`
5. **Mishnah 5 (Ben Zoma):** `Inside a stone beit midrash. A younger scholar with bright eyes (Ben Zoma) gestures as he explains to an older white-bearded sage seated calmly (Rabbi Elazar ben Azariah), while a few students listen. Above them two bubbles: a sun, then a moon added beside it; and a second bubble with a rising sun and a crown.`
(Mishnah 4 is an SVG diagram; no prompt.)

## Pilot plan
Round 1 (done for Mishnah 1): each prompt in styles A, B and C on 1-2 models (about 8 to 24 images; well under a dollar at the prices we looked up). You choose a direction and say what's wrong. Round 2+: I revise this file. Then run the locked template once on unseen chapters (one case-heavy, one from Taharot) with no tweaks, to measure the first-time hit rate.

## Round 2 plan
0. **Model comparison first (2026-10-09):** same Mishnah 1:1 clay prompt in AI Studio on `gemini-3.1-flash-image` (Nano Banana 2, ~$0.067/img standard, ~$0.034 batch) vs `gemini-nano-banana-2.1` (~$0.034 standard, ~$0.017 batch), 2 runs each. Gemini's own claim about which model the app used is unreliable. Pick the cheaper if quality holds.
1. **Hard scene:** Mishnah 3 (Rabbi Tarfon) in clay on Gemini, using the updated rules above.
2. **Consistency test:** upload the round-1 Gemini clay image of Rabban Gamliel as a reference and ask for the same character in a new scene. If he stays recognizable, scale up; sages recur throughout the Mishnah.
3. **Then:** the locked template on unseen chapters (one case-heavy, one from Taharot) with no tweaks.

## Round 2 results (2026-10-09, Gemini app, clay)
- Mishnah 1 with the updated rules: met every rule (scroll, sun in window, no text/white band, stake visible).
- Mishnah 3 (Tarfon), two runs: the run with two distinct bubbles was clearly better; see the 'Alternatives must look different' rule. Travelers with blank faces look eerie; ask for simple hooded faces.
- Same sage looks different from run to run (Gamliel, Tarfon). Next test: reference-image consistency (step 3).
- Consistency test (Tarfon reference image attached, new scene): same face/beard/vest preserved, so reference images work for one recurring character. The test request did not repeat the no-text / full-face rules, so the printed speech-bubble text, one blank face and look-alike supporting figures do NOT count as failures; they show every request must carry the full rule block (a new chat carries nothing over). Whether the rules prevent them is still to be seen. Next: two reference characters in one scene, with the full rule block.

## Working decision (2026-10-09)
**Kids style = plasticine clay (E), Gemini image model (Nano Banana), reference images attached for each recurring character, and the FULL rule block in every request.** Two-character test passed (Tarfon + a second sage, both recognizable and distinct). Notes: describe each character from its reference image, not the cast sheet (the model follows the written description over the image); include "scrolls never bound books" every time (bound books appeared when the rule was left out). Still to test: three or more characters, a locked template on an unseen chapter, and the teen style. Model/version and cost: see the model-comparison step (needs a paid Gemini API account).

## Visual vocabulary (proposed 2026-10-09 after the Bava Kamma 5 round)
- **Framed panel vs thought bubble.** Halakhic alternatives (the question the mishnah decides) go in **framed boxes**: rounded rectangles floating above the scene, no tail, attached to no one, no icon in the corner (the scroll icon was tried and dropped). **Thought bubbles** are only for what a character is actually thinking, and their dots must lead to exactly one head. (Round 3: bubbles came from the cow, from nowhere, and from a man who wasn't thinking the question.)
- **Pays / does not pay (liable / exempt):** a small round badge in the UPPER-RIGHT corner of the box or picture (never part of the scene): balance scale tipped down with gold coins in the RIGHT pan only = pays; level scale with both pans empty = does not pay. Do NOT use check/cross for liability (they read as right/wrong).
- **With / without permission:** open gate with the householder waving the visitor in vs closed gate with a red no-entry circle. The visitor appears in both panels.
- **Numerals** are allowed where counting matters (e.g. 9 and 10 on a measuring rod). Words stay out: baked-in words cannot be translated or edited. Decision on a short-words exception: author to decide.
- **A visibly pregnant cow** shows 'not yet born'; a calf beside its mother shows 'already born'.
- **Check the legal logic of every symbol pair** before prompting (BK 5:5: death at ten vs death at nine, not injury at nine, since injury is liable at any depth).
- **The question mark sits in the gap between the two panels**, outside both, never inside a panel (author rule, 2026-10-09; the pit picture did it right, the others put it inside a bubble).

## Layouts (added 2026-10-09)
Choose by how the cases relate:
- **Main action scene + two boxes**: one case, the boxes show the alternatives or what happened next (BK 5:1, 5:5, 5:6).
- **Two full scenes side by side (a diptych)**: two different cases with two different rulings (BK 5:2, probably 5:3). The two scenes need only share the same basic setup, not be identical (author, 2026-10-09). Preferred: write two independent prompts from the same setup text, changing only the differences; they can run in parallel/batch. Optional: generate the second as an edit of the first with it attached, if a closer match is wanted.
## More lessons from round 4
- Never describe something in a box as 'tiny'; ask for 'normal size and proportion'.
- Do not mention the scale anywhere except the badge (a scale described 'beside the householder' appeared on the walls too).
- Dead animals: on the back, legs in the air, X on each eye (a sleeping pose reads as asleep).
- Use the same shape for a recurring object (e.g. a round pit) in the scene and the boxes.
- Everything the case needs must be INSIDE the setting it names (the cow and pots were outside the courtyard).

## Symbols are overlays (decided 2026-10-09)
Symbols that sit outside the scene (pay / does-not-pay badges, the '?' between boxes, check/cross) are NOT drawn by the image model (it drifted: coins in both pans, different scales). Make one master set once (data/master_symbols_prompts.md) and overlay it on every picture: for a diptych, at the picture's upper-right corner; for a box layout, at each box's upper-right corner, with the boxes located by scripts/detect_boxes.py (a vision-model call, ~1 cent per image; tested on three BK 5 images, all three boxes pairs found accurately). Prompts keep that corner empty (v4). In-scene symbols (the no-entry circle on a gate) stay in the prompt and get checked. A post-generation vision checklist (right pan only, round pit, no stray text) can catch drift.

## Round 5 lessons (v3 test results, 2026-10-09)
- 5:1 and 5:5 (one run) came out right first time with v3/v4-style prompts.
- Prompts the author paraphrased ('2 panels') produced a merged diptych with different people and the cow/pots outside the courtyard: keep two separate prompts for two scenes, fix the cast with identical clothing/age descriptions in both, and state the camera ('we stand in the street outside the open gate looking in; walls on all sides; everything between the gate and the house').
- A layout must be stated firmly ('exactly two boxes, no more, no fewer'); one 5:5 run omitted the boxes. A vision checklist after generation can catch this and trigger a regeneration automatically.
- Models add unrequested people (a woman bystander in 5:5): say 'Draw ONLY the people and animals named; no extra people'.
- A pit must show depth: use a cutaway side view in boxes, with the ox 'at the very bottom, well below ground level'.
- Payer marking: a person who pays is marked by an overlay (a small copy of the pay badge above his head, or a short arrow from the box's lower edge); remove that person from the boxes so he isn't confused with being there when the harm happens. `scripts/detect_person.py` locates a described figure; tested accurate on 5:6.
- Badge drift in v3: the right-pan-only rule held in all five badges, but the badge frame/color differed per image; overlays still give exactness.

## Round 6 results (v5 prompts, 2026-10-09)
All five BK 5 pictures judged good by the author. 5:2b matched 5:2a only when generated in the SAME chat as an edit ("use the previous picture as the reference: keep exactly the same ...; make only these changes"); an independent new-chat attempt with identical cast text did not match. Artifact: asking for 'the upper-right corner kept plain and empty' made the model draw an inset rectangle in that corner of boxes (5:1, 5:6) -> drop that sentence and let overlay badges overlap the box corner. Backgrounds sometimes white/two-tone: add 'the sky fills the whole background'.

## ABSOLUTE RULE: paired scenes (author, 2026-10-09)
Any two-part picture (identical setup, one key thing different) is made in the SAME chat: generate the first, then ask for the second with "Using the previous picture as reference, everything is exactly the same except: ...". It worked perfectly every time (BM 1:4 pair etc.); never generate the second fresh and hope it matches. In the automated pipeline this means two sequential API calls, the second sending the first image as input plus that sentence. (This supersedes the earlier 'two independent prompts, can be batched' option.)
## Round 7: Bava Metzia 1, first try (9 pictures)
By eye at full size, clean on the first try: 1:1a, 1:1b, 1:2, 1:4a, 1:4b, 1:7 (6 of 9). Defects, all of one kind (counts and placement the prompt did not pin down): 1:5 drew two small children instead of one; 1:3a and 1:3b drew a second purse on the ground; the 1:1 outcome boxes were FINE (a cloak cut in half, and cut 3/4 and 1/4: clear at full size; the checker and a thumbnail view wrongly suggested otherwise). Fixes: say 'exactly N of each person and object' and name where each one is. Checker (tuned): caught 1:5 (extra child) and 1:3b; missed the duplicate purse in 1:3a; was wrong about the 1:1 pointing gestures and the 1:1 outcome boxes (both fine; always view a flagged detail at full size before accepting a 'wrong' verdict, and never judge proportions from a thumbnail); mistook the allowed '?' for a numeral until told it is expected. Use it as a screen, not a replacement for the author's eye; the risk is a false pass.

## Round 8: the author's picture review of BM 1 (2026-10-09)
- **No money/coins for splitting** (1:2 coins were confusing): use fraction overlays (half | half, three quarters | quarter), added in code (scripts/fraction_badge.py, compose_bm1_fractions.py); BK 5 and later chapters may use them too.
- **The '?' only between two possible explanations of one unknown fact** (1:7, BK 5:1); never between separate rulings (1:2) or separate cases (1:5).
- **Make physical constraints obvious**: 'cannot leave the field' means an enclosed field and a closed gate, with no path out (the first 1:4a had the deer next to an exit).
- **Boxes must not duplicate the main scene** (1:5): when the two things are two cases, make them two SCENES (a pair, second as an edit of the first), each with the badge over the right person; no '?'.
- **Different people in the same picture must look different from each other** (1:7: the finder and the people in the boxes looked identical): give each distinct person a different tunic color, beard, cap or hair. The converse holds too: the same person must look the same wherever he appears (main scene and boxes, or the two pictures of a pair).
- **Legend wording is parallel**: 'pays / does not pay', 'keeps it / has no claim', 'returns it / does not return it', 'holds it', 'follows the postscript'.
- Pictures flagged by the author are hidden from the site until redone (1:2, 1:4 pair, 1:5, 1:7).

## RULE: read the source commentary before writing a brief; never add a mechanism the source does not state (author, 2026-10-09)
Before drafting any brief or prompt, read R. Kulp's commentary on that mishnah (and Kehati once available) and take the legal condition from it exactly. Do not invent physical details to dramatize a condition. Example (BM 1:4): Kulp's condition is that the animal is physically unable to leave the field; I wrongly added a fenced field and a closed gate, so the deer could not have got in and the scene looked like a circle dance. The correct picture shows the ANIMAL's inability (a deer with a splinted leg lying on the grass) and the contrast (a healthy deer bounding away); no fence appears anywhere. Check each brief by asking: 'where does the source say this?'

## RULE: where overlay symbols go (author, 2026-10-09)
Place badges and fraction pills TOWARD THE TOP of the picture or box, where least happens, so they never cover a hand, face or object that matters (and read first). Where a symbol describes a relation between two people (a split between them), put it between them, centered on the top edge of the frame. BM 1:1: centered on the top edge of the sign board (canvas padded 70px at the top so nothing is clipped). BM 1:2: centered between the two men on the top frame of each box. Do not default to a box's upper-right corner: that was only a convenient default in BK 5 and BM 1:5, and should be reviewed picture by picture for what it covers.

Placement review of existing pictures (2026-10-09): BK 5:2a/2b badges moved up so they no longer touch the gate door; BK 5:6 payer tag shifted left, clear of the '?'; BK 5:5 and 5:6 box-corner badges kept (the top-centre spot in 5:5 is occupied by the rod and the '10'); BM 1:3a/3b person tags already clear. Rule of thumb: check the candidate spot at full size for what it covers; the top-right corner of a box is acceptable only when the top-centre is busy.

## Round 9 (BM 1 redos, 2026-10-09)
Good first time: 1:2 (with fractions), 1:5a/1:5b (pair), 1:7. Redo: the 1:4 pair. Lessons: (1) 'lies on the grass' made the deer completely still: say 'stands on three legs, hobbling' for a creature that is stuck but present; (2) in an edit, state counts again ('exactly two chasers and exactly one deer') and a direction ('running away from the chasers, who are close behind'); (3) the first 1:7 attempt printed the words CLEAN-SHAVEN, GIVER and BALD as captions even though the prompt said no words: those were descriptor words I had written in capitals; write descriptions in plain lowercase and describe by appearance ('a man with a white cap and a dark blue tunic') not by role labels. Unproven but cheap to avoid. (4) The checker passes 1:5a, 1:5b, 1:7. Tags: 1:5 keeps-tags over the father and the daughter on padded canvases; the 1:7 stop sign sits beside the finder's head.

BM 1 final tally: first try 6/9 clean; after one prompt revision based on the author's review, 9/9. Total picture generations: 9 + 6 reruns. The wording rules that fixed the failures: exact counts, exact direction, name where each object is, state the physical condition of the animal, and nothing the source does not say.

Site legend (author, from a phone screenshot): vertical dividers between symbol groups break when the groups wrap. Below 1000px wide the legend stacks, each group a block separated by horizontal lines, and each symbol is kept together with its words (flex, no wrapping between icon and label). Always check new layout pieces at phone width (375px) as well as desktop.

## Hard-set briefs (2026-10-09; data/hard_set_briefs.json)
Eight mishnayot from the 60-sample that the case template does not fit (Shabbat 7:4, Oholot 13:1, Kelim 5:9, Yoma 6:2, Middot 1:3, Temurah 2:1, Yadayim 3:5, Rosh Hashanah 3:8) were briefed from the mishnah and R. Kulp only. Result: 5 are SVG-only (tables, flows, a map), 2 could take a clay scene (Yoma 6:2, Rosh Hashanah 3:8, the latter mixed with an SVG), and none needs the question mark. About nine new symbol pairs would be needed, so the symbol set will grow with the corpus. Check against Kehati before generating anything. Flag: R. Kulp's commentary on Yadayim 3:5 misquotes the 85-letter verse as Numbers 11:35-36; the mishnah says 10:35-36.

## RULE: plain language in everything a reader sees (author, 2026-10-09)
Do not use overly technical or specialist terms in outlines, charts, diagram labels, captions or symbol legends. Use the plain word a young reader would understand, and keep the source's own term only where it is needed and glossed. Example: the legend said 'follows the postscript'; 'postscript' is a technical word, so it now reads 'follows the attached note' (the diagram card says 'a note (postscript) attached to the documents'). Check each label by asking whether a ten-year-old would know the word; if not, rephrase or gloss it once. Candidates already on the list to rephrase or gloss: 'defiles the hands' (Yadayim 3:5), 'susceptible to impurity' (Kelim 5:9), 'libations' (Temurah 2:1), 'lien' (Bava Metzia 1:6; the legend says 'lien recorded'), 'halitzah', 'ketubah', 'terumah', 'tam'.
