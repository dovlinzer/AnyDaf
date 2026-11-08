#!/usr/bin/env python3
"""Review page for the model's verdicts on the cross-references (judge_xrefs.py): a sample, so the
author can measure how often the judge is right before its proposed corrections are accepted.
No Anthropic API calls.

    venv/bin/python build_judge_review.py OUTDIR      # writes OUTDIR/index.html
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from judge_xrefs import JUDGED, clean, gemara, passage

HERE = Path(__file__).parent
TEMPLATE = HERE / "judge_review_template.html"
# (group shown to the reviewer, rows it covers, how many to sample)
GROUPS = [
    ("Proposed corrections", lambda x: x["kind"] == "flag" and x["judge"]["verdict"] == "B", 45),
    ("Kept as cited", lambda x: x["kind"] == "flag" and x["judge"]["verdict"] in ("A", "both"), 20),
    ("Neither or unsure", lambda x: x["kind"] == "flag" and x["judge"]["verdict"] in ("neither", "unsure"), 99),
    ("Weak match: judged wrong", lambda x: x["kind"] == "weak" and x["judge"]["verdict"] == "no", 99),
    ("Weak match: judged right", lambda x: x["kind"] == "weak" and x["judge"]["verdict"] == "yes", 10),
]


# The author doesn't use the Semag or the Tur; their references are judged but not reviewed.
SKIP_WORKS = {"smag", "tur"}


def item(x, group):
    g = gemara(x["tractate"], x["amud"], x["line"], x.get("to"))
    segs = [s for s in g.split("\n[") if s]
    lines = []
    for s in segs:
        head, *rest = s.lstrip("[").split("\n")
        parts = {r.split(": ", 1)[0]: r.split(": ", 1)[1] for r in rest if ": " in r}
        lines.append({"n": head.rstrip("]"), "he": parts.get("Gemara", ""), "en": parts.get("English", "")})
    out = {"id": x["cid"] if "cid" in x else f"{x['kind']}|{x['tractate']}|{x['amud']}|{x['line']}|{x['ref']}",
           "group": group, "where": f"{x['tractate']} {x['amud']}:{x['line']}", "layer": x["layer"],
           "work": x.get("work"), "lines": lines, "verdict": x["judge"]["verdict"],
           "reason": x["judge"].get("reason", ""),
           "a": {"ref": x["ref"], "text": passage(x["ref"], g) or "(not in Sefaria's text)"}}
    if x["kind"] == "flag":
        out["b"] = {"ref": x["alt"], "text": passage(x["alt"], g) or "", "how": x.get("how", "")}
    return out


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    judged = json.loads(JUDGED.read_text())
    rnd = random.Random(7)
    data = []
    for name, test, n in GROUPS:
        rows = [x for x in judged if test(x) and x.get("work") not in SKIP_WORKS]
        pick = rnd.sample(rows, min(n, len(rows)))
        data += [item(x, name) for x in pick]
        print(f"{name}: {len(pick)} of {len(rows)}")
    (out / "index.html").write_text(TEMPLATE.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    print(f"{len(data)} items, {(out / 'index.html').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
