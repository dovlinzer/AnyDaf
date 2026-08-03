#!/usr/bin/env python3
"""
check_recitation_restart.py — corpus-wide scan for the Niddah 60 "Ketem B'Ketem" pattern:
a lecturer states a question/phrase informally, then circles back moments later to recite
it formally (quote, then translate) -- and pass 1 mistakes that formal re-recitation for the
START OF A NEW TOPIC, splitting one continuous question into two macro/micro segments.

Signature: the Hebrew/Aramaic spoken in the ~45s right AFTER a segment boundary shares a
verbatim 4+ word run with the Hebrew/Aramaic spoken in the ~150s right BEFORE it. Free,
mechanical, no LLM calls -- reuses hebrew_word_set's normalization from prototype_text_first_v2.

Usage:
    python check_recitation_restart.py                # scan whole corpus, print summary
    python check_recitation_restart.py --list          # also list every flagged boundary
    python check_recitation_restart.py output/niddah_60 # single daf, verbose
"""
import argparse
import json
from pathlib import Path

from prototype_text_first_v2 import hebrew_word_set, srt_seconds, mmss_seconds
from srt_parser import parse_srt
from check_pass2_coverage import find_srt

OUTPUT_ROOT = Path(__file__).parent / "output"
BEFORE_WINDOW = 150.0   # seconds to look back before the boundary
AFTER_WINDOW = 45.0     # seconds to look forward after the boundary
NGRAM = 4                # consecutive-word run length that counts as "the same phrase"


MIN_DISTINCT = 3  # require the shared n-gram to have >=3 distinct words -- filters out
                   # simple ABAB emphasis-repetition ("Rabbi Chiya Rabbi Chiya") which is
                   # ordinary oratory, not a duplicated-topic signature.


def ngrams(words: list[str], n: int) -> set[tuple]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)
            if len(set(words[i:i + n])) >= MIN_DISTINCT}


def ordered_hebrew_words(text: str) -> list[str]:
    # hebrew_word_set drops order; rebuild an ordered, normalized list the same way.
    from prototype_text_first_v2 import HEBREW_WORD_RE, normalize_hebrew_word, MIN_WORD_LEN
    words = [normalize_hebrew_word(w) for w in HEBREW_WORD_RE.findall(text)]
    return [w for w in words if len(w) >= MIN_WORD_LEN]


def check_daf(daf_dir: Path, verbose: bool) -> list[dict]:
    seg_path = daf_dir / "01_segmentation.json"
    if not seg_path.exists():
        return []
    try:
        seg = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    masechta, daf = seg.get("masechta"), seg.get("daf")
    if not masechta or not daf:
        return []
    srt_path = find_srt(masechta, int(daf), seg.get("amud"))
    if not srt_path:
        return []
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not entries:
        return []

    times = [srt_seconds(e.start_time) for e in entries]
    texts = [e.text for e in entries]

    def words_in_window(t_start: float, t_end: float) -> list[str]:
        buf = []
        for t, txt in zip(times, texts):
            if t_start <= t < t_end:
                buf.append(txt)
        return ordered_hebrew_words(" ".join(buf))

    flags = []
    macro_segments = seg.get("macro_segments", [])
    for mi, macro in enumerate(macro_segments):
        if mi == 0:
            continue  # first macro has no "before" content in this daf's own transcript
        ts = mmss_seconds(macro.get("timestamp", "0:00"))
        before = words_in_window(max(0.0, ts - BEFORE_WINDOW), ts)
        after = words_in_window(ts, ts + AFTER_WINDOW)
        if len(before) < NGRAM or len(after) < NGRAM:
            continue
        shared = ngrams(before, NGRAM) & ngrams(after, NGRAM)
        if shared:
            flags.append({
                "daf": daf_dir.name,
                "label": f"{masechta} {daf}{seg.get('amud') or ''}",
                "macro_title": macro.get("display_title"),
                "timestamp": macro.get("timestamp"),
                "shared_phrase": " ".join(next(iter(shared))),
                "n_shared": len(shared),
            })
            if verbose:
                print(f"  FLAG: macro '{macro.get('display_title')}' @ {macro.get('timestamp')} "
                      f"repeats phrase: {' '.join(next(iter(shared)))!r} ({len(shared)} shared 4-grams)")
    return flags


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--list", action="store_true", help="List every flagged boundary, not just the summary")
    args = ap.parse_args()

    if args.dirs:
        dafim = [Path(d) for d in args.dirs]
        verbose = True
    else:
        dafim = sorted(p.parent for p in OUTPUT_ROOT.glob("*/01_segmentation.json"))
        verbose = False

    all_flags = []
    total_boundaries = 0
    dafim_checked = 0
    for d in dafim:
        seg_path = d / "01_segmentation.json"
        if seg_path.exists():
            try:
                seg = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
                total_boundaries += max(0, len(seg.get("macro_segments", [])) - 1)
            except Exception:
                pass
        flags = check_daf(d, verbose)
        if flags:
            dafim_checked += 1
            all_flags.extend(flags)

    print(f"\nScanned {len(dafim)} daf dirs, {total_boundaries} macro boundaries checked.")
    print(f"Flagged: {len(all_flags)} boundaries across {dafim_checked} dafim "
          f"({len(all_flags) / total_boundaries * 100:.1f}% of boundaries)." if total_boundaries else "")

    if args.list or args.dirs:
        for f in all_flags:
            print(f"  {f['label']:30s} {f['timestamp']:>6s}  {f['macro_title']:30s}  "
                  f"repeats: {f['shared_phrase']!r}")


if __name__ == "__main__":
    main()
