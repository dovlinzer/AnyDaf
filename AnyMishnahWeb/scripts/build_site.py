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
             ("hold", "A document of unknown nature among his own: leave it until Elijah comes"), ("follow", "A simpon (a note attached to the documents): do what it says")]
    b = T(260, 34, "Found documents: what to do", 19, 700, "#1b3a8a", "middle")
    for i, (k, t) in enumerate(cards):
        y = 52 + i * 92
        b += f'<rect x="8" y="{y}" width="504" height="84" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/>' + badge(k, 20, y + 12, 60) + multi(96, y + 34, t, 38, 16, 20, w=600)
    return svg((520, 52 + 6 * 92 + 4), b, "Found documents: what to do")
DIAG_BK5 = {3: svg_53, 4: svg_54, 5: svg_55, 7: svg_57}
DIAG_BM1 = {5: svg_bm15, 6: svg_bm16, 8: svg_bm18}
import os
OV = json.load(open("data/overlays.json")) if os.path.exists("data/overlays.json") else {}
OV_OLD = json.load(open("data/overlays_older.json")) if os.path.exists("data/overlays_older.json") else {}
def stage(spec, pic, base=""):
    W, H = spec["w"], spec["h"]; pct = lambda v, t: f"{100 * v / t:.3f}%"; hot = ""; ov = ""
    for i, h in enumerate(spec["hotspots"]):
        l, t, r, b = h["rect"]
        q = str(i + 1) if len(spec["hotspots"]) > 1 else "?"; ans = h.get("answer", "").replace("tag-", "")
        hot += f'<button class="hot" data-h="{i}" data-ans="{esc(ans)}" data-q="{esc(q)}" aria-pressed="false" aria-label="{esc(h["label"])}" style="left:{pct(l,W)};top:{pct(t,H)};width:{pct(r-l,W)};height:{pct(b-t,H)}"></button>'
        for bd in h["badges"]:
            tr = "translate(-50%,-50%)" if bd["anchor"] == "center" else "translate(-50%,-100%)"
            ov += f'<img class="ov" data-h="{i}" src="img/{bd["src"]}" alt="" style="left:{pct(bd["x"],W)};top:{pct(bd["y"],H)};width:{pct(bd["w"],W)};--t:{tr}">'
    return f'<div class="stage"><img src="{spec["clean"]}" alt="{esc(pic[1])}" loading="lazy">{hot}{ov}</div>'
TRAY = []
def quiz_ui(spec):
    if not TRAY: return ""
    tb = "".join(f'<button class="tb" type="button" data-k="{k}" aria-label="{esc(name)}" title="{esc(name)}"><img src="img/badge-{k}.png" alt="" draggable="false"></button>' for k, name in TRAY)
    hs = spec["hotspots"]; many = len(hs) > 1
    ask = " ".join(f'<span class="qa">{("<b>%d</b> " % (i + 1)) if many else ""}{esc("What goes on the picture?" if h["label"].startswith("Show") else h["label"])}</span>' for i, h in enumerate(hs))
    return f'<div class="qask qonly">{ask}</div><div class="tray qonly"><span class="tl">Badges</span>{tb}</div><div class="qmsg qonly" role="status" aria-live="polite"></div>'
QBTN = ' <span class="qonly qbtns"><button class="qshow" type="button">Show answers</button><button class="qreset" type="button">Try again</button></span>'
QHINT = '<span class="qonly qhint">Drag a badge from the tray onto the picture, or tap a badge and then tap where it belongs.</span>'
def variant(aud, mode, inner, cap, note=""):
    n = f' <span class="note">{esc(note)}</span>' if note else ""
    return f'<figure class="pic v" data-aud="{aud}" data-mode="{mode}">{inner}<figcaption><span class="ctext">{esc(cap)}{n}</span></figcaption></figure>'
