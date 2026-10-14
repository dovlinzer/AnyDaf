"""Pre-flight check for picture prompts (2026-10-13). Run BEFORE any prompt goes to the author:
    python3 scripts/check_prompts.py data/clay_prompts_bk1-6_v2.md [more files]
Flags the kinds of failure we have actually had (STYLE_BIBLE.md): two moments in one picture ('then'), expression words that came out wrong
('sheepish', 'calm' -> smiling), a person with no stated expression, an edit that does not start 'Using the (previous|attached) picture as reference,
everything is exactly the same except', an edit that moves something without saying where it ends up, poses the model cannot draw (a back leg kicked
toward us, anything 'behind' the thing it touches), risk words (bandage, sandal, blood, smile...), a scene with no 'Exactly ...' count line, and style-block
negatives. It cannot judge whether a scene is right; it only catches the repeat offenders. Exit code 1 if anything is flagged."""
import re, sys
MOMENT = ["then", "afterwards", "after that", "until", "later", "before", "once", "while the"]
BAD_EXPR = ["sheepish", "calm", "bemused", "content", "relaxed", "satisfied", "pleased", "amused", "smug", "peaceful", "innocent", "casual"]
RISK = ["bandage", "bruise", "sandal", "blood", "hat", "scarf", "necklace", "bracelet", "tool", "bird", "baby", "tear", "smile", "laugh", "hand on", "limp"]
POSE = ["back leg", "hind leg", "back hoof", "hind", "from behind", "over his shoulder", "over her shoulder", "behind the jar", "behind the", "looks back", "turns around"]
MOVE = ["moves", "carries", "brings", "drops", "lays", "places", "throws", "falls", "tosses", "puts", "pushes", "pulls", "hands"]
WHERE = ["on", "in", "onto", "into", "at", "beside", "under", "inside", "outside", "against", "near", "beyond", "across", "over", "from"]
PEOPLE = r"\b(man|woman|boy|girl|farmer|shepherd|judge|judges|witness|witnesses|shopkeeper|child)\b"
EDIT = re.compile(r"^Using the (previous|attached) picture as reference, everything is exactly the same except", re.I)
def load(p):
    t = open(p).read(); out = {}
    for m in re.finditer(r"## (\S+?): (.*?)\n.*?```\n(.*?)```", t, re.S): out[m.group(1)] = (m.group(2), m.group(3))
    return out
def sents(x): return [s.strip() for s in re.split(r"(?<=[.;])\s+", x.replace("\n", " ")) if s.strip()]
bad = 0
for fn in sys.argv[1:]:
    for pid, (title, txt) in load(fn).items():
        style, scene = (txt.split("THE SCENE TO DRAW:") + [""])[:2] if "THE SCENE TO DRAW:" in txt else ("", txt)
        is_edit = scene.strip().lower().startswith("using the")
        low = scene.lower(); flags = []
        if is_edit and not EDIT.match(scene.strip()): flags.append("edit does not open with 'Using the previous/attached picture as reference, everything is exactly the same except'")
        for w in MOMENT:
            if re.search(r"\b" + w + r"\b", low): flags.append(f"possible second moment: '{w}' (a case that needs 'then' is two pictures)")
        for w in BAD_EXPR:
            if re.search(r"\b" + w + r"\b", low): flags.append(f"expression word that has misfired: '{w}' (use worried / puzzled / alarmed / concerned / frowning / dismayed)")
        for w in RISK:
            if re.search(r"\b" + w + r"\b", low): flags.append(f"risk word: '{w}'")
        for w in POSE:
            if w in low: flags.append(f"pose the model draws badly: '{w}' (draw it in profile, or change the pose)")
        n_people = len(set(re.findall(r"(?:a|the|one) (?:\w+ )?" + PEOPLE, low)))
        if not is_edit and low.count("expression") < max(1, min(n_people, 2)): flags.append("a person may have no stated expression")
        if not is_edit and "exactly" not in low: flags.append("no 'Exactly ...' count line")
        if is_edit:
            for s in sents(scene):
                ws = re.findall(r"[a-z']+", s.lower())
                for i, w in enumerate(ws):
                    if w in MOVE and not any(x in WHERE for x in ws[i + 1:i + 7]): flags.append(f"edit moves something but may not say where it ends up: '{s[:80]}'"); break
        for w in ("never", "without", "not "):
            if re.search(r"\b" + w, style.lower()): flags.append(f"STYLE BLOCK contains '{w.strip()}' (negatives in the style block get drawn)")
        for w in RISK:
            if re.search(r"\b" + w + r"\b", style.lower().replace("children's", "")): flags.append(f"STYLE BLOCK mentions '{w}' (it leaks into every picture)")
        if flags: bad += 1; print(f"\n== {fn.split('/')[-1]}  {pid}  {title[:60]}"); [print("   -", f) for f in dict.fromkeys(flags)]
print(f"\n{bad} prompt(s) flagged")
sys.exit(1 if bad else 0)
