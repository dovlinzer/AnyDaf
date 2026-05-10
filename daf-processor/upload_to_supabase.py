#!/usr/bin/env python3
"""
Upload daf-processor output files to Supabase.

Populates tables:
  shiur_content   — one row per daf (segmentation JSON, rewrite, final)
  shiur_sections  — one row per segment with talmudic text and source_type
                    (only when --sections flag is passed; no embeddings)

Required environment variables:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key from Supabase dashboard → Settings → API

Usage:
  python upload_to_supabase.py                                    # shiur_content for all output/
  python upload_to_supabase.py --dir output/menachot_80           # single daf, shiur_content only
  python upload_to_supabase.py --sections                         # all dafs, both tables
  python upload_to_supabase.py --dir output/berakhot_11 --sections # single daf, both tables
  python upload_to_supabase.py --dry-run --sections               # preview, no writes
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import time

import requests
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
CONTENT_TABLE  = "shiur_content"
SECTIONS_TABLE = "shiur_sections"

PASS_FILES = {
    "segmentation": "01_segmentation.json",
    "rewrite":      "02_rewrite.md",
    "cleanup":      "025_cleanup.md",
    "final":        "03_final.md",
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
            wait = 2.0 * (2 ** attempt)   # 2 4 8 16 32 64 s
            logger.warning(f"  Network error (attempt {attempt + 1}/{retries}), "
                           f"retrying in {wait:.0f}s: {e}")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_headers(service_key: str) -> dict:
    return {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
    }


def upsert(url: str, rows, headers: dict, dry_run: bool, label: str) -> bool:
    if dry_run:
        count = len(rows) if isinstance(rows, list) else 1
        print(f"  [DRY RUN] Would upsert {count} row(s) → {label}")
        return True
    h = {**headers, "Prefer": "resolution=merge-duplicates"}
    resp = _request("POST", url, headers=h, json=rows, timeout=60)
    if resp.status_code in (200, 201):
        return True
    logger.error(f"  ✗ {label}: HTTP {resp.status_code} — {resp.text[:300]}")
    return False


def delete_sections_for_daf(tractate: str, daf: float, headers: dict, dry_run: bool) -> bool:
    """Delete all shiur_sections rows for (tractate, daf) before re-upserting."""
    if dry_run:
        print(f"  [DRY RUN] Would delete existing {SECTIONS_TABLE} rows for "
              f"{tractate} {daf_label(daf)}")
        return True
    url = (f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}"
           f"?tractate=eq.{requests.utils.quote(tractate)}&daf=eq.{daf}")
    resp = _request("DELETE", url, headers=headers, timeout=30)
    if resp.status_code in (200, 204):
        return True
    logger.error(f"  ✗ delete {tractate} {daf}: HTTP {resp.status_code} — {resp.text[:200]}")
    return False


def daf_to_float(daf: int, amud: Optional[str]) -> float:
    return float(daf) + (0.5 if amud == 'b' else 0.0)


def daf_label(daf_float: float) -> str:
    return str(int(daf_float)) if daf_float % 1 == 0 else f"{int(daf_float)}b"


_TRACTATE_CANONICAL = {
    "chullin":  "Hullin",
    "hullin":   "Hullin",
    "eruvin":   "Eiruvin",
    "megilah":  "Megillah",
    "megila":   "Megillah",
}


def parse_dir_name(dir_name: str) -> Tuple[Optional[str], Optional[float]]:
    parts = dir_name.split("_")
    for i in range(len(parts) - 1, -1, -1):
        m = re.match(r'^(\d+)([ab])?$', parts[i], re.IGNORECASE)
        if m:
            base = int(m.group(1))
            amud = m.group(2).lower() if m.group(2) else None
            raw = "_".join(parts[:i])
            tractate = _TRACTATE_CANONICAL.get(raw, " ".join(w.capitalize() for w in parts[:i]))
            return tractate, daf_to_float(base, amud)
    return None, None


def load_segmentation(seg_file: Path) -> Optional[dict]:
    if not seg_file.exists():
        return None
    raw = seg_file.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"  Invalid JSON in {seg_file}: {e}")
        return None


def ts_to_seconds(ts: str) -> Optional[float]:
    parts = re.split(r":", ts.strip())
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (ValueError, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# Section parsing from 03_final.md
# ---------------------------------------------------------------------------

_BLOCKQUOTE_RE = re.compile(r'^((?:>.*\n?)+)', re.MULTILINE)


def _extract_talmudic_block(content: str) -> Tuple[str, str]:
    """
    Split a section's content into (talmudic_text, lecture_text).
    The talmudic blockquote, if present, always appears at the very start of the content.
    Returns (blockquote_str, remaining_lecture_text).
    """
    stripped = content.lstrip('\n')
    m = _BLOCKQUOTE_RE.match(stripped)
    if m and '**Hebrew/Aramaic:**' in m.group(0):
        talmudic = m.group(0).strip()
        lecture = stripped[m.end():].strip()
        return talmudic, lecture
    return '', stripped.strip()


def _detect_source_type(title: str, talmudic_text: str) -> str:
    if re.match(r'mishnah', title, re.IGNORECASE):
        return 'mishnah'
    if talmudic_text:
        return 'talmudic'
    return 'shiur_discussion'


def split_final_into_sections(text: str) -> List[dict]:
    """
    Split 03_final.md on ## (macro) and ### (micro) headers.

    Returns list of dicts:
      {'level': 'macro'|'micro', 'title': str,
       'content': str,           # lecture text only (blockquote stripped)
       'talmudic_text': str,     # Hebrew/Aramaic + English translation blockquote
       'source_type': str,       # 'talmudic' | 'mishnah' | 'shiur_discussion'
       'parent_macro_title': str|None}
    """
    sections: List[dict] = []
    current_macro_title: Optional[str] = None
    current_title: Optional[str] = None
    current_level: Optional[str] = None
    current_lines: List[str] = []

    def flush():
        if current_title is None or current_level is None:
            return
        raw_content = "\n".join(current_lines[1:])  # skip the header line itself
        talmudic_text, lecture_text = _extract_talmudic_block(raw_content)
        source_type = _detect_source_type(current_title, talmudic_text)
        sections.append({
            "level":              current_level,
            "title":              current_title,
            "content":            lecture_text,
            "talmudic_text":      talmudic_text,
            "source_type":        source_type,
            "parent_macro_title": None if current_level == "macro" else current_macro_title,
        })

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_macro_title = current_title
            current_level = "macro"
            current_lines = [line]
        elif line.startswith("### "):
            flush()
            current_title = line[4:].strip()
            current_level = "micro"
            current_lines = [line]
        elif line.startswith("# ") and current_title is None:
            continue  # top-level daf header
        elif current_title is not None:
            current_lines.append(line)

    flush()
    return sections


# ---------------------------------------------------------------------------
# Build rows
# ---------------------------------------------------------------------------

def build_content_row(tractate: str, daf: float, job_dir: Path) -> dict:
    row: dict = {"tractate": tractate, "daf": daf}
    seg = load_segmentation(job_dir / PASS_FILES["segmentation"])
    if seg is not None:
        row["segmentation"] = seg
    for key in ("rewrite", "final"):
        f = job_dir / PASS_FILES[key]
        if f.exists():
            row[key] = f.read_text(encoding="utf-8")
    return row


def build_section_rows(tractate: str, daf: float, job_dir: Path) -> List[dict]:
    """
    Build shiur_sections rows from 03_final.md (preferred) or 02_rewrite.md (fallback).
    Timestamps come from 01_segmentation.json matched by title.
    Returns rows ready for upsert (no embeddings — column was dropped).
    """
    # Prefer 03_final.md (has talmudic blockquotes); fall back to 025_cleanup.md
    # (Hebrew/Aramaic words replaced with English, inline re-citations removed),
    # then 02_rewrite.md (raw rewrite).
    for key in ("final", "cleanup", "rewrite"):
        candidate = job_dir / PASS_FILES[key]
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            sections = split_final_into_sections(text)
            if key != "final":
                logger.debug(f"  {job_dir.name}: using {PASS_FILES[key]} (no 03_final.md)")
            break
    else:
        return []

    if not sections:
        return []

    seg = load_segmentation(job_dir / PASS_FILES["segmentation"])
    macros = seg.get("macro_segments", []) if seg else []
    macro_by_title = {m["title"].strip().lower(): m for m in macros}

    rows: List[dict] = []
    segment_index = 0
    macro_section_pos = 0
    macro_info: dict = {}  # title → (segment_index, segmentation_dict)

    for section in sections:
        level = section["level"]
        title = section["title"]

        if level == "macro":
            seg_match = macro_by_title.get(title.strip().lower())
            if seg_match is None and macro_section_pos < len(macros):
                seg_match = macros[macro_section_pos]
            ts_str  = seg_match["timestamp"] if seg_match else None
            ts_secs = ts_to_seconds(ts_str) if ts_str else None
            macro_info[title] = (segment_index, seg_match)
            macro_section_pos += 1
            parent_seg_index = None

        else:  # micro
            parent_title = section["parent_macro_title"]
            parent_seg_index, parent_seg_match = macro_info.get(parent_title, (None, None))
            ts_str  = None
            ts_secs = None
            if parent_seg_match:
                micros = parent_seg_match.get("micro_segments", [])
                micro_match = next(
                    (m for m in micros
                     if m["title"].strip().lower() == title.strip().lower()),
                    None,
                )
                if micro_match:
                    ts_str  = micro_match.get("timestamp")
                    ts_secs = ts_to_seconds(ts_str) if ts_str else None

        source_type = section.get("source_type", "shiur_discussion")

        # shiur_discussion rows have no talmudic_text and are no longer stored
        # in shiur_sections — the full interleaved shiur is in shiur_content.final
        # and fetched on demand when the user requests it.
        if source_type == "shiur_discussion":
            segment_index += 1
            continue

        rows.append({
            "tractate":             tractate,
            "daf":                  daf,
            "segment_index":        segment_index,
            "parent_segment_index": parent_seg_index,
            "title":                title,
            "timestamp_mm_ss":      ts_str,
            "timestamp_secs":       ts_secs,
            "talmudic_text":        section.get("talmudic_text") or None,
            "source_type":          source_type,
        })
        segment_index += 1

    return rows


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_job(tractate: str, daf: float, job_dir: Path,
               headers: dict, dry_run: bool, sections: bool) -> bool:
    label = f"{tractate} {daf_label(daf)}"
    ok = True

    # shiur_content
    content_row = build_content_row(tractate, daf, job_dir)
    cols = [k for k in content_row if k not in ("tractate", "daf")]
    if not cols:
        logger.warning(f"  {label}: no output files found, skipping")
        return False
    url = f"{SUPABASE_URL}/rest/v1/{CONTENT_TABLE}?on_conflict=tractate,daf"
    if not upsert(url, content_row, headers, dry_run, f"{label} → {CONTENT_TABLE}"):
        ok = False
    else:
        logger.info(f"  ✓ {label} → {CONTENT_TABLE} ({', '.join(cols)})")

    if not sections:
        return ok

    # shiur_sections
    section_rows = build_section_rows(tractate, daf, job_dir)
    if not section_rows:
        logger.warning(f"  {label}: no sections parsed, skipping {SECTIONS_TABLE}")
        return ok

    # Drop rows with no text content (nothing useful to store or search)
    before = len(section_rows)
    section_rows = [
        r for r in section_rows
        if (r.get("content") or "").strip() or (r.get("talmudic_text") or "").strip()
    ]
    skipped = before - len(section_rows)
    if skipped:
        logger.warning(f"  {label}: skipping {skipped} section(s) with empty content")
    if not section_rows:
        logger.warning(f"  {label}: no sections with content, skipping {SECTIONS_TABLE}")
        return ok
    if dry_run:
        print(f"  [DRY RUN] Would upload {len(section_rows)} sections for {label}")

    delete_sections_for_daf(tractate, daf, headers, dry_run)

    chunk_size = 50
    sections_url = f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}?on_conflict=tractate,daf,segment_index"
    all_ok = True
    for i in range(0, len(section_rows), chunk_size):
        chunk = section_rows[i:i + chunk_size]
        if not upsert(sections_url, chunk, headers, dry_run,
                      f"{label} → {SECTIONS_TABLE} [{i}:{i+len(chunk)}]"):
            all_ok = False
    if all_ok:
        logger.info(f"  ✓ {label} → {SECTIONS_TABLE} ({len(section_rows)} rows)")
    else:
        ok = False

    return ok


def collect_jobs(output_dir: Path, single_dir: Optional[Path],
                 tractate_filter: Optional[set] = None):
    dirs = [single_dir] if single_dir else sorted(
        d for d in output_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    jobs: List[Tuple[str, float, Path]] = []
    for d in dirs:
        tractate, daf_float = parse_dir_name(d.name)
        if tractate is None:
            logger.warning(f"Cannot parse tractate/daf from '{d.name}', skipping")
            continue
        if tractate_filter and tractate.lower() not in tractate_filter:
            continue
        if any((d / f).exists() for f in PASS_FILES.values()):
            jobs.append((tractate, daf_float, d))
    return jobs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Upload daf-processor output to Supabase (shiur_content + optionally shiur_sections)"
    )
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--dir", default=None, help="Upload a single job directory")
    parser.add_argument("--tractates", default=None,
                        help="Comma-separated list of tractates to upload, e.g. "
                             "\"Berakhot,Shabbat,Sanhedrin\" (case-insensitive)")
    parser.add_argument("--sections", action="store_true",
                        help="Also upload shiur_sections rows with talmudic text and source_type")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Re-upload even if rows exist (upsert always overwrites)")
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
        print("Error: SUPABASE_SERVICE_KEY not set.", file=sys.stderr)
        sys.exit(1)

    tractate_filter = (
        {t.strip().lower() for t in args.tractates.split(",")}
        if args.tractates else None
    )
    jobs = collect_jobs(
        Path(args.output_dir),
        Path(args.dir) if args.dir else None,
        tractate_filter,
    )
    if not jobs:
        print("No jobs found.")
        return

    suffix = ""
    if args.sections:
        suffix += " (with --sections)"
    if tractate_filter:
        suffix += f" (tractates: {', '.join(sorted(tractate_filter))})"
    print(f"Found {len(jobs)} job(s){suffix}")
    headers = get_headers(service_key or "dry-run-key")

    succeeded = failed = 0
    for tractate, daf, job_dir in jobs:
        if upload_job(tractate, daf, job_dir, headers, args.dry_run, args.sections):
            succeeded += 1
        else:
            failed += 1

    print(f"\nDone: {succeeded} succeeded, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
