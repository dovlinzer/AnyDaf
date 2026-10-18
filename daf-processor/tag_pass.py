#!/usr/bin/env python3
"""Add outcome tags (chart.tags) to the charts of outlines made before the tag list existed, without
regenerating the outlines. One Batch API request per outline file (Sonnet 5 by default: this is
reading each cell and choosing from a closed list, not outlining).

The model sees each chart (its section's title and gist, the chart's title/caption, columns and rows)
and the tag rules from outline_pass.py, word for word; it returns only the tags, which are merged into
the outline file (original kept as *.before_tags.json). Hebrew outlines (04_outline_he.json) were
adapted from the Medium outline with the same charts, so they take the Medium tags by position, no call.

    venv/bin/python -u tag_pass.py --site            # every English outline on the preview site
    venv/bin/python -u tag_pass.py --files bava_metzia_4:opus55_medium ... [--dry-run]
    venv/bin/python -u tag_pass.py --site --merge-only  # re-merge saved results
"""
import argparse
import json
import re
import shutil
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from outline_pass import OUTCOME_TAGS, RESULTS, STATE_DIR, SYSTEM_PROMPT as OUTLINE_PROMPT

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
SITE_DATA = HERE.parent / "AnyDafWeb" / "site" / "data"
POLL_INTERVAL = 60
SUFFIX_TAG = {"M": "opus55_medium", "H": "opus55_high"}

# the outline prompt's own tag rule, so the two never drift
_rule = re.search(r"^- `tags` marks.*?(?=\n\n)", OUTLINE_PROMPT, re.S | re.M).group(0)

SYSTEM_PROMPT = f"""You are adding outcome tags to the charts of an existing study outline of one daf of Talmud. The charts are already written; you only mark each cell's outcome so the site can show a badge and color beside it.

The rule the outline writers follow:

{_rule}

You receive each chart with the id, title and summary line of its section, the chart's title and caption, its column headers and its rows (row label first). For each chart return `tags`, the same shape as its rows: one list per row, one entry per cell, `null` for the row label and for every cell that is not an outcome. A cell that only describes, reasons, quotes or gives a position without a result is `null`. Read what the cell means in its column: in a column such as "Ruling" or "Result", "he must swear" is `oath`; in a column of reasons, the same words are `null`. When a chart has no outcomes in it at all, return `null` for that chart instead of a grid. When a cell is clearly an outcome but no tag fits, leave it `null` and add it to `tag_questions`.

Return only JSON, no prose: {{"charts": {{"<section id>": [[...], ...] or null, ...}}, "tag_questions": [{{"section", "cell", "note"}}]}} with every section id you were given."""


def site_files():
    """(key, tag) for every English outline the preview site shows, from its data file names."""
    out = []
    for p in sorted(SITE_DATA.glob("*.json")):
        m = re.match(r"(.+?)(?:_(M|H|HE))?$", p.stem)
        key, suf = m.group(1), m.group(2)
        if key == "chagigah_6" or suf == "HE":      # the example already carries tags; Hebrew copies Medium
            continue
        out.append((key, SUFFIX_TAG.get(suf, "opus55")))
    return out


def charts(outline):
    found = []

    def walk(ns):
        for n in ns or []:
            if n.get("chart") and n["chart"].get("rows"):
                found.append(n)
            walk(n.get("children"))

    walk(outline.get("sections"))
    return found


def outline_file(key, tag):
    return RESULTS / key / f"04_outline_{tag}.json"


def source(key, tag):
    p = outline_file(key, tag)
    b = p.with_name(p.stem + ".before_tags.json")
    return json.loads((b if b.exists() else p).read_text(encoding="utf-8"))


def user_prompt(key, outline):
    parts = [f"Daf: {key}\n"]
    for n in charts(outline):
        c = n["chart"]
        parts.append(json.dumps({"section": n["id"], "section_title": n.get("title"), "gist": n.get("gist"),
                                 "chart_title": c.get("title") or "", "caption": c.get("caption") or "",
                                 "columns": c.get("columns"), "rows": c.get("rows")}, ensure_ascii=False))
    return "\n\n".join(parts)


def cid(key, tag):
    return f"{key}__{tag}"


