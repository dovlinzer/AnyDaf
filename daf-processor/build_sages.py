#!/usr/bin/env python3
"""Sages panel pilot: who's who data for the tanna'im and amora'im, and who appears on each daf.
No Anthropic API calls.

    venv/bin/python build_sages.py fetch               # cache Sefaria people topics + Hebrew Wikipedia categories
    venv/bin/python build_sages.py build               # merge into outline/sages/sages.json
    venv/bin/python build_sages.py mentions KEY ...    # sages named on each daf -> outline/sages/mentions/<key>.json

Sources:
- Sefaria topics (the 925 members of "talmudic-people"): names in Hebrew and English, generation
  code (T1-T6 tanna'im, A1-A8 amora'im, etc.), learned-from / taught links, a short bio, wiki links.
  Sefaria has no region field.
- Hebrew Wikipedia's category tree (אמוראי ארץ ישראל / אמוראי בבל / תנאים, split by generation):
  region and generation, joined to Sefaria through Sefaria's own heWikiLink.
- Our authorities_taxonomy.json (Glida table + Hebrew Wikipedia) as a fallback for region.

Mentions are local name matching on the saved daf text (daf_text/), with nikud stripped. A name
that fits more than one sage (Rabbi Elazar the tanna vs the amora, Rabba / Rava) is listed with
all its candidates and marked ambiguous: in production the outline pass will resolve those.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "outline" / "sages"
CACHE = OUT / "cache"
DAF_TEXT = HERE / "daf_text"
TAXONOMY = HERE / "topic_analysis" / "taxonomy" / "authorities_taxonomy.json"
SEFARIA = "https://www.sefaria.org/api/topics/"
HEWIKI = "https://he.wikipedia.org/w/api.php"
UA = {"User-Agent": "AnyDaf study-aids research (dlinzer@yctorah.org)"}
WIKI_ROOTS = {"אמוראי ארץ ישראל": ("amora", "Eretz Yisrael"),
              "אמוראי בבל": ("amora", "Bavel"),
              "תנאים": ("tanna", None)}
HEB_ORDINAL = {"הראשון": 1, "השני": 2, "השלישי": 3, "הרביעי": 4, "החמישי": 5, "השישי": 6,
               "השביעי": 7, "השמיני": 8}


def get(url, **params):
    for attempt in range(6):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2 * 2 ** attempt)
    raise RuntimeError(f"failed: {url}")


# ---------- fetch ----------

def fetch():
    (CACHE / "sefaria").mkdir(parents=True, exist_ok=True)
    # Two overlapping lists: "talmudic-people" (925, mostly lesser figures) and the curated
    # "talmudic-figures" (260, the major sages); then everyone they name as a teacher, student
    # or colleague, until no new names turn up.
    people = get(SEFARIA + "talmudic-people", with_links=1)["links"]["is-category-of"]["links"]
    figures = get(SEFARIA + "talmudic-figures", with_links=1)["links"]["displays-above"]["links"]
    slugs = {l["topic"] for l in people + figures}

    def one(slug):
        d = get(SEFARIA + urllib.parse.quote(slug), with_links=1)
        if d:
            (CACHE / "sefaria" / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    while True:
        todo = sorted(s for s in slugs if not (CACHE / "sefaria" / f"{s}.json").exists())
        print(f"Sefaria: {len(slugs)} people, {len(todo)} to fetch")
        with ThreadPoolExecutor(4) as ex:
            for i, _ in enumerate(ex.map(one, todo), 1):
                if i % 100 == 0:
                    print(f"  {i}/{len(todo)}")
        linked = set()
        for s in slugs:
            p = CACHE / "sefaria" / f"{s}.json"
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                for kind in ("learned-from", "taught", "corresponded-with"):
                    linked.update(link_slugs(d, kind))
        if linked <= slugs:
            break
        slugs |= linked
    (CACHE / "sefaria_slugs.json").write_text(json.dumps(sorted(slugs)), encoding="utf-8")

    # Hebrew Wikipedia: walk each root category, recording the subcategory each page sits in.
    pages = {}
    for root_cat, (kind, region) in WIKI_ROOTS.items():
        stack, seen = [(root_cat, None)], set()
        while stack:
            cat, gen_cat = stack.pop()
            if cat in seen:
                continue
            seen.add(cat)
            cont = {}
            while True:
                d = get(HEWIKI, action="query", list="categorymembers", cmtitle="קטגוריה:" + cat,
                        cmlimit=500, format="json", **cont)
                for m in d["query"]["categorymembers"]:
                    t = m["title"]
                    if t.startswith("קטגוריה:"):
                        sub = t.split(":", 1)[1]
                        if "דור" in sub or len(seen) < 3:
                            stack.append((sub, sub if "דור" in sub else gen_cat))
                    elif m["ns"] == 0:
                        pages.setdefault(t, []).append({"root": root_cat, "cat": gen_cat or cat})
                if "continue" not in d:
                    break
                cont = {"cmcontinue": d["continue"]["cmcontinue"]}
        print(f"Hebrew Wikipedia {root_cat}: {len(seen)} categories")
    (CACHE / "hewiki.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Hebrew Wikipedia: {len(pages)} pages")


# ---------- build ----------

def strip_nikud(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not ("֑" <= c <= "ׇ" and c not in "־׃"))
    return s.replace("־", " ")


def wiki_title(url):
    if not url or "wikipedia.org/wiki/" not in url:
        return None
    return urllib.parse.unquote(url.split("/wiki/", 1)[1]).replace("_", " ")


def wiki_facts(entries):
    """(kind, region, generation) from the Hebrew Wikipedia categories a page sits in."""
    kind = gen = None
    regions = []
    for e in entries:
        k, reg = WIKI_ROOTS[e["root"]]
        kind = kind or k
        if reg and reg not in regions:
            regions.append(reg)
        m = re.search(r"הדור (\S+)", e["cat"])
        if m and m.group(1) in HEB_ORDINAL:
            gen = gen or HEB_ORDINAL[m.group(1)]
        elif "המעבר" in e["cat"]:
            gen = gen or 0
    # An amora in both lists moved between them (R. Zeira, Ulla...): "Bavel / Eretz Yisrael".
    return kind, " / ".join(regions) or None, gen


def sefaria_gen(code):
    """'A2' -> ('amora', 2); 'T4' -> ('tanna', 4); 'A3/A4' -> ('amora', 3); 'TA' (between the
    tanna'im and amora'im) -> ('tanna', 6); 'Z3' (zugot) -> ('zug', 3); anything else -> (None, None)."""
    code = (code or "").split("/")[0]
    if code == "TA":
        return "tanna", 6
    m = re.fullmatch(r"([TAZ])(\d)", code)
    if not m:
        return None, None
    return {"T": "tanna", "A": "amora", "Z": "zug"}[m.group(1)], int(m.group(2))


def taxonomy_regions():
    """Hebrew name (no nikud) -> region, from our own authorities table."""
    items = list(json.loads(TAXONOMY.read_text(encoding="utf-8")).values())[0]
    out = {}
    for i in items:
        notes = i.get("notes") or ""
        region = ("Bavel" if "Babylon" in notes else "Eretz Yisrael" if "Eretz Yisrael" in notes else None)
        if i.get("parent_id") and region:
            for n in [i.get("hebrew") or ""] + [a for a in i.get("aliases", []) if re.search("[א-ת]", a)]:
                out[strip_nikud(n).strip()] = region
    return out


def link_slugs(d, kind):
    return [l["topic"] for l in d.get("links", {}).get(kind, {}).get("links", [])]


def build():
    slugs = json.loads((CACHE / "sefaria_slugs.json").read_text())
    wiki = json.loads((CACHE / "hewiki.json").read_text(encoding="utf-8"))
    tax = taxonomy_regions()
    sages, stats = {}, {"wiki_region": 0, "tax_region": 0, "no_region": 0, "wiki_by_name": 0}
    he_owners = {}
    for slug in slugs:
        p = CACHE / "sefaria" / f"{slug}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            for t in {strip_nikud(t["text"]).strip() for t in d.get("titles", []) if t.get("lang") == "he"}:
                he_owners[t] = he_owners.get(t, 0) + 1
    for slug in slugs:
        p = CACHE / "sefaria" / f"{slug}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        props = d.get("properties") or {}
        code = (props.get("generation") or {}).get("value")
        kind, gen = sefaria_gen(code)
        he = (d.get("primaryTitle") or {}).get("he") or d.get("he") or ""
        titles_he = sorted({strip_nikud(t["text"]).strip() for t in d.get("titles", []) if t.get("lang") == "he"})
        wt = wiki_title((props.get("heWikiLink") or {}).get("value"))
        if not wt:
            # No link from Sefaria: take a Wikipedia page whose title is one of the sage's Hebrew
            # names, but only a name that no other Sefaria person also carries.
            wt = next((t for t in titles_he if t in wiki and he_owners.get(t) == 1), None)
            stats["wiki_by_name"] += bool(wt)
        wkind, region, wgen = wiki_facts(wiki.get(wt, [])) if wt else (None, None, None)
        titles_en = sorted({t["text"] for t in d.get("titles", []) if t.get("lang") == "en"})
        kind = kind or wkind
        if kind == "tanna" and not region:
            region = "Eretz Yisrael"      # the default for tanna'im; Wikipedia marks the exceptions
        if region:
            stats["wiki_region"] += 1
        else:
            region = next((tax[t] for t in titles_he if t in tax), None)
            stats["tax_region" if region else "no_region"] += 1
        sages[slug] = {
            "slug": slug,
            "en": (d.get("primaryTitle") or {}).get("en") or d.get("en"),
            "he": strip_nikud(he),
            "titles_he": titles_he, "titles_en": titles_en,
            "kind": kind,                 # tanna | amora | None (biblical, zugot, others)
            "generation": gen if gen is not None else wgen,
            "generation_code": code,
            "region": region,
            "teachers": link_slugs(d, "learned-from"),
            "students": link_slugs(d, "taught"),
            "colleagues": link_slugs(d, "corresponded-with"),
            "bio": ((d.get("description") or {}).get("en") or "").strip(),
            "num_sources": d.get("numSources") or 0,
            "links": {k: (props.get(k) or {}).get("value") for k in ("enWikiLink", "heWikiLink", "jeLink")
                      if (props.get(k) or {}).get("value")},
        }
    ov = json.loads((OUT / "overrides.json").read_text(encoding="utf-8"))
    for slug, facts in ov.items():
        if slug in sages:
            sages[slug].update(facts)
            sages[slug]["override"] = sorted(facts)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sages.json").write_text(json.dumps(sages, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for s in sages.values():
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"{len(sages)} sages -> {(OUT / 'sages.json').relative_to(HERE)}  kinds {kinds}  region {stats}")


# ---------- mentions ----------

# Names are matched only in these shapes: a title + name ("רבי יוחנן", "רב הונא", "רבן גמליאל",
# "מר זוטרא", "בר קפרא", "ריש לקיש"), or one of the one-word names below. "רב" and "לוי" are also
# ordinary words, so they count only right after "אמר" and its forms.
TITLES = ("רבי ", "רב ", "רבן ", "מר ", "בר ", "בן ", "ריש ", "אבא ", "רבה ", "רבא ", "איסי ")
ONE_WORD = {"אביי", "רבא", "רבה", "עולא", "רבינא", "זעירי", "חזקיה", "שמואל", "אמימר", "רבין", "אבימי",
            "רמי בר חמא"}
AFTER_AMAR = {"רב", "לוי"}
FIXED = {"רבא": "rava", "אביי": "abaye", "רב": "rav", "שמואל": "shmuel-(amora)", "עולא": "ulla"}
AMAR = r"(?:אמר|ואמר|דאמר|כדאמר|אמרי|מתקיף לה|משמיה ד)\s"


def name_index(sages):
    """Hebrew name -> slugs of every Sefaria person carrying it."""
    idx = {}
    for s in sages.values():
        for t in s["titles_he"]:
            t = re.sub(r"\s*\(.*?\)", "", t).replace("'", "").strip()
            t = re.sub(r"^ר ", "רבי ", t)
            if (t.startswith(TITLES) and " " in t) or t in ONE_WORD or t in AFTER_AMAR:
                idx.setdefault(t, set()).add(s["slug"])
    # One-word names that mean one sage in the Bavli, whatever else carries them as an alias
    # (Sefaria lists "רבא" among Rabbi Abba's names).
    for name, slug in FIXED.items():
        if slug in sages:
            idx[name] = {slug}
    return {k: sorted(v) for k, v in idx.items()}


def label_key(label):
    """'11b.4' -> (11, 'b', 4), for sorting line labels in text order."""
    m = re.match(r"(\d+)([ab])\.(\d+)", label)
    return (int(m.group(1)), m.group(2), int(m.group(3)))


def era(s):
    """One timeline for tanna'im and amora'im: T1-T6 -> 1-6, A1-A8 -> 7-14, zugot before both."""
    g = s.get("generation")
    if g is None:
        return None
    return {"zug": -5 + g, "tanna": g, "amora": 6 + g}.get(s.get("kind"))


def outline_span(key):
    """(first, last) line label the daf's outline covers, or None if it has no line anchors."""
    r = HERE / "outline" / "results" / key
    # effort-test outlines (04_outline_opus55_medium/high) share one computed scope
    for p in (r / "04_outline_opus55.json", r / "04_outline_opus55_medium.json", r / "04_outline_opus55_high.json",
              HERE / "outline" / f"example_{key}.json"):
        if p.exists():
            labels = []
            def walk(ns):
                for n in ns or []:
                    t = n.get("text") or {}
                    labels.extend(x for x in (t.get("from"), t.get("to")) if x)
                    walk(n.get("children"))
            walk(json.loads(p.read_text(encoding="utf-8")).get("sections"))
            if labels:
                return min(labels, key=label_key), max(labels, key=label_key)
    return None


