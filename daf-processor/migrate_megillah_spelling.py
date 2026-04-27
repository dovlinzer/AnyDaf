#!/usr/bin/env python3
"""
One-time migration: rename tractate "Megilah" → "Megillah" in episode_audio.

The SoundCloud sync scripts historically stored the tractate as "Megilah" (one l),
while shiur_content uses "Megillah" (two l's). This mismatch caused the app to find
shiur content but not audio for Megillah. Run this once to fix existing rows, then
the updated sync_episodes.py will use "Megillah" going forward.

Required env vars:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key (bypasses RLS)

Usage:
  python migrate_megillah_spelling.py           # apply fix
  python migrate_megillah_spelling.py --dry-run # preview affected rows
"""

import argparse
import logging
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
EPISODE_TABLE = "episode_audio"


def supabase_headers(service_key: str) -> dict:
    return {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
    }


def fetch_affected(service_key: str) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{EPISODE_TABLE}?tractate=eq.Megilah&select=tractate,daf,audio_url"
    resp = requests.get(url, headers=supabase_headers(service_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def apply_migration(service_key: str) -> int:
    """PATCH all rows where tractate='Megilah' to 'Megillah'. Returns count updated."""
    url = f"{SUPABASE_URL}/rest/v1/{EPISODE_TABLE}?tractate=eq.Megilah"
    headers = {
        **supabase_headers(service_key),
        "Prefer": "return=representation",
    }
    resp = requests.patch(url, headers=headers, json={"tractate": "Megillah"}, timeout=30)
    if resp.status_code not in (200, 201):
        logger.error(f"PATCH failed: HTTP {resp.status_code} — {resp.text[:300]}")
        return -1
    updated = resp.json()
    return len(updated) if isinstance(updated, list) else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rename tractate "Megilah" → "Megillah" in episode_audio'
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

    rows = fetch_affected(service_key)
    if not rows:
        logger.info('No rows with tractate="Megilah" found — nothing to do.')
        return 0

    logger.info(f'Found {len(rows)} episode_audio rows with tractate="Megilah":')
    for r in sorted(rows, key=lambda x: float(x["daf"])):
        daf = float(r["daf"])
        label = f"{int(daf)}{'b' if daf % 1 else ''}"
        logger.info(f"  Megillah {label}  {r['audio_url'][:80]}")

    if args.dry_run:
        logger.info("[DRY RUN] No changes written.")
        return 0

    count = apply_migration(service_key)
    if count < 0:
        return 1
    logger.info(f'Done: {count} rows updated to tractate="Megillah".')
    return 0


if __name__ == "__main__":
    sys.exit(main())
