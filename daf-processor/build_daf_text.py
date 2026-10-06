#!/usr/bin/env python3
"""Build our own saved copy of the Bavli text (Hebrew/Aramaic + Sefaria's English), for the
AnyDaf web app and, later, the apps. No Anthropic API calls.

The study outline's anchors (`6a.8`) are Sefaria segment numbers as sefaria.py writes them into
sefaria*.md, so the saved copy has to use exactly that numbering. Most of Shas is already cached
in output/*/sefaria*.md (current daf, previous amud, next daf); this script collects those, fetches
the remaining amudim from Sefaria with the same function the pipeline uses (sefaria._fetch_amud),
and writes one JSON file per tractate:

    daf_text/<Tractate>.json  {"tractate", "amudim": {"6a": {"source": "cache"|"sefaria",
                                                           "segments": [{"n", "he", "en"}]}}}

Then `--upload` loads it into Supabase `daf_text` (create the table first with
../daf-text-migration.sql in the SQL editor), one row per amud.

    venv/bin/python build_daf_text.py --dry-run        # count what's cached vs. missing
    venv/bin/python build_daf_text.py                  # collect + fetch the missing amudim
    venv/bin/python build_daf_text.py --upload         # also load into Supabase
    venv/bin/python build_daf_text.py --only Chagigah  # limit to tractates

Fetching is resumable: amudim already in daf_text/ are not fetched again (use --refetch).

Hebrew explanation (for the Hebrew outlines): `--steinsaltz` also fetches Sefaria's Hebrew
Steinsaltz ("William Davidson Edition - Hebrew", CC BY-NC), one request per tractate, into
daf_text/steinsaltz/<Tractate>.json, and every run merges it into the segments as "hx" (Gemara
words in **bold**, as in "en"). It is numbered line for line with the Gemara; an amud whose line
count differs is left without "hx" and reported.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import sefaria

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
OUTPUT = HERE / "output"
OUT = HERE / "daf_text"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")
TABLE = "daf_text"
FETCH_PAUSE = 0.4   # seconds between Sefaria requests
UPLOAD_CHUNK = 50

# (Sefaria name, first daf, last daf, first amud) — from AnyDaf/Tractate.swift. The last daf's
# amud b is tried and skipped if Sefaria has no text (many tractates end on amud a).
BAVLI = [
    ("Berakhot", 2, 64, "a"), ("Shabbat", 2, 157, "a"), ("Eiruvin", 2, 105, "a"),
    ("Pesachim", 2, 121, "a"), ("Shekalim", 2, 22, "a"), ("Rosh Hashanah", 2, 35, "a"),
    ("Yoma", 2, 88, "a"), ("Sukkah", 2, 56, "a"), ("Beitzah", 2, 40, "a"), ("Taanit", 2, 31, "a"),
    ("Megillah", 2, 32, "a"), ("Moed Katan", 2, 29, "a"), ("Chagigah", 2, 27, "a"),
    ("Yevamot", 2, 122, "a"), ("Ketubot", 2, 112, "a"), ("Nedarim", 2, 91, "a"), ("Nazir", 2, 66, "a"),
    ("Sotah", 2, 49, "a"), ("Gittin", 2, 90, "a"), ("Kiddushin", 2, 82, "a"),
    ("Bava Kamma", 2, 119, "a"), ("Bava Metzia", 2, 119, "a"), ("Bava Batra", 2, 176, "a"),
    ("Sanhedrin", 2, 113, "a"), ("Makkot", 2, 24, "a"), ("Shevuot", 2, 49, "a"),
    ("Avodah Zarah", 2, 76, "a"), ("Horayot", 2, 14, "a"),
    ("Zevachim", 2, 120, "a"), ("Menachot", 2, 110, "a"), ("Hullin", 2, 142, "a"),
    ("Bekhorot", 2, 61, "a"), ("Arakhin", 2, 34, "a"), ("Temurah", 2, 34, "a"), ("Keritot", 2, 28, "a"),
    ("Meilah", 2, 22, "a"), ("Kinnim", 22, 25, "a"), ("Tamid", 25, 33, "b"), ("Middot", 34, 37, "a"),
    ("Niddah", 2, 73, "a"),
]

HEADER = re.compile(r"^###\s+(.+?)\s+(\d+[ab])\s*$")
ITEM = re.compile(r"^\*\*(\d+)\.\*\*\s*$")


def parse_md(text: str):
    """Yield (tractate, amud, segments) for each '### Tractate 6a' section of a sefaria*.md."""
    cur, amud, segs, n = None, None, [], None
    for line in text.splitlines():
        m = HEADER.match(line)
        if m:
            if cur:
                yield cur, amud, segs
            cur, amud, segs, n = sefaria._lookup(m.group(1)) or m.group(1), m.group(2), [], None
            continue
        m = ITEM.match(line)
        if m:
            n = int(m.group(1))
            segs.append({"n": n, "he": "", "en": ""})
            continue
        if segs and n is not None:
            if line.startswith("*Hebrew/Aramaic:*"):
                segs[-1]["he"] = line[len("*Hebrew/Aramaic:*"):].strip()
            elif line.startswith("*Translation:*"):
                segs[-1]["en"] = line[len("*Translation:*"):].strip()
    if cur:
        yield cur, amud, segs


def collect_cache() -> dict:
    """{(tractate, amud): segments} from every cached sefaria*.md. A daf's own sefaria.md wins
    over a neighbor's prev/next copy; among equals the longest (most segments) wins."""
    found = {}
    for rank, name in ((0, "sefaria.md"), (1, "sefaria_prev.md"), (1, "sefaria_next.md")):
        for p in OUTPUT.glob(f"*/{name}"):
            for tr, amud, segs in parse_md(p.read_text(encoding="utf-8")):
                if not segs:
                    continue
                key = (tr, amud)
                old = found.get(key)
                if old is None or (rank, -len(segs)) < (old[0], -len(old[1])):
                    found[key] = (rank, segs)
    return {k: v[1] for k, v in found.items()}