def fig(pic):
    """Four variants (younger/older x static/interactive); CSS shows the one chosen in the toolbar.
    Younger static = the original composed picture with badges baked in. Older pictures live in site/img/older/<pid>.jpg (static, badges baked)
    and site/img/older/clean/<pid>.jpg + data/overlays_older.json (interactive); until they exist the older choice shows the younger picture with a note."""
    pid = pic[0].rsplit(".", 1)[0]; spec = OV.get(pid); cap = pic[1]
    btn = ' <span class="hint">%s</span> <button class="all" type="button">Show all</button>'
    if not spec: y_i = variant("y", "i", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap)
    else: y_i = variant("y", "i", stage(spec, pic) + quiz_ui(spec), cap).replace("</figcaption>", (btn % esc(spec["hint"])) + QBTN + QHINT + "</figcaption>")
    y_s = variant("y", "s", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap)
    old_s = os.path.exists(f"site/img/older/{pid}.jpg"); spec_o = OV_OLD.get(pid)
    miss = "Older-audience picture not made yet; showing the younger one."
    if old_s: o_s = variant("o", "s", f'<img src="img/older/{pid}.jpg" alt="{esc(cap)}" loading="lazy">', cap)
    else: o_s = variant("o", "s", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap, miss)
    if spec_o: o_i = variant("o", "i", stage(spec_o, pic) + quiz_ui(spec_o), cap).replace("</figcaption>", (btn % esc(spec_o["hint"])) + QBTN + QHINT + "</figcaption>")
    elif spec: o_i = variant("o", "i", stage(spec, pic) + quiz_ui(spec), cap, miss).replace("</figcaption>", (btn % esc(spec["hint"])) + QBTN + QHINT + "</figcaption>")
    else: o_i = variant("o", "i", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap, miss)
    return y_i + y_s + o_i + o_s
