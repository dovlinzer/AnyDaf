"""Write the Hebrew pages' text FRESH in Hebrew (not a translation), one mishnah at a time, with the Hebrew mishnah and Steinsaltz's explanation as context -> data/he/strings.json.
The English strings (data/he/_all.json, written by build_site.py) supply only the FACTS and the slot each text fills (title, summary, heading, bullet, caption, question, principle...).
Our English outlines are our own paraphrase of the mishnah, Kehati and Kulp; the Hebrew is again our own wording (never Kehati's or Steinsaltz's sentences). A DRAFT for the author's review.
Run: python3 scripts/write_he.py [ctx ...]     e.g. 2:m1 3:summary   (default: everything except UI strings, which keep their short translations)"""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
ALL = json.load(open("data/he/_all.json")); HEF = "data/he/strings.json"; HE = json.load(open(HEF))
only = set(sys.argv[1:])
def norm_html(s): return re.sub(r"<[^>]+>", "", s)
def facts(c):
    L = {m["n"]: m for m in json.load(open(f"data/bava_kamma_{c}_layer1.json"))["mishnayot"]}; D = {m["n"]: m for m in json.load(open(f"data/bava_kamma_{c}.json"))["mishnayot"]}
    return L, D
QQ = json.load(open("data/quiz_questions.json")); QP = json.load(open("data/quiz_principles.json"))
def kinds(c):
    L, _ = facts(c); k = {}
    for n, m in L.items():
        k[m["title"]] = "title of the mishnah section (short noun phrase)"; k[m["summary"]] = "one-sentence summary of the mishnah under its title"
        for s in m["outline"]:
            k[s["h"]] = "short heading of an outline block"
            for t, _src in s["b"]: k[t] = "one bullet of the outline (one clear sentence)"
        ch = m.get("chart")
        if ch:
            k[ch["title"]] = "title of a small table"
            for x in ch["cols"]: k[x] = "table column heading"
            for r in ch["rows"]:
                for x in r: k[x] = "table cell (short)"
        for p in m.get("pictures", []):
            for q in (p["pics"] if isinstance(p, dict) else [p]):
                k[q[1]] = "caption under an illustration (describe what the picture shows and the ruling)"
    for pid, qs in QQ.items():
        if pid.startswith(f"bk{c}-"):
            for q in qs: k[q] = "quiz question shown above an illustration; must be a full question ending with a question mark"
    for pid, ps in QP.items():
        if pid.startswith(f"bk{c}-"):
            for q in ps: k[q] = "one-sentence principle shown after a correct quiz answer; keep the source tag in parentheses"
    S = json.load(open(f"data/bava_kamma_{c}_summary.json"))
    for x in S["principles"]:
        k[x["t"]] = "a key principle of the chapter (one or two sentences, with the Hebrew terms written plainly)"
        if x.get("note"): k[x["note"]] = "note under a principle"
    for x in S["terms"]: k[x["term"]] = "heading of a key term"; k[x["def"]] = "definition of a key term (one or two sentences)"
    for x in S["debates"]:
        k[x["title"]] = "title of a debate (a question)"; k[x["a"]] = "the first party's position in a debate (the party's name is the box heading: do not repeat it)"; k[x["b"]] = "the second party's position (do not repeat the party's name)"
        k[x.get("wa", "")] = "name of a party/opinion"; k[x.get("wb", "")] = "name of a party/opinion"
    return k
