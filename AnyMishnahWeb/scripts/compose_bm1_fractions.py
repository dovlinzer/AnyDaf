"""Overlay the fraction pills on the two cloak pictures (BM 1:1), centered just under the outcome sign board."""
import base64, io, json, sys, urllib.request
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import KEY
def sign_box(im):
    W, H = im.size; buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "b", "description": "box", "input_schema": {"type": "object", "properties": {k: {"type": "number"} for k in ("left", "top", "right", "bottom")}, "required": ["left", "top", "right", "bottom"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 300, "tools": [tool], "tool_choice": {"type": "tool", "name": "b"},
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": f"The image is {W}x{H} pixels. Give the outer pixel bounds of the square framed wooden sign board (on a post, at the upper left) that shows a white garment cut in two pieces."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return [b for b in json.load(urllib.request.urlopen(req, timeout=120))["content"] if b["type"] == "tool_use"][0]["input"]
for name, badge in (("bm1-1a", "half-half"), ("bm1-1b", "3q-1q")):
    im = Image.open(f"data/generated_originals/bm1/{name}.jpg").convert("RGB"); b = sign_box(im); bd = Image.open(f"site/img/badge-{badge}.png")
    w = int((b["right"] - b["left"]) * 0.72); h = int(bd.height * w / bd.width); bd = bd.resize((w, h), Image.LANCZOS)
    cx = (b["left"] + b["right"]) / 2; y = int(b["bottom"] - 0.62 * h - 6)
    sh = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([10, 14, w + 10, h + 14], radius=h // 2, fill=(0, 0, 0, 70))
    im.paste(sh, (int(cx - w / 2 - 10), y - 10), sh); im.paste(bd, (int(cx - w / 2), y), bd); im.save(f"site/img/{name}.jpg", quality=90); print(name, b)
