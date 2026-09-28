"""Align one or more amudim: page image + Sefaria text -> page_layout/out/<Tractate>/<daf><amud>.json

    python -m page_layout.run Yevamot 3a
    python -m page_layout.run Bava_Metzia 2a 2b 3a
    python -m page_layout.run Kiddushin 3a-12b          # a range, both amudim

No API calls. Output per amud:
  image: {drive_id, w, h}; frame; qc: per-stream alignment stats and flags;
  gemara / rashi / tosafot: lines [{box, words: [{text, box, dh, toks: [[ref, word_index], ...]}]}]
    (words with text null are printed marks with no Sefaria counterpart: catchwords, margin markers);
  segments: {ref: [[x, y, w, h], ...]} one box per printed line a Gemara segment or comment covers,
    the unit the apps highlight ('3a.4'; 'Rashi on Yevamot 3a:4:2').
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import align as A
from . import fetch, layout

OUT = fetch.HERE / "out"

# QC thresholds (POC: 0.10-0.19 per word on a clean page)
MAX_COST_PER_WORD = 0.30
MAX_SKIP_TXT = 5


def classify(lines: list[dict], frame: dict, s: float) -> dict:
    com_h, gem_h = layout.type_sizes(lines)
    if not gem_h:                         # one type size only: fall back to the POC's fixed cut
        gem_cut, col_cut = 25 * s, 23 * s
    else:                                 # POC on Yevamot 3a: sizes 21.5/27, cuts 25 and 23
        gem_cut, col_cut = com_h + 0.64 * (gem_h - com_h), com_h + 0.27 * (gem_h - com_h)
    core = [L for L in lines if L["cch"] >= gem_cut and L["w"] > 400 * s]
    gx = np.median([L["x"] for L in core]) if core else 0
    gw = np.median([L["w"] for L in core]) if core else 0
    mid = (frame["x0"] + frame["x1"]) / 2
    top = min((L["y"] for L in lines), default=0)
    for i, L in enumerate(lines):
        L["id"] = i
        # the running header (chapter and masechet name) is set larger than the Gemara
        L["header"] = bool(gem_h and L["cch"] >= 1.12 * gem_h and L["y"] < top + 0.04 * frame["y1"])
        # slivers far thinner than any type on the page are decoration cut into strips (the frame
        # around a masechet's opening word, BM 2a), not lines of text
        L["ornament"] = bool(com_h and L["h"] < 0.5 * com_h)
        in_col = core and abs(L["x"] - gx) < 40 * s and L["w"] < gw + 40 * s
        L["gem"] = bool((in_col and L["cch"] >= col_cut) or L["cch"] >= gem_cut)
        L["words"] = A.words_of(L, 0.44 * L["cch"] if L["cch"] else 10 * s)   # POC: 11px at 27, 10px at 21.5
        L["full"] = L["w"] > 0.7 * (frame["x1"] - frame["x0"])
        L["side"] = "R" if L["x"] + L["w"] / 2 > mid else "L"
    return dict(commentary=round(com_h, 1), gemara=round(gem_h, 1), gem_cut=round(gem_cut, 1))


def reading_order(ls: list[dict]) -> list[dict]:
    """Top to bottom by printed row, right to left within a row: a row found as two fragments
    (split at a marker or a whitespace river) must read right fragment first."""
    rows = []
    for L in sorted(ls, key=lambda L: L["y"] + L["h"] / 2):
        yc = L["y"] + L["h"] / 2
        if rows and abs(yc - rows[-1][0]) < 0.5 * min(L["h"], rows[-1][1]):
            rows[-1][2].append(L)
        else:
            rows.append([yc, L["h"], [L]])
    return [L for _, _, r in rows for L in sorted(r, key=lambda L: -L["x"])]


def amud_json(tractate: str, daf: int, amud: str, verbose: bool = False) -> dict | None:
    img = fetch.page_image(tractate, daf, amud)
    if not img:
        print(f"  {tractate} {daf}{amud}: no page image")
        return None
    b = layout.binarize(img)
    H, W = b.shape
    s = W / layout.REF_W
    frame = layout.find_frame(b)
    lines = layout.find_lines(b, frame)
    sizes = classify(lines, frame, s)

    pd, pa = fetch.previous_amud(daf, amud)
    pp = OUT / tractate / f"{pd}{pa}.json"          # the previous amud's own result, if aligned already
    prev_json = json.loads(pp.read_text()) if pp.exists() else None
    T = {"gemara": A.gemara_tokens(fetch.gemara(tractate, daf, amud), daf, amud)}
    for name in ("Rashi", "Tosafot"):
        prev = fetch.commentary(name, tractate, pd, pa) if pd >= 2 else []
        cin = prev_json["carry_out"].get(name.lower()) if prev_json and "carry_out" in prev_json else None
        T[name.lower()] = A.commentary_tokens(fetch.commentary(name, tractate, daf, amud), prev, cin)

    lines = [L for L in lines if not L["header"] and not L["ornament"]]
    gem = reading_order([L for L in lines if L["gem"]])
    com = [L for L in lines if not L["gem"]]
    inner, outer = ("R", "L") if amud == "a" else ("L", "R")      # Rashi sits on the inner side
    col_r = [L for L in com if not L["full"] and L["side"] == inner]
    col_t = [L for L in com if not L["full"] and L["side"] == outer]
    top_y = gem[0]["y"] if gem else frame["y0"]
    full_bot = [L for L in com if L["full"] and L["y"] > top_y]
    full_top = [L for L in com if L["full"] and L["y"] <= top_y]

    # full-width lines above and below the Gemara each belong to one commentary (whichever runs on
    # past the other's end): try every owner and keep the cheapest
    best = None
    for top_owner in (("rashi", "tosafot") if full_top else (None,)):
        for bot_owner in (("rashi", "tosafot") if full_bot else (None,)):
            def mine(o):
                return (full_top if top_owner == o else []) + (full_bot if bot_owner == o else [])
            R = reading_order(col_r + mine("rashi"))
            Tl = reading_order(col_t + mine("tosafot"))
            cr, ct = A.run(R, T["rashi"]), A.run(Tl, T["tosafot"])
            tot = cr["cost"] + ct["cost"]
            if best is None or tot < best[0]:
                best = (tot, (top_owner, bot_owner), R, Tl, cr, ct)
    _, owner, R, Tl, cr, ct = best
    cg = A.run(gem, T["gemara"])

    out = dict(tractate=tractate, daf=daf, amud=amud,
               image=dict(drive_id=fetch.drive_id(tractate, daf, amud), w=W, h=H),
               frame={k: v for k, v in frame.items() if k != "how"},
               qc=dict(frame=frame["how"], type_sizes=sizes, full_width_owner=dict(top=owner[0], bottom=owner[1])),
               segments={})
    flags = []
    for name, sl, res in (("gemara", gem, cg), ("rashi", R, cr), ("tosafot", Tl, ct)):
        out[name] = A.to_lines(sl, T[name], res)
        st = A.stats(res, T[name])
        out["qc"][name] = st
        if st["cost_per_word"] > MAX_COST_PER_WORD:
            flags.append(f"{name} cost/word {st['cost_per_word']}")
        if st["skip_txt"] > MAX_SKIP_TXT:
            flags.append(f"{name} {st['skip_txt']} text words not placed")
        if not sl and T[name]:
            flags.append(f"{name}: no lines found")
    out["qc"]["flags"] = flags
    out["qc"]["carry_in"] = "from the previous amud's result" if prev_json and "carry_out" in prev_json else "estimated"
    out["carry_out"] = {"rashi": A.carry_out(cr, T["rashi"]), "tosafot": A.carry_out(ct, T["tosafot"])}

    # one box per (ref, printed line): what the apps highlight
    seg = defaultdict(list)
    for name in ("gemara", "rashi", "tosafot"):
        for L in out[name]:
            per = defaultdict(list)
            for w in L["words"]:
                for ref, _ in w.get("toks") or []:
                    per[ref].append(w["box"])
            for ref, boxes in per.items():
                x0 = min(b_[0] for b_ in boxes); x1 = max(b_[0] + b_[2] for b_ in boxes)
                seg[ref].append([x0, L["box"][1], x1 - x0, L["box"][3]])
    out["segments"] = dict(seg)

    if verbose:
        for name in ("gemara", "rashi", "tosafot"):
            print(f"    {name:8s} {out['qc'][name]}")
    return out


def parse_amudim(args: list[str]) -> list[tuple[int, str]]:
    out = []
    for a in args:
        m = re.fullmatch(r"(\d+)([ab])(?:-(\d+)([ab]))?", a)
        if not m:
            sys.exit(f"bad amud {a!r}")
        d0, a0 = int(m.group(1)), m.group(2)
        if not m.group(3):
            out.append((d0, a0)); continue
        d1, a1 = int(m.group(3)), m.group(4)
        d, am = d0, a0
        while (d, am) <= (d1, a1):
            out.append((d, am))
            d, am = (d, "b") if am == "a" else (d + 1, "a")
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    tractate = sys.argv[1].replace("_", " ")
    for daf, amud in parse_amudim(sys.argv[2:]):
        t0 = time.time()
        j = amud_json(tractate, daf, amud, verbose=True)
        if not j:
            continue
        p = OUT / tractate / f"{daf}{amud}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")))
        fl = j["qc"]["flags"]
        print(f"  {tractate} {daf}{amud}: {time.time() - t0:.1f}s  {'FLAGGED: ' + '; '.join(fl) if fl else 'ok'}")


if __name__ == "__main__":
    main()
