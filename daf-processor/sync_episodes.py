#!/usr/bin/env python3
"""
Sync episode audio URLs to Supabase episode_audio table.

Mirrors the FeedManager logic on iOS/Android:
  Phase 1: Walk the SoundCloud RSS feed → collect direct MP3 URLs (no client ID needed).
  Phase 2: Fetch SoundCloud playlists → collect soundcloud-track://ID URLs for gaps
           (requires SOUNDCLOUD_CLIENT_ID; exits with error if it returns 401/403).

Direct MP3 URLs from RSS are permanent and stored forever. As dafs cycle through
the RSS window and are synced, they accumulate direct URLs in Supabase, reducing
dependence on the SoundCloud client ID over time.

Daf numbering:
  N.0 = amud aleph (full-daf recording, or explicit "Na" label)
  N.5 = amud bet (explicit "Nb" label, or interstitial range "Nb–(N+1)a")

Conflict resolution when two tracks map to the same .0 slot:
  - Explicit "Na" displaces a plain "N" incumbent → plain "N" is bumped to N.5
  - Plain "N" arriving after an explicit "Na" is stored as N.5
  - Two titles with the same computed daf and no displacement possible → skipped

Required env vars:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key (bypasses RLS)
  SOUNDCLOUD_CLIENT_ID  SoundCloud API client ID

Usage:
  python sync_episodes.py                 # full sync
  python sync_episodes.py --rss-only      # skip playlists (no client ID needed)
  python sync_episodes.py --check         # validate client ID without syncing
  python sync_episodes.py --dry-run       # preview without writing
"""

import argparse
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL      = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SOUNDCLOUD_CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
RSS_BASE          = "https://feeds.soundcloud.com/users/soundcloud:users:958779193/sounds.rss"
EPISODE_TABLE     = "episode_audio"

# Canonical tractate name → SoundCloud playlist ID
TRACTATE_PLAYLIST_IDS: dict[str, int] = {
    "Berakhot":      1224453841,
    "Shabbat":       1224957730,
    "Eiruvin":       1224604675,
    "Pesachim":      1223731237,
    "Yoma":          1224408415,
    "Sukkah":        1224961240,
    "Beitzah":       1224467716,
    "Rosh Hashanah": 1225124800,
    "Ta\u2019anit":  1947852215,
    "Moed Katan":    1947706063,
    "Chagigah":      1947633743,
    "Yevamot":       1225156528,
    "Ketubot":       1224649789,
    "Nedarim":       1224705577,
    "Nazir":         1950629151,
    "Sotah":         1595841331,
    "Gittin":        1224617542,
    "Kiddushin":     1224719668,
    "Bava Kamma":    1224873547,
    "Bava Metzia":   1224692203,
    "Bava Batra":    1224939157,
    "Sanhedrin":     1225177738,
    "Makkot":        1224421891,
    "Shevuot":       1954367887,
    "Avodah Zarah":  1224438616,
    "Horayot":       1224645901,
    "Zevachim":      1225250722,
    "Menachot":      1950820791,
    "Hullin":        1224735955,
    "Bekhorot":      1224596788,
    "Arakhin":       1224424696,
    "Temurah":       1225194493,
    "Meilah":        1224865387,
    "Keritot":       1224780505,
    "Megillah":      1224639490,
    "Shekalim":      1224387193,
    "Kinnim":        1954771503,
    "Tamid":         1954771299,
    "Middot":        1954771395,
    "Niddah":        1225213678,
}

# Build set of known tractate names (lowercase) for title parsing
_KNOWN_TRACTATES_LOWER = {t.lower(): t for t in TRACTATE_PLAYLIST_IDS}