def wanted(only: set | None):
    for tr, start, end, first in BAVLI:
        if only and tr not in only:
            continue
        for daf in range(start, end + 1):
            for side in ("a", "b"):
                if daf == start and first == "b" and side == "a":
                    continue
                yield tr, f"{daf}{side}"


def fetch(tr: str, amud: str):
    md = sefaria._fetch_amud(tr, int(amud[:-1]), amud[-1])
    if not md:
        return None
    segs = next((s for _, _, s in parse_md(md)), [])
    return segs or None


def upload(books: dict, dry: bool):
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key and not dry:
        sys.exit("SUPABASE_SERVICE_KEY not set in .env")
    h = {"apikey": key or "", "Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates"}
    rows = [{"tractate": tr, "amud": amud, "daf": int(amud[:-1]), "side": amud[-1],
             "segments": a["segments"], "source": a["source"]}
            for tr, book in books.items() for amud, a in book["amudim"].items()]
    print(f"upload: {len(rows)} rows -> {TABLE}{' (dry run)' if dry else ''}")
    if dry:
        return
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=tractate,amud"
    for i in range(0, len(rows), UPLOAD_CHUNK):
        chunk = rows[i:i + UPLOAD_CHUNK]
        for attempt in range(6):
            try:
                r = requests.post(url, headers=h, json=chunk, timeout=60)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 5:
                    raise
                time.sleep(2 * 2 ** attempt)
        if r.status_code not in (200, 201):
            sys.exit(f"upload failed at row {i}: HTTP {r.status_code} {r.text[:300]}")
        print(f"  {min(i + UPLOAD_CHUNK, len(rows))}/{len(rows)}", end="\r")
    print()


STEINSALTZ = OUT / "steinsaltz"


def clean_hx(t: str) -> str:
    t = re.sub(r"<big>[^<]*</big>\s*", "", t)            # paragraph letters (א, ב ...)
    t = re.sub(r"(?s)<sup[^>]*>.*?</sup>|<i class=\"footnote\">.*?</i>", "", t)
    t = re.sub(r"</?(?:b|strong)>", "**", t)
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("****", "").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t).strip()


