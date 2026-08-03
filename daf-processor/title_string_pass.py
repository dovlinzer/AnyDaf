#!/usr/bin/env python3
"""
title_string_pass.py — content-based header sync for the "108 count-mismatched" set
(see CLAUDE.md, "apply_display_titles.py matches POSITIONALLY"; title_pass_mismatched.txt).

apply_display_titles.py zips segmentation display_titles against ##/### headings by
INDEX — safe only when the counts match exactly, which the mismatched set by definition
doesn't. sync_md_headers.py only handles one narrow case (a display_title that gained a
"(II)"-style rank suffix, where the old un-suffixed heading is still findable by exact
text search) — not applicable when the essay's own headings are independently-written
full sentences that were never derived from display_title at all (found live on
Berakhot 31b: segmentation has 33 micro display_titles, the essay has only 32 ###
headings — pass 2 evidently wrote one heading covering two adjacent micro-topics).

This script instead aligns the two ordered lists (segmentation display_titles, essay
headings — separately per level, ## and ###) by CONTENT similarity, not position or
exact string match, via a monotonic edit-distance-style DP: each side can skip entries
(a segmentation topic that got no separate heading; a stray essay heading with no
segmentation counterpart) at a fixed penalty, and matched pairs score by word overlap
(exact + phonetic, reusing check_pass2_coverage.py's normalize/content_words/
phonetic_key — the same "does this transliteration/content word survive" signal already
used elsewhere in this pipeline). Both sequences are chronological/document-order, so a
monotonic alignment (never matching segmentation entry i to an essay heading after
matching i+1 to an earlier one) is the right structural assumption — same idea as
prototype_text_first_v10.py's align_constrained(), one level up (labels, not text).

Dry-run by default — prints the proposed mapping (old heading -> new display_title,
score) for review. Low-confidence matches (score below MIN_CONFIDENCE) are always
flagged and never auto-applied, even with --apply, since a wrong header rewrite here is
exactly the kind of silent mislabeling apply_display_titles.py's own gotcha warns about.

Usage:
    python title_string_pass.py output/berakhot_31b              # dry run, single daf
    python title_string_pass.py output/berakhot_31b --apply       # write changes
    python title_string_pass.py --mismatched-file title_pass_mismatched.txt --apply
"""
import argparse
import json
import re
import sys
from pathlib import Path

from check_pass2_coverage import normalize, content_words, phonetic_key
from prototype_text_first import parse_essay_sections

SKIP_PENALTY = -1.0   # cost of leaving a segmentation entry or essay heading unmatched
MIN_CONFIDENCE = 2    # matched pairs scoring below this are flagged, never auto-applied


PREFIX_LEN = 4  # two content words sharing this long a common PREFIX (not fixed-slice) are treated as the same root


def _strip_possessive(word: str) -> str:
    return word[:-2] if word.endswith("'s") else word


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n


def similarity(seg_title: str, heading_text: str) -> float:
    """Word overlap, scored on three tiers: exact, phonetic-key (transliteration
    spelling variants — see check_pass2_coverage.py's phonetic_key), and shared-prefix
    (catches inflectional/derivational suffix mismatches phonetic_key doesn't fold,
    e.g. segmentation's 'Samuel Paskens' vs the essay's 'paskening' — found live on
    Berakhot 31b, where several genuinely-correct pairs scored 0 on exact+phonetic
    alone). Possessives ("Body's") are also stripped before comparing — the raw
    apostrophe otherwise blocks an exact match against the essay's unpossessed form."""
    seg_words = [_strip_possessive(w) for w in content_words(normalize(seg_title))]
    head_words = [_strip_possessive(w) for w in content_words(normalize(heading_text))]
    if not seg_words or not head_words:
        return 0.0
    head_set = set(head_words)
    head_phonetic = {phonetic_key(w) for w in head_words}
    score = 0.0
    for w in seg_words:
        if w in head_set:
            score += 1.0
        elif phonetic_key(w) in head_phonetic:
            score += 1.0
        elif any(_common_prefix_len(w, hw) >= PREFIX_LEN for hw in head_words):
            score += 0.75
    return score


