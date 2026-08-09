#!/usr/bin/env python3
"""
prototype_text_first_v10.py — PROTOTYPE. v9 plus a trailing-isolation guard on span_end.

WHAT v9 GOT WRONG. Human review of Bava Batra 174, 153, and 103 found the same defect in
three different guises: a large block of text at the END of the daf that was never
discussed in the shiur. Root cause is structural, not a v9-specific bug — it lives in
longest_consistent_run() (prototype_text_first_v3.py), which every version since v3 has
inherited unchanged:

  span_end = max(boundaries), and assembly emits EVERY pool segment from span_start to
  span_end, matched or not — that is what "completeness" means in this pipeline. The
  consistency filter only enforces non-decreasing TIME as segment index increases; it has
  no defense against a single ISOLATED, marginal-confidence match landing at a much later
  INDEX and thereby vouching for everything between it and the true last real match.

Confirmed against the raw match data on all three:
  * Bava Batra 174 — last real match at idx 40. Kept run then jumps to idx 62 (Δ22) on a
    single score-0.67 match — the opening of the NEXT daf's mishnah. 22 unrecited segments
    got pulled in behind it.
  * Bava Batra 153 — three matches (idx 27, 28, 36) land at the IDENTICAL SRT timestamp,
    which is physically impossible (one lecturer cannot recite three different passages in
    the same instant). One anomalous transcript window scored against several real
    segments at once; the farthest (idx 36, Δ8 from 28) became the new span_end.
  * Bava Batra 103 — idx 22→26 (Δ4, score 0.50) then 26→30 (Δ4, score 0.56): a recurring
    Talmudic rhetorical pattern ("X mahu?" — "what of case X?") produced two consecutive
    weak matches onto the NEXT daf's mishnah, which reuses the same pattern for an
    unrelated case.

A 220-daf corpus sample confirms this is not particular to these three: matches with a
same-tail-position index jump >4 at score <0.85 appear on ~3.6% of sampled dafim (8/220).

THE FIX — guarded_consistent_run(), a from-scratch longest-non-decreasing-subsequence DP
(v3's original uses O(n log n) patience sorting, which only tracks the best tail per length
and has no way to prefer one equal-length chain over another). Here, a transition from
match i to match j is forbidden outright when j jumps more than JUMP_GAP indices ahead of i
without a HIGH_CONFIDENCE score (or shares i's exact timestamp) — removing it from the
search, not filtering it from the result. This matters: a first attempt ran v3's plain LIS
first and filtered its output, but on Bava Batra 103 the plain LIS chose between two
equal-length chains — the real one (ending at the mishna's own closing words) and a
spurious one (jumping to the next daf's mishna via a recurring "X mahu?" phrasing) — and
picked the spurious one on a tie-break that has no opinion about plausibility. A post-hoc
filter can only delete from whichever chain won; it can't recover the one the search
discarded. Making the transition unreachable lets the real chain win outright.

Calibrated against a 220-daf corpus sample: gap>3 & score<0.85 catches 22 of 5,745 sampled
transitions (0.38%) — narrow enough that it should not touch legitimate content, and it
correctly reproduces the desired outcome on all three review dafim, restoring Bava Batra
103's mishna text that the filter-based attempt had lost as collateral damage (see
AnyDaf/CLAUDE.md).

Everything else — the constrained alignment, the mid-sentence rule, the colon fix — is
unchanged from v9. Zero API calls; both completeness invariants still asserted.

Usage:
    python prototype_text_first_v10.py output/bava_batra_174
    python prototype_text_first_v10.py --all --diagnose
"""

# v9's own rationale (constrained alignment, mid-sentence rule, colon fix, "§" bonus) is
# unchanged here and documented in prototype_text_first_v9.py.

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

