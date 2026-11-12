"""Sense pointers for BDB entries of verse words (Batch API, Sonnet).

The passage window marks every citation of the verse in a word's BDB entry and opens the entry there. Most entries
never cite the verse (BDB cites a sample of verses), and a long verb entry then opens at its top: "and the dead one"
(והמת, Exodus 21:36) shows מוּת "die" with its forms, and the participle's sense ("of animals ... dead dog") lies far
below. This step asks for the sense of the word's plain meaning in its verse (pshat: the verse read on its own, not the
Gemara's derashah on it) and stores a short verbatim phrase where it begins ("bq"), which the page marks and scrolls
to, as it does with the Jastrow/Klein pointers ("q"). The sense depends only on the verse word, so it is worked out
once per (headword, verse, verse word) however often the Gemara quotes the verse. "No sense fits" then means the
entry is probably the wrong one; those are listed in outline/word_gloss/bdb_review.json and get no pointer.

  venv/bin/python bdb_senses.py fetch     # BDB entries and verse texts (Sefaria) -> bdb_entries.json, bdb_verse_text.json

  venv/bin/python bdb_senses.py build     # requests + token count and cost
  venv/bin/python bdb_senses.py submit    # Batch API
  venv/bin/python bdb_senses.py harvest   # writes "bq" into outline/word_gloss/bdb.json
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

from word_gloss_pilot import MODELS
from word_gloss_run import batch_wait, parse_json

HERE = Path(__file__).parent
WG = HERE / "outline" / "word_gloss"
BDB = WG / "bdb.json"
ENTRIES = WG / "bdb_entries.json"
VTEXT = WG / "bdb_verse_text.json"
REVIEW = WG / "bdb_review.json"
REQS, PLAN, STATE = WG / "bdb_sense_requests.jsonl", WG / "bdb_sense_plan.json", WG / "bdb_sense_batch.json"
TAGS = re.compile(r"<[^>]+>")
CAP = 160          # characters of each sense shown in the outline
CHUNK = 10         # items per request

SYSTEM = """You help English-speaking learners of the Babylonian Talmud who tap a word of a Bible verse quoted in the Gemara and see its entry in the Brown-Driver-Briggs Hebrew lexicon (BDB). BDB entries are long; the page will open the entry at the sense that fits the word in this verse.

Each item gives the word as it stands in the verse, the verse (Hebrew, with an English translation), and an outline of the BDB entry: one line per sense (indented by depth), each cut to its first words. Lines that list forms ("Pf. 3 ms. ...", "Impf. ...") are not senses.

For each item:
- "q": copy, character for character, the first words (3 to 8) of the outline line where the sense that fits begins ("of animals Lv 11:39", "sometimes c. לְ pers. only = become the property of"). Point to the most specific sense that fits the word's plain meaning in this verse (pshat): the verse read on its own terms, as a Bible dictionary reads it, not as the Gemara expounds it. A participle used as a noun or adjective ("the dead one") fits the verb's sense for that subject (a dead animal: "of animals"). Use "" if only the entry's opening sense fits.
- "fit": "yes" if some sense fits the word's plain meaning in the verse; "no" if none does (the entry is probably the wrong one: another word spelled the same).

