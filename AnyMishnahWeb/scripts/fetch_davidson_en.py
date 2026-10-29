"""Replace the English translation in data/bava_*.json with the William Davidson Edition (Koren/Steinsaltz, CC-BY-NC) from Sefaria,
keeping its <b> (the mishnah's own words) and <i> markup, and drop Kulp's text and commentary. Run: python3 scripts/fetch_davidson_en.py"""
import json, urllib.request, urllib.parse, re
VER = "William Davidson Edition - English"
FILES = [(f"data/bava_kamma_{c}.json", "Mishnah_Bava_Kamma", c) for c in range(1, 7)] + [("data/bava_metzia_1.json", "Mishnah_Bava_Metzia", 1)]
for path, book, ch in FILES:
    d = json.load(open(path))
    u = f"https://www.sefaria.org/api/v3/texts/{book}.{ch}?version=" + urllib.parse.quote("english|" + VER)
    t = json.load(urllib.request.urlopen(u, timeout=60))["versions"][0]["text"]
    ms = d["mishnayot"]
    print(path, "mishnayot", len(ms), "davidson segments", len(t))
    assert len(t) == len(ms), (path, len(t), len(ms))
    for m, en in zip(ms, t):
        en = en if isinstance(en, str) else " ".join(en)
        en = en.replace("an ox that was an imbecile", "an ox that was a <i>shoteh</i> (disoriented)").replace("an imbecile", "a person with psychosis").replace("the imbecile", "the person with psychosis")   # author rule 2026-10-28: shoteh = a person with psychosis
        m["en"] = re.sub(r"\s+", " ", en).strip(); m.pop("kulp", None)
    d.setdefault("translation", VER)
    json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