# ':' deliberately EXCLUDED. In Talmudic text a colon introduces quoted speech — Gittin 18b
# segment 35 ends "...amar leih:" and segment 36 is the reply — so a colon marks the next
# segment as a CONTINUATION, not a sentence end. Treating it as terminal split a quotation
# from its speaker. Affects 1.1% of segments corpus-wide (99 of 9,137 sampled).
TERMINATORS = ".!?׃"
NEW_TOPIC_BONUS = 0.60           # reward a block that begins at Sefaria's own "§" marker

JUMP_GAP = 3          # index gap beyond which a match must earn extra trust to extend the span
HIGH_CONFIDENCE = 0.85  # score required for a jump larger than JUMP_GAP to be trusted

LOW_SCORE_FLOOR = 0.45   # a section's only claim on a segment must clear this on its own...
LOW_MARGIN_FLOOR = 0.01  # ...or be at least this far ahead of the runner-up section

HEAD_ANCHOR_CONFIDENCE = 0.90  # span_start's own match must be this solid to vouch for a neighbor
HEAD_NEIGHBOR_FLOOR = 0.40     # the neighbor's own (sub-threshold) score must clear this

# A "section opening sentence" bonus (reward a block starting with the segment its own
# section's first sentence discusses) was tried and pulled back out 2026-07-30. Tested
# against all 7 confirmed cases in a 200-daf sample: fixed 1, left 6 unchanged — including
# the motivating Bava Batra 174 case, which uses transliterated Hebrew terms ("ibayu lehu")
# that share zero vocabulary with Sefaria's English translation ("A dilemma was raised"),
# an inherent blind spot of English-word-overlap scoring that a bigger bonus can't fix. One
# other confirmed case (Sukkah 10) was separately blocked by the mid-sentence-continuation
# rule regardless of any bonus. Not reliable enough to ship; see chat history if revisiting.


def guarded_consistent_run(matches: list[tuple[int, float, float]]) -> list[tuple[int, float, float]]:
    """v3's longest_consistent_run, with the jump forbidden as a DP transition rather than
    filtered out of its result afterward.

    First attempt (filter_isolated_jumps, kept in git history) ran v3's plain LIS first and
    trimmed suspect matches from ITS output. That is too late: on Bava Batra 103 the plain
    LIS had to choose between two equal-length non-decreasing chains — the real one
    (...22, 23, 24, ending at the mishna's own closing words) and a spurious one (...22, 26,
    30, jumping into the NEXT daf's mishna via a recurring "X mahu?" phrasing) — and its
    tie-break, an implementation detail of patience sorting with no opinion on which chain
    is more *plausible*, happened to pick the spurious one. A post-hoc filter can only
    delete from whichever chain won; it cannot recover the real one that was discarded
    during the search. Forbidding the same transition (jump > JUMP_GAP with score <
    HIGH_CONFIDENCE, or sharing the predecessor's exact timestamp) DURING the search removes
    it from the graph entirely, so the real chain wins on length without contention — and
    the mishna's own idx 23/24, previously lost as collateral damage, are restored.

    O(n^2) DP: matches per daf rarely exceed ~150, and full-corpus runtime confirmed fine.
    """
    n = len(matches)
    if n == 0:
        return []
    length = [1] * n
    parent = [-1] * n
    for j in range(n):
        idx_j, t_j, score_j = matches[j]
        for i in range(j):
            idx_i, t_i, _ = matches[i]
            if t_i > t_j:
                continue  # time must be non-decreasing as index increases
            gap = idx_j - idx_i
            if gap > JUMP_GAP and (score_j < HIGH_CONFIDENCE or t_j == t_i):
                continue  # forbidden: a big jump needs strong, unambiguous support
            if length[i] + 1 > length[j]:
                length[j] = length[i] + 1
                parent[j] = i
    best = max(range(n), key=lambda k: (length[k], matches[k][0]))
    out = []
    k = best
    while k != -1:
        out.append(matches[k])
        k = parent[k]
    return out[::-1]


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

    rescue_homeless_singletons(sections, assigned, scores)

    for i, sec in enumerate(sections):
        sec["anchor_index"] = assigned[i][-1] if assigned[i] else None


