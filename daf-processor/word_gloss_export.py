"""Word glossary -> the site: one file per amud, outline/word_gloss/site/<Tractate>_<amud>.json, which
build_prototype.py copies to the site's glossary/. No API.

Each file: {"lines": {"<line>": [word, ...]}} with one item per word of the line's Hebrew (the same words, in the same
order, as the passage window wraps them), each {"g": gloss, "e": entry ("K:" for Klein) or absent, "q": the phrase
where the sense begins, "name": 1 for a name shown as its gloss alone, "sage": slug in the Sages kit, "t": 1 for a
title before a name, "l": "he"/"ar", "b": BDB headword and "v": its verse, for a word of a verse quote, with "s" its Strong's number, "bw" the
word Sefaria finds it by and "bq" the start of the sense that fits}.

  WG_RUN=run7 WG_BASE=run5 venv/bin/python word_gloss_run.py fix     # first
  WG_RUN=run7 venv/bin/python word_gloss_export.py
"""
import json
import os
import re
from pathlib import Path

import word_gloss_run as W
from word_gloss_pilot import amud_lines

KIT = W.HERE.parent / "AnyMishnahWeb" / "reference-kit" / "sages" / "sages.json"
OUT = W.HERE / "outline" / "word_gloss" / "site"
WRAP = re.compile(r"[א-ת][א-ת֑-ׇ\"'׳״]*")   # app.html's wrapWords


def sage_index():
    """Plain Hebrew name -> sage slug: the sage whose own name it is before one who has it only as another spelling
    (רבא is Rava's name and an alternative for R. Abba), then the most quoted."""
    ss = json.loads(KIT.read_text())["sages"]
    by = {}
    for slug, s in ss.items():
        main_ = W.plain(s.get("he") or "").strip()
        for h in set(s.get("alt_he") or []) | {main_}:
            h = W.plain(h).strip()
            if h:
                by.setdefault(h, []).append((h != main_, s.get("tier") or 9, slug))
    return {h: sorted(v)[0][2] for h, v in by.items()}


def main():
    meta = json.loads((W.RUN / "meta.json").read_text())
    plan = json.loads((W.RUN / "entry_plan.json").read_text())["sonnet"]
    gl = json.loads((W.RUN / "gloss_sonnet.json").read_text())
    fx = json.loads((W.RUN / "final.json").read_text())
    names, sages = set(fx["names"]), sage_index()
    bdb_file = W.HERE / "outline" / "word_gloss" / "bdb.json"   # bdb_verses.py: BDB entries for words of verse quotes
    bdb = json.loads(bdb_file.read_text()) if bdb_file.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    for c, m in meta.items():
        lines = {str(x["n"]): x for x in amud_lines(m["tractate"], m["amud"])}
        out = {}
        for n, ws in m["words"].items():
            wrapped = WRAP.findall(re.sub(r"<[^>]+>", " ", lines[n]["he"]))
            if len(wrapped) != len(ws):
                print(f"  {c} line {n}: {len(wrapped)} words on the page, {len(ws)} glossed; skipped")
                continue
            row = []
            for i, w in enumerate(ws):
                g = (gl.get(c) or {}).get(n) or []
                k = plan["where"].get(f"{c}:{n}:{i}")
                it = plan["items"].get(k) if k else None
                if not it or len(g) != len(ws):
                    row.append({})
                    continue
                x = {"g": it["g"].replace(W.TITLE_NOTE, "")}
                if it["g"].endswith(W.TITLE_NOTE):
                    x["t"] = 1
                lang = g[i].get("l")
                if lang in ("he", "ar"):
                    x["l"] = lang
                hw = fx["entries"].get(k)
                if hw:
                    x["e"] = hw
                    q = (fx["senses"].get(f"{hw}|{it['g'].lower().strip()}") or {}).get("q")
                    if q:
                        x["q"] = q
                if k in names:
                    x["name"] = 1
                if W.name_tokens(it["g"]) and not x.get("t"):
                    p = W.plain(w)
                    for f in [p] + [p[j:] for j in (1, 2) if all(ch in "ודבלכמשה" for ch in p[:j])]:
                        if W.fin(f) in sages:
                            x["sage"] = sages[W.fin(f)]
                            break
                bx = bdb.get(c.replace(" ", "_"), {}).get(n, {}).get(str(i)) or \
                    bdb.get(f"{m['tractate'].replace(' ', '_')}_{m['amud']}", {}).get(n, {}).get(str(i))
                if bx:
                    x["b"], x["v"] = bx["b"], bx["v"]
                    for k in ("s", "bw", "bq"):   # Strong's number, the word to look it up by, sense pointer (bdb_senses.py)
                        if bx.get(k):
                            x[k] = bx[k]
                row.append(x)
            out[n] = row
        f = OUT / f"{m['tractate'].replace(' ', '_')}_{m['amud']}.json"
        f.write_text(json.dumps({"lines": out}, ensure_ascii=False, separators=(",", ":")))
        print(f"{f.name}: {len(out)} lines, {sum(len(r) for r in out.values())} words, "
              f"{sum(1 for r in out.values() for x in r if 'sage' in x)} linked to sages")


if __name__ == "__main__":
    main()
