"""Draw a cream pill badge with stacked fractions (e.g. [(1,2),(1,2)] or [(3,4),(1,4)]) in the interim cream-and-brown style.
Usage: import make(fracs) -> PIL RGBA image."""
from PIL import Image, ImageDraw, ImageFont
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
def make(fracs, scale=1.0):
    f = ImageFont.truetype(FONT, int(150 * scale)); W = int(330 * len(fracs) * scale) + 120; H = int(420 * scale)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, W - 6, H - 6], radius=H // 2, fill=(150, 105, 80, 255)); d.rounded_rectangle([34, 34, W - 34, H - 34], radius=H // 2 - 28, fill=(247, 237, 218, 255))
    col = (88, 56, 40, 255); cx0 = 60 + int(165 * scale)
    for i, (n, dn) in enumerate(fracs):
        cx = cx0 + i * int(330 * scale)
        for txt, y in ((str(n), H // 2 - int(125 * scale)), (str(dn), H // 2 + int(18 * scale))):
            w = d.textlength(txt, font=f); d.text((cx - w / 2, y - int(40 * scale)), txt, font=f, fill=col)
        d.rounded_rectangle([cx - int(75 * scale), H // 2 - 8, cx + int(75 * scale), H // 2 + 8], 8, fill=col)
        if i < len(fracs) - 1: d.rounded_rectangle([cx + int(165 * scale) - 6, 90, cx + int(165 * scale) + 6, H - 90], 6, fill=(150, 105, 80, 255))
    return im.resize((W // 3, H // 3), Image.LANCZOS)
if __name__ == "__main__":
    make([(1, 2), (1, 2)]).save("site/img/badge-half-half.png"); make([(3, 4), (1, 4)]).save("site/img/badge-3q-1q.png")
