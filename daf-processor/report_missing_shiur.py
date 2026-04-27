#!/usr/bin/env python3
"""
Report audio episodes that have no shiur content (final pass).

Output example:
  Berakhot   2a-5b, 27a, 30a-38b
  Shabbat    100b-102a
  ...

Usage:
  python report_missing_shiur.py                  # missing final
  python report_missing_shiur.py --any            # missing any of: segmentation, rewrite, final
  python report_missing_shiur.py --field rewrite  # missing a specific field
  python report_missing_shiur.py --condense       # bridge over dafs absent from episode_audio
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL     = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY     = os.environ.get("SUPABASE_SERVICE_KEY", "")
PAGE_SIZE        = 1000

# Seder order for tractate sorting (approximate canonical sequence)
SEDER_ORDER = [
    "Berakhot",
    "Shabbat","Eiruvin","Pesachim","Shekalim","Yoma","Sukkah","Beitzah",
    "Rosh Hashanah","Ta\u2019anit","Megillah","Moed Katan","Chagigah",
    "Yevamot","Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin",
    "Bava Kamma","Bava Metzia","Bava Batra","Sanhedrin","Makkot",
    "Shevuot","Avodah Zarah","Horayot",
    "Zevachim","Menachot","Chullin","Bekhorot","Arakhin","Temurah",
    "Keritot","Meilah","Niddah",
]
SEDER_RANK = {t: i for i, t in enumerate(SEDER_ORDER)}

# Normalize variant spellings that appear inconsistently across tables
_NORMALIZE: dict[str, str] = {
    "Megilah":     "Megillah",
    "Megila":      "Megillah",
    "Megilah":     "Megillah",
    "Hullin":      "Chullin",
    "Eruvin":      "Eiruvin",
}

def normalize_tractate(name: str) -> str:
    return _NORMALIZE.get(name, name)


def headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }


def fetch_all(table: str, select: str, filters: str = "") -> list[dict]:
    """Paginate through all rows of a Supabase table."""
    rows = []
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}{filters}&limit={PAGE_SIZE}&offset={offset}"
        resp = requests.get(url, headers=headers(), timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def daf_to_int(daf: float) -> int:
    """Convert numeric daf to a sequential integer for range detection."""
    return round(daf * 2)  # 5.0 → 10, 5.5 → 11, 6.0 → 12 …


def int_to_daf_str(n: int, has_half_dafs: bool) -> str:
    """Convert sequential integer back to a display string."""
    daf_num = n / 2
    if daf_num == int(daf_num):
        return str(int(daf_num))
    return f"{int(daf_num)}b"


def compress_ranges(daf_floats: list[float]) -> str:
    """
    Compress a sorted list of daf values into a compact range string.
    E.g. [5.0, 5.5, 6.0, 6.5, 7.0, 9.5, 10.0] → "5a-7a, 9b-10a"
    If no .5 values exist anywhere, omit the a/b suffix entirely.
    """
    if not daf_floats:
        return ""

    has_half = any(d != int(d) for d in daf_floats)
    ints = sorted(daf_to_int(d) for d in daf_floats)
    # Whole dafs multiply by 2, so consecutive whole dafs differ by 2, not 1.
    step = 1 if has_half else 2

    ranges = []
    start = ints[0]
    prev  = ints[0]
    for n in ints[1:]:
        if n == prev + step:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    ranges.append((start, prev))

    parts = []
    for s, e in ranges:
        if s == e:
            parts.append(int_to_daf_str(s, has_half))
        else:
            parts.append(f"{int_to_daf_str(s, has_half)}-{int_to_daf_str(e, has_half)}")
    return ", ".join(parts)


def condense_ranges(missing_dafs: set[float], all_audio_dafs: list[float]) -> str:
    """
    Like compress_ranges, but bridges over dafs absent from episode_audio entirely.
    A range ends only when a daf that IS in episode_audio also IS in shiur_content.

    E.g. audio=[2,5,6,7], shiur={5}, missing={2,6,7} → "2, 6-7"
    E.g. audio=[2,5,6,7], shiur={},  missing={2,5,6,7} → "2-7"  (gap at 3,4 bridged)
    """
    if not missing_dafs:
        return ""

    has_half = any(d != int(d) for d in all_audio_dafs)

    def fmt(d: float) -> str:
        return str(int(d)) if d == int(d) else f"{int(d)}b"

    sorted_audio = sorted(all_audio_dafs)
    ranges: list[tuple[float, float]] = []
    run_start: float | None = None
    run_end:   float | None = None

    for daf in sorted_audio:
        if daf in missing_dafs:
            if run_start is None:
                run_start = daf
            run_end = daf
        else:
            # This daf is covered — close the current run if open
            if run_start is not None:
                ranges.append((run_start, run_end))
                run_start = run_end = None

    if run_start is not None:
        ranges.append((run_start, run_end))

    parts = []
    for s, e in ranges:
        parts.append(fmt(s) if s == e else f"{fmt(s)}-{fmt(e)}")
    return ", ".join(parts)


def tractate_sort_key(name: str) -> tuple:
    return (SEDER_RANK.get(name, 999), name)


def main():
    parser = argparse.ArgumentParser(description="Report audio episodes missing shiur content.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--any", action="store_true",
                       help="Report episodes missing any shiur field (segmentation, rewrite, or final)")
    group.add_argument("--field", choices=["segmentation", "rewrite", "final"], default="final",
                       help="Which field to check (default: final)")
    parser.add_argument("--condense", action="store_true",
                        help="Bridge over dafs absent from episode_audio; show the outer span of each missing run")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        sys.exit("Error: SUPABASE_SERVICE_KEY not set")

    # Fetch all audio episodes
    print("Fetching episode_audio…", end=" ", flush=True)
    audio_rows = fetch_all("episode_audio", "tractate,daf")
    print(f"{len(audio_rows)} episodes")

    audio_set: set[tuple[str, float]] = {
        (normalize_tractate(r["tractate"]), float(r["daf"])) for r in audio_rows
    }

    # Keep per-tractate sorted daf lists for --condense mode
    audio_by_tractate: dict[str, list[float]] = defaultdict(list)
    for tractate, daf in audio_set:
        audio_by_tractate[tractate].append(daf)

    # Fetch shiur_content rows that have the required field(s)
    print("Fetching shiur_content…", end=" ", flush=True)
    if args.any:
        # Any row that has ALL three fields populated
        filters = "&segmentation=not.is.null&rewrite=not.is.null&final=not.is.null"
        check_label = "segmentation + rewrite + final"
    else:
        field = args.field
        filters = f"&{field}=not.is.null"
        check_label = field

    shiur_rows = fetch_all("shiur_content", "tractate,daf", filters)
    print(f"{len(shiur_rows)} rows with {check_label}")

    shiur_set: set[tuple[str, float]] = {
        (normalize_tractate(r["tractate"]), float(r["daf"])) for r in shiur_rows
    }

    missing = audio_set - shiur_set

    if not missing:
        print(f"\nAll {len(audio_set)} episodes have {check_label}. Nothing to do!")
        return

    # Group by tractate
    by_tractate: dict[str, list[float]] = defaultdict(list)
    for tractate, daf in missing:
        by_tractate[tractate].append(daf)

    total_missing = sum(len(v) for v in by_tractate.values())
    print(f"\nMissing {check_label}: {total_missing} / {len(audio_set)} episodes\n")

    col_width = max(len(t) for t in by_tractate) + 2
    for tractate in sorted(by_tractate, key=tractate_sort_key):
        dafs = sorted(by_tractate[tractate])
        if args.condense:
            range_str = condense_ranges(set(dafs), audio_by_tractate[tractate])
        else:
            range_str = compress_ranges(dafs)
        print(f"  {tractate:<{col_width}}{range_str}")

    print()


if __name__ == "__main__":
    main()
