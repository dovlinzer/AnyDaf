#!/usr/bin/env python3
"""
sync_md_headers.py — Update ## section headers in rewrite/final .md files
after display_titles have been renamed by check_segmentation.py --fix.

Strategy: targeted search-and-replace, not positional matching.
For each macro segment whose display_title ends with a rank suffix
(" (II)", " (III)", etc.), the script derives the old header
(base title + "…") and replaces it in the .md files.

This avoids false replacements in dapim where the segmentation JSON was
re-run after the .md files were already generated (making positional
matching unreliable).

Also handles explicit manual renames supplied via --manual-renames.

Usage:
  python3 sync_md_headers.py                  # dry run
  python3 sync_md_headers.py --apply          # apply changes
  python3 sync_md_headers.py --output-dir ./output
"""

import argparse
import json
import re
import sys
from pathlib import Path


RANK_SUFFIX_RE = re.compile(r"\s*\((II|III|IV|V|VI|VII|VIII|IX|X|\d+)\)\s*$", re.IGNORECASE)


def load_segmentation(seg_file: Path):
    if not seg_file.exists():
        return None
    try:
        return json.loads(seg_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def derive_old_headers(new_title: str) -> list[str]:
    """
    Given a renamed display_title (ending with a rank suffix),
    return the candidate old ## header strings the .md might contain.
    The renamed title was produced from an old title that ended with "…"
    by stripping "…", possibly truncating, and appending the suffix.

    We try the base with and without "…" to be robust.
    """
    base = RANK_SUFFIX_RE.sub("", new_title).strip()
    candidates = [
        f"## {base}…",   # most common: old title had trailing ellipsis
        f"## {base}",    # less common: old title had no ellipsis
    ]
    return candidates


def sync_file(md_file: Path, rename_pairs: list[tuple[str, str]], apply: bool) -> list[str]:
    """
    Apply old→new header replacements in md_file, matching whole lines only.
    rename_pairs: list of (new_title, [candidate_old_headers]) — for each new title
    we try candidates in order, replacing only the first one found. This prevents
    replacing the unadorned first-occurrence header (e.g. "## Cooking Vessels")
    when a "…" variant ("## Cooking Vessels…") also exists and should be the one swapped.
    Returns list of change descriptions.
    """
    if not md_file.exists():
        return []

    lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
    changes = []

    for new_title, old_candidates in rename_pairs:
        new_h = f"## {new_title}"
        for old_h in old_candidates:
            if old_h == new_h:
                continue
            # Match whole lines only — avoids substring hits like
            # "## Blood-Stained Garmen" inside "## Blood-Stained Garment"
            matched = False
            for i, line in enumerate(lines):
                if line.rstrip("\n\r") == old_h:
                    changes.append(
                        f"  {md_file.parent.name}/{md_file.name}: '{old_h[3:]}' → '{new_title}'"
                    )
                    if apply:
                        lines[i] = new_h + line[len(old_h):]  # preserve line ending
                    matched = True
                    break
            if matched:
                break   # stop at first candidate found

    if apply and changes:
        md_file.write_text("".join(lines), encoding="utf-8")

    return changes


def build_rename_pairs(display_titles: list[str]) -> list[tuple[str, list[str]]]:
    """
    For each display_title that ends with a rank suffix, build
    (new_title, [candidate_old_headers]) with "…" variant first.
    """
    pairs = []
    seen_new = set()
    for title in display_titles:
        if not RANK_SUFFIX_RE.search(title):
            continue
        if title in seen_new:
            continue
        seen_new.add(title)
        pairs.append((title, derive_old_headers(title)))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Sync ## headers in .md files with renamed display_titles from segmentation JSON."
    )
    parser.add_argument("--output-dir", default="./output",
                        help="Directory containing job subdirectories (default: ./output)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes. Without this flag, only a dry run is shown.")
    parser.add_argument(
        "--manual-renames", nargs="*", metavar="OLD=NEW",
        help="Additional explicit header renames in 'Old Title=New Title' form, "
             "applied globally across all .md files. "
             "Example: --manual-renames 'Rov Presumption…=Rov: Witnesses'"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Error: output directory '{output_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    # Parse manual renames into a global replacement map
    global_replacements: dict[str, str] = {}
    for item in (args.manual_renames or []):
        if "=" not in item:
            print(f"Warning: skipping malformed --manual-renames entry '{item}' (no '=')")
            continue
        old, new = item.split("=", 1)
        global_replacements[f"## {old.strip()}"] = f"## {new.strip()}"

    seg_files = sorted(output_dir.glob("*/01_segmentation.json"))
    if not seg_files:
        print("No segmentation files found.")
        sys.exit(0)

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"{mode} — scanning {len(seg_files)} directories…\n")

    total_changes = 0

    for seg_file in seg_files:
        data = load_segmentation(seg_file)
        if not data:
            continue

        display_titles = [m.get("display_title", "") for m in data.get("macro_segments", [])]
        auto_pairs = build_rename_pairs(display_titles)

        # Merge global manual renames as additional pairs
        global_pairs = [(new[3:], [old]) for old, new in global_replacements.items()]
        all_pairs = auto_pairs + global_pairs

        if not all_pairs:
            continue

        daf_dir = seg_file.parent
        for md_name in ("02_rewrite.md", "03_final.md"):
            changes = sync_file(daf_dir / md_name, all_pairs, args.apply)
            for c in changes:
                print(c)
            total_changes += len(changes)

    print(f"\n{'Changes applied' if args.apply else 'Changes that would be made'}: {total_changes}")
    if not args.apply and total_changes > 0:
        print("Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
