#!/usr/bin/env python3
"""Add Gemara line anchors to outlines generated before anchors existed. One Batch API request
per daf (Sonnet 5 by default: this is alignment, not outlining).

Each outline section gets "text": {"from": "6a.8", "to": "6a.15"}, the Sefaria labels the web app
and apps use to scroll the Gemara, page and shiur in step with the outline. The model sees the
outline (ids, titles, amud, gists, bullets) and the labelled Sefaria text; it returns only the
anchors, which are then merged into the outline file (original kept as *.pre_anchors.json).

    venv/bin/python -u anchor_pass.py --dafim gittin_18 ... [--outline opus55] [--dry-run]
    venv/bin/python -u anchor_pass.py --dafim ... --merge-only     # re-merge saved results

Local checks after merging (free): labels exist, ranges run forward, children sit inside their
parent, and starts follow document order.
"""
import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from key_terms_pass import compact_outline
from outline_pass import MODEL_TAGS, RESULTS, STATE_DIR, parse_outline
from upload_to_supabase import parse_dir_name

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
DAF_TEXT = HERE / "daf_text"
POLL_INTERVAL = 60
NEXT_EDGE = 6

SYSTEM_PROMPT = """You are adding Gemara line anchors to an existing study outline of one daf of Talmud.

You receive the outline (each section's id, title, amud, one-line gist and bullets, indented by depth) and the Gemara text, one line per Sefaria segment, each with its label in brackets: [6a.8] is amud 6a, segment 8.

For every section, give the first and last label of the Gemara text that section covers: {"from": "6a.8", "to": "6a.15"}.
- Use only labels that appear in the text you are given. A section may start on the previous amud (e.g. "5b.24") when the outline begins there.
- A parent's range spans all of its children's ranges; a child's range lies inside its parent's.
- Sections are in the Gemara's order, so each section starts at or after the one before it (children count: a parent and its first child usually start on the same label). Ranges of consecutive siblings usually meet or leave no gap; they overlap only when a line genuinely belongs to both.
- A section that returns to an earlier topic still anchors to where it falls in the text now, not to the earlier passage.
- Anchor to the lines the section actually outlines. Bullets marked as the shiur's analysis don't move the range; the Gemara bullets do.
- If the outline covers material that continues onto the next daf, the last section ends at the last label on this daf that it covers.
- Be exact: the app scrolls the text to these lines.

Return only JSON, no prose: {"anchors": {"<section id>": {"from": "<label>", "to": "<label>"}, ...}} with every section id in the outline."""


def amud_key(a: str):
    return int(a[:-1]), a[-1]


def neighbor(amud: str, step: int) -> str:
    idx = int(amud[:-1]) * 2 + (amud[-1] == "b") + step
    return f"{idx // 2}{'ab'[idx % 2]}"


def outline_span(outline: dict) -> list[str]:
    found = set()

    def walk(ns):
        for n in ns or []:
            found.update(re.findall(r"\d+[ab]", str(n.get("amud", "")).split("→")[0]))
            walk(n.get("children"))

    walk(outline.get("sections"))
    seq = sorted(found, key=amud_key)
    out, a = [], seq[0]
    while True:
        out.append(a)
        if a == seq[-1]:
            return out
        a = neighbor(a, 1)


def text_lines(key: str, outline: dict) -> list[tuple[str, str]]:
    """[(label, english)] for the outline's amudim, plus the start of the next amud."""
    tractate, _ = parse_dir_name(key)
    book = json.loads((DAF_TEXT / f"{tractate}.json").read_text(encoding="utf-8"))["amudim"]
    span = outline_span(outline)
    after = neighbor(span[-1], 1)
    lines = []
    for a in span:
        lines += [(f"{a}.{s['n']}", s["en"].replace("**", "")) for s in book.get(a, {}).get("segments", [])]
    lines += [(f"{after}.{s['n']}", s["en"].replace("**", ""))
              for s in book.get(after, {}).get("segments", [])[:NEXT_EDGE]]
    return lines


def outline_path(key, tag):
    return RESULTS / key / f"04_outline_{tag}.json"


def user_prompt(key: str, outline: dict) -> str:
    def walk(ns, depth, out):
        for n in ns or []:
            out.append(f"{'  ' * depth}[{n['id']}] amud {n.get('amud', '')}")
            walk(n.get("children"), depth + 1, out)
        return out
    text = "\n".join(f"[{lab}] {en}" for lab, en in text_lines(key, outline))
    return (f"# Daf: {key}\n\n## Outline\n{compact_outline(outline)}\n\n"
            f"## Section ids and amudim\n" + "\n".join(walk(outline.get("sections"), 0, [])) +
            f"\n\n## Gemara text (Sefaria English)\n{text}\n\nNow give the anchors JSON.")


