#!/usr/bin/env python3
"""Review page: our cross-references beside the Vilna scan, for checking against the printed margin.
No Anthropic API calls. Reads xrefs/ (build_xrefs.py), daf_text/, the page scans, and Sefaria's links
API for the Hebrew names of the references.

    venv/bin/python build_xref_review.py OUTDIR      # writes OUTDIR/index.html and OUTDIR/img/
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import requests

from build_xrefs import BOOKS_HE, LETTERS
from page_layout import fetch as layout

HERE = Path(__file__).parent
TEMPLATE = HERE / "xref_review_template.html"
IMG_WIDTH = 2000

# (tractate, daf, amud, why this amud)
SAMPLE = [
    ("Bava Metzia", 2, "a", "Baseline: the counts match Wikisource"),
    ("Kiddushin", 40, "b", "Halakhic and aggadic mixed"),
    ("Menachot", 29, "b", "Many Ein Mishpat links; Wikisource marks none"),
    ("Bekhorot", 13, "a", "Many Ein Mishpat links; Wikisource marks none"),
    ("Sukkah", 39, "a", "Sukkah's links carry a different label"),
    ("Yoma", 85, "b", "Rambam but no Shulchan Arukh; Wikisource has more letters"),
    ("Yoma", 73, "a", "Rambam but no Shulchan Arukh"),
    ("Sanhedrin", 37, "a", "Rambam but no Shulchan Arukh"),
    ("Sanhedrin", 66, "b", "Rambam but no Shulchan Arukh"),
    ("Nazir", 51, "a", "Rambam but no Shulchan Arukh"),
    ("Sanhedrin", 98, "b", "No Ein Mishpat at all: is that right?"),
    ("Pesachim", 87, "b", "No Ein Mishpat at all: is that right?"),
    ("Megillah", 6, "a", "No Ein Mishpat at all: is that right?"),
    ("Zevachim", 3, "b", "No Ein Mishpat at all: is that right?"),
    ("Hullin", 32, "b", "No Ein Mishpat, and only one reference of any kind"),
]
WORK_ORDER = {"rambam": 0, "smag": 1, "tur": 2, "sa": 3, "other": 4}
NIKUD = re.compile(r"[֑-ׇ]")
EN_TO_HE = {v: k for k, v in BOOKS_HE.items()}
NUMS = sorted(((v, k) for k, v in LETTERS.items()), reverse=True)


def he_num(n: int) -> str:
    if n in (15, 16):
        return {15: "טו", 16: "טז"}[n]
    out = ""
    for v, c in NUMS:
        while n >= v:
            out += c
            n -= v
    return out


def he_verse(ref: str) -> str:
    m = re.match(r"(.+) (\d+):(\d+)$", ref)
    return f"{EN_TO_HE[m.group(1)]} {he_num(int(m.group(2)))}, {he_num(int(m.group(3)))}"


def he_refs(tractate: str, amud: str) -> dict:
    r = requests.get(f"https://www.sefaria.org/api/links/{tractate.replace(' ', '_')}.{amud}",
                     params={"with_text": 0}, headers={"User-Agent": "AnyDaf cross-references"}, timeout=60)
    r.raise_for_status()
    return {x["ref"]: x.get("sourceHeRef") for x in r.json()}


def first_words(he: str, n: int = 7) -> str:
    words = NIKUD.sub("", re.sub(r"<[^>]+>", "", he or "")).split()
    return " ".join(words[:n]) + (" …" if len(words) > n else "")


def amud_data(tractate, daf, amud, why, out: Path):
    label = f"{daf}{amud}"
    key = f"{tractate.replace(' ', '_')}_{label}"
    segs = json.loads((HERE / "daf_text" / f"{tractate}.json").read_text())["amudim"][label]["segments"]
    lines = json.loads((HERE / "xrefs" / f"{tractate}.json").read_text())["amudim"].get(label, {})
    names = he_refs(tractate, label)
    rows = []
    for n in sorted(lines, key=int):
        items = []
        for it in lines[n]:
            items.append({"k": it["k"], "work": it.get("work"), "cat": it.get("cat"), "ref": it["ref"],
                          "to": it.get("to"), "he": he_verse(it["ref"]) if it["k"] == "verse" else names.get(it["ref"])})
        rank = {"verse": 0, "em": 1, "ms": 2}
        items.sort(key=lambda i: (rank[i["k"]], WORK_ORDER.get(i["work"], 9)))
        text = first_words(segs[int(n) - 1].get("he")) if n != "0" else "כל העמוד"
        rows.append({"n": int(n), "text": text, "items": items})

    src = layout.page_image(tractate, daf, amud)
    subprocess.run(["sips", "--resampleWidth", str(IMG_WIDTH), "-s", "formatOptions", "62",
                    str(src), "--out", str(out / "img" / f"{key}.jpg")], check=True, capture_output=True)
    return {"key": key, "title": f"{tractate} {label}", "why": why, "rows": rows}


def main():
    out = Path(sys.argv[1])
    (out / "img").mkdir(parents=True, exist_ok=True)
    data = []
    for s in SAMPLE:
        print(s[0], s[1], s[2], flush=True)
        data.append(amud_data(*s, out))
    html = TEMPLATE.read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False))
    (out / "index.html").write_text(html)
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{out}: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
