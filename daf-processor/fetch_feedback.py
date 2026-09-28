"""Download readers' outline notes from Supabase (outline_feedback) for review and fix-ups.

    python fetch_feedback.py                 # summary of every note
    python fetch_feedback.py --write         # also one file per note under outline/feedback/rows/
    python fixup_pass.py --from-flags outline/feedback/rows --tag opus55_medium   # notes -> fix-up files

Reads with the service key (SUPABASE_SERVICE_KEY in .env), which the site never sees: the site's
anon key can only add notes (outline-feedback-migration.sql). No API cost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
ROWS = HERE / "outline" / "feedback" / "rows"
# the site's version marks -> result tags
TAGS = {"M": "opus55_medium", "H": "opus55_high", None: "opus55"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write one JSON file per note for fixup_pass.py")
    ap.add_argument("--all", action="store_true", help="include notes already marked applied or declined")
    a = ap.parse_args()
    key = os.environ.get("SUPABASE_SERVICE_KEY") or sys.exit("SUPABASE_SERVICE_KEY not set in daf-processor/.env")
    params = {"select": "*", "order": "created_at"}
    if not a.all:
        params["status"] = "eq.open"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/outline_feedback", params=params, timeout=60,
                     headers={"apikey": key, "Authorization": f"Bearer {key}"})
    r.raise_for_status()
    rows = r.json()
    print(f"{len(rows)} notes" + ("" if a.all else " (open)"))
    by = Counter((x["daf"], x.get("version")) for x in rows)
    for (daf, v), n in sorted(by.items()):
        print(f"  {daf}{' (' + v + ')' if v else ''}: {n}")
    for x in rows:
        who = x.get("reader_name") or "anonymous"
        print(f"\n[{x['id']}] {x['daf']} {x.get('version') or ''} · {x.get('section_title') or 'whole daf'} · "
              f"{x['kind']} · {who} · {x['created_at'][:16]}\n  {x['note']}")
    if a.write:
        ROWS.mkdir(parents=True, exist_ok=True)
        for x in rows:
            doc = {"daf": x["daf"], "tag": TAGS.get(x.get("version"), "opus55"), "section": x.get("section_id"),
                   "title": x.get("section_title"), "kind": x["kind"], "note": x["note"], "status": x["status"],
                   "reader": x.get("reader_name"), "at": x["created_at"]}
            (ROWS / f"{x['id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {len(rows)} files to {ROWS.relative_to(HERE)}")


if __name__ == "__main__":
    main()
