#!/usr/bin/env python3
"""Pilot: a dictionary form and an English gloss, in context, for every word of the Gemara.

For the passage window's word lookup (AnyDafWeb app.html): instead of guessing a word's stem by stripping
letters, the page would show a gloss worked out once, ahead of time, from the line's Aramaic, Davidson's English
and Steinsaltz's Hebrew together, and fetch the Jastrow / Klein entries for the dictionary form it names.

Batch API, one request per amud, run on two models side by side to compare accuracy and cost.

    venv/bin/python word_gloss_pilot.py build      # -> outline/word_gloss/requests_<model>.jsonl, prints token counts
    venv/bin/python word_gloss_pilot.py submit     # submits one batch per model, waits
    venv/bin/python word_gloss_pilot.py harvest    # -> outline/word_gloss/<model>.json + report.md
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)
HERE = Path(__file__).parent
OUT = HERE / "outline" / "word_gloss"
TEXT = HERE / "daf_text"

# Batch prices per MTok (input, output). Sonnet 5.5 and Haiku 5.5 (prompt <= 100K) from the claude-api skill's
# model notes; batch = half the list price.
MODELS = {"sonnet": ("claude-sonnet-5-5", 1.00, 5.00), "haiku": ("claude-haiku-5-5", 0.05, 0.25)}
PILOT = [("Bava Metzia", d) for d in ("2a", "2b", "3a", "3b", "11a", "11b")] + \
        [("Kiddushin", d) for d in ("2a", "2b")] + [("Berakhot", d) for d in ("2a", "2b")] + \
        [("Shabbat", d) for d in ("21a", "21b")]

NIKUD = re.compile(r"[֑-ׇ]")
TAGS = re.compile(r"<[^>]+>")
WORD = re.compile(r"[א-ת][א-ת֑-ׇ\"'׳״]*")   # the page's own word pattern (wrapWords)

SYSTEM = """You prepare a word-by-word glossary of the Babylonian Talmud for English-speaking learners. A learner taps a word in the Aramaic/Hebrew text and sees your gloss, plus the dictionary entry for the form you name.

For each line you get the Gemara text (vocalized), the William Davidson English translation, and Steinsaltz's Hebrew explanation, in which the Gemara's own words appear in **bold** followed by his Hebrew rendering in [brackets]. Use all three to decide what each word means in this line.

For every word in the numbered word list, give:
- "w": the word as listed, without vowels (so the entries can be checked against the text).
- "lemma": the dictionary form, as Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi lists it, unvocalized: for a verb its root (קתני -> תני, למיתנא -> תני, דמשתבע -> שבע, תימא -> אמר), for a noun or adjective its singular absolute form (שבועת -> שבועה), for a particle the particle itself (נמי, הכא). Strip prefixes (ו, ד, ה, ב, ל, מ, ש, כ, and ק/קא before a verb) and suffixes. For a person's name, the name (רב, אביי, יוחנן). For a word that is really an abbreviation, the abbreviation as written. Stay within the word itself: give the dictionary form of this word in its own language, never its equivalent in the other language. An Aramaic word keeps its Aramaic form (מיתבר -> תבר, not the Hebrew שבר; לישתוק -> שתק as Jastrow lists the Aramaic), and a Hebrew word its Hebrew form, even when the meaning is the same.
- "g": a short English gloss of what the word means HERE, in context, 1 to 5 words, including what its prefixes and suffixes add ("and let him teach", "who swears", "if you say", "from the Sages", "it was taught"). For a term of art, the term's sense here ("by rabbinic law", "an oath"). For a name, the person ("Rabbi Yochanan"). Plain English; write Hebrew terms in italic transliteration only if they are terms of art.

