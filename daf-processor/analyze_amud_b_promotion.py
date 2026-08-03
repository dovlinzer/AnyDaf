#!/usr/bin/env python3
"""
analyze_amud_b_promotion.py — DRY-RUN ONLY. No files are modified.

For every output directory whose name ends in "<daf>b" (e.g. "yevamot_33b"),
answers the two independent questions needed to eventually decide whether it
should stay labeled "Xb" or be promoted to a standalone "X+1":

  1. ROOM — does a plain "X+1" directory already exist for this tractate? If
     so, promoting would collide with real, separately-filed content, so
     there is no room. (Chains of consecutive b's are visible as adjacent
     rows in the report, sorted by tractate/daf, rather than resolved here —
     promoting one shifts the room-check for the next, and that cascade is a
     decision to make by eye, not to auto-resolve.)

  2. COVERAGE — how much of the NEXT daf's own text actually appears inside
     this directory's assembled essay (03_final.md), measured by matching
     every individual Sefaria item of the next daf (from the already-widened
     sefaria_next.md) against the essay text — the same line-matching
     approach find_amud_b.py already uses for its own prev-daf check
     (first_match_in_final, decreasing anchor lengths), just pointed at the
     next daf instead of the previous one. This is a content-weighted
     measurement, not a text-position heuristic, so a one-line boundary
     artifact barely moves it.

Writes a CSV to review_v10_relocated/amud_b_promotion_analysis.csv and prints
a summary. Picking an actual coverage threshold is a follow-up decision once
the real distribution is visible — this script does not choose one.
"""
import csv
import os
import re
from pathlib import Path

from find_amud_b import parse_sefaria_items, first_match_in_final
import json

HERE = Path(__file__).parent
OUTPUT_ROOT = HERE / "output"
REPORT_PATH = HERE / "review_v10_relocated" / "amud_b_promotion_analysis.csv"

_TRACTATE_CANONICAL = {
    "chullin": "Hullin",
    "hullin": "Hullin",
    "eruvin": "Eiruvin",
    "megilah": "Megillah",
    "megila": "Megillah",
}


def daf_to_float(daf: int, amud: str | None) -> float:
    return float(daf) + (0.5 if amud == 'b' else 0.0)


def parse_dir_name(dir_name: str) -> tuple[str | None, float | None]:
    parts = dir_name.split("_")
    for i in range(len(parts) - 1, -1, -1):
        m = re.match(r'^(\d+)([ab])?$', parts[i], re.IGNORECASE)
        if m:
            base = int(m.group(1))
            amud = m.group(2).lower() if m.group(2) else None
            raw = "_".join(parts[:i])
            tractate = _TRACTATE_CANONICAL.get(raw.lower(), " ".join(w.capitalize() for w in parts[:i]))
            return tractate, daf_to_float(base, amud)
    return None, None


def build_tractate_map() -> dict[str, dict[float, str]]:
    """tractate -> {daf_float: dirname}"""
    m: dict[str, dict[float, str]] = {}
    for d in sorted(os.listdir(OUTPUT_ROOT)):
        if not (OUTPUT_ROOT / d).is_dir():
            continue
        tractate, daf_float = parse_dir_name(d)
        if tractate is None:
            continue
        m.setdefault(tractate, {})[daf_float] = d
    return m


def coverage_for(dirname: str) -> dict | None:
    daf_dir = OUTPUT_ROOT / dirname
    final_path = daf_dir / "03_final.md"
    next_path = daf_dir / "sefaria_next.md"
    seg_path = daf_dir / "01_segmentation.json"

    if not final_path.exists() or not next_path.exists():
        return None

    final_lines = final_path.read_text(encoding="utf-8", errors="replace").splitlines()
    next_text = next_path.read_text(encoding="utf-8", errors="replace")

    next_parts = next_text.split('---\n\n')
    next_a_items = parse_sefaria_items(next_parts[0])
    next_b_items = parse_sefaria_items(next_parts[1]) if len(next_parts) > 1 else []

    def match_count(items: list[str]) -> int:
        return sum(1 for it in items if first_match_in_final(it, final_lines) is not None)

    next_a_matched = match_count(next_a_items)
    next_b_matched = match_count(next_b_items)

    # Own daf's amud-b coverage: how much of THIS directory's own amud b is
    # actually present, vs. the shiur genuinely starting partway through it
    # (e.g. beginning mid-amud-b) -- needed to tell "a full amud b + a third
    # of the next amud a" apart from "half an amud b + a third of the next
    # amud a", which is really still just amud-b-scale content overall.
    own_sefaria_path = daf_dir / "sefaria.md"
    own_b_item_count = own_b_matched = None
    own_b_coverage_pct = None
    if own_sefaria_path.exists():
        own_text = own_sefaria_path.read_text(encoding="utf-8", errors="replace")
        own_parts = own_text.split('---\n\n')
        own_b_items = parse_sefaria_items(own_parts[1]) if len(own_parts) > 1 else []
        own_b_item_count = len(own_b_items)
        own_b_matched = match_count(own_b_items)
        own_b_coverage_pct = round(100 * own_b_matched / own_b_item_count, 1) if own_b_items else None

    seg = {}
    if seg_path.exists():
        try:
            seg = json.loads(seg_path.read_text())
        except Exception:
            seg = {}

    next_a_coverage_pct = round(100 * next_a_matched / len(next_a_items), 1) if next_a_items else None
    total_daf_coverage_pct = (
        round((own_b_coverage_pct + next_a_coverage_pct) / 2, 1)
        if own_b_coverage_pct is not None and next_a_coverage_pct is not None else None
    )

    return {
        "own_b_item_count": own_b_item_count,
        "own_b_matched": own_b_matched,
        "own_b_coverage_pct": own_b_coverage_pct,
        "next_a_item_count": len(next_a_items),
        "next_a_matched": next_a_matched,
        "next_a_coverage_pct": next_a_coverage_pct,
        "next_b_item_count": len(next_b_items),
        "next_b_matched": next_b_matched,
        "next_b_coverage_pct": round(100 * next_b_matched / len(next_b_items), 1) if next_b_items else None,
        "total_daf_coverage_pct": total_daf_coverage_pct,
        "shiur_start_amud": seg.get("shiur_start_amud"),
        "amud_b_segment_index": seg.get("amud_b_segment_index"),
        "next_daf_widened": (daf_dir / "sefaria_next.md.bak_before_amud_b_widen").exists(),
    }


