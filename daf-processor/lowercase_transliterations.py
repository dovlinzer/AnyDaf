"""
Lowercase capitalized transliterated words in rewrite.md and final.md files.

In prose lines (not headings, not blockquotes), any *...*-italicized span that
appears mid-sentence (preceded by a space) and starts with a capital letter gets
each word's initial letter lowercased.

Proper names (Rabbi X, place names) may also get lowercased — that's an accepted
trade-off over leaving all transliterations inconsistently capitalized.
"""

import re
import glob
import os


def lowercase_italic_span(content: str) -> str:
    """Lowercase the first letter of each word in a transliterated span."""
    return re.sub(r'\b([A-Z])', lambda m: m.group(1).lower(), content)


def process_line(line: str) -> str:
    stripped = line.lstrip()
    # Leave headings and blockquotes unchanged
    if stripped.startswith('#') or stripped.startswith('>'):
        return line

    # Match *...* spans that are mid-sentence (preceded by a space or open paren)
    # and whose content starts with a capital letter.
    def replace(m: re.Match) -> str:
        content = m.group(1)
        return f'*{lowercase_italic_span(content)}*'

    return re.sub(r'(?<=[ (])\*([A-Z][^*\n]+)\*', replace, line)


def process_file(filepath: str) -> bool:
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.readlines()

    updated = [process_line(line) for line in original]

    if updated != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(updated)
        return True
    return False


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base, 'output')

    patterns = ['**/*rewrite.md', '**/*final.md']
    changed = 0
    for pattern in patterns:
        for filepath in sorted(glob.glob(os.path.join(output_dir, pattern), recursive=True)):
            if process_file(filepath):
                print(f'Updated: {os.path.relpath(filepath, base)}')
                changed += 1

    print(f'\n{changed} file(s) updated.')


if __name__ == '__main__':
    main()
