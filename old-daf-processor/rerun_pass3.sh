#!/bin/bash
# Re-run pass 3 (source insertion) for 28 remaining files where essay prose was
# incorrectly replaced by *[Continued from above]* placeholders.
# Berakhot 11b, Berakhot 12, Berakhot 7, Hullin 15 already completed — excluded.
# Passes 1 and 2 are untouched.

# Delete stale Sefaria prev/next cache files so pass 3 fetches fresh context.
find output -name "sefaria_prev.md" -o -name "sefaria_next.md" | xargs rm -f

python3 main.py \
    "srt/processed/Hullin 10.srt" \
    "srt/processed/Hullin 13.srt" \
    "srt/processed/Hullin 16.srt" \
    "srt/processed/Hullin 17.srt" \
    "srt/processed/Hullin 18.srt" \
    "srt/processed/Hullin 22.srt" \
    "srt/processed/Hullin 23.srt" \
    "srt/processed/Hullin 25.srt" \
    "srt/processed/Hullin 26.srt" \
    "srt/processed/Hullin 3.srt" \
    "srt/processed/Hullin 4.srt" \
    "srt/processed/Hullin 5.srt" \
    "srt/processed/Hullin 5b.srt" \
    "srt/processed/Hullin 8.srt" \
    "srt/processed/Hullin 9.srt" \
    "srt/processed/Menachot 109.srt" \
    "srt/processed/Menachot 73.srt" \
    "srt/processed/Menachot 74.srt" \
    "srt/processed/Menachot 75.srt" \
    "srt/processed/Menachot 78.srt" \
    "srt/processed/Menachot 82.srt" \
    "srt/processed/Menachot 83.srt" \
    "srt/processed/Menachot 86.srt" \
    "srt/processed/Menachot 89.srt" \
    "srt/processed/Menachot 90.srt" \
    "srt/processed/Menachot 93.srt" \
    "srt/processed/Menachot 95.srt" \
    "srt/processed/Menachot 97.srt" \
    --passes 3 \
    --batch
