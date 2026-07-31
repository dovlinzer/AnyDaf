from typing import Optional


def _daf_label(masechta: str, daf: int, amud: Optional[str] = None) -> str:
    return f"{masechta} {daf}{amud or ''}"


def segmentation_prompt(masechta: str, daf: int, timestamped_transcript: str,
                        amud: Optional[str] = None) -> str:
    label = _daf_label(masechta, daf, amud)
    return f"""You are analyzing a transcript of a Talmud lecture (Daf Yomi shiur) on {label}.

Produce three layers of segmentation:

1. MACRO SEGMENTS (2–6 per daf): Major conceptual units representing the primary topics or \
arguments covered. For each, provide:
   - title: a full descriptive title (no length limit) — used as a section header in the \
written essay.
   - display_title: a short label (25 characters or fewer) — shown as a navigation pill in \
the audio player. Use short, dense labels like "Psulo Kodem Shechita", "Mum Debate", \
"Chutz Limkomo", "Nesachim", "Shelo Lishma". Drop articles, conjunctions, and filler words. \
Hebrew/Aramaic terms count toward the limit.
   - timestamp: the [MM:SS] of the nearest sentence where it begins.

   CRITICAL ORDERING RULES — you must follow these exactly:
   - Macro segments MUST appear in strict chronological order. The timestamp of each macro \
segment must be later than the timestamp of the previous one.
   - Micro segments within each macro segment must also be in strict chronological order.
   - A macro segment's first micro segment timestamp must be >= the macro segment's own timestamp.
   - A macro segment's last micro segment timestamp must be < the next macro segment's timestamp.
   - If the lecture introduces Topic A, then digresses to Topic B, then returns to Topic A: \
create THREE macro segments — "Topic A", "Topic B", "Topic A (continued)" — in the order \
they actually appear in the audio. Do NOT merge the two occurrences of Topic A into one \
segment with a timestamp from its first appearance.
   - NEVER group non-contiguous audio into one macro segment. If a topic is discussed at \
minute 62 and again at minute 88, with unrelated content between them, those are two \
separate macro segments, not one. A macro segment must cover a single uninterrupted \
block of the audio — its micro timestamps must form a continuous, non-overlapping sequence \
with no gaps large enough to contain other topics.
   - SELF-CHECK before outputting: verify that for every consecutive pair of macro segments \
(N, N+1), the last micro timestamp of N is earlier than the first micro timestamp of N+1. \
If any violation exists, split or reorder until the constraint holds.
   - UNIQUE DISPLAY TITLES: Every display_title across all macro segments must be distinct. \
No two macro segments may share the same display_title or near-identical wording (e.g., \
"Rov Presumption" and "Rov Presumption…" are too similar). If a topic continues after an \
interruption, append a distinguishing term instead of an ellipsis — e.g., "Rov: Witnesses", \
"Rov: Final Ruling", "Migo II", or "Topic A (Resumed)". The same uniqueness rule applies \
to micro segment display_titles within the same macro segment.

2. MICRO SEGMENTS: Finer divisions within each macro segment, suitable for audio chapter \
markers. For each, provide a full title (no length limit), a display_title (25 characters \
or fewer, same convention as macro segments), and a timestamp. Must be in chronological \
order within their parent macro segment.

3. TOPICAL TAGS: Recurring halachic concepts, terms, and named disputants that appear across \
multiple segments (e.g., "piggul," "kiddush halechem," "im alu lo yered," \
"Rabbi Eliezer vs. Rabbi Yehoshua"). For each tag, list the timestamps where it appears.

Return ONLY raw valid JSON with this exact structure — no markdown fences, no ```json, no commentary before or after:
{{
  "masechta": "{masechta}",
  "daf": {daf},
  "amud": "{amud or ''}",
  "macro_segments": [
    {{
      "title": "...",
      "display_title": "...",
      "timestamp": "MM:SS",
      "micro_segments": [
        {{"title": "...", "display_title": "...", "timestamp": "MM:SS"}}
      ]
    }}
  ],
  "topical_tags": [
    {{"term": "...", "timestamps": ["MM:SS"]}}
  ]
}}

TIMESTAMPED TRANSCRIPT:

{timestamped_transcript}"""


