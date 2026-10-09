"""Build site/index.html and site/bava-kamma-5.html from data/bava_kamma_5.json (Sefaria) and data/bava_kamma_5_layer1.json.
Pictures (site/img/bk5-*.jpg) come from compose_bk5.py. The AnyDaf sprite (site/sprite.svg) is inlined for the diagrams."""
import html, json, re
SPRITE = re.sub(r"<svg class=\"sprite\"", '<svg class="sprite" style="position:absolute;width:0;height:0"', open("site/sprite.svg").read())
def clean(s): return re.sub(r"<[^>]+>", "", s or "")
def esc(s): return html.escape(s)
FONT = "Public Sans, system-ui, sans-serif"
def T(x, y, s, size=15, w=400, fill="#1A1F2E", anchor="start"): return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" font-weight="{w}" fill="{fill}">{esc(s)}</text>'
def U(sym, x, y, w, h, color=None): return f'<use href="#{sym}" x="{x}" y="{y}" width="{w}" height="{h}"' + (f' style="color:{color}"' if color else "") + "/>"
def badge(kind, x, y, d): return f'<image href="img/badge-{kind}.png" x="{x}" y="{y}" width="{d}" height="{d}"/>'
def wrap(s, n):
    lines, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    return lines + [cur]
def multi(x, y, s, n, size=15, lh=19, **k): return "".join(T(x, y + i * lh, t, size, **k) for i, t in enumerate(wrap(s, n)))
def svg(vb, body, label): return f'<svg viewBox="0 0 {vb[0]} {vb[1]}" role="img" aria-label="{esc(label)}"><rect width="{vb[0]}" height="{vb[1]}" rx="14" fill="url(#sky)"/>{body}</svg>'
def matrix(title, cols, rows, vb_w=520, label_w=190, row_h=116, note=None, bd=62):
    """rows: (label, icon_svg_or_'', [(kind or None, caption)...]). Narrow viewBox so text renders large in the panel."""
    cw = (vb_w - label_w - 14) / len(cols); h = 104 + row_h * len(rows) + (34 if note else 6)
    b = multi(vb_w / 2, 34, title, 34, 19, 22, w=700, fill="#1b3a8a", anchor="middle") if len(title) > 34 else T(vb_w / 2, 36, title, 19, 700, "#1b3a8a", "middle")
    top = 54 if len(title) <= 34 else 78
    for j, c in enumerate(cols): b += f'<rect x="{label_w + j*cw}" y="{top}" width="{cw-6}" height="34" rx="8" fill="#1b3a8a"/>' + T(label_w + j * cw + cw / 2 - 3, top + 23, c, 15, 700, "#fff", "middle")
    for i, (lab, icon, cells) in enumerate(rows):
        y = top + 44 + i * row_h
        b += f'<rect x="8" y="{y}" width="{vb_w-16}" height="{row_h-8}" rx="10" fill="#ffffffaa" stroke="#d9cfbd"/>' + (icon(y) if callable(icon) else icon) + multi(24 if not icon else 84, y + 28, lab, max(12, int((label_w - (24 if not icon else 84) - 8) / 7.4)), 16 if not icon else 14, 20, w=600)
        for j, (kind, cap) in enumerate(cells):
            cx = label_w + j * cw + cw / 2 - 3
            if kind: b += badge(kind, cx - bd / 2, y + 8, bd) + multi(cx, y + bd + 26, cap, 18, 14, 16, anchor="middle")
            else: b += T(cx, y + 56, cap or "not stated", 14, 400, "#8a8a8a", "middle")
    if note: b += multi(vb_w / 2, top + 44 + row_h * len(rows) + 12, note, 52, 14, 17, fill="#444", anchor="middle")
    return svg((vb_w, h + 40), b, title)
def svg_53():
    rows = [("The householder's ox gores it, or his dog bites it", lambda y: U("man", 26, y + 12, 34, 68, "#8C4A60"), [("notpay", "Householder is exempt"), ("pay", "Householder pays")]),
            ("The visiting ox gores the householder's ox", lambda y: U("bull", 18, y + 30, 58, 37), [("pay", "Visitor pays"), (None, "")]),
            ("The visiting ox falls into the cistern and fouls the water", lambda y: U("bull", 18, y + 30, 58, 37), [("pay", "Visitor pays"), (None, "")]),
            ("The visiting ox falls in and kills the householder's father or son", lambda y: U("bull", 18, y + 30, 58, 37), [("pay", "Visitor pays the ransom"), (None, "")])]
    return matrix("Who pays when a man brings his ox into a courtyard?", ["No permission", "With permission"], rows, 520, 236, 118, "Rabbi: the householder is liable only if he agreed to guard the ox.")
