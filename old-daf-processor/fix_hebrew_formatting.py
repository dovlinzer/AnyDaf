#!/usr/bin/env python3
"""
fix_hebrew_formatting.py

For each output/*/03_final.md, uses the matching SRT to build a
Hebrew→transliteration lookup and then fixes prose sections (non-blockquote lines):

  1. *Hebrew-script* (italic but wrong language) → *transliteration*
  2. bare Hebrew script                          → *transliteration*
  3. plain unitalicized multi-word transliteration from the SRT → *transliteration*

Single-word transliterations (daf, Gemara, Mishnah, etc.) are NOT auto-italicized
to avoid false positives on proper nouns.

Run from the daf-processor directory:
    python3 fix_hebrew_formatting.py [--dry-run]
"""

import re
import sys
from pathlib import Path

# ── Hebrew Unicode ranges (base letters + niqqud + cantillation + presentation forms) ──
HEB_CHAR = r'[\u0590-\u05FF\uFB1D-\uFB4F\u05F0-\u05F4]'
HEB_RE   = re.compile(HEB_CHAR + r'+')

# SRT junk lines (sequence numbers and timestamps)
TS_RE = re.compile(r'^\d+$|^\d{1,2}:\d{2}:\d{2}')

OUTPUT_DIR = Path('output')
SRT_DIR    = Path('srt/processed')

DRY_RUN = '--dry-run' in sys.argv


# ── SRT helpers ──────────────────────────────────────────────────────────────

def load_srt_text(path: Path) -> str:
    """Strip SRT timestamps/sequence numbers and return plain text."""
    lines = []
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if line and not TS_RE.match(line):
            lines.append(line)
    return ' '.join(lines)


def build_lookup(srt_text: str):
    """
    Scan SRT text for (Hebrew phrase, transliteration) pairs.

    Returns:
        he2en  – {hebrew_phrase: transliteration}
        en_set – {translit_lower: translit_orig}  only for multi-word phrases ≥6 chars
    """
    he2en  = {}
    en_set = {}

    # Common English stopwords — when we hit one of these after a Hebrew phrase,
    # the transliteration has ended and English prose has begun.
    STOPWORDS = re.compile(
        r'^(?:a|an|the|of|in|on|to|for|and|or|but|not|no|it|its|'
        r'is|are|was|were|we|you|he|she|they|them|their|our|so|as|'
        r'with|from|by|at|be|been|have|has|had|do|did|that|this|'
        r'there|here|which|who|what|when|where|how|if|then|than|'
        r'also|just|now|all|some|one|two|three|four|five|six|'
        r'seven|eight|nine|ten|about|after|before|during|while|'
        r'meaning|literally|actually|essentially|basically|namely|'
        r'i\.e\.|e\.g\.|etc\.)$',
        re.IGNORECASE
    )

    # Patterns that confirm a word is likely a Hebrew transliteration
    heb_phoneme_re = re.compile(
        r"sh|ch|tz|ts|'[aeiou]|[bvlm][ei][-']"
        r"|(?:im|ot|ah|it|eh|enu|echa|echem|einu|ein)\b"
        r"|^(?:ha|he|be|le|mi|la|li|u|v|b|l|m|k|d)[-']",
        re.IGNORECASE
    )

    # Split SRT text on Hebrew sequences; odd-indexed items are Hebrew spans,
    # even-indexed items are the Latin text that follows each Hebrew span.
    hebrew_span_re = re.compile(
        r'((?:' + HEB_CHAR + r'|[\u05F3\u05F4])'        # starts with Hebrew
        r'(?:' + HEB_CHAR + r'|[\u05F3\u05F4 "\'])*)'   # followed by Hebrew+spaces
    )
    segments = hebrew_span_re.split(srt_text)
    # segments: [before_0, heb_1, after_1, heb_2, after_2, ...]

    for i in range(1, len(segments), 2):
        heb = segments[i].strip(' .,;!?"\'')
        if not HEB_RE.search(heb):
            continue

        # Collect transliteration words from the immediately following Latin text
        after = segments[i + 1] if i + 1 < len(segments) else ''
        after = after.lstrip(' .,;')

        translit_words = []
        for word in after.split():
            # Strip trailing punctuation for the stopword check
            clean = word.rstrip('.,;!?')
            if not clean:
                continue
            # Stop at English stopwords
            if STOPWORDS.match(clean):
                break
            # Stop if we've collected 8 words already
            if len(translit_words) >= 8:
                break
            # Skip if first word starts with a single letter + space (e.g. "s ani" artifact)
            if len(translit_words) == 0 and len(clean) <= 1:
                break
            translit_words.append(clean)
            # Stop after sentence-ending punctuation
            if re.search(r'[.!?]$', word):
                break

        en = ' '.join(translit_words).strip()
        if len(en) < 2:
            continue

        he2en[heb] = en

        # Only add multi-word phrases to the en→italic lookup if EVERY word
        # passes the Hebrew phoneme test (prevents "Mishna says", "Rabbi Yochanan",
        # "Rashi frames", "Shabbat itself", etc. from being italicized).
        if ' ' in en and len(en) >= 6:
            words = en.split()
            if len(words) >= 2 and all(_is_translit_word(w) for w in words):
                en_set[en.lower()] = en

    return he2en, en_set


