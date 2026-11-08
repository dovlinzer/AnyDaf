#!/usr/bin/env python3
"""Judge the cross-references check_xrefs.py could not settle, with a model reading the texts.
CALLS THE ANTHROPIC API (Batch). Run only with the author's authorization for that run.

Two kinds of request:
  flag  -- check_xrefs.py found another passage that fits the Gemara line much better than the one
           Sefaria cites (a misread numeral, a numbering off by one, the wrong amud). The model reads
           the line beside both passages and says which one the line points to.
  weak  -- a seeded sample of references whose word overlap was too low to confirm. The model says
           whether the cited passage matches the line, to measure how many errors hide there.

    venv/bin/python judge_xrefs.py build [--weak 200]   # requests -> outline/xref_check/judge_requests.jsonl
    venv/bin/python judge_xrefs.py submit               # Batch API; resumable (state in .judge_batch.json)
    venv/bin/python judge_xrefs.py harvest              # -> judged.json, report_judged.md
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from build_xrefs import parse_cite
from check_xrefs import RESULT, flat, node, split_ref, words

load_dotenv(Path(__file__).parent / ".env", override=True)
HERE = Path(__file__).parent
MODEL = "claude-sonnet-5-5"
JUDGED = RESULT / "judged.json"
MAX_CHARS = 1800      # a Tur siman or Semag mitzvah can run for pages
LONG_WINDOW = 2400    # ... so a long unit is shown at the stretch that best matches the Gemara line
NIKUD = re.compile(r"[֑-ׇ]")
TAGS = re.compile(r"<[^>]+>")

SYSTEM = """You check cross-references printed in the margins of the Vilna Talmud: Ein Mishpat (where the ruling is codified in Rambam, Semag, Tur, Shulchan Arukh), Mesoret HaShas (parallel passages in the Talmud, Mishnah or Tosefta) and verse citations. The digital copy was transcribed from the printed page, and Rashi-script numerals are easy to misread (ח as א, ו as ז, ה as ח, ד as ר), and some numbers are off by one or two because editions number differently.

