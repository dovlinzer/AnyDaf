#!/usr/bin/env python3
"""
prototype_text_first_v3.py — PROTOTYPE. Sefaria-first document assembly.

Fixes the two defects v2 exposed on unseen dafim:

1. ADJACENT DAF TEXT (found on Sanhedrin 6b). A shiur routinely runs past its own daf's
   boundaries — Sanhedrin 6b's lecture continues well into 7a. v2 only read sefaria.md,
   so 10 of its 11 "missing" passages were scored as unrecoverable losses when in fact
   they sit in the already-cached sefaria_next.md. The real pass 3 passes prev/next as
   context for exactly this reason. v3 pools all three into one continuous index space.

2. BOOTSTRAP POISONING (found on bekhorot_10). v2 walked forward greedily with a
   monotonic pointer: the first candidate crossing threshold won, and everything before
   it became permanently unreachable. On bekhorot_10 a spurious match on segment #32 at
   0:31 (during the intro) truncated 82% of the daf silently. v3 instead scores every
   segment independently against its best-matching transcript window, then keeps the
   longest chronologically-consistent run — so a lone temporal outlier is discarded
   instead of dictating the alignment.

Placement uses no LLM: the SRT already contains the Hebrew the lecturer reads aloud, so
"when was segment N recited" is local text matching; pass 1 already timestamped every
essay section. Aligning three time-indexed sequences is arithmetic, not comprehension.
Assembly is pure string slicing, so content cannot be dropped or fabricated — both
invariants are asserted numerically before anything is written.

Usage:
    python prototype_text_first_v3.py output/hullin_88
    python prototype_text_first_v3.py --all --diagnose      # corpus scan, writes nothing
"""

import argparse
import json
import re
from bisect import bisect_right
from pathlib import Path

from check_pass2_coverage import find_srt
from prototype_text_first import parse_sefaria_full, parse_essay_sections
from prototype_text_first_v2 import (
    hebrew_word_set, srt_seconds, mmss_seconds, assemble_complete,
)
from srt_parser import parse_srt

OUTPUT_ROOT = Path(__file__).parent / "output"

MISLABELED = {
    "avodah_zarah_7", "hullin_136", "ketubot_35", "megillah_24", "nedarim_3",
    "pesachim_15", "rosh_hashanah_14", "shabbat_91", "sukkah_54", "moed_katan_27",
    "hullin_70", "shabbat_90", "moed_katan_28", "yevamot_59b", "nazir_36",
    "megillah_30", "nazir_33", "nedarim_86", "nedarim_86b", "pesachim_19",
}

# Transcript entries a single Sefaria segment may be recited across. Was 40, which spans a
# MEDIAN OF 2.0 MINUTES — long enough that two minutes of the lecturer *reviewing* a sugya
# accumulates enough of its shared Hebrew vocabulary (ערב, לוה, מלוה, גמרא...) to "cover"
# segments that were never recited at all. Found on Bava Batra 174b, whose opening is a
# contextual recap of the previous daf: segments 6, 7, 15, 16 and 17 all matched inside one
# minute (two at a perfect 1.00), putting six unrelated passages ahead of the lecturer's
# first words. 20 entries (~1 minute) requires the words to arrive in a tight burst, which
# is what actual recitation looks like; review-chatter no longer clears the bar.
WINDOW_ENTRIES = 20
DEFAULT_THRESHOLD = 0.5  # fraction of a segment's distinct Hebrew words needed to count
MIN_SEGMENT_WORDS = 4    # segments with fewer distinct words are too short to match safely


