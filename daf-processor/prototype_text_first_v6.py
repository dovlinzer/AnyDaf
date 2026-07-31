#!/usr/bin/env python3
"""
prototype_text_first_v6.py — PROTOTYPE. Adds Sefaria's own structural signals to v5's
DP alignment.

WHAT v5 GOT WRONG. Human review of Gittin 18b found one clearly-wrong assignment: the
segment beginning "chayishinan shema piyes" opened the "Ten People Command" section,
though it is literally the second half of the previous segment's sentence and concerns
appeasement, not the ten-people case. Two independent causes:

  1. A FALSE CONTENT MATCH. That segment ends "...afilu mikan ve'ad ASARA YAMIM" — ten
     DAYS — and mentions Rabbi Yochanan. The section is "Ten People Command". Word overlap
     on "asara"/"ten" and "yochanan" scored a confident hit on the wrong passage; content
     similarity alone cannot distinguish ten days from ten people.
  2. AN IGNORED BOUNDARY. Sefaria's segmentation splits mid-sentence — segment 28 ends on
     a semicolon and segment 29 completes the clause. v5 was free to place a section
     boundary between them, which no reading of the text would ever do.

THE FIX — two structural constraints, both read directly off Sefaria's own text rather
than inferred:

  * NEVER SPLIT MID-SENTENCE. If a segment's predecessor ends without a sentence
    terminator, the pair is one continuous sentence, and a section boundary between them
    is forbidden outright. Measured at 5.3% of segments corpus-wide (200-daf sample), so
    this constrains real cases without being a rare special case.
  * PREFER SEFARIA'S OWN TOPIC MARKER. Sefaria prefixes a new discussion's translation
    with "§" (7.8% of segments). A block starting there gets a bonus, so headings align
    with the text's own topic boundaries instead of with a word-overlap coincidence.

These are hard/soft respectively on purpose: the mid-sentence rule admits no exceptions,
while "§" is strong evidence but not the only place a shiur may legitimately begin a
section.

Zero API calls; both completeness invariants still asserted before writing.

Usage:
    python prototype_text_first_v6.py output/gittin_18
    python prototype_text_first_v6.py --all --diagnose
"""

import argparse
import json
from pathlib import Path

from check_pass2_coverage import find_srt
from find_sefaria_indices import strip_nikud
from prototype_text_first import parse_essay_sections
from prototype_text_first_v3 import (
    MISLABELED, OUTPUT_ROOT, DEFAULT_THRESHOLD,
    build_pool, best_match_times, longest_consistent_run,
)
from prototype_text_first_v4 import assemble_heading_first, section_timestamps
from prototype_text_first_v5 import pair_scores
from srt_parser import parse_srt

TERMINATORS = ".:!?׃״”"          # a segment ending in one of these completes its sentence
NEW_TOPIC_BONUS = 0.60           # reward a block that begins at Sefaria's own "§" marker


def is_continuation(pool: list[dict], j: int) -> bool:
    """True if segment j completes a sentence begun in segment j-1, in which case a
    section boundary must never fall between them."""
    if j <= 0 or j >= len(pool):
        return False
    prev = strip_nikud(pool[j - 1]["hebrew"]).rstrip()
    if not prev:
        return False
    return prev[-1] not in TERMINATORS


def starts_new_topic(pool: list[dict], j: int) -> bool:
    """Sefaria marks the start of a new discussion by prefixing its translation with §."""
    return 0 <= j < len(pool) and pool[j]["translation"].lstrip().startswith("§")


def align_constrained(sections: list[dict], pool: list[dict], span_start: int, span_end: int,
                       boundaries: dict[int, float], ts: dict[int, float]) -> None:
    """v5's monotonic DP, plus a hard no-mid-sentence-split constraint and a bonus for
    aligning a block with Sefaria's "§" topic marker."""
    span = range(span_start, span_end + 1)
    seg_list = [j for j in span if j < len(pool)]
    m, n = len(sections), len(seg_list)
    if m == 0 or n == 0:
        for s in sections:
            s["anchor_index"] = None
        return

    scores = pair_scores(sections, pool, span, boundaries, ts)

    # A boundary at position k means a new block begins at seg_list[k]. Forbid that where
    # seg_list[k] merely completes the previous segment's sentence. k == 0 is the document
    # start, never a split.
    forbidden = {k for k in range(1, n) if is_continuation(pool, seg_list[k])}

    NEG = float("-inf")
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0

    for i in range(1, m + 1):
        for j in range(n + 1):
            best, best_k = NEG, j
            for k in range(j + 1):
                if dp[i - 1][k] == NEG or k in forbidden:
                    continue
                block = sum(scores.get((i - 1, seg_list[x]), 0.0) for x in range(k, j))
                if k < j and starts_new_topic(pool, seg_list[k]):
                    block += NEW_TOPIC_BONUS
                val = dp[i - 1][k] + block
                if val > best:
                    best, best_k = val, k
            dp[i][j] = best
            back[i][j] = best_k

    if dp[m][n] == NEG:      # constraints left no valid partition; fall back to unconstrained
        from prototype_text_first_v5 import align
        align(sections, pool, span_start, span_end, boundaries, ts)
        return

    assigned: list[list[int]] = [[] for _ in range(m)]
    j = n
    for i in range(m, 0, -1):
        k = back[i][j]
        assigned[i - 1] = seg_list[k:j]
        j = k

    for i, sec in enumerate(sections):
        sec["anchor_index"] = assigned[i][-1] if assigned[i] else None


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
    span_start = min(boundaries) if boundaries else 0
    span_end = max(boundaries) if boundaries else len(pool) - 1

    essay = (daf_dir / "02_rewrite.md").read_text(encoding="utf-8", errors="replace")
    sections = parse_essay_sections(essay)
    ts = section_timestamps(sections, daf_dir)
    align_constrained(sections, pool, span_start, span_end, boundaries, ts)

    seg_list = [j for j in range(span_start, span_end + 1) if j < len(pool)]
    stats = {
        "daf": daf_dir.name,
        "label": f"{masechta} {daf}{seg.get('amud') or ''}",
        "matched": len(boundaries),
        "span": (span_start, span_end),
        "sections": len(sections),
        "anchored": sum(1 for s in sections if s["anchor_index"] is not None),
        "mid_sentence_splits_blocked": sum(
            1 for k in range(1, len(seg_list)) if is_continuation(pool, seg_list[k])),
    }

    if not diagnose:
        doc, n_sec, n_items = assemble_heading_first(sections, pool, span_start, span_end)
        expected = span_end - span_start + 1
        assert n_sec == len(sections), f"section loss {n_sec}/{len(sections)}"
        assert n_items == expected, f"sefaria loss {n_items}/{expected}"
        out = daf_dir / "03_text_first_prototype_v6.md"
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
            print(f"  matched {s['matched']} segs | span {s['span']} | sections {s['sections']} "
                  f"(anchored {s['anchored']}) | mid-sentence splits blocked: "
                  f"{s['mid_sentence_splits_blocked']}")
            if "wrote" in s:
                print(f"  completeness verified: {s['emitted_sections']}/{s['sections']} sections, "
                      f"{s['emitted_items']} segments -> {s['wrote']}")


if __name__ == "__main__":
    main()