You are given one line of Gemara (Aramaic/Hebrew, with Steinsaltz's Hebrew explanation and an English translation) and the passage or passages a reference could name. Judge by content: the codified ruling, parallel passage or verse that this Gemara line actually discusses or quotes. A Rambam or Shulchan Arukh ruling restates the Gemara's law in its own words; a parallel Talmud passage repeats the same statement or story elsewhere; a verse citation names the verse the line quotes.

Reply with one JSON object and nothing else:
{"verdict": "...", "reason": "one short sentence, in English, naming what in the texts decides it"}"""

FLAG_TASK = """The margin cites passage A. Passage B is the reading the reference would name {how}.

Verdicts:
- "A": A is what the line refers to (B is unrelated, or less fitting).
- "B": B is what the line refers to and A is not: the reference is wrong and should be B.
- "both": both fit (e.g. a quote spanning two verses, or two rulings both drawn from this line); A is acceptable.
- "neither": neither fits the line.
- "unsure": the texts don't let you decide."""

WEAK_TASK = """Verdicts:
- "yes": the passage is what the line refers to.
- "partly": related to the line's topic, but not clearly the ruling/passage this line gives.
- "no": the passage has nothing to do with the line; the reference looks wrong.
- "unsure": the texts don't let you decide."""


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", NIKUD.sub("", TAGS.sub("", t or ""))).strip()


_bavli = {}


def amud_segs(tractate: str, amud: str):
    if tractate not in _bavli:
        p = HERE / "daf_text" / f"{tractate}.json"
        _bavli[tractate] = json.loads(p.read_text())["amudim"] if p.exists() else {}
    return (_bavli[tractate].get(amud) or {}).get("segments") or []


def gemara(tractate, amud, line, to=None) -> str:
    segs = amud_segs(tractate, amud)
    end = line
    if to and ":" in to and to.split(":")[0] == amud:
        end = int(to.split(":")[1])
    elif to and str(to).isdigit():
        end = int(to)
    out = []
    for n in range(max(1, line), min(len(segs), max(line, end)) + 1):
        s = segs[n - 1]
        out.append(f"[{amud}:{n}]\nGemara: {clean(s.get('he'))}\nSteinsaltz: {clean(s.get('hx'))}\n"
                   f"English: {clean(s.get('en'))}")
    return "\n".join(out)


def best_window(text: str, near: str) -> str:
    """The LONG_WINDOW-character stretch of text sharing the most words with the Gemara line."""
    target, best = words(near), (-1, 0)
    for start in range(0, max(1, len(text) - LONG_WINDOW + 600), 600):
        n = len(words(text[start:start + LONG_WINDOW]) & target)
        best = max(best, (n, -start))
    start = -best[1]
    return ("… " if start else "") + text[start:start + LONG_WINDOW] + (" …" if start + LONG_WINDOW < len(text) else "")


def passage(ref: str, near: str | None = None) -> str | None:
    """The text a reference names: a Bavli line with its neighbours, or a book's unit (a long one cut
    to the stretch that best matches `near`, the Gemara line, when given)."""
    p = parse_cite(ref) if re.match(r"^[A-Z][a-z' ]+ \d+[ab]", ref) else None
    if p:
        tr, amud, line, _ = p
        segs = amud_segs(tr, amud)
        if not segs:
            return None
        lo, hi = (max(1, line - 1), min(len(segs), line + 1)) if line else (1, len(segs))
        return " / ".join(clean(segs[i - 1].get("he")) for i in range(lo, hi + 1))[:MAX_CHARS]
    title, nums = split_ref(ref)
    t = node(title, nums)
    if t in (None, "missing book"):
        return None
    text = clean(flat(t))
    if near and len(text) > MAX_CHARS:
        return best_window(text, near)
    return text[:MAX_CHARS] or None


def request(cid: str, prompt: str) -> dict:
    return {"custom_id": cid,
            "params": {"model": MODEL, "max_tokens": 4000, "thinking": {"type": "adaptive"},
                       "output_config": {"effort": "low"}, "system": SYSTEM,
                       "messages": [{"role": "user", "content": prompt}]}}


def files(tag: str):
    sfx = f"_{tag}" if tag else ""
    return (RESULT / f"judge_requests{sfx}.jsonl", RESULT / f"judge_meta{sfx}.json",
            RESULT / f".judge_batch{sfx}.json")


def build(n_weak: int, works: set | None = None, tag: str = ""):
    """works: rebuild only references to these works (e.g. smag, tur), keeping their request ids."""
    flags = json.loads((RESULT / "flags.json").read_text())
    weak = json.loads((RESULT / "weak.json").read_text())
    reqs, meta, skipped = [], {}, collections.Counter()
    for i, f in enumerate(flags):
        if works and f.get("work") not in works:
            continue
        g = gemara(f["tractate"], f["amud"], f["line"], f.get("to")) if f["line"] else ""
        a, b = passage(f["ref"], g), passage(f["alt"], g) if f.get("alt") else None
        if not g or not b:
            skipped["no alternative" if g else "whole-amud link"] += 1
            continue
        a_text = a if a else "(this passage does not exist in Sefaria's text)"
        prompt = (f"Gemara, {f['tractate']}:\n{g}\n\nPassage A ({f['ref']}):\n{a_text}\n\n"
                  f"Passage B ({f['alt']}):\n{b}\n\n" + FLAG_TASK.format(how=f"if {f['how']}"))
        cid = f"flag_{i}"
        reqs.append(request(cid, prompt))
        meta[cid] = {"kind": "flag", "cid": cid, **f}
    random.seed(20261102)
    for i, w in enumerate(random.sample(weak, min(n_weak, len(weak)))):
        if works and w.get("work") not in works:
            continue
        g = gemara(w["tractate"], w["amud"], w["line"], w.get("to")) if w["line"] else ""
        a = passage(w["ref"], g)
        if not g or not a:
            skipped["weak: no text"] += 1
            continue
        prompt = f"Gemara, {w['tractate']}:\n{g}\n\nCited passage ({w['ref']}):\n{a}\n\n{WEAK_TASK}"
        cid = f"weak_{i}"
        reqs.append(request(cid, prompt))
        meta[cid] = {"kind": "weak", "cid": cid, **w}
    req_file, meta_file, _ = files(tag)
    req_file.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
    meta_file.write_text(json.dumps(meta, ensure_ascii=False))
    print(f"{len(reqs)} requests ({sum(m['kind'] == 'flag' for m in meta.values())} flags, "
          f"{sum(m['kind'] == 'weak' for m in meta.values())} weak); skipped {dict(skipped)}")
    estimate(reqs)


def estimate(reqs):
    """Input tokens counted exactly on a sample (count_tokens is free); output is an assumption."""
    client = anthropic.Anthropic()
    random.seed(1)
    sample = random.sample(reqs, min(40, len(reqs)))
    tok = [client.messages.count_tokens(model=MODEL, system=r["params"]["system"],
                                        messages=r["params"]["messages"]).input_tokens for r in sample]
    avg_in = sum(tok) / len(tok)
    out_guess = 700   # low effort: brief thinking plus a one-line JSON answer
    cost = len(reqs) * (avg_in * 1.0 + out_guess * 5.0) / 1e6   # Sonnet 5.5 batch: $1 in, $5 out per MTok
    print(f"input ~{avg_in:,.0f} tokens/request (measured on {len(sample)}); "
          f"est. ${cost:,.2f} at ~{out_guess} output tokens/request")


def submit(tag: str = ""):
    from fix_pass2_gaps import submit_and_wait
    req_file, _, state = files(tag)
    reqs = [json.loads(l) for l in req_file.read_text().splitlines()]
    batch = submit_and_wait(anthropic.Anthropic(), reqs, state)
    state.write_text(json.dumps({"batch_id": batch.id}))   # submit_and_wait removes it when done
    print(f"batch {batch.id}: {batch.request_counts}")


def same(x):
    return (x["kind"], x["tractate"], x["amud"], x["line"], x["ref"], x.get("alt"))


def harvest(tag: str = ""):
    """A tagged rerun replaces its references' verdicts in judged.json; the report covers them all."""
    client = anthropic.Anthropic()
    _, meta_file, state = files(tag)
    meta = json.loads(meta_file.read_text())
    bid = json.loads(state.read_text())["batch_id"]
    out, usage = [], collections.Counter()
    for r in client.messages.batches.results(bid):
        m = dict(meta[r.custom_id])
        if r.result.type != "succeeded":
            m["judge"] = {"verdict": "error", "reason": r.result.type}
        else:
            msg = r.result.message
            usage["in"] += msg.usage.input_tokens
            usage["out"] += msg.usage.output_tokens
            text = "".join(b.text for b in msg.content if b.type == "text")
            j = re.search(r"\{.*\}", text, re.S)
            try:
                m["judge"] = json.loads(j.group(0))
            except (AttributeError, json.JSONDecodeError):
                m["judge"] = {"verdict": "unparsed", "reason": text[:300]}
        out.append(m)
    if tag:
        new = {same(x): x for x in out}
        out = [new.get(same(x), x) for x in json.loads(JUDGED.read_text())]
    JUDGED.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    cost = (usage["in"] * 1.0 + usage["out"] * 5.0) / 1e6
    lines = ["# Cross-references judged by the model", "",
             f"Batch {bid}{f' ({tag})' if tag else ''}, {MODEL}. {usage['in']:,} input + {usage['out']:,} output tokens, ${cost:.2f}.", ""]
    for kind in ("flag", "weak"):
        rows = [x for x in out if x["kind"] == kind]
        lines += [f"## {kind} ({len(rows)})", "", "| Layer | " + " | ".join(
            v := sorted({x['judge']['verdict'] for x in rows})) + " |", "|---|" + "---:|" * len(v)]
        by = collections.defaultdict(collections.Counter)
        for x in rows:
            by[x["layer"]][x["judge"]["verdict"]] += 1
        lines += [f"| {k} | " + " | ".join(str(c[x]) for x in v) + " |" for k, c in sorted(by.items())] + [""]
    (RESULT / "report_judged.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "submit", "harvest"])
    ap.add_argument("--weak", type=int, default=200)
    ap.add_argument("--works", help="rebuild only these works, e.g. smag,tur (use with --tag)")
    ap.add_argument("--tag", default="", help="a rerun's name; its files sit beside the first run's")
    a = ap.parse_args()
    works = set(a.works.split(",")) if a.works else None
    {"build": lambda: build(a.weak, works, a.tag), "submit": lambda: submit(a.tag),
     "harvest": lambda: harvest(a.tag)}[a.cmd]()