css = """:root{--bg:#f7f4ec;--fg:#222;--card:#fff;--blue:#1b3a8a;--tint:#f1f3fb}@media(prefers-color-scheme:dark){:root{--bg:#14161c;--fg:#e8e6df;--card:#1d2028;--tint:#232838}}
html{scroll-behavior:smooth}body{font:17px/1.55 'Public Sans',system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}header{background:var(--blue);color:#fff;padding:18px 24px}header h1{margin:0;font-family:Newsreader,Georgia,serif}
.pills{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 16px;border-bottom:1px solid #8884;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pills span{font-weight:600;margin-right:6px}
.pills a{display:inline-grid;place-items:center;min-width:38px;height:38px;border-radius:19px;background:var(--card);color:var(--blue);text-decoration:none;font-weight:700;border:1.5px solid var(--blue)}.pills a.on,.pills a:hover{background:var(--blue);color:#fff}
main{max-width:1240px;margin:auto;padding:12px 16px}section{scroll-margin-top:70px;margin:26px 0}section h2{font-family:Newsreader,Georgia,serif;margin:0 0 2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}@media(max-width:900px){.grid{grid-template-columns:1fr}.grid .text{order:-1}}
.grid>*{min-width:0}td,th{overflow-wrap:anywhere}.panel{background:var(--card);border-radius:14px;padding:16px 20px;box-shadow:0 1px 4px #0002}.aids{background:var(--tint)}
.he{font:24px/1.9 'Times New Roman',serif;margin-bottom:10px}.sum{font-style:italic;opacity:.8;margin:0 0 10px}
h4{margin:12px 0 2px}ul{margin:0 0 4px;padding-left:22px}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:17px}td,th{border:1px solid #bbb8;padding:7px 10px;text-align:left}th{background:#1b3a8a22}.chart{margin:14px 0}.chart svg{width:100%;height:auto;display:block}
.stage{position:relative}.hot{position:absolute;background:transparent;border:2px dashed transparent;border-radius:10px;cursor:pointer;padding:0}.hot:hover,.hot:focus-visible{border-color:#1b3a8acc;background:#ffffff1f;outline:none}
.hot::after{content:"tap";position:absolute;left:50%;bottom:6px;transform:translateX(-50%);background:#1b3a8acc;color:#fff;font:600 12px 'Public Sans',sans-serif;padding:2px 9px;border-radius:10px;opacity:.9;animation:tp 2.2s ease-in-out infinite}.hot[aria-pressed=true]::after{display:none}
@keyframes tp{50%{opacity:.35}}.ov{position:absolute;height:auto;opacity:0;transform:var(--t) scale(.5);transition:opacity .25s,transform .25s;pointer-events:none;filter:drop-shadow(0 3px 4px #0006)}.ov.on{opacity:1;transform:var(--t) scale(1)}
.hint{opacity:.85;font-style:italic}.all{margin-left:8px;font:600 12px 'Public Sans',sans-serif;border:1.5px solid var(--blue);color:var(--blue);background:var(--card);border-radius:12px;padding:1px 10px;cursor:pointer}
.pic{margin:16px 0}.pic img{width:100%;height:auto;border-radius:12px;display:block}figcaption{font-size:14px;opacity:.7;margin-top:4px}details{margin-top:10px}summary{cursor:pointer;font-weight:600}
.legend{background:var(--card);border-radius:12px;padding:12px 20px;margin:14px 0;display:flex;gap:0;align-items:center;flex-wrap:wrap}.legend .grp{display:flex;gap:18px;align-items:center;padding:0 22px;border-left:1px solid #8886}.legend .grp:first-child{padding-left:0;border-left:0}.legend .grp>span{display:flex;align-items:center;gap:8px}.legend .t{display:block}.b{flex:none}.b.wide{width:auto;height:40px}\n@media(max-width:1000px){.legend{flex-direction:column;align-items:stretch}.legend .grp{flex-wrap:wrap;padding:12px 0;border-left:0;border-top:1px solid #8886;gap:10px 22px}.legend .grp:first-child{border-top:0;padding-top:0}.legend .grp:last-child{padding-bottom:0}}.b{width:44px;height:44px;vertical-align:middle;margin-right:6px}
.v{display:none}html[data-aud=y][data-mode=i] .v[data-aud=y][data-mode=i],html[data-aud=y][data-mode=s] .v[data-aud=y][data-mode=s],html[data-aud=o][data-mode=i] .v[data-aud=o][data-mode=i],html[data-aud=o][data-mode=s] .v[data-aud=o][data-mode=s],html[data-aud=y][data-mode=q] .v[data-aud=y][data-mode=i],html[data-aud=o][data-mode=q] .v[data-aud=o][data-mode=i]{display:block}html[data-mode=s] .ionly,html[data-mode=q] .ionly,html:not([data-mode=q]) .qlegend{display:none}.note{font-style:italic;color:#8a5a00}
.qonly,.qs{display:none}html[data-mode=q] .qonly{display:block}html[data-mode=q] .qs{display:inline}html[data-mode=q] .qbtns,html[data-mode=q] .qhint{display:inline}html[data-mode=q] .all,html[data-mode=q] .hint,html[data-mode=q] .ctext{display:none}
.tray{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--tint);border-radius:12px;padding:8px 12px;margin-top:8px}html:not([data-mode=q]) .tray{display:none}.tl{font-weight:600;font-size:13px;opacity:.75}.tb{border:2px solid transparent;background:var(--card);border-radius:12px;padding:3px 6px;cursor:grab;touch-action:none;user-select:none}.tb img{height:46px;width:auto;display:block;border-radius:0;pointer-events:none}.tb.sel{border-color:var(--blue);box-shadow:0 0 0 3px #1b3a8a33}
.ghost{position:fixed;height:52px;width:auto;transform:translate(-50%,-50%);pointer-events:none;z-index:60;filter:drop-shadow(0 6px 8px #0006);opacity:.95}
html[data-mode=q] .hot{border:2px dashed #1b3a8acc;background:#ffffff26}html[data-mode=q] .hot::after{content:attr(data-q);left:5px;top:5px;bottom:auto;transform:none;min-width:22px;text-align:center;border-radius:12px;padding:1px 7px;font-size:13px;animation:none;opacity:.95}.ov{z-index:3}.qask{display:none;gap:4px 16px;flex-wrap:wrap;font-size:14px;margin-top:8px}html[data-mode=q] .qask{display:flex}.qa b{background:#1b3a8acc;color:#fff;border-radius:10px;padding:0 7px;margin-right:2px}html[data-mode=q] .hot.ok::after{display:none}html[data-mode=q] .hot.ok{border-color:#2a8a4acc;border-style:solid;background:transparent}html[data-mode=q] .hot.over{background:#1b3a8a33;border-style:solid}html[data-mode=q] .hot.gave{border-color:#c98a00cc}
.hot.wrong{animation:shk .45s;border-color:#c0392b!important;background:#c0392b33!important}.hot.right{box-shadow:0 0 0 4px #2a8a4a88}@keyframes shk{20%,60%{transform:translateX(-7px)}40%,80%{transform:translateX(7px)}}
.qmsg{font-size:15px;font-weight:600;min-height:1.4em;margin-top:6px}.qmsg.good{color:#1f7a3d}.qmsg.bad{color:#b03a2e}.qbtns button{margin-left:8px;font:600 12px 'Public Sans',sans-serif;border:1.5px solid var(--blue);color:var(--blue);background:var(--card);border-radius:12px;padding:1px 10px;cursor:pointer}.qhint{font-style:italic;opacity:.85}.qs{font-weight:600}
.opts{display:flex;gap:22px;flex-wrap:wrap;align-items:center;padding:8px 16px;background:var(--tint);border-bottom:1px solid #8884;font-size:14px}.opts b{margin-right:6px}.seg{display:inline-flex;border:1.5px solid var(--blue);border-radius:16px;overflow:hidden}.seg button{font:600 13px 'Public Sans',sans-serif;border:0;background:var(--card);color:var(--blue);padding:4px 14px;cursor:pointer}.seg button[aria-pressed=true]{background:var(--blue);color:#fff}
.grid3{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:18px;align-items:start}@media(max-width:1000px){.grid3{grid-template-columns:1fr}}.grid3>*{min-width:0}.grid3 h3{margin:0 0 6px;font-family:Newsreader,Georgia,serif}.pr li{margin:0 0 10px}.refs{white-space:nowrap}.mref{font-size:12px;font-weight:600;background:var(--card);border:1px solid var(--blue);border-radius:9px;padding:0 6px;margin-left:4px;text-decoration:none}.pnote{font-size:14px;opacity:.8;font-style:italic}dl{margin:0}dt{margin-top:10px}dd{margin:2px 0 0}dt .he{font-size:18px;margin:0 4px}.debate{margin:0 0 14px}.debate h4{margin:0 0 4px}.sides{display:grid;gap:8px}.sides p{margin:2px 0 0}.sides>div{background:var(--card);border-radius:10px;padding:8px 12px}
.banner{background:#fff3cd;color:#5a4500;padding:10px 24px;font-size:14px}footer{font-size:12px;opacity:.7;padding:14px 24px;max-width:1240px;margin:auto}a{color:var(--blue)}"""
fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Newsreader:wght@500;700&family=Public+Sans:wght@400;600;700&display=swap" rel="stylesheet">'
HEAD_JS = '<script>(function(){var d=document.documentElement,a="y",m="i";try{a=localStorage.getItem("mAud")||a;m=localStorage.getItem("mMode")||m}catch(e){}d.dataset.aud=a;d.dataset.mode=m})()</script>'
head_html = lambda t: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{t}</title>{fonts}<style>{css}</style>{HEAD_JS}</head><body>{SPRITE}<svg style="position:absolute;width:0;height:0"><defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9D6EA"/><stop offset="1" stop-color="#F3EBDD"/></linearGradient></defs></svg>'
foot = '<footer>Hebrew: Mishnah, ed. Romm, Vilna 1913 (public domain). English translation and commentary: Mishnah Yomit by R. Joshua Kulp, via Sefaria, licensed CC-BY. Outlines, charts and diagrams drafted by Claude (Anthropic) from the mishnah and R. Kulp\'s text and under review. The illustrations are AI-generated; the round symbols are interim. Prototype for discussion, not for distribution.</footer>'
JS = r"""<script>
(function(){
var root=document.documentElement, sel=null;
function $$(q,r){return [].slice.call((r||document).querySelectorAll(q))}
function msg(fig,t,c){var m=fig.querySelector('.qmsg');if(m){m.textContent=t;m.className='qmsg qonly '+(c||'')}}
function score(){var ok=0,n=0,done=0;$$('.v[data-mode=i]').filter(function(f){return f.offsetParent!==null&&f.querySelector('.tray')}).forEach(function(f){$$('.hot',f).forEach(function(h){n++;if(h._done)done++;if(h._first)ok++})});var e=document.getElementById('qscore');if(e)e.textContent='Quiz: '+ok+' of '+n+' right on the first try'+(done<n?' ('+(n-done)+' still to place)':'')}
function resetQuiz(){sel=null;$$('.stage').forEach(function(st){var hs=$$('.hot',st);hs.forEach(function(h,i){st._set(i,false);h.classList.remove('ok','wrong','right','over','gave');h._t=0;h._first=false;h._done=false});var f=st.parentElement;$$('.tb',f).forEach(function(b){b.classList.remove('sel')});msg(f,'')});score()}
function select(fig,b){var same=sel&&sel.fig===fig&&sel.kind===b.dataset.k;$$('.tb.sel').forEach(function(x){x.classList.remove('sel')});if(same){sel=null;return}sel={fig:fig,kind:b.dataset.k};b.classList.add('sel')}
function finished(st){var hs=$$('.hot',st);if(hs.every(function(h){return h._done})){var ok=hs.filter(function(h){return h._first}).length;msg(st.parentElement,'All placed: '+ok+' of '+hs.length+' right on the first try.','good')}}
function place(st,h,k){if(h._done)return;var fig=st.parentElement,i=st._hs.indexOf(h);if(k===h.dataset.ans){h._first=!(h._t>0);h._done=true;st._set(i,true);h.classList.add('ok','right');setTimeout(function(){h.classList.remove('right')},900);msg(fig,h._first?'Right!':'Right, on another try.','good');finished(st)}else{h._t=(h._t||0)+1;h.classList.add('wrong');setTimeout(function(){h.classList.remove('wrong')},500);msg(fig,'Not that one. Look at the picture again and try another badge.','bad')}score()}
$$('.seg').forEach(function(g){var k=g.dataset.key,K=k==='aud'?'mAud':'mMode';function sync(){$$('button',g).forEach(function(b){b.setAttribute('aria-pressed',b.dataset.v===root.dataset[k])})}sync();$$('button',g).forEach(function(b){b.addEventListener('click',function(){root.dataset[k]=b.dataset.v;try{localStorage.setItem(K,b.dataset.v)}catch(e){}sync();if(k==='mode')resetQuiz();else score()})})});
$$('.stage').forEach(function(st){var hs=$$('.hot',st),fig=st.parentElement;function set(i,on){hs[i].setAttribute('aria-pressed',on);$$('.ov[data-h="'+i+'"]',st).forEach(function(o){o.classList.toggle('on',on)})}st._set=set;st._hs=hs;
hs.forEach(function(h,i){h.addEventListener('click',function(){if(root.dataset.mode==='q'){if(!sel||sel.fig!==fig){msg(fig,'Pick a badge from the tray first, then tap where it belongs.','');return}place(st,h,sel.kind)}else set(i,h.getAttribute('aria-pressed')!=='true')})});
var btn=fig.querySelector('.all');if(btn)btn.addEventListener('click',function(){var on=btn.textContent==='Show all';hs.forEach(function(_,i){set(i,on)});btn.textContent=on?'Hide all':'Show all'});
var show=fig.querySelector('.qshow'),rs=fig.querySelector('.qreset');
if(show)show.addEventListener('click',function(){hs.forEach(function(h,i){if(!h._done){h._done=true;h._first=false;set(i,true);h.classList.add('ok','gave')}});msg(fig,'Answers shown.','');score()});
if(rs)rs.addEventListener('click',function(){sel=null;hs.forEach(function(h,i){set(i,false);h.classList.remove('ok','wrong','right','over','gave');h._t=0;h._first=false;h._done=false});$$('.tb',fig).forEach(function(b){b.classList.remove('sel')});msg(fig,'');score()});
$$('.tb',fig).forEach(function(b){
b.addEventListener('click',function(e){if(e.detail===0&&root.dataset.mode==='q')select(fig,b)});
b.addEventListener('pointerdown',function(e){if(root.dataset.mode!=='q')return;e.preventDefault();var sx=e.clientX,sy=e.clientY,ghost=null,over=null;try{b.setPointerCapture(e.pointerId)}catch(x){}
function tgt(x,y){return document.elementsFromPoint(x,y).filter(function(n){return n.classList&&n.classList.contains('hot')&&st.contains(n)})[0]||null}
function mv(ev){if(!ghost&&Math.hypot(ev.clientX-sx,ev.clientY-sy)>6){ghost=b.querySelector('img').cloneNode();ghost.className='ghost';document.body.appendChild(ghost)}if(ghost){ghost.style.left=ev.clientX+'px';ghost.style.top=ev.clientY+'px';var t=tgt(ev.clientX,ev.clientY);if(over&&over!==t)over.classList.remove('over');if(t)t.classList.add('over');over=t}}
function up(ev){b.removeEventListener('pointermove',mv);b.removeEventListener('pointerup',up);b.removeEventListener('pointercancel',up);if(over)over.classList.remove('over');if(ghost){ghost.remove();var t=ev.type==='pointerup'?tgt(ev.clientX,ev.clientY):null;if(t){sel={fig:fig,kind:b.dataset.k};place(st,t,b.dataset.k)}}else if(ev.type==='pointerup')select(fig,b)}
b.addEventListener('pointermove',mv);b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up)})})});
var L=$$('.pills a');var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){L.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id)})}})},{rootMargin:'-30% 0px -60% 0px'});$$('section').forEach(function(s){io.observe(s)});
resetQuiz();
})();
</script>"""
js = JS
def leg(groups, extra=""):
    g = "".join('<div class="grp">' + "".join(f'<span><img class="b{" wide" if k.startswith("pay-") else ""}" src="img/badge-{k}.png" alt=""><span class="t"><b>{esc(a)}</b> {esc(b)}</span></span>' for k, a, b in grp) + "</div>" for grp in groups)
    return '<div class="legend">' + g + extra + "</div>"
