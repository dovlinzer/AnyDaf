"""CLAY pictures for Bava Kamma 3 (younger audience), same method as build_overlays_older.py. Older-audience (graphic novel, style A) pictures -> site/img/older/clean/<pid>.jpg (badge-free, for Explore and Quiz),
site/img/older/<pid>.jpg (all badges baked in, for Static) and data/overlays_older.json. Same placement rules as build_overlays.py
(badges toward the top, clear of faces; a split between two people goes between them). Coordinates come from vision calls;
the baked Static pictures are the visual check, so LOOK at them after every run."""
import json, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import detect
import ast, base64, io, urllib.request
from PIL import ImageDraw, ImageFont
from detect_boxes import KEY
OUT = "site/img/"
_src = open(os.path.join(os.path.dirname(__file__), "build_overlays.py")).read(); _ns = dict(globals())
for _n in ast.parse(_src).body:   # take ONLY the helper functions: importing build_overlays would rerun the whole clay build
    if isinstance(_n, ast.FunctionDef) and _n.name in ("bbox", "pad_top", "box_hot", "whole", "person_tag"): exec(compile(ast.Module([_n], []), "build_overlays.py", "exec"), _ns)
bbox, pad_top, box_hot, whole, person_tag = (_ns[k] for k in ("bbox", "pad_top", "box_hot", "whole", "person_tag"))
G = "data/generated_originals/clay/"; OUT = "site/img/"; os.makedirs(OUT + "clean", exist_ok=True)
spec = {}
def add(pid, im, hots, hint):
    W, H = im.size; im.save(f"{OUT}clean/{pid}.jpg", quality=92)
    flat = im.convert("RGBA")
    for h in hots:
        for b in h["badges"]:
            bi = Image.open(OUT + b["src"]).convert("RGBA"); w = int(b["w"]); hh = int(w * bi.height / bi.width); bi = bi.resize((w, hh), Image.LANCZOS)
            x = int(b["x"] - w / 2); y = int(b["y"] - hh / 2) if b["anchor"] == "center" else int(b["y"] - hh)
            flat.alpha_composite(bi, (x, y)) if x >= 0 and y >= 0 else flat.paste(bi, (x, y), bi)
    flat.convert("RGB").save(f"{OUT}{pid}.jpg", quality=92)
    spec[pid] = {"clean": f"img/clean/{pid}.jpg", "w": W, "h": H, "hint": hint, "hotspots": hots}; print(pid, len(hots))
def boxes_of(pid, pad=0):
    _, bx = detect(G + pid + ".jpg"); return [{"left": b["left"], "top": b["top"] + pad, "right": b["right"], "bottom": b["bottom"] + pad} for b in bx]
def rd(pid): return Image.open(G + pid + ".jpg").convert("RGB")
def pad_top(im, px, stretch=False):   # stretch = repeat the top row (right when the top is plain sky); reflect = mirror the top strip (right when branches or beams reach the top)
    out = Image.new("RGB", (im.width, im.height + px)); out.paste(im, (0, px))
    out.paste(im.crop((0, 0, im.width, 6)).resize((im.width, px), Image.BICUBIC) if stretch else im.crop((0, 0, im.width, px)).transpose(Image.FLIP_TOP_BOTTOM), (0, 0)); return out
SKIP = set()   # 1:1b is being redone (the small piece did not read as part of the same cloak); no older picture yet
only = set(sys.argv[1:])
def go(pid): return pid not in SKIP and (not only or pid in only)
def tags(pid, pad, items, stretch=False):
    if not go(pid): return
    im = pad_top(rd(pid), pad, stretch) if pad else rd(pid); hots = [person_tag(im, d, k, lab, ans, 1264, 848 + pad) for d, k, lab, ans in items]
    add(pid, im, hots, "Tap a person to see the ruling.")
tags("bk3-1a", 30, [("the man in the blue tunic sprawled on the road, holding his leg", "notpay", "The man who tripped", "notpay"), ("the grey-haired woman in the brown dress and cream apron standing at the left", "pay", "The owner of the jug", "pay")])
tags("bk3-1b", 100, [("the woman in the green dress with a white head covering, holding a jug handle", "pay", "The owner of the jug", "pay")], stretch=True)
tags("bk3-2a", 0, [("the woman in the grey dress and white head covering pouring a bucket of water", "pay", "The woman who poured the water", "pay")])
tags("bk3-2b", 60, [("the old man with a white beard and both hands on his head, at the right", "pay", "The owner of the field", "pay")])
tags("bk3-3", 60, [("the man in the grey tunic and head cloth holding a pitchfork, at the left", "pay", "The man who put the straw on the road", "pay")])
tags("bk3-4", 0, [("the woman in the brown dress and white head covering lying on the ground at the left, with a rack of pots on her back", "pay", "The first pot-seller", "pay")])
tags("bk3-5s", 0, [("the man in the brown tunic carrying a long wooden beam on his shoulder, on the left", "notpay", "The owner of the beam", "notpay")])
tags("bk3-5a", 30, [("the man in the brown cloak carrying a long wooden beam on his shoulder, on the left", "notpay", "The owner of the beam", "notpay")])
tags("bk3-5b", 30, [("the man in the brown cloak carrying a long wooden beam on his shoulder, on the left", "pay", "The owner of the beam", "pay")])
tags("bk3-5c", 30, [("the man in the brown cloak carrying a long wooden beam on his shoulder, with a raised hand", "notpay", "The owner of the beam", "notpay")])
tags("bk3-6", 0, [("the woman in the purple dress and white head covering sitting on the ground at the left", "notpay", "The woman", "notpay"), ("the bearded man in the tan tunic sitting on the ground at the right", "notpay", "The man", "notpay")])
tags("bk3-7", 70, [("the woman in the rust-coloured dress holding an axe, at the left", "pay", "The woman splitting wood", "pay")])
tags("bk3-11a", 0, [("the woman in the green dress and white head covering, in the middle", "notpay", "The owner of the red ox", "notpay"), ("the bald man in the yellow tunic at the right", "notpay", "The owner of the black ox", "notpay")])
tags("bk3-11b", 0, [("the woman in the green dress and white head covering standing at the wall", "pay", "The owner of both chasing oxen", "pay")])
OVP = "data/overlays.json"; old = json.load(open(OVP)); old.update(spec); json.dump(old, open(OVP, "w"), indent=1); print("saved", len(old))
