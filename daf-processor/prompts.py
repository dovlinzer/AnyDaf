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
copied verbatim — do not rephrase or substitute with the longer `title` field. \
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
- Preserve all halachic analysis, source citations, named opinions, and textual references \
exactly — do not simplify, omit, or reorder arguments
- Retain Hebrew and Aramaic terms in *italicized transliteration* in the essay prose \
(e.g. *shechita*, *basar b'chalav*, *treif*) — do not use Hebrew script inline in the \
prose body, and do not leave transliterations unitalicized. Hebrew script belongs only \
in the Sefaria blockquotes, not in running English text.
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
("it is the 23rd of the Omer"), off-topic side remarks, and repetitive restatements
- Student questions: if a question prompted a substantive explanation, absorb it into the \
prose as a natural transition ("One might ask...," "This raises the question of...," \
"A closer look reveals..."). If an exchange was logistical or tangential, omit it entirely.
- Write in flowing paragraphs. No bullet points or numbered lists.
- Do not add analysis, conclusions, or sourced references that are not present in the \
original transcript.

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
    # Build the optional preceding-context block
    prev_block = ""
    if prev_daf_tail:
        prev_block = f"""
SEFARIA TEXT FOR {masechta.upper()} {daf - 1} (PRECEDING DAF — for context only):

{prev_daf_tail}

---
"""

    # Build the optional following-context block
    next_block = ""
    if next_daf_head:
        next_block = f"""

---

SEFARIA TEXT FOR {masechta.upper()} {daf + 1} (FOLLOWING DAF — for context only):

{next_daf_head}"""

    return f"""Below is a written essay based on a shiur on {label}, followed by \
the Sefaria text for that daf (and, where available, the end of the preceding daf and \
the beginning of the following daf as supplementary context).

Your task is to insert the Sefaria source text after the relevant essay headings. \
Work in two explicit steps.

─── STEP 1: ALIGNMENT ───────────────────────────────────────────────────────────

For each section of the essay (## or ### heading), scan the section body for Hebrew or \
Aramaic text that the lecturer is reading aloud — it typically appears as a Hebrew/\
Aramaic phrase or sentence followed immediately by an English translation. Use those \
Hebrew/Aramaic strings as anchors to locate the exact position of that section within \
the Sefaria text provided.

Key alignment rules:
- Check the PRECEDING DAF context first for the opening section(s). It is common for \
a shiur to begin a few lines before the new daf; if the anchor for the first section \
matches text in the preceding-daf block, use that text.
- Likewise, check the FOLLOWING DAF context for the closing section(s) if the shiur \
appears to run past the end of the current daf.
- The sections cover the text sequentially: where one section's source ends, the next \
section's source begins immediately after it. Do not skip backwards.
- If a section contains no Hebrew/Aramaic anchor (pure analysis of a previously cited \
passage), it continues from where the previous section left off.
- If a section discusses a passage that appears in none of the three Sefaria blocks \
provided, leave that section without a blockquote.

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
a question or reaction to the immediately preceding passage.
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

*[Continued from above]* usage — STRICT RULE:
*[Continued from above]* is a blockquote substitute ONLY. It occupies exactly the \
same position as a > blockquote — between the heading line and the essay prose — \
and signals that no new Sefaria passage begins here. The essay prose that follows \
the heading is ALWAYS preserved in full, whether or not a blockquote or \
*[Continued from above]* precedes it.

Use *[Continued from above]* ONLY when BOTH of the following are true: \
(1) the essay section contains no Hebrew or Aramaic text that can be located in \
the Sefaria text — i.e. the lecturer is doing pure analysis with no new Talmudic \
quotation; AND (2) there are no Sefaria segments remaining between the end of the \
previous blockquote and the anchor of the next anchored section. If condition (2) \
fails — meaning there ARE Sefaria segments that come after your last insertion \
point and before the next real anchor — those segments must be inserted here as a \
blockquote; do not use *[Continued from above]*. \
Additionally, *[Continued from above]* must NEVER appear before the first Sefaria \
blockquote in the document. If the opening section(s) of the essay have no \
Hebrew/Aramaic anchor, leave them with no blockquote and no placeholder — the \
first *[Continued from above]* can only appear after at least one real blockquote \
has already been inserted. If the section body \
contains ANY Hebrew/Aramaic string (even a single short clause like הָוֵי בַּהּ \
רַב עַמְרָם: אַהֵיָיא) that appears in the Sefaria text, that text is a new anchor \
and must get its own blockquote covering from the end of the previous insertion up \
to and including that passage — never collapsed into *[Continued from above]*.

CORRECT format for a section with no new Sefaria text and no pending segments:
  ### Section Title
  *[Continued from above]*
  [full essay prose for this section — never omitted]

CORRECT format for an anchor-less section where pending Sefaria segments exist \
between the last insertion and the next anchor:
  ### Section Title
  > **Hebrew/Aramaic:** [pending Sefaria segments, copied verbatim]
  >
  > **Translation:** [corresponding translation]
  [full essay prose for this section — never omitted]

INCORRECT — prose deleted:
  ### Section Title
  *[Continued from above]*
  [nothing]

INCORRECT — *[Continued from above]* used when pending segments exist:
  ### Section Title
  *[Continued from above]*
  [essay prose]   ← wrong if there are uninserted segments before the next anchor

Do not alter the essay text in any way — only insert blockquotes after headings. \
Every word of prose from the input essay must appear in the output.

FORMAT for each inserted blockquote:
  > **Hebrew/Aramaic:** [full passage, copied exactly from the Sefaria text, \
including any מַתְנִי׳ / גְּמָ׳ label at the start]
  >
  > **Translation:** [English translation from the Sefaria text, with **bold** for \
Talmudic source text and plain text for Rashi/commentary additions, including any \
MISHNA / GEMARA label at the start]

ESSAY:

{essay}

---
{prev_block}
SEFARIA TEXT FOR {label.upper()}:

{sefaria_text}{next_block}"""
