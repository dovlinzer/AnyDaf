#!/usr/bin/env python3
"""outline_pass.py — generate a nested study outline for each daf (Batch API).

Reads, per daf directory:
  01_segmentation.json            shiur sections (full `title`s are raw material for headings)
  02_rewrite_wall_patched.md      the shiur essay (falls back to 02_rewrite.md)
  sefaria_prev.md / sefaria.md / sefaria_next.md   English translation only (no Hebrew:
                                  the outline doesn't need it and it is token-heavy)
  previous daf's essay tail       the start of a daf is often taught at the end of the
                                  previous shiur (Chagigah 6's opening was)

Writes outline/results/<key>/04_outline_<model-tag>.json (+ .raw.txt), where <key> is the daf
directory name, or <daf>_textonly for a text-only run.

Text-only runs ("--dafim gittin_18:textonly") withhold every piece of shiur material (segmentation,
essay, previous essay tail) to test how the pass does from the Gemara alone. A daf with no
output/ directory at all (never processed, e.g. shabbat_38) is read from outline/textonly/<daf>/,
which holds hand-assembled sefaria*.md files; for such a daf the previous daf's essay tail IS
still sent, as it would be in production.

Each model gets its own batch, so one model's slow queue doesn't hold back the others.

The worked examples in the prompt are outline/example_bekhorot_13.json and
outline/example_bava_metzia_3.json: V2 outlines (2026-10-18) finished by hand to the author's review
and the later rules, with a daf summary each (2026-10-19). Keep Bekhorot 13 and Bava Metzia 3 out of
any test set — they are the answer key. (Chagigah 6, the earlier example, still pairs with its Hebrew
version as hebrew_pass.py's model.)

Usage:
    python -u outline_pass.py --dafim gittin_18 shabbat_21 --models claude-sonnet-5 claude-opus-5
    python -u outline_pass.py --dafim gittin_18 --dry-run     # print prompt sizes, no API call
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
OUTPUT = HERE / "output"
EXAMPLES = [("Bekhorot 13", HERE / "outline" / "example_bekhorot_13.json"),
            ("Bava Metzia 3", HERE / "outline" / "example_bava_metzia_3.json")]
EXAMPLE_KEYS = {"bekhorot_13", "bava_metzia_3"}
SPRITE = HERE / "outline" / "sprite.svg"      # shared figure/animal symbols the illustrations draw on
STATE_DIR = HERE / "outline"
RESULTS = HERE / "outline" / "results"
TEXTONLY_DIR = HERE / "outline" / "textonly"
PREV_ESSAY_TAIL_CHARS = 6000
EDGE_ITEMS = 4  # Sefaria items taken from the end of the previous amud / start of the next
POLL_INTERVAL = 60

MODEL_TAGS = {"claude-sonnet-5": "sonnet5", "claude-opus-5": "opus5", "claude-opus-5-5": "opus55"}

SYSTEM_PROMPT = """You are building a study outline of one daf of Talmud for the AnyDaf app. The outline's job is to give a learner a bird's-eye view of how the daf's discussion is built: reading only the headings and their summary lines, a learner should see what the daf discusses, how the parts relate, and where the Gemara goes next. The bullets then fill in each step.

The outline must read as explanation, not as an index. The test: a reader who glances at any part of it should think "I know what this is about," not "this is written for insiders." Comprehensibility matters more than brevity.

## Voice
Numbers that are data in the case are always numerals, in summaries, bullets, headings, charts and pictures alike, even when they stand alone: amounts of money, quantities, measures, weights and sizes, times and ages, and any number a party claims, admits, denies or hands over ("he admits 3 of the 5 *sela'im*", "Witnesses to 50 of a Denied 100", "From 1 to 8 Candles", "3 by 3 fingerbreadths"). Words are for small counts of the people, things or steps in the discussion itself: "two witnesses", "Three Women in One Bed", "One Pot or Two", "two readings of the baraita". Any other number above ten is a numeral. Fractions are written full size with a slash, never as a small fraction character (½, ¾): "3/4 and 1/4", "1/8 or 1/6". Use plain English prepositions: "in the case of the garment" or "regarding the garment", never "over the garment".
Write as a teacher explaining the daf to a capable student sitting across the table: briefly, plainly, in sentences you would actually say aloud. Not a catalog entry, not a lecture. Stay succinct: warmth comes from narrating and explaining, not from extra words. No asides, no "fascinatingly," no rhetorical buildup.

