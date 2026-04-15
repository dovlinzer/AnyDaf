#!/usr/bin/env python3
"""
apply_display_titles.py
Replace ## and ### headings in 02_rewrite.md and 03_final.md with the
display_title values from 01_segmentation.json, matched by position.

## headings  → macro segment display_titles (in order)
### headings → micro segment display_titles (in order, across all macros)

Run with --dry-run to preview without writing.
"""
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
DRY_RUN = "--dry-run" in sys.argv


def apply_titles(path: Path, macro_display: list[str], micro_display: list[str]) -> bool:
    """Replace ## and ### heading text with the display_title values by position."""
    lines = path.read_text().splitlines(keepends=True)
    new_lines = []
    macro_idx = 0
    micro_idx = 0
    changed = False

    for line in lines:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        if stripped.startswith("## ") and macro_idx < len(macro_display):
            new_title = macro_display[macro_idx]
            new_line = f"{indent}## {new_title}\n"
            if new_line != line:
                changed = True
            new_lines.append(new_line)
            macro_idx += 1

        elif stripped.startswith("### ") and micro_idx < len(micro_display):
            new_title = micro_display[micro_idx]
            new_line = f"{indent}### {new_title}\n"
            if new_line != line:
                changed = True
            new_lines.append(new_line)
            micro_idx += 1

        else:
            new_lines.append(line)

    if changed and not DRY_RUN:
        path.write_text("".join(new_lines))

    return changed


total_updated = 0

for daf_dir in sorted(OUTPUT_DIR.iterdir()):
    seg_file     = daf_dir / "01_segmentation.json"
    rewrite_file = daf_dir / "02_rewrite.md"
    final_file   = daf_dir / "03_final.md"

    if not seg_file.exists() or not rewrite_file.exists():
        continue

    try:
        with open(seg_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR {daf_dir.name}: {e}", file=sys.stderr)
        continue

    macros = data.get("macro_segments", [])
    if not macros or "display_title" not in macros[0]:
        print(f"{daf_dir.name}: skipped (no display_title in segmentation — re-run Pass 1)")
        continue

    macro_display = [m["display_title"] for m in macros]
    micro_display = [
        mic["display_title"]
        for m in macros
        for mic in m.get("micro_segments", [])
        if "display_title" in mic
    ]

    r_changed = apply_titles(rewrite_file, macro_display, micro_display)
    f_changed = apply_titles(final_file,   macro_display, micro_display) if final_file.exists() else False

    if r_changed or f_changed:
        total_updated += 1
        label = "would update" if DRY_RUN else "updated"
        parts = []
        if r_changed: parts.append("rewrite")
        if f_changed: parts.append("final")
        print(f"{daf_dir.name}: {label} {' + '.join(parts)}")

if total_updated == 0:
    print("All headings already match display_titles — nothing to change.")
elif DRY_RUN:
    print(f"\n{total_updated} daf(s) would be updated. (dry-run — no files written)")
else:
    print(f"\n{total_updated} daf(s) updated.")
