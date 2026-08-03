"""Parse an assembled v10 output into an ordered block sequence, and for each Talmud
insertion (a Hebrew+Translation blockquote pair) compute its LOCAL candidate window:
every ### heading between the previous blockquote and the next blockquote, inclusive
of its own. This bounds relocation search to "does it belong here, or with the
immediately neighboring inserted text" — never a daf-wide search."""
import re
from dataclasses import dataclass, field

HEB_RE = re.compile(r'^> \*\*Hebrew/Aramaic:\*\* (.+)$')
TRANS_RE = re.compile(r'^> \*\*Translation:\*\* (.+)$')
H2_RE = re.compile(r'^## (.+)$')
H3_RE = re.compile(r'^### (.+)$')

@dataclass
class Block:
    kind: str  # 'h2' | 'h3' | 'quote' | 'prose'
    text: str = ""
    hebrew: str = ""
    translation: str = ""
    start: int = -1   # raw line index, inclusive
    end: int = -1     # raw line index, exclusive

def parse_blocks(md_text: str) -> list[Block]:
    blocks = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if H2_RE.match(line):
            blocks.append(Block("h2", text=H2_RE.match(line).group(1), start=i, end=i+1))
        elif H3_RE.match(line):
            blocks.append(Block("h3", text=H3_RE.match(line).group(1), start=i, end=i+1))
        elif HEB_RE.match(line):
            heb = HEB_RE.match(line).group(1)
            trans = ""
            start = i
            end = i + 1
            if i + 1 < len(lines) and TRANS_RE.match(lines[i+1]):
                trans = TRANS_RE.match(lines[i+1]).group(1)
                end = i + 2
                i += 1
            blocks.append(Block("quote", hebrew=heb, translation=trans, start=start, end=end))
        elif line.strip() and not line.strip() == "---":
            blocks.append(Block("prose", text=line.strip(), start=i, end=i+1))
        i += 1
    return blocks

def heading_of(blocks: list[Block], idx: int) -> str:
    for j in range(idx, -1, -1):
        if blocks[j].kind == "h3":
            return blocks[j].text
    return "(no heading)"

def prose_of_heading(blocks: list[Block], h3_idx: int) -> str:
    parts = []
    for j in range(h3_idx + 1, len(blocks)):
        if blocks[j].kind in ("h2", "h3"):
            break
        if blocks[j].kind == "prose":
            parts.append(blocks[j].text)
    return " ".join(parts)

def quote_indices(blocks: list[Block]) -> list[int]:
    return [i for i, b in enumerate(blocks) if b.kind == "quote"]

def quote_runs(blocks: list[Block]) -> list[list[int]]:
    """Maximal runs of consecutive quote blocks sharing the same current heading —
    these move as one atomic unit (splitting a continuously-recited passage across
    different headers isn't a real option; the guarded-search/DP machinery upstream
    already treats them as one block for the same reason)."""
    qidx = quote_indices(blocks)
    runs, current = [], []
    last_heading = None
    for qi in qidx:
        h = heading_of(blocks, qi)
        if current and h == last_heading and qi == current[-1] + 1:
            current.append(qi)
        else:
            if current:
                runs.append(current)
            current = [qi]
        last_heading = h
    if current:
        runs.append(current)
    return runs

def build_windows(blocks: list[Block]) -> list[dict]:
    """One entry per quote RUN: its own heading, concatenated hebrew/translation, and
    the ordered list of candidate (heading, prose) pairs — every ### heading strictly
    between the previous run and the next run, PLUS the run's own current heading
    (always included as the status-quo option even if it falls outside that band)."""
    runs = quote_runs(blocks)
    h3_positions = [i for i, b in enumerate(blocks) if b.kind == "h3"]
    windows = []
    for k, run in enumerate(runs):
        first_qi, last_qi = run[0], run[-1]
        prev_last_qi = runs[k-1][-1] if k > 0 else -1
        next_first_qi = runs[k+1][0] if k+1 < len(runs) else len(blocks)
        cand_h3 = [h for h in h3_positions if prev_last_qi < h < next_first_qi]
        current_heading = heading_of(blocks, first_qi)
        current_h3 = max([h for h in h3_positions if h < first_qi], default=None)
        if current_h3 is not None and current_h3 not in cand_h3:
            cand_h3 = sorted(cand_h3 + [current_h3])
        candidates = []
        for h in cand_h3:
            candidates.append({
                "heading": blocks[h].text,
                "prose": prose_of_heading(blocks, h),
                "is_current": h == current_h3,
            })
        windows.append({
            "quote_indices": run,
            "hebrew": " / ".join(blocks[i].hebrew for i in run),
            "translation": " ".join(blocks[i].translation for i in run),
            "items": [{"hebrew": blocks[i].hebrew, "translation": blocks[i].translation} for i in run],
            "current_heading": current_heading,
            "candidates": candidates,
        })
    return windows

if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(text)
    windows = build_windows(blocks)
    print(f"{len(windows)} quote runs total")
    multi = [w for w in windows if len(w["candidates"]) > 1]
    print(f"{len(multi)} have >1 candidate (worth asking Claude); {len(windows)-len(multi)} are unambiguous (single candidate, skip)")
    for w in windows:
        if len(w["candidates"]) <= 1:
            continue
        print(f"\nrun@{w['quote_indices']} current={w['current_heading']!r}")
        for c in w["candidates"]:
            flag = " *current*" if c["is_current"] else ""
            print(f"   candidate: {c['heading']!r} (prose {len(c['prose'])} chars){flag}")
