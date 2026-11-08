#!/usr/bin/env python3
"""Build the Vilna-style cross-references for each line of the Bavli. No Anthropic API calls.

Three layers, keyed by the same line numbers as daf_text/ (Gemara segment N = line label 2a.N):

    em      Ein Mishpat / Ner Mitzvah (Rambam, Semag, Tur, Shulchan Arukh), from Sefaria's links
    ms      Mesoret HaShas (other Gemarot, Tosefta, Mishnah, Midrash...), from Sefaria's links
    verse   Verses quoted on the line, read from the text itself: Wikisource Hebrew's "(דברים כב, ג)"
            (which also gives the word it follows) and Davidson's "(Deuteronomy 22:3)". Sefaria's
            links to Tanakh are not used: they have no Torah Or label and include looser links.

    venv/bin/python build_xrefs.py fetch      # stream Sefaria's export, keep the Bavli rows (~700 MB read)
    venv/bin/python build_xrefs.py build      # write xrefs/<Tractate>.json and outline/xrefs_coverage.md

    xrefs/<Tractate>.json  {"tractate", "export", "amudim": {"2a": {"7": [
        {"k": "verse", "ref": "Deuteronomy 22:3", "src": "he+en", "w": 7},
        {"k": "em", "work": "rambam", "ref": "Mishneh Torah, Sales 20:4"},
        {"k": "ms", "cat": "Talmud", "ref": "Bava Kamma 113b:9", "to": "2a:8"}]}}}

"to" is the end of a passage that runs past this line; the reference sits on the passage's first
line, and line "0" holds links Sefaria ties to the whole amud. "w" counts the words before the
citation in the Wikisource text, citations left out.
fetch is resumable, one filtered file per export file under xrefs/cache/. xrefs/ is gitignored.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from build_daf_text import BAVLI

HERE = Path(__file__).parent
DAF_TEXT = HERE / "daf_text"
OUT = HERE / "xrefs"
CACHE = OUT / "cache"
WIKISOURCE = HERE / "page_layout" / "cache" / "text"
REPORT = HERE / "outline" / "xrefs_coverage.md"
EXPORT = "https://storage.googleapis.com/sefaria-export/links/links{}.csv"
EXPORT_FILES = 17   # links0..links16 as of the October 2026 export

csv.field_size_limit(sys.maxsize)

# Sefaria's spelling -> ours (daf_text, the apps)
ALIASES = {"Eruvin": "Eiruvin", "Chullin": "Hullin"}
TRACTATES = {t[0] for t in BAVLI}
NAMES = sorted(TRACTATES | set(ALIASES), key=len, reverse=True)
CITE = re.compile(
    r"^(%s) (\d+[ab])(?::(\d+))?(?:-(?:(\d+[ab]):)?(\d+[ab]?))?$" % "|".join(map(re.escape, NAMES)))
EM = {"ein mishpat / ner mitsvah", "ein mishpat"}   # Sukkah has the short label
MS = "mesorat hashas"
WORKS = (("Mishneh Torah", "rambam"), ("Shulchan Arukh", "sa"), ("Tur", "tur"), ("Sefer Mitzvot Gadol", "smag"))

BOOKS_HE = {
    "בראשית": "Genesis", "שמות": "Exodus", "ויקרא": "Leviticus", "במדבר": "Numbers", "דברים": "Deuteronomy",
    "יהושע": "Joshua", "שופטים": "Judges", "שמואל א": "I Samuel", "שמואל ב": "II Samuel",
    "מלכים א": "I Kings", "מלכים ב": "II Kings", "ישעיהו": "Isaiah", "ירמיהו": "Jeremiah",
    "יחזקאל": "Ezekiel", "הושע": "Hosea", "יואל": "Joel", "עמוס": "Amos", "עובדיה": "Obadiah",
    "יונה": "Jonah", "מיכה": "Micah", "נחום": "Nahum", "חבקוק": "Habakkuk", "צפניה": "Zephaniah",
    "חגי": "Haggai", "זכריה": "Zechariah", "מלאכי": "Malachi", "תהלים": "Psalms", "משלי": "Proverbs",
    "איוב": "Job", "שיר השירים": "Song of Songs", "רות": "Ruth", "איכה": "Lamentations",
    "קהלת": "Ecclesiastes", "אסתר": "Esther", "דניאל": "Daniel", "עזרא": "Ezra", "נחמיה": "Nehemiah",
    "דברי הימים א": "I Chronicles", "דברי הימים ב": "II Chronicles",
}
HE_CITE = re.compile(r"\((%s) ([א-ת׳״'\"]+),? ([א-ת׳״'\"]+)\)" % "|".join(sorted(BOOKS_HE, key=len, reverse=True)))
EN_CITE = re.compile(
    r"\((%s) (\d+):(\d+)(?:[-–](?:\d+:)?\d+)?\)" % "|".join(sorted(BOOKS_HE.values(), key=len, reverse=True)))
LETTERS = dict(zip("אבגדהוזחטיכלמנסעפצקרשת", (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200, 300, 400)))


def gematria(s: str) -> int:
    return sum(LETTERS.get(c, 0) for c in s)


def parse_cite(s: str):
    """(tractate, amud, line or None, end) for a Bavli citation, else None. end is "2b:3", "8" or None."""
    m = CITE.match(s)
    if not m:
        return None
    tr, amud, line, end_amud, end = m.groups()
    tail = f"{end_amud}:{end}" if end_amud else end
    return ALIASES.get(tr, tr), amud, int(line) if line else None, tail


def fetch():
    CACHE.mkdir(parents=True, exist_ok=True)
    for i in range(EXPORT_FILES):
        dest = CACHE / f"bavli{i}.csv"
        if dest.exists():
            print(f"links{i}: already fetched", flush=True)
            continue
        kept = read = 0
        tmp = dest.with_suffix(".tmp")
        req = urllib.request.Request(EXPORT.format(i), headers={"User-Agent": "AnyDaf cross-references"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "w", newline="") as out:
            w = csv.writer(out)
            for row in csv.reader(io.TextIOWrapper(r, encoding="utf-8", newline="")):
                read += 1
                if len(row) >= 7 and (parse_cite(row[0]) or parse_cite(row[1])):
                    w.writerow(row[:7])
                    kept += 1
        tmp.rename(dest)
        print(f"links{i}: {read:,} rows, kept {kept:,}", flush=True)


def wikisource_lines(tr: str, amud: str):
    name = {"Eiruvin": "Eruvin"}.get(tr, tr).replace(" ", "_")
    for n in (name, tr.replace(" ", "_")):
        p = WIKISOURCE / f"{n}.{amud}__Wikisource_Talmud_Bavli.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def verses_he(text: str):
    """[(ref, words before)] from one line of Wikisource's text."""
    plain = re.sub(r"<[^>]+>", " ", text)
    found, words, pos = [], 0, 0
    for m in HE_CITE.finditer(plain):
        words += len(plain[pos:m.start()].split())
        pos = m.end()
        ch, vs = gematria(m.group(2)), gematria(m.group(3))
        if ch and vs:
            found.append((f"{BOOKS_HE[m.group(1)]} {ch}:{vs}", words))
    return found


