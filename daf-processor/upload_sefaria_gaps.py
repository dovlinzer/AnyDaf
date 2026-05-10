#!/usr/bin/env python3
"""
upload_sefaria_gaps.py

Reads JSON files from ./sefaria_gaps/ (produced by fetch_sefaria_gaps.py)
and uploads their segments to shiur_sections with source_type='sefaria'.

Each JSON file covers one daf (both amudim).  Before upserting the new rows,
existing sefaria rows for that (tractate, daf) are deleted so re-runs are safe.

Features:
  - Resumable: --skip-existing skips dafs already present in the DB
  - Dry-run: shows what would be uploaded without writing anything
  - Tractate filter: --tractate to upload one tractate only

Usage:
  python upload_sefaria_gaps.py                         # upload all gap JSONs
  python upload_sefaria_gaps.py --tractate Berakhot     # one tractate only
  python upload_sefaria_gaps.py --dry-run               # preview only
  python upload_sefaria_gaps.py --skip-existing         # skip already-uploaded dafs
  python upload_sefaria_gaps.py --force                 # re-upload even if in DB
"""

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger(__name__)

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY   = os.environ["SUPABASE_SERVICE_KEY"]
SECTIONS_TABLE = "shiur_sections"
GAPS_DIR       = Path(__file__).parent / "sefaria_gaps"

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _request(method: str, url: str, *, retries: int = 6, **kwargs):
    """HTTP request with exponential backoff on connection/DNS errors."""
    for attempt in range(retries):
        try:
            return requests.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise
            wait = 2.0 * (2 ** attempt)
            logger.warning(f"  Network error (attempt {attempt + 1}/{retries}), "
                           f"retrying in {wait:.0f}s: {e}")
            time.sleep(wait)


def fetch_existing_sefaria_dafs() -> set[tuple[str, int]]:
    """
    Return set of (tractate, daf_int) already present in shiur_sections
    with source_type='sefaria'.
    """
    existing: set[tuple[str, int]] = set()
    offset = 0
    limit  = 1000
    while True:
        r = _request(
            "GET",
            f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}",
            headers=HEADERS,
            params={
                "select":      "tractate,daf",
                "source_type": "eq.sefaria",
                "limit":       str(limit),
                "offset":      str(offset),
            },
            timeout=30,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        for row in rows:
            daf = float(row["daf"])
            existing.add((row["tractate"], int(daf)))
        if len(rows) < limit:
            break
        offset += limit
    return existing


def delete_sefaria_rows(tractate: str, daf_int: int, dry_run: bool) -> bool:
    """Delete all sefaria rows for this (tractate, daf floor)."""
    if dry_run:
        print(f"  [DRY RUN] Would delete sefaria rows for {tractate} {daf_int}")
        return True
    # Delete rows where daf is either daf_int.0 or daf_int.5
    for daf_float in (float(daf_int), float(daf_int) + 0.5):
        url = (
            f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}"
            f"?tractate=eq.{requests.utils.quote(tractate)}"
            f"&daf=eq.{daf_float}"
            f"&source_type=eq.sefaria"
        )
        r = _request("DELETE", url, headers=HEADERS, timeout=30)
        if r.status_code not in (200, 204):
            logger.error(f"  ✗ delete {tractate} {daf_int}: HTTP {r.status_code} — {r.text[:200]}")
            return False
    return True


def upsert_rows(rows: list[dict], label: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(rows)} rows → {label}")
        return True
    h = {**HEADERS, "Prefer": "resolution=merge-duplicates"}
    r = _request(
        "POST",
        f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}",
        headers=h,
        json=rows,
        timeout=60,
    )
    if r.status_code in (200, 201):
        return True
    logger.error(f"  ✗ upsert {label}: HTTP {r.status_code} — {r.text[:300]}")
    return False


# ---------------------------------------------------------------------------
# Daf float encoding
# ---------------------------------------------------------------------------

