#!/usr/bin/env python3
"""The site's copy of the Vilna margin cross-references: Sefaria's links (build_xrefs.py) with the accepted
corrections applied and every reference still in doubt held back. No Anthropic API.

Held back: Rambam / Shulchan Arukh references on the author's review list (to_review.json); any other reference
the model judged wrong or couldn't decide (judged.json: a flag with verdict B / neither / unsure, a weak match
judged "no"). Applied: corrections.json (remove / add per line). Ein Mishpat references carry their note's
letter and the Gemara words it marks where Wikisource has them (em_notes.py).

    venv/bin/python build_xrefs_site.py      # -> xrefs/site/<Tractate>.json, read by AnyDafWeb's build

Per tractate: {"amudim": {amud: {line: [[kind, ref, letter, word], ...]}}}; kind is "em" (Ein Mishpat),
"ms" (Mesoret HaShas) or "v" (a verse). Line "0" is a link to the whole amud.
"""
from __future__ import annotations

import collections
import json

from check_xrefs import RESULT
from em_notes import OUT as NOTES
from build_xrefs import OUT as XREFS

SITE = XREFS / "site"
DOUBT = {"B", "neither", "unsure", "unparsed", "error"}


def held_back():
    held = set()
    for x in json.loads((RESULT / "judged.json").read_text()):
        if x.get("work") in ("rambam", "sa"):
            continue   # these went through the recheck; corrections / to_review decide them
        v = x["judge"]["verdict"]
        if (x["kind"] == "flag" and v in DOUBT) or (x["kind"] == "weak" and v == "no"):
            held.add((x["tractate"], x["amud"], x["line"], x["ref"]))
    for r in json.loads((RESULT / "to_review.json").read_text()):
        t, rest = r["where"].rsplit(" ", 1)
        a, n = rest.split(":")
        held.add((t, a, int(n), r["sefaria"]))
    return held


def corrections():
    by = collections.defaultdict(lambda: {"remove": set(), "add": []})
    for c in json.loads((RESULT / "corrections.json").read_text()):
        t, rest = c["where"].rsplit(" ", 1)
        a, n = rest.split(":")
        k = by[(t, a, int(n))]
        k["remove"].update(c["remove"])
        k["add"] += [r for r in c["add"] if r not in k["add"]]
    return by


def main():
    SITE.mkdir(exist_ok=True)
    held, fixes, stats = held_back(), corrections(), collections.Counter()
    for f in sorted(XREFS.glob("*.json")):
        d = json.loads(f.read_text())
        t = d["tractate"]
        np = NOTES / f.name
        notes = json.loads(np.read_text())["amudim"] if np.exists() else {}
        out = {}
        for amud, lines in d["amudim"].items():
            for n, items in lines.items():
                line = int(n)
                fix = fixes.get((t, amud, line), {"remove": set(), "add": []})
                where = {r["ref"]: r for r in (notes.get(amud) or {}).get("lines", {}).get(n, [])}
                rows, seen = [], set()

                def em_row(ref):
                    note = next((x for x in (where.get(ref) or {}).get("notes", []) if x.get("line") == line), None)
                    return ["em", ref, note and note.get("letter"), note and note.get("word")]

                for it in items:
                    ref = it["ref"]
                    if ref in seen:
                        continue
                    if (t, amud, line, ref) in held:
                        stats["held back"] += 1
                        continue
                    if ref in fix["remove"]:
                        stats["corrected"] += 1
                        continue
                    seen.add(ref)
                    rows.append(em_row(ref) if it["k"] == "em" else ["v" if it["k"] == "verse" else "ms", ref, None, None])
                for ref in fix["add"]:
                    if ref not in seen:
                        seen.add(ref)
                        rows.append(em_row(ref))
                        stats["added"] += 1
                if rows:
                    out.setdefault(amud, {})[n] = [[x for x in r if x is not None] if r[2] is None else r for r in rows]
                    stats["shown"] += len(rows)
        (SITE / f.name).write_text(json.dumps({"tractate": t, "amudim": out}, ensure_ascii=False, separators=(",", ":")))
    size = sum(p.stat().st_size for p in SITE.glob("*.json"))
    print(dict(stats), f"{size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
