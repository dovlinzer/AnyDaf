import re
from dataclasses import dataclass
from typing import List


@dataclass
class SRTEntry:
    index: int
    start_time: str   # "HH:MM:SS,mmm"
    end_time: str
    text: str


def parse_srt(content: str) -> List[SRTEntry]:
    entries = []
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = [l for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        time_match = re.match(r'(\S+)\s+-->\s+(\S+)', lines[1])
        if not time_match:
            continue
        start, end = time_match.group(1), time_match.group(2)
        text = ' '.join(lines[2:])
        entries.append(SRTEntry(index=idx, start_time=start, end_time=end, text=text))
    return entries


def _to_mmss(srt_time: str) -> str:
    """Convert HH:MM:SS,mmm to MM:SS."""
    parts = re.split(r'[:,]', srt_time)
    if len(parts) >= 3:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        total = h * 3600 + m * 60 + s
        return f"{total // 60:02d}:{total % 60:02d}"
    return srt_time


def srt_to_timestamped_text(entries: List[SRTEntry]) -> str:
    """One line per SRT entry with [MM:SS] prefix — used for segmentation pass."""
    return '\n'.join(f"[{_to_mmss(e.start_time)}] {e.text}" for e in entries)


def srt_to_text(entries: List[SRTEntry], entries_per_para: int = 8) -> str:
    """Plain text grouped into paragraphs — used for rewrite pass."""
    paragraphs = []
    for i in range(0, len(entries), entries_per_para):
        chunk = entries[i:i + entries_per_para]
        paragraphs.append(' '.join(e.text for e in chunk))
    return '\n\n'.join(paragraphs)
