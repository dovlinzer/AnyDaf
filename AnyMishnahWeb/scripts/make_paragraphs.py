"""Add paragraph breaks to the mishnayot (fields "he_p" and "en_p" in data/bava_*.json): aligned lists, paragraph i of the Hebrew matches paragraph i of the English.
Guide: the divisions of the Be'eri/Kaufmann edition on Sefaria (public domain; blank lines between units) where it has them, plus judgement (a case with its ruling; a new case; a dispute).
Nothing is reworded: the paragraphs must join back to the original text exactly (checked). Run: python3 scripts/make_paragraphs.py   -> a DRAFT for the author's review."""
import json, os, re, sys, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
BE = "Mishnah based on the Kaufmann manuscript, edited by Dan Be'eri"
FILES = [(f"data/bava_kamma_{c}.json", "Mishnah_Bava_Kamma", c) for c in range(1, 7)] + [("data/bava_metzia_1.json", "Mishnah_Bava_Metzia", 1)]
norm = lambda s: re.sub(r"\s+", " ", s).strip()
SYS = ("You divide each mishnah into paragraphs for a study page, in Hebrew and in English together. Break only where the mishnah moves to a new case, a new ruling block, a new speaker or dispute, or a new topic: for example "
       "a case and its immediate ruling stay together; a following case or an added condition starts a new paragraph. Use the Be'eri/Kaufmann edition's divisions (blank lines) as a guide where it has them; you may add breaks it lacks, "
       "but do not add so many that a short mishnah is chopped: most mishnayot get 1 to 4 paragraphs; a one-sentence mishnah stays one paragraph. "
       "You may NOT change, reorder, add or remove any word, punctuation, tag or {{marker}}: each paragraph list must be an exact partition of the given text. Return the SAME number of Hebrew and English paragraphs, aligned in meaning. "
       "Return JSON: {\"items\": [{\"n\": number, \"he_p\": [..], \"en_p\": [..]}]}.")
TOOL = {"name": "out", "description": "paragraphs", "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}, "he_p": {"type": "array", "items": {"type": "string"}}, "en_p": {"type": "array", "items": {"type": "string"}}}, "required": ["n", "he_p", "en_p"]}}}, "required": ["items"]}}
def call(items):
    body = {"model": "claude-opus-4-5", "max_tokens": 16000, "system": SYS, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "out"}, "messages": [{"role": "user", "content": json.dumps(items, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600)); out = [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]["items"]
    if isinstance(out, str): out = json.JSONDecoder().raw_decode(out.strip())[0]
    return out
def beeri(book, ch):
    u = f"https://www.sefaria.org/api/v3/texts/{book}.{ch}?version=" + urllib.parse.quote("hebrew|" + BE)
    t = json.load(urllib.request.urlopen(u, timeout=60))["versions"][0]["text"]
    return [re.sub(r"<[^>]+>", "", x if isinstance(x, str) else " ".join(x)) for x in t]
for f, book, ch in FILES:
    d = json.load(open(f)); ms = d["mishnayot"]; be = beeri(book, ch)
    items = [{"n": m["n"], "hebrew": norm(re.sub(r"<[^>]+>", "", m["he"])), "english": m["en_smooth"], "beeri_units": [norm(x) for x in re.split(r"\n\s*\n", be[i]) if norm(x)]} for i, m in enumerate(ms)]
    for attempt in range(3):
        out = {o["n"]: o for o in call(items)}
        bad = []
        for m in ms:
            o = out.get(m["n"]); h0 = norm(re.sub(r"<[^>]+>", "", m["he"])); e0 = norm(m["en_smooth"])
            if not o or norm(" ".join(o["he_p"])) != h0 or norm(" ".join(o["en_p"])) != e0 or len(o["he_p"]) != len(o["en_p"]): bad.append(m["n"])
        if not bad: break
        items = [i for i in items if i["n"] in bad] if attempt < 2 else items
        print("  retry", bad)
    if bad: print("  FAILED validation for", bad); continue
    for m in ms: m["he_p"] = [norm(x) for x in out[m["n"]]["he_p"]]; m["en_p"] = [norm(x) for x in out[m["n"]]["en_p"]]
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=1); print(f, [len(m["he_p"]) for m in ms])
