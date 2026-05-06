#!/usr/bin/env python3
"""
check_supabase_titles.py — Compare local segmentation display_titles against
the values currently stored in Supabase before uploading.

For each daf, fetches the macro_segment display_titles from Supabase and
compares them with the local 01_segmentation.json. Prints:
  - Titles that changed (the expected result of our --fix work)
  - Any unexpected changes (titles that changed for reasons other than
    adding a rank suffix like "(II)")
  - Dapim present locally but missing from Supabase
  - Dapim present in Supabase but missing locally

Usage:
  python3 check_supabase_titles.py                # full report
  python3 check_supabase_titles.py --unexpected-only   # only flag surprises
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
CONTENT_TABLE = "shiur_content"

RANK_RE = re.compile(r"\s*\((II|III|IV|V|VI|VII|VIII|IX|X|\d+)\)\s*$", re.IGNORECASE)

# Must stay in sync with upload_to_supabase.py _TRACTATE_CANONICAL
_TRACTATE_CANONICAL = {
    "chullin":  "Hullin",
    "hullin":   "Hullin",
    "eruvin":   "Eiruvin",
    "megilah":  "Megillah",
    "megila":   "Megillah",
}


def normalize_masechta(masechta: str) -> str:
    """Normalize masechta to the canonical name stored in Supabase."""
    key = masechta.lower().replace(" ", "_")
    return _TRACTATE_CANONICAL.get(key, masechta)


def fetch_supabase_segmentations() -> dict[str, list[str]]:
    """
    Returns {daf_key: [display_title, ...]} for all rows in Supabase.
    daf_key = "Masechta_daf" matching the local output directory convention.
    """
    if not SUPABASE_KEY:
        print("Error: SUPABASE_SERVICE_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    results = {}
    page_size = 500
    offset = 0

    print("Fetching segmentation data from Supabase...", end="", flush=True)
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/{CONTENT_TABLE}"
            f"?select=tractate,daf,segmentation"
            f"&segmentation=not.is.null"
            f"&order=tractate,daf"
            f"&limit={page_size}&offset={offset}"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        for row in rows:
            seg = row.get("segmentation")
            if not seg:
                continue
            # Supabase returns JSONB as already-parsed dict
            if isinstance(seg, str):
                try:
                    seg = json.loads(seg)
                except json.JSONDecodeError:
                    continue
            macros = seg.get("macro_segments", [])
            titles = [m.get("display_title", "") for m in macros]
            tractate = row["tractate"]
            daf = row["daf"]   # float: 5.0=5a, 5.5=5b
            key = _daf_key(tractate, daf)
            results[key] = titles
        offset += len(rows)
        print(".", end="", flush=True)
        if len(rows) < page_size:
            break

    print(f" {len(results)} rows fetched.")
    return results


def _daf_key(tractate: str, daf) -> str:
    """Stable key for cross-referencing local vs. Supabase."""
    return f"{tractate}|{daf}"


def _local_daf_key(data: dict) -> str:
    masechta = normalize_masechta(data.get("masechta", ""))
    daf_raw  = data.get("daf", 0)
    amud     = (data.get("amud") or "a").lower()
    daf_float = float(daf_raw) + (0.5 if amud == "b" else 0.0)
    return f"{masechta}|{daf_float}"


def is_expected_change(old_title: str, new_title: str) -> bool:
    """
    True if new_title is old_title with a rank suffix added (our --fix work)
    or old_title with trailing "…" replaced by a rank suffix.
    """
    if old_title == new_title:
        return True
    # Strip trailing "…" from old for comparison
    old_base = old_title.rstrip("…").strip()
    new_base = RANK_RE.sub("", new_title).strip()
    # new_base should start with old_base (handles 25-char truncation)
    return new_base.startswith(old_base[:len(new_base)])


def main():
    parser = argparse.ArgumentParser(
        description="Compare local display_titles against Supabase before uploading."
    )
    parser.add_argument("--output-dir", default="./output",
                        help="Local output directory (default: ./output)")
    parser.add_argument("--unexpected-only", action="store_true",
                        help="Print only unexpected changes, not the full expected-change list")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    seg_files  = sorted(output_dir.glob("*/01_segmentation.json"))

    supabase_map = fetch_supabase_segmentations()

    expected_changes  = []
    unexpected_changes = []
    local_only        = []
    supabase_only     = list(supabase_map.keys())

    for seg_file in seg_files:
        try:
            data = json.loads(seg_file.read_text())
        except Exception:
            continue

        local_titles = [m.get("display_title", "")
                        for m in data.get("macro_segments", [])]
        key = _local_daf_key(data)
        label = f"{normalize_masechta(data.get('masechta',''))} {data.get('daf','')}{data.get('amud','') or ''}"

        if key not in supabase_map:
            local_only.append(label)
            continue

        if key in supabase_only:
            supabase_only.remove(key)

        remote_titles = supabase_map[key]

        if local_titles == remote_titles:
            continue

        # Titles differ — classify each changed position
        for i, (loc, rem) in enumerate(zip(local_titles, remote_titles)):
            if loc != rem:
                if is_expected_change(rem, loc):
                    expected_changes.append(f"  {label} [{i}]: '{rem}' → '{loc}'")
                else:
                    unexpected_changes.append(
                        f"  *** {label} [{i}]: remote='{rem}' local='{loc}'"
                    )

        # Length differences
        if len(local_titles) != len(remote_titles):
            unexpected_changes.append(
                f"  *** {label}: local has {len(local_titles)} segments, "
                f"Supabase has {len(remote_titles)}"
            )

    # Report
    print(f"\n{'='*60}")
    print(f"EXPECTED CHANGES (rank suffix added by --fix): {len(expected_changes)}")
    print(f"{'='*60}")
    if not args.unexpected_only:
        for c in expected_changes:
            print(c)
    else:
        print(f"  (use without --unexpected-only to see all {len(expected_changes)} entries)")

    print(f"\n{'='*60}")
    print(f"UNEXPECTED CHANGES: {len(unexpected_changes)}")
    print(f"{'='*60}")
    for c in unexpected_changes:
        print(c)
    if not unexpected_changes:
        print("  None — only rank-suffix renames detected.")

    if local_only:
        print(f"\nLocal only (not in Supabase): {len(local_only)}")
        for l in local_only[:10]:
            print(f"  {l}")
        if len(local_only) > 10:
            print(f"  ... and {len(local_only)-10} more")

    if supabase_only:
        print(f"\nSupabase only (no local output): {len(supabase_only)}")
        for s in supabase_only[:10]:
            print(f"  {s}")


if __name__ == "__main__":
    main()