Reply with one JSON object and nothing else:
{"lines": [{"n": <line number>, "words": [{"w": "...", "lemma": "...", "g": "..."}, ...]}, ...]}
Give exactly one entry per listed word, in the listed order."""


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", TAGS.sub("", t or "")).strip()


def amud_lines(tractate: str, amud: str):
    return json.loads((TEXT / f"{tractate}.json").read_text())["amudim"][amud]["segments"]


def prompt(tractate: str, amud: str) -> tuple[str, dict]:
    parts, words = [f"{tractate} {amud}"], {}
    for s in amud_lines(tractate, amud):
        ws = WORD.findall(s.get("he", ""))
        words[s["n"]] = [NIKUD.sub("", w) for w in ws]
        parts.append(f"\n## Line {s['n']}\nGemara: {clean(s.get('he'))}\nEnglish: {clean(s.get('en'))}\n"
                     f"Steinsaltz: {clean(s.get('hx'))}\nWords: " + " ".join(f"{i + 1}:{w}" for i, w in enumerate(ws)))
    return "\n".join(parts), words


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    client = anthropic.Anthropic()
    for key, (model, pin, pout) in MODELS.items():
        reqs = []
        for t, a in PILOT:
            text, words = prompt(t, a)
            cid = f"{t.replace(' ', '_')}_{a}"
            meta[cid] = {"tractate": t, "amud": a, "words": words}
            reqs.append({"custom_id": cid, "params": {
                "model": model, "max_tokens": 32000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"}, "system": SYSTEM,
                "messages": [{"role": "user", "content": text}]}})
        (OUT / f"requests_{key}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
        tin = sum(client.messages.count_tokens(model=model, system=SYSTEM, messages=r["params"]["messages"]).input_tokens
                  for r in reqs)
        print(f"{key}: {len(reqs)} requests, {tin:,} input tokens (${tin * pin / 1e6:.2f} in at batch rates)")
    nw = sum(len(v) for m in meta.values() for v in m["words"].values())
    nl = sum(len(m["words"]) for m in meta.values())
    print(f"{len(PILOT)} amudim, {nl} lines, {nw} words")
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))


def submit():
    client = anthropic.Anthropic()
    state = OUT / "batches.json"
    ids = json.loads(state.read_text()) if state.exists() else {}
    for key in MODELS:
        if key not in ids:
            reqs = [json.loads(l) for l in (OUT / f"requests_{key}.jsonl").read_text().splitlines()]
            ids[key] = client.messages.batches.create(requests=reqs).id
            state.write_text(json.dumps(ids))
            print(f"{key}: batch {ids[key]}")
    while True:
        bs = {k: client.messages.batches.retrieve(v) for k, v in ids.items()}
        print({k: (b.processing_status, b.request_counts.succeeded) for k, b in bs.items()}, flush=True)
        if all(b.processing_status == "ended" for b in bs.values()):
            return
        time.sleep(30)


def harvest():
    client = anthropic.Anthropic()
    meta = json.loads((OUT / "meta.json").read_text())
    ids = json.loads((OUT / "batches.json").read_text())
    report = ["# Word-gloss pilot", ""]
    for key, bid in ids.items():
        model, pin, pout = MODELS[key]
        res, tin, tout, bad = {}, 0, 0, []
        for r in client.messages.batches.results(bid):
            m = meta[r.custom_id]
            if r.result.type != "succeeded":
                bad.append(f"{r.custom_id}: {r.result.type}")
                continue
            msg = r.result.message
            tin += msg.usage.input_tokens
            tout += msg.usage.output_tokens
            text = "".join(b.text for b in msg.content if b.type == "text")
            try:
                got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except (AttributeError, json.JSONDecodeError):
                bad.append(f"{r.custom_id}: unparsed ({msg.stop_reason})")
                continue
            lines = {}
            for ln in got.get("lines", []):
                want = m["words"].get(str(ln.get("n"))) or m["words"].get(ln.get("n"))
                ws = ln.get("words", [])
                if want is None or len(ws) != len(want):
                    bad.append(f"{r.custom_id} line {ln.get('n')}: words don't match the list "
                               f"({len(ws)} vs {len(want or [])})")
                lines[str(ln.get("n"))] = ws
            res[r.custom_id] = lines
        (OUT / f"{key}.json").write_text(json.dumps(res, ensure_ascii=False, indent=0))
        nw = sum(len(v) for m in meta.values() for v in m["words"].values())
        cost = (tin * pin + tout * pout) / 1e6
        report += [f"## {key} ({model}, effort low)", "",
                   f"{tin:,} input + {tout:,} output tokens, ${cost:.2f} for {nw} words "
                   f"(${cost / nw * 1e3:.3f} per 1,000 words; Bavli ~1,883,000 words -> ~${cost / nw * 1883461:,.0f}).", ""]
        report += [f"- {b}" for b in bad] or ["- every line's word list matched"]
        report.append("")
    (OUT / "report.md").write_text("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "submit", "harvest"])
    {"build": build, "submit": submit, "harvest": harvest}[ap.parse_args().cmd]()
