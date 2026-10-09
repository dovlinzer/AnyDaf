"""Composite interim badges onto the Bava Metzia 1 pictures and write them to site/img/bm1-*.jpg.
Payer-tag style: a badge floats above the head of the person it concerns (found with detect_person.find_point);
box layouts get the badge at each box's upper-right corner (detect_boxes)."""
import sys
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import detect
from detect_person import find_point
SRC = "data/generated_originals/bm1/"
def badge(n): return Image.open(f"site/img/badge-{n}.png")
def paste(im, b, cx, cy, d):
    b = b.resize((d, d), Image.LANCZOS)
    sh = Image.new("RGBA", (d + 20, d + 20), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([10, 14, d + 10, d + 14], fill=(0, 0, 0, 70))
    im.paste(sh, (int(cx - d / 2 - 10), int(cy - d / 2 - 10)), sh); im.paste(b, (int(cx - d / 2), int(cy - d / 2)), b)
def tag_person(name, kind, desc, d=110):
    im = Image.open(SRC + name + ".jpg").convert("RGB"); pt = find_point(im, desc); tx, ty = pt["x"], pt["y"] - 16
    ImageDraw.Draw(im).polygon([(tx - 16, ty - 24), (tx + 16, ty - 24), (tx, ty)], fill=(250, 245, 230), outline=(110, 80, 60))
    paste(im, badge(kind), tx, max(d / 2 + 6, ty - 24 - d / 2), d); im.save(f"site/img/{name}.jpg", quality=90); print(name)
def box_badges(name, kinds, d=104):
    im, boxes = detect(SRC + name + ".jpg"); im = im.convert("RGB")
    for b, k in zip(sorted(boxes, key=lambda b: b["left"])[:2], kinds): paste(im, badge(k), b["right"] - 14, b["top"] + 14, d)
    im.save(f"site/img/{name}.jpg", quality=90); print(name)
for n in ("bm1-1a", "bm1-1b", "bm1-2"): Image.open(SRC + n + ".jpg").convert("RGB").save(f"site/img/{n}.jpg", quality=90); print(n)
tag_person("bm1-3a", "keeps", "the bald man in an orange tunic who is hugging a leather purse (on the right)")
tag_person("bm1-3b", "noclaim", "the bald man in an orange tunic standing on the right with a hand on his chest")
tag_person("bm1-4a", "keeps", "the man wearing a straw hat with a grey moustache, standing in the middle of the field, hand on his chest")
tag_person("bm1-4b", "noclaim", "the man wearing a straw hat with a grey moustache, standing in the middle of the field, hand on his chest")
box_badges("bm1-5", ["keeps", "keeps"])
tag_person("bm1-7", "noreturn", "the man in a brown tunic at the bottom center holding up a rolled document")
