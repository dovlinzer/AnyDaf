#!/usr/bin/env python3
"""
sofer_batch.py — Submit audio files to Sofer.ai for batch transcription.

Standard-mode workflow (cheaper, up to 500 files, processed within 24 hrs):
  1. Build a list of audio sources from a directory + base URL, or a URL list file
  2. Upload a batch manifest      (POST /v1/transcriptions/batch-files)
  3. Submit the batch job         (POST /v1/transcriptions/batch)
  4. Optionally poll for status   (GET  /v1/transcriptions/batch/{id}/status)
  5. Optionally download SRTs     (GET  /v1/transcriptions/{id})

Usage examples:

  # Filenames hosted at a base URL (most common — no local copy needed):
  python sofer_batch.py \\
      --base-url   https://example.com/audio \\
      --filenames  menachot79.mp3 menachot80.mp3 \\
      --tractate   Menachot

  # Auto-discover filenames by scanning a local directory:
  python sofer_batch.py \\
      --audio-dir  ./audio \\
      --base-url   https://example.com/audio \\
      --tractate   Menachot

  # Explicit list of full URLs, one per line (optionally "URL<TAB>Title"):
  python sofer_batch.py --url-file urls.txt --tractate Menachot

  # Look up audio URLs from Supabase by tractate + daf range:
  python sofer_batch.py --supabase-range "Menachot 2-26"
  # Titles are set to e.g. "Menachot 2", "Menachot 3" — no filename guessing needed.
  # Missing dafs in the range are skipped. soundcloud-track:// URIs are resolved
  # if SOUNDCLOUD_CLIENT_ID is set in the environment.

  # Multi-segment ranges (individual dafs, disjoint ranges, mixed tractates):
  python sofer_batch.py --supabase-range "Hullin 3, 5-10, 15, 17, 20-30"
  python sofer_batch.py --supabase-range "Hullin 3, Hullin 5-10, Hullin 15"
  python sofer_batch.py --supabase-range "Hullin 2-10, Menachot 5-8, Hullin 20"

  # Check status of an existing batch:
  python sofer_batch.py --status <batch-id>

  # Poll until done and download all SRT files:
  python sofer_batch.py --status <batch-id> --poll --download-dir ./srt
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple  # noqa: F401 — Tuple used in type comments

import requests
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOFER_API_KEY = os.environ.get("SOFER_API_KEY", "sek_pyp9MGWJUogOnSLbtVRCnh2gPYaW4lO4N5r")
SOFER_BASE_URL = "https://api.sofer.ai"

# Transcription settings applied to every file in the batch
TRANSCRIPTION_INFO = {
    "model": "v1",
    "primary_language": "en",
    "hebrew_word_format": ["en", "he"],
    "auto_detect_speakers": True,
}

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".mp4", ".webm"}
MANIFEST_POLL_INTERVAL = 5    # seconds between manifest validation polls
BATCH_POLL_INTERVAL   = 60    # seconds between batch status polls

# Supabase — used by --supabase-range to look up episode audio URLs
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY", "")
)

# SoundCloud — used to resolve soundcloud-track:// URIs stored in Supabase
SOUNDCLOUD_CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
_SC_HEADERS = {
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Title inference from filenames (reuses daf-identifier logic from sefaria.py)
# ---------------------------------------------------------------------------

MASECHTA_MAP = {
    "berakhot": "Berakhot", "berachot": "Berakhot", "brachos": "Berakhot",
    "shabbat": "Shabbat", "shabbos": "Shabbat",
    "eruvin": "Eiruvin", "eiruvin": "Eiruvin",
    "pesachim": "Pesachim",
    "yoma": "Yoma",
    "sukkah": "Sukkah",
    "beitzah": "Beitzah",
    "taanit": "Ta\u2019anit", "taanis": "Ta\u2019anit",
    "megillah": "Megilah", "megila": "Megilah",
    "yevamot": "Yevamot", "yevamos": "Yevamot",
    "ketubot": "Ketubot", "kesuvos": "Ketubot",
    "nedarim": "Nedarim",
    "nazir": "Nazir",
    "sotah": "Sotah",
    "gittin": "Gittin",
    "kiddushin": "Kiddushin",
    "babakamma": "Bava Kamma", "bavakamma": "Bava Kamma",
    "babametzia": "Bava Metzia", "bavametzia": "Bava Metzia",
    "bababatra": "Bava Batra", "bavabatra": "Bava Batra",
    "sanhedrin": "Sanhedrin",
    "makkot": "Makkot", "makkos": "Makkot",
    "shevuot": "Shevuot", "shevuos": "Shevuot",
    "avodahzarah": "Avodah Zarah",
    "horayot": "Horayot",
    "zevachim": "Zevachim", "zvachim": "Zevachim",
    "menachot": "Menachot", "menachos": "Menachot",
    "chullin": "Hullin", "hullin": "Hullin", "hulin": "Hullin",
    "bekhorot": "Bekhorot", "bechoros": "Bekhorot",
    "arakhin": "Arakhin", "erchin": "Arakhin",
    "temurah": "Temurah",
    "keritot": "Keritot", "kerisos": "Keritot",
    "meilah": "Meilah",
    "tamid": "Tamid",
    "niddah": "Niddah",
}


def _infer_title(filename_stem: str, tractate_override: Optional[str] = None) -> str:
    """Try to derive a human-readable title like 'Menachot 79' from a filename."""
    s = filename_stem.lower()
    for prefix in ("rdldafyomi", "dafyomi", "rdl"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.split("_")[0]

    # Try "name + number" pattern
    m = re.match(r"([a-z]+?)(\d+)$", s.strip())
    if m:
        raw_name = re.sub(r"[^a-z]", "", m.group(1))
        masechta = MASECHTA_MAP.get(raw_name)
        if masechta:
            return f"{masechta} {m.group(2)}"

    # Fall back to tractate override + number if we can extract a number
    if tractate_override:
        nums = re.findall(r"\d+", filename_stem)
        if nums:
            return f"{tractate_override} {nums[-1]}"

    return filename_stem  # last resort: raw filename


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SOFER_API_KEY}",
        "Content-Type": "application/json",
    }


def _post(path: str, body: dict) -> dict:
    url = f"{SOFER_BASE_URL}{path}"
    logger.debug(f"POST {path}\n{json.dumps(body, indent=2, ensure_ascii=False)}")
    resp = requests.post(url, headers=_headers(), json=body, timeout=30)
    logger.debug(f"  → {resp.status_code}: {resp.text[:500]}")
    if not resp.ok:
        logger.error(f"POST {path} → {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp.json()


def _get(path: str, params: Optional[dict] = None) -> requests.Response:
    """Raw GET — returns the Response object so callers can handle content-type themselves."""
    url = f"{SOFER_BASE_URL}{path}"
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    if not resp.ok:
        logger.error(f"GET {path} → {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp


def _get_json(path: str, params: Optional[dict] = None) -> dict:
    return _get(path, params).json()


# ---------------------------------------------------------------------------
# Link extraction (for Google Drive, YouTube, etc.)
# ---------------------------------------------------------------------------

# Stems that appear in sharing URLs but carry no useful filename information
_USELESS_STEMS = {"view", "share", "download", "preview", "open", "edit", "uc"}


def _is_useless_stem(stem: str) -> bool:
    return (not stem
            or stem.lower() in _USELESS_STEMS
            or re.match(r"^item_\d+$", stem.lower()) is not None)


# URL patterns that are sharing/redirect URLs rather than direct audio links
_SHARING_URL_PATTERNS = [
    r"drive\.google\.com",
    r"docs\.google\.com",
    r"youtu\.be",
    r"youtube\.com",
    r"dropbox\.com/s/",
    r"1drv\.ms",          # OneDrive short links
    r"onedrive\.live\.com",
]
_SHARING_RE = re.compile("|".join(_SHARING_URL_PATTERNS), re.IGNORECASE)


def _is_sharing_url(url: str) -> bool:
    return bool(_SHARING_RE.search(url))


def _is_gdrive_folder(url: str) -> bool:
    return bool(re.search(r"drive\.google\.com/drive/folders/", url, re.IGNORECASE))


def _gdrive_file_id(url: str) -> Optional[str]:
    """Extract a Google Drive file ID from a share URL, or None."""
    m = re.search(r"drive\.google\.com/file/d/([^/?#]+)", url)
    return m.group(1) if m else None


def _gdrive_direct_url(file_id: str) -> str:
    """Convert a Google Drive file ID to a direct download URL."""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def resolve_url(url: str) -> Tuple[str, str]:
    """
    Resolve a sharing URL to a direct download URL.
    First tries the Sofer.ai link-extraction endpoint; if that returns an error,
    falls back to a built-in conversion for Google Drive share links.
    Returns (download_url, file_name).
    """
    # Strip stray trailing backslashes / whitespace that can appear in URL files
    url = url.strip().rstrip("\\")

    logger.info(f"  Resolving link: {url}")

    # Try Sofer.ai link extraction first
    try:
        resp = _post("/v1/link/extract", {"url": url})
        download_url = resp["download_url"]
        file_name = resp.get("file_name", "")
        logger.info(f"    → {download_url}")
        return download_url, file_name
    except Exception as e:
        logger.debug(f"  Sofer.ai link extraction failed ({e}); trying built-in conversion")

    # Fallback: Google Drive share URL → direct download URL
    file_id = _gdrive_file_id(url)
    if file_id:
        download_url = _gdrive_direct_url(file_id)
        logger.info(f"    → {download_url}  (Google Drive direct download)")
        return download_url, ""

    # Nothing worked
    raise RuntimeError(
        f"Could not resolve URL to a direct download link: {url}\n"
        "Check that the file is publicly shared and the URL is a single-file share link."
    )


def resolve_items(items: List[dict]) -> List[dict]:
    """
    For any item whose audio_url looks like a sharing link, call the Sofer.ai
    link-extraction endpoint and replace the URL with the direct download URL.
    Items with direct URLs are passed through unchanged.
    """
    resolved = []
    for item in items:
        url = item["audio_url"]
        if _is_sharing_url(url):
            download_url, file_name = resolve_url(url)
            title = item.get("title") or ""
            original_stem = Path(url.split("?")[0]).stem
            # Replace the title if it's useless (e.g. "view" from a Google Drive share URL)
            # or if we got a real filename back from the API that we can do better with.
            if file_name and (_is_useless_stem(title) or title == original_stem):
                title = _infer_title(Path(file_name).stem) or title
            resolved.append({"audio_url": download_url, "title": title or file_name})
        else:
            resolved.append(item)
    return resolved


def supported_sites() -> List[dict]:
    """Return the list of sites supported by Sofer.ai's link-extraction endpoint."""
    return _get_json("/v1/link/sites")


