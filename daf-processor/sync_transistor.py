#!/usr/bin/env python3
"""
Sync Transistor audio URLs from the transfer spreadsheet to Supabase episode_audio.

Reads a Google Sheet (CSV export) that maps tractate + daf → Transistor URL,
then upserts those URLs into the episode_audio table (tractate, daf, audio_url).

Rows where "Daf number" == 0 are invalid placeholders and are skipped.

The sheet is expected to be publicly readable (no auth required).

Required env vars:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key (bypasses RLS)

Usage:
  python sync_transistor.py                    # upsert all rows from sheet
  python sync_transistor.py --dry-run          # preview without writing
  python sync_transistor.py --sheet-id ID      # override spreadsheet ID
"""

import argparse
import csv
import io
import logging
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SHEET_ID      = "1WfsQMuSU2fVaAuEqQwpQDD6h_xB9zPqO53oVwqKuMmI"
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
EPISODE_TABLE = "episode_audio"

# Spelling variants found in the sheet → canonical Supabase tractate name.
# Extend this dict if new variants appear.
_ALIASES: dict[str, str] = {
    "ta'anit":     "Ta\u2019anit",
    "taanit":      "Ta\u2019anit",
    "moed katan":  "Moed Katan",
    "ketuvot":     "Ketubot",
    "ketubot":     "Ketubot",
    "avodah zara": "Avodah Zarah",
    "avoda zarah": "Avodah Zarah",
    "avoda zara":  "Avodah Zarah",
    "menahot":     "Menachot",
    "me'ilah":     "Meilah",
    "meilah":      "Meilah",
    "peschim":     "Pesachim",
    "rosh hashana": "Rosh Hashanah",
}


def normalize_tractate(raw: str) -> str:
    """Title-case and apply alias corrections to a raw tractate name from the sheet."""
    cleaned = raw.strip()
    lower = cleaned.lower()
    if lower in _ALIASES:
        return _ALIASES[lower]
    # Title-case as a fallback (handles "berakhot" → "Berakhot")
    return cleaned.title()


def fetch_sheet_rows(sheet_id: str) -> list[dict]:
    """Download the Google Sheet as CSV and return parsed rows."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    logger.info(f"Fetching sheet: {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch sheet: {e}")
        sys.exit(1)

    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


def parse_rows(raw_rows: list[dict]) -> list[dict]:
    """
    Parse and validate sheet rows.
    Returns list of {"tractate": str, "daf": float, "audio_url": str}.
    Skips rows with daf_number == 0 or missing/invalid data.
    """
    results = []
    skipped_zero = 0
    skipped_invalid = 0

    for row in raw_rows:
        # Sheet columns: Massechet, Daf, Link, Daf number
        raw_tractate  = (row.get("Massechet") or "").strip()
        raw_link      = (row.get("Link") or "").strip()
        raw_daf_num   = (row.get("Daf number") or "").strip()

        if not raw_tractate or not raw_link or not raw_daf_num:
            skipped_invalid += 1
            continue

        try:
            daf_num = float(raw_daf_num)
        except ValueError:
            logger.warning(f"  Skipping row with non-numeric daf: {row}")
            skipped_invalid += 1
            continue

        if daf_num == 0:
            skipped_zero += 1
            continue

        tractate = normalize_tractate(raw_tractate)
        results.append({"tractate": tractate, "daf": daf_num, "audio_url": raw_link})

    logger.info(
        f"Parsed {len(results)} valid rows "
        f"({skipped_zero} skipped as daf=0, {skipped_invalid} skipped as invalid)"
    )
    return results


def upsert_rows(rows: list[dict], service_key: str, dry_run: bool) -> tuple[int, int]:
    """Upsert rows to Supabase. Returns (succeeded, failed)."""
    if not rows:
        logger.warning("No rows to upsert.")
        return 0, 0

    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(rows)} rows to {EPISODE_TABLE}:")
        for r in rows:
            logger.info(f"  {r['tractate']} {r['daf']} → {r['audio_url']}")
        return len(rows), 0

    batch_size = 500
    succeeded = failed = 0
    url = f"{SUPABASE_URL}/rest/v1/{EPISODE_TABLE}?on_conflict=tractate,daf"
    headers = {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates",
    }

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            resp = requests.post(url, headers=headers, json=batch, timeout=60)
            if resp.status_code in (200, 201):
                succeeded += len(batch)
                logger.info(f"  ✓ Upserted rows {i+1}–{i+len(batch)}")
            else:
                failed += len(batch)
                logger.error(
                    f"  ✗ Batch {i+1}–{i+len(batch)}: "
                    f"HTTP {resp.status_code} — {resp.text[:300]}"
                )
        except Exception as e:
            failed += len(batch)
            logger.error(f"  ✗ Batch {i+1}–{i+len(batch)} network error: {e}")

    return succeeded, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Transistor URLs from Google Sheet to Supabase episode_audio"
    )
    parser.add_argument("--dry-run",  action="store_true",
                        help="Fetch and parse but do not write to Supabase")
    parser.add_argument("--sheet-id", default=SHEET_ID,
                        help="Google Sheet ID (default: hardcoded transfer sheet)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not service_key and not args.dry_run:
        logger.error("SUPABASE_SERVICE_KEY not set.")
        return 1

    raw_rows = fetch_sheet_rows(args.sheet_id)
    rows = parse_rows(raw_rows)

    logger.info(f"Upserting {len(rows)} Transistor URLs to Supabase…")
    succeeded, failed = upsert_rows(rows, service_key or "dry-run", args.dry_run)
    logger.info(f"Done: {succeeded} upserted, {failed} failed")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
