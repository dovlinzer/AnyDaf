"""Second chance for glossed words left with no dictionary entry (Batch API, Sonnet, pennies).

A word gets no entry when none of its candidates fits, and usually that is because the candidate list missed the right
entry: the candidates come from the word's own letters and the glosser's dictionary form, and when that form is off
(כרעיה "its leg" looked up under רעה, not כְּרַע) the right entry was never offered. So:

  1. forms:  the model names the dictionary forms to look up (Jastrow's spelling, no vowels), which are fetched from
             Sefaria and added to the candidates;
  2. choose: the model chooses among the enlarged list (or none, for a name or a word no entry defines), with the
             phrase where the fitting sense begins.

Writes <run>/recheck.json {"<item key>": {"e": entry, "q": sense phrase}}, which word_gloss_run.py's fix() applies.
Names (shown as their gloss alone) and words with no candidates are left out.

  WG_RUN=run8 venv/bin/python word_gloss_recheck.py forms
  WG_RUN=run8 venv/bin/python word_gloss_recheck.py choose
  WG_RUN=run8 venv/bin/python word_gloss_run.py fix          # then word_gloss_export.py
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import anthropic

import word_gloss_run as W

RUN = W.RUN
FORMS, OUT = RUN / "recheck_forms.json", RUN / "recheck.json"
MODEL, PIN, POUT = W.MODELS["sonnet"]

FORMS_SYSTEM = """You help link words of the Babylonian Talmud to their entries in Jastrow's Dictionary (and Klein's, for Hebrew words). Each item gives a word as it stands in the Gemara (without vowels, with any prefix letters ד ו ב ל ה מ ש כ), the English gloss already decided for it, a few words of its line, and the entries looked up so far, none of which defines it.

For each item, name up to three headwords to look up, as Jastrow spells them, without vowels: the word's dictionary form with prefixes and suffixes removed (כרעיה "its leg" -> כרע; דיינא "the judge" -> דיינא, דיין), the root for a verb form, and the Aramaic or Hebrew form Jastrow is likely to list it under.

Reply with one JSON object and nothing else: {"forms": {"<item id>": ["...", "..."], ...}}"""

CHOOSE_SYSTEM = """You link words of the Babylonian Talmud to the right dictionary entry (Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi, or Klein's dictionary of Hebrew for Hebrew words), for English-speaking learners who tap a word and see the entry.

Each item gives a word from the Gemara (without vowels), its language, the English gloss already decided for it in its line, a few words of the line around it, and numbered candidate entries, each with its full text. Judge the word without its prefix letters (ד, ו, ב, ל, ה, מ, ש, כ): the gloss includes their meaning, the entry does not.

For each item:
- "c": the number of the entry that defines this word in the sense of its gloss, or 0 if none does (a wrong entry is worse than none: the reader then sees the gloss alone).
- "q": copy, character for character, a short phrase (3 to 8 words) of that entry where the sense that fits begins (a sense number with its first words, a form marker with its form, or the sense's first English words); "" if it is the entry's opening sense.

Reply with one JSON object and nothing else: {"choices": {"<item id>": {"c": 2, "q": "..."}, ...}}"""


def todo():
    plan = json.loads((RUN / "entry_plan.json").read_text())["sonnet"]
    fx = json.loads((RUN / "final.json").read_text())
    names = set(fx["names"])
    return plan, {k: v for k, v in plan["items"].items() if k not in fx["entries"] and k not in names and v["cands"]}


def run_batch(reqs, label):
    client = anthropic.Anthropic()
    bid = client.messages.batches.create(requests=reqs).id
    W.batch_wait(client, {label: bid})
    tin = tout = 0
    out = {}
    for r in client.messages.batches.results(bid):
        if r.result.type != "succeeded":
            print("failed:", r.custom_id)
            continue
        m = r.result.message
        tin += m.usage.input_tokens
        tout += m.usage.output_tokens
        out.update(W.parse_json("".join(b.text for b in m.content if b.type == "text")) or {})
    print(f"{label}: {tin:,} in + {tout:,} out, ${(tin * PIN + tout * POUT) / 1e6:.2f}")
    return out


def line(v):
    return f"{v['w']} ({v.get('lang') or 'language not marked'}) = \"{v['g']}\" — in: {v.get('ctx', '')}"


def forms():
    _, its = todo()
    keys = sorted(its)
    text = [f"[{j + 1}] {line(its[k])}\n  looked up: " + ", ".join(W.ref(x).removeprefix("K:") for x in its[k]["cands"])
            for j, k in enumerate(keys)]
    got = run_batch([{"custom_id": "forms", "params": {
        "model": MODEL, "max_tokens": 4000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
        "system": FORMS_SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(text)}]}}], "forms").get("forms") or {}
    out = {keys[int(i) - 1]: [W.fin(W.plain(f)) for f in fs if isinstance(f, str)][:3]
           for i, fs in got.items() if str(i).isdigit() and 1 <= int(i) <= len(keys) and isinstance(fs, list)}
    cache = json.loads(W.CACHE.read_text())
    need = sorted({f for fs in out.values() for f in fs} - set(cache))
    with ThreadPoolExecutor(8) as ex:
        for q, v in ex.map(W.fetch, need):
            if v is not None:
                cache[q] = v
    W.CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    FORMS.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k, fs in out.items():
        print(" ", k, "->", fs)


def choose():
    _, its = todo()
    fms = json.loads(FORMS.read_text())
    cache = json.loads(W.CACHE.read_text())
    keys = sorted(its)
    plan, text = {}, []
    for j, k in enumerate(keys):
        v = its[k]
        cs, seen = [], set()
        for f in [None] + fms.get(k, []):
            for x in (v["cands"] if f is None else
                      W.candidates(f, None, cache, hebrew=v.get("lang") == "Hebrew")):
                if W.ref(x) not in seen:
                    seen.add(W.ref(x))
                    cs.append(W.ref(x))
        texts = W.fetch_entries(set(cs))
        cs = [c for c in cs if texts.get(c)][:16]
        plan[str(j + 1)] = {"key": k, "cands": cs}
        text.append(f"[{j + 1}] {line(v)}\n" + "\n".join(
            f"  {n + 1}. {'Klein: ' if c.startswith('K:') else ''}{c.removeprefix('K:')} — {texts[c][:1500]}"
            for n, c in enumerate(cs)))
    got = run_batch([{"custom_id": "choose", "params": {
        "model": MODEL, "max_tokens": 8000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
        "system": CHOOSE_SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(text)}]}}], "choose").get("choices") or {}
    texts = W.fetch_entries({c for p in plan.values() for c in p["cands"]})
    out = {}
    for i, p in plan.items():
        a = got.get(i) or {}
        c = a.get("c") if isinstance(a, dict) else None
        if not isinstance(c, int) or not 1 <= c <= len(p["cands"]):
            print("  none:", p["key"])
            continue
        hw, q = p["cands"][c - 1], W.norm_ws(a.get("q") or "")
        rec = {"e": hw}
        if q and W.norm_ws(texts[hw]).find(q) > 0:
            rec["q"] = q
        out[p["key"]] = rec
        print(" ", p["key"], "->", hw, f"({q})" if "q" in rec else "")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"forms": forms, "choose": choose}[sys.argv[1]]()