def summary_html(path, base):
    if not os.path.exists(path): return ""
    S = json.load(open(path)); refs = lambda ms: "".join(f'<a class="mref" href="#m{n}">{base}:{n}</a>' for n in ms)
    pr = "".join(f'<li>{esc(x["t"])} <span class="refs">{refs(x["m"])}</span>' + (f'<div class="pnote">{esc(x["note"])}</div>' if x.get("note") else "") + "</li>" for x in S["principles"])
    tm = "".join(f'<dt><b>{esc(x["term"])}</b> <span class="he" lang="he" dir="rtl">{esc(x["he"])}</span> <span class="refs">{refs(x["m"])}</span></dt><dd>{esc(x["def"])}</dd>' for x in S["terms"])
    db = "".join(f'<div class="debate"><h4>{esc(x["title"])} <span class="refs">{refs([x["m"]])}</span></h4><div class="sides"><div><b>View 1</b><p>{esc(x["a"])}</p></div><div><b>View 2</b><p>{esc(x["b"])}</p></div></div></div>' for x in S["debates"])
    return (f'<section id="summary"><h2>Chapter summary</h2><p class="sum">{esc(S["status"])}</p><div class="grid3">'
            f'<div class="panel aids"><h3>Key principles</h3><ol class="pr">{pr}</ol></div>'
            f'<div class="panel aids"><h3>Key terms</h3><dl>{tm}</dl></div>'
            f'<div class="panel aids"><h3>Key debates</h3>{db}</div></div></section>')
