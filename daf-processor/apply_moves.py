"""apply_moves.py — applies relocate_check.py's "high confidence" verdicts to an
assembled v10 output, moving each relocated quote-run to the end of its target heading's
existing content. Writes a patched copy for manual review; never overwrites the source
(the same test-scope philosophy as fix_pass2_gaps.py — a report + a patched copy to
compare against, not a silent in-place edit)."""
import sys, json, os
from relocate_parse import parse_blocks, quote_runs, heading_of

def h3_insert_points(blocks, lines):
    """For each h3 block, the raw line index just before the next h2/h3 — where
    relocated content gets appended (end of that section's existing content).

    parse_blocks() deliberately excludes bare '---' divider lines from the block
    list (they carry no heading/quote/prose meaning), so a naive "next h2/h3
    block" boundary walks straight past one. Corpus convention puts '---' right
    before each '## ' macro heading — when the target h3 is the last one under
    its macro, that means the boundary found above sits on the FAR side of the
    divider, and content spliced there reads as introducing the next macro
    section instead of concluding this one (confirmed live on Bava Metzia 11's
    "Reconciliation" and Bava Batra 153's "Ruling & Clarification", both moved
    to the correct heading by relocate_check.py but landing after the '---').
    Stop at the divider instead, if one falls inside this section's own span."""
    h3_idx = [i for i, b in enumerate(blocks) if b.kind == "h3"]
    points = {}
    for k, bi in enumerate(h3_idx):
        end = None
        for b in blocks[bi+1:]:
            if b.kind in ("h2", "h3"):
                end = b.start
                break
        if end is None:
            end = blocks[-1].end
        for li in range(blocks[bi].end, end):
            if lines[li].strip() == "---":
                end = li
                break
        points[blocks[bi].text] = end
    return points

