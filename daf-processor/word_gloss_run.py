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
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import anthropic
from dotenv import load_dotenv

from word_gloss_pilot import HERE, MODELS, SYSTEM as GLOSS_SYSTEM, amud_lines, prompt

load_dotenv(HERE / ".env", override=True)
RUN = HERE / "outline" / "word_gloss" / os.environ.get("WG_RUN", "run2")   # run3: gloss rule + entry fixes; run4: entries by dictionary form
CACHE = HERE / "outline" / "word_gloss" / "dict_full.json"   # Jastrow and Klein ("lex": "J" / "K")
AMUDIM = [("Bava Kamma", "10b"), ("Sanhedrin", "37a"), ("Ketubot", "17a"), ("Hullin", "88a")]
if RUN.name >= "run5":   # four more, mostly the Gemara's own Aramaic and no Mishnah, for a second test set
    AMUDIM += [("Gittin", "56a"), ("Bava Kamma", "27b"), ("Kiddushin", "45b"), ("Menachot", "29b")]
ENTRY_MODEL = "sonnet"
GKS = [k for k in os.environ.get("WG_GLOSS", ",".join(MODELS)).split(",") if k in MODELS]   # gloss pipelines to run
ONLY = json.loads(open(os.environ["WG_ONLY"]).read()) if os.environ.get("WG_ONLY") else None   # targeted rerun
NIK = re.compile(r"[֑-ׇ\"'׳״]")
TAGS = re.compile(r"<[^>]+>")
FIN = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
MAX_CANDS = 12
SENSE_CHARS = 320
# Prepositions with a pronoun suffix, and the possessive דיד-: Jastrow has no entry that helps a reader here (only the
# bare prefix or a "v." pointer), so these show the gloss alone.
GLOSS_ONLY = {"לי", "לך", "ליך", "ליה", "לה", "לן", "לכו", "לכון", "להו", "להון", "להם", "לו", "לנו", "לכם",
              "בי", "בך", "ביה", "בה", "בן", "בכו", "בהו", "בהון", "בו", "בם", "בהם",
              "מיניה", "מינה", "מינאי", "מינך", "מינן", "מינייהו", "מינהון", "ממנו", "ממנה",
              "דידי", "דידך", "דידיה", "דידה", "דידן", "דידכו", "דידהו", "עליה", "עלה", "עלייהו", "עלן", "עלי"}


def gloss_only(w):
    w = plain(w)
    # only the prefixes that come before these forms (ולה, דליה, לדידיה): stripping כ or מ would make כלה into לה
    return any(f in GLOSS_ONLY for f in [w] + [w[k:] for k in (1, 2) if all(c in "ודבל" for c in w[:k])])


TITLES = {"רב", "רבי", "רבן"}
TITLE_NOTE = " (title before a sage's name)"


def is_title(ws, glosses, i):
    """רב / רבי / רבן (with a prefix like ד ו ל כ) when the next word is a name: the reader needs no entry for the title.
    Without a name after it the word is a person (Rav, Rebbe) and keeps its entry."""
    w = plain(ws[i])
    stem = next((w[k:] for k in (0, 1, 2) if w[k:] in TITLES and all(c in "ודלכמשב" for c in w[:k])), None)
    if not stem or i + 1 >= len(ws):
        return False
    nxt = (glosses[i + 1].get("g") or "").strip()
    return bool(nxt) and nxt[0].isupper()


def plain(w):
    return NIK.sub("", w or "")


def fin(w):
    return w[:-1] + FIN[w[-1]] if len(w) > 1 and w[-1] in FIN else w


SUFFIXES = ("ייהו", "יהון", "יהו", "הון", "יה", "א")


def wforms(w):
    """The word, its forms without 1-2 prefix letters (and without the Aramaic present-tense ק / קא), and each of
    those without its inner yod or vav (Jastrow often spells defectively: נבילה -> נבלה)."""
    base = [w]
    for k in (1, 2):
        if len(w) - k >= 2 and all(c in "ודהבלמשכ" for c in w[:k]):
            base.append(fin(w[k:]))
    # then without the Aramaic final -א (Jastrow heads קְרָב, קְרָבָא under קרב) or a pronoun suffix (ידיה -> יד);
    # these come after the word as written, so a root alef or heh (קרא, אתא) is still found first
    for b in list(base):
        for suf in SUFFIXES:
            if b.endswith(suf) and len(b) - len(suf) >= (3 if suf == "א" else 2):
                base.append(fin(b[:-len(suf)]))
    # last, without the present-tense ק / קא (a word that merely starts with ק, like קרבא, finds its entry above)
    for b in list(base):
        if b.startswith("קא") and len(b) >= 5:
            base.append(b[2:])
        elif b.startswith("ק") and len(b) >= 4:
            base.append(b[1:])
    out = []
    for b in base:
        for f in (b, b[0] + b[1:-1].replace("י", "") + b[-1] if len(b) > 3 else b,
                  b[0] + b[1:-1].replace("ו", "") + b[-1] if len(b) > 3 else b):
            if f not in out and len(f) >= 2:
                out.append(f)
    return out



