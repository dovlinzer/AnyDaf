#!/usr/bin/env python3
"""apply_moves_batch.py — loops apply_moves.apply() over an explicit list of dafim,
writing each one's final reviewable .md. Local/no API cost.

apply_moves.py's own __main__ reuses a single --suffix for BOTH the v10 source filename
(f"03_text_first_prototype_v10{suffix}.md") and the relocate JSON/output filename
(f"{daf}{suffix}.json" / f"{daf}{suffix}_relocated.md") -- fine when both happen to share
one suffix, but relocate_run_all.py's --v10-file and --suffix are independently
configurable and don't have to match (e.g. v10 file suffixed "_wallpatched", JSON/output
suffixed "_wallpatched_split"). This wrapper takes the v10 filename and the JSON/output
suffix as separate arguments instead of conflating them.

First step toward the corpus-wide gap noted in CLAUDE.md ("apply_moves.py inserted
relocated content..." section): no --all mode, and never writes to output/<daf>/03_final.md
-- still true here, this is explicit-list-only and still writes to the review_v10_relocated/
side directory, matching the existing test-scope convention until promotion is designed."""
import argparse
import json
import os
from apply_moves import apply

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "review_v10_relocated")


def moves_from_results(results):
    moves = {}
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
        elif res.get("moved") and res.get("confidence") == "high":
            moves[tuple(r["quote_indices"])] = {"type": "single", "target": res["chosen_heading"]}
    return moves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dafim", nargs="*")
    ap.add_argument("--all", action="store_true",
                     help="Process every daf under output/ that has both --v10-file and a "
                          "review_v10_relocated/{daf}{suffix}.json already (i.e. relocate has run)")
    ap.add_argument("--v10-file", required=True, help="v10 filename to read from each daf dir, e.g. 03_text_first_prototype_v10_wallpatched.md")
    ap.add_argument("--suffix", required=True, help="Suffix identifying the relocate JSON / output filename, e.g. _wallpatched_split")
    args = ap.parse_args()

    if args.all:
        import glob
        dafim = sorted(
            os.path.basename(os.path.dirname(p))
            for p in glob.glob(os.path.join(HERE, "output", "*", args.v10_file))
            if os.path.exists(os.path.join(OUT_DIR, f"{os.path.basename(os.path.dirname(p))}{args.suffix}.json"))
        )
    elif args.dafim:
        dafim = args.dafim
    else:
        ap.error("pass daf name(s) or --all")

    for daf in dafim:
        src = os.path.join(HERE, "output", daf, args.v10_file)
        json_path = os.path.join(OUT_DIR, f"{daf}{args.suffix}.json")
        results = json.load(open(json_path, encoding="utf-8"))
        moves = moves_from_results(results)
        patched, applied = apply(src, moves)
        outpath = os.path.join(OUT_DIR, f"{daf}{args.suffix}_relocated.md")
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(patched)
        print(f"{daf}: {applied}/{len(moves)} moves applied -> {outpath}")


if __name__ == "__main__":
    main()
