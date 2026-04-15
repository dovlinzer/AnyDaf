#!/usr/bin/env python3
"""
Repair out-of-order timestamps in existing segmentation JSON files.

Usage:
  # Fix a single file in place:
  python repair_segmentation.py output/menachot_79/01_segmentation.json

  # Fix all segmentation files under output/:
  python repair_segmentation.py --all

  # Preview changes without writing:
  python repair_segmentation.py --all --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

from pipeline import repair_segmentation


def repair_file(path: Path, dry_run: bool) -> bool:
    raw = path.read_text(encoding='utf-8').strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  SKIP {path}: invalid JSON ({e})")
        return False

    repaired = repair_segmentation(data)
    out = json.dumps(repaired, ensure_ascii=False, indent=2)

    if repaired == data:
        print(f"  OK   {path} (already in order)")
        return True

    print(f"  FIX  {path}")
    if not dry_run:
        path.write_text(out, encoding='utf-8')
    return True


def main():
    parser = argparse.ArgumentParser(description="Repair segmentation JSON timestamp ordering")
    parser.add_argument("files", nargs="*", help="Specific segmentation JSON file(s) to repair")
    parser.add_argument("--all", action="store_true",
                        help="Repair all 01_segmentation.json files under ./output/")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing files")
    args = parser.parse_args()

    if not args.files and not args.all:
        parser.print_help()
        sys.exit(1)

    paths = []
    if args.files:
        paths = [Path(f) for f in args.files]
    if args.all:
        paths += sorted(Path(args.output_dir).rglob("01_segmentation.json"))

    if not paths:
        print("No files found.")
        sys.exit(0)

    for p in paths:
        repair_file(p, args.dry_run)


if __name__ == "__main__":
    main()
