#!/usr/bin/env python3
"""Review page for the word-gloss pilot (word_gloss_pilot.py): every word with both models' dictionary form and
gloss side by side; a click marks a model's answer wrong (saved in the page's db, collection gloss_marks).
No Anthropic API.

    venv/bin/python build_word_gloss_review.py OUTDIR      # writes OUTDIR/index.html
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from word_gloss_pilot import OUT, PILOT, amud_lines, clean

TAGS = re.compile(r"<[^>]+>")
plain = lambda w: re.sub(r"[\u0591-\u05C7\"'׳״]", "", w or "")


def main(outdir: str):
    meta = json.loads((OUT / "meta.json").read_text())
    res = {k: json.loads((OUT / f"{k}.json").read_text()) for k in ("sonnet", "haiku")}
    plan = json.loads((OUT / "entry_plan.json").read_text())
    ent = {k: json.loads((OUT / f"entries_{k}.json").read_text()) for k in ("sonnet", "haiku")}
    if (OUT / "entries_sonnet_med.json").exists():   # the medium-effort run in smaller requests replaces the first
        ent["sonnet"] = json.loads((OUT / "entries_sonnet_med.json").read_text())
    data = []
    for t, a in PILOT:
        cid = f"{t.replace(' ', '_')}_{a}"
        lines = []
        for s in amud_lines(t, a):
            n = str(s["n"])
            words = meta[cid]["words"].get(n, [])
            rows = []
            for i, w in enumerate(words):
                row = [w]
                for k in ("sonnet", "haiku"):
                    got = (res[k].get(cid) or {}).get(n) or []
                    g = got[i] if len(got) == len(words) else \
                        next((x for x in got if plain(x.get("w")) == plain(w)), None)
                    row.append([g.get("lemma", ""), g.get("g", "")] if g else None)
                iid = plan[cid]["where"].get(f"{n}:{i}")
                defs = {hw: d for hw, d in next((c for j, _, _, c in plan[cid]["items"] if j == iid), [])}
                for k in ("sonnet", "haiku"):
                    hw = (ent[k].get(cid) or {}).get(iid)
                    row.append([hw, defs.get(hw, "")] if hw else None)
                rows.append(row)
            lines.append({"n": s["n"], "he": clean(s.get("he")), "en": clean(s.get("en")), "w": rows})
        data.append({"id": cid, "name": f"{t} {a}", "lines": lines})
    html = (Path(__file__).parent / "word_gloss_review_template.html").read_text()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    print(out / "index.html", sum(len(l["w"]) for d in data for l in d["lines"]), "words")


if __name__ == "__main__":
    main(sys.argv[1])
