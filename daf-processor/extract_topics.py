#!/usr/bin/env python3
"""
Extract all topical_tags from shiur_content in Supabase and produce:
  topics_raw.json    — full occurrence data: term → list of {tractate, daf, timestamps}
  topics_report.tsv  — human-readable summary sorted by breadth (# tractates), then frequency

Usage:
  python extract_topics.py
  python extract_topics.py --out-dir ./topic_analysis
  python extract_topics.py --local   # read from ./output instead of Supabase

Requires:
  SUPABASE_URL          (defaults to the project URL)
  SUPABASE_SERVICE_KEY  (or SUPABASE_ANON_KEY — anon key is sufficient for reads)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
PAGE_SIZE = 500  # rows per request


# ---------------------------------------------------------------------------
# Supabase fetch
# ---------------------------------------------------------------------------

def get_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not key:
        sys.exit("Error: set SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY")
    return key


def fetch_all_segmentations(key: str) -> list[dict]:
    """
    Page through shiur_content and return list of
    {'tractate': str, 'daf': float, 'segmentation': dict}.
    Rows with no segmentation are skipped.
    """
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    url = f"{SUPABASE_URL}/rest/v1/shiur_content"
    params = {
        "select": "tractate,daf,segmentation",
        "segmentation": "not.is.null",
        "order": "tractate,daf",
        "limit": PAGE_SIZE,
    }

    rows = []
    offset = 0
    while True:
        params["offset"] = offset
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if resp.status_code != 200:
            sys.exit(f"Supabase error {resp.status_code}: {resp.text[:300]}")
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        print(f"  fetched {len(rows)} rows...", end="\r", flush=True)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(f"  fetched {len(rows)} rows total      ")
    return rows


# ---------------------------------------------------------------------------
# Local fallback (read from ./output/)
# ---------------------------------------------------------------------------

def load_segmentation_local(seg_file: Path) -> Optional[dict]:
    raw = seg_file.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def parse_dir_name(name: str):
    parts = name.split("_")
    for i in range(len(parts) - 1, -1, -1):
        m = re.match(r"^(\d+)([ab])?$", parts[i], re.IGNORECASE)
        if m:
            base = int(m.group(1))
            amud = (m.group(2) or "").lower()
            daf = float(base) + (0.5 if amud == "b" else 0.0)
            tractate = " ".join(w.capitalize() for w in parts[:i])
            return tractate, daf
    return None, None


def fetch_all_segmentations_local(output_dir: Path) -> list[dict]:
    rows = []
    for d in sorted(output_dir.iterdir()):
        if not d.is_dir():
            continue
        seg_file = d / "01_segmentation.json"
        if not seg_file.exists():
            continue
        tractate, daf = parse_dir_name(d.name)
        if tractate is None:
            continue
        seg = load_segmentation_local(seg_file)
        if seg:
            rows.append({"tractate": tractate, "daf": daf, "segmentation": seg})
    print(f"  loaded {len(rows)} local segmentation files")
    return rows


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------

def daf_label(daf_float: float) -> str:
    return str(int(daf_float)) if daf_float % 1 == 0 else f"{int(daf_float)}b"


def extract_topics(rows: list[dict]) -> dict:
    """
    Returns a dict keyed by raw term string:
      {
        "term": str,
        "daf_count": int,
        "tractate_count": int,
        "tractates": [str, ...],          # sorted unique tractates
        "occurrences": [
          {"tractate": str, "daf": str, "timestamps": [str, ...]},
          ...
        ]
      }
    Sorted by (tractate_count desc, daf_count desc, term asc).
    """
    # term → list of occurrence dicts
    raw: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        seg = row.get("segmentation") or {}
        if isinstance(seg, str):
            try:
                seg = json.loads(seg)
            except json.JSONDecodeError:
                continue

        tractate = row["tractate"]
        daf = daf_label(float(row["daf"]))

        for tag in seg.get("topical_tags", []):
            term = tag.get("term", "").strip()
            if not term:
                continue
            timestamps = tag.get("timestamps", [])
            raw[term].append({
                "tractate": tractate,
                "daf": daf,
                "timestamps": timestamps,
            })

    # Build structured output
    result = {}
    for term, occs in raw.items():
        tractates = sorted({o["tractate"] for o in occs})
        result[term] = {
            "term": term,
            "daf_count": len(occs),
            "tractate_count": len(tractates),
            "tractates": tractates,
            "occurrences": occs,
        }

    # Sort: broadest tractate spread first, then most dafs, then alpha
    sorted_result = dict(
        sorted(
            result.items(),
            key=lambda kv: (-kv[1]["tractate_count"], -kv[1]["daf_count"], kv[0].lower()),
        )
    )
    return sorted_result


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def write_json(topics: dict, path: Path):
    path.write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(topics)} unique terms)")


def write_tsv(topics: dict, path: Path):
    lines = ["term\tdaf_count\ttractate_count\ttractates\tsample_dafs"]
    for entry in topics.values():
        # show up to 5 sample daf references
        samples = [f"{o['tractate']} {o['daf']}" for o in entry["occurrences"][:5]]
        lines.append(
            "\t".join([
                entry["term"],
                str(entry["daf_count"]),
                str(entry["tractate_count"]),
                ", ".join(entry["tractates"]),
                "; ".join(samples),
            ])
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")


def print_stats(topics: dict, total_rows: int):
    daf_counts = [v["daf_count"] for v in topics.values()]
    tractate_counts = [v["tractate_count"] for v in topics.values()]

    shas_wide = [t for t in topics.values() if t["tractate_count"] >= 10]
    multi_tractate = [t for t in topics.values() if 2 <= t["tractate_count"] < 10]
    single_tractate = [t for t in topics.values() if t["tractate_count"] == 1]

    print()
    print("=" * 60)
    print("TOPIC INDEX ANALYSIS")
    print("=" * 60)
    print(f"  Dafs processed:          {total_rows}")
    print(f"  Unique raw terms:        {len(topics)}")
    print(f"  Total tag occurrences:   {sum(daf_counts)}")
    print(f"  Avg terms per daf:       {sum(daf_counts)/total_rows:.1f}")
    print()
    print(f"  Shas-wide (10+ tractates): {len(shas_wide)}")
    print(f"  Multi-tractate (2–9):      {len(multi_tractate)}")
    print(f"  Single-tractate:           {len(single_tractate)}")
    print()

    print("TOP 30 BY TRACTATE BREADTH:")
    print(f"  {'TERM':<55} {'DAFS':>5}  {'TRACTATES':>10}")
    print(f"  {'-'*55} {'-----':>5}  {'----------':>10}")
    for entry in list(topics.values())[:30]:
        term = entry["term"][:54]
        print(f"  {term:<55} {entry['daf_count']:>5}  {entry['tractate_count']:>10}")
    print()

    print("SAMPLE SINGLE-TRACTATE TERMS (first 10):")
    shown = 0
    for entry in topics.values():
        if entry["tractate_count"] == 1:
            print(f"  [{entry['tractates'][0]}]  {entry['term']}  ({entry['daf_count']} dafs)")
            shown += 1
            if shown >= 10:
                break
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract topical tags from shiur_content")
    parser.add_argument("--out-dir", default="./topic_analysis",
                        help="Directory to write output files (default: ./topic_analysis)")
    parser.add_argument("--local", action="store_true",
                        help="Read from ./output/ instead of Supabase")
    parser.add_argument("--output-dir", default="./output",
                        help="Local output dir (used with --local)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching segmentation data...")
    if args.local:
        rows = fetch_all_segmentations_local(Path(args.output_dir))
    else:
        rows = fetch_all_segmentations(get_key())

    if not rows:
        sys.exit("No rows returned.")

    print("Extracting topics...")
    topics = extract_topics(rows)

    write_json(topics, out_dir / "topics_raw.json")
    write_tsv(topics, out_dir / "topics_report.tsv")
    print_stats(topics, len(rows))


if __name__ == "__main__":
    main()