Reply with one JSON object and nothing else: {"senses": {"<item id>": {"q": "...", "fit": "yes"}, ...}}"""


def bare(hw):
    return re.sub(r"[֑-ׇ²³¹⁰-⁹\s]", "", hw)


def get(hw, ref, strong=None, verse_words=()):
    """Sefaria's BDB entry with this headword, looked up for this verse: by the verse's own word (as bdb_verses.py
    found it), then the headword pointed and plain."""
    for w in (*verse_words, re.sub(r"[²³¹⁰-⁹\s]+$", "", hw), bare(hw)):
        u = ("https://www.sefaria.org/api/words/" + urllib.parse.quote(w) + "?never_split=1&lookup_ref=" +
             urllib.parse.quote(ref))
        try:
            es = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "word-glossary"}),
                                                  timeout=30))
        except Exception:
            continue
        e = next((e for e in es if e.get("parent_lexicon") == "BDB Dictionary" and e["headword"] == hw and
                  (not strong or strong in (e.get("strong_numbers") or []))), None)
        if e:
            return w, e
    return None, None


def fetch():
    bdb = json.loads(BDB.read_text())
    pairs = sorted({(x["b"], x["v"], x.get("s")) for a in bdb.values() for l in a.values() for x in l.values()})
    cache = json.loads((WG / "bdb_cache.json").read_text())   # bdb_verses.py: "<verse word>|<ref>" -> its BDB entries
    vw = {}
    for k, es in cache.items():
        w, ref = k.split("|", 1)
        for e in es:
            for st in e["s"]:
                vw.setdefault((e["hw"], ref, st), []).append(w)
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(pairs, ex.map(lambda p: get(*p, vw.get(p, [])), pairs)))
    out = {f"{h}|{v}|{st}": {"w": w, "e": e} for (h, v, st), (w, e) in res.items() if e}
    ENTRIES.write_text(json.dumps(out, ensure_ascii=False))
    print(len(pairs), "BDB headword+verse pairs;", len(out), "found;", "missing:",
          [p for p, (w, e) in res.items() if not e])
    vt = json.loads(VTEXT.read_text()) if VTEXT.exists() else {}
    need = sorted({v for _, v, _ in pairs} - set(vt))

    def verse(ref):
        u = "https://www.sefaria.org/api/texts/" + urllib.parse.quote(ref) + "?context=0&commentary=0"
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "word-glossary"}),
                                                 timeout=30))
        except Exception:
            return None
        flat = lambda t: " ".join(flat(x) for x in t) if isinstance(t, list) else (t or "")
        clean = lambda t: re.sub(r"\s+", " ", TAGS.sub("", re.sub(r"<sup.*?</sup>|<i class=\"footnote\">.*?</i>", "", flat(t)))).strip()
        return {"he": clean(d.get("he")), "en": clean(d.get("text"))}
    with ThreadPoolExecutor(8) as ex:
        for ref, t in zip(need, ex.map(verse, need)):
            if t:
                vt[ref] = t
    VTEXT.write_text(json.dumps(vt, ensure_ascii=False, indent=1))
    print(len(vt), "verse texts")


def outline(e):
    out = []

    def walk(ss, depth):
        for s in ss or []:
            d = re.sub(r"\s+", " ", TAGS.sub("", s.get("definition") or "")).strip()
            if d:
                out.append("  " * depth + d[:CAP])
            walk(s.get("senses"), depth + 1)
    walk((e.get("content") or {}).get("senses"), 0)
    return "\n".join(out)


def skey(x):
    """One sense per headword, verse and verse word (the word as it stands in the verse)."""
    return f"{x['b']}|{x['v']}|{x.get('bw') or ''}"


def items():
    """One item per (headword, verse, verse word) whose entry does not cite the verse itself."""
    bdb, ents, vt = json.loads(BDB.read_text()), json.loads(ENTRIES.read_text()), json.loads(VTEXT.read_text())
    out = {}
    for key, lines in bdb.items():
        for n, ws in lines.items():
            for i, x in ws.items():
                ent = ents.get(f"{x['b']}|{x['v']}|{x.get('s')}")
                if not ent or f'data-ref="{x["v"]}"' in json.dumps(ent["e"], ensure_ascii=False):
                    continue
                x = {**x, "bw": ent["w"]}
                out.setdefault(skey(x), {"hw": x["b"], "v": x["v"], "w": ent["w"], "verse": vt.get(x["v"]) or {},
                                         "text": outline(ent["e"])})
    return out


def build():
    its = items()
    keys = sorted(its)
    model, pin, _ = MODELS["sonnet"]
    reqs = []
    for s in range(0, len(keys), CHUNK):
        text = [f"[{s + j + 1}] {its[k]['w']} in {its[k]['v']}: {its[k]['verse'].get('he', '')}\n"
                f"({its[k]['verse'].get('en', '')})\nBDB {its[k]['hw']}:\n{its[k]['text']}"
                for j, k in enumerate(keys[s:s + CHUNK])]
        reqs.append({"custom_id": f"bdb__{s // CHUNK}", "params": {
            "model": model, "max_tokens": 6000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
            "system": SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(text)}]}})
    REQS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
    PLAN.write_text(json.dumps({"keys": keys, "items": its}, ensure_ascii=False))
    client = anthropic.Anthropic()
    tin = sum(client.messages.count_tokens(model=model, system=SYSTEM, messages=r["params"]["messages"]).input_tokens
              for r in reqs)
    print(f"{len(keys)} items, {len(reqs)} requests, {tin:,} input tokens (${tin * pin / 1e6:.2f} before output)")


def submit():
    client = anthropic.Anthropic()
    if not STATE.exists():
        reqs = [json.loads(l) for l in REQS.read_text().splitlines()]
        STATE.write_text(json.dumps({"id": client.messages.batches.create(requests=reqs).id}))
    batch_wait(client, {"bdb senses": json.loads(STATE.read_text())["id"]})


def harvest():
    client = anthropic.Anthropic()
    plan = json.loads(PLAN.read_text())
    keys, its = plan["keys"], plan["items"]
    _, pin, pout = MODELS["sonnet"]
    tin = tout = 0
    got, review, stats = {}, [], {"pointer": 0, "opening": 0, "not found": 0, "no fit": 0}
    for r in client.messages.batches.results(json.loads(STATE.read_text())["id"]):
        if r.result.type != "succeeded":
            print("failed:", r.custom_id)
            continue
        m = r.result.message
        tin += m.usage.input_tokens
        tout += m.usage.output_tokens
        for iid, a in ((parse_json("".join(b.text for b in m.content if b.type == "text")) or {}).get("senses") or {}).items():
            if not str(iid).isdigit() or not 1 <= int(iid) <= len(keys) or not isinstance(a, dict):
                continue
            k = keys[int(iid) - 1]
            q = re.sub(r"\s+", " ", a.get("q") or "").strip()
            text = re.sub(r"\s+", " ", its[k]["text"])
            if a.get("fit") != "yes":
                stats["no fit"] += 1
                review.append({"key": k, "hw": its[k]["hw"], "verse": its[k]["v"], "word": its[k]["w"]})
                print("  no fit:", k)
            elif not q:
                stats["opening"] += 1
            elif text.find(q) > 0:
                got[k] = q
                stats["pointer"] += 1
            else:
                stats["not found"] += 1
                print("  not found:", k, "->", q)
    bdb, ents = json.loads(BDB.read_text()), json.loads(ENTRIES.read_text())
    for lines in bdb.values():
        for ws in lines.values():
            for x in ws.values():
                x.pop("bq", None)
                x.pop("bw", None)
                ent = ents.get(f"{x['b']}|{x['v']}|{x.get('s')}")
                if ent:
                    x["bw"] = ent["w"]
                q = got.get(skey(x))
                if q:
                    x["bq"] = q
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1))
    BDB.write_text(json.dumps(bdb, ensure_ascii=False, indent=1))
    print(f"BDB senses: {tin:,} in + {tout:,} out, ${(tin * pin + tout * pout) / 1e6:.2f}. {stats}")


if __name__ == "__main__":
    {"fetch": fetch, "build": build, "submit": submit, "harvest": harvest}[sys.argv[1]]()
