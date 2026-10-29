#!/usr/bin/env python3
"""Teachers, students, colleagues, family and dates for the sages, from Hebrew Wikipedia's
infobox (תבנית:אישיות רבנית). No Anthropic API calls; Wikipedia's API only, cached.

    venv/bin/python sages_wiki.py fetch     # article wikitext -> outline/sages/cache/hewiki_pages/
    venv/bin/python sages_wiki.py build     # -> outline/sages/wiki_facts.json, and a coverage report

Only facts are taken (who taught whom, dates), never Wikipedia's wording: its text is CC BY-SA.
A link in the infobox becomes a sage only when its page is the page of exactly one sage in
sages.json (Sefaria's heWikiLink, or the build's unique-name match); otherwise it is kept as a
plain name, for review.
"""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

from build_sages import CACHE, OUT, HEWIKI, get, wiki_title, strip_nikud

PAGES = CACHE / "hewiki_pages"
FIELDS = {"רבותיו": "teachers", "תלמידיו": "students", "בני דורו": "colleagues",
          "אב": "father", "אם": "mother", "ילדים": "children", "בת זוג": "spouse", "בן זוג": "spouse",
          "חותנים": "in_laws", "חתנים": "sons_in_law", "אחים": "siblings", "קרובים": "relatives"}
DATES = {"תאריך לידה": "born", "תאריך פטירה": "died", "התחלת פעילות": "active_from",
         "סיום פעילות": "active_to"}


# Pages the automatic matching misses (no Sefaria link, a name shared with others).
# Also where Sefaria's own heWikiLink is wrong: it swaps Rabban Gamliel of Yavneh and his grandson.
WIKI_TITLES = {"shmuel-(amora)": "שמואל (אמורא)",
               "rabban-gamliel": "רבן גמליאל דיבנה",
               "rabban-gamliel-b-rabbi-(iii)": "רבן גמליאל ברבי"}


def guess_more(sages, have):
    """For the 250 most quoted sages with no page yet: try each Hebrew name (and the name without
    its title) as a page title; keep a page only if it has the rabbinic infobox and its era
    (תנאים / אמוראים) agrees with the sage's kind. Returns {slug: (title, text)}."""
    census = json.loads((OUT / "census_bavli.json").read_text(encoding="utf-8"))
    ranked = [k for k in census if sages[k]["kind"] in ("tanna", "amora")][:250]
    word = {"tanna": "תנא", "amora": "אמורא"}
    tries = {}
    for slug in ranked:
        if slug in have:
            continue
        names = [WIKI_TITLES[slug]] if slug in WIKI_TITLES else []
        for t in sages[slug]["titles_he"]:
            names += [t, re.sub(r"^(?:רבי|רב|רבן) ", "", t)]
        tries[slug] = list(dict.fromkeys(names))
    flat = sorted({n for v in tries.values() for n in v})
    got = {}
    for i in range(0, len(flat), 50):
        got.update(query(flat[i:i + 50], content=True))
        time.sleep(0.5)
    out = {}
    for slug, names in tries.items():
        for n in names:
            title, text = got.get(n, (None, None))
            info = infobox(text or "")
            era = " ".join(info.get(k, "") for k in ("התחלת פעילות", "סיום פעילות"))
            if info and (word[sages[slug]["kind"]] in era or slug in WIKI_TITLES):
                out[slug] = (n, title, text)
                break
    return out


def candidate_titles(sages, wiki_cats):
    """slug -> the Wikipedia title to fetch: Sefaria's own link, else one of the sage's Hebrew
    names that is a page in Wikipedia's sage categories and belongs to no other sage."""
    owners = {}
    for s in sages.values():
        for t in s["titles_he"]:
            owners[t] = owners.get(t, 0) + 1
    out = {}
    for slug, s in sages.items():
        t = WIKI_TITLES.get(slug) or wiki_title((s.get("links") or {}).get("heWikiLink"))
        if not t:
            t = next((n for n in s["titles_he"] if n in wiki_cats and owners.get(n) == 1), None)
        if t:
            out[slug] = t
    return out


def query(titles, content):
    """{asked title: (canonical title, wikitext or None)} for up to 50 titles, following redirects."""
    params = {"action": "query", "format": "json", "redirects": 1, "titles": "|".join(titles)}
    if content:
        params.update(prop="revisions", rvprop="content", rvslots="main")
    d = get(HEWIKI, **params)["query"]
    hop = {}
    for k in ("normalized", "redirects"):
        for x in d.get(k, []):
            hop[x["from"]] = x["to"]
    pages = {p["title"]: p for p in d.get("pages", {}).values()}
    out = {}
    for t in titles:
        c = t
        for _ in range(3):
            c = hop.get(c, c)
        p = pages.get(c)
        if not p or "missing" in p:
            out[t] = (None, None)
            continue
        text = p["revisions"][0]["slots"]["main"]["*"] if content and p.get("revisions") else None
        out[t] = (c, text)
    return out


