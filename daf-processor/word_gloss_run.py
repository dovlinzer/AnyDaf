#!/usr/bin/env python3
"""Word glossary, second pilot: the full pipeline on new amudim, with each gloss model's output carried through to
the Jastrow entry, so the two can be compared on what the reader finally sees.

  1. gloss    Sonnet 5.5 and Haiku 5.5 each gloss every word in its line (word_gloss_pilot's prompt). A line whose
              word count comes back wrong is resent (whole amud) up to twice.
  2. cands    Jastrow candidates from Sefaria's /api/words for the word, its prefix-stripped forms and both models'
              dictionary forms; entries that only point elsewhere ("v. X") also bring in X. Each candidate is shown
              with all its senses (English up to the first citation, verb stems labelled), not just its opening.
              No API cost; cached in outline/word_gloss/jastrow_full.json.
  3. entry    Sonnet 5.5 (medium effort, 50 items a request) chooses the entry for each distinct word + gloss,
              once per gloss model.

    venv/bin/python word_gloss_run.py gloss-build | gloss-submit | gloss-harvest
    venv/bin/python word_gloss_run.py cands
    venv/bin/python word_gloss_run.py entry-build | entry-submit | entry-harvest
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import anthropic
from dotenv import load_dotenv

from word_gloss_pilot import HERE, MODELS, SYSTEM as GLOSS_SYSTEM, prompt

load_dotenv(HERE / ".env", override=True)
RUN = HERE / "outline" / "word_gloss" / "run2"
CACHE = HERE / "outline" / "word_gloss" / "jastrow_full.json"
AMUDIM = [("Bava Kamma", "10b"), ("Sanhedrin", "37a"), ("Ketubot", "17a"), ("Hullin", "88a")]
ENTRY_MODEL = "sonnet"
NIK = re.compile(r"[֑-ׇ\"'׳״]")
TAGS = re.compile(r"<[^>]+>")
FIN = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
MAX_CANDS = 12
SENSE_CHARS = 320


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


def cid_of(t, a):
    return f"{t.replace(' ', '_')}_{a}"


def batch_wait(client, ids):
    while True:
        bs = {k: client.messages.batches.retrieve(v) for k, v in ids.items()}
        print({k: (b.processing_status, b.request_counts.succeeded) for k, b in bs.items()}, flush=True)
        if all(b.processing_status == "ended" for b in bs.values()):
            return
        time.sleep(30)


def parse_json(text):
    try:
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except (AttributeError, json.JSONDecodeError):
        return None


# ---------- 1. glosses ----------

def gloss_request(model, t, a, rid):
    text, _ = prompt(t, a)
    return {"custom_id": rid, "params": {
        "model": model, "max_tokens": 32000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
        "system": GLOSS_SYSTEM, "messages": [{"role": "user", "content": text}]}}


def gloss_build():
    RUN.mkdir(parents=True, exist_ok=True)
    meta = {}
    for t, a in AMUDIM:
        _, words = prompt(t, a)
        meta[cid_of(t, a)] = {"tractate": t, "amud": a, "words": words}
    (RUN / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    for key, (model, *_r) in MODELS.items():
        reqs = [gloss_request(model, t, a, cid_of(t, a)) for t, a in AMUDIM]
        (RUN / f"gloss_requests_{key}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
    print(len(AMUDIM), "amudim,", sum(len(w) for m in meta.values() for w in m["words"].values()), "words")


def gloss_submit(tries=3):
    """Submit both models; then resend any amud whose lines came back with the wrong word count."""
    client = anthropic.Anthropic()
    meta = json.loads((RUN / "meta.json").read_text())
    state = RUN / "gloss_batches.json"
    st = json.loads(state.read_text()) if state.exists() else {}
    for key in MODELS:
        if key not in st:
            reqs = [json.loads(l) for l in (RUN / f"gloss_requests_{key}.jsonl").read_text().splitlines()]
            st[key] = [client.messages.batches.create(requests=reqs).id]
            state.write_text(json.dumps(st))
    for attempt in range(tries):
        batch_wait(client, {k: v[-1] for k, v in st.items()})
        res, usage = gloss_collect(client, st, meta)
        redo = {k: [c for c in meta if not amud_ok(res[k].get(c), meta[c])] for k in MODELS}
        print("bad amudim:", redo, flush=True)
        if not any(redo.values()) or attempt == tries - 1:
            break
        for k, cids in redo.items():
            if cids:
                model = MODELS[k][0]
                reqs = [gloss_request(model, meta[c]["tractate"], meta[c]["amud"], f"{c}__r{attempt + 1}") for c in cids]
                st[k].append(client.messages.batches.create(requests=reqs).id)
        state.write_text(json.dumps(st))


def amud_ok(lines, m):
    return bool(lines) and all(len(lines.get(n) or []) == len(ws) for n, ws in m["words"].items())


def gloss_collect(client, st, meta):
    """Results of every batch for each model; a later resend replaces an earlier answer only if it is complete."""
    res, usage = {}, {}
    for key, ids in st.items():
        out, tin, tout = {}, 0, 0
        for bid in ids:
            for r in client.messages.batches.results(bid):
                if r.result.type != "succeeded":
                    continue
                m = r.result.message
                tin += m.usage.input_tokens
                tout += m.usage.output_tokens
                cid = r.custom_id.split("__")[0]
                got = parse_json("".join(b.text for b in m.content if b.type == "text")) or {}
                lines = {str(ln.get("n")): ln.get("words", []) for ln in got.get("lines", [])}
                if cid not in out or (amud_ok(lines, meta[cid]) and not amud_ok(out[cid], meta[cid])):
                    out[cid] = lines
        res[key], usage[key] = out, (tin, tout)
    return res, usage


def gloss_harvest():
    client = anthropic.Anthropic()
    meta = json.loads((RUN / "meta.json").read_text())
    st = json.loads((RUN / "gloss_batches.json").read_text())
    res, usage = gloss_collect(client, st, meta)
    report = ["# Glosses"]
    for key, out in res.items():
        (RUN / f"gloss_{key}.json").write_text(json.dumps(out, ensure_ascii=False))
        tin, tout = usage[key]
        _, pin, pout = MODELS[key]
        bad = [c for c in meta if not amud_ok(out.get(c), meta[c])]
        report.append(f"{key}: {tin:,} in + {tout:,} out, ${(tin * pin + tout * pout) / 1e6:.2f}; "
                      f"{len(st[key])} batch(es); amudim still wrong: {bad or 'none'}")
    (RUN / "report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))


# ---------- 2. candidates ----------

def sense_text(e):
    """All of an entry's senses, each as its English up to the first citation; verb stems labelled."""
    parts = []

    def walk(ss, stem=""):
        for x in ss or []:
            vs = (x.get("grammar") or {}).get("verbal_stem") if isinstance(x.get("grammar"), dict) else None
            d = re.sub(r"\s+", " ", TAGS.sub("", x.get("definition") or "")).strip()
            d = re.split(r"\b(?:Targ|Ib|Y|B|M|Sabb|Ber|Pes|Gitt|Kidd|Snh|Ab|Tosef|Yoma|Ḥull|Keth|Yeb|Ned|Sot|Men|Lev|Gen|Num|Yalk|Pesik|Koh|Lam|Esth|Cant|Ruth|Midr|Tanḥ|Sifra|Sifré|Mekh|Erub|Succ|Meg|Taan|Bets|Ḥag|Mak|Shebu|Hor|Zeb|Bekh|Arakh|Tem|Ker|Meil|Tam|Midd|Kinn|Nidd|Toh|Ohol|Neg|Par|Mikv|Makhsh|Zab|Yad|Ukts|Kel|Dem|Kil|Sheb|Ter|Maas|Ḥall|Orl|Bicc|Peah|R|Ex|Deut|Is|Jer|Ez|Ps|Prov|Job|Dan|Ezr|Neh|Chr|Sam|Kings|Jud|Josh|Hos|Am|Mic|Hab|Zech|Mal)\.\s|\d", d)[0].strip(" ,;.—-[](")
            d = d[:110]
            if d:
                parts.append((f"{stem} " if stem else "") + d)
            walk(x.get("senses"), vs or stem)
    walk((e.get("content") or {}).get("senses"))
    return "; ".join(parts)[:SENSE_CHARS]


