#!/usr/bin/env python3
"""
Audit 03_final.md files for missing Sefaria text coverage.

For each output directory, compares the numbered segments in sefaria.md against
the blockquoted Hebrew passages in 03_final.md. Reports consecutive runs of 2+
missing segments within the "covered range" (between the first and last segment
that did get inserted) — a strong signal that the rewrite or source-insertion
pass skipped a stretch of Talmudic text.

Usage:
    python audit_gaps.py                         # all output dirs
    python audit_gaps.py --dir output/menachot_109  # single dir (debug)
    python audit_gaps.py --min-gap 3             # only flag gaps of 3+ missing
    python audit_gaps.py --csv my_report.csv     # custom output path
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import List, Optional

# ── Hebrew normalization ──────────────────────────────────────────────────────

# Nikud (vowel points) sit in U+0591–U+05C7; stripping them avoids
# mismatches between the sefaria.md source and the blockquotes in 03_final.md,
# which may have been lightly reformatted by the Haiku insertion pass.
_NIKUD_RE = re.compile(r'[֑-ׇװ-״יִ-פֿ]')


def _norm(text: str) -> str:
    """Strip nikud, collapse whitespace."""
    return re.sub(r'\s+', ' ', _NIKUD_RE.sub('', text)).strip()


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_sefaria(text: str) -> List[dict]:
    """
    Parse sefaria.md into a flat ordered list of segments.

    Format in sefaria.md:
        ### Tractate NNa
        **1.**
        *Hebrew/Aramaic:* <text>
        *Translation:* <text>
        **2.**
        ...
    Returns list of dicts: {section, local_n, global_n, heb, heb_norm}
    """
    segs: List[dict] = []
    current_section: Optional[str] = None
    current: Optional[dict] = None

    for line in text.splitlines():
        # Section header
        m = re.match(r'^#{2,3}\s+(.+)', line)
        if m:
            current_section = m.group(1).strip()
            continue

        # Segment number **N.**
        m = re.match(r'^\*\*(\d+)\.\*\*\s*$', line.strip())
        if m:
            current = {
                'section': current_section,
                'local_n': int(m.group(1)),
                'global_n': len(segs) + 1,
                'heb': '',
                'heb_norm': '',
            }
            segs.append(current)
            continue

        # Hebrew line
        m = re.match(r'^\*Hebrew/Aramaic:\*\s+(.+)', line)
        if m and current is not None:
            current['heb'] = m.group(1).strip()
            current['heb_norm'] = _norm(current['heb'])

    return segs


def parse_final_blockquotes(text: str) -> List[str]:
    """
    Extract all blockquoted Hebrew/Aramaic passages from 03_final.md.

    Each blockquote starts with:
        > **Hebrew/Aramaic:** <text>
    and may continue on subsequent > lines until a non-> line.

    Returns a list of normalized Hebrew strings (one per blockquote).
    """
    results: List[str] = []
    buf: List[str] = []
    in_heb = False

    for line in text.splitlines():
        if re.match(r'^>\s*\*\*Hebrew/Aramaic:\*\*', line):
            # Start a new Hebrew capture
            buf = [re.sub(r'^>\s*\*\*Hebrew/Aramaic:\*\*\s*', '', line)]
            in_heb = True
        elif in_heb:
            if line.startswith('>'):
                content = line[1:].strip()
                # Stop capturing at the Translation line or an empty > line
                if re.match(r'\*\*Translation', content):
                    results.append(_norm(' '.join(buf)))
                    buf = []
                    in_heb = False
                elif content:
                    buf.append(content)
                # Empty > line — continue (multi-line Hebrew)
            else:
                # Non-> line ends the blockquote
                if buf:
                    results.append(_norm(' '.join(buf)))
                buf = []
                in_heb = False

    if buf:
        results.append(_norm(' '.join(buf)))

    return results


# ── Gap detection ─────────────────────────────────────────────────────────────

def _seg_in_final(seg_norm: str, final_norms: List[str], anchor: int = 55) -> bool:
    """Check if a sefaria segment appears in any final blockquote."""
    if not seg_norm or len(seg_norm) < 8:
        return True   # too short to anchor reliably — treat as present
    key = seg_norm[:anchor]
    return any(key in f for f in final_norms)


def find_gaps(segs: List[dict], final_norms: List[str], min_gap: int = 2) -> dict:
    """
    Mark each segment as present/absent, find the covered range,
    then identify consecutive runs of ≥ min_gap missing segments within it.

    Returns a dict with coverage stats and gap list.
    """
    for seg in segs:
        seg['present'] = _seg_in_final(seg['heb_norm'], final_norms)

    present_idx = [i for i, s in enumerate(segs) if s['present']]

    if len(present_idx) < 2:
        return {'covered_segs': 0, 'gaps': []}

    first, last = present_idx[0], present_idx[-1]
    covered = last - first + 1
    inner_missing = [i for i in range(first + 1, last) if not segs[i]['present']]

    # Group consecutive missing indices into runs
    gaps = []
    run: List[int] = []
    for idx in inner_missing:
        if run and idx != run[-1] + 1:
            if len(run) >= min_gap:
                g = _make_gap(run, segs)
                gaps.append(g)
            run = []
        run.append(idx)
    if len(run) >= min_gap:
        gaps.append(_make_gap(run, segs))

    return {
        'total_segs': len(segs),
        'covered_segs': covered,
        'covered_first': segs[first]['global_n'],
        'covered_last': segs[last]['global_n'],
        'inner_missing_count': len(inner_missing),
        'gaps': gaps,
    }


def _make_gap(run: List[int], segs: List[dict]) -> dict:
    first_seg = segs[run[0]]
    last_seg  = segs[run[-1]]
    return {
        'count': len(run),
        'section': first_seg['section'],
        'local_n_start': first_seg['local_n'],
        'local_n_end': last_seg['local_n'],
        'global_n_start': first_seg['global_n'],
        'global_n_end': last_seg['global_n'],
        'sample_heb': first_seg['heb'][:100],
    }


# ── Per-directory audit ───────────────────────────────────────────────────────

def audit_dir(d: Path, min_gap: int = 2) -> Optional[dict]:
    sef = d / 'sefaria.md'
    fin = d / '03_final.md'
    if not sef.exists() or not fin.exists():
        return None

    segs = parse_sefaria(sef.read_text(encoding='utf-8'))
    finals = parse_final_blockquotes(fin.read_text(encoding='utf-8'))

    if not segs or not finals:
        return None

    result = find_gaps(segs, finals, min_gap=min_gap)
    if not result.get('gaps'):
        return None

    return {'directory': d.name, **result}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir', default='./output',
                        help='Root output directory (default: ./output)')
    parser.add_argument('--dir',
                        help='Audit a single directory (for debugging)')
    parser.add_argument('--min-gap', type=int, default=2,
                        help='Minimum consecutive missing segments to flag (default: 2)')
    parser.add_argument('--csv', default='',
                        help='CSV output path (default: <output-dir>/../audit_gaps.csv)')
    parser.add_argument('--top', type=int, default=30,
                        help='Print top N results to stdout (default: 30)')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.dir:
        # Debug mode: single directory
        d = Path(args.dir)
        r = audit_dir(d, min_gap=args.min_gap)
        if r:
            _print_result(r)
        else:
            print(f'No gaps found in {d.name}')
        return

    dirs = sorted(d for d in output_dir.iterdir() if d.is_dir())
    print(f'Auditing {len(dirs)} directories…', file=sys.stderr)

    results = []
    for d in dirs:
        r = audit_dir(d, min_gap=args.min_gap)
        if r:
            results.append(r)

    results.sort(key=lambda x: -x['inner_missing_count'])

    print(f'\nTotal dafs audited : {len(dirs)}')
    print(f'Dafs with gaps     : {len(results)}')
    print(f'(min-gap threshold : {args.min_gap})')
    print()

    print(f'{"Directory":<35} {"Total":>6} {"Covered":>8} {"Missing":>8} {"Gaps":>5}')
    print('-' * 70)
    for r in results[:args.top]:
        print(f'{r["directory"]:<35} {r["total_segs"]:>6} {r["covered_segs"]:>8} '
              f'{r["inner_missing_count"]:>8} {len(r["gaps"]):>5}')
        for g in r['gaps']:
            print(f'    [{g["section"]}] segs {g["local_n_start"]}–{g["local_n_end"]} '
                  f'({g["count"]} missing): {g["sample_heb"][:70]}…')

    if len(results) > args.top:
        print(f'  … and {len(results) - args.top} more (see CSV)')

    # Write CSV
    csv_path = Path(args.csv) if args.csv else output_dir.parent / 'audit_gaps.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'directory', 'total_segs', 'covered_segs', 'inner_missing',
            'gap_count', 'gap_index',
            'gap_section', 'gap_local_n_start', 'gap_local_n_end',
            'gap_missing_count', 'gap_sample_heb',
        ])
        for r in results:
            for gi, g in enumerate(r['gaps']):
                w.writerow([
                    r['directory'], r['total_segs'], r['covered_segs'],
                    r['inner_missing_count'], len(r['gaps']), gi + 1,
                    g['section'], g['local_n_start'], g['local_n_end'],
                    g['count'], g['sample_heb'],
                ])
    print(f'\nCSV written to: {csv_path}')


def _print_result(r: dict):
    print(f"Directory : {r['directory']}")
    print(f"Total segs: {r['total_segs']}")
    print(f"Covered   : segs {r['covered_first']}–{r['covered_last']} ({r['covered_segs']} segs)")
    print(f"Missing   : {r['inner_missing_count']} within covered range")
    print(f"Gaps      : {len(r['gaps'])}")
    for g in r['gaps']:
        print(f"  [{g['section']}] segs {g['local_n_start']}–{g['local_n_end']} "
              f"({g['count']} missing)")
        print(f"    → {g['sample_heb'][:80]}…")


if __name__ == '__main__':
    main()
