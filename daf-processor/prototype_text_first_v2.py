#!/usr/bin/env python3
"""
prototype_text_first_v2.py — PROTOTYPE ONLY, not wired into the pipeline.

Refines prototype_text_first.py's placement step. That version anchored essay
sections to Sefaria segments via English word-overlap (essay prose vs. Sefaria's
English translation) — imprecise on long narrative dafs where the same names/themes
recur across many segments (Berakhot 31b).

This version instead walks the RAW TRANSCRIPT chronologically and detects, in
Hebrew/Aramaic itself (extracted straight from the SRT's own embedded Hebrew-script
tokens — the transcript already interleaves recognized Hebrew words with their
transliteration), the moment the lecturer has recited enough of the NEXT Sefaria
segment's own words — not just its opening words, which a Rashi/Tosafot partial quote
of the Gemara would also trigger — to count as a genuine full recitation. That gives
a boundary timestamp per Sefaria segment. Essay sections (which already carry their
own timestamps from 01_segmentation.json) are then anchored by which boundary window
their timestamp falls in — a same-language (Hebrew-to-Hebrew), high-precision signal,
sidestepping the cross-content English matching that produced Berakhot 31b's ordering
noise. Content between two full-recitation boundaries (a Rashi/Tosafot discussion that
only partially echoes the Gemara's words) naturally lands as commentary on the
PRECEDING Sefaria segment — the fix for the Sanhedrin 6b Aaron/Chur gap found in v1.

Zero API calls. Backbone and essay text are both copied verbatim (Python slicing) —
never regenerated — so the silent-drop-under-volume bug that hit pass 2 and
fix_pass2_gaps.py's patch() structurally cannot recur here.

Usage:
    python prototype_text_first_v2.py output/hullin_88 [--threshold 0.5]
"""

import argparse
import json
import re
from pathlib import Path

from prototype_text_first import parse_sefaria_full, parse_essay_sections
from srt_parser import parse_srt

HEBREW_WORD_RE = re.compile(r"[֐-׿]+")
_NIKUD_RE = re.compile(r"[֑-ׇֽֿׁׂׅׄ]")
_FINAL_LETTERS = str.maketrans("ךםןףץ", "כמנפצ")

MIN_WORD_LEN = 3          # drop 1-2 letter Hebrew words (prefixes, conjunctions — noise)
DEFAULT_THRESHOLD = 0.5    # fraction of a segment's distinct words needed for a "full" match
LOOKAHEAD = 3              # how many segments ahead to check per SRT entry (lecturer may
                            # read several segments in a row with no intervening commentary)


def normalize_hebrew_word(w: str) -> str:
    w = _NIKUD_RE.sub("", w)
    return w.translate(_FINAL_LETTERS)


def hebrew_word_set(text: str) -> set[str]:
    words = (normalize_hebrew_word(w) for w in HEBREW_WORD_RE.findall(text))
    return {w for w in words if len(w) >= MIN_WORD_LEN}


def srt_seconds(srt_time: str) -> float:
    h, m, rest = srt_time.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def mmss_seconds(mmss: str) -> float:
    parts = mmss.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0.0


def detect_boundaries(srt_entries, sefaria_items: list[dict], search_start: int, search_end: int,
                       threshold: float) -> dict[int, float]:
    """Walk the transcript chronologically; return {sefaria_index: timestamp} marking
    the moment the lecturer's cumulative recitation since the last advance first
    reaches `threshold` coverage of that segment's own distinct Hebrew words."""
    items_by_index = {it["index"]: it for it in sefaria_items}
    word_sets = {i: hebrew_word_set(items_by_index[i]["hebrew"]) for i in range(search_start, search_end + 1)
                 if i in items_by_index}

    boundaries: dict[int, float] = {}
    pointer = None          # last CONFIRMED sefaria index; None = still bootstrapping
    accumulated: set[str] = set()

    for entry in srt_entries:
        t = srt_seconds(entry.start_time)
        accumulated |= hebrew_word_set(entry.text)

        if pointer is None:
            # Bootstrap: which candidate in the search range does the accumulated text
            # best cover so far?
            best_idx, best_cov = None, 0.0
            for i in range(search_start, search_end + 1):
                ws = word_sets.get(i)
                if not ws:
                    continue
                cov = len(accumulated & ws) / len(ws)
                if cov > best_cov:
                    best_idx, best_cov = i, cov
            if best_idx is not None and best_cov >= threshold:
                pointer = best_idx
                boundaries[pointer] = t
                accumulated = set()
        else:
            advanced = True
            while advanced and pointer < search_end:
                advanced = False
                for lookahead in range(1, LOOKAHEAD + 1):
                    candidate = pointer + lookahead
                    ws = word_sets.get(candidate)
                    if not ws:
                        continue
                    cov = len(accumulated & ws) / len(ws)
                    if cov >= threshold:
                        pointer = candidate
                        boundaries[pointer] = t
                        accumulated = set()
                        advanced = True
                        break

    return boundaries


