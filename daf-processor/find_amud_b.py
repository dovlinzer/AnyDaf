#!/usr/bin/env python3
"""
find_amud_b.py — Detect where amud B begins in each shiur.

For each output directory that has both sefaria.md and 03_final.md:
1. Find the last amud A sefaria item's position in 03_final.md
2. Find the first amud B sefaria item that appears AFTER that position
3. Walk back to the nearest heading (## or ###)
4. Map that heading to a segment index + timestamp
5. Write amud_b_segment_index and amud_b_timestamp to 01_segmentation.json

Run:
    python find_amud_b.py                      # all output dirs
    python find_amud_b.py output/Hullin_13     # single dir
    python find_amud_b.py --dry-run            # preview, no writes
    python find_amud_b.py --force              # re-process even if already set
"""

import argparse
import json
import re
import sys
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parent / "output"


def parse_sefaria_items(section_text: str) -> list[str]:
    """Return Hebrew/Aramaic item texts from a sefaria section."""
    return re.findall(r'\*\*\d+\.\*\*\n\*Hebrew/Aramaic:\* ([^\n]+)', section_text)


def first_match_in_final(item: str, final_lines: list[str]) -> int | None:
    """Return line index of the first occurrence of item (using decreasing anchor lengths)."""
    for anchor_len in (40, 25, 20, 15):
        anchor = item[:anchor_len].strip()
        if not anchor:
            continue
        for ln, line in enumerate(final_lines):
            if anchor in line:
                return ln
    return None


def nearest_heading(final_lines: list[str], from_line: int) -> tuple[str, str] | None:
    """
    Walk backwards from from_line to find the nearest ## or ### heading.
    Returns (heading_type, heading_text) where heading_type is '##' or '###'.
    """
    for i in range(from_line, -1, -1):
        line = final_lines[i]
        if line.startswith('### '):
            return ('###', line[4:].strip())
        if line.startswith('## '):
            return ('##', line[3:].strip())
    return None


def lookup_segment(heading_type: str, heading_text: str,
                   macro_segments: list[dict]) -> tuple[int, str] | None:
    """
    Return (segment_index, timestamp) for the given heading.
    For ## headings: match macro segment display_title or title.
    For ### headings: match micro_segment display_title or title within any macro segment,
                      return that macro segment's index + the micro-segment's timestamp.
    """
    if heading_type == '##':
        for i, seg in enumerate(macro_segments):
            if (seg.get('display_title', '').strip() == heading_text or
                    seg.get('title', '').strip() == heading_text):
                return (i, seg.get('timestamp', ''))
    else:  # '###'
        for i, seg in enumerate(macro_segments):
            for micro in seg.get('micro_segments', []):
                if (micro.get('display_title', '').strip() == heading_text or
                        micro.get('title', '').strip() == heading_text):
                    return (i, micro.get('timestamp', ''))
    return None


