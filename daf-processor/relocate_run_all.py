"""relocate_run_all.py — batch runner for relocate_check.py over a fixed daf list, saving
one JSON per daf under OUT_DIR (each entry: quote_indices, current_heading, candidates,
and Claude's verdict). Resumable — skips any daf whose output file already exists.
Direct API calls (not the Batch API) — this is test-scope tooling for a small, known
batch; a corpus-wide run should go through the Batch API, matching every other pipeline
stage's cost-conscious default (see CLAUDE.md)."""
import sys
import json
import os
import time
import argparse
from relocate_parse import parse_blocks, build_windows
from relocate_check import check_window
from relocate_rescue_starved import apply_rescue_pass

DAFIM = ["bava_batra_103","bava_batra_153","bava_batra_174","bava_batra_84",
         "bava_metzia_11","berakhot_31b","gittin_18","hullin_88","nazir_59",
         "niddah_60","niddah_67","yevamot_33","zevachim_29"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "review_v10_relocated")
os.makedirs(OUT_DIR, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--dafim", nargs="*", default=DAFIM, help="Daf dir names to process")
ap.add_argument("--v10-file", default="03_text_first_prototype_v10.md",
                 help="v10-assembled filename to read from each daf dir")
ap.add_argument("--suffix", default="", help="Suffix for the output JSON filename, e.g. '_wallpatched'")
args = ap.parse_args()

for d in args.dafim:
    outpath = f"{OUT_DIR}/{d}{args.suffix}.json"
    if os.path.exists(outpath):
        print(f"{d}: already done, skipping")
        continue
    path = os.path.join(os.path.dirname(__file__), "output", d, args.v10_file)
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(text)
    windows = build_windows(blocks)
    results = []
    n_checked = 0
    for w in windows:
        if len(w["candidates"]) <= 1:
            continue
        # check_window() catches its own malformed-JSON/response failures internally
        # and returns None rather than raising -- the old `break` right after the call
        # exited this loop on the FIRST attempt regardless of whether result was a real
        # verdict or None, so a bad response silently became a permanent no-op with no
        # retry (found 2026-08-07 on Meilah 8's 8-item "Shtei Halechem" mega-run: the
        # model's response wasn't valid JSON on that attempt, and the window was never
        # retried, so v10's original -- also wrong -- placement was never reconsidered
        # at all). Now retries on a None result too, not just on a raised exception.
        result = None
        for attempt in range(3):
            try:
                result = check_window(w)
                if result is not None:
                    break
                print(f"  retry {d} run={w['quote_indices']}: check_window returned None")
            except Exception as e:
                print(f"  retry {d} run={w['quote_indices']}: {e}")
                result = None
            time.sleep(3)
        n_checked += 1
        results.append({
            "quote_indices": w["quote_indices"],
            "current_heading": w["current_heading"],
            "candidates": [c["heading"] for c in w["candidates"]],
            "result": result,
        })
    rescued = apply_rescue_pass(blocks, windows, results)

    moved = sum(1 for r in results if r["result"] and r["result"].get("moved"))
    rescue_note = f", {rescued} starved-heading window(s) re-checked" if rescued else ""
    print(f"{d}: {n_checked} checked, {moved} recommended moves{rescue_note}")
    with open(outpath, "w") as f:
        json.dump(results, f, indent=2)
