"""Run check_picture on every picture of a chapter that exists in the config folder (name.jpg/.png/.webp).
Usage: run_checks.py data/bava_metzia_1_checks.json   Prints one line per picture; writes <folder>/check_report.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from check_picture import check
cfg = json.load(open(sys.argv[1])); rep = {}
for name, c in cfg["pictures"].items():
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(cfg["folder"], name + ext)
        if os.path.exists(p):
            fails, res = check(p, c["boxes"], c["cast"], c["numerals"], c["scene"], True, c.get("single", []), c.get("expect_qmark"))
            rep[name] = {"pass": not fails, "fails": fails, "warnings": res["warnings"]}
            print(("PASS " if not fails else "FAIL ") + name, "|", "; ".join(fails + ["(warn) " + w for w in res["warnings"]]) or "-"); break
    else: print("----", name, "(no image yet)")
json.dump(rep, open(os.path.join(cfg["folder"], "check_report.json"), "w"), indent=1)