def rewrite_prompt(masechta: str, daf: int, transcript: str, segmentation_json: str,
                   amud: Optional[str] = None) -> str:
    label = _daf_label(masechta, daf, amud)
    return f"""You are editing a transcript of a Talmud lecture (Daf Yomi shiur) on \
{label} into a polished written essay for a learned Jewish audience familiar \
with Talmudic terminology.

Begin the document with a top-level header (# {label} — Daf Yomi Shiur). \
Use the `display_title` field of each macro segment as the ## section header, \
copied verbatim — do not rephrase, truncate, or substitute any other field. \
There must be exactly one ## heading per macro segment, in order. \
Do not create additional ## headings; if you need to subdivide within a macro segment, \
use ### instead. \
Within each ## section, use the `display_title` field of each micro segment as the \
### subsection header, copied verbatim.

SEGMENTATION:
{segmentation_json}

GUIDELINES:
- Maintain the author's voice: direct, analytically rigorous, willing to flag when \
something is surprising or counterintuitive ("this is a striking Gemara," "the argument \
seems to favor X, yet...")
- NEVER REFER TO THE LECTURER IN THE THIRD PERSON. The essay is written in the \
lecturer's own voice, so phrases like "as the lecturer notes," "the lecturer observes," \
"the lecturer acknowledges," "the lecturer offers the analogy of..." must not appear — \
they turn the lecturer's own analysis into a report about someone else. Simply state the \
point directly: "as noted above," "this is, admittedly, an unsatisfying Gemara," "consider \
the analogy of catastrophic insurance." Where the lecturer appears as a party in a worked \
hypothetical ("a debt that Reuven owes to the lecturer"), use first person instead — "a \
debt that Reuven owes me" — which is how it was actually said. This applies to any \
third-person stand-in for the speaker, not only the word "lecturer".
- Preserve all halachic analysis, source citations, named opinions, and textual references \
exactly — do not simplify, omit, or reorder arguments. Source attributions are especially \
critical: when the lecturer attributes a statement or explanation to a specific source \
(*Tosafot*, *Rashi*, a named Amora, the *Gemara* itself), that attribution must be \
clearly maintained and must not be merged with or transferred to a different source. \
If *Tosafot* offers one explanation and the *Gemara* offers a separate one, they must \
appear as distinct attributed positions, not conflated into a single account.
- TRANSLATION OF HEBREW/ARAMAIC TERMS: Translate Hebrew and Aramaic terms that appear in \
the lecturer's own explanatory prose into English. For example, "a korban on the \
mizbeyach" → "a sacrifice on the altar"; "a keves or ayil" → "a lamb or ram". \
Do NOT translate the following categories — keep them as *italicized transliterations*:
  (1) Proper nouns: names of people (*Rabbi Yochanan*, *Abaye*, *Rava*), places \
(*Bavel*, *Eretz Yisrael*, *Yerushalayim*), tractate names (*Menachot*, *Yevamot*).
  (2) Widely-used Jewish English terms that carry meaning beyond a plain translation: \
*mitzvah*, *Shabbat*, *Yom Tov*, *Yom Kippur*, *Torah*, *halacha*, *pasuk*, *bracha*, \
*daf*, *masechta*, *sugya*, *machloket*, *mishna*, *Gemara*, *baraita*, *tanna*, \
*amora*, *Rishonim*, *Acharonim*, *psak*, *teshuvah*, *beit din*, *tzaddik*.
  (3) The central technical terms of {masechta} — the concepts that define this \
tractate's subject matter and would be awkward or confusing to translate throughout. \
Use judgment: if a term appears repeatedly as the core subject of the tractate \
(e.g. *korban*/*korbanot*, *olah*, *mincha*, *mizbeach* in a tractate on temple \
service; *yibbum*, *zikkah*, *chalitza* in a tractate on levirate marriage; \
*kiddushin*, *get* in a tractate on marriage law), keep it in transliteration.
  (4) Terms being analyzed as specific words — when the Talmudic argument turns on \
the precise word itself ("the word *X* teaches..."), keep the original term.
- DIRECT TALMUDIC QUOTATIONS: When the lecturer reads aloud a phrase from the Gemara, \
baraita, or mishna, always present it as *italicized transliteration* — English \
translation (e.g. *Tanu Rabbanan* — the Rabbis taught; *shlosha lugim* — three log; \
*ve-dilma* — perhaps). Do not omit the transliteration for direct quotations even \
when you are translating the lecturer's own vocabulary elsewhere. This double form \
is required for subsequent processing.
- Do not use Hebrew script inline in the prose body. Hebrew script belongs only in \
the Sefaria blockquotes, not in running English text.
- Transliterated terms that are retained are always **lowercase** in prose body text, \
regardless of how they appear in the source transcript. Do not capitalize common \
Hebrew/Aramaic nouns mid-sentence (e.g. *kaveiret*, *lechatchila*, *meitivei*, \
*tanur*, not *Kaveiret*, *Lechatchila*, *Meitivei*, *Tanur*). The only exceptions \
are proper nouns: names of people (*Rabbi Hiyya*), places (*Sura*, *Bavel*), and \
tractate names (*Chullin*, *Menachot*) retain their initial capital.
- Hebrew letter names used as numbers: when a Hebrew letter name is spoken as a numerical \
reference (daf number, amud, pasuk, perek, mishnah, etc.), convert it to its Arabic numeral. \
Standard values — alef=1, bet/beis=2, gimel=3, dalet/daled=4, heh/hey=5, vav=6, zayin=7, \
chet/ches=8, tet/tes=9, yud=10, kaf=20, lamed=30, mem=40, nun=50, samech=60, ayin=70, \
peh=80, tzadi/tzadik=90, kuf=100, reish=200, shin=300, taf/tav=400. Multiple consecutive \
letter names combine additively (highest value first): "ayin tet" = 70+9 = 79. Examples: \
"daf ayin tet amud bet" → "79b"; "Pasuk heh" → "Pasuk 5"; "daf chof zayin amud alef" → \
"27a". Do NOT convert when the letter itself is the subject — e.g. in an acronym \
("Vav stands for vlad chatat"), a linguistic remark ("the word ends with a taf"), or any \
explicit discussion of the letter as a letter rather than as a number.
- Cut: filler phrases ("okay," "let's take a look," "you know," "so"), logistical comments \
("it is the 23rd of the Omer"), and off-topic side remarks. Cut PAGE-NAVIGATION \
directions in particular — instructions telling listeners where to look on the physical \
page, which mean nothing to a reader of the essay: "we pick up at the bottom of 173b", \
"about ten lines from the bottom", "at the two dots", "the last of the wide lines of \
Rashi at the top", "Today's daf is 174". Open with the substance, not with where the \
passage sits on the page. You may cut repetitive \
restatements only in the lecturer's own explanatory prose — NEVER cut or compress the \
Talmudic text itself (Gemara passages, beraitot, mishnayot, Rishonim quotations, or \
named Amoraic/Tannaitic rulings), even when a passage appears to restate something \
already said.
- Do NOT cut background explanations of Talmudic concepts, institutions, or terminology \
that the lecturer introduces — for example, an explanation of what a *mavoi* is, how \
*eruvin* work, what *tumah* means, or any similar orientation to a concept that may be \
unfamiliar to the reader. These are valuable pedagogical content even when they \
temporarily digress from the main halachic argument, and they must be retained in full.
- Student questions: if a question prompted a substantive explanation, absorb it into the \
prose as a natural transition ("One might ask...," "This raises the question of...," \
"A closer look reveals..."). If an exchange was logistical or tangential, omit it entirely.
- Write in flowing paragraphs. No bullet points or numbered lists.
- Do not add analysis, conclusions, or sourced references that are not present in the \
original transcript.

CRITICAL — NO SKIPPING TALMUDIC TEXT:
Every Talmudic passage the lecturer reads aloud — Gemara, baraita, mishna, Rishon, or \
named ruling — must appear in the essay together with its full exposition. When the \
lecturer moves to a new passage (even a short one, even one that seems like a challenge \
or transition), include that passage and the discussion of it. Do not defer it to a later \
section on the grounds that a related topic is resolved there, and do not collapse a \
multi-step dialectic (challenge → partial answer → further challenge → final answer) into \
only its final conclusion. Each step of the dialectic, including intermediate answers that \
are later revised or retracted, must appear in the section where the lecturer covers it — \
not grouped with related material from a different point in the lecture.

Pay particular attention to brief dialectical moves that are easy to overlook: \
a one-sentence answer or wordplay (*aliyah* = *me'uleh*), a first answer that is quickly \
challenged (*targuma* + one phrase), a short transitional question (*vi'amai...*, \
*vi'ha vi'khen katani...*) posed between an answer and its follow-up objection. \
Each of these is a real move in the Talmudic argument and must be written into the \
essay at the point in the lecture where the lecturer introduces it — never omitted \
because it is brief, immediately superseded, or seems like a mere transition.

CRITICAL — LONG CONTINUOUS READINGS (AGGADA AND NARRATIVE PASSAGES):
Some stretches of the lecture consist of the lecturer reading a continuous narrative or \
Aggadic passage — a story, a dialogue between named figures, a sustained Midrashic \
account — with comparatively little interspersed explanation, sometimes with all \
commentary held until after a large block has been read straight through. This is exactly \
as much a real Talmudic passage as a tightly-argued halachic exchange, and the same \
no-skipping rule applies to it in full: every beat of the narrative — each statement, \
reply, and turn of the story — must appear in the essay, in the order the lecturer reads \
it, even though it arrives as one long stretch rather than as separate quote-and-comment \
exchanges. Do not compress a multi-part narrative into a summary of its outcome, and do \
not wait to write a section until you reach the lecturer's commentary on it — write the \
narrative itself first, fully, in the section where it is read, whether or not commentary \
follows immediately. A long run of quoted material with little lecturer voice attached is \
a sign to preserve more content in full, not less.

CRITICAL — SECTION ORDERING:
The Gemara frequently refers back to previously cited passages, but the essay must reflect \
the order in which the lecturer actually covers material, not the order in which sources \
first appear in the Talmud. Do NOT move content to an earlier section because it is \
thematically related to something discussed there. Every piece of analysis belongs in the \
section and subsection where the lecturer addresses it in the audio, as determined by the \
segmentation timestamps. If the lecturer revisits a topic from an earlier segment, that \
discussion stays in its current section — do not merge it back into the earlier one.

TRANSCRIPT:

{transcript}"""


