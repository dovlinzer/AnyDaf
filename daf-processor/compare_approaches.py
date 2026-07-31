#!/usr/bin/env python3
"""
compare_approaches.py — Head-to-head structural comparison of the two pass-3 designs.

Approach A (current):  02_rewrite.md --[LLM pass 2.5 + 3]--> 03_final.md
Approach B (prototype): sefaria.md + 02_rewrite.md --[local assembly]--> 03_text_first_prototype_v3.md

Both output documents use the same `> **Hebrew/Aramaic:**` blockquote convention, so the
SAME measurement code runs against both — the comparison is apples-to-apples by
construction rather than by two hand-written checkers that might disagree.

Measures four things per document, all free/local:
  1. GEMARA COVERAGE   — what fraction of this daf's Sefaria segments actually appear?
  2. COMMENTARY COVER  — what fraction of 02_rewrite.md's own ## / ### sections survive?
  3. ORDERING          — are the Gemara quotes in true source order (non-decreasing index)?
  4. DUPLICATION       — is any Sefaria segment quoted more than once?

Usage:
    python compare_approaches.py output/hullin_88 output/sanhedrin_6 ...
"""

import argparse
import re
from pathlib import Path

from prototype_text_first import parse_sefaria_full
from prototype_text_first_v2 import hebrew_word_set

HEADING_RE = re.compile(r'^(#{2,3}) (.+)$', re.MULTILINE)
BLOCKQUOTE_RE = re.compile(r'>\s*\*\*Hebrew/Aramaic:\*\*\s*(.+?)(?=\n>|\n\n|\Z)', re.DOTALL)

MATCH_THRESHOLD = 0.6   # word-overlap fraction for "this blockquote IS that segment"


def headings(text: str) -> list[str]:
    return [m.group(2).strip() for m in HEADING_RE.finditer(text)]


def blockquote_hebrews(text: str) -> list[str]:
    return [m.group(1).strip() for m in BLOCKQUOTE_RE.finditer(text)]


def match_sequence(doc: str, sefaria_items: list[dict]) -> tuple[list[int], set[int]]:
    """Return (matched_index_sequence_in_document_order, set_of_covered_indices).
    Each blockquote is assigned the Sefaria segment it best overlaps, if any clears
    MATCH_THRESHOLD — verbatim copies score ~1.0, so a high bar is safe here."""
    item_words = {it["index"]: hebrew_word_set(it["hebrew"]) for it in sefaria_items}
    seq: list[int] = []
    covered: set[int] = set()
    for bq in blockquote_hebrews(doc):
        bq_words = hebrew_word_set(bq)
        if not bq_words:
            continue
        best_idx, best_score = None, 0.0
        for idx, words in item_words.items():
            if not words:
                continue
            score = len(bq_words & words) / len(words)
            if score > best_score:
                best_idx, best_score = idx, score
        if best_idx is not None and best_score >= MATCH_THRESHOLD:
            seq.append(best_idx)
            covered.add(best_idx)
    return seq, covered


def analyze(doc: str, sefaria_items: list[dict], rewrite_headings: list[str]) -> dict:
    seq, covered = match_sequence(doc, sefaria_items)

    inversions = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
    duplicates = len(seq) - len(set(seq))

    doc_headings = headings(doc)
    doc_set = [h for h in doc_headings]
    surviving = 0
    remaining = list(doc_set)
    for h in rewrite_headings:
        if h in remaining:
            remaining.remove(h)
            surviving += 1

    return {
        "gemara_covered": len(covered),
        "gemara_total": len(sefaria_items),
        "commentary_surviving": surviving,
        "commentary_total": len(rewrite_headings),
        "inversions": inversions,
        "duplicates": duplicates,
        "blockquotes": len(seq),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+")
    args = parser.parse_args()

    rows = []
    for d in args.dirs:
        daf_dir = Path(d)
        sefaria_path = daf_dir / "sefaria.md"
        rewrite_path = daf_dir / "02_rewrite.md"
        a_path = daf_dir / "03_final.md"
        b_path = daf_dir / "03_text_first_prototype_v3.md"

        if not (sefaria_path.exists() and rewrite_path.exists()):
            print(f"{daf_dir.name}: SKIP (missing sefaria.md or 02_rewrite.md)")
            continue

        sefaria_items = parse_sefaria_full(sefaria_path.read_text(encoding="utf-8"))
        rewrite_headings = headings(rewrite_path.read_text(encoding="utf-8", errors="replace"))

        for label, path in (("A", a_path), ("B", b_path)):
            if not path.exists():
                print(f"{daf_dir.name} [{label}]: SKIP (no {path.name})")
                continue
            stats = analyze(path.read_text(encoding="utf-8", errors="replace"),
                            sefaria_items, rewrite_headings)
            stats["daf"] = daf_dir.name
            stats["approach"] = label
            rows.append(stats)

    hdr = (f"{'daf':18s} {'app':4s} {'gemara covered':>16s} {'commentary kept':>17s} "
           f"{'out-of-order':>13s} {'dupes':>6s}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        gem = f"{r['gemara_covered']}/{r['gemara_total']} ({100*r['gemara_covered']/max(r['gemara_total'],1):.0f}%)"
        com = f"{r['commentary_surviving']}/{r['commentary_total']} ({100*r['commentary_surviving']/max(r['commentary_total'],1):.0f}%)"
        print(f"{r['daf']:18s} {r['approach']:4s} {gem:>16s} {com:>17s} "
              f"{r['inversions']:>13d} {r['duplicates']:>6d}")

    print("\nTotals by approach:")
    for label in ("A", "B"):
        sub = [r for r in rows if r["approach"] == label]
        if not sub:
            continue
        gc, gt = sum(r["gemara_covered"] for r in sub), sum(r["gemara_total"] for r in sub)
        cc, ct = sum(r["commentary_surviving"] for r in sub), sum(r["commentary_total"] for r in sub)
        inv, dup = sum(r["inversions"] for r in sub), sum(r["duplicates"] for r in sub)
        print(f"  {label}: gemara {gc}/{gt} ({100*gc/max(gt,1):.1f}%) | "
              f"commentary {cc}/{ct} ({100*cc/max(ct,1):.1f}%) | "
              f"out-of-order {inv} | dupes {dup}")


if __name__ == "__main__":
    main()
