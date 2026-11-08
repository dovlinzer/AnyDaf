#!/usr/bin/env python3
"""Check the cross-references in xrefs/ against the texts they cite. No Anthropic API calls.

Sefaria's Ein Mishpat and Mesoret HaShas links were read from the printed margin, and Rashi-script
numerals are easy to misread (author's catch, Bava Metzia 2a: Rambam Plaintiff and Defendant 9:8 was
read as 9:1, ח as א). Wikisource has the same misreading, so it is no independent check. This script
compares each Gemara line with the passage it cites, and with the passages its number would name if
one numeral letter were misread (or the number were off by one or two, as editions number
differently). It flags a reference when another candidate matches the line clearly better, or when
the cited passage doesn't exist.

    venv/bin/python check_xrefs.py fetch     # cited books from Sefaria's export -> xrefs/sources/
    venv/bin/python check_xrefs.py check     # -> outline/xref_check/flags.json, outline/xref_check/report.md

Matching is by shared words, weighted by rarity, between the Gemara (its Aramaic plus Steinsaltz's
Hebrew) and the cited text. A low score alone proves nothing: the Rambam often rewords the Gemara.
Only "another candidate fits much better" and "doesn't exist" are flagged. Midrash and Megillat
Ta'anit are not checked (their numbering differs too much between editions).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

from build_xrefs import BAVLI, LETTERS, OUT as XREFS, parse_cite

HERE = Path(__file__).parent
SOURCES = XREFS / "sources"
RESULT = HERE / "outline" / "xref_check"
EXPORT = "https://storage.googleapis.com/sefaria-export/"
CHECKED_CATS = {"Talmud", "Mishnah", "Tosefta", "Tanakh"}

# Numeral letters a reader can mistake for one another in Rashi script (and in the scans' OCR)
LOOKALIKE = {"א": "ח", "ח": "אהת", "ה": "חת", "ת": "חה", "ד": "ר", "ר": "ד", "ב": "כ", "כ": "ב",
             "ו": "זי", "ז": "ו", "י": "ו", "ג": "נ", "נ": "ג", "ט": "מ", "מ": "ט", "ע": "צ", "צ": "ע",
             "ק": "ה", "ס": "ט"}
NUMS = sorted(((v, k) for k, v in LETTERS.items()), reverse=True)

# Flag when an alternative beats the cited passage by this much. A neighbouring number has to win by
# far more than a look-alike: neighbouring halakhot share their vocabulary.
RATIO, MARGIN, FLOOR = 1.6, 0.06, 0.12
NEAR_RATIO, NEAR_MARGIN = 2.5, 0.12
MIN_WORDS = 8   # a shorter line borrows the next one


def he_num(n: int) -> str:
    if n in (15, 16):
        return {15: "טו", 16: "טז"}[n]
    out = ""
    for v, c in NUMS:
        while n >= v:
            out += c
            n -= v
    return out


def lookalikes(n: int) -> list[int]:
    """Numbers whose usual numeral differs from n's by one look-alike letter."""
    s, found = he_num(n), set()
    for i, c in enumerate(s):
        for r in LOOKALIKE.get(c, ""):
            t = s[:i] + r + s[i + 1:]
            v = sum(LETTERS[x] for x in t)
            if v > 0 and he_num(v) == t:
                found.add(v)
    return sorted(found - {n})


# --- words -----------------------------------------------------------------------------------
FINALS = str.maketrans("ךםןףץ", "כמנפצ")
PREFIX = "הבלמשכד"


def words(text: str) -> set[str]:
    text = re.sub(r"<[^>]+>|\*\*", " ", text or "")
    text = re.sub(r"[֑-ׇ]", "", text).replace("־", " ")
    out = set()
    for w in re.findall(r"[א-ת]+", text):
        w = w.translate(FINALS)
        if len(w) < 2:
            continue
        out.add(w)
        s = w[1:] if w[0] == "ו" and len(w) > 3 else w
        if s[0] in PREFIX and len(s) > 3:
            s = s[1:]
        out.add(s)
    return out


