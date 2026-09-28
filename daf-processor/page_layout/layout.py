"""Find the page frame, the column gutters and the printed lines on a Vilna page image.

Ported from the POC's seg.py + lines.py, with the hand-set frame replaced by detection and every
pixel constant scaled by image width (the POC values assume a ~2617px-wide scan).
"""
from __future__ import annotations

import cv2
import numpy as np

REF_W = 2617


def binarize(path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    _, b = cv2.threshold(im, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return b.astype(np.uint8)


def _runs(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    """[start, end) runs of True at least min_len long."""
    m = np.concatenate([[False], mask, [False]])
    d = np.diff(m.astype(np.int8))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= min_len]


def glyph_heights(b: np.ndarray, min_area: int = 6) -> np.ndarray:
    if b.size == 0 or min(b.shape) < 2:        # OpenCV segfaults on empty input
        return np.array([])
    n, _, st, _ = cv2.connectedComponentsWithStats(np.ascontiguousarray(b), connectivity=8)
    return st[1:, 3][st[1:, 4] >= min_area] if n > 1 else np.array([])


def find_frame(b: np.ndarray) -> dict:
    """The main text frame: inside the margin columns (Ein Mishpat, Mesoret HaShas), below the running
    header, above the bottom notes. Returns x0, x1, y0, y1 plus how each edge was found."""
    H, W = b.shape
    s = W / REF_W
    how = {}
    # Left/right: the margin columns are cut off by full-height blank strips.
    # Look in the upper-middle band first: notes under the frame can run the full page width
    # across the bottom third (Bekhorot's Shita Mekubetzet) and cover the strips there.
    for lo, hi in ((.15, .5), (.2, .8), (.1, .35)):
        mid = b[int(H * lo):int(H * hi)].mean(0) < 0.004
        runs = _runs(mid, int(8 * s))
        left = [r for r in runs if 0 < r[0] and r[1] < W * 0.3 and r[0] > W * 0.05]
        right = [r for r in runs if r[0] > W * 0.7 and r[1] < W * 0.95]
        if left and right:
            break
    ink_cols = np.flatnonzero(b.mean(0) > 0.002)
    x0 = left[-1][1] if left else int(ink_cols[0])
    x1 = right[0][0] if right else int(ink_cols[-1]) + 1
    how["x"] = f"margin gutters {'found' if left else 'MISSING'}/{'found' if right else 'MISSING'}"
    # Top: skip the running header (first ink block) and the gap under it.
    rows = b[:, x0:x1].mean(1)
    ink_rows = np.flatnonzero(rows > 0.002)
    first = int(ink_rows[0])
    gaps = [g for g in _runs(rows < 0.002, int(12 * s)) if g[0] > first]
    y0 = gaps[0][1] if gaps and gaps[0][0] - first < 120 * s else first
    how["y0"] = "below header" if y0 != first else "first ink (no header found)"
    # Bottom: the notes under the frame are in smaller type, below a wide blank band.
    last = int(ink_rows[-1]) + 1
    ref_h = np.median(glyph_heights(b[y0:last, x0:x1])) if last > y0 else 0
    y1, how["y1"] = last, "last ink"
    for g0, g1 in _runs(rows < 0.002, int(20 * s)):
        if g0 < H * 0.55 or g0 <= y0:
            continue
        below = b[g1:last, x0:x1]
        gh = glyph_heights(below)
        if len(gh) and np.median(gh) < 0.85 * ref_h:
            y1, how["y1"] = g0, f"above bottom notes (glyph height {np.median(gh):.0f} vs {ref_h:.0f})"
            break
    return dict(x0=int(x0), x1=int(x1), y0=int(y0), y1=int(y1), how=how)


def gutter_mask(m: np.ndarray, s: float) -> np.ndarray:
    """Blank vertical strips between columns: white pixels in vertical white runs >= L that form strips
    >= 40px wide not touching the frame's sides (POC seg.py, vectorized with morphology)."""
    h, w = m.shape
    L, top_run, min_w = int(170 * s), int(60 * s), int(40 * s)
    white = (m == 0).astype(np.uint8)
    pad = L - top_run          # a blank run touching the top counts from 60px (POC special case)
    wp = np.vstack([np.ones((pad, w), np.uint8), white])
    gut = cv2.morphologyEx(wp, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, L)))[pad:]
    gut = cv2.morphologyEx(gut, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_w, 1)))
    g = gut.astype(bool)
    touch_l = np.cumprod(g, axis=1).astype(bool)                 # per row, the run touching the left side
    touch_r = np.cumprod(g[:, ::-1], axis=1)[:, ::-1].astype(bool)
    return g & ~touch_l & ~touch_r


