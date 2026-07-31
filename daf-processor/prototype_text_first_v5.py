#!/usr/bin/env python3
"""
prototype_text_first_v5.py — PROTOTYPE. Sefaria-first assembly with DP alignment.

Keeps v4's heading-first emission (heading -> its Gemara -> its commentary) and replaces
v4's timestamp-window anchoring with a proper monotonic sequence alignment.

WHY THE WINDOW RULE WASN'T ENOUGH. v4 anchored each section to the segments recited inside
its own timestamp window. Human review of Gittin 18b found a residual off-by-one: the
"Rav Natan bar Hoshaya / two women" passage landed under "Rav Netinah" when it plainly
belongs to "Two Wives Case", whose commentary discusses exactly that objection. The cause
is a hard precision limit rather than a bug — pass 1 timestamps those two micro-segments
at 14:15 and 14:23, an 8-second window for a whole topic, because pass 1's micro
timestamps are approximate topic markers, not recitation times. No window rule can
resolve an 8-second window covering minutes of material.

THE FIX. Both sequences are monotonic: the essay's sections run in document order and the
Gemara segments run in text order. So assigning segments to sections is a monotonic
partition problem, solved exactly by dynamic programming rather than a greedy scan —
partition the in-span segment sequence into consecutive (possibly empty) blocks, one per
section, maximising total content agreement.

Content agreement is measured English-to-English: an essay section's prose against
Sefaria's own English translation of the segment. v1 tried this as a *global* signal and
scattered badly on long aggadic dafim (Berakhot 31b), where names and themes recur across
dozens of segments. Here it is constrained by the DP's monotonicity plus a timestamp
prior, so it only ever adjudicates between nearby candidates — using each signal where it
is strong and letting the other cover its weakness.

Still zero API calls; still pure string slicing, with both completeness invariants
asserted before writing.

Usage:
    python prototype_text_first_v5.py output/gittin_18
    python prototype_text_first_v5.py --all --diagnose
"""

import argparse
import json
import re
from pathlib import Path

from check_pass2_coverage import STOPWORDS, find_srt, normalize
from prototype_text_first import parse_essay_sections
from prototype_text_first_v3 import (
    MISLABELED, OUTPUT_ROOT, DEFAULT_THRESHOLD,
    build_pool, best_match_times, longest_consistent_run,
)
from prototype_text_first_v4 import assemble_heading_first, section_timestamps
from srt_parser import parse_srt

# A segment's translation carries Sefaria's own interpolated clarifications, so a section
# genuinely discussing it shares distinctive nouns with it. Weight relative to the
# timestamp prior below.
CONTENT_WEIGHT = 1.0
TIME_WEIGHT = 0.35
EMPTY_PENALTY = 0.0   # sections legitimately have no Gemara; do not force assignment


def content_words_en(text: str) -> set[str]:
    """Distinctive English words: drop markdown, stopwords, and short tokens."""
    text = re.sub(r"[*_>#`]", " ", text)
    return {w for w in normalize(text) if w not in STOPWORDS and len(w) > 3}


def pair_scores(sections: list[dict], pool: list[dict], span: range,
                 boundaries: dict[int, float], ts: dict[int, float]) -> dict:
    """score[(section_i, segment_idx)] = how strongly this section discusses this segment."""
    sec_words = [content_words_en(s["title"] + " " + s["body"]) for s in sections]
    seg_words = {i: content_words_en(pool[i]["translation"]) for i in span if i < len(pool)}

    # Timestamp prior: a section whose window contains the segment's recitation gets a
    # bonus. Deliberately a nudge, not a gate — pass 1's windows are unreliable at fine
    # granularity, which is the whole reason content matching is here.
    sec_times = [ts.get(id(s)) for s in sections]
    known = [t for t in sec_times if t is not None]
    span_lo, span_hi = (min(known), max(known)) if known else (0.0, 1.0)

    scores: dict = {}
    for i, sw in enumerate(sec_words):
        t_i = sec_times[i]
        for j in span:
            gw = seg_words.get(j)
            if not gw:
                continue
            overlap = len(sw & gw) / len(gw)
            s = CONTENT_WEIGHT * overlap
            bt = boundaries.get(j)
            if t_i is not None and bt is not None and span_hi > span_lo:
                # Closer in time -> larger bonus, scaled to the daf's own timespan.
                closeness = 1.0 - min(abs(bt - t_i) / (span_hi - span_lo), 1.0)
                s += TIME_WEIGHT * closeness
            scores[(i, j)] = s
    return scores


def align(sections: list[dict], pool: list[dict], span_start: int, span_end: int,
          boundaries: dict[int, float], ts: dict[int, float]) -> None:
    """Assign each in-span segment to exactly one section via monotonic DP, then record
    each section's last segment as its anchor (what assemble_heading_first consumes).

    dp[i][j] = best total score using the first i sections to absorb the first j segments.
    Monotonic by construction, so document order and text order can never disagree."""
    span = range(span_start, span_end + 1)
    seg_list = [j for j in span if j < len(pool)]
    m, n = len(sections), len(seg_list)
    if m == 0 or n == 0:
        for s in sections:
            s["anchor_index"] = None
        return

    scores = pair_scores(sections, pool, span, boundaries, ts)
    NEG = float("-inf")
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0

    for i in range(1, m + 1):
        for j in range(n + 1):
            best, best_k = NEG, j
            # Section i absorbs seg_list[k:j] (empty when k == j).
            for k in range(j + 1):
                if dp[i - 1][k] == NEG:
                    continue
                block = sum(scores.get((i - 1, seg_list[x]), 0.0) for x in range(k, j))
                val = dp[i - 1][k] + block + (EMPTY_PENALTY if k == j else 0.0)
                if val > best:
                    best, best_k = val, k
            dp[i][j] = best
            back[i][j] = best_k

    # Walk the choices back to recover each section's block.
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
    align(sections, pool, span_start, span_end, boundaries, ts)

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
        out = daf_dir / "03_text_first_prototype_v5.md"
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
