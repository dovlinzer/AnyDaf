#!/usr/bin/env python3
"""Writes the shared sages data for iTalmud and Illustrated Mishna:
AnyMishnahWeb/reference-kit/sages/sages.json. No Anthropic API calls.

    venv/bin/python sages_kit.py

Inputs (edit these, never the output):
- outline/sages/sages.json         Sefaria people: names, kind, generation, region, bio, links
- outline/sages/wiki_facts.json    Hebrew Wikipedia infobox facts (sages_wiki.py)
- outline/sages/census_bavli.json, census_mishnah.json   mention counts (build_sages.py census)
- outline/sages/kit_overrides.json the author's picks: major sages, tiers, links to drop or add
- outline/sages/stories.json       approved stories per sage (may be empty)

Also writes quoted.json: the amudim (Bavli) and mishnayot (Mishnah) where each sage is named.

Relationships are made two-way here (a teacher of B makes B his student), so each record
lists everything the graph draws around that sage. Every link carries a `source` field
("" until stage 2 fills in the passage) and the sources it came from (sefaria / wikipedia / author).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAGES = HERE / "outline" / "sages"
KIT = HERE.parent / "AnyMishnahWeb" / "reference-kit" / "sages"

# Approximate years (CE; negative is BCE) for Sefaria's generation codes. Draft for the author.
# Zugot, then the six generations of tanna'im and the transition (TA), then the amora'im.
GEN_YEARS = {
    "Z1": (-170, -140), "Z2": (-140, -100), "Z3": (-100, -60), "Z4": (-60, -30), "Z5": (-30, 10),
    "T1": (10, 40), "T2": (40, 80), "T3": (80, 110), "T4": (110, 135), "T5": (135, 170),
    "T6": (170, 200), "TA": (200, 230),
    "A1": (220, 250), "A2": (250, 290), "A3": (290, 320), "A4": (320, 350), "A5": (350, 375),
    "A6": (375, 425), "A7": (425, 460), "A8": (460, 500),
}
TIER1, TIER2 = 60, 250          # by rank in the Bavli count, then the author's overrides
REL = {"teachers": "students", "students": "teachers", "colleagues": "colleagues",
       "father": "children", "mother": "children", "children": "parents", "parents": "children",
       "spouse": "spouse", "in_laws": "sons_in_law", "sons_in_law": "in_laws",
       "siblings": "siblings", "relatives": "relatives"}
FAMILY = ("father", "mother", "parents", "children", "spouse", "in_laws", "sons_in_law", "siblings",
          "relatives")


def load(name, default=None):
    p = SAGES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def years(code):
    """(from, to) for a code like 'A3' or 'A3/A4' (the span of both)."""
    spans = [GEN_YEARS[c] for c in (code or "").split("/") if c in GEN_YEARS]
    return [min(a for a, _ in spans), max(b for _, b in spans)] if spans else None


def main():
    sages = load("sages.json")
    wiki = load("wiki_facts.json", {})
    bavli, mishnah = load("census_bavli.json", {}), load("census_mishnah.json", {})
    ov = load("kit_overrides.json", {})
    stories = load("stories.json", {})

    # who to include: every sage with a kind, a count, or a link to one of those
    keep = {k for k, x in sages.items() if x["kind"] or k in bavli or k in mishnah}

    # links: (a, rel, b-or-name) -> sources
    links = {}
    def add(a, rel, b, src, note=""):
        if not b or b == a:
            return
        key = (a, rel, b)
        e = links.setdefault(key, {"from": set(), "note": ""})
        e["from"].add(src)
        e["note"] = e["note"] or note
    for k in keep:
        x = sages[k]
        for rel in ("teachers", "students", "colleagues"):
            for b in x.get(rel) or []:
                if b in sages:
                    add(k, rel, b, "sefaria")
        w = wiki.get(k, {})
        for rel in REL:
            for e in w.get(rel) or []:
                b = e.get("slug") or ("name:" + e["name"])
                add(k, rel, b, "wikipedia", e.get("note", ""))
    for a, rel, b in ov.get("add_links", []):
        add(a, rel, b, "author")
    drop = {tuple(x) for x in ov.get("drop_links", [])}
    # make two-way
    for (a, rel, b), e in list(links.items()):
        if not b.startswith("name:") and b in sages:
            back = links.setdefault((b, REL[rel], a), {"from": set(), "note": e["note"]})
            back["from"] |= e["from"]
    # a sage whose only link is to a kept sage comes along (as someone's teacher, say)
    keep |= {b for (a, _, b) in links if a in keep and b in sages}

    # tiers
    ranked = [k for k in bavli if sages[k]["kind"] in ("tanna", "amora", "zug")]
    rank = {k: i for i, k in enumerate(ranked)}
    major = set(ov.get("major", []))
    tier_ov = ov.get("tier", {})
    def tier(k):
        if k in tier_ov:
            return tier_ov[k]
        if k in major or rank.get(k, 1e9) < TIER1:
            return 1
        return 2 if rank.get(k, 1e9) < TIER2 else 3
    # The Mishnah site ranks by the Mishnah: its own tiers by the same rule
    mranked = [k for k in mishnah if sages[k]["kind"] in ("tanna", "zug")]
    mrank = {k: i for i, k in enumerate(mranked)}
    mtier_ov = ov.get("tier_mishnah", {})
    def mtier(k):
        if k in mtier_ov:
            return mtier_ov[k]
        if k in major or mrank.get(k, 1e9) < 25:
            return 1
        return 2 if mrank.get(k, 1e9) < 60 else 3

    out = {}
    for k in sorted(keep):
        x, w = sages[k], wiki.get(k, {})
        rels = {}
        for (a, rel, b), e in links.items():
            if a != k or (a, rel, b) in drop:
                continue
            item = ({"id": b} if not b.startswith("name:") else {"name": b[5:]})
            item.update({"by": sorted(e["from"]), "source": ""})
            if e["note"]:
                item["note"] = e["note"]
            rels.setdefault(rel, []).append(item)
        def exact(y):
            return y if y and len(y) == 2 else None   # a 'century' range is too rough to show
        born, died = exact(w.get("born_year")), exact(w.get("died_year"))
        rec = {
            "en": x["en"], "he": x["he"], "alt_en": x["titles_en"], "alt_he": x["titles_he"],
            "kind": x["kind"], "gen": x["generation"], "gen_code": x["generation_code"],
            "region": x["region"],
            "years": years(x["generation_code"]),          # approximate, from the generation
            "born": born, "died": died,                   # from Wikipedia, when it gives a year
            "tier": tier(k), "tier_mishnah": mtier(k) if k in mishnah else 3,
            "bio": x.get("bio") or "", "bio_he": x.get("bio_he") or "",
            "sefaria": k, "wiki_he": (x.get("links") or {}).get("heWikiLink") or "",
            "count": {"bavli": bavli.get(k, {}).get("total", 0), "mishnah": mishnah.get(k, {}).get("total", 0)},
            "quoted": {"bavli": bavli.get(k, {}).get("by_tractate", {}),
                       "mishnah": mishnah.get(k, {}).get("by_tractate", {})},
            "estimated_count": bavli.get(k, {}).get("guessed", 0) > bavli.get(k, {}).get("total", 0) / 2,
            "links": {r: sorted(v, key=lambda i: (i.get("id") is None, -sages.get(i.get("id"), {}).get("num_sources", 0)))
                      for r, v in rels.items()},
            "stories": stories.get(k, []),
        }
        out[k] = rec
    KIT.mkdir(parents=True, exist_ok=True)
    data = {"_note": "Built by daf-processor/sages_kit.py; do not edit. Years are approximate "
                     "(from the generation) unless born/died are given.",
            "gen_years": GEN_YEARS, "sages": out}
    (KIT / "sages.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # where each sage is named, loaded only when a reader opens the full list
    quoted = {k: {"bavli": bavli.get(k, {}).get("amudim", {}), "mishnah": mishnah.get(k, {}).get("mishnayot", {})}
              for k in out if k in bavli or k in mishnah}
    (KIT / "quoted.json").write_text(json.dumps(quoted, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = {t: sum(1 for r in out.values() if r["tier"] == t) for t in (1, 2, 3)}
    size = (KIT / "sages.json").stat().st_size // 1024
    print(f"{len(out)} sages (tier 1: {n[1]}, tier 2: {n[2]}, tier 3: {n[3]}); "
          f"{sum(len(v) for r in out.values() for v in r['links'].values())} links; {size} KB -> {KIT / 'sages.json'}")


if __name__ == "__main__":
    main()
