"""Fetch one chapter of Mishnah from Sefaria: Hebrew (Romm Vilna), Kulp's Mishnah Yomit
translation (CC-BY) and Kulp's explanation (CC-BY). Usage: fetch_sefaria.py Berakhot 1"""
import json, sys, urllib.parse, urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AnyMishnahWeb/0.1"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def main(tractate, chapter):
    base = "https://www.sefaria.org/api/texts/"
    ref = f"Mishnah_{tractate}.{chapter}"
    he = get(base + ref + "?context=0&commentary=0&vhe=" + urllib.parse.quote("Mishnah, ed. Romm, Vilna 1913"))
    en = get(base + ref + "?context=0&commentary=0&ven=" + urllib.parse.quote("Mishnah Yomit by Dr. Joshua Kulp"))
    out = {"tractate": tractate, "chapter": int(chapter), "mishnayot": []}
    for i, (h, e) in enumerate(zip(he["he"], en["text"]), 1):
        k = get(f"{base}English_Explanation_of_Mishnah_{tractate}.{chapter}.{i}?context=0")
        out["mishnayot"].append({"n": i, "he": h, "en": e,
                                 "kulp": k.get("text") if k.get("versionTitle") else None})
    return out

if __name__ == "__main__":
    t, c = sys.argv[1], sys.argv[2]
    d = main(t, c)
    path = f"data/{t.lower()}_{c}.json"
    json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
    for m in d["mishnayot"]:
        print(m["n"], len(m["he"]), len(m["en"]), type(m["kulp"]).__name__)