# Spelling variants found in SoundCloud track titles → canonical name
_ALIASES: dict[str, str] = {
    "ta'anit":    "Ta\u2019anit",  # straight apostrophe vs curly
    "taanit":     "Ta\u2019anit",
    "ketuvot":    "Ketubot",
    "ketubot":    "Ketubot",
    "avodah zara": "Avodah Zarah",  # missing trailing h
    "avoda zarah": "Avodah Zarah",
    "avoda zara":  "Avodah Zarah",
    "menahot":    "Menachot",
    "me'ilah":    "Meilah",        # apostrophe variant
    "meilah":     "Meilah",
    "peschim":    "Pesachim",      # typo in SoundCloud title
    "moedkatan":  "Moed Katan",
    "roshhashanah": "Rosh Hashanah",
    "rosh hashana": "Rosh Hashanah",
    "megilah":    "Megillah",      # one-l variant in SoundCloud/Transistor titles
    "megila":     "Megillah",
}
# Merge aliases into lookup (aliases do not override canonical spellings)
for _alias, _canonical in _ALIASES.items():
    _KNOWN_TRACTATES_LOWER.setdefault(_alias, _canonical)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def supabase_headers(service_key: str) -> dict:
    return {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
    }

# Headers that mimic a browser request — needed for SoundCloud API-v2 calls,
# which return 403 for requests with a Python/requests user-agent.
SC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://soundcloud.com",
    "Referer":         "https://soundcloud.com/",
}


def parse_title(title: str) -> tuple[Optional[str], Optional[float], bool]:
    """
    Parse 'Tractate Name DafNumber[suffix]' from an RSS/playlist title.
    Returns (canonical_tractate, daf_float, has_explicit_a) or (None, None, False).

    daf_float: N.0 = amud aleph (or full-daf), N.5 = amud bet / interstitial
    has_explicit_a: True when the daf token has a trailing 'a' (e.g. "5a", "24a")

    Examples:
      "Berakhot 5"       → ("Berakhot", 5.0, False)
      "Berakhot 5a"      → ("Berakhot", 5.0, True)
      "Berakhot 5b"      → ("Berakhot", 5.5, False)
      "Berakhot 5b-6a"   → ("Berakhot", 5.5, False)  [leading token sets slot]
      "Berakhot 5b - 6a" → ("Berakhot", 5.5, False)  [spaces around dash ok]
    """
    # Strip trailing parenthetical: "Title (123)" → "Title"
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", title.strip())
    parts = cleaned.split()
    if len(parts) < 2:
        return None, None, False

    # Try longest prefix as tractate name first (handles multi-word tractates)
    for end in range(len(parts) - 1, 0, -1):
        candidate = " ".join(parts[:end]).lower()
        if candidate in _KNOWN_TRACTATES_LOWER:
            daf_token = parts[end]
            m = re.match(r"^(\d+)(.*)", daf_token)
            if not m:
                continue
            base = int(m.group(1))
            if base <= 0 or base > 200:
                continue
            suffix = m.group(2).lower()
            is_half = suffix.startswith("b")
            has_explicit_a = suffix.startswith("a")
            daf_float = float(base) + (0.5 if is_half else 0.0)
            return _KNOWN_TRACTATES_LOWER[candidate], daf_float, has_explicit_a

    return None, None, False


# ---------------------------------------------------------------------------
# Phase 1: RSS feed
# ---------------------------------------------------------------------------

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
}

def fetch_rss_episodes() -> dict[str, dict[float, str]]:
    """Walk all RSS pages and return tractate → daf → direct MP3 URL."""
    index: dict[str, dict[float, str]] = {}
    next_url: Optional[str] = RSS_BASE
    page = 0

    while next_url:
        page += 1
        logger.info(f"  RSS page {page}: {next_url}")
        try:
            resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"  ✗ RSS page {page} fetch failed: {e}")
            break

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error(f"  ✗ RSS page {page} XML parse error: {e}")
            break

        channel = root.find("channel")
        if channel is None:
            break

        for item in channel.findall("item"):
            title_el = item.find("title")
            enc_el   = item.find("enclosure")
            if title_el is None or enc_el is None:
                continue
            title    = (title_el.text or "").strip()
            audio_url = enc_el.get("url", "").strip()
            if not audio_url or not audio_url.startswith("http"):
                continue

            tractate, daf, _ = parse_title(title)
            if tractate and daf is not None:
                index.setdefault(tractate, {}).setdefault(daf, audio_url)

        # Next page link
        next_url = None
        for link in channel.findall("atom:link", _NS):
            if link.get("rel") == "next":
                next_url = link.get("href")
                break

    total = sum(len(v) for v in index.values())
    logger.info(f"  RSS complete: {total} episodes across {len(index)} tractates")
    return index