# Common Hebrew words that need no dictionary entry; the gloss alone serves the reader.
HEB_COMMON = {"היה", "היו", "הוא", "היא", "הם", "הן", "זה", "זו", "זאת", "אלו", "אלה", "אשר", "את", "אותו", "אותה",
              "אותם", "של", "על", "אל", "עם", "כל", "לא", "אין", "יש", "כי", "אם", "או", "גם", "אף", "מה", "כן", "הרי",
              "אלא", "אחד", "אחת", "אמר", "אמרו", "אומר", "אני", "אנו", "אתה", "אנחנו", "עד", "אבל"}


def heb_common(w):
    w = plain(w)
    return any(f in HEB_COMMON for f in [w] + [w[k:] for k in (1, 2) if all(c in "ושהדבלמ" for c in w[:k])])


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
        return q, [{"hw": e["headword"], "lex": "J" if "Jastrow" in e["parent_lexicon"] else "K", "senses": sense_text(e),
                    "ptr": pointer(e), "near": near(e)}
                   for e in es if isinstance(e, dict) and re.search(r"Jastrow|Klein", e.get("parent_lexicon", ""))]
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


def candidates(word, lemma, cache, hebrew=False):
    """Jastrow candidates; for a Hebrew word Klein's entries after them (up to 3 more), for terms Jastrow lacks or defines worse."""
    out, seen = [], set()

    def add(e, via=None, own=False):
        key = e.get("lex", "J") + e["hw"]
        if key not in seen and len(out) < MAX_CANDS:
            seen.add(key)
            out.append({"hw": e["hw"], "lex": e.get("lex", "J"), "senses": e["senses"], "via": via, "own": own})

    def filled(es):
        """Jastrow's Aramaic entry that says only "ch. same" comes with no English: give it the senses of the entry
        above it with the same spelling, marked as its Aramaic form."""
        out_, prev = [], None
        for e in es or []:
            if e.get("lex", "J") == "J" and not e["senses"] and prev and \
                    plain(prev["hw"]).rstrip(" I²³") == plain(e["hw"]).rstrip(" I²³"):
                e = dict(e, senses="(Aramaic, ch.) same as the entry above: " + prev["senses"])
            out_.append(e)
            if e.get("lex", "J") == "J" and e["senses"]:
                prev = e
        return out_

    full = cache

    class Filled:
        def get(self, q):
            return filled(full.get(q))
    cache = Filled()
    own = wforms(plain(word))
    qs = own + ([fin(plain(lemma))] if lemma and fin(plain(lemma)) not in own else [])
    for q in qs:
        for e in cache.get(q) or []:
            if e.get("lex", "J") != "J":
                continue
            add(e, own=q in own and not e["hw"].rstrip(" I²³").endswith("־"))
            if e.get("ptr"):
                for t in cache.get(e["ptr"]) or []:
                    if t.get("lex", "J") == "J" and plain(t["hw"]).startswith(e["ptr"]):
                        add(t, e["hw"])
            if e.get("near"):
                for t in cache.get(plain(e["near"])) or []:
                    if t.get("lex", "J") == "J" and t["hw"] == e["near"]:
                        add(t, e["hw"])
    if hebrew:   # Klein after Jastrow (Jastrow's Hebrew entries are written for the Talmud), with room of its own
        cap = len(out) + 3
        for q in qs:
            for e in cache.get(q) or []:
                if e.get("lex") == "K" and len(out) < cap:
                    key = "K" + e["hw"]
                    if key not in seen:
                        seen.add(key)
                        out.append({"hw": e["hw"], "lex": "K", "senses": e["senses"], "via": None, "own": q in own})
    return out


# ---------- 3. entries ----------

ENTRY_SYSTEM = """You link words of the Babylonian Talmud to the right entry in Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi, for English-speaking learners who tap a word and see the entry.

Each item is one dictionary form with all its uses in the passage: every distinct word (without vowels) built on it, with the English gloss already decided for that word in its line, a few words of the line around it, and its language (Hebrew or Aramaic). The item's suggested dictionary form is only a hint: it can be wrong, and sometimes names the word's equivalent in the other language (the Hebrew שבר for the Aramaic תבר). Then numbered candidate Jastrow entries, each with its senses (English only, citations removed; verb stems such as Pa., Ithpe., Hif. label the senses that follow). Jastrow often has several entries with one spelling (numbered I, II, III), and separate Hebrew and Aramaic ("ch.") entries for the same word.

For each use, choose the entry that defines the word in the sense of its gloss:
- be consistent: uses with the same meaning in the same language get the same entry; give different entries only when the meaning or the language really differs;
- the language decides between a Hebrew and an Aramaic entry: each use is marked Hebrew or Aramaic. A Hebrew use gets Jastrow's Hebrew entry, which is written for the word's use in the Talmud; choose a Klein entry (Klein's dictionary of biblical and rabbinic Hebrew; those candidates are marked "Klein:") only when Jastrow has no entry that fits, or when Klein's clearly fits the gloss better (a word in a quoted verse is moved to Klein afterwards, so need not be judged here); an Aramaic use gets Jastrow's Aramaic ("ch.") entry when Jastrow has both, and never a Klein entry. The two are often spelled differently (Hebrew שָׁנָה, Aramaic תְּנֵי; Hebrew זָקֵן, Aramaic סָב): an Aramaic use of תני takes תְּנֵי, not the Hebrew entry;
- the part of speech follows the gloss: a verb gets the verb's entry, not a noun from the same root (תנא "taught" is תְּנֵי, while תנא "a Tanna" is תַּנָּא);
- prefer an entry found from the word itself as written (marked "from the word") when one fits; turn to the suggested form's entry only when none of those fits;
- the entry for the word's root or base form, not one for a prefix letter alone, and not a different word that shares the spelling;
- read all the senses: the sense that fits may come late in an entry;
- go by the gloss, not the spelling alone: an entry that matches the word letter for letter is wrong if it defines another meaning (לְעוֹלָם "forever" for ולעולם glossed "and in the world", in עולם הבא);
- an entry that only refers elsewhere ("v. X") is acceptable only if its target is not among the candidates; prefer the target (marked "via").
If no candidate fits a use, answer 0 for it.

Reply with one JSON object and nothing else: {"choices": {"<use id>": <candidate number or 0>, ...}} with every use id, e.g. "12a"."""

