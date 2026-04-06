#!/usr/bin/env python3
"""
build-episodes.py
-----------------
Fetches all Daf Yomi audio from the YCT SoundCloud account (via RSS feed and
playlist API) and writes episodes.json to the same directory as this script.

Run this weekly (or use the GitHub Actions workflow in .github/workflows/) to
keep the web widget's episode index up to date.

Usage:
    python3 build-episodes.py
"""

import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOUNDCLOUD_USER_ID = "958779193"
CLIENT_ID = "1IzwHiVxAHeYKAMqN0IIGD3ZARgJy2kl"
FEED_BASE = f"https://feeds.soundcloud.com/users/soundcloud:users:{SOUNDCLOUD_USER_ID}/sounds.rss"
OUTPUT = Path(__file__).parent / "episodes.json"

# Alternate spellings found in feed titles → canonical tractate name
FEED_TO_CANONICAL = {
    "menahot":      "Menachot",
    "zevachim":     "Zevahim",
    "taanit":       "Ta'anit",
    "meilah":       "Me'ilah",
    "berachot":     "Berakhot",
    "berachos":     "Berakhot",
    "brachot":      "Berakhot",
    "shabbos":      "Shabbat",
    "kesubos":      "Ketubot",
    "shevuos":      "Shevuot",
    "moed katan":   "Moed Katan",
    "avodah zarah": "Avodah Zarah",
    "avoda zara":   "Avodah Zarah",
    "megilah":      "Megillah",
    "rosh hashana": "Rosh Hashanah",
    "rosh hashanah":"Rosh Hashanah",
    "bava kama":    "Bava Kamma",
    "bava metzia":  "Bava Metzia",
    "bava batra":   "Bava Batra",
    "middos":       "Middot",
    "middoth":      "Middot",
}

ALL_TRACTATES = [
    "Berakhot", "Shabbat", "Eruvin", "Pesachim", "Shekalim", "Yoma", "Sukkah",
    "Beitzah", "Rosh Hashanah", "Ta'anit", "Megillah", "Moed Katan", "Chagigah",
    "Yevamot", "Ketubot", "Nedarim", "Nazir", "Sotah", "Gittin", "Kiddushin",
    "Bava Kamma", "Bava Metzia", "Bava Batra", "Sanhedrin", "Makkot", "Shevuot",
    "Avodah Zarah", "Horayot", "Zevahim", "Menachot", "Hullin", "Bekhorot",
    "Arachin", "Temurah", "Keritot", "Me'ilah", "Kinnim", "Tamid", "Middot", "Niddah",
]