def build_pool(daf_dir: Path) -> list[dict]:
    """Unified, continuously-indexed pool across prev/current/next daf texts.

    A shiur's true span is not bounded by its own daf — pooling lets the span detector
    find the real start and end rather than clipping at an arbitrary file boundary."""
    pool: list[dict] = []
    for fn in ("sefaria_prev.md", "sefaria.md", "sefaria_next.md"):
        p = daf_dir / fn
        if not p.exists():
            continue
        for it in parse_sefaria_full(p.read_text(encoding="utf-8", errors="replace")):
            pool.append({
                "index": len(pool),          # continuous across all three files
                "source": fn,
                "local_index": it["index"],
                "hebrew": it["hebrew"],
                "translation": it["translation"],
            })
    return pool


def best_match_times(entries, pool: list[dict], threshold: float) -> list[tuple[int, float, float]]:
    """For each pooled segment, the transcript time at which it is best recited.

    Scored independently per segment (no forward-only pointer), so no single early
    mistake can lock out later — or earlier — material. Returns [(index, time, score)]
    for segments clearing `threshold`, sorted by segment index."""
    entry_words = [hebrew_word_set(e.text) for e in entries]
    entry_times = [srt_seconds(e.start_time) for e in entries]

    # Inverted index: Hebrew word -> entries containing it. Lets each segment consider
    # only windows that could plausibly contain it, instead of scanning the whole
    # transcript for every segment.
    word_to_entries: dict[str, set[int]] = {}
    for i, ws in enumerate(entry_words):
        for w in ws:
            word_to_entries.setdefault(w, set()).add(i)

    results: list[tuple[int, float, float]] = []
    for seg in pool:
        seg_words = hebrew_word_set(seg["hebrew"])
        if len(seg_words) < MIN_SEGMENT_WORDS:
            continue

        candidates = set()
        for w in seg_words:
            candidates |= word_to_entries.get(w, set())
        if not candidates:
            continue

        best_score, best_time = 0.0, None
        for start in sorted(candidates):
            acc: set[str] = set()
            for j in range(start, min(start + WINDOW_ENTRIES, len(entry_words))):
                acc |= entry_words[j]
                score = len(acc & seg_words) / len(seg_words)
                if score > best_score:
                    best_score, best_time = score, entry_times[start]
                if score >= 0.999:
                    break
            if best_score >= 0.999:
                break

        if best_time is not None and best_score >= threshold:
            results.append((seg["index"], best_time, best_score))

    results.sort(key=lambda r: r[0])
    return results


def longest_consistent_run(matches: list[tuple[int, float, float]]) -> list[tuple[int, float, float]]:
    """Keep the largest subset whose times are non-decreasing as segment index increases.

    The lecture proceeds forward through the text, so a segment matching at a time
    inconsistent with its neighbours is a false positive (bekhorot_10's #32 at 0:31).
    Classic O(n log n) longest-non-decreasing-subsequence over time."""
    if not matches:
        return []
    tails: list[float] = []
    tail_idx: list[int] = []
    parent = [-1] * len(matches)

    for i, (_, t, _) in enumerate(matches):
        pos = bisect_right(tails, t)
        if pos == len(tails):
            tails.append(t)
            tail_idx.append(i)
        else:
            tails[pos] = t
            tail_idx[pos] = i
        parent[i] = tail_idx[pos - 1] if pos > 0 else -1

    out = []
    k = tail_idx[len(tails) - 1]
    while k != -1:
        out.append(matches[k])
        k = parent[k]
    return out[::-1]


