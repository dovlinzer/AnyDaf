#!/usr/bin/env python3
"""
check_pass2_coverage.py — Heuristic local audit: does 02_rewrite.md (pass 2's essay)
cover every Talmudic quotation the lecturer reads aloud in the source SRT?

Free, local, no API cost — pure text matching, same spirit as
check_anchor_section_mismatch.py.

Background: pass 2 (rewrite_prompt) is the only pass that ever reads the raw SRT.
Everything downstream (2.5, 3, and the existing audits) only ever looks at what pass 2
wrote — so a passage pass 2 silently drops is invisible to every other check in the
pipeline. Found live on Hullin 88: a full statement-and-rejection exchange ("Darash Rav
Nachman bar Rav Chisda... Amar Rava: Hai burcha!") was never written into the essay at
all, despite the prompt's own explicit "CRITICAL — NO SKIPPING TALMUDIC TEXT" instruction
covering exactly this class of brief dialectical move.

METHOD
  1. Reconstruct the exact text pass 2 was given: srt_to_text(parse_srt(...)) — the same
     function pipeline.py feeds into rewrite_prompt().
  2. Scan that text for quote-introduction markers (Amar, Darash, Tanu Rabbanan, Tanya,
     etc.) — transliterated Aramaic connector words that virtually always introduce a new
     piece of Talmudic text being read aloud.
  3. For each marker, take the following ~12-word window as a candidate "quote signature"
     and break it into overlapping 4-word n-grams.
  4. Check whether ANY of those n-grams appears in 02_rewrite.md (normalized: lowercase,
     punctuation stripped). Per the rewrite prompt's own rule, a genuine direct quotation
     must survive as *italicized transliteration* somewhere in the essay — it does not need
     to survive verbatim as a whole phrase, but some contiguous chunk of the source words
     should.
  5. Flag markers with zero n-gram overlap as candidate dropped passages.

KNOWN LIMITATIONS — read before trusting a flag as a real defect:
  - Marker list is not exhaustive. This UNDER-reports (misses some real quote
    introductions) rather than over-reports on marker selection itself.
  - "Amar"/"Amru" are extremely common and mostly correctly covered — expect the large
    majority of flags on these to be false positives from paraphrase (the essay legitimately
    reworded the sentence around the quote, e.g. attribution moved, quote split across
    two sentences) rather than real omissions. Spot-check the flagged window against the
    essay's corresponding section before concluding content was actually dropped.
  - A marker whose following words are pure ATTRIBUTION ("Amar Rav Pappa") rather than
    quoted content can false-positive if the name itself doesn't recur verbatim nearby in
    the essay, even though the quote after the name is present.
  - This is a triage tool, not a certainty — same caveat as check_anchor_section_mismatch.py.

Usage:
    python check_pass2_coverage.py                      # whole corpus
    python check_pass2_coverage.py output/hullin_88      # single daf
    python check_pass2_coverage.py --top 30              # show N worst dafs (default 20)
"""

import argparse
import re
import sys
from pathlib import Path

from srt_parser import parse_srt, srt_to_text

OUTPUT_ROOT = Path(__file__).parent / "output"
SRT_DIR = Path(__file__).parent / "srt" / "processed"

_NORMALIZE = {
    "Eruvin": "Eiruvin",
    "Megilah": "Megillah",
    "Megila": "Megillah",
    "Chullin": "Hullin",
}

# The reverse problem from _NORMALIZE: here the segmentation JSON's `masechta` field already
# has the canonical spelling, but the SRT FILENAME on disk uses a different transliteration --
# found 2026-08-08 chasing 36 dafim (19 Taanit, 17 Megillah) that v10 assembly silently skipped
# as "no matching SRT" even though their SRTs exist. Taanit's files use a RIGHT SINGLE
# QUOTATION MARK (U+2019, "Ta’anit"), not a plain apostrophe -- a smart-quote variant, same
# general class as the Hebrew-text/curly-quote normalization drift documented elsewhere in this
# file. Megillah's files are spelled with one L ("Megilah"). Keyed by the canonical (post-
# _NORMALIZE) name; find_srt tries each alias after the canonical form fails.
_FILENAME_ALIASES = {
    "Taanit": ["Ta’anit", "Ta'anit"],
    "Megillah": ["Megilah"],
}

MARKERS = [
    r"Amar", r"Amru", r"Darash", r"Tanu Rabbanan", r"Tanya", r"Tana",
    r"Ika d.?amrei", r"Ta Shema", r"Meitivei", r"Rami", r"Iy Nami",
    r"Puk Chazi", r"Ba.?u Minei", r"Matnitin", r"Tanan", r"Tnan",
]
MARKER_RE = re.compile(r"\b(" + "|".join(MARKERS) + r")\b", re.IGNORECASE)

