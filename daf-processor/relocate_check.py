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
from relocate_parse import parse_blocks, build_windows, marker_split_points

client = anthropic.Anthropic()

def build_prompt(w):
    items = w["items"]
    n = len(items)
    lines = [
        "You are checking whether a piece of quoted Talmudic text (Gemara/mishna/baraita) "
        "sits under the right section heading in an assembled essay. The essay was built by "
        "an automated pipeline that sometimes places a passage under the wrong nearby heading.",
        "",
        f"Below is the passage, broken into its {n} individual textual item(s) in order, "
        "followed by the candidate headings it could belong under — every heading between "
        "the previous quoted passage and the next one in the essay (so the true home is "
        "guaranteed to be in this list; you are not searching the whole essay). Each "
        "candidate shows that section's own prose (what the essay author actually wrote/said "
        "about that topic).",
        "",
    ]
    for i, it in enumerate(items, 1):
        lines.append(f"ITEM {i} of {n}:")
        lines.append(f"  HEBREW/ARAMAIC: {it['hebrew']}")
        lines.append(f"  ENGLISH TRANSLATION: {it['translation']}")
    lines.append("")
    lines.append("CANDIDATES (in order as they appear in the essay):")
    for i, c in enumerate(w["candidates"]):
        cur = "  [this is where it currently sits]" if c["is_current"] else ""
        prose = c["prose"] if c["prose"] else "(no prose under this heading)"
        lines.append(f"{i}. {c['heading']!r}{cur}\n   PROSE: {prose}")
    lines.append("")
    lines.append(
        "Which candidate does this passage's content actually belong under, based on what "
        "the prose is discussing? Almost always all items above belong together under ONE "
        "heading — reply with FORM 1 in that case. If the current placement is genuinely "
        "correct, return its own index. If several prose sections plausibly discuss related "
        "material and none is clearly the best match, prefer the CURRENT placement and mark "
        "confidence low — only recommend moving when a different candidate's prose is a "
        "clearly better match for THIS passage's specific content."
    )
    if n > 1:
        lines.append(
            "\nFORM 2 is for a SPECIFIC pipeline bug: an automated matching step sometimes "
            "glues together a short sentence that WRAPS UP one topic with the ENTIRE START "
            "of the next, unrelated topic, because they happened to sit next to each other "
            "in the source text. Use FORM 2 only when there is a genuine STRUCTURAL seam "
            "between the items — a new Mishnah beginning (look for 'MISHNA:' or similar), "
            "an entirely new case/scenario with its own new facts, or a shift to a different "
            "dispute that does not depend on what came before. A real example: item 1 is the "
            "closing line of a resolved dispute ('the halakha follows X'), and items 2 "
            "onward are the opening Mishnah and Gemara of a completely different case that a "
            "reader would recognize as its own self-contained unit even with item 1 deleted.\n"
            "Do NOT use FORM 2 for: multiple Amoraim disputing or refining the SAME point; a "
            "challenge followed by its resolution; one Amora's ruling followed by another "
            "Amora's elaboration, qualification, or exception to that SAME ruling; or a "
            "single chain of question-objection-answer even if several named Sages speak in "
            "turn. All of those are one continuous topic, however many sub-points or "
            "speakers it contains — reply FORM 1. If you're not confident the seam is a real "
            "structural break rather than just a shift in emphasis, prefer FORM 1."
        )
    lines.append(
        '\nFORM 1 (the whole passage belongs under one heading):\n'
        '{"action": "single", "best_index": <int>, "confidence": "high"|"medium"|"low", '
        '"reason": "<one sentence>"}'
    )
    if n > 1:
        lines.append(
            '\nFORM 2 (items 1..split_after belong under one heading, the rest under another):\n'
            '{"action": "split", "split_after": <int, 1 to ' + str(n - 1) + '>, '
            '"first_index": <int>, "first_confidence": "high"|"medium"|"low", "first_reason": "<one sentence>", '
            '"second_index": <int>, "second_confidence": "high"|"medium"|"low", "second_reason": "<one sentence>"}'
        )
    lines.append("\nReply with ONLY the JSON object, no other text.")
    return "\n".join(lines)

