#!/usr/bin/env python3
"""
Cross-reference missing shiurim against local .srt files.

Finds episodes that:
  (a) are in episode_audio
  (b) are NOT in shiur_content (missing the target field)
  (c) DO have a matching .srt file on disk

These are candidates for (re-)processing through the pipeline.

Usage:
  python check_srt_coverage.py                          # check srt/processed/
  python check_srt_coverage.py --srt-dir path/to/srts  # custom directory
  python check_srt_coverage.py --field rewrite          # check a different field
  python check_srt_coverage.py --any                    # all three passes must exist
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PAGE_SIZE    = 1000

DEFAULT_SRT_DIR = Path(__file__).parent / "srt" / "processed"

# Filename pattern: "Tractate Name 42.srt", "Tractate Name 42b.srt", "Tractate Name 42a.srt"
SRT_RE = re.compile(r"^(.+?) (\d+)(a|b)?\.srt$", re.IGNORECASE)


def headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }


def fetch_all(table: str, select: str, filters: str = "") -> list[dict]:
    rows, offset = [], 0
    while True:
        url = (f"{SUPABASE_URL}/rest/v1/{table}"
               f"?select={select}{filters}&limit={PAGE_SIZE}&offset={offset}")
        resp = requests.get(url, headers=headers(), timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def parse_srt_filename(filename: str) -> tuple[str, float] | None:
    """
    Parse an SRT filename into (tractate, daf_float).
    Returns None if the filename doesn't match the expected pattern.

      "Berakhot 11.srt"  → ("Berakhot", 11.0)   # whole daf / amud aleph
      "Berakhot 11a.srt" → ("Berakhot", 11.0)   # explicit amud aleph
      "Berakhot 11b.srt" → ("Berakhot", 11.5)   # amud bet
    """
    m = SRT_RE.match(filename)
    if not m:
        return None
    tractate = m.group(1)
    daf_int  = int(m.group(2))
    suffix   = (m.group(3) or "").lower()
    daf      = daf_int + (0.5 if suffix == "b" else 0.0)
    return tractate, daf


def scan_srt_dir(srt_dir: Path) -> dict[tuple[str, float], Path]:
    """Return a mapping of (tractate, daf) → srt file path for all .srt files found."""
    result: dict[tuple[str, float], Path] = {}
    if not srt_dir.is_dir():
        sys.exit(f"Error: SRT directory not found: {srt_dir}")
    for f in srt_dir.iterdir():
        if f.suffix.lower() != ".srt":
            continue
        parsed = parse_srt_filename(f.name)
        if parsed is None:
            continue
        key = parsed
        if key in result:
            print(f"  Warning: duplicate SRT for {key[0]} {key[1]}: {f.name} vs {result[key].name}")
        result[key] = f
    return result


def daf_str(daf: float) -> str:
    if daf == int(daf):
        return str(int(daf))
    return f"{int(daf)}b"


def main():
    parser = argparse.ArgumentParser(
        description="Find missing shiurim that already have local .srt files."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--any", action="store_true",
                       help="Require all three fields (segmentation, rewrite, final)")
    group.add_argument("--field", choices=["segmentation", "rewrite", "final"], default="final",
                       help="Which shiur_content field to check (default: final)")
    parser.add_argument("--srt-dir", type=Path, default=DEFAULT_SRT_DIR,
                        help=f"Directory to scan for .srt files (default: {DEFAULT_SRT_DIR})")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        sys.exit("Error: SUPABASE_SERVICE_KEY not set")

    # 1. Scan SRT files on disk
    print(f"Scanning {args.srt_dir} …", end=" ", flush=True)
    srt_map = scan_srt_dir(args.srt_dir)
    print(f"{len(srt_map)} .srt files found")

    # 2. Fetch all audio episodes from Supabase
    print("Fetching episode_audio …", end=" ", flush=True)
    audio_rows = fetch_all("episode_audio", "tractate,daf")
    audio_set: set[tuple[str, float]] = {
        (r["tractate"], float(r["daf"])) for r in audio_rows
    }
    print(f"{len(audio_set)} episodes")

    # 3. Fetch shiur_content rows that already have the target field
    print("Fetching shiur_content …", end=" ", flush=True)
    if args.any:
        filters = "&segmentation=not.is.null&rewrite=not.is.null&final=not.is.null"
        check_label = "segmentation + rewrite + final"
    else:
        filters = f"&{args.field}=not.is.null"
        check_label = args.field

    shiur_rows = fetch_all("shiur_content", "tractate,daf", filters)
    shiur_set: set[tuple[str, float]] = {
        (r["tractate"], float(r["daf"])) for r in shiur_rows
    }
    print(f"{len(shiur_set)} rows with {check_label}")

    # 4. Compute missing episodes
    missing = audio_set - shiur_set

    # 5. Intersect with available SRTs
    ready = [(tractate, daf, srt_map[(tractate, daf)])
             for (tractate, daf) in missing
             if (tractate, daf) in srt_map]

    if not ready:
        print(f"\nNo missing shiurim have a local .srt file. Nothing ready to process.")
        return

    # Group by tractate, sort by daf
    by_tractate: dict[str, list[tuple[float, Path]]] = defaultdict(list)
    for tractate, daf, path in ready:
        by_tractate[tractate].append((daf, path))

    total = sum(len(v) for v in by_tractate.values())
    print(f"\n{total} missing shiurim have a local .srt (missing {check_label}):\n")

    col_width = max(len(t) for t in by_tractate) + 2
    for tractate in sorted(by_tractate):
        entries = sorted(by_tractate[tractate])
        daf_list = ", ".join(daf_str(d) for d, _ in entries)
        print(f"  {tractate:<{col_width}}{daf_list}")

    # Also print unmatched SRTs: srt files for dafs that aren't in episode_audio at all
    orphaned = [
        (tractate, daf, path)
        for (tractate, daf), path in sorted(srt_map.items())
        if (tractate, daf) not in audio_set
    ]
    if orphaned:
        print(f"\n{len(orphaned)} .srt file(s) don't match any episode_audio row "
              "(tractate name mismatch or daf not in database):")
        for tractate, daf, path in orphaned:
            print(f"  {path.name}")


if __name__ == "__main__":
    main()
