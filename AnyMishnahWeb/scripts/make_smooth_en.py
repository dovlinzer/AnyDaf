"""Write a SMOOTH English rendering of each mishnah (field "en_smooth" in data/bava_*.json) from the William Davidson Edition (CC BY-NC, via Sefaria):
the model reads the whole Davidson text (amber <b> = the mishnah's own words, plain = the editors' connecting explanation) and the Hebrew mishnah, then writes one fluent
translation that stays as close as possible to the amber words and the Hebrew, using the plain text only to make the sentences grammatical. A DRAFT for the author's review.
Run: python3 scripts/make_smooth_en.py [chapter-file ...]   (default: all seven chapters)"""
import json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
FILES = sys.argv[1:] or [f"data/bava_kamma_{c}.json" for c in range(1, 7)] + ["data/bava_metzia_1.json"]
SYS = ("You prepare an English reading translation of the Mishnah for a study site. For each mishnah you get (1) the Hebrew and (2) the William Davidson English, in which <b>bold</b> marks the words that translate the mishnah itself "
       "and the plain text between is the editors' explanation. Write ONE smooth translation of the mishnah that: stays as close as possible to the Hebrew and the bold words, in the same order; adds only the small connecting words the "
       "sentence needs to be grammatical and clear (a verb, 'then', 'if', 'the one who'), taking them from the plain text; leaves out the editors' explanations, examples, cross-references and 'the Gemara explains' remarks; "
       "does not add halakhic content that is not in the Hebrew; keeps every case, number, name and dispute of the mishnah; reads as natural modern English. "
       "Keep Hebrew terms the editors transliterate in italics with <i>...</i> (for example <i>mav'eh</i>) and keep <i>shoteh</i> only when it is an ox. "
       "FIXED TERMS: translate the Hebrew word שוטה (a person) as 'a person with psychosis', never 'imbecile', 'idiot' or 'insane'; חרש as 'a deaf-mute'; מועד as 'an attested danger'; תם as 'harmless'. "
       "Use only <i> tags for markup. Return JSON: {\"t\": [one string per mishnah, same order]}.")
TOOL = {"name": "out", "description": "smooth translations", "input_schema": {"type": "object", "properties": {"t": {"type": "array", "items": {"type": "string"}}}, "required": ["t"]}}
def call(items):
    body = {"model": "claude-opus-4-5", "max_tokens": 16000, "system": SYS, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "out"},
            "messages": [{"role": "user", "content": json.dumps(items, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600)); t = [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]["t"]
    if isinstance(t, str): t = json.JSONDecoder().raw_decode(t.strip())[0]
    return t
for f in FILES:
    d = json.load(open(f)); ms = d["mishnayot"]
    items = [{"n": m["n"], "hebrew": re.sub(r"<[^>]+>", "", m["he"]), "davidson": m["en"]} for m in ms]
    out = call(items); assert len(out) == len(ms), (f, len(out), len(ms))
    for m, t in zip(ms, out):
        t = re.sub(r"<(?!/?i>)[^>]+>", "", t).strip(); assert not re.search(r"imbecile|idiot|insane", t, re.I), (f, m["n"], t[:80]); m["en_smooth"] = t
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=1); print(f, len(ms), "done")
