#!/usr/bin/env python3
"""Key conceptual terms (glossary) pilot: one Batch API request per daf per model.

Reads the daf's Sefaria text (Hebrew + English) and an existing study outline
(outline/results/<key>/04_outline_<outline-model>.json), and asks for the 3-8 legal
categories and principles the sugya turns on, each with a general definition, one line on
how this daf uses it, the spellings that appear in the outline (for highlighting), and the
outline sections where it matters.

The pilot runs as its own pass so it can reuse the outlines already generated. In production
the same instructions fold into outline_pass.py's call (one request per daf).

    venv/bin/python -u key_terms_pass.py --dafim gittin_18 shabbat_38 ... --dry-run
    venv/bin/python -u key_terms_pass.py --dafim ... --models claude-sonnet-5 claude-opus-5-5

Writes outline/results/<key>/05_key_terms_<model>.json (+ .raw.txt) and prints local checks
(section ids exist, aliases occur in the outline, Hebrew occurs in the daf text). No API call
happens with --dry-run.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from outline_pass import MODEL_TAGS, RESULTS, STATE_DIR, parse_outline, parse_spec

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
EXAMPLE = HERE / "outline" / "key_terms_example_chagigah_6.json"
EXAMPLE_OUTLINE = HERE / "outline" / "example_chagigah_6.json"
POLL_INTERVAL = 60

SYSTEM_PROMPT = """You are choosing the key conceptual terms for one daf of Talmud in the AnyDaf study app. They appear as a short glossary at the top of the daf's study outline, and are highlighted in the outline's bullets; tapping one shows its definition.