TRACTATE_PLAYLIST_IDS = {
    "Berakhot":      1224453841,
    "Shabbat":       1224957730,
    "Eruvin":        1224604675,
    "Pesachim":      1223731237,
    "Yoma":          1224408415,
    "Sukkah":        1224961240,
    "Beitzah":       1224467716,
    "Rosh Hashanah": 1225124800,
    "Ta'anit":       1947852215,
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
    "Zevahim":       1225250722,
    "Menachot":      1950820791,
    "Hullin":        1224735955,
    "Bekhorot":      1224596788,
    "Arachin":       1224424696,
    "Temurah":       1225194493,
    "Me'ilah":       1224865387,
    "Kinnim":        1954771503,
    "Tamid":         1954771299,
    "Middot":        1954771395,
    "Niddah":        1225213678,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "AnyDaf-Builder/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

def canonical_tractate(feed_name):
    lower = feed_name.lower().replace("'", "").strip()
    if lower in FEED_TO_CANONICAL:
        return FEED_TO_CANONICAL[lower]
    for t in ALL_TRACTATES:
        if t.lower().replace("'", "") == lower:
            return t
    return None

def parse_title(title):
    """Extract (tractate, daf_int) from a feed title like 'Menahot 48 (5786)'."""
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", title).strip()
    parts = cleaned.split()
    if len(parts) < 2:
        return None
    m = re.match(r"^(\d+)", parts[-1])
    if not m:
        return None
    daf = int(m.group(1))
    if daf <= 0:
        return None
    feed_name = " ".join(parts[:-1])
    canonical = canonical_tractate(feed_name)
    if not canonical:
        return None
    return canonical, daf

def resolve_stream_url(track_id):
    """
    Resolve a SoundCloud track ID to a playable CDN URL.
    Returns the URL string, or None on failure.
    NOTE: The returned URL is a signed CloudFront URL that expires after a few
    days — re-run this script weekly to keep URLs fresh.
    """
    try:
        data = fetch(f"https://api-v2.soundcloud.com/tracks/{track_id}?client_id={CLIENT_ID}")
        track = json.loads(data)
        auth = track.get("track_authorization", "")
        transcodings = track.get("media", {}).get("transcodings", [])
        # Prefer progressive (direct MP3) over HLS
        progressive = next(
            (t for t in transcodings if t.get("format", {}).get("protocol") == "progressive"),
            None
        )
        if not progressive:
            return None
        tc_url = progressive["url"] + f"?client_id={CLIENT_ID}&track_authorization={auth}"
        stream_data = json.loads(fetch(tc_url))
        return stream_data.get("url")
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Phase 1: RSS
# ---------------------------------------------------------------------------

def fetch_rss():
    index = {}
    url = FEED_BASE
    page = 0
    while url:
        page += 1
        print(f"  RSS page {page} … ", end="", flush=True)
        data = fetch(url)
        root = ET.fromstring(data)

        items = root.findall(".//item")
        added = 0
        for item in items:
            title_el = item.find("title")
            enc_el = item.find("enclosure")
            if title_el is None or enc_el is None:
                continue
            audio_url = enc_el.attrib.get("url", "")
            if not audio_url:
                continue
            parsed = parse_title(title_el.text or "")
            if not parsed:
                continue
            tractate, daf = parsed
            index.setdefault(tractate, {})
            if daf not in index[tractate]:
                index[tractate][daf] = audio_url
                added += 1

        print(f"{len(items)} items ({added} new)")

        # Find next page (atom:link rel="next")
        url = None
        for el in root.iter():
            if el.get("rel") == "next" and el.get("href"):
                url = el.get("href")
                break

    return index

# ---------------------------------------------------------------------------
# Phase 2: SoundCloud playlist API
# ---------------------------------------------------------------------------

def fetch_playlist_tracks(tractate, playlist_id):
    """Returns {daf: stream_url_or_sc_track_id} for a given playlist."""
    dafs = {}
    try:
        data = fetch(f"https://api-v2.soundcloud.com/playlists/{playlist_id}?client_id={CLIENT_ID}")
        j = json.loads(data)
        tracks = j.get("tracks", [])

        full_tracks = [t for t in tracks if "title" in t]
        stub_ids   = [t["id"] for t in tracks if "title" not in t]

        # Batch-fetch stubs
        for i in range(0, len(stub_ids), 50):
            batch = stub_ids[i:i + 50]
            ids_param = ",".join(str(x) for x in batch)
            try:
                batch_data = fetch(f"https://api-v2.soundcloud.com/tracks?ids={ids_param}&client_id={CLIENT_ID}")
                full_tracks.extend(json.loads(batch_data))
            except Exception as e:
                print(f"\n    stub batch error: {e}", end="")

        for track in full_tracks:
            title = track.get("title", "")
            urn   = track.get("urn", "")
            if not title or not urn:
                continue
            parsed = parse_title(title)
            if not parsed:
                continue
            _, daf = parsed
            track_id = urn.split(":")[-1]
            if daf not in dafs:
                dafs[daf] = f"soundcloud-track:{track_id}"

    except Exception as e:
        print(f"\n    playlist {playlist_id} error: {e}", end="")

    return tractate, dafs

def fetch_playlists_parallel(index):
    """Fetch all playlist data in parallel, fill in missing dafs."""
    print("\nPhase 2: SoundCloud playlists (parallel) …")

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(fetch_playlist_tracks, t, pid): t
            for t, pid in TRACTATE_PLAYLIST_IDS.items()
        }
        for future in as_completed(futures):
            tractate, dafs = future.result()
            index.setdefault(tractate, {})
            added = sum(1 for d, u in dafs.items() if d not in index[tractate])
            for daf, url in dafs.items():
                if daf not in index[tractate]:
                    index[tractate][daf] = url
            print(f"  {tractate}: {added} new dafs")

# ---------------------------------------------------------------------------
# Phase 3 (optional): resolve soundcloud-track: URLs to direct CDN URLs
# ---------------------------------------------------------------------------

def resolve_api_tracks(index):
    """
    Attempt to resolve soundcloud-track: entries to direct CDN URLs so the
    widget can play them without needing any proxy server.

    This is optional — if resolution fails or you skip it, the widget falls back
    to a 'Listen on SoundCloud' link for those dafs.
    """
    print("\nPhase 3: Resolving API track URLs …")
    to_resolve = [
        (tractate, daf, url)
        for tractate, dafs in index.items()
        for daf, url in dafs.items()
        if url.startswith("soundcloud-track:")
    ]
    print(f"  {len(to_resolve)} tracks to resolve …")

    def resolve_one(item):
        tractate, daf, url = item
        track_id = url.split(":")[-1]
        cdn_url = resolve_stream_url(track_id)
        return tractate, daf, cdn_url

    resolved = failed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for tractate, daf, cdn_url in pool.map(resolve_one, to_resolve):
            if cdn_url:
                index[tractate][daf] = cdn_url
                resolved += 1
            else:
                failed += 1

    print(f"  Resolved: {resolved}  Failed/kept as sc-track: {failed}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    resolve = "--resolve" in sys.argv or "-r" in sys.argv

    print("Phase 1: RSS feed …")
    index = fetch_rss()

    fetch_playlists_parallel(index)

    if resolve:
        resolve_api_tracks(index)
    else:
        sc_count = sum(
            1 for dafs in index.values()
            for u in dafs.values() if u.startswith("soundcloud-track:")
        )
        if sc_count:
            print(f"\nNote: {sc_count} older episodes stored as soundcloud-track: IDs.")
            print("      Run with --resolve to pre-fetch their CDN URLs (adds ~2 min,")
            print("      but those URLs expire after a few days — re-run weekly).")

    total = sum(len(v) for v in index.values())
    print(f"\nTotal: {total} episodes across {len(index)} tractates")

    # JSON keys must be strings
    output = {t: {str(d): u for d, u in dafs.items()} for t, dafs in index.items()}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Saved → {OUTPUT}")

if __name__ == "__main__":
    main()
