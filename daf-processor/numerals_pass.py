#!/usr/bin/env python3
"""Write the numbers that are data in a case as numerals, in existing English outlines (the prompt now
asks for this; outlines made before it spell them out). No API.

Converted: any number above ten ("fifty", "a hundred", "two thousand"); and one to ten when it is an
amount: before a unit of money, measure or time ("five sela'im", "thirty days"), after a verb of
claiming, admitting, denying, owing or paying ("admits three"), or in "N of M" ("three of five").
Small counts of people or things ("two witnesses", "three women") stay words.

Headings, summaries, bullets, chart titles and cells, picture titles, captions and labels, and each key
term's "on this daf" line. Originals are kept as *.before_numerals.json.

    venv/bin/python numerals_pass.py [--dry-run] [--show]
"""
import argparse
import glob
import json
import re
import shutil
from pathlib import Path

RESULTS = Path(__file__).parent / "outline" / "results"
UNITS_ = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SMALL = r"(?:two|three|four|five|six|seven|eight|nine|ten)"
BIG = (r"(?:(?:a|one|two|three|four|five|six|seven|eight|nine)\s+(?:hundred|thousand)"
       r"|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?"
       r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|hundred|thousand)")
UNIT = (r"(?:zuz|dinars?|dinarim|sela'?im|sela'?s?|ma'?neh|manim|perutah|perutot|coins|shekels?|"
        r"cubits?|amot|tefachim|handbreadths?|fingerbreadths?|days?|years?|months?|hours?|log|se'ah|kor)")
VERB = (r"(?:claims?|claimed|admits?|admitted|admitting|denies|denied|denying|owes|owed|lent|pays?|paid|"
        r"hands? over|handed over|returns?|returned|collects?|collected)")


def value(w):
    w = w.lower().replace("-", " ")
    parts = w.split()
    if parts[-1] in ("hundred", "thousand"):
        mult = 100 if parts[-1] == "hundred" else 1000
        head = 1 if len(parts) == 1 or parts[0] in ("a", "one") else UNITS_[parts[0]]
        return head * mult
    n = 0
    for p in parts:
        n += TENS.get(p) or UNITS_.get(p, 0)
    return n


def fmt(n):
    return f"{n:,}"


RX = [
    # above ten, anywhere
    re.compile(rf"(?<![\w'-])({BIG})(?![\w'-])", re.I),
    # small amount before a unit (allowing an italic star: "five *sela'im*")
    re.compile(rf"(?<![\w'-])({SMALL})(?=\s+\*?{UNIT}\b)(?!\s+days\s+of\s+Creation)", re.I),
    # after a claiming verb
    re.compile(rf"\b{VERB}\s+(?:only\s+|the\s+other\s+|all\s+)?({SMALL})\b", re.I),
]
OF = re.compile(rf"(?<![\w'-])({SMALL}|\d[\d,]*)(\s+of\s+(?:the\s+)?)({SMALL}|\d[\d,]*)(?![\w'-])", re.I)


def convert(s, hits):
    if not s or not isinstance(s, str):
        return s
    for rx in RX:
        def sub(m):
            word = m.group(1)
            n = value(word)
            if not n:
                return m.group(0)
            hits.append(word)
            g0, st = m.group(0), m.start(1) - m.start(0)
            return g0[:st] + fmt(n) + g0[st + len(word):]
        s = rx.sub(sub, s)

    # "three of five", "3 of five": both numerals (not "one of the two", a count of people)
    def of(m):
        a, mid, b = m.groups()
        if a.lower() == "one" or (not a[0].isdigit() and not b[0].isdigit() and b.lower() in ("two",)):
            return m.group(0)
        out = []
        for w in (a, b):
            if w[0].isdigit():
                out.append(w)
            else:
                hits.append(w)
                out.append(fmt(value(w)))
        return out[0] + mid + out[1]
    return OF.sub(of, s)


def svg_convert(svg, hits):
    return re.sub(r">([^<]+)<", lambda m: ">" + convert(m.group(1), hits) + "<", svg)


def fix(o):
    hits = []

    def walk(ns):
        for n in ns or []:
            for k in ("title", "gist"):
                n[k] = convert(n.get(k), hits)
            for b in n.get("bullets") or []:
                if isinstance(b, dict):
                    b["text"] = convert(b.get("text"), hits)
            c = n.get("chart")
            if isinstance(c, dict):
                for k in ("title", "caption"):
                    c[k] = convert(c.get(k), hits)
                c["columns"] = [convert(x, hits) for x in c.get("columns") or []]
                c["rows"] = [[convert(x, hits) for x in r] for r in c.get("rows") or []]
            il = n.get("illustration")
            if isinstance(il, dict):
                for k in ("title", "caption"):
                    il[k] = convert(il.get(k), hits)
                if il.get("svg"):
                    il["svg"] = svg_convert(il["svg"], hits)
            walk(n.get("children"))

    walk(o.get("sections"))
    for t in o.get("key_terms") or []:
        t["on_this_daf"] = convert(t.get("on_this_daf"), hits)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    total = 0
    for f in sorted(glob.glob(str(RESULTS / "*/04_outline_opus55*.json"))):
        if ".before" in f or "pre_anchors" in f or "round1" in f:
            continue
        p = Path(f)
        b = p.with_name(p.stem + ".before_numerals.json")
        o = json.loads((b if b.exists() else p).read_text(encoding="utf-8"))
        hits = fix(o)
        if not hits:
            continue
        total += len(hits)
        print(f"{p.parent.name:18s} {p.stem[11:]:18s} {len(hits):3d}" + (f"  {sorted(set(h.lower() for h in hits))}" if args.show else ""))
        if args.dry_run:
            continue
        if not b.exists():
            shutil.copy2(p, b)
        p.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{total} numbers written as numerals")


if __name__ == "__main__":
    main()