STEIN = {c: json.load(open(f"data/steinsaltz/bk_{c}_biur.json")) for c in (1, 2, 3)}
SYS = ("You are a Hebrew-speaking teacher of Mishnah writing a study aid for Israeli adult learners. The page shows the mishnah itself (with Steinsaltz's explanation) and, next to it, short study notes. "
       "WRITE each note FRESH, in natural, clear, idiomatic Hebrew, as a good teacher would say it aloud: do NOT translate the English word by word and do not follow its sentence structure. The English gives you only the FACTS and the SLOT the text fills. "
       "Use the Hebrew mishnah (and Steinsaltz's explanation, given as context) to pick the natural halakhic Hebrew: quote the mishnah's own phrases where they fit (משלם, פטור, חייב, ברשות הרבים, דרכו ל, שמירתו עליך, מועד, תם), prefer short sentences, active verbs, no calques (avoid 'על פי', 'ביחס ל', 'מבחינת', "
       "'אם כן...אז'). Do not copy Steinsaltz's or Kehati's sentences: your own words. Add no fact, drop no fact. If you are not sure of a Hebrew word, use the word the mishnah or Steinsaltz uses; never invent a word. No nikud. No transliteration and no parentheses around technical terms: write the Hebrew term plainly. "
       "References: 'Mishnah 3:1' -> 'משנה ג:א', 'Kehati 2:5' -> 'קהתי ב:ה', 'Kulp' -> 'קולפ' (Hebrew letters for chapter and mishnah). Numbers inside prose as words (עשרה טפחים). Names: Rabbi X -> רבי X, Rabban Shimon ben Gamaliel -> רבן שמעון בן גמליאל, the Sages -> חכמים. "
       "Quiz questions: a complete question ending with '?', addressed neutrally. Debate positions: do not repeat the party's name (it is the box heading). Keep each text about as long as the English or shorter. "
       "STYLE EXAMPLE. English: 'A beast is an attested danger to eat fruit and vegetables, so the owner pays full damages (Mishnah 2:2).' Stilted: 'בהמה היא מועד לאכול פירות וירקות ולכן הבעלים משלמים נזק שלם (משנה 2:2)'. Fresh: 'הבהמה מועדת לאכול פירות וירקות, ולכן בעליה משלם נזק שלם (משנה ב:ב)'. "
       "Return JSON {\"t\": [...]} with one Hebrew text per input item, in the same order.")
TOOL = {"name": "out", "description": "hebrew", "input_schema": {"type": "object", "properties": {"t": {"type": "array", "items": {"type": "string"}}}, "required": ["t"]}}
def call(ctx, items):
    c, part = ctx.split(":"); c = int(c); kd = kinds(c); L, D = facts(c)
    head = f"Bava Kamma chapter {c}, "
    if part.startswith("m"):
        n = int(part[1:]); head += f"mishnah {n}.\n\nTHE MISHNAH (Hebrew):\n{norm_html(D[n]['he'])}\n\nSTEINSALTZ'S EXPLANATION (context only, do not copy):\n" + "\n".join(norm_html(sg) for pc in STEIN[c].get(str(n), []) for sg in pc["segs"]) + f"\n\nENGLISH TITLE OF THIS MISHNAH SECTION: {L[n]['title']}"
    else: head += "chapter summary (key principles, terms, debates). Mishnah sections: " + "; ".join(f"{n}. {m['title']}" for n, m in L.items())
    payload = {"context": head, "items": [{"id": i, "slot": kd.get(x, "short label or diagram text"), "english": x} for i, x in enumerate(items)]}
    body = {"model": os.environ.get("HE_MODEL", "claude-opus-4-5"), "max_tokens": 8000, "system": SYS, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "out"}, "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for _ in range(3):
        r = json.load(urllib.request.urlopen(req, timeout=300)); t = [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]["t"]
        if isinstance(t, str):
            try: t = json.JSONDecoder().raw_decode(t.strip())[0]
            except Exception: t = []
        if len(t) == len(items): return dict(zip(items, t))
    print("mismatch", ctx); return {}
if __name__ == "__main__":
    groups = {}
    for x, ctx in ALL.items():
        if ctx != "ui" and (not only or ctx in only): groups.setdefault(ctx, []).append(x)
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(lambda kv: call(*kv), groups.items()): HE.update(res)
    json.dump(HE, open(HEF, "w"), ensure_ascii=False, indent=1); print("wrote", sum(len(v) for v in groups.values()), "texts in", len(groups), "groups")