# ---------------------------------------------------------------------------
# Phase 2: SoundCloud playlists
# ---------------------------------------------------------------------------

def check_client_id() -> bool:
    """Returns True if SOUNDCLOUD_CLIENT_ID is valid, False if 401/403."""
    if not SOUNDCLOUD_CLIENT_ID:
        logger.error("  SOUNDCLOUD_CLIENT_ID is not set")
        return False
    url = f"https://api-v2.soundcloud.com/tracks?ids=1&client_id={SOUNDCLOUD_CLIENT_ID}"
    try:
        resp = requests.get(url, headers=SC_HEADERS, timeout=15)
    except Exception as e:
        logger.error(f"  Client ID check network error: {e}")
        return False
    if resp.status_code in (401, 403):
        logger.error(
            f"  ✗ SoundCloud client ID is INVALID (HTTP {resp.status_code}). "
            "Update SOUNDCLOUD_CLIENT_ID in GitHub Actions secrets:\n"
            "  1. Go to soundcloud.com in Chrome\n"
            "  2. DevTools → Network → filter 'api-v2'\n"
            "  3. Copy client_id= from any api-v2.soundcloud.com request"
        )
        return False
    logger.info(f"  ✓ SoundCloud client ID is valid (HTTP {resp.status_code})")
    return True


def fetch_playlist(tractate: str, playlist_id: int) -> dict[float, str]:
    """Fetch all tracks from a SoundCloud playlist → daf_float → soundcloud-track://ID URL.

    Conflict resolution for two tracks mapping to the same .0 slot:
      - Explicit "Na" displaces a plain "N" → plain "N" is re-slotted at N.5
      - Plain "N" arriving after an explicit "Na" → stored directly at N.5
      - Any other collision → the later track is skipped (logged as duplicate)
    """
    dafs: dict[float, str] = {}
    explicit_a: set[float] = set()   # .0 slots claimed by an explicit "Na" label

    url = f"https://api-v2.soundcloud.com/playlists/{playlist_id}?client_id={SOUNDCLOUD_CLIENT_ID}"
    try:
        resp = requests.get(url, headers=SC_HEADERS, timeout=30)
    except Exception as e:
        logger.warning(f"  ✗ Playlist {tractate} ({playlist_id}) network error: {e}")
        return dafs

    if resp.status_code != 200:
        logger.warning(f"  ✗ Playlist {tractate} HTTP {resp.status_code}")
        return dafs

    try:
        data = resp.json()
    except Exception:
        return dafs

    tracks = data.get("tracks", [])
    full_tracks = []
    stub_ids = []
    for track in tracks:
        if "title" in track:
            full_tracks.append(track)
        elif "id" in track:
            stub_ids.append(track["id"])

    # Batch-fetch stubs (SoundCloud only hydrates the first ~5 in a playlist response)
    batch_size = 50
    for i in range(0, len(stub_ids), batch_size):
        batch = stub_ids[i:i + batch_size]
        batch_url = (
            f"https://api-v2.soundcloud.com/tracks"
            f"?ids={','.join(map(str, batch))}&client_id={SOUNDCLOUD_CLIENT_ID}"
        )
        try:
            batch_resp = requests.get(batch_url, headers=SC_HEADERS, timeout=30)
            if batch_resp.status_code == 200:
                full_tracks.extend(batch_resp.json())
        except Exception:
            pass

    parse_failures = []
    duplicates = []
    for track in full_tracks:
        title = (track.get("title") or "").strip()
        urn   = (track.get("urn")   or "").strip()
        if not title or not urn:
            continue
        _, daf, has_explicit_a = parse_title(title)
        if daf is None:
            parse_failures.append(title)
            continue
        track_id = urn.split(":")[-1]
        if not track_id:
            continue
        sc_url = f"soundcloud-track://{track_id}"

        if daf not in dafs:
            # Slot is free — store it
            dafs[daf] = sc_url
            if has_explicit_a:
                explicit_a.add(daf)
        elif daf % 1 == 0:
            # Collision on an integer (.0) slot
            half = daf + 0.5
            if has_explicit_a and daf not in explicit_a:
                # Incoming "Na" outranks a plain incumbent → bump plain to .5
                if half not in dafs:
                    dafs[half] = dafs[daf]
                dafs[daf] = sc_url
                explicit_a.add(daf)
                logger.debug(f"    {title}: explicit 'a' displaced plain incumbent to {half}")
            elif not has_explicit_a and daf in explicit_a:
                # Incumbent is "Na"; incoming plain "N" is the b-side
                if half not in dafs:
                    dafs[half] = sc_url
                    logger.debug(f"    {title}: plain 'N' after 'Na' stored as {half}")
                else:
                    duplicates.append(title)
            else:
                duplicates.append(title)
        else:
            # Collision on a .5 slot (two b-side episodes)
            duplicates.append(title)

    track_count_reported = data.get("track_count", "?")
    logger.info(
        f"    {tractate}: {len(tracks)} tracks in response "
        f"(playlist reports {track_count_reported}), "
        f"{len(full_tracks)} resolved, {len(dafs)} parsed"
    )
    if parse_failures:
        logger.warning(f"    {tractate}: {len(parse_failures)} unparseable titles: {parse_failures[:5]}")
    if duplicates:
        logger.info(f"    {tractate}: {len(duplicates)} duplicate daf(s) skipped: {duplicates[:5]}")

    return dafs