def build_prompt_split3(w, split1, split2):
    """FORM 3: a 3-way split, but the split points are PINNED by code (marker_split_points
    in relocate_parse.py), not chosen by the model. Only offered for runs with exactly two
    internal MISHNA:/GEMARA: markers -- validated 2026-08-06: free-choice 3-way splitting
    (letting the model pick where to cut) produced a real regression on Zevachim 29,
    over-splitting a run that FORM 2 already handled correctly, because a topic shift within
    continuous Gemara isn't the same thing as a genuine Mishna/Gemara structural seam. Pinning
    the cut points to literal markers removes that failure mode; the model's only remaining
    job is assigning each pre-cut segment to the candidate whose prose actually matches it."""
    items = w["items"]
    groups = [items[:split1], items[split1:split2], items[split2:]]
    lines = [
        "You are checking whether pieces of quoted Talmudic text (Gemara/mishna/baraita) "
        "sit under the right section headings in an assembled essay. The essay was built by "
        "an automated pipeline that sometimes places a passage under the wrong nearby heading.",
        "",
        "The passage below has ALREADY been split into 3 segments at its Mishna/Gemara "
        "structural boundaries (detected mechanically, not by you). Your only job is to "
        "assign each of the 3 segments to the candidate heading whose prose actually matches "
        "its content -- two segments may end up at the same heading if that's genuinely "
        "correct, and you can say a segment's current position is already right.",
        "",
    ]
    for gi, group in enumerate(groups, 1):
        lines.append(f"SEGMENT {gi} ({len(group)} item(s)):")
        for it in group:
            lines.append(f"  HEBREW/ARAMAIC: {it['hebrew']}")
            lines.append(f"  ENGLISH TRANSLATION: {it['translation']}")
        lines.append("")
    lines.append("CANDIDATES (in order as they appear in the essay):")
    for i, c in enumerate(w["candidates"]):
        cur = "  [this is where it currently sits]" if c["is_current"] else ""
        prose = c["prose"] if c["prose"] else "(no prose under this heading)"
        lines.append(f"{i}. {c['heading']!r}{cur}\n   PROSE: {prose}")
    lines.append("")
    lines.append(
        "Reply with ONLY this JSON object, no other text:\n"
        '{"segment1_index": <int>, "segment1_confidence": "high"|"medium"|"low", "segment1_reason": "<one sentence>", '
        '"segment2_index": <int>, "segment2_confidence": "high"|"medium"|"low", "segment2_reason": "<one sentence>", '
        '"segment3_index": <int>, "segment3_confidence": "high"|"medium"|"low", "segment3_reason": "<one sentence>"}'
    )
    return "\n".join(lines)

def split3_points(w):
    """Returns (split1, split2) if this window needs FORM 3 (two literal
    MISHNA:/GEMARA: markers), else None. Pure/no API call -- shared by the
    synchronous and Batch API paths so both dispatch identically."""
    n = len(w["items"])
    if n <= 2:
        return None
    pts = marker_split_points(w["items"])
    return (pts[0], pts[1]) if len(pts) == 2 else None


def parse_response_split3(w, split1, split2, text):
    """Pure parsing of a FORM-3 model response into the same result shape
    check_window_split3 returns -- no API call, reusable by the Batch API path."""
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except Exception:
        return None

    headings, confidences, reasons = [], [], []
    for seg in (1, 2, 3):
        idx = data.get(f"segment{seg}_index")
        if idx is None or not (0 <= idx < len(w["candidates"])):
            return None
        headings.append(w["candidates"][idx]["heading"])
        confidences.append(data.get(f"segment{seg}_confidence"))
        reasons.append(data.get(f"segment{seg}_reason"))

    return {
        "action": "split3",
        "split1": split1,
        "split2": split2,
        "first_heading": headings[0],
        "first_confidence": confidences[0],
        "first_reason": reasons[0],
        "second_heading": headings[1],
        "second_confidence": confidences[1],
        "second_reason": reasons[1],
        "third_heading": headings[2],
        "third_confidence": confidences[2],
        "third_reason": reasons[2],
        "current_heading": w["current_heading"],
        "moved": any(h != w["current_heading"] for h in headings),
    }


def parse_response(w, text):
    """Pure parsing of a FORM-1/FORM-2 model response into the same result shape
    check_window returns -- no API call, reusable by the Batch API path."""
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except Exception:
        return None

    n = len(w["quote_indices"])
    if data.get("action") == "split" and n > 1:
        split_after = data.get("split_after")
        fi, si = data.get("first_index"), data.get("second_index")
        if not (isinstance(split_after, int) and 1 <= split_after < n):
            return None
        if fi is None or not (0 <= fi < len(w["candidates"])):
            return None
        if si is None or not (0 <= si < len(w["candidates"])):
            return None
        first_heading = w["candidates"][fi]["heading"]
        second_heading = w["candidates"][si]["heading"]
        if first_heading == second_heading:
            # Not actually a split (both halves landed on the same heading) --
            # collapse to a single move so downstream code has one shape to handle.
            data = {"best_index": fi}
        else:
            return {
                "action": "split",
                "split_after": split_after,
                "first_heading": first_heading,
                "first_confidence": data.get("first_confidence"),
                "first_reason": data.get("first_reason"),
                "second_heading": second_heading,
                "second_confidence": data.get("second_confidence"),
                "second_reason": data.get("second_reason"),
                "current_heading": w["current_heading"],
                "moved": True,
            }

    idx = data.get("best_index")
    if idx is None or not (0 <= idx < len(w["candidates"])):
        return None
    data["action"] = "single"
    data["chosen_heading"] = w["candidates"][idx]["heading"]
    data["current_heading"] = w["current_heading"]
    data["moved"] = data["chosen_heading"] != w["current_heading"]
    return data


def check_window_split3(w, split1, split2):
    prompt = build_prompt_split3(w, split1, split2)
    resp = client.messages.create(
        model=REWRITE_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response_split3(w, split1, split2, resp.content[0].text)

def check_window(w):
    pts = split3_points(w)
    if pts:
        return check_window_split3(w, *pts)

    prompt = build_prompt(w)
    resp = client.messages.create(
        model=REWRITE_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_response(w, resp.content[0].text)

if __name__ == "__main__":
    path = sys.argv[1]
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(text)
    windows = build_windows(blocks)
    for w in windows:
        if len(w["candidates"]) <= 1:
            continue
        result = check_window(w)
        status = "SPLIT3" if result and result.get("action") == "split3" else \
                 "SPLIT" if result and result.get("action") == "split" else \
                 ("MOVE" if result and result["moved"] else "stay")
        print(f"[{status}] run={w['quote_indices']} current={w['current_heading']!r} -> {result}")
