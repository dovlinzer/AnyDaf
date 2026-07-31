#!/usr/bin/env python3
"""
prototype_text_first_v4.py — PROTOTYPE. Sefaria-first assembly, readability fixes.

v3 produced structurally complete documents, but human review of Gittin 18b found two
real readability defects. Both are addressed here; detection/span logic is unchanged
(imported from v3).

1. HEADING ON THE WRONG SIDE OF ITS TEXT.
   v3 emitted: Gemara -> heading -> commentary. The heading therefore landed *between* a
   passage and the discussion of that passage, so a section's opening paragraphs referred
   backwards to Gemara sitting above their own heading — reported as confusing on
   "Circumventing Zman", "Takanah Effectiveness" and "Three-Month Wait".
   v4 emits: heading -> Gemara -> commentary, so the heading scopes the whole unit.
   Side benefit: this is the same shape Approach A produces, which is what
   upload_to_supabase.py's split_final_into_sections() and find_sefaria_indices.py
   expect (blockquote immediately after the heading) — so it also removes the downstream
   parser incompatibility that would otherwise have blocked adoption.

2. ANCHORED TO THE WRONG SIDE OF THE RECITATION.
   v3 anchored a section to the last segment recited *before the section began*. But the
   lecturer characteristically announces a topic, THEN reads the text, THEN explains it —
   so a section's own timestamp precedes the recitation it is about. The result was
   commentary appearing above the text it discussed, and consecutive Gemara segments
   piling up together after several commentary blocks (reported on "Three-Month Wait" and
   the Shmuel sequence).
   v4 anchors each section to the segments recited within its OWN window — from its
   timestamp up to the next section's timestamp — so heading, text and discussion group
   together as one unit.

Still zero API calls, still pure string slicing: both completeness invariants (every
section emitted exactly once, every in-span Sefaria segment emitted exactly once, in
order) are asserted before anything is written.

Usage:
    python prototype_text_first_v4.py output/gittin_18
    python prototype_text_first_v4.py --all --diagnose
"""

import argparse
import json
import re
from pathlib import Path

from prototype_text_first import parse_essay_sections
from prototype_text_first_v2 import mmss_seconds
from prototype_text_first_v3 import (
    MISLABELED, OUTPUT_ROOT, DEFAULT_THRESHOLD,
    build_pool, best_match_times, longest_consistent_run,
)
from check_pass2_coverage import find_srt
from srt_parser import parse_srt


def section_timestamps(sections: list[dict], daf_dir: Path) -> dict[int, float]:
    """id(section) -> timestamp, matched POSITIONALLY against pass 1's segmentation.
    (Title-string matching across independently-generated passes is unreliable — see
    AnyDaf/CLAUDE.md 'Bug 3'.)"""
    seg = json.loads((daf_dir / "01_segmentation.json").read_text(errors="replace"))
    macro_segments = seg.get("macro_segments", [])

    groups: list[tuple[dict, list[dict]]] = []
    for sec in sections:
        if sec["level"] == 2:
            groups.append((sec, []))
        elif groups:
            groups[-1][1].append(sec)

    ts: dict[int, float] = {}
    if len(groups) == len(macro_segments):
        for (macro_sec, micro_secs), macro in zip(groups, macro_segments):
            ts[id(macro_sec)] = mmss_seconds(macro["timestamp"])
            micros = macro.get("micro_segments", [])
            if len(micro_secs) == len(micros):
                for micro_sec, micro in zip(micro_secs, micros):
                    ts[id(micro_sec)] = mmss_seconds(micro["timestamp"])
    return ts


def assign_window_anchors(sections: list[dict], boundaries: dict[int, float],
                           ts: dict[int, float]) -> None:
    """Anchor each section to the LAST segment recited within its own window —
    [own timestamp, next section's timestamp) — rather than the last one recited before
    it started.

    This is the fix for defect 2. The lecturer names a topic before reading its text, so
    'last segment before this section began' systematically resolves one passage too
    early, stranding the commentary above its own source."""
    # Window end for each section = the next section (in document order) that has a
    # timestamp. The final section's window runs to the end of the recording.
    ordered = sorted(boundaries.items(), key=lambda kv: kv[1])
    next_ts: dict[int, float] = {}
    pending: list[dict] = []
    for sec in sections:
        t = ts.get(id(sec))
        if t is not None:
            for p in pending:
                next_ts[id(p)] = t
            pending = []
        pending.append(sec)
    for p in pending:
        next_ts[id(p)] = float("inf")

    for sec in sections:
        t = ts.get(id(sec))
        if t is None:
            sec["anchor_index"] = None
            continue
        window_end = next_ts.get(id(sec), float("inf"))
        anchor = None
        for idx, bt in ordered:
            # Include everything recited up to the END of this section's own window.
            if bt < window_end:
                anchor = idx
            else:
                break
        sec["anchor_index"] = anchor


