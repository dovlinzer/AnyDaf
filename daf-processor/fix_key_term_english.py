"""Put key terms back in the original where an outline wrote their English instead (no API).

    python fix_key_term_english.py SPEC...            # dry run: counts per outline
    python fix_key_term_english.py SPEC... --show      # every change, with context
    python fix_key_term_english.py SPEC... --apply     # write (originals kept as *.before_termfix.json)
    SPEC = daf@tag, e.g. kiddushin_3@opus55_medium, shabbat_38@opus55

Why: the outlines wrote many key terms in English ("oven", "firstborn donkey", "stain"), and the
key-term step then listed that English as the term's alias, so the glossary linked "swept" to a
definition of "swept". The prompt now keeps key terms in the original (outline_pass.py, "Hebrew and
Aramaic words"); this repairs the outlines made before that.

What it does, per outline:
  * RULES maps an English phrase to the transliteration it stands for. A rule applies only when that
    outline's own key terms list the phrase as an alias, so "courtyard" becomes *chatzer* only on a
    daf whose glossary has kinyan chatzer. The list was reviewed pair by pair (2026-09-25); verbs and
    clauses that don't read as a term ("rationalize", "break its neck") and ordinary English
    ("burden of proof", "same kind") are deliberately not in it.
  * Skipped: text inside quotation marks (verse translations), text already in italics, and English
    standing right beside its own transliteration (a gloss already).
  * The first replacement on the daf (in a gist or bullet) keeps the English once as a gloss:
    *peter chamor* (firstborn donkey).
  * Titles, gists, bullets, chart cells, picture captions and `continues`. Not SVG labels: longer
    words could overflow the drawings.
  * Key terms: English aliases are dropped (they only linked English words to the glossary), and the
    term's own transliteration is added as an alias when the text now uses it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "outline" / "results"
WORDS = {w.strip().lower() for w in open("/usr/share/dict/words")}

RULES = {
    "firstborn donkeys": "*pitrei chamor*", "firstborn donkey": "*peter chamor*",
    "firstborn in one aspect": "*bekhor le'davar echad*", "firstborn in one respect": "*bekhor le'davar echad*",
    "one-aspect firstborn": "*bekhor le'davar echad*",
    "doubtful firstborn": "*safek bekhor*", "uncertain firstborn": "*safek bekhor*", "firstborn": "*bekhor*",
    "hebrew maidservant": "*amah ivriyah*", "maidservant": "*amah ivriyah*",
    "four cubits": "*arba amot*", "guarantor": "*arev*", "neck-breaking": "*arifah*",
    "forbidden in benefit": "*asur be'hana'ah*", "private altar": "*bamat yachid*", "intercourse": "*bi'ah*",
    "compromise": "*bitzua*", "mediation": "*bitzua*",
    "replacement in the priest's possession": "*chalifin be'yad kohen*",
    "five sin offerings left to die": "*chamesh chata'ot metot*", "five sin offerings": "*chamesh chata'ot metot*",
    "unsecured courtyard": "*chatzer she'einah mishtameret*", "secured courtyard": "*chatzer ha'mishtameret*",
    "mobile courtyard": "*chatzer mehalekhet*", "courtyard acquisition": "*kinyan chatzer*", "courtyard": "*chatzer*",
    "deaf-mutes": "*chershim*", "deaf-mute": "*cheresh*", "blood of the soul": "*dam ha'nefesh*",
    "financial association": "*derara de'mamona*", "deferral": "*dichui*",
    "decree on a decree": "*gezeirah le'gezeirah*", "deduction": "*gira'on*", "verdict": "*gmar din*",
    "standing and valuation": "*ha'amadah ve'ha'arakhah*",
    "artifice to circumvent interest": "*ha'aramat ribit*", "artifice of interest": "*ha'aramat ribit*",
    "lifting a found item for another": "*magbiah metziah le'chavero*",
    "lifting a find for another": "*magbiah metziah le'chavero*", "lifting for another": "*magbiah metziah le'chavero*",
    "lifting": "*hagbahah*", "benefit of the loan": "*hana'at milveh*", "here you are": "*heilakh*",
    "consecrated property": "*hekdesh*", "prohibition serves as intent": "*isuro zehu machshavto*",
    "deferred sanctity": "*kedushah dechuyah*", "pushed-aside sanctity": "*kedushah dechuyah*",
    "sanctity that comes by itself": "*kedushah ha'ba'ah me'eleha*",
    "sanctity of value": "*kedushat damim*", "inherent sanctity": "*kedushat ha'guf*", "double payment": "*kefel*",
    "tyrian coinage": "*kesef Tzuri*", "provincial coinage": "*kesef medinah*",
    "stains": "*ketamim*", "stain": "*ketem*", "uncertain betrothal": "*safek kiddushin*",
    "betrothal with a loan": "*kiddushin be'milveh*", "movables acquired along with land": "*kinyan agav*",
    "acquisition by cloth": "*kinyan chalifin*", "covering the blood": "*kisui ha'dam*",
    "ratification": "*kiyum shtar*", "full denial": "*kofer ha'kol*", "animal tithe": "*ma'aser behemah*",
    "property of uncertain ownership": "*mamon ha'mutal be'safek*", "collateral": "*mashkon*", "pledge": "*mashkon*",
    "gift given on condition of return": "*matanah al menat le'hachzir*",
    "gift on condition of return": "*matanah al menat le'hachzir*", "returnable gift": "*matanah al menat le'hachzir*",
    "priestly gifts": "*matanot kehunah*", "mistaken purchase": "*mekach ta'ut*", "pulling": "*meshikhah*",
    "one returning a lost item": "a *meshiv aveidah*", "returning a lost item": "*meshiv aveidah*",
    "smoothed piles": "*miruach*", "partial admission": "*modeh be'miktzat*",
    "admission to part of a claim": "*modeh be'miktzat*", "reins": "*moseira*",
    "betrothed young virgin": "*na'arah ha'me'orasah*", "liened property": "*nekhasim meshubadim*",
    "mother and young": "*oto ve'et beno*", "disqualified consecrated animals": "*pesulei ha'mukdashin*",
    "fit to see": "*re'uyah lirot*", "period of fitness": "*she'at ha'kosher*", "oath in vain": "*shevuat shav*",
    "land lien": "*shibud karka'ot*", "lien on land": "*shibud karka'ot*", "forgotten sheaf": "*shikhechah*",
    "appraisal": "*shuma*", "alleyway": "*simta*", "oven": "*tanur*", "substitute": "*temurah*",
    "untithed produce": "*tevel*", "food impurity": "*tum'at okhlin*", "tent impurity": "*tum'at ohel*",
    "common denominator": "*tzad ha'shaveh*", "hand of a gentile is in the middle": "*yad oved kokhavim ba'emtza*",
    "ambiguous intimations": "*yadayim she'einan mochiot*", "designation": "*yi'ud*",
    "important man": "*adam chashuv*", "earth": "*afar*",
    "one rises in holiness and does not descend": "*ma'alin ba'kodesh ve'ein moridin*",
}
# a phrase can be written as the English of a term in quotes: "here you are" is the claim *heilakh*
QUOTED_OK = {"here you are"}
GLOSS = {"firstborn donkeys": "firstborn donkeys", "deaf-mutes": "deaf-mutes", "stains": "stains",
         "one returning a lost item": "returning a lost item"}


def fold(s):
    return re.sub(r"[^a-z]", "", s.lower())


def _english_word(w):
    if w in WORDS or w in RULES:
        return True
    for suf, add in (("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", ""), ("ly", ""), ("izing", "ize")):
        if w.endswith(suf) and (w[:-len(suf)] + add) in WORDS:
            return True
    return False


def is_english(al):
    ws = [w for w in re.findall(r"[a-z]+", al.lower()) if len(w) >= 3]
    return bool(ws) and all(_english_word(w) for w in ws)


def load(key, tag):
    p = R / key / f"04_outline_{tag}.json"
    o = json.loads(p.read_text(encoding="utf-8"))
    kp = None if o.get("key_terms") else R / key / "05_key_terms_opus55.json"
    kt = o.get("key_terms") or (json.loads(kp.read_text(encoding="utf-8"))["key_terms"] if kp and kp.exists() else [])
    return p, o, kp, kt


def fields(o):
    """(kind, node, getter, setter) for every text field in reading order."""
    out = []

    def walk(ns):
        for n in ns or []:
            out.append(("title", n, "title"))
            out.append(("gist", n, "gist"))
            for b in n.get("bullets") or []:
                out.append(("bullet", b, "text"))
            c = n.get("chart")
            if c:
                out.append(("chart", c, "caption"))
                for i in range(len(c.get("columns") or [])):
                    out.append(("chart", c["columns"], i))
                for r in c.get("rows") or []:
                    for i in range(len(r)):
                        out.append(("chart", r, i))
            if n.get("illustration"):
                out.append(("caption", n["illustration"], "caption"))
            if n.get("continues"):
                out.append(("continues", n, "continues"))
            walk(n.get("children"))
    walk(o.get("sections"))
    return out


def inside(text, pos):
    """True if pos sits inside quotation marks or *italics*."""
    before = text[:pos]
    if before.count("“") > before.count("”") or before.count('"') % 2 == 1:
        return True
    return before.count("*") % 2 == 1


def fix_outline(key, tag, show=False):
    p, o, kp, kt = load(key, tag)
    aliases = {}
    for t in kt:
        for al in t.get("aliases") or []:
            if is_english(al):
                aliases[al.lower()] = t
    rules = [(a, RULES[a]) for a in sorted(RULES, key=len, reverse=True) if a in aliases]
    # each rule's own term, as it may already be spelled beside the English (a gloss)
    own = {a: {fold(aliases[a]["term"])} | {fold(x) for x in aliases[a].get("aliases") or [] if not is_english(x)}
              | {fold(RULES[a])} for a, _ in rules}
    glossed, changes = set(), []
    for kind, obj, k in fields(o):
        text = obj[k] if isinstance(obj, dict) else obj[k]
        if not isinstance(text, str) or not text:
            continue
        new, i = text, 0
        for a, rep in rules:
            pat = re.compile(r"(?<![\w'’-])(" + re.escape(a) + r")(?![\w'’-])", re.I)
            out, last = [], 0
            for m in pat.finditer(new):
                s, e = m.span()
                quoted = a in QUOTED_OK and s > 0 and new[s - 1] in '"“' and e < len(new) and new[e] in '"”'
                if not quoted and inside(new, s):
                    continue
                window = fold(new[max(0, s - 60):s] + new[e:e + 60])
                if any(tr and len(tr) > 3 and tr in window for tr in own[a]):
                    continue                                   # already glossed beside its term
                if new[e:e + 3] == " (*":
                    continue
                r = rep
                lead = new[:s].rstrip()
                if m.group(1)[0].isupper() and (not lead or lead[-1] in ".:?!—"):   # starts the field or a sentence
                    r = re.sub(r"^(a )?\*(\w)", lambda x: (x.group(1) or "").capitalize() + "*" + x.group(2).upper(), r)
                gloss = ""
                in_parens = new[:s].count("(") > new[:s].count(")")
                if kind in ("gist", "bullet") and rep not in glossed and not in_parens:
                    glossed.add(rep)
                    gloss = f" ({GLOSS.get(a, m.group(1).lower())})"
                elif kind not in ("gist", "bullet") and rep not in glossed:
                    pass                                       # gloss at the first gist/bullet mention
                if quoted:
                    s, e = s - 1, e + 1
                # a / an before the new word
                pre = new[last:s]
                pm = re.search(r"\b([Aa])n? $", pre)
                if pm and not rep.startswith("a "):
                    first = re.sub(r"[^A-Za-z]", "", r)[:1].lower()
                    art = "an" if first in "aeiou" else "a"
                    art = art.capitalize() if pm.group(1) == "A" else art
                    pre = pre[:pm.start()] + art + " "
                out.append(pre + r + gloss)
                last = e
                changes.append((kind, a, text[max(0, m.start() - 40):m.end() + 30]))
            if out:
                new = "".join(out) + new[last:]
        if new != text:
            obj[k] = new
    # key terms: drop English aliases, add the transliteration the text now uses
    for t in kt:
        t["aliases"] = [a for a in t.get("aliases") or [] if not is_english(a)]
    if show:
        for c in changes:
            print(f"    {c[0]:8s} {c[1]!r}: …{c[2]}…")
    return p, o, kp, kt, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    total = 0
    for spec in a.specs:
        key, tag = spec.split("@")
        p, o, kp, kt, changes = fix_outline(key, tag, a.show)
        total += len(changes)
        print(f"{spec:28s} {len(changes):4d} changes")
        if a.apply:
            bak = p.with_name(p.stem + ".before_termfix.json")
            if not bak.exists():
                shutil.copy(p, bak)
            p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
            if kp:
                kb = kp.with_name(kp.stem + ".before_termfix.json")
                if not kb.exists():
                    shutil.copy(kp, kb)
                kd = json.loads(kp.read_text(encoding="utf-8"))
                kd["key_terms"] = kt
                kp.write_text(json.dumps(kd, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total {total} changes" + ("" if a.apply else " (dry run)"))


if __name__ == "__main__":
    main()


def add_translit_aliases(key, tag):
    """After a --apply: each term gains, as aliases, the transliterations its English was replaced
    with (from the English aliases it had before), when the text now uses them."""
    p, o, kp, kt = load(key, tag)
    bp = (kp or p).with_name((kp or p).stem + ".before_termfix.json")
    if not bp.exists():
        return 0
    old = json.loads(bp.read_text(encoding="utf-8"))
    old_kt = old.get("key_terms") or []
    text = " ".join(str(obj[k]) for _, obj, k in fields(o)).lower()
    added = 0
    for t, ot in zip(kt, old_kt):
        for a in ot.get("aliases") or []:
            rep = RULES.get(a.lower())
            if not rep:
                continue
            x = re.sub(r"^a ", "", rep).strip("*")
            if x.lower() in text and x.lower() not in {y.lower() for y in t["aliases"]}:
                t["aliases"].append(x); added += 1
        t["aliases"].sort(key=len, reverse=True)
    p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    if kp:
        kd = json.loads(kp.read_text(encoding="utf-8")); kd["key_terms"] = kt
        kp.write_text(json.dumps(kd, ensure_ascii=False, indent=1), encoding="utf-8")
    return added
