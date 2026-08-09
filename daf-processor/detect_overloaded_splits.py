#!/usr/bin/env python3
"""detect_overloaded_splits.py — FLAG ONLY, no file modifications.

relocate_check.py's split feature caps at one split point (two pieces) per quote run.
Found on Nazir 59 and Niddah 60 (2026-08-03): a run can genuinely span 3+ distinct
headings, and when it does, the model is forced to bundle two of them together under one
target -- even when candidate headings that exist specifically for that bundled content
sit completely empty in the final output right next to an oversized pile.

This script finds that pattern mechanically, without touching relocate_check's scoring or
the split logic at all: for every quote run at or above RUN_THRESHOLD items, load its
ORIGINAL candidate list (from the relocate-check JSON, built before any moves) and check
the FINAL applied output for headings that were offered as candidates but ended up with
zero quotes, while the run's actual target(s) absorbed most or all of it. A candidate
heading having zero quotes is not inherently suspicious on its own -- most headings are
pure commentary with no attached quote by design. The signal here is specifically that the
SAME window that already flagged this heading as a plausible topical fit for an oversized,
still-ambiguous run left it with nothing.

Usage:
    python detect_overloaded_splits.py                  # scan the fixed 13-daf test batch
    python detect_overloaded_splits.py output/nazir_59/03_text_first_prototype_v10_wallpatched.md review_v10_relocated/nazir_59_wallpatched_split.json
"""
import json
import sys
from pathlib import Path

from relocate_parse import parse_blocks, quote_runs, heading_of

HERE = Path(__file__).parent
RELOC_DIR = HERE / "review_v10_relocated"

RUN_THRESHOLD = 4   # only worth flagging once a run is big enough to plausibly hold 3+ topics
PILE_THRESHOLD = 6  # a single heading absorbing this many quotes is the real "pileup" signal

# (daf, final markdown path, json path) -- the FINAL reviewed file (post-move) per
# apply_split_batch.py's JOBS list, not the pre-move v10 source.
JOBS = [
    ("bava_batra_103", "review_v10_relocated/bava_batra_103_wallpatched_split_relocated.md",
     "review_v10_relocated/bava_batra_103_wallpatched_split.json"),
    ("bava_batra_153", "review_v10_relocated/bava_batra_153_wallpatched_split_relocated.md",
     "review_v10_relocated/bava_batra_153_wallpatched_split.json"),
    ("bava_batra_174", "review_v10_relocated/bava_batra_174_wallpatched_split_relocated.md",
     "review_v10_relocated/bava_batra_174_wallpatched_split.json"),
    ("bava_batra_84", "review_v10_relocated/bava_batra_84_wallpatched_split_relocated.md",
     "review_v10_relocated/bava_batra_84_wallpatched_split.json"),
    ("bava_metzia_11", "review_v10_relocated/bava_metzia_11_wallpatched_split_relocated.md",
     "review_v10_relocated/bava_metzia_11_wallpatched_split.json"),
    ("berakhot_31b", "review_v10_relocated/berakhot_31b_wallpatched_split_relocated.md",
     "review_v10_relocated/berakhot_31b_wallpatched_split.json"),
    ("gittin_18", "review_v10_relocated/gittin_18_wallpatched_split_relocated.md",
     "review_v10_relocated/gittin_18_wallpatched_split.json"),
    ("hullin_88", "review_v10_relocated/hullin_88_wallpatched_split_relocated.md",
     "review_v10_relocated/hullin_88_wallpatched_split.json"),
    ("nazir_59", "review_v10_relocated/nazir_59_wallpatched_split_relocated.md",
     "review_v10_relocated/nazir_59_wallpatched_split.json"),
    ("niddah_60", "review_v10_relocated/niddah_60_wallpatched_split_relocated.md",
     "review_v10_relocated/niddah_60_wallpatched_split.json"),
    ("niddah_67", "review_v10_relocated/niddah_67_wallpatched_split_relocated.md",
     "review_v10_relocated/niddah_67_wallpatched_split.json"),
    ("yevamot_33", "review_v10_relocated/yevamot_33_wallpatched_split_relocated.md",
     "review_v10_relocated/yevamot_33_wallpatched_split.json"),
    ("zevachim_29", "review_v10_relocated/zevachim_29_split_relocated.md",
     "review_v10_relocated/zevachim_29_split.json"),
]


def quotes_per_heading(final_md_path: Path) -> dict:
    """heading text -> number of quote blocks under it in the FINAL (post-move) output."""
    text = final_md_path.read_text(encoding="utf-8", errors="replace")
    blocks = parse_blocks(text)
    counts: dict[str, int] = {}
    for i, b in enumerate(blocks):
        if b.kind == "quote":
            h = heading_of(blocks, i)
            counts[h] = counts.get(h, 0) + 1
    return counts


def scan_daf(daf: str, final_md_path: Path, json_path: Path) -> list[dict]:
    if not final_md_path.exists() or not json_path.exists():
        return []
    results = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
    counts = quotes_per_heading(final_md_path)

    # A candidate with zero quotes ANYWHERE in the whole document is a much stronger
    # signal than "zero within this one window" -- nearly every pure-commentary heading
    # satisfies the latter trivially, since most headings never get a quote at all.
    all_h3 = {h for h in counts} | {c for entry in results for c in entry.get("candidates", [])}
    globally_empty = {h for h in all_h3 if counts.get(h, 0) == 0}

    flags = []
    for entry in results:
        run = entry["quote_indices"]
        if len(run) < RUN_THRESHOLD:
            continue
        candidates = entry.get("candidates", [])
        res = entry.get("result") or {}
        chosen = {res.get("chosen_heading"), res.get("first_heading"), res.get("second_heading")}
        chosen.discard(None)

        winner_counts = {c: counts.get(c, 0) for c in chosen}
        if not winner_counts or max(winner_counts.values(), default=0) < PILE_THRESHOLD:
            continue

        empty_candidates = [c for c in candidates if c not in chosen and c in globally_empty]
        if not empty_candidates:
            continue

        flags.append({
            "daf": daf,
            "quote_indices": run,
            "run_size": len(run),
            "current_heading": entry.get("current_heading"),
            "chosen": sorted(chosen),
            "winner_counts": winner_counts,
            "empty_candidates": empty_candidates,
            "all_candidates": candidates,
        })
    return flags


def main():
    if len(sys.argv) == 3:
        jobs = [("(single file)", Path(sys.argv[1]), Path(sys.argv[2]))]
    else:
        jobs = [(d, HERE / f, HERE / j) for d, f, j in JOBS]

    all_flags = []
    for daf, final_md_path, json_path in jobs:
        flags = scan_daf(daf, Path(final_md_path), Path(json_path))
        all_flags.extend(flags)

    print(f"Scanned {len(jobs)} daf(im), run threshold >= {RUN_THRESHOLD} items.")
    print(f"{len(all_flags)} run(s) flagged: large run, empty candidate heading(s) sitting "
          f"in the same window as the (over)loaded target.\n")

    for f in all_flags:
        print(f"[{f['daf']}] run@{f['quote_indices']} ({f['run_size']} items), "
              f"current={f['current_heading']!r}")
        print(f"  chosen target(s) + final quote count: {f['winner_counts']}")
        print(f"  empty candidate(s) in same window: {f['empty_candidates']}")
        print(f"  all candidates considered: {f['all_candidates']}")
        print()


if __name__ == "__main__":
    main()
