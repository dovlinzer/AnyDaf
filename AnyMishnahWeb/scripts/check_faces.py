"""Finds badges and quiz chips that sit on a person's face (2026-10-13). For every picture in data/overlays.json (and overlays_older.json) it asks the vision model for the
face boxes of the people in the clean picture, then tests the badge rectangles and the quiz chips (same geometry as build_site.stage) against them.
Run: python3 scripts/check_faces.py [pid ...]   (prints overlaps; exit 1 if any). Look at what it reports, then move the badge in the overlay script."""
import base64, io, json, os, sys, urllib.request
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY
def faces(path):
    im = Image.open(path).convert("RGB"); W, H = im.size; buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "f", "description": "faces", "input_schema": {"type": "object", "properties": {"faces": {"type": "array", "items": {"type": "object", "properties": {k: {"type": "number"} for k in ("left", "top", "right", "bottom")}, "required": ["left", "top", "right", "bottom"]}}}, "required": ["faces"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 800, "tools": [tool], "tool_choice": {"type": "tool", "name": "f"}, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": f"The image is {W}x{H} pixels. List the tight pixel box of every HUMAN face visible (clay or drawn figures), including small ones in framed boxes. Not animals."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return [x for x in json.load(urllib.request.urlopen(req, timeout=120))["content"] if x["type"] == "tool_use"][0]["input"]["faces"]
def rects(spec):
    W = spec["w"]; out = []
    for i, h in enumerate(spec["hotspots"]):
        tagged = h["badges"] and h["badges"][0]["anchor"] == "bottom"
        for bd in h["badges"]:
            im = Image.open("site/img/" + bd["src"]); w = bd["w"]; hh = w * im.height / im.width
            x0 = bd["x"] - w / 2; y0 = bd["y"] - hh if bd["anchor"] == "bottom" else bd["y"] - hh / 2
            out.append((f"badge {i + 1}", x0, y0, x0 + w, y0 + hh))
        cs = 63
        if tagged:
            bd = h["badges"][0]; im = Image.open("site/img/" + bd["src"]); sc = bd["w"] / im.width; th = im.height * sc; dh = (im.height - 34) * sc
            cx = bd["x"] + 0.40 * bd["w"]; cy = bd["y"] - th + 0.12 * dh; out.append((f"chip {i + 1}", cx - cs / 2, cy - cs / 2, cx + cs / 2, cy + cs / 2))
        else:
            l, t = h["rect"][0], h["rect"][1]; out.append((f"chip {i + 1}", l + 8 * W / 600, t + 8 * W / 600, l + 8 * W / 600 + cs, t + 8 * W / 600 + cs))
    return out
CH = json.load(open('data/chip_overrides.json')) if os.path.exists('data/chip_overrides.json') else {}
bad = 0; only = set(sys.argv[1:])
for fn in ("data/overlays.json", "data/overlays_older.json"):
    if not os.path.exists(fn): continue
    for pid, spec in json.load(open(fn)).items():
        if only and pid not in only: continue
        path = "site/" + spec["clean"]
        if not os.path.exists(path) or not spec["hotspots"]: continue
        try: fc = faces(path)
        except Exception as e: print(pid, "vision failed", e); continue
        rs = rects(spec)
        for k, v in (CH.get(pid) or {}).items(): rs = [r for r in rs if r[0] != f'chip {int(k) + 1}'] + [(f'chip {int(k) + 1}', v[0] - 31, v[1] - 31, v[0] + 31, v[1] + 31)]
        for name, a, b, c, d in rs:
            for f in fc:
                ix = max(0, min(c, f["right"]) - max(a, f["left"])); iy = max(0, min(d, f["bottom"]) - max(b, f["top"])); fa = max(1, (f["right"] - f["left"]) * (f["bottom"] - f["top"]))
                if ix * iy / fa > 0.08: bad += 1; print(f"{fn.split('/')[-1][:-5]:<16}{pid:<10}{name:<9} covers {100 * ix * iy / fa:.0f}% of a face at ({int(f['left'])},{int(f['top'])})")
print(f"{bad} overlap(s)"); sys.exit(1 if bad else 0)
