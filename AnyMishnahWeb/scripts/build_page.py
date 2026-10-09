"""Build prototype/berakhot_1.html from data/berakhot_1.json (Sefaria) and the layer-1 draft."""
import json, re, html
D = json.load(open("data/berakhot_1.json")); L = json.load(open("data/berakhot_1_layer1_draft.json"))
SVGS = {3: open("prototype/tarfon.svg").read()}
def clean(s): return re.sub(r"<[^>]+>", "", s or "")
def kulp(parts):
    out = []
    for p in parts[1:]:
        out.append("<p>" + re.sub(r"<(?!/?b>)[^>]+>", " ", p).replace("<br>", " ") + "</p>")
    return "".join(out)
def chart(c):
    if not c: return ""
    if c.get("type") == "timeline":
        marks = "".join(f'<li><span class="dot"></span>{html.escape(m)}</li>' for m in c["marks"])
        return f'<div class="chart"><h4>{html.escape(c["title"])}</h4><ol class="timeline">{marks}</ol></div>'
    head = "".join(f"<th>{html.escape(x)}</th>" for x in c["cols"])
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(x)}</td>" for x in r) + "</tr>" for r in c.get("rows", []))
    note = "" if rows else '<tr><td colspan="%d" class="todo">table to be filled from source</td></tr>' % len(c["cols"])
    return f'<div class="chart"><h4>{html.escape(c["title"])}</h4><table><tr>{head}</tr>{rows}{note}</table></div>'
def pics(n, items):
    out = []
    for i, ill in enumerate(items):
        if n == 3 and i == 0:
            out.append(f'<figure class="pic">{SVGS[3]}<figcaption>Test scene (SVG) — {html.escape(ill["brief"])}</figcaption></figure>')
        else:
            out.append(f'<figure class="pic ph"><div>Illustration to come</div><figcaption>{html.escape(ill["brief"])}</figcaption></figure>')
    return "".join(out)
def layer2(l2):
    if not l2: return '<div class="layer2"><span class="tag">Deeper layer</span> Coming once Kehati is available.</div>'
    body = "".join(f'<h4>{html.escape(s["h"])} <small class="src">[{html.escape(s["src"])}]</small></h4><ul>' + "".join(f"<li>{html.escape(b)}</li>" for b in s["b"]) + "</ul>" for s in l2["sections"])
    return f'<div class="layer2 on"><span class="tag t2">Deeper layer — draft</span><p class="small">{html.escape(l2["source"])}. {html.escape(l2["note"])}</p>{body}{chart(l2["chart"])}</div>'
secs = []
for m, a in zip(D["mishnayot"], L["mishnayot"]):
    n = m["n"]
    ol = "".join(f'<h4>{html.escape(s["h"])}</h4><ul>' + "".join(f"<li>{html.escape(b)}</li>" for b in s["b"]) + "</ul>" for s in a["outline"])
    secs.append(f'''<section id="m{n}"><h2>Mishnah {n}: {html.escape(a["title"])}</h2>
<p class="sum">{html.escape(a["summary"])}</p>
<div class="grid"><div class="text"><div class="he" lang="he" dir="rtl">{clean(m["he"])}</div>
<div class="en">{clean(m["en"])}</div>
<details><summary>Kulp's explanation</summary>{kulp(m["kulp"])}</details></div>
<div class="aids"><div class="layer1"><span class="tag">Simple reading</span>{ol}{chart(a.get("chart"))}</div>{pics(n, a["illustrations"])}
{layer2(a.get("layer2"))}</div></div></section>''')
css = """body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f7f4ec;color:#222}header{background:#1b3a8a;color:#fff;padding:16px 24px}
main{max-width:1100px;margin:auto;padding:16px}section{background:#fff;border-radius:12px;padding:16px 20px;margin:20px 0;box-shadow:0 1px 4px #0002}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}@media(max-width:860px){.grid{grid-template-columns:1fr}}
.he{font:22px/1.8 'Times New Roman',serif;margin-bottom:10px}.en{color:#333}.sum{font-style:italic;color:#555}
.tag{display:inline-block;background:#1b3a8a;color:#fff;border-radius:10px;padding:1px 10px;font-size:12px;margin-bottom:6px}
.t2{background:#7a2cd0}.small{font-size:12px;color:#777;margin:2px 0}.src{font-weight:normal;color:#888;font-size:11px}.layer2.on{border:1px solid #7a2cd0;color:#222;font-size:16px;background:#faf6ff}.layer2{margin-top:10px;padding:10px;border:1px dashed #aaa;border-radius:8px;color:#777;font-size:14px}
h4{margin:10px 0 2px}ul{margin:0 0 4px;padding-left:20px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}.todo{color:#999}
.timeline{list-style:none;padding:0;border-left:3px solid #1b3a8a;margin-left:8px}.timeline li{padding:4px 0 4px 14px;position:relative}.dot{position:absolute;left:-9px;top:10px;width:12px;height:12px;border-radius:6px;background:#e0a100}
.pic{margin:12px 0}.pic svg{width:100%;height:auto;border-radius:10px}.ph div{background:#e9e6dc;height:140px;border-radius:10px;display:grid;place-items:center;color:#888}
figcaption{font-size:12px;color:#777;margin-top:2px}details{margin-top:8px}footer{font-size:12px;color:#666;padding:12px 24px}"""
page = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Berakhot 1 — prototype</title><style>{css}</style></head>
<body><header><h1 style="margin:0">Mishnah Berakhot, chapter 1</h1><div>Prototype — layer 1 is a draft checked against Kulp; layer 2 awaits Kehati.</div></header>
<main>{"".join(secs)}</main>
<footer>Hebrew: Mishnah, ed. Romm, Vilna 1913 (public domain). English and explanation: Mishnah Yomit by Dr. Joshua Kulp, via Sefaria, CC-BY.</footer></body></html>'''
open("prototype/berakhot_1.html", "w").write(page)
print(len(page))
