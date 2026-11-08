#!/usr/bin/env python3
"""Ein Mishpat notes by letter and by the word they mark, from Hebrew Wikisource. No Anthropic API.

Sefaria's links say only which line an Ein Mishpat reference belongs to. A line can carry several
notes (Shabbat 104b:4 has ט on ואפצא and י on כתבו באבר), so comparing a reference with the whole line
can't tell its note from the next one. Wikisource has both halves: its Gemara pages mark each note's
letter on its word ({{שוליים|ט}}ואפצא), and its "עין משפט ונר מצוה" pages give each note's contents.

    venv/bin/python em_notes.py fetch     # raw pages -> xrefs/wikisource/ (resumable)
    venv/bin/python em_notes.py build     # -> xrefs/em_notes/<Tractate>.json

Wikisource has Ein Mishpat pages for 24 tractates; the rest are skipped.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from build_xrefs import LETTERS, OUT as XREFS
from check_xrefs import he_num

HERE = Path(__file__).parent
RAW = XREFS / "wikisource"
OUT = XREFS / "em_notes"
DAF_TEXT = HERE / "daf_text"
API = "https://he.wikisource.org/w/api.php"
EM_PREFIX = "עין משפט ונר מצוה/"

# Our tractate names -> Wikisource's
HE_TRACTATE = {
    "Berakhot": "ברכות", "Shabbat": "שבת", "Eiruvin": "עירובין", "Pesachim": "פסחים", "Yoma": "יומא",
    "Sukkah": "סוכה", "Beitzah": "ביצה", "Rosh Hashanah": "ראש השנה", "Taanit": "תענית",
    "Megillah": "מגילה", "Moed Katan": "מועד קטן", "Chagigah": "חגיגה", "Yevamot": "יבמות",
    "Ketubot": "כתובות", "Nedarim": "נדרים", "Nazir": "נזיר", "Sotah": "סוטה", "Gittin": "גיטין",
    "Kiddushin": "קידושין", "Bava Kamma": "בבא קמא", "Bava Metzia": "בבא מציעא", "Bava Batra": "בבא בתרא",
    "Sanhedrin": "סנהדרין", "Makkot": "מכות", "Shevuot": "שבועות", "Avodah Zarah": "עבודה זרה",
    "Horayot": "הוריות", "Zevachim": "זבחים", "Menachot": "מנחות", "Hullin": "חולין", "Bekhorot": "בכורות",
    "Arakhin": "ערכין", "Temurah": "תמורה", "Keritot": "כריתות", "Meilah": "מעילה", "Tamid": "תמיד",
    "Niddah": "נדה",
}


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "AnyDaf cross-references (dlinzer@yctorah.org)"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network blips: back off and retry
            if attempt == 4:
                raise
            print(f"  retry ({e})", flush=True)
            time.sleep(5 * (attempt + 1))


def _contents(titles: list[str]) -> dict[str, str]:
    """Raw wikitext for up to 50 titles; missing pages are left out."""
    d = _get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
              "titles": "|".join(titles)})
    out = {}
    for p in d["query"]["pages"].values():
        if "revisions" in p:
            out[p["title"]] = p["revisions"][0]["slots"]["main"]["*"]
    return out


def em_titles() -> list[str]:
    titles, cont = [], {}
    while True:
        d = _get({"action": "query", "list": "allpages", "apprefix": EM_PREFIX, "aplimit": 500, **cont})
        titles += [p["title"] for p in d["query"]["allpages"]]
        if "continue" not in d:
            return titles
        cont = d["continue"]


def amudim(tractate: str) -> list[str]:
    return list(json.loads((XREFS / f"{tractate}.json").read_text())["amudim"])


def page_title(tractate: str, amud: str) -> str:
    return f"{HE_TRACTATE[tractate]} {he_num(int(amud[:-1]))} {'א' if amud[-1] == 'a' else 'ב'}"


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    em_file = RAW / "_ein_mishpat.json"
    em = json.loads(em_file.read_text()) if em_file.exists() else {}
    if not em:
        titles = em_titles()
        for i in range(0, len(titles), 50):
            em.update(_contents(titles[i:i + 50]))
        em_file.write_text(json.dumps(em, ensure_ascii=False))
    print(f"Ein Mishpat pages: {len(em)}", flush=True)
    covered = {t.split("/")[1] for t in em}
    for tractate, he in HE_TRACTATE.items():
        if he not in covered or not (XREFS / f"{tractate}.json").exists():
            continue
        dest = RAW / f"{tractate}.json"
        if dest.exists():
            continue
        pages = {}
        want = {page_title(tractate, a): a for a in amudim(tractate)}
        keys = list(want)
        for i in range(0, len(keys), 50):
            got = _contents(keys[i:i + 50])
            pages.update({want[t]: txt for t, txt in got.items() if t in want})
            time.sleep(0.5)
        dest.write_text(json.dumps(pages, ensure_ascii=False))
        print(f"{tractate}: {len(pages)} of {len(want)} amudim", flush=True)


# --- parsing ---------------------------------------------------------------------------------
FINALS = str.maketrans("ךםןףץ", "כמנפצ")
SA_SECTION = {'או"ח': "Orach Chayim", 'יו"ד': "Yoreh De'ah", 'אה"ע': "Even HaEzer", 'חו"מ': "Choshen Mishpat"}
SECTION_SA = {v: k for k, v in SA_SECTION.items()}
TEMPLATE = re.compile(r"\{\{\s*([^|{}]+?)\s*((?:\|[^{}]*)?)\}\}")
NOTE_LETTER = re.compile(r'\{\{ד"מ\|([^}|]+)\}\}')
RAMBAM = re.compile(r'\{\{עין\s+משפט רמב"ם\|([^|}]*)\|([^|}]*)\|([^|}]*)\}\}((?:\s*(?:ו?הלכה|ו?הלכות|ו)\s*[א-ת"\']+)*)')
SA = re.compile(r'\{\{עין משפט טוש"ע\|([^|}]*)\|([^|}]*)\|?([^|}]*)\}\}((?:\s*(?:ו?סעיף|ו?סעיפים|ו)\s*[א-ת"\']+)*)')


def num(s: str) -> int:
    """Value of a Hebrew numeral ("יא", "קכה", "ט\"ו"); 0 when it isn't one."""
    s = re.sub(r"[\"'׳״]", "", s.strip())
    return sum(LETTERS.get(c, 0) for c in s.translate(FINALS)) if s and all(
        c in LETTERS for c in s.translate(FINALS)) else 0