def pit(x, y, depth, num):
    return (f'<rect x="{x}" y="{y}" width="56" height="52" rx="4" fill="#C9A66B"/><rect x="{x+13}" y="{y}" width="30" height="{depth}" fill="#4a2f1c"/>'
            f'<rect x="{x+26}" y="{y-6}" width="4" height="{depth+6}" fill="#EDE3CF"/>' + T(x + 28, y - 12, num, 15, 700, "#333", "middle"))
def svg_55():
    rows = [("Ten handbreadths or more", lambda y: pit(18, y + 38, 46, "10"), [("pay", "Digger pays"), ("pay", "Digger pays (implied)")]),
            ("Less than ten handbreadths", lambda y: pit(18, y + 38, 38, "9"), [("notpay", "Digger is exempt"), ("pay", "Digger pays")])]
    return matrix("Who pays for the animal in the pit?", ["The animal dies", "The animal is injured"], rows, 520, 186, 122)
def svg_54():
    b = '<defs><marker id="ar" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0 0 L12 6 L0 12Z" fill="#555"/></marker></defs>' + T(260, 34, "Aimed at one, struck another", 19, 700, "#1b3a8a", "middle")
    for k, (lab, arrow, kind, cap) in enumerate((("An ox", "aims at another ox", "notpay", "No payment for the offspring"), ("A man", "aims at another man", "pay", "Pays for the offspring (to the husband or his heirs)"))):
        y = 52 + k * 176
        b += f'<rect x="8" y="{y}" width="504" height="164" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/>'
        b += (U("bull", 16, y + 40, 96, 62) if k == 0 else U("man", 38, y + 16, 48, 96, "#4E7A8C")) + T(64, y + 138, lab, 15, 600, "#333", "middle")
        b += f'<path d="M122 {y+72} L212 {y+72}" stroke="#555" stroke-width="3" fill="none" marker-end="url(#ar)"/>' + multi(168, y + 40, arrow, 13, 12, 15, anchor="middle") + T(168, y + 98, "but strikes", 12, 400, "#444", "middle")
        b += U("woman", 222, y + 16, 54, 108, "#8C4A60") + T(249, y + 138, "a woman", 15, 600, "#333", "middle")
        b += f'<path d="M290 {y+72} L324 {y+72}" stroke="#555" stroke-width="3" fill="none" marker-end="url(#ar)"/>'
        b += badge(kind, 368, y + 8, 64) + multi(400, y + 96, cap, 28, 14, 17, w=600, anchor="middle")
    return svg((520, 410), b, "An ox or a man who aimed at another and struck a woman")
