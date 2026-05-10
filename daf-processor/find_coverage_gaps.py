#!/usr/bin/env python3
"""
find_coverage_gaps.py

Compares the known daf ranges for every tractate (mirroring allTractates in
AnyDaf/Tractate.swift) against the dafs present in shiur_content, and reports
which dafs have no shiur coverage.

These are candidates for Sefaria gap-fill in shiur_sections.

Output:
  - Per-tractate coverage summary printed to stdout
  - coverage_gaps.tsv  — tab-separated: tractate, daf_float, daf_label
    (one row per missing daf, for use by the future gap-fill upload script)

Usage:
  python find_coverage_gaps.py
  python find_coverage_gaps.py --tractate Pesachim   # single tractate
"""

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# ---------------------------------------------------------------------------
# Tractate definitions — mirrors allTractates in AnyDaf/Tractate.swift
# (name, startDaf, endDaf, startAmud)  startAmud: 0=aleph, 1=bet
# ---------------------------------------------------------------------------
ALL_TRACTATES = [
    # Seder Zeraim
    ("Berakhot",      2,   64,  0),
    # Seder Moed
    ("Shabbat",       2,  157,  0),
    ("Eiruvin",       2,  105,  0),
    ("Pesachim",      2,  121,  0),
    ("Shekalim",      2,   22,  0),
    ("Rosh Hashanah", 2,   35,  0),
    ("Yoma",          2,   88,  0),
    ("Sukkah",        2,   56,  0),
    ("Beitzah",       2,   40,  0),
    ("Ta'anit",       2,   31,  0),
    ("Megillah",      2,   32,  0),
    ("Moed Katan",    2,   29,  0),
    ("Chagigah",      2,   27,  0),
    # Seder Nashim
    ("Yevamot",       2,  122,  0),
    ("Ketubot",       2,  112,  0),
    ("Nedarim",       2,   91,  0),
    ("Nazir",         2,   66,  0),
    ("Sotah",         2,   49,  0),
    ("Gittin",        2,   90,  0),
    ("Kiddushin",     2,   82,  0),
    # Seder Nezikin
    ("Bava Kamma",    2,  119,  0),
    ("Bava Metzia",   2,  119,  0),
    ("Bava Batra",    2,  176,  0),
    ("Sanhedrin",     2,  113,  0),
    ("Makkot",        2,   24,  0),
    ("Shevuot",       2,   49,  0),
    ("Avodah Zarah",  2,   76,  0),
    ("Horayot",       2,   14,  0),
    # Seder Kodashim
    ("Zevachim",      2,  120,  0),
    ("Menachot",      2,  110,  0),
    ("Hullin",        2,  142,  0),
    ("Bekhorot",      2,   61,  0),
    ("Arakhin",       2,   34,  0),
    ("Temurah",       2,   34,  0),
    ("Keritot",       2,   28,  0),
    ("Meilah",        2,   22,  0),
    ("Kinnim",       22,   25,  0),
    ("Tamid",        25,   33,  1),  # starts at 25b
    ("Middot",       34,   37,  0),
    # Seder Taharot
    ("Niddah",        2,   73,  0),
]

