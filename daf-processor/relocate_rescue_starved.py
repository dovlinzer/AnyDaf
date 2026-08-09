#!/usr/bin/env python3
"""relocate_rescue_starved.py — narrow second relocate pass (see AnyDaf/CLAUDE.md,
"Rescue starved headings", 2026-08-07).

build_windows()/quote_runs() compute every window's candidate list ONCE, upfront, from the
static v10 assembly, before any relocate verdict exists. So when round 1 moves a heading's
only quote-run away, any OTHER window that would now sensibly want that now-empty heading
as a candidate never gets the chance -- it was never offered, and round 1 never revisits it.

This is a narrow, evidence-gated fix for exactly that case, not a general "always offer
neighboring headings" change (which would be a much bigger, riskier search-space expansion --
see the Bava Metzia 11 "Tosafot Question" investigation in CLAUDE.md for why that's out of
scope for now):

  1. A heading H counts as STARVED only if it natively owned at least one quote-run in the
     original v10 assembly (i.e., it's not simply a heading that never had any quotes to
     begin with -- see "Two Reasons Explained" in the BM11 case, which is excluded by this
     rule) AND, after applying round 1's confidence-gated moves, ends up with zero quote
     blocks (native or moved-in).
  2. For each starved H, find any window whose OWN current heading is the very next h3
     after H (no other h3 in between) and whose candidate list does not already include H.
  3. Re-run relocate_check.check_window on that window with H inserted as an extra
     candidate (at the front, since H precedes everything else in the window), and report
     the new verdict alongside the old one for manual comparison.

Dry-run / reporting only -- writes review_v10_relocated/{daf}_rescue_report.json, does not
touch the canonical *_wallpatched_split.json or apply any moves.
"""
import json
import os
from pathlib import Path

from relocate_parse import parse_blocks, build_windows, quote_runs, heading_of, prose_of_heading
from relocate_check import check_window

HERE = Path(__file__).parent
OUT_DIR = HERE / "review_v10_relocated"

DAFIM = ["bava_batra_103", "bava_batra_153", "bava_batra_174", "bava_batra_84",
         "bava_metzia_11", "berakhot_31b", "gittin_18", "hullin_88", "nazir_59",
         "niddah_60", "niddah_67", "yevamot_33"]


def moved_sub_runs(run, move):
    """Mirrors apply_moves.py's move-decision logic: returns [(sub_run, target), ...] for
    the pieces that actually move (confidence == 'high'), without touching any files."""
    if move is None:
        return []
    out = []
    if move.get("action") == "single":
        if move.get("moved") and move.get("confidence") == "high":
            out.append((run, move["chosen_heading"]))
    elif move.get("action") == "split":
        k = move["split_after"]
        if move.get("first_confidence", "high") == "high":
            out.append((run[:k], move["first_heading"]))
        if move.get("second_confidence", "high") == "high":
            out.append((run[k:], move["second_heading"]))
    elif move.get("action") == "split3":
        k1, k2 = move["split1"], move["split2"]
        if move.get("first_confidence", "high") == "high":
            out.append((run[:k1], move["first_heading"]))
        if move.get("second_confidence", "high") == "high":
            out.append((run[k1:k2], move["second_heading"]))
        if move.get("third_confidence", "high") == "high":
            out.append((run[k2:], move["third_heading"]))
    return out


def find_starved(blocks, results_by_key):
    """Returns {heading_text: h3_block_index} for headings that natively owned a quote-run
    and end up with zero quote blocks after round 1's confidence-gated moves."""
    runs = quote_runs(blocks)
    native_heading_of_block = {}   # block idx (quote) -> its ORIGINAL heading text
    remaining = set()              # block indices still under their ORIGINAL heading
    gained = {}                    # heading text -> set of block indices moved in

    for run in runs:
        h = heading_of(blocks, run[0])
        for bi in run:
            native_heading_of_block[bi] = h
        move = results_by_key.get(tuple(run))
        moves = moved_sub_runs(run, move)
        moved_block_ids = set()
        for sub_run, target in moves:
            moved_block_ids.update(sub_run)
            gained.setdefault(target, set()).update(sub_run)
        for bi in run:
            if bi not in moved_block_ids:
                remaining.add(bi)

    final_count = {}
    for bi, h in native_heading_of_block.items():
        if bi in remaining:
            final_count[h] = final_count.get(h, 0) + 1
    for h, blk_ids in gained.items():
        final_count[h] = final_count.get(h, 0) + len(blk_ids)

    native_headings = set(native_heading_of_block.values())
    starved = {h for h in native_headings if final_count.get(h, 0) == 0}

    h3_idx_by_text = {}
    for i, b in enumerate(blocks):
        if b.kind == "h3":
            h3_idx_by_text.setdefault(b.text, []).append(i)

    out = {}
    for h in starved:
        positions = h3_idx_by_text.get(h)
        if not positions:
            continue
        # a heading title could repeat; pick the occurrence that actually owned a run
        run_starts = [run[0] for run in runs if heading_of(blocks, run[0]) == h]
        if not run_starts:
            continue
        anchor = min(run_starts)
        best = max((p for p in positions if p < anchor), default=positions[0])
        out[h] = best
    return out


