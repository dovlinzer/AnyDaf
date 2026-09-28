"""Collect and unblind the A/B outline test's votes (Supabase outline_ab_votes).

    python fetch_ab_votes.py                    # tally for round3, unblinded with outline/ab_key_round3.json
    python fetch_ab_votes.py --round round3 --notes

The latest vote per (tester, daf) counts. A/B are mapped back to the result tags with the key file
the A/B page was built with; the key never leaves this machine. Reads with the service key. No API cost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
NAMES = {"opus55_medium": "Medium", "opus55_high": "High"}
ASPECTS = ("overall", "structure", "charts", "pictures")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="round3")
    ap.add_argument("--notes", action="store_true", help="print every note, unblinded")
    a = ap.parse_args()
    key = json.loads((HERE / "outline" / f"ab_key_{a.round}.json").read_text())
    sk = os.environ.get("SUPABASE_SERVICE_KEY") or sys.exit("SUPABASE_SERVICE_KEY not set in daf-processor/.env")
    r = requests.get(f"{SUPABASE_URL}/rest/v1/outline_ab_votes", timeout=60,
                     params={"select": "*", "round": f"eq.{a.round}", "order": "created_at"},
                     headers={"apikey": sk, "Authorization": f"Bearer {sk}"})
    r.raise_for_status()
    latest = {}
    for v in r.json():                                   # later rows replace earlier ones
        latest[(v["tester_id"], v["daf"])] = v
    testers = {t for t, _ in latest}
    print(f"{len(latest)} verdicts from {len(testers)} tester(s) on {len({d for _, d in latest})} dafim\n")

    def unblind(v, aspect):
        c = v.get(aspect)
        return None if not c else "same" if c == "same" else NAMES.get(key[v["daf"]][c], key[v["daf"]][c])
    for aspect in ASPECTS:
        tally = Counter(x for v in latest.values() if (x := unblind(v, aspect)))
        print(f"{aspect:9s} " + "  ".join(f"{k}: {n}" for k, n in tally.most_common()))
    by_daf = defaultdict(Counter)
    for v in latest.values():
        if (x := unblind(v, "overall")):
            by_daf[v["daf"]][x] += 1
    print("\nper daf (overall):")
    for d in key:
        if by_daf[d]:
            print(f"  {d:16s} " + "  ".join(f"{k} {n}" for k, n in by_daf[d].most_common()))
    if a.notes:
        print("\nnotes:")
        for v in latest.values():
            if v.get("note"):
                prefer = unblind(v, "overall") or "-"
                print(f"  {v['daf']} ({v.get('tester_name') or v['tester_id'][:8]}, prefers {prefer}): {v['note']}")


if __name__ == "__main__":
    main()