def verses_en(text: str):
    # "(see Leviticus 5:2)" is the translator's note and doesn't match: the citation must open the parens
    return [f"{b} {c}:{v}" for b, c, v in EN_CITE.findall((text or "").replace("\xa0", " "))]


def build():
    amudim = {}
    for f in sorted(DAF_TEXT.glob("*.json")):
        d = json.loads(f.read_text())
        amudim[d["tractate"]] = {a: v["segments"] for a, v in d["amudim"].items()}
    refs = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    stats = collections.defaultdict(collections.Counter)
    problems = collections.Counter()
    seen = set()
    other_types = collections.Counter()

    def place(cite, other, kind, extra):
        tr, amud, line, end = parse_cite(cite)
        segs = amudim.get(tr, {}).get(amud)
        if not segs:
            problems["amud not in daf_text"] += 1
            return
        if line is None:
            problems["anchored to the whole amud, kept as line 0"] += 1
            line = 0
        if line > len(segs):
            problems["line past the end of the amud"] += 1
            return
        key = (tr, amud, line, kind, other)
        if key in seen:
            return
        seen.add(key)
        item = {"k": kind, **extra, "ref": other}
        if end:
            item["to"] = end if ":" in end or end[-1] in "ab" else f"{amud}:{end}"
        refs[tr][amud][str(line)].append(item)
        stats[tr][kind] += 1
        stats[tr][extra.get("work") or extra.get("cat") or kind] += 1

    for f in sorted(CACHE.glob("bavli*.csv")):
        with open(f, newline="") as fh:
            for a, b, ctype, _t1, _t2, c1, c2 in csv.reader(fh):
                for cite, other, cat in ((a, b, c2), (b, a, c1)):
                    if not parse_cite(cite):
                        continue
                    if ctype in EM and cat == "Halakhah":
                        work = next((w for pre, w in WORKS if other.startswith(pre)), "other")
                        place(cite, other, "em", {"work": work})
                    elif ctype == MS:
                        place(cite, other, "ms", {"cat": cat})
                    elif cat in ("Talmud", "Tosefta", "Mishnah"):
                        other_types[(ctype or "(no label)", cat)] += 1

    agree = collections.Counter()
    no_he, mismatched = [], []
    for tr, am in amudim.items():
        for amud, segs in am.items():
            lines = wikisource_lines(tr, amud)
            if lines is None:
                no_he.append(f"{tr} {amud}")
            elif len(lines) != len(segs):
                problems["Wikisource and daf_text differ in line count"] += 1
                mismatched.append(f"{tr} {amud} ({len(lines)}/{len(segs)})")
            for i, seg in enumerate(segs):
                en = verses_en(seg.get("en"))
                he = verses_he(lines[i]) if lines and i < len(lines) and isinstance(lines[i], str) else []
                left = list(en)
                items = []
                for ref, w in he:
                    src = "he"
                    if ref in left:
                        left.remove(ref)
                        src = "he+en"
                    items.append({"k": "verse", "ref": ref, "src": src, "w": w})
                items += [{"k": "verse", "ref": r, "src": "en"} for r in left]
                for it in items:
                    agree[it["src"]] += 1
                    stats[tr]["verse"] += 1
                if items:
                    refs[tr][amud][str(seg.get("n", i + 1))][:0] = items

    export_date = "2026-10-01"
    for tr, am in refs.items():
        (OUT / f"{tr}.json").write_text(json.dumps(
            {"tractate": tr, "export": export_date, "amudim": am}, ensure_ascii=False, separators=(",", ":")))

    write_report(amudim, refs, stats, agree, problems, other_types, no_he, export_date)
    print("line-count mismatches:", ", ".join(mismatched))
    print(f"verses: {dict(agree)}\nproblems: {dict(problems)}\nno Wikisource text: {len(no_he)} amudim")
    print(f"wrote {len(refs)} tractates to {OUT}, report {REPORT}")


