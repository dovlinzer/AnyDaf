#!/usr/bin/env python3
"""Pilot, step 2 of the word glossary: choose the right Jastrow entry for each Gemara word.

Step 1 (word_gloss_pilot.py) gave each word a dictionary form and an English gloss. A spelling often names several
Jastrow entries (אָמַר I "to join" / אֲמַר "to say"; כֹּל "all" / כּוּלָה "a measure"), and neither the form nor
matching English words picks among them reliably. So here the model sees the actual candidates (headword + the
opening of each definition, from Sefaria's /api/words, cached in outline/word_gloss/jastrow_cache.json) and
chooses one.

One request per amud and model; each distinct (word, gloss) in an amud is asked once. Both models get the same
candidate lists (the word's own forms plus both models' step-1 forms), so their choices can be compared.

    venv/bin/python word_entry_pilot.py build | submit | harvest   # -> outline/word_gloss/entries_<model>.json
"""
from __future__ import annotations

import argparse
import json
import re
import time

import anthropic

from word_gloss_pilot import MODELS, OUT, PILOT, amud_lines, clean

CACHE = OUT / "jastrow_cache.json"
NIK = re.compile(r"[֑-ׇ\"'׳״]")
FIN = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
MAX_CANDS = 10
SNIPPET = 110


def plain(w):
    return NIK.sub("", w or "")


def fin(w):
    return w[:-1] + FIN[w[-1]] if len(w) > 1 and w[-1] in FIN else w


def wforms(w):
    out = [w]
    for k in (1, 2):
        if len(w) - k >= 2 and all(c in "ודהבלמשכ" for c in w[:k]):
            out.append(fin(w[k:]))
    return out


SYSTEM = """You link each word of a Babylonian Talmud passage to the right entry in Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi, for English-speaking learners who tap a word to see its entry.

You get the passage (Aramaic/Hebrew with the William Davidson English), then a list of items. Each item is a word as it appears in a given line, with the English gloss already decided for it there, and numbered candidate Jastrow entries (headword, then the opening of the definition; Jastrow often has several entries with the same spelling, numbered I, II, III).

For each item choose the one entry that defines this word in this sense: the entry for the word's root or base form, not one for the prefix letter alone (choose the entry for ל- or ב- only when the word is really just that preposition with a pronoun suffix, like ליה or בו), and not a different word that happens to share the spelling. If none of the candidates fits, answer 0.

Reply with one JSON object and nothing else: {"choices": {"<item id>": <candidate number or 0>, ...}}"""


def load():
    meta = json.loads((OUT / "meta.json").read_text())
    res = {k: json.loads((OUT / f"{k}.json").read_text()) for k in MODELS}
    return meta, res, json.loads(CACHE.read_text())


def items_for(cid, meta, res, cache):
    """[(item id, line n, word, {model: gloss}, [(headword, snippet)])], plus a map (n, i) -> item id."""
    items, where, seen = [], {}, {}
    for n, words in meta[cid]["words"].items():
        got = {k: (res[k].get(cid) or {}).get(n) or [] for k in MODELS}
        for i, w in enumerate(words):
            g = {k: (got[k][i] if len(got[k]) == len(words) else None) for k in MODELS}
            key = (plain(w), tuple((g[k] or {}).get("g", "") for k in MODELS))
            if key in seen:
                where[(n, i)] = seen[key]
                continue
            cands, hws = [], set()
            qs = wforms(plain(w)) + [fin(plain(g[k]["lemma"])) for k in MODELS if g[k]]
            for q in qs:
                for hw, d in cache.get(q) or []:
                    if hw not in hws and len(cands) < MAX_CANDS:
                        hws.add(hw)
                        cands.append((hw, re.sub(r"\s+", " ", d).strip()[:SNIPPET]))
            iid = str(len(items) + 1)
            seen[key] = where[(n, i)] = iid
            items.append((iid, n, w, {k: (g[k] or {}).get("g", "") for k in MODELS}, cands))
    return items, where


