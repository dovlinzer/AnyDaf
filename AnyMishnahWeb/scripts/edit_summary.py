"""Helper: edit data/<name>_summary.json items. apply(name, {('principles',i): {'t':..,'src':..}, ('terms',i): {...}, ('debates',i): {...}, ('status',None): 'text'})"""
import json
def apply(name, edits):
    p = f"data/{name}_summary.json"; d = json.load(open(p))
    for (sec, i), v in edits.items():
        if sec == "status": d["status"] = v
        else: d[sec][i].update(v)
    json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
    s = json.dumps(d, ensure_ascii=False); print(name, "Kulp mentions left:", s.count("Kulp"))
