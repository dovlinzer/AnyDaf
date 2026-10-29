"""Build site/index.html and site/bava-kamma-5.html from data/bava_kamma_5.json (Sefaria) and data/bava_kamma_5_layer1.json.
Pictures (site/img/bk5-*.jpg) come from compose_bk5.py. The AnyDaf sprite (site/sprite.svg) is inlined for the diagrams."""
import html, json, re, os, sys
# ---- Hebrew pages: LANG is 'en' (normal), 'collect' (record every English string that reaches the page) or 'he' (substitute data/he/strings.json)
LANG = "en"; HE = {}; SEEN = {}; CTX = "ui"   # SEEN: English string -> where it appears (chapter:mN, chapter:summary, ui)
def tr(s):
    if not isinstance(s, str): return s
    if LANG == "collect" and re.search(r"[A-Za-z]{2}", s): SEEN.setdefault(s, CTX)
    elif LANG == "he": return HE.get(s, s)
    return s
SPRITE = re.sub(r"<svg class=\"sprite\"", '<svg class="sprite" style="position:absolute;width:0;height:0"', open("site/sprite.svg").read())
def clean(s): return re.sub(r"<[^>]+>", "", s or "")
def en_html(s): return re.sub(r"&lt;(/?)(b|i)&gt;", r"<\1\2>", html.escape(s or ""))

GLOSS = {}; CUR_TR = ""
TERMS = {"avot nezikin": ("avot nezikin", "primary causes of injury"), "shor": ("shor", "ox"), "bor": ("bor", "pit"), "mav'eh": ("mav'eh", "crop-destroying beast"), "hev'er": ("hev'er", "fire"),
         "mazik": ("mazik", "damaging party"), "nizak": ("nizak", "damaged party"), "meilah": ("me'ilah", "misuse of consecrated property"),
         "tam": ("tam", "unattested danger", "tamim", "unattested dangers"), "muad": ("mu'ad", "attested danger", "mu'adim", "attested dangers")}
_MK = re.compile(r"\{\{([a-z' ]+?)(?:\|(a|A|the|The|p|i))?\}\}")
_MU = re.compile(r"\[\[([a-z]+)\|([^\]]+)\]\]")
MEASURES = json.load(open("data/measures.json"))["units"]
def _mu(h): return _MU.sub(lambda m: f'<span class="mu" data-m="{m.group(1)}" tabindex="0" role="button" title="Measure: tap for sizes">{m.group(2)}</span>', h)
def smooth_html(s, many=False):
    """English text with {{term|a/the/p}} markers: the first use in a mishnah shows the pair (italic term + gloss, order follows the 'Terms first' choice); later uses show the bare term or gloss with a dotted underline (a key term, tap/hover for the other form)."""
    seen = set()
    if many: return _mu("".join("<p>" + _sm1(x, seen) + "</p>" for x in s))
    return _mu(_sm1(s, seen))
def _sm1(s, seen):
    out, last = [], 0
    for m in _MK.finditer(s):
        k, opt = m.group(1), m.group(2) or ""
        tr, en = TERMS[k][0], TERMS[k][1]
        if opt == "p" and len(TERMS[k]) > 2: tr, en = TERMS[k][2], TERMS[k][3]
        art_en = {"a": ("an " if en[0] in "aeiou" else "a "), "A": ("An " if en[0] in "aeiou" else "A "), "the": "the ", "The": "The "}.get(opt, "")
        art_he = {"a": ("an " if tr[0] in "aeiou" else "a "), "A": ("An " if tr[0] in "aeiou" else "A "), "the": "the ", "The": "The "}.get(opt, "")
        out.append(en_html(s[last:m.start()])); last = m.end()
        e, h = html.escape(en), html.escape(tr)
        linked = bool(GLOSS.get(k, {}).get("def"))
        dk = f' data-k="{k}" tabindex="0" role="button"' if linked else ""
        if opt == "i":   # incidental technical term: English first, term in parentheses and underlined, in either setting; links to the glossary
            out.append(f'{e} (<span class="kti"{dk} title="Technical term, mentioned here in passing: click for the glossary entry">{h}</span>)'); continue
        if k not in seen:
            seen.add(k)
            out.append(f'<span class="kt1"{dk}><span class="t-en">{art_en}{e} (<i>{h}</i>)</span><span class="t-he">{art_he}<i>{h}</i> ({e})</span></span>')
        else:
            out.append(f'<span class="{'kt' if linked else 'ktn'}"{dk} title="{h}: {e}"><span class="t-en">{art_en}{e}</span><span class="t-he">{art_he}{h}</span></span>')
    out.append(en_html(s[last:])); return "".join(out)
def esc(s): return html.escape(tr(s))
# key Hebrew terms (transliterations) are shown in italics throughout; I() = escape + italicise
KEYTERMS = ["hamotzi mechavero alav hara'ayah", "acharayut nekhasim", "avot nezikin", "av nezikin", "mu'ad", "muad", "mav'eh", "hev'er", "tzrarot", "gerama", "grama", "apotropos", "simpon", "zakhah",
            "nezek", "kofer", "dayo", "tefachim", "tefach", "regel", "keren", "shen", "shor", "bor", "esh", "tam", "Baraita", "Tosefta"]
_KT = re.compile(r"(?<![A-Za-z'\u2019])(" + "|".join(re.escape(k).replace("'", "['\u2019]") for k in sorted(KEYTERMS, key=len, reverse=True)) + r")(?![A-Za-z])", re.I)
def I(s):
    if LANG != "en": return html.escape(tr(s))
    out, last = [], 0
    for m in _KT.finditer(s or ""):
        out.append(html.escape(s[last:m.start()])); out.append("<i>" + html.escape(m.group(0)) + "</i>"); last = m.end()
    out.append(html.escape((s or "")[last:])); return "".join(out)
# ---- term pairs: "attested danger (mu'ad)" can show English-first or Hebrew-first (toolbar option "Terms first")
_GL = [("mu'ad", r"attested dangers?"), ("muad", r"attested dangers?"), ("tam", r"unattested dangers?"), ("shen", r"tooth"), ("regel", r"foot"), ("keren", r"horn"), ("kofer", r"ransom"),
       ("avot nezikin", r"(?:primary|archetypal) causes of (?:injury|damage)"), ("bor", r"pit"), ("shor", r"ox"), ("mav'eh", r"crop-destroying beast"), ("hev'er", r"fire"), ("esh", r"fire"), ("nezek", r"damage"),
       ("apotropos", r"guardian"), ("zakhah", r"acquire"), ("acharayut nekhasim", r"lien"), ("simpon", r"postscripts?"), ("tefach", r"handbreadth"), ("grama", r"indirect cause")]
_TP = re.compile(r"(?<![A-Za-z'\u2019])(?:(?P<art>an?|the|An?|The)\s+)?(?P<en>" + "|".join(f"(?:{g})(?=\\s+\\()" for _, g in _GL) + r")\s*\((?P<he>" + "|".join(re.escape(t).replace("'", "['\u2019]") for t, _ in _GL) + r")\)")
def _art(a, he):
    if not a: return ""
    if a.lower() == "the": return a + " "
    w = ("An " if a[0] == "A" else "an ") if he[0] in "aeiou" else ("A " if a[0] == "A" else "a ")
    return w
def TT(s):
    if LANG != "en": return html.escape(tr(s))
    """escape + italic key terms; each 'English (term)' pair becomes both orders, CSS shows the chosen one."""
    s = s or ""; out, last = [], 0
    for m in _TP.finditer(s):
        a, en, he = m.group("art"), m.group("en"), m.group("he")
        plural = en.lower().endswith("s") and en.lower() not in ("simpon",) and he not in ("simpon",) and ("dangers" in en.lower() or en.lower().endswith("oxen"))
        art_en = (a + " ") if a else ""
        art_he = "" if plural else _art(a, he)
        if a and a[0].isupper(): pass
        cap = not a and en[:1].isupper()
        he_first = (he[:1].upper() + he[1:]) if (cap and not a) else he
        en_in = en[:1].lower() + en[1:] if cap else en
        mid = html.escape(s[last:m.start()]); out.append(I(s[last:m.start()]) if False else mid)
        e1 = f"{html.escape(art_en)}{html.escape(en)} (<i>{html.escape(he)}</i>)"
        h1 = f"{html.escape(art_he)}<i>{html.escape(he_first)}</i> ({html.escape(en_in)})"   # tam and mu'ad are adjectives AND types of ox: "a harmless ox (tam)" <-> "a tam (harmless ox)"
        out.append(f'<span class="t-en">{e1}</span><span class="t-he">{h1}</span>'); last = m.end()
    out.append(html.escape(s[last:]))
    res = "".join(out)
    # italicise remaining key terms outside tags (pairs already italic)
    return _ital_outside(res)
def _ital_outside(h):
    parts = re.split(r"(<[^>]+>)", h); depth_i = 0; res = []
    for p_ in parts:
        if p_.startswith("<"):
            if p_ == "<i>": depth_i += 1
            elif p_ == "</i>": depth_i -= 1
            res.append(p_)
        elif depth_i == 0:
            res.append(re.sub(_KT, lambda m: "<i>" + m.group(0) + "</i>", p_))
        else: res.append(p_)
    return "".join(res)
def term_head(t):
    if LANG != "en": return html.escape(tr(t))   # key-terms list heading: "ransom (kofer)" <-> "kofer (ransom)"
    m = re.match(r"^(.*?) \(([^()]+)\)$", t or "")
    if not m: return I(t)
    en, he = m.group(1), m.group(2)
    return f'<i>{html.escape(he)}</i> ({html.escape(en)})'

FONT = "Public Sans, system-ui, sans-serif"
def _T(x, y, s, size=15, w=400, fill="#1A1F2E", anchor="start"): return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" font-weight="{w}" fill="{fill}">{html.escape(s)}</text>'
def T(x, y, s, *a, **k): return _T(x, y, tr(s), *a, **k)
def U(sym, x, y, w, h, color=None): return f'<use href="#{sym}" x="{x}" y="{y}" width="{w}" height="{h}"' + (f' style="color:{color}"' if color else "") + "/>"
def badge(kind, x, y, d): return f'<image href="img/badge-{kind}.png" x="{x}" y="{y}" width="{d}" height="{d}"/>'
def wrap(s, n):
    lines, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    return lines + [cur]
def multi(x, y, s, n, size=15, lh=19, **k): return "".join(_T(x, y + i * lh, t, size, **k) for i, t in enumerate(wrap(tr(s), n)))
def svg(vb, body, label): return f'<svg viewBox="0 0 {vb[0]} {vb[1]}" role="img" aria-label="{esc(label)}"><rect width="{vb[0]}" height="{vb[1]}" rx="14" fill="url(#sky)"/>{body}</svg>'
def matrix(title, cols, rows, vb_w=520, label_w=190, row_h=116, note=None, bd=62):
    """rows: (label, icon_svg_or_'', [(kind or None, caption)...]). Narrow viewBox so text renders large in the panel."""
    title = tr(title); cw = (vb_w - label_w - 14) / len(cols); h = 104 + row_h * len(rows) + (34 if note else 6)
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

def flame(x, y, k=1.0): return f'<g transform="translate({x},{y}) scale({k})"><path d="M20 2 C30 18 40 26 32 46 C29 54 11 54 8 44 C3 32 14 26 14 14 C18 18 18 8 20 2Z" fill="#E0662E"/><path d="M20 24 C25 32 28 36 24 46 C22 50 16 50 15 44 C13 38 19 32 20 24Z" fill="#F4B942"/></g>'
def pit_open(x, y, h, added=0, label=""):
    ground = f'<rect x="{x}" y="{y}" width="110" height="26" rx="4" fill="#C9A66B"/>'
    cut = f'<rect x="{x+25}" y="{y}" width="60" height="{h}" fill="#4a2f1c"/>'
    extra = f'<rect x="{x+25}" y="{y+h-added}" width="60" height="{added}" fill="#8b4f2a"/>' if added else ""
    return ground + cut + extra + f'<rect x="{x}" y="{y+26}" width="25" height="{h-26}" fill="#C9A66B"/><rect x="{x+85}" y="{y+26}" width="25" height="{h-26}" fill="#C9A66B"/>' + (T(x + 55, y + h + 20, label, 14, 600, "#333", "middle") if label else "")