# ---------------------------------------------------------------------------
# Core steps
# ---------------------------------------------------------------------------

def upload_manifest(items: List[dict], tractate: str) -> str:
    """
    Upload a batch manifest and return the batch_file_id.
    items: list of {"audio_url": ..., "title": ...}
    """
    logger.info(f"Uploading manifest with {len(items)} item(s)…")
    body = {
        "content_type": "json",
        "json_items": items,
        "metadata": {
            "title": tractate,
            "description": f"Daf Yomi shiurim — {tractate}",
        },
    }
    resp = _post("/v1/transcriptions/batch-files", body)
    batch_file_id = resp["batch_file_id"]
    logger.info(f"  Manifest uploaded → batch_file_id: {batch_file_id}")

    # Poll until validated
    while resp.get("status") not in ("VALID", "INVALID"):
        logger.info(f"  Manifest status: {resp.get('status')} — waiting…")
        time.sleep(MANIFEST_POLL_INTERVAL)
        resp = _get_json(f"/v1/transcriptions/batch-files/{batch_file_id}")

    if resp["status"] == "INVALID":
        errors = resp.get("validation_errors", [])
        raise RuntimeError(f"Manifest validation failed: {errors}")

    logger.info(f"  Manifest VALID ({resp['item_count']} items, {resp['size_bytes']} bytes)")
    return batch_file_id


