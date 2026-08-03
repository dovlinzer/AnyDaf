#!/usr/bin/env python3
"""
widen_sefaria_next.py — one-time backfill for jobs whose own shiur content is anchored
at (or spans through) a daf's amud b (segmentation.json amud in {'b', 'a-b'}).

Root cause (see AnyDaf/CLAUDE.md, "sefaria_next.md look-ahead" / yevamot_33): the pipeline's
"next daf" context fetch (_get_sefaria_next_head / fetch_daf_head) only ever pulls the
following daf's amud A, never amud B. For a job whose own content ends at amud B, that is
only ONE amud of forward buffer -- if the shiur runs a full extra amud past the boundary
(confirmed live on Yevamot 33/33b, whose discussion of Rava's statement to Rav Nachman and
the Er/Onan sugya sits on 34b, one amud past what was ever fetched), the source text simply
isn't there for v10 to insert, with no error -- it looks like a normal, complete essay.

Fix: for every job with amud in ('b', 'a-b'), replace sefaria_next.md with fetch_daf_text()
(both amudim of the next daf) instead of fetch_daf_head() (amud A only). Free -- Sefaria API
only, no LLM calls. Original content is preserved as .bak_before_amud_b_widen (once).

Usage:
    python widen_sefaria_next.py --dry-run           # just report what would change
    python widen_sefaria_next.py                     # run for real
    python widen_sefaria_next.py output/yevamot_33 output/yevamot_33b   # scope to specific dirs
"""
import argparse
import json
import sys
import time
from pathlib import Path

from sefaria import fetch_daf_text

OUTPUT_ROOT = Path(__file__).parent / "output"


def find_candidates() -> list[Path]:
    dirs = []
    for seg_path in sorted(OUTPUT_ROOT.glob("*/01_segmentation.json")):
        try:
            seg = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if seg.get("amud") in ("b", "a-b"):
            dirs.append(seg_path.parent)
    return dirs


def process_daf(daf_dir: Path, dry_run: bool) -> str:
    seg_path = daf_dir / "01_segmentation.json"
    seg = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
    masechta, daf = seg.get("masechta"), seg.get("daf")
    if not masechta or not daf:
        return "skip (no masechta/daf)"

    next_path = daf_dir / "sefaria_next.md"
    old_text = next_path.read_text(encoding="utf-8", errors="replace") if next_path.exists() else None

    if dry_run:
        return f"would fetch {masechta} {int(daf) + 1} (a+b)"

    new_text = fetch_daf_text(masechta, int(daf) + 1)
    if new_text.startswith("[Sefaria text not available"):
        return f"FAILED fetch for {masechta} {int(daf) + 1} — left untouched"

    if old_text is not None and old_text == new_text:
        return "unchanged (already widened)"

    if old_text is not None:
        backup = next_path.with_suffix(next_path.suffix + ".bak_before_amud_b_widen")
        if not backup.exists():
            backup.write_text(old_text, encoding="utf-8")

    next_path.write_text(new_text, encoding="utf-8")
    return f"widened ({masechta} {int(daf) + 1}, {len(new_text)} chars, was {len(old_text or '')})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*", help="Specific output dirs to process (default: all 862 amud-b/a-b dafim)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.15, help="Delay between Sefaria requests")
    ap.add_argument("--all", action="store_true",
                     help="Process every output dir, not just amud in ('b','a-b') — "
                          "use once the amud field is known to be unreliable as a filter")
    args = ap.parse_args()

    if args.all:
        dafim = sorted(p.parent for p in OUTPUT_ROOT.glob("*/01_segmentation.json"))
    else:
        dafim = [Path(d) for d in args.dirs] if args.dirs else find_candidates()
    print(f"{'DRY RUN' if args.dry_run else 'RUNNING'} — {len(dafim)} daf(im)\n")

    results = {}
    for i, d in enumerate(dafim, 1):
        try:
            result = process_daf(d, args.dry_run)
        except Exception as e:
            result = f"ERROR: {e}"
        results[d.name] = result
        print(f"[{i}/{len(dafim)}] {d.name}: {result}")
        if not args.dry_run:
            time.sleep(args.sleep)

    widened = sum(1 for r in results.values() if r.startswith("widened"))
    failed = sum(1 for r in results.values() if r.startswith("FAILED") or r.startswith("ERROR"))
    unchanged = sum(1 for r in results.values() if r.startswith("unchanged"))
    print(f"\nDone. widened={widened} unchanged={unchanged} failed={failed} total={len(dafim)}")


if __name__ == "__main__":
    main()