def assign_anchors(sections: list[dict], boundaries: dict[int, float], daf_dir: Path) -> None:
    """Anchor each essay section to the last Gemara segment recited at or before the
    section's own timestamp. Sections are matched to pass 1's timestamps POSITIONALLY —
    title-string matching across independently-generated passes is unreliable (see
    AnyDaf/CLAUDE.md 'Bug 3')."""
    seg = json.loads((daf_dir / "01_segmentation.json").read_text(errors="replace"))
    macro_segments = seg.get("macro_segments", [])

    groups: list[tuple[dict, list[dict]]] = []
    for sec in sections:
        if sec["level"] == 2:
            groups.append((sec, []))
        elif groups:
            groups[-1][1].append(sec)

    ts_for_section: dict[int, float] = {}
    if len(groups) == len(macro_segments):
        for (macro_sec, micro_secs), macro in zip(groups, macro_segments):
            ts_for_section[id(macro_sec)] = mmss_seconds(macro["timestamp"])
            micros = macro.get("micro_segments", [])
            if len(micro_secs) == len(micros):
                for micro_sec, micro in zip(micro_secs, micros):
                    ts_for_section[id(micro_sec)] = mmss_seconds(micro["timestamp"])

    ordered = sorted(boundaries.items(), key=lambda kv: kv[1])
    for sec in sections:
        t = ts_for_section.get(id(sec))
        if t is None:
            sec["anchor_index"] = None
            continue
        anchor = None
        for idx, bt in ordered:
            if bt <= t:
                anchor = idx
            else:
                break
        sec["anchor_index"] = anchor


