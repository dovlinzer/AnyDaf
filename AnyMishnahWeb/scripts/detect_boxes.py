"""Ask a vision model where the two framed boxes are in a generated picture; draw a test badge
at each box's upper-right corner. Usage: detect_boxes.py in.jpg out.png
Key: ANTHROPIC_API_KEY from AnyYCTorah's content_index/.env (never printed)."""
import base64, io, json, re, sys, urllib.request
from PIL import Image, ImageDraw
ENV = "/Users/dovlinzer/claudecode/AnyYCTorah/scripts/content_index/.env"
KEY = re.search(r"^ANTHROPIC_API_KEY=(.+)$", open(ENV).read(), re.M).group(1).strip().strip('"\'')
def detect(path):
    im = Image.open(path).convert("RGB"); W, H = im.size
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "boxes", "description": "report boxes", "input_schema": {"type": "object", "properties": {"boxes": {"type": "array", "items": {"type": "object", "properties": {
        "left": {"type": "number"}, "top": {"type": "number"}, "right": {"type": "number"}, "bottom": {"type": "number"}}, "required": ["left", "top", "right", "bottom"]}}}, "required": ["boxes"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 600, "tools": [tool], "tool_choice": {"type": "tool", "name": "boxes"},
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
                {"type": "text", "text": f"The image is {W}x{H} pixels. Find the framed rounded rectangles (picture boxes) floating in the upper part. Report each one's outer frame edges in pixel coordinates (left, top, right, bottom), left to right."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    return im, [b for b in r["content"] if b["type"] == "tool_use"][0]["input"]["boxes"]
if __name__ == "__main__":
    im, boxes = detect(sys.argv[1]); d = ImageDraw.Draw(im)
    for b in boxes:
        d.rectangle([b["left"], b["top"], b["right"], b["bottom"]], outline=(255, 0, 255), width=3)
        r = 38; cx, cy = b["right"] - 10, b["top"] + 10
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 220, 90), outline=(90, 60, 20), width=4)
    im.save(sys.argv[2]); print(boxes)
