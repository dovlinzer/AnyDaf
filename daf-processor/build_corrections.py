#!/usr/bin/env python3
"""Turn the reviewed Ein Mishpat verdicts into corrections to Sefaria's links. No Anthropic API.

Sources, in order of authority:
  author_overrides.json   the author's corrections from the review page (win on their line)
  rejudged.json           the model's verdicts (rejudge_xrefs.py), for references still in question
                          after em_notes' book-aware matching ("B" = change; "A"/"both" = keep)

A correction is a set change on one line: refs to remove and refs to add. A reference the note also
lists is never removed for another one ("both 2:1 and 3:1"), and ranges are added halakha by halakha.

    venv/bin/python build_corrections.py   # -> outline/xref_check/corrections.json, to_review.json
"""
from __future__ import annotations

import collections
import json

from check_xrefs import RESULT
import rejudge_xrefs

OVERRIDES = RESULT / "author_overrides.json"
CORRECTIONS = RESULT / "corrections.json"
TO_REVIEW = RESULT / "to_review.json"
# cards where the review page showed a note from another line (fixed since): the author's call there
# was made on the wrong note, so it is asked again rather than applied
ASK_AGAIN = {"Bava Batra 150a:5", "Bava Batra 150a:6", "Berakhot 17b:15", "Makkot 10b:5", "Eiruvin 83a:4",
             "Gittin 44a:5"}


def where(x):
    return f"{x['tractate']} {x['amud']}:{x['line']}"


def main():
    judged = json.loads(rejudge_xrefs.OUT.read_text())
    live = rejudge_xrefs.items()   # what is still in question with today's notes
    overrides = {o["where"]: o for o in json.loads(OVERRIDES.read_text())["entries"]}
    out, review, kept = [], [], collections.Counter()
    for x in judged:
        k = (x["tractate"], x["amud"], x["line"], x["a"])
        w, v = where(x), x["judge"]["verdict"]
        if w in overrides:
            continue
        if w in ASK_AGAIN:
            review.append({"where": w, "sefaria": x["a"], "other": x["b"], "reason": "look again: the card showed a note from another line",
                           "verdict": v, "model": x["judge"]["reason"]})
            continue
        if k not in live:
            kept["now agrees with its note"] += 1
            continue
        if [n.get("line") for n in live[k]["notes"]] != [n.get("line") for n in x["notes"]] or live[k]["b"] != x["b"]:
            review.append({"where": w, "sefaria": x["a"], "reason": "the note behind this verdict changed; ask again"})
            continue
        if x["cid"].startswith("rd_"):   # judged after the note fixes: shown to the author before applying
            review.append({"where": w, "sefaria": x["a"], "other": x["b"], "reason": "new verdict, to confirm",
                           "verdict": v, "model": x["judge"]["reason"]})
        elif v == "B":
            out.append({"where": w, "remove": [x["a"]], "add": [x["b"]], "by": "model", "why": x["judge"]["reason"]})
        elif v in ("A", "both"):
            kept["model kept Sefaria's"] += 1
        else:
            review.append({"where": w, "sefaria": x["a"], "other": x["b"], "reason": f"model: {v}",
                           "verdict": v, "model": x["judge"]["reason"]})
    for w, o in overrides.items():
        if o["remove"] or o["add"]:
            out.append({"where": w, "remove": o["remove"], "add": o["add"], "by": "author", "why": o["why"]})
        else:
            kept["author kept Sefaria's"] += 1
    judged_keys = {(x["tractate"], x["amud"], x["line"], x["a"]) for x in judged}
    for k, it in live.items():
        if k not in judged_keys:
            review.append({"where": f"{k[0]} {k[1]}:{k[2]}", "sefaria": k[3], "other": it["b"],
                           "reason": "no Sefaria text for the other reading, so not judged"})
    wb = json.loads((RESULT / "wrong_book.json").read_text())
    for r in wb:
        w = f"{r['tractate']} {r['amud']}:{r['line']}"
        if w not in overrides:
            review.append({"where": w, "sefaria": r["sefaria"], "other": r["suggested"],
                           "reason": f"wrong book? note {r['letter']} ({r['kind']})", "note": r["note"]})
    CORRECTIONS.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    TO_REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1))
    print(f"corrections: {len(out)} ({sum(c['by'] == 'model' for c in out)} model, "
          f"{sum(c['by'] == 'author' for c in out)} author)")
    print("kept as Sefaria has them:", dict(kept))
    print(f"to review: {len(review)}", dict(collections.Counter(r['reason'].split(';')[0].split(' (')[0] for r in review)))


if __name__ == "__main__":
    main()
