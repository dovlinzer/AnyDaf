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
    confirmed patch can be spliced back in at the right offsets.

    Also stops at a bare '---' divider line, not just the next '##'/'###' heading.
    Corpus convention puts '---' right before each '## ' macro heading (same convention
    apply_moves.h3_insert_points() relies on) -- when the flagged section is the LAST h3
    under its macro, the divider is the next thing in the file after its prose. Without
    this, the captured span swallowed the divider, and splicing in the patched text (which
    naturally doesn't reproduce a divider it was never told about) silently dropped it from
    the essay -- confirmed on Gittin 18's "Takanah Effectiveness" patch, 2026-08-03."""
    pat = re.compile(r'^### ' + re.escape(title) + r'\s*$\n(.*?)(?=^#{2,3} |^---\s*$|\Z)',
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

    titles_in_order = [t for t, _ in segs]

    flags = []
    for title, spoken_chars, prose_chars in flag_ratios(ratio_results):
        start, end, span = windows[title]
        if not span:
            continue  # heading not found in essay — shouldn't happen given apply_display_titles.py, but skip safely
        section_text, prose_text, sec_start, sec_end = span
        spoken_text = " ".join(e.text for j, e in enumerate(entries) if start <= entry_secs[j] < end)

        # Neighboring sections' prose, so the verifier/patcher can recognize when the
        # "missing" content is actually a forward-preview or backward-callback that
        # already gets its own full treatment under an adjacent heading -- see
        # bava_batra_84's "Resolution Vessels" (CLAUDE.md, 2026-08-06): the patch had
        # duplicated the neighboring "Meshicha Domain Transfer"/"Rental in Private Domain"
        # argument into an earlier section because that content genuinely fell within the
        # earlier section's raw transcript time window.
        pos = titles_in_order.index(title)
        prev_title = titles_in_order[pos - 1] if pos > 0 else None
        next_title = titles_in_order[pos + 1] if pos + 1 < len(titles_in_order) else None
        prev_prose = (windows[prev_title][2][1] if prev_title and windows[prev_title][2] else None)
        next_prose = (windows[next_title][2][1] if next_title and windows[next_title][2] else None)

        flags.append({
            "title": title, "spoken_text": spoken_text, "spoken_chars": spoken_chars,
            "prose_text": prose_text, "prose_chars": prose_chars,
            "section_text": section_text, "section_start": sec_start, "section_end": sec_end,
            "prev_title": prev_title, "prev_prose": prev_prose,
            "next_title": next_title, "next_prose": next_prose,
        })

    label = f"{masechta} {daf}{amud or ''}"
    return {"label": label, "essay": rewrite_text, "essay_path": rewrite_path, "flags": flags}, None


VERIFY_PROMPT = """You are auditing one section of a written essay adapted from a Talmud \
lecture transcript. This section was flagged by a mechanical pre-filter as having a low \
prose-to-speech ratio — but that filter is deliberately loose and over-flags in three known, \
NOT-real ways, which you must rule out before confirming a real gap:

(a) Direct Talmudic recitation (Gemara/mishna/baraita quoted aloud) is CORRECTLY short or \
absent from this prose — a separate, later editing pass inserts the actual source text as \
its own block, so recitation "missing" from THIS prose is expected and fine, not a defect.
(b) Rambling, repetition, false starts, and live back-and-forth workshopping between \
speakers legitimately compresses hard into clean written prose — a shorter, tighter \
restatement of the same point is fine, not a defect.
(c) The lecturer sometimes verbally previews an upcoming point or circles back to one \
already made — that content can fall inside THIS section's raw transcript time window even \
though it belongs, and gets its own full treatment, under the PREVIOUS or NEXT section shown \
below. Do not count that as missing from this section; it is correctly placed there instead.

PREVIOUS SECTION ({prev_title}):
{prev_prose}

NEXT SECTION ({next_title}):
{next_prose}

TRANSCRIPT EXCERPT (raw spoken text for this section's full time window; may mix Hebrew/\
Aramaic recitation, audience questions, and the lecturer's own commentary):
{spoken}

ESSAY SECTION (the polished prose covering this same window):
{prose}

Question: setting aside (a), (b), and (c) above, does the transcript contain a distinct \
explanatory point, ruling, argument, or exchange — the lecturer's own analysis, not \
recitation, and not already covered by the previous or next section — that is genuinely \
ABSENT from the essay section (not merely stated more briefly)? Only answer YES if real \
substance is missing.

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
- If the confirmed point substantially overlaps with what the PREVIOUS or NEXT section below \
already covers in full, do NOT reproduce that argument here — that would duplicate content \
the reader will see in full elsewhere. At most, add a brief single-clause forward/backward \
reference (e.g., "...a question the gemara will resolve shortly"); never restate the \
argument's substance a second time.

PREVIOUS SECTION ({prev_title}):
{prev_prose}

NEXT SECTION ({next_title}):
{next_prose}

TRANSCRIPT EXCERPT (raw spoken text for this section's full time window):
{spoken}

CURRENT ESSAY SECTION (missing the confirmed content):
{section}

Return ONLY the complete revised section (the ### heading line through the end of the \
section), nothing else — no preamble, no explanation."""


def _neighbor_fields(f: dict) -> dict:
    """Formats a flag's prev/next neighbor title+prose for prompt interpolation, with
    placeholders at either end of a daf where no neighbor exists."""
    return {
        "prev_title": f["prev_title"] or "(none — this is the first section)",
        "prev_prose": f["prev_prose"] or "(none)",
        "next_title": f["next_title"] or "(none — this is the last section)",
        "next_prose": f["next_prose"] or "(none)",
    }


def parse_verify_response(text: str) -> tuple[bool, str]:
    verdict_m = re.search(r"VERDICT:\s*(YES|NO)", text, re.IGNORECASE)
    reason_m = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
    is_missing = bool(verdict_m and verdict_m.group(1).upper() == "YES")
    reason = reason_m.group(1).strip() if reason_m else text.strip()
    return is_missing, reason


def run_batch(dirs: list[str], dry_run: bool, out_file: str):
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
        # Keyed by the directory string, not data["label"] -- two distinct directories can
        # produce the identical human-readable label (e.g. berakhot_24 and berakhot_24b both
        # computing "Berakhot 24b" from a stale/duplicate `amud` field in their own
        # 01_segmentation.json -- 122 such collisions found corpus-wide 2026-08-08). Keying
        # daf_data by label let the second directory processed silently overwrite the first's
        # entry, so a later patch lookup by (label, i) could fetch the WRONG daf's flag and
        # splice its patched text into an unrelated essay at the wrong offset. The directory
        # string is guaranteed unique (it's the glob/arg source itself); label is display-only.
        daf_data[d] = data
        print(f"{data['label']}: {len(data['flags'])} candidate flag(s)")
        for i, f in enumerate(data["flags"]):
            custom_id = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{d}__{i}")
            verify_requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": VERIFY_MODEL, "max_tokens": 200,
                    "messages": [{"role": "user",
                                  "content": VERIFY_PROMPT.format(spoken=f["spoken_text"], prose=f["prose_text"],
                                                                   **_neighbor_fields(f))}],
                },
            })
            flag_index.append((d, i, custom_id))

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

    confirmed = []  # (dir_key, flag_idx)
    for dir_key, i, custom_id in flag_index:
        if custom_id not in verdicts:
            continue
        is_missing, reason = verdicts[custom_id]
        f = daf_data[dir_key]["flags"][i]
        status = "CONFIRMED MISSING" if is_missing else "false positive (adequately covered)"
        print(f"\n[{daf_data[dir_key]['label']} / {f['title']!r}] {status}")
        print(f"  reason: {reason}")
        if is_missing:
            confirmed.append((dir_key, i))

    print(f"\n{len(confirmed)} of {len(verify_requests)} flag(s) confirmed as real gaps.")

    if dry_run:
        print("Dry run, stopping here.")
        return

    patches_by_dir = {}
    if confirmed:
        print(f"\n{'=' * 70}\nPhase B: patching {len(confirmed)} section(s)\n{'=' * 70}")
        patch_requests = []
        for idx, (dir_key, i) in enumerate(confirmed):
            f = daf_data[dir_key]["flags"][i]
            custom_id = f"patch_{idx}"
            patch_requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": PATCH_MODEL, "max_tokens": 4000,
                    "messages": [{"role": "user",
                                  "content": PATCH_PROMPT.format(spoken=f["spoken_text"], section=f["section_text"],
                                                                  **_neighbor_fields(f))}],
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

        for idx, (dir_key, i) in enumerate(confirmed):
            custom_id = f"patch_{idx}"
            if custom_id not in patched_text:
                continue
            f = daf_data[dir_key]["flags"][i]
            patches_by_dir.setdefault(dir_key, []).append((f["section_start"], f["section_end"], patched_text[custom_id]))

        for dir_key, patches in patches_by_dir.items():
            essay = daf_data[dir_key]["essay"]
            patches.sort(key=lambda p: p[0], reverse=True)
            patched_essay = essay
            for start, end, new_text in patches:
                patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
            out_path = daf_data[dir_key]["essay_path"].parent / out_file
            out_path.write_text(patched_essay, encoding="utf-8")
            print(f"Wrote {out_path}  ({len(patches)} section(s) patched)")

    # Every requested dir that didn't get an actual patch above still needs out_file written --
    # downstream steps (v10 assembly, relocate) uniformly expect this filename to exist for
    # every daf, not just the ones with a confirmed gap. This must run per-daf, not gated on
    # `if not confirmed` globally: a corpus-scale run has SOME dafim with confirmed patches and
    # others without, so a global "any confirmed anywhere -> skip passthrough entirely" check
    # (the original shape, correct only for an all-or-nothing single-daf run) silently left 246
    # of 2278 dafim with no output file at all in the 2026-08-08 corpus run -- found by
    # comparing the requested dir list against actual `02_rewrite_wall_patched.md` presence
    # after the run, not by anything in this script's own logging. Covers three cases: (a)
    # daf_data entries with flags but none confirmed, (b) daf_data entries with zero flags to
    # begin with, (c) dirs that never entered daf_data at all (get_flags_with_context itself
    # failed -- e.g. "no matching SRT" -- but 02_rewrite.md still exists and is still valid
    # input for v10; originally found on Sanhedrin 67, 0/4 flags confirmed, 6-daf batch).
    passthrough_count = 0
    for d in dirs:
        if d in patches_by_dir:
            continue
        if d in daf_data:
            essay_text = daf_data[d]["essay"]
            out_path = daf_data[d]["essay_path"].parent / out_file
        else:
            rewrite_path = Path(d) / "02_rewrite.md"
            if not rewrite_path.exists():
                continue  # genuinely missing input, already reported as SKIP above
            essay_text = rewrite_path.read_text(encoding="utf-8", errors="replace")
            out_path = Path(d) / out_file
        out_path.write_text(essay_text, encoding="utf-8")
        passthrough_count += 1
    if passthrough_count:
        print(f"\nWrote {passthrough_count} passthrough copy/copies (no confirmed patch, or flag data unavailable).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", help="Output dir(s) to process")
    parser.add_argument("--dry-run", action="store_true", help="Verify only, skip patching")
    parser.add_argument("--no-batch", action="store_true",
                         help="Direct/synchronous calls instead of the Batch API. Only use when "
                              "faster turnaround is needed and full price is acceptable.")
    parser.add_argument("--out-file", default="02_rewrite_wall_patched.md",
                         help="Output essay filename to write within each daf dir "
                              "(default: 02_rewrite_wall_patched.md)")
    args = parser.parse_args()

    if not args.no_batch:
        run_batch(args.dirs, args.dry_run, args.out_file)
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
                           "content": VERIFY_PROMPT.format(spoken=f["spoken_text"], prose=f["prose_text"],
                                                            **_neighbor_fields(f))}],
            )
            is_missing, reason = parse_verify_response(resp.content[0].text)
            status = "CONFIRMED MISSING" if is_missing else "false positive (adequately covered)"
            print(f"\n[{f['title']!r}] {status}")
            print(f"  reason: {reason}")
            if is_missing and not args.dry_run:
                resp = client.messages.create(
                    model=PATCH_MODEL, max_tokens=4000,
                    messages=[{"role": "user",
                               "content": PATCH_PROMPT.format(spoken=f["spoken_text"], section=f["section_text"],
                                                               **_neighbor_fields(f))}],
                )
                new_text = resp.content[0].text.strip()
                patches.append((f["section_start"], f["section_end"], new_text))
                print(f"  -> patched section ({len(new_text)} chars)")

        if not args.dry_run:
            if patches:
                patches.sort(key=lambda p: p[0], reverse=True)
                patched_essay = essay
                for start, end, new_text in patches:
                    patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
                out_path = daf_dir / args.out_file
                out_path.write_text(patched_essay, encoding="utf-8")
                print(f"\nWrote {out_path}")
            else:
                # Passthrough copy -- see the matching comment in run_batch() above.
                out_path = daf_dir / args.out_file
                out_path.write_text(essay, encoding="utf-8")
                print(f"\nWrote {out_path}  (passthrough, no patches needed)")


if __name__ == "__main__":
    main()