CTX = 4


def line_langs(t, a):
    """'Mishnah' for lines inside a mishna on this amud, else None (the model judges from the context)."""
    out, inm = {}, False
    for s in amud_lines(t, a):
        en = s.get("en") or ""
        if "MISHNA" in en[:12]:
            inm = True
        elif "GEMARA" in en[:12]:
            inm = False
        out[str(s["n"])] = "Mishnah (Hebrew)" if inm else None
    return out


def group_key(w, lemma):
    lem = fin(plain(lemma))
    return lem if len(lem) >= 2 else plain(w)


def items_for(gk, meta, glosses, cache):
    """Distinct (word, gloss) items for one gloss model, with candidates and where they occur, plus groups: the items
    sharing a dictionary form, which the entry step decides together."""
    items, where, groups = {}, {}, {}
    for c, m in meta.items():
        langs = line_langs(m["tractate"], m["amud"])
        for n, ws in m["words"].items():
            g = (glosses[gk].get(c) or {}).get(n) or []
            if len(g) != len(ws):
                continue
            for i, w in enumerate(ws):
                gl, lem = g[i].get("g", ""), g[i].get("lemma", "")
                lang = {"he": "Hebrew", "ar": "Aramaic"}.get(g[i].get("l")) or langs.get(n)
                hebrew = (lang or "").startswith(("Hebrew", "Mishnah"))
                title = is_title(ws, g, i)
                if title and TITLE_NOTE not in gl:
                    gl += TITLE_NOTE
                key = f"{plain(w)}|{gl.lower().strip()}"
                where[f"{c}:{n}:{i}"] = key
                if key not in items:
                    ctx = " ".join(plain(x) for x in ws[max(0, i - CTX):i]) + " [" + plain(w) + "] " + \
                          " ".join(plain(x) for x in ws[i + 1:i + 1 + CTX])
                    skip = gloss_only(w) or title or (hebrew and heb_common(w))
                    items[key] = {"w": plain(w), "lemma": lem, "g": gl, "ctx": ctx.strip(), "lang": lang,
                                  "cands": [] if skip else candidates(w, lem, cache, hebrew)}
                    if items[key]["cands"]:
                        groups.setdefault(group_key(w, lem), []).append(key)
    return items, where, groups


def group_cands(keys, items):
    out, seen = [], set()
    for k in keys:   # own-word candidates first, then the rest
        for own in (True, False):
            for x in items[k]["cands"]:
                if bool(x.get("own")) == own and ref(x) not in seen:
                    seen.add(ref(x))
                    out.append(x)
    return out[:2 * MAX_CANDS]


def ref(x):
    """How a chosen entry is stored: Jastrow's headword, or "K:" + Klein's."""
    return ("K:" if x.get("lex") == "K" else "") + x["hw"]