def pointer(e):
    """The headword an entry merely points to ("v. X"), if that is all it says."""
    raw = TAGS.sub("", json.dumps((e.get("content") or {}).get("senses") or [], ensure_ascii=False))
    if len(raw) > 220:
        return None
    m = re.search(r"\bv\.\s*([א-ת֑-ׇ]{2,})", raw)
    return plain(m.group(1)) if m else None


def near(e):
    """The neighbouring headword a short entry defers to ("as preced.", "v. preced.", "v. next w.")."""
    raw = TAGS.sub("", json.dumps((e.get("content") or {}).get("senses") or [], ensure_ascii=False))
    if len(raw) > 220:
        return None
    if re.search(r"preced", raw):
        return e.get("prev_hw")
    if re.search(r"next w", raw):
        return e.get("next_hw")
    return None


def fetch(q):
    try:
        url = "https://www.sefaria.org/api/words/" + urllib.parse.quote(q) + "?never_split=0"
        with urllib.request.urlopen(url, timeout=30) as f:
            es = json.load(f)
        return q, [{"hw": e["headword"], "senses": sense_text(e), "ptr": pointer(e), "near": near(e)}
                   for e in es if isinstance(e, dict) and "Jastrow" in e.get("parent_lexicon", "")]
    except Exception:
        return q, None


