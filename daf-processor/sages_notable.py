"""Notable passages for the sages kit: Sefaria's curated 'Notable Sources' for each sage, only those that are direct Bavli material.
Output: outline/sages/notable.json = {slug: [{title, ref, cite, en, he}]}, read by sages_kit.py.

For each sage (Sefaria topic = the kit's key): /api/v2/topics/<slug>?with_refs=1, the 'about' links that carry a curated title (descriptions.en.title) and
whose ref is a Bavli tractate, in Sefaria's own order (curatedPrimacy, highest first). The card title is Sefaria's; its summary is NOT used (author's rule).
The text is the William Davidson Edition (Koren; CC BY-NC 4.0, via Sefaria): English, and the vocalized Aramaic/Hebrew for the Hebrew pages, cut to an
excerpt ending in an ellipsis; the full passage is one click away on Sefaria. cite = the folio(s) without the line number ('Sanhedrin 86a', not 'Sanhedrin 86a:3').
Cached in outline/sages/cache/notable/. Run: venv/bin/python sages_notable.py [--refresh]"""
import json, re, sys, html, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(__file__).parent / "outline" / "sages"
CACHE = OUT / "cache" / "notable"; CACHE.mkdir(parents=True, exist_ok=True)
KIT = Path(__file__).parents[1] / "AnyMishnahWeb/reference-kit/sages/sages.json"
V_EN, V_HE = "William Davidson Edition - English", "William Davidson Edition - Vocalized Aramaic"
LIMIT_EN, LIMIT_HE = 480, 340
REFRESH = "--refresh" in sys.argv

def get(url, tries=4):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AnyDaf-sages/1.0"}), timeout=30))
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(1.5 * (i + 1))

def cached(name, fn):
    f = CACHE / (urllib.parse.quote(name, safe="") + ".json")
    if f.exists() and not REFRESH: return json.loads(f.read_text(encoding="utf-8"))
    v = fn(); f.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8"); return v

# the Bavli tractates, as the kit's census names them
# Sefaria's names for the 37 tractates of the Bavli (the census spells a few differently: Eiruvin, Hullin)
BAVLI = {t.replace("_", " ") for t in """Berakhot Shabbat Eruvin Pesachim Rosh_Hashanah Yoma Sukkah Beitzah Taanit Megillah Moed_Katan Chagigah Yevamot Ketubot Nedarim
Nazir Sotah Gittin Kiddushin Bava_Kamma Bava_Metzia Bava_Batra Sanhedrin Makkot Shevuot Avodah_Zarah Horayot Zevachim Menachot Chullin Bekhorot Arakhin Temurah
Keritot Meilah Tamid Niddah""".split()}
FOLIO = re.compile(r"^(.+?) (\d+[ab])\b")

def clean(t):
    t = re.sub(r'<sup class="footnote-marker">.*?</sup>\s*<i class="footnote">.*?</i>', "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace(" ", " ")
    t = re.sub(r"^\s*§\s*", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()

def flat(x):
    return [y for i in x for y in flat(i)] if isinstance(x, list) else [x]

def excerpt(t, limit):
    if len(t) <= limit: return t
    cut = t[:limit]
    m = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("׃ "))   # prefer a sentence end late in the window
    cut = cut[:m + 1] if m > limit * 0.6 else cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:-—") + "…"

def text(ref, version, lang):
    def fetch():
        u = "https://www.sefaria.org/api/texts/" + urllib.parse.quote(ref.replace(" ", "_"), safe="_:.-") + "?context=0&commentary=0&pad=0&" + ("vhe=" if lang == "he" else "ven=") + urllib.parse.quote(version)
        d = get(u)
        return " ".join(clean(s) for s in flat(d["he" if lang == "he" else "text"]) if isinstance(s, str) and s.strip())
    return cached(f"{ref}|{lang}", fetch)

def cite(ref):
    """'Sanhedrin 86a:3' -> 'Sanhedrin 86a'; 'Avodah Zarah 18a:14-18b:4' -> 'Avodah Zarah 18a–18b'."""
    m = FOLIO.match(ref)
    book, first = m.group(1), m.group(2)
    last = re.findall(r"(\d+[ab])", ref.split("-", 1)[1])[0] if "-" in ref and re.findall(r"(\d+[ab])", ref.split("-", 1)[1]) else first
    return f"{book} {first}" + (f"–{last}" if last != first else "")

def topic(slug):
    return cached("topic|" + slug, lambda: get(f"https://www.sefaria.org/api/v2/topics/{urllib.parse.quote(slug)}?with_refs=1&with_links=0"))

def one(slug):
    try: d = topic(slug)
    except Exception: return slug, []
    rows = []
    for x in (d.get("refs") or {}).get("about", {}).get("refs", []):
        de = ((x.get("descriptions") or {}).get("en") or {})
        m = FOLIO.match(x.get("ref", ""))
        if not de.get("title") or not m or m.group(1) not in BAVLI: continue
        rows.append(((x.get("order") or {}).get("curatedPrimacy", {}).get("en", 0), x["ref"], de["title"].strip()))
    out = []
    for _, ref, title in sorted(rows, reverse=True):
        try: en, he = text(ref, V_EN, "en"), text(ref, V_HE, "he")
        except Exception: continue
        if en: out.append({"title": title, "ref": ref, "cite": cite(ref), "en": excerpt(en, LIMIT_EN), "he": excerpt(he, LIMIT_HE)})
    return slug, out

if __name__ == "__main__":
    slugs = sorted(json.loads(KIT.read_text(encoding="utf-8"))["sages"])
    with ThreadPoolExecutor(6) as ex: res = dict(ex.map(one, slugs))
    res = {k: v for k, v in res.items() if v}
    (OUT / "notable.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(res), "sages,", sum(len(v) for v in res.values()), "passages")
