"""Evidence for the glossary's 'Primary discussion' field: in which mishnayot of each chapter OUR outlines (written from the mishnah and Kehati) discuss a concept.
The field itself is chosen by hand (editorial); this shows what the outlines support. Usage: python3 scripts/term_locations.py "harmless|tam" ["attested danger|mu'ad" ...]"""
import json, re, sys
for pt in sys.argv[1:]:
    print("==", pt)
    for c in range(1, 7):
        d = json.load(open(f"data/bava_kamma_{c}_layer1.json")); hit = []
        for m in d["mishnayot"]:
            txt = " ".join([m["title"], m["summary"]] + [t for s in m["outline"] for t, _ in s["b"]])
            if re.search(pt, txt, re.I): hit.append(m["n"])
        print(f"  BK {c}:", hit)
