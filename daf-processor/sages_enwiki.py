#!/usr/bin/env python3
"""English Wikipedia as a second source for the sages' family relations (the Hebrew infobox reads miss
what is only in prose or only in the English article; the two Wikipedias are written separately).

    venv/bin/python sages_enwiki.py fetch    # Hebrew page -> English title (langlinks) -> wikitext, cached
    venv/bin/python sages_enwiki.py build    # -> outline/sages/enwiki_relations.json and enwiki_candidates.md

Only facts (who was whose father, son, wife, brother ...), never Wikipedia's wording (CC BY-SA).
Nothing is applied automatically: candidates go to the author, accepted ones into kit_overrides.json add_links."""
import json, re, sys, time, urllib.parse
from build_sages import CACHE, OUT, get
PAGES = CACHE / "hewiki_pages"; EN = CACHE / "enwiki_pages"; EN.mkdir(exist_ok=True)
API = "https://en.wikipedia.org/w/api.php"; HEAPI = "https://he.wikipedia.org/w/api.php"

def fetch():
    pages = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in PAGES.glob("*.json")}
    ll_path = CACHE / "he_to_en_titles.json"
    ll = json.loads(ll_path.read_text(encoding="utf-8")) if ll_path.exists() else {}
    titles = sorted({d["title"] for d in pages.values() if d.get("title")} - set(ll))
    for i in range(0, len(titles), 50):
        r = get(HEAPI, action="query", format="json", prop="langlinks", lllang="en", lllimit="500", redirects=1, titles="|".join(titles[i:i+50]))["query"]
        hop = {x["from"]: x["to"] for k in ("normalized", "redirects") for x in r.get(k, [])}
        got = {p["title"]: (p.get("langlinks") or [{}])[0].get("*") for p in r["pages"].values()}
        for t in titles[i:i+50]:
            c = t
            for _ in range(3): c = hop.get(c, c)
            ll[t] = got.get(c)
        time.sleep(0.3)
    ll_path.write_text(json.dumps(ll, ensure_ascii=False, indent=1), encoding="utf-8")
    ens = sorted({v for v in ll.values() if v})
    have = {f.stem for f in EN.glob("*.json")}
    todo = [e for e in ens if urllib.parse.quote(e, safe="") not in have]
    for i in range(0, len(todo), 50):
        r = get(API, action="query", format="json", redirects=1, prop="revisions", rvprop="content", rvslots="main", titles="|".join(todo[i:i+50]))["query"]
        for p in r["pages"].values():
            if "revisions" in p:
                (EN / (urllib.parse.quote(p["title"], safe="") + ".json")).write_text(json.dumps({"title": p["title"], "text": p["revisions"][0]["slots"]["main"]["*"]}, ensure_ascii=False), encoding="utf-8")
        hop = {x["from"]: x["to"] for k in ("normalized", "redirects") for x in r.get(k, [])}
        (CACHE / "en_redirects.json").write_text(json.dumps({**(json.loads((CACHE / "en_redirects.json").read_text()) if (CACHE / "en_redirects.json").exists() else {}), **hop}, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.3)
    print(len(titles), "Hebrew titles asked,", len(ens), "English pages,", len(list(EN.glob('*.json'))), "cached")

KIT = OUT.parents[2] / "AnyMishnahWeb/reference-kit/sages/sages.json"
# (pattern before the link) -> what the LINKED person is to the page's sage
EN_WORDS = [(r"(?:son|grandson|great-grandson|descendant) of", "parent_of_me"), (r"(?:daughter|granddaughter) of", "parent_of_me"),
            (r"(?:his|her) (?:father|grandfather|great-grandfather|great-great-grandfather|ancestor)(?: was| is|,)?", "parent_of_me"),
            (r"(?:father|grandfather|great-grandfather) of", "child_of_me"), (r"(?:his|her) (?:sons?|grandsons?|daughters?|children|grandchildren|descendants?)(?: were| was| included|,| are)?(?: [A-Za-z ,]{0,20})?", "child_of_me"),
            (r"(?:brother|sister) of", "sibling"), (r"(?:his|her) (?:brothers?|sisters?)", "sibling"), (r"(?:married|wife of|husband of|his wife|her husband|wed)", "spouse"),
            (r"(?:son-in-law|father-in-law) of", "inlaw"), (r"(?:his|her) (?:son-in-law|father-in-law|sons-in-law)", "inlaw")]
LINK = r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]"