def load_daf(key):
    """The lines the daf's outline covers: an outline often starts on the previous amud or runs
    into the next (Chagigah 6 opens on 5b). Without anchors, the daf's own two amudim."""
    from upload_to_supabase import parse_dir_name
    tractate, daf = parse_dir_name(key)
    book = json.loads((DAF_TEXT / f"{tractate}.json").read_text(encoding="utf-8"))["amudim"]
    n = int(daf)
    segs = []
    for amud in (f"{n - 1}b", f"{n}a", f"{n}b", f"{n + 1}a"):
        for s in (book.get(amud) or {}).get("segments", []):
            segs.append((f"{amud}.{s['n']}", s["he"], s.get("en", "")))
    span = outline_span(key)
    if span:
        lo, hi = label_key(span[0]), label_key(span[1])
        return tractate, [x for x in segs if lo <= label_key(x[0]) <= hi]
    return tractate, [x for x in segs if x[0].split(".")[0] in (f"{n}a", f"{n}b")]


_MATCHER = None


def matcher():
    """(sages, name index, compiled pattern), built once."""
    global _MATCHER
    if _MATCHER is None:
        sages = json.loads((OUT / "sages.json").read_text(encoding="utf-8"))
        idx = name_index(sages)
        names = sorted((n for n in idx if n not in AFTER_AMAR), key=len, reverse=True)   # longest first
        pat = re.compile(r"(?<![א-ת])(?:ו|ד|כ|ל|ש|וד|דל|וכ)?(" + "|".join(map(re.escape, names)) + r")(?![א-ת])"
                         r"|(?<![א-ת])" + AMAR + r"(" + "|".join(AFTER_AMAR) + r")(?![א-ת])")
        _MATCHER = (sages, idx, pat)
    return _MATCHER