def rescue_homeless_singletons(sections: list[dict], assigned: list[list[int]], scores: dict) -> None:
    """A section whose ENTIRE block is one segment that scores weakly AND ambiguously
    likely landed there by a near coin-flip, not because it belongs — the essay simply
    never discusses it (found on Bava Batra 174's Rabban Shimon ben Gamliel aside: best
    score 0.44, only 0.006 ahead of the runner-up, across five candidate sections — none
    of the five score it confidently). Rather than leave it stranded under an unrelated
    heading, merge it onto whichever section already owns the segment immediately before
    it: end of the preceding, already-anchored block, not the middle of an unrelated one.

    Calibrated against a 180-daf sample: flagging on low SCORE alone (11-19% of ALL
    single-segment placements) or low MARGIN alone (12-26%) is far too broad — both are
    common even for correctly-placed segments, since neighboring sections in a continuous
    sugya naturally share vocabulary and the time-proximity bonus varies smoothly across
    a section boundary. Requiring BOTH at once narrows it to ~2.6% of singletons, which is
    where Bava Batra 174's actual case sits (well inside both floors)."""
    owner: dict[int, int] = {}
    for i, a in enumerate(assigned):
        for j in a:
            owner[j] = i
    for i, a in enumerate(assigned):
        if len(a) != 1:
            continue
        idx = a[0]
        prev_owner = owner.get(idx - 1)
        if prev_owner is None or prev_owner == i:
            continue
        all_scores = sorted((scores.get((si, idx), 0.0) for si in range(len(sections))), reverse=True)
        top1 = all_scores[0]
        top2 = all_scores[1] if len(all_scores) > 1 else 0.0
        if top1 < LOW_SCORE_FLOOR and (top1 - top2) < LOW_MARGIN_FLOOR:
            assigned[prev_owner].append(idx)
            assigned[i] = []
            owner[idx] = prev_owner


def extend_head_to_confident_neighbor(
        kept: list[tuple[int, float, float]],
        raw_all_by_idx: dict[int, tuple[float, float]],
) -> list[tuple[int, float, float]]:
    """Pull span_start back by one segment if it was cut off by paraphrase, not absence.

    Found on Bava Batra 103: the lecturer explained *תנן התם...* in English rather than
    reciting it, so it scored 0.41 — just under DEFAULT_THRESHOLD (0.5) — while the very
    next segment, which WAS recited verbatim, scored 1.00. best_match_times() only returns
    segments clearing threshold, so span_start started one segment too late and the first
    blockquote opened mid-thought, even though the excluded segment was real, adjacent,
    and clearly covered (confirmed against the SRT — a Rashbam girsa discussion of exactly
    this text).

    Deliberately head-only, single-step, and narrow. A 180-daf sample found tail
    candidates (span_end+1) at 2-3x the rate of head candidates, with no way yet to tell
    a genuine recitation from an echo of the fabricated-transcript-tail problem the
    guarded LIS was built to reject — extending forward risks undoing that fix, so it's
    out of scope here. At ANCHOR_CONFIDENCE=0.90 / NEIGHBOR_FLOOR=0.40 the head rule fired
    on 2 of 174 sampled dafim (~1.1%); both spot-checked as real, substantive continuations
    of the anchor segment's own sentence/topic, not noise.
    """
    if not kept:
        return kept
    span_start, _, anchor_score = kept[0]
    if span_start - 1 < 0 or anchor_score < HEAD_ANCHOR_CONFIDENCE:
        return kept
    neighbor = raw_all_by_idx.get(span_start - 1)
    if neighbor is None or neighbor[1] < HEAD_NEIGHBOR_FLOOR:
        return kept
    nb_time, nb_score = neighbor
    return [(span_start - 1, nb_time, nb_score)] + kept


