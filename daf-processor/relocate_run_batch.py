#!/usr/bin/env python3
"""relocate_run_batch.py — Batch API version of relocate_run_all.py, for corpus-scale runs.

relocate_run_all.py makes one direct, synchronous API call per quote-run, strictly one at a
time (~83 sec/daf measured on the 6-daf validation batch — see CLAUDE.md, "why is it taking
so long" — extrapolates to ~54 hours sequential for the full corpus). This script submits
every window across every requested daf as ONE Batch API submission (matching
fix_wall_of_text.py's existing pattern, via fix_pass2_gaps.submit_and_wait), gets ~50% batch
pricing, and runs server-side in parallel instead of one call at a time.

Two-phase, same as relocate_run_all.py's own two rounds:
  Phase 1 — one batch covering every window with >1 candidate, across every requested daf.
  Phase 2 — the starved-heading rescue pass (relocate_rescue_starved.py's logic), which
            depends on phase 1's results, submitted as a second batch.

Writes the same per-daf JSON shape relocate_run_all.py produces
(review_v10_relocated/{daf}{suffix}.json), so apply_moves_batch.py needs no changes.

Usage:
    python relocate_run_batch.py --dafim sanhedrin_67 shabbat_11 --v10-file 03_text_first_prototype_v10_wallpatched.md --suffix _wallpatched_split
    python relocate_run_batch.py --all --v10-file 03_text_first_prototype_v10_wallpatched.md --suffix _wallpatched_split
"""
import argparse
import glob
import json
import os
import time
from pathlib import Path

import anthropic
import httpx
from config import REWRITE_MODEL
from fix_pass2_gaps import submit_and_wait
from relocate_check import build_prompt, build_prompt_split3, split3_points, parse_response, parse_response_split3
from relocate_parse import parse_blocks, build_windows, prose_of_heading
from relocate_rescue_starved import find_rescue_targets

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "review_v10_relocated")


