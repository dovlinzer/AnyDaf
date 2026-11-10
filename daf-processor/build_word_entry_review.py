#!/usr/bin/env python3
"""Review page for the second word-glossary pilot (word_gloss_run.py): the words where the Sonnet-gloss pipeline and
the Haiku-gloss pipeline end at different Jastrow entries. The reviewer picks which is right (saved in the page's db,
collection entry_votes). No Anthropic API.

    venv/bin/python build_word_entry_review.py OUTDIR      # writes OUTDIR/index.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from word_gloss_pilot import amud_lines, clean
from build_word_gloss_review import toks
from word_gloss_run import AMUDIM, RUN, cid_of, plain


def gloss_cat(a, b):
    """'same' (identical), 'close' (share a content word) or 'diff' (different in meaning)."""
    x, y = a.lower().strip(), b.lower().strip()
    return "same" if x == y else "close" if toks(x) & toks(y) else "diff"


def main(outdir: str):
    plan = json.loads((RUN / "entry_plan.json").read_text())
    chosen = json.loads((RUN / "entries.json").read_text())
    meta = json.loads((RUN / "meta.json").read_text())
    senses = {}
    for gk in plan:
        for v in plan[gk]["items"].values():
            for c in v["cands"]:
                senses.setdefault(c["hw"], c["senses"])
    cards = []
    for t, a in AMUDIM:
        cid = cid_of(t, a)
        lines = {str(s["n"]): s for s in amud_lines(t, a)}
        for n, ws in meta[cid]["words"].items():
            for i, w in enumerate(ws):
                pos = f"{cid}:{n}:{i}"
                ks, kh = plan["sonnet"]["where"].get(pos), plan["haiku"]["where"].get(pos)
                es, eh = chosen["sonnet"].get(ks), chosen["haiku"].get(kh)
                if not ks or not kh or es == eh:
                    continue
                vs, vh = plan["sonnet"]["items"][ks], plan["haiku"]["items"][kh]
                cards.append({"id": pos.replace(":", "_"), "amud": f"{t} {a}", "line": n, "i": i,
                              "cat": gloss_cat(vs["g"], vh["g"]),
                              "words": [plain(x) for x in ws], "en": clean(lines[n].get("en")),
                              "s": {"g": vs["g"], "lemma": plain(vs["lemma"]), "hw": es, "senses": senses.get(es, "")},
                              "h": {"g": vh["g"], "lemma": plain(vh["lemma"]), "hw": eh, "senses": senses.get(eh, "")}})
    html = (Path(__file__).parent / "word_entry_review_template.html").read_text()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html.replace("__DATA__", json.dumps(cards, ensure_ascii=False)))
    print(out / "index.html", len(cards), "words to review")


if __name__ == "__main__":
    main(sys.argv[1])