def process(daf_dir: Path, threshold: float, diagnose: bool,
            essay_file: str = "02_rewrite.md", out_file: str = "03_text_first_prototype_v10.md") -> dict | None:
    if not all((daf_dir / f).exists() for f in
               ("01_segmentation.json", essay_file, "sefaria.md")):
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
    # Safety net for the ITEM_RE boundary bug (found on Meilah 8, fixed 2026-08-07):
    # a pool item whose translation contains these labels means parse_sefaria_full's
    # regex swallowed a neighboring item's raw markdown instead of stopping at the
    # correct boundary -- was silently possible whenever a Sefaria item has no English
    # translation (e.g. the chapter-closing "Hadran" formula). The regex is fixed, but
    # this assertion is the durable guard against this corruption class recurring in
    # any form, on any daf, without needing a human to notice a garbled blockquote.
    for it in pool:
        assert "*Hebrew/Aramaic:*" not in it["translation"] and "*Translation:*" not in it["translation"], (
            f"pool item {it['index']} ({it['source']}) has a corrupted translation "
            f"(embedded raw Sefaria markdown) -- see CLAUDE.md, 'Hadran' item swallow bug")
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not pool or not entries:
        return None

    raw_all = best_match_times(entries, pool, 0.0)  # unfiltered: needed for the head rescue
    raw_all_by_idx = {i: (t, s) for i, t, s in raw_all}
    raw = [m for m in raw_all if m[2] >= threshold]
    unguarded = longest_consistent_run(raw)   # for diagnostics only, never assembled from
    kept = guarded_consistent_run(raw)
    kept = extend_head_to_confident_neighbor(kept, raw_all_by_idx)
    trimmed = len(unguarded) - len(kept)
    boundaries = {idx: t for idx, t, _ in kept}
    span_start = min(boundaries) if boundaries else 0
    span_end = max(boundaries) if boundaries else len(pool) - 1

    essay = (daf_dir / essay_file).read_text(encoding="utf-8", errors="replace")
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
        "matched_delta_vs_unguarded": trimmed,
    }

    if not diagnose:
        doc, n_sec, n_items = assemble_heading_first(sections, pool, span_start, span_end)
        expected = span_end - span_start + 1
        assert n_sec == len(sections), f"section loss {n_sec}/{len(sections)}"
        assert n_items == expected, f"sefaria loss {n_items}/{expected}"
        out = daf_dir / out_file
        out.write_text(doc, encoding="utf-8")
        stats.update(wrote=str(out), emitted_sections=n_sec, emitted_items=n_items)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--essay-file", default="02_rewrite.md",
                     help="Essay filename to read from each daf dir (default: 02_rewrite.md)")
    ap.add_argument("--out-file", default="03_text_first_prototype_v10.md",
                     help="Output filename to write within each daf dir")
    args = ap.parse_args()

    dirs = ([d for d in sorted(OUTPUT_ROOT.iterdir()) if d.name not in MISLABELED]
            if args.all else [Path(d) for d in args.dirs])

    for d in dirs:
        if not d.is_dir():
            continue
        try:
            s = process(d, args.threshold, args.diagnose, args.essay_file, args.out_file)
        except AssertionError as e:
            print(f"{d.name}: COMPLETENESS ASSERTION FAILED — {e}")
            continue
        if s and not args.all:
            print(f"\n{s['label']}  ({s['daf']})")
            print(f"  matched {s['matched']} segs | span {s['span']} | sections {s['sections']} "
                  f"(anchored {s['anchored']}) | mid-sentence splits blocked: "
                  f"{s['mid_sentence_splits_blocked']} | matched vs unguarded LIS: "
                  f"{s['matched_delta_vs_unguarded']:+d}")
            if "wrote" in s:
                print(f"  completeness verified: {s['emitted_sections']}/{s['sections']} sections, "
                      f"{s['emitted_items']} segments -> {s['wrote']}")


if __name__ == "__main__":
    main()
