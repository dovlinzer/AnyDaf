"""BDB entries for the words of verse quotes in the Gemara (no API).

A word inside ״…״ in a line of the Hebrew text is part of a verse quote. Its verse is one the text cites (the
Torah Or's references, printed inline: xrefs/site/<Tractate>.json, kind "v") on that line or the three before it,
since a short quote often repeats a verse cited just above. The word is matched to the verse's own words, and
TAHOT (STEPBible's Translators Amalgamated Hebrew OT, CC BY 4.0: every word of the Bible with its Strong's number;
outline/word_gloss/tahot/, gitignored) gives its Strong's number. Sefaria's BDB entries list their Strong's numbers,
so the number names the entry with no guessing between homographs.

Writes outline/word_gloss/bdb.json: {"<Tractate>_<amud>": {"<line>": {"<word index>": {"b": BDB headword,
"v": "Exodus 21:24"}}}}, which word_gloss_export.py merges into the site files.

  WG_RUN=run8 venv/bin/python bdb_verses.py
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import word_gloss_run as W
from word_gloss_pilot import amud_lines

HERE = Path(__file__).parent
WG = HERE / "outline" / "word_gloss"
TAHOT = WG / "tahot"
CACHE = WG / "bdb_cache.json"
OUT = WG / "bdb.json"
BACK = 3   # lines before a quote whose cited verses it may repeat

BOOKS = {"Gen": "Genesis", "Exo": "Exodus", "Lev": "Leviticus", "Num": "Numbers", "Deu": "Deuteronomy",
         "Jos": "Joshua", "Jdg": "Judges", "Rut": "Ruth", "1Sa": "I Samuel", "2Sa": "II Samuel", "1Ki": "I Kings",
         "2Ki": "II Kings", "1Ch": "I Chronicles", "2Ch": "II Chronicles", "Ezr": "Ezra", "Neh": "Nehemiah",
         "Est": "Esther", "Job": "Job", "Psa": "Psalms", "Pro": "Proverbs", "Ecc": "Ecclesiastes",
         "Sng": "Song of Songs", "Isa": "Isaiah", "Jer": "Jeremiah", "Lam": "Lamentations", "Ezk": "Ezekiel",
         "Dan": "Daniel", "Hos": "Hosea", "Jol": "Joel", "Amo": "Amos", "Oba": "Obadiah", "Jon": "Jonah",
         "Mic": "Micah", "Nam": "Nahum", "Hab": "Habakkuk", "Zep": "Zephaniah", "Hag": "Haggai",
         "Zec": "Zechariah", "Mal": "Malachi"}
ROW = re.compile(r"^(\w{3})\.(\d+)\.(\d+)(?:\((\d+)\.(\d+)\))?#\d+=\S*\t([^\t]*)\t[^\t]*\t[^\t]*\t([^\t]*)")
PREFIX = "ודהבלמשכ"


def tahot():
    """'Exodus 21:24' (Hebrew versification) -> [(plain word, Strong's number of its main part)]."""
    verses = {}
    for f in sorted(TAHOT.glob("*.txt")):
        for line in f.read_text().splitlines():
            m = ROW.match(line)
            if not m or m.group(1) not in BOOKS:
                continue
            ch, vs = (m.group(4), m.group(5)) if m.group(4) else (m.group(2), m.group(3))
            heb, st = m.group(6), m.group(7)
            main = re.search(r"\{H(\d+)", st) or re.search(r"H(\d+)", st)
            lem = re.search(r"\{H\d+\w*=([^=]+)=", line)
            word = W.fin(W.plain(heb.replace("/", "").replace("\\", "")))
            if word:
                verses.setdefault(f"{BOOKS[m.group(1)]} {int(ch)}:{int(vs)}", []).append(
                    (word, str(int(main.group(1))) if main else None, lem.group(1) if lem else ""))
    return verses


def expand(ref):
    """'Exodus 21:24-25' -> ['Exodus 21:24', 'Exodus 21:25']."""
    m = re.match(r"^(.*) (\d+):(\d+)(?:-(\d+))?$", ref)
    if not m:
        return []
    a, b = int(m.group(3)), int(m.group(4) or m.group(3))
    return [f"{m.group(1)} {m.group(2)}:{v}" for v in range(a, min(b, a + 10) + 1)]


def skel(w):
    return re.sub(r"(?<=.)[וי](?=.)", "", w)


def match(word, verse):
    """Index of the verse word that the Gemara's word is: same letters, then without vowel letters (ו, י), each also
    with a prefix letter added or dropped on either side."""
    w = W.fin(re.sub(r"[^א-ת]", "", W.plain(word)))   # a quote's last word carries its ״
    forms = [w] + [w[k:] for k in (1, 2) if len(w) > k + 1 and all(c in PREFIX for c in w[:k])]
    for test in (lambda a, b: a == b, lambda a, b: skel(a) == skel(b)):
        for i, (v, *_) in enumerate(verse):
            vs = [v] + [v[k:] for k in (1, 2) if len(v) > k + 1 and all(c in PREFIX for c in v[:k])]
            if any(test(a, b) for a in forms for b in vs):
                return i
    return None


def bdb_entry(word, ref, strong, lemma, cache):
    """The BDB Dictionary entry Sefaria gives for this word in this verse whose Strong's numbers include it."""
    key = f"{word}|{ref}"
    if key not in cache:
        url = ("https://www.sefaria.org/api/words/" + urllib.parse.quote(word) + "?never_split=1&lookup_ref=" +
               urllib.parse.quote(ref))
        for _ in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "word-glossary"}), timeout=30) as r:
                    es = json.load(r)
                break
            except Exception:
                time.sleep(2)
        else:
            es = []
        cache[key] = [{"hw": e["headword"], "s": e.get("strong_numbers") or []} for e in es
                      if e.get("parent_lexicon") == "BDB Dictionary"]
    hits = [e["hw"] for e in cache[key] if strong in e["s"]]
    # several entries can share a Strong's number (עַיִן and עוֹנָה): TAHOT's lemma picks between them
    bare = lambda h: W.plain(re.sub(r"[\u00b2\u00b3\u00b9\u2070-\u2079\s]+$", "", h))
    same = [h for h in hits if lemma and bare(h) == W.plain(lemma)]
    return (same or hits or [None])[0]


