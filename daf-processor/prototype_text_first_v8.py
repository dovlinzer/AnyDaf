#!/usr/bin/env python3
"""
prototype_text_first_v8.py — PROTOTYPE. Fixes the two defects human review found in v7.

v7 introduced a lateness penalty so a passage is placed where its discussion STARTS rather
than where it best matches. That fixed the "traverse four headers before reaching the text"
problem (confirmed on Berakhot 31b), but review of Gittin 18b found two regressions.

1. OVEREAGER EARLY PLACEMENT — the opening section acquired an unrelated Gemara passage,
   with a ripple effect through the following sections.

   Cause: v7 treated any section scoring >=60% of the best score as "genuinely discusses
   this passage", and used the earliest such section as the point the lateness penalty
   measures from. But content scores cluster tightly — on Gittin 18b the "shelosha gittin
   pesulin" passage scored 0.517 at its correct home (Psulim Gets Kelali) while twelve of
   fifteen sections cleared the 0.310 bar, including the opening framing section at 0.317,
   which shares only generic vocabulary (get, zman). The penalty then dragged the passage
   five sections early. Measured across five dafim, v7's mean placement error was strongly
   NEGATIVE (-2.25 on Hullin 88, -21.87 on Niddah 60) — text systematically arriving before
   the discussion of it, exactly what the reviewer described.

   Fix: EARLY_MATCH_RATIO 0.60 -> 0.85. Only a section scoring within 15% of the best is
   treated as genuinely discussing the passage, which distinguishes real discussion from
   shared vocabulary. Mean placement error moves to roughly zero, and MORE sections receive
   text (Berakhot 31b: 18 -> 23), so grouping improves too.

2. A PASSAGE SPLIT MID-SENTENCE, which v6 did not do.

   Cause: v6's no-mid-sentence-split rule treated ":" as sentence-final. In Talmudic text a
   colon almost always INTRODUCES quoted speech — Gittin 18b segment 35 ends "...amar leih:"
   ("he said to him:") and segment 36 is the reply, "kedai hu Rabbi Shimon lismoch alav
   bish'at ha-dchak". Splitting there orphans the quotation from its speaker. v7 didn't
   create this flaw; its different placement merely exposed it. Corpus-wide, 1.1% of
   segments (99 of 9,137 sampled) end in such a colon.

   Fix: ":" removed from TERMINATORS, so a trailing colon now marks the NEXT segment as a
   continuation and forbids a section boundary between them.

Zero API calls; both completeness invariants asserted before writing.

Usage:
    python prototype_text_first_v8.py output/gittin_18
    python prototype_text_first_v8.py --all --diagnose
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
from prototype_text_first_v6 import starts_new_topic, NEW_TOPIC_BONUS
from srt_parser import parse_srt

# ':' deliberately absent — see defect 2 above. '׃' (sof pasuk) IS terminal.
TERMINATORS = ".!?׃"

EARLY_MATCH_RATIO = 0.85   # within 15% of best = genuinely discusses it (was 0.60 in v7)
LATENESS_TOLERANCE = 3     # sections of lateness that cost nothing
LATENESS_PENALTY = 0.15    # cost per section beyond the tolerance
LATENESS_CAP = 0.45        # maximum total penalty, so it tie-breaks rather than overrides


def is_continuation(pool: list[dict], j: int) -> bool:
    """True if segment j completes a sentence begun in j-1 — including the very common case
    of a speech-introducing colon ("amar leih:") whose quoted reply is the next segment."""
    if j <= 0 or j >= len(pool):
        return False
    prev = strip_nikud(pool[j - 1]["hebrew"]).rstrip()
    return bool(prev) and prev[-1] not in TERMINATORS


def lateness_adjusted_scores(sections, pool, span, boundaries, ts) -> dict:
    scores = pair_scores(sections, pool, span, boundaries, ts)
    for j in span:
        col = [(i, scores.get((i, j), 0.0)) for i in range(len(sections))]
        best = max((v for _, v in col), default=0.0)
        if best <= 0:
            continue
        earliest = min((i for i, v in col if v >= EARLY_MATCH_RATIO * best), default=None)
        if earliest is None:
            continue
        for i, v in col:
            late = i - earliest - LATENESS_TOLERANCE
            if late > 0:
                scores[(i, j)] = v - min(LATENESS_PENALTY * late, LATENESS_CAP)
    return scores


def align_v8(sections, pool, span_start, span_end, boundaries, ts) -> None:
    span = range(span_start, span_end + 1)
    seg_list = [j for j in span if j < len(pool)]
    m, n = len(sections), len(seg_list)
    if m == 0 or n == 0:
        for s in sections:
            s["anchor_index"] = None
        return

    scores = lateness_adjusted_scores(sections, pool, span, boundaries, ts)
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

    if dp[m][n] == NEG:
        from prototype_text_first_v6 import align_constrained
        align_constrained(sections, pool, span_start, span_end, boundaries, ts)
        return

    assigned = [[] for _ in range(m)]
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
    align_v8(sections, pool, span_start, span_end, boundaries, ts)

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
        out = daf_dir / "03_text_first_prototype_v8.md"
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
            print(f"  matched {s['matched']} | span {s['span']} | sections {s['sections']} "
                  f"(anchored {s['anchored']})")
            if "wrote" in s:
                print(f"  completeness verified: {s['emitted_sections']}/{s['sections']} sections, "
                      f"{s['emitted_items']} segments -> {s['wrote']}")


if __name__ == "__main__":
    main()