def apply(path, moves_by_run_key):
    """moves_by_run_key: dict mapping tuple(quote_indices) -> a move spec, using the SAME
    block indices build_windows()/relocate_check.py produced. A move spec is one of:
      {"type": "single", "target": <heading text>}
      {"type": "split", "split_after": <int>, "first_target": <heading>, "second_target": <heading>}
      {"type": "split3", "split1": <int>, "split2": <int>,
       "first_target": <heading>, "second_target": <heading>, "third_target": <heading>}
    For a split, run[:split_after] and run[split_after:] are relocated independently —
    each half may move to a different heading (or stay, if its target equals the run's
    current heading). split3 is the same idea with two pinned cut points and three pieces
    (relocate_check.py only produces split3 when both cuts land on a literal Mishna/Gemara
    marker boundary — see marker_split_points in relocate_parse.py).

    A moved sub-run is inserted in DOCUMENT ORDER relative to whatever else ends up under
    its target heading, not simply appended at the end of that heading's existing content.
    Without this, a sub-run moved INTO a heading that already has its own untouched native
    quotes lands after them even when it originally sat earlier in the daf -- confirmed on
    Bava Batra 174's "Amoraim Debate: Labels": the dilemma + Rabbi Yitzchak's resolution
    (originally the tail of "Rav Huna: Language Test", moved forward by a split) have a
    lower block index than that heading's own native Rav Chisda/Rava quotes, so they must
    land BEFORE them, not after (found 2026-08-07)."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    blocks = parse_blocks("\n".join(lines))
    runs = quote_runs(blocks)
    insert_points = h3_insert_points(blocks, lines)

    removals = []
    insertions = {}  # target heading -> list of (origin block index, raw text)
    applied = 0

    def move_subrun(sub_run, target, current_h):
        nonlocal applied
        if not sub_run or target == current_h or target not in insert_points:
            return
        line_start = blocks[sub_run[0]].start
        line_end = blocks[sub_run[-1]].end
        raw = "\n".join(lines[line_start:line_end])
        removals.append((line_start, line_end))
        insertions.setdefault(target, []).append((sub_run[0], raw))
        applied += 1

    for run in runs:
        key = tuple(run)
        move = moves_by_run_key.get(key)
        if not move:
            continue
        current_h = heading_of(blocks, run[0])
        if move["type"] == "single":
            move_subrun(run, move["target"], current_h)
        elif move["type"] == "split":
            k = move["split_after"]
            if move.get("first_confidence", "high") == "high":
                move_subrun(run[:k], move["first_target"], current_h)
            if move.get("second_confidence", "high") == "high":
                move_subrun(run[k:], move["second_target"], current_h)
        elif move["type"] == "split3":
            k1, k2 = move["split1"], move["split2"]
            if move.get("first_confidence", "high") == "high":
                move_subrun(run[:k1], move["first_target"], current_h)
            if move.get("second_confidence", "high") == "high":
                move_subrun(run[k1:k2], move["second_target"], current_h)
            if move.get("third_confidence", "high") == "high":
                move_subrun(run[k2:], move["third_target"], current_h)

    for target in insertions:
        insertions[target].sort(key=lambda p: p[0])

    keep = [True] * len(lines)
    for s, e in removals:
        for i in range(s, e):
            keep[i] = False

    # Every KEPT (non-moved) quote/prose block's start line, tagged with its (unchanged)
    # heading and its block index -- used to interleave pending insertions for that
    # heading in the right slot as we walk the document top to bottom.
    kept_block_starts = {}
    for bi, b in enumerate(blocks):
        if b.kind in ("h2", "h3") or not keep[b.start]:
            continue
        kept_block_starts[b.start] = (bi, heading_of(blocks, bi))

    flushed = {t: 0 for t in insertions}

    def flush_upto(target, upto_block_index):
        blobs = insertions.get(target)
        if not blobs:
            return []
        i = flushed[target]
        out_blobs = []
        while i < len(blobs) and blobs[i][0] < upto_block_index:
            out_blobs.append(blobs[i][1])
            i += 1
        flushed[target] = i
        return out_blobs

    out = []
    for i, line in enumerate(lines):
        if i in kept_block_starts:
            bi, heading_text = kept_block_starts[i]
            for blob in flush_upto(heading_text, bi):
                out.append(blob)
                out.append("")
        for target, blobs in insertions.items():
            if insert_points.get(target) == i:
                for _, blob in blobs[flushed[target]:]:
                    out.append(blob)
                    out.append("")
                flushed[target] = len(blobs)
        if keep[i]:
            out.append(line)
    for target, blobs in insertions.items():
        for _, blob in blobs[flushed[target]:]:
            out.append(blob)
            out.append("")
    return "\n".join(out), applied

if __name__ == "__main__":
    daf = sys.argv[1]
    suffix = sys.argv[2] if len(sys.argv) > 2 else ""
    here = os.path.dirname(__file__)
    v10_file = f"03_text_first_prototype_v10{suffix}.md"
    src = os.path.join(here, "output", daf, v10_file)
    results = json.load(open(os.path.join(here, "review_v10_relocated", f"{daf}{suffix}.json")))
    moves = {}
    for r in results:
        res = r["result"]
        if not res:
            continue
        if res.get("action") == "split":
            # Each half is gated on its own confidence (apply() below only moves a half
            # if it's high) -- a low-confidence half just means that half stays put,
            # it doesn't block the other half's fix.
            moves[tuple(r["quote_indices"])] = {
                "type": "split",
                "split_after": res["split_after"],
                "first_target": res["first_heading"],
                "first_confidence": res.get("first_confidence"),
                "second_target": res["second_heading"],
                "second_confidence": res.get("second_confidence"),
            }
        elif res.get("action") == "split3":
            moves[tuple(r["quote_indices"])] = {
                "type": "split3",
                "split1": res["split1"],
                "split2": res["split2"],
                "first_target": res["first_heading"],
                "first_confidence": res.get("first_confidence"),
                "second_target": res["second_heading"],
                "second_confidence": res.get("second_confidence"),
                "third_target": res["third_heading"],
                "third_confidence": res.get("third_confidence"),
            }
        elif res.get("moved") and res.get("confidence") == "high":
            moves[tuple(r["quote_indices"])] = {"type": "single", "target": res["chosen_heading"]}
    patched, applied = apply(src, moves)
    outdir = os.path.join(here, "review_v10_relocated")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, f"{daf}{suffix}_relocated.md")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"{daf}: {applied}/{len(moves)} moves actually applied -> {outpath}")