def assign_anchors_by_timestamp(sections: list[dict], boundaries: dict[int, float], daf_dir: Path) -> None:
    """Title-string matching between segmentation display_title (pass 1) and the essay's
    own ## / ### header text (pass 2/3) is unreliable — they're independently generated
    and routinely diverge (documented in AnyDaf/CLAUDE.md as 'Bug 3'). Match positionally
    instead: the i-th macro_segment's timestamp <-> the i-th ## header; within a macro,
    the j-th micro_segment's timestamp <-> the j-th ### header following it."""
    seg = json.loads((daf_dir / "01_segmentation.json").read_text())
    macro_segments = seg.get("macro_segments", [])

    # Group the flat section list into (macro_section, [micro_sections...]) chunks by
    # document order, so each macro's own micros can be counted and aligned independently.
    groups: list[tuple[dict, list[dict]]] = []
    for sec in sections:
        if sec["level"] == 2:
            groups.append((sec, []))
        elif groups:
            groups[-1][1].append(sec)

    ts_for_section: dict[int, float] = {}   # id(section) -> timestamp

    if len(groups) == len(macro_segments):
        for (macro_sec, micro_secs), macro in zip(groups, macro_segments):
            ts_for_section[id(macro_sec)] = mmss_seconds(macro["timestamp"])
            micros = macro.get("micro_segments", [])
            if len(micro_secs) == len(micros):
                for micro_sec, micro in zip(micro_secs, micros):
                    ts_for_section[id(micro_sec)] = mmss_seconds(micro["timestamp"])

    sorted_bounds = sorted(boundaries.items(), key=lambda kv: kv[1])  # [(index, time), ...] by time

    for sec in sections:
        sec_time = ts_for_section.get(id(sec))
        if sec_time is None:
            sec["anchor_index"] = None
            continue
        anchor = None
        for idx, bound_time in sorted_bounds:
            if bound_time <= sec_time:
                anchor = idx
            else:
                break
        sec["anchor_index"] = anchor
        sec["score"] = None


def assemble_complete(sections: list[dict], sefaria_items: list[dict],
                       span_start: int, span_end: int) -> tuple[str, int, int]:
    """Assemble the Sefaria backbone with every essay section spliced in, guaranteeing
    BOTH texts survive completely:

      - every Sefaria segment in [span_start, span_end] is emitted exactly once, in order
      - every essay section is emitted exactly once, in document order

    A section with a confirmed anchor is emitted after that anchor's Gemara text. A section
    with NO anchor (or an anchor already passed) is emitted at the current position — i.e.
    flushed *before* the next Gemara match rather than discarded. This is the rule that
    makes the design complete rather than merely well-ordered: v1/v2's assemble() silently
    dropped unanchored sections, which on an aggadic daf meant losing half the commentary.

    Returns (document, sections_emitted, sefaria_items_emitted) so the caller can assert
    the invariants numerically instead of trusting them."""
    items_by_index = {it["index"]: it for it in sefaria_items}
    out: list[str] = []
    pointer = span_start
    sections_emitted = 0
    items_emitted = 0

    def emit_gemara_through(upto: int) -> None:
        nonlocal pointer, items_emitted
        while pointer <= upto:
            item = items_by_index.get(pointer)
            if item is not None:
                out.append(f"> **Hebrew/Aramaic:** {item['hebrew']}")
                out.append(f"> **Translation:** {item['translation']}")
                out.append("")
                items_emitted += 1
            pointer += 1

    for sec in sections:
        idx = sec["anchor_index"]
        if idx is not None and idx >= pointer:
            emit_gemara_through(idx)
        out.append(sec["heading_line"])
        out.append("")
        out.append(sec["body"])
        out.append("")
        sections_emitted += 1

    emit_gemara_through(span_end)   # trailing Gemara after the last commentary section
    return "\n".join(out), sections_emitted, items_emitted


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    for d in args.dirs:
        daf_dir = Path(d)
        seg = json.loads((daf_dir / "01_segmentation.json").read_text())
        masechta, daf, amud = seg.get("masechta"), seg.get("daf"), seg.get("amud")

        from check_pass2_coverage import find_srt
        srt_path = find_srt(masechta, int(daf), amud)
        if not srt_path:
            print(f"{daf_dir}: SKIP (no SRT found)")
            continue

        sefaria_items = parse_sefaria_full((daf_dir / "sefaria.md").read_text(encoding="utf-8"))
        essay = (daf_dir / "02_rewrite.md").read_text(encoding="utf-8")
        sections = parse_essay_sections(essay)
        entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))

        search_start, search_end = 0, len(sefaria_items) - 1

        boundaries = detect_boundaries(entries, sefaria_items, search_start, search_end, args.threshold)
        assign_anchors_by_timestamp(sections, boundaries, daf_dir)

        span_start = min(boundaries) if boundaries else 0
        span_end = max(boundaries) if boundaries else len(sefaria_items) - 1

        print(f"\n{'=' * 70}\n{daf_dir}  —  {len(boundaries)}/{len(sefaria_items)} Sefaria segments "
              f"matched (threshold={args.threshold}), span [{span_start}, {span_end}]\n{'=' * 70}")
        prev_idx = -1
        for sec in sections:
            idx = sec["anchor_index"]
            flag = ""
            if idx is not None and idx < prev_idx:
                flag = "  <-- OUT OF ORDER"
            if idx is not None:
                prev_idx = idx
            print(f"  [{'##' if sec['level'] == 2 else '###'}] {sec['title'][:55]:55s} -> sefaria #{idx}{flag}")

        assembled, n_sec, n_items = assemble_complete(sections, sefaria_items, span_start, span_end)

        expected_items = sum(1 for i in range(span_start, span_end + 1)
                             if any(it["index"] == i for it in sefaria_items))
        assert n_sec == len(sections), f"section loss: {n_sec} emitted vs {len(sections)} input"
        assert n_items == expected_items, f"sefaria loss: {n_items} emitted vs {expected_items} in span"
        print(f"\n  completeness: {n_sec}/{len(sections)} sections, "
              f"{n_items}/{expected_items} sefaria segments in span — both verified")

        out_path = daf_dir / "03_text_first_prototype_v2.md"
        out_path.write_text(assembled, encoding="utf-8")
        print(f"  Wrote {out_path} ({len(assembled)} chars)")


if __name__ == "__main__":
    main()