def main():
    tmap = build_tractate_map()
    rows = []

    for tractate, dafmap in tmap.items():
        for daf_float, dirname in sorted(dafmap.items()):
            if not dirname.endswith("b") or daf_float % 1 != 0.5:
                continue
            base_daf = int(daf_float - 0.5)
            room = (base_daf + 1.0) not in dafmap

            cov = coverage_for(dirname)
            row = {
                "tractate": tractate,
                "dirname": dirname,
                "base_daf": base_daf,
                "room_for_promotion": room,
                "next_plain_dir_if_blocked": dafmap.get(base_daf + 1.0, ""),
            }
            if cov is None:
                row["skip_reason"] = "missing 03_final.md or sefaria_next.md"
            else:
                row.update(cov)
            rows.append(row)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tractate", "dirname", "base_daf", "room_for_promotion", "next_plain_dir_if_blocked",
        "own_b_item_count", "own_b_matched", "own_b_coverage_pct",
        "next_a_item_count", "next_a_matched", "next_a_coverage_pct",
        "next_b_item_count", "next_b_matched", "next_b_coverage_pct",
        "total_daf_coverage_pct",
        "shiur_start_amud", "amud_b_segment_index", "next_daf_widened", "skip_reason",
    ]
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- Summary ----
    total = len(rows)
    skipped = sum(1 for r in rows if "skip_reason" in r)
    scored = [r for r in rows if "skip_reason" not in r]
    with_room = [r for r in scored if r["room_for_promotion"]]
    print(f"Total 'Xb' directories: {total}  (skipped, missing files: {skipped})")
    print(f"Scored: {len(scored)}  |  Room for promotion (no existing plain X+1): {len(with_room)}")
    print()

    print("Coverage distribution among 'room' candidates (next daf's amud-a coverage %):")
    buckets = [0, 10, 30, 50, 70, 90]
    for lo, hi in zip(buckets, buckets[1:] + [101]):
        n = sum(1 for r in with_room
                if r["next_a_coverage_pct"] is not None and lo <= r["next_a_coverage_pct"] < hi)
        print(f"  {lo:3d}-{hi-1:3d}%: {n}")

    print()
    print("Top 20 'room' candidates by next-daf coverage (strongest promotion signal first):")
    ranked = sorted(
        (r for r in with_room if r["next_a_coverage_pct"] is not None),
        key=lambda r: r["next_a_coverage_pct"], reverse=True,
    )
    for r in ranked[:20]:
        print(f"  {r['dirname']:30s} next-a: {r['next_a_matched']}/{r['next_a_item_count']} "
              f"({r['next_a_coverage_pct']}%)  next-b: {r['next_b_matched']}/{r['next_b_item_count']} "
              f"({r['next_b_coverage_pct']})  shiur_start_amud={r['shiur_start_amud']}")

    print()
    print("Middle band (30-49% next-a coverage) — own amud-b coverage + total daf coverage,")
    print("i.e. (own_b_coverage_pct + next_a_coverage_pct) / 2:")
    middle = [r for r in with_room
              if r["next_a_coverage_pct"] is not None and 30 <= r["next_a_coverage_pct"] < 50]
    middle.sort(key=lambda r: (r["total_daf_coverage_pct"] or 0), reverse=True)
    for r in middle:
        print(f"  {r['dirname']:30s} own-b: {r['own_b_matched']}/{r['own_b_item_count']} "
              f"({r['own_b_coverage_pct']}%)  next-a: {r['next_a_matched']}/{r['next_a_item_count']} "
              f"({r['next_a_coverage_pct']}%)  -> total_daf_coverage: {r['total_daf_coverage_pct']}%")

    print()
    print(f"Full report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
