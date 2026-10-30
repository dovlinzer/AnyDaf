"""Cut a clay figure out of its white background: python3 scripts/cutout_clay.py in.jpg out.png
Flood from the picture's edges through near-white or pale grey only (so the white beard inside the figure stays), feather the edge a little, crop tight."""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFilter
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB"); W, H = im.size
work = im.copy(); MARK = (255, 0, 255)
for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (W // 2, 0), (0, H // 2), (W - 1, H // 2)]:
    if work.getpixel(seed) != MARK and min(work.getpixel(seed)) >= 215:   # white or pale grey
        ImageDraw.floodfill(work, seed, MARK, thresh=20)
bg = (np.array(work) == np.array(MARK)).all(axis=2)
fg = Image.fromarray(((~bg) * 255).astype("uint8"))
fg = fg.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))   # drop specks, pull the edge in a pixel
# keep only the figure: whatever is joined to the middle of the picture (drops specks where a faded background was missed)
mark = fg.copy(); ImageDraw.floodfill(mark, (W // 2, int(H * 0.62)), 128, thresh=0)
fg = mark.point(lambda v: 255 if v == 128 else 0)
alpha = fg.filter(ImageFilter.GaussianBlur(1.0))
rgba = im.convert("RGBA"); rgba.putalpha(alpha)
ys, xs = np.where(np.array(alpha) > 8)
rgba = rgba.crop((max(xs.min() - 2, 0), max(ys.min() - 2, 0), min(xs.max() + 3, W), min(ys.max() + 3, H)))
rgba.save(out); print(out, rgba.size)