def main():
    verses = tahot()
    print(len(verses), "verses in TAHOT")
    meta = json.loads((W.RUN / "meta.json").read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    out, stats = {}, {"quoted": 0, "no verse": 0, "no match": 0, "no entry": 0, "found": 0}
    for c, m in meta.items():
        t, a = m["tractate"], m["amud"]
        xr = json.loads((HERE / "xrefs" / "site" / f"{t}.json").read_text())["amudim"].get(a, {})
        lines = {str(x["n"]): x for x in amud_lines(t, a)}
        amud_refs = [r for v in xr.values() for x in v if x[0] == "v" for r in expand(x[1])]
        for n, ws in m["words"].items():
            q = W.quoted(lines[n].get("he") or "")
            if not q:
                continue
            refs = []
            for k in range(int(n), max(0, int(n) - BACK - 1), -1):
                for x in xr.get(str(k), []):
                    kind, r = x[0], x[1]
                    if kind == "v":
                        refs += [x for x in expand(r) if x not in refs]
            # each quote (a run of words inside ״…״) goes with the cited verse that most of its words match: at
            # least two, or its one word if that is not a small word (a song or saying in quotes matches no verse)
            runs, cur = [], []
            for i in sorted(x for x in q if x < len(ws)):
                if cur and i != cur[-1] + 1:
                    runs.append(cur)
                    cur = []
                cur.append(i)
            if cur:
                runs.append(cur)
            for run in runs:
                stats["quoted"] += len(run)
                if not refs and not amud_refs:
                    stats["no verse"] += len(run)
                    continue
                # distinct verse words of three letters or more (three לא's in a song match one לֹא, not a verse)
                strong_hits = lambda r, js: len({j for j in js.values() if j is not None and len(verses[r][j][0]) >= 3})
                def best_of(rs):
                    return max(((r, {i: match(ws[i], verses[r]) for i in run}) for r in rs if r in verses),
                               key=lambda x: strong_hits(*x), default=(None, {}))
                best = best_of(refs)
                if not best[0] or not strong_hits(*best):   # a verse cited further up the amud
                    best = best_of(amud_refs)
                r, js = best
                hit = strong_hits(r, js) if r else 0
                if r and not hit and len(run) == 1 and js[run[0]] is not None:
                    hit = 1   # a one-word quote of a short word (דם)
                if not (hit >= 2 or (len(run) <= 2 and hit == 1)):
                    stats["no match"] += len(run)
                    continue
                for i in run:
                    j = js[i]
                    if j is None:
                        stats["no match"] += 1
                        continue
                    _found(out, stats, cache, verses, r, j, t, a, n, i)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(stats)


def _found(out, stats, cache, verses, r, j, t, a, n, i):
    word, strong, lemma = verses[r][j]
    hw = bdb_entry(word, r, strong, lemma, cache) if strong else None
    if not hw:
        stats["no entry"] += 1
        return
    stats["found"] += 1
    out.setdefault(f"{t.replace(' ', '_')}_{a}", {}).setdefault(n, {})[str(i)] = {"b": hw, "v": r}


if __name__ == "__main__":
    main()
