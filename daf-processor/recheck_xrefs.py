#!/usr/bin/env python3
"""Recheck the judged Rambam / Shulchan Arukh references (judge_xrefs.py) against Wikisource's Ein
Mishpat notes (em_notes.py). No Anthropic API.

The first check compared each reference with its whole line, so on a line with two notes the less
central one lost to its neighbour (Shabbat 104b:4: 4:2 belongs to note ט on ואפצא, and 4:1 to note י on
כתבו באבר). Each reference now gets one of:

  same note cites both      the note itself gives both numbers ("הלכה א ב"): drop the flag
  alt is its own note       the suggested place is another note on this amud: drop the flag
  wikisource has the alt    Wikisource's note gives the suggested number where Sefaria gives the cited one
  phrase: flag / ok / weak  the cited and suggested passages scored against the words the note's letter covers
  no note                   Wikisource has no note matching either (or no Ein Mishpat for this tractate)

    venv/bin/python recheck_xrefs.py                 # -> outline/xref_check/rechecked.json, report_rechecked.md
    venv/bin/python recheck_xrefs.py disagreements   # -> disagreements.json: Sefaria vs Wikisource numbers
"""
from __future__ import annotations

import collections
import json

from check_xrefs import lookalikes, RESULT, Scorer, beats, flat, load_bavli, node, split_ref, words, FLOOR
from em_notes import OUT as NOTES, link_key, matches, rambam_book

OUT = RESULT / "rechecked.json"
REPORT = RESULT / "report_rechecked.md"


def notes_for(tractate: str):
    p = NOTES / f"{tractate}.json"
    return json.loads(p.read_text())["amudim"] if p.exists() else None


def key_of(ref: str):
    work = "rambam" if ref.startswith("Mishneh Torah") else "sa" if ref.startswith("Shulchan Arukh") else None
    return work and link_key({"ref": ref, "work": work})


def recheck(x, amud_data, scorer):
    ref, alt = x["ref"], x.get("alt")
    ck, ak = key_of(ref), alt and key_of(alt)
    row = next((r for r in amud_data["lines"].get(str(x["line"]), []) if r["ref"] == ref), None)
    cited_notes = [nt for nt in amud_data["notes"] if any(matches(ck, r) for r in nt["refs"])]
    alt_notes = [nt for nt in amud_data["notes"] if ak and any(matches(ak, r) for r in nt["refs"])]
    out = {"notes": row["notes"] if row else [], "status": row["status"] if row else "no_note"}
    if alt_notes and cited_notes and any(n is a for n in alt_notes for a in cited_notes):
        out["recheck"] = "same note cites both"
        return out
    if alt_notes and cited_notes:
        out["recheck"] = "alt is its own note"
        out["alt_notes"] = [{"letter": l, "text": n["text"], **amud_data["markers"].get(l, {})}
                            for n in alt_notes for l in n["letters"]]
        return out
    if alt_notes and not cited_notes:
        out["recheck"] = "wikisource has the alt"
        out["alt_notes"] = [{"letter": l, "text": n["text"], **amud_data["markers"].get(l, {})}
                            for n in alt_notes for l in n["letters"]]
        return out
    phrases = [n["phrase"] for n in out["notes"] if n.get("phrase")]
    if not phrases:
        out["recheck"] = "no note" if not cited_notes else "no marker"
        return out
    src = words(" ".join(phrases))
    title, nums = split_ref(ref)
    ct = node(title, nums)
    cited = scorer.sim(src, words(flat(ct))) if ct not in (None, "missing book") else 0.0
    out["phrase_score"] = round(cited, 3)
    if alt:
        at, an = split_ref(alt)
        t = node(at, an)
        a = scorer.sim(src, words(flat(t))) if t not in (None, "missing book") else 0.0
        out["phrase_alt_score"] = round(a, 3)
        out["recheck"] = "phrase: flag" if beats(a, cited, x.get("how", "")) else \
            "phrase: ok" if cited >= FLOOR else "phrase: weak"
    else:
        out["recheck"] = "phrase: ok" if cited >= FLOOR else "phrase: weak"
    return out


def main():
    judged = json.loads((RESULT / "judged.json").read_text())
    scorer = Scorer()
    load_bavli(scorer)   # word rarity across the Bavli
    cache, rows = {}, []
    for x in judged:
        if x.get("work") not in ("rambam", "sa"):
            continue
        if x["tractate"] not in cache:
            cache[x["tractate"]] = notes_for(x["tractate"])
        nd = cache[x["tractate"]]
        if nd is None:
            rows.append({**x, "recheck": "no wikisource"})
            continue
        amud = nd.get(x["amud"]) or {"lines": {}, "notes": [], "markers": {}}
        rows.append({**x, **recheck(x, amud, scorer)})
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1))

    c = collections.Counter((r["kind"], r["judge"]["verdict"], r["recheck"]) for r in rows)
    lines = ["# Rambam and Shulchan Arukh references rechecked against Wikisource's Ein Mishpat", "",
             "| Kind | Model's verdict | Recheck | References |", "|---|---|---|---:|"]
    lines += [f"| {k} | {v} | {r} | {n} |" for (k, v, r), n in sorted(c.items())]
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))




def misread(a: int, b: int) -> bool:
    """Could one number be a misreading of the other: a look-alike numeral, or one or two off?"""
    return abs(a - b) <= 2 or b in lookalikes(a) or a in lookalikes(b)


