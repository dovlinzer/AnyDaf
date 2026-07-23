#!/usr/bin/env python3
"""
check_anchor_section_mismatch.py — flags real pass-3 defects in 03_final.md, purely
by local text comparison against ground-truth source files (no API cost):

1. Content fidelity — every blockquote's Hebrew/Aramaic text is matched against the
   actual Sefaria source (sefaria_prev.md + sefaria.md + sefaria_next.md, combined
   into one ordered pool), not just checked structurally against HTML-comment
   anchors. Three real failure modes, each with a low false-positive rate because
   they check actual text content rather than presence/absence of a marker:
     FABRICATED    - blockquote text doesn't appear anywhere in the source pool
     DUPLICATE     - two blockquotes quote substantially the same passage
     OUT OF ORDER  - a blockquote's matched source position is earlier than the
                     previous blockquote's — content quoted out of sequence or
                     repeated from much earlier in the daf

   This replaces an earlier, purely structural check (does this section have an
   HTML-comment anchor vs. does it have a blockquote) that had two well-documented
   false-positive modes: (a) several consecutive sections legitimately sharing one
   indivisible Sefaria segment, blockquoted once under the first; (b) one long,
   continuous passage legitimately split across many consecutive headers per the
   prompt's "no gaps" rule, most of which have no anchor of their own. Both are
   correct, desired pass-3 behavior — a structural presence/absence check can't
   tell them apart from real bugs, which is why it produced so much noise
   (confirmed on Avodah Zarah 2, Bava Batra 116, and much of the Hullin corpus).
   Checking actual text content instead sidesteps both false-positive modes
   directly: neither pattern ever duplicates, fabricates, or reorders content.

2. Heading/blockquote structure — compares heading text and order in 03_final.md
   against 025_cleanup.md (or 02_rewrite.md for older, pre-pass-2.5 dafs) to catch
   dropped, merged, or reordered headings. No known false-positive mode.

3. Missing **bold** markup on a blockquote's Translation line — Sefaria's source
   text already has this markup baked in (bold = literal Talmudic words, plain =
   Rashi-style interpolations); pass 3 is supposed to copy it through verbatim.
   A translation with zero ** spans means the markup was dropped while copying
   (the Avodah Zarah 3 bug). No known false-positive mode.
"""
import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

from find_sefaria_indices import parse_sefaria_items, match_hebrew, strip_nikud, extract_blockquote_hebrews

OUTPUT_ROOT = Path(__file__).parent / "output"

HEADER_RE = re.compile(r'^(#{2,3}) (.+)$', re.MULTILINE)
TRANSLATION_LINE_RE = re.compile(r'^>\s*\*\*Translation:\*\*(.*)$', re.MULTILINE)


def split_sections(text: str):
    """Return list of (level, title, body) for each ## / ### heading, in order."""
    matches = list(HEADER_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1), m.group(2).strip(), text[start:end]))
    return sections


def check_bold_markup(final_text: str):
    """Flag any blockquote Translation line with zero **bold** spans."""
    flags = []
    for i, m in enumerate(TRANSLATION_LINE_RE.finditer(final_text)):
        if '**' not in m.group(1):
            flags.append(f"NO BOLD MARKUP — blockquote #{i + 1}'s Translation line has no ** spans")
    return flags


def build_source_pool(daf_dir: Path):
    """Ordered (position, hebrew_text) list across sefaria_prev + sefaria + sefaria_next."""
    pool_texts = []
    for name in ("sefaria_prev.md", "sefaria.md", "sefaria_next.md"):
        path = daf_dir / name
        if path.exists():
            items, _ = parse_sefaria_items(path.read_text(encoding='utf-8'))
            pool_texts.extend(text for _, text in items)
    return list(enumerate(pool_texts))


TRANSLATION_ITEM_RE = re.compile(r'\*Translation:\*\s*(.+?)(?=\n\*Hebrew|\n\n\*\*\d|\Z)', re.DOTALL)
CITATION_MARKER_RE = re.compile(r'\b(?:stated|taught|learned|mishna|gemara)\b[^.]{0,40}\(\d+[ab]\)', re.IGNORECASE)


def build_translation_pool(daf_dir: Path):
    """Translation text per pool position, aligned 1:1 with build_source_pool's
    Hebrew pool (same files, same order) — used only to detect an explicit
    backward-citation marker like "the mishna stated (89b)" for annotating
    OUT OF ORDER flags, not for matching itself."""
    translations = []
    for name in ("sefaria_prev.md", "sefaria.md", "sefaria_next.md"):
        path = daf_dir / name
        if path.exists():
            text = path.read_text(encoding='utf-8')
            parts = re.split(r'\n---\n', text, maxsplit=1)
            for part in parts:
                translations.extend(m.group(1).strip() for m in TRANSLATION_ITEM_RE.finditer(part))
    return translations


