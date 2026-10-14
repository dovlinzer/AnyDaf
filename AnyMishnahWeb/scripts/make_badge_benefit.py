"""badge-pay-benefit.png: 'pays only what it benefited' (2:2c, 6:2a): a stack of coins level with a stack of food, equal heights (author's idea, 2026-10-13).
Drawn with PIL at 4x, same disc as the other badges (156x156, cream disc, brown ring). Then run scripts/build_overlays_clay_bk1246.py for the tags."""
from PIL import Image, ImageDraw
S = 4; W = 156 * S; im = Image.new("RGBA", (W, W), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.ellipse([0, 0, W - 1, W - 1], fill=(150, 105, 80, 255)); d.ellipse([5 * S, 5 * S, W - 5 * S, W - 5 * S], fill=(244, 237, 221, 255))
base = 112 * S; top = 52 * S   # both stacks end at the same top line
def coin(cx, y, rw=17, rh=6, fill=(226, 178, 52, 255), edge=(138, 98, 20, 255)):
    d.ellipse([(cx - rw) * S, y - rh * S, (cx + rw) * S, y + rh * S], fill=fill, outline=edge, width=2 * S)
    d.rectangle([(cx - rw) * S, y - 0, (cx + rw) * S, y + 5 * S], fill=fill)
    d.arc([(cx - rw) * S, y - rh * S + 5 * S, (cx + rw) * S, y + rh * S + 5 * S], 0, 180, fill=edge, width=2 * S)
    d.line([(cx - rw) * S, y, (cx - rw) * S, y + 5 * S], fill=edge, width=2 * S); d.line([(cx + rw) * S, y, (cx + rw) * S, y + 5 * S], fill=edge, width=2 * S)
n = 0; y = base
while y > top - 2 * S:
    coin(50, y); y -= 10 * S; n += 1
# food stack: three produce pieces, same top line
def ball(cx, cy, r, fill, edge):
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=edge, width=2 * S)
ball(106, 103, 17, (116, 170, 70, 255), (62, 104, 38, 255)); d.arc([92 * S, 90 * S, 120 * S, 116 * S], 200, 340, fill=(62, 104, 38, 255), width=2 * S)
ball(94, 81, 13, (206, 60, 48, 255), (130, 30, 24, 255)); ball(118, 81, 13, (206, 60, 48, 255), (130, 30, 24, 255))
ball(106, 61, 12, (236, 164, 52, 255), (150, 98, 20, 255)); d.line([106 * S, 49 * S, 106 * S, 44 * S], fill=(90, 62, 30, 255), width=2 * S)
# level line: both stacks reach the same height
d.line([30 * S, 46 * S, 126 * S, 46 * S], fill=(110, 78, 60, 200), width=2 * S)
for x in range(34, 126, 8): pass
im.resize((156, 156), Image.LANCZOS).save("site/img/badge-pay-benefit.png"); print("saved", n, "coins")
