#!/usr/bin/env python3
"""
Scrape a fresh SoundCloud client_id from their web app JS bundle.

SoundCloud embeds the client_id in their publicly-served JavaScript. This script
fetches the SoundCloud homepage, finds the JS bundle URLs, and extracts the
client_id — the same value visible in any api-v2.soundcloud.com network request.

Usage (called from GitHub Actions before sync_episodes.py):
  python3 refresh_client_id.py                        # prints client_id to stdout
  python3 refresh_client_id.py --fallback OLD_ID      # falls back to OLD_ID if scraping fails
  python3 refresh_client_id.py --validate             # also validates against SC API

Exit codes:
  0  client_id found (and valid, if --validate)
  1  failed to scrape and no usable fallback
"""

import argparse
import logging
import re
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s",
                    stream=sys.stderr)
logger = logging.getLogger(__name__)

# Browser-like headers — same as sync_episodes.py
SC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://soundcloud.com",
    "Referer":         "https://soundcloud.com/",
}

# Patterns to find client_id in minified JS — ordered most-specific first
_CLIENT_ID_PATTERNS = [
    r'client_id:"([a-zA-Z0-9_-]{20,})"',
    r"client_id:'([a-zA-Z0-9_-]{20,})'",
    r'"client_id","([a-zA-Z0-9_-]{20,})"',
    r'clientId:"([a-zA-Z0-9_-]{20,})"',
    r'client_id=([a-zA-Z0-9_-]{20,})[^a-zA-Z0-9_-]',
]


def scrape_client_id() -> str:
    """
    Fetch SoundCloud homepage → find JS bundle URLs → extract client_id.
    Returns the client_id string, or "" on failure.
    """
    logger.info("Fetching SoundCloud homepage...")
    try:
        resp = requests.get("https://soundcloud.com", headers=SC_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch SoundCloud homepage: {e}")
        return ""

    # SoundCloud serves JS from their CDN: https://a-v2.sndcdn.com/assets/*.js
    js_urls = re.findall(r'https://a-v2\.sndcdn\.com/assets/[^"\'>\s]+\.js', resp.text)
    if not js_urls:
        # Fallback: any <script src="..."> tag
        js_urls = re.findall(r'<script[^>]+src="(https://[^"]+\.js)"', resp.text)

    logger.info(f"Found {len(js_urls)} JS bundle(s)")

    for js_url in js_urls:
        short = js_url.split("/")[-1][:40]
        try:
            js_resp = requests.get(js_url, headers=SC_HEADERS, timeout=30)
            if js_resp.status_code != 200:
                logger.debug(f"  {short}: HTTP {js_resp.status_code}")
                continue
            for pattern in _CLIENT_ID_PATTERNS:
                m = re.search(pattern, js_resp.text)
                if m:
                    client_id = m.group(1)
                    logger.info(f"  Found client_id in {short}: {client_id}")
                    return client_id
        except Exception as e:
            logger.warning(f"  Error fetching {short}: {e}")

    logger.warning("Could not extract client_id from any JS bundle")
    return ""


def validate_client_id(client_id: str) -> bool:
    """Returns True if client_id is accepted by the SoundCloud API."""
    url = f"https://api-v2.soundcloud.com/tracks?ids=1&client_id={client_id}"
    try:
        resp = requests.get(url, headers=SC_HEADERS, timeout=15)
        ok = resp.status_code == 200
        logger.info(f"Validation: HTTP {resp.status_code} → {'✓ valid' if ok else '✗ invalid'}")
        return ok
    except Exception as e:
        logger.error(f"Validation request failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape SoundCloud client_id from JS bundle")
    parser.add_argument("--fallback", default="",
                        help="client_id to use if scraping fails (e.g. current stored value)")
    parser.add_argument("--validate", action="store_true",
                        help="Validate the scraped/fallback ID against SoundCloud API")
    args = parser.parse_args()

    # 1. Try scraping
    client_id = scrape_client_id()

    # 2. Fall back to stored ID if scraping failed
    if not client_id:
        if args.fallback:
            logger.warning(f"Scraping failed — using fallback client_id: {args.fallback}")
            client_id = args.fallback
        else:
            logger.error("Scraping failed and no fallback provided")
            return 1

    # 3. Optionally validate
    if args.validate and not validate_client_id(client_id):
        logger.error(f"client_id {client_id!r} failed validation")
        return 1

    # 4. Print to stdout (captured by GitHub Actions step output)
    print(client_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
