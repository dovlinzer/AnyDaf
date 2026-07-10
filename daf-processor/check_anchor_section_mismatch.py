#!/usr/bin/env python3
"""
check_anchor_section_mismatch.py — flag dafs where a section's blockquote(s) in
03_final.md don't match up with where its HTML-comment anchors actually lived in
025_cleanup.md. Purely structural (header counts), no cross-script text matching,
no API cost.

Two suspicious patterns per section:
  MISSING  - section had an anchor in 025_cleanup.md but got NO blockquote in 03_final.md
             (its content likely got pulled into an earlier section instead)
  EXTRA    - section had NO anchor in 025_cleanup.md but got a blockquote anyway
             (likely a later section's content pulled backward into this one —
             the exact Avodah Zarah 2 "Tosafot: Sunday" bug)

Both are heuristic flags, not certain bugs (e.g. EXTRA is legitimate when a
commentary section genuinely picks up a dangling pending Sefaria segment that
truly belongs to no one else) - use as a triage list, not a verdict.
"""
import argparse
import re
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parent / "output"

HEADER_RE = re.compile(r'^(#{2,3}) (.+)$', re.MULTILINE)
ANCHOR_RE = re.compile(r'<!--.*?-->', re.DOTALL)
BLOCKQUOTE_RE = re.compile(r'^>\s*\*\*Hebrew/Aramaic:\*\*', re.MULTILINE)


def split_sections(text: str):
    """Return list of (level, title, body) for each ## / ### heading, in order."""
    matches = list(HEADER_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1), m.group(2).strip(), text[start:end]))
    return sections


def check_dir(daf_dir: Path):
    cleanup_path = daf_dir / "025_cleanup.md"
    final_path = daf_dir / "03_final.md"
    if not cleanup_path.exists() or not final_path.exists():
        return None

    cleanup_sections = split_sections(cleanup_path.read_text(encoding='utf-8'))
    final_sections = split_sections(final_path.read_text(encoding='utf-8'))

    if len(cleanup_sections) != len(final_sections):
        return [f"HEADER COUNT MISMATCH: {len(cleanup_sections)} in 025_cleanup vs {len(final_sections)} in 03_final"]

    flags = []
    for (lvl_c, title_c, body_c), (lvl_f, title_f, body_f) in zip(cleanup_sections, final_sections):
        if title_c != title_f:
            flags.append(f"TITLE MISMATCH: {title_c!r} vs {title_f!r}")
            continue
        n_anchors = len(ANCHOR_RE.findall(body_c))
        n_blockquotes = len(BLOCKQUOTE_RE.findall(body_f))
        if n_anchors > 0 and n_blockquotes == 0:
            flags.append(f"MISSING  {lvl_c} {title_c!r} — {n_anchors} anchor(s) in 2.5, 0 blockquotes in final")
        elif n_anchors == 0 and n_blockquotes > 0:
            flags.append(f"EXTRA    {lvl_c} {title_c!r} — 0 anchors in 2.5, {n_blockquotes} blockquote(s) in final")
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