def fetch_playlist_episodes(existing: dict[str, dict[float, str]]) -> dict[str, dict[float, str]]:
    """Fetch all playlists and return gaps not already covered by existing (RSS) URLs."""
    index: dict[str, dict[float, str]] = {}
    client_ok = check_client_id()
    if not client_ok:
        # Don't fail the whole sync — RSS URLs were already collected and are fine.
        # But exit non-zero so GitHub Actions reports the failure.
        logger.error(
            "\n⚠️  SoundCloud client ID is invalid. RSS episodes will still be synced,\n"
            "   but older dafs (from playlists) could not be updated.\n"
            "   Update SOUNDCLOUD_CLIENT_ID in GitHub Actions → Settings → Secrets."
        )

    for tractate, playlist_id in TRACTATE_PLAYLIST_IDS.items():
        if not client_ok:
            index[tractate] = {}
            continue
        logger.info(f"  Playlist: {tractate} ({playlist_id})")
        dafs = fetch_playlist(tractate, playlist_id)
        # Only keep dafs not already covered by RSS direct URLs
        existing_tractate = existing.get(tractate, {})
        new_dafs = {d: u for d, u in dafs.items() if d not in existing_tractate}
        index[tractate] = new_dafs

    total = sum(len(v) for v in index.values())
    logger.info(f"  Playlists complete: {total} additional episodes")
    return index


# ---------------------------------------------------------------------------
# Supabase upsert
# ---------------------------------------------------------------------------

