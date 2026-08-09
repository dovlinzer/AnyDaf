#!/usr/bin/env python3
"""promote_to_final.py — copies apply_moves_batch.py's output (the final, post-relocate
essay) to output/{daf}/03_final.md, the file upload_to_supabase.py and the apps read from.

Deliberately a separate, explicit step from apply_moves_batch.py rather than an automatic
last line of it -- per CLAUDE.md's corpus-wide order (header fix -> wall-of-text -> v10 ->
relocate -> prev-daf-boundary hand-patch -> PROMOTE -> find_sefaria_indices -> find_amud_b ->
upload), promotion must happen AFTER the Hullin-88-class hand-patch check, not before, or
that check's whole point (catching a dropped opening before it ships) is moot. Never run this
before that check has been done for the daf(im) in question.

Usage:
    python promote_to_final.py sanhedrin_67 shabbat_11 --suffix _wallpatched_split
    python promote_to_final.py --all --suffix _wallpatched_split
    python promote_to_final.py --all --suffix _wallpatched_split --dry-run
"""
import argparse
import glob
import os
import shutil

HERE = os.path.dirname(__file__)
REL_DIR = os.path.join(HERE, "review_v10_relocated")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dafim", nargs="*")
    ap.add_argument("--all", action="store_true",
                     help="Promote every daf that has a {daf}{suffix}_relocated.md")
    ap.add_argument("--suffix", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all:
        dafim = sorted(
            os.path.basename(p)[:-len(f"{args.suffix}_relocated.md")]
            for p in glob.glob(os.path.join(REL_DIR, f"*{args.suffix}_relocated.md"))
        )
    elif args.dafim:
        dafim = args.dafim
    else:
        ap.error("pass daf name(s) or --all")

    for daf in dafim:
        src = os.path.join(REL_DIR, f"{daf}{args.suffix}_relocated.md")
        dst_dir = os.path.join(HERE, "output", daf)
        dst = os.path.join(dst_dir, "03_final.md")
        if not os.path.exists(src):
            print(f"{daf}: SKIP (no {src})")
            continue
        if not os.path.isdir(dst_dir):
            print(f"{daf}: SKIP (no output dir {dst_dir})")
            continue
        if args.dry_run:
            print(f"{daf}: would copy {src} -> {dst}")
            continue
        if os.path.exists(dst):
            shutil.copy2(dst, dst + ".bak_before_v10_promotion")
        shutil.copy2(src, dst)
        print(f"{daf}: promoted -> {dst}")


if __name__ == "__main__":
    main()
