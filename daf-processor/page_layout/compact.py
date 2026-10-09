"""The site's version of an amud's layout: what the web page (and later the apps) draws over the
scan, in fractions of the page so any image size fits. About 13 KB an amud, against ~110 KB for
the full result in out/.

    {"g": {Gemara label: [[x, y, w, h], ...]},   one box per printed line
     "c": [{who, on, boxes, dh, text}],           Rashi / Tosafot comments: the Gemara label each
                                                  glosses, its boxes, opening words, full text
     "rough": bool}                               the aligner flagged this amud's Gemara

Used by AnyDafWeb/prototype/build_prototype.py (dafim with an outline carry it in their data file)
and by upload_r2.py (every amud, to Cloudflare R2 for any daf)."""
from __future__ import annotations

import json
import re

from . import fetch
OUT = fetch.HERE / "out"     # page_layout.run's results (not imported from run, which needs numpy)

COMMENTATORS = (("rashi", "Rashi"), ("tosafot", "Tosafot"))


def site_layout(tractate: str, amud: str) -> dict | None:
    """tractate as named in out/ (the scans' spelling); None when page_layout hasn't run for it."""
    p = OUT / tractate / f"{amud}.json"
    if not p.exists():
        return None
    j = json.loads(p.read_text(encoding="utf-8"))
    W, H = j["image"]["w"], j["image"]["h"]
    fr = lambda b: [round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)]
    g = {ref: [fr(b) for b in boxes] for ref, boxes in j["segments"].items() if re.fullmatch(r"\d+[ab]\.\d+", ref)}
    # Full comment texts from Sefaria's Vilna edition (page_layout's own cache), for this amud and
    # the previous one, since a comment can run over from it; split at the dibbur ha'matchil.
    n, side = int(amud[:-1]), amud[-1]
    pd, pa = fetch.previous_amud(n, side)
    texts = {}
    for _, who in COMMENTATORS:
        for d_, a_ in ((pd, pa), (n, side)):
            try:
                texts.update(fetch.commentary(who, tractate, d_, a_))
            except Exception:                 # not cached and offline: fall back to placed words
                pass
    c, seen = [], set()
    for stream, who in COMMENTATORS:
        for line in j.get(stream) or []:
            for w in line["words"]:
                for ref, _ in w.get("toks") or []:
                    m = re.search(r"(\d+[ab]):(\d+):\d+$", ref)
                    if not m or ref in seen or not j["segments"].get(ref):
                        continue
                    seen.add(ref)
                    full = texts.get(ref, "")
                    sep = next((x for x in (" - ", ". ") if x in full[:120]), None)
                    dh, rest = (full.split(sep, 1) if sep else ("", full))
                    c.append({"who": ref.split(" on ")[0], "on": f"{m.group(1)}.{m.group(2)}",
                              "boxes": [fr(b_) for b_ in j["segments"][ref]], "dh": dh.strip(), "text": rest.strip()})
    rough = any(f.startswith("gemara") for f in j["qc"].get("flags", []))
    return {"g": g, "c": c, "rough": rough}