def build_request(key, tag, outline, model, effort):
    return {"custom_id": cid(key, tag),
            "params": {"model": model, "max_tokens": 16000, "thinking": {"type": "adaptive"},
                       "output_config": {"effort": effort},
                       "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                       "messages": [{"role": "user", "content": user_prompt(key, outline)}]}}


def valid_grid(tags, rows):
    if tags is None:
        return True
    if not isinstance(tags, list) or len(tags) != len(rows):
        return False
    for t, r in zip(tags, rows):
        if not isinstance(t, list) or len(t) != len(r):
            return False
        for x in t:
            if x is not None and any(y.split(":")[0].strip() not in OUTCOME_TAGS for y in str(x).split("+")):
                return False
    return True


def merge(key, tag):
    raw = RESULTS / key / f"04_tags_{tag}.raw.txt"
    if not raw.exists():
        print(f"  {key} {tag}: no result")
        return None
    text = raw.read_text(encoding="utf-8")
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    outline = source(key, tag)
    got, probs, tagged = data.get("charts") or {}, [], 0
    for n in charts(outline):
        c = n["chart"]
        c.pop("tones", None)                         # tags supersede the older marking
        t = got.get(n["id"], "missing")
        if t == "missing":
            probs.append(f"{n['id']}: no tags returned")
        elif not valid_grid(t, c["rows"]):
            probs.append(f"{n['id']}: tags don't fit the chart ({t})")
        elif t and any(x for row in t for x in row):
            c["tags"] = t
            tagged += 1
    if data.get("tag_questions"):
        outline["tag_questions"] = data["tag_questions"]
    p = outline_file(key, tag)
    b = p.with_name(p.stem + ".before_tags.json")
    if not b.exists():
        shutil.copy2(p, b)
    p.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {key:16s} {tag:14s} {tagged}/{len(charts(outline))} charts tagged, "
          f"{len(data.get('tag_questions') or [])} questions" + ("".join(f"\n      ! {x}" for x in probs)))
    return outline


def copy_to_hebrew(key):
    """Give the Hebrew outline the Medium outline's tags, chart by chart (same sections and charts)."""
    hp = outline_file(key, "he")
    if not hp.exists():
        return
    en = json.loads(outline_file(key, "opus55_medium").read_text(encoding="utf-8"))
    hb = hp.with_name(hp.stem + ".before_tags.json")
    he = json.loads((hb if hb.exists() else hp).read_text(encoding="utf-8"))
    by_id = {n["id"]: n["chart"] for n in charts(en)}
    n_ok = 0
    for n in charts(he):
        c, e = n["chart"], by_id.get(n["id"])
        c.pop("tones", None)
        if e and e.get("tags") and valid_grid(e["tags"], c["rows"]):
            c["tags"] = e["tags"]
            n_ok += 1
        elif e and e.get("tags"):
            print(f"      ! {key} he {n['id']}: chart shape differs from the English, left untagged")
    if not hb.exists():
        shutil.copy2(hp, hb)
    hp.write_text(json.dumps(he, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {key:16s} he             {n_ok} charts tagged (from Medium)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="store_true")
    ap.add_argument("--files", nargs="*", default=[], help="key:tag")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args()

    files = site_files() if args.site else [tuple(f.split(":")) for f in args.files]
    files = [(k, t) for k, t in files if charts(source(k, t))]

    if not args.merge_only:
        n_charts = sum(len(charts(source(k, t))) for k, t in files)
        chars = sum(len(user_prompt(k, source(k, t))) for k, t in files)
        print(f"{len(files)} requests, {n_charts} charts, {chars:,} prompt chars "
              f"(+ {len(SYSTEM_PROMPT):,} system) with {args.model} (effort {args.effort})")
        if args.dry_run:
            return
        client = anthropic.Anthropic()
        state = STATE_DIR / ".tag_batch.json"
        if state.exists():
            bid = json.loads(state.read_text())["batch_id"]
            print(f"Resuming batch {bid}")
        else:
            bid = client.messages.batches.create(
                requests=[build_request(k, t, source(k, t), args.model, args.effort) for k, t in files]).id
            state.write_text(json.dumps({"batch_id": bid}))
            print(f"Submitted batch {bid}", flush=True)
        while True:
            b = client.messages.batches.retrieve(bid)
            c = b.request_counts
            print(f"  {b.processing_status}: succeeded={c.succeeded} processing={c.processing} errored={c.errored}",
                  flush=True)
            if b.processing_status == "ended":
                break
            time.sleep(POLL_INTERVAL)
        usage = []
        for r in client.messages.batches.results(bid):
            key, tag = r.custom_id.split("__")
            if r.result.type != "succeeded":
                print(f"  {r.custom_id}: {r.result.type}")
                continue
            msg = r.result.message
            u = msg.usage
            usage.append({"id": r.custom_id, "in": u.input_tokens, "cache_read": u.cache_read_input_tokens,
                          "cache_write": u.cache_creation_input_tokens, "out": u.output_tokens, "stop": msg.stop_reason})
            text = next((blk.text for blk in msg.content if blk.type == "text"), "")
            (RESULTS / key / f"04_tags_{tag}.raw.txt").write_text(text, encoding="utf-8")
        (STATE_DIR / "last_tag_usage.json").write_text(json.dumps(usage, indent=1))
        state.unlink()
        tin = sum(x["in"] for x in usage); tout = sum(x["out"] for x in usage)
        cr = sum(x["cache_read"] or 0 for x in usage); cw = sum(x["cache_write"] or 0 for x in usage)
        # Sonnet 5 batch pricing: half of $3 / $15 per million
        cost = (tin * 1.5 + cw * 1.875 + cr * 0.15 + tout * 7.5) / 1e6
        print(f"usage: in {tin:,} cache_write {cw:,} cache_read {cr:,} out {tout:,}  ~${cost:.2f}")

    for k, t in files:
        merge(k, t)
    for k in sorted({k for k, t in files if t == "opus55_medium"}):
        copy_to_hebrew(k)


if __name__ == "__main__":
    main()
