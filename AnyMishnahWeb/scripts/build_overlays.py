"""Build the interactive-overlay data: clean (badge-free) pictures in site/img/clean/ and data/overlays.json.
For each picture: hotspots (click targets, in % of the picture) and the badges each one reveals, with the correct answer
kept in the data so a drag-the-badge game can use it later. Coordinates come from vision calls (boxes, people, animals);
positions follow the placement rule: toward the top, clear of faces and hands, between two people for a split."""
import base64, io, json, os, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from detect_boxes import KEY, detect
G = "data/generated_originals/"; B = G + "bm1/"; OUT = "site/img/"; os.makedirs(OUT + "clean", exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
def bbox(im, desc):
    W, H = im.size; buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    tool = {"name": "b", "description": "box", "input_schema": {"type": "object", "properties": {k: {"type": "number"} for k in ("left", "top", "right", "bottom")}, "required": ["left", "top", "right", "bottom"]}}
    body = {"model": "claude-sonnet-4-5", "max_tokens": 300, "tools": [tool], "tool_choice": {"type": "tool", "name": "b"},
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": f"The image is {W}x{H} pixels. Give the tight pixel bounding box of: {desc}. Look only at the large main scene unless the description says otherwise."}]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return [x for x in json.load(urllib.request.urlopen(req, timeout=120))["content"] if x["type"] == "tool_use"][0]["input"]
def pad_top(im, px):
    out = Image.new("RGB", (im.width, im.height + px)); out.paste(im, (0, px)); out.paste(im.crop((0, 0, im.width, 6)).resize((im.width, px), Image.BICUBIC), (0, 0)); return out
def make_tag(kind):   # disc with a small pointer below; anchor = pointer tip
    d = Image.open(f"{OUT}badge-{kind}.png").convert("RGBA"); S = d.width; im = Image.new("RGBA", (S, S + 34), (0, 0, 0, 0)); im.paste(d, (0, 0), d)
    ImageDraw.Draw(im).polygon([(S // 2 - 15, S - 3), (S // 2 + 15, S - 3), (S // 2, S + 32)], fill=(247, 237, 218, 255), outline=(150, 105, 80, 255)); im.save(f"{OUT}tag-{kind}.png")
def make_frac_pay(n, dn, name):   # pay-scale disc + fraction, in one pill
    s = 3; H = 150 * s; W = 330 * s; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, W - 6, H - 6], radius=H // 2, fill=(150, 105, 80, 255)); d.rounded_rectangle([30, 30, W - 30, H - 30], radius=H // 2 - 24, fill=(247, 237, 218, 255))
    ic = Image.open(f"{OUT}badge-pay.png").convert("RGBA").resize((H - 70, H - 70), Image.LANCZOS); im.paste(ic, (40, 35), ic)
    f = ImageFont.truetype(FONT, 150 * s // 3 * 2 // 2 + 40); cx = H - 70 + 40 + (W - (H - 70 + 40)) // 2 - 10; col = (88, 56, 40, 255)
    for txt, y in ((str(n), 18 * s), (str(dn), 74 * s)):
        w = d.textlength(txt, font=f); d.text((cx - w / 2, y), txt, font=f, fill=col)
    d.rounded_rectangle([cx - 38 * s, H // 2 - 5, cx + 38 * s, H // 2 + 5], 5, fill=col); im.resize((W // 3, H // 3), Image.LANCZOS).save(f"{OUT}{name}.png")
for k in ("pay", "notpay", "keeps", "noclaim", "noreturn"): make_tag(k)
make_frac_pay(1, 2, "badge-pay-half"); make_frac_pay(1, 4, "badge-pay-quarter")
def box_hot(boxes, kinds, labels, answers, d=104, corner=True, top_center=False, pill=None):
    hots = []
    for b, k, lab, ans in zip(sorted(boxes, key=lambda b: b["left"])[:2], kinds, labels, answers):
        if top_center: bd = {"src": pill, "x": (b["left"] + b["right"]) / 2, "y": b["top"] - 4, "w": 118, "anchor": "center"}
        else: bd = {"src": f"badge-{k}.png", "x": b["right"] - 14, "y": b["top"] + 14, "w": d, "anchor": "center"}
        hots.append({"label": lab, "rect": [b["left"], b["top"], b["right"], b["bottom"]], "badges": [bd], "answer": ans})
    return hots
def whole(W, H, kind, label, ans, x=None, y=None, d=160):
    return [{"label": label, "rect": [0, 0, W, H], "badges": [{"src": f"badge-{kind}.png", "x": x if x is not None else W - 150, "y": y if y is not None else 100, "w": d, "anchor": "center"}], "answer": ans}]
def person_tag(im, desc, kind, label, ans, W, H, d=104, anchor_top=True, side=None, dy=0):
    r = bbox(im, desc); cx = (r["left"] + r["right"]) / 2
    if side: b = {"src": f"badge-{kind}.png", "x": r["right"] + side, "y": r["top"] + 40 + dy, "w": d, "anchor": "center"}
    else: b = {"src": f"tag-{kind}.png", "x": cx, "y": r["top"] - 8 + dy, "w": d, "anchor": "bottom"}
    return {"label": label, "rect": [r["left"] - 10, r["top"] - 10, r["right"] + 10, r["bottom"] + 10], "badges": [b], "answer": ans}
spec = {}
def add(pid, im, hots, hint):
    W, H = im.size; im.save(f"{OUT}clean/{pid}.jpg", quality=90)
    spec[pid] = {"clean": f"img/clean/{pid}.jpg", "w": W, "h": H, "hint": hint, "hotspots": hots}; print(pid, len(hots))
# ---- Bava Kamma 5
im = Image.open(G + "42_clean.jpg").convert("RGB"); W, H = im.size
cow = bbox(im, "the large dead cow lying on her back on the left (whole body including legs)"); calf = bbox(im, "the small dead calf lying on its back at the lower middle")
add("bk5-1", im, [
  {"label": "The cow: what the owner of the ox pays", "rect": [cow["left"], cow["top"], cow["right"], cow["bottom"]], "badges": [{"src": "badge-pay-half.png", "x": 525, "y": 548, "w": 185, "anchor": "center"}], "answer": "pay-half"},
  {"label": "The calf: what the owner of the ox pays", "rect": [calf["left"], calf["top"], calf["right"], calf["bottom"]], "badges": [{"src": "badge-pay-quarter.png", "x": 618, "y": 738, "w": 160, "anchor": "center"}], "answer": "pay-quarter"}],
  "Tap the cow and the calf to see what the owner of the ox pays for each.")
add("bk5-2a", Image.open(G + "41.jpg").convert("RGB"), whole(1264, 848, "notpay", "Show the ruling", "notpay"), "Tap the picture to see the ruling.")
add("bk5-2b", Image.open(G + "40.jpg").convert("RGB"), whole(1264, 848, "pay", "Show the ruling", "pay"), "Tap the picture to see the ruling.")
im = Image.open(G + "38.jpg").convert("RGB"); _, bx = detect(G + "38.jpg")
add("bk5-5", im, box_hot(bx, ["pay", "notpay"], ["The pit of ten handbreadths", "The pit of nine handbreadths"], ["pay", "notpay"]), "Tap each box to see whether he pays.")
im = Image.open(G + "39_clean.jpg").convert("RGB"); _, bx = detect(G + "39_clean.jpg")
hots = box_hot(bx, ["notpay", "pay"], ["Covered pit", "Open pit"], ["notpay", "pay"])
hots.append(person_tag(im, "the man in a green tunic standing with hands on his hips, in the main scene at the lower right of centre", "pay", "Who pays?", "pay", 1264, 848))
add("bk5-6", im, hots, "Tap each box, and the man in green, to see who pays.")
# ---- Bava Metzia 1
for pid, kind_pill in (("bm1-1a", "half-half"), ("bm1-1b", "3q-1q")):
    raw = Image.open(B + pid + ".jpg").convert("RGB"); im = pad_top(raw, 70); sb = bbox(raw, "the square framed wooden sign board (on a post, at the upper left) showing a white garment cut in two pieces")
    cx = (sb["left"] + sb["right"]) / 2
    add(pid, im, [{"label": "How the cloak is divided", "rect": [sb["left"], sb["top"] + 70, sb["right"], sb["bottom"] + 70], "badges": [{"src": f"badge-{kind_pill}.png", "x": cx, "y": sb["top"] + 70 - 2, "w": int((sb["right"] - sb["left"]) * 0.62), "anchor": "center"}], "answer": kind_pill}], "Tap the sign to see how the cloak is divided.")
im = Image.open(B + "bm1-2.jpg").convert("RGB"); _, bx = detect(B + "bm1-2.jpg")
add("bm1-2", im, box_hot(bx, ["", ""], ["They swear, then split it", "They agree, then split it"], ["half-half", "half-half"], top_center=True, pill="badge-half-half.png"), "Tap each box to see how it is split.")
for pid, kind, lab, ans in (("bm1-3a", "keeps", "Does he keep it?", "keeps"), ("bm1-3b", "noclaim", "Does he keep it?", "noclaim")):
    im = Image.open(B + pid + ".jpg").convert("RGB"); add(pid, im, [person_tag(im, "the bald man in an orange tunic standing on the right", kind, lab, ans, 1264, 848)], "Tap the man in orange to see the ruling.")
for pid, kind in (("bm1-4a", "keeps"), ("bm1-4b", "noclaim")):
    im = Image.open(B + pid + ".jpg").convert("RGB"); add(pid, im, [person_tag(im, "the field's owner wearing a straw hat and brown tunic with a grey moustache, hand on his chest", kind, "Does the field acquire it?", kind, 1264, 848)], "Tap the field's owner to see the ruling.")
for pid, desc in (("bm1-5a", "the grey-bearded father seated at the table on the left (including his head)"), ("bm1-5b", "the woman in the green dress standing on the right")):
    raw = Image.open(B + pid + ".jpg").convert("RGB"); im = pad_top(raw, 90); r = bbox(raw, desc); cx = (r["left"] + r["right"]) / 2
    add(pid, im, [{"label": "Who keeps what is found?", "rect": [r["left"] - 10, r["top"] + 80, r["right"] + 10, r["bottom"] + 100], "badges": [{"src": "tag-keeps.png", "x": cx, "y": r["top"] + 90 - 8, "w": 104, "anchor": "bottom"}], "answer": "keeps"}], "Tap the person to see who keeps it.")
im = Image.open(B + "bm1-7.jpg").convert("RGB")
add("bm1-7", im, [person_tag(im, "the man in the orange tunic standing at the bottom centre holding a scroll", "noreturn", "Should he return it?", "noreturn", 1264, 848, d=110, side=150, dy=0)], "Tap the man in orange to see the ruling.")
json.dump(spec, open("data/overlays.json", "w"), indent=1); print("saved", len(spec))