def submit_batch(batch_file_id: str, tractate: str) -> str:
    """Submit the batch job and return the batch_id."""
    logger.info("Submitting batch transcription job…")
    body = {
        "processing_mode": "standard",
        "batch_file_id": batch_file_id,
        "batch_title": tractate,
        "info": TRANSCRIPTION_INFO,
    }
    resp = _post("/v1/transcriptions/batch", body)
    batch_id = resp["batch_id"]
    logger.info(
        f"  Batch submitted → batch_id: {batch_id}  "
        f"({resp['total_count']} transcriptions, status: {resp['status']})"
    )
    return batch_id


def get_batch_status(batch_id: str) -> dict:
    """Fetch and return the current batch status."""
    return _get_json(f"/v1/transcriptions/batch/{batch_id}/status")


def print_status(status: dict) -> None:
    """Pretty-print a batch status response."""
    print(
        f"\nBatch {status['batch_id']}\n"
        f"  Status    : {status['status']}\n"
        f"  Total     : {status['total_count']}\n"
        f"  Completed : {status['completed_count']}\n"
        f"  Failed    : {status['failed_count']}\n"
        f"  Pending   : {status['pending_count']}\n"
    )
    for t in status.get("transcriptions", []):
        dur = f"  {t['duration']:.0f}s" if t.get("duration") else ""
        print(f"  [{t['status']:12s}] {t['title']}{dur}  ({t['id']})")


def poll_until_done(batch_id: str) -> dict:
    """Poll batch status until COMPLETED or FAILED, logging progress."""
    logger.info(f"Polling batch {batch_id} (every {BATCH_POLL_INTERVAL}s)…")
    while True:
        status = get_batch_status(batch_id)
        logger.info(
            f"  {status['status']}  "
            f"completed={status['completed_count']}  "
            f"failed={status['failed_count']}  "
            f"pending={status['pending_count']}"
        )
        if status["status"] in ("COMPLETED", "FAILED"):
            return status
        time.sleep(BATCH_POLL_INTERVAL)


