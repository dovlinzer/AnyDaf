#!/usr/bin/env python3
"""Italicize transliterated key terms in the headings and picture labels of existing English
outlines (the prompt now asks for this; outlines made before it don't have it). No API.

Terms come from the daf's own key_terms (term + aliases) plus those of the tractate's other
outlines, longest first. Headings and chart/picture titles get *term*; SVG labels get
<tspan font-style="italic">term</tspan>. Text already in italics is left alone.

    venv/bin/python italicize_terms.py [--dry-run] [--show]   # every English outline under outline/results
"""
import argparse
import glob
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).parent / "outline" / "results"
TAGS = ("opus55", "opus55_medium", "opus55_high", "opus55_medium_v2")
# words that occur as aliases but are ordinary English in a heading
SKIP = {"mishnah", "gemara", "torah", "kohen", "kohanim", "shabbat", "beraita", "baraita", "halakha"}
# older outlines kept some English renderings as aliases; a term with any of these words is English
ENGLISH = set("""alleyway lifting pulling penalized ratified using the and its one part upon light wick drawn
animal consecrated disqualified claim decree doubtful firstborn firstborns produce respect susceptible
uncertain gore in of a to""".split())


def tractate(key):
    return re.sub(r"_\d+b?$", "", key)


def files():
    for tag in TAGS:
        for f in sorted(glob.glob(str(RESULTS / f"*/04_outline_{tag}.json"))):
            yield Path(f)


def terms_of(o):
    out = set()
    for t in o.get("key_terms") or []:
        for s in [t.get("term")] + list(t.get("aliases") or []):
            s = (s or "").strip()
            if (len(s) >= 3 and not re.search(r"[֐-׿]", s) and s.lower() not in SKIP
                    and not ENGLISH & set(re.findall(r"[a-z]+", s.lower()))
                    and not re.search(r"(ing|ed|ly|tion)\b", s.lower())):
                out.add(s)
    return out


def pattern(terms):
    alts = sorted(terms, key=len, reverse=True)
    body = "|".join(re.escape(t).replace(r"\'", "['’]").replace(r"\-", "[-' ]?") for t in alts)
    return re.compile(rf"(?<![\w'’*])({body})(?![\w'’])", re.I)


def italicize_md(s, rx, hits):
    """*term* in a markdown string, outside spans already in * or **."""
    parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", s)
    for i in range(0, len(parts), 2):
        def sub(m):
            hits.append(m.group(1))
            return f"*{m.group(1)}*"
        parts[i] = rx.sub(sub, parts[i])
    return "".join(parts)


def italicize_svg(svg, rx, hits):
    def text_el(m):
        inner, depth_it, out = m.group(2), [], []
        for tok in re.split(r"(<[^>]+>)", inner):
            if tok.startswith("</tspan"):
                if depth_it:
                    depth_it.pop()
                out.append(tok)
            elif tok.startswith("<tspan"):
                if not tok.endswith("/>"):
                    depth_it.append("italic" in tok)
                out.append(tok)
            elif tok.startswith("<"):
                out.append(tok)
            elif any(depth_it):
                out.append(tok)
            else:
                def sub(mm):
                    hits.append(mm.group(1))
                    return f'<tspan font-style="italic">{mm.group(1)}</tspan>'
                out.append(rx.sub(sub, tok))
        return m.group(1) + "".join(out) + m.group(3)

    return re.sub(r"(<text\b(?![^>]*font-style\s*=\s*['\"]italic)[^>]*>)(.*?)(</text>)", text_el, svg, flags=re.S)


def fix(o, rx):
    hits = []

    def walk(ns):
        for n in ns or []:
            if n.get("title"):
                n["title"] = italicize_md(n["title"], rx, hits)
            c = n.get("chart")
            if isinstance(c, dict) and c.get("title"):
                c["title"] = italicize_md(c["title"], rx, hits)
            il = n.get("illustration")
            if isinstance(il, dict):
                if il.get("title"):
                    il["title"] = italicize_md(il["title"], rx, hits)
                if il.get("svg"):
                    il["svg"] = italicize_svg(il["svg"], rx, hits)
            walk(n.get("children"))

    walk(o.get("sections"))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    paths = list(files())
    by_tr = defaultdict(set)
    for p in paths:
        o = json.loads(p.read_text(encoding="utf-8"))
        by_tr[tractate(p.parent.name)] |= terms_of(o)

    total = 0
    for p in paths:
        b = p.with_name(p.stem + ".before_italics.json")
        o = json.loads((b if b.exists() else p).read_text(encoding="utf-8"))
        terms = terms_of(o) | by_tr[tractate(p.parent.name)]
        if not terms:
            continue
        hits = fix(o, pattern(terms))
        total += len(hits)
        print(f"{p.parent.name:18s} {p.stem[11:]:18s} {len(hits):3d}" + (f"  {sorted(set(hits))}" if args.show else ""))
        if args.dry_run or not hits:
            continue
        if not b.exists():
            shutil.copy2(p, b)
        p.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{total} terms italicized")


if __name__ == "__main__":
    main()