def build_request(key, outline, model, effort):
    return {"custom_id": f"{key}__{MODEL_TAGS[model]}",
            "params": {"model": model, "max_tokens": 16000, "thinking": {"type": "adaptive"},
                       "output_config": {"effort": effort},
                       "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                       "messages": [{"role": "user", "content": user_prompt(key, outline)}]}}


def check(outline, pos):
    probs, last = [], -1

    def walk(ns, parent):
        nonlocal last
        for n in ns or []:
            r = n.get("text") or {}
            f, t = pos.get(r.get("from")), pos.get(r.get("to"))
            name = n.get("title", n["id"])
            if f is None or t is None:
                probs.append(f"{name}: unknown or missing label {r}")
            else:
                if f > t:
                    probs.append(f"{name}: runs backward {r}")
                if f < last:
                    probs.append(f"{name}: starts before the previous section {r}")
                if parent and (f < parent[0] or t > parent[1]):
                    probs.append(f"{name}: outside its parent {r}")
                last = f
            walk(n.get("children"), (f, t) if f is not None and t is not None else parent)

    walk(outline.get("sections"), None)
    return probs


def widen_parents(nodes, pos) -> list[str]:
    """A parent's range must span its children's. Where the model stopped a parent short (it tends
    to end a parent on its own first line when a child follows), stretch the parent to cover them.
    Deterministic and local; returns what changed."""
    changed = []

    def span(n):
        r = n.get("text") or {}
        lo, hi = pos.get(r.get("from")), pos.get(r.get("to"))
        for c in n.get("children") or []:
            clo, chi = span(c)
            if clo is not None and (lo is None or clo < lo):
                lo = clo
            if chi is not None and (hi is None or chi > hi):
                hi = chi
        if lo is not None and hi is not None:
            labels = {v: k for k, v in pos.items()}
            new = {"from": labels[lo], "to": labels[hi]}
            if new != r:
                changed.append(f"{n.get('title', n['id'])}: {r} -> {new}")
                n["text"] = new
        return lo, hi

    for n in nodes or []:
        span(n)
    return changed


def merge(key, tag, anchors_tag):
    op = outline_path(key, tag)
    ap = RESULTS / key / f"04_anchors_{anchors_tag}.json"
    anchors = json.loads(ap.read_text(encoding="utf-8"))["anchors"]
    backup = op.with_name(op.stem + ".pre_anchors.json")
    if not backup.exists():
        shutil.copy(op, backup)
    outline = json.loads(backup.read_text(encoding="utf-8"))
    missing = []

    def walk(ns):
        for n in ns or []:
            a = anchors.get(n["id"])
            if a and a.get("from"):
                n["text"] = {"from": a["from"], "to": a.get("to") or a["from"]}
            else:
                missing.append(n["id"])
            walk(n.get("children"))

    walk(outline.get("sections"))
    pos = {lab: i for i, (lab, _) in enumerate(text_lines(key, outline))}
    widened = widen_parents(outline.get("sections"), pos)
    op.write_text(json.dumps(outline, ensure_ascii=False, indent=1), encoding="utf-8")
    for w in widened:
        print(f"    widened {w}")
    probs = check(outline, pos) + [f"no anchor for {m}" for m in missing]
    print(f"  {key}: merged into {op.relative_to(HERE)}" + ("" if probs else " (checks clean)"))
    for p in probs:
        print(f"    check: {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--outline", default="opus55")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args()
    tag = MODEL_TAGS[args.model]

    outlines = {}
    for key in args.dafim:
        p = outline_path(key, args.outline)
        backup = p.with_name(p.stem + ".pre_anchors.json")
        outlines[key] = json.loads((backup if backup.exists() else p).read_text(encoding="utf-8"))

    if args.merge_only:
        for key in args.dafim:
            merge(key, args.outline, tag)
        return

    print(f"{len(outlines)} requests with {args.model} (effort {args.effort})")
    for key, o in outlines.items():
        print(f"  {key:16s} prompt {len(user_prompt(key, o)):,} chars")
    if args.dry_run:
        return

    client = anthropic.Anthropic()
    state = STATE_DIR / f".anchor_batch_{tag}.json"
    if state.exists():
        bid = json.loads(state.read_text())["batch_id"]
        print(f"Resuming batch {bid}")
    else:
        bid = client.messages.batches.create(
            requests=[build_request(k, o, args.model, args.effort) for k, o in outlines.items()]).id
        state.write_text(json.dumps({"batch_id": bid}))
        print(f"Submitted batch {bid}")
    while True:
        b = client.messages.batches.retrieve(bid)
        c = b.request_counts
        print(f"  {b.processing_status}: succeeded={c.succeeded} processing={c.processing} errored={c.errored}")
        if b.processing_status == "ended":
            break
        time.sleep(POLL_INTERVAL)

    usage = []
    for r in client.messages.batches.results(bid):
        key = r.custom_id.split("__")[0]
        if r.result.type != "succeeded":
            print(f"  {key}: {r.result.type}")
            continue
        msg = r.result.message
        u = msg.usage
        usage.append({"id": r.custom_id, "in": u.input_tokens, "cache_read": u.cache_read_input_tokens,
                      "cache_write": u.cache_creation_input_tokens, "out": u.output_tokens, "stop": msg.stop_reason})
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        (RESULTS / key / f"04_anchors_{tag}.raw.txt").write_text(text, encoding="utf-8")
        try:
            (RESULTS / key / f"04_anchors_{tag}.json").write_text(
                json.dumps(parse_outline(text), ensure_ascii=False, indent=1), encoding="utf-8")
            merge(key, args.outline, tag)
        except Exception as e:
            print(f"  {key}: could not parse ({e}); raw saved")
    (STATE_DIR / "last_anchor_usage.json").write_text(json.dumps(usage, indent=1))
    state.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
