"""Script-only, no API — Process A's mechanical pre-filter (see CLAUDE.md, "pass 2
commentary gaps"). Measures, per micro-segment (the ### subsection unit), how much the
lecturer actually said in the SRT during that segment's time window vs how much English
prose pass 2 produced under that same display_title in 02_rewrite.md. A segment where the
lecturer spoke a lot but pass 2 wrote little prose is a candidate "wall of text" —
compressed/dropped explanatory commentary, independent of how Approach B later placed any
Gemara blockquotes (that's a separate, downstream concern, already handled by
relocate_check.py).

CALIBRATION NOTE (2026-07-31): a pure length-ratio threshold cannot reliably separate
"lecturer genuinely said little" from "essay compressed naturally verbose spoken Hebrew
into tight prose, which is fine" — Bava Metzia 11's confirmed real gap ("Critique",
spoken=7919, prose=2170) sits at ratio 0.27, while a threshold tight enough to have decent
precision (ratio<=0.15) would have missed it, and a threshold loose enough to catch it
(ratio<=0.35) flags 96% of the corpus. This script is deliberately loose/recall-oriented —
it's meant to generate CANDIDATES for a Claude verify step (the same two-stage shape as
fix_pass2_gaps.py), not to be trusted as ground truth on its own. That verify+patch stage
has not been built yet."""
import json
import re
import sys
from pathlib import Path

from srt_parser import parse_srt
from check_pass2_coverage import find_srt

OUTPUT_ROOT = Path(__file__).parent / "output"

def to_seconds(t: str) -> float:
    parts = t.split(":")
    parts = [float(p.replace(",", ".")) for p in parts]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec

def srt_entry_seconds(e) -> float:
    # "HH:MM:SS,mmm"
    h, m, rest = e.start_time.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def flat_micro_segments(seg_json):
    out = []
    for macro in seg_json.get("macro_segments", []):
        for micro in macro.get("micro_segments", []):
            out.append(micro["display_title"])
            out.append(to_seconds(micro["timestamp"]))
    # returns list of (title, start_sec) pairs interleaved -> reshape
    titles = out[0::2]
    starts = out[1::2]
    return list(zip(titles, starts))

def extract_subsection_prose(rewrite_text: str, title: str) -> str:
    # ### title ... up to next ### or ## or end
    pat = re.compile(r'^### ' + re.escape(title) + r'\s*$\n(.*?)(?=^#{2,3} |\Z)',
                      re.MULTILINE | re.DOTALL)
    m = pat.search(rewrite_text)
    return m.group(1).strip() if m else ""

def scan_daf(daf_dir: Path):
    seg_path = daf_dir / "01_segmentation.json"
    rewrite_path = daf_dir / "02_rewrite.md"
    if not seg_path.exists() or not rewrite_path.exists():
        return None
    seg_json = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
    masechta, daf, amud = seg_json.get("masechta"), seg_json.get("daf"), seg_json.get("amud")
    srt_path = find_srt(masechta, int(daf), amud)
    if not srt_path:
        return None
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not entries:
        return None
    entry_secs = [srt_entry_seconds(e) for e in entries]
    total_end = entry_secs[-1] if entry_secs else 0.0

    segs = flat_micro_segments(seg_json)
    if not segs:
        return None
    rewrite_text = rewrite_path.read_text(encoding="utf-8", errors="replace")

    results = []
    for i, (title, start) in enumerate(segs):
        end = segs[i+1][1] if i+1 < len(segs) else total_end + 1
        spoken_chars = sum(len(entries[j].text) for j, s in enumerate(entry_secs) if start <= s < end)
        prose = extract_subsection_prose(rewrite_text, title)
        prose_chars = len(prose)
        results.append((title, spoken_chars, prose_chars))
    return results

def flag(results, min_spoken=1500, max_ratio=0.35):
    return [(t, sp, pr) for t, sp, pr in results if sp >= min_spoken and (pr / sp if sp else 1) <= max_ratio]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        d = OUTPUT_ROOT / sys.argv[1]
        results = scan_daf(d)
        if results is None:
            print("no data")
        else:
            for t, sp, pr in results:
                ratio = pr / sp if sp else 0
                marker = " <== FLAG" if sp >= 1500 and ratio <= 0.35 else ""
                print(f"{t!r:35s} spoken={sp:6d} prose={pr:6d} ratio={ratio:.2f}{marker}")
    else:
        flagged_dafim = 0
        flagged_sections = 0
        rows = []
        dirs = sorted(OUTPUT_ROOT.iterdir())
        for i, d in enumerate(dirs):
            if not d.is_dir():
                continue
            try:
                results = scan_daf(d)
            except Exception:
                continue
            if not results:
                continue
            flags = flag(results)
            if flags:
                flagged_dafim += 1
                flagged_sections += len(flags)
                rows.append((d.name, flags))
        print(f"Dafim scanned with data, flagged: {flagged_dafim}")
        print(f"Total flagged sections: {flagged_sections}")
        for name, flags in rows:
            print(name, [(f[0], f[1], f[2]) for f in flags])