def write_report(amudim, refs, stats, agree, problems, other_types, no_he, export_date):
    out = [f"# Cross-reference coverage (Sefaria export {export_date})", "",
           "Counts of references, per tractate. *Amudim with EM* is the share with any Ein Mishpat link. "
           "Generated by `build_xrefs.py`.", "",
           "| Tractate | Amudim | With EM | Rambam | SA | Tur | Semag | Mesoret HaShas | Gemara | Tosefta | Verses |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    total = collections.Counter()
    order = [t[0] for t in BAVLI]
    for tr in order:
        if tr not in amudim:
            continue
        n = len(amudim[tr])
        em = sum(1 for lines in refs[tr].values() if any(i["k"] == "em" for l in lines.values() for i in l))
        s = stats[tr]
        row = [n, em, s["rambam"], s["sa"], s["tur"], s["smag"], s["ms"], s["Talmud"], s["Tosefta"], s["verse"]]
        for k, v in zip("n em r s t m ms g f v".split(), row):
            total[k] += v
        out.append(f"| {tr} | {n} | {round(100 * em / n) if n else 0}% | " + " | ".join(map(str, row[2:])) + " |")
    out.append(f"| **All** | {total['n']} | {round(100 * total['em'] / total['n'])}% | " + " | ".join(
        str(total[k]) for k in "r s t m ms g f v".split()) + " |")
    out += ["", "## Verses: Hebrew and English citations on the same line", "",
            f"Both: {agree['he+en']:,}. Hebrew only: {agree['he']:,}. English only: {agree['en']:,}.", "",
            "## Problems", ""] + [f"- {k}: {v:,}" for k, v in problems.most_common()]
    out += [f"- Amudim with no cached Wikisource text: {len(no_he)}" + (f" ({', '.join(no_he[:40])})" if no_he else ""), "",
            "## Bavli links with other labels (not used)", ""]
    out += [f"- {t}, to {c}: {v:,}" for (t, c), v in other_types.most_common(20)]
    REPORT.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "build"])
    args = ap.parse_args()
    fetch() if args.step == "fetch" else build()
