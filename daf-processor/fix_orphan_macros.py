#!/usr/bin/env python3
"""
fix_orphan_macros.py — find and remove segmentation macro_segments entries that
have no '## ' heading of their own in 03_final.md (content folded into a
neighboring section during pass 2/rewrite or a later relocate/wall-of-text pass,
or a stale leftover from a manually-deleted essay section).

This is what causes shiur pill navigation to jump to the wrong section:
find_sefaria_indices.py only trusts positional macro<->heading matching when the
counts are equal; any orphan macro breaks that parity for the whole daf and pushes
every macro onto a fragile exact-title-string fallback, silently mis-assigning
sefaria_index once a title fails to match (see CLAUDE.md, "shiur pill navigation
out of sync" for the full writeup and an example on Shabbat 12).

Two shapes of mismatch exist and only one is handled here:
  - macros > headers ("orphan macro"): the fixable case this script handles.
  - headers > macros: a *different* bug (duplicate/"see above" placeholder
    headings, or genuinely untracked essay content) -- deleting a macro entry
    doesn't fix it. Reported separately as "weird", never touched.

Within the orphan-macro case, an orphan's own micro_segments are re-homed to
whichever surviving macro's block now actually contains their '### ' heading in
03_final.md, rather than being discarded -- downstream consumers (find_amud_b.py
in particular) key off exact micro-segment title/timestamp data, not the macro
that originally held it.

Usage:
    python fix_orphan_macros.py                  # scan whole corpus, report only
    python fix_orphan_macros.py output/shabbat_12 # scan one dir, report only
    python fix_orphan_macros.py --apply           # apply fix to all clean cases
    python fix_orphan_macros.py --apply output/shabbat_12

After --apply, re-run for the affected dirs:
    python find_sefaria_indices.py --force <dirs>
    python find_amud_b.py --force <dirs>
and re-upload to Supabase:
    python upload_to_supabase.py --dir output/<daf>   # per daf
"""
import argparse
import json
import re
import shutil
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parent / "output"
heading_re = re.compile(r'^(##|###) (.+)$', re.MULTILINE)


def ts_key(ts):
    try:
        parts = [int(p) for p in ts.split(":")]
    except (ValueError, AttributeError, TypeError):
        return (0, 0)
    while len(parts) < 2:
        parts.append(0)
    return tuple(parts[-2:])


def classify(daf_dir: Path):
    """Return a dict describing the mismatch (or None if counts already match)."""
    seg_path = daf_dir / "01_segmentation.json"
    final_path = daf_dir / "03_final.md"
    if not seg_path.exists() or not final_path.exists():
        return None
    try:
        seg = json.loads(seg_path.read_text())
    except json.JSONDecodeError:
        return None
    macros = seg.get("macro_segments", [])
    if not macros:
        return None
    final_text = final_path.read_text()

    headings = [(m.start(), m.group(1), m.group(2).strip()) for m in heading_re.finditer(final_text)]
    h2 = [(pos, text) for pos, lvl, text in headings if lvl == "##"]
    h2_set = {text for _, text in h2}
    h3_set = {text for pos, lvl, text in headings if lvl == "###"}

    if len(macros) == len(h2_set):
        return None

    orphans = []
    kept = []
    for m in macros:
        title = (m.get("title") or "").strip()
        disp = (m.get("display_title") or "").strip()
        if title in h2_set or disp in h2_set:
            kept.append(m)
        else:
            orphans.append(m)

    extra_headers = [t for t in h2_set if t not in
                     {(m.get("title") or "").strip() for m in macros} and
                     t not in {(m.get("display_title") or "").strip() for m in macros}]
    header_counts = {}
    for _, text in h2:
        header_counts[text] = header_counts.get(text, 0) + 1
    dup_headers = {t: c for t, c in header_counts.items() if c > 1}

    clean = bool(orphans) and not extra_headers and not dup_headers and len(kept) == len(h2_set)

    return {
        "seg": seg, "macros": macros, "kept": kept, "orphans": orphans,
        "h2": h2, "h3_set": h3_set, "clean": clean,
        "extra_headers": extra_headers, "dup_headers": dup_headers,
        "seg_path": seg_path, "final_text": final_text,
    }