def entry_build(chunk=50):
    meta = json.loads((RUN / "meta.json").read_text())
    glosses = {k: json.loads((RUN / f"gloss_{k}.json").read_text()) for k in MODELS}
    cache = json.loads(CACHE.read_text())
    model, pin, _ = MODELS[ENTRY_MODEL]
    client = anthropic.Anthropic()
    plan = {}
    for gk in GKS:
        items, where, groups = items_for(gk, meta, glosses, cache)
        if ONLY:
            groups = {g: ks for g, ks in groups.items() if g in ONLY["groups"]}
        ids, gcands, blocks = {}, {}, []
        for gi, (lem, keys) in enumerate(sorted(groups.items())):
            cs = group_cands(keys, items)
            gcands[str(gi + 1)] = [ref(x) for x in cs]
            uses = []
            for j, k in enumerate(keys):
                uid = f"{gi + 1}{chr(97 + j) if j < 26 else 'z' + str(j)}"
                ids[k] = uid
                v = items[k]
                uses.append(f"  {uid}) {v['w']} = \"{v['g']}\"" + (f" [{v['lang']}]" if v["lang"] else "") +
                            f" — in: {v['ctx']}")
            blocks.append((len(keys), f"[{gi + 1}] suggested form {lem}\nUses:\n" + "\n".join(uses) + "\nCandidates:\n" +
                           "\n".join(f"  {j + 1}. {'Klein: ' if x.get('lex') == 'K' else ''}{x['hw']}{' (via ' + x['via'] + ')' if x['via'] else ''}"
                                      f"{' (from the word)' if x.get('own') else ''} — {x['senses'] or '(no English given)'}"
                                      for j, x in enumerate(cs))))
        reqs, cur, n = [], [], 0
        for size, b in blocks:   # whole groups per request, about `chunk` uses each
            if cur and n + size > chunk:
                reqs.append(cur)
                cur, n = [], 0
            cur.append(b)
            n += size
        if cur:
            reqs.append(cur)
        reqs = [{"custom_id": f"{gk}__{r}", "params": {
            "model": model, "max_tokens": 16000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"},
            "system": ENTRY_SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(bs)}]}} for r, bs in enumerate(reqs)]
        plan[gk] = {"items": items, "where": where, "ids": ids, "gcands": gcands}
        (RUN / f"entry_requests_{gk}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
        tin = sum(client.messages.count_tokens(model=model, system=ENTRY_SYSTEM, messages=r["params"]["messages"]).input_tokens
                  for r in reqs)
        print(f"{gk} glosses: {len(items)} distinct word+gloss in {len(groups)} groups, {len(reqs)} requests, "
              f"{tin:,} input tokens (${tin * pin / 1e6:.2f})")
    (RUN / "entry_plan.json").write_text(json.dumps(plan, ensure_ascii=False))


def entry_submit():
    client = anthropic.Anthropic()
    state = RUN / "entry_batch.json"
    if not state.exists():
        reqs = [json.loads(l) for gk in GKS for l in (RUN / f"entry_requests_{gk}.jsonl").read_text().splitlines()]
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
            cands = plan[gk]["gcands"].get(re.match(r"\d+", str(iid)).group(0), []) if k else []
            if isinstance(j, int) and 1 <= j <= len(cands):
                chosen[gk][k] = cands[j - 1]
    (RUN / "entries.json").write_text(json.dumps(chosen, ensure_ascii=False))
    # per running word: the entry each pipeline shows
    same = diff = none = 0
    keys = set(plan["sonnet"]["where"]) & set(plan["haiku"]["where"]) if len(plan) > 1 else set()
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



# ---------- 4. senses: where in a long entry the word's sense begins ----------

ENTRIES = HERE / "outline" / "word_gloss" / "jastrow_entries.json"
SHORT_ENTRY = 500      # an entry this short is shown whole; no pointer needed
ENTRY_CHARS = 6000     # longer entries are cut here for the model (a sense past this point gets no pointer)

SENSE_SYSTEM = """You help English-speaking learners of the Babylonian Talmud who tap a word and see its entry in Jastrow's Dictionary. Long entries cover many senses; the page will open the entry at the sense that fits the word in its line.

Each item gives a word from the Gemara (without vowels), the English gloss already decided for it in its line, a few words of the line around it, and the full text of the Jastrow entry chosen for it (citations included).

For each item:
- "q": copy, character for character, a short phrase from the entry (3 to 8 words) where the sense that fits the gloss begins: a sense number with its first words ("2) to say"), a form marker with its form ("Pl. רַבָּנָן", "Pa. אַמֵּר"), or the first words of the sense's English. Use "" if the sense that fits is the entry's opening sense.
  Point to the sense that matches the gloss; if two senses match about equally well, choose the earlier one. Choose by what the word means here, not by the passage's topic: a general word in a specialized context keeps its general sense (ספר "scroll" in a passage about a Torah scroll is "book, document", not the sense for ס׳ תורה). An idiom the entry lists (נָיְחָא נפשיה "his soul rested", i.e. he died) is the sense to point to when the gloss is that idiom. Prefer the plain, literal sense over a figurative or extended one ("to crumble" over "to refute"; "to see, assess" over "to regard as") unless the gloss itself is figurative.
- "fit": "yes" if some sense of this entry fits the word as glossed; "no" if none does (the entry is probably the wrong one for this word). Judge the word without its prefix letters (ד, ו, ב, ל, ה, מ, ש, כ): the gloss includes their meaning ("of what" for דמאי), the entry does not. A gloss that is a person's name (Rav, Kahana) fits an entry that lists the name or the title it comes from.

Reply with one JSON object and nothing else: {"senses": {"<item id>": {"q": "...", "fit": "yes"}, ...}}"""


def entry_text(e):
    out = []

    def walk(ss):
        for x in ss or []:
            d = re.sub(r"\s+", " ", TAGS.sub("", x.get("definition") or "")).strip()
            if d:
                out.append(((x.get("number") or "") + " " + d).strip())
            walk(x.get("senses"))
    walk((e.get("content") or {}).get("senses"))
    return " ".join(out)


def fetch_entries(hws):
    cache = json.loads(ENTRIES.read_text()) if ENTRIES.exists() else {}

    def get(hw):
        q = re.sub(r"\s+[IVX]+$|\s*[¹²³⁴]$", "", plain(hw.removeprefix("K:"))).replace("־", "")
        try:
            url = "https://www.sefaria.org/api/words/" + urllib.parse.quote(q) + "?never_split=0"
            with urllib.request.urlopen(url, timeout=30) as f:
                es = json.load(f)
            lex = "Klein" if hw.startswith("K:") else "Jastrow"
            hit = next((e for e in es if isinstance(e, dict) and lex in e.get("parent_lexicon", "")
                        and e.get("headword") == hw.removeprefix("K:")), None)
            return hw, entry_text(hit) if hit else None
        except Exception:
            return hw, None
    todo = sorted(h for h in hws if h not in cache)
    with ThreadPoolExecutor(8) as ex:
        for hw, t in ex.map(get, todo):
            if t is not None:
                cache[hw] = t
    ENTRIES.write_text(json.dumps(cache, ensure_ascii=False))
    return cache


def sense_items(gk):
    plan = json.loads((RUN / "entry_plan.json").read_text())[gk]
    chosen = json.loads((RUN / "entries.json").read_text())[gk]
    texts = fetch_entries(set(chosen.values()))
    items = {}
    for k, hw in chosen.items():
        t = texts.get(hw)
        if not t or len(t) <= SHORT_ENTRY:
            continue
        v = plan["items"][k]
        items[f"{hw}|{v['g'].lower().strip()}"] = {"hw": hw, "w": v["w"], "g": v["g"], "ctx": v.get("ctx", ""), "text": t}
    return items, texts


SENSE_MODEL = os.environ.get("WG_SENSE_MODEL", "sonnet")
SFX = "" if SENSE_MODEL == "sonnet" else "_" + SENSE_MODEL


def sense_build(gk="sonnet", chunk=12):
    items, _ = sense_items(gk)
    if ONLY:
        items = {k: v for k, v in items.items() if k in set(ONLY["senses"])}
    keys = sorted(items)
    model, pin, _ = MODELS[SENSE_MODEL]
    reqs = []
    for s in range(0, len(keys), chunk):
        text = []
        for j, k in enumerate(keys[s:s + chunk]):
            v = items[k]
            text.append(f"[{s + j + 1}] {v['w']} = \"{v['g']}\" — in: {v['ctx']}\nEntry {v['hw']}: {v['text'][:ENTRY_CHARS]}")
        reqs.append({"custom_id": f"{gk}__{s // chunk}", "params": {
            "model": model, "max_tokens": 8000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
            "system": SENSE_SYSTEM, "messages": [{"role": "user", "content": "\n\n".join(text)}]}})
    (RUN / f"sense_requests_{gk}{SFX}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))
    (RUN / f"sense_plan_{gk}.json").write_text(json.dumps({"keys": keys, "items": items}, ensure_ascii=False))
    client = anthropic.Anthropic()
    tin = sum(client.messages.count_tokens(model=model, system=SENSE_SYSTEM, messages=r["params"]["messages"]).input_tokens
              for r in reqs)
    print(f"{gk}: {len(items)} long entry+gloss pairs, {len(reqs)} requests, {tin:,} input tokens (${tin * pin / 1e6:.2f})")


def sense_submit(gk="sonnet"):
    client = anthropic.Anthropic()
    state = RUN / f"sense_batch_{gk}{SFX}.json"
    if not state.exists():
        reqs = [json.loads(l) for l in (RUN / f"sense_requests_{gk}{SFX}.jsonl").read_text().splitlines()]
        state.write_text(json.dumps({"id": client.messages.batches.create(requests=reqs).id}))
    batch_wait(client, {"senses": json.loads(state.read_text())["id"]})


def norm_ws(t):
    return re.sub(r"\s+", " ", t).strip()


def sense_harvest(gk="sonnet"):
    client = anthropic.Anthropic()
    sp = json.loads((RUN / f"sense_plan_{gk}.json").read_text())
    keys, items = sp["keys"], sp["items"]
    bid = json.loads((RUN / f"sense_batch_{gk}{SFX}.json").read_text())["id"]
    _, pin, pout = MODELS[SENSE_MODEL]
    tin = tout = 0
    out, stats = {}, {"pointer": 0, "opening": 0, "not found": 0, "no fit": 0, "missing": 0}
    for r in client.messages.batches.results(bid):
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
            q, fit = norm_ws(a.get("q") or ""), a.get("fit") == "yes"
            text = norm_ws(items[k]["text"])
            at = text.find(q) if q else 0
            rec = {"fit": fit}
            if q and at > 0:
                rec["q"] = q
            out[k] = rec
            stats["no fit" if not fit else "pointer" if "q" in rec else "not found" if q and at < 0 else "opening"] += 1
    stats["missing"] = len(keys) - len(out)
    (RUN / f"senses_{gk}{SFX}.json").write_text(json.dumps(out, ensure_ascii=False))
    line = f"Senses ({gk} pipeline, {SENSE_MODEL}): {tin:,} in + {tout:,} out, ${(tin * pin + tout * pout) / 1e6:.2f}. {stats}"
    with open(RUN / "report.md", "a") as f:
        f.write(line + "\n")
    print(line)
    for k, v in out.items():
        if not v["fit"]:
            print("  no fit:", k)



# ---------- 5. retry: a second choice where the sense step found no fitting sense ----------

RETRY_SYSTEM = """You link words of the Babylonian Talmud to the right dictionary entry (Jastrow's Dictionary of the Targumim, Talmud Babli and Yerushalmi, or Klein's dictionary of Hebrew for Hebrew words), for English-speaking learners who tap a word and see the entry.

Each item gives a word from the Gemara (without vowels), its language, the English gloss already decided for it in its line, a few words of the line around it, and numbered candidate entries with their senses. An entry chosen earlier for this word was checked and found to have no sense that fits the gloss; it is listed as rejected. Choose the candidate that defines this word in the sense of its gloss, or 0 if none does: answering 0 is better than a wrong entry, since the reader will then see the gloss alone.

Reply with one JSON object and nothing else: {"choices": {"<item id>": <candidate number or 0>, ...}}"""


def retry_build():
    reqs, rplan = [], {}
    for gk in GKS:
        plan = json.loads((RUN / "entry_plan.json").read_text())[gk]
        chosen = json.loads((RUN / "entries.json").read_text())[gk]
        senses = json.loads((RUN / f"senses_{gk}.json").read_text())
        bad = {k for k, v in senses.items() if not v["fit"]}
        todo = [k for k, hw in chosen.items() if f"{hw}|{plan['items'][k]['g'].lower().strip()}" in bad]
        rplan[gk] = {}
        text = []
        for j, k in enumerate(todo):
            v = plan["items"][k]
            cs = [x for x in v["cands"] if ref(x) != chosen[k]]
            rplan[gk][str(j + 1)] = {"key": k, "cands": [ref(x) for x in cs], "rejected": chosen[k]}
            text.append(f"[{j + 1}] {v['w']} ({v.get('lang') or 'language not marked'}) = \"{v['g']}\" — in: {v['ctx']}\n"
                        f"  rejected: {chosen[k].removeprefix('K:')}\n" + "\n".join(
                f"  {n + 1}. {'Klein: ' if x.get('lex') == 'K' else ''}{x['hw']} — {x['senses'] or '(no English given)'}"
                for n, x in enumerate(cs)))
        if text:
            reqs.append({"custom_id": gk, "params": {
                "model": MODELS["sonnet"][0], "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "medium"}, "system": RETRY_SYSTEM,
                "messages": [{"role": "user", "content": "\n\n".join(text)}]}})
        print(f"{gk}: {len(todo)} words to choose again")
    (RUN / "retry_plan.json").write_text(json.dumps(rplan, ensure_ascii=False))
    (RUN / "retry_requests.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs))


def retry_submit():
    client = anthropic.Anthropic()
    state = RUN / "retry_batch.json"
    if not state.exists():
        reqs = [json.loads(l) for l in (RUN / "retry_requests.jsonl").read_text().splitlines()]
        state.write_text(json.dumps({"id": client.messages.batches.create(requests=reqs).id}))
    batch_wait(client, {"retry": json.loads(state.read_text())["id"]})


def retry_harvest():
    """entries_final.json: entries.json with the second choices applied; a word with no fitting entry is dropped
    (the reader sees its gloss alone) and listed under "dropped"."""
    client = anthropic.Anthropic()
    rplan = json.loads((RUN / "retry_plan.json").read_text())
    final = json.loads((RUN / "entries.json").read_text())
    bid = json.loads((RUN / "retry_batch.json").read_text())["id"]
    _, pin, pout = MODELS["sonnet"]
    tin = tout = 0
    dropped, changed = {gk: [] for gk in rplan}, {gk: 0 for gk in rplan}
    for r in client.messages.batches.results(bid):
        gk = r.custom_id
        if r.result.type != "succeeded":
            print("failed:", gk)
            continue
        m = r.result.message
        tin += m.usage.input_tokens
        tout += m.usage.output_tokens
        ch = (parse_json("".join(b.text for b in m.content if b.type == "text")) or {}).get("choices", {})
        for iid, it in rplan[gk].items():
            j = ch.get(iid)
            if isinstance(j, int) and 1 <= j <= len(it["cands"]):
                final[gk][it["key"]] = it["cands"][j - 1]
                changed[gk] += 1
            else:
                final[gk].pop(it["key"], None)
                dropped[gk].append(it["key"])
    final["dropped"] = dropped
    (RUN / "entries_final.json").write_text(json.dumps(final, ensure_ascii=False))
    line = (f"Retry: {tin:,} in + {tout:,} out, ${(tin * pin + tout * pout) / 1e6:.2f}. "
            f"New entry: {changed}; gloss alone: { {k: len(v) for k, v in dropped.items()} }")
    with open(RUN / "report.md", "a") as f:
        f.write(line + "\n")
    print(line)



# ---------- 6. fix: local checks after the model steps (no API) ----------
# Proper names: a gloss that is a name ("Kahana", "Neharde'a") keeps its entry only if the entry is the name's own
# (Jastrow's "pr. n." / "name of", or an entry opening with the name); else it moves to a name entry spelled like the
# word, or shows the gloss alone, marked as a name. Hebrew words: a Jastrow entry gives way to Klein's entry for the same
# word when the word is in a verse quote. Last, corrections.json (found in review) overrides both.

CORRECTIONS = HERE / "outline" / "word_gloss" / "corrections.json"
BASE_RUN = os.environ.get("WG_BASE")   # an earlier full run whose senses a targeted rerun's senses are laid over
LATIN = re.compile(r"[A-Za-zÀ-ɏḀ-ỿʿ'’]{2,}")
NAME_MARK = re.compile(r"\bpr\. ?n\.|\bn\. ?pr\.|\bnames? of\b")
NOT_NAMES = {"jew", "jews", "jewish", "god", "lord", "holy", "blessed", "torah", "mishnah", "mishna", "gemara", "sages",
             "sage", "rabbis", "rabbinic", "merciful", "heaven", "shabbat", "sabbath", "temple", "israelite", "israelites",
             "levite", "levites", "priest", "priests", "tanna", "tannaim", "amora", "amoraim", "baraita", "halakha",
             "shema", "passover", "pesach", "festival", "festivals", "amen", "ark", "sanhedrin", "scripture", "written",
             "oral", "law", "master", "creator", "omnipresent", "almighty", "one", "he", "him", "his", "i", "me", "my",
             "mine", "you", "your", "yours", "thou", "thee", "thy", "who", "whom", "house", "west", "east", "sanctuary",
             "king", "nasi", "yah", "name", "presence", "shekhinah"}
def skel(t):
    """A transliteration's consonant skeleton, so Yochanan = Johanan, Nehardea = N'hard'ʿa, Rav = Rab."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if c.isascii() and c.isalpha())
    for a, b in (("ch", "h"), ("kh", "h"), ("sh", "s"), ("th", "t"), ("ph", "f"), ("tz", "ts"), ("j", "y"), ("w", "v"),
                 ("v", "b"), ("k", "c"), ("q", "c")):
        t = t.replace(a, b)
    t = re.sub(r"[aeiou]", "", t)
    return re.sub(r"(.)\1+", r"\1", t)


def name_tokens(g):
    toks = re.findall(r"\b[A-Z][A-Za-z'’ḥḤṭṣʿ]+", g)
    # no English-dictionary filter: glosses are lowercase, so a capital marks a name even when the word is also
    # English (Cain, Bag); the exceptions are the capitalized nouns and divine pronouns listed in NOT_NAMES
    return [t for t in toks if t.lower() not in NOT_NAMES and t.lower().rstrip("s") not in NOT_NAMES]


def sk_match(a, b):
    a, b = skel(a), skel(b)
    n = min(3, len(a), len(b))
    return bool(a) and (a == b or (n >= 2 and a[:n] == b[:n]) or (n >= 3 and a[-3:] == b[-3:]))


def name_entry(text, toks, strict=False):
    """Where the name's sense begins in an entry (0 for the opening), or None if the entry is not the name's.
    strict: only an entry that opens with the name itself (for moving a word to another entry)."""
    if not text:
        return None
    lead = re.sub(r"^\([^)]*\)\s*", "", text)
    if any(w[0].isupper() and sk_match(w, t) for w in LATIN.findall(lead[:60])[:3] for t in toks):
        return 0
    if strict:
        return None
    for m in NAME_MARK.finditer(text):
        if m.start() < 150:
            return 0
        # the name that follows, every word of it ("Resh Maya" is not "Reish"; "Ḥăninah (Love)" is not "Hanina")
        run = []
        for w in LATIN.findall(text[m.end():m.end() + 80]):
            if w in ("pl", "pr", "m", "f"):
                continue
            if not w[0].isupper():
                break
            run.append(w)
        if run and all(any(sk_match(w, t) for t in toks) for w in run[:3]):
            return m.start()
    return None


def bare(hw):
    return re.sub(r"[\s*IVX¹²³⁴ᴵⱽ]+$|^\*", "", plain(hw.removeprefix("K:"))).replace("־", "").strip()


def quoted(he):
    """Indices of the words inside ״…״ in a line of the Hebrew text: the Gemara's verse quotes (an abbreviation's ״
    sits between letters and opens nothing)."""
    out, inside = set(), False
    for i, t in enumerate(x for x in he.split() if re.search(r"[א-ת]", x)):
        letters = [j for j, c in enumerate(t) if "א" <= c <= "ת"]
        if "״" in t[:letters[0]]:
            inside = True
        if inside:
            out.add(i)
        if "״" in t[letters[-1] + 1:]:
            inside = False
    return out


def in_verse(where):
    """Item keys with at least one occurrence inside a verse quote."""
    meta = json.loads((RUN / "meta.json").read_text())
    qs, out = {}, set()
    for pos, k in where.items():
        c, n, i = pos.rsplit(":", 2)
        if c not in qs:
            qs[c] = {str(x["n"]): quoted(x.get("he") or "") for x in amud_lines(meta[c]["tractate"], meta[c]["amud"])}
        if int(i) in qs[c].get(n, ()):
            out.add(k)
    return out


def fix():
    gk = "sonnet"
    plan = json.loads((RUN / "entry_plan.json").read_text())[gk]
    final = json.loads((RUN / "entries_final.json").read_text())
    entries = dict(final[gk])
    senses = json.loads((HERE / "outline" / "word_gloss" / BASE_RUN / f"senses_{gk}.json").read_text()) if BASE_RUN else {}
    senses.update(json.loads((RUN / f"senses_{gk}.json").read_text()))
    corr = json.loads(CORRECTIONS.read_text()) if CORRECTIONS.exists() else {"entries": {}, "senses": {}}
    items = plan["items"]
    gl = lambda k: items[k]["g"].lower().strip()
    names, log = [], []
    named = {k: name_tokens(v["g"]) for k, v in items.items() if v["cands"] and not v["g"].endswith(TITLE_NOTE)}
    named = {k: t for k, t in named.items() if t}
    texts = fetch_entries({entries[k] for k in named if entries.get(k)} |
                          {ref(x) for k in named for x in items[k]["cands"] if x.get("lex") == "J"})
    for k, toks in sorted(named.items()):
        hw = entries.get(k)
        at = name_entry(texts.get(hw), toks) if hw else None
        if at is not None:
            if at:   # a name sense inside a longer entry: open the entry there
                senses[f"{hw}|{gl(k)}"] = {"fit": True, "q": norm_ws(texts[hw])[at:at + 40].rsplit(" ", 1)[0]}
            continue
        w = plain(items[k]["w"])
        forms = {w} | {fin(w[n:]) for n in (1, 2) if len(w) - n >= 2 and all(c in "ודבלכמשה" for c in w[:n])}
        new = next((ref(x) for x in items[k]["cands"] if x.get("lex") == "J" and bare(x["hw"]) in forms
                    and name_entry(texts.get(ref(x)), toks, strict=True) == 0), None)
        log.append(f"name  {k}: {hw} -> {new or '(gloss alone, a name)'}")
        if new:
            entries[k] = new
        else:
            entries.pop(k, None)
            names.append(k)
    # Klein for words of a verse quote only: elsewhere Jastrow's entry, written for the Talmud's usage, is kept
    # unless the entry step judged Klein the better match
    verse = in_verse(plan["where"])
    for k, hw in list(entries.items()):
        v = items.get(k)
        if not v or k in named or hw.startswith("K:") or k not in verse:
            continue
        pts = lambda h: re.sub(r"[\u0591-\u05AF\u05BD\u05C0\u05C3]|[\sIVX¹²³⁴ᴵⱽ*]+$|^\*", "", h.removeprefix("K:"))
        js = next((x["senses"] for x in v["cands"] if ref(x) == hw), "")
        verb = bool(re.match(r"[^;]{0,40}?\bto [a-z]", js or ""))
        ks = [ref(x) for x in v["cands"] if x.get("lex") == "K" and bare(x["hw"]) == bare(hw)
              and (pts(x["hw"]) == pts(hw) or (verb and pts(x["hw"]) == plain(pts(x["hw"]))))]   # same vowels, or a verb's root
        if len(ks) == 1:
            entries[k] = ks[0]
            log.append(f"klein {k}: {hw} -> {ks[0]}")
    for k, hw in corr.get("entries", {}).items():
        if k not in items:
            log.append(f"corr  {k}: not in this run")
            continue
        log.append(f"corr  {k}: {entries.get(k)} -> {hw}")
        if hw:
            entries[k] = hw
            if k in names:
                names.remove(k)
        else:
            entries.pop(k, None)
    for sk, q in corr.get("senses", {}).items():
        senses[sk] = {"fit": True, **({"q": q} if q else {})}
        log.append(f"sense {sk}: -> {q or '(opening)'}")
    (RUN / "final.json").write_text(json.dumps({"entries": entries, "senses": senses, "names": names},
                                               ensure_ascii=False))
    (RUN / "fix_log.txt").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    print(f"{len(entries)} entries, {len(names)} names shown as gloss alone, {len(log)} changes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gloss-build", "gloss-submit", "gloss-harvest", "cands",
                                    "entry-build", "entry-submit", "entry-harvest", "sense-build", "sense-submit",
                                    "sense-harvest", "retry-build", "retry-submit", "retry-harvest", "fix"])
    {"gloss-build": gloss_build, "gloss-submit": gloss_submit, "gloss-harvest": gloss_harvest, "cands": cands,
     "entry-build": entry_build, "entry-submit": entry_submit, "entry-harvest": entry_harvest,
     "sense-build": lambda: [sense_build(g) for g in GKS],
     "sense-submit": lambda: [sense_submit(g) for g in GKS],
     "sense-harvest": lambda: [sense_harvest(g) for g in GKS],
     "retry-build": retry_build, "retry-submit": retry_submit, "retry-harvest": retry_harvest, "fix": fix}[ap.parse_args().cmd]()