def cleanup_prompt(essay: str) -> str:
    return f"""You are processing a Talmudic essay. Your sole task is to convert \
Hebrew/Aramaic translation bridges into HTML comments.

A translation bridge is an italicized transliterated phrase immediately followed by \
an em-dash (—) and its English translation. Examples:
  *Tanu Rabbanan* — the Rabbis taught
  *shlosha lugim* — three log
  *ve-dilma* — perhaps
  *lo shanu ela* — this only applies when

For each translation bridge, make this transformation:
  BEFORE: *phrase* — English translation
  AFTER:  <!-- phrase --> English translation

Remove the italicized phrase and the em-dash; insert an HTML comment containing the \
phrase; keep the English translation unchanged.

Do NOT convert:
- Terms not followed by an em-dash: standalone italicized terms like *Gemara*, \
*baraita*, *mishna*, *korban*, *olah*, or terms under textual analysis \
("the word *kacha* teaches...")
- Anything inside a blockquote (lines starting with >)
- Section headers (lines starting with # or ##)
- A phrase followed by a colon rather than an em-dash (*Tanu Rabbanan*: ...)

When a bridge spans a longer phrase with nested italics or punctuation, convert the \
whole transliterated portion up to the em-dash into the comment.

Return the complete essay with ONLY the translation bridges converted. Do not alter \
any other text, markdown formatting, or structure.

ESSAY:

{essay}"""


