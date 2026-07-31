"""apply_moves.py — applies relocate_check.py's "high confidence" verdicts to an
assembled v10 output, moving each relocated quote-run to the end of its target heading's
existing content. Writes a patched copy for manual review; never overwrites the source
(the same test-scope philosophy as fix_pass2_gaps.py — a report + a patched copy to
compare against, not a silent in-place edit)."""
import sys, json, os
from relocate_parse import parse_blocks, quote_runs, heading_of

def h3_insert_points(blocks):
    """For each h3 block, the raw line index just before the next h2/h3 — where
    relocated content gets appended (end of that section's existing content)."""
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
        points[blocks[bi].text] = end
    return points

def apply(path, moves_by_run_key):
    """moves_by_run_key: dict mapping tuple(quote_indices) -> target_heading_text,
    using the SAME block indices build_windows()/relocate_check.py produced."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    blocks = parse_blocks("\n".join(lines))
    runs = quote_runs(blocks)
    insert_points = h3_insert_points(blocks)

    removals = []
    insertions = {}
    applied = 0
    for run in runs:
        key = tuple(run)
        target = moves_by_run_key.get(key)
        if not target:
            continue
        current_h = heading_of(blocks, run[0])
        if target == current_h or target not in insert_points:
            continue
        line_start = blocks[run[0]].start
        line_end = blocks[run[-1]].end
        raw = "\n".join(lines[line_start:line_end])
        removals.append((line_start, line_end))
        insertions.setdefault(target, []).append(raw)
        applied += 1

    keep = [True] * len(lines)
    for s, e in removals:
        for i in range(s, e):
            keep[i] = False

    out = []
    for i, line in enumerate(lines):
        for target, blobs in list(insertions.items()):
            if insert_points.get(target) == i:
                for blob in blobs:
                    out.append(blob)
                    out.append("")
                del insertions[target]
        if keep[i]:
            out.append(line)
    for target, blobs in insertions.items():
        for blob in blobs:
            out.append(blob)
            out.append("")
    return "\n".join(out), applied

if __name__ == "__main__":
    daf = sys.argv[1]
    here = os.path.dirname(__file__)
    src = os.path.join(here, "output", daf, "03_text_first_prototype_v10.md")
    results = json.load(open(os.path.join(here, "review_v10_relocated", f"{daf}.json")))
    moves = {}
    for r in results:
        res = r["result"]
        if res and res.get("moved") and res.get("confidence") == "high":
            moves[tuple(r["quote_indices"])] = res["chosen_heading"]
    patched, applied = apply(src, moves)
    outdir = os.path.join(here, "review_v10_relocated")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, f"{daf}_relocated.md")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"{daf}: {applied}/{len(moves)} moves actually applied -> {outpath}")
