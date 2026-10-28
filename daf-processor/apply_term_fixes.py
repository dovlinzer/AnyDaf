"""Apply term_fixes.fix_terms to every saved English text (no API cost).

Covers the saved Bavli text (daf_text/*.json), the cached Sefaria files and the shiur essays
under output/ and review_v10_relocated/, and the segmentation titles. A Translation line is
paired with the Hebrew/Aramaic line above it, so the Hebrew-gated "insane" rules apply too.

    python apply_term_fixes.py            # dry run: counts only
    python apply_term_fixes.py --write
"""
import argparse
import glob
import json
import re
from pathlib import Path

from term_fixes import fix_terms

ROOT = Path(__file__).parent
HE_LINE = re.compile(r"Hebrew/Aramaic:\**\s*(.*)")


def fix_markdown(text):
    """Fix each line; a Translation line also sees the Hebrew of its own item."""
    out, he = [], None
    for line in text.split("\n"):
        m = HE_LINE.search(line)
        if m:
            he = m.group(1)
        elif "Translation:" in line:
            line = fix_terms(line, he)
            he = None
        else:
            line = fix_terms(line)
        out.append(line)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    changed = {}

    for f in sorted(glob.glob(str(ROOT / "daf_text" / "*.json"))):
        d = json.load(open(f))
        n = 0
        for amud in d["amudim"].values():
            for seg in amud.get("segments", []):
                new = fix_terms(seg.get("en"), seg.get("he"))
                if new != seg.get("en"):
                    seg["en"] = new
                    n += 1
        if n:
            changed[f] = n
            if args.write:
                json.dump(d, open(f, "w"), ensure_ascii=False)

    md = [p for pat in ("output/*/*.md", "review_v10_relocated/*.md") for p in glob.glob(str(ROOT / pat))]
    for f in sorted(md):
        text = open(f).read()
        if "mbecil" not in text and "insan" not in text and "incompeten" not in text and "crazy" not in text:
            continue
        new = fix_markdown(text)
        if new != text:
            changed[f] = sum(a != b for a, b in zip(text.split("\n"), new.split("\n")))
            if args.write:
                open(f, "w").write(new)

    for f in sorted(glob.glob(str(ROOT / "output" / "*" / "01_segmentation.json"))):
        text = open(f).read()
        if "mbecil" not in text:
            continue
        new = fix_terms(text)
        if new != text:
            changed[f] = text.count("mbecil")
            if args.write:
                open(f, "w").write(new)

    print(f"{len(changed)} files, {sum(changed.values())} lines {'changed' if args.write else 'to change'}")
    for kind in ("daf_text", "sefaria", "03_final", "02_rewrite", "review_v10", "01_segmentation"):
        print(f"  {kind}: {sum(1 for f in changed if kind in f)} files")


if __name__ == "__main__":
    main()
