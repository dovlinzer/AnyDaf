"""Small helper: apply replacements/deletions to outline bullets in data/<name>_layer1.json.
Usage in a script: from edit_bullets import apply; apply('bava_kamma_1', {(1,'Why four?',1): ('new text','Kehati 1:1'), (2,'The principle',2): None})
Key = (mishnah n, section heading, bullet index in the ORIGINAL list). None deletes. Indices refer to the original order."""
import json
def apply(name, edits):
    p = f"data/{name}_layer1.json"; d = json.load(open(p))
    for m in d["mishnayot"]:
        for s in m["outline"]:
            new = []
            for i, b in enumerate(s["b"]):
                k = (m["n"], s["h"], i)
                if k in edits:
                    if edits[k] is None: continue
                    new.append(list(edits[k]))
                else: new.append(b)
            s["b"] = new
    json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
    left = [(m["n"], s["h"], t) for m in d["mishnayot"] for s in m["outline"] for t, src in s["b"] if "Kulp" in src or "Kulp" in t]
    print(name, "bullets still mentioning Kulp:", len(left)); [print("  ", x) for x in left]