## What counts as a key term
A key term is a legal category, institution or principle that the sugya turns on: a learner who doesn't grasp it can't follow the argument. Examples: chatzer (a person's property acquiring for him), yad (a legal "hand" that acquires), shaliach (agency), ona'ah (overcharging), garuf ve'katum, mitztamek ve'yafeh lo, chinukh, olat re'iyah.
- NOT a vocabulary list. Leave out hard Aramaic words and Gemara idioms (teiku, kashya, ibaya lehu, mai beinaihu), people, places, books, and generic words any learner knows (mitzvah, Shabbat, Torah).
- NOT every concept mentioned. A term that appears once in passing isn't key. Prefer the terms the discussion is built on, and the distinctions that recur across sections.
- 3-8 terms per daf. Fewer is fine for a short or aggadic daf; an aggadic daf may have none worth listing, and then the list is empty.
- One entry per sense. If the daf uses a word in one specific legal sense (chatzer as a means of acquisition, not a courtyard), the entry is that sense, and "sense" says which.
- Opposites and contrasting cases are separate entries: *mitztamek ve'yafeh lo* (improves as it shrivels) and *mitztamek ve'ra lo* (deteriorates as it shrivels) are two terms, as are *chatzer ha'mishtameret* and *chatzer she'einah mishtameret*. Never list one side of a pair as another spelling of the other, or a reader who taps it gets the opposite definition. If the daf only ever names the pair together, one entry may cover both, but then "term" names both sides and "definition" explains each.

## Fields
- "term": the standard transliteration, lower case except proper nouns, e.g. "olat re'iyah", "kinyan chatzer".
- "hebrew": the term in Hebrew without nikud, as it appears in the text when it does.
- "sense": a few words naming the specific sense, e.g. "acquisition through one's property". This keeps entries with the same name apart across Shas.
- "definition": 1-2 sentences defining the term in general, not tied to this daf, so that the same definition would serve on any daf that uses this sense. Plain English; state only what is uncontroversial and standard. No citations.
- "on_this_daf": one sentence on how this daf uses or debates the term. Follow the Gemara text; don't repeat the definition.
- "aliases": the exact spellings of the term that appear in the outline's headings, gists and bullets (without the asterisks), longest first, so the app can highlight them: transliterated forms only (with and without a prefix, singular and plural), never an English translation. Include only strings that actually occur in the outline. The outline writes every key term in the original (see "Hebrew and Aramaic words"), so the term's transliteration is always among them.
- "sections": ids of the outline sections where the term matters, in outline order.

## Output
Return only a JSON object, no prose before or after:
{"daf": "<name>", "key_terms": [ {"term", "hebrew", "sense", "definition", "on_this_daf", "aliases", "sections"} ]}

## Worked example (Chagigah 6)
The outline it was drawn from (headings, gists and bullets):
{EXAMPLE_OUTLINE}

The key terms:
{EXAMPLE}
"""


def sefaria_bilingual(path: Path) -> list[tuple[str, str, str]]:
    """[(label, hebrew, english)] for each item; label like '6a.3'."""
    if not path.exists():
        return []
    items, amud, label, heb = [], "", None, ""
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+\S.*?(\d+[ab])\s*$", line)
        if m:
            amud = m.group(1)
            continue
        m = re.match(r"^\*\*(\d+)\.\*\*\s*$", line)
        if m:
            label, heb = f"{amud}.{m.group(1)}", ""
            continue
        if line.startswith("*Hebrew/Aramaic:*"):
            heb = line[len("*Hebrew/Aramaic:*"):].strip()
        elif line.startswith("*Translation:*") and label:
            items.append((label, heb, line[len("*Translation:*"):].strip().replace("**", "")))
            label = None
    return items


def compact_outline(outline: dict) -> str:
    """Headings, gists and bullets only (no charts or SVG), indented by depth."""
    lines = []

    def walk(n, depth):
        pad = "  " * depth
        lines.append(f"{pad}[{n.get('id')}] {n.get('title', '')}")
        if n.get("gist"):
            lines.append(f"{pad}  gist: {n['gist']}")
        for b in n.get("bullets", []):
            lines.append(f"{pad}  - {b['text'] if isinstance(b, dict) else b}")
        for c in n.get("children", []):
            walk(c, depth + 1)

    for s in outline.get("sections", []):
        walk(s, 0)
    return "\n".join(lines)


def system_text() -> str:
    ex_outline = compact_outline(json.loads(EXAMPLE_OUTLINE.read_text(encoding="utf-8")))
    return (SYSTEM_PROMPT.replace("{EXAMPLE_OUTLINE}", ex_outline)
            .replace("{EXAMPLE}", EXAMPLE.read_text(encoding="utf-8").strip()))


def outline_for(key: str, outline_tag: str) -> dict:
    p = RESULTS / key / f"04_outline_{outline_tag}.json"
    if not p.exists():
        sys.exit(f"no outline {p.relative_to(HERE)}")
    return json.loads(p.read_text(encoding="utf-8"))


def build_user_prompt(key: str, d: Path, outline: dict) -> str:
    text = "\n".join(f"[{lab}] {heb}\n       {eng}" for lab, heb, eng in sefaria_bilingual(d / "sefaria.md"))
    return (f"# Daf: {key}\n\n## Study outline\n{compact_outline(outline)}\n\n"
            f"## Gemara text (Hebrew/Aramaic, then Sefaria's English)\n{text}\n\n"
            "Now produce the key terms JSON for this daf.")


def build_request(spec: str, model: str, outline_tag: str, effort: str) -> dict:
    key, d, _ = parse_spec(spec)
    return {
        "custom_id": f"{key}__{MODEL_TAGS[model]}",
        "params": {
            "model": model,
            "max_tokens": 16000,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
            "system": [{"type": "text", "text": system_text(), "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": build_user_prompt(key, d, outline_for(key, outline_tag))}],
        },
    }


# ---------- local checks (free) ----------

def strip_nikud(s: str) -> str:
    return re.sub(r"[֑-ׇ]", "", s)


def heb_skeleton(s: str) -> str:
    """Nikud-free, without the matres lectionis that spelling varies on (ו, י) or punctuation."""
    return re.sub(r"[^א-ת]", "", strip_nikud(s)).replace("ו", "").replace("י", "")


def outline_text(outline: dict) -> str:
    parts = []

    def walk(n):
        parts.extend([n.get("title", ""), n.get("gist", "")])
        parts.extend(b["text"] if isinstance(b, dict) else b for b in n.get("bullets", []))
        for c in n.get("children", []):
            walk(c)

    for s in outline.get("sections", []):
        walk(s)
    return " ".join(parts).replace("*", "").lower()


def section_ids(outline: dict) -> list[str]:
    ids = []

    def walk(n):
        ids.append(n.get("id"))
        for c in n.get("children", []):
            walk(c)

    for s in outline.get("sections", []):
        walk(s)
    return ids


def check_terms(terms: dict, outline: dict, d: Path) -> list[str]:
    probs = []
    kt = terms.get("key_terms", [])
    if len(kt) > 8:
        probs.append(f"{len(kt)} terms (limit 8)")
    ids, text = section_ids(outline), outline_text(outline)
    daf_heb = heb_skeleton(" ".join(h for _, h, _ in sefaria_bilingual(d / "sefaria.md")))
    for t in kt:
        name = t.get("term", "?")
        for f in ("term", "hebrew", "sense", "definition", "on_this_daf", "aliases", "sections"):
            if not t.get(f):
                probs.append(f"{name}: missing {f}")
        bad = [s for s in t.get("sections", []) if s not in ids]
        if bad:
            probs.append(f"{name}: unknown sections {bad}")
        absent = [a for a in t.get("aliases", []) if a.lower() not in text]
        if absent:
            probs.append(f"{name}: aliases not in outline {absent}")
        if t.get("hebrew") and heb_skeleton(t["hebrew"]) not in daf_heb:
            probs.append(f"{name}: Hebrew '{t['hebrew']}' not found in the daf text (may be fine)")
    return probs


def harvest(client, batch_id, usage_log, src, outline_tag):
    for r in client.messages.batches.results(batch_id):
        key, tag = r.custom_id.split("__")
        outdir = RESULTS / key
        if r.result.type != "succeeded":
            print(f"  {r.custom_id}: {r.result.type}")
            continue
        msg = r.result.message
        text = next((b.text for b in msg.content if b.type == "text"), "")
        u = msg.usage
        usage_log.append({"id": r.custom_id, "model": msg.model, "stop": msg.stop_reason,
                          "in": u.input_tokens, "cache_read": u.cache_read_input_tokens,
                          "cache_write": u.cache_creation_input_tokens, "out": u.output_tokens})
        if msg.stop_reason != "end_turn":
            print(f"  {r.custom_id}: stop_reason={msg.stop_reason}")
        (outdir / f"05_key_terms_{tag}.raw.txt").write_text(text, encoding="utf-8")
        try:
            terms = parse_outline(text)
            out = outdir / f"05_key_terms_{tag}.json"
            out.write_text(json.dumps(terms, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  wrote {out.relative_to(HERE)} ({len(terms.get('key_terms', []))} terms)")
            for p in check_terms(terms, outline_for(key, outline_tag), src[key]):
                print(f"    check: {p}")
        except Exception as e:
            print(f"  {r.custom_id}: could not parse JSON ({e}); raw text saved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--models", nargs="+", default=["claude-sonnet-5", "claude-opus-5-5"])
    ap.add_argument("--outline", default="opus55", help="which model's outline to draw terms from")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-only", action="store_true", help="re-run local checks on saved results")
    args = ap.parse_args()

    src = {}
    for spec in args.dafim:
        key, d, _ = parse_spec(spec)
        if d.name == "chagigah_6":
            sys.exit("chagigah_6 is the worked example; leave it out of the run")
        outline_for(key, args.outline)
        src[key] = d

    if args.check_only:
        for key, d in src.items():
            for m in args.models:
                p = RESULTS / key / f"05_key_terms_{MODEL_TAGS[m]}.json"
                if p.exists():
                    print(f"{key} {MODEL_TAGS[m]}:")
                    for prob in check_terms(json.loads(p.read_text()), outline_for(key, args.outline), d):
                        print(f"    {prob}")
        return

    print(f"{len(src)} dafim x {len(args.models)} models = {len(src) * len(args.models)} requests; "
          f"system prompt {len(system_text()):,} chars (cached); effort {args.effort}")
    for spec in args.dafim:
        key, d, _ = parse_spec(spec)
        print(f"  {key:24s} user prompt {len(build_user_prompt(key, d, outline_for(key, args.outline))):,} chars")
    if args.dry_run:
        return

    client = anthropic.Anthropic()
    batches = {}
    for model in args.models:
        state = STATE_DIR / f".key_terms_batch_{MODEL_TAGS[model]}.json"
        if state.exists():
            batches[model] = json.loads(state.read_text())["batch_id"]
            print(f"Resuming {model} batch {batches[model]}")
        else:
            reqs = [build_request(s, model, args.outline, args.effort) for s in args.dafim]
            batches[model] = client.messages.batches.create(requests=reqs).id
            state.write_text(json.dumps({"batch_id": batches[model]}))
            print(f"Submitted {model} batch {batches[model]} ({len(reqs)} requests)")

    usage_log, pending = [], dict(batches)
    while pending:
        for model, bid in list(pending.items()):
            b = client.messages.batches.retrieve(bid)
            c = b.request_counts
            print(f"  {MODEL_TAGS[model]:7s} {b.processing_status}: succeeded={c.succeeded} "
                  f"processing={c.processing} errored={c.errored}")
            if b.processing_status == "ended":
                harvest(client, bid, usage_log, src, args.outline)
                (STATE_DIR / f".key_terms_batch_{MODEL_TAGS[model]}.json").unlink(missing_ok=True)
                del pending[model]
        (STATE_DIR / "last_key_terms_usage.json").write_text(json.dumps(usage_log, indent=1))
        if pending:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