def _format_srt_time(seconds: float) -> str:
    """Convert float seconds → SRT timestamp HH:MM:SS,mmm."""
    ms = int(round((seconds % 1) * 1000))
    total_s = int(seconds)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt_from_timestamps(timestamps: list) -> str:
    """
    Convert Sofer.ai word-level timestamps to standard SRT format.
    Groups words into subtitle cues, breaking on:
      - speaker change
      - pause > 1 second between words
      - cue exceeding 7 seconds
      - cue reaching 12 words
    """
    MAX_WORDS     = 12
    MAX_DURATION  = 7.0   # seconds
    PAUSE_GAP     = 1.0   # seconds of silence → new cue

    cues: List[Tuple[float, float, str]] = []  # (start, end, text)
    cur_words: List[str] = []
    cur_start  = 0.0
    cur_end    = 0.0
    cur_speaker: Optional[str] = None

    for entry in timestamps:
        word    = (entry.get("word") or "").strip()
        start   = float(entry.get("start") or 0.0)
        end     = float(entry.get("end")   or 0.0)
        speaker = entry.get("speaker") or ""
        if not word:
            continue

        if cur_words:
            gap      = start - cur_end
            duration = cur_end - cur_start
            if (len(cur_words) >= MAX_WORDS
                    or duration >= MAX_DURATION
                    or gap >= PAUSE_GAP
                    or speaker != cur_speaker):
                cues.append((cur_start, cur_end, " ".join(cur_words)))
                cur_words = []

        if not cur_words:
            cur_start  = start
            cur_speaker = speaker

        cur_words.append(word)
        cur_end = end

    if cur_words:
        cues.append((cur_start, cur_end, " ".join(cur_words)))

    blocks = []
    for i, (start, end, text) in enumerate(cues, 1):
        blocks.append(
            f"{i}\n"
            f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def download_srt(transcription_id: str, title: str, out_dir: Path,
                 diagnose: bool = False) -> None:
    """Download a completed transcription as SRT and save it."""
    safe = re.sub(r"[^\w\s-]", "_", title).strip()
    out_path = out_dir / f"{safe}.srt"

    # ── Fetch the transcription object ──────────────────────────────────────
    meta = _get_json(f"/v1/transcriptions/{transcription_id}")

    if diagnose:
        json_path = out_dir / f"{safe}.json"
        json_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        logger.info(f"  Raw response → {json_path}")

    # ── Build SRT from word-level timestamps (primary path) ─────────────────
    timestamps = meta.get("timestamps")
    if timestamps and isinstance(timestamps, list):
        srt_text = _build_srt_from_timestamps(timestamps)
        if srt_text:
            out_path.write_text(srt_text, encoding="utf-8")
            logger.info(f"  Saved ({len(timestamps)} words → {out_path.name})")
            return

    # ── Fallback: pre-built SRT string in the response ──────────────────────
    inline = meta.get("srt") or meta.get("srt_content") or ""
    if inline:
        out_path.write_text(inline, encoding="utf-8")
        logger.info(f"  Saved (inline srt field): {out_path}")
        return

    logger.error(
        f"  ✗ No timestamps or SRT content found for '{title}' ({transcription_id}). "
        "Re-run with --diagnose to inspect the raw response."
    )


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def items_from_filenames(filenames: List[str], base_url: str, tractate: Optional[str]) -> List[dict]:
    """Build items list from explicit filenames + a base URL."""
    items = []
    for name in filenames:
        url = f"{base_url.rstrip('/')}/{name}"
        title = _infer_title(Path(name).stem, tractate)
        items.append({"audio_url": url, "title": title})
        logger.debug(f"  {title}  →  {url}")
    return items


def items_from_dir(audio_dir: Path, base_url: str, tractate: Optional[str]) -> List[dict]:
    """Discover audio filenames by scanning a local directory, then build items with base_url."""
    files = sorted(
        f for f in audio_dir.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not files:
        raise FileNotFoundError(f"No audio files found in {audio_dir}")
    return items_from_filenames([f.name for f in files], base_url, tractate)


def items_from_url_file(url_file: Path, tractate: Optional[str]) -> List[dict]:
    """
    Build items list from a text file.
    Supported formats per line:
      - bare URL
      - URL<TAB>Title
      - URL Title (space-separated, title is everything after first space)
    """
    items = []
    raw = url_file.read_text(encoding="utf-8", errors="replace")
    if raw.lstrip().startswith("{\\rtf"):
        raise ValueError(
            f"{url_file} appears to be an RTF document, not a plain-text file.\n"
            "Please save it as plain text:\n"
            "  • TextEdit: Format → Make Plain Text, then File → Save (choose .txt)\n"
            "  • Or create it in Terminal:  nano links.txt"
        )

    for line in raw.splitlines():
        line = line.strip().rstrip("\\")
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            url, title = line.split("\t", 1)
        else:
            parts = line.split(" ", 1)
            url = parts[0]
            title = parts[1].strip() if len(parts) > 1 else None
        url = url.strip().rstrip("\\")

        if not title:
            # Guess title from URL path — but ignore useless path components like "view"
            stem = Path(url.split("?")[0]).stem
            if _is_useless_stem(stem):
                # Google Drive and similar sharing URLs: placeholder title that
                # resolve_items will replace with the real filename from the API
                title = f"item_{len(items) + 1}"
            else:
                title = _infer_title(stem, tractate)
        items.append({"audio_url": url.strip(), "title": title.strip()})
    return items


# ---------------------------------------------------------------------------
# Supabase range lookup
# ---------------------------------------------------------------------------

def _daf_label(daf: float) -> str:
    """Convert daf float to display label: 2.0 → '2', 2.5 → '2b'."""
    if daf % 1 == 0:
        return str(int(daf))
    return f"{int(daf)}b"


def _parse_range_part(range_part: str) -> Tuple[float, float]:
    """Parse 'N-M' or 'N' into (daf_start, daf_end)."""
    m = re.match(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", range_part)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^(\d+(?:\.\d+)?)$", range_part)
    if m:
        daf = float(m.group(1))
        return daf, daf
    raise ValueError(
        f"Cannot parse daf range {range_part!r}. "
        "Expected 'N-M' (e.g. '2-26') or a single daf number."
    )


def _parse_supabase_ranges(range_str: str) -> List[Tuple[str, float, float]]:
    """
    Parse a multi-segment range string into a list of (tractate, daf_start, daf_end) tuples.

    Supported formats:
      Single range  : 'Menachot 2-26'
      Multi compact : 'Hullin 3, 5-10, 15, 17, 20-30'
                      (tractate carries over to bare number/range segments)
      Multi explicit: 'Hullin 3, Hullin 5-10, Hullin 15'
      Mixed         : 'Hullin 2-10, Menachot 5-8, Hullin 20'
                      (a new tractate name resets the current tractate)
    """
    segments = [s.strip() for s in range_str.split(",")]
    results: List[Tuple[str, float, float]] = []
    current_tractate: Optional[str] = None

    for seg in segments:
        if not seg:
            continue

        # Try "Tractate N-M" or "Tractate N" (tractate = one or more letter/space tokens)
        m = re.match(r"^([A-Za-z][A-Za-z ]+?)\s+(\d[\d.\-]*)$", seg)
        if m:
            raw_tractate = m.group(1).strip()
            range_part   = m.group(2).strip()
            _key = re.sub(r"[^a-z]", "", raw_tractate.lower())
            current_tractate = MASECHTA_MAP.get(_key, raw_tractate)
        else:
            # Bare number or range: "5", "5-10"
            m2 = re.match(r"^(\d[\d.\-]*)$", seg)
            if not m2:
                raise ValueError(
                    f"Cannot parse segment {seg!r}. "
                    "Expected 'Tractate N', 'Tractate N-M', 'N', or 'N-M'."
                )
            if current_tractate is None:
                raise ValueError(
                    f"Segment {seg!r} has no tractate. "
                    "Start with a tractate name, e.g. 'Hullin 3, 5-10, 15'."
                )
            range_part = m2.group(1)

        daf_start, daf_end = _parse_range_part(range_part)
        results.append((current_tractate, daf_start, daf_end))

    if not results:
        raise ValueError(f"No valid segments found in {range_str!r}")

    return results


def _resolve_soundcloud_track(track_id: str) -> Optional[str]:
    """
    Convert a SoundCloud track ID to a direct MP3 stream URL.

    SoundCloud API v2 two-step flow:
      1. GET /tracks/{id}?client_id=... → track metadata with media.transcodings
      2. GET {transcoding.url}?client_id=... → {"url": "<actual stream URL>"}

    Prefers the progressive MP3 transcoding (direct download-style URL).
    Falls back to any available transcoding if progressive MP3 is absent.
    Returns None if SOUNDCLOUD_CLIENT_ID is unset or resolution fails.
    """
    if not SOUNDCLOUD_CLIENT_ID:
        return None

    # Step 1: fetch track metadata
    track_url = (
        f"https://api-v2.soundcloud.com/tracks/{track_id}"
        f"?client_id={SOUNDCLOUD_CLIENT_ID}"
    )
    try:
        resp = requests.get(track_url, headers=_SC_HEADERS, timeout=15)
    except Exception as e:
        logger.warning(f"  SoundCloud track fetch error for {track_id}: {e}")
        return None

    if resp.status_code != 200:
        logger.warning(
            f"  SoundCloud track API → HTTP {resp.status_code} for track {track_id}. "
            f"Response: {resp.text[:200]}"
        )
        return None

    try:
        track_data = resp.json()
    except Exception as e:
        logger.warning(f"  SoundCloud track {track_id}: could not parse JSON — {e}")
        return None

    transcodings = (track_data.get("media") or {}).get("transcodings", [])
    if not transcodings:
        logger.warning(f"  SoundCloud track {track_id}: no transcodings in response")
        return None

    # Prefer progressive (direct-download) MP3; fall back to first available
    chosen = None
    for t in transcodings:
        fmt = t.get("format", {})
        if fmt.get("protocol") == "progressive" and "mpeg" in fmt.get("mime_type", ""):
            chosen = t
            break
    if not chosen:
        chosen = transcodings[0]

    # Step 2: resolve the transcoding URL to an actual stream URL
    transcoding_url = chosen.get("url", "")
    if not transcoding_url:
        logger.warning(f"  SoundCloud track {track_id}: transcoding entry has no url field")
        return None

    try:
        sep = "&" if "?" in transcoding_url else "?"
        stream_resp = requests.get(
            f"{transcoding_url}{sep}client_id={SOUNDCLOUD_CLIENT_ID}",
            headers=_SC_HEADERS,
            timeout=15,
        )
    except Exception as e:
        logger.warning(f"  SoundCloud transcoding fetch error for track {track_id}: {e}")
        return None

    if stream_resp.status_code != 200:
        logger.warning(
            f"  SoundCloud transcoding API → HTTP {stream_resp.status_code} for track {track_id}"
        )
        return None

    stream_url = stream_resp.json().get("url")
    if not stream_url:
        logger.warning(
            f"  SoundCloud transcoding response for track {track_id} missing 'url' key. "
            f"Keys: {list(stream_resp.json().keys())}"
        )
    return stream_url


def _query_supabase_episodes(
    tractate: str,
    daf_min: float,
    daf_max: float,
    supabase_key: str,
) -> List[dict]:
    """
    Fetch all episode_audio rows for a tractate within [daf_min, daf_max].
    Returns raw Supabase rows sorted by daf.
    """
    ep_url = f"{SUPABASE_URL}/rest/v1/episode_audio"
    headers = {
        "apikey":        supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept":        "application/json",
    }
    resp = requests.get(
        ep_url,
        headers=headers,
        params=[
            ("select",   "tractate,daf,audio_url"),
            ("tractate", f"eq.{tractate}"),
            ("daf",      f"gte.{daf_min}"),
            ("daf",      f"lte.{daf_max}"),
            ("order",    "daf"),
        ],
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"Supabase query failed: HTTP {resp.status_code} — {resp.text[:300]}"
        )
    return resp.json()


def items_from_supabase_range(range_str: str, supabase_key: str) -> List[dict]:
    """
    Query Supabase episode_audio for one or more tractate + daf ranges and
    return items suitable for the sofer.ai batch manifest.

    range_str supports:
      Single range  : 'Menachot 2-26'
      Multi compact : 'Hullin 3, 5-10, 15, 17, 20-30'
      Multi explicit: 'Hullin 3, Hullin 5-10, Hullin 15'
      Mixed         : 'Hullin 2-10, Menachot 5-8, Hullin 20'

    Returns list of {"audio_url": ..., "title": ...} with exact tractate/daf
    labels (e.g. 'Menachot 2', 'Menachot 2b') so downstream SRT files are
    named correctly without any filename inference.
    """
    if not supabase_key:
        raise RuntimeError(
            "A Supabase key is required for --supabase-range.\n"
            "Set SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY, "
            "or pass --supabase-key."
        )

    segments = _parse_supabase_ranges(range_str)

    # Group segments by tractate so we minimise Supabase round-trips.
    # For each tractate, fetch [min_daf, max_daf] in one query, then
    # filter rows to only those covered by at least one segment.
    from collections import defaultdict
    by_tractate: dict = defaultdict(list)
    for tractate, daf_start, daf_end in segments:
        by_tractate[tractate].append((daf_start, daf_end))

    # Collect items in the order the user specified segments, deduplicating
    # by (tractate, daf) in case ranges overlap.
    seen: set = set()
    items: List[dict] = []
    skipped = 0

    # We need rows keyed by (tractate, daf) for the ordered pass below.
    row_map: dict = {}  # (tractate, daf) → audio_url
    for tractate, ranges in by_tractate.items():
        daf_min = min(r[0] for r in ranges)
        daf_max = max(r[1] for r in ranges)
        logger.info(
            f"Querying Supabase: {tractate} daf "
            f"{_daf_label(daf_min)}–{_daf_label(daf_max)}"
            + (f" ({len(ranges)} segment(s))" if len(ranges) > 1 else "")
        )
        rows = _query_supabase_episodes(tractate, daf_min, daf_max, supabase_key)
        logger.info(f"  {tractate}: {len(rows)} row(s) in broad range")
        for row in rows:
            daf = float(row.get("daf", 0))
            row_map[(tractate, daf)] = (row.get("audio_url") or "").strip()

    # Walk segments in order, preserving user-specified ordering
    for tractate, daf_start, daf_end in segments:
        # Collect all dafs in this segment (from the fetched rows)
        matching = sorted(
            daf for (t, daf) in row_map if t == tractate
            and daf_start <= daf <= daf_end
        )
        if not matching:
            logger.warning(
                f"  No episodes found for {tractate} daf "
                f"{_daf_label(daf_start)}–{_daf_label(daf_end)} — skipping segment"
            )
            continue

        for daf in matching:
            key = (tractate, daf)
            if key in seen:
                continue
            seen.add(key)

            audio_url = row_map[key]
            title = f"{tractate} {_daf_label(daf)}"

            if audio_url.startswith("soundcloud-track://"):
                track_id = audio_url.removeprefix("soundcloud-track://")
                if not SOUNDCLOUD_CLIENT_ID:
                    logger.warning(
                        f"  {title}: skipping — soundcloud-track:// URI requires SOUNDCLOUD_CLIENT_ID. "
                        "Export it in the same terminal: export SOUNDCLOUD_CLIENT_ID=<your_key>"
                    )
                    skipped += 1
                    continue
                resolved = _resolve_soundcloud_track(track_id)
                if resolved:
                    logger.info(f"  {title}: resolved soundcloud-track://{track_id} → stream URL")
                    audio_url = resolved
                else:
                    logger.warning(
                        f"  {title}: skipping — SoundCloud API could not resolve track {track_id} "
                        "(see warnings above for the API response)"
                    )
                    skipped += 1
                    continue

            if not audio_url:
                logger.warning(f"  {title}: skipping — no audio_url in Supabase row")
                skipped += 1
                continue

            items.append({"audio_url": audio_url, "title": title})

    if not items and skipped == 0:
        tractates_str = ", ".join(by_tractate.keys())
        raise RuntimeError(
            f"No episodes found in Supabase for: {range_str}\n"
            f"Checked tractate(s): {tractates_str}\n"
            "Check that the tractate names match exactly and that episode_audio is populated."
        )

    if skipped:
        logger.warning(f"  Skipped {skipped} episode(s) (no resolvable URL)")
    logger.info(f"  Total: {len(items)} item(s) to transcribe")
    return items


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    global SOFER_API_KEY  # may be overridden by --api-key argument

    parser = argparse.ArgumentParser(
        description="Submit audio files to Sofer.ai for batch transcription.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = parser.add_mutually_exclusive_group()
    src.add_argument("--filenames", metavar="FILE", nargs="+",
                     help="Audio filenames at --base-url (e.g. menachot79.mp3 menachot80.mp3)")
    src.add_argument("--audio-dir", metavar="DIR",
                     help="Scan a local directory for audio files (requires --base-url)")
    src.add_argument("--url-file", metavar="FILE",
                     help="Text file with one audio URL per line (direct links or Google Drive share links)")
    src.add_argument("--supabase-range", metavar="RANGE",
                     help="Look up audio URLs from Supabase episode_audio table by tractate + daf range. "
                          "Supports a single range ('Menachot 2-26'), individual dafs, and "
                          "comma-separated multi-segment specs. "
                          "Compact form (tractate carries over to bare segments): "
                          "'Hullin 3, 5-10, 15, 17, 20-30'. "
                          "Explicit form: 'Hullin 3, Hullin 5-10, Hullin 15'. "
                          "Mixed tractates: 'Hullin 2-10, Menachot 5-8, Hullin 20'. "
                          "Missing dafs in a range are skipped gracefully. "
                          "soundcloud-track:// URIs are resolved via the SoundCloud API if "
                          "SOUNDCLOUD_CLIENT_ID is set.")
    src.add_argument("--status", metavar="BATCH_ID",
                     help="Print status for an existing batch (no new submission)")
    src.add_argument("--sites", action="store_true",
                     help="List the sites supported by Sofer.ai's link-extraction endpoint and exit")

    parser.add_argument("--base-url", metavar="URL",
                        help="Base URL where the audio files are hosted (required with --filenames or --audio-dir)")
    parser.add_argument("--tractate", default="Shiurim",
                        help="Tractate name used as batch_title and for title inference "
                             "(default: Shiurim; not needed with --supabase-range)")
    parser.add_argument("--supabase-key", default=SUPABASE_KEY,
                        help="Supabase API key for --supabase-range "
                             "(overrides SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY env vars)")
    parser.add_argument("--poll", action="store_true",
                        help="After submitting, keep polling until the batch is done")
    parser.add_argument("--download-dir", metavar="DIR",
                        help="Download completed SRT files to this directory (implies --poll)")
    parser.add_argument("--from-json", metavar="DIR",
                        help="Re-generate SRT files from .json files previously saved by "
                             "--diagnose, without making any API calls. "
                             "E.g. --from-json ./srt --download-dir ./srt")
    parser.add_argument("--diagnose", action="store_true",
                        help="Dump raw API response JSON for each transcription during download "
                             "(use when SRT download fails to see what the API actually returns)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--api-key", default=SOFER_API_KEY,
                        help="Sofer.ai API key (overrides SOFER_API_KEY env var and built-in default)")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Allow overriding key via argument
    SOFER_API_KEY = args.api_key

    # Normalise tractate spelling so e.g. "Chullin" → "Hullin"
    _t_key = re.sub(r"[^a-z]", "", args.tractate.lower())
    args.tractate = MASECHTA_MAP.get(_t_key, args.tractate)

    # --sites: list supported link-extraction sites
    if args.sites:
        sites = supported_sites()
        print("Sites supported by Sofer.ai link extraction:")
        for s in sites:
            print(f"  {s['name']:20s}  {s['url']}")
        return

    # --status: just show status (and optionally download)
    if args.status:
        status = get_batch_status(args.status)
        print_status(status)
        if args.poll and status["status"] not in ("COMPLETED", "FAILED"):
            status = poll_until_done(args.status)
            print_status(status)
        if args.download_dir:
            out_dir = Path(args.download_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            for t in status.get("transcriptions", []):
                if t["status"] == "COMPLETED":
                    download_srt(t["id"], t["title"], out_dir, diagnose=args.diagnose)
        return

    # --from-json: re-generate SRTs from previously saved .json files
    if args.from_json:
        json_dir = Path(args.from_json)
        out_dir  = Path(args.download_dir) if args.download_dir else json_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            logger.error(f"No .json files found in {json_dir}")
            sys.exit(1)
        logger.info(f"Re-generating SRTs from {len(json_files)} JSON file(s) in {json_dir}…")
        for jf in json_files:
            title = jf.stem  # e.g. "Menachot 73"
            safe  = re.sub(r"[^\w\s-]", "_", title).strip()
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"  Could not parse {jf.name}: {e}")
                continue
            timestamps = data.get("timestamps")
            if not timestamps:
                logger.warning(f"  No timestamps in {jf.name}, skipping")
                continue
            srt_text = _build_srt_from_timestamps(timestamps)
            out_path = out_dir / f"{safe}.srt"
            out_path.write_text(srt_text, encoding="utf-8")
            logger.info(f"  {jf.name} → {out_path.name} ({len(timestamps)} words)")
        return

    # Build items list
    if args.filenames:
        if not args.base_url:
            parser.error("--filenames requires --base-url")
        items = items_from_filenames(args.filenames, args.base_url, args.tractate)
        batch_title = args.tractate
    elif args.audio_dir:
        if not args.base_url:
            parser.error("--audio-dir requires --base-url")
        items = items_from_dir(Path(args.audio_dir), args.base_url, args.tractate)
        batch_title = args.tractate
    elif args.url_file:
        items = items_from_url_file(Path(args.url_file), args.tractate)
        batch_title = args.tractate
    elif args.supabase_range:
        items = items_from_supabase_range(args.supabase_range, args.supabase_key)
        # Derive batch title from the unique tractate(s) in the parsed segments
        _segs = _parse_supabase_ranges(args.supabase_range)
        _tractates = list(dict.fromkeys(t for t, _, _ in _segs))  # unique, ordered
        batch_title = " / ".join(_tractates)
    else:
        parser.error("Provide --filenames, --audio-dir, --url-file, --supabase-range, or --status")

    if not items:
        logger.error("No audio sources found.")
        sys.exit(1)

    # Detect Google Drive folder URL (common mistake)
    for item in items:
        if _is_gdrive_folder(item["audio_url"]):
            print(
                "\nERROR: Google Drive folder URLs are not supported.\n"
                "You need individual file share links, one per file.\n\n"
                "How to get them:\n"
                "  1. Open the folder in Google Drive\n"
                "  2. Right-click each audio file → 'Share' → 'Copy link'\n"
                "     (URL looks like: https://drive.google.com/file/d/FILE_ID/view?usp=sharing)\n"
                "  3. Put each share link on its own line in a text file\n"
                "  4. Run: python sofer_batch.py --url-file links.txt --tractate Menachot\n\n"
                "The script will automatically resolve each share link to a direct download URL.\n"
            )
            sys.exit(1)

    # Auto-resolve sharing URLs (Google Drive file links, Dropbox, etc.)
    if any(_is_sharing_url(item["audio_url"]) for item in items):
        logger.info("Resolving sharing URLs via Sofer.ai link extraction…")
        items = resolve_items(items)

    print(f"Found {len(items)} audio file(s) to transcribe:")
    for item in items:
        print(f"  {item['title']}")
        print(f"    {item['audio_url']}")

    # Upload manifest → submit batch
    batch_file_id = upload_manifest(items, batch_title)
    batch_id = submit_batch(batch_file_id, batch_title)

    print(f"\n✓ Batch submitted. batch_id: {batch_id}")
    print(f"  Check status:    python sofer_batch.py --status {batch_id}")
    print(f"  Poll + download: python sofer_batch.py --status {batch_id} --poll --download-dir ./srt\n")

    # Optionally poll
    if args.download_dir:
        args.poll = True

    if args.poll:
        status = poll_until_done(batch_id)
        print_status(status)
        if args.download_dir:
            out_dir = Path(args.download_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Downloading SRT files to {out_dir}…")
            for t in status.get("transcriptions", []):
                if t["status"] == "COMPLETED":
                    download_srt(t["id"], t["title"], out_dir, diagnose=args.diagnose)


if __name__ == "__main__":
    main()
