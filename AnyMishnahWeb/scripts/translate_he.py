"""Translate the English strings the Hebrew pages need (data/he/_needed.json, written by build_site.py) into Hebrew -> data/he/strings.json (merged, never overwritten).
Source of truth is OUR English text (itself a paraphrase of the mishnah, Kehati and Kulp): this is a translation, never new content, and never Kehati's own Hebrew wording.
Run: python3 scripts/translate_he.py   then python3 scripts/build_site.py.   The output is a DRAFT for the author's review (data/he/strings.json is editable by hand)."""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
NEED = json.load(open("data/he/_needed.json")); HEF = "data/he/strings.json"; HE = json.load(open(HEF)) if os.path.exists(HEF) else {}
todo = [x for x in NEED if x not in HE]
GLOSS = {}
for c in (1, 2, 3):
    for t in json.load(open(f"data/bava_kamma_{c}_summary.json"))["terms"]: GLOSS[t["term"]] = t["he"]
MANUAL = {"attested danger / mu'ad": "מועד", "harmless / tam": "תם", "tooth / shen": "שן", "foot / regel": "רגל", "horn / keren": "קרן", "ransom / kofer": "כופר", "it is enough / dayo": "דיו", "the four primary causes of injury / avot nezikin": "אבות נזיקין",
          "ox / shor": "שור", "pit / bor": "בור", "crop-destroying beast / mav'eh": "מבעה", "fire / hev'er": "הבער (כשם הקטגוריה במשנה א:א; אחרת: אש)", "damage / nezek": "נזק", "indirect cause / grama": "גרמא",
          "guardian / apotropos": "אפוטרופוס", "handbreadth / tefach": "טפח", "burden of proof / hamotzi mechavero alav hara'ayah": "המוציא מחברו עליו הראיה", "I have prepared / hichsharti": "הכשרתי",
          "public domain": "רשות הרבים", "domain of the damaged party": "רשות הניזק", "half damages": "חצי נזק", "full damages": "נזק שלם", "pays / is liable": "משלם / חייב", "does not pay / is exempt": "אינו משלם / פטור",
          "Kehati": "קהתי", "R. Kulp": "ר' קולפ", "Rabbi": "רבי", "Rabban": "רבן", "Rav": "רב", "Shmuel": "שמואל", "the Sages": "חכמים", "Younger/Older (audience)": "צעירים / מבוגרים (קהל היעד)", "Static / Explore / Quiz": "קבוע / חקירה / חידון"}
SYS = ("You translate English study-site text about the Mishnah (Bava Kamma) into clear, modern, plain Hebrew without nikud, for Hebrew-speaking learners. The English is a paraphrase of the mishnah, Kehati and R. Kulp: translate FAITHFULLY, add nothing, drop nothing, "
       "and do not reproduce Kehati's own Hebrew phrasing (write in your own plain words). Use the standard Hebrew halakhic term for each key term (glossary below) and write it as ordinary Hebrew: where the English has a pair like \"an attested danger (mu'ad)\" write just the Hebrew term (\"מועד\"), "
       "no transliteration, no parentheses. Keep numbers and references (\"Mishnah 3:1\" -> \"משנה 3:1\"; \"Kehati 2:5\" -> \"קהתי 2:5\"; \"Kulp\" -> \"קולפ\"). Names: Rabbi Judah -> רבי יהודה, R. Meir -> רבי מאיר, Rabban Shimon ben Gamaliel -> רבן שמעון בן גמליאל, the Sages -> חכמים. "
       "Strings that are fragments (a label, a button, a heading, text in parentheses) stay short fragments. Keep any punctuation that frames them, such as parentheses. Quiz questions are addressed neutrally (\"האם הוא משלם?\"). "
       "Return JSON: {\"t\": [Hebrew strings in the SAME order as the input]}.\n\nGLOSSARY:\n" + "\n".join(f"{k} = {v}" for k, v in {**{k: v for k, v in GLOSS.items()}, **MANUAL}.items()))
TOOL = {"name": "out", "description": "translations", "input_schema": {"type": "object", "properties": {"t": {"type": "array", "items": {"type": "string"}}}, "required": ["t"]}}
def one(batch):
    body = {"model": "claude-sonnet-4-5", "max_tokens": 8000, "system": SYS, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "out"}, "messages": [{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for _ in range(3):
        r = json.load(urllib.request.urlopen(req, timeout=300)); t = [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]["t"]
        if isinstance(t, str):
            try: t = json.JSONDecoder().raw_decode(t.strip())[0]
            except Exception: t = []
        if len(t) == len(batch): return dict(zip(batch, t))
    print("batch size mismatch, skipped", len(batch)); return {}
if __name__ == "__main__":
    B = [todo[i:i + 30] for i in range(0, len(todo), 30)]
    with ThreadPoolExecutor(5) as ex:
        for res in ex.map(one, B): HE.update(res)
    json.dump(HE, open(HEF, "w"), ensure_ascii=False, indent=1); print("translated", len(HE), "of", len(NEED))
