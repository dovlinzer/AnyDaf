"""Find one figure in a generated picture and draw a payer-arrow from a box's badge to it.
Usage: detect_person.py in.jpg out.png "description of the person"
Uses detect_boxes.detect for the boxes and a vision call for the person's head point."""
import base64, io, json, math, re, sys, urllib.request
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import KEY, detect
def find_point(im, desc):
    W, H = im.size; buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "pt", "description": "point", "input_schema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 300, "tools": [tool], "tool_choice": {"type": "tool", "name": "pt"},
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": f"The image is {W}x{H} pixels. Return the pixel coordinates of the top of the head of: {desc}. Look only at the large main scene in the lower part, not inside the framed boxes."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    return [b for b in r["content"] if b["type"] == "tool_use"][0]["input"]
if __name__ == "__main__":
    im, boxes = detect(sys.argv[1]); pt = find_point(im, sys.argv[3]); d = ImageDraw.Draw(im)
    b = boxes[-1]; r = 38; sx, sy = b["right"] - 10, b["top"] + 10 + r
    d.ellipse([b["right"] - 10 - r, b["top"] + 10 - r, b["right"] - 10 + r, b["top"] + 10 + r], fill=(250, 220, 90), outline=(90, 60, 20), width=4)
    tx, ty = pt["x"], pt["y"] - 25
    d.line([(sx, sy), ((sx + tx) / 2 + 60, (sy + ty) / 2), (tx, ty)], fill=(200, 30, 30), width=8, joint="curve")
    a = math.atan2(ty - (sy + ty) / 2, tx - ((sx + tx) / 2 + 60))
    d.polygon([(tx, ty), (tx - 30 * math.cos(a - .4), ty - 30 * math.sin(a - .4)), (tx - 30 * math.cos(a + .4), ty - 30 * math.sin(a + .4))], fill=(200, 30, 30))
    im.save(sys.argv[2]); print(boxes, pt)
