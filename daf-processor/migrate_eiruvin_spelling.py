#!/usr/bin/env python3
"""
One-time migration: rename tractate "Eruvin" → "Eiruvin" in shiur_content
(and shiur_sections if present).

Job directories were historically named "eruvin_*", so upload_to_supabase.py stored
the tractate as "Eruvin". The episode_audio table uses "Eiruvin" (from sync_episodes.py),
causing the app to find audio but not shiur content for Eiruvin. Run this once to fix
existing rows; the updated scripts will use "Eiruvin" going forward.

Required env vars:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key (bypasses RLS)

Usage:
  python migrate_eiruvin_spelling.py           # apply fix
  python migrate_eiruvin_spelling.py --dry-run # preview affected rows
"""

import argparse
import logging
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
TABLES = ["shiur_content", "shiur_sections"]


def supabase_headers(service_key: str) -> dict:
    return {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
    }


def fetch_affected(table: str, service_key: str) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}?tractate=eq.Eruvin&select=tractate,daf"
    resp = requests.get(url, headers=supabase_headers(service_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def apply_migration(table: str, service_key: str) -> int:
    """PATCH all rows where tractate='Eruvin' to 'Eiruvin'. Returns count updated."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?tractate=eq.Eruvin"
    headers = {
        **supabase_headers(service_key),
        "Prefer": "return=representation",
    }
    resp = requests.patch(url, headers=headers, json={"tractate": "Eiruvin"}, timeout=30)
    if resp.status_code not in (200, 201):
        logger.error(f"  PATCH {table} failed: HTTP {resp.status_code} — {resp.text[:300]}")
        return -1
    updated = resp.json()
    return len(updated) if isinstance(updated, list) else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rename tractate "Eruvin" → "Eiruvin" in shiur_content and shiur_sections'
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show affected rows without writing")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not service_key:
        logger.error("SUPABASE_SERVICE_KEY not set.")
        return 1

    any_found = False
    for table in TABLES:
        rows = fetch_affected(table, service_key)
        if not rows:
            logger.info(f'{table}: no rows with tractate="Eruvin" — nothing to do.')
            continue

        any_found = True
        dafs = sorted({float(r["daf"]) for r in rows})
        daf_labels = [f"{int(d)}{'b' if d % 1 else ''}" for d in dafs]
        logger.info(f'{table}: {len(rows)} rows with tractate="Eruvin": {", ".join(daf_labels)}')

        if args.dry_run:
            continue

        count = apply_migration(table, service_key)
        if count < 0:
            return 1
        logger.info(f'  ✓ {table}: {count} rows updated to tractate="Eiruvin".')

    if args.dry_run and any_found:
        logger.info("[DRY RUN] No changes written.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
