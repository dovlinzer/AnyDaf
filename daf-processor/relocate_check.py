"""
relocate_check.py — for each ambiguous Talmud-quote placement in an assembled v10 output
(a quote-run with more than one candidate heading in its local window — see
relocate_parse.py), asks Claude whether the current heading is right or whether one of
the neighboring candidates fits the quote's actual content better.

Search is bounded to the LOCAL window: every heading strictly between the previous quote
run and the next one, plus the quote's own current heading. Never searches the whole daf
— the true home is guaranteed to be adjacent to already-placed quotes, not somewhere
across a dense/repetitive daf where a scoring-based search destabilizes everything (see
CLAUDE.md, "confident wrong opening" — the algorithmic attempts that preceded this one).

Validated on the 13-daf review batch (2026-07-31): 204 checks, 62 moves recommended (59
high confidence / 3 medium / 0 low), reproduced every previously-confirmed manual fix and
one case (Bava Metzia 11's "Open Questions" segment) that scoring-based search never found
at all, because the correct section is written in transliteration with zero English-word
overlap against Sefaria's translation — a blind spot no amount of algorithmic tuning fixes,
but trivial for an LLM that's actually reading.

Usage:
    python relocate_check.py output/bava_metzia_11/03_text_first_prototype_v10.md
    python relocate_run_all.py                      # batch over the 13-daf review set
"""
import sys
import json
import re
from config import REWRITE_MODEL
import anthropic
from relocate_parse import parse_blocks, build_windows

client = anthropic.Anthropic()

def build_prompt(w):
    lines = [
        "You are checking whether a piece of quoted Talmudic text (Gemara/mishna/baraita) "
        "sits under the right section heading in an assembled essay. The essay was built by "
        "an automated pipeline that sometimes places a passage under the wrong nearby heading.",
        "",
        "Below is the Hebrew/Aramaic passage and its English translation, followed by the "
        "candidate headings it could belong under — every heading between the previous quoted "
        "passage and the next one in the essay (so the true home is guaranteed to be in this "
        "list; you are not searching the whole essay). Each candidate shows that section's own "
        "prose (what the essay author actually wrote/said about that topic).",
        "",
        f"HEBREW/ARAMAIC: {w['hebrew']}",
        f"ENGLISH TRANSLATION: {w['translation']}",
        "",
        "CANDIDATES (in order as they appear in the essay):",
    ]
    for i, c in enumerate(w["candidates"]):
        cur = "  [this is where it currently sits]" if c["is_current"] else ""
        prose = c["prose"] if c["prose"] else "(no prose under this heading)"
        lines.append(f"{i}. {c['heading']!r}{cur}\n   PROSE: {prose}")
    lines.append("")
    lines.append(
        "Which candidate does this passage's content actually belong under, based on what "
        "the prose is discussing? Reply with ONLY a JSON object: "
        '{"best_index": <int>, "confidence": "high"|"medium"|"low", "reason": "<one sentence>"}. '
        "If the current placement is genuinely correct, return its own index. If several "
        "prose sections plausibly discuss related material and none is clearly the best "
        "match, prefer the CURRENT placement and mark confidence low — only recommend moving "
        "it when a different candidate's prose is a clearly better match for THIS passage's "
        "specific content."
    )
    return "\n".join(lines)

def check_window(w):
    prompt = build_prompt(w)
    resp = client.messages.create(
        model=REWRITE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except Exception:
        return None
    idx = data.get("best_index")
    if idx is None or not (0 <= idx < len(w["candidates"])):
        return None
    data["chosen_heading"] = w["candidates"][idx]["heading"]
    data["current_heading"] = w["current_heading"]
    data["moved"] = data["chosen_heading"] != w["current_heading"]
    return data

if __name__ == "__main__":
    path = sys.argv[1]
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(text)
    windows = build_windows(blocks)
    for w in windows:
        if len(w["candidates"]) <= 1:
            continue
        result = check_window(w)
        status = "MOVE" if result and result["moved"] else "stay"
        print(f"[{status}] run={w['quote_indices']} current={w['current_heading']!r} -> {result}")
