#!/usr/bin/env python3
"""
fix_h2_mismatch.py
For each daf where 02_rewrite.md and 03_final.md have more ## headings than
macro_segments in 01_segmentation.json, demote the excess ## headings (beyond
the first N) to ### headings in both files.

Run check_h2_mismatch.py first to preview what will be fixed.
Pass --dry-run to preview changes without writing.
"""
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
DRY_RUN = "--dry-run" in sys.argv


def fix_file(path: Path, macro_count: int) -> bool:
    """
    Demote ## headings beyond the first `macro_count` to ###.
    Returns True if the file was (or would be) modified.
    """
    lines = path.read_text().splitlines(keepends=True)
    h2_seen = 0
    new_lines = []
    changed = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("## "):
            h2_seen += 1
            if h2_seen > macro_count:
                # Demote: replace leading ## with ###
                indent = line[: len(line) - len(stripped)]
                new_line = indent + "###" + stripped[2:]
                new_lines.append(new_line)
                changed = True
                continue
        new_lines.append(line)

    if changed and not DRY_RUN:
        path.write_text("".join(new_lines))

    return changed


fixed_any = False

for daf_dir in sorted(OUTPUT_DIR.iterdir()):
    seg_file     = daf_dir / "01_segmentation.json"
    rewrite_file = daf_dir / "02_rewrite.md"
    final_file   = daf_dir / "03_final.md"

    if not seg_file.exists() or not rewrite_file.exists():
        continue

    try:
        with open(seg_file) as f:
            data = json.load(f)
        macro_count = len(data.get("macro_segments", []))
    except Exception as e:
        print(f"ERROR {daf_dir.name}: {e}", file=sys.stderr)
        continue

    h2_count = sum(
        1 for line in rewrite_file.read_text().splitlines()
        if line.strip().startswith("## ")
    )

    if h2_count == macro_count:
        continue

    excess = h2_count - macro_count
    print(f"{daf_dir.name}: {h2_count} ## headings, {macro_count} macro segments "
          f"— demoting {excess} excess heading(s) to ###")

    r_changed = fix_file(rewrite_file, macro_count)
    f_changed = fix_file(final_file, macro_count) if final_file.exists() else False

    if DRY_RUN:
        print(f"  [dry-run] rewrite={'would change' if r_changed else 'no change'}, "
              f"final={'would change' if f_changed else 'no change'}")
    else:
        print(f"  rewrite={'updated' if r_changed else 'no change'}, "
              f"final={'updated' if f_changed else 'no change'}")

    fixed_any = True

if not fixed_any:
    print("No mismatches found — nothing to fix.")
elif DRY_RUN:
    print("\n(dry-run — no files written)")
