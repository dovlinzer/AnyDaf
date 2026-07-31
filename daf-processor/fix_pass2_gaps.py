#!/usr/bin/env python3
"""
fix_pass2_gaps.py — Two-stage fix for pass 2 content drops found by
check_pass2_coverage.py.

Stage A (verify, Haiku): for each candidate flag, ask whether the flagged transcript
excerpt is genuinely absent from its corresponding essay section — a semantic check
that should clear out the word-overlap heuristic's remaining false positives.

Stage B (patch, Sonnet — same model as pass 2 itself): for confirmed drops, rewrite
the affected essay section with the missing content woven in, following pass 2's own
style rules.

TEST SCOPE — direct API only, not wired into the batch pipeline. Does not overwrite
02_rewrite.md; writes a report and a patched copy for manual comparison against
verified ground truth. Corpus-wide rollout (if this test looks good) should go through
the existing Batch API machinery in pipeline.py instead, for resilience.

Usage:
    python fix_pass2_gaps.py output/hullin_88
    python fix_pass2_gaps.py output/hullin_88 output/berakhot_31 ...
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import anthropic

from check_pass2_coverage import (
    MARKER_RE, MIN_WINDOW_WORDS, MIN_CONTENT_WORDS,
    content_words, find_srt, normalize, phonetic_key,
)
from config import SEGMENTATION_MODEL, REWRITE_MODEL, BATCH_POLL_INTERVAL, BATCH_TIMEOUT
from srt_parser import parse_srt

CONTEXT_CHARS = 350   # transcript excerpt radius (chars) around a flagged marker
VERIFY_MODEL = SEGMENTATION_MODEL   # Haiku — cheap semantic yes/no check
PATCH_MODEL = REWRITE_MODEL         # Sonnet — same model/voice as pass 2 itself


def srt_seconds(srt_time: str) -> float:
    h, m, rest = srt_time.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def build_transcript_with_offsets(entries):
    """Flatten SRT entries into one string, tracking (start_char, end_char, seconds)
    per entry so a later char offset can be mapped back to a timestamp."""
    parts, offsets, pos = [], [], 0
    for e in entries:
        start = pos
        parts.append(e.text)
        pos += len(e.text)
        offsets.append((start, pos, srt_seconds(e.start_time)))
        parts.append(" ")
        pos += 1
    return "".join(parts), offsets


def timestamp_for_offset(offsets, char_pos: int) -> float:
    for start, end, secs in offsets:
        if start <= char_pos < end:
            return secs
    return offsets[-1][2] if offsets else 0.0


def macro_segment_for_timestamp(macro_segments: list[dict], seconds: float) -> dict | None:
    """Last macro segment whose own timestamp is <= target — same 'owning segment'
    pattern used throughout this codebase (e.g. iOS ShiurClient.amudASegmentIndex)."""
    best = None
    for seg in macro_segments:
        ts = seg.get("timestamp", "")
        parts = ts.split(":")
        if len(parts) != 2:
            continue
        seg_secs = int(parts[0]) * 60 + int(parts[1])
        if seg_secs <= seconds:
            best = seg
        else:
            break
    return best or (macro_segments[0] if macro_segments else None)


def micro_segment_for_timestamp(macro: dict, seconds: float) -> dict | None:
    """Same 'last segment before target' pattern as macro_segment_for_timestamp, one
    level finer. Using only the macro segment left placement decisions (which of its
    several ### subsections?) entirely to the patch model's guess — found live on
    Hullin 88: it guessed wrong, placing new content in 'Klal Tzarich l'Prat' when
    the segmentation's own micro timestamps put it under 'Ribuy u'Miut Method',
    two subsections later. Targeting the micro segment directly removes that guess."""
    best = None
    for micro in macro.get("micro_segments", []):
        ts = micro.get("timestamp", "")
        parts = ts.split(":")
        if len(parts) != 2:
            continue
        secs = int(parts[0]) * 60 + int(parts[1])
        if secs <= seconds:
            best = micro
        else:
            break
    return best


def extract_section(essay: str, level: str, display_title: str) -> tuple[str, int, int] | None:
    """Return (section_text, start_char, end_char) for a '{level} {display_title}' block —
    from that heading line to the next heading of the same level or higher (shorter), or
    end of file. level is '##' (macro) or '###' (micro)."""
    heading_re = re.compile(rf"^{re.escape(level)} {re.escape(display_title)}\s*$", re.MULTILINE)
    m = heading_re.search(essay)
    if not m:
        return None
    start = m.start()
    stop_re = re.compile(r"^#{1," + str(len(level)) + r"} ", re.MULTILINE)
    next_m = stop_re.search(essay[m.end():])
    end = m.end() + next_m.start() if next_m else len(essay)
    return essay[start:end], start, end


def get_flags_with_context(daf_dir: Path):
    """Re-run the coverage heuristic but keep timestamp + essay-section info per flag,
    which check_pass2_coverage.py's standalone report doesn't track."""
    seg_path = daf_dir / "01_segmentation.json"
    rewrite_path = daf_dir / "02_rewrite.md"
    seg = json.loads(seg_path.read_text())
    masechta, daf, amud = seg.get("masechta"), seg.get("daf"), seg.get("amud")
    macro_segments = seg.get("macro_segments", [])

    srt_path = find_srt(masechta, int(daf), amud)
    if not srt_path:
        return None, f"no SRT for {masechta} {daf}{amud or ''}"

    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    transcript, offsets = build_transcript_with_offsets(entries)
    transcript_words = normalize(transcript)

    essay = rewrite_path.read_text(encoding="utf-8", errors="replace")
    essay_words = content_words(normalize(essay))
    essay_content_words = set(essay_words)
    essay_phonetic_keys = {phonetic_key(w) for w in essay_words}

    flags = []
    for m in MARKER_RE.finditer(transcript):
        prefix_words = normalize(transcript[:m.start()])
        start_idx = len(prefix_words)
        window = transcript_words[start_idx:start_idx + 14]
        if len(window) < MIN_WINDOW_WORDS:
            continue
        window_content = content_words(window)
        if len(window_content) < MIN_CONTENT_WORDS:
            continue
        matched = set(window_content) & essay_content_words
        matched |= {w for w in window_content if phonetic_key(w) in essay_phonetic_keys}
        if len(matched) >= 2:
            continue

        seconds = timestamp_for_offset(offsets, m.start())
        macro = macro_segment_for_timestamp(macro_segments, seconds)
        if not macro:
            continue
        micro = micro_segment_for_timestamp(macro, seconds)
        section = None
        target_desc = macro["display_title"]
        if micro:
            section = extract_section(essay, "###", micro["display_title"])
            target_desc = f'{macro["display_title"]} > {micro["display_title"]}'
        if not section:
            # No micro match (macro has none, or its ### heading wasn't found in the
            # essay) — fall back to the whole macro block.
            section = extract_section(essay, "##", macro["display_title"])
            target_desc = macro["display_title"]
        if not section:
            continue
        section_text, sec_start, sec_end = section

        excerpt_start = max(0, m.start() - CONTEXT_CHARS)
        excerpt_end = min(len(transcript), m.start() + CONTEXT_CHARS)
        excerpt = transcript[excerpt_start:excerpt_end]

        flags.append({
            "marker": m.group(1),
            "timestamp": seconds,
            "macro_title": target_desc,
            "excerpt": excerpt,
            "section_text": section_text,
            "section_start": sec_start,
            "section_end": sec_end,
        })
    return {"label": f"{masechta} {daf}{amud or ''}", "essay": essay, "flags": flags,
            "essay_path": rewrite_path}, None


VERIFY_PROMPT = """You are auditing a written essay adapted from a Talmud lecture transcript, \
checking whether the essay dropped a piece of content the lecturer covered.

TRANSCRIPT EXCERPT (raw, spoken, may mix Hebrew/Aramaic transliteration and English):
{excerpt}

ESSAY SECTION (the polished section this excerpt's timestamp falls within):
{section}

Question: does the essay section include the specific content in the transcript excerpt \
above — the statement, exchange, or passage — even if paraphrased, reworded, or covered \
briefly? Minor wording differences do not count as missing. Only answer NO if the actual \
substance (the specific statement, ruling, or exchange) is genuinely absent.

Respond in exactly this format, nothing else:
VERDICT: YES or NO
REASON: one sentence"""

PATCH_PROMPT = """You are editing one section of a written essay adapted from a Talmud \
lecture transcript. One or more pieces of content from the transcript were confirmed \
missing from this section. Insert all of them in the correct place(s), in the same voice \
as the rest of the essay.

STYLE RULES (from the essay's own writing guidelines):
- Direct Talmudic quotations (a phrase the lecturer reads aloud from Gemara/baraita/mishna) \
must appear as *italicized transliteration* — English translation, e.g. *Tanu Rabbanan* — \
the Rabbis taught.
- Keep transliterated terms lowercase unless they are proper nouns.
- Do not use Hebrew script inline — transliteration only.
- Write in flowing paragraphs, no bullet points or lists.
- Do not alter, shorten, or remove any of the section's existing content — only insert the \
missing material at the point(s) in the section where it chronologically belongs.
- Match the existing section's tone: analytically rigorous, willing to flag when something \
is surprising ("this is a striking Gemara," "the argument seems to favor X, yet...").
- The excerpts below are given in chronological order and may overlap or continue one \
another — read all of them together before writing, and produce ONE coherent integration, \
not a separate inserted paragraph per excerpt. Do not reintroduce the same baraita, \
statement, or attribution more than once if multiple excerpts describe the same passage \
from slightly different points in the recording.

TRANSCRIPT EXCERPT(S) containing the missing content (raw, spoken — extract and integrate \
only the substantive Talmudic content, not filler or side conversation):
{excerpts}

CURRENT ESSAY SECTION (missing the content above):
{section}

Return ONLY the complete revised section (the ## or ### heading line through the end of the \
section), nothing else — no preamble, no explanation."""


def parse_verify_response(text: str) -> tuple[bool, str]:
    verdict_m = re.search(r"VERDICT:\s*(YES|NO)", text, re.IGNORECASE)
    reason_m = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
    is_missing = bool(verdict_m and verdict_m.group(1).upper() == "NO")
    reason = reason_m.group(1).strip() if reason_m else text.strip()
    return is_missing, reason


def verify(client: anthropic.Anthropic, excerpt: str, section: str) -> tuple[bool, str]:
    resp = client.messages.create(
        model=VERIFY_MODEL, max_tokens=200,
        messages=[{"role": "user", "content": VERIFY_PROMPT.format(excerpt=excerpt, section=section)}],
    )
    return parse_verify_response(resp.content[0].text)


def patch(client: anthropic.Anthropic, excerpts: list[str], section: str) -> str:
    """Patch a section against ALL of its confirmed-missing excerpts in one call.
    Multiple flags landing in the same section must never be patched independently —
    each patch() call fully rewrites the section, so applying more than one per section
    sequentially corrupts the splice (stale offsets from the first patch no longer align
    with the second). One call per unique section, with every excerpt it needs, is the
    only safe way to do this."""
    joined = "\n\n---\n\n".join(f"Excerpt {i + 1}:\n{e}" for i, e in enumerate(excerpts))
    resp = client.messages.create(
        model=PATCH_MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": PATCH_PROMPT.format(excerpts=joined, section=section)}],
    )
    return resp.content[0].text.strip()


# ─── Batch API mode ──────────────────────────────────────────────────────────────
# Mirrors pipeline.py's _run_batch_phase pattern (resumable via a saved batch_id state
# file, same poll/backoff shape) — reused here rather than reinvented so a machine
# sleep/interruption mid-run is recoverable the same way the rest of this codebase
# already handles it.

def submit_and_wait(client: anthropic.Anthropic, requests_list: list[dict], state_file: Path):
    """Submit a batch (or resume one already submitted by an interrupted prior run),
    poll until done, and return the finished batch object. Caller reads results via
    client.messages.batches.results(batch.id)."""
    batch = None
    if state_file.exists():
        try:
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            batch = client.messages.batches.retrieve(saved["batch_id"])
            print(f"  Resuming saved batch {saved['batch_id']} (status={batch.processing_status})")
        except Exception as e:
            print(f"  Could not resume saved batch ({e}); submitting fresh")
            batch = None

    if batch is None:
        print(f"  Submitting {len(requests_list)} request(s) to Batch API...")
        batch = client.messages.batches.create(requests=requests_list)
        print(f"  Batch ID: {batch.id}")
        state_file.write_text(json.dumps({"batch_id": batch.id}), encoding="utf-8")

    start = time.time()
    # Same retry/backoff shape as pipeline.py's _run_batch_phase poll loop — a bare
    # retrieve() call with no retry crashed a live run on a plain transient
    # httpx.ConnectError, losing all progress even though the batch (and its saved
    # state file) were both fine. The whole point of using Batch API here is
    # resilience to exactly this kind of interruption.
    poll_error_backoff = [10, 30, 60, 120, 300]
    while True:
        for poll_attempt, wait in enumerate(poll_error_backoff + [None]):
            try:
                batch = client.messages.batches.retrieve(batch.id)
                break
            except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
                if wait is not None:
                    print(f"  Poll error ({e}); retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        counts = batch.request_counts
        print(f"  Status: {batch.processing_status} | succeeded={counts.succeeded} "
              f"processing={counts.processing} errored={counts.errored}")
        if batch.processing_status == "ended":
            break
        if time.time() - start > BATCH_TIMEOUT:
            print(f"  Batch timed out after {BATCH_TIMEOUT}s. Batch ID saved to {state_file}. "
                  f"Rerun to resume.")
            sys.exit(1)
        time.sleep(BATCH_POLL_INTERVAL)

    state_file.unlink(missing_ok=True)
    return batch


def run_batch(dirs: list[str], dry_run: bool):
    client = anthropic.Anthropic()
    out_dir = Path(dirs[0]).parent  # e.g. "output" — where state files live

    # ── Collect flags across all requested dafim up front ──────────────────────
    daf_data = {}   # label -> data dict from get_flags_with_context
    flag_index = []  # (label, flag_idx) in submission order, mirrors verify_requests
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
                                  "content": VERIFY_PROMPT.format(excerpt=f["excerpt"], section=f["section_text"])}],
                },
            })
            flag_index.append((data["label"], i, custom_id))

    if not verify_requests:
        print("No flags found across the requested dafim.")
        return

    # ── Phase A: verify (batch) ─────────────────────────────────────────────────
    print(f"\n{'=' * 70}\nPhase A: verifying {len(verify_requests)} flag(s) across "
          f"{len(daf_data)} daf(im)\n{'=' * 70}")
    verify_state = out_dir / ".fix_pass2_verify_batch.json"
    verify_batch = submit_and_wait(client, verify_requests, verify_state)

    verdicts = {}  # custom_id -> (is_missing, reason)
    for result in client.messages.batches.results(verify_batch.id):
        if result.result.type != "succeeded":
            print(f"  ✗ {result.custom_id}: {result.result.type}")
            continue
        verdicts[result.custom_id] = parse_verify_response(result.result.message.content[0].text)

    # ── Group confirmed-missing flags by (label, section) ───────────────────────
    confirmed_by_key = {}  # (label, section_start, section_end) -> {section_text, excerpts, macro_title}
    for label, i, custom_id in flag_index:
        if custom_id not in verdicts:
            continue
        is_missing, reason = verdicts[custom_id]
        f = daf_data[label]["flags"][i]
        status = "CONFIRMED MISSING" if is_missing else "false positive (covered)"
        print(f"\n[{label} / {f['marker']} @ {f['timestamp']:.0f}s, '{f['macro_title']}'] {status}")
        print(f"  reason: {reason}")
        if is_missing:
            key = (label, f["section_start"], f["section_end"])
            bucket = confirmed_by_key.setdefault(key, {
                "section_text": f["section_text"], "excerpts": [], "macro_title": f["macro_title"],
            })
            bucket["excerpts"].append(f["excerpt"])

    if dry_run or not confirmed_by_key:
        print(f"\n{len(confirmed_by_key)} section(s) need patching (dry-run, stopping here)"
              if dry_run else "\nNo confirmed drops — nothing to patch.")
        return

    # ── Phase B: patch (batch) — one request per (daf, section) ────────────────
    print(f"\n{'=' * 70}\nPhase B: patching {len(confirmed_by_key)} section(s)\n{'=' * 70}")
    patch_requests = []
    key_order = list(confirmed_by_key.keys())
    for idx, key in enumerate(key_order):
        bucket = confirmed_by_key[key]
        joined = "\n\n---\n\n".join(f"Excerpt {i + 1}:\n{e}" for i, e in enumerate(bucket["excerpts"]))
        custom_id = f"patch_{idx}"
        patch_requests.append({
            "custom_id": custom_id,
            "params": {
                "model": PATCH_MODEL, "max_tokens": 4000,
                "messages": [{"role": "user",
                              "content": PATCH_PROMPT.format(excerpts=joined, section=bucket["section_text"])}],
            },
        })

    patch_state = out_dir / ".fix_pass2_patch_batch.json"
    patch_batch = submit_and_wait(client, patch_requests, patch_state)

    patched_text = {}  # custom_id -> text
    for result in client.messages.batches.results(patch_batch.id):
        if result.result.type != "succeeded":
            print(f"  ✗ {result.custom_id}: {result.result.type}")
            continue
        patched_text[result.custom_id] = result.result.message.content[0].text.strip()

    # ── Apply patches, grouped by daf ───────────────────────────────────────────
    patches_by_label = {}
    for idx, key in enumerate(key_order):
        label, start, end = key
        custom_id = f"patch_{idx}"
        if custom_id not in patched_text:
            continue
        patches_by_label.setdefault(label, []).append((start, end, patched_text[custom_id]))

    for label, patches in patches_by_label.items():
        essay = daf_data[label]["essay"]
        patches.sort(key=lambda p: p[0], reverse=True)
        patched_essay = essay
        for start, end, new_text in patches:
            patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
        out_path = daf_data[label]["essay_path"].parent / "02_rewrite_patched.md"
        out_path.write_text(patched_essay, encoding="utf-8")
        print(f"Wrote {out_path}  ({len(patches)} section(s) patched)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", help="Output dir(s) to process")
    parser.add_argument("--dry-run", action="store_true", help="Detect + verify only, skip patching")
    parser.add_argument("--batch", action="store_true",
                         help="Use the Batch API across all dirs at once (resumable via saved "
                              "batch_id state files if interrupted) instead of direct calls per-daf")
    args = parser.parse_args()

    if args.batch:
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

        # Group by section (start, end) — multiple flags landing in the same section
        # must be patched together in one call, never independently (see patch()'s
        # docstring for why independent patches to the same span corrupt the splice).
        confirmed_by_section: dict[tuple[int, int], dict] = {}
        for f in data["flags"]:
            is_missing, reason = verify(client, f["excerpt"], f["section_text"])
            status = "CONFIRMED MISSING" if is_missing else "false positive (covered)"
            print(f"\n[{f['marker']} @ {f['timestamp']:.0f}s, section '{f['macro_title']}'] {status}")
            print(f"  reason: {reason}")

            if is_missing and not args.dry_run:
                key = (f["section_start"], f["section_end"])
                bucket = confirmed_by_section.setdefault(key, {
                    "section_text": f["section_text"], "excerpts": [], "macro_title": f["macro_title"],
                })
                bucket["excerpts"].append(f["excerpt"])

        if confirmed_by_section:
            for key, bucket in confirmed_by_section.items():
                n = len(bucket["excerpts"])
                print(f"\nPatching '{bucket['macro_title']}' with {n} confirmed excerpt(s)...")
                new_section = patch(client, bucket["excerpts"], bucket["section_text"])
                bucket["new_text"] = new_section
                print(f"  -> patched section ({len(new_section)} chars)")

            # Apply from the end of the file backward so earlier offsets stay valid —
            # safe now because each (start, end) key appears at most once.
            patches = sorted(
                ((start, end, b["new_text"]) for (start, end), b in confirmed_by_section.items()),
                key=lambda p: p[0], reverse=True,
            )
            patched_essay = essay
            for start, end, new_text in patches:
                # Never trust the model's trailing whitespace to match the original
                # section's exact separator before the next heading/rule — normalize to
                # exactly one blank line, matching this file's own convention everywhere
                # else. (Found live: a bare .strip() on the patch response ate the blank
                # line before a "---" divider, gluing it directly onto the next heading.)
                patched_essay = patched_essay[:start] + new_text.rstrip() + "\n\n" + patched_essay[end:]
            out_path = daf_dir / "02_rewrite_patched.md"
            out_path.write_text(patched_essay, encoding="utf-8")
            print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
