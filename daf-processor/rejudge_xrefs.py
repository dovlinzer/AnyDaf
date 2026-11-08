#!/usr/bin/env python3
"""Judge again the Rambam / Shulchan Arukh numbers still in doubt after recheck_xrefs.py, now showing the
model the Ein Mishpat note: its letter, the Gemara words the letter marks, and the note's full text.
CALLS THE ANTHROPIC API (Batch). Run only with the author's authorization for that run.

Three sources of requests, merged so each reference is asked once:
  rechecked   the model's earlier "B" verdicts that recheck_xrefs.py could not explain away
              (recheck: wikisource has the alt, phrase: *, no marker, no note)
  uncovered   "B" verdicts in tractates Wikisource has no Ein Mishpat for, where the suggested place is
              not already linked to the same line (so it isn't just the line's other note)
  disagree    disagreements.json: Sefaria's number differs from Wikisource's note by a possible misreading

A is always Sefaria's number, B the other reading.

    venv/bin/python rejudge_xrefs.py build      # -> outline/xref_check/rejudge_requests.jsonl (+ cost estimate)
    venv/bin/python rejudge_xrefs.py submit     # Batch API; resumable (state in .rejudge_batch.json)
    venv/bin/python rejudge_xrefs.py harvest    # -> rejudged.json, report_rejudged.md
"""
from __future__ import annotations

import collections
import json
import re
import sys

import anthropic

from check_xrefs import RESULT
from judge_xrefs import MODEL, amud_segs, clean, estimate, passage, request
from recheck_xrefs import key_of

DELTA = "--delta" in sys.argv   # judge only what changed since the full run (files *_delta)
_SFX = "_delta" if DELTA else ""
REQS = RESULT / f"rejudge_requests{_SFX}.jsonl"
META = RESULT / f"rejudge_meta{_SFX}.json"
STATE = RESULT / f".rejudge_batch{_SFX}.json"
OUT = RESULT / "rejudged.json"
REPORT = RESULT / "report_rejudged.md"
LINKS = RESULT.parent.parent / "xrefs"
KEEP = {"wikisource has the alt", "phrase: flag", "phrase: ok", "phrase: weak", "no marker", "no note"}

SYSTEM = """You check Ein Mishpat references printed in the margin of the Vilna Talmud: where a Gemara ruling is codified in Rambam's Mishneh Torah or the Shulchan Arukh. Each note carries a Hebrew letter, and the same letter is printed in the Gemara before the word where the ruling begins. A line of Gemara often has two or more notes, each for a different ruling, so a passage that fits the line's other note is not evidence against this one.

The digital copies were transcribed from the printed page, and Rashi-script numerals are easy to misread (ח as א, ו as ז, ה as ח, ד as ר, ט as ש), and some numbers are off by one or two. Two numbers for one reference are in question. Judge by content: which of the two codifies the ruling stated at the Gemara words this note marks. Rambam and the Shulchan Arukh restate the Gemara's law in their own words.

Reply with one JSON object and nothing else:
{"verdict": "...", "reason": "one short sentence, in English, naming what in the texts decides it"}"""

TASK = """Verdicts:
- "A": A is what this note refers to; B is not (B may belong to another note on the line).
- "B": B is what this note refers to and A is not: the number should be B.
- "both": both codify this ruling (e.g. the note cites both); A is acceptable.
- "neither": neither codifies the ruling at the marked words.
- "unsure": the texts don't let you decide."""


def other_refs(tractate, amud, line, cache={}):
    """Every Rambam / Shulchan Arukh reference Sefaria links to this line."""
    if tractate not in cache:
        p = LINKS / f"{tractate}.json"
        cache[tractate] = json.loads(p.read_text())["amudim"] if p.exists() else {}
    return [r["ref"] for r in (cache[tractate].get(amud) or {}).get(str(line), [])
            if r.get("k") == "em" and r.get("work") in ("rambam", "sa")]


def gem(tractate, amud, lines):
    segs = amud_segs(tractate, amud)
    lo, hi = max(1, min(lines)), min(len(segs), max(lines))
    return "\n".join(f"[{amud}:{n}]\nGemara: {clean(segs[n - 1].get('he'))}\n"
                     f"Steinsaltz: {clean(segs[n - 1].get('hx'))}\nEnglish: {clean(segs[n - 1].get('en'))}"
                     for n in range(lo, hi + 1))


def items():
    """(key, item) for every reference to ask about; key = (tractate, amud, line, Sefaria's ref)."""
    out = {}
    for d in json.loads((RESULT / "disagreements.json").read_text()):
        k = (d["tractate"], d["amud"], d["line"], d["sefaria"])
        out[k] = {"source": ["disagree"], "tractate": d["tractate"], "amud": d["amud"], "line": d["line"],
                  "work": d["work"], "a": d["sefaria"], "b": d["wikisource"],
                  "notes": [{"letter": d["letter"], "text": d["note"], "word": d["word"],
                             "line": d["marker_line"], "phrase": d["phrase"]}], "favours": d["favours"]}
    for x in json.loads((RESULT / "rechecked.json").read_text()):
        if x["kind"] != "flag" or x["judge"]["verdict"] != "B":
            continue
        if x["recheck"] == "no wikisource":
            if x["alt"] in other_refs(x["tractate"], x["amud"], x["line"]):
                continue
            src = "uncovered"
        elif x["recheck"] in KEEP:
            src = "rechecked"
        else:
            continue
        k = (x["tractate"], x["amud"], x["line"], x["ref"])
        if k in out and out[k]["b"] == x["alt"]:
            out[k]["source"].append(src)
            out[k]["first_reason"] = x["judge"].get("reason")
            continue
        notes = x.get("notes") or x.get("alt_notes") or []
        out[k] = {"source": [src], "tractate": x["tractate"], "amud": x["amud"], "line": x["line"],
                  "work": x["work"], "a": x["ref"], "b": x["alt"], "how": x.get("how"),
                  "notes": [{k2: n.get(k2) for k2 in ("letter", "text", "word", "line", "phrase")} for n in notes],
                  "recheck": x["recheck"], "first_reason": x["judge"].get("reason")}
    return out


