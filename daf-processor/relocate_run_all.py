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
from relocate_parse import parse_blocks, build_windows
from relocate_check import check_window

DAFIM = ["bava_batra_103","bava_batra_153","bava_batra_174","bava_batra_84",
         "bava_metzia_11","berakhot_31b","gittin_18","hullin_88","nazir_59",
         "niddah_60","niddah_67","yevamot_33","zevachim_29"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "review_v10_relocated")
os.makedirs(OUT_DIR, exist_ok=True)

for d in DAFIM:
    outpath = f"{OUT_DIR}/{d}.json"
    if os.path.exists(outpath):
        print(f"{d}: already done, skipping")
        continue
    path = os.path.join(os.path.dirname(__file__), "output", d, "03_text_first_prototype_v10.md")
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(text)
    windows = build_windows(blocks)
    results = []
    n_checked = 0
    for w in windows:
        if len(w["candidates"]) <= 1:
            continue
        for attempt in range(3):
            try:
                result = check_window(w)
                break
            except Exception as e:
                print(f"  retry {d} run={w['quote_indices']}: {e}")
                time.sleep(3)
                result = None
        n_checked += 1
        results.append({
            "quote_indices": w["quote_indices"],
            "current_heading": w["current_heading"],
            "candidates": [c["heading"] for c in w["candidates"]],
            "result": result,
        })
    moved = sum(1 for r in results if r["result"] and r["result"].get("moved"))
    print(f"{d}: {n_checked} checked, {moved} recommended moves")
    with open(outpath, "w") as f:
        json.dump(results, f, indent=2)