# Normalize alternate DB spellings to canonical names used above.
# shiur_content has both "Taanit" and "Ta'anit" due to inconsistent uploads.
DB_NAME_ALIASES: dict[str, str] = {
    "Taanit":  "Ta'anit",
    "Tamud":   "Tamid",   # just in case
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def daf_to_float(daf_num: int, amud: int) -> float:
    """2, 0 → 2.0 (2a);  2, 1 → 2.5 (2b)"""
    return float(daf_num) + (0.5 if amud else 0.0)


def float_to_label(daf: float) -> str:
    """2.0 → '2a';  2.5 → '2b'"""
    base = int(daf)
    return f"{base}b" if daf % 1 else f"{base}a"


def expected_daf_numbers(entry: tuple) -> list[int]:
    """Return every daf page number for a tractate (one per blatt, not per amud side)."""
    name, start_daf, end_daf, start_amud = entry
    return list(range(start_daf, end_daf + 1))


# ---------------------------------------------------------------------------
# Supabase fetch
# ---------------------------------------------------------------------------

def fetch_covered_dafs() -> set[tuple[str, int]]:
    """Return set of (canonical_tractate_name, daf_number) present in shiur_content.

    A daf is covered if ANY row exists for that daf number — whether it's the
    whole daf (11.0 alone), just the aleph side (11.0 when 11.5 also exists),
    or just the bet side (11.5). We group by floor(daf) so that both 11.0 and
    11.5 map to daf number 11.
    """
    covered: set[tuple[str, int]] = set()
    offset = 0
    limit = 1000
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/shiur_content",
            headers=HEADERS,
            params={"select": "tractate,daf", "limit": str(limit), "offset": str(offset)},
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        for row in rows:
            daf = float(row["daf"])
            # Only mark covered if the .0 entry exists.
            # .0 alone = full daf (both sides) or at least the a-side.
            # .5 alone = only the b-side → a-side is missing → still a gap.
            # When we find such a gap we'll just fetch the whole daf from
            # Sefaria — the b-side overlap is harmless.
            if daf % 1 == 0:
                name = DB_NAME_ALIASES.get(row["tractate"], row["tractate"])
                covered.add((name, int(daf)))
        if len(rows) < limit:
            break
        offset += limit
    return covered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Find daf coverage gaps vs shiur_content")
    parser.add_argument("--tractate", default=None,
                        help="Limit report to one tractate (case-sensitive)")
    args = parser.parse_args()

    print("Fetching covered dafs from shiur_content…")
    covered = fetch_covered_dafs()
    print(f"  {len(covered)} daf-sides with shiur coverage.\n")

    tractates = [t for t in ALL_TRACTATES if args.tractate is None or t[0] == args.tractate]
    if args.tractate and not tractates:
        print(f"Unknown tractate: {args.tractate}", file=sys.stderr)
        sys.exit(1)

    total_expected = total_covered = total_gaps = 0
    all_gaps: list[tuple[str, float, str]] = []

    print(f"  {'Tractate':<20}  {'Covered':>8}  {'Total':>6}  {'Pct':>5}  Missing")
    print(f"  {'-'*20}  {'-'*8}  {'-'*6}  {'-'*5}  -------")

    for entry in tractates:
        name = entry[0]
        daf_nums = expected_daf_numbers(entry)
        gaps = [(name, d) for d in daf_nums if (name, d) not in covered]
        n_covered = len(daf_nums) - len(gaps)
        pct = 100 * n_covered // len(daf_nums) if daf_nums else 0

        total_expected += len(daf_nums)
        total_covered  += n_covered
        total_gaps     += len(gaps)
        all_gaps.extend(gaps)

        gap_note = "" if not gaps else f"{len(gaps)} missing"
        print(f"  {name:<20}  {n_covered:>8}  {len(daf_nums):>6}  {pct:>4}%  {gap_note}")

    print(f"\n  {'TOTAL':<20}  {total_covered:>8}  {total_expected:>6}  "
          f"{100*total_covered//total_expected:>4}%  {total_gaps} gaps\n")

    if not all_gaps:
        print("No gaps found — full coverage!")
        return

    # Machine-readable TSV for the gap-fill upload script
    tsv_path = Path(__file__).parent / "coverage_gaps.tsv"
    with open(tsv_path, "w") as f:
        f.write("tractate\tdaf\n")
        for tractate, daf in all_gaps:
            f.write(f"{tractate}\t{daf}\n")

    # Human-readable report grouped by tractate
    # Group gaps by tractate (preserving Talmud order from all_gaps)
    from itertools import groupby
    txt_path = Path(__file__).parent / "coverage_gaps.txt"
    with open(txt_path, "w") as f:
        f.write("COVERAGE GAPS — dapim with no shiur in shiur_content\n")
        f.write("=" * 60 + "\n\n")
        for tractate, group in groupby(all_gaps, key=lambda x: x[0]):
            daf_nums = [str(d) for _, d in group]
            f.write(f"{tractate} ({len(daf_nums)} missing):\n")
            # Wrap at 20 per line
            for i in range(0, len(daf_nums), 20):
                f.write("  " + ", ".join(daf_nums[i:i+20]) + "\n")
            f.write("\n")
        f.write(f"Total: {total_gaps} missing dapim\n")

    print(f"Machine-readable: {tsv_path}")
    print(f"Human-readable:   {txt_path}")
    print(f"\n{total_gaps} missing dapim — each = one full daf to fetch from Sefaria.")


if __name__ == "__main__":
    main()
