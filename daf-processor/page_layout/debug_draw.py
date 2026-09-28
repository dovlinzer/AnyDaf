"""Draw an aligned amud's lines by stream: python -m page_layout.debug_draw Tractate 12a OUT.jpg"""
import json
import sys

import cv2

from . import fetch
from .run import OUT

COL = {"gemara": (220, 90, 30), "rashi": (40, 60, 220), "tosafot": (40, 160, 40)}


def main():
    t, a, dst = sys.argv[1].replace("_", " "), sys.argv[2], sys.argv[3]
    j = json.loads((OUT / t / f"{a}.json").read_text())
    im = cv2.imread(str(fetch.CACHE / "img" / t / f"{a}.jpg"))
    for s, c in COL.items():
        for L in j[s]:
            x, y, w, h = L["box"]
            cv2.rectangle(im, (x, y), (x + w, y + h), c, 4)
            for wd in L["words"]:
                if not wd.get("text"):
                    x, y, w, h = wd["box"]
                    cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 0), 6)
    f = j["frame"]
    cv2.rectangle(im, (f["x0"], f["y0"]), (f["x1"], f["y1"]), (0, 200, 255), 6)
    k = 1000 / im.shape[1]
    cv2.imwrite(dst, cv2.resize(im, (1000, int(im.shape[0] * k))))


if __name__ == "__main__":
    main()
