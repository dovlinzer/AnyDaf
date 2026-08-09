#!/usr/bin/env python3
"""FLAG ONLY, zero API cost -- diagnostic for the Gittin-18-class issue: does
fix_wall_of_text.py's prose insertion perturb align_constrained's placement DP for
NEARBY items, not just the section it directly patches? Pool/matching/boundaries are
byte-identical between plain and wall-patched runs (only essay prose differs), so any
difference in which heading an item lands under is attributable to the patch's prose
change shifting pair_scores' word-overlap term.

Runs align_constrained's own DP twice per daf (plain essay vs wall-patched essay) and
diffs the resulting item->heading assignment. No files are modified."""
import json
from pathlib import Path

from prototype_text_first import parse_essay_sections
from prototype_text_first_v3 import build_pool, best_match_times, DEFAULT_THRESHOLD
from prototype_text_first_v4 import section_timestamps
from prototype_text_first_v5 import pair_scores
from prototype_text_first_v10 import (
    guarded_consistent_run, extend_head_to_confident_neighbor,
    is_continuation, starts_new_topic, NEW_TOPIC_BONUS,
    rescue_homeless_singletons,
)
from check_pass2_coverage import find_srt
from srt_parser import parse_srt

HERE = Path(__file__).parent

DAFIM = ["bava_batra_103", "bava_batra_153", "bava_batra_174", "bava_batra_84",
         "bava_metzia_11", "berakhot_31b", "gittin_18", "hullin_88", "nazir_59",
         "niddah_60", "niddah_67", "yevamot_33"]  # zevachim_29 excluded -- no wallpatched variant


def align_and_get_assignment(sections, pool, span_start, span_end, boundaries, ts):
    """Copy of align_constrained's DP that also RETURNS assigned (section_idx -> pool
    item indices), which the shipped function computes internally but discards after
    setting anchor_index."""
    span = range(span_start, span_end + 1)
    seg_list = [j for j in span if j < len(pool)]
    m, n = len(sections), len(seg_list)
    if m == 0 or n == 0:
        return {}

    scores = pair_scores(sections, pool, span, boundaries, ts)
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
        return None  # unconstrained fallback path -- skip, too different a code path to diff cleanly

    assigned = [[] for _ in range(m)]
    j = n
    for i in range(m, 0, -1):
        k = back[i][j]
        assigned[i - 1] = seg_list[k:j]
        j = k
    rescue_homeless_singletons(sections, assigned, scores)

    item_to_heading = {}
    for i, a in enumerate(assigned):
        for idx in a:
            item_to_heading[idx] = sections[i]["title"]
    return item_to_heading


def run_one(daf: str):
    d = HERE / "output" / daf
    seg = json.loads((d / "01_segmentation.json").read_text(errors="replace"))
    masechta, daf_num = seg.get("masechta"), seg.get("daf")
    srt_path = find_srt(masechta, int(daf_num), seg.get("amud"))
    if not srt_path:
        return None

    pool = build_pool(d)
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    raw_all = best_match_times(entries, pool, 0.0)
    raw_all_by_idx = {i: (t, s) for i, t, s in raw_all}
    raw = [m for m in raw_all if m[2] >= DEFAULT_THRESHOLD]
    kept = guarded_consistent_run(raw)
    kept = extend_head_to_confident_neighbor(kept, raw_all_by_idx)
    boundaries = {idx: t for idx, t, _ in kept}
    span_start = min(boundaries) if boundaries else 0
    span_end = max(boundaries) if boundaries else len(pool) - 1

    results = {}
    for label, essay_file in [("plain", "02_rewrite.md"), ("wallpatched", "02_rewrite_wall_patched.md")]:
        essay_path = d / essay_file
        if not essay_path.exists():
            return None
        essay = essay_path.read_text(encoding="utf-8", errors="replace")
        sections = parse_essay_sections(essay)
        ts = section_timestamps(sections, d)
        item_to_heading = align_and_get_assignment(sections, pool, span_start, span_end, boundaries, ts)
        if item_to_heading is None:
            return None
        results[label] = item_to_heading

    diffs = []
    for idx in sorted(set(results["plain"]) & set(results["wallpatched"])):
        h_plain = results["plain"][idx]
        h_wp = results["wallpatched"][idx]
        if h_plain != h_wp:
            diffs.append((idx, h_plain, h_wp))
    return diffs


def main():
    total_diffs = 0
    for daf in DAFIM:
        try:
            diffs = run_one(daf)
        except Exception as e:
            print(f"{daf}: ERROR {e}")
            continue
        if diffs is None:
            print(f"{daf}: SKIPPED (missing file or unconstrained-fallback path)")
            continue
        total_diffs += len(diffs)
        if diffs:
            print(f"{daf}: {len(diffs)} item(s) changed heading between plain and wallpatched:")
            for idx, h_plain, h_wp in diffs:
                print(f"   item {idx}: {h_plain!r} -> {h_wp!r}")
        else:
            print(f"{daf}: 0 differences")
    print(f"\nTotal placement differences across {len(DAFIM)} dafim: {total_diffs}")


if __name__ == "__main__":
    main()