WINDOW_WORDS = 14
MIN_WINDOW_WORDS = 5   # skip markers too close to end-of-transcript to form a real window
MIN_CONTENT_WORDS = 3  # skip windows with too few non-stopword words to judge overlap on

# Common English filler — stripping these leaves mostly the transliterated Aramaic/Hebrew
# terms and proper nouns, which is exactly the content pass 2's own rules require to survive
# verbatim ("*italicized transliteration*") regardless of how the surrounding English is
# paraphrased. Matching on this filtered set tolerates reordering/rewording far better than
# raw n-grams over the full window did.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "so", "if", "of", "in", "on", "at", "to", "for",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these",
    "those", "we", "you", "he", "she", "they", "i", "my", "your", "his", "her", "our", "their",
    "not", "no", "yes", "do", "does", "did", "will", "would", "can", "could", "should", "may",
    "might", "must", "have", "has", "had", "as", "by", "with", "from", "about", "there", "here",
    "what", "when", "where", "why", "how", "who", "which", "says", "said", "say", "taught",
    "teach", "teaches", "means", "meant", "mean", "one", "some", "any", "all", "just", "now",
    "then", "than", "too", "also", "up", "out", "so", "okay", "well", "right", "know",
    "explain", "explains", "explained", "explanation",
}

# Ultra-common Aramaic/Hebrew connector and title words. Found live on Hullin 88: "Rav",
# "bar", "ein", "ela" (from "Darash Rav Nachman bar Rav Chisda... ein mechasin ela
# bedavar...") all satisfied the >=2-word overlap threshold by coincidentally recurring
# elsewhere in the essay (nearly every Amora's name contains "Rav" or "bar"; "ein"/"ela" are
# stock grammatical particles), even though the genuinely distinctive words in that same
# window (nachman, chisda, mechasin, bedavar, shezorin, umatzmiach) matched nothing and the
# passage was in fact completely absent — a false negative. These recur in essentially every
# Talmudic passage regardless of which specific quote is under discussion, so — same as
# English filler — they carry no evidence that *this particular* quote survived.
ARAMAIC_STOPWORDS = {
    "rav", "rabbi", "rabbah", "rebbi", "bar", "ein", "ela", "hai", "ika", "leka",
    "lo", "ki", "ka", "mai", "man", "hu", "ho", "da", "amar", "amru", "amara", "amaru",
    "gemara", "mishna", "mishnah", "tanna", "tannaim", "amora", "amoraim", "rabbanan",
}

# The quote-introduction markers themselves recur constantly (that's *why* they're used as
# markers) and are never, by construction, evidence that the specific quote after them
# survived — derived from MARKERS itself so the two lists can't drift apart.
_MARKER_WORDS = {
    w.lower() for phrase in
    (re.sub(r"[.?]", "", p) for p in
     ["Amar", "Amru", "Darash", "Tanu", "Rabbanan", "Tanya", "Tana", "Ika", "damrei",
      "Ta", "Shema", "Meitivei", "Rami", "Iy", "Nami", "Puk", "Chazi", "Bau", "Minei",
      "Matnitin", "Tanan", "Tnan"])
    for w in phrase.split()
}
STOPWORDS |= ARAMAIC_STOPWORDS | _MARKER_WORDS


def normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    text = re.sub(r"[^a-zA-Z0-9\s']", " ", text)
    return [w for w in text.lower().split() if w]


def content_words(words: list[str]) -> list[str]:
    """Non-stopword words — the transliterated/technical terms most likely to survive
    verbatim through a paraphrase, per pass 2's own quotation-preservation rule."""
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def phonetic_key(word: str) -> str:
    """
    Fold common Hebrew/Aramaic transliteration spelling variants to a rough
    consonant-skeleton key, so e.g. "lamikze" (SRT spelling) and "lemikze"/"lemiksa"
    (essay spelling) compare equal. Found live: Bava Batra 95's central sugya term was
    transliterated differently between the SRT and 02_rewrite.md, producing a false
    "dropped content" flag on thoroughly-covered material — transliteration has no fixed
    standard, so this kind of drift is routine, not a defect.

    Not a full phonetic algorithm, just folds the handful of ambiguities transliteration
    schemes disagree on most often (digraphs before single letters; order matters below).
    Deliberately conservative: the caller still requires 2+ independent word matches
    before treating something as "covered," so one coincidental key collision can't by
    itself hide a real omission.
    """
    w = word.lower()
    w = w.replace("tz", "z").replace("ts", "z")
    w = w.replace("ch", "k").replace("kh", "k")
    w = w.replace("sh", "s")
    w = w.replace("ph", "f")
    w = w.replace("q", "k").replace("c", "k")
    w = w.replace("w", "v")
    if len(w) > 1:
        w = w[0] + re.sub(r"[aeiouy']", "", w[1:])
    return w