def apply_fix(daf_dir: Path, info: dict) -> str:
    seg, kept, orphans = info["seg"], info["kept"], info["orphans"]
    h2, h3_set = info["h2"], info["h3_set"]
    h2_positions = [pos for pos, _ in h2]

    def owning_h2_index(pos):
        idx = None
        for i, p in enumerate(h2_positions):
            if p <= pos:
                idx = i
            else:
                break
        return idx

    h3_to_h2idx = {}
    for m in heading_re.finditer(info["final_text"]):
        if m.group(1) == "###":
            h3_to_h2idx[m.group(2).strip()] = owning_h2_index(m.start())

    migrated = dropped = 0
    for orphan in orphans:
        for micro in orphan.get("micro_segments", []):
            mtitle = (micro.get("title") or "").strip()
            mdisp = (micro.get("display_title") or "").strip()
            match_text = mtitle if mtitle in h3_set else (mdisp if mdisp in h3_set else None)
            h2_idx = h3_to_h2idx.get(match_text) if match_text else None
            if h2_idx is None:
                dropped += 1
                continue
            kept[h2_idx].setdefault("micro_segments", []).append(micro)
            migrated += 1
        if not orphan.get("micro_segments"):
            otitle = (orphan.get("title") or "").strip()
            odisp = (orphan.get("display_title") or "").strip()
            match_text = otitle if otitle in h3_set else (odisp if odisp in h3_set else None)
            h2_idx = h3_to_h2idx.get(match_text) if match_text else None
            if h2_idx is not None:
                kept[h2_idx].setdefault("micro_segments", []).append({
                    "title": otitle, "display_title": odisp,
                    "timestamp": orphan.get("timestamp", ""),
                })
                migrated += 1

    for m in kept:
        if m.get("micro_segments"):
            m["micro_segments"].sort(key=lambda mi: ts_key(mi.get("timestamp", "")))
        m.pop("sefaria_index", None)
        m.pop("matched", None)
    for stale_key in ("amud_b_sefaria_index", "amud_b_segment_index",
                       "amud_b_timestamp", "amud_b_micro_title",
                       "shiur_start_daf", "shiur_start_amud"):
        seg.pop(stale_key, None)

    bak_path = info["seg_path"].with_name(info["seg_path"].name + ".bak_before_orphan_removal")
    if not bak_path.exists():
        shutil.copy(info["seg_path"], bak_path)

    seg["macro_segments"] = kept
    info["seg_path"].write_text(json.dumps(seg, ensure_ascii=False, indent=2))
    names = [(o.get("display_title") or o.get("title")) for o in orphans]
    return f"removed {len(orphans)} {names} | migrated {migrated} micro-segment(s), dropped {dropped}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="*", help="Specific output dir(s) (default: all)")
    parser.add_argument("--apply", action="store_true", help="Write fixes for clean cases (default: report only)")
    args = parser.parse_args()

    dirs = [Path(d) for d in args.dirs] if args.dirs else sorted(OUTPUT_ROOT.iterdir())

    clean_n = weird_n = 0
    for d in dirs:
        if not d.is_dir():
            continue
        info = classify(d)
        if info is None:
            continue
        if info["clean"]:
            clean_n += 1
            if args.apply:
                result = apply_fix(d, info)
                print(f"{d.name:25s} FIXED: {result}")
            else:
                names = [(o.get("display_title") or o.get("title")) for o in info["orphans"]]
                print(f"{d.name:25s} CLEAN orphan case: {names}")
        else:
            weird_n += 1
            print(f"{d.name:25s} WEIRD (needs manual review): "
                  f"extra_headers={info['extra_headers']} dup_headers={info['dup_headers']}")

    print(f"\n{clean_n} clean orphan case(s){' fixed' if args.apply else ' found (rerun with --apply to fix)'}, "
          f"{weird_n} weird case(s) left for manual review.")
    if clean_n and args.apply:
        print("\nNow re-run for the fixed dirs:")
        print("  python find_sefaria_indices.py --force <dirs>")
        print("  python find_amud_b.py --force <dirs>")
        print("  python upload_to_supabase.py --dir output/<daf>   # per daf, needs Supabase creds")


if __name__ == "__main__":
    main()
