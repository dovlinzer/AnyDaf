#!/usr/bin/env python3
"""Fix-up pass: apply the author's review notes to existing outlines, without regenerating them.

Notes come from the review page's "Flag" buttons (stored with the page; saved locally as
outline/fixups/<daf>__<tag>.json) or are written by hand in the same shape:

    {"daf": "bava_batra_84", "tag": "opus55_medium",
     "notes": [{"id": "n1", "section": "s9", "title": "...", "kind": "heading", "note": "..."}]}

kind: heading | gist | structure | add_chart | fix_chart | add_picture | fix_picture | content | other

The model gets the same instructions and worked example as the outline pass (cached), the daf's
materials, the current outline and the notes, and returns only edit operations. Everything the
notes don't touch stays exactly as it was. Applying is local: the original is kept as
04_outline_<tag>.before_fixups.json and all the free checks run again.

    venv/bin/python fixup_pass.py --dafim bava_batra_84 --tag opus55_medium --dry-run
    venv/bin/python fixup_pass.py --dafim bava_batra_84 --tag opus55_medium          # Batch API
    venv/bin/python fixup_pass.py --apply-only bava_batra_84 --tag opus55_medium     # re-apply a saved reply
    venv/bin/python fixup_pass.py --from-flags DIR --tag opus55_medium    # notes saved from the page

The review page stores each note as a document in its "flags" collection; save them with the
ArtifactData tool (`list`, `out_dir`), then --from-flags turns them into the notes files above.

Calls the Anthropic API (Batch): get the author's go-ahead for each run, per the project rules.
"""
import argparse
import copy
import json
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

import outline_pass as op

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
FIXUPS = HERE / "outline" / "fixups"
MODEL = "claude-opus-5-5"
FIELDS = {"title", "gist", "bullets", "chart", "illustration", "text", "continues", "returns_to", "flag", "amud"}

INSTRUCTIONS = """# This is a fix-up pass, not a new outline

The author has reviewed the outline below and left notes. Make the changes the notes ask for, following all the rules above (headings, charts, pictures, transliteration, key terms), and change nothing else: sections the notes don't concern stay exactly as they are. A note may take more than one operation (a new subsection is an insert plus moves). If a note can't be done well, or would break a rule, don't force it; say why in `skipped`.

Return only this JSON, with no text before or after it:
{
  "ops": [
    {"op": "set", "id": "<section id>", "field": "title|gist|bullets|chart|illustration|text|continues|returns_to|flag|amud", "value": <the new value, in the outline's own format; null removes the field>},
    {"op": "insert", "parent": "<id, or null for top level>", "after": "<sibling id, or null to go first>", "section": {<a full section: id, title, amud, text, gist, bullets, children...>}},
    {"op": "move", "id": "<section id>", "parent": "<new parent id, or null for top level>", "after": "<sibling id, or null to go first>"},
    {"op": "delete", "id": "<section id>"}
  ],
  "done": [{"note": "<note id>", "how": "<one line: what you changed>"}],
  "skipped": [{"note": "<note id>", "why": "<one line>"}]
}
New sections get fresh ids (e.g. "s9a"). Keep text anchors exact: a parent's range spans its children's, and ranges follow the Gemara's order. A new or redrawn picture is a complete SVG following the illustration rules."""


def strip_svgs(outline: dict, keep: set[str]) -> dict:
    """The outline with pictures the notes don't touch shortened to a placeholder (saves input)."""
    o = copy.deepcopy(outline)

    def walk(ns):
        for n in ns or []:
            il = n.get("illustration")
            if isinstance(il, dict) and n.get("id") not in keep:
                il["svg"] = "[picture unchanged: leave as is]"
            walk(n.get("children"))
    walk(o.get("sections"))
    for k in ("judgment_calls", "coverage_notes"):
        o.pop(k, None)
    return o


def notes_path(key: str, tag: str) -> Path:
    return FIXUPS / f"{key}__{tag}.json"