def fetch():
    PAGES.mkdir(parents=True, exist_ok=True)
    sages = json.loads((OUT / "sages.json").read_text(encoding="utf-8"))
    wiki_cats = json.loads((CACHE / "hewiki.json").read_text(encoding="utf-8"))
    want = candidate_titles(sages, wiki_cats)
    todo = [(s, t) for s, t in want.items() if not (PAGES / f"{s}.json").exists()]
    print(f"{len(want)} sages have a Wikipedia page; {len(todo)} to fetch")
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        res = query([t for _, t in chunk], content=True)
        for slug, t in chunk:
            title, text = res[t]
            (PAGES / f"{slug}.json").write_text(json.dumps({"asked": t, "title": title, "text": text},
                                                           ensure_ascii=False), encoding="utf-8")
        time.sleep(0.5)
    have = {f.stem for f in PAGES.glob("*.json") if json.loads(f.read_text(encoding="utf-8")).get("text")}
    extra = guess_more(sages, have)
    for slug, (asked, title, text) in extra.items():
        (PAGES / f"{slug}.json").write_text(json.dumps({"asked": asked, "title": title, "text": text, "guessed": True},
                                                       ensure_ascii=False), encoding="utf-8")
    print(f"{len(extra)} more pages found by name for the most quoted sages")
    # Canonical titles of every page an infobox links to, to match links to sages.
    links = set()
    for f in PAGES.glob("*.json"):
        info = infobox(json.loads(f.read_text(encoding="utf-8")).get("text") or "")
        for v in info.values():
            links.update(t for t, _ in wikilinks(v))
    canon_path = CACHE / "hewiki_canonical.json"
    canon = json.loads(canon_path.read_text(encoding="utf-8")) if canon_path.exists() else {}
    rest = sorted(links - set(canon))
    for i in range(0, len(rest), 50):
        res = query(rest[i:i + 50], content=False)
        canon.update({k: v[0] for k, v in res.items()})
        time.sleep(0.3)
    canon_path.write_text(json.dumps(canon, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(canon)} linked titles resolved")


def infobox(text):
    """{field: raw value} from the article's אישיות רבנית infobox (top-level fields only)."""
    m = re.search(r"\{\{\s*אישיות רבנית", text)
    if not m:
        return {}
    i, depth, body = m.end(), 1, []
    while i < len(text) and depth:
        if text.startswith("{{", i):
            depth += 1; body.append("{{"); i += 2; continue
        if text.startswith("}}", i):
            depth -= 1
            if depth:
                body.append("}}")
            i += 2; continue
        body.append(text[i]); i += 1
    body = "".join(body)
    # split on | at depth 0 (outside {{ }} and [[ ]])
    parts, cur, d = [], [], 0
    j = 0
    while j < len(body):
        two = body[j:j + 2]
        if two in ("{{", "[["):
            d += 1; cur.append(two); j += 2; continue
        if two in ("}}", "]]"):
            d -= 1; cur.append(two); j += 2; continue
        if body[j] == "|" and d == 0:
            parts.append("".join(cur)); cur = []; j += 1; continue
        cur.append(body[j]); j += 1
    parts.append("".join(cur))
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def drop_refs(v):
    v = re.sub(r"\{\{\s*הערה\|.*?\}\}", "", v, flags=re.S)
    return re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", v, flags=re.S)


def wikilinks(v):
    """[(target, shown)] for each [[link]] in a field value, references removed."""
    return [(a.strip(), (b or a).strip()) for a, b in re.findall(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]",
                                                                drop_refs(v))]


def items(v):
    """A field's entries: its links, plus plain names separated by commas or line breaks."""
    v = drop_refs(v)
    v = re.sub(r"\{\{ש\}\}|<br\s*/?>", ",", v)
    out = []
    for chunk in re.split(r",|\n|•", v):
        chunk = chunk.strip(" ;.")
        if not chunk:
            continue
        ls = wikilinks(chunk)
        if ls:
            out.extend(("link", t, shown, re.sub(r"\[\[.*?\]\]", "", chunk).strip(" ()")) for t, shown in ls)
        else:
            plain = re.sub(r"\{\{.*?\}\}|'''?|\(.*?\)", "", chunk).strip()
            if plain:
                out.append(("text", None, plain, ""))
    return out


def plain(v):
    v = drop_refs(v)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\{\{ש\}\}|<br\s*/?>", "; ", v)
    return re.sub(r"\{\{.*?\}\}|'''?", "", v).strip()


