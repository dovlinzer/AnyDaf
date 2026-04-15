#!/usr/bin/env python3
"""
check_h2_mismatch.py
Scan all output directories and report dafs where the number of ## headings
in 02_rewrite.md does not match the number of macro_segments in 01_segmentation.json.
"""
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"

mismatches = []
errors = []

for daf_dir in sorted(OUTPUT_DIR.iterdir()):
    seg_file    = daf_dir / "01_segmentation.json"
    rewrite_file = daf_dir / "02_rewrite.md"

    if not seg_file.exists() or not rewrite_file.exists():
        continue

    try:
        with open(seg_file) as f:
            data = json.load(f)
        macro_count = len(data.get("macro_segments", []))
    except Exception as e:
        errors.append(f"  {daf_dir.name}: segmentation parse error — {e}")
        continue

    rewrite_text = rewrite_file.read_text()
    h2_count = sum(1 for line in rewrite_text.splitlines()
                   if line.strip().startswith("## "))

    if h2_count != macro_count:
        mismatches.append((daf_dir.name, macro_count, h2_count))

if mismatches:
    print(f"{'DAF':<30} {'MACRO SEGS':>10}  {'## HEADINGS':>11}  {'DIFF':>6}")
    print("-" * 62)
    for name, macro, h2 in mismatches:
        diff = h2 - macro
        sign = f"+{diff}" if diff > 0 else str(diff)
        print(f"{name:<30} {macro:>10}  {h2:>11}  {sign:>6}")
    print(f"\n{len(mismatches)} mismatch(es) found.")
else:
    print("All dafs have matching ## heading counts.")

for e in errors:
    print(e, file=sys.stderr)