def find_srt(masechta: str, daf: int, amud: str | None) -> Path | None:
    """
    The segmentation JSON's own `amud` field is unreliable as a filename suffix — it's
    set from filename parsing (parse_filename) and, per the find_amud_b.py investigation,
    is frequently a stale/misleading artifact rather than a genuine single-amud marker
    (Hullin 88 itself is a confirmed case: amud="b" even though the SRT and full daf's
    content live at "Hullin 88.srt", no "b" suffix). Try with the tag first, but always
    fall back to the bare "{masechta} {daf}.srt" form.
    """
    masechta = _NORMALIZE.get(masechta, masechta)
    for name in [masechta] + _FILENAME_ALIASES.get(masechta, []):
        for suffix in (amud or "", ""):
            candidate = SRT_DIR / f"{name} {daf}{suffix}.srt"
            if candidate.exists():
                return candidate
            target = f"{name.lower()} {daf}{suffix}.srt"
            for f in SRT_DIR.glob("*.srt"):
                if f.name.lower() == target:
                    return f
    return None


def audit_daf(daf_dir: Path) -> dict | str:
    import json
    seg_path = daf_dir / "01_segmentation.json"
    rewrite_path = daf_dir / "02_rewrite.md"
    if not seg_path.exists() or not rewrite_path.exists():
        return "SKIP (missing segmentation or rewrite)"

    try:
        seg = json.loads(seg_path.read_text())
    except Exception:
        return "SKIP (corrupt segmentation json)"

    masechta = seg.get("masechta")
    daf = seg.get("daf")
    amud = seg.get("amud")
    if not masechta or not daf:
        return "SKIP (no masechta/daf in segmentation)"

    srt_path = find_srt(masechta, int(daf), amud)
    if not srt_path:
        return f"SKIP (no matching SRT for {masechta} {daf}{amud or ''})"

    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not entries:
        return "SKIP (empty/unparseable SRT)"
    transcript = srt_to_text(entries)
    transcript_words = normalize(transcript)

    essay = rewrite_path.read_text(encoding="utf-8", errors="replace")
    essay_words = content_words(normalize(essay))
    essay_content_words = set(essay_words)
    essay_phonetic_keys = {phonetic_key(w) for w in essay_words}

    flags = []
    for m in MARKER_RE.finditer(transcript):
        # Work in word-space, not char-space, for windowing.
        prefix_words = normalize(transcript[:m.start()])
        start_idx = len(prefix_words)
        window = transcript_words[start_idx:start_idx + WINDOW_WORDS]
        if len(window) < MIN_WINDOW_WORDS:
            continue
        window_content = content_words(window)
        if len(window_content) < MIN_CONTENT_WORDS:
            continue
        matched = set(window_content) & essay_content_words
        matched_phonetic = {w for w in window_content if phonetic_key(w) in essay_phonetic_keys}
        all_matched = matched | matched_phonetic
        # Require at least two distinctive words (exact or phonetic-key match) to survive
        # somewhere in the essay; tolerant of paraphrase, reordering, and transliteration
        # spelling drift, but flags windows with near-zero trace either way.
        if len(all_matched) < 2:
            flags.append({
                "marker": m.group(1),
                "window": " ".join(window),
                "overlap": len(all_matched),
                "matched_words": sorted(all_matched),
                "content_words": len(window_content),
            })

    return {
        "label": f"{masechta} {daf}{amud or ''}",
        "marker_count": len(list(MARKER_RE.finditer(transcript))),
        "flags": flags,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="*", help="Specific output dir(s) to check (default: all)")
    parser.add_argument("--top", type=int, default=20, help="Show N worst dafs by flag count")
    args = parser.parse_args()

    dirs = [Path(d) for d in args.dirs] if args.dirs else sorted(OUTPUT_ROOT.iterdir())

    results = []
    skipped = 0
    for d in dirs:
        if not d.is_dir():
            continue
        r = audit_daf(d)
        if isinstance(r, str):
            skipped += 1
            continue
        results.append(r)

    total_flags = sum(len(r["flags"]) for r in results)
    flagged_dafs = [r for r in results if r["flags"]]

    print(f"Checked {len(results)} dafs ({skipped} skipped — no SRT match or missing files)")
    print(f"{len(flagged_dafs)} dafs have at least one flag, {total_flags} total flags\n")

    flagged_dafs.sort(key=lambda r: len(r["flags"]), reverse=True)
    for r in flagged_dafs[:args.top]:
        print(f"{r['label']:25s}  {len(r['flags'])} flags / {r['marker_count']} markers checked")

    if len(args.dirs) == 1:
        r = results[0] if results else None
        if r:
            print(f"\n=== Detail for {r['label']} ===")
            for f in r["flags"]:
                matched = f"matched={f['matched_words']}" if f["matched_words"] else "matched=NONE"
                print(f"  [{f['marker']}] ({matched}) {f['window']}")


if __name__ == "__main__":
    main()
