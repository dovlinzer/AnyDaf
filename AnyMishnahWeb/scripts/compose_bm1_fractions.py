"""Fraction pills for BM 1:1 and 1:2. Placement rule (author): toward the TOP, where least happens in the picture.
1:1: centered on the top edge of the outcome sign board (canvas padded at the top so nothing is cut off).
1:2: centered between the two men, straddling the top frame of each box."""
import base64, io, json, sys, urllib.request
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import KEY, detect
def pill(im, bd, cx, cy, w):
    h = int(bd.height * w / bd.width); b = bd.resize((w, h), Image.LANCZOS)
    sh = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([10, 14, w + 10, h + 14], radius=h // 2, fill=(0, 0, 0, 70))
    im.paste(sh, (int(cx - w / 2 - 10), int(cy - h / 2 - 10)), sh); im.paste(b, (int(cx - w / 2), int(cy - h / 2)), b)
def sign_box(im):
    W, H = im.size; buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "b", "description": "box", "input_schema": {"type": "object", "properties": {k: {"type": "number"} for k in ("left", "top", "right", "bottom")}, "required": ["left", "top", "right", "bottom"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 300, "tools": [tool], "tool_choice": {"type": "tool", "name": "b"},
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": f"The image is {W}x{H} pixels. Give the outer pixel bounds of the square framed wooden sign board (on a post, at the upper left) that shows a white garment cut in two pieces."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return [b for b in json.load(urllib.request.urlopen(req, timeout=120))["content"] if b["type"] == "tool_use"][0]["input"]
def pad_top(im, px):
    out = Image.new("RGB", (im.width, im.height + px)); out.paste(im, (0, px))
    strip = im.crop((0, 0, im.width, 6)).resize((im.width, px), Image.BICUBIC); out.paste(strip, (0, 0)); return out, px
SRC = "data/generated_originals/bm1/"
for name, badge in (("bm1-1a", "half-half"), ("bm1-1b", "3q-1q")):
    im = Image.open(SRC + name + ".jpg").convert("RGB"); b = sign_box(im); im, off = pad_top(im, 70)
    bd = Image.open(f"site/img/badge-{badge}.png"); pill(im, bd, (b["left"] + b["right"]) / 2, b["top"] + off - 2, int((b["right"] - b["left"]) * 0.62))
    im.save(f"site/img/{name}.jpg", quality=90); print(name, b)
im, boxes = detect(SRC + "bm1-2.jpg"); im = im.convert("RGB"); bd = Image.open("site/img/badge-half-half.png")
for b in sorted(boxes, key=lambda b: b["left"])[:2]: pill(im, bd, (b["left"] + b["right"]) / 2, b["top"] - 4, 118)
im.save("site/img/bm1-2.jpg", quality=90); print("bm1-2")
