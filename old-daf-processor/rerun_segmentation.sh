#!/bin/bash
# Re-run all passes (1–3) for the 7 daf(im) not yet reprocessed.
# The 13 files already rerun successfully are excluded.
# (Berakhot 10 and Menachot 88 had passes 1+2 complete but pass 3 failed/unknown;
#  running all passes for simplicity.)

python3 main.py \
    "srt/processed/Berakhot 10.srt" \
    "srt/processed/Menachot 88.srt" \
    "srt/processed/Hullin 19.srt" \
    "srt/processed/Hullin 29b.srt" \
    "srt/processed/Menachot 79.srt" \
    "srt/processed/Menachot 96.srt" \
    "srt/processed/Menachot 98.srt" \
    --batch