def cands():
    meta = json.loads((RUN / "meta.json").read_text())
    glosses = {k: json.loads((RUN / f"gloss_{k}.json").read_text()) for k in MODELS}
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    qs = set()
    for c, m in meta.items():
        for n, ws in m["words"].items():
            for i, w in enumerate(ws):
                qs.update(wforms(plain(w)))
                for k in MODELS:
                    g = (glosses[k].get(c) or {}).get(n) or []
                    if len(g) == len(ws) and g[i].get("lemma"):
                        qs.add(fin(plain(g[i]["lemma"])))
    for rnd in range(2):   # the second round fetches what "v. X" entries point to
        todo = sorted(q for q in qs if q not in cache)
        with ThreadPoolExecutor(8) as ex:
            for q, v in ex.map(fetch, todo):
                if v is not None:
                    cache[q] = v
        qs = {e["ptr"] for q in qs for e in cache.get(q) or [] if e.get("ptr")} | \
             {plain(e["near"]) for q in qs for e in cache.get(q) or [] if e.get("near")}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    print(len(cache), "queries cached")


def candidates(word, lemma, cache):
    out, seen = [], set()

    def add(e, via=None):
        if e["hw"] not in seen and len(out) < MAX_CANDS:
            seen.add(e["hw"])
            out.append({"hw": e["hw"], "senses": e["senses"], "via": via})

    for q in [fin(plain(lemma))] + wforms(plain(word)) if lemma else wforms(plain(word)):
        for e in cache.get(q) or []:
            add(e)
            if e.get("ptr"):
                for t in cache.get(e["ptr"]) or []:
                    if plain(t["hw"]).startswith(e["ptr"]):
                        add(t, e["hw"])
            if e.get("near"):
                for t in cache.get(plain(e["near"])) or []:
                    if t["hw"] == e["near"]:
                        add(t, e["hw"])
    return out


# ---------- 3. entries ----------

ENTRY_SYSTEM = """You link words of the Babylonian Talmud to the right entry in Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi, for English-speaking learners who tap a word and see the entry.

Each item gives a word as it appears in the Gemara (without vowels), its dictionary form, and the English gloss already decided for it in its line. Then numbered candidate Jastrow entries, each with its senses (English only, citations removed; verb stems such as Pa., Ithpe., Hif. label the senses that follow). Jastrow often has several entries with one spelling (numbered I, II, III), and separate Hebrew and Aramaic ("ch.") entries for the same word.

For each item choose the entry that defines this word in the sense of the gloss:
- the entry for the word's root or base form, not one for a prefix letter alone (choose ל- or ב- only when the word is just that preposition with a pronoun suffix, like ליה or בו), and not a different word that shares the spelling;
- read all the senses: the sense that fits may come late in an entry;
- an entry that only refers elsewhere ("v. X") is acceptable only if its target is not among the candidates; prefer the target (marked "via");
- when a Hebrew and an Aramaic entry both fit, prefer the one matching the word's language here (Mishnah and baraita are Hebrew, the Gemara's own discussion mostly Aramaic).
If no candidate fits, answer 0.

Reply with one JSON object and nothing else: {"choices": {"<item id>": <candidate number or 0>, ...}}"""


def items_for(gk, meta, glosses, cache):
    """Distinct (word, gloss) items across the run for one gloss model, with candidates and where they occur."""
    items, where = {}, {}
    for c, m in meta.items():
        for n, ws in m["words"].items():
            g = (glosses[gk].get(c) or {}).get(n) or []
            for i, w in enumerate(ws):
                if len(g) != len(ws):
                    continue
                gl, lem = g[i].get("g", ""), g[i].get("lemma", "")
                key = f"{plain(w)}|{gl.lower().strip()}"
                where[f"{c}:{n}:{i}"] = key
                if key not in items:
                    items[key] = {"w": plain(w), "lemma": lem, "g": gl, "cands": candidates(w, lem, cache)}
    return items, where


