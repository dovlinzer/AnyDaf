#!/usr/bin/env python3
"""
Remove *[Continued from above]* lines that appear before the first real
blockquote (>) in each 03_final.md file.
"""

import glob
import os

PLACEHOLDER = "*[Continued from above]*"

files = sorted(glob.glob("output/**/03_final.md", recursive=True))
fixed = []

for path in files:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    seen_blockquote = False
    new_lines = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            seen_blockquote = True
        if not seen_blockquote and stripped == PLACEHOLDER:
            removed += 1
            # Also remove a trailing blank line if present
            continue
        new_lines.append(line)

    if removed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        fixed.append((path, removed))
        print(f"Fixed {path}: removed {removed} premature placeholder(s)")

if not fixed:
    print("No premature *[Continued from above]* found in any file.")
else:
    print(f"\nTotal: {len(fixed)} file(s) fixed.")
