"""Run page_layout over all of Shas, tractate by tractate in the apps' order.

    python -m page_layout.run_all                      # everything not done yet
    python -m page_layout.run_all --only Berakhot Shabbat
    python -m page_layout.run_all --redo               # redo amudim already done
    python -m page_layout.run_all --keep-images        # keep the page scans (about 2 MB each)

No API calls. Each amud goes to out/<Tractate>/<daf><amud>.json as with page_layout.run, in order
within a tractate, so each amud receives the commentary carried over from the one before.
Resumable: an amud already in out/ is skipped (and still serves as the next one's carry-in).

The scans are deleted once an amud is done, unless they were in the cache before this run: all of
Shas at full size is about 11 GB. Rerunning an amud later downloads its scan again.

Every amud is logged to page_layout/run_all.log; out/_summary.json keeps, per tractate, how many
amudim were done and which were flagged (the Gemara flags are the ones that matter on the site).
Tractates with no Bavli Gemara on Sefaria are skipped: Shekalim (Yerushalmi) and Kinnim (Mishnah
only). Tamid has no Rashi or Tosafot there, so only its Gemara is placed.
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

from . import fetch
from .run import OUT, amud_json

LOG = fetch.HERE / "run_all.log"
SUMMARY = OUT / "_summary.json"
SKIP = {"Shekalim", "Kinnim"}
# pages.json lists two tractates twice, under two spellings; the first spelling is used
DUPLICATES = {"Rosh Hashanah": "Rosh HaShanah", "Ta'anit": "Ta’anit"}


def tractate_pages() -> list[tuple[str, list[tuple[int, str]]]]:
    pages = json.loads(fetch.PAGES_JSON.read_text())
    out = []
    for t, ps in pages.items():
        if t in SKIP or t in DUPLICATES or not ps:
            continue
        nums = sorted(int(n) for n in ps)
        out.append((t, [(n // 2 + 1, "a" if n % 2 == 0 else "b") for n in nums]))
    return out


def log(msg: str):
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--keep-images", action="store_true")
    a = ap.parse_args()
    summary = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else {}
    log(f"=== run_all started {time.strftime('%Y-%m-%d %H:%M')} ===")
    for t, amudim in tractate_pages():
        if a.only and t not in [x.replace("_", " ") for x in a.only]:
            continue
        S = summary.setdefault(t, {"done": 0, "flagged": {}, "errors": {}, "no_text": []})
        t0, n_new = time.time(), 0
        for daf, amud in amudim:
            key, p = f"{daf}{amud}", OUT / t / f"{daf}{amud}.json"
            if p.exists() and not a.redo:
                continue
            img = fetch.CACHE / "img" / t / f"{key}.jpg"
            had_img = img.exists()
            try:
                if not fetch.gemara(t, daf, amud):   # no Gemara text on this amud (a tractate's last amud a)
                    S["no_text"] = sorted(set(S["no_text"]) | {key})
                    continue
                s0 = time.time()
                j = amud_json(t, daf, amud)
                if not j:
                    S["errors"][key] = "no page image"
                    continue
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")))
                fl = j["qc"]["flags"]
                if fl:
                    S["flagged"][key] = fl
                else:
                    S["flagged"].pop(key, None)
                S["errors"].pop(key, None)
                n_new += 1
                log(f"  {t} {key}: {time.time() - s0:.1f}s  {'FLAGGED: ' + '; '.join(fl) if fl else 'ok'}")
            except Exception as e:                   # one bad amud never stops the run
                S["errors"][key] = f"{type(e).__name__}: {e}"
                log(f"  {t} {key}: ERROR {type(e).__name__}: {e}")
                log("    " + traceback.format_exc().strip().splitlines()[-1])
            finally:
                if not had_img and not a.keep_images and img.exists():
                    img.unlink()
            S["done"] = len(list((OUT / t).glob("*.json"))) if (OUT / t).exists() else 0
            SUMMARY.parent.mkdir(parents=True, exist_ok=True)
            SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        gem = sum(1 for f in S["flagged"].values() if any(x.startswith("gemara") for x in f))
        log(f"{t}: {n_new} new in {(time.time() - t0) / 60:.1f} min; {S['done']}/{len(amudim)} done, "
            f"{len(S['flagged'])} flagged ({gem} on the Gemara), {len(S['errors'])} errors")
    log(f"=== run_all finished {time.strftime('%Y-%m-%d %H:%M')} ===")


if __name__ == "__main__":
    main()
