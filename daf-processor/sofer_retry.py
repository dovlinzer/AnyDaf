#!/usr/bin/env python3
"""
sofer_retry.py — Re-submit FAILED transcriptions from a sofer_batch.py status output.

Reads status lines from a file or stdin, extracts every FAILED item by title,
looks up the corresponding audio URL in Supabase, and submits a new batch.

Usage:

  # Pipe status output directly:
  python sofer_batch.py --status <batch-id> | python sofer_retry.py

  # Or save status to a file and pass it:
  python sofer_batch.py --status <batch-id> > status.txt
  python sofer_retry.py status.txt

  # Optionally poll until done and download SRTs:
  python sofer_retry.py status.txt --poll --download-dir ./srt
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Import shared helpers from sofer_batch (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from sofer_batch import (
    MASECHTA_MAP,
    SOFER_API_KEY,
    SUPABASE_KEY,
    SOUNDCLOUD_CLIENT_ID,
    _daf_label,
    _resolve_soundcloud_track,
    _query_supabase_episodes,
    upload_manifest,
    submit_batch,
    poll_until_done,
    print_status,
    download_srt,
)

logger = logging.getLogger(__name__)

# Matches lines like:
#   [FAILED      ] Ketubot 58  3617s  (dbf9ee2a-...)
#   [FAILED      ] Gittin 90  (b4021789-...)   ← no duration
_STATUS_LINE_RE = re.compile(
    r"\[FAILED\s*\]\s+(.+?)\s+(?:\d+s\s+)?\([0-9a-f-]{36}\)",
    re.IGNORECASE,
)

# Matches a title like "Ketubot 58" or "Nazir 44b"
_TITLE_RE = re.compile(r"^([A-Za-z][A-Za-z ]+?)\s+(\d+b?)$", re.IGNORECASE)


def parse_failed_titles(text: str) -> list[str]:
    """Return the list of titles (e.g. ['Ketubot 58', 'Nazir 44b']) for all FAILED lines."""
    titles = []
    for line in text.splitlines():
        m = _STATUS_LINE_RE.search(line)
        if m:
            titles.append(m.group(1).strip())
    return titles


def title_to_tractate_daf(title: str) -> tuple[str, float] | None:
    """
    Convert 'Ketubot 58' → ('Ketubot', 58.0)
             'Nazir 44b'  → ('Nazir',  44.5)
    Returns None if the title cannot be parsed.
    """
    m = _TITLE_RE.match(title)
    if not m:
        return None
    raw_tractate = m.group(1).strip()
    daf_str = m.group(2).strip().lower()

    # Normalise tractate name
    key = re.sub(r"[^a-z]", "", raw_tractate.lower())
    tractate = MASECHTA_MAP.get(key, raw_tractate)

    daf = float(daf_str.rstrip("b"))
    if daf_str.endswith("b"):
        daf += 0.5
    return tractate, daf


def items_from_failed_titles(titles: list[str], supabase_key: str) -> list[dict]:
    """
    Resolve a list of titles to Supabase audio URLs.
    Groups by tractate for efficient querying.
    Returns items suitable for the sofer.ai batch manifest.
    """
    if not supabase_key:
        raise RuntimeError(
            "A Supabase key is required.\n"
            "Set SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY in your environment."
        )

    # Parse and group by tractate
    by_tractate: dict[str, list[float]] = {}
    unparseable = []
    for title in titles:
        result = title_to_tractate_daf(title)
        if result is None:
            unparseable.append(title)
            continue
        tractate, daf = result
        by_tractate.setdefault(tractate, []).append(daf)

    if unparseable:
        logger.warning(f"Could not parse {len(unparseable)} title(s): {unparseable}")

    if not by_tractate:
        raise RuntimeError("No parseable FAILED titles found in the input.")

    # Fetch rows from Supabase; build (tractate, daf) → audio_url map
    row_map: dict[tuple[str, float], str] = {}
    for tractate, dafs in by_tractate.items():
        daf_min = min(dafs)
        daf_max = max(dafs)
        logger.info(
            f"Querying Supabase: {tractate} daf "
            f"{_daf_label(daf_min)}–{_daf_label(daf_max)} ({len(dafs)} needed)"
        )
        rows = _query_supabase_episodes(tractate, daf_min, daf_max, supabase_key)
        for row in rows:
            daf = float(row.get("daf", 0))
            row_map[(tractate, daf)] = (row.get("audio_url") or "").strip()

    # Build items in the original title order
    items = []
    missing = []
    skipped = []
    for title in titles:
        result = title_to_tractate_daf(title)
        if result is None:
            continue
        tractate, daf = result
        key = (tractate, daf)
        audio_url = row_map.get(key)
        if audio_url is None:
            missing.append(title)
            continue

        if audio_url.startswith("soundcloud-track://"):
            track_id = audio_url.removeprefix("soundcloud-track://")
            if not SOUNDCLOUD_CLIENT_ID:
                logger.warning(
                    f"  {title}: skipping — soundcloud-track:// URI requires "
                    "SOUNDCLOUD_CLIENT_ID. Export it in your terminal."
                )
                skipped.append(title)
                continue
            resolved = _resolve_soundcloud_track(track_id)
            if resolved:
                audio_url = resolved
            else:
                logger.warning(
                    f"  {title}: skipping — could not resolve SoundCloud track {track_id}"
                )
                skipped.append(title)
                continue

        if not audio_url:
            logger.warning(f"  {title}: skipping — no audio_url in Supabase row")
            skipped.append(title)
            continue

        items.append({"audio_url": audio_url, "title": title})

    if missing:
        logger.warning(f"  {len(missing)} title(s) not found in Supabase: {missing}")
    if skipped:
        logger.warning(f"  {len(skipped)} title(s) skipped (no resolvable URL)")

    return items


def main():
    parser = argparse.ArgumentParser(
        description="Re-submit FAILED sofer.ai transcriptions from a status output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "status_file",
        nargs="?",
        help="File containing sofer_batch.py status output (default: stdin)",
    )
    parser.add_argument(
        "--batch-title",
        default="Retry",
        help="Title for the new batch (default: 'Retry')",
    )
    parser.add_argument(
        "--supabase-key",
        default=SUPABASE_KEY,
        help="Supabase API key (overrides SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY)",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll until the new batch is done",
    )
    parser.add_argument(
        "--download-dir",
        metavar="DIR",
        help="Download completed SRT files to this directory (implies --poll)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and look up items but do not submit the batch",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Read status text
    if args.status_file:
        text = Path(args.status_file).read_text(encoding="utf-8", errors="replace")
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        text = sys.stdin.read()

    # Parse failed titles
    titles = parse_failed_titles(text)
    if not titles:
        logger.error("No FAILED lines found in the input.")
        sys.exit(1)
    logger.info(f"Found {len(titles)} FAILED item(s).")

    # Look up audio URLs from Supabase
    items = items_from_failed_titles(titles, args.supabase_key)
    if not items:
        logger.error("No items could be resolved. Nothing to submit.")
        sys.exit(1)

    print(f"\n{len(items)} item(s) to resubmit:")
    for item in items:
        print(f"  {item['title']}")
        print(f"    {item['audio_url']}")

    if args.dry_run:
        print("\n[dry-run] Stopping before submission.")
        return

    # Derive batch title from the unique tractates present
    tractates = list(dict.fromkeys(
        title_to_tractate_daf(item["title"])[0]
        for item in items
        if title_to_tractate_daf(item["title"])
    ))
    batch_title = args.batch_title if args.batch_title != "Retry" else " / ".join(tractates) + " (retry)"

    # Submit
    batch_file_id = upload_manifest(items, batch_title)
    batch_id = submit_batch(batch_file_id, batch_title)

    print(f"\n✓ Retry batch submitted. batch_id: {batch_id}")
    print(f"  Check status:    python3 sofer_batch.py --status {batch_id}")
    print(f"  Poll + download: python3 sofer_batch.py --status {batch_id} --poll --download-dir ./srt\n")

    if args.download_dir:
        args.poll = True

    if args.poll:
        status = poll_until_done(batch_id)
        print_status(status)
        if args.download_dir:
            out_dir = Path(args.download_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            for t in status.get("transcriptions", []):
                if t["status"] == "COMPLETED":
                    download_srt(t["id"], t["title"], out_dir)


if __name__ == "__main__":
    main()
