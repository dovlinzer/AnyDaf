#!/usr/bin/env python3
"""Zero-API-cost inventory pass: scans every multi-candidate quote run across the 13-daf
batch for internal MISHNA:/GEMARA: markers (literal text the Sefaria items themselves
carry) via relocate_parse.marker_split_points -- the same gate relocate_check.py uses to
decide whether a run qualifies for a 3-way split (FORM 3). A run with exactly one marker
already gets a correct 2-way split from FORM 2 (the marker IS the seam). A run with
exactly two markers qualifies for FORM 3. Useful for re-checking the qualifying set after
future v10 reruns without spending any API calls."""
from pathlib import Path
from relocate_parse import parse_blocks, build_windows, marker_split_points

HERE = Path(__file__).parent

DAFIM = [
    ("bava_batra_103", "_wallpatched"),
    ("bava_batra_153", "_wallpatched"),
    ("bava_batra_174", "_wallpatched"),
    ("bava_batra_84", "_wallpatched"),
    ("bava_metzia_11", "_wallpatched"),
    ("berakhot_31b", "_wallpatched"),
    ("gittin_18", "_wallpatched"),
    ("hullin_88", "_wallpatched"),
    ("nazir_59", "_wallpatched"),
    ("niddah_60", "_wallpatched"),
    ("niddah_67", "_wallpatched"),
    ("yevamot_33", "_wallpatched"),
    ("zevachim_29", ""),
]

def main():
    one_marker, two_markers, three_plus = [], [], []
    for daf, suffix in DAFIM:
        path = HERE / "output" / daf / f"03_text_first_prototype_v10{suffix}.md"
        text = path.read_text(encoding="utf-8", errors="replace")
        blocks = parse_blocks(text)
        windows = build_windows(blocks)
        for w in windows:
            if len(w["candidates"]) <= 1 or len(w["items"]) <= 2:
                continue
            pts = marker_split_points(w["items"])
            if len(pts) == 1:
                one_marker.append((daf, w, pts))
            elif len(pts) == 2:
                two_markers.append((daf, w, pts))
            elif len(pts) >= 3:
                three_plus.append((daf, w, pts))

    print(f"Runs (3+ items, >1 candidate) with exactly 1 internal marker (FORM 2 already covers these): {len(one_marker)}")
    for daf, w, pts in one_marker:
        print(f"  [{daf}] run@{w['quote_indices']} ({len(w['items'])} items) current={w['current_heading']!r} marker@{pts}")

    print(f"\nRuns with exactly 2 internal markers (FORM 3 candidates under the new gate): {len(two_markers)}")
    for daf, w, pts in two_markers:
        print(f"  [{daf}] run@{w['quote_indices']} ({len(w['items'])} items) current={w['current_heading']!r} marker@{pts} candidates={[c['heading'] for c in w['candidates']]}")

    print(f"\nRuns with 3+ internal markers (beyond FORM 3's scope, needs a look): {len(three_plus)}")
    for daf, w, pts in three_plus:
        print(f"  [{daf}] run@{w['quote_indices']} ({len(w['items'])} items) current={w['current_heading']!r} marker@{pts}")


if __name__ == "__main__":
    main()
