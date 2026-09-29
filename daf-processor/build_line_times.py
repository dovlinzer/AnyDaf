#!/usr/bin/env python3
"""When each line of Gemara is read aloud in the shiur: the audio sync data for the web app.

Reuses v10 assembly's own matching (prototype_text_first_v10.process), which already finds these
times to place the Gemara in the written shiur but never saves them: best_match_times over the
SRT, the guarded consistent run, and the head extension. Each matched pool item is then named by
its Sefaria line label (e.g. "11a.6") by exact Hebrew against daf_text/, the same way the web page
ties the shiur's quotes to lines, since the pool's own numbering is per file, not per amud.

Lines the lecturer explained in English instead of reading aloud have no time here; the page
gives them the time of the last line read before them.

    python build_line_times.py                 # every output/ daf with a transcript
    python build_line_times.py bava_metzia_11 bekhorot_10

Local, no API. Writes outline/line_times.json: {dir: {tractate, daf, srt_end, lines: {label: s}}}.
"""
import json
import re
import sys
from pathlib import Path

from check_pass2_coverage import find_srt
from prototype_text_first_v3 import DEFAULT_THRESHOLD, best_match_times, build_pool
from prototype_text_first_v10 import extend_head_to_confident_neighbor, guarded_consistent_run
from srt_parser import parse_srt
from upload_to_supabase import parse_dir_name

HERE = Path(__file__).resolve().parent
OUT = HERE / "outline" / "line_times.json"
TEXT_NAME = {"Ta’anit": "Taanit", "Ta'anit": "Taanit"}
books: dict[str, dict] = {}


def norm_he(s: str) -> str:
    return re.sub(r"[^א-ת]", "", re.sub(r"[֑-ׇ]", "", s))


def srt_seconds(t: str) -> float:
    h, m, rest = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def labels_by_hebrew(tractate: str, daf: int) -> dict[str, str]:
    """Normalized Hebrew -> line label, for the amudim a shiur on this daf can reach."""
    name = TEXT_NAME.get(tractate, tractate)
    if name not in books:
        p = HERE / "daf_text" / f"{name}.json"
        books[name] = json.loads(p.read_text(encoding="utf-8"))["amudim"] if p.exists() else {}
    am, out = books[name], {}
    for a in (f"{daf - 1}b", f"{daf}a", f"{daf}b", f"{daf + 1}a", f"{daf + 1}b"):
        for s in (am.get(a) or {}).get("segments") or []:
            out.setdefault(norm_he(s["he"]), f"{a}.{s['n']}")
    return out


def line_times(d: Path) -> dict | None:
    try:
        seg = json.loads((d / "01_segmentation.json").read_text(errors="replace"))
    except Exception:
        return None
    masechta, sdaf = seg.get("masechta"), seg.get("daf")
    if not masechta or not sdaf or not (d / "sefaria.md").exists():
        return None
    srt = find_srt(masechta, int(sdaf), seg.get("amud"))
    if not srt:
        return None
    entries = parse_srt(srt.read_text(encoding="utf-8", errors="replace"))
    pool = build_pool(d)
    if not entries or not pool:
        return None
    raw_all = best_match_times(entries, pool, 0.0)
    kept = guarded_consistent_run([m for m in raw_all if m[2] >= DEFAULT_THRESHOLD])
    kept = extend_head_to_confident_neighbor(kept, {i: (t, s) for i, t, s in raw_all})
    tractate, daf = parse_dir_name(d.name)
    lab = labels_by_hebrew(tractate, int(daf))
    lines = {}
    for idx, t, _ in kept:
        label = lab.get(norm_he(pool[idx]["hebrew"]))
        if label and label not in lines:
            lines[label] = round(t, 1)
    return {"tractate": tractate, "daf": daf, "srt_end": round(srt_seconds(entries[-1].end_time), 1),
            "matched": len(kept), "lines": dict(sorted(lines.items(), key=lambda kv: kv[1]))}


def main():
    names = sys.argv[1:]
    dirs = [HERE / "output" / n for n in names] if names else sorted(p for p in (HERE / "output").iterdir() if p.is_dir())
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() and names else {}
    done = skipped = unnamed = 0
    for i, d in enumerate(dirs, 1):
        r = line_times(d)
        if r is None:
            skipped += 1
            continue
        unnamed += r["matched"] - len(r["lines"])
        data[d.name] = r
        done += 1
        if i % 200 == 0:
            print(f"  {i}/{len(dirs)}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    lines = sum(len(v["lines"]) for v in data.values())
    print(f"{done} dafim timed, {skipped} skipped (no transcript or sefaria.md); {lines} lines; "
          f"{unnamed} matched items with no line label. Wrote {OUT}")


if __name__ == "__main__":
    main()
