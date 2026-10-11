"""Render every picture with all of its badges revealed (what 'Show all' shows), to check positions at full size.
Usage: preview_overlays.py pid [pid ...]  -> scratch sheet path printed."""
import json, sys
from PIL import Image
spec = json.load(open("data/overlays.json")); ids = sys.argv[1:] or list(spec)
ims = []
for pid in ids:
    sp = spec[pid]; im = Image.open("site/" + sp["clean"]).convert("RGBA")
    for h in sp["hotspots"]:
        for b in h["badges"]:
            t = Image.open("site/img/" + b["src"]).convert("RGBA"); w = int(b["w"]); t = t.resize((w, int(t.height * w / t.width)), Image.LANCZOS)
            x = int(b["x"] - t.width / 2); y = int(b["y"] - (t.height / 2 if b["anchor"] == "center" else t.height)); im.alpha_composite(t, (max(0, x), max(0, y)))
    ims.append(im.convert("RGB"))
w = 760; ims = [i.resize((w, int(i.height * w / i.width))) for i in ims]; H = max(i.height for i in ims)
cols = 2; rows = (len(ims) + 1) // 2; s = Image.new("RGB", (w * cols + 10, (H + 10) * rows), (255, 255, 255))
for k, i in enumerate(ims): s.paste(i, ((k % cols) * (w + 10), (k // cols) * (H + 10)))
out = "/private/tmp/claude-501/-Users-dovlinzer-claudecode-AnyYCTorah/2ada617c-4f4a-473c-8bec-fd27cf024560/scratchpad/ov_preview.png"; s.save(out); print(out)
