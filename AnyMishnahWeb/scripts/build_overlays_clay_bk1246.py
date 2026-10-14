"""CLAY pictures for Bava Kamma 1, 2, 4, 6 (2026-10-13): installs data/generated_originals/clay/bk{1,2,4,6}-*.jpg.
Pictures with no ruling (1:1 set, 1:3, 6:2a, which needs a 'pays the benefit' badge not yet decided) are copied as plain static pictures.
Pictures with a ruling get person tags (same method as build_overlays_clay_bk3.py); LOOK at every baked picture after a run.
Run: python3 scripts/build_overlays_clay_bk1246.py [pid ...]"""
import json, os, sys, shutil
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import ast
_src = open(os.path.join(os.path.dirname(__file__), "build_overlays_clay_bk3.py")).read().split("SKIP = set()")[0]
_ns = {"__file__": os.path.join(os.path.dirname(__file__), "build_overlays_clay_bk3.py")}; exec(_src, _ns)
add, rd, pad_top, bbox, person_tag = (_ns[k] for k in ("add", "rd", "pad_top", "bbox", "person_tag"))
from PIL import ImageDraw
OUT, G = "site/img/", "data/generated_originals/clay/"
def make_tag(kind):   # disc with a small pointer below (same as build_overlays.py)
    d = Image.open(f"{OUT}badge-{kind}.png").convert("RGBA"); S = d.width; im = Image.new("RGBA", (S, d.height + 34), (0, 0, 0, 0)); im.paste(d, (0, 0), d)
    ImageDraw.Draw(im).polygon([(S // 2 - 15, d.height - 3), (S // 2 + 15, d.height - 3), (S // 2, d.height + 32)], fill=(247, 237, 218, 255), outline=(150, 105, 80, 255)); im.save(f"{OUT}tag-{kind}.png")
make_tag("pay-half"); make_tag("pay-benefit")
PLAIN = ["bk1-1a", "bk1-1a2", "bk1-1b", "bk1-1c", "bk1-1d", "bk1-1d2", "bk1-3", "bk6-4a", "bk6-4c"]  # 6:4a/c: nothing has happened yet (act only), so no ruling or quiz; the ruling is on 6:4b/d
TAGS = {  # pid: [(description, kind, label)]
 "bk2-1a": [("the man in the grey tunic at the gate on the right", "pay", "The owner of the cow")],
 "bk2-1b": [("the man in the grey tunic at the gate on the right", "pay-half", "The owner of the cow")],
 "bk2-2a": [("the man in the grey tunic and head cloth standing in the doorway on the right", "pay", "The owner of the cow")],
 "bk2-2b": [("the man in the grey tunic and head cloth standing in the doorway on the right", "pay-half", "The owner of the cow")],
 "bk2-2c": [("the man in the grey tunic on the right", "pay-benefit", "The owner of the cow")],
 "bk2-3a": [("the man in the grey tunic at the right doorway", "pay", "The owner of the dog")],
 "bk2-3b": [("the round flat cake on the plate under the dog's mouth", "pay", "The cake"), ("the tall stack of wheat sheaves at the right", "pay-half", "The stack")],
 "bk2-6": [("the man in the brown tunic lying asleep on the mat", "pay", "The man who slept")],
 "bk4-4a": [("the boy in the yellow tunic at the right", "notpay", "The owner of the brown ox")],
 "bk4-4b": [("the man in the blue tunic at the right", "pay", "The owner of the brown ox")],
 "bk6-1a": [("the man in the brown tunic and vest in the left foreground", "notpay", "The farmer")],
 "bk6-1b": [("the man in the brown tunic and vest in the left foreground", "pay", "The farmer")],
 "bk6-2a": [("the woman in the brown dress standing on the road at the top", "pay-benefit", "The shepherd")],
 "bk6-2b": [("the woman in the brown dress standing at the top right", "pay", "The shepherd")],
 "bk6-4b": [("the man in the brown tunic at the right of the large fire", "pay", "The man who added the wood")],
 "bk6-4d": [("the man in the green tunic holding the torch at the left", "pay", "The man who brought the fire")],
 "bk6-6a": [("the man in the blue tunic at the right with his hands raised", "pay", "The camel's owner")],
 "bk6-6b": [("the woman in the red dress standing in the shop doorway at the left", "pay", "The shopkeeper")]}
only = set(sys.argv[1:]); spec = {}
for pid in PLAIN:
    if not only or pid in only: shutil.copy(G + pid + ".jpg", OUT + pid + ".jpg"); print("plain", pid)
for pid, items in TAGS.items():
    if only and pid not in only: continue
    im = rd(pid); hots = []
    top = min(bbox(im, d)["top"] for d, _, _ in items); pad = max(0, 138 - top) if top < 138 else 0
    if pad: im = pad_top(im, pad)
    hots = [person_tag(im, d, k, lab, k, 1264, 848 + pad) for d, k, lab in items]
    if pid == "bk2-3b":   # the cake's tag sat on the dog's face: move it right, clear of the dog
        hots[0]["badges"][0]["x"] = 640; hots[0]["badges"][0]["y"] = 650
        hots[1]["badges"][0]["x"] = 840; hots[1]["badges"][0]["y"] = 178   # over the sheaf, not at the picture edge
    add(pid, im, hots, "Tap " + ("a person" if len(items) == 1 else "the cake or the stack") + " to see the ruling.")
OVP = "data/overlays.json"; old = json.load(open(OVP)); old.update(_ns["spec"]); json.dump(old, open(OVP, "w"), indent=1); print("saved", len(old))