def svg_57():
    b = T(320, 34, "Ox and all other animals: the same for these laws", 19, 700, "#1b3a8a", "middle")
    b += U("bull", 30, 60, 110, 71) + U("goat", 160, 64, 90, 63) + U("ram", 262, 64, 90, 63) + U("lamb", 364, 66, 86, 60)
    b += '<g transform="translate(470,62)"><ellipse cx="38" cy="42" rx="26" ry="15" fill="#B58A52"/><path d="M58 34 Q70 18 66 8 L74 8 Q80 24 66 44Z" fill="#B58A52"/><circle cx="72" cy="8" r="9" fill="#B58A52"/><path d="M68 0 q-6 -10 -10 -6 M78 0 q6 -10 10 -6" stroke="#6E4B22" stroke-width="2.5" fill="none"/><rect x="18" y="52" width="5" height="22" fill="#8a6234"/><rect x="48" y="52" width="5" height="22" fill="#8a6234"/></g>'
    b += '<g transform="translate(570,70)"><ellipse cx="22" cy="28" rx="20" ry="13" fill="#4E8FB4"/><circle cx="46" cy="16" r="9" fill="#4E8FB4"/><path d="M53 16 l13 4 l-13 4Z" fill="#E0A82E"/><path d="M4 32 l-14 10 l16 -2Z" fill="#3b7192"/></g>'
    b += T(85, 148, "Ox", 14, 600, "#333", "middle") + T(307, 148, "Other beasts", 14, 600, "#333", "middle") + T(510, 148, "Wild animals", 14, 600, "#333", "middle") + T(592, 148, "Birds", 14, 600, "#333", "middle")
    laws = [("Falling into a pit", ""), ("Keeping away from Sinai", "Ex 19:13"), ("Two-fold restitution", "Ex 22:3, 8"), ("Lost property", "Ex 23:4, Dt 22:1"), ("Unloading", "Ex 23:5"), ("Muzzling", "Dt 25:4"), ("Diverse kinds", "Lev 19:19, Dt 22:10"), ("The Sabbath", "Ex 20:10, Dt 5:14")]
    for i, (t, r) in enumerate(laws):
        x = 12 + (i % 4) * 155; y = 176 + (i // 4) * 96
        b += f'<rect x="{x}" y="{y}" width="146" height="84" rx="12" fill="#e9eefb" stroke="#1b3a8a" stroke-width="1.5"/>' + multi(x + 73, y + 32, t, 16, 15, 18, w=600, fill="#1b3a8a", anchor="middle") + (T(x + 73, y + 72, r, 12, 400, "#445", "middle") if r else "")
    b += T(320, 392, "The Torah says ox because oxen were the most common animal.", 14, 400, "#444", "middle")
    return svg((640, 410), b, "An ox and all other animals are alike for eight laws")
def table(c):
    if not c: return ""
    head = "".join(f"<th>{esc(x)}</th>" for x in c["cols"]); rows = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>" for r in c["rows"])
    return f'<div class="chart"><h4>{esc(c["title"])}</h4><table><tr>{head}</tr>{rows}</table></div>'
def svg_bm15():
    groups = (("Belongs to him (the father or husband)", "#1b3a8a", [("A minor son or daughter", "child"), ("A Canaanite slave or female slave", "person"), ("His wife", "woman")]),
              ("Belongs to the finder", "#2c7a46", [("A grown son or daughter", "person"), ("A Hebrew slave or female slave", "person"), ("A wife he has divorced, even if her ketubah is unpaid", "woman")]))
    b = T(260, 34, "Who owns what a family member finds?", 19, 700, "#1b3a8a", "middle"); y = 54
    for title, col, rows in groups:
        b += f'<rect x="8" y="{y}" width="504" height="36" rx="10" fill="{col}"/>' + T(260, y + 24, title, 16, 700, "#fff", "middle"); y += 44
        for lab, sym in rows:
            h = 84
            b += f'<rect x="8" y="{y}" width="504" height="{h-6}" rx="10" fill="#ffffffaa" stroke="#d9cfbd"/>'
            b += (U("child", 34, y + 12, 28, 56, "#4E7A8C") if sym == "child" else U(sym, 30, y + 6, 36, 66, "#8C4A60" if sym == "woman" else "#4E7A8C"))
            b += multi(92, y + 34, lab, 34, 16, 20, w=600)
            y += h
        y += 8
    return svg((520, y + 6), b, "Who owns what a family member finds")
def svg_bm16():
    rows = [("Rabbi Meir", "", [("noreturn", "Does not return it"), ("return", "Returns it")]), ("The Sages", "", [("noreturn", "Does not return it"), ("noreturn", "Does not return it")])]
    return matrix("Found loan documents: return them?", ["Lien recorded", "No lien"], rows, 520, 150, 120, "The court collects from the property when there is a lien.", 62)
def svg_bm18():
    cards = [("return", "Court documents, letters of evaluation or sustenance, halitzah, refusal, arbitration"), ("return", "Documents in a satchel or bag, or a bundle of three tied together"),
             ("return", "Three documents where one man borrowed from three: to the borrower"), ("return", "Three documents where one man lent to three: to the lender"),
             ("hold", "A document of unknown nature among his own: leave it until Elijah comes"), ("follow", "A postscript with it: do what the postscript says")]
    b = T(260, 34, "Found documents: what to do", 19, 700, "#1b3a8a", "middle")
    for i, (k, t) in enumerate(cards):
        y = 52 + i * 92
        b += f'<rect x="8" y="{y}" width="504" height="84" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/>' + badge(k, 20, y + 12, 60) + multi(96, y + 34, t, 38, 16, 20, w=600)
    return svg((520, 52 + 6 * 92 + 4), b, "Found documents: what to do")
DIAG_BK5 = {3: svg_53, 4: svg_54, 5: svg_55, 7: svg_57}
DIAG_BM1 = {5: svg_bm15, 6: svg_bm16, 8: svg_bm18}
def fig(pic): return f'<figure class="pic"><img src="img/{pic[0]}" alt="{esc(pic[1])}" loading="lazy"><figcaption>{esc(pic[1])}</figcaption></figure>'
css = """:root{--bg:#f7f4ec;--fg:#222;--card:#fff;--blue:#1b3a8a;--tint:#f1f3fb}@media(prefers-color-scheme:dark){:root{--bg:#14161c;--fg:#e8e6df;--card:#1d2028;--tint:#232838}}
html{scroll-behavior:smooth}body{font:17px/1.55 'Public Sans',system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}header{background:var(--blue);color:#fff;padding:18px 24px}header h1{margin:0;font-family:Newsreader,Georgia,serif}
.pills{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 16px;border-bottom:1px solid #8884;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pills span{font-weight:600;margin-right:6px}
.pills a{display:inline-grid;place-items:center;min-width:38px;height:38px;border-radius:19px;background:var(--card);color:var(--blue);text-decoration:none;font-weight:700;border:1.5px solid var(--blue)}.pills a.on,.pills a:hover{background:var(--blue);color:#fff}
main{max-width:1240px;margin:auto;padding:12px 16px}section{scroll-margin-top:70px;margin:26px 0}section h2{font-family:Newsreader,Georgia,serif;margin:0 0 2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}@media(max-width:900px){.grid{grid-template-columns:1fr}.grid .text{order:-1}}
.panel{background:var(--card);border-radius:14px;padding:16px 20px;box-shadow:0 1px 4px #0002}.aids{background:var(--tint)}
.he{font:24px/1.9 'Times New Roman',serif;margin-bottom:10px}.sum{font-style:italic;opacity:.8;margin:0 0 10px}
h4{margin:12px 0 2px}ul{margin:0 0 4px;padding-left:22px}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:17px}td,th{border:1px solid #bbb8;padding:7px 10px;text-align:left}th{background:#1b3a8a22}.chart{margin:14px 0}.chart svg{width:100%;height:auto;display:block}
.pic{margin:16px 0}.pic img{width:100%;height:auto;border-radius:12px;display:block}figcaption{font-size:14px;opacity:.7;margin-top:4px}details{margin-top:10px}summary{cursor:pointer;font-weight:600}
.legend{background:var(--card);border-radius:12px;padding:12px 20px;margin:14px 0;display:flex;gap:0;align-items:center;flex-wrap:wrap}.legend .grp{display:flex;gap:18px;align-items:center;padding:0 22px;border-left:1px solid #8886}.legend .grp:first-child{padding-left:0;border-left:0}.b{width:44px;height:44px;vertical-align:middle;margin-right:6px}
.banner{background:#fff3cd;color:#5a4500;padding:10px 24px;font-size:14px}footer{font-size:12px;opacity:.7;padding:14px 24px;max-width:1240px;margin:auto}a{color:var(--blue)}"""
fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Newsreader:wght@500;700&family=Public+Sans:wght@400;600;700&display=swap" rel="stylesheet">'
head_html = lambda t: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{t}</title>{fonts}<style>{css}</style></head><body>{SPRITE}<svg style="position:absolute;width:0;height:0"><defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9D6EA"/><stop offset="1" stop-color="#F3EBDD"/></linearGradient></defs></svg>'
foot = '<footer>Hebrew: Mishnah, ed. Romm, Vilna 1913 (public domain). English translation and commentary: Mishnah Yomit by R. Joshua Kulp, via Sefaria, licensed CC-BY. Outlines, charts and diagrams drafted by Claude (Anthropic) from the mishnah and R. Kulp\'s text and under review. The illustrations are AI-generated; the round symbols are interim. Prototype for discussion, not for distribution.</footer>'
js = "<script>const L=[...document.querySelectorAll('.pills a')];const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){L.forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id))}}),{rootMargin:'-30% 0px -60% 0px'});document.querySelectorAll('section').forEach(s=>io.observe(s));</script>"
def leg(groups, extra=""):
    g = "".join('<div class="grp">' + "".join(f'<span><img class="b" src="img/badge-{k}.png" alt=""> <b>{esc(a)}</b> {esc(b)}</span>' for k, a, b in grp) + "</div>" for grp in groups)
    return '<div class="legend">' + g + extra + "</div>"
def build(data, layer1, diagrams, title, sub, outfile, legend):
    D = json.load(open(data)); L = {m["n"]: m for m in json.load(open(layer1))["mishnayot"]}; secs = []
    for m in D["mishnayot"]:
        n = m["n"]; a = L[n]
        ol = "".join(f'<h4>{esc(s["h"])}</h4><ul>' + "".join(f"<li>{esc(t)}</li>" for t, src in s["b"]) + "</ul>" for s in a["outline"])
        kul = "".join("<p>" + re.sub(r"<(?!/?b>)[^>]+>", " ", k).replace("<br>", " ") + "</p>" for k in m["kulp"][1:] if k)
        pics = (fig(a["picture"]) if a.get("picture") else "") + (fig(a["picture2"]) if a.get("picture2") else "")
        dg = diagrams[n]() if n in diagrams else ""
        kdet = f"<details><summary>R. Kulp's commentary</summary>{kul}</details>" if kul else ""
        secs.append(f'''<section id="m{n}"><h2>Mishnah {n}: {esc(a["title"])}</h2><p class="sum">{esc(a["summary"])}</p>
<div class="grid"><div class="panel aids">{ol}{table(a.get("chart")) if n not in diagrams else ""}{('<div class="chart">'+dg+'</div>') if dg else ""}</div>
<div class="panel text"><div class="he" lang="he" dir="rtl">{clean(m["he"])}</div><div class="en">{clean(m["en"])}</div>{pics}{kdet}</div></div></section>''')
    pills = '<nav class="pills"><span>Jump to mishnah</span>' + "".join(f'<a href="#m{m["n"]}">{m["n"]}</a>' for m in D["mishnayot"]) + '</nav>'
    page = head_html(title) + f'<header><h1>{esc(title)}</h1><div>{esc(sub)}</div></header><div class="banner">Prototype draft for review. The deeper layer (from Kehati) is not built yet. <a href="index.html">All chapters</a></div>' + pills + "<main>" + legend + "".join(secs) + "</main>" + foot + js + "</body></html>"
    open(outfile, "w").write(page); print(outfile, len(page))
PAY = [("pay", "pays", "(is liable)"), ("notpay", "does not pay", "(is exempt)")]
build("data/bava_kamma_5.json", "data/bava_kamma_5_layer1.json", DIAG_BK5, "Mishnah Bava Kamma, chapter 5", "Outlines, charts and pictures", "site/bava-kamma-5.html",
      leg([PAY], '<div class="grp"><span>A <b>?</b> between two boxes: the two possibilities the mishnah decides between.</span></div>'))
build("data/bava_metzia_1.json", "data/bava_metzia_1_layer1.json", DIAG_BM1, "Mishnah Bava Metzia, chapter 1", "Outlines, charts and pictures", "site/bava-metzia-1.html",
      leg([[("keeps", "keeps it", ""), ("noclaim", "has no claim", "")], [("return", "returns it", ""), ("noreturn", "does not return it", "")], [("hold", "holds it", ""), ("follow", "follows the postscript", "")]], '<div class="grp"><span>A <b>?</b> between two boxes: the two possibilities the mishnah decides between.</span></div>'))
open("site/index.html", "w").write(head_html("AnyMishnah prototype") + '<header><h1>AnyMishnah (prototype)</h1><div>Mishnah with outlines, charts and illustrations</div></header><div class="banner">Prototype for review. Link-only; not indexed.</div><main><div class="panel"><h2>Chapters so far</h2><ul><li><a href="bava-kamma-5.html">Bava Kamma, chapter 5</a> (pit, courtyard and ox cases; 7 mishnayot)</li><li><a href="bava-metzia-1.html">Bava Metzia, chapter 1</a> (found objects and documents; 8 mishnayot)</li></ul></div></main>' + foot + "</body></html>")