def build():
    kit = json.loads(KIT.read_text(encoding="utf-8"))["sages"]
    ll = json.loads((CACHE / "he_to_en_titles.json").read_text(encoding="utf-8"))
    red = json.loads((CACHE / "en_redirects.json").read_text(encoding="utf-8")) if (CACHE / "en_redirects.json").exists() else {}
    page_of = {}
    for f in PAGES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("title"): page_of.setdefault(d["title"], []).append(f.stem)
    en_to_slug = {}
    for he, en in ll.items():
        if en and len(page_of.get(he, [])) == 1: en_to_slug[en] = page_of[he][0]
    def to_slug(target):
        t = target.strip().replace("_", " ")
        for c in (t, red.get(t), t[:1].upper() + t[1:]):
            if c in en_to_slug: return en_to_slug[c]
        return None
    have = {}
    for k, x in kit.items():
        for v in (x.get("links") or {}).values():
            for l in v:
                if l.get("id"): have.setdefault(k, set()).add(l["id"]); have.setdefault(l["id"], set()).add(k)
    rel_name = {"parent_of_me": "father/ancestor", "child_of_me": "child/descendant", "sibling": "sibling", "spouse": "spouse", "inlaw": "in-law"}
    out, seen = [], set()
    for f in sorted(EN.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8")); title, text = d["title"], d["text"]
        me = to_slug(title)
        if not me or me not in kit: continue
        t = re.sub(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
        t = re.sub(r"\{\{[Ss]fn[^}]*\}\}|\{\{[Ee]fn[^}]*\}\}", "", t)
        sentences = re.split(r"(?<=[.!?])\s+|\n", t)
        for sent in sentences:
            for pat, rel in EN_WORDS:
                for m in re.finditer(pat + r"[^\[\n]{0,20}?" + LINK, sent, flags=re.I):
                    b = to_slug(m.group(1))
                    if not b or b == me or b in have.get(me, set()): continue
                    key = (me, rel, b)
                    if key in seen: continue
                    seen.add(key)
                    out.append((me, rel, b, re.sub(r"\s+", " ", sent[max(0, m.start() - 60):m.end() + 70])))
        # infobox fields
        for fld, rel in (("parents", "parent_of_me"), ("father", "parent_of_me"), ("children", "child_of_me"), ("spouse", "spouse"), ("relatives", "relative"), ("siblings", "sibling")):
            for m in re.finditer(r"\|\s*" + fld + r"\s*=([^\n]*(?:\n(?!\|)[^\n]*)*)", t):
                for lm in re.finditer(LINK, m.group(1)):
                    b = to_slug(lm.group(1))
                    if not b or b == me or b in have.get(me, set()) or (me, rel, b) in seen: continue
                    seen.add((me, rel, b)); out.append((me, rel, b, "infobox: " + fld))
    lines = ["# Family relations in ENGLISH Wikipedia that the data lacks (candidates, unverified)\n", f"{len(out)} candidates; check each, then add accepted ones to kit_overrides.json add_links.\n"]
    for me, rel, b, ctx in out:
        lines.append(f"- **{kit[me]['en']}** ←{rel_name.get(rel, rel)}→ **{kit[b]['en']}**  (`{me}` / `{b}`)  …{ctx}…")
    (OUT / "enwiki_candidates.md").write_text("\n".join(lines), encoding="utf-8")
    json.dump(out, open(OUT / "enwiki_relations.json", "w"), ensure_ascii=False, indent=1)
    print(len(out), "candidates ->", OUT / "enwiki_candidates.md")

if __name__ == "__main__":
    {"fetch": fetch, "build": build}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
