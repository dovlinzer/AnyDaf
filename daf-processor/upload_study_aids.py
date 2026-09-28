#!/usr/bin/env python3
"""Upload per-daf study aids (outline + key terms) to Supabase `daf_study_aids`. No API calls.

Create the table first: ../study-aids-migration.sql in the Supabase SQL editor.

    venv/bin/python upload_study_aids.py --dafim bava_metzia_11 gittin_18 ... [--model opus55] [--dry-run]
    venv/bin/python upload_study_aids.py --example        # the Chagigah 6 worked example

Illustration SVG is sanitized here (clean_svg + uniquify_ids), so every reader gets safe markup.
The editorial fields (judgment_calls, coverage_notes, runners_up) stay in the local files and are never
uploaded: they are notes for review, not for learners.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from build_outline_review import clean_svg, uniquify_ids
from upload_to_supabase import parse_dir_name

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
RESULTS = HERE / "outline" / "results"
EXAMPLE = HERE / "outline" / "example_chagigah_6.json"
EXAMPLE_TERMS = HERE / "outline" / "key_terms_example_chagigah_6.json"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
TABLE = "daf_study_aids"
MODEL_IDS = {"sonnet5": "claude-sonnet-5", "opus5": "claude-opus-5", "opus55": "claude-opus-5-5"}
PROMPT_VERSION = "2026-09-24-test"
EDITORIAL = ("judgment_calls", "coverage_notes", "runners_up")


def sanitize(nodes):
    for n in nodes or []:
        if isinstance(n.get("illustration"), dict) and "svg" in n["illustration"]:
            n["illustration"]["svg"] = uniquify_ids(clean_svg(n["illustration"]["svg"]))
        sanitize(n.get("children"))


def row(key: str, outline: dict, terms: list | None, model: str) -> dict:
    tractate, daf = parse_dir_name(key)
    if tractate is None:
        sys.exit(f"can't read tractate/daf from {key}")
    # Outlines from the revised pass carry their key terms inline; older ones have a separate file.
    terms = outline.get("key_terms") or terms
    outline = {k: v for k, v in outline.items() if k not in EDITORIAL and k != "key_terms"}
    sanitize(outline.get("sections"))
    return {"tractate": tractate, "daf": daf, "outline": outline, "key_terms": terms,
            "model": model, "prompt_version": PROMPT_VERSION, "status": "draft"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="*", default=[])
    ap.add_argument("--model", default="opus55", choices=list(MODEL_IDS))
    ap.add_argument("--example", action="store_true", help="also upload the Chagigah 6 worked example")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = []
    if args.example:
        terms = json.loads(EXAMPLE_TERMS.read_text(encoding="utf-8"))["key_terms"]
        rows.append(row("chagigah_6", json.loads(EXAMPLE.read_text(encoding="utf-8")), terms, "author example"))
    for key in args.dafim:
        if key.endswith("_textonly"):
            sys.exit(f"{key}: text-only test variants aren't uploaded")
        op = RESULTS / key / f"04_outline_{args.model}.json"
        if not op.exists():
            sys.exit(f"missing {op.relative_to(HERE)}")
        tp = RESULTS / key / f"05_key_terms_{args.model}.json"
        terms = json.loads(tp.read_text(encoding="utf-8")).get("key_terms") if tp.exists() else None
        rows.append(row(key, json.loads(op.read_text(encoding="utf-8")), terms, MODEL_IDS[args.model]))

    for r in rows:
        print(f"  {r['tractate']} {r['daf']:g}: {len(r['outline'].get('sections', []))} sections, "
              f"{len(r['key_terms'] or [])} terms, {len(json.dumps(r, ensure_ascii=False)) // 1024} KB")
    if args.dry_run or not rows:
        return
    key = os.environ.get("SUPABASE_SERVICE_KEY") or sys.exit("SUPABASE_SERVICE_KEY not set in .env")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates"}
    for attempt in range(6):
        try:
            r = requests.post(f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=tractate,daf", headers=h,
                              json=rows, timeout=120)
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 5:
                raise
            time.sleep(2 * 2 ** attempt)
    if r.status_code not in (200, 201):
        sys.exit(f"upload failed: HTTP {r.status_code} {r.text[:300]}")
    print(f"uploaded {len(rows)} rows -> {TABLE}")


if __name__ == "__main__":
    main()
