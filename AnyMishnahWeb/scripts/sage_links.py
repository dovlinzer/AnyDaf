"""Which sage each name in a chapter's mishnayot means, for the sage links on the site.
Run with the daf-processor venv (it uses build_sages.find_names, the same matcher and context rule as iTalmud
and the kit's Mishnah counts):  ../daf-processor/venv/bin/python scripts/sage_links.py
Writes data/sage_links.json: {"bava-kamma-3": {"he": {hebrew name: slug}, "slugs": [slug, ...]}}.
build_site.py reads it; it does not need the venv."""
import sys, json, re, glob, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "daf-processor"))
import build_sages as B

sages = B.matcher()[0]
out = {}
for f in sorted(glob.glob("data/bava_*_[0-9].json")):
    D = json.load(open(f))
    key = os.path.basename(f)[:-5].replace("_", "-")
    segs = [(f"{D['chapter']}a.{m['n']}", re.sub(r"<[^>]+>", "", m["he"]), "") for m in D["mishnayot"]]
    he = {}
    for r in B.find_names(segs):
        pick = r["pick"]
        if sages[pick]["kind"] == "amora":   # no amora speaks in the Mishnah (same rule as the kit's census)
            tannaim = [c for c in r["candidates"] if sages[c]["kind"] in ("tanna", "zug")]
            if not tannaim: continue
            pick = max(tannaim, key=lambda c: sages[c]["num_sources"])
        he[r["name"]] = pick
    out[key] = {"he": he, "slugs": sorted(set(he.values()))}
json.dump(out, open("data/sage_links.json", "w"), ensure_ascii=False, indent=1)
for k, v in out.items(): print(k, v["he"])