def assemble_heading_first(sections: list[dict], pool: list[dict],
                            span_start: int, span_end: int) -> tuple[str, int, int]:
    """heading -> its Gemara -> its commentary, for each section in document order.

    Completeness is structural, exactly as in v3: the pointer only moves forward, every
    in-span segment is emitted exactly once, and every section is emitted exactly once.
    Returns (document, sections_emitted, segments_emitted) for numeric assertion."""
    by_index = {it["index"]: it for it in pool}
    out: list[str] = []
    pointer = span_start
    n_sec = n_items = 0

    def emit_gemara_through(upto: int) -> None:
        nonlocal pointer, n_items
        while pointer <= upto:
            item = by_index.get(pointer)
            if item is not None:
                out.append(f"> **Hebrew/Aramaic:** {item['hebrew']}")
                out.append(f"> **Translation:** {item['translation']}")
                out.append("")
                n_items += 1
            pointer += 1

    for sec in sections:
        out.append(sec["heading_line"])
        out.append("")
        idx = sec["anchor_index"]
        if idx is not None and idx >= pointer:
            emit_gemara_through(idx)          # text comes under its own heading
        out.append(sec["body"])
        out.append("")
        n_sec += 1

    emit_gemara_through(span_end)             # any trailing Gemara after the last section
    return "\n".join(out), n_sec, n_items


def process(daf_dir: Path, threshold: float, diagnose: bool) -> dict | None:
    if not all((daf_dir / f).exists() for f in
               ("01_segmentation.json", "02_rewrite.md", "sefaria.md")):
        return None
    try:
        seg = json.loads((daf_dir / "01_segmentation.json").read_text(errors="replace"))
    except Exception:
        return None
    masechta, daf = seg.get("masechta"), seg.get("daf")
    if not masechta or not daf:
        return None
    srt_path = find_srt(masechta, int(daf), seg.get("amud"))
    if not srt_path:
        return None

    pool = build_pool(daf_dir)
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not pool or not entries:
        return None

    kept = longest_consistent_run(best_match_times(entries, pool, threshold))
    boundaries = {idx: t for idx, t, _ in kept}

    essay = (daf_dir / "02_rewrite.md").read_text(encoding="utf-8", errors="replace")
    sections = parse_essay_sections(essay)
    ts = section_timestamps(sections, daf_dir)
    assign_window_anchors(sections, boundaries, ts)

    span_start = min(boundaries) if boundaries else 0
    span_end = max(boundaries) if boundaries else len(pool) - 1

    stats = {
        "daf": daf_dir.name,
        "label": f"{masechta} {daf}{seg.get('amud') or ''}",
        "matched": len(boundaries),
        "span": (span_start, span_end),
        "sections": len(sections),
        "anchored": sum(1 for s in sections if s["anchor_index"] is not None),
    }

    if not diagnose:
        doc, n_sec, n_items = assemble_heading_first(sections, pool, span_start, span_end)
        expected = span_end - span_start + 1
        assert n_sec == len(sections), f"section loss {n_sec}/{len(sections)}"
        assert n_items == expected, f"sefaria loss {n_items}/{expected}"
        out = daf_dir / "03_text_first_prototype_v4.md"
        out.write_text(doc, encoding="utf-8")
        stats.update(wrote=str(out), emitted_sections=n_sec, emitted_items=n_items)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()

    dirs = ([d for d in sorted(OUTPUT_ROOT.iterdir()) if d.name not in MISLABELED]
            if args.all else [Path(d) for d in args.dirs])

    for d in dirs:
        if not d.is_dir():
            continue
        try:
            s = process(d, args.threshold, args.diagnose)
        except AssertionError as e:
            print(f"{d.name}: COMPLETENESS ASSERTION FAILED — {e}")
            continue
        if s and not args.all:
            print(f"\n{s['label']}  ({s['daf']})")
            print(f"  matched {s['matched']} segs | span {s['span']} "
                  f"| sections {s['sections']} (anchored {s['anchored']})")
            if "wrote" in s:
                print(f"  completeness verified: {s['emitted_sections']}/{s['sections']} sections, "
                      f"{s['emitted_items']} segments -> {s['wrote']}")


if __name__ == "__main__":
    main()