def prompt(it):
    lines = {it["line"]} | {n["line"] for n in it["notes"] if n.get("line")}
    g = gem(it["tractate"], it["amud"], lines)
    near = " ".join(n.get("phrase") or "" for n in it["notes"]) or g
    a, b = passage(it["a"], near), passage(it["b"], near)
    if not b:
        return None
    parts = [f"Gemara, {it['tractate']}:\n{g}"]
    if it["notes"]:
        for n in it["notes"]:
            parts.append(f"Ein Mishpat note {n['letter']} (Wikisource's transcription): {n['text']}\n"
                         f"Its letter is printed before the words: {n.get('word') or '(not marked)'}"
                         + (f" (line {it['amud']}:{n['line']})" if n.get("line") else "")
                         + (f"\nThe Gemara from those words on: {n['phrase']}" if n.get("phrase") else ""))
    else:
        parts.append("(No transcription of this tractate's Ein Mishpat notes is available, so the note's letter "
                     "and its words are unknown.)")
    others = [r for r in other_refs(it["tractate"], it["amud"], it["line"]) if r not in (it["a"], it["b"])]
    if others:
        parts.append("Other Rambam / Shulchan Arukh references linked to this line: " + "; ".join(others))
    parts.append(f"Passage A ({it['a']}, the number in Sefaria's data):\n"
                 f"{a or '(this passage does not exist in Sefaria’s text)'}")
    parts.append(f"Passage B ({it['b']}, the other reading):\n{b}")
    return "\n\n".join(parts) + "\n\n" + TASK


def key(x):
    return (x["tractate"], x["amud"], x["line"], x["a"])


def changed(old, it):
    return [n.get("line") for n in old["notes"]] != [n.get("line") for n in it["notes"]] or old["b"] != it["b"]


def todo():
    """In --delta mode, only what the fixed notes newly put in question or whose note changed."""
    live = sorted(items().items())
    if not DELTA:
        return live
    old = {key(x): x for x in json.loads(OUT.read_text())}
    return [(k, it) for k, it in live if k not in old or changed(old[k], it)]


def build():
    reqs, meta, skipped = [], {}, collections.Counter()
    for i, (k, it) in enumerate(todo()):
        p = prompt(it)
        if not p:
            skipped["no text for B"] += 1
            continue
        cid = f"{'rd' if DELTA else 're'}_{i}"
        reqs.append(request(cid, p))
        meta[cid] = {"cid": cid, **it}
    reqs = [{**r, "params": {**r["params"], "system": SYSTEM}} for r in reqs]
    REQS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
    META.write_text(json.dumps(meta, ensure_ascii=False))
    c = collections.Counter("+".join(m["source"]) for m in meta.values())
    print(f"{len(reqs)} requests {dict(c)}; skipped {dict(skipped)}")
    estimate(reqs)


def submit():
    from fix_pass2_gaps import submit_and_wait
    reqs = [json.loads(l) for l in REQS.read_text().splitlines()]
    batch = submit_and_wait(anthropic.Anthropic(), reqs, STATE)
    STATE.write_text(json.dumps({"batch_id": batch.id}))
    print(f"batch {batch.id}: {batch.request_counts}")


def harvest():
    client = anthropic.Anthropic()
    meta = json.loads(META.read_text())
    bid = json.loads(STATE.read_text())["batch_id"]
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
                # unescaped quotes in the reason (the marked Hebrew words) break the JSON; the verdict still reads
                v = re.search(r'"verdict"\s*:\s*"(\w+)"', text)
                r2 = re.search(r'"reason"\s*:\s*"(.*)"\s*\}', text, re.S)
                m["judge"] = {"verdict": v.group(1) if v else "unparsed",
                              "reason": (r2.group(1) if r2 else text)[:300]}
        out.append(m)
    if DELTA:   # merge into the full run: replace changed references, add new ones
        new = {key(x): x for x in out}
        prev = json.loads(OUT.read_text())
        merged = [new.pop(key(x), x) for x in prev] + list(new.values())
        OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    else:
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    cost = (usage["in"] * 1.0 + usage["out"] * 5.0) / 1e6
    c = collections.Counter(("+".join(x["source"]), x["work"], x["judge"]["verdict"]) for x in out)
    lines = ["# Rambam / Shulchan Arukh numbers judged again with the Ein Mishpat note", "",
             f"Batch {bid}, {MODEL}. {usage['in']:,} input + {usage['out']:,} output tokens, ${cost:.2f}.", "",
             "| Source | Work | Verdict | References |", "|---|---|---|---:|"]
    lines += [f"| {s} | {w} | {v} | {n} |" for (s, w, v), n in sorted(c.items())]
    (RESULT / "report_rejudged_delta.md" if DELTA else REPORT).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    {"build": build, "submit": submit, "harvest": harvest}[sys.argv[1]]()