def upsert_episodes(
    index: dict[str, dict[float, str]],
    service_key: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Upsert all episodes to Supabase. Returns (succeeded, failed)."""
    rows = [
        {"tractate": tractate, "daf": daf, "audio_url": url}
        for tractate, dafs in index.items()
        for daf, url in dafs.items()
    ]
    if not rows:
        logger.warning("  No rows to upsert.")
        return 0, 0

    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert {len(rows)} rows to {EPISODE_TABLE}")
        for tractate, dafs in sorted(index.items()):
            half_dafs = sorted(d for d in dafs if d % 1 != 0)
            if half_dafs:
                labels = [f"{int(d)}b" for d in half_dafs]
                logger.info(f"    {tractate} half-dafs: {labels}")
        return len(rows), 0

    # Supabase REST upsert in batches of 500
    batch_size = 500
    succeeded = failed = 0
    url = f"{SUPABASE_URL}/rest/v1/{EPISODE_TABLE}?on_conflict=tractate,daf"
    headers = {**supabase_headers(service_key), "Prefer": "resolution=merge-duplicates"}

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            resp = requests.post(url, headers=headers, json=batch, timeout=60)
            if resp.status_code in (200, 201):
                succeeded += len(batch)
                logger.info(f"  ✓ Upserted rows {i+1}–{i+len(batch)}")
            else:
                failed += len(batch)
                logger.error(f"  ✗ Batch {i+1}–{i+len(batch)}: HTTP {resp.status_code} — {resp.text[:300]}")
        except Exception as e:
            failed += len(batch)
            logger.error(f"  ✗ Batch {i+1}–{i+len(batch)} network error: {e}")

    return succeeded, failed


def upsert_app_config(service_key: str, key: str, value: str) -> None:
    """Upsert a single key-value pair to the app_config table."""
    url = f"{SUPABASE_URL}/rest/v1/app_config"
    headers = {**supabase_headers(service_key), "Prefer": "resolution=merge-duplicates"}
    payload = [{"key": key, "value": value, "updated_at": "now()"}]
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        logger.warning(f"  app_config upsert failed: HTTP {resp.status_code}")
    else:
        logger.info(f"  ✓ app_config: {key} updated")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync SoundCloud episode URLs to Supabase episode_audio table"
    )
    parser.add_argument("--rss-only",  action="store_true",
                        help="Skip playlist phase (no client ID required)")
    parser.add_argument("--check",     action="store_true",
                        help="Only validate the SoundCloud client ID, then exit")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Fetch data but do not write to Supabase")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.check:
        ok = check_client_id()
        return 0 if ok else 1

    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not service_key and not args.dry_run:
        logger.error("SUPABASE_SERVICE_KEY not set.")
        return 1

    # Phase 1: RSS (no client ID needed)
    logger.info("Phase 1: RSS feed")
    rss_index: dict[str, dict[float, str]] = fetch_rss_episodes()

    # Phase 2: SoundCloud playlists (fills in older dafs not in RSS)
    client_id_valid = True
    if args.rss_only:
        playlist_index: dict[str, dict[float, str]] = {}
    else:
        logger.info("Phase 2: SoundCloud playlists")
        client_id_valid = check_client_id()
        if client_id_valid:
            playlist_index = fetch_playlist_episodes(rss_index)
        else:
            playlist_index = {}

    # Merge: RSS wins over playlist (direct MP3 > soundcloud-track://)
    merged: dict[str, dict[float, str]] = {}
    all_tractates = set(rss_index) | set(playlist_index)
    for tractate in all_tractates:
        merged[tractate] = {**playlist_index.get(tractate, {}), **rss_index.get(tractate, {})}

    total = sum(len(v) for v in merged.values())
    half_daf_total = sum(1 for dafs in merged.values() for d in dafs if d % 1 != 0)
    logger.info(f"Merged: {total} episodes across {len(merged)} tractates ({half_daf_total} half-dafs)")

    # Upsert to Supabase
    logger.info("Upserting to Supabase…")
    succeeded, failed = upsert_episodes(merged, service_key or "dry-run", args.dry_run)
    logger.info(f"Done: {succeeded} upserted, {failed} failed")

    if SOUNDCLOUD_CLIENT_ID and not args.dry_run:
        upsert_app_config(service_key, "soundcloud_client_id", SOUNDCLOUD_CLIENT_ID)

    # Exit non-zero if client ID was bad OR any upsert rows failed
    if failed > 0:
        return 1
    if not client_id_valid and not args.rss_only:
        return 2  # Partial success — RSS synced but playlists failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
