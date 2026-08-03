#!/usr/bin/env python3
"""
fix_wall_of_text.py — Two-stage Claude verify/patch for wall_of_text2.py's candidates.

wall_of_text2.py is a mechanical pre-filter (spoken-chars vs prose-chars ratio) —
deliberately loose/recall-oriented (see its own docstring's calibration note), so most
flagged sections are expected to be false positives: either (a) direct Talmudic
recitation, which is correctly short/absent from pass 2 prose since Approach B/pass 3
handles it separately via Sefaria blockquotes, or (b) rambling/repetitive/back-and-forth
spoken Hebrew that legitimately compresses hard into clean written prose. Only a real,
distinct explanatory point/ruling/exchange that's genuinely absent counts as a true
positive.

Stage A (verify, Haiku): for each flagged section, ask whether real explanatory content
is genuinely missing, explicitly excluding recitation and natural compression as reasons
to flag.

Stage B (patch, Sonnet — same model as pass 2 itself): for confirmed drops, rewrite the
affected section with the missing content woven in, following pass 2's own style rules.

Mirrors fix_pass2_gaps.py's two-stage shape (see CLAUDE.md, "Process A" note) — same
model choices, same Batch API resumability (submit_and_wait is imported, not
reimplemented), same "one patch call per section, never independent overlapping patches"
discipline.

Does not overwrite 02_rewrite.md; writes 02_rewrite_wall_patched.md per patched daf for
manual comparison against the original.

Usage:
    python fix_wall_of_text.py output/bava_batra_103 output/bava_batra_153 ...   # batch API (default)
    python fix_wall_of_text.py output/bava_batra_103 --no-batch                  # direct calls
    python fix_wall_of_text.py output/bava_batra_103 --dry-run                   # verify only
"""

import argparse
import json
import re
import sys
from pathlib import Path

import anthropic

from check_pass2_coverage import find_srt
from config import SEGMENTATION_MODEL, REWRITE_MODEL
from fix_pass2_gaps import submit_and_wait
from srt_parser import parse_srt
from wall_of_text2 import to_seconds, srt_entry_seconds, flat_micro_segments, flag as flag_ratios

VERIFY_MODEL = SEGMENTATION_MODEL   # Haiku — cheap semantic check
PATCH_MODEL = REWRITE_MODEL         # Sonnet — same model/voice as pass 2 itself


def extract_subsection_span(rewrite_text: str, title: str):
    """Same regex as wall_of_text2.extract_subsection_prose, but also returns the full
    match span (heading line through prose, up to the next heading or EOF) so a
    confirmed patch can be spliced back in at the right offsets."""
    pat = re.compile(r'^### ' + re.escape(title) + r'\s*$\n(.*?)(?=^#{2,3} |\Z)',
                      re.MULTILINE | re.DOTALL)
    m = pat.search(rewrite_text)
    if not m:
        return None
    return m.group(0), m.group(1).strip(), m.start(), m.end()


def get_flags_with_context(daf_dir: Path):
    seg_path = daf_dir / "01_segmentation.json"
    rewrite_path = daf_dir / "02_rewrite.md"
    if not seg_path.exists() or not rewrite_path.exists():
        return None, "missing 01_segmentation.json or 02_rewrite.md"
    seg_json = json.loads(seg_path.read_text(encoding="utf-8", errors="replace"))
    masechta, daf, amud = seg_json.get("masechta"), seg_json.get("daf"), seg_json.get("amud")
    srt_path = find_srt(masechta, int(daf), amud)
    if not srt_path:
        return None, "no matching SRT"
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    if not entries:
        return None, "empty SRT"
    entry_secs = [srt_entry_seconds(e) for e in entries]
    total_end = entry_secs[-1] if entry_secs else 0.0

    segs = flat_micro_segments(seg_json)
    if not segs:
        return None, "no micro segments"
    rewrite_text = rewrite_path.read_text(encoding="utf-8", errors="replace")

    ratio_results = []
    windows = {}  # title -> (start, end) seconds, for building spoken text below
    for i, (title, start) in enumerate(segs):
        end = segs[i + 1][1] if i + 1 < len(segs) else total_end + 1
        spoken_chars = sum(len(entries[j].text) for j, s in enumerate(entry_secs) if start <= s < end)
        span = extract_subsection_span(rewrite_text, title)
        prose_chars = len(span[1]) if span else 0
        ratio_results.append((title, spoken_chars, prose_chars))
        windows[title] = (start, end, span)

    flags = []
    for title, spoken_chars, prose_chars in flag_ratios(ratio_results):
        start, end, span = windows[title]
        if not span:
            continue  # heading not found in essay — shouldn't happen given apply_display_titles.py, but skip safely
        section_text, prose_text, sec_start, sec_end = span
        spoken_text = " ".join(e.text for j, e in enumerate(entries) if start <= entry_secs[j] < end)
        flags.append({
            "title": title, "spoken_text": spoken_text, "spoken_chars": spoken_chars,
            "prose_text": prose_text, "prose_chars": prose_chars,
            "section_text": section_text, "section_start": sec_start, "section_end": sec_end,
        })

    label = f"{masechta} {daf}{amud or ''}"
    return {"label": label, "essay": rewrite_text, "essay_path": rewrite_path, "flags": flags}, None