def find_names(segs):
    """Sage names in [(label, he, en)], in text order, each with its candidates and a guess."""
    sages, idx, pat = matcher()
    found = {}
    for label, he, _en in segs:
        text = re.sub(r"[^\sא-ת״׳\"']", " ", strip_nikud(he))
        text = re.sub(r"\s+", " ", text)
        for m in pat.finditer(text):
            name = m.group(1) or m.group(2)
            f = found.setdefault(name, {"name": name, "candidates": idx[name], "lines": []})
            if label not in f["lines"]:
                f["lines"].append(label)
    # Ambiguous names: pick the candidate whose era sits closest to the unambiguous sages
    # named on the same or nearby lines (Rabbi Elazar among amora'im is R. Elazar b. Pedat).
    # A cheap guess, used only when the outline didn't name its sages itself.
    pos = {label: i for i, (label, _, _) in enumerate(segs)}
    # A baraita quoted amid amora'im still names tanna'im, so when every candidate is a
    # tanna (or every one an amora), only sages of that kind count as context.
    known = [(pos[l], era(sages[f["candidates"][0]]), sages[f["candidates"][0]]["kind"])
             for f in found.values() if len(f["candidates"]) == 1
             for l in f["lines"] if era(sages[f["candidates"][0]]) is not None]
    rows = []
    for f in found.values():
        cands = f["candidates"]
        pick, how = cands[0], "only"
        if len(cands) > 1:
            kinds = {sages[c]["kind"] for c in cands} & {"tanna", "amora"}
            pool = [k for k in known if len(kinds) != 1 or k[2] in kinds]
            near = ([e for i, e, _ in pool if any(abs(i - pos[l]) <= 2 for l in f["lines"])]
                    or [e for _, e, _ in pool])
            mid = sorted(near)[len(near) // 2] if near else None
            def score(c):
                x = sages[c]
                dist = abs(era(x) - mid) if mid is not None and era(x) is not None else 99
                return (x["kind"] not in ("tanna", "amora"), dist, -x["num_sources"])
            pick = min(cands, key=score)
            how = "context" if mid is not None and era(sages[pick]) is not None else "most cited"
        rows.append({**f, "count": len(f["lines"]), "first": f["lines"][0],
                     "ambiguous": len(cands) > 1, "pick": pick, "pick_by": how})
    rows.sort(key=lambda r: label_key(r["first"]))
    return rows


def segs_between(tractate, start, end):
    """[(label, he, en)] for the lines start..end of a tractate's saved text (they may span amudim)."""
    book = json.loads((DAF_TEXT / f"{tractate}.json").read_text(encoding="utf-8"))["amudim"]
    lo, hi = label_key(start), label_key(end)
    out = []
    for amud, a in book.items():
        m = re.match(r"(\d+)([ab])$", amud)
        if not m or not ((lo[0], lo[1]) <= (int(m.group(1)), m.group(2)) <= (hi[0], hi[1])):
            continue
        for s in a.get("segments", []):
            lab = f"{amud}.{s['n']}"
            if lo <= label_key(lab) <= hi:
                out.append((lab, s["he"], s.get("en", "")))
    return sorted(out, key=lambda x: label_key(x[0]))


def describe(slug):
    """'R. Elazar b. Pedat (amora, A3, Eretz Yisrael)' for a prompt's candidate list."""
    x = matcher()[0][slug]
    facts = [f for f in (x["kind"], x.get("generation_code"), x.get("region")) if f]
    return f"{x['en']}" + (f" ({', '.join(facts)})" if facts else "")


def _fold(name):
    n = name.lower().replace("rabbi ", "r. ").replace("rebbi ", "r. ").replace(" ben ", " b. ").replace(" bar ", " b. ")
    return re.sub(r"[^a-z. ]", "", n.replace("ch", "h")).strip()


def resolve(sage):
    """The sages.json slug for an outline's sage entry: its own id if valid, else its full name
    matched against every sage's English names. None if nothing matches uniquely."""
    sages = matcher()[0]
    if sage.get("id") in sages:
        return sage["id"]
    want = _fold(sage.get("full_name") or sage.get("name") or "")
    hits = {k for k, v in sages.items() if any(_fold(t) == want for t in set(v["titles_en"]) | {v["en"]})}
    return hits.pop() if len(hits) == 1 else None


def mentions(keys):
    (OUT / "mentions").mkdir(parents=True, exist_ok=True)
    for key in keys:
        tractate, segs = load_daf(key)
        rows = find_names(segs)
        out = {"key": key, "tractate": tractate, "sages": rows}
        (OUT / "mentions" / f"{key}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        amb = sum(r["ambiguous"] for r in rows)
        print(f"  {key}: {len(rows)} names, {amb} ambiguous")


# ---------- panel payload ----------

def outline_rows(key, outline):
    """Panel rows from the outline's own `sages` list (the model named each sage), with the
    Gemara lines where local matching finds the chosen sage's name."""
    tractate, segs = load_daf(key)
    found = find_names(segs)
    rows = []
    for g in outline["sages"]:
        slug = resolve(g)
        if not slug:
            continue
        lines = sorted({l for r in found if slug in r["candidates"] for l in r["lines"]}, key=label_key)
        rows.append({"name": g.get("hebrew") or matcher()[0][slug]["he"], "candidates": [slug], "lines": lines,
                     "ambiguous": False, "pick": slug, "sections": g.get("sections") or [],
                     "outline_name": g.get("name")})
    return rows


def panel(key, outline=None):
    """The sages list for one daf, shaped for the web page. Uses the outline's own `sages` when it
    has them; otherwise the name-matching guesses from `mentions` (None if those weren't run)."""
    sages = matcher()[0]
    if outline and outline.get("sages") is not None:
        rows = outline_rows(key, outline)
    else:
        mp = OUT / "mentions" / f"{key}.json"
        if not mp.exists():
            return None
        rows = json.loads(mp.read_text(encoding="utf-8"))["sages"]
    here = {r["pick"] for r in rows}
    people = lambda slugs: [{"id": x, "en": sages[x]["en"], "here": x in here} for x in slugs if x in sages]
    out, seen = [], {}
    for r in rows:
        x = sages[r["pick"]]
        if r["pick"] in seen:                     # two spellings of one sage: merge their lines
            prev = out[seen[r["pick"]]]
            prev["lines"] = sorted(set(prev["lines"]) | set(r["lines"]), key=label_key)
            prev["he"] = prev["he"] if len(prev["he"]) >= len(r["name"]) else r["name"]
            prev["sections"] = list(dict.fromkeys(prev["sections"] + r.get("sections", [])))
            continue
        seen[r["pick"]] = len(out)
        out.append({
            "id": r["pick"], "en": x["en"], "he": r["name"], "kind": x["kind"], "gen": x["generation"],
            "region": x["region"], "lines": r["lines"], "bio": x["bio"],
            "url": "https://www.sefaria.org/topics/" + urllib.parse.quote(r["pick"]),
            "wiki": x["links"].get("enWikiLink") or x["links"].get("heWikiLink"),
            "teachers": people(x["teachers"]), "students": people(x["students"]),
            "colleagues": people(x["colleagues"]),
            # English spellings, for highlighting the sage in the outline (the page folds
            # spelling differences: R./Rabbi, ch/h, Yose/Yosei/Yossi, a final h)
            "aliases": sorted(set(x["titles_en"]) | {x["en"]} | ({r["outline_name"]} if r.get("outline_name") else set())),
            "sections": r.get("sections", []),
            "guess": r["ambiguous"],
            "alts": [sages[c]["en"] for c in r["candidates"] if c != r["pick"]],
            "unchecked": x.get("override", []),
        })
    return out


if __name__ == "__main__":
    cmd, rest = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "fetch":
        fetch()
    elif cmd == "build":
        build()
    elif cmd == "mentions":
        mentions(rest)
    else:
        sys.exit(__doc__)