def find_rescue_targets(blocks, windows, results_by_key):
    """Returns [(window, starved_heading_text, h3_block_index), ...] -- every window
    eligible for a round-2 re-check because a heading immediately before it went starved
    and isn't already in its candidate list."""
    h3_positions = [i for i, b in enumerate(blocks) if b.kind == "h3"]
    starved = find_starved(blocks, results_by_key)
    targets = []
    for h, h_bi in starved.items():
        next_h3 = min((p for p in h3_positions if p > h_bi), default=None)
        if next_h3 is None:
            continue
        for w in windows:
            first_qi = w["quote_indices"][0]
            current_h3 = max((p for p in h3_positions if p < first_qi), default=None)
            if current_h3 != next_h3:
                continue
            if any(c["heading"] == h for c in w["candidates"]):
                continue
            targets.append((w, h, h_bi))
    return targets


def apply_rescue_pass(blocks, windows, results):
    """Production entry point (see AnyDaf/CLAUDE.md, "Rescue starved headings"). Mutates
    `results` (the same list relocate_run_all.py builds -- dicts with quote_indices/
    current_heading/candidates/result) in place: every rescue-eligible window is re-checked
    with its starved neighbor added as a candidate, and its entry is overwritten with the
    round-2 verdict (round 2 strictly dominates round 1 -- same candidates plus one more, so
    there's no reason to prefer round 1 once round 2 exists, even when it doesn't change
    anything). Returns the number of windows re-checked."""
    results_by_key = {tuple(r["quote_indices"]): r["result"] for r in results}
    by_key = {tuple(r["quote_indices"]): r for r in results}
    targets = find_rescue_targets(blocks, windows, results_by_key)
    for w, h, h_bi in targets:
        rescued_candidate = {"heading": h, "prose": prose_of_heading(blocks, h_bi), "is_current": False}
        w2 = dict(w)
        w2["candidates"] = [rescued_candidate] + list(w["candidates"])
        new_result = check_window(w2)
        entry = by_key.get(tuple(w["quote_indices"]))
        if entry is not None:
            entry["candidates"] = [c["heading"] for c in w2["candidates"]]
            entry["result"] = new_result
    return len(targets)


def main():
    report = {}
    for daf in DAFIM:
        v10_path = HERE / "output" / daf / "03_text_first_prototype_v10_wallpatched.md"
        json_path = OUT_DIR / f"{daf}_wallpatched_split.json"
        if not v10_path.exists() or not json_path.exists():
            print(f"{daf}: SKIP (missing v10 file or round-1 JSON)")
            continue

        text = v10_path.read_text(encoding="utf-8", errors="replace")
        blocks = parse_blocks(text)
        windows = build_windows(blocks)
        results = json.loads(json_path.read_text())
        results_by_key = {tuple(r["quote_indices"]): r["result"] for r in results}

        h3_positions = [i for i, b in enumerate(blocks) if b.kind == "h3"]
        starved = find_starved(blocks, results_by_key)

        daf_report = []
        for h, h_bi in starved.items():
            next_h3 = min((p for p in h3_positions if p > h_bi), default=None)
            if next_h3 is None:
                continue
            for w in windows:
                first_qi = w["quote_indices"][0]
                current_h3 = max((p for p in h3_positions if p < first_qi), default=None)
                if current_h3 != next_h3:
                    continue
                if any(c["heading"] == h for c in w["candidates"]):
                    continue  # already offered -- not a rescue case
                rescued_candidate = {
                    "heading": h, "prose": prose_of_heading(blocks, h_bi), "is_current": False,
                }
                w2 = dict(w)
                w2["candidates"] = [rescued_candidate] + list(w["candidates"])
                old_result = results_by_key.get(tuple(w["quote_indices"]))
                new_result = check_window(w2)
                entry = {
                    "starved_heading": h,
                    "window_quote_indices": w["quote_indices"],
                    "window_current_heading": w["current_heading"],
                    "old_candidates": [c["heading"] for c in w["candidates"]],
                    "new_candidates": [c["heading"] for c in w2["candidates"]],
                    "round1_result": old_result,
                    "round2_result": new_result,
                }
                daf_report.append(entry)
                status = "CHANGED" if new_result and new_result.get("action") != "single" or \
                    (new_result and new_result.get("chosen_heading") != w["current_heading"]) else "same"
                print(f"{daf}: starved={h!r} rescues window {w['quote_indices']} "
                      f"(current={w['current_heading']!r}) -> {status}")

        if not daf_report:
            print(f"{daf}: 0 starved heading(s) with a rescuable neighbor")
        report[daf] = daf_report

    out_path = OUT_DIR / "rescue_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    total = sum(len(v) for v in report.values())
    print(f"\n{total} rescue case(s) found across {len(DAFIM)} dafim -> {out_path}")


if __name__ == "__main__":
    main()
