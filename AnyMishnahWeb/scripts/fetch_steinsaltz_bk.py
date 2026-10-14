"""Steinsaltz's Hebrew explanation (biur) of each mishnah of Bava Kamma 1-3, from Sefaria ('Steinsaltz on Bava Kamma', William Davidson Edition - Hebrew, CC-BY-NC)
-> data/steinsaltz/bk_N_biur.json {mishnah n: [segment html]}. Shown under the Hebrew mishnah on the Hebrew pages, credited to Rabbi Adin Even-Israel Steinsaltz.
The Gemara quotes each mishnah in pieces; Steinsaltz marks a piece '<big>א משנה</big>' and the Gemara that follows '<big>ב גמרא</big>'. We take every piece (from its marker to the next marker),
and assign it to a mishnah of ours by the overlap of its bold words (the mishnah's own text) with the Romm Hebrew. Bold = the mishnah's words, plain = Steinsaltz's explanation.
Run: python3 scripts/fetch_steinsaltz_bk.py   (uses data/steinsaltz/bk_raw.json if present)"""
import json, os, re, time, urllib.request
RAW = "data/steinsaltz/bk_raw.json"
def g(u):
    for _ in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "AnyMishnahWeb/0.1"}), timeout=60))
        except Exception: time.sleep(1)
if not os.path.exists(RAW):
    raw = {}
    for d in range(2, 60):
        for s in "ab":
            r = g(f"https://www.sefaria.org/api/texts/Steinsaltz_on_Bava_Kamma.{d}{s}?context=0&commentary=0")
            if r and r.get("he"): raw[f"{d}{s}"] = r["he"]
    json.dump(raw, open(RAW, "w"), ensure_ascii=False)
raw = json.load(open(RAW))
def norm(s):
    s = re.sub(r"<[^>]+>", " ", s); s = re.sub(r"[֑-ׇ]", "", s); return re.sub(r"[^א-ת ]", " ", s).split()
M = {(c, m["n"]): set(norm(m["he"])) for c in (1, 2, 3) for m in json.load(open(f"data/bava_kamma_{c}.json"))["mishnayot"]}
def clean(s):
    s = re.sub(r"<big>.*?</big>", "", s); s = re.sub(r"</?small>", "", s); s = re.sub(r"<(?!/?b>)[^>]+>", "", s); return s.strip()
out = {1: {}, 2: {}, 3: {}}
for ref, segs in raw.items():
    if int(ref[:-1]) >= 36: continue
    for i, s in enumerate(segs):
        if not (isinstance(s, str) and "משנה</big>" in s): continue
        toks = norm(" ".join(re.findall(r"<b>(.*?)</b>", s, flags=re.S)))
        if not toks: continue
        best = max(M, key=lambda k: len(set(toks) & M[k]) / len(set(toks)))
        if len(set(toks) & M[best]) / len(set(toks)) <= 0.6: continue
        piece = [clean(s)]
        for t in segs[i + 1:]:
            if not isinstance(t, str) or "גמרא</big>" in t or "משנה</big>" in t: break
            piece.append(clean(t))
        out[best[0]].setdefault(best[1], []).append({"ref": ref, "segs": [p for p in piece if p]})
for c in out:
    json.dump(out[c], open(f"data/steinsaltz/bk_{c}_biur.json", "w"), ensure_ascii=False, indent=1)
    print(c, {n: [len(p["segs"]) for p in v] for n, v in sorted(out[c].items())})