def align(seg_titles: list[str], headings: list[str]) -> list[tuple[int, int | None, float]]:
    """Monotonic alignment allowing skips on both sides. Returns, for each essay heading
    index j, the (j, matched_seg_index_or_None, score) triple — segmentation index None
    means no segmentation entry matched well enough to justify pairing (heading left as-is)."""
    n, m = len(seg_titles), len(headings)
    NEG = float("-inf")
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, choice = NEG, None
            if i > 0 and dp[i - 1][j] != NEG:
                val = dp[i - 1][j]  # skip segmentation entry i-1
                if val > best:
                    best, choice = val, ("skip_seg", i - 1, j)
            if j > 0 and dp[i][j - 1] != NEG:
                val = dp[i][j - 1] + SKIP_PENALTY  # skip essay heading j-1
                if val > best:
                    best, choice = val, ("skip_head", i, j - 1)
            if i > 0 and j > 0 and dp[i - 1][j - 1] != NEG:
                sim = similarity(seg_titles[i - 1], headings[j - 1])
                val = dp[i - 1][j - 1] + sim
                if val > best:
                    best, choice = val, ("match", i - 1, j - 1, sim)
            dp[i][j] = best
            back[i][j] = choice

    # Backtrack, collecting one entry per essay heading (skip_head -> None match).
    result: dict[int, tuple[int | None, float]] = {}
    i, j = n, m
    while not (i == 0 and j == 0):
        choice = back[i][j]
        kind = choice[0]
        if kind == "skip_seg":
            i, j = i - 1, j
        elif kind == "skip_head":
            _, i2, j2 = choice
            result[j2] = (None, 0.0)
            i, j = i2, j2
        else:  # match
            _, si, hj, sim = choice
            result[hj] = (si, sim)
            i, j = si, hj
    return [(j, result[j][0], result[j][1]) for j in sorted(result)]


def process_daf(daf_dir: Path, level: str, apply: bool) -> list[str]:
    """level: 'macro' (##) or 'micro' (###)."""
    seg_path = daf_dir / "01_segmentation.json"
    rewrite_path = daf_dir / "02_rewrite.md"
    if not seg_path.exists() or not rewrite_path.exists():
        return []
    seg = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
    macro_segments = seg.get("macro_segments", [])

    if level == "macro":
        seg_titles = [m.get("display_title", "") for m in macro_segments]
        heading_level = 2
    else:
        seg_titles = [mi.get("display_title", "") for m in macro_segments for mi in m.get("micro_segments", [])]
        heading_level = 3

    essay = rewrite_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_essay_sections(essay)
    headings = [s for s in sections if s["level"] == heading_level]
    heading_texts = [s["title"] for s in headings]

    if len(seg_titles) == len(heading_texts):
        return []  # already aligned at this level — apply_display_titles.py handles it

    pairs = align(seg_titles, heading_texts)
    lines = essay.split("\n") if apply else None
    report = []
    changed = False
    for j, si, score in pairs:
        old_title = heading_texts[j]
        if si is None:
            report.append(f"  [unmatched] {'#'*heading_level} {old_title!r} — no segmentation entry scored, left as-is")
            continue
        new_title = seg_titles[si]
        if new_title == old_title:
            continue
        flag = "" if score >= MIN_CONFIDENCE else "  *** LOW CONFIDENCE — not auto-applied ***"
        report.append(f"  {'#'*heading_level} {old_title!r} -> {new_title!r}  (score={score:.2f}){flag}")
        if apply and score >= MIN_CONFIDENCE:
            old_line = f"{'#'*heading_level} {old_title}"
            new_line = f"{'#'*heading_level} {new_title}"
            for k, line in enumerate(lines):
                if line == old_line:
                    lines[k] = new_line
                    changed = True
                    break
    if apply and changed:
        backup = rewrite_path.with_suffix(rewrite_path.suffix + ".bak_before_title_string_pass")
        if not backup.exists():
            backup.write_text(essay, encoding="utf-8")
        rewrite_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*", help="Output dir(s) to process")
    ap.add_argument("--mismatched-file", help="Process every daf listed in this file (e.g. title_pass_mismatched.txt)")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = ap.parse_args()

    dirs = [Path(d) for d in args.dirs]
    if args.mismatched_file:
        for line in Path(args.mismatched_file).read_text().splitlines():
            name = line.split("\t")[0].strip()
            if name:
                dirs.append(Path("output") / name)

    if not dirs:
        print("No dafim specified.", file=sys.stderr)
        sys.exit(1)

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"{mode} — {len(dirs)} daf(im)\n")
    for d in dirs:
        report = process_daf(d, "macro", args.apply) + process_daf(d, "micro", args.apply)
        if report:
            print(f"{d.name}:")
            for line in report:
                print(line)
            print()


if __name__ == "__main__":
    main()
