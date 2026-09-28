"""Align the known Sefaria text to the printed words on a page, using word widths only (no OCR).

POC align.py, generalized:
  * every token carries its Sefaria ref and word index, so each box links to the text and the
    line labels the outlines and shiurim use (Gemara '3a.4'; 'Rashi on Yevamot 3a:4:2');
  * amud aleph/bet: Rashi is on the inner side, right on aleph and left on bet;
  * carry-overs: the previous amud's last comment is put in front of each commentary and may be
    skipped for free (only its tail is printed here), and this amud's last comment may be cut off
    for free (its tail is printed on the next amud);
  * the DP is vectorized per row (same recurrence as the POC; ~100x faster).
"""
from __future__ import annotations

import math
import re

import numpy as np

# letter-width weights (POC)
WID = {c: 0.45 for c in "יוןז'׳"}
WID.update({c: 0.7 for c in "גנ"})
WID.update({c: 0.3 for c in '.:,;"״-'})
WID.update({c: 0.45 for c in "()[]"})
WID.update({c: 1.15 for c in "משםטצע"})

SKIP_IMG, SKIP_TXT, SPLIT, GAP = 1.6, 1.6, 0.5, 0.35


def pw(tok: str, bold: bool = False) -> float:
    return sum(WID.get(c, 1.0) for c in tok) * (1.25 if bold else 1.0)


# ---------- text tokens ----------
def gemara_tokens(segments: list[str], daf: int, amud: str) -> list[dict]:
    toks = []
    for si, seg in enumerate(segments, 1):
        seg = re.sub(r"\([^)]*\)", " ", seg)          # Sefaria's verse refs; the print has superscript marks
        for wi, t in enumerate(seg.split()):
            toks.append(dict(t=t, w=pw(t), dh=False, ref=f"{daf}{amud}.{si}", wi=wi))
    return toks


def comment_tokens(ref: str, text: str, **flags) -> list[dict]:
    dh, sep, body = text.partition(" - ")
    if not sep:
        dh, body = "", text
    out, wi = [], 0
    dw = dh.split()
    if dw:
        dw[-1] += "."                                   # the print ends a dibur hamatchil with a period
    for t in dw:
        out.append(dict(t=t, w=pw(t, True), dh=True, ref=ref, wi=wi, **flags)); wi += 1
    for t in body.split():
        out.append(dict(t=t, w=pw(t), dh=False, ref=ref, wi=wi, **flags)); wi += 1
    return out


CARRY = 3   # how many comments may run over an amud break (BM 11a: the last two both do)


TAIL_COST = 0.3   # per token left for the next amud: without it a whole column can shift for free


def commentary_tokens(comments: list[tuple[str, str]], carried: list[tuple[str, str]],
                      carry_in: dict | None = None) -> list[dict]:
    """What may be printed here, in order.
    carry_in (the previous amud's recorded carry_out, {ref: first unplaced word}) known: exactly those
    words go in front and must be placed like any other text. Unknown (previous amud not aligned):
    the previous amud's last CARRY comments go in front as lead, free to skip as an opening run.
    This amud's last CARRY comments are flagged tail: they may run on to the next amud."""
    toks = []
    if carry_in is not None:
        for ref, text in carried:
            if ref in carry_in:
                toks += comment_tokens(ref, text)[carry_in[ref]:]
    else:
        for ref, text in carried[-CARRY:]:
            toks += comment_tokens(ref, text, lead=True)
    for k, (ref, text) in enumerate(comments):
        toks += comment_tokens(ref, text, tail=(k >= len(comments) - CARRY))
    return toks


# ---------- image words ----------
def words_of(L: dict, thr: float) -> list[dict]:
    iv = sorted((c[0], c[0] + c[2], c[1], c[1] + c[3]) for c in L["cc"])
    if not iv:
        return []
    out, cur = [], list(iv[0])
    for a, b, y0, y1 in iv[1:]:
        if a - cur[1] <= thr:
            cur[1] = max(cur[1], b); cur[2] = min(cur[2], y0); cur[3] = max(cur[3], y1)
        else:
            out.append(cur); cur = [a, b, y0, y1]
    out.append(cur)
    out.sort(key=lambda w: -w[0])                      # right-to-left reading order
    return [dict(x0=w[0], x1=w[1], y0=w[2], y1=w[3], w=w[1] - w[0], line=L["id"]) for w in out]