def ref_str(key_ref: str, nums: list[int]) -> str:
    title, _ = split_ref(key_ref)
    return f"{title} {':'.join(map(str, nums))}"


def disagreements():
    """Every Sefaria reference whose number no Wikisource note on its amud gives, where a note gives the
    same place with one number different: which reading do the note's words favour?"""
    scorer = Scorer()
    load_bavli(scorer)
    rows = []
    for f in sorted(NOTES.glob("*.json")):
        d = json.loads(f.read_text())
        for amud, v in d["amudim"].items():
            for n, items in v["lines"].items():
                for it in items:
                    if it["status"] != "no_note":
                        continue
                    work, section, nums = key_of(it["ref"])
                    for nt in v["notes"]:
                        for r in nt["refs"]:
                            if r["work"] != work or (work == "sa" and r["section"] != section) \
                                    or (work == "rambam" and rambam_book(r.get("halakhot")) not in (None, section)) \
                                    or len(r["nums"]) != len(nums):
                                continue
                            diff = [(a, b) for a, b in zip(nums, r["nums"]) if a != b]
                            if len(diff) != 1 or not misread(*diff[0]):
                                continue
                            for letter in nt["letters"]:
                                mk = v["markers"].get(letter, {})
                                src = words(mk.get("phrase") or "")
                                title, _ = split_ref(it["ref"])
                                s_t, w_t = node(title, nums), node(title, r["nums"])
                                s = scorer.sim(src, words(flat(s_t))) if src and s_t not in (None, "missing book") else None
                                w = scorer.sim(src, words(flat(w_t))) if src and w_t not in (None, "missing book") else None
                                rows.append({"tractate": d["tractate"], "amud": amud, "line": int(n), "work": work,
                                             "sefaria": it["ref"], "wikisource": ref_str(it["ref"], r["nums"]),
                                             "letter": letter, "note": nt["text"], "word": mk.get("word"),
                                             "marker_line": mk.get("line"), "phrase": mk.get("phrase"),
                                             "sefaria_score": s and round(s, 3), "wikisource_score": w and round(w, 3)})
    # one row per reference: the note whose letter is on the reference's line, else the first
    best = {}
    for r in rows:
        k = (r["tractate"], r["amud"], r["line"], r["sefaria"])
        if k not in best or (r["marker_line"] == r["line"] and best[k]["marker_line"] != r["line"]):
            best[k] = r
    out = list(best.values())
    for r in out:
        s, w = r["sefaria_score"], r["wikisource_score"]
        r["favours"] = ("unknown" if s is None or w is None else
                        "wikisource" if w >= FLOOR and w >= 1.6 * s and w - s >= 0.06 else
                        "sefaria" if s >= FLOOR and s >= 1.6 * w and s - w >= 0.06 else "unclear")
    (RESULT / "disagreements.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    c = collections.Counter((r["work"], r["favours"]) for r in out)
    print("Sefaria and Wikisource disagree (one number):", len(out))
    for k, v in sorted(c.items()):
        print(" ", k, v)


def wrong_book():
    """Rambam links whose chapter and halakha match a note on their amud but whose book doesn't:
    e.g. Bava Batra 150a, Sefaria 'Ownerless Property and Gifts 10:13' where the note has Bikkurim 10:13."""
    rows = []
    for f in sorted(NOTES.glob("*.json")):
        d = json.loads(f.read_text())
        for amud, v in d["amudim"].items():
            for n, items in v["lines"].items():
                for it in items:
                    if it["status"] != "no_note" or not it["ref"].startswith("Mishneh Torah"):
                        continue
                    _, book, nums = key_of(it["ref"])
                    hits = []
                    for nt in v["notes"]:
                        for r in nt["refs"]:
                            other = rambam_book(r.get("halakhot"))
                            if r["work"] != "rambam" or not other or other == book or len(r["nums"]) < 2 or len(nums) < 2:
                                continue
                            same = r["nums"][:2] == nums[:2]
                            # or the halakha matches and the chapter is a misreading: a book and a chapter both
                            # misread, so only the note whose letter is on this very line counts
                            near = (r["nums"][1] == nums[1] and misread(r["nums"][0], nums[0]))
                            for letter in nt["letters"]:
                                mk = v["markers"].get(letter, {})
                                if same or (near and mk.get("line") == int(n)):
                                    hits.append({"letter": letter, "note": nt["text"], "word": mk.get("word"),
                                                 "marker_line": mk.get("line"), "kind": "book" if same else "book+chapter",
                                                 "suggested": f"{other} {':'.join(map(str, r['nums'][:2]))}"})
                    if hits:
                        hits.sort(key=lambda h: (h["kind"] != "book", h["marker_line"] != int(n)))
                        rows.append({"tractate": d["tractate"], "amud": amud, "line": int(n),
                                     "sefaria": it["ref"], **hits[0]})
    (RESULT / "wrong_book.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("Rambam links with the right numbers in the wrong book:", len(rows))
    for r in rows:
        print(f"  [{r['kind']}] {r['tractate']} {r['amud']}:{r['line']}  {r['sefaria']}  ->  {r['suggested']}  (note {r['letter']})")


if __name__ == "__main__":
    import sys
    {"disagreements": disagreements, "wrong_book": wrong_book}.get((sys.argv[1:] or [""])[0], main)()