You receive: the shiur's segmentation (the lecture's own section titles, in lecture order), the shiur essay written from the lecture, the tail of the previous daf's essay, and Sefaria's English translation of this daf plus a few lines on either side. Some dafim have no shiur at all; then you receive only the Gemara text (and perhaps the previous daf's essay tail), and you build the whole outline from the text: every bullet is `"source": "gemara"`, and no section carries the "Gemara text only" flag, since the whole outline is.

## Scope
- Outline exactly the lines named under "Lines to outline" in the message. They are set so that consecutive dafim meet with no gap and no overlap (the shiurim run straight through the Gemara, and the boundaries follow them), so start at the first line and end at the last even when that falls mid-exchange; the first section's `text.from` and the last section's `text.to` are those two labels. If the first line picks up an exchange that began earlier, the first section's gist says in a clause what is being discussed ("Continuing the question of whether…"). If a discussion continues past the last line, outline what is here and fill in `continues`. When no lines are named, outline the daf's own two amudim.
- Shiur material that falls outside that scope is left out; mention it in `coverage_notes`.
- Gemara on this daf that the shiur does not discuss is still outlined, from the text alone, with `"flag": "Gemara text only"` on that section. Check the previous daf's essay tail first: the lecturer may have covered it at the end of the previous shiur, in which case use that material and don't flag it.

## Structure: this is the heart of the task
- Build the hierarchy from the logic of the sugya, not from the shiur segmentation. The segmentation is flat and follows the lecture; use it only as a guide to where topics change.
- A top-level section is a self-contained discussion. Its children are the parts of that discussion. Children share the parent's question even when their topics differ: in the Bekhorot 13 example, "Acquiring from a Gentile by *Kesef* or by *Meshikhah*" holds R. Oshaya's baraita, the purchase in each direction, and Ameimar's view under R. Yochanan and Reish Lakish, with its excursion into *ona'ah* and robbing a gentile. They are different topics in one bucket, because they all serve the question of which act acquires between a Jew and a gentile.
- Nest as deep as the logic requires: often two or three levels, sometimes four. A section with no natural parts has no children; don't invent a single child.
- Anchor every section to the Gemara lines it covers with `"text": {"from": "6a.8", "to": "6a.15"}`, using the bracketed labels on the Sefaria lines you are given (a label from the previous amud, such as "5b.24", is fine when the section starts there). A parent's range spans its children's. Ranges follow the Gemara's order; a section that `returns_to` an earlier one still anchors to where it falls in the text. The app uses these anchors to scroll the Gemara text in step with the outline, so they must be exact.
- Keep the Gemara's order. Never move a section. When the Gemara returns to an earlier point, leave the section where it falls and add a `returns_to` link to the earlier section's id, with a short note.
- There will be judgment calls. Make the call, and record in `judgment_calls` each place where a different structure would also be reasonable, saying briefly what the alternative was and why you chose as you did.

## Headers
Headers are labels, not sentences, but every header must make sense read alone, as if in a table of contents, to someone who has not read the section. Write your own; never generic ("The Gemara's Question", "Continued"). The segmentation's `title` fields are raw material only, and they contain errors.
- Name the subject. Not "No Bekhorah" but "A Shevi'it Animal's Firstborn."
- Say exactly what is in dispute. The schools argue over which offering has the higher minimum, not which "must cost more" (a pilgrim may spend as much as he likes on both); a header that loosens the question misstates it.
- Opposing opinions are set off with "vs." ("R. Yishmael vs. R. Akiva: …"); "X and Y" reads as if they agree. A header may also avoid naming both sides ("Why Beit Shammai Favor the Olah and Beit Hillel the Shelamim"), but don't shy away from "vs." when it is the clearest way to show a dispute.
- One clear statement or question, not a string of labels. A short claim with a verb ("Isn't Holy," "Owes the Gifts") reads better than stacked nouns.
- At most one colon, for an attribution ("Rav Chisda:") or the "Mishnah:" label, and no dashes chaining extra labels on the end.
- Technical terms only when the reader can tell from the header what they refer to. Never gloss a term in a header: no English in parentheses. The gloss belongs at the term's first mention in a summary line or bullet, where it links to the glossary.
- Name the issue at stake. When a section sets a criterion or a threshold, the header names what is being defined ("When a Minor's Obligation Starts"), not a "Which X?" question, which sounds like choosing between two Xs rather than setting the criteria.
- Name the idea, not just the ruling. When a section turns on a conceptual principle, above all one the Gemara or the shiur names explicitly, the header names that principle rather than restating the ruling. Fall back to the ruling only when no clear principle emerges.
- Use "Why" only when the section is about the reason. When the point is that something happened (the Gemara strikes a name from a list, rejects a proof), say that it happened: "The Gemara Strikes R. Yishmael from Abaye's List", not "Why the Gemara Strikes…", even if the section also gives the reason.
- Open with "Why" when the section, or much of it, explains or debates the underlying principle: why a courtyard acquires, why an oath is imposed. Sections about details and applications (which cases, which people, what amounts) get a plain topic or a "what" / "can" question, not "Why."
- Name a sage only when the section is about his position: it is challenged, defended or disputed. If his ruling is simply accepted and developed, leave the name out.
- Reasons go in the summary line, not the header. A header may point to the reason in label form when it is the crux, or use "Why…" as above.
- A section that opens a new Mishnah says so: its header starts with "Mishnah:", so the learner sees where each Mishnah begins.
- These rules apply to top-level headers too; a top-level header stays in topic form, as clear as possible.

| Instead of | Write |
| --- | --- |
| Shevi'it Animal: Redeeming a Donkey, Its Own Bekhorah, and Challah | Permissible Uses for an Animal Bought with Shevi'it Produce |
| Rav Chisda: No Bekhorah, but Priestly Gifts — Burning vs. Eating | Rav Chisda: A Shevi'it Animal's Firstborn Isn't Holy, but It Owes the Priestly Gifts |
| Rabbi Yochanan: Neither Owner Nor Thief Can Sanctify a Stolen Object (acceptable) | Rabbi Yochanan: Possession as a Component of Full Ownership (better) |
| Ein Shaliach Li'dvar Aveirah: Could the Agent Refuse, or Is He Bound? (a principle section) | Why Can a Courtyard Commit Theft for Its Owner, When an Agent Can't? |
| A Minor's Chatzer as Yad: Get, Found Items, Girl or Boy? (a detail section) | Can a Minor Acquire Through a Courtyard? Girl vs. Boy, Divorce vs. Found Items |
| The Re'iyah Among the Mitzvot with No Fixed Measure (says where it is listed, not what is discussed) | Does the Re'iyah Have No Minimum, or Only No Maximum? |
| Which Child Must Be Brought Up to the Temple? (sounds like a choice between two children) | When a Minor's Obligation Starts and the Nature of Chinukh |

## Summary lines
Every section gets a summary line, the `gist`, readable on its own. Headers plus summary lines together form the outline's "headlines" view, so they must carry the flow by themselves.
- A summary orients; it doesn't summarize. Its job is to tell the reader what the section is about and what is coming, so they know where they are; the bullets supply the detail. Short is good: often one sentence, rarely more than two or three.
- A top-level summary states the core of the discussion: the question or dispute, and how the sides divide, in a sentence you would say to a student. Leave out background that comes before the debate (what the offerings are, why the question arises at all, that a minor has no obligation of his own); the reader meets it in the bullets. A governing principle that the section's rulings all follow from is not background: when it explains them, open with it in one short sentence ("*Shevi'it* produce is given for eating, not for trade or burning. So a lamb bought with it may not redeem a certain *peter chamor*…"). Only then, if useful, map what the section covers. Never open with "Three steps:" or any label and colon followed by a list.
- If a summary names the principle behind a dispute, it says it concretely ("Beit Shammai favor the *olah*, given wholly to God, and Beit Hillel the *shelamim*, which its owners share"), never as an abstract label ("a question of emphasis in worship"). If it can't be said concretely in a clause, leave it to the bullets.
- A lower-level summary narrates what happens: who says what, and how it comes out, with people (litigants, Rabbis, the Gemara) as the subjects of active verbs. If a second sentence helps, use it to map what the passage covers.
- A summary is made of full sentences, each with its own subject. Don't open with a participle or a dangling connective: a daf that picks up the previous daf's discussion says "The Gemara continues to explore whether…" or "The Gemara continues with R. Chiya's ruling that…", not "Continuing the question of…"; a return says "The Gemara returns to…", not "Returning to…"; and a follow-up question says "The Gemara then asks whether…", not "Then can the Mishnah…?". A plain question may still open a summary ("Why does the tractate begin with the *peter chamor*?").
- A section with several substantial children names its main sub-discussions in its summary, so the headlines view shows them even when they sit a level down.
- State a position plainly in a short sentence of its own, then, separately and briefly, what it does for the argument ("Three pilgrimage offerings, each with its own unique feature. Since only the *chagigah* preceded Sinai, the Sinai *olah* must have been the *tamid*."). Folding the position into a sentence about where the argument goes makes both harder to follow.
- A distinct discussion gets its own sentence. Don't chain it onto a dispute ("…, and Abaye adds that…") as if it were one more position on the same line.

Instead of: "Four cases: both claim the whole garment, one claims all and the other half, two with an animal, and parties who admit or have witnesses, each with its oath and division."
Write: "Two litigants holding one item each swear to their minimum share and divide it. The Mishnah covers equal claims, a whole-versus-half claim, an animal ridden or led, and when no oath is needed."

Instead of: "Three steps: whether an animal bought with Shevi'it produce may redeem a peter chamor, Rav Chisda's ruling that it is exempt from bekhorah but owes the priestly gifts, and the challenge from challah."
Write: "What an animal bought with Shevi'it produce may be used for. It may not redeem a certain peter chamor, though Rav Chisda allows a doubtful one; its firstborn is not a bekhor, but it owes the priestly gifts, a distinction the Gemara tests against challah."

## Bullets
Same voice as the summaries. Each bullet is one complete thought you would say to that student, and it makes sense without the Gemara open. Explain a technical term on first use. Where it helps, orient the student directly ("To follow the cases, keep three parties in view…") or raise the question the Gemara is answering ("How, if Torah money is Tyrian?").
- Each bullet is one step of the discussion: who says what, and on what basis (a verse, a baraita, a sevara).
- `detail`: 2 for the main steps (the standard view); 3 for supporting detail (proof texts, secondary steps, fine points) shown only in the detailed view. Standard view should read as a complete, compact account.
- `source`: "gemara" for what the text itself says, grounded in the Sefaria translation; "shiur" for the lecturer's analysis, including rishonim and acharonim brought in the shiur and conceptual framing. Never present shiur analysis as the Gemara's. Never state Gemara content that isn't in the provided text.
- When a Mishnah or baraita is one tanna's view, open its bullet with the label and the tanna in parentheses: "Mishnah (Beit Shammai): …", "Mishnah (R. Meir): …". This is the one place a parenthesis beats a sentence; never "The Mishnah, by Beit Shammai".
- Mark Hebrew and Aramaic terms in *italics* with single asterisks, as the examples do, in headings and summary lines as well as bullets and charts ("Sumakhos Divides Only Where There Is *Derara de'Mamona*"). In a picture, set a transliterated word in italics with `<tspan font-style="italic">`. No other markup, except the ruling words in a chart cell (see Charts).
- Rulings are "permitted" and "forbidden", never "prohibited": "Prohibited" and "Permitted" look alike at a glance. The same in charts and pictures.
- Name the Gemara's moves precisely, not in the Sefaria translation's wording: a *kushya* or *meitivei* is a challenge or objection; a *ba'ya* is a question. Almost never write "dilemma": keep it for a real choice between two equally weighty options.

## Give the reason
In every summary line and bullet (headers are exempt), give the reason. When a ruling, distinction or objection appears, state the principle or reasoning behind it, not just the conclusion: why the oath is imposed, why the firstborn is exempt but the gifts are owed. A ruling without its reason is the most common thing that makes an outline feel like a list. Not just "Rav Nachman concludes that every kohen is suspect," but "…since any kohen may talk himself into using the donkey before he redeems it."

## Hebrew and Aramaic words: key terms in the original
Anything that merits a key-term entry (see "Key terms"), and any legal category, principle or technical term of that kind, is written in the original, transliterated and in italics, every time it comes up: headings, gists, bullets, charts and picture labels (*garuf ve'katum*, *chazarah*, *mitztamek ve'ra lo*, *kinyan chatzer*, *ona'ah*). Halakhic matters are stated in their proper terms: "the mitzvah of *chinukh*", not "training"; a general English word blurs what the halakha is about and makes the statement weaker. Gloss once, at the first mention outside a heading. The first time a key term or technical phrase appears in a summary line or a bullet, give its English in parentheses right after it, e.g. *hefshet ve'nituach* (flaying and cutting into pieces); after that use the term alone. Never gloss in a heading: headings stay clean, and the term still links to the glossary everywhere. Don't gloss basic vocabulary a Gemara learner already knows (*katan*, *simchah*, *matan Torah*, *mitzvah*, *teiku*). Don't tack a transliterated quotation onto an English sentence in parentheses ("…deletes him from the list (*u'machkeih…*)"); either quote the words as part of the sentence or leave them out. Never write a key term's English translation in its place ("swept", "returning", "shrivels and deteriorates"), and never let the English stand in for it in later bullets: the glossary links the term, and its English is only a gloss. Ordinary things that are not terms of art stay in English: "one kind", not *min echad*; "wax", not *sha'avah*. Never use both names for one thing, least of all in one heading ("*Min Echad* or Two Kinds?").

## Transliteration
Transliterate Hebrew and Aramaic by one standard, whatever the essay or the Sefaria translation does (they differ from it and from each other):
- כ or ך without dagesh is **kh** (*chinukh*, *melakhah*, *berakhah*); ח is **ch** (*chatzer*, *Chagigah*, *nituach*); צ is **tz**; ת is always **t** (*Shabbat*, *Tosafot*); ק is **k**.
- A final ה is **-ah** (*Chagigah*, *mitzvah*, *Mishnah*).
- An apostrophe marks א or ע between vowels **only where the two vowels would otherwise run together** (*re'iyah*, *Mo'ed*, *tanna'im*, *ne'emru*); leave it out where u or i is followed by a different vowel, which is read as two syllables anyway (*nituach*, not *nitu'ach*).
- Prefixes (ו ה ב ל מ ש כ) take an **apostrophe, never a dash**: *ve'nituach*, *kelalot u'feratot*, *ha'mishtameret*, *be'Sinai*.
- Double a letter for dagesh only where the spelling is conventional (*Shabbat*, *Kiddushin*).
- Established spellings override these rules: tractate names as the app lists them (Hullin, Eiruvin, Taanit, Meilah, Moed Katan), sages' names in common English usage (Rav Chisda, R. Yochanan), and this list: {EXCEPTIONS}

## When the essay and the Gemara text conflict, the text wins
The Sefaria text is the authority for what the Gemara says; the essay is the authority only for the lecturer's own analysis. The essay was written from a spoken lecture and contains slips. Whenever the two disagree on a matter of fact about the text, follow the text, and record each discrepancy in `coverage_notes` (what the essay says, what the text says, which you followed). `coverage_notes` and `judgment_calls` are editorial notes for the author's review and are never shown to learners: nothing in a title, gist, bullet, chart or `continues` may mention the essay, a discrepancy or a correction. The learner simply sees the text's version. This covers:
- who said something, including the chain of transmission ("R. Yitzchak bar Nachmani in the name of Rav Oshaya", not "in the name of R. Yehoshua"), and spelling of names ("R. Elazar", not "R. Eliezer");
- what a step concludes: whether a proof is accepted or deflected, whether a question is resolved or left as *teiku* or *teyuvta* (the essay may say the Gemara "reassigns" R. Yishmael when the text only strikes him from the list);
- the order of steps: follow the order of the text even when the essay discusses them in a different order;
- which source is cited (Mishnah, baraita or Tosefta), and chapter numbers, verses and counts.
A difference of interpretation is not a conflict: the lecturer's reading of the Gemara stays in the outline, marked `"source": "shiur"`, beside the Gemara step it explains.

## Charts
- Add a `chart` to a section only when its material really is a grid: several parties, cases or arguments compared along the same dimensions (tanna'im by position, cases by ruling, arguments by rebuttal). It needs at least 2 rows and 2 columns of real content, with no filler cells.
- Most dafim have two to four charts; fewer is right when the daf has little grid-shaped material. Never force one. A chart supplements the bullets; it doesn't replace them.
- When a chart could either replay the Gemara's back-and-forth or set out the principles and distinctions at stake, lean to the conceptual one (what each side holds and why), without becoming abstract.
- A Mishnah with some complexity (several cases, conditions or parties) gets a chart or an illustration that distills it; a simple Mishnah doesn't. This is a judgment, not a rule to apply mechanically.
- List the charts you considered but didn't make in `runners_up.charts`, each with a one-line reason.
- Four columns at most, counting the row labels. A chart of sentences with five or more columns is intimidating and its type gets small, above all on a phone. More columns are fine only when every cell is a word or two, such as a grid of animals or cases against "permitted" / "forbidden" that the colors make easy to read.
- When a party has several items of one kind (two arguments, three conditions, two replies), put them in one cell as a numbered list, one item per line, with a line break between them ("1. ...\n2. ..."), rather than a column for each.
- Keep what answers what side by side. When each side's arguments draw replies from the other side, put the replies to a row's arguments in that same row, in a column such as "The other school's reply", numbered to match: reply 1 sits beside argument 1. Never make the reader trace a reply to a cell in another row.
- Orientation, always: the parties go on the rows (tanna'im, amora'im, schools, versions of a tradition such as "R. Meir's version"), and the cases, questions or aspects being compared go on the columns. Beit Shammai and Beit Hillel are two rows; "left on a swept stove" and "taken off on Shabbat" are two columns. When the grid compares things rather than people (the three pilgrimage offerings and what is unique to each), the things are the rows.
- Every chart has a `title`: a mental anchor that tells the reader what they are about to look at. It follows the header rules (understandable alone, naming the case or the idea, not a string of labels), and when the chart is about a case it states the whole case: "A note with no sum: the creditor claims five *sela'im* and the debtor admits three," not "The baraita of the unspecified note." A chart that lays out a dispute may be titled "X vs. Y: the question" ("Beit Shammai vs. Beit Hillel: which offering has the higher minimum"): unlike a header, the "vs." is welcome here, since it tells the reader the debate is about to be laid out side by side. Name what is at stake, not what the cells hold: "arguments and replies" adds nothing the chart doesn't show. Don't number charts; the site numbers them. An optional one-sentence `caption` may add what the title can't.
- `columns` is the header row; each entry in `rows` is a list of cell strings with the row label first. An empty first header cell is fine.
- `tags` marks each cell's outcome so the site can put a badge and color beside it: the same shape as `rows`, one entry per cell, chosen from this closed list, or `null` for the row label and for any cell that is not an outcome:
  `pays`, `exempt` (owes nothing), `oath`, `no-oath`, `divides`, `takes` (collects or is awarded it), `no-claim`, `keeps`, `returns`, `not-returned` (does not return it), `holds` (holds it without deciding: set aside, left pending, "until Eliyahu comes"), `acquires`, `not-acquired`, `permitted`, `forbidden`, `valid`, `invalid`, `effective` (betrothed, divorced, redeemed, consecrated, it takes effect), `not-effective`.
  Choose the tags by what the chart asks, and keep one family of tags within a chart, so the reader compares like with like. When the chart asks what happens to the disputed object itself (who ends up with it, whether it is divided, whether it is set aside), use the object family: `keeps`, `divides`, `holds`, `takes`: the garment sugyot ("they divide it", "the one in possession keeps it", "it rests until Eliyahu comes"). When the chart asks whether someone owes something, use `pays` / `exempt`, even when the result is that he holds on to an object: "he must give the kohen another lamb" is `pays`, and "he keeps the lamb" against it is `exempt`, since the lamb is only the means of paying. Keep `acquires` / `not-acquired` for whether someone takes possession by a *kinyan* (buying, selling, a gift, a find).
  In a tagged column, every cell that states an outcome gets a tag. A conditional or partial ruling takes the tag of its main outcome, and the condition stays in the words ("pays, only if he admits" is `pays`).
  Add shares only when how the item is divided is itself at stake (three-quarters and a quarter against half each); a plain even split is just `divides`, since "½, ½" on every cell is busy and says nothing. Shares go after a colon, one for each party in the order the cell names them: `divides:1/2,1/2`, `divides:3/4,1/4`, `pays:1/2`. The badge shows only its icon and the shares, never a word, so the shares must be right. A cell whose outcome has two parts that go together ("swears and collects", "divided without an oath") may carry both, joined with `+`, the part most in dispute first (its color marks the ruling words): `divides:1/2,1/2+no-oath`, `takes+oath`. Use one tag when only one part is what the chart is about: favor the issue most in dispute (if the question is whether the item is divided or kept, tag the division, not the oath). Within one column, tag every cell for the same issue, so the reader compares like with like. Tag only a column whose cells are the rulings the chart compares; a column about the source or nature of a law (Torah or rabbinic, the reason, the verse) carries no tags, even when its cells mention an oath. In a tagged cell, wrap the words of the ruling itself in double asterisks ("**the one in possession keeps it**", "**divided without an oath**"); the site sets them a little larger, in the outcome's color. The tag never replaces the words: every cell still says everything in full, as explicit and nuanced as the case needs, because readers can turn the badges off. Judge by what the cell means, not its wording. When a cell is an outcome but no tag fits, leave it `null` and list it in `tag_questions` ({"section", "cell", "note"}), so the author can decide whether a new badge is needed. Leave `tags` out of a chart with no outcomes in it. For example, a chart of the garment cases with columns "", "Claims", "Oath", "Result" might have `"tags": [[null, null, "oath", "divides:1/2,1/2"], [null, null, "oath", "divides:3/4,1/4"], [null, null, "no-oath", "divides:1/2,1/2"]]`.

## Illustrations
Visual learners get 4 to 7 illustrations per daf, scaled to the daf: more for a long daf with several major disputes or many physical cases, fewer for a short or mostly aggadic one. Each is a flat, labeled SVG drawing attached to the section it illustrates, as `"illustration": {"title", "caption", "svg"}`. A picture's job is to let the reader see the case: choose and draw for the reader who can't picture it from the text alone. The `title` follows the header rules and names the case or the idea; don't number pictures, the site numbers them.

Illustrate concrete scenarios, not abstractions. When a case has two or more scenarios, show them side by side, even if each is simple: visual learners grasp a case by seeing its versions. Cases with several parties, or money and objects changing hands, also call for a picture. A point about what a word means is an abstraction; leave it to the text. Don't skip a complicated scenario because it is hard to draw: that is where a picture helps most.

Choose what to draw in this order:
1. A Mishnah with some complexity gets a picture that distills its cases (not a simple one; a judgment, not a rule).
2. The pivotal distinctions and debates that become running themes of the sugya, wherever they sit in the outline: importance decides, not nesting depth. A decisive distinction three levels down deserves a picture as much as a top-level section does.
3. Then any main discussion still unillustrated, then the steps hardest to picture from the text.
4. Revisiting a scene is good when it shows something new: another opinion's arrangement, a changed layout, a later case. Only a repeat that adds nothing is ruled out.
List the subjects you considered but didn't draw in `runners_up.illustrations`, each with a one-line reason.

Good subjects:
- the physical scene the text describes (a stove and where a pot stands on it; the altar and pillars at Sinai);
- the parties to a dispute, grouped by position with their names (the two camps at Sinai);
- counts and comparisons drawn out (Shavuot's 10 olot vs. 2 shelamim, animal by animal);
- a sequence or timeline (Sinai, Ohel Mo'ed, Arvot Mo'av);
- a vivid story or aggada in the text (Rebbi and R. Chama bar Chanina eating shriveled eggs).
How to draw it:
- Show the ruling on the object itself: a dashed line dividing the garment, the document cut in two, the coins going to each party. No abstract stand-ins (bars, proportion meters) when the object can show it.
- Draw the relationships. When a case turns on how the parties stand toward each other (who claims from whom, who swears to whom, who owes whom), arrange the figures so the layout mirrors that structure: three parties in a triangle, two adversaries facing each other. Draw a line for each relationship and label it with the ruling on that line; a dashed line, or none, where there is no claim. Never set the parties in a row when the case is about how they connect. Example, BM 3 (Shevuot 45a): the employer at the top, the storekeeper and the laborer below, "swears and collects" on each line to the employer, and a dashed line between the two of them marked "what business do I have with him?"
- What two parties claim about each other goes on the line between them, one claim above the line and one below it ("What business do I have with him?" / "Even if he swears to me, he is not trustworthy to me"), so the reader sees at once that the claims are parallel.
- Keep the case and the ruling apart. When a picture shows both a scenario and the sages' positions on it, put them in separate bands: the case in one, the disputing sages and their rulings in another, visibly distinct (a light panel behind each, a small label such as "The case" / "The ruling"). The case is the focus: its band is the larger one, and the ruling band is smaller, with smaller figures. Lay the ruling band out differently from the case: the opinions stacked one above the other, each a small `#sage` with its ruling beside it on one line. Never set the sages side by side under the people in the case, which suggests a parallel (this sage goes with that party) that isn't there.
- When a picture is about what one party says, claims, plans or does toward another (a claim, an admission, a ploy, a payment), draw the other party too, facing the first, so the reader sees whom it is aimed at. A debtor's ploy to escape an oath shows the creditor he means to put it to.
- The people are the picture. The parties to a case are drawn the same size. A prop that only says who someone is (a counter for a storekeeper) is small and set off to the side, or left out; it never outweighs the person.
- Put the outcome in the picture: a short caption under each figure or object saying what that party does, gets or swears.
- When the Gemara has a term for the concept, use it as a label and pair it with a concrete instance (*derara de'mamona*: a cow and its calf, with ownership of the calf in doubt).
- When a scene turns on what someone says or thinks, put it in a speech bubble (`#bubble`, `#bubble-r`) or a thought cloud (`#thought`, `#thought-r`), with the text inside it. Don't caption speech as floating quoted text under a figure. Most scenes with dialogue have at least one bubble. Keep bubble text to a line or two, in the speaker's own voice, and in the tense the speaker would use at that moment of the story ("I came for the festival, so I brought him," for what she already did).
- A bubble belongs to its speaker: it sits just above the speaker's head and close to it, with the tail ending just above the head. `#bubble` (tail at its lower left) sits slightly to the right of the head; `#bubble-r` (tail at its lower right) slightly to the left. Pick the side away from lines and other figures. A bubble never floats in open space or seems to come out of a line or another object.
- Center the text in the bubble, with equal space above and below. The bubble's body is the top four-fifths of the symbol (the tail is below it), so for a bubble drawn at y with height h the body's middle is at y + 0.42h: one line has its baseline about 5 below that point; two lines of 14px have theirs about 5 above and 14 below it.
Weaker and stronger choices, from BM 2:
| Case | Weaker | Stronger |
| --- | --- | --- |
| Two holding a garment | A bar below the garment split into halves | A dashed line down the garment itself |
| Which case to draw | Two things "I found it" could mean (a linguistic point) | *Mori ve'amar*: the find vs. the purchase, two real scenarios |
| Two buyers, one shopkeeper | Skipped | Both buyers handing money to the shopkeeper |
| Storekeeper and laborer | The parties' claims, without the document or the ruling | The document divided, with the ruling captioned under the storekeeper |
| *Derara de'mamona* | A general scene | The term as a label, with a cow and calf as the case |
Rules:
- Every label is exact text: names as the text has them, a Hebrew or Aramaic key phrase where it helps (as in the examples), nothing the outline doesn't support. Never depict God.
- Pictures read left to right, since the page is in English: a sequence, a list, or a set of items being compared runs left to right in the order the text gives it (the Mishnah's oven, *kupach* and stove, in that order). A picture of a real physical layout (the Temple, a courtyard, directions) follows the real arrangement and labels the directions instead. Give each Hebrew `<text>` element `direction="rtl"`.
- Draw with simple shapes plus the shared figure library below, which the page already contains: reference symbols with `<use href="#id" x y width height/>` and never redefine them, and never draw a person of your own. Which figure for whom:
  - `#sage` for a tanna, an amora, or any voice that rules on the case (scholar's mantle and scroll), at width w and height 1.75w, colored per figure with `style="color:<robe>;--beard:<color>;--wrap:<head-cloth>;--mantle:<color>"`. Sages stand plainly: no waving, no tallit or tzitzit, no modern dress.
  - the people in the case: `#man` (`style="color:<tunic>;--beard:<c>;--hair:<c>"`; leave the beard off a young man with `--beard:transparent`), `#woman`, `#girl` (a minor daughter), `#child` (a boy or a small child), `#kohen` (`--sash`), each 1:2 (children 1:2 at about half an adult's height). Use women and girls wherever the case has them (a wife, a daughter, a betrothed woman, a widow), and say who each figure is in a label.
  - figures who hold, hand over or reach for something: `#man-reach`, `#woman-reach` (one arm bent forward, facing right) and `#man-reach-r`, `#woman-reach-r` (facing left), styled like `#man` / `#woman`. The hand is at 98% of the figure's width and 56% of its height (for a figure drawn at x, y, w, h: x + 0.98w, y + 0.56h; facing left, x + 0.02w); place the object so it touches the hand. The figures have no other arms. Never draw an arm or hand yourself, as a line, a path or a stroke: drawn arms come out as long sticks. Bring the figure to the object instead of stretching an arm toward it; two people holding one garment stand at its two edges.
  - roles and places: `#court` (a beit din of three; width w, height 0.6w), `#counter` (a shop; put the seller behind it).
  - objects that change hands: `#coins`, `#coin`, `#document` (a note, a get, a bill of sale), `#garment`; animals `#lamb`, `#ram`, `#goat`, `#bull`.
  - `#bubble`, `#bubble-r`, `#thought`, `#thought-r` stretch to any width and height you give them.
  - outcome badges, the same set the charts use: `#badge-pays`, `#badge-exempt`, `#badge-oath`, `#badge-no-oath`, `#badge-divides`, `#badge-keeps` (the item in hand, as `#badge-acquires`), `#badge-no-claim`, `#badge-returns`, `#badge-not-returned`, `#badge-holds`, `#badge-follows`, `#badge-acquires`, `#badge-not-acquired`, `#badge-permitted`, `#badge-forbidden` (square, about 26-32 wide). Wherever a picture shows an outcome, place its badge beside it: under a figure next to what that party does or gets, or in a ruling band between the sage and his ruling, one badge per opinion. The words always appear with the badge.
- `viewBox="0 0 900 H"` with H between 380 and 560, or up to 620 for a picture with a case band and a ruling band. Start with a full-size background rect. Use the examples' palette of soft panel colors, its font families (Newsreader for titles, Public Sans for labels, Frank Ruhl Libre for Hebrew) and minimum text size 12. Keep every element inside the viewBox. No text may run over or touch a drawing, a line, a figure or another label: a line's label sits beside the line in open space, never on it; place labels in open space, and where room is short, break the label onto two lines, shorten it, or move or shrink the drawing to make room. Before finishing each picture, check every label's extent against what lies beneath it.
- Give the root `<svg>` `role="img"` and a `<title>` describing the scene. No scripts, no external images or links, no `<style>` blocks, no ids that could collide with the library's.
- Show rulings in color, the same way every time, because it makes a big difference for visual learners: whatever the picture marks as permitted is green (text `#24592E`, or `#mark-ok` beside it), whatever it marks as forbidden is red (text `#8C2F2F`, or `#mark-no`). Use the marks wherever a case in the picture has a ruling. Only rulings get these colors.
- When a picture sets out a debate over a ruling, make the difference jump out. Word the opinions in parallel, so that only the contested words differ ("both collect with an oath" / "both collect without an oath", not "both swear and collect" / "no oath"), and set those contested words 1px larger, bold, each opinion in its own color. Mark the whole ruling, not just the word that differs: "**can obligate** an oath" / "**cannot obligate** an oath", never "**can** obligate" / "**cannot** obligate", since "can" alone doesn't tell the reader what is ruled. The same goes for the ruling words in a chart cell. Use green and red only when the opinions really are permitted against forbidden; otherwise use a contrasting pair that carries no verdict, such as blue (#1B3A8A) and amber (#9A6212), the same pair for the same two sides throughout the daf. The reason that follows each opinion stays in the plain text color.
- One picture, one point. Draw the contrast the section turns on and leave out what doesn't serve it: where Ben Nannas treats two cases differently, show his two cases side by side and leave the Rabbis' view out, since adding a third opinion turns a clear contrast into a puzzle.
- Opposing claims go in separate speech bubbles, one over each party ("I gave him the food" / "I got nothing"). A line between two figures carries what they share or how they are related, never their competing claims.
- Show each party's outcome once, in one place: on the line to him or under his figure, not both.
- Badges that belong together go together: a party who swears and collects gets the oath badge and the collect badge side by side, in the same place.
- Oath and no oath, pays and exempt, divided and kept are not good and bad outcomes: show them in the blue and amber pair, not green and red, and use the outcome badges for them, never the ✓ and ✗ marks, which are only for permitted and forbidden.
- The caption is one or two sentences saying what the picture shows and where it comes from in the text.

{KEY_TERMS}

## Sages
List in `sages` every tanna, amora and other sage of the Mishnah and Talmud whom the outline names (in a heading, gist, bullet, chart or picture), in order of first appearance. The app shows them in a "Sages" panel with each one's generation, region, teachers and students, and highlights their names in the outline, so the identification must be right.
- The message lists the sage names found in these lines by simple name matching, each with its candidates (an id and a description). It can include false matches and miss names. For a name with one candidate, check it is right; for a name with several, choose by context: who he speaks with or answers, whether he is quoted in a Mishnah or baraita (a tanna) or in the Gemara's own discussion (an amora), and in whose name he speaks. An unqualified name means the sage it conventionally means (R. Shimon in a baraita is R. Shimon bar Yochai).
- Use the chosen candidate's id. For a sage the list doesn't have (it missed the name, or the outline names him from the shiur), give `"id": null` and his full, unambiguous name in `full_name` ("Rabbi Yehuda HaNasi" for Rebbi, "R. Yochanan b. Nappacha").
- `name` is the name as the outline writes it; write each sage's name the same way throughout the outline. `hebrew` is his name as the text has it (or the usual Hebrew form). `sections` lists the ids of the sections that name him.
- Leave out biblical figures (Shmuel the prophet is not the amora Shmuel), schools (Beit Shammai, Beit Hillel), anonymous voices (the Gemara, the Rabbanan, "a tanna", "the Sages"), and rishonim and acharonim brought in the shiur.

## Quiz
Write 8 multiple-choice questions on the daf, in `quiz`, in the order of the Gemara. They are a self-test for the learner, so:
- Test the bottom lines, the themes and the key distinctions (what is the ruling and why, what separates two cases, what a key term means), never the shakla ve'tarya (who asked which question, what came first).
- The question states the whole case it asks about, so it can be answered without the outline open: "A note with no sum: the creditor claims five and the debtor admits three. What does R. Shimon ben Elazar rule?", not "The baraita of the unspecified note: what does R. Shimon ben Elazar say?"
- Four `options`, the right one first (the site shuffles them). Wrong options are plausible: rulings and reasons a learner might confuse, often the other side's view, never jokes.
- `why` is one or two sentences: the reason the right answer is right, in the outline's voice.
- `line` is the Sefaria label where the answer is found, from the lines you were given.
- Same markup as the bullets: Hebrew and Aramaic terms in single-asterisk italics.

## Daf summary
Write it last, in `daf_summary`, from your own outline: nothing that isn't in the sections. It closes the page as a panel the reader opens to review the daf.
- `summary`: one sentence, "Discussion of: …", naming the daf's main topics in order, each with its positions in a few words. It also heads the page.
- `takeaways`: 3 to 5 bottom lines a learner should leave with: rulings, principles and the distinctions that decide them, each a full sentence that is concrete enough to stand alone. Not the shakla ve'tarya (who asked what), and not the section titles restated. `sections` lists the ids it comes from.
- `debates`: 2 to 4 of the daf's main disputes, the ones the daf is built around. `question` as a question; `sides`, each {"who", "view"}, with the parties named as in the outline and the view in a short clause; `outcome`: how it comes out (a ruling, the Gemara's resolution, or that it is left open), or null when the daf moves on without one; `sections`.
- `key_terms`: 3 to 6 of your `key_terms`, written exactly as their `term`, only the ones the takeaways and debates turn on.
- The same voice and markup as the rest of the outline: Hebrew and Aramaic terms in single-asterisk italics, numbers as numerals by the rules above.

## Output
Return only a JSON object, with no prose before or after it and no code fence, in exactly the shape of the examples:
{"daf", "scope": {"start", "end"}, "sections": [node], "key_terms": [term], "sages": [sage], "quiz": [question], "daf_summary": {"summary", "takeaways": [{"text", "sections": [id]}], "debates": [{"question", "sides": [{"who", "view"}], "outcome": string|null, "sections": [id]}], "key_terms": [string]}, "judgment_calls": [string], "coverage_notes": [string], "runners_up": {"charts": [{"section", "subject", "why_not"}], "illustrations": [{"section", "subject", "why_not"}]}, "tag_questions": [{"section", "cell", "note"}]}
node = {"id": "s1", "title", "amud", "text": {"from", "to"}, "gist", "flag"?, "bullets": [{"text", "detail": 2|3, "source": "gemara"|"shiur"}], "chart"?: {"title", "caption"?, "columns": [string], "rows": [[string]] (a cell may hold "\n" line breaks), "tags"?: [[string|null]]}, "illustration"?: {"title", "caption", "svg"}, "returns_to"?: [{"id", "note"}], "continues"?: string, "children": [node]}
question = {"q", "options": [string, string, string, string] (the right one first), "why", "line"}
term = {"term", "hebrew", "sense", "definition", "on_this_daf", "aliases": [string], "sections": [id]}
sage = {"id": string|null, "name", "full_name"?, "hebrew", "sections": [id]}
Ids are unique across the whole outline ("s1", "s2", ... in document order). `amud` is a short label such as "6a", "6a–6b" or "6b → 7a". `judgment_calls`, `coverage_notes`, `runners_up` and `tag_questions` are editorial notes for the author, never shown to learners.
Before you finish, check every chart once more: parties (tanna'im, amora'im, schools, versions) on the rows, cases or aspects on the columns. A column headed with a sage's name is almost always the wrong way round.

## Figure library (already on the page; reference these ids, never redefine them)
{LIBRARY}

## Worked examples, approved by the author as the model
Two dafim, outlined in full. Follow their method, voice and markup; their content is theirs alone.
"""


def sefaria_english(path: Path) -> list[tuple[str, str]]:
    """Return [(label, translation)] for each item, label like '6a.3'."""
    if not path.exists():
        return []
    items, amud = [], ""
    label = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+\S.*?(\d+[ab])\s*$", line)
        if m:
            amud = m.group(1)
            continue
        m = re.match(r"^\*\*(\d+)\.\*\*\s*$", line)
        if m:
            label = f"{amud}.{m.group(1)}"
            continue
        if line.startswith("*Translation:*") and label:
            items.append((label, line[len("*Translation:*"):].strip().replace("**", "")))
            label = None
    return items


def prev_dir(d: Path) -> Path | None:
    m = re.match(r"^(.*?)_(\d+)(b?)$", d.name)
    if not m:
        return None
    stem, num, b = m.group(1), int(m.group(2)), m.group(3)
    cands = [f"{stem}_{num}"] if b else [f"{stem}_{num - 1}b", f"{stem}_{num - 1}"]
    for c in cands:
        for base in (OUTPUT, TEXTONLY_DIR):
            if (base / c).is_dir():
                return base / c
    return None


def next_dir(d: Path) -> Path | None:
    m = re.match(r"^(.*?)_(\d+)(b?)$", d.name)
    if not m:
        return None
    stem, num, b = m.group(1), int(m.group(2)), m.group(3)
    for c in ([f"{stem}_{num + 1}"] if b else [f"{stem}_{num}b", f"{stem}_{num + 1}"]):
        for base in (OUTPUT, TEXTONLY_DIR):
            if (base / c).is_dir():
                return base / c
    return None


# ---------- where each daf's outline starts and ends ----------
# Consecutive shiurim run straight through the Gemara, so they set the boundaries: a daf's outline
# ends at its own last quoted line or just before the next shiur's first quoted line, whichever is
# later, and the next daf's outline starts on the line after. No gaps, no overlaps, and the same
# answer whatever model or effort runs it. Computed locally from each shiur's Gemara quotes
# (03_final.md, verbatim Sefaria text since v10).

def _label_key(label: str) -> tuple:
    m = re.match(r"(\d+)([ab])\.(\d+)", label)
    return (int(m.group(1)), m.group(2), int(m.group(3)))


def _heb(s: str) -> str:
    return re.sub(r"[^\u05D0-\u05EA]", "", re.sub(r"[\u0591-\u05C7]", "", s))


def _pool(d: Path) -> list[tuple[str, str]]:
    """[(label, hebrew)] for the previous amud, this daf and the next amud, in text order."""
    from key_terms_pass import sefaria_bilingual
    items = []
    for f in ("sefaria_prev.md", "sefaria.md", "sefaria_next.md"):
        items += [(lab, he) for lab, he, _ in sefaria_bilingual(d / f)]
    seen, out = set(), []
    for lab, he in sorted(items, key=lambda x: _label_key(x[0])):
        if lab not in seen:
            seen.add(lab)
            out.append((lab, he))
    return out


def quoted_labels(d: Path | None) -> list[str]:
    """The Sefaria lines a shiur quotes, in text order."""
    if not d or not (d / "03_final.md").exists():
        return []
    quotes = [_heb(q) for q in re.findall(r"\*\*Hebrew/Aramaic:\*\*\s*(.+)",
                                         (d / "03_final.md").read_text(encoding="utf-8"))]
    return [lab for lab, he in _pool(d) if len(_heb(he)) >= 8 and any(_heb(he) in q for q in quotes)]


def daf_scope(d: Path) -> tuple[str, str, str] | None:
    """(first line, last line, how) for this daf's outline, or None to use the daf's own amudim."""
    mine = quoted_labels(d)
    if not mine:
        return textonly_scope(d)
    labels = [lab for lab, _ in _pool(d)]
    own = [lab for lab, _ in sefaria_english(d / "sefaria.md")]
    idx = {lab: i for i, lab in enumerate(labels)}
    key = _label_key
    start, end, how = mine[0], mine[-1], ["own quotes"]
    # A shiur's first verbatim quote can come after lines it teaches in paraphrase (Chagigah 6
    # quotes from 6a.15), so a daf always keeps its own amud's opening lines.
    if own and key(own[0]) < key(start):
        start, how = own[0], how + ["from its own first line"]
    prev_q = quoted_labels(prev_dir(d))
    if prev_q and prev_q[-1] in idx:                      # start after the previous daf's end
        after = labels[idx[prev_q[-1]] + 1] if idx[prev_q[-1]] + 1 < len(labels) else None
        if after and key(after) > key(start):
            start, how = after, how + ["previous shiur ran past this one's first quote"]
    nxt = next_dir(d)
    next_q = quoted_labels(nxt)
    if next_q:                                            # the next daf's start, floored the same way
        next_own = [lab for lab, _ in sefaria_english(nxt / "sefaria.md")]
        if next_own and key(next_own[0]) < key(next_q[0]):
            next_q = [next_own[0]] + next_q
    if next_q and next_q[0] in idx and idx[next_q[0]] > 0:  # end just before the next daf starts
        before = labels[idx[next_q[0]] - 1]
        if key(before) > key(end):
            end, how = before, how + ["lines up to the next shiur's start"]
    if not own or key(start) > key(own[-1]) or key(end) < key(own[0]) or key(start) > key(end):
        return None                                        # inconsistent: page boundaries instead
    return start, end, "; ".join(how)


def textonly_scope(d: Path) -> tuple[str, str, str] | None:
    """A daf with no shiur fills the gap between its neighbours' outlines: from the line after the
    previous daf's end to the line before the next daf's start (each side falls back to this daf's
    own first or last line when that neighbour has no shiur either)."""
    labels = [lab for lab, _ in _pool(d)]
    own = [lab for lab, _ in sefaria_english(d / "sefaria.md")]
    if not own:
        return None
    idx = {lab: i for i, lab in enumerate(labels)}
    start, end, how = own[0], own[-1], ["no shiur"]
    p, n = prev_dir(d), next_dir(d)
    ps = daf_scope(p) if p and quoted_labels(p) else None
    ns = daf_scope(n) if n and quoted_labels(n) else None
    if ps and ps[1] in idx and idx[ps[1]] + 1 < len(labels):
        start, how = labels[idx[ps[1]] + 1], how + ["after the previous daf's end"]
    if ns and ns[0] in idx and idx[ns[0]] > 0:
        end, how = labels[idx[ns[0]] - 1], how + ["up to the next daf's start"]
    if _label_key(start) > _label_key(end):
        return None
    return start, end, "; ".join(how)


def essay_path(d: Path) -> Path:
    p = d / "02_rewrite_wall_patched.md"
    return p if p.exists() else d / "02_rewrite.md"


def segmentation_outline(d: Path) -> str:
    seg = json.loads((d / "01_segmentation.json").read_text(encoding="utf-8"))
    lines = []
    for m in seg.get("macro_segments", []):
        lines.append(f"## {m.get('title', '')}  [{m.get('timestamp', '')}]")
        for s in m.get("micro_segments", []):
            lines.append(f"   - {s.get('title', '')}  [{s.get('timestamp', '')}]")
    return "\n".join(lines)


def parse_spec(spec: str) -> tuple[str, Path, bool]:
    """'gittin_18' or 'gittin_18:textonly' -> (result key, source dir, withhold shiur?)."""
    name, _, mode = spec.partition(":")
    if mode not in ("", "textonly"):
        sys.exit(f"unknown mode in {spec!r}")
    src = OUTPUT / name if (OUTPUT / name).is_dir() else TEXTONLY_DIR / name
    has_shiur = (src / "01_segmentation.json").exists() and essay_path(src).exists()
    textonly = mode == "textonly" or not has_shiur
    key = f"{name}_textonly" if mode == "textonly" else name
    return key, src, textonly


def build_user_prompt(d: Path, textonly: bool = False, withhold_prev: bool = False) -> str:
    parts = [f"# Daf: {d.name}"]
    if textonly:
        parts.append("There is no shiur for this daf. Build the outline from the Gemara text alone.")
    else:
        parts.append("## Shiur segmentation (lecture order, full titles)\n" + segmentation_outline(d))

    pd = None if withhold_prev else prev_dir(d)
    if pd and essay_path(pd).exists():
        tail = essay_path(pd).read_text(encoding="utf-8")[-PREV_ESSAY_TAIL_CHARS:]
        parts.append(f"## Tail of the previous daf's essay ({pd.name}), for context only\n…{tail}")

    if not textonly:
        parts.append("## Shiur essay for this daf\n" + essay_path(d).read_text(encoding="utf-8"))

    def fmt(items):
        return "\n".join(f"[{lab}] {txt}" for lab, txt in items)
    scope = daf_scope(d)
    prev_items, next_items = edge_items(d)
    parts.append("## Sefaria English: end of the previous amud (context)\n" + fmt(prev_items))
    parts.append("## Sefaria English: THIS daf\n" + fmt(sefaria_english(d / "sefaria.md")))
    parts.append("## Sefaria English: start of the next daf (context)\n" + fmt(next_items))
    if scope:
        parts.append(f"## Lines to outline\nOutline from [{scope[0]}] through [{scope[1]}]. These boundaries meet "
                     f"the neighbouring dafim's outlines exactly, so start and end there even mid-exchange.")
    else:
        parts.append("## Lines to outline\nOutline this daf's own two amudim, from its first line to its last.")
    parts.append(sage_candidates(d, scope))
    parts.append("Now produce the outline JSON for this daf.")
    return "\n\n".join(parts)


def sage_candidates(d: Path, scope) -> str:
    """The sage names local matching finds in the lines to outline, each with its candidates,
    for the model to confirm or choose between (build_sages.find_names; no API)."""
    import build_sages
    from upload_to_supabase import parse_dir_name
    tractate, _ = parse_dir_name(d.name)
    if scope:
        start, end = scope[0], scope[1]
    else:
        own = [lab for lab, _ in sefaria_english(d / "sefaria.md")]
        if not own:
            return "## Sages named in these lines\n(none found)"
        start, end = own[0], own[-1]
    try:
        rows = build_sages.find_names(build_sages.segs_between(tractate, start, end))
    except FileNotFoundError:
        rows = []
    lines = [f"- {r['name']} [{', '.join(r['lines'][:6])}{', …' if len(r['lines']) > 6 else ''}]: "
             + " | ".join(f"{c} = {build_sages.describe(c)}" for c in r["candidates"]) for r in rows]
    return ("## Sages named in these lines (simple name matching: may include false matches and miss names)\n"
            + ("\n".join(lines) or "(none found)"))


EXCEPTIONS = HERE / "outline" / "transliteration_exceptions.json"
# Chagigah 6's sages (the earlier worked example, still hebrew_pass.py's model and shown on the site). Rebbi and R. Yochanan show
# the id-null case: Rebbi's bare "רבי" isn't matched locally, and R. Yochanan comes from the shiur.
# Shmuel in 6a.3 is the prophet and is left out.
EXAMPLE_SAGES = [
    {"id": "rav-zera", "name": "R. Zeira", "hebrew": "רבי זירא", "sections": ["s1"]},
    {"id": "abaye", "name": "Abaye", "hebrew": "אביי", "sections": ["s1", "s4", "s5", "s8"]},
    {"id": None, "name": "Rebbi", "full_name": "Rabbi Yehuda HaNasi", "hebrew": "רבי", "sections": ["s1"]},
    {"id": "shimon-bar-yochai", "name": "R. Shimon", "hebrew": "רבי שמעון", "sections": ["s1"]},
    {"id": "rabbi-yishmael-b-elisha", "name": "R. Yishmael", "hebrew": "רבי ישמעאל",
     "sections": ["s4", "s5", "s5a", "s6", "s8"]},
    {"id": "rabbi-elazar-b-shamua", "name": "R. Elazar", "hebrew": "רבי אלעזר", "sections": ["s5", "s6"]},
    {"id": "rabbi-akiva", "name": "R. Akiva", "hebrew": "רבי עקיבא", "sections": ["s5", "s5a", "s6"]},
    {"id": "rabbi-yose-hagelili", "name": "R. Yosi HaGlili", "hebrew": "רבי יוסי הגלילי", "sections": ["s5", "s7", "s8"]},
    {"id": "rav-chisda", "name": "Rav Chisda", "hebrew": "רב חסדא", "sections": ["s9"]},
    {"id": "mar-zutra", "name": "Mar Zutra", "hebrew": "מר זוטרא", "sections": ["s9"]},
    {"id": "rav-aha-b-rava", "name": "Rav Acha b. Rava", "hebrew": "רב אחא בריה דרבא", "sections": ["s9"]},
    {"id": None, "name": "R. Yochanan", "full_name": "R. Yochanan b. Nappacha", "hebrew": "רבי יוחנן", "sections": ["s10"]},
]


def key_terms_section() -> str:
    """The key-term rules, shared with key_terms_pass.py (the pilot) so the two never drift."""
    from key_terms_pass import SYSTEM_PROMPT as KT
    a, b = KT.index("## What counts as a key term"), KT.index("## Output")
    body = KT[a:b].replace("## What counts as a key term", "### What counts as a key term").replace("## Fields", "### Fields")
    return ("## Key terms\nList the daf's key conceptual terms in `key_terms`. They appear as a short glossary "
            "at the top of the outline and are highlighted in its bullets; tapping one shows its definition.\n\n"
            + body.strip())


def exceptions_text() -> str:
    ex = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["terms"]
    return "; ".join(f"*{t['use']}* (not {', '.join(t['not'])})" for t in ex) + "."


def example_text() -> str:
    # compact JSON: the examples are about a third of the prompt, and indentation is pure overhead
    return "".join(f"\n### {name}\n" + json.dumps(json.loads(p.read_text(encoding="utf-8")), ensure_ascii=False, separators=(",", ":"))
                   for name, p in EXAMPLES)


def system_blocks() -> list[dict]:
    library = SPRITE.read_text(encoding="utf-8")
    text = (SYSTEM_PROMPT.replace("{LIBRARY}", library).replace("{EXCEPTIONS}", exceptions_text())
            .replace("{KEY_TERMS}", key_terms_section()))
    # One cached block: instructions + library + example are identical across every request.
    return [{"type": "text", "text": text + example_text(), "cache_control": {"type": "ephemeral"}}]


TAG_SUFFIX = ""   # --suffix: a prompt revision's results go beside the earlier ones, not over them


def run_tag(model: str, effort: str | None) -> str:
    """Result tag: 'opus55', or 'opus55_medium' when comparing effort levels, plus any --suffix."""
    return MODEL_TAGS[model] + (f"_{effort}" if effort else "") + (f"_{TAG_SUFFIX}" if TAG_SUFFIX else "")


def build_request(spec: str, model: str, effort: str | None = None) -> dict:
    key, d, textonly = parse_spec(spec)
    # A daf that has its own shiur but is run text-only also withholds the previous essay tail,
    # so nothing from any shiur leaks in; a daf with no shiur of its own keeps it, as in production.
    withhold_prev = textonly and ":" in spec
    return {
        "custom_id": f"{key}__{run_tag(model, effort)}",
        "params": {
            "model": model,
            # Outline + 4-5 SVG illustrations + adaptive thinking; batch requests aren't subject
            # to the SDK's synchronous-timeout limit, so a generous ceiling costs nothing unused.
            # Opus 5.5's ceiling. At effort high, Bava Metzia 11 used all of 64,000 and was cut off
            # before its key terms (2026-09-24); medium used ~56,000 on both test dafim.
            "max_tokens": 128000,
            "thinking": {"type": "adaptive"},
            # Set explicitly so the three models are compared at the same effort
            # (Opus 5.5 defaults to medium, the others to high).
            "output_config": {"effort": effort or "high"},
            "system": system_blocks(),
            "messages": [{"role": "user", "content": build_user_prompt(d, textonly, withhold_prev)}],
        },
    }


def parse_outline(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        fixed = _drop_extra_closers(t)
        if fixed is not None:
            return fixed
        from json_repair import repair_json
        return json.loads(repair_json(t))


def _drop_extra_closers(t: str) -> dict | None:
    """The model sometimes closes one bracket too many, or one too few, at the end of 'sections':
    the root object then ends before key_terms (Bava Metzia 2, Medium), or key_terms lands inside
    the last section (Bekhorot 10, Kiddushin 8, Medium). Drop or add the fewest closers there that
    make the whole reply one object with both keys at the top."""
    k = re.search(r',\s*"key_terms"', t)
    if not k:
        return None
    i = k.start()
    m = re.search(r"[\]\}\s]+$", t[:i])
    if not m:
        return None
    run, start = m.group(0).replace(" ", "").replace("\n", ""), m.start()
    cands = []
    for cut in range(1, len(run) + 1):                      # too many closers
        cands += [run[:pos] + run[pos + cut:] for pos in range(len(run) - cut + 1)]
    cands += [run + extra for extra in ("}", "]", "}]", "]}", "}]}", "]}]", "}]}]", "]}]}")]   # too few
    for c in cands:
        body = t[:start] + c + t[i:]
        for tail in ("", "}", "]}", "}]}"):                 # and whatever the end then lacks
            try:
                d = json.loads(body + tail)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and "sections" in d and "key_terms" in d:
                return d
    return None

def edge_items(d: Path) -> tuple[list, list]:
    """The neighbours' lines shown with the daf: the last EDGE_ITEMS of the previous amud and the
    first EDGE_ITEMS of the next daf, widened to reach this daf's scope (plus two lines of context
    past its end), since a shiur may start or end on a neighbour's lines."""
    scope = daf_scope(d)
    prev_all = sefaria_english(d / "sefaria_prev.md")
    next_all = sefaria_english(d / "sefaria_next.md")
    cut, n = len(prev_all) - EDGE_ITEMS, EDGE_ITEMS
    if scope:
        cut = min(cut, next((i for i, (lab, _) in enumerate(prev_all) if lab == scope[0]), cut))
        n = max(n, next((i + 3 for i, (lab, _) in enumerate(next_all) if lab == scope[1]), n))
    return prev_all[max(cut, 0):], next_all[:n]


def label_pool(d: Path) -> list[str]:
    """The Sefaria labels the model was shown, in text order (edges of the neighbours included)."""
    prev_items, next_items = edge_items(d)
    return ([lab for lab, _ in prev_items] + [lab for lab, _ in sefaria_english(d / "sefaria.md")]
            + [lab for lab, _ in next_items])


def check_anchors(outline: dict, d: Path) -> list[str]:
    """Free local check: every section's text range uses real labels, runs forward, sits inside
    its parent, and starts no earlier than the section before it."""
    pos = {lab: i for i, lab in enumerate(label_pool(d))}
    problems, last_start = [], -1

    def walk(nodes, parent=None):
        nonlocal last_start
        for n in nodes or []:
            rng = n.get("text") or {}
            f, to = pos.get(rng.get("from")), pos.get(rng.get("to"))
            name = n.get("title", n.get("id"))
            if f is None or to is None:
                problems.append(f"{name}: unknown or missing label {rng}")
            else:
                if f > to:
                    problems.append(f"{name}: range runs backward {rng}")
                if f < last_start:
                    problems.append(f"{name}: starts before the previous section")
                if parent and (f < parent[0] or to > parent[1]):
                    problems.append(f"{name}: outside its parent's range")
                last_start = f
            walk(n.get("children"), (f, to) if f is not None and to is not None else parent)
    walk(outline.get("sections"))
    scope, secs = daf_scope(d), outline.get("sections") or []
    if scope and secs:
        first, last = (secs[0].get("text") or {}).get("from"), (secs[-1].get("text") or {}).get("to")
        if first != scope[0] or last != scope[1]:
            problems.append(f"outline runs {first}–{last}, but its lines are {scope[0]}–{scope[1]}")
    return problems


# The closed list of chart outcome tags (the prompt's list; the site maps each to its word, colour and badge).
OUTCOME_TAGS = {"pays", "exempt", "oath", "no-oath", "divides", "takes", "no-claim", "keeps", "returns", "not-returned", "holds",
                "acquires", "not-acquired", "permitted", "forbidden", "valid", "invalid", "effective", "not-effective"}


# A column header that starts with a sage's name or title ("R. Yannai", "Abba Kohen Bardela", "Rav
# Sheshet's reading"). Deliberately broad: it only raises a flag for review.
SAGE_HEADER = re.compile(r"^(?:R\.\s|Rav\b|Rabbi\b|Rabban\b|Rabbeinu\b|Beit\s|Abba\b|Abaye\b|Rava\b|Rabba\b|"
                         r"Shmuel\b|Ulla\b|Reish\b|Resh\b|Rabbanan\b|Chachamim\b|Tanna\b|Ravina\b|Rebbi\b)")


def check_sages(outline: dict, nodes: list, d: Path) -> list[str]:
    """Each sage resolves to one sages.json entry, names real sections, and is named in them;
    a candidate-list name the outline's sages don't cover is reported (it may be fine)."""
    import build_sages
    if outline.get("sages") is None:
        return ["no sages list"]
    probs, ids = [], {n.get("id") for n in nodes}
    by_id = {n.get("id"): n for n in nodes}
    seen = set()
    for g in outline["sages"]:
        slug = build_sages.resolve(g)
        label = g.get("name") or g.get("full_name")
        if not slug:
            probs.append(f"sage '{label}' ({g.get('full_name') or g.get('id')}) doesn't resolve to one sage")
        elif slug in seen:
            probs.append(f"sage '{label}' listed twice ({slug})")
        seen.add(slug)
        bad = [s for s in g.get("sections") or [] if s not in ids]
        if bad:
            probs.append(f"sage '{label}': unknown sections {bad}")
        last = (g.get("name") or "").split()[-1:]    # a light check that the name is really there
        miss = [s for s in g.get("sections") or [] if s in by_id and last and last[0].lower()
                not in json.dumps(by_id[s], ensure_ascii=False).lower()]
        if miss:
            probs.append(f"sage '{label}' not found in sections {miss}")
    return probs


def _num(tag, name, default=0.0):
    m = re.search(rf"\b{name}\s*=\s*['\"]([-\d.]+)", tag)
    return float(m.group(1)) if m else default


def label_overlaps(svg: str) -> list[str]:
    """Labels that run over a figure, an object or a straight line, estimated from the label's length
    (about 0.55 em a character) and the drawing's boxes. A label wholly inside an object is taken as
    meant. Rough by design: it only raises a flag."""
    shapes = []
    for u in re.finditer(r"<use\b[^>]*>", svg):
        tag = u.group(0)
        if re.search(r"#(?:bubble|thought)", tag):       # speech bubbles hold their text
            continue
        x, y, w, h = (_num(tag, k) for k in ("x", "y", "width", "height"))
        if w and h:
            ref = re.search(r"#([\w-]+)", tag)
            shapes.append((x, y, x + w, y + h, ref.group(1) if ref else "drawing"))
    for p in re.finditer(r"<path\b[^>]*\bd\s*=\s*['\"]M\s*([-\d.]+)[ ,]([-\d.]+)\s*L\s*([-\d.]+)[ ,]([-\d.]+)\s*['\"]", svg):
        x1, y1, x2, y2 = (float(p.group(i)) for i in range(1, 5))
        if x1 == x2 or y1 == y2:                          # straight horizontal or vertical lines only
            shapes.append((min(x1, x2) - 1.5, min(y1, y2) - 1.5, max(x1, x2) + 1.5, max(y1, y2) + 1.5, "line"))
    out = []
    for m in re.finditer(r"(?s)<text\b([^>]*)>(.*?)</text>", svg):
        attrs, body = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        fs, x, y = _num(attrs, "font-size", 14), _num(attrs, "x"), _num(attrs, "y")
        w = len(body) * fs * 0.55
        an = re.search(r"text-anchor\s*=\s*['\"](\w+)", attrs)
        a = an.group(1) if an else "start"
        rtl = "rtl" in attrs
        x0 = x - w / 2 if a == "middle" else (x - w if (a == "end") != rtl else x)
        box = (x0, y - fs * 0.8, x0 + w, y + fs * 0.2)
        for s in shapes:
            ix = max(0, min(box[2], s[2]) - max(box[0], s[0]))
            iy = max(0, min(box[3], s[3]) - max(box[1], s[1]))
            inside = s[0] <= box[0] and box[2] <= s[2] and s[1] <= box[1] and box[3] <= s[3]
            # a label set wholly on an object (½ on a garment) is meant; one crossing its edge is not
            if (s[4] == "line" and ix * iy > 0) or (not inside and ix * iy > 0.05 * w * fs):
                out.append(f"'{body.strip()[:40]}' runs over the {s[4]}")
                break
    return out


def check_output(outline: dict, d: Path) -> list[str]:
    """Free local checks beyond anchors: chart orientation (a column headed with a sage's name is
    almost always transposed), key terms (fields, sections, aliases), picture count, and spellings
    the exceptions list rules out."""
    from key_terms_pass import check_terms
    probs, nodes = [], []

    def walk(ns):
        for n in ns or []:
            nodes.append(n)
            walk(n.get("children"))

    walk(outline.get("sections"))
    NUMWORDS = r"\b(?:Eleven|Twelve|Twenty|Thirty|Forty|Fifty|Sixty|Seventy|Eighty|Ninety|Hundred|Thousand)\b"
    for n in nodes:
        if re.search(NUMWORDS, n.get("title") or ""):
            probs.append(f"heading '{n.get('title')}' spells out a number: write it as a numeral")
        t = n.get("title") or ""
        small = re.findall(r"\b(?:two|three|four|five|six|seven|eight|nine|ten)\b", t, re.I)
        if len(small) + len(re.findall(r"\b\d+\b", t)) >= 2 and small:
            probs.append(f"heading '{t}' sets numbers side by side: write them all as numerals")
        for s in [n.get("gist") or ""] + [b.get("text", "") for b in n.get("bullets") or []]:
            # not "hands over the money", where over belongs to the verb
            if re.search(r"(?<!hand )(?<!hands )(?<!handed )(?<!handing )\bover the (?:garment|item|animal|money|field|note|deposit)\b", s):
                probs.append(f"'over the …' in '{n.get('title')}': use 'regarding' or 'in the case of'")
    NUMW = r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
    DATA = rf"\b(?:{NUMW})\s+(?:zuz|dinars?|dinarim|sela'?im|sela|ma'?neh|manim|perutah|perutot|coins|silver|gold|cubits?|amot|tefachim|handbreadths|fingerbreadths|days|years)\b|\b(?:claims?|admits?|admitted|denies|denied|owes|lent|pays?|paid|hands? over|handed over|returns?)\s+(?:only\s+|the\s+other\s+|all\s+)?(?:{NUMW})\b"
    for n in nodes:
        il = n.get("illustration") or {}
        texts = [n.get("title") or "", n.get("gist") or ""] + [b.get("text", "") for b in n.get("bullets") or []]
        texts += [str(x) for r in ((n.get("chart") or {}).get("rows") or []) for x in r]
        texts += re.findall(r">([^<]+)<", il.get("svg") or "")
        bad = sorted({m.group(0) for t in texts for m in re.finditer(DATA, t, re.I)})
        if re.match(r"(?:Continuing|Returning to|Then)\b", (n.get("gist") or "").strip()):
            probs.append(f"summary of '{n.get('title')}' opens with a participle or 'Then': give it a subject (\"The Gemara continues…\")")
        if bad:
            probs.append(f"'{n.get('title')}' spells out amounts in the case ({', '.join(bad[:3])}): write them as numerals")
        if re.search(r"<(?:path|line|polyline)\b[^>]*stroke\s*=\s*['\"]#(?:D6AE86|D8B38E)", il.get("svg") or "", re.I):
            probs.append(f"picture in '{n.get('title')}' draws an arm: use #man-reach / #woman-reach")
    for n in nodes:
        for o in label_overlaps((n.get("illustration") or {}).get("svg") or ""):
            probs.append(f"picture in '{n.get('title')}': {o}")
    for t in outline.get("key_terms") or []:
        if re.search(r"\s(?:and|or|vs\.?)\s|/", str(t.get("term", ""))):
            probs.append(f"key term '{t.get('term')}' names two things: opposites are separate entries")
    for n in nodes:
        cols = (n.get("chart") or {}).get("columns") or []
        sages = [c for c in cols[1:] if SAGE_HEADER.match(str(c).strip("*' "))]
        if sages:
            probs.append(f"chart in '{n.get('title')}' has sages as column headers {sages}: check the orientation")
        ch = n.get("chart") or {}
        cells = [str(x) for r in ch.get("rows") or [] for x in r[1:]]
        if len(cols) > 4 and cells and sum(map(len, cells)) / len(cells) > 20:
            probs.append(f"chart in '{n.get('title')}' has {len(cols)} columns of sentences (limit 4 unless the cells are a word or two)")
        if ch.get("tones") is not None:
            rows, tones = ch.get("rows") or [], ch.get("tones") or []
            if len(tones) != len(rows) or any(len(t or []) != len(r) for t, r in zip(tones, rows)) or \
               any(x not in ("ok", "no", None) for t in tones for x in (t or [])):
                probs.append(f"chart in '{n.get('title')}': tones don't match the rows (shape or values)")
        if ch.get("tags") is not None:
            rows, tags = ch.get("rows") or [], ch.get("tags") or []
            bad = [x for t in tags for x in (t or []) if x is not None and any(y.split(":")[0].strip() not in OUTCOME_TAGS for y in str(x).split("+"))]
            if len(tags) != len(rows) or any(len(t or []) != len(r) for t, r in zip(tags, rows)):
                probs.append(f"chart in '{n.get('title')}': tags don't match the rows' shape")
            if bad:
                probs.append(f"chart in '{n.get('title')}': tags not on the list {bad}")
        if ch and not ch.get("title"):
            probs.append(f"chart in '{n.get('title')}' has no title")
        il = n.get("illustration") or {}
        if il and not il.get("title"):
            probs.append(f"picture in '{n.get('title')}' has no title")
        # speech drawn as floating quoted text rather than in a bubble
        svg = il.get("svg") or ""
        if re.search(r'<text[^>]*>\s*[“"][^<]{6,}', svg) and not re.search(r'#(?:bubble|thought)', svg):
            probs.append(f"picture in '{n.get('title')}' quotes speech but has no bubble")
        # headers: at most one colon, no dash-chained labels
        t = n.get("title") or ""
        if t.count(":") > 1 or re.search(r"\s[—–-]\s", t):
            probs.append(f"header '{t}': more than one colon or a dash-chained label")
        # summaries: no "Three steps:" / label-colon-list openings
        g = n.get("gist") or ""
        if re.match(r"^[\w' ]{1,24}:\s", g) and "," in g.split(":", 1)[1][:120]:
            probs.append(f"summary of '{t}' opens with a label and a list: '{g[:50]}…'")
    pics = sum(1 for n in nodes if n.get("illustration"))
    if not 4 <= pics <= 7:
        probs.append(f"{pics} illustrations (target 4-7)")
    if outline.get("key_terms") is not None:
        probs += [f"key term: {p}" for p in check_terms(outline, outline, d) if "may be fine" not in p]
    ds = outline.get("daf_summary")
    if not isinstance(ds, dict):
        probs.append("no daf_summary")
    else:
        ids = {n["id"] for n in nodes}
        terms = {t.get("term") for t in outline.get("key_terms") or []}
        if not str(ds.get("summary") or "").startswith("Discussion of"):
            probs.append("daf_summary.summary should start 'Discussion of:'")
        if not 3 <= len(ds.get("takeaways") or []) <= 5:
            probs.append(f"daf_summary has {len(ds.get('takeaways') or [])} takeaways (3-5 asked)")
        if not 2 <= len(ds.get("debates") or []) <= 4:
            probs.append(f"daf_summary has {len(ds.get('debates') or [])} debates (2-4 asked)")
        for x in (ds.get("takeaways") or []) + (ds.get("debates") or []):
            bad = [i for i in x.get("sections") or [] if i not in ids]
            if bad or not x.get("sections"):
                probs.append(f"daf_summary item needs section ids from the outline (bad: {bad})")
        for db in ds.get("debates") or []:
            if len(db.get("sides") or []) < 2:
                probs.append(f"daf_summary debate '{db.get('question')}' needs at least two sides")
        missing = [t for t in ds.get("key_terms") or [] if t not in terms]
        if missing:
            probs.append(f"daf_summary key_terms not in key_terms: {missing}")
        if not 3 <= len(ds.get("key_terms") or []) <= 6:
            probs.append(f"daf_summary has {len(ds.get('key_terms') or [])} key terms (3-6 asked)")
    quiz = outline.get("quiz")
    if quiz is None:
        probs.append("no quiz")
    else:
        pool = set(label_pool(d))
        if len(quiz) != 8:
            probs.append(f"quiz has {len(quiz)} questions (8 asked)")
        for k, q in enumerate(quiz, 1):
            o = q.get("options") or []
            if len(o) != 4 or len(set(o)) != 4 or not q.get("q") or not q.get("why"):
                probs.append(f"quiz {k}: needs a question, four different options and a why")
            if q.get("line") not in pool:
                probs.append(f"quiz {k}: line {q.get('line')!r} isn't one of the daf's labels")
    probs += check_sages(outline, nodes, d)
    text = json.dumps({k: v for k, v in outline.items() if k not in ("judgment_calls", "coverage_notes", "runners_up", "tag_questions")},
                      ensure_ascii=False).lower()
    for t in json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["terms"]:
        for bad in t["not"]:
            if re.search(rf"(?<![a-z']){re.escape(bad.lower())}(?![a-z'])", text):
                probs.append(f"spelling: '{bad}' should be '{t['use']}'")
    # A new Mishnah gets "Mishnah:" in the heading of the section that opens there.
    english = {lab: t for f in ("sefaria_prev.md", "sefaria.md", "sefaria_next.md")
               for lab, t in sefaria_english(d / f)}
    opens = {}
    for n in nodes:
        f = (n.get("text") or {}).get("from")
        opens.setdefault(f, []).append(n.get("title", ""))
    scope = daf_scope(d)
    for lab, t in english.items():
        if not re.match(r"\s*MISHNA\b", t):
            continue
        if scope and not (_label_key(scope[0]) <= _label_key(lab) <= _label_key(scope[1])):
            continue
        if lab in opens and not any(x.startswith("Mishnah") for x in opens[lab]):
            probs.append(f"Mishnah at {lab}: heading '{opens[lab][0]}' doesn't start with 'Mishnah:'")
        elif lab not in opens and lab in english and any(
                _label_key(r["text"]["from"]) < _label_key(lab) <= _label_key(r["text"]["to"])
                for r in nodes if (r.get("text") or {}).get("from") in english and (r.get("text") or {}).get("to") in english):
            probs.append(f"Mishnah at {lab}: no section opens there")
    n_pro = len(re.findall(r"\bprohibited\b", text, re.I))
    if n_pro:
        probs.append(f"'prohibited' used {n_pro}x: the author's word is 'forbidden'")
    # The author's rule: "dilemma" almost never (Sefaria uses it for a plain question or challenge).
    n_dil = len(re.findall(r"\bdilemma", text))
    if n_dil:
        probs.append(f"'dilemma' used {n_dil}x: check it isn't a question or challenge")
    return probs


def harvest(client, batch_id, usage_log, src_dirs):
    for r in client.messages.batches.results(batch_id):
        key, tag = r.custom_id.split("__")
        outdir = RESULTS / key
        outdir.mkdir(parents=True, exist_ok=True)
        if r.result.type != "succeeded":
            print(f"  {r.custom_id}: {r.result.type}")
            continue
        msg = r.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        u = msg.usage
        usage_log.append({"id": r.custom_id, "model": msg.model, "stop": msg.stop_reason,
                          "in": u.input_tokens, "cache_read": u.cache_read_input_tokens,
                          "cache_write": u.cache_creation_input_tokens, "out": u.output_tokens})
        if msg.stop_reason != "end_turn":
            print(f"  {r.custom_id}: stop_reason={msg.stop_reason}")
        (outdir / f"04_outline_{tag}.raw.txt").write_text(text, encoding="utf-8")
        try:
            out = outdir / f"04_outline_{tag}.json"
            outline = parse_outline(text)
            from anchor_pass import widen_parents
            pos = {lab: i for i, lab in enumerate(label_pool(src_dirs[key]))}
            for ch in widen_parents(outline.get("sections"), pos):
                print(f"    widened: {ch}")
            out.write_text(json.dumps(outline, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  wrote {out.relative_to(HERE)}")
            for prob in check_anchors(outline, src_dirs[key]):
                print(f"    anchor: {prob}")
            for prob in check_output(outline, src_dirs[key]):
                print(f"    check: {prob}")
        except Exception as e:
            print(f"  {r.custom_id}: could not parse JSON ({e}); raw text saved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True, help="daf dir names; append :textonly to withhold the shiur")
    ap.add_argument("--models", nargs="+", default=list(MODEL_TAGS))
    ap.add_argument("--efforts", nargs="+", choices=["low", "medium", "high", "xhigh", "max"],
                    help="compare effort levels: one batch per model per effort, results tagged e.g. opus55_medium")
    ap.add_argument("--suffix", default="", help="added to the result tag, e.g. v2 -> opus55_medium_v2")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    global TAG_SUFFIX
    TAG_SUFFIX = args.suffix

    for spec in args.dafim:
        key, d, textonly = parse_spec(spec)
        if not (d / "sefaria.md").exists():
            sys.exit(f"no sefaria.md for {spec} (looked in {d})")
        if d.name in EXAMPLE_KEYS:
            sys.exit(f"{d.name} is a worked example; leave it out of the run")

    runs = [(m, e) for m in args.models for e in (args.efforts or [None])]
    sys_chars = len(system_blocks()[0]["text"])
    print(f"{len(args.dafim)} dafim x {len(runs)} runs ({', '.join(run_tag(m, e) for m, e in runs)}) = "
          f"{len(args.dafim) * len(runs)} requests; system prompt {sys_chars:,} chars (cached)")
    for spec in args.dafim:
        key, d, textonly = parse_spec(spec)
        prompt = build_user_prompt(d, textonly, textonly and ":" in spec)
        print(f"  {key:24s} {'TEXT ONLY ' if textonly else ''}user prompt {len(prompt):,} chars")
    if args.dry_run:
        return

    client = anthropic.Anthropic()
    batches = {}
    for model, effort in runs:
        tag = run_tag(model, effort)
        state = STATE_DIR / f".outline_batch_{tag}.json"
        if state.exists():
            batches[tag] = json.loads(state.read_text())["batch_id"]
            print(f"Resuming {tag} batch {batches[tag]}")
        else:
            reqs = [build_request(spec, model, effort) for spec in args.dafim]
            batches[tag] = client.messages.batches.create(requests=reqs).id
            state.write_text(json.dumps({"batch_id": batches[tag]}))
            print(f"Submitted {tag} batch {batches[tag]} ({len(reqs)} requests)")

    src_dirs = {parse_spec(s)[0]: parse_spec(s)[1] for s in args.dafim}
    usage_log, pending = [], dict(batches)
    while pending:
        for tag, bid in list(pending.items()):
            b = client.messages.batches.retrieve(bid)
            c = b.request_counts
            print(f"  {tag:14s} {b.processing_status}: succeeded={c.succeeded} "
                  f"processing={c.processing} errored={c.errored}")
            if b.processing_status == "ended":
                harvest(client, bid, usage_log, src_dirs)
                (STATE_DIR / f".outline_batch_{tag}.json").unlink(missing_ok=True)
                del pending[tag]
        (STATE_DIR / "last_run_usage.json").write_text(json.dumps(usage_log, indent=1))
        if pending:
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