# ---------- DP ----------
def align(imgw: list[dict], toks: list[dict], scale: float):
    """Minimum-cost alignment of image words to tokens. Moves: skip an image word, skip a token,
    or match a image words (1-2, on one line) to k tokens (1-3; 2 image words only to 1 token).
    Tokens flagged lead are free to skip at the start; tokens flagged tail free to leave unplaced at
    the end. Returns (cost, pairs) with pairs [(image idxs, token idxs)] in order."""
    n, m = len(imgw), len(toks)
    iw = np.array([w["w"] for w in imgw], float)
    tw = np.array([t["w"] for t in toks], float)
    # S[j] = cost of skipping tokens 0..j-1. Carried-in (lead) tokens are free to skip only as the
    # opening run before anything is placed (row 0); after that every skip costs the same.
    S = np.concatenate([[0.0], np.cumsum(np.full(m, SKIP_TXT))])
    S0 = np.concatenate([[0.0], np.cumsum([0.0 if t.get("lead") else SKIP_TXT for t in toks])])
    T = np.concatenate([[0.0], np.cumsum(tw)])
    INF = 1e18
    D = np.full((n + 1, m + 1), INF)
    D[0] = S0
    choice = np.zeros((n + 1, m + 1), np.int8)          # 0: skip image word; 1..: MOVES index + 1
    src = np.zeros((n + 1, m + 1), np.int32)            # column the row's best entry came from
    src[0] = 0
    MOVES = [(a, k) for a in (1, 2) for k in (1, 2, 3) if not (a == 2 and k != 1)]
    J = np.arange(m + 1)
    for i in range(1, n + 1):
        C = D[i - 1] + SKIP_IMG
        ch = np.zeros(m + 1, np.int8)
        for mi, (a, k) in enumerate(MOVES):
            if a > i or (a == 2 and imgw[i - 1]["line"] != imgw[i - 2]["line"]):
                continue
            wi = iw[i - a:i].sum()
            js = J[k:]
            wt = (T[js] - T[js - k] + GAP * (k - 1)) * scale
            c = D[i - a, js - k] + np.abs(np.log(wi / wt)) * 2 + SPLIT * ((a - 1) + (k - 1))
            better = c < C[k:]
            C[k:][better] = c[better]
            ch[k:][better] = mi + 1
        # then optional token skips: D[i,j] = min_{q<=j} C[q] + S[j] - S[q]
        v = C - S
        idx = np.zeros(m + 1, np.int64)
        best = np.minimum.accumulate(v)
        # argmin positions of the running minimum
        is_new = np.concatenate([[True], v[1:] < best[:-1]])
        pos = np.where(is_new, J, 0)
        idx = np.maximum.accumulate(pos)
        D[i] = best + S
        src[i] = idx
        choice[i] = ch
    # end: this amud's last comment may run on to the next amud
    tail_ok = [j for j in range(m + 1) if all(toks[q].get("tail") for q in range(j, m))]
    j_end = min(tail_ok, key=lambda j: D[n, j] + TAIL_COST * (m - j))
    cost = D[n, j_end] + TAIL_COST * (m - j_end)
    pairs = [([], [q]) for q in range(m - 1, j_end - 1, -1)]  # left for the next amud
    i, j = n, j_end
    while i > 0:
        q = int(src[i, j])
        for t in range(j - 1, q - 1, -1):
            pairs.append(([], [t]))
        j = q
        c = choice[i, j]
        if c == 0:
            pairs.append(([i - 1], [])); i -= 1
        else:
            a, k = MOVES[c - 1]
            pairs.append((list(range(i - a, i)), list(range(j - k, j)))); i -= a; j -= k
    for t in range(j - 1, -1, -1):
        pairs.append(([], [t]))
    return float(cost), pairs[::-1]


def run(stream_lines: list[dict], toks: list[dict]):
    imgw = [w for L in stream_lines for w in L["words"]]
    if not imgw or not toks:
        return dict(cost=float("inf"), per_word=float("inf"), pairs=[], imgw=imgw, scale=0)
    # first guess from median widths: unaffected by how much carried-in text is printed here
    scale = float(np.median([w["w"] for w in imgw]) / np.median([t["w"] for t in toks]))
    for _ in range(2):                                   # refit the scale from 1:1 matches
        cost, pairs = align(imgw, toks, scale)
        r = [imgw[I[0]]["w"] / toks[J[0]]["w"] for I, J in pairs if len(I) == 1 and len(J) == 1]
        if r:
            scale = float(np.median(r))
    cost, pairs = align(imgw, toks, scale)
    return dict(cost=cost, per_word=cost / max(1, len(imgw)), pairs=pairs, imgw=imgw, scale=scale)


def stats(res: dict, toks: list[dict]) -> dict:
    pr = res["pairs"]
    lead_skipped = sum(1 for I, J in pr if not I and J and toks[J[0]].get("lead"))
    tail_left = sum(1 for I, J in pr if not I and J and toks[J[0]].get("tail") and
                    all(not I2 for I2, J2 in pr if J2 and J2[0] > J[0]))
    return dict(
        img_words=len(res["imgw"]), tokens=len(toks),
        one_to_one=sum(1 for I, J in pr if len(I) == 1 and len(J) == 1),
        skip_img=sum(1 for I, J in pr if not J),
        skip_txt=sum(1 for I, J in pr if not I and J) - lead_skipped - tail_left,
        carried_in=sum(1 for I, J in pr if I and J and toks[J[0]].get("lead")),
        left_for_next=tail_left,
        cost_per_word=round(res["per_word"], 3))


def to_lines(stream_lines: list[dict], toks: list[dict], res: dict) -> list[dict]:
    imgw = res["imgw"]
    out = {L["id"]: dict(box=[L["x"], L["y"], L["w"], L["h"]], words=[]) for L in stream_lines}
    for I, J in res["pairs"]:
        if not I:
            continue
        x0 = min(imgw[x]["x0"] for x in I); x1 = max(imgw[x]["x1"] for x in I)
        y0 = min(imgw[x]["y0"] for x in I); y1 = max(imgw[x]["y1"] for x in I)
        w = dict(box=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)])
        if J:
            w.update(text=" ".join(toks[q]["t"] for q in J), dh=any(toks[q]["dh"] for q in J),
                     toks=[[toks[q]["ref"], toks[q]["wi"]] for q in J])
        else:
            w.update(text=None)                            # a printed mark with no Sefaria counterpart
        out[imgw[I[0]]["line"]]["words"].append(w)
    return [out[L["id"]] for L in stream_lines]


def carry_out(res: dict, toks: list[dict]) -> dict:
    """{ref: first word index left for the next amud}: the trailing unplaced tail tokens."""
    out = {}
    for I, J in reversed(res["pairs"]):
        if I:
            break
        for q in J:
            if toks[q].get("tail"):
                r = toks[q]["ref"]
                out[r] = min(out.get(r, 10 ** 9), toks[q]["wi"])
    return out
