#!/usr/bin/env python3
"""
Upload daf-processor output files to Supabase.

Populates two tables:
  shiur_content   — one row per daf (segmentation JSON, rewrite, final)
  shiur_sections  — one row per macro segment (title, timestamp, content, full-text index)

Required environment variables:
  SUPABASE_URL          e.g. https://zewdazoijdpakugfvnzt.supabase.co
  SUPABASE_SERVICE_KEY  Service-role key from Supabase dashboard → Settings → API

Usage:
  python upload_to_supabase.py                        # upload all output/
  python upload_to_supabase.py --dir output/menachot_80
  python upload_to_supabase.py --dry-run              # preview, no writes
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
CONTENT_TABLE  = "shiur_content"
SECTIONS_TABLE = "shiur_sections"

PASS_FILES = {
    "segmentation": "01_segmentation.json",
    "rewrite":      "02_rewrite.md",
    "final":        "03_final.md",
}


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
    """POST one or more rows as an upsert. rows can be a dict or a list of dicts."""
    if dry_run:
        count = len(rows) if isinstance(rows, list) else 1
        print(f"  [DRY RUN] Would upsert {count} row(s) → {label}")
        return True
    h = {**headers, "Prefer": "resolution=merge-duplicates"}
    resp = requests.post(url, headers=h, json=rows, timeout=60)
    if resp.status_code in (200, 201):
        return True
    logger.error(f"  ✗ {label}: HTTP {resp.status_code} — {resp.text[:300]}")
    return False


def daf_to_float(daf: int, amud: Optional[str]) -> float:
    """Encode (daf, amud) as a numeric(4,1) float matching the episode_audio convention.
    N.0 = amud aleph / whole-daf shiur; N.5 = amud bet shiur."""
    return float(daf) + (0.5 if amud == 'b' else 0.0)


def daf_label(daf_float: float) -> str:
    """Format a daf float for display: 11.0 → '11', 11.5 → '11b'."""
    return str(int(daf_float)) if daf_float % 1 == 0 else f"{int(daf_float)}b"



# Canonical tractate names for dir-name → Supabase normalisation.
# Any spelling found in directory names → the exact name used in Supabase tables.
_TRACTATE_CANONICAL = {
    "chullin": "Hullin",
    "hullin":  "Hullin",
}


def parse_dir_name(dir_name: str) -> Tuple[Optional[str], Optional[float]]:
    """Return (tractate, daf_float) from a job directory name like 'berakhot_11' or 'berakhot_11b'."""
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
    """'MM:SS' → float seconds."""
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
# Section splitting
# ---------------------------------------------------------------------------

def split_rewrite_into_sections(rewrite: str) -> List[dict]:
    """
    Split a markdown rewrite on ## (macro) and ### (micro) headers.

    Returns list of dicts:
      {'level': 'macro'|'micro', 'title': str, 'content': str,
       'parent_macro_title': str|None}

    The top-level # daf header is skipped. Content includes the header line.
    Old rewrites with only ## headers produce macro-only output (no micros).
    """
    sections: List[dict] = []
    current_macro_title: Optional[str] = None
    current_title: Optional[str] = None
    current_level: Optional[str] = None
    current_lines: List[str] = []

    def flush():
        if current_title is not None and current_level is not None:
            sections.append({
                "level":              current_level,
                "title":              current_title,
                "content":            "\n".join(current_lines).strip(),
                "parent_macro_title": None if current_level == "macro" else current_macro_title,
            })

    for line in rewrite.splitlines():
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
    rewrite_file = job_dir / PASS_FILES["rewrite"]
    if not rewrite_file.exists():
        return []

    rewrite = rewrite_file.read_text(encoding="utf-8")
    sections = split_rewrite_into_sections(rewrite)
    if not sections:
        return []

    seg = load_segmentation(job_dir / PASS_FILES["segmentation"])
    macros = seg.get("macro_segments", []) if seg else []

    # Build lookups for matching by title (case-insensitive), with positional fallback.
    macro_by_title = {m["title"].strip().lower(): m for m in macros}

    rows: List[dict] = []
    segment_index = 0          # global sequential index within this daf
    macro_section_pos = 0      # counts macro sections seen so far (positional fallback)

    # Maps macro title → (segment_index, segmentation_dict) for micro matching
    macro_info: dict = {}

    for section in sections:
        level = section["level"]
        title = section["title"]
        content = section["content"]

        if level == "macro":
            seg_match = macro_by_title.get(title.strip().lower())
            if seg_match is None and macro_section_pos < len(macros):
                seg_match = macros[macro_section_pos]  # positional fallback

            ts_str  = seg_match["timestamp"] if seg_match else None
            ts_secs = ts_to_seconds(ts_str) if ts_str else None

            rows.append({
                "tractate":             tractate,
                "daf":                  daf,
                "segment_index":        segment_index,
                "parent_segment_index": None,
                "title":                title,
                "timestamp_mm_ss":      ts_str,
                "timestamp_secs":       ts_secs,
                "content":              content,
            })
            macro_info[title] = (segment_index, seg_match)
            macro_section_pos += 1

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

            rows.append({
                "tractate":             tractate,
                "daf":                  daf,
                "segment_index":        segment_index,
                "parent_segment_index": parent_seg_index,
                "title":                title,
                "timestamp_mm_ss":      ts_str,
                "timestamp_secs":       ts_secs,
                "content":              content,
            })

        segment_index += 1

    return rows


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_job(tractate: str, daf: float, job_dir: Path,
               headers: dict, dry_run: bool) -> bool:
    label = f"{tractate} {daf_label(daf)}"
    ok = True

    # shiur_content row
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

    # shiur_sections rows
    section_rows = build_section_rows(tractate, daf, job_dir)
    if section_rows:
        url = f"{SUPABASE_URL}/rest/v1/{SECTIONS_TABLE}?on_conflict=tractate,daf,segment_index"
        if not upsert(url, section_rows, headers, dry_run,
                      f"{label} → {SECTIONS_TABLE} ({len(section_rows)} sections)"):
            ok = False
        else:
            logger.info(f"  ✓ {label} → {SECTIONS_TABLE} ({len(section_rows)} sections)")
    else:
        logger.debug(f"  {label}: no rewrite file — skipping {SECTIONS_TABLE}")

    return ok


def collect_jobs(output_dir: Path, single_dir: Optional[Path]):
    dirs = [single_dir] if single_dir else sorted(
        d for d in output_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    jobs: List[Tuple[str, float, Path]] = []
    for d in dirs:
        tractate, daf_float = parse_dir_name(d.name)
        if tractate is None:
            logger.warning(f"Cannot parse tractate/daf from '{d.name}', skipping")
            continue
        if any((d / f).exists() for f in PASS_FILES.values()):
            jobs.append((tractate, daf_float, d))
    return jobs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Upload daf-processor output to Supabase (shiur_content + shiur_sections)"
    )
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--dir", default=None, help="Upload a single job directory")
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

    jobs = collect_jobs(Path(args.output_dir), Path(args.dir) if args.dir else None)
    if not jobs:
        print("No jobs found.")
        return

    print(f"Found {len(jobs)} job(s)")
    headers = get_headers(service_key or "dry-run-key")

    succeeded = failed = 0
    for tractate, daf, job_dir in jobs:
        if upload_job(tractate, daf, job_dir, headers, args.dry_run):
            succeeded += 1
        else:
            failed += 1

    print(f"\nDone: {succeeded} succeeded, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