class Scorer:
    def __init__(self):
        self.df = collections.Counter()
        self.n = 0

    def add(self, ws: set[str]):
        self.df.update(ws)
        self.n += 1

    def idf(self, w):
        return math.log((self.n + 1) / (self.df.get(w, 0) + 1))

    def sim(self, a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        num = sum(self.idf(w) ** 2 for w in a & b)
        da = math.sqrt(sum(self.idf(w) ** 2 for w in a))
        db = math.sqrt(sum(self.idf(w) ** 2 for w in b))
        return num / (da * db) if da and db else 0.0

    def evidence(self, a, b, k=6):
        return sorted(a & b, key=self.idf, reverse=True)[:k]


# --- cited books ------------------------------------------------------------------------------
def toc_paths():
    toc = json.loads(urllib.request.urlopen(EXPORT + "table_of_contents.json", timeout=120).read())
    paths = {}

    def walk(n, cats):
        if isinstance(n, list):
            for x in n:
                walk(x, cats)
        elif "contents" in n:
            walk(n["contents"], cats + [n.get("category")])
        elif "title" in n:
            paths[n["title"]] = cats
    walk(toc, [])
    return paths


def split_ref(ref: str):
    """("Mishneh Torah, Sales", [20, 4]) from "Mishneh Torah, Sales 20:4" (a range keeps its start)."""
    m = re.match(r"^(.*?) (\d+(?::\d+)*)(?:-[\d:]+)?$", ref)
    return (m.group(1), [int(x) for x in m.group(2).split(":")]) if m else (ref, [])


COMPLEX = ("Tur", "Sefer Mitzvot Gadol")


def book_of(title: str):
    """(file title, keys inside it) — Tur and Semag are one book each with named parts."""
    for root in COMPLEX:
        if title.startswith(root + ", "):
            return root, title[len(root) + 2:].split(", ")
    return title, []


def cited_refs():
    for f in sorted(XREFS.glob("*.json")):
        d = json.loads(f.read_text())
        for amud, lines in d["amudim"].items():
            for n, items in lines.items():
                for it in items:
                    yield d["tractate"], amud, int(n), it


def fetch():
    SOURCES.mkdir(parents=True, exist_ok=True)
    paths = toc_paths()
    books = set()
    for _tr, _am, _n, it in cited_refs():
        if it["k"] == "verse" or (it["k"] == "ms" and it.get("cat") in CHECKED_CATS - {"Talmud", "Tanakh"}) \
                or it["k"] == "em" and it.get("work") != "other":
            title = split_ref(it["ref"])[0]
            books.add(book_of(title)[0] if it["k"] != "verse" else title)
    for title in sorted(books):
        dest = SOURCES / f"{title}.json"
        if dest.exists():
            continue
        cats = paths.get(title)
        if cats is None:
            print(f"not in the export's contents: {title}")
            continue
        url = EXPORT + "json/" + "/".join(urllib.parse.quote(x) for x in cats + [title, "Hebrew", "merged.json"])
        try:
            d = json.loads(urllib.request.urlopen(url, timeout=180).read())
        except Exception as e:
            print(f"failed: {title}: {e}")
            continue
        dest.write_text(json.dumps({"title": title, "version": d.get("versionTitle"), "text": d["text"]},
                                   ensure_ascii=False))
        print(f"fetched {title}", flush=True)


_books = {}


def node(title: str, nums: list[int]):
    """The text at a reference (any depth), or None if it doesn't exist."""
    root, keys = book_of(title)
    if root not in _books:
        p = SOURCES / f"{root}.json"
        _books[root] = json.loads(p.read_text())["text"] if p.exists() else None
    t = _books[root]
    if t is None:
        return "missing book"
    for k in keys:
        if not isinstance(t, dict) or k not in t:
            return "missing book"
        t = t[k]
    if isinstance(t, dict):
        t = t.get("")
    for n in nums:
        if not isinstance(t, list) or n < 1 or n > len(t) or not t[n - 1]:
            return None
        t = t[n - 1]
    return t


def flat(t) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return " ".join(flat(x) for x in t)
    return ""


def candidates(nums: list[int], near: bool):
    """(numbers, how they differ from the citation) for every alternative reading."""
    out = []
    for i, n in enumerate(nums):
        for v in lookalikes(n):
            out.append((nums[:i] + [v] + nums[i + 1:], f"{he_num(n)} read for {he_num(v)}"))
    if near and nums:
        for d in (-2, -1, 1, 2):
            v = nums[-1] + d
            if v >= 1:
                out.append((nums[:-1] + [v], f"numbered {'+' if d > 0 else ''}{d}"))
    return out


# --- the Gemara --------------------------------------------------------------------------------
def load_bavli(scorer: Scorer):
    lines = {}
    for f in sorted((HERE / "daf_text").glob("*.json")):
        d = json.loads(f.read_text())
        for amud, v in d["amudim"].items():
            lines[(d["tractate"], amud)] = segs = [words((s.get("he") or "") + " " + (s.get("hx") or ""))
                                                   for s in v["segments"]]
            for ws in segs:
                scorer.add(ws)
    return lines


def window(lines, tr, amud, n, to=None):
    segs = lines.get((tr, amud)) or []
    if not segs:
        return set()
    end = n
    if to and ":" in to and to.split(":")[0] == amud:
        end = int(to.split(":")[1])
    elif to and to.isdigit():
        end = int(to)
    lo, hi = n or 1, min(len(segs), max(n or 1, end))
    ws = set().union(*segs[lo - 1:hi])
    if len(ws) < MIN_WORDS * 2 and hi < len(segs):   # words() keeps two forms of most words
        ws |= segs[hi]
    return ws


def daf_label(daf: int, side: str) -> str:
    return f"{daf}{side}"


def check():
    RESULT.mkdir(parents=True, exist_ok=True)
    scorer = Scorer()
    bavli = load_bavli(scorer)
    for root in [p.stem for p in SOURCES.glob("*.json")]:
        node(root, [])   # load, then count their units for word rarity
    units = []

    def collect(t):
        if isinstance(t, str):
            units.append(t)
        elif isinstance(t, list):
            for x in t:
                if isinstance(x, str):
                    units.append(x)
                else:
                    collect(x)
        elif isinstance(t, dict):
            for x in t.values():
                collect(x)
    for t in _books.values():
        collect(t)
    for u in units:
        scorer.add(words(u))

    stats = collections.defaultdict(collections.Counter)
    flags, weak = [], []
    for tr, amud, n, it in cited_refs():
        layer = it["k"] if it["k"] != "ms" else "ms:" + it.get("cat", "")
        if it["k"] == "em" and it.get("work") == "other" or it["k"] == "ms" and it.get("cat") not in CHECKED_CATS:
            stats[layer]["not checked"] += 1
            continue
        src = window(bavli, tr, amud, n, it.get("to")) if n else set().union(*(bavli.get((tr, amud)) or [set()]))
        if not src:
            stats[layer]["no Gemara text"] += 1
            continue
        if it.get("cat") == "Talmud":
            res = check_bavli(scorer, bavli, src, it["ref"], (tr, amud))
        else:
            res = check_book(scorer, src, it["ref"])
        stats[layer][res["verdict"]] += 1
        if res["verdict"] in ("flag", "doesn't exist"):
            flags.append({"tractate": tr, "amud": amud, "line": n, "layer": layer,
                          "work": it.get("work"), "ref": it["ref"], "to": it.get("to"), **res})
        elif res["verdict"] == "weak match":
            weak.append({"tractate": tr, "amud": amud, "line": n, "layer": layer, "work": it.get("work"),
                         "ref": it["ref"], "to": it.get("to"), "score": res["score"]})

    flags.sort(key=lambda f: (-(f.get("alt_score", 0) - f.get("score", 0)), f["tractate"], f["amud"]))
    (RESULT / "flags.json").write_text(json.dumps(flags, ensure_ascii=False, indent=1))
    (RESULT / "weak.json").write_text(json.dumps(weak, ensure_ascii=False))
    write_report(stats, flags)
    for layer, c in sorted(stats.items()):
        print(layer, dict(c))
    print(f"{len(flags)} flags -> {RESULT}")


def beats(alt: float, cited: float, how: str) -> bool:
    near = how.startswith(("numbered", "daf ", "other amud"))
    ratio, margin = (NEAR_RATIO, NEAR_MARGIN) if near else (RATIO, MARGIN)
    return alt >= FLOOR and alt >= ratio * cited and alt - cited >= margin


def check_book(scorer, src, ref, near=True):
    title, nums = split_ref(ref)
    t = node(title, nums)
    if t == "missing book":
        return {"verdict": "book not available"}
    if t is None:
        alts = []
        for cand, how in candidates(nums, near):
            c = node(title, cand)
            if c not in (None, "missing book"):
                alts.append((scorer.sim(src, words(flat(c))), cand, how))
        best = max(alts, default=None)
        out = {"verdict": "doesn't exist", "score": 0.0}
        if best and best[0] >= FLOOR:
            out.update(alt=f"{title} {':'.join(map(str, best[1]))}", alt_score=round(best[0], 3), how=best[2])
        return out
    tw = words(flat(t))
    score = scorer.sim(src, tw)
    best = None
    for cand, how in candidates(nums, near):
        c = node(title, cand)
        if c in (None, "missing book"):
            continue
        cw = words(flat(c))
        s = scorer.sim(src, cw)
        if best is None or s > best[0]:
            best = (s, cand, how, cw)
    if best and beats(best[0], score, best[2]):
        return {"verdict": "flag", "score": round(score, 3), "alt": f"{title} {':'.join(map(str, best[1]))}",
                "alt_score": round(best[0], 3), "how": best[2],
                "cited_words": scorer.evidence(src, tw), "alt_words": scorer.evidence(src, best[3])}
    return {"verdict": "ok" if score >= FLOOR else "weak match", "score": round(score, 3)}


def check_bavli(scorer, bavli, src, ref, home):
    p = parse_cite(ref)
    if not p:
        return {"verdict": "unparsed"}
    tr, amud, line, _end = p
    daf, side = int(amud[:-1]), amud[-1]

    def best_line(a):
        segs = bavli.get((tr, a))
        if not segs:
            return None
        return max((scorer.sim(src, set().union(*segs[max(0, i - 1):i + 2])), i + 1) for i in range(len(segs)))
    cited = bavli.get((tr, amud))
    if not cited:
        return {"verdict": "doesn't exist", "score": 0.0}
    here = best_line(amud)
    score = scorer.sim(src, set().union(*cited[max(0, (line or 1) - 2):(line or 1) + 1])) if line else here[0]
    alts = [(daf_label(daf, "b" if side == "a" else "a"), "other amud")]
    alts += [(daf_label(v, s), f"{he_num(daf)} read for {he_num(v)}") for v in lookalikes(daf) for s in "ab"]
    alts += [(daf_label(daf + d, s), f"daf {'+' if d > 0 else ''}{d}") for d in (-1, 1) for s in "ab"]
    best = None
    for a, how in alts:
        if (tr, a) == home:   # the line itself always matches
            continue
        b = best_line(a)
        if b and (best is None or b[0] > best[0]):
            best = (b[0], a, b[1], how)
    top = max(here[0], score)
    if best and beats(best[0], top, best[3]):
        return {"verdict": "flag", "score": round(top, 3), "alt": f"{tr} {best[1]}:{best[2]}",
                "alt_score": round(best[0], 3), "how": best[3]}
    if line and here[0] >= FLOOR and here[0] >= RATIO * score and here[0] - score >= MARGIN:
        return {"verdict": "line", "score": round(score, 3), "alt": f"{tr} {amud}:{here[1]}", "alt_score": round(here[0], 3)}
    return {"verdict": "ok" if top >= FLOOR else "weak match", "score": round(top, 3)}


def write_report(stats, flags):
    out = ["# Cross-reference check", "",
           "Each reference compared with the text it cites, and with the passages a misread numeral (or a "
           "numbering off by one or two) would name. Generated by `check_xrefs.py`. *Line*: the right amud, "
           "but Sefaria's line within it fits less well than another (affects only which text a popup shows).", "",
           "| Layer | Checked | Matches | Weak match | Flagged | Doesn't exist | Line | Not checked |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for layer, c in sorted(stats.items()):
        checked = sum(v for k, v in c.items() if k not in ("not checked", "book not available", "no Gemara text"))
        out.append(f"| {layer} | {checked:,} | {c['ok']:,} | {c['weak match']:,} | {c['flag']:,} | "
                   f"{c[chr(100) + 'oesn' + chr(39) + 't exist']:,} | {c['line']:,} | "
                   f"{c['not checked'] + c['book not available'] + c['no Gemara text']:,} |")
    out += ["", "## Flags, strongest first", ""]
    for f in flags[:400]:
        alt = f" -> **{f['alt']}** ({f.get('how', '')}, {f.get('alt_score')} vs {f['score']})" if f.get("alt") else ""
        out.append(f"- {f['tractate']} {f['amud']}:{f['line']} · {f['ref']}{alt}" +
                   (" · doesn't exist" if f["verdict"] == "doesn't exist" else ""))
    (RESULT / "report.md").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "check"])
    args = ap.parse_args()
    fetch() if args.step == "fetch" else check()
