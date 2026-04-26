#!/usr/bin/env python3
"""
Sync Transistor audio URLs from two Transistor RSS feeds to Supabase episode_audio.

Fetches both feeds:
  - https://feeds.transistor.fm/daf-yomi-archive        (older archive)
  - https://feeds.transistor.fm/daf-yomi-by-yct-with-rabbi-dov-linzer  (newer episodes)

The newer feed takes priority: if a daf appears in both, the newer-feed URL wins.

Transistor URLs overwrite existing SoundCloud URLs for any daf already in the table
(merge-duplicates updates audio_url for matching tractate+daf rows).

Required env vars:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key (bypasses RLS)

Usage:
  python sync_transistor_rss.py            # upsert all episodes from both feeds
  python sync_transistor_rss.py --dry-run  # preview without writing
"""

import argparse
import logging
import os
import sys
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

from sync_episodes import parse_title

load_dotenv()

logger = logging.getLogger(__name__)

TRANSISTOR_FEEDS = [
    "https://feeds.transistor.fm/daf-yomi-archive",
    "https://feeds.transistor.fm/daf-yomi-by-yct-with-rabbi-dov-linzer",
]
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
EPISODE_TABLE  = "episode_audio"

_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_transistor_episodes(feed_url: str) -> dict[str, dict[float, str]]:
    """Walk all RSS pages for feed_url and return tractate → daf → direct MP3 URL."""
    index: dict[str, dict[float, str]] = {}
    next_url: str | None = feed_url
    page = 0

    while next_url:
        page += 1
        logger.info(f"  RSS page {page}: {next_url}")
        try:
            resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"  ✗ Page {page} fetch failed: {e}")
            break

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error(f"  ✗ Page {page} XML parse error: {e}")
            break

        channel = root.find("channel")
        if channel is None:
            break

        items_on_page = parsed_on_page = 0
        for item in channel.findall("item"):
            title_el = item.find("title")
            enc_el   = item.find("enclosure")
            if title_el is None or enc_el is None:
                continue
            title     = (title_el.text or "").strip()
            audio_url = enc_el.get("url", "").strip()
            if not audio_url or not audio_url.startswith("http"):
                continue

            items_on_page += 1
            tractate, daf, _ = parse_title(title)
            if tractate and daf is not None:
                index.setdefault(tractate, {})[daf] = audio_url
                parsed_on_page += 1
            else:
                logger.debug(f"    Unparseable title: {title!r}")

        logger.info(f"    {items_on_page} items, {parsed_on_page} parsed")

        next_url = None
        for link in channel.findall("atom:link", _NS):
            if link.get("rel") == "next":
                next_url = link.get("href")
                break

    total = sum(len(v) for v in index.values())
    logger.info(f"  Feed complete: {total} episodes across {len(index)} tractates")
    return index


def upsert_episodes(
    index: dict[str, dict[float, str]],
    service_key: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Upsert all episodes to Supabase. Returns (succeeded, failed)."""
    rows = [
        {"tractate": tractate, "daf": daf, "audio_url": url}
        for tractate, dafs in sorted(index.items())
        for daf, url in sorted(dafs.items())
    ]
    if not rows:
        logger.warning("  No rows to upsert.")
        return 0, 0

    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert {len(rows)} rows to {EPISODE_TABLE}:")
        for tractate, dafs in sorted(index.items()):
            for daf in sorted(dafs):
                amud = f"{int(daf)}{'b' if daf % 1 else ''}"
                logger.info(f"    {tractate} {amud} → {dafs[daf][:90]}")
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
        description="Sync Transistor RSS audio URLs to Supabase episode_audio"
    )
    parser.add_argument("--dry-run",   action="store_true",
                        help="Fetch and parse but do not write to Supabase")
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

    # Fetch archive feed first, then newer feed — later entries overwrite earlier ones
    merged: dict[str, dict[float, str]] = {}
    for feed_url in TRANSISTOR_FEEDS:
        logger.info(f"Fetching Transistor feed: {feed_url}")
        feed_index = fetch_transistor_episodes(feed_url)
        for tractate, dafs in feed_index.items():
            merged.setdefault(tractate, {}).update(dafs)
    index = merged

    total = sum(len(v) for v in index.values())
    logger.info(f"Upserting {total} Transistor URLs to Supabase…")
    succeeded, failed = upsert_episodes(index, service_key or "dry-run", args.dry_run)
    logger.info(f"Done: {succeeded} upserted, {failed} failed")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