def build():
    meta, res, cache = load()
    client = anthropic.Anthropic()
    plan = {}
    for key, (model, pin, pout) in MODELS.items():
        reqs = []
        for t, a in PILOT:
            cid = f"{t.replace(' ', '_')}_{a}"
            items, where = items_for(cid, meta, res, cache)
            plan[cid] = {"items": [[i, n, w, c] for i, n, w, _, c in items],
                         "where": {f"{n}:{i}": v for (n, i), v in where.items()}}
            text = [f"{t} {a}"] + [f"Line {s['n']}: {clean(s.get('he'))}\n  English: {clean(s.get('en'))}"
                                   for s in amud_lines(t, a)]
            text.append("\n# Items")
            for iid, n, w, gl, cands in items:
                if not cands:
                    continue
                text.append(f"\n[{iid}] line {n}: {plain(w)} = \"{gl[key]}\"\n" +
                            "\n".join(f"  {j + 1}. {hw} — {d}" for j, (hw, d) in enumerate(cands)))
            reqs.append({"custom_id": cid, "params": {
                "model": model, "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"}, "system": SYSTEM,
                "messages": [{"role": "user", "content": "\n".join(text)}]}})
        (OUT / f"entry_requests_{key}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
        tin = sum(client.messages.count_tokens(model=model, system=SYSTEM, messages=r["params"]["messages"]).input_tokens
                  for r in reqs)
        print(f"{key}: {len(reqs)} requests, {tin:,} input tokens (${tin * pin / 1e6:.2f} in at batch rates)")
    (OUT / "entry_plan.json").write_text(json.dumps(plan, ensure_ascii=False))
    print(sum(len(p["items"]) for p in plan.values()), "items (distinct word + gloss per amud)")


def submit():
    client = anthropic.Anthropic()
    state = OUT / "entry_batches.json"
    ids = json.loads(state.read_text()) if state.exists() else {}
    for key in MODELS:
        if key not in ids:
            reqs = [json.loads(l) for l in (OUT / f"entry_requests_{key}.jsonl").read_text().splitlines()]
            ids[key] = client.messages.batches.create(requests=reqs).id
            state.write_text(json.dumps(ids))
            print(f"{key}: batch {ids[key]}", flush=True)
    while True:
        bs = {k: client.messages.batches.retrieve(v) for k, v in ids.items()}
        print({k: (b.processing_status, b.request_counts.succeeded) for k, b in bs.items()}, flush=True)
        if all(b.processing_status == "ended" for b in bs.values()):
            return
        time.sleep(30)


def harvest():
    client = anthropic.Anthropic()
    plan = json.loads((OUT / "entry_plan.json").read_text())
    ids = json.loads((OUT / "entry_batches.json").read_text())
    picked, lines = {}, ["", "# Entry choice"]
    for key, bid in ids.items():
        model, pin, pout = MODELS[key]
        tin = tout = 0
        out, bad = {}, []
        for r in client.messages.batches.results(bid):
            if r.result.type != "succeeded":
                bad.append(f"{r.custom_id}: {r.result.type}")
                continue
            msg = r.result.message
            tin += msg.usage.input_tokens
            tout += msg.usage.output_tokens
            text = "".join(b.text for b in msg.content if b.type == "text")
            try:
                ch = json.loads(re.search(r"\{.*\}", text, re.S).group(0))["choices"]
            except (AttributeError, json.JSONDecodeError, KeyError):
                bad.append(f"{r.custom_id}: unparsed ({msg.stop_reason})")
                continue
            items = {i: c for i, n, w, c in plan[r.custom_id]["items"]}
            out[r.custom_id] = {}
            for iid, cands in items.items():
                j = ch.get(iid)
                out[r.custom_id][iid] = cands[j - 1][0] if isinstance(j, int) and 1 <= j <= len(cands) else None
        picked[key] = out
        (OUT / f"entries_{key}.json").write_text(json.dumps(out, ensure_ascii=False))
        n = sum(len(p["items"]) for p in plan.values())
        cost = (tin * pin + tout * pout) / 1e6
        lines += [f"## {key}", f"{tin:,} input + {tout:,} output tokens, ${cost:.2f} for {n} items "
                  f"(3,755 words; Bavli ~1,883,000 words -> ~${cost / 3755 * 1883461:,.0f})."] + [f"- {b}" for b in bad]
    same = diff = 0
    for cid, p in plan.items():
        for i, n, w, c in p["items"]:
            a, b = (picked.get(k, {}).get(cid, {}).get(i) for k in MODELS)
            same += a == b
            diff += a != b
    lines.append(f"\nSame entry chosen for {same} items, different for {diff}.")
    with open(OUT / "report.md", "a") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "submit", "harvest"])
    {"build": build, "submit": submit, "harvest": harvest}[ap.parse_args().cmd]()