# Hebrew single-letter/short connectors that are not transliteration phonemes
# but are legitimate parts of a Hebrew phrase (u/and, v/and, b/in, l/for, etc.)
_HEB_CONNECTORS = {
    'o', 'u', 'v', 've', 'b', 'be', 'l', 'le', 'mi', 'ki', 'im',
    'k', 'ke', 'd', 'de', 'she', 'ha', 'al', 'el', 'ad',
    'uv', 'uve', 'umi', 'ubi', 'ule', 'ube', 'ul',
}

_HEB_PHONEME_RE = re.compile(
    r"sh|ch|tz|'[aeiou]"            # removed |ts (causes false positives on "itself", "rejects")
    r"|(?:im|ot|ah|it|eh|enu|echa|echem|einu|ein)$"
    r"|^(?:ha|he|be|le|mi|la|li|u[bv]|v|b|l|m|k|d)[aeiou]",
    re.IGNORECASE
)

# Common English words that accidentally contain Hebrew phoneme patterns.
# "sh" appears in: should, wish, fish, dish, wash, push, rush, show, shut, ...
# "ch" appears in: church, bunch, much, such, which, reach, teach, ...
_ENGLISH_WORDS = {
    'should', 'would', 'could', 'shall', 'show', 'shows', 'shown', 'shut',
    'wash', 'dish', 'fish', 'push', 'rush', 'cash', 'mesh', 'dash', 'lash',
    'trash', 'flash', 'slash', 'brush', 'crush', 'flush', 'plush', 'blush',
    'wish', 'fresh', 'flesh', 'bush', 'gush', 'lush', 'much', 'such',
    'which', 'each', 'reach', 'teach', 'beach', 'bunch', 'church', 'touch',
    'itself', 'himself', 'herself', 'themselves', 'ourselves', 'yourself',
    'says', 'rejects', 'selects', 'affects', 'effects', 'connects',
    'frames', 'holds', 'argues', 'states', 'teaches', 'allows', 'requires',
}


def _is_translit_word(word: str) -> bool:
    """Return True if a single word looks like a Hebrew transliteration word."""
    w = word.lower().rstrip('.,;!?\'"')
    if not w:
        return False
    if w in _ENGLISH_WORDS:
        return False           # known English false-positive
    if w in _HEB_CONNECTORS:
        return True
    return bool(_HEB_PHONEME_RE.search(w))


def find_srt(dir_name: str):
    """Map an output directory name (e.g. 'menachot_88') to its SRT file."""
    name = dir_name.replace('_', ' ')
    for srt in SRT_DIR.glob('*.srt'):
        if srt.stem.lower() == name.lower():
            return srt
    return None


# ── Line-level fixing ─────────────────────────────────────────────────────────

