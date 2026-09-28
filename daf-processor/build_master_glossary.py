#!/usr/bin/env python3
"""Cluster per-daf key terms into a draft master glossary. Local only, no API calls.

Reads outline/results/<key>/05_key_terms_<tag>.json (plus the Chagigah 6 worked example) and
groups entries that name the same concept, even under different spellings (chatzer / chatzeir /
hatzer), by Hebrew skeleton first and a folded transliteration second. Within each group, each
distinct sense becomes its own entry (chatzer as acquisition vs. courtyard). Each sense keeps
every candidate definition with its daf, for the author to pick or rewrite one core definition,
and gets suggested related topics in the AskAnyDaf taxonomy (topic_analysis/taxonomy/seed_taxonomy.json).

    venv/bin/python build_master_glossary.py --tag opus55
    -> outline/glossary/master_draft.json

Sense splitting is a heuristic (word overlap of the "sense" lines); every group with more than
one sense is flagged for review rather than trusted.
"""
import argparse
import json
import re
from pathlib import Path

from key_terms_pass import heb_skeleton

HERE = Path(__file__).parent
RESULTS = HERE / "outline" / "results"
EXAMPLE = HERE / "outline" / "key_terms_example_chagigah_6.json"
TAXONOMY = HERE / "topic_analysis" / "taxonomy" / "seed_taxonomy.json"
OUT = HERE / "outline" / "glossary" / "master_draft.json"

STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "by", "with", "one's", "as"}


def fold(translit: str) -> str:
    """Fold common transliteration variants: chatzer/chatzeir/hatzer -> hatzer-ish key."""
    s = translit.lower()
    s = re.sub(r"[’'`\-\s]", "", s)
    for a, b in (("ch", "h"), ("kh", "h"), ("tz", "z"), ("ts", "z"), ("ei", "e"), ("ee", "i"),
                 ("ai", "a"), ("oo", "u"), ("ph", "f"), ("sh", "s"), ("th", "t")):
        s = s.replace(a, b)
    s = re.sub(r"(.)\1", r"\1", s)          # double letters
    s = re.sub(r"h$", "", s)                # final heh
    return s


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOP}


def same_sense(a: str, b: str) -> bool:
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.5


def load_terms(tag: str) -> list[dict]:
    rows = []
    for t in json.loads(EXAMPLE.read_text(encoding="utf-8"))["key_terms"]:
        rows.append({**t, "daf_key": "chagigah_6", "model": "author example"})
    for p in sorted(RESULTS.glob(f"*/05_key_terms_{tag}.json")):
        for t in json.loads(p.read_text(encoding="utf-8")).get("key_terms", []):
            rows.append({**t, "daf_key": p.parent.name, "model": tag})
    return rows


SKIP_CATEGORIES = ("BIBLICAL FIGURES", "RABBINIC AUTHORITIES", "GEOGRAPHY", "JEWISH HISTORY")


def taxonomy_entries() -> list[dict]:
    """Taxonomy topics a concept could link to (people, places and history left out)."""
    if not TAXONOMY.exists():
        return []
    out = []
    for e in json.loads(TAXONOMY.read_text(encoding="utf-8"))["entries"]:
        if (e.get("category") or "").startswith(SKIP_CATEGORIES):
            continue
        name = re.sub(r"\s*\(.*\)$", "", e.get("name", ""))
        out.append({**e, "_lat": {fold(w) for w in name.split() if len(w) >= 4},
                    "_heb": {heb_skeleton(w) for w in (e.get("hebrew") or "").split() if len(heb_skeleton(w)) >= 3}})
    return out


def taxonomy_candidates(rows: list[dict], tax: list[dict], n: int = 3) -> list[dict]:
    """Topics sharing a transliterated or Hebrew word with the term. The taxonomy is coarser
    than the glossary (olat tamid -> Korban Tamid), so these are related-topic suggestions for
    the author to confirm, never automatic identities."""
    lat = {fold(w) for r in rows for w in r.get("term", "").split() if len(w) >= 4}
    heb = {heb_skeleton(w) for r in rows for w in r.get("hebrew", "").split() if len(heb_skeleton(w)) >= 3}
    scored = []
    for e in tax:
        score = 2 * len(lat & e["_lat"]) + len(heb & e["_heb"])
        if score >= 2:
            scored.append((score, e["id"], e["name"]))
    scored.sort(key=lambda x: -x[0])
    return [{"id": i, "name": nm, "score": sc} for sc, i, nm in scored[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="opus55", help="which model's key terms to cluster")
    args = ap.parse_args()

    rows = load_terms(args.tag)
    groups: list[dict] = []           # {"heb": set, "fold": set, "rows": [...]}
    for r in rows:
        hk, fk = heb_skeleton(r.get("hebrew", "")), fold(r.get("term", ""))
        g = next((g for g in groups if (hk and hk in g["heb"]) or fk in g["fold"]), None)
        if g is None:
            g = {"heb": set(), "fold": set(), "rows": []}
            groups.append(g)
        if hk:
            g["heb"].add(hk)
        g["fold"].add(fk)
        g["rows"].append(r)

    tax = taxonomy_entries()
    entries = []
    for g in groups:
        senses: list[dict] = []
        for r in g["rows"]:
            s = next((s for s in senses if same_sense(s["sense"], r.get("sense", ""))), None)
            if s is None:
                s = {"sense": r.get("sense", ""), "candidates": [], "dafim": []}
                senses.append(s)
            s["candidates"].append({"daf": r["daf_key"], "source": r["model"], "definition": r.get("definition", ""),
                                    "on_this_daf": r.get("on_this_daf", "")})
            if r["daf_key"] not in s["dafim"]:
                s["dafim"].append(r["daf_key"])
        first = g["rows"][0]
        variants = sorted({r["term"] for r in g["rows"]} | {a for r in g["rows"] for a in r.get("aliases", [])})
        entries.append({
            "id": re.sub(r"[^a-z0-9]+", "_", first["term"].lower().replace("'", "")).strip("_"),
            "term": first["term"],
            "hebrew": first.get("hebrew", ""),
            "variants": variants,
            "taxonomy_candidates": taxonomy_candidates(g["rows"], tax),
            "needs_sense_review": len(senses) > 1,
            "senses": [{**s, "core_definition": None, "status": "draft"} for s in senses],
        })

    entries.sort(key=lambda e: (-sum(len(s["dafim"]) for s in e["senses"]), e["term"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source_tag": args.tag, "entries": entries}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    multi = sum(e["needs_sense_review"] for e in entries)
    linked = sum(bool(e["taxonomy_candidates"]) for e in entries)
    print(f"{len(rows)} per-daf terms -> {len(entries)} master entries "
          f"({multi} flagged for sense review, {linked} with a taxonomy suggestion) -> {OUT.relative_to(HERE)}")


if __name__ == "__main__":
    main()