def entry_build(chunk=50):
    meta = json.loads((RUN / "meta.json").read_text())
    glosses = {k: json.loads((RUN / f"gloss_{k}.json").read_text()) for k in MODELS}
    cache = json.loads(CACHE.read_text())
    model, pin, _ = MODELS[ENTRY_MODEL]
    client = anthropic.Anthropic()
    plan = {}
    for gk in MODELS:
        items, where = items_for(gk, meta, glosses, cache)
        keys = [k for k, v in items.items() if v["cands"]]
        ids = {k: str(j + 1) for j, k in enumerate(keys)}
        plan[gk] = {"items": items, "where": where, "ids": ids}
        reqs = []
        for s in range(0, len(keys), chunk):
            text = []
            for k in keys[s:s + chunk]:
                v = items[k]
                text.append(f"[{ids[k]}] {v['w']} (dictionary form {plain(v['lemma'])}) = \"{v['g']}\"\n" + "\n".join(
                    f"  {j + 1}. {x['hw']}{' (via ' + x['via'] + ')' if x['via'] else ''} — {x['senses'] or '(no English given)'}"
                    for j, x in enumerate(v["cands"])))
            reqs.append({"custom_id": f"{gk}__{s // chunk}", "params": {
                "model": model, "max_tokens": 16000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
                "system": ENTRY_SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(text)}]}})
        (RUN / f"entry_requests_{gk}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
        tin = sum(client.messages.count_tokens(model=model, system=ENTRY_SYSTEM, messages=r["params"]["messages"]).input_tokens
                  for r in reqs)
        print(f"{gk} glosses: {len(items)} distinct word+gloss ({len(keys)} with candidates), {len(reqs)} requests, "
              f"{tin:,} input tokens (${tin * pin / 1e6:.2f})")
    (RUN / "entry_plan.json").write_text(json.dumps(plan, ensure_ascii=False))


def entry_submit():
    client = anthropic.Anthropic()
    state = RUN / "entry_batch.json"
    if not state.exists():
        reqs = [json.loads(l) for gk in MODELS for l in (RUN / f"entry_requests_{gk}.jsonl").read_text().splitlines()]
        state.write_text(json.dumps({"id": client.messages.batches.create(requests=reqs).id}))
    batch_wait(client, {"entries": json.loads(state.read_text())["id"]})


def entry_harvest():
    client = anthropic.Anthropic()
    plan = json.loads((RUN / "entry_plan.json").read_text())
    bid = json.loads((RUN / "entry_batch.json").read_text())["id"]
    _, pin, pout = MODELS[ENTRY_MODEL]
    tin = tout = 0
    chosen = {gk: {} for gk in plan}
    for r in client.messages.batches.results(bid):
        gk = r.custom_id.split("__")[0]
        if r.result.type != "succeeded":
            print("failed:", r.custom_id)
            continue
        m = r.result.message
        tin += m.usage.input_tokens
        tout += m.usage.output_tokens
        ch = (parse_json("".join(b.text for b in m.content if b.type == "text")) or {}).get("choices", {})
        byid = {v: k for k, v in plan[gk]["ids"].items()}
        for iid, j in ch.items():
            k = byid.get(str(iid))
            cands = plan[gk]["items"][k]["cands"] if k else []
            if isinstance(j, int) and 1 <= j <= len(cands):
                chosen[gk][k] = cands[j - 1]["hw"]
    (RUN / "entries.json").write_text(json.dumps(chosen, ensure_ascii=False))
    # per running word: the entry each pipeline shows
    same = diff = none = 0
    keys = set(plan["sonnet"]["where"]) & set(plan["haiku"]["where"])
    for w in keys:
        a = chosen["sonnet"].get(plan["sonnet"]["where"][w])
        b = chosen["haiku"].get(plan["haiku"]["where"][w])
        if a is None or b is None:
            none += 1
        elif a == b:
            same += 1
        else:
            diff += 1
    line = (f"Entries ({MODELS[ENTRY_MODEL][0]}, medium): {tin:,} in + {tout:,} out, ${(tin * pin + tout * pout) / 1e6:.2f}. "
            f"Of {len(keys)} running words: same entry {same}, different {diff}, missing on one side {none}.")
    with open(RUN / "report.md", "a") as f:
        f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gloss-build", "gloss-submit", "gloss-harvest", "cands",
                                    "entry-build", "entry-submit", "entry-harvest"])
    {"gloss-build": gloss_build, "gloss-submit": gloss_submit, "gloss-harvest": gloss_harvest, "cands": cands,
     "entry-build": entry_build, "entry-submit": entry_submit, "entry-harvest": entry_harvest}[ap.parse_args().cmd]()