def build(data, layer1, diagrams, title, sub, outfile, legend, tray=()):
    TRAY[:] = list(tray)
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
    opts = '<div class="opts"><span><b>Illustrations for</b><span class="seg" data-key="aud"><button type="button" data-v="y">Younger</button><button type="button" data-v="o">Older</button></span></span><span><b>Mode</b><span class="seg" data-key="mode"><button type="button" data-v="s">Static</button><button type="button" data-v="i">Explore</button><button type="button" data-v="q">Quiz</button></span></span><span class="qs" id="qscore"></span></div>'
    pills = '<nav class="pills"><span>Jump to mishnah</span>' + "".join(f'<a href="#m{m["n"]}">{m["n"]}</a>' for m in D["mishnayot"]) + '<a href="#summary" style="padding:0 14px">Summary</a></nav>'
    page = head_html(title) + f'<header><h1>{esc(title)}</h1><div>{esc(sub)}</div></header><div class="banner">Prototype draft for review. The deeper layer (from Kehati) is not built yet. <a href="index.html">All chapters</a></div>' + opts + pills + "<main>" + legend + "".join(secs) + summary_html(data.replace(".json", "_summary.json"), D["chapter"] if isinstance(D["chapter"], int) else str(D["chapter"]).split()[-1]) + "</main>" + foot + js + "</body></html>"
    open(outfile, "w").write(page); print(outfile, len(page))
