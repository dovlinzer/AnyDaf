#!/usr/bin/env python3
"""
find_sefaria_indices.py — Map each macro segment header to a Sefaria segment index.

For each output directory with sefaria.md, 03_final.md, and 01_segmentation.json:
  1. Parse sefaria.md to build a flat list of (global_0based_index, hebrew_text) pairs.
     Amud A items: indices 0..(a_count-1). Amud B items: a_count..(total-1).
  2. For each ## macro header in 03_final.md, extract the Hebrew/Aramaic text of the
     first blockquote immediately following it.
  3. Substring-match (decreasing anchor lengths) to find the sefaria item index.
  4. For segments with no blockquote (pure shiur_discussion), carry forward the most
     recently matched index.
  5. Write sefaria_index into each macro segment dict in 01_segmentation.json.
  6. Write amud_b_sefaria_index = a_count (0-based index of first amud B segment in the
     flat Sefaria array — equal to SefariaClient.fetchText(amud:"a").count on iOS/Android).

Usage:
    python find_sefaria_indices.py                      # all output dirs
    python find_sefaria_indices.py output/Hullin_13     # single dir
    python find_sefaria_indices.py --dry-run            # preview, no writes
    python find_sefaria_indices.py --force              # re-process even if already set
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parent / "output"

# Hebrew nikud (vowel points) and cantillation marks — strip these before comparing
# so that different orderings of combining characters (e.g. holam+dagesh vs dagesh+holam)
# don't cause false mismatches.
_HEBREW_DIACRITIC_RE = re.compile(r'[֑-ׇﬞ]')

def strip_nikud(text: str) -> str:
    return _HEBREW_DIACRITIC_RE.sub('', text)


# ---------------------------------------------------------------------------
# Parse sefaria.md
# ---------------------------------------------------------------------------

def parse_sefaria_items(sefaria_text: str) -> tuple[list[tuple[int, str]], int]:
    """
    Return (items, a_count) where:
      items   = list of (global_0based_index, hebrew_text) across both amudim
      a_count = number of amud A items = amud_b_sefaria_index for the iOS/Android array
    """
    # Split on the --- separator between amud A and amud B
    parts = re.split(r'\n---\n', sefaria_text, maxsplit=1)

    # Each item is introduced by '**N.**' then '*Hebrew/Aramaic:* text'
    item_re = re.compile(
        r'\*Hebrew/Aramaic:\*\s*(.+?)(?=\n\*Translation|\n\n\*\*\d|\Z)',
        re.DOTALL,
    )

    def extract(section: str) -> list[str]:
        return [m.group(1).strip() for m in item_re.finditer(section)]

    a_items = extract(parts[0])
    b_items = extract(parts[1]) if len(parts) > 1 else []

    a_count = len(a_items)
    items: list[tuple[int, str]] = [(i, t) for i, t in enumerate(a_items)]
    items += [(a_count + i, t) for i, t in enumerate(b_items)]
    return items, a_count


# ---------------------------------------------------------------------------
# Extract Hebrew texts from all blockquotes in a 03_final.md block
# ---------------------------------------------------------------------------

def extract_blockquote_hebrews(block: str) -> list[str]:
    """
    Extract the Hebrew/Aramaic text from every '> **Hebrew/Aramaic:** ...' blockquote
    in block (the text between two ## headers).  A ## block may contain multiple ###
    sub-sections each with their own blockquote, so we collect all of them.
    """
    results = []
    for m in re.finditer(
        r'>\s*\*\*Hebrew/Aramaic:\*\*\s*(.+?)(?=\n>|\n\n|\Z)', block, re.DOTALL
    ):
        text = m.group(1).strip()
        if text:
            results.append(text)
    return results


# ---------------------------------------------------------------------------
# Match Hebrew text against sefaria items
# ---------------------------------------------------------------------------

def match_hebrew(hebrew: str, items: list[tuple[int, str]]) -> int | None:
    """
    Return the 0-based global index of the best-matching sefaria item.
    Tries decreasing anchor lengths so minor textual differences don't block matches.
    Strips nikud (vowel points) before comparing to avoid mismatches from
    different canonical orderings of combining characters (e.g. holam+dagesh vs dagesh+holam).
    """
    hebrew_bare = strip_nikud(hebrew)
    items_bare = [(idx, strip_nikud(text)) for idx, text in items]
    for anchor_len in (40, 30, 20, 15):
        anchor = hebrew_bare[:anchor_len].strip()
        if not anchor:
            continue
        for idx, text_bare in items_bare:
            if anchor in text_bare:
                return idx
        # Also try reversed direction: sefaria item prefix inside blockquote
        for idx, text_bare in items_bare:
            item_prefix = text_bare[:anchor_len].strip()
            if item_prefix and item_prefix in hebrew_bare:
                return idx
    return None


def match_any_hebrew(hebrews: list[str], items: list[tuple[int, str]]) -> int | None:
    """Try matching each Hebrew text in hebrews; return the first hit."""
    for hebrew in hebrews:
        result = match_hebrew(hebrew, items)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Process one output directory
# ---------------------------------------------------------------------------

def process_dir(daf_dir: Path, dry_run: bool, force: bool) -> str:
    seg_path    = daf_dir / "01_segmentation.json"
    sefaria_path = daf_dir / "sefaria.md"
    final_path  = daf_dir / "03_final.md"

    if not seg_path.exists():
        return "SKIP (no segmentation)"
    if not sefaria_path.exists():
        return "SKIP (no sefaria.md)"
    if not final_path.exists():
        return "SKIP (no 03_final.md)"

    seg = json.loads(seg_path.read_text())
    macros = seg.get("macro_segments", [])
    if not macros:
        return "SKIP (no macro_segments)"

    if not force and any("sefaria_index" in m for m in macros):
        return "SKIP (already set)"

    sefaria_text = sefaria_path.read_text()
    final_text   = final_path.read_text()

    items, a_count = parse_sefaria_items(sefaria_text)
    if not items:
        return "SKIP (no sefaria items parsed)"

    # Split 03_final.md on ## headers; collect ALL blockquotes from each block
    # (a ## block may have multiple ### sub-sections each with their own blockquote)
    macro_re = re.compile(r'^## (.+)$', re.MULTILINE)
    matches = list(macro_re.finditer(final_text))
    title_to_hebrews: dict[str, list[str]] = {}
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(final_text)
        title_to_hebrews[title] = extract_blockquote_hebrews(final_text[start:end])

    # Assign sefaria_index to each macro segment
    matched  = 0
    last_idx = 0

    for macro in macros:
        title   = macro.get("title",         "").strip()
        display = macro.get("display_title", "").strip()

        hebrews = title_to_hebrews.get(title) or title_to_hebrews.get(display) or []
        if hebrews:
            idx = match_any_hebrew(hebrews, items)
            if idx is not None:
                macro["sefaria_index"] = idx
                last_idx = idx
                matched += 1
                continue

        # No blockquote or no match — shiur-discussion segment, leave sefaria_index unset
        macro.pop("sefaria_index", None)

    seg["amud_b_sefaria_index"] = a_count
    detail = f"{matched}/{len(macros)} matched, amud_b_sefaria_index={a_count}"

    if dry_run:
        return f"DRY-RUN → {detail}"

    seg_path.write_text(json.dumps(seg, ensure_ascii=False, indent=2))
    return f"OK → {detail}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "dirs", nargs="*",
        help="Specific output dir(s) to process (default: all dirs under output/)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without writing any files")
    parser.add_argument("--force", action="store_true",
                        help="Re-process even if sefaria_index is already set")
    args = parser.parse_args()

    dirs = [Path(d) for d in args.dirs] if args.dirs else sorted(OUTPUT_ROOT.iterdir())

    ok = miss = skip = 0
    for d in dirs:
        if not d.is_dir():
            continue
        status = process_dir(d, dry_run=args.dry_run, force=args.force)
        prefix = status.split()[0]
        if prefix in ("OK", "DRY-RUN"):
            ok += 1
        elif "MISS" in prefix:
            miss += 1
        else:
            skip += 1
        print(f"{d.name:35s}  {status}")

    print(f"\nDone: {ok} written, {miss} missed, {skip} skipped")


if __name__ == "__main__":
    main()