def amud_to_daf_float(daf_int: int, amud: str) -> float:
    """'a' → daf_int + 0.0,  'b' → daf_int + 0.5"""
    return float(daf_int) + (0.5 if amud == "b" else 0.0)


# ---------------------------------------------------------------------------
# Build rows from gap JSON
# ---------------------------------------------------------------------------

def build_rows_from_gap(payload: dict) -> list[dict]:
    """
    Convert a sefaria_gaps JSON payload into shiur_sections rows.

    Each segment is a separate row. The daf float is set per amud:
      amud 'a'  → daf_int + 0.0
      amud 'b'  → daf_int + 0.5

    segment_index is global within the daf (already set correctly by fetch script).
    """
    tractate = payload["tractate"]
    daf_int  = int(payload["daf"])
    rows = []
    for seg in payload.get("segments", []):
        daf_float = amud_to_daf_float(daf_int, seg["amud"])
        rows.append({
            "tractate":             tractate,
            "daf":                  daf_float,
            "segment_index":        seg["segment_index"],
            "parent_segment_index": None,
            "title":                None,
            "timestamp_mm_ss":      None,
            "timestamp_secs":       None,
            "talmudic_text":        seg["talmudic_text"] or None,
            "source_type":          "sefaria",
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Upload sefaria_gaps/ JSON files to shiur_sections"
    )
    parser.add_argument("--tractate", default=None,
                        help="Limit to one tractate (case-insensitive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be uploaded without writing")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip dafs already present in the DB (default: re-upload)")
    parser.add_argument("--force", action="store_true",
                        help="Alias for NOT --skip-existing (re-upload even if present)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not GAPS_DIR.exists():
        print(f"ERROR: {GAPS_DIR} not found — run fetch_sefaria_gaps.py first")
        return

    gap_files = sorted(GAPS_DIR.glob("*.json"))
    if args.tractate:
        # Filter by tractate name embedded in the filename
        pat = re.compile(re.sub(r'\W+', '_', args.tractate).strip('_').lower(), re.IGNORECASE)
        gap_files = [f for f in gap_files if pat.match(f.stem)]

    logger.info(f"{len(gap_files)} gap JSON file(s) to process")

    # Optionally pre-fetch which dafs are already uploaded
    existing: set[tuple[str, int]] = set()
    if args.skip_existing and not args.dry_run:
        logger.info("Fetching existing sefaria rows from DB…")
        existing = fetch_existing_sefaria_dafs()
        logger.info(f"  {len(existing)} daf(s) already in DB")

    uploaded = skipped = failed = 0

    for gap_file in gap_files:
        payload = json.loads(gap_file.read_text(encoding="utf-8"))
        tractate = payload["tractate"]
        daf_int  = int(payload["daf"])
        label    = f"{tractate} {daf_int}"

        if args.skip_existing and (tractate, daf_int) in existing:
            logger.debug(f"  skip {label} (already uploaded)")
            skipped += 1
            continue

        rows = build_rows_from_gap(payload)
        if not rows:
            logger.warning(f"  ✗ {label}: no segments in file — skipping")
            failed += 1
            continue

        logger.info(f"  uploading {label}: {len(rows)} segment(s)…")

        # Delete old sefaria rows for this daf before upserting
        if not delete_sefaria_rows(tractate, daf_int, args.dry_run):
            failed += 1
            continue

        # Group rows by daf_float for cleaner upsert batches (optional — upsert all at once)
        if not upsert_rows(rows, label, args.dry_run):
            failed += 1
            continue

        logger.info(f"  ✓ {label}")
        uploaded += 1

    if not args.dry_run:
        print(f"\nDone: {uploaded} uploaded, {skipped} skipped, {failed} failed")
    else:
        print(f"\n[DRY RUN] Would upload {len(gap_files)} daf(s).")


if __name__ == "__main__":
    main()
