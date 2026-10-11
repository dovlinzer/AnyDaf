"""Older-audience (graphic novel, style A) pictures -> site/img/older/clean/<pid>.jpg (badge-free, for Explore and Quiz),
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
G = "data/generated_originals/older/"; OUT = "site/img/"; os.makedirs(OUT + "older/clean", exist_ok=True)
spec = {}
def add(pid, im, hots, hint):
    W, H = im.size; im.save(f"{OUT}older/clean/{pid}.jpg", quality=92)
    flat = im.convert("RGBA")
    for h in hots:
        for b in h["badges"]:
            bi = Image.open(OUT + b["src"]).convert("RGBA"); w = int(b["w"]); hh = int(w * bi.height / bi.width); bi = bi.resize((w, hh), Image.LANCZOS)
            x = int(b["x"] - w / 2); y = int(b["y"] - hh / 2) if b["anchor"] == "center" else int(b["y"] - hh)
            flat.alpha_composite(bi, (x, y)) if x >= 0 and y >= 0 else flat.paste(bi, (x, y), bi)
    flat.convert("RGB").save(f"{OUT}older/{pid}.jpg", quality=92)
    spec[pid] = {"clean": f"img/older/clean/{pid}.jpg", "w": W, "h": H, "hint": hint, "hotspots": hots}; print(pid, len(hots))
def boxes_of(pid, pad=0):
    _, bx = detect(G + pid + ".jpg"); return [{"left": b["left"], "top": b["top"] + pad, "right": b["right"], "bottom": b["bottom"] + pad} for b in bx]
def rd(pid): return Image.open(G + pid + ".jpg").convert("RGB")
def pad_top(im, px, stretch=False):   # stretch = repeat the top row (right when the top is plain sky); reflect = mirror the top strip (right when branches or beams reach the top)
    out = Image.new("RGB", (im.width, im.height + px)); out.paste(im, (0, px))
    out.paste(im.crop((0, 0, im.width, 6)).resize((im.width, px), Image.BICUBIC) if stretch else im.crop((0, 0, im.width, px)).transpose(Image.FLIP_TOP_BOTTOM), (0, 0)); return out
SKIP = set()   # 1:1b is being redone (the small piece did not read as part of the same cloak); no older picture yet
only = set(sys.argv[1:])
def go(pid): return pid not in SKIP and (not only or pid in only)
# ---- Bava Kamma 5
if go("bk5-1"):
    im = rd("bk5-1"); cow = bbox(im, "the large dead cow lying on her side at the lower left (whole body)"); calf = bbox(im, "the small dead calf lying on the ground at the bottom centre")
    add("bk5-1", im, [
      {"label": "The cow: what the owner of the ox pays", "rect": [cow["left"], cow["top"], cow["right"], cow["bottom"]], "badges": [{"src": "badge-pay-half.png", "x": (cow["left"] + cow["right"]) / 2 + 60, "y": (cow["top"] + cow["bottom"]) / 2 - 20, "w": 185, "anchor": "center"}], "answer": "pay-half"},
      {"label": "The calf: what the owner of the ox pays", "rect": [calf["left"], calf["top"], calf["right"], calf["bottom"]], "badges": [{"src": "badge-pay-quarter.png", "x": (calf["left"] + calf["right"]) / 2, "y": calf["top"] - 18, "w": 160, "anchor": "center"}], "answer": "pay-quarter"}],
      "Tap the cow and the calf to see what the owner of the ox pays for each.")
if go("bk5-2a"): add("bk5-2a", rd("bk5-2a"), whole(1264, 848, "notpay", "Show the ruling", "notpay", x=640, y=120), "Tap the picture to see the ruling.")
if go("bk5-2b"): add("bk5-2b", rd("bk5-2b"), whole(1264, 848, "pay", "Show the ruling", "pay", x=640, y=120), "Tap the picture to see the ruling.")
if go("bk5-5"): add("bk5-5", rd("bk5-5"), box_hot(boxes_of("bk5-5"), ["pay", "notpay"], ["The pit of ten handbreadths", "The pit of nine handbreadths"], ["pay", "notpay"]), "Tap each box to see whether he pays.")
if go("bk5-6"):
    im = rd("bk5-6"); hots = box_hot(boxes_of("bk5-6"), ["notpay", "pay"], ["Covered pit", "Open pit"], ["notpay", "pay"])
    hots.append(person_tag(im, "the man in a green tunic standing with hands on his hips in the main scene, centre", "pay", "Who pays?", "pay", 1264, 848, side=70, dy=20)); add("bk5-6", im, hots, "Tap each box, and the man in green, to see who pays.")
# ---- Bava Metzia 1
for pid, kp in (("bm1-1a", "half-half"), ("bm1-1b", "3q-1q")):
    if pid in SKIP: continue
    if not go(pid): continue
    raw = rd(pid); im = pad_top(raw, 70, True); sb = bbox(raw, "the single framed rounded box in the upper left corner showing a white garment")
    add(pid, im, [{"label": "How the cloak is divided", "rect": [sb["left"], sb["top"] + 70, sb["right"], sb["bottom"] + 70], "badges": [{"src": f"badge-{kp}.png", "x": (sb["left"] + sb["right"]) / 2, "y": sb["top"] + 70 - 32, "w": int((sb["right"] - sb["left"]) * 0.46), "anchor": "center"}], "answer": kp}], "Tap the box to see how the cloak is divided.")
if go("bm1-2"):
    raw = rd("bm1-2"); im = pad_top(raw, 40, True)
    add("bm1-2", im, box_hot(boxes_of("bm1-2", 40), ["", ""], ["They swear, then split it", "They agree, then split it"], ["half-half", "half-half"], top_center=True, pill="badge-half-half.png"), "Tap each box to see how it is split.")
for pid, kind in (("bm1-3a", "keeps"), ("bm1-3b", "noclaim")):
    if go(pid): im = rd(pid); add(pid, im, [person_tag(im, "the bald man in an orange tunic on the right", kind, "Does he keep it?", kind, 1264, 848)], "Tap the man in orange to see the ruling.")
for pid, kind in (("bm1-4a", "keeps"), ("bm1-4b", "noclaim")):
    if go(pid): im = pad_top(rd(pid), 20); add(pid, im, [person_tag(im, "the field's owner wearing a straw hat and brown tunic, hand on his chest", kind, "Does the field acquire it?", kind, 1264, 868)], "Tap the field's owner to see the ruling.")
for pid, rect in (("bm1-5a", (60, 110, 760, 848)), ("bm1-5b", (850, 115, 1175, 848))):   # father; grown daughter (fixed after checking the baked picture)
    if not go(pid): continue
    im = pad_top(rd(pid), 40); l, t, r_, b_ = rect; cx = (l + r_) / 2
    add(pid, im, [{"label": "Who keeps what is found?", "rect": [l, t + 40, r_, b_ + 40], "badges": [{"src": "tag-keeps.png", "x": cx, "y": t + 40 - 6, "w": 104, "anchor": "bottom"}], "answer": "keeps"}], "Tap the person to see who keeps it.")
if go("bm1-7"):
    im = rd("bm1-7"); add("bm1-7", im, [person_tag(im, "the man in the orange tunic at the bottom centre holding a scroll", "noreturn", "Should he return it?", "noreturn", 1264, 848, d=110, side=190, dy=60)], "Tap the man in orange to see the ruling.")
if only and os.path.exists("data/overlays_older.json"): old = json.load(open("data/overlays_older.json")); old.update(spec); spec = old
json.dump(spec, open("data/overlays_older.json", "w"), indent=1); print("saved", len(spec))
