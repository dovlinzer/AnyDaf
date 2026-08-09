#!/usr/bin/env python3
"""
prototype_text_first.py — PROTOTYPE ONLY, not wired into the pipeline.

Tests an inverted pass-3 design: instead of inserting Sefaria blockquotes into the
essay (current design — essay is the backbone, vulnerable to whatever pass 2 dropped
or the essay itself silently drops under a heavy patch), assemble the Sefaria text as
the backbone (copied verbatim from sefaria.md, zero LLM involvement, so it cannot be
dropped or misplaced) and splice the essay's own commentary sections into it at the
point each one discusses.

Deliberately zero API calls: placement is decided by free local word-overlap matching
between each essay section's body text and each Sefaria segment's English translation
(same content-word/phonetic-key technique already validated this session in
check_pass2_coverage.py, just pointed in the other direction). The backbone and the
essay commentary are both copied verbatim by Python string slicing — never
regenerated — so this cannot reproduce the "silent drop under volume" bug that hit
both pass 2 and fix_pass2_gaps.py's patch().

Usage:
    python prototype_text_first.py output/hullin_88
"""

import argparse
import re
import sys
from pathlib import Path

from check_pass2_coverage import content_words, normalize, phonetic_key

ITEM_RE = re.compile(
    r'\*Hebrew/Aramaic:\*[ \t]*(.+?)\n\*Translation:\*[ \t]*(.*?)(?=\n\n\*\*\d|\Z)',
    re.DOTALL,
)
# NOTE: translation group is (.*?) (zero-or-more), not (.+?) -- some Sefaria items
# (e.g. the chapter-closing "Hadran" formula) genuinely have no English translation.
# With \s* (which also matches newlines) after each label and a one-or-more translation
# group, an empty translation forced the lazy match to consume forward past the blank
# line into the ENTIRE next item (its "**N.**" label, Hebrew, and real translation) in
# search of the next "\n\n**" boundary -- silently merging two pool items into one
# garbage-translation entry and making the swallowed item's own Hebrew unmatchable as
# a standalone quote. Found on Meilah 8 (found 2026-08-07): the Hadran line swallowed
# the actual Chatas Ha'of Mishna text, producing a visibly broken blockquote in the
# final essay. [ \t]* (not \s*) keeps each label's own line separate from the next, and
# (.*?) lets an empty translation match zero characters instead of forcing a search
# past the boundary. Confirmed corpus-wide: 416 sefaria*.md files / 420 items hit the
# empty-translation case that triggered this.


def parse_sefaria_full(text: str) -> list[dict]:
    """Flat list of {index, amud, hebrew, translation}, 0-based across both amudim —
    same global indexing scheme as find_sefaria_indices.py's a_count convention."""
    parts = re.split(r'\n---\n', text, maxsplit=1)

    def extract(section: str) -> list[tuple[str, str]]:
        return [(m.group(1).strip(), m.group(2).strip()) for m in ITEM_RE.finditer(section)]

    a_items = extract(parts[0])
    b_items = extract(parts[1]) if len(parts) > 1 else []
    items = []
    for i, (heb, trans) in enumerate(a_items):
        items.append({"index": i, "amud": "a", "hebrew": heb, "translation": trans})
    for i, (heb, trans) in enumerate(b_items):
        items.append({"index": len(a_items) + i, "amud": "b", "hebrew": heb, "translation": trans})
    return items


def parse_essay_sections(essay: str) -> list[dict]:
    """Flat, document-order list of ## and ### sections with their own body text
    (text up to the next heading of any level)."""
    heading_re = re.compile(r'^(#{2,3}) (.+)$', re.MULTILINE)
    matches = list(heading_re.finditer(essay))
    sections = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(essay)
        body = essay[m.end():end].strip()
        sections.append({
            "level": level, "title": title, "body": body,
            "heading_line": m.group(0),
        })
    return sections


def _word_set_and_phonetic(words: list[str]) -> tuple[set, set]:
    return set(words), {phonetic_key(w) for w in words}