VERIFY_PROMPT = """You are auditing one section of a written essay adapted from a Talmud \
lecture transcript. This section was flagged by a mechanical pre-filter as having a low \
prose-to-speech ratio — but that filter is deliberately loose and over-flags in two known, \
NOT-real ways, which you must rule out before confirming a real gap:

(a) Direct Talmudic recitation (Gemara/mishna/baraita quoted aloud) is CORRECTLY short or \
absent from this prose — a separate, later editing pass inserts the actual source text as \
its own block, so recitation "missing" from THIS prose is expected and fine, not a defect.
(b) Rambling, repetition, false starts, and live back-and-forth workshopping between \
speakers legitimately compresses hard into clean written prose — a shorter, tighter \
restatement of the same point is fine, not a defect.

TRANSCRIPT EXCERPT (raw spoken text for this section's full time window; may mix Hebrew/\
Aramaic recitation, audience questions, and the lecturer's own commentary):
{spoken}

ESSAY SECTION (the polished prose covering this same window):
{prose}

Question: setting aside (a) and (b) above, does the transcript contain a distinct \
explanatory point, ruling, argument, or exchange — the lecturer's own analysis, not \
recitation — that is genuinely ABSENT from the essay section (not merely stated more \
briefly)? Only answer YES if real substance is missing.

Respond in exactly this format, nothing else:
VERDICT: YES or NO
REASON: one sentence"""

PATCH_PROMPT = """You are editing one section of a written essay adapted from a Talmud \
lecture transcript. A specific piece of the lecturer's own explanatory content was \
confirmed missing from this section. Insert it in the correct place, in the same voice as \
the rest of the essay.

STYLE RULES (from the essay's own writing guidelines):
- Direct Talmudic quotations (a phrase the lecturer reads aloud from Gemara/baraita/mishna) \
must appear as *italicized transliteration* — English translation, e.g. *Tanu Rabbanan* — \
the Rabbis taught. Do not add new blockquotes of source text; that is handled by a separate, \
later pass. Only integrate the LECTURER'S OWN explanatory commentary/analysis, not the raw \
recitation itself.
- Keep transliterated terms lowercase unless they are proper nouns.
- Do not use Hebrew script inline — transliteration only.
- Write in flowing paragraphs, no bullet points or lists.
- Do not alter, shorten, or remove any of the section's existing content — only insert the \
missing material at the point where it belongs.
- Match the existing section's tone: analytically rigorous, willing to flag when something \
is surprising.
- Do not include filler, false starts, or rambling from the transcript excerpt — extract \
and integrate only the substantive point.

TRANSCRIPT EXCERPT (raw spoken text for this section's full time window):
{spoken}

CURRENT ESSAY SECTION (missing the confirmed content):
{section}

Return ONLY the complete revised section (the ### heading line through the end of the \
section), nothing else — no preamble, no explanation."""


def parse_verify_response(text: str) -> tuple[bool, str]:
    verdict_m = re.search(r"VERDICT:\s*(YES|NO)", text, re.IGNORECASE)
    reason_m = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
    is_missing = bool(verdict_m and verdict_m.group(1).upper() == "YES")
    reason = reason_m.group(1).strip() if reason_m else text.strip()
    return is_missing, reason


