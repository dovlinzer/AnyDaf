#!/usr/bin/env python3
"""
Daf Yomi Shiur Processor (v2 — with translation + cleanup pass)
Converts SRT lecture transcripts into formatted, source-annotated written essays.

Four passes:
  1.   Segmentation  (Haiku)  — SRT → JSON outline
  2.   Rewrite       (Sonnet) — SRT + outline → essay (Hebrew/Aramaic translated to English)
  2.5. Cleanup       (Sonnet) — essay → essay with direct-quote Aramaic hidden in HTML comments
  3.   Source insert (Haiku)  — essay + Sefaria text → final essay with blockquotes inserted
                                and HTML comments stripped

Usage examples:
  # Single file, direct API:
  python main2.py rdldafyomimenachot79.srt --no-batch

  # Run only cleanup + source insertion (passes 2 and 2.5 already done):
  python main2.py rdldafyomimenachot79.srt --no-batch --passes 3

  # Run only the cleanup pass:
  python main2.py rdldafyomimenachot79.srt --no-batch --passes 2.5
"""

import argparse
import logging
import sys
from pathlib import Path

from pipeline2 import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description='Process Daf Yomi SRT transcripts into formatted shiur documents.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'input', nargs='+',
        help='SRT file(s) or directory containing SRT files',
    )
    parser.add_argument(
        '--output-dir', default='./output',
        help='Directory for output files (default: ./output)',
    )
    parser.add_argument(
        '--no-batch', action='store_true',
        help='Use direct API calls instead of the Batch API (default: batch mode).',
    )
    parser.add_argument(
        '--workers', type=int, default=3,
        help='Parallel workers for direct mode (default: 3)',
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Skip passes whose output files already exist (safe to rerun after interruption)',
    )
    parser.add_argument(
        '--masechta',
        help='Override masechta name, e.g. "Menachot" (use with single-file input)',
    )
    parser.add_argument(
        '--daf', type=int,
        help='Override daf number (use with single-file input)',
    )
    parser.add_argument(
        '--amud', choices=['a', 'b'],
        help='Override amud (a or b) when a shiur covers only one side of a daf (use with single-file input)',
    )
    parser.add_argument(
        '--passes', choices=['all', '1', '2', '2.5', '3'], default='all',
        help=(
            'Which pass(es) to run: all (default), 1=segmentation, '
            '2=rewrite, 2.5=cleanup, 3=source insertion. '
            'Each pass requires the previous pass output to exist.'
        ),
    )
    parser.add_argument(
        '--refresh-sefaria', action='store_true',
        help='Ignore cached sefaria.md files and re-fetch from Sefaria (useful after fixing fetch errors)',
    )
    parser.add_argument(
        '--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging verbosity (default: INFO)',
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S',
    )

    # Collect SRT files
    srt_files = []
    for raw in args.input:
        p = Path(raw)
        if p.is_dir():
            found = sorted(p.glob('*.srt')) + sorted(p.glob('*.SRT'))
            if not found:
                print(f"Warning: no .srt files found in {p}", file=sys.stderr)
            srt_files.extend(found)
        elif p.is_file():
            srt_files.append(p)
        else:
            print(f"Warning: {raw} not found, skipping", file=sys.stderr)

    if not srt_files:
        print("Error: no SRT files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(srt_files)} SRT file(s)")

    # Validate override usage
    if (args.masechta or args.daf or args.amud) and len(srt_files) != 1:
        print("Error: --masechta / --daf overrides require exactly one input file.", file=sys.stderr)
        sys.exit(1)

    pipeline = Pipeline(
        output_dir=Path(args.output_dir),
        use_batch=not args.no_batch,
        workers=args.workers,
        resume=args.resume,
        passes=args.passes,
        refresh_sefaria=args.refresh_sefaria,
    )

    pipeline.process_files(
        srt_files,
        masechta_override=args.masechta,
        daf_override=args.daf,
        amud_override=args.amud,
    )


if __name__ == '__main__':
    main()