def amud_after(a: str) -> str:
    return a[:-1] + "b" if a[-1] == "a" else f"{int(a[:-1]) + 1}a"


def fetch_steinsaltz(books: dict, refetch: bool):
    """One request per tractate: Steinsaltz_on_<Tractate>.<first>-<last>, Hebrew version."""
    STEINSALTZ.mkdir(exist_ok=True)
    for tr, book in books.items():
        p = STEINSALTZ / f"{tr}.json"
        if p.exists() and not refetch:
            continue
        amudim = sorted(book["amudim"], key=amud_key)
        if not amudim:
            continue
        name = {"Eiruvin": "Eruvin", "Hullin": "Chullin"}.get(tr, tr)   # Sefaria's spelling for this edition
        ref = f"Steinsaltz_on_{name.replace(' ', '_')}.{amudim[0]}-{amudim[-1]}"
        for attempt in range(5):
            try:
                r = requests.get(f"https://www.sefaria.org/api/v3/texts/{ref}", params={"version": "hebrew"}, timeout=120)
                break
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 4:
                    raise
                time.sleep(5 * 2 ** attempt)
        vs = r.json().get("versions") if r.ok else None
        if not vs:
            print(f"  {tr}: no Hebrew Steinsaltz on Sefaria (HTTP {r.status_code})")
            continue
        out, a = {}, amudim[0]
        for seg in vs[0]["text"]:
            out[a] = [clean_hx(x) if isinstance(x, str) else "" for x in (seg if isinstance(seg, list) else [seg])]
            a = amud_after(a)
        p.write_text(json.dumps({"tractate": tr, "version": vs[0].get("versionTitle"), "license": vs[0].get("license"),
                                 "amudim": out}, ensure_ascii=False), encoding="utf-8")
        print(f"  {tr}: {len(out)} amudim of Hebrew Steinsaltz")
        time.sleep(FETCH_PAUSE)


_NIKUD = re.compile(r"[\u0591-\u05C7]")


def _words(t: str) -> set:
    return set(re.findall(r"[\u05D0-\u05EA]{2,}", _NIKUD.sub("", t.replace("\u05BE", " "))))


def skipped_line(segs: list, hx: list):
    """Where an amud has one Gemara line more than its explanation (most often the chapter's
    closing "hadran" line, which Steinsaltz doesn't explain), the line to leave out: the one that
    makes the Gemara words Steinsaltz quotes in bold agree best with the lines they sit beside.
    None when no choice is clearly right."""
    g = [_words(s_["he"]) for s_ in segs]
    b = [_words(" ".join(re.findall(r"\*\*(.+?)\*\*", h))) for h in hx]
    ov = lambda i, j: len(g[i] & b[j]) / (len(b[j]) or 1)
    n = len(hx)
    pre = [0.0]
    for i in range(n):
        pre.append(pre[-1] + ov(i, i))
    suf = [0.0] * (n + 2)
    for i in range(n, 0, -1):            # Gemara line i pairs with explanation i-1 after the skip
        suf[i] = suf[i + 1] + ov(i, i - 1)
    scores = [pre[k] + suf[k + 1] for k in range(n + 1)]
    best = max(range(n + 1), key=lambda k: scores[k])
    runner = max((x for k, x in enumerate(scores) if k != best), default=0)
    hadran = [k for k, s_ in enumerate(segs) if "הדרן" in s_["he"]]
    if hadran and scores[hadran[0]] >= scores[best] - 0.5:
        return hadran[0]
    return best if scores[best] - runner >= 0.5 else None