def build_request(key: str, tag: str, effort: str) -> dict:
    d = op.OUTPUT / key
    if not d.is_dir():
        d = HERE / "outline" / "textonly" / key
    textonly = not (d / "02_rewrite.md").exists()
    outline = json.loads((op.RESULTS / key / f"04_outline_{tag}.json").read_text(encoding="utf-8"))
    notes = json.loads(notes_path(key, tag).read_text(encoding="utf-8"))["notes"]
    keep = {n["section"] for n in notes if n["kind"] in ("fix_picture", "add_picture")}
    user = "\n\n".join([
        op.build_user_prompt(d, textonly),
        "## The outline as it stands\n" + json.dumps(strip_svgs(outline, keep), ensure_ascii=False, indent=1),
        "## The author's notes\n" + json.dumps(
            [{k: n[k] for k in ("id", "section", "title", "kind", "note") if k in n} for n in notes],
            ensure_ascii=False, indent=1),
        INSTRUCTIONS,
    ])
    return {"custom_id": f"{key}__{tag}__fixup",
            "params": {"model": MODEL, "max_tokens": 64000, "thinking": {"type": "adaptive"},
                       "output_config": {"effort": effort}, "system": op.system_blocks(),
                       "messages": [{"role": "user", "content": user}]}}


# ---------- applying the edits (local) ----------

def _find(nodes, sid, parent=None):
    for i, n in enumerate(nodes):
        if n.get("id") == sid:
            return nodes, i, parent
        hit = _find(n.get("children") or [], sid, n)
        if hit:
            return hit
    return None


def _children(outline, pid):
    if pid is None:
        return outline["sections"]
    hit = _find(outline["sections"], pid)
    if not hit:
        raise ValueError(f"no section {pid}")
    node = hit[0][hit[1]]
    return node.setdefault("children", [])


def _place(siblings, after, node):
    if after is None:
        siblings.insert(0, node)
        return
    idx = next((i for i, n in enumerate(siblings) if n.get("id") == after), None)
    if idx is None:
        raise ValueError(f"no sibling {after} to place after")
    siblings.insert(idx + 1, node)


def apply_ops(outline: dict, ops: list[dict]) -> tuple[dict, list[str]]:
    o, log = copy.deepcopy(outline), []
    for x in ops:
        kind = x.get("op")
        try:
            if kind == "set":
                if x["field"] not in FIELDS:
                    raise ValueError(f"field {x['field']} not editable")
                hit = _find(o["sections"], x["id"])
                if not hit:
                    raise ValueError(f"no section {x['id']}")
                node = hit[0][hit[1]]
                if x["field"] == "illustration" and isinstance(x.get("value"), dict):
                    x["value"]["svg"] = op_clean_svg(x["value"].get("svg", ""))
                if x.get("value") is None:
                    node.pop(x["field"], None)
                else:
                    node[x["field"]] = x["value"]
                log.append(f"set {x['id']}.{x['field']}")
            elif kind == "insert":
                sec = x["section"]
                if _find(o["sections"], sec.get("id")):
                    raise ValueError(f"id {sec.get('id')} already used")
                _place(_children(o, x.get("parent")), x.get("after"), sec)
                log.append(f"insert {sec.get('id')} under {x.get('parent')} after {x.get('after')}")
            elif kind == "move":
                hit = _find(o["sections"], x["id"])
                if not hit:
                    raise ValueError(f"no section {x['id']}")
                node = hit[0].pop(hit[1])
                if x.get("parent") and _find([node], x["parent"]):
                    raise ValueError("can't move a section under itself")
                _place(_children(o, x.get("parent")), x.get("after"), node)
                log.append(f"move {x['id']} under {x.get('parent')} after {x.get('after')}")
            elif kind == "delete":
                hit = _find(o["sections"], x["id"])
                if not hit:
                    raise ValueError(f"no section {x['id']}")
                hit[0].pop(hit[1])
                log.append(f"delete {x['id']}")
            else:
                raise ValueError(f"unknown op {kind}")
        except (KeyError, ValueError) as e:
            log.append(f"SKIPPED {kind}: {e}")
    return o, log


def op_clean_svg(svg: str) -> str:
    from build_outline_review import clean_svg
    return clean_svg(svg)