def texts_overlap(a: str, b: str, min_fraction: float = 0.75) -> bool:
    """
    True if a and b are substantially the same passage — measured as the longest
    single contiguous run they share, as a fraction of the shorter text's length.
    Talmudic text is full of formulaic parallel clauses (e.g. "three log of water
    minus a kortov, into which fell a kortov of WINE..." vs "...of MILK...") that
    share a long common opening or template but are genuinely different rulings —
    a prefix/suffix or aggregate-similarity check flags those as false positives.
    Requiring most of the shorter text to be one continuous shared run (not just
    a shared opening) correctly lets templated-but-distinct clauses through while
    still catching an actually-repeated passage.
    """
    a_bare, b_bare = strip_nikud(a), strip_nikud(b)
    shorter_len = min(len(a_bare), len(b_bare))
    if shorter_len < 15:
        return a_bare in b_bare or b_bare in a_bare
    match = SequenceMatcher(None, a_bare, b_bare).find_longest_match(0, len(a_bare), 0, len(b_bare))
    return (match.size / shorter_len) >= min_fraction


def check_content_fidelity(daf_dir: Path, final_text: str):
    pool = build_source_pool(daf_dir)
    if not pool:
        return []  # no sefaria.md at all — nothing to check against
    translations = build_translation_pool(daf_dir)

    flags = []
    prev_idx = None
    prev_text = None
    for i, hebrew in enumerate(extract_blockquote_hebrews(final_text)):
        idx = match_hebrew(hebrew, pool)
        preview = hebrew[:40].replace("\n", " ")
        if idx is None:
            flags.append(f"FABRICATED   blockquote #{i + 1} — not found anywhere in Sefaria source: {preview!r}...")
        elif prev_idx is not None and idx < prev_idx:
            note = ""
            if idx < len(translations) and CITATION_MARKER_RE.search(translations[idx]):
                note = " [Sefaria's own translation cites an earlier daf here — may be a legitimate backward reference, not a reordering bug]"
            flags.append(
                f"OUT OF ORDER blockquote #{i + 1} — matches source position {idx}, earlier than "
                f"blockquote #{i}'s position {prev_idx}: {preview!r}...{note}"
            )
        elif prev_idx is not None and idx == prev_idx and texts_overlap(hebrew, prev_text):
            flags.append(f"DUPLICATE    blockquote #{i + 1} — quotes substantially the same passage as blockquote #{i}: {preview!r}...")
        if idx is not None:
            prev_idx, prev_text = idx, hebrew
    return flags


def check_dir(daf_dir: Path):
    final_path = daf_dir / "03_final.md"
    if not final_path.exists():
        return None

    final_text = final_path.read_text(encoding='utf-8')
    flags = check_bold_markup(final_text)
    flags += check_content_fidelity(daf_dir, final_text)

    final_sections = split_sections(final_text)
    cleanup_path = daf_dir / "025_cleanup.md"
    rewrite_path = daf_dir / "02_rewrite.md"
    source_path = cleanup_path if cleanup_path.exists() else (rewrite_path if rewrite_path.exists() else None)
    if source_path is not None:
        source_sections = split_sections(source_path.read_text(encoding='utf-8'))
        if len(source_sections) != len(final_sections):
            flags.append(
                f"HEADER COUNT MISMATCH: {len(source_sections)} in {source_path.name} vs {len(final_sections)} in 03_final"
            )
        else:
            for (_, title_s, _), (_, title_f, _) in zip(source_sections, final_sections):
                if title_s != title_f:
                    flags.append(f"TITLE MISMATCH: {title_s!r} vs {title_f!r}")

    return flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dirs', nargs='*', help='Specific output dir(s) (default: all)')
    args = parser.parse_args()

    dirs = [Path(d) for d in args.dirs] if args.dirs else sorted(OUTPUT_ROOT.iterdir())

    total_dafs = 0
    flagged_dafs = 0
    total_flags = 0
    for d in dirs:
        if not d.is_dir():
            continue
        flags = check_dir(d)
        if flags is None:
            continue
        total_dafs += 1
        if flags:
            flagged_dafs += 1
            total_flags += len(flags)
            print(f"\n{d.name}:")
            for f in flags:
                print(f"  {f}")

    print(f"\n\nChecked {total_dafs} dafs, {flagged_dafs} flagged ({total_flags} total flags)")


if __name__ == '__main__':
    main()
