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

The worked example in the prompt is outline/example_chagigah_6.json, the hand-built outline
the author approved (2026-09-23). Keep Chagigah 6 out of any test set — it is the answer key.

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
EXAMPLE = HERE / "outline" / "example_chagigah_6.json"
SPRITE = HERE / "outline" / "sprite.svg"      # shared figure/animal symbols the illustrations draw on
STATE_DIR = HERE / "outline"
RESULTS = HERE / "outline" / "results"
TEXTONLY_DIR = HERE / "outline" / "textonly"
PREV_ESSAY_TAIL_CHARS = 6000
EDGE_ITEMS = 4  # Sefaria items taken from the end of the previous amud / start of the next
POLL_INTERVAL = 60

MODEL_TAGS = {"claude-sonnet-5": "sonnet5", "claude-opus-5": "opus5", "claude-opus-5-5": "opus55"}

SYSTEM_PROMPT = """You are building a study outline of one daf of Talmud for the AnyDaf app. The outline's job is to give a learner a bird's-eye view of how the daf's discussion is built: reading only the headings and their one-line gists, a learner should see what the daf discusses, how the parts relate, and where the Gemara goes next. The bullets then fill in each step.

You receive: the shiur's segmentation (the lecture's own section titles, in lecture order), the shiur essay written from the lecture, the tail of the previous daf's essay, and Sefaria's English translation of this daf plus a few lines on either side. Some dafim have no shiur at all; then you receive only the Gemara text (and perhaps the previous daf's essay tail), and you build the whole outline from the text: every bullet is `"source": "gemara"`, and no section carries the "Gemara text only" flag, since the whole outline is.

## Scope
- Outline exactly the lines named under "Lines to outline" in the message. They are set so that consecutive dafim meet with no gap and no overlap (the shiurim run straight through the Gemara, and the boundaries follow them), so start at the first line and end at the last even when that falls mid-exchange; the first section's `text.from` and the last section's `text.to` are those two labels. If the first line picks up an exchange that began earlier, the first section's gist says in a clause what is being discussed ("Continuing the question of whether…"). If a discussion continues past the last line, outline what is here and fill in `continues`. When no lines are named, outline the daf's own two amudim.
- Shiur material that falls outside that scope is left out; mention it in `coverage_notes`.
- Gemara on this daf that the shiur does not discuss is still outlined, from the text alone, with `"flag": "Gemara text only"` on that section. Check the previous daf's essay tail first: the lecturer may have covered it at the end of the previous shiur, in which case use that material and don't flag it.

## Structure: this is the heart of the task
- Build the hierarchy from the logic of the sugya, not from the shiur segmentation. The segmentation is flat and follows the lecture; use it only as a guide to where topics change.
- A top-level section is a self-contained discussion. Its children are the parts of that discussion. Children share the parent's question even when their topics differ: in the example, "The Olah at Mount Sinai" holds the positions of the tanna'im, the working out of those positions, R. Yosi HaGlili's baraita, the realignment of R. Yishmael and the parsing of the verse. They are different topics in one bucket, because they all serve the question of what the olah at Sinai was.
- Nest as deep as the logic requires: often two or three levels, sometimes four. A section with no natural parts has no children; don't invent a single child.
- Anchor every section to the Gemara lines it covers with `"text": {"from": "6a.8", "to": "6a.15"}`, using the bracketed labels on the Sefaria lines you are given (a label from the previous amud, such as "5b.24", is fine when the section starts there). A parent's range spans its children's. Ranges follow the Gemara's order; a section that `returns_to` an earlier one still anchors to where it falls in the text. The app uses these anchors to scroll the Gemara text in step with the outline, so they must be exact.
- Keep the Gemara's order. Never move a section. When the Gemara returns to an earlier point, leave the section where it falls and add a `returns_to` link to the earlier section's id, with a short note.
- There will be judgment calls. Make the call, and record in `judgment_calls` each place where a different structure would also be reasonable, saying briefly what the alternative was and why you chose as you did.

## Headings and gists
- Write your own headings, never generic ("The Gemara's Question", "Continued"). The segmentation's `title` fields are raw material only, and they contain errors.
- A heading is a small summary in itself: it names the options, positions or issues the section lays out, not only its topic. "*Bitzua*: Sin, Mitzvah, or a Window That Closes" and "'*Lo Taguru*': Fear, Recusal and Speech in Court" tell the learner what the section holds; "Compromise in Court" does not. When a section turns on a key term, put the term in the heading. Up to about 12 words and no more than three or four items; "Term: A, B or C" works well, and so does a question the section answers ("The Olah at Sinai: *Re'iyah* or *Tamid*?"). The example's headings show the style.
- A section that opens a new Mishnah says so: its heading starts with "Mishnah:" ("Mishnah: Pulling, Measuring, Renting the Spot, and Lifting Flax"), so the learner sees where each Mishnah begins.
- Every section gets a `gist`: one sentence, readable on its own. Headings plus gists together form the outline's "headlines" view, so they must carry the flow by themselves. A section with several substantial children names its main sub-discussions in its gist ("Three questions: whether the gentile must have seen blood, unequal loss, and attributing a stain to a woman who has one"), so the headlines view shows them even when they sit a level down.

## Bullets
- Each bullet is one step of the discussion: who says what, and on what basis (a verse, a baraita, a sevara).
- `detail`: 2 for the main steps (the standard view); 3 for supporting detail (proof texts, secondary steps, fine points) shown only in the detailed view. Standard view should read as a complete, compact account.
- `source`: "gemara" for what the text itself says, grounded in the Sefaria translation; "shiur" for the lecturer's analysis, including rishonim and acharonim brought in the shiur and conceptual framing. Never present shiur analysis as the Gemara's. Never state Gemara content that isn't in the provided text.
- Mark Hebrew and Aramaic terms in *italics* with single asterisks, as the example does. No other markup.
- Rulings are "permitted" and "forbidden", never "prohibited": "Prohibited" and "Permitted" look alike at a glance. The same in charts and pictures.
- Name the Gemara's moves precisely, not in the Sefaria translation's wording: a *kushya* or *meitivei* is a challenge or objection; a *ba'ya* is a question. Almost never write "dilemma": keep it for a real choice between two equally weighty options.

## Hebrew and Aramaic words: key terms in the original
Anything that merits a key-term entry (see "Key terms"), and any legal category, principle or technical term of that kind, is written in the original, transliterated and in italics, every time it comes up: headings, gists, bullets, charts and picture labels (*garuf ve'katum*, *chazarah*, *mitztamek ve'ra lo*, *kinyan chatzer*, *ona'ah*). The first time a term appears on the daf, give its English once in parentheses right after it, e.g. *gerufah u'ketumah* (swept of coals or banked with ashes); after that use the term alone. Never write a key term's English translation in its place ("swept", "returning", "shrivels and deteriorates"), and never let the English stand in for it in later bullets: the glossary links the term, and its English is only a gloss. Ordinary things that are not terms of art stay in English: "one kind", not *min echad*; "wax", not *sha'avah*. Never use both names for one thing, least of all in one heading ("*Min Echad* or Two Kinds?").

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
- Orientation, always: the parties go on the rows (tanna'im, amora'im, schools, versions of a tradition such as "R. Meir's version"), and the cases, questions or aspects being compared go on the columns. Beit Shammai and Beit Hillel are two rows; "left on a swept stove" and "taken off on Shabbat" are two columns. When the grid compares things rather than people (the three pilgrimage offerings and what is unique to each), the things are the rows.
- `columns` is the header row; each entry in `rows` is a list of cell strings with the row label first. An empty first header cell is fine.
- `tones` marks what each cell rules, so the app can color it: the same shape as `rows`, one entry per cell, `"ok"` for a cell that permits, validates or says something takes effect (permitted, may be eaten, acquires, betrothed, valid), `"no"` for one that forbids, invalidates or fails (forbidden, may not, does not acquire, not betrothed, invalid), and `null` for everything else, including the row label, a cell that says both, and cells about liability or exemption (whether those are the good outcome depends on the case). Judge by what the cell means, not its wording: "Beit Hillel permit leaving the food" is `"ok"`, "Concern that he may sin" is `null`. Leave `tones` out of a chart with no rulings in it.

## Illustrations
Visual learners get 4 to 7 illustrations per daf, scaled to the daf: more for a long daf with several major disputes or many physical cases, fewer for a short or mostly aggadic one. Each is a flat, labeled SVG drawing attached to the section it illustrates, as `"illustration": {"caption", "svg"}`. Their purpose is to visualize the discussion, not to decorate it.

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
Rules:
- Every label is exact text: names as the text has them, a Hebrew or Aramaic key phrase where it helps (as in the example), nothing the outline doesn't support. Never depict God.
- Pictures read left to right, since the page is in English: a sequence, a list, or a set of items being compared runs left to right in the order the text gives it (the Mishnah's oven, *kupach* and stove, in that order). A picture of a real physical layout (the Temple, a courtyard, directions) follows the real arrangement and labels the directions instead. Give each Hebrew `<text>` element `direction="rtl"`.
- Draw with simple shapes plus the shared figure library below, which the page already contains: reference symbols with `<use href="#id" x y width height/>` and never redefine them. Sages are `#sage`, colored per figure with `style="color:<robe>;--beard:<color>;--wrap:<head-cloth>"`, drawn at width w and height 1.75w. They stand plainly: no waving, no tallit or tzitzit, no modern dress.
- `viewBox="0 0 900 H"` with H between 380 and 560. Start with a full-size background rect. Use the example's palette of soft panel colors, its font families (Newsreader for titles, Public Sans for labels, Frank Ruhl Libre for Hebrew) and minimum text size 12. Keep every element inside the viewBox. No text may run over a drawing, a figure or another label: place labels in open space, and where room is short, break the label onto two lines, shorten it, or move or shrink the drawing to make room. Before finishing each picture, check every label's extent against what lies beneath it.
- Give the root `<svg>` `role="img"` and a `<title>` describing the scene. No scripts, no external images or links, no `<style>` blocks, no ids that could collide with the library's.
- Show rulings in color, the same way every time, because it makes a big difference for visual learners: whatever the picture marks as permitted is green (text `#24592E`, or `#mark-ok` beside it), whatever it marks as forbidden is red (text `#8C2F2F`, or `#mark-no`). Use the marks wherever a case in the picture has a ruling. Only rulings get these colors.
- The caption is one or two sentences saying what the picture shows and where it comes from in the text.

{KEY_TERMS}

## Output
Return only a JSON object, with no prose before or after it and no code fence, in exactly the shape of the example:
{"daf", "scope": {"start", "end"}, "sections": [node], "key_terms": [term], "judgment_calls": [string], "coverage_notes": [string], "runners_up": {"charts": [{"section", "subject", "why_not"}], "illustrations": [{"section", "subject", "why_not"}]}}
node = {"id": "s1", "title", "amud", "text": {"from", "to"}, "gist", "flag"?, "bullets": [{"text", "detail": 2|3, "source": "gemara"|"shiur"}], "chart"?: {"caption", "columns": [string], "rows": [[string]], "tones"?: [["ok"|"no"|null]]}, "illustration"?: {"caption", "svg"}, "returns_to"?: [{"id", "note"}], "continues"?: string, "children": [node]}
term = {"term", "hebrew", "sense", "definition", "on_this_daf", "aliases": [string], "sections": [id]}
Ids are unique across the whole outline ("s1", "s2", ... in document order). `amud` is a short label such as "6a", "6a–6b" or "6b → 7a". `judgment_calls`, `coverage_notes` and `runners_up` are editorial notes for the author, never shown to learners.
Before you finish, check every chart once more: parties (tanna'im, amora'im, schools, versions) on the rows, cases or aspects on the columns. A column headed with a sage's name is almost always the wrong way round.

## Figure library (already on the page; reference these ids, never redefine them)
{LIBRARY}

## Worked example: Chagigah 6, approved by the author as the model
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
    parts.append("Now produce the outline JSON for this daf.")
    return "\n\n".join(parts)


EXCEPTIONS = HERE / "outline" / "transliteration_exceptions.json"
KEY_TERMS_EXAMPLE = HERE / "outline" / "key_terms_example_chagigah_6.json"
# Editorial runners-up for the worked example (never shown to learners).
EXAMPLE_RUNNERS_UP = {
    "charts": [
        {"section": "s1", "subject": "The lame and the blind child under each school",
         "why_not": "Two cases and one principle (Abaye's rule); the bullets carry it without a grid."},
        {"section": "s9", "subject": "The two readings of Shemot 24:5",
         "why_not": "One question with two readings and no further dimensions; a chart would repeat the bullets."},
    ],
    "illustrations": [
        {"section": "s10", "subject": "The five mitzvot with no fixed measure",
         "why_not": "A list of mitzvot, not a scene or a comparison; nothing to picture."},
    ],
}


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
    ex = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    ex["key_terms"] = json.loads(KEY_TERMS_EXAMPLE.read_text(encoding="utf-8"))["key_terms"]
    ex["runners_up"] = EXAMPLE_RUNNERS_UP
    return json.dumps(ex, ensure_ascii=False, indent=1)


def system_blocks() -> list[dict]:
    library = SPRITE.read_text(encoding="utf-8")
    text = (SYSTEM_PROMPT.replace("{LIBRARY}", library).replace("{EXCEPTIONS}", exceptions_text())
            .replace("{KEY_TERMS}", key_terms_section()))
    # One cached block: instructions + library + example are identical across every request.
    return [{"type": "text", "text": text + example_text(), "cache_control": {"type": "ephemeral"}}]


def run_tag(model: str, effort: str | None) -> str:
    """Result tag: 'opus55', or 'opus55_medium' when comparing effort levels."""
    return MODEL_TAGS[model] + (f"_{effort}" if effort else "")


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


# A column header that starts with a sage's name or title ("R. Yannai", "Abba Kohen Bardela", "Rav
# Sheshet's reading"). Deliberately broad: it only raises a flag for review.
SAGE_HEADER = re.compile(r"^(?:R\.\s|Rav\b|Rabbi\b|Rabban\b|Rabbeinu\b|Beit\s|Abba\b|Abaye\b|Rava\b|Rabba\b|"
                         r"Shmuel\b|Ulla\b|Reish\b|Resh\b|Rabbanan\b|Chachamim\b|Tanna\b|Ravina\b|Rebbi\b)")


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
    for n in nodes:
        cols = (n.get("chart") or {}).get("columns") or []
        sages = [c for c in cols[1:] if SAGE_HEADER.match(str(c).strip("*' "))]
        if sages:
            probs.append(f"chart in '{n.get('title')}' has sages as column headers {sages}: check the orientation")
        ch = n.get("chart") or {}
        if ch.get("tones") is not None:
            rows, tones = ch.get("rows") or [], ch.get("tones") or []
            if len(tones) != len(rows) or any(len(t or []) != len(r) for t, r in zip(tones, rows)) or \
               any(x not in ("ok", "no", None) for t in tones for x in (t or [])):
                probs.append(f"chart in '{n.get('title')}': tones don't match the rows (shape or values)")
    pics = sum(1 for n in nodes if n.get("illustration"))
    if not 4 <= pics <= 7:
        probs.append(f"{pics} illustrations (target 4-7)")
    if outline.get("key_terms") is not None:
        probs += [f"key term: {p}" for p in check_terms(outline, outline, d) if "may be fine" not in p]
    text = json.dumps({k: v for k, v in outline.items() if k not in ("judgment_calls", "coverage_notes", "runners_up")},
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for spec in args.dafim:
        key, d, textonly = parse_spec(spec)
        if not (d / "sefaria.md").exists():
            sys.exit(f"no sefaria.md for {spec} (looked in {d})")
        if d.name == "chagigah_6":
            sys.exit("chagigah_6 is the worked example; leave it out of the run")

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
