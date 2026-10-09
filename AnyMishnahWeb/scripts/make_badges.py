"""Cut the two clay payment badges (not-pay, pay) out of a generated picture that shows both.
Usage: make_badges.py picture.jpg  -> site/img/badge-notpay.png, badge-pay.png (circular alpha mask).
Asks a vision model for each badge's circle (center, radius)."""
import base64, io, json, sys, urllib.request
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import KEY
im = Image.open(sys.argv[1]).convert("RGB"); W, H = im.size
buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
tool = {"name": "c", "description": "circles", "input_schema": {"type": "object", "properties": {"badges": {"type": "array", "items": {"type": "object", "properties": {
    "cx": {"type": "number"}, "cy": {"type": "number"}, "radius": {"type": "number"}, "scale_state": {"type": "string", "enum": ["level_empty", "tipped_with_coins"]}}, "required": ["cx", "cy", "radius", "scale_state"]}}}, "required": ["badges"]}}
body = {"model": "claude-sonnet-4-5", "max_tokens": 500, "tools": [tool], "tool_choice": {"type": "tool", "name": "c"},
        "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": f"The image is {W}x{H} pixels. It has two round cream badges near the top, each containing a balance scale. Report each badge's outer circle: center (cx, cy) and radius in pixels, and whether its scale is level with empty pans or tipped with coins."}]}]}
req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
    headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=120))
for b in [x for x in r["content"] if x["type"] == "tool_use"][0]["input"]["badges"]:
    cx, cy, rad = b["cx"], b["cy"], b["radius"] * 1.04
    crop = im.crop((int(cx - rad), int(cy - rad), int(cx + rad), int(cy + rad))).convert("RGBA")
    mask = Image.new("L", crop.size, 0); ImageDraw.Draw(mask).ellipse([0, 0, crop.size[0] - 1, crop.size[1] - 1], fill=255)
    crop.putalpha(mask)
    name = "badge-pay.png" if b["scale_state"] == "tipped_with_coins" else "badge-notpay.png"
    crop.save("site/img/" + name); print(name, b)
