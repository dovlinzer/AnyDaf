#!/usr/bin/env python3
"""One-off runner: applies the new split-aware relocate_check.py verdicts (saved under
*_wallpatched_split.json / *_split.json) to their source v10 files, writing
*_wallpatched_split_relocated.md / *_split_relocated.md for review. Bypasses
apply_moves.py's CLI, which assumes the JSON suffix and the v10 source suffix are the
same string -- not true here (source is "_wallpatched", output is "_wallpatched_split")."""
import json
import os
from apply_moves import apply

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "review_v10_relocated")

# (daf, v10_source_suffix, json_and_output_suffix)
JOBS = [
    ("bava_batra_103", "_wallpatched", "_wallpatched_split"),
    ("bava_batra_153", "_wallpatched", "_wallpatched_split"),
    ("bava_batra_174", "_wallpatched", "_wallpatched_split"),
    ("bava_batra_84", "_wallpatched", "_wallpatched_split"),
    ("bava_metzia_11", "_wallpatched", "_wallpatched_split"),
    ("berakhot_31b", "_wallpatched", "_wallpatched_split"),
    ("gittin_18", "_wallpatched", "_wallpatched_split"),
    ("hullin_88", "_wallpatched", "_wallpatched_split"),
    ("nazir_59", "_wallpatched", "_wallpatched_split"),
    ("niddah_60", "_wallpatched", "_wallpatched_split"),
    ("niddah_67", "_wallpatched", "_wallpatched_split"),
    ("yevamot_33", "_wallpatched", "_wallpatched_split"),
    ("zevachim_29", "", "_split"),
]

for daf, v10_suffix, out_suffix in JOBS:
    src = os.path.join(HERE, "output", daf, f"03_text_first_prototype_v10{v10_suffix}.md")
    json_path = os.path.join(OUT_DIR, f"{daf}{out_suffix}.json")
    results = json.load(open(json_path))
    moves = {}
    n_split = n_single = 0
    for r in results:
        res = r["result"]
        if not res:
            continue
        if res.get("action") == "split":
            moves[tuple(r["quote_indices"])] = {
                "type": "split",
                "split_after": res["split_after"],
                "first_target": res["first_heading"],
                "first_confidence": res.get("first_confidence"),
                "second_target": res["second_heading"],
                "second_confidence": res.get("second_confidence"),
            }
            n_split += 1
        elif res.get("action") == "split3":
            moves[tuple(r["quote_indices"])] = {
                "type": "split3",
                "split1": res["split1"],
                "split2": res["split2"],
                "first_target": res["first_heading"],
                "first_confidence": res.get("first_confidence"),
                "second_target": res["second_heading"],
                "second_confidence": res.get("second_confidence"),
                "third_target": res["third_heading"],
                "third_confidence": res.get("third_confidence"),
            }
            n_split += 1
        elif res.get("moved") and res.get("confidence") == "high":
            moves[tuple(r["quote_indices"])] = {"type": "single", "target": res["chosen_heading"]}
            n_single += 1
    patched, applied = apply(src, moves)
    out_path = os.path.join(OUT_DIR, f"{daf}{out_suffix}_relocated.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"{daf}: {n_single} single-move(s), {n_split} split(s) queued, {applied} sub-moves actually applied -> {out_path}")