def find_lines(b: np.ndarray, frame: dict) -> list[dict]:
    """Printed lines in the frame: box, median glyph height (cch: separates Gemara type from
    commentary) and the glyph boxes, in page coordinates."""
    X0, X1, Y0, Y1 = frame["x0"], frame["x1"], frame["y0"], frame["y1"]
    s = b.shape[1] / REF_W
    m = b[Y0:Y1, X0:X1].copy()
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    small = np.flatnonzero(st[:, 4] < 4)
    small = small[small > 0]
    if len(small):
        m[np.isin(lab, small)] = 0
    gut = gutter_mask(m, s)
    sm = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(45 * s)), 1)))
    sm[gut] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(sm, connectivity=4)
    comps = [list(map(int, st[i, :4])) for i in range(1, n) if st[i, 2] > 25 * s and st[i, 3] > 8 * s]

    # merge same-row fragments with a small gap
    merged = []
    for x, y, w, h in sorted(comps, key=lambda c: (c[1], c[0])):
        for M in merged:
            ox = max(0, min(y + h, M[1] + M[3]) - max(y, M[1]))
            gap = max(M[0] - (x + w), x - (M[0] + M[2]))
            if ox > 0.6 * min(h, M[3]) and gap < 45 * s:
                nx, ny = min(x, M[0]), min(y, M[1])
                M[2], M[3] = max(x + w, M[0] + M[2]) - nx, max(y + h, M[1] + M[3]) - ny
                M[0], M[1] = nx, ny
                break
        else:
            merged.append([x, y, w, h])

    # a fragment can grow into another one merged earlier; repeat until no two boxes on a row
    # overlap, or the glyphs they share are read twice (BM 2a Rashi)
    changed = True
    while changed:
        changed = False
        for a in merged:
            for b_ in merged:
                if a is b_:
                    continue
                ox = min(a[0] + a[2], b_[0] + b_[2]) - max(a[0], b_[0])
                oy = min(a[1] + a[3], b_[1] + b_[3]) - max(a[1], b_[1])
                if ox > 0 and oy > 0.5 * min(a[3], b_[3]):
                    nx, ny = min(a[0], b_[0]), min(a[1], b_[1])
                    a[2], a[3] = max(a[0] + a[2], b_[0] + b_[2]) - nx, max(a[1] + a[3], b_[1] + b_[3]) - ny
                    a[0], a[1] = nx, ny
                    merged.remove(b_)
                    changed = True
                    break
            if changed:
                break

    def cch_of(bx):
        x, y, w, h = bx[:4]
        v = glyph_heights(m[y:y + h, x:x + w])
        return float(np.median(v)) if len(v) else 0.0

    # rejoin fragments split by a whitespace "river" when a neighbouring line spans the gap
    changed = True
    while changed:
        changed = False
        for A in merged:
            for Bx in merged:
                if A is Bx or A[0] > Bx[0]:
                    continue
                ox = min(A[1] + A[3], Bx[1] + Bx[3]) - max(A[1], Bx[1])
                gap = Bx[0] - (A[0] + A[2])
                if ox <= 0.5 * min(A[3], Bx[3]) or gap < 0 or gap > 120 * s:
                    continue
                ca, cb = cch_of(A), cch_of(Bx)
                if max(ca, cb) > 1.15 * min(ca, cb):
                    continue
                u0, u1 = A[0], Bx[0] + Bx[2]
                if any(C is not A and C is not Bx and abs(C[1] - A[1]) < 70 * s
                       and C[0] <= u0 + 15 * s and C[0] + C[2] >= u1 - 15 * s for C in merged):
                    ny = min(A[1], Bx[1])
                    A[3] = max(A[1] + A[3], Bx[1] + Bx[3]) - ny
                    A[1], A[2] = ny, u1 - u0
                    merged.remove(Bx)
                    changed = True
                    break
            if changed:
                break

    def split_tall(x, y, w, h):
        sub = m[y:y + h, x:x + w]
        gh = glyph_heights(sub)
        ch = np.median(gh) if len(gh) else 0
        if not ch:
            return [(x, y, w, h)]
        pitch = int(1.72 * ch)            # line pitch ~1.7x glyph height (POC: 48/27 Gemara, 36/21 commentary)
        k = int(round(h / pitch))
        if h < 1.6 * pitch or k < 2:
            return [(x, y, w, h)]
        prof = np.convolve(sub.sum(1).astype(float), np.ones(5) / 5, "same")
        cuts = []
        for j in range(1, k):
            c = int(j * h / k)
            lo, hi = max(0, c - pitch // 3), min(h, c + pitch // 3)
            cuts.append(lo + int(np.argmin(prof[lo:hi])))
        edges = [0] + cuts + [h]
        return [(x, y + a, w, e - a) for a, e in zip(edges, edges[1:])]

    lines = []
    for bx in merged:
        for x, y, w, h in split_tall(*bx):
            sub = np.ascontiguousarray(m[y:y + h, x:x + w])
            if min(sub.shape) < 2:
                continue
            n, _, st, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
            cc = [st[i, :4] for i in range(1, n) if st[i, 4] >= 6]
            lines.append(dict(
                x=int(x + X0), y=int(y + Y0), w=int(w), h=int(h),
                cch=float(np.median([c[3] for c in cc])) if cc else 0.0,
                cc=[[int(a + x + X0), int(b_ + y + Y0), int(c), int(d)] for a, b_, c, d in cc]))
    lines.sort(key=lambda L: (L["y"], -L["x"]))
    return lines


def type_sizes(lines: list[dict]) -> tuple[float, float]:
    """(next size down, Gemara) glyph heights on this page. Absolute sizes vary between scan sets,
    and a page can carry three sizes (Bekhorot: Tosafot ~22, Rashi ~26, Gemara ~32; Kiddushin adds
    small notes), so find the peaks of the line-height histogram (weighted by line width): the
    Gemara is the largest heavy peak, and the cut sits between it and the next heavy peak below."""
    c = [(round(L["cch"]), L["w"]) for L in lines if L["cch"] > 0]
    if len(c) < 4:
        return 0.0, 0.0
    hi = max(v for v, _ in c) + 2
    h = np.zeros(hi + 2)
    for v, w in c:
        h[v] += w
    sm = np.convolve(h, [1, 2, 1], "same") / 4
    tot = sm.sum()
    peaks = [i for i in range(1, len(sm) - 1) if sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and sm[i] >= 0.015 * tot]
    if len(peaks) < 2:
        return (float(peaks[0]) if peaks else 0.0), 0.0
    gem = peaks[-1]
    below = [p for p in peaks if p < gem / 1.1]
    if not below:
        return float(gem), 0.0
    return float(below[-1]), float(gem)