def extra_nums(tail: str) -> list[int]:
    return [n for n in (num(w) for w in re.findall(r"[א-ת\"']+", tail) if w not in (
        "והלכה", "הלכה", "והלכות", "הלכות", "סעיף", "וסעיף", "סעיפים", "וסעיפים")) if n]


def plain(wikitext: str) -> str:
    """A note's text for a reader: templates spelled out, links reduced to their label."""
    def tpl(m):
        name, args = m.group(1), [a for a in m.group(2).split("|")[1:]]
        if name.startswith("עין") and 'רמב"ם' in name and len(args) >= 3:
            return f'רמב"ם הלכות {args[1]} פרק {args[0]} הלכה {args[2]}'
        if name == 'עין משפט טוש"ע' and len(args) >= 2:
            return f'טוש"ע {args[0]} סימן {args[1]}' + (f" סעיף {args[2]}" if len(args) > 2 and args[2] else "")
        return ""
    s = re.sub(r"<[^>]+>", "", wikitext)
    s = TEMPLATE.sub(tpl, s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", s).strip(" :")


SA_NAMES = {**SA_SECTION, 'י"ד': "Yoreh De'ah", 'א"ה': "Even HaEzer", 'אבה"ע': "Even HaEzer", 'ח"מ': "Choshen Mishpat",
            "אורח חיים": "Orach Chayim", "יורה דעה": "Yoreh De'ah", "אבן העזר": "Even HaEzer",
            "חושן משפט": "Choshen Mishpat"}
PIECES = re.compile(
    r'(?P<rt>\{\{עין\s+משפט רמב"ם\|(?P<rt_ch>[^|}]*)\|(?P<rt_name>[^|}]*)\|(?P<rt_h>[^|}]*)(?:\|[^}]*)?\}\})'
    r'|(?P<st>\{\{עין משפט טוש"ע\|(?P<st_sec>[^|}]*)\|(?P<st_si>[^|}]*)\|?(?P<st_se>[^|}]*)\}\})'
    r'|(?P<rl>\[\[רמב"ם הלכות (?P<rl_name>[^\]|#]+?) (?P<rl_ch>[א-ת"\']+)(?: (?P<rl_h2>[א-ת"\']+))?(?:#הלכה (?P<rl_h>[א-ת"\']+))?(?:\|(?P<rl_lab>[^\]]*))?\]\])'
    r'|(?P<sl>\[\[שולחן ערוך (?P<sl_sec>אורח חיים|יורה דעה|אבן העזר|חושן משפט) (?P<sl_si>[א-ת"\']+)(?: (?P<sl_se>[א-ת"\']+))?(?:\|[^\]]*)?\]\])'
    r'|(?P<rp>מיי\'[^,:\[{]*)'
    r'|(?P<sp>(?:טוש"ע|טור ש"ע|טור וש"ע|ש"ע|שו"ע)[^,:\[{]*)'
    r'|(?P<more>(?:ו?הלכה|ו?הלכות|ו?הל\'|ו?סעיף|ו?סעיפים|וסי\')\s*[^,:\[{]*)')
NUMWORD = re.compile(r'[א-ת]+(?:["\'][א-ת]?)?')


def numeral(w: str) -> int:
    """A properly formed numeral's value ("יז", "י\"ז", "קכה", "טו"); 0 for any other word."""
    bare = re.sub(r"[\"'׳״]", "", w).translate(FINALS)
    n = num(bare)
    return n if n and he_num(n) == bare and bare not in ("שמ",) else 0


def numbers(s: str) -> list[int]:
    """The numerals at the start of a run like "ז ח ט", "ב' וד'"; stops at the first other word."""
    out = []
    s = re.sub(r"([א-ת\"']+)\s*[-–]\s*([א-ת\"']+)", lambda m: f"{m.group(1)} עד {m.group(2)}", s)
    span = False
    for w in NUMWORD.findall(s):
        if w in ("הלכה", "והלכה", "הלכות", "והלכות", "הל", "והל", "סעיף", "וסעיף", "סעיפים", "וסעיפים", "סע",
                 "וסע"):
            continue   # "הלכה ט והלכה י והלכה יא"
        if w == "עד":
            span = True
            continue
        n = numeral(w) or (numeral(w[1:]) if w.startswith("ו") and len(w) > 1 else 0)
        if not n:
            break
        if span and out and n > out[-1]:   # "ו-י": six through ten
            out.extend(range(out[-1] + 1, n + 1))
        else:
            out.append(n)
        span = False
    return out


def note_refs(line: str, state: dict) -> list[dict]:
    """The Rambam and Shulchan Arukh places a note cites, in any of Wikisource's forms."""
    refs, last = [], None   # last: the work a following "והלכה ח" / "וסעיף מ" continues

    def rambam(ch, hals, name=""):
        nonlocal last
        state["rambam"] = (ch, name)
        last = "rambam"
        refs.extend({"work": "rambam", "halakhot": name, "nums": [ch, h]} for h in hals)
        if not hals and ch:
            refs.append({"work": "rambam", "halakhot": name, "nums": [ch]})

    def sa(sec, siman, seifs):
        nonlocal last
        state["sa"] = (sec, siman)
        last = "sa"
        if seifs:
            refs.extend({"work": "sa", "section": sec, "nums": [siman, s]} for s in seifs)
        else:
            refs.append({"work": "sa", "section": sec, "nums": [siman]})

    for m in PIECES.finditer(line):
        g = m.groupdict()
        if g["rt"]:
            rambam(num(g["rt_ch"]), [num(g["rt_h"])] if num(g["rt_h"]) else [], g["rt_name"].strip())
        elif g["st"] and SA_NAMES.get(g["st_sec"].strip()):
            sa(SA_NAMES[g["st_sec"].strip()], num(g["st_si"]), [num(g["st_se"])] if num(g["st_se"]) else [])
        elif g["rl"]:
            # the link target is "BOOK CH [H]"; the book can be several words, so read the numbers off the end
            words = " ".join(x for x in (g["rl_name"], g["rl_ch"], g["rl_h2"]) if x).split()
            tail = []
            while words and numeral(words[-1]) and len(tail) < 2:
                tail.insert(0, numeral(words.pop()))
            if not tail or not words:
                continue
            g = {**g, "rl_name": " ".join(words), "rl_ch": None}
            ch = tail[0]
            hals = [h for h in (tail[1:] + ([numeral(g["rl_h"])] if g["rl_h"] and numeral(g["rl_h"]) else [])) if h]
            lab = g["rl_lab"] or ""
            k = re.search(r"הלכ(?:ה|ות|')\s*(.*)", lab)
            for h in numbers(k.group(1)) if k else []:
                if h not in hals:
                    hals.append(h)
            rambam(ch, hals, g["rl_name"])
        elif g["sl"]:
            sa(SA_NAMES[g["sl_sec"]], num(g["sl_si"]), [num(g["sl_se"])] if g["sl_se"] else [])
        elif g["rp"]:
            s = g["rp"]
            # each "פ"X מהל' NAME הלכה A B" (or "שם הל' A") is one chapter
            for part in re.split(r"\s+ו(?=פ[\"א-ת])", s):
                ch = re.search(r"(?:^|\s)(?:פרק\s+([א-ת\"']+)|פ([א-ת]*\"[א-ת]|[א-ת])(?=\s))", part)
                name = re.search(r"מהל(?:כות|')\s+(.+?)(?=\s+הל|$)", part)
                h = re.search(r"(?:^|\s)הל(?:כה|כות|כ'|')?\s*(.*)$", part)   # not the הל of מהל'
                hals = numbers(h.group(1)) if h else []
                if "שם" in part.split()[:3] and not ch and state["rambam"]:
                    c, nm = state["rambam"]
                    if hals:
                        rambam(c, hals, nm)
                    else:   # "מיי' שם": the previous note's places
                        prev = [r for r in state.get("rambam_refs", [])]
                        refs.extend(prev)
                        last = "rambam"
                elif ch:
                    rambam(num(ch.group(1) or ch.group(2)), hals, name.group(1) if name else "")
            state["rambam_refs"] = [r for r in refs if r["work"] == "rambam"] or state.get("rambam_refs", [])
        elif g["sp"]:
            s = g["sp"]
            for part in re.split(r"\s+ו(?=סי)", s):
                sec = next((v for k, v in SA_NAMES.items() if re.search(r"(?:^|\s)" + re.escape(k) + r"(?:\s|$)", part)),
                           None)
                si = re.search(r"סי(?:מן|')\s*([א-ת\"']+)", part)
                se = re.search(r"סע(?:יף|יפים|')\s*(.*)$", part)
                seifs = numbers(se.group(1)) if se else []
                if sec is None and state["sa"]:
                    sec = state["sa"][0]
                siman = num(si.group(1)) if si else (state["sa"][1] if state["sa"] and sec == state["sa"][0] else 0)
                if sec and siman:
                    sa(sec, siman, seifs)
        elif g["more"] and last and not re.search(r"[|\]]", g["more"]):   # not words inside another work's link
            extra = numbers(re.sub(r"^ו?(?:הלכה|הלכות|הל'|סעיף|סעיפים)", "", g["more"]))
            if last == "rambam" and state["rambam"]:
                rambam(state["rambam"][0], extra, state["rambam"][1])
            elif last == "sa" and state["sa"] and not g["more"].startswith("וסי"):
                sa(state["sa"][0], state["sa"][1], extra)
    if any(r["work"] == "rambam" for r in refs):
        state["rambam_refs"] = [r for r in refs if r["work"] == "rambam"]
    return refs


def parse_notes(em: dict[str, str], he_tractate: str) -> dict[str, list[dict]]:
    """amud ("104b") -> its notes: [{letters, refs, text}] in page order."""
    out: dict[str, list[dict]] = {}
    state = {"rambam": None, "sa": None}   # the last place cited, for "שם"
    for title, txt in em.items():
        if title.split("/")[1] != he_tractate:
            continue
        for m in re.finditer(r"<קטע התחלה=([^/>]+?)\s*/>(.*?)<קטע סוף=\1\s*/>", txt, re.S):
            parts = m.group(1).split()
            if len(parts) != 2 or not num(parts[0]):
                continue
            amud = f"{num(parts[0])}{'a' if parts[1] == 'א' else 'b'}"
            for line in m.group(2).split("\n"):
                letters = NOTE_LETTER.findall(line)
                if not letters:
                    continue
                refs = note_refs(line, state)
                out.setdefault(amud, []).append(
                    {"letters": [l.strip() for l in letters], "refs": refs,
                     "text": plain(NOTE_LETTER.sub("", re.sub(r"\{\{נר מצוה פתיחה\|[^}]*\}\}", "", line)))})
    return out


NIKUD = re.compile(r"[֑-ׇ]")


def norm(w: str) -> str:
    return re.sub(r"[^א-ת]", "", NIKUD.sub("", w)).translate(FINALS)


def gemara_tokens(wikitext: str):
    """[(word, original, letters marking it)] for a Wikisource Gemara page (the Gemara only, not the
    Rashi and Tosafot that follow it on the same page)."""
    parts = re.findall(r"<קטע התחלה=ג\s*/>(.*?)<קטע סוף=ג\s*/>", wikitext, re.S)
    s = re.sub(r"<[^>]+>", " ", " ".join(parts) if parts else wikitext)
    s = re.sub(r"\{\{שוליים\|([א-ת]{1,2})\}\}", r" @@\1@@ ", s)
    for _ in range(3):  # nested templates: innermost first
        s = re.sub(r"\{\{[^{}]*\}\}", " ", s)
    s = s.replace("'''", "")
    out, pending = [], []
    for tok in s.split():
        m = re.fullmatch(r"@@([א-ת]{1,2})@@", tok)
        if m:
            pending.append(m.group(1))
            continue
        w = norm(tok)
        if w:
            out.append((w, tok, pending))
            pending = []
    return out


def sefaria_words(segments):
    words, line_of = [], []
    for seg in segments:
        for tok in seg["he"].split():
            w = norm(tok)
            if w:
                words.append(w)
                line_of.append(seg["n"])
    return words, line_of


def markers(wikitext: str, segments) -> dict[str, dict]:
    """letter -> {line, word}: the Sefaria line and the printed words a note's letter sits on."""
    import difflib
    toks = gemara_tokens(wikitext)
    sw, line_of = sefaria_words(segments)
    if not toks or not sw:
        return {}
    sm = difflib.SequenceMatcher(None, [t[0] for t in toks], sw, autojunk=False)
    to_sef = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            to_sef[a + k] = b + k
    out = {}
    for i, (_, orig, letters) in enumerate(toks):
        if not letters:
            continue
        j = next((to_sef[k] for k in range(i, min(i + 6, len(toks))) if k in to_sef), None)
        if j is None:
            j = next((to_sef[k] for k in range(i - 1, max(i - 6, -1), -1) if k in to_sef), None)
        word = " ".join(t[1] for t in toks[i:i + 3])
        # the stretch this letter covers: up to the next letter, at least 8 words, at most 40
        nxt = next((k for k in range(i + 1, len(toks)) if toks[k][2]), len(toks))
        phrase = " ".join(t[1] for t in toks[i:min(max(nxt, i + 8), i + 40)])
        for letter in letters:
            out.setdefault(letter, {"line": line_of[j] if j is not None else None, "word": word,
                                    "phrase": phrase})
    return out


def link_key(it: dict):
    """(work, section, nums) of a Sefaria Ein Mishpat link, for comparing with a note's refs."""
    ref, work = it["ref"], it.get("work")
    m = re.match(r"^(.*?) (\d+(?::\d+)*)", ref)
    if not m or work not in ("rambam", "sa"):
        return None
    nums = [int(x) for x in m.group(2).split(":")]
    # the SA section, or the Rambam book (Sefaria's title)
    section = m.group(1).split(", ")[-1] if work == "sa" else m.group(1)
    return work, section, nums


def matches(key, r) -> bool:
    work, section, nums = key
    if r["work"] != work or (work == "sa" and r["section"] != section):
        return False
    if work == "rambam":   # a book the note names must be the link's book (unresolved names don't block)
        book = rambam_book(r.get("halakhot"))
        if book and section and book != section:
            return False
    n = min(len(nums), len(r["nums"]))
    return n > 0 and nums[:n] == r["nums"][:n] and (work != "rambam" or n == 2 or len(r["nums"]) == 1)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    em = json.loads((RAW / "_ein_mishpat.json").read_text())
    total = {}
    for f in sorted(RAW.glob("*.json")):
        if f.name.startswith("_"):
            continue
        tractate = f.stem
        pages = json.loads(f.read_text())
        notes = parse_notes(em, HE_TRACTATE[tractate])
        text = json.loads((DAF_TEXT / f"{tractate}.json").read_text())["amudim"]
        links = json.loads((XREFS / f"{tractate}.json").read_text())["amudim"]
        result, stats = {}, {}
        for amud, lines in links.items():
            amud_notes = notes.get(amud, [])
            mk = markers(pages.get(amud, ""), text.get(amud, {}).get("segments", [])) if amud in pages else {}
            rows = {}
            for n, items in lines.items():
                for it in items:
                    key = it.get("k") == "em" and link_key(it)
                    if not key:
                        continue
                    found = [nt for nt in amud_notes if any(matches(key, r) for r in nt["refs"])]
                    cands = [{"letter": l, "text": nt["text"], **mk.get(l, {"line": None, "word": None})}
                             for nt in found for l in nt["letters"]]
                    here = [c for c in cands if c["line"] == int(n)]
                    if here:
                        status = "on_line"
                    elif any(c["line"] is not None for c in cands):
                        status = "other_line"
                    elif cands:
                        status = "no_marker"
                    else:
                        status = "no_note" if amud_notes else "no_notes_for_amud"
                    stats[status] = stats.get(status, 0) + 1
                    rows.setdefault(n, []).append({"ref": it["ref"], "status": status, "notes": here or cands})
            result[amud] = {"lines": rows, "notes": amud_notes, "markers": mk}
        (OUT / f"{tractate}.json").write_text(json.dumps(
            {"tractate": tractate, "amudim": result}, ensure_ascii=False, indent=0))
        print(f"{tractate}: {stats}", flush=True)
        for k, v in stats.items():
            total[k] = total.get(k, 0) + v
    print("all:", total)



# ---- Rambam book names: Wikisource's Hebrew (often shortened) -> Sefaria's English title ----
BOOKS_FILE = XREFS / "meta" / "rambam_books.json"   # Sefaria title -> heTitle, from Sefaria's /api/index
BOOK_ALIASES = {   # acronyms and short forms the word matching can't resolve
    'יו"ט': "Rest on a Holiday", 'יום טוב': "Rest on a Holiday", 'ת"ת': "Torah Study",
    'ק"ש': "Reading the Shema", 'עכו"ם': "Foreign Worship and Customs of the Nations",
    'ע"ז': "Foreign Worship and Customs of the Nations", 'ס"ת': "Tefillin, Mezuzah and the Torah Scroll",
    'עבודת יוה"כ': "Service on the Day of Atonement", 'יוה"כ': "Service on the Day of Atonement",
    'שביתת עשור': "Rest on the Tenth of Tishrei", 'שמיטין': "Sabbatical Year and the Jubilee",
    'מגילה': "Scroll of Esther and Hanukkah", 'נשיאות כפים': "Prayer and the Priestly Blessing",
    'ברכת כהנים': "Prayer and the Priestly Blessing", 'מתנות כהונה': "First Fruits and other Gifts to Priests Outside the Sanctuary",
    'אבידה': "Robbery and Lost Property", 'פקדון': "Borrowing and Deposit",
    'מעשר': "Tithes", 'מלוה': "Creditor and Debtor", 'מלווה': "Creditor and Debtor",
    'ביאת המקדש': "Admission into the Sanctuary", 'תמידין': "Daily Offerings and Additional Offerings",
    'תמידין ומוספין': "Daily Offerings and Additional Offerings", 'פסולי מוקדשין': "Sacrifices Rendered Unfit",
    'ערכין': "Appraisals and Devoted Property", 'ערכין וחרמין': "Appraisals and Devoted Property",
    'טומאת אוכלין': "Defilement of Foods", 'מעשה קרבנות': "Sacrificial Procedure", 'מעה"ק': "Sacrificial Procedure",
    'איסורי מזבח': "Things Forbidden on the Altar", 'כלי מקדש': "Vessels of the Sanctuary and Those Who Serve Therein",
    'עבודת כוכבים': "Foreign Worship and Customs of the Nations", 'עו"ג': "Foreign Worship and Customs of the Nations",
    'ס"ת ומזוזה': "Tefillin, Mezuzah and the Torah Scroll", 'טומאת משכב ומושב': "Those Who Defile Bed or Seat",
    'נשיאת כפים': "Prayer and the Priestly Blessing", 'י"ט': "Rest on a Holiday", 'שלוחים': "Agents and Partners",
    'טומאת המת': "Defilement by a Corpse",
}


def _sk(s: str) -> list[str]:
    s = re.sub(r"[^א-ת ]", "", s.replace("משנה תורה, ", "").replace("הלכות ", ""))
    words = []
    for w in s.split():
        w = re.sub(r"[יו]", "", w)
        w = re.sub(r"[הא]$", "", w)
        if w:
            words.append(w)
    return words


_books = None


def rambam_book(he: str) -> str | None:
    """Sefaria's 'Mishneh Torah, X' for a Hebrew book name as the notes write it, or None if unsure."""
    global _books
    if _books is None:
        _books = {k: _sk(v) for k, v in json.loads(BOOKS_FILE.read_text()).items()}
    he = re.sub(r'\s+ו?ה"\S+.*$', "", (he or "").strip())
    if he in BOOK_ALIASES:
        return "Mishneh Torah, " + BOOK_ALIASES[he]
    words = _sk(he)
    if not words:
        return None
    hits = []
    for title, tw in _books.items():
        used, exact = set(), 0
        for w in words:
            i = next((i for i, t in enumerate(tw) if i not in used and t == w), None)
            if i is None:
                i = next((i for i, t in enumerate(tw) if i not in used and (t.startswith(w) or w.startswith(t))), None)
            else:
                exact += 1
            if i is None:
                break
            used.add(i)
        else:
            # rank: more whole-word matches, the name starting the title, a shorter title
            hits.append(((-exact, 0 if 0 in used else 1, len(tw)), title))
    hits.sort()
    if not hits or (len(hits) > 1 and hits[0][0] == hits[1][0]):
        return None
    return hits[0][1]


if __name__ == "__main__":
    {"fetch": fetch, "build": build}[sys.argv[1]]()
