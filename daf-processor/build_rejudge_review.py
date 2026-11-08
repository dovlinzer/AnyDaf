#!/usr/bin/env python3
"""Review page for rejudge_xrefs.py: a sample of each verdict, each card showing the Gemara (the marked
word highlighted), the Ein Mishpat note, and Sefaria's number beside the other reading. No Anthropic API.

    venv/bin/python build_rejudge_review.py OUTDIR      # writes OUTDIR/index.html
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from judge_xrefs import amud_segs, clean, passage
from rejudge_xrefs import OUT as REJUDGED, other_refs

HERE = Path(__file__).parent
TEMPLATE = HERE / "rejudge_review_template.html"
HOW = {"disagree": "Wikisource's note", "rechecked": "first check's suggestion", "uncovered": "first check's suggestion"}
GROUPS = [
    ("Change to B", lambda x: x["judge"]["verdict"] == "B", 50),
    ("Keep Sefaria's", lambda x: x["judge"]["verdict"] in ("A", "both"), 30),
    ("Neither or unsure", lambda x: x["judge"]["verdict"] not in ("A", "B", "both"), 20),
]


def item(x, group):
    lines = sorted({x["line"]} | {n["line"] for n in x["notes"] if n.get("line")})
    segs = amud_segs(x["tractate"], x["amud"])
    near = " ".join(n.get("phrase") or "" for n in x["notes"])
    return {"id": x["cid"], "group": group, "where": f"{x['tractate']} {x['amud']}:{x['line']}", "layer": "em",
            "work": x["work"], "verdict": x["judge"]["verdict"], "reason": x["judge"].get("reason", ""),
            "lines": [{"n": f"{x['amud']}:{n}", "he": clean(segs[n - 1].get("he")), "en": segs[n - 1].get("en", "")}
                      for n in range(lines[0], min(len(segs), lines[-1]) + 1)],
            "notes": [{k: n.get(k) for k in ("letter", "word", "text", "line")} for n in x["notes"]],
            "others": [r for r in other_refs(x["tractate"], x["amud"], x["line"]) if r not in (x["a"], x["b"])],
            "a": {"ref": x["a"], "text": passage(x["a"], near) or "(not in Sefaria's text)"},
            "b": {"ref": x["b"], "text": passage(x["b"], near) or "", "how": HOW[x["source"][0]]}}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rows_all = json.loads(REJUDGED.read_text())
    rnd = random.Random(11)
    data = []
    for name, test, n in GROUPS:
        rows = [x for x in rows_all if test(x)]
        pick = rnd.sample(rows, min(n, len(rows)))
        data += [item(x, name) for x in pick]
        print(f"{name}: {len(pick)} of {len(rows)}")
    (out / "index.html").write_text(TEMPLATE.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    print(f"{len(data)} items, {(out / 'index.html').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