def process_dir(daf_dir: Path, dry_run: bool, force: bool) -> str:
    """Process one output directory. Returns a status string for logging."""
    seg_path = daf_dir / "01_segmentation.json"
    sefaria_path = daf_dir / "sefaria.md"
    final_path = daf_dir / "03_final.md"

    if not seg_path.exists():
        return "SKIP (no segmentation)"
    if not sefaria_path.exists():
        return "SKIP (no sefaria.md)"
    if not final_path.exists():
        return "SKIP (no 03_final.md)"

    seg = json.loads(seg_path.read_text())
    macro_segments = seg.get("macro_segments", [])
    if not macro_segments:
        return "SKIP (no macro_segments)"

    if seg.get("amud") == "b":
        return "SKIP (amud b only)"

    if not force and "amud_b_segment_index" in seg:
        return "SKIP (already set)"

    sefaria_text = sefaria_path.read_text()
    final_lines = final_path.read_text().splitlines()

    # Split sefaria into amud A and amud B sections
    parts = sefaria_text.split('---\n\n')
    if len(parts) < 2:
        return "SKIP (no --- separator in sefaria.md)"

    a_section = parts[0]
    # The amud B section starts after the ### Xb heading
    b_match = re.search(r'###[^\n]+\d+b\n\n(.+)', sefaria_text[sefaria_text.index('---'):], re.DOTALL)
    if not b_match:
        return "SKIP (no amud B section header)"
    b_section = b_match.group(1)

    a_items = parse_sefaria_items(a_section)
    b_items = parse_sefaria_items(b_section)

    if not b_items:
        return "SKIP (no amud B items)"

    # Find the last amud A item's position in 03_final.md.
    # We use the LAST successfully matched A item to establish the amud A boundary.
    amud_a_last_line = -1
    for item in reversed(a_items):
        ln = first_match_in_final(item, final_lines)
        if ln is not None:
            amud_a_last_line = ln
            break

    # Find the first amud B item that appears STRICTLY AFTER the amud A boundary.
    # Items at or before the boundary are in shared/bridge content (still in amud A context).
    found_heading_type: str | None = None
    found_heading_text: str | None = None
    found_seg_idx: int | None = None
    found_timestamp: str | None = None
    found_b_item_idx: int | None = None

    for b_idx, item in enumerate(b_items[:10]):
        ln = first_match_in_final(item, final_lines)
        if ln is None:
            continue
        if ln <= amud_a_last_line:
            continue  # Still in amud A territory
        heading = nearest_heading(final_lines, ln)
        if heading is None:
            continue
        result = lookup_segment(heading[0], heading[1], macro_segments)
        if result is None:
            continue
        found_heading_type = heading[0]
        found_heading_text = heading[1]
        found_seg_idx, found_timestamp = result
        found_b_item_idx = b_idx
        break

    if found_seg_idx is None:
        # Fall back: if no amud A anchor was found, try items 1+ (old behavior)
        if amud_a_last_line == -1:
            for b_idx, item in enumerate(b_items[1:10], 1):
                ln = first_match_in_final(item, final_lines)
                if ln is None:
                    continue
                heading = nearest_heading(final_lines, ln)
                if heading is None:
                    continue
                result = lookup_segment(heading[0], heading[1], macro_segments)
                if result is None:
                    continue
                found_heading_type = heading[0]
                found_heading_text = heading[1]
                found_seg_idx, found_timestamp = result
                found_b_item_idx = b_idx
                break

    if found_seg_idx is None:
        return f"MISS (amudA boundary={amud_a_last_line}, no B item matched)"

    detail = f"segment {found_seg_idx} '{found_heading_text}' @ {found_timestamp} (B[{found_b_item_idx}], {found_heading_type})"

    if dry_run:
        return f"DRY-RUN → {detail}"

    seg["amud_b_segment_index"] = found_seg_idx
    seg["amud_b_timestamp"] = found_timestamp
    if found_heading_type == '###':
        seg["amud_b_micro_title"] = found_heading_text
    else:
        seg.pop("amud_b_micro_title", None)
    seg_path.write_text(json.dumps(seg, ensure_ascii=False, indent=2))
    return f"OK → {detail}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="*", help="Specific output dir(s) to process (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    parser.add_argument("--force", action="store_true", help="Re-process even if amud_b already set")
    args = parser.parse_args()

    if args.dirs:
        dirs = [Path(d) for d in args.dirs]
    else:
        dirs = sorted(OUTPUT_ROOT.iterdir())

    ok = miss = skip = 0
    for d in dirs:
        if not d.is_dir():
            continue
        status = process_dir(d, dry_run=args.dry_run, force=args.force)
        prefix = status.split()[0]
        if prefix == "OK":
            ok += 1
        elif prefix == "MISS":
            miss += 1
        elif prefix == "DRY-RUN":
            ok += 1  # count as would-be-ok
        else:
            skip += 1
        print(f"{d.name:30s}  {status}")

    print(f"\nDone: {ok} written, {miss} missed, {skip} skipped")


if __name__ == "__main__":
    main()