def score_overlap(section_words: set, section_phonetic: set, translation: str) -> int:
    trans_words = content_words(normalize(translation))
    trans_word_set = set(trans_words)
    trans_phonetic = {phonetic_key(w) for w in trans_words}
    exact = section_words & trans_word_set
    phon = {w for w in section_words if phonetic_key(w) in trans_phonetic}
    return len(exact | phon)


def assign_anchors(sections: list[dict], sefaria_items: list[dict]) -> None:
    """Mutates each section in place, adding 'anchor_index' (best-matching Sefaria
    index, or None if no section text / no signal) and 'score'."""
    for sec in sections:
        words = content_words(normalize(sec["title"] + " " + sec["body"]))
        if not words:
            sec["anchor_index"] = None
            sec["score"] = 0
            continue
        word_set, _ = _word_set_and_phonetic(words)
        best_idx, best_score = None, 0
        for item in sefaria_items:
            s = score_overlap(word_set, None, item["translation"])
            if s > best_score:
                best_idx, best_score = item["index"], s
        sec["anchor_index"] = best_idx
        sec["score"] = best_score


def detect_span(sections: list[dict], sefaria_items: list[dict]) -> tuple[int, int]:
    """Trim to the range of Sefaria indices actually anchored by some section — the
    'simple pass' the architecture calls for, done here via the same overlap matching
    rather than a separate LLM call."""
    anchored = [s["anchor_index"] for s in sections if s["anchor_index"] is not None]
    if not anchored:
        return 0, len(sefaria_items) - 1
    return min(anchored), max(anchored)


def assemble(sections: list[dict], sefaria_items: list[dict], start: int, end: int) -> str:
    by_index: dict[int, list[dict]] = {}
    for sec in sections:
        if sec["anchor_index"] is None:
            continue
        by_index.setdefault(sec["anchor_index"], []).append(sec)

    out = []
    items_by_index = {it["index"]: it for it in sefaria_items}
    for i in range(start, end + 1):
        item = items_by_index.get(i)
        if item is None:
            continue
        out.append(f"> **Hebrew/Aramaic:** {item['hebrew']}")
        out.append(f"> **Translation:** {item['translation']}")
        out.append("")
        for sec in by_index.get(i, []):
            out.append(sec["heading_line"])
            out.append("")
            out.append(sec["body"])
            out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+")
    args = parser.parse_args()

    for d in args.dirs:
        daf_dir = Path(d)
        sefaria_path = daf_dir / "sefaria.md"
        rewrite_path = daf_dir / "02_rewrite.md"
        if not sefaria_path.exists() or not rewrite_path.exists():
            print(f"{daf_dir}: SKIP (missing sefaria.md or 02_rewrite.md)")
            continue

        sefaria_items = parse_sefaria_full(sefaria_path.read_text(encoding="utf-8"))
        essay = rewrite_path.read_text(encoding="utf-8")
        sections = parse_essay_sections(essay)
        assign_anchors(sections, sefaria_items)
        start, end = detect_span(sections, sefaria_items)

        print(f"\n{'=' * 70}\n{daf_dir}  —  {len(sections)} essay sections, "
              f"{len(sefaria_items)} Sefaria segments, span [{start}, {end}]\n{'=' * 70}")
        prev_idx = -1
        for sec in sections:
            idx = sec["anchor_index"]
            flag = ""
            if idx is not None and idx < prev_idx:
                flag = "  <-- OUT OF ORDER vs previous section"
            if idx is not None:
                prev_idx = idx
            print(f"  [{'##' if sec['level'] == 2 else '###'}] {sec['title'][:55]:55s} "
                  f"-> sefaria #{idx} (score={sec['score']}){flag}")

        assembled = assemble(sections, sefaria_items, start, end)
        out_path = daf_dir / "03_text_first_prototype.md"
        out_path.write_text(assembled, encoding="utf-8")
        print(f"\nWrote {out_path} ({len(assembled)} chars)")


if __name__ == "__main__":
    main()
