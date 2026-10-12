"""Show what a new prompt file ADDS or DROPS compared with a base file, per picture, sentence by sentence, and flag risk words.
Use before any prompt goes to the author: every added sentence must be justified by the mishnah, Kehati or Kulp, or be a stated expression.
Run: python3 scripts/prompt_diff.py data/graphic-novel_prompts_bk3_v3.md data/clay_prompts_bk3_v2.md"""
import re, sys
RISK = ["bandage","bruise","sandal","blood","hat","scarf","necklace","bracelet","basket","tool","dog","cat","bird","child","baby","tear","smile","laugh","hand on","limp"]
def load(p):
    t = open(p).read(); out = {}
    for m in re.finditer(r"## (\S+?):.*?```\n(.*?)```", t, re.S):
        out[m.group(1)] = m.group(2)
    return out
def sents(x): return [s.strip() for s in re.split(r"(?<=[.;])\s+", x.replace("\n", " ")) if s.strip()]
base, new = load(sys.argv[1]), load(sys.argv[2])
for pid, txt in new.items():
    sc = txt.split("THE SCENE TO DRAW:")[-1]; st = txt.split("THE SCENE TO DRAW:")[0] if "THE SCENE TO DRAW:" in txt else ""
    b = set(sents(base.get(pid, "").split("THE SCENE TO DRAW:")[-1]))
    add = [s for s in sents(sc) if s not in b]
    print(f"\n== {pid}: {len(add)} sentence(s) not in the base")
    for s in add: print("  +", s, ("   <-- RISK: " + ", ".join(w for w in RISK if re.search(r"\b"+w+r"\b", s.lower()))) if any(re.search(r"\b"+w+r"\b", s.lower()) for w in RISK) else "")
    for w in RISK:
        if re.search(r"\b"+w+r"\b", st.lower().replace("children's","")): print("  !! STYLE BLOCK mentions", w, "(it will leak into every picture)")
