"""Composite the master payment badges onto the generated Bava Kamma 5 pictures.
Boxes are located with detect_boxes.detect; the payer tag with detect_person.find_point."""
import sys
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import detect
from detect_person import find_point
IMG = "data/generated_originals/"
PAY = Image.open("site/img/badge-pay.png"); NOT = Image.open("site/img/badge-notpay.png")
def paste(im, badge, cx, cy, d):
    b = badge.resize((d, d), Image.LANCZOS)
    sh = Image.new("RGBA", (d + 20, d + 20), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([10, 14, d + 10, d + 14], fill=(0, 0, 0, 70))
    im.paste(sh, (int(cx - d / 2 - 10), int(cy - d / 2 - 10)), sh); im.paste(b, (int(cx - d / 2), int(cy - d / 2)), b)
def box_badges(src, out, left, right, d=128):
    im, boxes = detect(IMG + src); im = im.convert("RGB")
    boxes = sorted(boxes, key=lambda b: b["left"])[:2]
    for b, kind in zip(boxes, (left, right)):
        paste(im, PAY if kind == "pay" else NOT, b["right"] - 14, b["top"] + 14, d)
    return im, boxes
def save(im, name): im.save("site/img/" + name, quality=90); print(name)
# 5:1 no badges
Image.open(IMG + "42_clean.jpg").convert("RGB").save("site/img/bk5-1.jpg", quality=90); print("bk5-1.jpg")
# 5:2a / 5:2b badge in the empty upper-right corner of the picture
for src, name, kind in (("41.jpg", "bk5-2a.jpg", "not"), ("40.jpg", "bk5-2b.jpg", "pay")):
    im = Image.open(IMG + src).convert("RGB"); W, H = im.size
    paste(im, PAY if kind == "pay" else NOT, W - 150, 130, 170); save(im, name)
# 5:5: left PAY (10), right NOT-PAY (9)
im, _ = box_badges("38.jpg", "bk5-5.jpg", "pay", "not"); save(im, "bk5-5.jpg")
# 5:6: left NOT-PAY, right PAY, plus a payer tag over the second partner
im, boxes = box_badges("39_clean.jpg", "bk5-6.jpg", "not", "pay")
pt = find_point(im, "the man in a green tunic standing with hands on his hips at the right, beside the pit's cover board (look only in the lower main scene)")
d = ImageDraw.Draw(im); tx, ty = pt["x"], pt["y"] - 18
d.polygon([(tx - 16, ty - 20), (tx + 16, ty - 20), (tx, ty)], fill=(250, 245, 230), outline=(110, 80, 60))
paste(im, PAY, tx, ty - 70, 96); save(im, "bk5-6.jpg")