TRAY_BK = [("pay", "pays"), ("notpay", "does not pay"), ("pay-half", "pays half"), ("pay-quarter", "pays a quarter")]
TRAY_BM = [("keeps", "keeps it"), ("noclaim", "has no claim"), ("return", "returns it"), ("noreturn", "does not return it"), ("hold", "holds it"), ("follow", "follows the simpon"), ("half-half", "splits in half"), ("3q-1q", "three quarters and a quarter")]
QL = '<div class="grp qlegend"><span><span class="t"><b>Quiz:</b> drag the right badge onto the picture, box or person.</span></span></div>'
PAY = [("pay", "pays", "(is liable)"), ("notpay", "does not pay", "(is exempt)")]
build("data/bava_kamma_5.json", "data/bava_kamma_5_layer1.json", DIAG_BK5, "Mishnah Bava Kamma, chapter 5", "Outlines, charts and pictures", "site/bava-kamma-5.html",
      leg([PAY, [("pay-half", "pays half", ""), ("pay-quarter", "pays a quarter", "")]], '<div class="grp"><span><span class="t">A <b>?</b> between two boxes: the two possibilities the mishnah decides between.</span></span></div><div class="grp ionly"><span><span class="t"><b>Tap</b> a picture, a box or a person to see the ruling.</span></span></div>' + QL), tray=TRAY_BK)
build("data/bava_metzia_1.json", "data/bava_metzia_1_layer1.json", DIAG_BM1, "Mishnah Bava Metzia, chapter 1", "Outlines, charts and pictures", "site/bava-metzia-1.html",
      leg([[("keeps", "keeps it", ""), ("noclaim", "has no claim", "")], [("return", "returns it", ""), ("noreturn", "does not return it", "")], [("hold", "holds it", ""), ("follow", "follows the simpon", "(the attached note)")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a picture, a box or a person to see the ruling.</span></span></div>' + QL), tray=TRAY_BM)
open("site/index.html", "w").write(head_html("AnyMishnah prototype") + '<header><h1>AnyMishnah (prototype)</h1><div>Mishnah with outlines, charts and illustrations</div></header><div class="banner">Prototype for review. Link-only; not indexed.</div><main><div class="panel"><h2>Chapters so far</h2><ul><li><a href="bava-kamma-5.html">Bava Kamma, chapter 5</a> (pit, courtyard and ox cases; 7 mishnayot)</li><li><a href="bava-metzia-1.html">Bava Metzia, chapter 1</a> (found objects and documents; 8 mishnayot)</li></ul></div></main>' + foot + "</body></html>")
