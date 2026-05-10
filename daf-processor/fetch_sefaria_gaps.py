#!/usr/bin/env python3
"""
fetch_sefaria_gaps.py

Reads coverage_gaps.tsv (produced by find_coverage_gaps.py) and fetches
the Sefaria text for each missing daf, storing one JSON file per daf in
./sefaria_gaps/.

The JSON files are the input for upload_sefaria_gaps.py, which uploads
them to shiur_sections with source_type='sefaria'.

Features:
  - Resumable: skips dafs whose JSON file already exists (--force to re-fetch)
  - Rate-limited: 1-second pause between Sefaria API calls
  - Filters: --tractate to fetch a single tractate

Usage:
  python fetch_sefaria_gaps.py                        # fetch all gaps
  python fetch_sefaria_gaps.py --tractate Berakhot    # one tractate only
  python fetch_sefaria_gaps.py --force                # re-fetch even if cached
  python fetch_sefaria_gaps.py --dry-run              # show what would be fetched
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from sefaria import _fetch_amud, _html_to_md, _flatten, MASECHTA_MAP

logger = logging.getLogger(__name__)

GAPS_FILE   = Path(__file__).parent / "coverage_gaps.tsv"
OUTPUT_DIR  = Path(__file__).parent / "sefaria_gaps"

# Sefaria's tractate name may differ from our canonical DB name.
# sefaria.py already normalises most; these handle the remaining mismatches.
DB_TO_SEFARIA: dict[str, str] = {
    "Ta'anit": "Taanit",   # Sefaria uses "Taanit", not "Ta'anit"
}


def slug(tractate: str) -> str:
    """Convert tractate name to a safe filename component: 'Bava Metzia' → 'bava_metzia'"""
    return re.sub(r'\W+', '_', tractate).strip('_').lower()


def gap_file(tractate: str, daf: int) -> Path:
    return OUTPUT_DIR / f"{slug(tractate)}_{daf}.json"


def fetch_daf_segments(tractate: str, daf: int) -> list[dict]:
    """
    Fetch both amudim of a daf from Sefaria.
    Returns a list of segment dicts:
      { segment_index, amud, talmudic_text }
    where talmudic_text is formatted for the TalmudText component:
      Hebrew line (no prefix → rendered right-aligned)
      > English line (blockquote → rendered left-aligned)
    """
    sefaria_name = DB_TO_SEFARIA.get(tractate, tractate)
    segments = []
    idx = 0

    for amud in ("a", "b"):
        # Re-use sefaria.py's internal fetch, which handles Shekalim/Kinnim/Middot
        raw_md = _fetch_amud(sefaria_name, daf, amud)
        if not raw_md:
            continue

        # Parse the markdown produced by _fetch_amud:
        # "**N.**\n*Hebrew/Aramaic:* he\n*Translation:* en\n"
        for block in re.split(r'\*\*\d+\.\*\*\n?', raw_md):
            block = block.strip()
            if not block or block.startswith("###"):
                continue

            he_match = re.search(r'\*Hebrew/Aramaic:\*\s*(.*?)(?:\n|$)', block, re.DOTALL)
            en_match = re.search(r'\*Translation:\*\s*(.*?)(?:\n|$)',     block, re.DOTALL)

            he = he_match.group(1).strip() if he_match else ""
            en = en_match.group(1).strip() if en_match else ""

            if not he and not en:
                continue

            # Format for TalmudText: Hebrew on plain line (right-aligned),
            # English on blockquote line (left-aligned)
            parts = []
            if he:
                parts.append(he)
            if en:
                parts.append(f"> {en}")
            talmudic_text = "\n".join(parts)

            segments.append({
                "segment_index": idx,
                "amud": amud,
                "talmudic_text": talmudic_text,
            })
            idx += 1

        # Polite pause between the two amud fetches
        time.sleep(0.5)

    return segments


def load_gaps(tractate_filter: str | None) -> list[tuple[str, int]]:
    if not GAPS_FILE.exists():
        raise FileNotFoundError(
            f"{GAPS_FILE} not found — run find_coverage_gaps.py first"
        )
    gaps = []
    with open(GAPS_FILE) as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            tractate, daf = parts[0], int(parts[1])
            if tractate_filter and tractate.lower() != tractate_filter.lower():
                continue
            gaps.append((tractate, daf))
    return gaps


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Sefaria text for gap dafs and store in sefaria_gaps/"
    )
    parser.add_argument("--tractate", default=None,
                        help="Limit to one tractate (case-insensitive)")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch even if JSON file already exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be fetched without making API calls")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    OUTPUT_DIR.mkdir(exist_ok=True)

    gaps = load_gaps(args.tractate)
    logger.info(f"{len(gaps)} dafs to process")

    skipped = fetched = failed = 0

    for tractate, daf in gaps:
        out = gap_file(tractate, daf)

        if out.exists() and not args.force:
            logger.debug(f"  skip {tractate} {daf} (already fetched)")
            skipped += 1
            continue

        label = f"{tractate} {daf}"

        if args.dry_run:
            print(f"  [DRY RUN] Would fetch {label} → {out.name}")
            continue

        logger.info(f"  fetching {label}…")
        try:
            segments = fetch_daf_segments(tractate, daf)
        except Exception as e:
            logger.error(f"  ✗ {label}: {e}")
            failed += 1
            time.sleep(2)
            continue

        if not segments:
            logger.warning(f"  ✗ {label}: no segments returned (Sefaria may not have this daf)")
            failed += 1
            time.sleep(1)
            continue

        payload = {
            "tractate":    tractate,
            "daf":         daf,
            "source_type": "sefaria",
            "fetched_at":  datetime.now(timezone.utc).isoformat(),
            "segments":    segments,
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  ✓ {label}: {len(segments)} segments → {out.name}")
        fetched += 1

        time.sleep(1)  # be polite to Sefaria

    if not args.dry_run:
        print(f"\nDone: {fetched} fetched, {skipped} skipped, {failed} failed")
        print(f"Files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