def fix_prose_line(line: str, he2en: dict, en_set: dict):
    """
    Apply all three fixes to a single non-blockquote prose line.
    Returns (fixed_line, [change_descriptions], [unfound_hebrew]).
    """
    changes  = []
    unfound  = []

    # ── Fix 1: *Hebrew* → *transliteration* ─────────────────────────────────
    def replace_italic_heb(m):
        content = m.group(1).strip()
        translit = he2en.get(content) or he2en.get(content.rstrip('.,;!?'))
        if translit:
            changes.append(f'italic-Hebrew → *{translit}*')
            return f'*{translit}*'
        unfound.append(content)
        return m.group(0)  # leave as-is

    line = re.sub(
        r'\*(' + HEB_CHAR + r'[^*]{0,250}?)\*',
        replace_italic_heb,
        line
    )

    # ── Fix 2: bare Hebrew → *transliteration* ───────────────────────────────
    def replace_bare_heb(m):
        heb = m.group(0)
        translit = he2en.get(heb) or he2en.get(heb.rstrip('.,;!?'))
        if translit:
            changes.append(f'bare-Hebrew "{heb[:25]}" → *{translit}*')
            return f'*{translit}*'
        unfound.append(heb)
        return heb

    line = HEB_RE.sub(replace_bare_heb, line)

    # ── Fix 3: plain multi-word transliteration → *italic* ───────────────────
    # Sort longest-first to avoid partial overlaps
    for en_lower, en_orig in sorted(en_set.items(), key=lambda x: -len(x[0])):
        pattern = r'(?<!\*)(?<![A-Za-z\'])(' + re.escape(en_lower) + r')(?![A-Za-z\'])(?!\*)'
        def do_italic(m, en_orig=en_orig):
            changes.append(f'plain-translit → *{en_orig}*')
            return f'*{en_orig}*'
        line = re.sub(pattern, do_italic, line, flags=re.IGNORECASE)

    return line, changes, unfound


# ── File-level processing ─────────────────────────────────────────────────────

def fix_final_md(final_path: Path, he2en: dict, en_set: dict):
    original = final_path.read_text(encoding='utf-8')
    lines    = original.splitlines(keepends=True)
    out      = []
    all_changes = []
    all_unfound = []

    for line in lines:
        stripped = line.strip()
        # Leave blockquotes, headings, blank lines, and *[Continued from above]* untouched
        if (stripped.startswith('>')
                or stripped.startswith('#')
                or not stripped
                or stripped == '*[Continued from above]*'):
            out.append(line)
            continue

        fixed, changes, unfound = fix_prose_line(line.rstrip('\n'), he2en, en_set)
        out.append(fixed + ('\n' if line.endswith('\n') else ''))
        all_changes.extend(changes)
        all_unfound.extend(unfound)

    new_content = ''.join(out)
    if new_content != original and not DRY_RUN:
        final_path.write_text(new_content, encoding='utf-8')

    return all_changes, all_unfound


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    finals = sorted(OUTPUT_DIR.glob('*/03_final.md'))
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Processing {len(finals)} files...\n")

    total_modified = 0
    global_unfound = []

    for final_path in finals:
        dir_name = final_path.parent.name
        srt_path = find_srt(dir_name)

        if not srt_path:
            print(f'  WARNING: no SRT found for {dir_name}')
            continue

        srt_text   = load_srt_text(srt_path)
        he2en, en_set = build_lookup(srt_text)
        changes, unfound = fix_final_md(final_path, he2en, en_set)

        if changes or unfound:
            total_modified += 1
            label = '[would modify]' if DRY_RUN else '[modified]'
            print(f'{label} {final_path}')
            for c in changes:
                print(f'  + {c}')
            for u in unfound:
                entry = f'{dir_name}: "{u[:40]}" — Hebrew script, no transliteration found'
                global_unfound.append(entry)
                print(f'  ! no match: "{u[:40]}"')

    print(f"\n{'='*60}")
    mode = 'Would modify' if DRY_RUN else 'Modified'
    print(f'{mode}: {total_modified}/{len(finals)} files')

    if global_unfound:
        print(f'\nHebrew script with no SRT transliteration ({len(global_unfound)} items):')
        print('These were left as-is and may need a manual fix or a targeted Claude call.')
        for u in global_unfound:
            print(f'  {u}')


if __name__ == '__main__':
    main()
