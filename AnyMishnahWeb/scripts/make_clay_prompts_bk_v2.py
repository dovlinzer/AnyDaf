"""Clay prompts v2 for BK 1-6 (2026-10-13): only the pictures that changed after the author's first Gemini run.
bk2-1b: fresh scene (not an edit), cow in profile so the back hoof shows. bk6-1b: 'worried' not 'sheepish'.
bk6-4a/b: ONE MOMENT PER PICTURE (act, then outcome). Run: python3 scripts/make_clay_prompts_bk_v2.py"""
src = open("scripts/make_prompts_bk1_2_4_6.py").read().split("CAST =")[0]
ns = {"__file__": "scripts/make_prompts_bk1_2_4_6.py"}; exec(src, ns); CLAY = ns["CLAY_STYLE"]
ITEMS = [
("bk2-1b", "2:1 the cow kicks the jar (NEW chat, a fresh scene: the edit gave a bent leg)", "scene",
 "Scene: the walled courtyard of a house, with a house door at the left. A brown cow stands in the middle of the courtyard seen exactly from the side, facing left. Her back leg is stretched straight out behind her at the side, and the whole leg and its hoof are clearly visible, with the hoof striking a large clay jar that stands on the ground at the right, which is cracking into pieces. The jar's owner, a woman in a green dress with a white head covering, stands by the house door with a dismayed expression. The cow's owner, a man in a grey tunic, stands by the open gate at the right with a startled expression. Exactly one cow, one jar, one woman and one man.",
 "the whole back leg in profile and the hoof ON the jar; not hidden behind it; one jar"),
("bk6-1b", "6:1 the gate was not shut properly (same chat, edit of 6:1a)", "edit",
 "Using the previous picture as reference, everything is exactly the same except: the sheepfold's wall is whole, with no gap. The wooden gate stands wide open and the heavy wooden bar leans against the wall; three sheep walk out through the open gate and two are eating the barley. The farmer has a worried expression. Exactly five sheep, one sheepfold, one farmer and one woman.",
 "farmer worried, not smiling; the rest as before"),
("bk6-4a", "6:4 a man adds wood to a fire (FIRST of a pair; make 6:4b in the SAME chat)", "scene",
 "Scene: the edge of a field of standing wheat at the right, in daylight. At the left a man in a green tunic crouches beside a small fire on the bare ground, holding a burning torch, with a calm expression. A second man, in a brown tunic, stands over the small fire and lays a bundle of dry brush on it, with a concerned expression. The fire is small and low, and the wheat is not burning. Exactly two men, one small fire, one bundle of dry brush and one field of wheat.",
 "ONLY the act: a small fire, the brown man laying wood on it; wheat untouched"),
("bk6-4b", "6:4 the fire grows and spreads (same chat, edit of 6:4a)", "edit",
 "Using the previous picture as reference, everything is exactly the same except: the bundle of brush is burning and the fire has become large, with tall flames, and the flames have spread to the wheat at the edge of the field, which is burning. Both men have stepped back and have alarmed expressions. Exactly two men, one large fire and one field of wheat.",
 "ONLY the outcome: big fire, burning wheat, both men alarmed"),
]
out = ["# Bava Kamma clay prompts v2 (2026-10-13): changed pictures only\n"]
for pid, title, k, scene, review in ITEMS:
    txt = ("GENERAL STYLE (the same for every picture):\n" + CLAY + "\n\nTHE SCENE TO DRAW:\n" + scene) if k == "scene" else scene
    out.append(f"\n## {pid}: {title}\n\nPASTE:\n```\n{txt}\n```\nReview: {review}.\n")
open("data/clay_prompts_bk1-6_v2.md", "w").write("".join(out)); print("ok")