def year(v):
    """An approximate year from a date field: '132', 'בין שנת 132 לשנת 136' -> 132-136,
    'המאה ה-2' -> 100-199, 'לפנה"ס' makes it negative. None if nothing usable."""
    t = plain(v)
    neg = 'לפנה"ס' in t or "לפני הספירה" in t
    c = re.search(r"המאה ה-?(\d+)", t)
    if c:
        n = int(c.group(1))
        lo, hi = (n - 1) * 100, n * 100 - 1
        return [-hi, -lo] if neg else [lo, hi]
    ys = [int(x) for x in re.findall(r"(?<!\d)(\d{2,4})(?!\d)", t) if 1 <= int(x) <= 700]
    if not ys:
        return None
    ys = [-y for y in ys] if neg else ys
    return [min(ys), max(ys)]


def build():
    sages = json.loads((OUT / "sages.json").read_text(encoding="utf-8"))
    canon = json.loads((CACHE / "hewiki_canonical.json").read_text(encoding="utf-8"))
    # Wikipedia page -> sage, only where one sage owns the page
    page_of = {}
    for f in PAGES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("title"):
            page_of.setdefault(d["title"], []).append(f.stem)
    owner = {t: v[0] for t, v in page_of.items() if len(v) == 1}
    # Fallback for a linked page no sage owns: the link's title or shown name, read as a Hebrew
    # name that exactly one sage carries (with or without "רבי"/"רב").
    by_name = {}
    for slug, x in sages.items():
        for t in set(x["titles_he"]) | {x["he"]}:
            for n in {t, re.sub(r"^(?:רבי|רב|רבן) ", "", t)}:
                by_name.setdefault(n, set()).add(slug)
    def match(target, shown):
        s = owner.get(canon.get(target) or target)
        if s:
            return s
        for n in (canon.get(target), target, shown):
            if n:
                n = re.sub(r"\s*\(.*?\)", "", n).strip()
                if len(n.split()) < 3:      # "רבן גמליאל" fits several; full names only
                    continue
                hit = by_name.get(n, set())
                if len(hit) == 1:
                    return next(iter(hit))
        return None
    facts, unmatched = {}, {}
    for f in sorted(PAGES.glob("*.json")):
        slug = f.stem
        d = json.loads(f.read_text(encoding="utf-8"))
        info = infobox(d.get("text") or "")
        if not info:
            continue
        rec = {"wiki": d["title"]}
        for field, key in FIELDS.items():
            if field not in info:
                continue
            got = []
            for kind, target, shown, note in items(info[field]):
                s = match(target, shown) if kind == "link" else None
                if s == slug:
                    continue
                entry = {"slug": s} if s else {"name": strip_nikud(shown)}
                if note:
                    entry["note"] = note
                got.append(entry)
                if not s:
                    unmatched[shown] = unmatched.get(shown, 0) + 1
            if got:
                rec.setdefault(key, []).extend(got)
        for field, key in DATES.items():
            if info.get(field):
                rec[key] = plain(info[field])
                y = year(info[field])
                if y and key in ("born", "died"):
                    rec[key + "_year"] = y
        facts[slug] = rec
    (OUT / "wiki_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(facts)} sages with an infobox; wrote wiki_facts.json")
    report(sages, facts)
    top = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    print("most frequent names not matched to a sage:", ", ".join(f"{n} ({c})" for n, c in top))


def report(sages, facts):
    census = json.loads((OUT / "census_bavli.json").read_text(encoding="utf-8"))
    ranked = [k for k in census if sages[k]["kind"] in ("tanna", "amora", "zug")]
    tiers = {"tier 1 (top 60)": ranked[:60], "tier 2 (next 190)": ranked[60:250]}
    for name, slugs in tiers.items():
        n = len(slugs)
        def has(fn):
            return sum(1 for s in slugs if fn(s))
        sef_t = has(lambda s: sages[s]["teachers"])
        sef_s = has(lambda s: sages[s]["students"])
        wk = has(lambda s: s in facts)
        t = has(lambda s: sages[s]["teachers"] or facts.get(s, {}).get("teachers"))
        st = has(lambda s: sages[s]["students"] or facts.get(s, {}).get("students"))
        col = has(lambda s: facts.get(s, {}).get("colleagues"))
        fam = has(lambda s: any(facts.get(s, {}).get(k) for k in ("father", "children", "spouse", "in_laws",
                                                                    "sons_in_law", "siblings")))
        gen = has(lambda s: sages[s]["generation"] is not None)
        dates = has(lambda s: facts.get(s, {}).get("born_year") or facts.get(s, {}).get("died_year"))
        print(f"\n{name}: {n} sages, {wk} with a Wikipedia infobox")
        print(f"  teachers  {t:4} ({sef_t} from Sefaria alone)")
        print(f"  students  {st:4} ({sef_s} from Sefaria alone)")
        print(f"  colleagues {col:3}   family {fam:3}   generation {gen:3}   dates {dates:3}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"fetch": fetch, "build": build}.get(cmd, lambda: sys.exit(__doc__))()