def apply_reply(key: str, tag: str, text: str) -> None:
    out = op.RESULTS / key / f"04_outline_{tag}.json"
    before = out.with_name(f"04_outline_{tag}.before_fixups.json")
    current = json.loads(out.read_text(encoding="utf-8"))
    if not before.exists():
        before.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    m = re.search(r"\{.*\}", text, re.S)
    reply = json.loads(m.group(0)) if m else {}
    fixed, log = apply_ops(current, reply.get("ops", []))
    out.write_text(json.dumps(fixed, ensure_ascii=False, indent=1), encoding="utf-8")
    d = op.OUTPUT / key if (op.OUTPUT / key).is_dir() else HERE / "outline" / "textonly" / key
    record = {"at": time.strftime("%Y-%m-%d %H:%M"), "applied": log, "done": reply.get("done", []),
              "skipped": reply.get("skipped", []),
              "checks": op.check_anchors(fixed, d) + op.check_output(fixed, d)}
    logp = FIXUPS / f"{key}__{tag}.log.json"
    history = json.loads(logp.read_text(encoding="utf-8")) if logp.exists() else []
    logp.write_text(json.dumps(history + [record], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {key} {tag}: {len(log)} edits, {len(record['done'])} notes done, {len(record['skipped'])} skipped")
    for line in log:
        print(f"    {line}")
    for s in record["skipped"]:
        print(f"    note {s.get('note')} skipped: {s.get('why')}")
    for c in record["checks"]:
        print(f"    check: {c}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="*", default=[])
    ap.add_argument("--tag", required=True, help="which outline to fix, e.g. opus55_medium")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-only", nargs="*", help="re-apply the saved reply for these dafim")
    ap.add_argument("--from-flags", help="directory of flag documents saved from the review page")
    args = ap.parse_args()

    if args.from_flags:
        groups = {}
        for p in sorted(Path(args.from_flags).rglob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            doc = doc.get("data", doc)
            if doc.get("status") == "applied" or doc.get("tag") != args.tag:
                continue
            groups.setdefault(doc["daf"], []).append({"id": p.stem, **{k: doc.get(k) for k in
                                                     ("section", "title", "kind", "note")}})
        FIXUPS.mkdir(parents=True, exist_ok=True)
        for daf, notes in groups.items():
            notes_path(daf, args.tag).write_text(json.dumps(
                {"daf": daf, "tag": args.tag, "notes": notes}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {daf}: {len(notes)} notes -> {notes_path(daf, args.tag).relative_to(HERE)}")
        return

    if args.apply_only:
        for key in args.apply_only:
            apply_reply(key, args.tag, (FIXUPS / f"{key}__{args.tag}.reply.txt").read_text(encoding="utf-8"))
        return
    reqs = []
    for key in args.dafim:
        if not notes_path(key, args.tag).exists():
            sys.exit(f"no notes: {notes_path(key, args.tag).relative_to(HERE)}")
        reqs.append(build_request(key, args.tag, args.effort))
    for r in reqs:
        n = len(json.loads(notes_path(r['custom_id'].split('__')[0], args.tag).read_text())["notes"])
        print(f"  {r['custom_id']}: {n} notes, user prompt {len(r['params']['messages'][0]['content']):,} chars")
    if args.dry_run or not reqs:
        return
    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=reqs)
    print(f"submitted {batch.id} ({len(reqs)} requests)", flush=True)
    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        time.sleep(60)
    usage = []
    for r in client.messages.batches.results(batch.id):
        key, tag, _ = r.custom_id.split("__")
        if r.result.type != "succeeded":
            print(f"  {r.custom_id}: {r.result.type}")
            continue
        msg = r.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        u = msg.usage
        usage.append({"id": r.custom_id, "stop": msg.stop_reason, "in": u.input_tokens,
                      "cache_read": u.cache_read_input_tokens, "cache_write": u.cache_creation_input_tokens,
                      "out": u.output_tokens})
        (FIXUPS / f"{key}__{tag}.reply.txt").write_text(text, encoding="utf-8")
        apply_reply(key, tag, text)
    (FIXUPS / "last_fixup_usage.json").write_text(json.dumps(usage, indent=1))


if __name__ == "__main__":
    main()