def build_request(idx, w):
    pts = split3_points(w)
    if pts:
        prompt = build_prompt_split3(w, *pts)
    else:
        prompt = build_prompt(w)
    return {
        "custom_id": str(idx),
        "params": {
            "model": REWRITE_MODEL,
            # 800 (relocate_check.py's original synchronous value) truncated mid-JSON
            # (stop_reason: max_tokens) on shekalim_11's one 18-quote-index split window,
            # 2026-08-09 -- large windows need more room for the reasoning fields before the
            # JSON verdict. Only 1 of 36,432 corpus-wide requests hit it, but the fix is free
            # (batch pricing is token-count-based, not a flat per-request fee) and removes the
            # failure mode outright rather than just tolerating it as unparseable noise.
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
    }


def parse_result(w, pts, text):
    return parse_response_split3(w, pts[0], pts[1], text) if pts else parse_response(w, text)


CHUNK_SIZE = 1500  # corpus-scale relocate submission (36,432 requests, ~298MB of prompt text
# -- measured 2026-08-08) hit the Batch API's 256MB request-size cap in one shot, rejected
# outright before any cost was incurred (same fail-closed behavior as an invalid custom_id), so
# no wasted spend, but no progress either. Chunked to 5000/request first (~41MB/chunk, well
# under the cap); that run looked hung for 48+ minutes with zero visible output, but WAS NOT --
# stdout was buffered (writing to a file, not a tty) so its real progress (5 chunks submitted
# and processed in sequence, ~5-10 min apiece) was invisible until killed. Dropped to 1500 and
# now always run with `python -u` (or PYTHONUNBUFFERED=1) so progress is actually observable
# in real time -- the smaller size is not itself required, just kept as a smaller unit of retry
# exposure now that create()/results() below can also hit plain transient network errors
# (Broken pipe, ReadTimeout -- both observed same night, unrelated to size).
# Custom_id stays globally unique across chunks since it's the pre-assigned index_map position,
# not reset per chunk, so no collision risk from splitting.

RETRY_BACKOFF = [10, 30, 60, 120, 300, 300, 300, 300, 300, 300]  # widened 2026-08-09, see
# the matching note on poll_error_backoff in fix_pass2_gaps.py -- same reasoning applies here.


def harvest_results(client, batch_id, texts):
    """Stream a batch's results into `texts` (custom_id -> response text), retrying the whole
    streamed read on a transient network error. results() returns a lazy iterator over the
    HTTP response body, so a mid-stream drop (httpx.ReadTimeout, seen live 2026-08-09) can
    fail partway through -- restarting the read is safe/idempotent since `texts` is a dict
    keyed by custom_id, so a retried partial or full re-read just overwrites the same keys."""
    for wait in RETRY_BACKOFF + [None]:
        try:
            for result in client.messages.batches.results(batch_id):
                if result.result.type != "succeeded":
                    print(f"  x {result.custom_id}: {result.result.type}")
                    continue
                texts[result.custom_id] = result.result.message.content[0].text
            return
        # results() is a streamed iterator -- a mid-stream drop raises the raw httpx
        # transport exception directly (httpx.ReadTimeout, seen live 2026-08-09), NOT the
        # anthropic-SDK-wrapped APIConnectionError that non-streaming calls like create()/
        # retrieve() raise. Both are caught here since either can occur depending on exactly
        # where in the read the failure happens.
        except (anthropic.APIConnectionError, anthropic.APIStatusError, httpx.TransportError) as e:
            if wait is not None:
                print(f"  Results read error ({e}); retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def run_batch_requests(client, requests, state_path, label, recover_batch_ids=None):
    """recover_batch_ids: batch IDs from a prior invocation of this same phase that were
    submitted but never collected -- e.g. the local process was killed mid-run while chunks
    were still legitimately processing server-side (found 2026-08-08: buffered stdout on a
    background run made 4 successfully-completed chunks + 1 in-progress chunk look like a
    hung process, and killing the local script does NOT cancel the remote batch -- the work,
    and its cost, already happened). Harvesting these instead of resubmitting avoids paying
    twice for the same requests. Every already-covered custom_id is skipped when building the
    remaining chunks below, so this is safe to pass even if the recovered batches only cover
    part of `requests`."""
    if not requests:
        return {}
    texts = {}
    for bid in (recover_batch_ids or []):
        batch = client.messages.batches.retrieve(bid)
        while batch.processing_status != "ended":
            print(f"  Recovering {bid}: status={batch.processing_status}, waiting...")
            time.sleep(30)
            batch = client.messages.batches.retrieve(bid)
        n_before = len(texts)
        harvest_results(client, bid, texts)
        print(f"  Recovered {bid}: +{len(texts) - n_before} result(s) ({len(texts)} total so far)")

    remaining = [r for r in requests if r["custom_id"] not in texts]
    if not remaining:
        return texts
    if texts:
        print(f"{label}: {len(texts)} already recovered, {len(remaining)} remaining")
    chunks = [remaining[i:i + CHUNK_SIZE] for i in range(0, len(remaining), CHUNK_SIZE)]
    for ci, chunk in enumerate(chunks):
        # Content-addressed, NOT positional (`_part{ci}`) -- found 2026-08-09 as the root
        # cause of 67 dafim (932 windows) silently getting ZERO relocate results despite the
        # run reporting success. `remaining` shrinks across repeated crash/relaunch cycles
        # (this file logged several tonight), so the number and boundaries of chunks differ
        # between invocations -- "part 2" of a 3-chunk retry is a totally different set of
        # requests than "part 2" of an earlier 8-chunk attempt. A state file only survives a
        # crash if it dies mid-poll (before submit_and_wait's own state_file.unlink() on
        # success), which is exactly what tonight's network drops did. The stale leftover
        # file from an earlier attempt's "part2" (a real, different 1500-request chunk) was
        # silently RESUMED in place of submitting this run's new "part2" (932 requests) --
        # `submit_and_wait` has no way to know the file's cached batch_id doesn't match the
        # content it's about to be asked to cover, and harvest_results writes results keyed
        # by their OWN embedded custom_id, so the stale batch's real results landed under
        # their own (already-covered) custom_ids while the intended 932 new custom_ids
        # simply never got submitted -- `result: None` for every one of them, indistinguishable
        # in the log from a normal successful chunk (it reported the STALE batch's counts).
        # Keying on the chunk's own first/last custom_id makes a collision impossible: two
        # chunks can only share a state filename if they cover the exact same requests.
        chunk_state = (state_path if len(chunks) == 1
                        else state_path.with_name(
                            f"{state_path.stem}_c{chunk[0]['custom_id']}-{chunk[-1]['custom_id']}{state_path.suffix}"))
        print(f"{label} part {ci + 1}/{len(chunks)}: submitting {len(chunk)} request(s)...")
        batch = submit_and_wait(client, chunk, chunk_state)
        harvest_results(client, batch.id, texts)
    return texts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="*", default=None, help="Daf dir names to process")
    ap.add_argument("--all", action="store_true", help="Process every daf under output/ that has the given --v10-file")
    ap.add_argument("--v10-file", default="03_text_first_prototype_v10_wallpatched.md")
    ap.add_argument("--suffix", default="_wallpatched_split")
    ap.add_argument("--recover-batch-ids", nargs="*", default=None,
                     help="Batch IDs from a prior phase-1 invocation that were submitted but "
                          "never collected (e.g. the local process was killed while they were "
                          "still legitimately processing server-side) -- harvested instead of "
                          "resubmitted, so already-paid-for work isn't paid for twice.")
    args = ap.parse_args()

    if args.all:
        dafim = sorted(
            os.path.basename(os.path.dirname(p))
            for p in glob.glob(os.path.join(HERE, "output", "*", args.v10_file))
        )
    elif args.dafim:
        dafim = args.dafim
    else:
        ap.error("pass --dafim <names...> or --all")

    os.makedirs(OUT_DIR, exist_ok=True)
    client = anthropic.Anthropic()

    # ── Load blocks/windows for every daf, skip already-done ──────────────────
    per_daf = {}
    for d in dafim:
        outpath = os.path.join(OUT_DIR, f"{d}{args.suffix}.json")
        if os.path.exists(outpath):
            print(f"{d}: already done, skipping")
            continue
        v10_path = os.path.join(HERE, "output", d, args.v10_file)
        if not os.path.exists(v10_path):
            print(f"{d}: SKIP (no {args.v10_file})")
            continue
        text = open(v10_path, encoding="utf-8", errors="replace").read()
        blocks = parse_blocks(text)
        windows = build_windows(blocks)
        per_daf[d] = {"blocks": blocks, "windows": windows, "outpath": outpath}

    if not per_daf:
        print("Nothing to do.")
        return

    # ── Phase 1: one batch across every window, every daf ─────────────────────
    requests = []
    index_map = []  # position i -> (daf, w, split3_points)
    for d, info in per_daf.items():
        for w in info["windows"]:
            if len(w["candidates"]) <= 1:
                continue
            idx = len(index_map)
            pts = split3_points(w)
            index_map.append((d, w, pts))
            requests.append(build_request(idx, w))

    state_path_1 = Path(HERE) / "output" / ".relocate_batch_phase1.json"
    texts = run_batch_requests(client, requests, state_path_1, "Phase 1",
                                recover_batch_ids=args.recover_batch_ids)

    results_by_daf = {d: [] for d in per_daf}
    results_by_key = {d: {} for d in per_daf}
    for i, (d, w, pts) in enumerate(index_map):
        text = texts.get(str(i))
        result = parse_result(w, pts, text) if text is not None else None
        entry = {
            "quote_indices": w["quote_indices"],
            "current_heading": w["current_heading"],
            "candidates": [c["heading"] for c in w["candidates"]],
            "result": result,
        }
        results_by_daf[d].append(entry)
        results_by_key[d][tuple(w["quote_indices"])] = result

    # Windows with 1 candidate never got a request/result at all -- they're
    # unambiguous by construction (relocate_run_all.py's `continue` above skips
    # them the same way), nothing to add for those.

    for d in per_daf:
        n_checked = len(results_by_daf[d])
        moved = sum(1 for r in results_by_daf[d] if r["result"] and r["result"].get("moved"))
        print(f"{d}: {n_checked} checked, {moved} recommended moves (phase 1)")

    # ── Phase 2: starved-heading rescue, one batch across every daf ───────────
    rescue_requests = []
    rescue_index_map = []  # position i -> (daf, w2)
    for d, info in per_daf.items():
        targets = find_rescue_targets(info["blocks"], info["windows"], results_by_key[d])
        for w, h, h_bi in targets:
            rescued_candidate = {"heading": h, "prose": prose_of_heading(info["blocks"], h_bi), "is_current": False}
            w2 = dict(w)
            w2["candidates"] = [rescued_candidate] + list(w["candidates"])
            idx = len(rescue_index_map)
            rescue_index_map.append((d, w, w2))
            pts = split3_points(w2)
            rescue_requests.append(build_request(idx, w2))

    state_path_2 = Path(HERE) / "output" / ".relocate_batch_phase2.json"
    rescue_texts = run_batch_requests(client, rescue_requests, state_path_2, "Phase 2 (rescue)")

    rescued_count = {d: 0 for d in per_daf}
    for i, (d, w, w2) in enumerate(rescue_index_map):
        text = rescue_texts.get(str(i))
        if text is None:
            continue
        pts = split3_points(w2)
        new_result = parse_result(w2, pts, text)
        for entry in results_by_daf[d]:
            if tuple(entry["quote_indices"]) == tuple(w["quote_indices"]):
                entry["candidates"] = [c["heading"] for c in w2["candidates"]]
                entry["result"] = new_result
                rescued_count[d] += 1
                break

    # ── Write per-daf JSONs, same shape as relocate_run_all.py ────────────────
    for d, info in per_daf.items():
        with open(info["outpath"], "w") as f:
            json.dump(results_by_daf[d], f, indent=2)
        note = f", {rescued_count[d]} starved-heading window(s) re-checked" if rescued_count[d] else ""
        print(f"{d}: wrote {info['outpath']}{note}")


if __name__ == "__main__":
    main()