def svg_bk11():
    cards = [("Ox", "alive; its way is to go out and do injury", lambda x, y: U("bull", x + 86, y + 20, 78, 50)),
             ("Crop-destroying beast", "alive; its way is to go out and do injury", lambda x, y: U("goat", x + 92, y + 18, 66, 56)),
             ("Fire", "not alive; its way is to go out and do injury", lambda x, y: flame(x + 103, y + 14, 1.1)),
             ("Pit", "its way is not to go out and do injury", lambda x, y: pit_open(x + 70, y + 26, 54))]
    b = T(260, 32, "The four primary causes of injury", 19, 700, "#1b3a8a", "middle")
    for i, (t, d, ic) in enumerate(cards):
        x = 8 + (i % 2) * 254; y = 48 + (i // 2) * 170
        b += f'<rect x="{x}" y="{y}" width="250" height="160" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/>' + ic(x, y) + T(x + 125, y + 112, t, 16, 700, "#1b3a8a", "middle") + multi(x + 125, y + 134, d, 30, 13, 16, anchor="middle")
    b += f'<rect x="8" y="392" width="504" height="92" rx="12" fill="#e9eefb" stroke="#1b3a8a" stroke-width="1.5"/>' + T(260, 416, "What they share", 15, 700, "#1b3a8a", "middle") + multi(260, 438, "It is their way to do injury; you are responsible to guard them; the one responsible pays from the best of his land.", 56, 14, 17, anchor="middle")
    return svg((520, 496), b, "The four primary causes of injury")
def svg_bk12():
    b = T(260, 32, "Partly making a pit: he pays as if he dug it all", 18, 700, "#1b3a8a", "middle")
    b += f'<rect x="8" y="48" width="250" height="262" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/><rect x="262" y="48" width="250" height="262" rx="12" fill="#ffffffaa" stroke="#d9cfbd"/>'
    b += pit_open(78, 96, 72, 0, "") + T(133, 196, "Dug by another:", 14, 600, "#333", "middle") + T(133, 214, "9 handbreadths", 14, 600, "#333", "middle") + T(133, 234, "an animal that falls survives", 12, 400, "#555", "middle")
    b += pit_open(332, 96, 80, 8, "") + T(387, 196, "He deepens it by one:", 14, 600, "#333", "middle") + T(387, 214, "10 handbreadths", 14, 600, "#333", "middle") + T(387, 234, "an animal that falls dies", 12, 400, "#555", "middle")
    b += badge("pay", 365, 246, 44) + T(387, 304, "he pays", 13, 600, "#333", "middle")
    b += multi(260, 338, "Whatever I am responsible to guard, I have made possible to do injury; if I partly made it possible, I pay as if I did all of it.", 52, 14, 17, anchor="middle", fill="#444")
    return svg((520, 396), b, "A pit deepened from nine to ten handbreadths")
def svg_bk22():
    rows = [("It ate fruit or vegetables", lambda y: U("bull", 18, y + 30, 58, 37), [("pay", "Full damages"), ("notpay", "Exempt; pays what it benefited")]),
            ("It ate clothing or utensils", lambda y: U("bull", 18, y + 30, 58, 37), [("pay-half", "Half damages"), ("notpay", "Exempt")])]
    return matrix("What the tooth eats, and where", ["In the damaged party's domain", "In the public domain"], rows, 520, 186, 122, "In the public domain it pays what it benefited from the middle of the marketplace or the front of a store, and the damage from the sides or inside a store.")
def svg_bk25():
    b = T(260, 32, "The ox that gores: which domain?", 19, 700, "#1b3a8a", "middle")
    for j, c in enumerate(("Public domain", "Injured party's domain")): b += f'<rect x="{182 + j * 168}" y="48" width="160" height="34" rx="8" fill="#1b3a8a"/>' + T(262 + j * 168, 71, c, 13, 700, "#fff", "middle")
    rows = [("Tooth and foot", [[("notpay", "Exempt")], [("pay", "Full damages")]]), ("Horn: it gores, pushes, bites, lies down, kicks", [[("pay-half", "Half damages")], [("pay-half", "Sages: half"), ("pay", "R. Tarfon: full")]])]
    for i, (lab, cells) in enumerate(rows):
        y = 92 + i * 132
        b += f'<rect x="8" y="{y}" width="504" height="122" rx="10" fill="#ffffffaa" stroke="#d9cfbd"/>' + multi(20, y + 40, lab, 18, 15, 19, w=600)
        for j, cell in enumerate(cells):
            cx = 262 + j * 168; n = len(cell)
            for k, (kind, cap) in enumerate(cell):
                bx = cx + (k - (n - 1) / 2) * 74
                b += badge(kind, bx - 28, y + 12, 56) + multi(bx, y + 86, cap, 11, 12, 14, anchor="middle")
    b += multi(260, 368, "The Sages: it is enough if the law derived is as strict as its source (dayo). The halakha follows the Sages.", 56, 13, 16, anchor="middle", fill="#444")
    return svg((520, 396), b, "The ox that gores, in the public domain and in the injured party's domain")
def svg_bk43():
    rows = [("An Israelite's ox gored an ox of the Temple", lambda y: U("bull", 18, y + 30, 58, 37), [("notpay", "Exempt")]),
            ("An ox of the Temple gored an Israelite's ox", lambda y: U("bull", 18, y + 30, 58, 37), [("notpay", "Exempt")]),
            ("An Israelite's ox gored a gentile's ox", lambda y: U("bull", 18, y + 30, 58, 37), [("notpay", "Exempt")]),
            ("A gentile's ox gored an Israelite's ox, a tam or an attested danger", lambda y: U("bull", 18, y + 30, 58, 37), [("pay", "Full damages")])]
    return matrix("Does the owner of the goring ox pay?", ["The owner"], rows, 520, 320, 110, "The first clause is learned from \"his neighbour's ox\" (Exodus 21:35).")
def svg_bk64():
    b = T(260, 32, "How far can the fire spread and he still pays?", 18, 700, "#1b3a8a", "middle")
    b += multi(260, 60, "Kindled in his own domain. A fence four cubits high, a public way or a river: exempt.", 56, 13, 16, anchor="middle", fill="#444")
    k = 5.6; bars = [("Rabbi Eliezer", 16, "16 cubits, like a public road", "#2c7a46"), ("Rabbi Akiva", 50, "50 cubits", "#1b3a8a")]
    for i, (n, v, lab, col) in enumerate(bars):
        y = 96 + i * 76
        b += T(12, y + 18, n, 15, 700, "#333") + f'<rect x="12" y="{y+28}" width="{v*k}" height="26" rx="6" fill="{col}"/>' + T(12 + v * k + 8, y + 47, lab, 13, 400, "#333")
    y = 248
    b += T(12, y + 18, "Rabbi Eleazar ben Azariah", 15, 700, "#333") + f'<rect x="12" y="{y+28}" width="230" height="26" rx="6" fill="none" stroke="#7a4aa0" stroke-width="2.5" stroke-dasharray="7 5"/>' + multi(252, y + 40, "as if in the middle of a kor's space", 28, 13, 15)
    y = 324
    b += T(12, y + 18, "Rabbi Shimon", 15, 700, "#333") + '<defs><linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#C75A2A"/><stop offset="1" stop-color="#C75A2A" stop-opacity="0"/></linearGradient></defs>' + f'<rect x="12" y="{y+28}" width="260" height="26" rx="6" fill="url(#fade)"/>' + multi(282, y + 40, "all by the nature of the fire", 26, 13, 15) + badge("pay", 462, y + 8, 44)
    b += multi(260, 404, "The halakha follows Rabbi Shimon: the larger the fire, the farther he is liable.", 56, 13, 16, anchor="middle", fill="#444")
    return svg((520, 424), b, "How far a fire kindled in one's own domain must spread")
DIAG_BK1 = {1: svg_bk11, 2: svg_bk12}
DIAG_BK2 = {2: svg_bk22, 5: svg_bk25}
DIAG_BK4 = {3: svg_bk43}
DIAG_BK6 = {4: svg_bk64}
import os
OV = json.load(open("data/overlays.json")) if os.path.exists("data/overlays.json") else {}
QP = json.load(open("data/quiz_principles.json")) if os.path.exists("data/quiz_principles.json") else {}
CHIPS = json.load(open("data/chip_overrides.json")) if os.path.exists("data/chip_overrides.json") else {}
QQ = json.load(open("data/quiz_questions.json")) if os.path.exists("data/quiz_questions.json") else {}
OV_OLD = json.load(open("data/overlays_older.json")) if os.path.exists("data/overlays_older.json") else {}
def stage(spec, pic, base="", pid=None):
    W, H = spec["w"], spec["h"]; pct = lambda v, t: f"{100 * v / t:.3f}%"; hot = ""; ov = ""
    for i, h in enumerate(spec["hotspots"]):
        l, t, r, b = h["rect"]
        q = str(i + 1) if len(spec["hotspots"]) > 1 else "?"; ans = h.get("answer", "").replace("tag-", "")
        hot += f'<button class="hot{' tg' if (h['badges'] and h['badges'][0]['anchor'] == 'bottom') else ''}" data-h="{i}" data-ans="{html.escape(ans)}" data-q="{esc(q)}" data-pr="{esc(TT((QP.get(pid) or [""] * 9)[i] if i < len(QP.get(pid) or []) else ""))}" aria-pressed="false" aria-label="{esc(h["label"])}" style="left:{pct(l,W)};top:{pct(t,H)};width:{pct(r-l,W)};height:{pct(b-t,H)}"></button>'
        for bd in h["badges"]:
            tr = "translate(-50%,-50%)" if bd["anchor"] == "center" else "translate(-50%,-100%)"
            ov += f'<img class="ov" data-h="{i}" src="img/{bd["src"]}" alt="" style="left:{pct(bd["x"],W)};top:{pct(bd["y"],H)};width:{pct(bd["w"],W)};--t:{tr}">'
    def chip_pos(h):
        ov_ = (CHIPS.get(pid) or {}).get(str(spec["hotspots"].index(h)))
        if ov_: return f'left:{pct(ov_[0], W)};top:{pct(ov_[1], H)};margin:-15px 0 0 -15px'
        bd = h["badges"][0] if h["badges"] else None
        if bd and bd["anchor"] == "bottom" and os.path.exists("site/img/" + bd["src"]):   # a tag: put the chip where the badge will land, at its upper-right, never inside the person's rectangle
            from PIL import Image as _I
            im = _I.open("site/img/" + bd["src"]); sc = bd["w"] / im.width; th = im.height * sc; dh = (im.height - 34) * sc
            return f'left:{pct(bd["x"] + 0.40 * bd["w"], W)};top:{pct(bd["y"] - th + 0.12 * dh, H)};margin:-15px 0 0 -15px'
        return f'left:{pct(h["rect"][0], W)};top:{pct(h["rect"][1], H)}'
    chips = "".join(f'<span class="qchip{" tg" if (h["badges"] and h["badges"][0]["anchor"] == "bottom") else ""}" data-h="{i}" style="{chip_pos(h)}">{("%d" % (i + 1)) if len(spec["hotspots"]) > 1 else "?"}</span>' for i, h in enumerate(spec["hotspots"]))
    return f'<div class="stage"><img src="{spec["clean"]}" alt="{esc(pic[1])}" loading="lazy">{hot}{ov}{chips}</div>'
TRAY = []
def quiz_ui(spec, pid=None):
    if not TRAY: return ""
    tb = "".join(f'<button class="tb" type="button" data-k="{k}" aria-label="{esc(name)}" title="{esc(name)}"><img src="img/badge-{k}.png" alt="" draggable="false"></button>' for k, name in TRAY)
    hs = spec["hotspots"]; many = len(hs) > 1
    qs = QQ.get(pid) or [h["label"] for h in hs]
    ask = " ".join(f'<span class="qa">{("<b>%d</b> " % (i + 1)) if many else ""}{TT(qs[i] if i < len(qs) else h["label"])}</span>' for i, h in enumerate(hs))
    return f'<div class="qask qonly">{ask}</div><div class="tray qonly" role="group" aria-label="Badges">{tb}</div><div class="qmsg qonly" role="status" aria-live="polite"></div>'
QBTN = ' <span class="qonly qbtns"><button class="qshow" type="button">Show answers</button><button class="qreset" type="button">Try again</button></span>'
QHINT = '<span class="qonly qhint">Drag a badge from the tray onto the picture, or tap a badge and then tap where it belongs.</span>'
def variant(aud, mode, inner, cap, note=""):
    n = f' <span class="note">{esc(note)}</span>' if note else ""
    return f'<figure class="pic v" data-aud="{aud}" data-mode="{mode}">{inner}<figcaption><span class="ctext">{TT(cap)}{n}</span></figcaption></figure>'
def fig(pic):
    """Four variants (younger/older x static/interactive); CSS shows the one chosen in the toolbar.
    Younger static = the original composed picture with badges baked in. Older pictures live in site/img/older/<pid>.jpg (static, badges baked)
    and site/img/older/clean/<pid>.jpg + data/overlays_older.json (interactive); until they exist the older choice shows the younger picture with a note."""
    pid = pic[0].rsplit(".", 1)[0]; spec = OV.get(pid); cap = pic[1]
    btn = ' <span class="hint">%s</span> <button class="all" type="button">Show all</button>'
    clay = os.path.exists(f"site/img/{pic[0]}") or os.path.exists(f"site/img/clean/{pid}.jpg")
    if not clay and not spec and not OV_OLD.get(pid): clay = True   # nothing else to show either
    if not clay: y_i = y_s = ""   # filled in below from the older picture
    elif not spec: y_i = variant("y", "i", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap)
    else: y_i = variant("y", "i", stage(spec, pic, '', pid) + quiz_ui(spec, pid), cap).replace("</figcaption>", (btn % esc(spec["hint"])) + QBTN + QHINT + "</figcaption>")
    if clay: y_s = variant("y", "s", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap)
    old_s = os.path.exists(f"site/img/older/{pid}.jpg"); spec_o = OV_OLD.get(pid)
    miss = "Older-audience picture not made yet; showing the younger one."
    if old_s: o_s = variant("o", "s", f'<img src="img/older/{pid}.jpg" alt="{esc(cap)}" loading="lazy">', cap)
    else: o_s = variant("o", "s", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap, miss)
    if spec_o: o_i = variant("o", "i", stage(spec_o, pic, '', pid) + quiz_ui(spec_o, pid), cap).replace("</figcaption>", (btn % esc(spec_o["hint"])) + QBTN + QHINT + "</figcaption>")
    elif spec: o_i = variant("o", "i", stage(spec, pic, '', pid) + quiz_ui(spec, pid), cap, miss).replace("</figcaption>", (btn % esc(spec["hint"])) + QBTN + QHINT + "</figcaption>")
    else: o_i = variant("o", "i", f'<img src="img/{pic[0]}" alt="{esc(cap)}" loading="lazy">', cap, miss)
    if not clay:   # no clay picture for this chapter yet: the younger choice shows the graphic-novel picture with a note
        ynote = "Younger-audience picture not made yet; showing the older-audience one."
        y_i = o_i.replace('data-aud="o"', 'data-aud="y"').replace("</figcaption>", f' <span class="note">{ynote}</span></figcaption>', 1) if spec_o else ""
        y_s = o_s.replace('data-aud="o"', 'data-aud="y"').replace("</figcaption>", f' <span class="note">{ynote}</span></figcaption>', 1)
    return y_i + y_s + o_i + o_s
css = """:root{--bg:#f7f4ec;--fg:#222;--card:#fff;--blue:#1b3a8a;--tint:#f1f3fb;--amber:#a85d00;--add:#5d5d5d}@media(prefers-color-scheme:dark){:root{--bg:#14161c;--fg:#e8e6df;--card:#1d2028;--tint:#232838;--amber:#f2b04a;--add:#b9b6ad}}
html{scroll-behavior:smooth}body{font:17px/1.55 'Public Sans',system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}header{position:relative;background:var(--blue);color:#fff;padding:14px 24px 18px}.brand{display:inline-flex;align-items:center;gap:12px;margin:0 0 12px;color:#fff;text-decoration:none}.brand img{height:44px;width:auto;display:block}.brand span{font-family:Newsreader,Georgia,serif;font-size:22px;font-weight:600;letter-spacing:.01em}header h1{margin:0;font-family:Newsreader,Georgia,serif}
.pills{position:sticky;top:0;z-index:5;background:var(--bg);padding:8px 16px;border-bottom:1px solid #8884;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pills span{font-weight:600;margin-right:6px}
.pills a{display:inline-grid;place-items:center;min-width:34px;height:34px;border-radius:17px;padding:0 6px;background:var(--card);color:var(--blue);text-decoration:none;font-weight:700;border:1.5px solid var(--blue)}.pills a.on,.pills a:hover{background:var(--blue);color:#fff}
main{max-width:1240px;margin:auto;padding:12px 16px}section{scroll-margin-top:70px;margin:26px 0}section h2{font-family:Newsreader,Georgia,serif;margin:0 0 2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}@media(max-width:900px){.grid{grid-template-columns:1fr}.grid .text{order:-1}}
.grid>*{min-width:0}td,th{overflow-wrap:anywhere}.panel{background:var(--card);border-radius:14px;padding:16px 20px;box-shadow:0 1px 4px #0002}.aids{background:var(--tint)}
.he{font:24px/1.9 'Times New Roman',serif;margin-bottom:10px}.sum{font-style:italic;opacity:.8;margin:0 0 10px}
h4{margin:12px 0 2px}ul{margin:0 0 4px;padding-left:22px}li{margin:3px 0}table{border-collapse:collapse;width:100%;font-size:17px}td,th{border:1px solid #bbb8;padding:7px 10px;text-align:left}th{background:#1b3a8a22}.chart{margin:14px 0}.chart svg{width:100%;height:auto;display:block}
.stage{position:relative}.hot{position:absolute;background:transparent;border:2px dashed transparent;border-radius:10px;cursor:pointer;padding:0}.hot:hover,.hot:focus,.hot:focus-visible,.hot:active{border-color:transparent;background:transparent;outline:none;-webkit-tap-highlight-color:transparent}
.hot::after{content:"tap";position:absolute;left:50%;bottom:6px;transform:translateX(-50%);background:#1b3a8acc;color:#fff;font:600 12px 'Public Sans',sans-serif;padding:2px 9px;border-radius:10px;opacity:.9;animation:tp 2.2s ease-in-out infinite}.hot[aria-pressed=true]::after{display:none}
@keyframes tp{50%{opacity:.35}}.ov{position:absolute;height:auto;opacity:0;transform:var(--t) scale(.5);transition:opacity .25s,transform .25s;pointer-events:none;filter:drop-shadow(0 3px 4px #0006)}.ov.on{opacity:1;transform:var(--t) scale(1)}
.hint{opacity:.85;font-style:italic}.en p,.he p{margin:0 0 .85em}.he p{line-height:1.45;margin-bottom:.6em}.en p:last-child,.he p:last-child{margin-bottom:0}.en{color:var(--add)}.en b{color:var(--amber);font-weight:600}.en.en-s{color:var(--fg)}.kt{border-bottom:1px dotted currentColor;cursor:help}.kti{color:inherit;text-decoration:underline dotted;cursor:help}.kt1[data-k],.kt{cursor:help}.ktn{border-bottom:0}.kt1:not([data-k]) i{font-style:italic}.about{position:fixed;inset:0;background:#0007;z-index:80;display:flex;align-items:center;justify-content:center;padding:16px}.about[hidden]{display:none}.abox{background:var(--card);color:var(--fg);max-width:560px;max-height:88vh;overflow:auto;border-radius:12px;padding:16px 20px;box-shadow:0 12px 40px #0006;font-size:15px}.abox h3{margin:0 0 8px}.abox .gx{float:right;border:0;background:none;color:inherit;font-size:22px;cursor:pointer}footer .aboutlink{white-space:nowrap}.gpop{position:absolute;z-index:60;max-width:320px;background:var(--card);color:var(--fg);border:1.5px solid var(--blue);border-radius:10px;box-shadow:0 8px 24px #0005;padding:10px 12px;font:14px/1.45 'Public Sans',system-ui,sans-serif}.tlist details{border-bottom:1px solid #8885;padding:6px 0}.tlist details:last-child{border-bottom:0}.tlist summary{cursor:pointer;font-size:17px}.tlist summary .he{font-size:18px;margin:0 4px;line-height:1.4}.tlist summary b{font-weight:600}.tbody{padding:2px 0 4px 18px;font-size:16px}.tlist .refs{font-size:12px}.mu{border-bottom:1px dotted currentColor;cursor:pointer}.mpop{position:fixed;max-height:calc(100vh - 16px);overflow:auto;z-index:61;width:min(540px,calc(100vw - 16px));background:var(--card);color:var(--fg);border:1.5px solid var(--blue);border-radius:12px;box-shadow:0 8px 24px #0005;padding:12px 14px;font:14px/1.45 'Public Sans',system-ui,sans-serif}.mpop .gx{float:right;border:0;background:none;color:inherit;font-size:18px;cursor:pointer}.mpop .mbuys{font-size:13.5px;margin:4px 0 0}.mpop .mbuys ul{margin:2px 0 0;padding-left:18px}.mpop h4{margin:0 0 2px;font-size:16px}.mpop .mrel{margin:6px 0;font-size:13.5px}.mpop .msrc{font-size:11.5px;opacity:.75;margin-top:6px}.mpop g[data-k]:hover path{filter:brightness(1.08)}.mpop g[data-k]:focus{outline:none}.mpop g[data-k]:focus-visible path{stroke:#2a4;stroke-width:3}.mpop svg text{font-family:'Public Sans',sans-serif}.tord{font-size:13px;margin:0 0 10px;display:flex;flex-wrap:wrap;gap:6px 6px;align-items:center;line-height:1.6}.tord [data-all]{margin-left:auto}.tord button{font:inherit;border:1px solid var(--blue);background:var(--card);color:var(--blue);border-radius:10px;padding:0 9px;margin-left:5px;cursor:pointer}.tord button.on{background:var(--blue);color:#fff}.gpop p{margin:6px 0 0}.gpop b{font-weight:700}.gpop .gh{font-size:15px}.gpop .loc{margin-top:6px;font-size:13px;opacity:.85}.gpop .gx{float:right;border:0;background:none;color:inherit;font-size:16px;cursor:pointer;margin:-4px -4px 0 6px}.loc{margin-top:4px;font-size:13px;opacity:.85}.en-s i{font-style:italic}html[data-eng=s] .en-d,html[data-eng=s] .ecd,html[data-eng=d] .en-s,html[data-eng=d] .ecs{display:none}.encredit{margin:6px 0 0;font-size:12.5px;opacity:.8}.all{margin-left:8px;font:600 12px 'Public Sans',sans-serif;border:1.5px solid var(--blue);color:var(--blue);background:var(--card);border-radius:12px;padding:1px 10px;cursor:pointer}
.pic{margin:16px 0}.pic img{width:100%;height:auto;border-radius:12px;display:block}figcaption{font-size:14px;opacity:.7;margin-top:4px}details{margin-top:10px}summary{cursor:pointer;font-weight:600}
.legend{background:var(--card);border-radius:12px;padding:12px 20px;margin:14px 0;display:flex;gap:0;align-items:center;flex-wrap:wrap}.legend .grp{display:flex;gap:18px;align-items:center;padding:0 22px;border-left:1px solid #8886}.legend .grp:first-child{padding-left:0;border-left:0}.legend .grp>span{display:flex;align-items:center;gap:8px}.legend .t{display:block}.b{flex:none}.b.wide{width:auto;height:40px}\n@media(max-width:1000px){.legend{flex-direction:column;align-items:stretch}.legend .grp{flex-wrap:wrap;padding:12px 0;border-left:0;border-top:1px solid #8886;gap:10px 22px}.legend .grp:first-child{border-top:0;padding-top:0}.legend .grp:last-child{padding-bottom:0}}.b{width:44px;height:44px;vertical-align:middle;margin-right:6px}
.v{display:none}html[data-aud=y][data-mode=i] .v[data-aud=y][data-mode=i],html[data-aud=y][data-mode=s] .v[data-aud=y][data-mode=s],html[data-aud=o][data-mode=i] .v[data-aud=o][data-mode=i],html[data-aud=o][data-mode=s] .v[data-aud=o][data-mode=s],html[data-aud=y][data-mode=q] .v[data-aud=y][data-mode=i],html[data-aud=o][data-mode=q] .v[data-aud=o][data-mode=i]{display:block}html[data-mode=s] .ionly,html[data-mode=q] .ionly,html:not([data-mode=q]) .qlegend{display:none}.note{font-style:italic;color:#8a5a00}
.qonly,.qs{display:none}html[data-mode=q] .qonly{display:block}html[data-mode=q] .qs{display:inline}html[data-mode=q] .qbtns,html[data-mode=q] .qhint{display:inline}html[data-mode=q] .all,html[data-mode=q] .hint,html[data-mode=q] figure:has(.tray) .ctext{display:none}
.tray{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--tint);border-radius:12px;padding:8px 12px;margin-top:8px}html:not([data-mode=q]) .tray{display:none}.tl{font-weight:600;font-size:13px;opacity:.75}.tb{border:2px solid transparent;background:var(--card);border-radius:12px;padding:3px 6px;cursor:grab;touch-action:none;user-select:none}.tb img{height:46px;width:auto;display:block;border-radius:0;pointer-events:none}.tb.sel{border-color:var(--blue);box-shadow:0 0 0 3px #1b3a8a33}
.ghost{position:fixed;height:52px;width:auto;transform:translate(-50%,-50%);pointer-events:none;z-index:60;filter:drop-shadow(0 6px 8px #0006);opacity:.95}
html[data-mode=q] .hot{border-color:transparent;background:none;pointer-events:none}html[data-mode=q] .hot::after{display:none!important}.qchip{display:none;position:absolute;width:30px;height:30px;margin:8px 0 0 8px;border-radius:50%;background:#1b3a8aee;color:#fff;font:700 15px 'Public Sans',sans-serif;place-items:center;pointer-events:none;z-index:4;box-shadow:0 1px 4px #0006}html[data-mode=q] .qchip{display:grid}.qchip.over{background:#c98a00;transform:scale(1.25)}.qchip.ok{background:#1f7a3d}.qchip.ok::before{content:'\\2713'}.qchip.ok{font-size:0}.qchip.ok::before{font-size:17px}.qchip.gave{background:#8a6a1a}.qchip.wrong{background:#b03a2e;animation:shk .45s}html[data-mode=q] .hot::after{content:attr(data-q);left:5px;top:5px;bottom:auto;transform:none;min-width:22px;text-align:center;border-radius:12px;padding:1px 7px;font-size:13px;animation:none;opacity:.95}.ov{z-index:3}.qask{display:none;flex-direction:column;gap:6px;font-size:15px;margin-top:10px}html[data-mode=q] .qask{display:flex}.qa b{background:#1b3a8acc;color:#fff;border-radius:10px;padding:0 7px;margin-right:2px}html[data-mode=q] .hot.ok::after{display:none}html[data-mode=q] .hot.ok,html[data-mode=q] .hot.over,html[data-mode=q] .hot.gave{border-color:transparent;background:none}html[data-mode=q] .hot.wrong{animation:none;border-color:transparent!important;background:none!important}html[data-mode=q] .hot.right{box-shadow:none}
.hot.wrong{animation:shk .45s;border-color:#c0392b!important;background:#c0392b33!important}.hot.right{box-shadow:0 0 0 4px #2a8a4a88}@keyframes shk{20%,60%{transform:translateX(-7px)}40%,80%{transform:translateX(7px)}}
html[data-mode=q] .hot.tg::after{display:none!important}.qmsg{font-size:15px;font-weight:600;min-height:1.4em;margin-top:6px}.qmsg.good{color:#1f7a3d}.qmsg.bad{color:#b03a2e}.qbtns button{margin-left:8px;font:600 12px 'Public Sans',sans-serif;border:1.5px solid var(--blue);color:var(--blue);background:var(--card);border-radius:12px;padding:1px 10px;cursor:pointer}.qhint{font-style:italic;opacity:.85}.qs{font-weight:600}.qbar{padding:0 24px}.qbar:has(.qs:empty){display:none}
.opts{color:var(--fg);font-size:14px;display:none;position:absolute;top:50px;right:12px;z-index:70;flex-direction:column;align-items:flex-start;border:1.5px solid var(--blue);border-radius:12px;background:var(--card);box-shadow:0 8px 24px #0005;padding:12px 16px;gap:10px}.opts.open{display:flex}.refbtn{position:absolute;top:10px;right:60px;width:38px;height:38px;border-radius:19px;border:0;background:#fff;box-shadow:0 1px 4px #0005;padding:0;display:grid;place-items:center;cursor:pointer}.mpop.inline{position:static;transform:none;max-height:none;width:100%;max-width:880px;margin:16px auto;box-shadow:none}.mpop.inline .gx{display:none}.mtabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 28px 8px 0}.mtabs button,.mvf button{font:inherit;font-size:13px;border:1px solid var(--blue);background:var(--card);color:var(--blue);border-radius:12px;padding:1px 11px;cursor:pointer}.mtabs button.on,.mvf button.on{background:var(--blue);color:#fff}.mvf{font-size:13px;margin:2px 0 4px;display:flex;gap:6px;align-items:center}
.mvf.eo{flex-direction:column;align-items:flex-start;gap:5px;width:max-content;max-width:100%;margin-left:auto}.mvf.eo span{opacity:.75}.gear{position:absolute;top:10px;right:14px;width:38px;height:38px;border-radius:19px;border:0;background:#fff;color:var(--blue);box-shadow:0 1px 4px #0005;padding:0;display:grid;place-items:center;cursor:pointer;line-height:1}.opts_x{display:flex;gap:22px;flex-wrap:wrap;align-items:center;padding:8px 16px;background:var(--tint);border-bottom:1px solid #8884;font-size:14px}.opts b{margin-right:6px}.seg{display:inline-flex;border:1.5px solid var(--blue);border-radius:16px;overflow:hidden}.seg button{font:600 13px 'Public Sans',sans-serif;border:0;background:var(--card);color:var(--blue);padding:4px 14px;cursor:pointer}.seg button[aria-pressed=true]{background:var(--blue);color:#fff}
.grid3{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:18px;align-items:start}@media(max-width:1000px){.grid3{grid-template-columns:1fr}}.grid3>*{min-width:0}.grid3 h3{margin:0 0 6px;font-family:Newsreader,Georgia,serif}.pr li{margin:0 0 10px}.refs{white-space:nowrap}.mref{font-size:12px;font-weight:600;background:var(--card);border:1px solid var(--blue);border-radius:9px;padding:0 6px;margin-left:4px;text-decoration:none}.pnote{font-size:14px;opacity:.8;font-style:italic}dl{margin:0}dt{margin-top:10px}dd{margin:2px 0 0}dt .he{font-size:18px;margin:0 4px}.debate{margin:0 0 14px}.debate h4{margin:0 0 4px}.sides{display:grid;gap:8px}.sides p{margin:2px 0 0}.sides>div{background:var(--card);border-radius:10px;padding:8px 12px}
.pills .sep{width:1px;align-self:stretch;background:#8886;margin:0 6px}.pills .lbl{font-weight:700;color:var(--blue)}@media(max-width:1000px){.pills{flex-wrap:nowrap;overflow-x:auto}.pills>*{flex:none}}.pgroup{border:1.5px solid var(--blue);border-radius:14px;padding:6px 14px 2px;margin:18px 0;background:var(--tint)}.pgroup .gh{margin:6px 0 0;font-family:Newsreader,Georgia,serif;font-size:21px;color:var(--blue)}.pgroup .gh span{font-size:15px;font-weight:400;opacity:.8}.pgroup .pic{margin:10px 0}section+section{border-top:1px solid #8888;padding-top:24px}#summary{border-top:2px solid var(--blue)}i{font-style:italic}.biur{margin:12px 0;background:var(--tint);border-radius:10px;padding:6px 14px}.biur summary{cursor:pointer;font-weight:700}.biur p{font-size:18px;line-height:1.85;margin:8px 0;opacity:.92}.biur p b{opacity:1}.biur-credit{font-size:12px;opacity:.7;margin:6px 0 2px}html[data-terms=en] .t-he,html[data-terms=he] .t-en{display:none}.chnav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 24px;background:var(--card);border-bottom:1px solid #8884}.chnav span{font-weight:600;margin-right:6px}.chnav a{display:inline-grid;place-items:center;min-width:38px;height:38px;border-radius:19px;color:var(--blue);text-decoration:none;font-weight:700;border:1.5px solid var(--blue);padding:0 8px}.chnav a.on,.chnav a:hover{background:var(--blue);color:#fff}.banner{background:#fff3cd;color:#5a4500;padding:10px 24px;font-size:14px}footer{font-size:12px;opacity:.7;padding:14px 24px;max-width:1240px;margin:auto}a{color:var(--blue)}"""
fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Newsreader:wght@500;700&family=Public+Sans:wght@400;600;700&display=swap" rel="stylesheet">'
HEAD_JS = '<script>(function(){var d=document.documentElement,a="y",m="i",t="en",g="s";try{a=localStorage.getItem("mAud")||a;m=localStorage.getItem("mMode")||m;t=localStorage.getItem("mTerms")||t;g=localStorage.getItem("mEng")||g}catch(e){}d.dataset.units=(function(){try{return localStorage.getItem("mUnits")||"us"}catch(e){return"us"}})();d.dataset.aud=a;d.dataset.mode=m;d.dataset.terms=t;d.dataset.eng=g})()</script>'
head_html = lambda t: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{t}</title>{fonts}<style>{css}</style>{HEAD_JS}</head><body>{SPRITE}<svg style="position:absolute;width:0;height:0"><defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9D6EA"/><stop offset="1" stop-color="#F3EBDD"/></linearGradient></defs></svg>'
def foot_html():
    he = LANG == "he"
    short = ("Hebrew: Mishnah, ed. Romm, Vilna 1913 (public domain). Explanation: Steinsaltz, William Davidson Edition, via Sefaria, CC BY-NC 4.0." if he else "English: smoothed by Claude from the William Davidson Edition (Koren), via Sefaria, CC BY-NC 4.0.")
    paras = ["Hebrew: Mishnah, ed. Romm, Vilna 1913 (public domain).",
             "English: a smoothed rendering written by Claude from the Hebrew and the William Davidson Edition (Koren, based on the Steinsaltz Talmud), via Sefaria, licensed CC BY-NC 4.0. A draft under review.",
             "Hebrew explanation (biur): Rabbi Adin Even-Israel Steinsaltz, William Davidson Edition, via Sefaria, CC BY-NC 4.0.",
             "Outlines, charts, glossary and diagrams were drafted by Claude (Anthropic) from the mishnah and Kehati, in our own words, and are under review.",
             "The illustrations are AI-generated; the round symbols are interim. Prototype for discussion, not for distribution."]
    body = "".join(f"<p>{esc(x)}</p>" for x in paras)
    return (f'<footer>{esc(short)} <a href="#" class="aboutlink">{esc("Sources and credits")}</a></footer>'
            f'<div class="about" id="about" hidden><div class="abox"><button class="gx" type="button" aria-label="Close">\u00d7</button><h3>{esc("Sources and credits")}</h3>{body}</div></div>'
            "<script>(function(){var a=document.getElementById('about');if(!a)return;document.addEventListener('click',function(e){var l=e.target.closest&&e.target.closest('.aboutlink');if(l){e.preventDefault();a.hidden=!a.hidden;return}if(!a.hidden&&(e.target.closest('.gx')||!e.target.closest('.abox')))a.hidden=true});document.addEventListener('keydown',function(e){if(e.key==='Escape')a.hidden=true})})()</script>")

JS = r"""<script>
(function(){
var root=document.documentElement, sel=null, LL=__L__;
function $$(q,r){return [].slice.call((r||document).querySelectorAll(q))}
function msg(fig,t,c){var m=fig.querySelector('.qmsg');if(m){m.innerHTML=t;m.className='qmsg qonly '+(c||'')}}
function score(){var ok=0,n=0,done=0;$$('.v[data-mode=i]').filter(function(f){return f.offsetParent!==null&&f.querySelector('.tray')}).forEach(function(f){$$('.hot',f).forEach(function(h){n++;if(h._done)done++;if(h._first)ok++})});var e=document.getElementById('qscore');if(e)e.textContent=LL.score(ok,n,done)}
function resetQuiz(){sel=null;$$('.ghost').forEach(function(g){g.remove()});$$('.stage').forEach(function(st){var hs=$$('.hot',st);hs.forEach(function(h,i){st._set(i,false);h.classList.remove('ok','wrong','right','over','gave');h._t=0;h._first=false;h._done=false});$$('.qchip',st).forEach(function(c){c.classList.remove('ok','wrong','over','gave')});var f=st.parentElement;$$('.tb',f).forEach(function(b){b.classList.remove('sel')});msg(f,'')});score()}
function select(fig,b){var same=sel&&sel.fig===fig&&sel.kind===b.dataset.k;$$('.tb.sel').forEach(function(x){x.classList.remove('sel')});if(same){sel=null;return}sel={fig:fig,kind:b.dataset.k};b.classList.add('sel')}
function finished(st){var hs=$$('.hot',st);if(hs.every(function(h){return h._done})){var ok=hs.filter(function(h){return h._first}).length;if(hs.length>1){var q=st.parentElement.querySelector('.qmsg');if(q)q.textContent+=' '+LL.allPlaced(ok,hs.length)}}}
function nearest(st,x,y){var best=-1,bd=1e9,ba=1e9,R=st.getBoundingClientRect();if(x<R.left-24||x>R.right+24||y<R.top-24||y>R.bottom+24)return null;st._hs.forEach(function(h,i){var r=h.getBoundingClientRect(),dx=Math.max(r.left-x,0,x-r.right),dy=Math.max(r.top-y,0,y-r.bottom),d=Math.hypot(dx,dy),a=r.width*r.height;if(d<bd-0.5||(Math.abs(d-bd)<=0.5&&a<ba)){best=i;bd=d;ba=a}});if(st._hs.length>1&&bd>140)return null;return best<0?null:st._hs[best]}
function mark0(st,h){var c=chip(st,h);if(c)c.classList.remove('over')}
function chip(st,h){return st.querySelector('.qchip[data-h="'+st._hs.indexOf(h)+'"]')}
function mark(st,h,cls,ms){var c=chip(st,h);if(!c)return;c.classList.add(cls);if(ms)setTimeout(function(){c.classList.remove(cls)},ms)}
function place(st,h,k){if(h._done)return;var fig=st.parentElement,i=st._hs.indexOf(h);if(k===h.dataset.ans){h._first=!(h._t>0);h._done=true;st._set(i,true);h.classList.add('ok','right');mark(st,h,'ok');setTimeout(function(){h.classList.remove('right')},900);msg(fig,(h._first?LL.right:LL.rightLater)+(h.dataset.pr?' '+LL.principle+' '+h.dataset.pr:''),'good');finished(st)}else{h._t=(h._t||0)+1;h.classList.add('wrong');mark(st,h,'wrong',500);setTimeout(function(){h.classList.remove('wrong')},500);msg(fig,LL.wrong,'bad')}score()}
$$('.seg').forEach(function(g){var k=g.dataset.key,K={aud:'mAud',mode:'mMode',terms:'mTerms',eng:'mEng',units:'mUnits'}[k];function sync(){$$('button',g).forEach(function(b){b.setAttribute('aria-pressed',b.dataset.v===root.dataset[k])})}sync();$$('button',g).forEach(function(b){b.addEventListener('click',function(){root.dataset[k]=b.dataset.v;try{localStorage.setItem(K,b.dataset.v)}catch(e){}sync();if(k==='mode')resetQuiz();else if(k==='aud')score()})})});
$$('.stage').forEach(function(st){var hs=$$('.hot',st),fig=st.parentElement;function set(i,on){hs[i].setAttribute('aria-pressed',on);$$('.ov[data-h="'+i+'"]',st).forEach(function(o){o.classList.toggle('on',on)})}st._set=set;st._hs=hs;
hs.forEach(function(h,i){h.addEventListener('click',function(){if(root.dataset.mode==='q'){if(!sel||sel.fig!==fig){msg(fig,LL.pick,'');return}place(st,h,sel.kind)}else set(i,h.getAttribute('aria-pressed')!=='true')})});
st.addEventListener('click',function(e){if(root.dataset.mode!=='q'||e.target.closest&&e.target.closest('.hot')&&e.detail===0)return;if(!sel||sel.fig!==fig){msg(fig,LL.pick,'');return}var h=nearest(st,e.clientX,e.clientY);if(!h){msg(fig,LL.tapPart,'');return}place(st,h,sel.kind)});
var btn=fig.querySelector('.all');if(btn)btn.addEventListener('click',function(){var on=btn.dataset.on!=='1';hs.forEach(function(_,i){set(i,on)});btn.dataset.on=on?'1':'';btn.textContent=on?LL.hideAll:LL.showAll});
var show=fig.querySelector('.qshow'),rs=fig.querySelector('.qreset');
if(show)show.addEventListener('click',function(){hs.forEach(function(h,i){if(!h._done){h._done=true;h._first=false;set(i,true);h.classList.add('ok','gave');mark(st,h,'ok');mark(st,h,'gave')}});msg(fig,LL.shown,'');score()});
if(rs)rs.addEventListener('click',function(){sel=null;hs.forEach(function(h,i){set(i,false);h.classList.remove('ok','wrong','right','over','gave');h._t=0;h._first=false;h._done=false});$$('.qchip',st).forEach(function(c){c.classList.remove('ok','wrong','over','gave')});$$('.tb',fig).forEach(function(b){b.classList.remove('sel')});msg(fig,'');score()});
$$('.tb',fig).forEach(function(b){
b.addEventListener('click',function(e){if(e.detail===0&&root.dataset.mode==='q')select(fig,b)});
b.addEventListener('pointerdown',function(e){if(root.dataset.mode!=='q')return;e.preventDefault();$$('.ghost').forEach(function(g){g.remove()});var sx=e.clientX,sy=e.clientY,ghost=null,over=null,fin=false;try{b.setPointerCapture(e.pointerId)}catch(x){}
function tgt(x,y){return nearest(st,x,y)}
function mv(ev){if(fin)return;if(ev.pointerType==='mouse'&&ev.buttons===0){up({type:'pointercancel'});return}if(!ghost&&Math.hypot(ev.clientX-sx,ev.clientY-sy)>6){ghost=b.querySelector('img').cloneNode();ghost.className='ghost';document.body.appendChild(ghost)}if(ghost){ghost.style.left=ev.clientX+'px';ghost.style.top=ev.clientY+'px';var t=tgt(ev.clientX,ev.clientY);if(over&&over!==t)mark0(st,over);if(t)chip(st,t)&&chip(st,t).classList.add('over');over=t}}
var EV=['pointermove','pointerup','pointercancel','lostpointercapture'];
function stop(){up({type:'pointercancel'})}
function key(k){if(k.key==='Escape')stop()}
function up(ev){if(fin)return;fin=true;EV.forEach(function(n){var f=n==='pointermove'?mv:up;b.removeEventListener(n,f);document.removeEventListener(n,f,true)});window.removeEventListener('blur',stop);document.removeEventListener('keydown',key,true);document.removeEventListener('contextmenu',stop,true);document.removeEventListener('visibilitychange',stop);if(over)mark0(st,over);if(ghost){ghost.remove();ghost=null;var t=ev.type==='pointerup'?tgt(ev.clientX,ev.clientY):null;if(t){sel={fig:fig,kind:b.dataset.k};place(st,t,b.dataset.k)}}else if(ev.type==='pointerup')select(fig,b)}
EV.forEach(function(n){var f=n==='pointermove'?mv:up;b.addEventListener(n,f);document.addEventListener(n,f,true)});window.addEventListener('blur',stop);document.addEventListener('keydown',key,true);document.addEventListener('contextmenu',stop,true);document.addEventListener('visibilitychange',stop)})})});
var L=$$('.pills a[href^="#"]');var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){L.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id)})}})},{rootMargin:'-30% 0px -60% 0px'});$$('section').forEach(function(s){io.observe(s)});
(function(){var b=document.querySelectorAll('.tord button[data-o]'),ab=document.querySelector('.tord [data-all]');if(!b.length)return;var dl=document.querySelector('.tlist'),it=[].slice.call(dl.children);it.forEach(function(e,i){e.dataset.i=i});var az=document.querySelector('.tord [data-o=en]');ab.onclick=function(){var open=ab.textContent==='Open all';it.forEach(function(e){e.open=open});ab.textContent=open?'Collapse all':'Open all'};b.forEach(function(x){x.onclick=function(){var o=x.dataset.o;b.forEach(function(y){y.classList.toggle('on',y===x)});it.slice().sort(function(a,c){return o==='i'?a.dataset.i-c.dataset.i:a.dataset[o].localeCompare(c.dataset[o],o==='he'?'he':'en')}).forEach(function(e){dl.appendChild(e)})}});az.click()})();
(function(){var g=document.querySelector('.gear'),o=document.querySelector('.opts');if(!g||!o)return;g.onclick=function(e){e.stopPropagation();var v=o.classList.toggle('open');g.setAttribute('aria-expanded',v)};document.addEventListener('click',function(e){if(!o.contains(e.target)&&e.target!==g){o.classList.remove('open');g.setAttribute('aria-expanded','false')}})})();
(function(){var E=document.getElementById('ms');if(!E)return;var M=JSON.parse(E.textContent),U=M.units,root=document.documentElement,pop=null;function ee(x){return String(x).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fmt(cc){var us=root.dataset.units!=='metric';if(!us){return cc>=1000?(cc/1000).toFixed(cc>=10000?0:2).replace(/\.?0+$/,'')+' liters':Math.round(cc)+' ml'}var oz=cc/29.5735;if(oz<32)return oz.toFixed(1)+' fl oz ('+(oz/8).toFixed(1)+' cups)';if(oz<128)return (oz/32).toFixed(1)+' quarts';var g=oz/128;return g.toFixed(g<10?1:0)+' gallons'}
function short(u){if(u.family==='eating')return fmtSmall(ccOf(u))+(u.approx?'+':'');if(u.family==='distance')return distLabel(u);if(u.family==='weight')return fmtWt(u.g);if(u.family==='length')return fmtLen(u.cm);if(u.family==='area')return fmtArea(u.sqm);if(u.family==='money')return u.ratio===1?'1 perutah':u.ratio.toLocaleString('en-US')+' perutot';return fmt(u.cc).replace(/ \(.*\)/,'').replace(/(\d+)\.\d+ gallons/,'$1 gallons').replace(/(\d+)\.0 fl oz/,'$1 fl oz')}
function fmtLen(cm){var us=root.dataset.units!=='metric';if(!us)return cm>=100?(cm/100).toFixed(2).replace(/\.?0+$/,'')+' m':(cm%1?cm.toFixed(1):cm)+' cm';var i=cm/2.54;return i<36?i.toFixed(i<10?2:1).replace(/\.?0+$/,'')+' in':(i/12).toFixed(1)+' ft'}
function fmtArea(m2){var us=root.dataset.units!=='metric';if(!us)return m2>=10000?(m2/10000).toFixed(2).replace(/\.?0+$/,'')+' hectares':Math.round(m2).toLocaleString('en-US')+' m\u00b2';var sf=m2*10.7639;return sf>=43560?(sf/43560).toFixed(1)+' acres':Math.round(sf/10)*10>=1000?(Math.round(sf/50)*50).toLocaleString('en-US')+' sq ft':Math.round(sf)+' sq ft'}
function fmtWt(g){var us=root.dataset.units!=='metric';if(!us)return g>=1000?(g/1000).toFixed(2).replace(/\.?0+$/,'')+' kg':(g%1?g.toFixed(1):g)+' g';var oz=g/28.3495;return oz<16?oz.toFixed(oz<1?2:1)+' oz':(g/453.592).toFixed(2)+' lb'}
function distLabel(u){var us=root.dataset.units!=='metric';return fmtDist(u.m)+(us&&u.kmnote?' ('+u.kmnote+')':'')}
function fmtDist(m){var us=root.dataset.units!=='metric';if(!us)return m>=1000?(m/1000).toFixed(2).replace(/\.?0+$/,'')+' km':Math.round(m)+' m';var ft=m*3.28084;return ft<1320?Math.round(ft/10)*10+' ft':(m/1609.344).toFixed(1).replace(/\.0$/,'')+' miles'}
var vfilter='all',eopin='rashi';
function ccOf(u){return u['cc_'+eopin]||u.cc}
function fmtSmall(cc){var us=root.dataset.units!=='metric';return us?(cc/29.5735).toFixed(1)+' fl oz':Math.round(cc)+' cc'}
function dim(u){var f=u.family;if(f==='eating')return Math.cbrt(ccOf(u));if(f==='weight')return Math.cbrt(u.g);return f==='money'?Math.cbrt(u.ratio):f==='volume'?Math.cbrt(u.cc):f==='length'?u.cm:Math.sqrt(u.sqm)}
function amount(u){if(u.family==='eating')return 'About <b>'+fmtSmall(ccOf(u))+'</b>'+(u.approx?' (more than this, and it varies by person)':'');if(u.family==='money')return u.ratio===1?'the smallest coin':'= '+u.ratio.toLocaleString('en-US')+' perutot';if(u.family==='distance')return 'About <b>'+distLabel(u)+'</b>';if(u.family==='weight')return 'About <b>'+fmtWt(u.g)+'</b> of silver';if(u.family==='length')return 'About <b>'+fmtLen(u.cm)+'</b>';if(u.family==='area')return 'About <b>'+fmtArea(u.sqm)+'</b>';return 'About <b>'+fmt(u.cc)+'</b>'}
function frac(r){if(r>=1)return r===Math.round(r)?String(r):r.toFixed(1);var d=1/r;return Math.abs(d-Math.round(d))<1e-9?'1/'+Math.round(d):r.toFixed(2)}
var MET={copper:['#c98a5a','#9a5a2c'],silver:['#d8d8dc','#6a6a72'],gold:['#f0c030','#a07800']};
function ladderDist(sel){var u0=U[sel],L=M.ladders.distance,mx=U[L[L.length-1]].m,LW=118,BW=380,sc=BW/mx,W=LW+BW+150,rowH=72,out='<svg viewBox="0 0 '+W+' '+(L.length*rowH+8)+'" width="100%" style="display:block;margin:0 auto;max-width:'+Math.round(W*1.25)+'px" role="img" aria-label="Distances drawn to scale as roads">'+(M.images.road?'<defs><pattern id="road" patternUnits="userSpaceOnUse" width="'+(36*M.images.road.ar)+'" height="36"><image href="'+M.images.road.src+'" width="'+(36*M.images.road.ar)+'" height="36" preserveAspectRatio="none"/></pattern></defs>':'');
L.forEach(function(k,i){var u=U[k],on=k===sel,y=i*rowH+10,w=Math.max(6,u.m*sc),r=u.ratio/u0.ratio,t='';out+='<g data-k="'+k+'" tabindex="0" role="button" aria-label="Compare everything to one '+ee(u.tr)+'" style="cursor:pointer"><rect x="0" y="'+(y-4)+'" width="'+W+'" height="'+(rowH-6)+'" fill="transparent"/><text x="'+(LW-10)+'" y="'+(y+16)+'" font-size="13" text-anchor="end" font-weight="'+(on?700:500)+'" fill="currentColor">'+ee(u.tr)+'</text><text x="'+(LW-10)+'" y="'+(y+36)+'" font-size="14" text-anchor="end" font-weight="'+(on?700:400)+'" fill="currentColor" lang="he">'+ee(u.he)+'</text>';
out+='<rect x="'+LW+'" y="'+y+'" width="'+w+'" height="36" rx="4" fill="'+(M.images.road?'url(#road)':(on?'#e0b24a':'#d8bf8f'))+'" stroke="'+(on?'#1b3a8a':'#5a4a38')+'" stroke-width="'+(on?4:1.2)+'"/>';
var ticks=k==='parsah'?4:0;for(var n=1;n<ticks;n++)out+='<line x1="'+(LW+w*n/ticks)+'" x2="'+(LW+w*n/ticks)+'" y1="'+y+'" y2="'+(y+(k==='parsah'?36:16))+'" stroke="#f5ecd9" stroke-width="'+(k==='parsah'?1.6:.8)+'"/>';
out+='<text x="'+(LW+w+10)+'" y="'+(y+24)+'" font-size="12" font-weight="800" fill="#2a1700" stroke="#fff6e0" stroke-width="3" paint-order="stroke">'+frac(r)+'</text><text x="'+(LW+w+10+(String(frac(r)).length*9+8))+'" y="'+(y+24)+'" font-size="11.5" font-weight="'+(on?700:500)+'" fill="currentColor">\u2248 '+ee(fmtDist(u.m))+'</text>'+(root.dataset.units!=='metric'&&u.kmnote?'<text x="'+(LW+w+10)+'" y="'+(y+44)+'" font-size="11" font-style="italic" fill="currentColor">('+ee(u.kmnote)+')</text>':'')+'</g>'});return out+'</svg>'}
function ladder(sel){if(U[sel].family==='distance')return ladderDist(sel);var u0=U[sel],fam=u0.family,L=(fam==='volume'&&vfilter!=='all')?M.ladders['volume_'+vfilter]:(fam==='volume'?M.ladders.volume_all:(fam==='eating'?M.ladders.eating.slice().sort(function(a,b){return ccOf(U[a])-ccOf(U[b])}):M.ladders[fam])),money=fam==='money',dfs=(fam==='money'||fam==='eating')?0:2,gp=fam==='eating'?26:(money?30:((fam==='area'||fam==='weight')?34:14)),max=U[L[L.length-1]],H=money?260:(fam==='eating'?150:(fam==='length'?85:200)),sc=H/dim(max),x=money?6:40,W=money?6:40,base=H+(money?20:16),out='';L.forEach(function(k){var u=U[k],v=(k==='dinarzahav'?Math.cbrt(2*U.dinar.ratio):dim(u))*sc,h=Math.max((money||fam==='length'||fam==='area'||fam==='weight'||fam==='eating')?8:14,v);u._h=h;var im=(M.images&&(money?(k==='maneh'?M.images.maneh:M.images['coin_'+(u.metal||'silver')]):M.images[(fam==='volume'&&vfilter!=='all')?(vfilter==='liquid'?'liquid':'dry'):(fam==='weight'?'weight':(fam==='eating'&&M.images['e_'+u.shape]?'e_'+u.shape:u.kind))]))||null;u._im=im;u._w=money?h:h*(im?im.ar:.85);u._hh=(money&&im)?h/im.ar:h;if(fam==='eating'){if(im&&im.wf){u._w=im.wf*v;u._h=u._w/im.ar}else if(im&&im.hf){u._h=im.hf*v;u._w=u._h*im.ar}else u._w=h*({olive:1.5,egg:.82,fig:1.05,bread:1.4,cup:.82}[u.shape]||1)}if(fam==='length')u._w=27;if(fam==='area')u._w=h;if(fam==='weight')u._w=h*(im?im.ar:1.1);if(k==='maneh'){u._w=Math.cbrt(U.sela.ratio)*sc;u._th=Math.max(2.6,u._w*.08);u._h=25*u._th}if(k==='maneh'&&u._im){u._hh=u._w/u._im.ar;u._h=u._hh}u._s=Math.max(u._w,money?62:(fam==='area'?78:50));u._L=(fam==='eating'&&im&&im.lx!=null)?u._w*im.lx+(u._s-u._w)/2:u._s/2;W+=u._s+gp});W+=money?12:18;if(fam==='volume')base+=34;out='<svg viewBox="0 0 '+W+' '+(base+(money?102:66))+'" width="100%" style="display:block;margin:0 auto;max-width:'+Math.round(W*1.3)+'px" role="img" aria-label="Measures drawn in proportion; each is marked with how many of the highlighted one it equals">'+'<defs><pattern id="plow" width="96" height="176" patternUnits="userSpaceOnUse"><image href="img/measures/plow.jpg" width="96" height="176" preserveAspectRatio="none"/></pattern><linearGradient id="gsl" x1="0" x2="1"><stop offset="0" stop-color="#b3b4bb"/><stop offset=".45" stop-color="#f1f1f5"/><stop offset="1" stop-color="#9fa0a8"/></linearGradient></defs><line x1="0" x2="'+W+'" y1="'+base+'" y2="'+base+'" stroke="#b8ad98" stroke-width="1.6"/>';
L.forEach(function(k,ix){var u=U[k],on=k===sel,r=(fam==='eating'?ccOf(u)/ccOf(u0):u.ratio/u0.ratio),cx=x+u._L,bx=cx-u._w*((fam==='eating'&&u._im&&u._im.lx!=null)?u._im.lx:.5),end=(ix===0||ix===L.length-1),lastm=money&&ix===L.length-1,ax=cx,an='middle',small=u._w<(money?30:28),fs=(small?11-dfs:Math.max(11-dfs,Math.min(20-dfs,u._w*.4)))*((k==='wdinar'||k==='wshekel')?.8:1),y=base-u._h,f=on?'#d9a21b':(money?'#c8c8cc':'#c9a574'),st=on?'#6b4700':(money?'#6a6a72':'#6b4f2b'),shape,ty;
if(money){var mc=MET[u.metal]||MET.silver;if(k==='maneh'&&!u._im){var q='',n,ry=u._w*.14,st2=on?'#1b3a8a':'#7b7b84',th=u._th;for(n=0;n<25;n++){var jx=((n*37)%5-2)*.5,yb=base-n*th-ry*.55,yt=yb-th;q+='<ellipse cx="'+(cx+jx)+'" cy="'+yb+'" rx="'+(u._w/2)+'" ry="'+ry+'" fill="#a4a5ad" stroke="'+st2+'" stroke-width=".5"/><rect x="'+(bx+jx)+'" y="'+yt+'" width="'+u._w+'" height="'+th+'" fill="url(#gsl)" stroke="none"/><line x1="'+(bx+jx)+'" x2="'+(bx+jx)+'" y1="'+yt+'" y2="'+yb+'" stroke="'+st2+'" stroke-width=".7"/><line x1="'+(bx+jx+u._w)+'" x2="'+(bx+jx+u._w)+'" y1="'+yt+'" y2="'+yb+'" stroke="'+st2+'" stroke-width=".7"/>'}var ty0=base-25*th-ry*.55-th;q+='<ellipse cx="'+cx+'" cy="'+ty0+'" rx="'+(u._w/2)+'" ry="'+ry+'" fill="#ececf0" stroke="'+(on?'#1b3a8a':'#6a6a72')+'" stroke-width="'+(on?2.2:1)+'"/><ellipse cx="'+cx+'" cy="'+ty0+'" rx="'+(u._w/2*.78)+'" ry="'+(ry*.78)+'" fill="none" stroke="#9a9aa2" stroke-width=".6"/>';shape=q;u._top=ty0;ty=base-u._h/2+fs*.35}else if(u._im){var hh=u._hh;shape=(on?(k==='maneh'?'<rect x="'+(bx-3)+'" y="'+(base-hh-3)+'" width="'+(u._w+6)+'" height="'+(hh+6)+'" rx="8" fill="none" stroke="#1b3a8a" stroke-width="3"/>':'<circle cx="'+cx+'" cy="'+(base-hh/2)+'" r="'+(Math.max(u._w,hh)/2+3)+'" fill="none" stroke="#1b3a8a" stroke-width="3"/>'):'')+'<image href="'+u._im.src+'" x="'+bx+'" y="'+(base-hh)+'" width="'+u._w+'" height="'+hh+'" preserveAspectRatio="none"/>';ty=small?base-hh-6:base-hh/2+fs*.35}else{shape='<circle cx="'+cx+'" cy="'+(base-u._h/2)+'" r="'+(u._h/2)+'" fill="'+mc[0]+'" stroke="'+(on?'#1b3a8a':mc[1])+'" stroke-width="'+(on?3:1.2)+'"/><circle cx="'+cx+'" cy="'+(base-u._h/2)+'" r="'+(u._h/2*.78)+'" fill="none" stroke="'+mc[1]+'" stroke-width=".7" opacity=".7"/>';ty=small?y-6:base-u._h/2+fs*.35}}
else if(fam==='length'){var rm=M.images.ruler,BW=27,HB=BW/2;shape=(rm?'<svg x="'+(cx-HB)+'" y="'+y+'" width="'+BW+'" height="'+u._h+'" viewBox="0 0 '+rm.w+' '+rm.h+'" preserveAspectRatio="xMidYMin slice"><image href="'+rm.src+'" width="'+rm.w+'" height="'+rm.h+'"/></svg><rect x="'+(cx-HB)+'" y="'+y+'" width="'+BW+'" height="'+u._h+'" fill="none" stroke="'+(on?'#1b3a8a':'#6b4f2b')+'" stroke-width="'+(on?3:1.2)+'"/>':'<rect x="'+(cx-HB)+'" y="'+y+'" width="'+BW+'" height="'+u._h+'" rx="2" fill="'+(on?'#e0b24a':'#d8bf8f')+'" stroke="'+(on?'#6b4700':'#8a6f3c')+'" stroke-width="'+(on?2.5:1.2)+'"/>')+(function(){var t='',n;for(n=1;n<u._h/8;n++)t+='<line x1="'+(cx-HB)+'" x2="'+(cx-HB+(n%4?7:13))+'" y1="'+(base-n*8)+'" y2="'+(base-n*8)+'" stroke="#5a4426" stroke-width=".7"/>';return t})();ty=y-6}
else if(fam==='eating'&&!u._im){var fc={olive:['#7d8a3c','#4c5722'],egg:['#f4ecd8','#9c8f6f'],fig:['#8a5a44','#4e2f22'],bread:['#dfae6c','#8a5f2a'],cup:['#c9a574','#6b4f2b']}[u.shape]||['#ccc','#666'],ed=u.shape==='bread'?'<rect x="'+bx+'" y="'+y+'" width="'+u._w+'" height="'+u._h+'" rx="'+(u._h*.35)+'" fill="'+fc[0]+'" stroke="'+(on?'#1b3a8a':fc[1])+'" stroke-width="'+(on?3:1.4)+'"/><path d="M'+(bx+u._w*.12)+' '+(y+u._h*.4)+' Q'+cx+' '+(y+u._h*.1)+' '+(bx+u._w*.88)+' '+(y+u._h*.4)+'" fill="none" stroke="'+fc[1]+'" stroke-width="1.2" opacity=".6"/>':'<ellipse cx="'+cx+'" cy="'+(base-u._h/2)+'" rx="'+(u._w/2)+'" ry="'+(u._h/2)+'" fill="'+fc[0]+'" stroke="'+(on?'#1b3a8a':fc[1])+'" stroke-width="'+(on?3:1.4)+'"/>';shape=ed;ty=small?y-6:base-u._h/2+fs*.35}
else if(fam==='weight'&&u._im){shape=(on?'<ellipse cx="'+cx+'" cy="'+(base+1)+'" rx="'+(u._w*.62)+'" ry="4.5" fill="#d9a21b" opacity=".9"/>':'')+'<image href="'+u._im.src+'" x="'+bx+'" y="'+y+'" width="'+u._w+'" height="'+u._h+'" preserveAspectRatio="none"/>';ty=small?y-6:y+u._h*.62+fs*.35}
else if(fam==='weight'){var wk=u._w*.09;shape='<path d="M'+bx+' '+base+' L'+(bx+u._w)+' '+base+' L'+(bx+u._w*.86)+' '+(y+u._h*.34)+' Q'+cx+' '+(y+u._h*.12)+' '+(bx+u._w*.14)+' '+(y+u._h*.34)+' Z" fill="'+(on?'#b08a4a':'#8d8478')+'" stroke="'+(on?'#1b3a8a':'#4d463c')+'" stroke-width="'+(on?3:1.4)+'"/><ellipse cx="'+cx+'" cy="'+(y+u._h*.2)+'" rx="'+(u._w*.12)+'" ry="'+(u._h*.1)+'" fill="'+(on?'#b08a4a':'#8d8478')+'" stroke="'+(on?'#1b3a8a':'#4d463c')+'" stroke-width="1.2"/>';ty=small?y-6:base-u._h*.3+fs*.35}
else if(fam==='area'){shape='<rect x="'+bx+'" y="'+y+'" width="'+u._w+'" height="'+u._h+'" fill="url(#plow)" stroke="'+(on?'#1b3a8a':'#5a3b1e')+'" stroke-width="'+(on?3:1.4)+'"/>';ty=small?y-6:y+u._h/2+fs*.35}
else if(u._im){shape=(on?'<ellipse cx="'+cx+'" cy="'+(base+1)+'" rx="'+(u._w*.62)+'" ry="4.5" fill="#d9a21b" opacity=".9"/>':'')+'<image href="'+u._im.src+'" x="'+bx+'" y="'+y+'" width="'+u._w+'" height="'+u._h+'" preserveAspectRatio="none"/>'+((k==='ephah'&&fam==='volume'&&M.images.liquid)?(function(){var y2=y-u._h-34,lq=M.images.liquid;return '<image href="'+lq.src+'" x="'+bx+'" y="'+y2+'" width="'+u._w+'" height="'+u._h+'" preserveAspectRatio="none"/><text x="'+cx+'" y="'+(y2+u._h*.62+fs*.35)+'" font-size="'+fs+'" text-anchor="middle" fill="#2a1700" stroke="#fff6e0" stroke-width="2.6" paint-order="stroke" font-weight="800">'+frac(r)+'</text><text x="'+cx+'" y="'+(y-12)+'" font-size="14" text-anchor="middle" fill="currentColor" font-weight="500">bath <tspan lang="he" font-size="15">\u05d1\u05ea</tspan></text>'})():'');ty=small?y-6:y+u._h*((fam==='eating'&&u._im.ly)?u._im.ly:.62)+fs*.35}
else{shape='<path d="M'+bx+' '+y+' L'+(bx+u._w)+' '+y+' L'+(bx+u._w*.9)+' '+base+' L'+(bx+u._w*.1)+' '+base+' Z" fill="'+f+'" stroke="'+st+'" stroke-width="'+(on?2.5:1.2)+'"/><ellipse cx="'+cx+'" cy="'+y+'" rx="'+(u._w/2)+'" ry="'+Math.max(2.5,u._w*.07)+'" fill="#efe1c3" stroke="'+st+'"/>';ty=small?y-6:y+u._h*.58+fs*.35}
out+='<g data-k="'+k+'" tabindex="0" role="button" aria-label="Compare everything to one '+ee(u.tr)+'" style="cursor:pointer"><rect x="'+x+'" y="'+(Math.min(y,ty-fs)-(k==='ephah'&&fam==='volume'?u._h+36:0))+'" width="'+u._s+'" height="'+(base+70-Math.min(y,ty-fs)+(k==='ephah'&&fam==='volume'?u._h+36:0))+'" fill="transparent"/>'+shape+'<text x="'+((fam==='eating'&&u._im&&u._im.lbx!=null)?bx+u._w*u._im.lbx:cx)+'" y="'+ty+'" font-size="'+fs+'" text-anchor="middle" fill="#2a1700" stroke="#fff6e0" stroke-width="2.6" paint-order="stroke" font-weight="800">'+frac(r)+'</text><text x="'+cx+'" y="'+(base+19)+'" font-size="'+(15-dfs)+'" text-anchor="middle" fill="currentColor" font-weight="'+(on?700:500)+'">'+ee(u.tr)+'</text><text x="'+cx+'" y="'+(base+38)+'" font-size="'+(16-dfs)+'" text-anchor="middle" fill="currentColor" font-weight="'+(on?700:400)+'" lang="he">'+ee(u.he)+'</text>'+(money?'<text x="'+ax+'" y="'+(base+55)+'" font-size="13" font-style="italic" text-anchor="'+an+'" fill="currentColor" font-weight="500">'+ee(u.metal||'')+'</text>'+(k==='maneh'?'<text x="'+ax+'" y="'+(base+73)+'" font-size="13" font-style="italic" text-anchor="middle" fill="currentColor" font-weight="500">(25 sela; 100 dinar/zuz)</text>':''):'')+(u.note?'<text x="'+ax+'" y="'+(base+(money?73:75))+'" font-size="12.5" font-style="italic" text-anchor="middle" fill="currentColor" font-weight="500">'+ee(u.note)+'</text>':'')+((end||(on&&!money))?'<text x="'+ax+'" y="'+(base+(money?(k==='maneh'?91:73):57))+'" font-size="'+(13.5-dfs)+'" text-anchor="'+an+'" fill="currentColor" font-weight="'+(on?700:500)+'">≈ '+ee(short(u))+'</text>':'')+'</g>';x+=u._s+gp});return out+'</svg>'}
function walkPanel(sel){var u=U[sel];if(u.family!=='distance'||!M.images.walker)return '';var im=M.images.walker,mins=u.ratio*18,t=mins<2?'about a minute':(mins>=60?'about '+Math.floor(mins/60)+' hour'+(mins>=120?'s':'')+(Math.round(mins%60)?' '+Math.round(mins%60)+' minutes':''):'about '+Math.round(mins)+' minutes');return '<div class="mwalk" style="display:flex;align-items:center;gap:14px;margin:8px 0 2px"><img src="'+im.src+'" alt="A traveller walking" style="height:120px;width:auto"><div style="font-size:14px"><b>On foot:</b> '+t+'\u2019 walk'+(sel==='mil'?'':', at 18 minutes to the mil')+' (Shulchan Arukh, Orach Chayim 459:2; others say 22.5 or 24 minutes).</div></div>'}
function handPanel(sel){if(U[sel].family!=='length'||!M.hand)return '';var H=M.hand,spread=sel==='zeret',im=spread?H.spread:H.closed;
function br(a,on,lab,lx,ly,anc,hz){var x1=a[0],y1=a[1],x2=a[2],y2=a[3],col=on?'#1b3a8a':'#6f7a91',w=on?8:4.5,t=hz?[0,-18]:[-18,0];return '<g'+(on?'':' opacity=".9"')+'><line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="'+col+'" stroke-width="'+w+'"/>'+(hz?'<line x1="'+x1+'" y1="'+(y1-18)+'" x2="'+x1+'" y2="'+(y1+18)+'" stroke="'+col+'" stroke-width="'+w+'"/><line x1="'+x2+'" y1="'+(y2-18)+'" x2="'+x2+'" y2="'+(y2+18)+'" stroke="'+col+'" stroke-width="'+w+'"/>':'<line x1="'+(x1-18)+'" y1="'+y1+'" x2="'+(x1+18)+'" y2="'+y1+'" stroke="'+col+'" stroke-width="'+w+'"/><line x1="'+(x2-18)+'" y1="'+y2+'" x2="'+(x2+18)+'" y2="'+y2+'" stroke="'+col+'" stroke-width="'+w+'"/>')+'<text x="'+lx+'" y="'+ly+'" font-size="34" text-anchor="'+anc+'" font-weight="'+(on?700:500)+'" fill="'+col+'" stroke="#fff" stroke-width="8" paint-order="stroke">'+lab+'</text></g>'}
var o='<div class="mhand"><div style="font-size:13px;margin:6px 0 0">Where this falls on the arm and hand, approximately <span style="opacity:.75">(a real arm varies; the measures are fixed)</span></div><svg viewBox="0 0 '+H.w+' '+H.h+'" width="100%" style="display:block;margin:0 auto;max-width:440px" role="img" aria-label="An arm and hand with the finger, handbreadth, span and cubit marked"><image href="'+im.src+'" x="0" y="0" width="'+H.w+'" height="'+H.h+'"/>';
if(spread){var z=im.zeret;o+=br(z,true,'zeret',(z[0]+z[2])/2+34,(z[1]+z[3])/2,'start')}
else{var e=im.etzba,t=im.tefach,a=im.amah;o+=br(e,sel==='etzba','etzba',e[0]+30,(e[1]+e[3])/2+12,'start');o+=br(t,sel==='tefach','tefach',t[0]-30,(t[1]+t[3])/2+12,'end');o+=br(a,sel==='amah','amah (elbow to middle fingertip)',(a[0]+a[2])/2,a[1]+52,'middle',true)}
o+='</svg></div>';return o}
function close(){if(pop){pop.remove();pop=null}}
function altName(u){return u.alt?' ('+ee(u.alt)+')':''}
function refUI(u){var fam=u.family,t='<div class="mtabs" role="tablist">';Object.keys(M.family_names).forEach(function(f){t+='<button type="button" data-fam="'+f+'" class="'+(f===fam?'on':'')+'">'+ee(M.family_names[f])+'</button>'});t+='</div>';if(fam==='eating'){t+='<div class="mvf eo"><span>Opinion</span>';[['rashi','Rashi (zayit \u00bd egg; peras 4 eggs)'],['rambam','Rambam (zayit \u2153 egg; peras 3 eggs)']].forEach(function(v){t+='<button type="button" data-eo="'+v[0]+'" class="'+(v[0]===eopin?'on':'')+'">'+v[1]+'</button>'});t+='</div>'}if(false){t+='<div class="mvf">Show: ';[['all','All'],['dry','Dry'],['liquid','Liquid']].forEach(function(v){t+='<button type="button" data-vf="'+v[0]+'" class="'+(v[0]===vfilter?'on':'')+'">'+v[1]+'</button>'});t+=(vfilter==='all'?' <span style="opacity:.75">An ephah (dry) and a bath (liquid) are the same size.</span>':'')+'</div>'}return t}
function fill(k){var u=U[k],ref=pop.dataset.ref==='1',b=(u.buys&&u.buys.length)?'<div class="mbuys"><b>'+(ref?'In the Mishnah and Talmud':'In the Mishnah')+'</b><ul>'+u.buys.map(function(t){return'<li>'+ee(t)+'</li>'}).join('')+'</ul></div>':'';pop.dataset.m=k;if(!pop.classList.contains('inline'))pop.style.width=((u.family==='money'||ref)?'min(800px,calc(100vw - 16px))':'');pop.innerHTML='<button class="gx" aria-label="Close">×</button>'+(ref?refUI(u):'')+'<h4><i>'+ee(u.tr)+'</i>'+altName(u)+' <span lang="he" dir="rtl">'+ee(u.he)+'</span></h4><div>'+amount(u)+'</div>'+ladder(k)+walkPanel(k)+handPanel(k)+b+'<div class="msrc">Tap any one to compare everything to it.'+(u.family==='volume'?' All contemporary equivalents follow R. Chaim Naeh.':'')+'</div>';pop.querySelector('.gx').addEventListener('click',close);pop.querySelectorAll('g[data-k]').forEach(function(g){g.addEventListener('click',function(e){e.stopPropagation();fill(g.dataset.k)});g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();fill(g.dataset.k)}})});
pop.querySelectorAll('.mtabs button').forEach(function(bt){bt.addEventListener('click',function(e){e.stopPropagation();fill(M.reference[bt.dataset.fam])})});
pop.querySelectorAll('.mvf button[data-eo]').forEach(function(bt){bt.addEventListener('click',function(e){e.stopPropagation();eopin=bt.dataset.eo;fill(pop.dataset.m)})});pop.querySelectorAll('.mvf button[data-vf]').forEach(function(bt){bt.addEventListener('click',function(e){e.stopPropagation();vfilter=bt.dataset.vf;var cur=pop.dataset.m,L=vfilter==='all'?M.ladders.volume_all:M.ladders['volume_'+vfilter];fill(L.indexOf(cur)>=0?cur:(vfilter==='liquid'?'log':'seah'))})})}
function place(){pop.style.top='8px';pop.style.left='50%';pop.style.transform='translateX(-50%)'}
function open(el){var k=el.dataset.m,u=U[k];if(!u)return;var idx=String([].indexOf.call(document.querySelectorAll('.mu'),el)),again=pop&&pop.dataset.i===idx;close();if(again)return;vfilter='all';pop=document.createElement('div');pop.className='mpop';pop.dataset.i=idx;document.body.appendChild(pop);fill(k);place()}
function openRef(fam,host){var wasRef=pop&&pop.dataset.ref==='1';close();if(wasRef&&!host)return;pop=document.createElement('div');pop.className='mpop'+(host?' inline':'');pop.dataset.ref='1';pop.dataset.i='ref';(host||document.body).appendChild(pop);fill(M.reference[fam||'volume']);if(!host)place()}
window.openRef=openRef;
document.addEventListener('click',function(e){var rb=e.target.closest&&e.target.closest('.refbtn');if(rb){e.preventDefault();openRef('volume');return}var t=e.target.closest&&e.target.closest('.mu');if(t){e.preventDefault();open(t)}else if(pop&&!pop.classList.contains('inline')&&!pop.contains(e.target)&&!(e.target.closest&&e.target.closest('.opts')))close()});document.addEventListener('keydown',function(e){if(e.key==='Escape'&&pop&&!pop.classList.contains('inline'))close();if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('mu')){e.preventDefault();open(e.target)}});
var sg=document.querySelector('.seg[data-key=units]');if(sg)sg.addEventListener('click',function(){if(pop)fill(pop.dataset.m)});var host=document.getElementById('refhost');if(host){var h0=(location.hash||'').replace('#','');openRef(M.reference[h0]?h0:'volume',host)}})();
resetQuiz();
var GL=null;try{GL=JSON.parse(document.getElementById('gl').textContent)}catch(e){}
var pop=null;function popsrc(el){var all=document.querySelectorAll('[data-k="'+el.dataset.k+'"]');return Array.prototype.indexOf.call(all,el)}function closePop(){if(pop){pop.remove();pop=null}}
function ee(x){return String(x).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function openPop(el){var again=pop&&pop.dataset.k===el.dataset.k&&pop.dataset.src===String(popsrc(el));closePop();if(again)return;var k=el.dataset.k,g=GL&&GL.t[k];if(!g)return;var he=root.dataset.terms==='he';
var head='<i>'+ee(g.tr)+'</i> ('+ee(g.en)+')';
var h='<button class="gx" aria-label="Close">×</button><div class="gh"><b>'+head+'</b>'+(g.he?' <span lang="he" dir="rtl">'+ee(g.he)+'</span>':'')+'</div>'+(g.def?'<p>'+ee(g.def)+'</p>':'')+(g.more?'<p>'+ee(g.more)+'</p>':'')+(g.here?'<p><b>In this tractate:</b> '+ee(g.here)+'</p>':'')+(g.loc?'<div class="loc">Primary discussion: '+ee(g.loc)+'</div>':'');
pop=document.createElement('div');pop.className='gpop';pop.dataset.k=k;pop.dataset.src=String(popsrc(el));pop.innerHTML=h;document.body.appendChild(pop);
var r=el.getBoundingClientRect(),w=pop.offsetWidth,l=Math.min(Math.max(8,r.left),window.innerWidth-w-8);pop.style.left=(l+window.scrollX)+'px';pop.style.top=(r.bottom+window.scrollY+6)+'px';
pop.querySelector('.gx').addEventListener('click',closePop)}
document.addEventListener('click',function(e){var t=e.target.closest&&e.target.closest('.kt,.kt1,.kti');if(t){e.preventDefault();openPop(t);return}if(pop&&!pop.contains(e.target))closePop()});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closePop();if((e.key==='Enter'||e.key===' ')&&e.target.dataset&&e.target.dataset.k){e.preventDefault();openPop(e.target)}});
})();
</script>"""
EN_L = "{pick:'Pick a badge from the tray first, then tap where it belongs.',tapPart:'Tap on the part of the picture you mean.',right:'Right!',rightLater:'Right, on another try.',principle:'The principle:',wrong:'Not that one. Look at the picture again and try another badge.',shown:'Answers shown.',hideAll:'Hide all',showAll:'Show all',score:function(ok,n,d){return 'Quiz: '+ok+' of '+n+' right on the first try'+(d<n?' ('+(n-d)+' still to place)':'')},allPlaced:function(ok,n){return 'All placed: '+ok+' of '+n+' right on the first try.'}}"
HE_L = "{pick:'בחרו תחילה סמל מהמגש, ואז הקישו היכן הוא שייך.',tapPart:'הקישו על החלק בתמונה שאתם מתכוונים אליו.',right:'נכון!',rightLater:'נכון, בניסיון נוסף.',principle:'העיקרון:',wrong:'לא זה. הביטו שוב בתמונה ונסו סמל אחר.',shown:'התשובות מוצגות.',hideAll:'הסתר הכול',showAll:'הצג הכול',score:function(ok,n,d){return 'חידון: '+ok+' מתוך '+n+' נכונים בניסיון הראשון'+(d<n?' (עוד '+(n-d)+' להצבה)':'')},allPlaced:function(ok,n){return 'כולם הוצבו: '+ok+' מתוך '+n+' נכונים בניסיון הראשון.'}}"
js = JS
def leg(groups, extra=""):
    g = "".join('<div class="grp">' + "".join(f'<span><img class="b{" wide" if k.startswith("pay-") else ""}" src="img/badge-{k}.png" alt=""><span class="t"><b>{esc(a)}</b> {esc(b)}</span></span>' for k, a, b in grp) + "</div>" for grp in groups)
    return '<div class="legend">' + g + extra + "</div>"
def _loc_text(x):
    """'Primary discussion' for a glossary entry: the tractate (+ chapters) and a short hand-written 'why' (defined here, treated there). Editorial; evidence: scripts/term_locations.py."""
    return " · ".join((l["name"] + " " + l.get("refs", "")).strip() + ((". " + l["why"]) if l.get("why") else "") for l in x.get("locus", []))
def _loc(x):
    t = _loc_text(x)
    return f'<div class="loc">{esc("Primary discussion")}: {esc(t)}</div>' if t else ""
def ms_json(h):
    M = json.load(open("data/measures.json"))
    return '<script type="application/json" id="ms">' + json.dumps(M, ensure_ascii=False).replace("</", "<\\/") + "</script>"
def gl_json(used):
    t = {}
    for k in used:
        g = GLOSS.get(k)
        if not g or not g.get("def"): continue   # a term with nothing to say beyond its translation gets no link
        t[k] = {"tr": TERMS[k][0], "en": TERMS[k][1], "he": g.get("he", ""), "def": g["def"], "more": g.get("more", ""), "here": g.get("here", ""), "loc": _loc_text(g)}
    return '<script type="application/json" id="gl">' + json.dumps({"t": t}, ensure_ascii=False).replace("</", "<\\/") + "</script>"
def summary_html(path, base):
    if not os.path.exists(path): return ""
    S = json.load(open(path)); refs = lambda ms: "".join(f'<a class="mref" href="#m{n}">{base}:{n}</a>' for n in ms)
    pr = "".join(f'<li>{TT(x["t"])} <span class="refs">{refs(x["m"])}</span>' + (f'<div class="pnote">{TT(x["note"])}</div>' if x.get("note") else "") + "</li>" for x in S["principles"])
    _tid = lambda x: (' id="t-' + x["id"] + '"') if x.get("id") else ""
    _tl = lambda t: re.sub(r"[^a-z ]", "", (re.search(r"\(([^()]+)\)$", t) or re.search(r"(.*)", t)).group(1).lower())
    tm = "".join(f'<details class="ti"{_tid(x)} data-en="{html.escape(_tl(x["term"]))}" data-he="{html.escape(x["he"])}"><summary><b>{term_head(x["term"])}</b> <span class="he" lang="he" dir="rtl">{esc(x["he"])}</span> <span class="refs">{refs(x["m"])}</span></summary><div class="tbody"><p>{TT(x["def"])}</p>{('<p>' + TT(x["more"]) + '</p>') if x.get("more") else ''}{('<p class="here"><b>' + esc("In this tractate") + ':</b> ' + TT(x["here"]) + '</p>') if x.get("here") else ''}{_loc(x)}</div></details>' for x in S["terms"])
    db = "".join(f'<div class="debate"><h4>{I(x["title"])} <span class="refs">{refs([x["m"]])}</span></h4><div class="sides"><div><b>{I(x.get("wa", "View 1"))}</b><p>{TT(x["a"])}</p></div><div><b>{I(x.get("wb", "View 2"))}</b><p>{TT(x["b"])}</p></div></div></div>' for x in S["debates"])
    return (f'<section id="summary"><h2>Chapter summary</h2><p class="sum">{esc("Draft for review. The outlines are in our own words.")}</p><div class="grid3">'
            f'<div class="panel aids"><h3>Key principles</h3><ol class="pr">{pr}</ol></div>'
            f'<div class="panel aids"><h3>Key terms</h3>{'<div class="tord" role="group" aria-label="Order of terms">Order: <button type="button" data-o="i">Appearance</button><button type="button" data-o="en" class="on">A\u2013Z</button><button type="button" data-o="he" lang="he">\u05d0\u2013\u05ea</button> <button type="button" data-all="1">Open all</button></div>' if LANG == "en" and len(S["terms"]) > 2 else ""}<div class="tlist">{tm}</div></div>'
            f'<div class="panel aids"><h3>Key debates</h3>{db}</div></div></section>')
HE_CH = {1, 2, 3}   # chapters that have a Hebrew page (bava-kamma-N-he.html)
HE_RTL_CSS = ("html[dir=rtl] body{font-family:'Heebo','Public Sans',system-ui,sans-serif}html[dir=rtl] ul,html[dir=rtl] ol{padding-left:0;padding-right:24px}html[dir=rtl] td,html[dir=rtl] th{text-align:right}"
              "html[dir=rtl] .chart svg{direction:ltr}html[dir=rtl] .legend .grp{border-left:0;border-right:1px solid #8886}html[dir=rtl] .legend .grp:first-child{border-right:0;padding-right:0}"
              "html[dir=rtl] .grid{direction:ltr}html[dir=rtl] .grid>*{direction:rtl}html[dir=rtl] .hot::after{content:\"הקישו\"}html[dir=rtl] .pills .sep{margin:0 6px}html[dir=rtl] .refs{white-space:nowrap}html[dir=rtl] .pnote,html[dir=rtl] figcaption{text-align:right}html[dir=rtl] .he{text-align:right}")
def map_nodes(page, fn):
    """apply fn(English string) -> Hebrew string or None to every text node and aria-label/title/alt attribute (not scripts or styles)."""
    out = []
    for part in re.split(r"(<script.*?</script>|<style.*?</style>)", page, flags=re.S):
        if part.startswith("<script") or part.startswith("<style"): out.append(part); continue
        res = []
        for pc in re.split(r"(<[^>]*>)", part):
            if pc.startswith("<"):
                def at(m):
                    raw = html.unescape(m.group(2)); t = fn(raw)
                    return m.group(0) if t is None else f'{m.group(1)}="{html.escape(t)}"'
                res.append(re.sub(r'(aria-label|title|alt)="([^"]*)"', at, pc))
            else:
                st = pc.strip(); t = fn(html.unescape(st)) if st else None
                res.append(pc.replace(st, html.escape(t), 1) if t is not None else pc)
        out.append("".join(res))
    return "".join(out)
def _build(data, layer1, diagrams, title, sub, outfile, legend, tray=()):
    he = LANG == "he"
    TRAY[:] = list(tray)
    D = json.load(open(data)); L = {m["n"]: m for m in json.load(open(layer1))["mishnayot"]}; secs = []; M_ = tr("Mishnah")
    _mm = re.search(r"bava-kamma-(\d+)", outfile); chn0 = int(_mm.group(1)) if _mm else None
    global CTX, GLOSS, CUR_TR
    CUR_TR = "bava-kamma" if "bava-kamma" in outfile else ("bava-metzia" if "bava-metzia" in outfile else "")
    _sp = data.replace(".json", "_summary.json"); GLOSS = {t["id"]: t for t in json.load(open("data/bava_kamma_1_summary.json"))["terms"] if t.get("id")}; GLOSS.update({t["id"]: t for t in json.load(open(_sp))["terms"] if t.get("id")} if os.path.exists(_sp) else {})
    for m in D["mishnayot"]:
        n = m["n"]; a = L[n]; CTX = f"{chn0}:m{n}"
        ol = "".join(f'<h4>{esc(s["h"])}</h4><ul>' + "".join(f"<li>{TT(t)}</li>" for t, src in s["b"]) + "</ul>" for s in a["outline"])
        pics = "".join((f'<div class="pgroup"><h4 class="gh"><i>{esc(p["group"])}</i>{"" if LANG != "en" else " <span>(" + esc(p["gloss"]) + ")</span>"}</h4>' + "".join(fig(q) for q in p["pics"]) + "</div>") if isinstance(p, dict) else fig(p) for p in (a.get("pictures") or [x for x in (a.get("picture"), a.get("picture2")) if x]))
        dg = diagrams[n]() if n in diagrams else ""
        if LANG != "en": en_div = ""
        else: en_div = f'<div class="en en-s">{smooth_html(m["en_p"], True) if m.get("en_p") else smooth_html(m["en_smooth"])}</div>' if m.get("en_smooth") else f'<div class="en">{en_html(m["en"])}</div>'
        biur_div = ""
        if LANG != "en":
            bp = f"data/steinsaltz/bk_{chn0}_biur.json"
            if chn0 and os.path.exists(bp) and str(n) in json.load(open(bp)):
                ps = json.load(open(bp))[str(n)]
                body = "".join(f"<p>{sg}</p>" for pc in ps for sg in pc["segs"])
                biur_div = ('<details class="biur" open><summary>ביאור</summary>' + body + '<div class="biur-credit">הביאור: הרב עדין אבן־ישראל שטיינזלץ, מהדורת וויליאם דוידסון, באדיבות ספריא. בהדגשה לשון המשנה, ברגיל הביאור. '
                            '<a href="https://creativecommons.org/licenses/by-nc/4.0/deed.he">CC BY-NC 4.0</a></div></details>')
        secs.append(f'''<section id="m{n}"><h2>{M_} {n}: {esc(a["title"])}</h2><p class="sum">{TT(a["summary"])}</p>
<div class="grid"><div class="panel aids">{ol}{table(a.get("chart")) if n not in diagrams else ""}{('<div class="chart">'+dg+'</div>') if dg else ""}</div>
<div class="panel text"><div class="he" lang="he" dir="rtl">{("".join("<p>" + html.escape(x) + "</p>" for x in m["he_p"])) if m.get("he_p") else clean(m["he"])}</div>{biur_div}{en_div}{pics}</div></div></section>''')
    CTX = f"{chn0}:summary"; _sum = summary_html(data.replace(".json", "_summary.json"), D["chapter"] if isinstance(D["chapter"], int) else str(D["chapter"]).split()[-1]); CTX = "ui"
    units_opt = "" if LANG != "en" else '<span><b>Measures</b><span class="seg" data-key="units"><button type="button" data-v="us">U.S.</button><button type="button" data-v="metric">Metric</button></span></span>'
    eng_opt = "" if LANG != "en" else '<span><b>English</b><span class="seg" data-key="eng"><button type="button" data-v="s">Smoothed</button><button type="button" data-v="d">Davidson</button></span></span>'
    terms_opt = "" if LANG != "en" else '<span><b>Terms first</b><span class="seg" data-key="terms"><button type="button" data-v="en">English</button><button type="button" data-v="he">Hebrew</button></span></span>'
    opts = '<div class="opts"><span><b>Illustrations for</b><span class="seg" data-key="aud"><button type="button" data-v="y">Younger</button><button type="button" data-v="o">Older</button></span></span><span><b>Interactive mode</b><span class="seg" data-key="mode"><button type="button" data-v="s">Static</button><button type="button" data-v="i">Explore</button><button type="button" data-v="q">Quiz</button></span></span>' + terms_opt + units_opt + '</div>'
    mo = re.search(r"bava-kamma-(\d+)\.html", outfile.replace("-he.html", ".html")); chn = int(mo.group(1)) if mo else None
    sfx = lambda c: "-he" if (he and c in HE_CH) else ""
    if mo: chs = '<span class="lbl">Bava Kamma, chapter</span>' + "".join(f'<a href="bava-kamma-{c}{sfx(c)}.html"' + (' class="on" aria-current="page"' if chn == c else '') + f'>{c}</a>' for c in range(1, 7))
    else: chs = f'<span class="lbl">{esc(title.replace("Mishnah ", ""))}</span>'
    haspics = any((a_.get("pictures") or a_.get("picture")) for a_ in L.values())
    if not haspics: opts = '<div class="opts">' + terms_opt + units_opt + '</div>' if terms_opt else ""; legend = ""
    langsw = ""
    if chn in HE_CH: langsw = f'<a class="langsw" href="bava-kamma-{chn}{"" if he else "-he"}.html" style="padding:0 12px">{"English" if he else "עברית"}</a>'
    pills = '<nav class="pills">' + chs + '<span class="sep"></span><span>Mishnah</span>' + "".join(f'<a href="#m{m["n"]}">{m["n"]}</a>' for m in D["mishnayot"]) + '<a href="#summary" style="padding:0 14px">Summary</a>' + langsw + '</nav>'
    page = head_html(tr(title) if he else title) + f'<header><a class="brand" href="index.html"><img src="img/yct-logo-white.png" alt="YCT Vibrant Torah Leadership"><span>{esc("Illustrated Mishna")}</span></a><h1>{esc(title)}</h1><div>{esc(sub)}</div>{('<button type="button" class="refbtn" aria-label="Reference tools" title="Reference: weights, measures and money"><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><rect x="2.5" y="8" width="19" height="8" rx="1.5" fill="#53607f"/><path d="M6 8v4M9 8v3M12 8v4M15 8v3M18 8v4" stroke="#fff" stroke-width="1.4"/></svg></button>' if LANG == "en" else '') + ('<button type="button" class="gear" aria-label="Settings" aria-expanded="false" title="Settings"><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="#53607f"><g><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(0 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(45 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(90 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(135 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(180 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(225 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(270 12 12)"/><rect x="9.9" y="1.2" width="4.2" height="5.2" rx="1" transform="rotate(315 12 12)"/><circle cx="12" cy="12" r="7.6"/></g><circle cx="12" cy="12" r="3.2" fill="#fff"/></svg></button>' + opts) if opts else ""}</header><div class="banner">Draft for review. <a href="index.html">All tractates</a> · <a href="#" class="aboutlink">{esc("Sources and credits")}</a></div>' + pills + ('<div class="qbar"><span class="qs" id="qscore"></span></div>' if haspics else '') + "<main>" + legend + "".join(secs) + _sum + "</main>" + (ms_json("".join(secs)) if not he else "") + (gl_json(sorted(set([k for k in re.findall(r'data-k="([^"]+)" tabindex', "".join(secs)) if k in TERMS]))) if not he else "") + foot_html() + js.replace("__L__", HE_L if he else EN_L) + "</body></html>"
    return page
def build(data, layer1, diagrams, title, sub, outfile, legend, tray=()):
    global LANG
    LANG = "en"; page = _build(data, layer1, diagrams, title, sub, outfile, legend, tray); open(outfile, "w").write(page); print(outfile, len(page))
    mo = re.search(r"bava-kamma-(\d+)\.html", outfile)
    if mo and int(mo.group(1)) in HE_CH:
        LANG = "collect"; cp = _build(data, layer1, diagrams, title, sub, outfile.replace(".html", "-he.html"), legend, tray)
        map_nodes(re.sub(r"<svg.*?</svg>", "", cp, flags=re.S), lambda x: (SEEN.setdefault(x, "ui") if re.search(r"[A-Za-z]{3}", x) else None) and None)   # SVG text is translated at source (T/multi)
        if HE:
            LANG = "he"; hp = _build(data, layer1, diagrams, title, sub, outfile.replace(".html", "-he.html"), legend, tray); LANG = "en"
            hp = map_nodes(hp, lambda x: HE.get(x))
            hp = hp.replace('<html lang="en">', '<html lang="he" dir="rtl">').replace("</style>", HE_RTL_CSS + "</style>", 1).replace("</head>", '<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600;700&display=swap" rel="stylesheet"></head>', 1)
            open(outfile.replace(".html", "-he.html"), "w").write(hp); print(outfile.replace(".html", "-he.html"), len(hp))
    LANG = "en"
if os.path.exists("data/he/strings.json"): HE.update(json.load(open("data/he/strings.json")))
TRAY_BKH = [("pay", "pays"), ("notpay", "does not pay"), ("pay-half", "pays half"), ("pay-benefit", "pays what it benefited")]
TRAY_BK = [("pay", "pays"), ("notpay", "does not pay"), ("pay-half", "pays half"), ("pay-quarter", "pays a quarter")]
TRAY_BK3 = [("pay", "pays"), ("notpay", "does not pay"), ("keeps", "keeps it")]
TRAY_BM = [("keeps", "keeps it"), ("noclaim", "has no claim"), ("return", "returns it"), ("noreturn", "does not return it"), ("hold", "holds it"), ("follow", "follows the simpon"), ("half-half", "splits in half"), ("3q-1q", "three quarters and a quarter")]
QL = '<div class="grp qlegend"><span><span class="t"><b>Quiz:</b> drag the right badge onto the picture, box or person.</span></span></div>'
PAY = [("pay", "pays", "(is liable)"), ("notpay", "does not pay", "(is exempt)")]
build("data/bava_kamma_1.json", "data/bava_kamma_1_layer1.json", DIAG_BK1, "Mishnah Bava Kamma, chapter 1", "Outlines, charts and summary", "site/bava-kamma-1.html", "")
build("data/bava_kamma_2.json", "data/bava_kamma_2_layer1.json", DIAG_BK2, "Mishnah Bava Kamma, chapter 2", "Outlines, charts and summary", "site/bava-kamma-2.html",
      leg([PAY, [("pay-half", "pays half", ""), ("pay-benefit", "pays what it benefited", "")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a person or an object to see the ruling.</span></span></div>' + QL), tray=TRAY_BKH)
build("data/bava_kamma_4.json", "data/bava_kamma_4_layer1.json", DIAG_BK4, "Mishnah Bava Kamma, chapter 4", "Outlines, charts and summary", "site/bava-kamma-4.html",
      leg([PAY, [("pay-half", "pays half", ""), ("pay-benefit", "pays what it benefited", "")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a person or an object to see the ruling.</span></span></div>' + QL), tray=TRAY_BKH)
build("data/bava_kamma_6.json", "data/bava_kamma_6_layer1.json", DIAG_BK6, "Mishnah Bava Kamma, chapter 6", "Outlines, charts and summary", "site/bava-kamma-6.html",
      leg([PAY, [("pay-half", "pays half", ""), ("pay-benefit", "pays what it benefited", "")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a person or an object to see the ruling.</span></span></div>' + QL), tray=TRAY_BKH)
build("data/bava_kamma_5.json", "data/bava_kamma_5_layer1.json", DIAG_BK5, "Mishnah Bava Kamma, chapter 5", "Outlines, charts and pictures", "site/bava-kamma-5.html",
      leg([PAY, [("pay-half", "pays half", ""), ("pay-quarter", "pays a quarter", "")]], '<div class="grp"><span><span class="t">A <b>?</b> between two boxes: the two possibilities the mishnah decides between.</span></span></div><div class="grp ionly"><span><span class="t"><b>Tap</b> a picture, a box or a person to see the ruling.</span></span></div>' + QL), tray=TRAY_BK)
build("data/bava_kamma_3.json", "data/bava_kamma_3_layer1.json", {}, "Mishnah Bava Kamma, chapter 3", "Outlines, charts and pictures", "site/bava-kamma-3.html",
      leg([PAY, [("keeps", "keeps it", "")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a picture or a person to see the ruling.</span></span></div>' + QL), tray=TRAY_BK3)
build("data/bava_metzia_1.json", "data/bava_metzia_1_layer1.json", DIAG_BM1, "Mishnah Bava Metzia, chapter 1", "Outlines, charts and pictures", "site/bava-metzia-1.html",
      leg([[("keeps", "keeps it", ""), ("noclaim", "has no claim", "")], [("return", "returns it", ""), ("noreturn", "does not return it", "")], [("hold", "holds it", ""), ("follow", "follows the simpon", "(the attached note)")]], '<div class="grp ionly"><span><span class="t"><b>Tap</b> a picture, a box or a person to see the ruling.</span></span></div>' + QL), tray=TRAY_BM)
TRACTATES = [("bava-kamma", "Bava Kamma", "בבא קמא", "damages", [(1, "the four primary causes of injury", 4), (2, "foot, tooth, tam and mu'ad", 6), (3, "damages in the public domain, collisions, oxen", 11), (4, "the goring ox, guards, an ox that kills", 9), (5, "pit, courtyard and ox cases", 7), (6, "the flock and fire", 6)]),
             ("bava-metzia", "Bava Metzia", "בבא מציעא", "found objects, loans and hire", [(1, "found objects and documents", 8)])]
CSS_HOME = "<style>.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin:22px 0}.tcard{display:block;text-decoration:none;color:var(--fg);background:var(--card);border:2px solid var(--blue);border-radius:16px;padding:26px 24px;box-shadow:0 1px 4px #0002}.tcard:hover{background:var(--tint)}.tcard h2{margin:0;font-family:Newsreader,Georgia,serif;font-size:32px;color:var(--blue)}.tcard .hx{font-size:26px;margin-top:2px;font-family:'Times New Roman',serif}.tcard p{margin:8px 0 0;opacity:.8}.chap{background:var(--card);border-radius:14px;padding:14px 20px;margin:14px 0;box-shadow:0 1px 4px #0002}.chap h3{margin:0 0 2px;font-family:Newsreader,Georgia,serif}.chap .d{opacity:.8;margin:0 0 8px}.mp{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.mp a{display:inline-grid;place-items:center;min-width:36px;height:36px;border-radius:18px;background:var(--card);color:var(--blue);text-decoration:none;font-weight:700;border:1.5px solid var(--blue);padding:0 6px}.mp a:hover{background:var(--blue);color:#fff}.mp .w{font-weight:600;margin-right:6px}.crumbs{padding:10px 24px;font-size:14px}</style>"
def tractate_page(slug, name, he, blurb, chapters):
    rows = ""
    for c, desc, n in chapters:
        pills = "".join(f'<a href="{slug}-{c}.html#m{k}">{k}</a>' for k in range(1, n + 1))
        hebr = f'</div><div class="mp" style="margin-top:6px"><span class="w" lang="he">עברית</span>' + "".join(f'<a href="{slug}-{c}-he.html#m{k}" lang="he">{k}</a>' for k in range(1, n + 1)) if (slug == "bava-kamma" and c in HE_CH) else ""
        rows += f'<div class="chap"><h3><a href="{slug}-{c}.html">Chapter {c}</a></h3><p class="d">{esc(desc)}</p><div class="mp"><span class="w">Mishnah</span>{pills}{hebr}</div></div>'
    more = '<p class="d">More chapters will follow.</p>'
    return (head_html(name).replace("</style>", CSS_HOME[7:-8] + "</style>", 1) + f'<header><a class="brand" href="index.html"><img src="img/yct-logo-white.png" alt="YCT Vibrant Torah Leadership"><span>{esc("Illustrated Mishna")}</span></a><h1>{esc(name)} <span lang="he">{he}</span></h1><div>Choose a chapter, or go straight to a mishnah</div></header><div class="banner">Draft for review. <a href="index.html">All tractates</a></div><main>' + rows + more + "</main>" + foot_html() + "</body></html>")
cards = "".join(f'<a class="tcard" href="{slug}-1.html"><h2>{name}</h2><div class="hx" lang="he">{he}</div></a>' for slug, name, he, blurb, chs in TRACTATES)
cards += '<a class="tcard" href="reference.html"><h2>Reference</h2><div class="hx" style="font-size:18px">Weights, measures and money</div></a>'
open("site/index.html", "w").write(head_html("Illustrated Mishna").replace("</style>", CSS_HOME[7:-8] + "</style>", 1) + '<header><a class="brand" href="index.html"><img src="img/yct-logo-white.png" alt="YCT Vibrant Torah Leadership"><span>Illustrated Mishna</span></a><div>Mishnah with outlines, charts and illustrations</div></header><div class="banner">Prototype for review. Link-only; not indexed.</div><main><div class="tcards">' + cards + '</div></main>' + foot_html() + "</body></html>")
os.makedirs("data/he", exist_ok=True)
_need = sorted(x for x in SEEN if x not in HE and not (re.fullmatch(r"[\w./#:\-]+", x) and re.search(r"[\d./#:_]", x)))
json.dump(_need, open("data/he/_needed.json", "w"), ensure_ascii=False, indent=1); json.dump({x: SEEN[x] for x in sorted(SEEN) if not (re.fullmatch(r"[\w./#:\-]+", x) and re.search(r"[\d./#:_]", x))}, open("data/he/_all.json", "w"), ensure_ascii=False, indent=1); print("Hebrew strings still needed:", len(_need))

# ---- stand-alone Reference page (same box as the header button)
LANG = "en"
_b1 = open("site/bava-kamma-1.html").read()
_gear = re.search(r'<button type="button" class="gear".*?</button>', _b1, re.S).group(0)
_unit = '<span><b>Measures</b><span class="seg" data-key="units"><button type="button" data-v="us">U.S.</button><button type="button" data-v="metric">Metric</button></span></span>'
open("site/reference.html", "w").write(head_html("Reference: weights, measures and money") + '<header><a class="brand" href="index.html"><img src="img/yct-logo-white.png" alt="YCT Vibrant Torah Leadership"><span>Illustrated Mishna</span></a><h1>Reference</h1><div>Weights, measures and money, as used in the Mishnah</div>' + _gear + '<div class="opts">' + _unit + '</div></header><div class="banner">Draft for review. <a href="index.html">All tractates</a></div><main><div id="refhost"></div></main>' + ms_json("") + foot_html() + js.replace("__L__", EN_L) + "</body></html>")
print("site/reference.html")