def merge_steinsaltz(books: dict):
    """Put the saved Steinsaltz into each segment as "hx", where the line counts agree."""
    added, off, skips = 0, [], []
    for book in books.values():               # start clean, so a rerun never keeps a stale "hx"
        for x in book["amudim"].values():
            for s_ in x["segments"]:
                s_.pop("hx", None)
    for tr, book in books.items():
        p = STEINSALTZ / f"{tr}.json"
        if not p.exists():
            continue
        st = json.loads(p.read_text(encoding="utf-8"))["amudim"]
        for amud, a in book["amudim"].items():
            hx = st.get(amud)
            if hx is None:
                continue
            segs = a["segments"]
            pairs = list(zip(segs, hx))
            if len(hx) == len(segs) - 1 and (k := skipped_line(segs, hx)) is not None:
                pairs = list(zip(segs[:k] + segs[k + 1:], hx))
                skips.append(f"{tr} {amud}.{k + 1}")
            elif len(hx) != len(segs):
                off.append(f"{tr} {amud} ({len(segs)} lines, {len(hx)} explained)")
                continue
            for s_, h in pairs:
                if h:
                    s_["hx"] = h
                    added += 1
    print(f"Hebrew Steinsaltz: {added} lines; {len(skips)} amudim with one unexplained line left out ({", ".join(skips)})" + (f"; {len(off)} amudim left out, line counts differ: " + ", ".join(off) if off else ""))


def amud_key(a: str):
    return int(a[:-1]), a[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count cached vs. missing; fetch and write nothing")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--refetch", action="store_true", help="fetch from Sefaria even when saved")
    ap.add_argument("--only", nargs="+", help="tractate names (Sefaria spelling)")
    ap.add_argument("--steinsaltz", action="store_true", help="also fetch Sefaria's Hebrew Steinsaltz (merged as \"hx\")")
    args = ap.parse_args()
    only = set(args.only) if args.only else None

    cache = collect_cache()
    OUT.mkdir(exist_ok=True)
    books = {}
    for tr, *_ in BAVLI:
        if only and tr not in only:
            continue
        p = OUT / f"{tr}.json"
        books[tr] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"tractate": tr, "amudim": {}}

    missing = []
    for tr, amud in wanted(only):
        book = books[tr]["amudim"]
        if (tr, amud) in cache and not args.refetch:
            book.setdefault(amud, {"source": "cache", "segments": cache[(tr, amud)]})
            if book[amud]["source"] == "cache":
                book[amud]["segments"] = cache[(tr, amud)]
        elif amud not in book or args.refetch:
            missing.append((tr, amud))
    have = sum(len(b["amudim"]) for b in books.values())
    print(f"{have} amudim from the cache or earlier runs; {len(missing)} to fetch from Sefaria")
    if args.dry_run:
        by_tr = {}
        for tr, a in missing:
            by_tr.setdefault(tr, []).append(a)
        for tr, a in by_tr.items():
            print(f"  {tr}: {len(a)} ({', '.join(a[:6])}{'…' if len(a) > 6 else ''})")
        return

    empty = []
    for i, (tr, amud) in enumerate(missing, 1):
        segs = fetch(tr, amud)
        if segs:
            books[tr]["amudim"][amud] = {"source": "sefaria", "segments": segs}
        else:
            empty.append(f"{tr} {amud}")
        if i % 20 == 0 or i == len(missing):
            print(f"  fetched {i}/{len(missing)}")
            for t, b in books.items():   # save as we go, so an interruption loses little
                b["amudim"] = dict(sorted(b["amudim"].items(), key=lambda kv: amud_key(kv[0])))
                (OUT / f"{t}.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        time.sleep(FETCH_PAUSE)

    if args.steinsaltz:
        fetch_steinsaltz(books, args.refetch)
    merge_steinsaltz(books)
    for t, b in books.items():
        b["amudim"] = dict(sorted(b["amudim"].items(), key=lambda kv: amud_key(kv[0])))
        (OUT / f"{t}.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    total = sum(len(b["amudim"]) for b in books.values())
    print(f"saved {total} amudim in {OUT.relative_to(HERE)}/")
    if empty:
        print(f"no text on Sefaria for {len(empty)} amudim (expected where a tractate ends on amud a): "
              + ", ".join(empty))
    if args.upload:
        upload(books, dry=False)


if __name__ == "__main__":
    main()