def source_insertion_prompt(
    masechta: str,
    daf: int,
    essay: str,
    sefaria_text: str,
    prev_daf_tail=None,  # type: Optional[str]
    next_daf_head=None,  # type: Optional[str]
    amud=None,           # type: Optional[str]
) -> str:
    label = _daf_label(masechta, daf, amud)
    prev_block = ""
    if prev_daf_tail:
        prev_block = f"""
SEFARIA TEXT FOR {masechta.upper()} {daf - 1} (PRECEDING DAF — for context only):

{prev_daf_tail}

---
"""

    next_block = ""
    if next_daf_head:
        next_block = f"""

---

SEFARIA TEXT FOR {masechta.upper()} {daf + 1} (FOLLOWING DAF — for context only):

{next_daf_head}"""

    return f"""Below is a written essay based on a shiur on {label}, followed by \
the Sefaria text for that daf (and, where available, the end of the preceding daf and \
the beginning of the following daf as supplementary context).

Your task is to insert the Sefaria source text after the relevant essay headings, \
then strip all HTML comments from the prose. Work through the four steps below \
internally, as your own private reasoning process — they are not a template for \
your response.

Your response must contain NOTHING but the final document: it starts directly with \
the essay's own first heading line (e.g. "# Avodah Zarah 2 — Daf Yomi Shiur") and \
contains only headings, blockquotes, and essay prose. Do not include the words \
"STEP 1", "STEP 2", "STEP 3", "STEP 4", or any other step label. Do not include any \
analysis, alignment notes, section-by-section commentary, or explanation of your \
reasoning — none of that belongs in the response. If you catch yourself writing a \
sentence that describes what you are about to do rather than being part of the essay \
itself, delete it.

─── STEP 1: ALIGNMENT ───────────────────────────────────────────────────────────

For each section of the essay (## or ### heading), locate anchors in the section body \
in this priority order:
  (a) HTML comments of the form <!-- Hebrew/Aramaic phrase --> — these are the primary \
anchors, placed where the lecturer originally quoted Talmudic text. Use the phrase \
inside the comment to locate the corresponding position in the Sefaria text.
  (b) If no HTML comment is present, look for any inline Hebrew or Aramaic text as a \
fallback anchor.

Key alignment rules:
- Check the PRECEDING DAF context first for the opening section(s). It is common for \
a shiur to begin a few lines before the new daf; if the anchor for the first section \
matches text in the preceding-daf block, use that text.
- Likewise, check the FOLLOWING DAF context for the closing section(s) if the shiur \
appears to run past the end of the current daf.
- The sections cover the text sequentially: where one section's source ends, the next \
section's source begins immediately after it. Do not skip backwards.
- If a section contains no anchor (pure analysis of a previously cited passage), it \
continues from where the previous section left off.
- If a section discusses a passage that appears in none of the three Sefaria blocks \
provided, leave that section without a blockquote.
- Commentary sections (e.g. Tosafot, Rashi, other Rishonim) very often analyze a \
passage that an EARLIER section already quoted — most commonly the Mishnah. That is \
normal and does not mean the section needs, or should be given, a blockquote of its \
own. Never assign such a section text whose real anchor belongs to a LATER section \
just to avoid leaving it without a blockquote — a commentary section discussing \
already-quoted material correctly has no blockquote at all (see the "no new Sefaria \
text" rule below). A section earns a blockquote only when ITS OWN body contains an \
anchor for NEW Sefaria text, or when genuinely-pending text (see below) belongs to it.

─── STEP 2: INSERTION ───────────────────────────────────────────────────────────

For each section where you found an anchor, insert the complete Sefaria passage \
immediately AFTER that section's heading line (## or ###), before the prose body, \
as a markdown blockquote.

What to insert:
- Insert the COMPLETE unit containing the anchor — the entire Mishnah (from \
מַתְנִי׳ / MISHNA to its end), the entire Baraita (from תָּנוּ רַבָּנַן / תַּנְיָא \
to its final word), or the complete Gemara sugya being read (from גְּמָ׳ / GEMARA \
or from the opening statement of the passage). Never truncate mid-sentence or mid-unit.
- Do NOT insert only the specific phrase the lecturer quoted. Insert the full \
surrounding unit as it appears in the Sefaria text.
- NO GAPS: after identifying where the lecture starts and ends in the Sefaria text, \
walk through that stretch continuously. Every segment of Sefaria text between your \
starting point and ending point must appear in exactly one blockquote — including short \
transitional or follow-up lines such as הָוֵי בַּהּ / אִיבַּעְיָא לְהוּ / אָמַר רַב X. \
These lines are new Talmudic statements and must be inserted even when they function as \
a question or reaction to the immediately preceding passage. Before moving from one \
essay section to the next, verify that every Sefaria segment between the end of the \
previous blockquote and the start of the next anchor has been placed in a blockquote. \
If any such segment has not yet been inserted, include it in the current section's \
blockquote before proceeding.
- Only use text that appears verbatim in the Sefaria text provided. \
Never fabricate, paraphrase, or approximate source text.

Section labels: retain מַתְנִי׳ / MISHNA and גְּמָ׳ / GEMARA (and any equivalent \
labels such as מתנ״ or גמ׳) exactly as they appear at the start of a unit in the \
Sefaria text. Do not strip or abbreviate them.

Splitting a Sefaria segment across two essay sections:
The Sefaria text groups multiple sentences into a single numbered segment. When \
such a segment spans the boundary between two essay sections — i.e. the first \
essay section quotes or discusses only the opening sentences, and the next section \
discusses the remainder — split the segment at the natural sentence boundary. \
Insert the first part as the blockquote for the first section and the second part \
as the blockquote for the following section. Do not force the entire segment into \
whichever section happens to contain the later anchor.

Sections with no new Sefaria text — STRICT RULE:
If an essay section contains no anchor that can be located in the Sefaria text \
AND there are no Sefaria segments remaining between the end of the previous \
blockquote and the anchor of the next anchored section, leave the section with \
NO blockquote and NO placeholder of any kind — go directly from the heading \
line to the essay prose. Do NOT insert *[Continued from above]* or any similar \
placeholder. If condition (2) fails — meaning there ARE Sefaria segments that come \
after your last insertion point and before the next real anchor — those segments \
must be inserted here as a blockquote.

CRITICAL CAVEAT before backfilling pending segments into an anchor-less section: \
first check whether the essay's NEXT section (the one that actually has an anchor) \
has its own HTML comment early in its body whose matched Sefaria position is AT or \
NEAR the start of that "pending" stretch. If so, that pending text is what the next \
section is quoting — it belongs there, not here. In that case leave the CURRENT \
(anchor-less) section with no blockquote, and let the next section's blockquote \
begin from the pending text's actual start. Only backfill pending text into the \
current section when the following section's own anchor clearly starts LATER than \
the pending stretch — i.e. when that text genuinely belongs to no other section and \
would otherwise be silently dropped.

CORRECT format for a section with no new Sefaria text and no pending segments:
  ### Section Title
  [full essay prose for this section — never omitted]

CORRECT format for an anchor-less section where pending Sefaria segments exist \
between the last insertion and the next anchor:
  ### Section Title
  > **Hebrew/Aramaic:** [pending Sefaria segments, copied verbatim]
  >
  > **Translation:** [corresponding translation]
  [full essay prose for this section — never omitted]

CRITICAL — DO NOT ALTER ESSAY PROSE: Every sentence from the input essay must appear \
in your output verbatim, with two exceptions only: (1) blockquotes are inserted after \
headings, and (2) HTML comments (<!-- ... -->) are removed in Step 3. No sentence, \
clause, or word of prose may be deleted, shortened, reworded, or moved. If you find \
yourself omitting a paragraph or condensing multiple sentences into one, stop — that \
is an error. The essay prose is fixed input; your only job is to add blockquotes and \
strip comments.

CRITICAL — NEVER DROP OR MERGE A HEADING: every ## and ### heading line in the input \
essay must appear, verbatim and exactly once, in your output — in the same order, \
with nothing merged together. This applies EVEN WHEN a section gets no blockquote of \
its own (a section with no new Sefaria text still keeps its own heading line, \
immediately followed by its own prose — see the "no new Sefaria text" format above). \
A common trap: sometimes several consecutive ## / ### sections all discuss the SAME \
single, indivisible Sefaria segment (the lecturer moved through it slowly across \
several micro-topics, but Sefaria itself has no smaller unit to split it into). In \
that case, insert the blockquote ONCE, under the FIRST such section — but the \
following sections still each keep their own heading line with no blockquote beneath \
it, exactly as if they were ordinary anchor-less commentary sections. Do NOT respond \
to "this text was already quoted above" by deleting the later headings and silently \
concatenating their prose into the first section — that discards real document \
structure and is a serious error, not a minor formatting choice.

FORMAT for each inserted blockquote:
  > **Hebrew/Aramaic:** [full passage, copied exactly from the Sefaria text, \
including any מַתְנִי׳ / גְּמָ׳ label at the start]
  >
  > **Translation:** [English translation from the Sefaria text, including any \
MISHNA / GEMARA label at the start]

CRITICAL — PRESERVE THE SEFARIA TRANSLATION'S EXISTING **BOLD** MARKUP EXACTLY: \
the Sefaria translation text you are copying already contains its own **bold** \
markdown — bold marks the literal Talmudic source words, plain text marks Rashi/ \
commentary interpolations that Sefaria adds for readability. This bold/plain \
distinction already exists character-for-character in the Sefaria text provided to \
you; your job is to copy it through unchanged, exactly like copying any other part \
of the passage verbatim. Do NOT decide for yourself which words look like Talmudic \
text and re-derive the bolding, and do NOT drop the ** markers while transcribing. \
Copy every ** pair from the source Sefaria segment into your blockquote in the same \
position relative to the surrounding words. A translation blockquote with zero \
**bold** spans in it is a strong signal that you dropped this formatting — check \
the corresponding Sefaria segment above and restore it before finishing.

─── STEP 3: COMMENT REMOVAL ─────────────────────────────────────────────────────

After completing all blockquote insertions, scan the entire output and remove every \
HTML comment (<!-- ... -->) from the prose. The final document must contain no HTML \
comments anywhere. Every word of prose (excluding the removed comments) must appear \
in the output unchanged.

─── STEP 4: VERIFICATION ────────────────────────────────────────────────────────

Before finishing, compare the ## and ### heading lines in the ESSAY input below \
against the heading lines in the document you are about to output. Every heading in \
the input must appear in the output, EXACTLY as it is spelled in the input, in the \
same order, with nothing added and nothing removed.

If a heading from the input is missing from your output: you merged it away by \
accident while copying prose. Find that exact point and re-insert that EXACT heading \
line, copied character-for-character from the ESSAY input — never a paraphrase, \
summary, or title of your own composition. Do not add a blockquote beneath a \
restored heading unless it has a genuine anchor of its own.

Do NOT invent, add, or split out any heading that does not appear verbatim in the \
ESSAY input, for any reason — not to organize long content, not to give a name to a \
sub-topic you notice, not to "improve" the structure. The set of headings in your \
output must be exactly the set of headings in the input: same count, same text, same \
order. Nothing more, nothing less.

REMINDER — OUTPUT FORMAT: your response is the final document ONLY. Begin your \
response with the essay's own first heading line. Do not begin your response with \
"STEP 1", a summary of your alignment analysis, or any other preamble.

ESSAY:

{essay}

---
{prev_block}
SEFARIA TEXT FOR {label.upper()}:

{sefaria_text}{next_block}"""
