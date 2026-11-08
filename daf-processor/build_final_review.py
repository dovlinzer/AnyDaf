#!/usr/bin/env python3
"""Review page for the Ein Mishpat references still open (build_corrections.py's to_review.json). Each card
shows the notes whose letters sit on that line, with the marked words. No Anthropic API.

    venv/bin/python build_final_review.py OUTDIR      # writes OUTDIR/index.html
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from build_corrections import TO_REVIEW
from em_notes import OUT as NOTES
from judge_xrefs import amud_segs, clean, passage
from rejudge_xrefs import other_refs

HERE = Path(__file__).parent
TEMPLATE = HERE / "final_review_template.html"
GROUPS = [("New verdicts", "new verdict"), ("Wrong book?", "wrong book"), ("Look again", "look again"),
          ("Model unsure", "model:"), ("No text for B", "no Sefaria text")]


def group(reason):
    return next(g for g, p in GROUPS if reason.startswith(p))


_notes = {}


def line_notes(tractate, amud, line):
    if tractate not in _notes:
        p = NOTES / f"{tractate}.json"
        _notes[tractate] = json.loads(p.read_text())["amudim"] if p.exists() else {}
    v = _notes[tractate].get(amud) or {"notes": [], "markers": {}}
    out = []
    for nt in v["notes"]:
        for letter in nt["letters"]:
            mk = v["markers"].get(letter, {})
            if mk.get("line") == line:
                out.append({"letter": letter, "word": mk.get("word"), "text": nt["text"], "line": line})
    return out


def item(i, r):
    tractate, rest = r["where"].rsplit(" ", 1)
    amud, line = rest.split(":")
    line = int(line)
    segs = amud_segs(tractate, amud)
    notes = line_notes(tractate, amud, line)
    near = " ".join(clean(segs[line - 1].get("he")) for _ in [0]) if 0 < line <= len(segs) else ""
    other = r.get("other")
    if other and not re.search(r"\d+(:\d+)?$", other):
        other = None
    return {"id": f"fr_{i}", "group": group(r["reason"]), "where": r["where"], "layer": "em",
            "work": "sa" if r["sefaria"].startswith("Shulchan") else "rambam",
            "verdict": r.get("verdict"), "reason": r.get("model", ""), "why": r["reason"],
            "lines": [{"n": f"{amud}:{n}", "he": clean(segs[n - 1].get("he")), "en": segs[n - 1].get("en", "")}
                      for n in range(max(1, line), min(len(segs), line) + 1)],
            "notes": notes,
            "others": [x for x in other_refs(tractate, amud, line) if x not in (r["sefaria"], other)],
            "a": {"ref": r["sefaria"], "text": passage(r["sefaria"], near) or "(not in Sefaria's text)"},
            "b": {"ref": other or "(none)", "text": (passage(other, near) if other else "") or "(no text on Sefaria)",
                  "how": "the other reading"}}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(TO_REVIEW.read_text())
    order = [g for g, _ in GROUPS]
    data = sorted((item(i, r) for i, r in enumerate(rows)), key=lambda d: order.index(d["group"]))
    (out / "index.html").write_text(TEMPLATE.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    for g in order:
        print(g, sum(d["group"] == g for d in data))


if __name__ == "__main__":
    main()
