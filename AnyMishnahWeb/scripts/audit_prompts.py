"""Content audit of picture prompts against the sources (2026-10-13). For each prompt it gives a model the mishnah (English), the outline built from the mishnah/Kulp/Kehati, and the scene text, and asks:
(1) EXTRANEOUS: every object, figure, setting feature, or expression in the scene that the case does not need (animals' expressions, walls, gates, props, background detail);
(2) KEY FACTS: the facts of the case that decide the ruling (the act, the damage, the contact, the state, the place), and whether the scene makes each one VISIBLE (not merely implied).
Run: python3 scripts/audit_prompts.py data/graphic-novel_prompts_bk1-6_v2.md [pid ...]   -> data/prompt_audit.md.  Cost: about a cent per prompt (sonnet). It is a second pair of eyes, not a verdict."""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
def load(p):
    t = open(p).read(); out = {}
    for m in re.finditer(r"## (\S+?): (.*?)\n.*?```\n(.*?)```\s*(?:Review: (.*?)\.?\n)?(?:Overlay: (.*?)\.?\n)?", t, re.S): out[m.group(1)] = (m.group(2), m.group(3), (m.group(4) or "") + " | " + (m.group(5) or ""))
    return out
def source(pid):
    c, n = re.match(r"bk(\d)-(\d+)", pid).groups(); d = json.load(open(f"data/bava_kamma_{c}.json"))["mishnayot"][int(n) - 1]
    en = d["en"]; l = json.load(open(f"data/bava_kamma_{c}_layer1.json"))["mishnayot"][int(n) - 1]
    ol = "\n".join(f"{s['h']}: " + " | ".join(b[0] for b in s["b"]) for s in l["outline"])
    return en, ol
TOOL = {"name": "audit", "description": "audit", "input_schema": {"type": "object", "properties": {
    "extraneous": {"type": "array", "items": {"type": "object", "properties": {"severity": {"type": "string", "enum": ["major", "minor"]}, "element": {"type": "string"}, "why": {"type": "string"}, "fix": {"type": "string"}}, "required": ["severity", "element", "why", "fix"]}},
    "key_facts": {"type": "array", "items": {"type": "object", "properties": {"fact": {"type": "string"}, "visible": {"type": "string", "enum": ["yes", "weak", "no"]}, "note": {"type": "string"}}, "required": ["fact", "visible", "note"]}},
    "verdict": {"type": "string"}}, "required": ["extraneous", "key_facts", "verdict"]}}
SYS = ("You audit picture prompts for a Mishnah study site. The picture must make the facts of the case that decide the ruling VISIBLE (the act, the contact, the damage or injury shown plainly as a wound, the state of the gate/pit/jar, who is who) "
       "and must contain NOTHING the case does not need: no walls, fences, gates, props, clothing details, background action or expressions on ANIMALS unless the case needs them. "
       "Each human figure needs a stated expression, and that is allowed; but flag an expression that adds meaning the case does not have (smiling, contented, smug, puzzled on an animal). "
       "A wall, gate or courtyard IS needed when the ruling depends on the domain or on the gate's state. For an edit prompt ('Using the previous/attached picture...'), judge the picture that results: what is kept plus what the edit changes. "
       "CONTEXT you must respect: (a) the site's quiz puts a ruling badge on each party whose liability is at stake, so the payer and the other party (owner of the animal or the jar, the injured party) SHOULD appear as figures; do not call them extraneous. "
       "(b) In chapter 2 the courtyard and its gate are the domain and belong; in chapter 1 the 1:1 pictures are deliberate ACTION SHOTS of a category (the ox goring, the pit, fire, the crop-destroying beast): judge them only for extras and visible damage, not for being 'conceptual'. "
       "(c) Mark an extraneous item 'major' only if the model is likely to draw it wrongly or it misleads about the case (an unneeded wall or gate, an animal's expression, a prop that suggests another case, an unstated injury or missing injury); everything else is 'minor' (scenery such as a hillside, clothing colour, sky). "
       "Do not ask for figures to be removed when they are the parties or the quiz targets. Be concrete and short. Say 'no' for a key fact only when the scene does not show it at all; 'weak' when it is implied or small.")
def audit(pid, title, scene, purpose=""):
    en, ol = source(pid)
    msg = f"PICTURE {pid}: {title}\nINTENDED PURPOSE / what to check / who gets the badge: {purpose}\n\nMISHNAH (English):\n{en}\n\nOUTLINE FROM THE SOURCES:\n{ol}\n\nSCENE PROMPT:\n{scene}"
    body = {"model": "claude-sonnet-4-5", "max_tokens": 1500, "system": SYS, "tools": [TOOL], "tool_choice": {"type": "tool", "name": "audit"}, "messages": [{"role": "user", "content": msg}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for attempt in range(3):
        r = json.load(urllib.request.urlopen(req, timeout=180)); a = [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]
        for key in ("extraneous", "key_facts"):
            if isinstance(a.get(key), str):
                try: a[key] = json.loads(a[key])
                except Exception: a[key] = []
        a["extraneous"] = [e for e in a.get("extraneous", []) if isinstance(e, dict)]; a["key_facts"] = [k for k in a.get("key_facts", []) if isinstance(k, dict)]
        if a["key_facts"] or attempt == 2: break
    return pid, title, a
if __name__ == "__main__":
    P = load(sys.argv[1]); only = set(a for a in sys.argv[2:])
    jobs = [(pid, t, txt.split("THE SCENE TO DRAW:")[-1].strip(), pur) for pid, (t, txt, pur) in P.items() if not only or pid in only]
    with ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda j: audit(*j), jobs))
    out = ["# Prompt audit (" + os.path.basename(sys.argv[1]) + ")\n"]; flagged = []
    for pid, t, a in res:
        out.append(f"\n## {pid}: {t}\nVerdict: {a['verdict']}\n")
        out.append("Key facts:\n" + "".join(f"- [{str(k.get('visible','no')).upper()}] {k.get('fact','?')} ({k.get('note','')})\n" for k in a["key_facts"]))
        out.append("Extraneous:\n" + ("".join(f"- [{str(e.get('severity','minor')).upper()}] {e.get('element','?')}: {e.get('why','')} -> {e.get('fix','')}\n" for e in a["extraneous"]) or "- none\n"))
        MAJ = [e for e in a["extraneous"] if e.get("severity") == "major"]; NO = [k for k in a["key_facts"] if k.get("visible") != "yes"]
        if MAJ or NO: flagged.append(pid)
    open("data/prompt_audit.md", "w").write("".join(out)); print("wrote data/prompt_audit.md", len(res), "audited;", len(flagged), "need attention:", ", ".join(flagged)); sys.exit(1 if flagged else 0)
