"""Erase the stray inset rectangle the model sometimes draws in a box's upper-right corner.
Usage: erase_corner_notch.py in.jpg out.jpg
Boxes are located roughly by vision (detect_boxes); everything else is pixel analysis, because the vision
coordinates can be ~60px off. Along a row just under the top frame, a notch shows as TWO frame-colored runs
(the notch's vertical line, then the right frame); no notch means one run. The notch area is then filled row
by row up to the real right frame with the median color just left of the notch."""
import sys
import numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from detect_boxes import detect
def runs(row_mask, x_from, x_to, minlen=5):
    out, start = [], None
    for x in range(x_from, x_to):
        if row_mask[x] and start is None: start = x
        if (not row_mask[x] or x == x_to - 1) and start is not None:
            if x - start >= minlen: out.append((start, x))
            start = None
    return out
def erase_in_box(a, b):
    H, W, _ = a.shape; cx = int((b["left"] + b["right"]) / 2)
    ys = list(range(max(0, int(b["top"]) - 10), int(b["top"]) + 28)); lum = [a[y, cx - 3:cx + 3].mean() for y in ys]
    y_frame = ys[int(np.argmin(lum))]; col = a[y_frame - 2:y_frame + 9, cx - 3:cx + 3].reshape(-1, 3).mean(axis=0)
    ai = a.astype(int); mask = ((ai[:, :, 0] - ai[:, :, 2]) > 42) & (ai[:, :, 0] < 232)   # clay-brown frame: saturated and not near-white
    y = y_frame
    while mask[y, cx]: y += 1
    top_inner = y; ry = top_inner + 26
    r = runs(mask[ry], cx, min(W - 1, int(b["right"]) + 90))
    if len(r) < 2: return None
    x_notch = (r[0][0] + r[0][1]) // 2; y_bot = ry
    while mask[y_bot, x_notch]: y_bot += 1
    if not (50 < y_bot - top_inner < 230): return None   # a long run is a real box frame, not a notch
    x0 = r[0][0] - 12; x_end_prev = None; last = None
    for yy in range(top_inner - 2, y_bot + 32):
        band = yy >= y_bot - 8
        if not band or x_end_prev is None:
            rr = runs(mask[yy], r[0][1] + 14, min(W - 1, int(b["right"]) + 90), minlen=3)
            x_end = rr[0][0] - 2 if rr else (x_end_prev or x0)
        else: x_end = x_end_prev
        if not band or last is None: last = np.median(a[yy, x0 - 16:x0 - 8], axis=0)   # in the line band, carry the last clean color
        if yy >= top_inner - 2 and x_end > x0: a[yy, x0:x_end] = last
        x_end_prev = x_end
    return (x0, top_inner, y_bot)
if __name__ == "__main__":
    im, boxes = detect(sys.argv[1]); a = np.array(im.convert("RGB")); boxes = sorted(boxes, key=lambda b: b["left"])[:2]
    for b in boxes: print("erased" if erase_in_box(a, b) else "no notch", b)
    Image.fromarray(a).save(sys.argv[2], quality=95)