def process(daf_dir: Path, threshold: float, diagnose: bool) -> dict | None:
    seg_path = daf_dir / "01_segmentation.json"
    if not (seg_path.exists() and (daf_dir / "02_rewrite.md").exists()
            and (daf_dir / "sefaria.md").exists()):
        return None
    try:
        seg = json.loads(seg_path.read_text(errors="replace"))
    except Exception:
        return None
    masechta, daf = seg.get("masechta"), seg.get("daf")
    if not masechta or not daf:
        return None
    srt_path = find_srt(masechta, int(daf), seg.get("amud"))
    if not srt_path:
        return None

    pool = build_pool(daf_dir)
    if not pool:
        return None
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not entries:
        return None

    raw = best_match_times(entries, pool, threshold)
    kept = longest_consistent_run(raw)
    discarded = len(raw) - len(kept)
    boundaries = {idx: t for idx, t, _ in kept}

    essay = (daf_dir / "02_rewrite.md").read_text(encoding="utf-8", errors="replace")
    sections = parse_essay_sections(essay)
    assign_anchors(sections, boundaries, daf_dir)

    span_start = min(boundaries) if boundaries else 0
    span_end = max(boundaries) if boundaries else len(pool) - 1

    n_current = sum(1 for s in pool if s["source"] == "sefaria.md")
    covered_current = sum(1 for i in boundaries
                          if pool[i]["source"] == "sefaria.md")

    span_total = span_end - span_start + 1 if boundaries else 0
    srt_heb = len(re.findall(r"[\u0590-\u05ff]", srt_path.read_text(encoding="utf-8", errors="replace")))

    stats = {
        "in_span_matched": len(boundaries),
        "in_span_total": span_total,
        "srt_heb": srt_heb,
        "daf": daf_dir.name,
        "label": f"{masechta} {daf}{seg.get('amud') or ''}",
        "pool": len(pool),
        "matched": len(boundaries),
        "discarded": discarded,
        "current_total": n_current,
        "current_covered": covered_current,
        "span": (span_start, span_end),
        "sections": len(sections),
        "anchored": sum(1 for s in sections if s["anchor_index"] is not None),
    }

    if not diagnose:
        doc, n_sec, n_items = assemble_complete(sections, pool, span_start, span_end)
        expected = span_end - span_start + 1
        assert n_sec == len(sections), f"section loss {n_sec}/{len(sections)}"
        assert n_items == expected, f"sefaria loss {n_items}/{expected}"
        out = daf_dir / "03_text_first_prototype_v3.md"
        out.write_text(doc, encoding="utf-8")
        stats["wrote"] = str(out)
        stats["emitted_sections"] = n_sec
        stats["emitted_items"] = n_items
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--all", action="store_true", help="scan every output/ dir")
    ap.add_argument("--diagnose", action="store_true", help="report only, write nothing")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()

    dirs = sorted(OUTPUT_ROOT.iterdir()) if args.all else [Path(d) for d in args.dirs]

    rows = []
    for d in dirs:
        if not d.is_dir():
            continue
        try:
            s = process(d, args.threshold, args.diagnose)
        except AssertionError as e:
            print(f"{d.name}: COMPLETENESS ASSERTION FAILED — {e}")
            continue
        if s:
            rows.append(s)

    if not args.all:
        for s in rows:
            cov = 100 * s["current_covered"] / max(s["current_total"], 1)
            print(f"\n{s['label']}  ({s['daf']})")
            print(f"  pool {s['pool']} segs (prev+cur+next) | matched {s['matched']} "
                  f"| discarded as inconsistent {s['discarded']}")
            print(f"  own-daf coverage {s['current_covered']}/{s['current_total']} ({cov:.0f}%)"
                  f" | span [{s['span'][0]}, {s['span'][1]}]")
            print(f"  sections {s['sections']} (anchored {s['anchored']})")
            if "wrote" in s:
                print(f"  completeness verified: {s['emitted_sections']}/{s['sections']} sections, "
                      f"{s['emitted_items']} segments -> {s['wrote']}")
        return

    excluded = [r for r in rows if r["daf"] in MISLABELED]
    no_heb = [r for r in rows if r["daf"] not in MISLABELED and r["srt_heb"] < 200]
    rows = [r for r in rows if r["daf"] not in MISLABELED and r["srt_heb"] >= 200]

    print(f"\nScanned {len(rows) + len(excluded) + len(no_heb)} dafs")
    print(f"  excluded {len(excluded)} known-mislabeled (wrong audio for the daf)")
    print(f"  excluded {len(no_heb)} with no Hebrew in the SRT (method cannot apply)")
    print(f"  analyzing {len(rows)}\n")

    ins = [100 * r["in_span_matched"] / max(r["in_span_total"], 1) for r in rows]
    ins.sort()
    def pct(v): return ins[int(len(ins) * v)] if ins else 0
    print("IN-SPAN alignment rate (of the text the lecturer actually covered):")
    print(f"  median {pct(0.50):.0f}%  |  25th {pct(0.25):.0f}%  |  10th {pct(0.10):.0f}%\n")
    ib = {"strong (>=85%)": 0, "ok (70-84%)": 0, "weak (50-69%)": 0, "poor (<50%)": 0}
    for v in ins:
        if v >= 85: ib["strong (>=85%)"] += 1
        elif v >= 70: ib["ok (70-84%)"] += 1
        elif v >= 50: ib["weak (50-69%)"] += 1
        else: ib["poor (<50%)"] += 1
    for k, v in ib.items():
        print(f"  {k:16s} {v:5d}  ({100*v/max(len(ins),1):.1f}%)")
    print()
    buckets = {"strong (>=80%)": 0, "ok (50-79%)": 0, "weak (20-49%)": 0, "poor (<20%)": 0}
    for s in rows:
        cov = 100 * s["current_covered"] / max(s["current_total"], 1)
        if cov >= 80: buckets["strong (>=80%)"] += 1
        elif cov >= 50: buckets["ok (50-79%)"] += 1
        elif cov >= 20: buckets["weak (20-49%)"] += 1
        else: buckets["poor (<20%)"] += 1
    for k, v in buckets.items():
        print(f"  {k:16s} {v:5d}  ({100*v/max(len(rows),1):.1f}%)")

    worst = [r for r in rows if r["current_covered"] / max(r["current_total"], 1) < 0.20]
    worst.sort(key=lambda s: s["current_covered"] / max(s["current_total"], 1))
    print(f"\nAll {len(worst)} dafs under 20% (dir / label / coverage):")
    for s in worst:
        cov = 100 * s["current_covered"] / max(s["current_total"], 1)
        print(f"  {s['daf']:22s} {s['label']:16s} {s['current_covered']:3d}/{s['current_total']:<3d} ({cov:4.0f}%)")


if __name__ == "__main__":
    main()