def run_batch(dirs: list[str], dry_run: bool):
    client = anthropic.Anthropic()
    out_dir = Path(dirs[0]).parent

    daf_data = {}
    flag_index = []
    verify_requests = []
    for d in dirs:
        daf_dir = Path(d)
        data, err = get_flags_with_context(daf_dir)
        if err:
            print(f"{daf_dir}: SKIP ({err})")
            continue
        daf_data[data["label"]] = data
        print(f"{data['label']}: {len(data['flags'])} candidate flag(s)")
        for i, f in enumerate(data["flags"]):
            custom_id = f"{data['label']}__{i}".replace(" ", "_").replace("'", "")
            verify_requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": VERIFY_MODEL, "max_tokens": 200,
                    "messages": [{"role": "user",
                                  "content": VERIFY_PROMPT.format(spoken=f["spoken_text"], prose=f["prose_text"])}],
                },
            })
            flag_index.append((data["label"], i, custom_id))

    if not verify_requests:
        print("No flags found across the requested dafim.")
        return

    print(f"\n{'=' * 70}\nPhase A: verifying {len(verify_requests)} flag(s) across "
          f"{len(daf_data)} daf(im)\n{'=' * 70}")
    verify_state = out_dir / ".fix_wall_verify_batch.json"
    verify_batch = submit_and_wait(client, verify_requests, verify_state)

    verdicts = {}
    for result in client.messages.batches.results(verify_batch.id):
        if result.result.type != "succeeded":
            print(f"  ✗ {result.custom_id}: {result.result.type}")
            continue
        verdicts[result.custom_id] = parse_verify_response(result.result.message.content[0].text)

    confirmed = []  # (label, flag_idx)
    for label, i, custom_id in flag_index:
        if custom_id not in verdicts:
            continue
        is_missing, reason = verdicts[custom_id]
        f = daf_data[label]["flags"][i]
        status = "CONFIRMED MISSING" if is_missing else "false positive (adequately covered)"
        print(f"\n[{label} / {f['title']!r}] {status}")
        print(f"  reason: {reason}")
        if is_missing:
            confirmed.append((label, i))

    print(f"\n{len(confirmed)} of {len(verify_requests)} flag(s) confirmed as real gaps.")

    if dry_run or not confirmed:
        print("Dry run, stopping here." if dry_run else "Nothing to patch.")
        return

    print(f"\n{'=' * 70}\nPhase B: patching {len(confirmed)} section(s)\n{'=' * 70}")
    patch_requests = []
    for idx, (label, i) in enumerate(confirmed):
        f = daf_data[label]["flags"][i]
        custom_id = f"patch_{idx}"
        patch_requests.append({
            "custom_id": custom_id,
            "params": {
                "model": PATCH_MODEL, "max_tokens": 4000,
                "messages": [{"role": "user",
                              "content": PATCH_PROMPT.format(spoken=f["spoken_text"], section=f["section_text"])}],
            },
        })

    patch_state = out_dir / ".fix_wall_patch_batch.json"
    patch_batch = submit_and_wait(client, patch_requests, patch_state)

    patched_text = {}
    for result in client.messages.batches.results(patch_batch.id):
        if result.result.type != "succeeded":
            print(f"  ✗ {result.custom_id}: {result.result.type}")
            continue
        patched_text[result.custom_id] = result.result.message.content[0].text.strip()

    patches_by_label = {}
    for idx, (label, i) in enumerate(confirmed):
        custom_id = f"patch_{idx}"
        if custom_id not in patched_text:
            continue
        f = daf_data[label]["flags"][i]
        patches_by_label.setdefault(label, []).append((f["section_start"], f["section_end"], patched_text[custom_id]))

    for label, patches in patches_by_label.items():
        essay = daf_data[label]["essay"]
        patches.sort(key=lambda p: p[0], reverse=True)
        patched_essay = essay
        for start, end, new_text in patches:
            patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
        out_path = daf_data[label]["essay_path"].parent / "02_rewrite_wall_patched.md"
        out_path.write_text(patched_essay, encoding="utf-8")
        print(f"Wrote {out_path}  ({len(patches)} section(s) patched)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", help="Output dir(s) to process")
    parser.add_argument("--dry-run", action="store_true", help="Verify only, skip patching")
    parser.add_argument("--no-batch", action="store_true",
                         help="Direct/synchronous calls instead of the Batch API. Only use when "
                              "faster turnaround is needed and full price is acceptable.")
    args = parser.parse_args()

    if not args.no_batch:
        run_batch(args.dirs, args.dry_run)
        return

    client = anthropic.Anthropic()
    for d in args.dirs:
        daf_dir = Path(d)
        data, err = get_flags_with_context(daf_dir)
        if err:
            print(f"{daf_dir}: SKIP ({err})")
            continue

        print(f"\n{'=' * 70}\n{data['label']}  —  {len(data['flags'])} candidate flag(s)\n{'=' * 70}")
        essay = data["essay"]
        patches = []
        for f in data["flags"]:
            resp = client.messages.create(
                model=VERIFY_MODEL, max_tokens=200,
                messages=[{"role": "user",
                           "content": VERIFY_PROMPT.format(spoken=f["spoken_text"], prose=f["prose_text"])}],
            )
            is_missing, reason = parse_verify_response(resp.content[0].text)
            status = "CONFIRMED MISSING" if is_missing else "false positive (adequately covered)"
            print(f"\n[{f['title']!r}] {status}")
            print(f"  reason: {reason}")
            if is_missing and not args.dry_run:
                resp = client.messages.create(
                    model=PATCH_MODEL, max_tokens=4000,
                    messages=[{"role": "user",
                               "content": PATCH_PROMPT.format(spoken=f["spoken_text"], section=f["section_text"])}],
                )
                new_text = resp.content[0].text.strip()
                patches.append((f["section_start"], f["section_end"], new_text))
                print(f"  -> patched section ({len(new_text)} chars)")

        if patches:
            patches.sort(key=lambda p: p[0], reverse=True)
            patched_essay = essay
            for start, end, new_text in patches:
                patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
            out_path = daf_dir / "02_rewrite_wall_patched.md"
            out_path.write_text(patched_essay, encoding="utf-8")
            print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
