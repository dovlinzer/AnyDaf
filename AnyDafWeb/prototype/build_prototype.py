#!/usr/bin/env python3
"""Build the AnyDafWeb prototype: a page with a daf picker, one data file per daf, and page images.

Left: the shared renderer (../renderer/). Right: the daf page image, the Gemara, or the written
shiur, scrolling in step with the outline through its `text` anchors (by amud only for outlines
generated before the anchors existed). Glossary and sages (daf-processor/build_sages.py) as pop-out panels.

    ../../daf-processor/venv/bin/python build_prototype.py --out DIR [--source local|supabase]

--source supabase reads everything back from Supabase (daf_study_aids, daf_text, shiur_content),
as the real web app will; local reads daf-processor's files. Output: DIR/index.html,
DIR/data/<key>.json, DIR/img/<key>_<amud>.jpg (Vilna pages from AnyTorah's image set, resized).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
DP = HERE.parent.parent / "daf-processor"
sys.path.insert(0, str(DP))
from build_outline_review import clean_svg, uniquify_ids  # noqa: E402
from upload_to_supabase import parse_dir_name  # noqa: E402
from build_outline_review import title_of  # noqa: E402
from build_sages import panel as sages_panel  # noqa: E402

load_dotenv(DP / ".env", override=True)

EDGE = 4
HEB_NUM = {1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה", 6: "ו", 7: "ז", 8: "ח", 9: "ט", 10: "י", 20: "כ", 30: "ל",
           40: "מ", 50: "נ", 60: "ס", 70: "ע", 80: "פ", 90: "צ", 100: "ק"}
TRACTATE_HE = {"Chagigah": "חגיגה", "Gittin": "גיטין", "Shabbat": "שבת", "Berakhot": "ברכות",
               "Bava Metzia": "בבא מציעא", "Bava Batra": "בבא בתרא", "Niddah": "נדה", "Kiddushin": "קידושין",
               "Sanhedrin": "סנהדרין", "Yevamot": "יבמות", "Hullin": "חולין"}
DAFIM = ["chagigah_6", "gittin_18", "shabbat_38", "berakhot_31b", "bava_metzia_11", "bava_batra_84",
         "niddah_60", "kiddushin_2", "sanhedrin_6b", "yevamot_33", "hullin_88", "shabbat_21"]
PAGES_JSON = HERE.parent.parent.parent / "AnyTorah" / "AnyTorahWeb" / "public" / "pages.json"
IMG_CACHE = DP / "outline" / ".page_cache"     # downloaded page images, reused across builds
EDITORIAL = ("judgment_calls", "coverage_notes", "runners_up")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zewdazoijdpakugfvnzt.supabase.co")


def heb_numeral(n: int) -> str:
    out = ""
    for v in sorted(HEB_NUM, reverse=True):
        while n >= v:
            if n in (15, 16):
                return out + ("טו" if n == 15 else "טז")
            out += HEB_NUM[v]
            n -= v
    return out


def amud_he(label: str) -> str:
    num, side = int(label[:-1]), label[-1]
    return heb_numeral(num) + ("." if side == "a" else ":")


def norm_he(s: str) -> str:
    return re.sub(r"[^\u05D0-\u05EA]", "", re.sub(r"[\u0591-\u05C7]", "", s))


def parse_shiur(text: str | None, order: dict, heb_to_label: dict) -> list[dict]:
    """03_final.md -> display blocks. Each quoted Hebrew/Translation pair is verbatim Sefaria text
    (v10 assembly), so it maps to its label by exact match; the pane syncs on those labels."""
    if not text:
        return []
    blocks, para, quote = [], [], None

    def flush():
        nonlocal para, quote
        if para:
            blocks.append({"t": "p", "x": " ".join(para)})
            para = []
        if quote:
            blocks.append({"t": "q", "pairs": quote})
            quote = None

    for line in text.splitlines():
        st = line.strip()
        m = re.match(r"^\[DAF:(\w+)\]$", st)
        if m:
            flush(); blocks.append({"t": "amud", "x": m.group(1)}); continue
        if st.startswith(">"):
            if para:
                blocks.append({"t": "p", "x": " ".join(para)}); para = []
            quote = quote or []
            body = st.lstrip("> ").strip()
            if body.startswith("**Hebrew/Aramaic:**"):
                he = body[len("**Hebrew/Aramaic:**"):].strip()
                lab = heb_to_label.get(norm_he(he))
                quote.append({"he": he, "en": "", "l": lab, "o": order.get(lab)})
            elif body.startswith("**Translation:**") and quote:
                quote[-1]["en"] = body[len("**Translation:**"):].strip()
            continue
        if not st:
            flush(); continue
        if st.startswith("### "):
            flush(); blocks.append({"t": "h3", "x": st[4:]}); continue
        if st.startswith("## "):
            flush(); blocks.append({"t": "h2", "x": st[3:]}); continue
        if st.startswith("# "):
            flush(); continue
        if st == "---":
            flush(); blocks.append({"t": "hr"}); continue
        if quote:
            flush()
        para.append(st)
    flush()
    return blocks


def clean(nodes):
    for n in nodes or []:
        if isinstance(n.get("illustration"), dict):
            n["illustration"]["svg"] = uniquify_ids(clean_svg(n["illustration"]["svg"]))
        clean(n.get("children"))


def amud_seq(tr_amudim: list[str]) -> list[str]:
    return sorted(tr_amudim, key=lambda a: (int(a[:-1]), a[-1]))


def neighbor(amud: str, step: int) -> str:
    n, side = int(amud[:-1]), amud[-1]
    idx = n * 2 + (side == "b") + step
    return f"{idx // 2}{'ab'[idx % 2]}"


def outline_amudim(outline: dict) -> list[str]:
    """Amudim the outline covers, from its sections' amud fields ("37b–38a", "38b → 39a")."""
    found = set()

    def walk(ns):
        for n in ns or []:
            found.update(re.findall(r"\d+[ab]", str(n.get("amud", "")).split("→")[0]))
            walk(n.get("children"))

    walk(outline.get("sections"))
    seq = amud_seq(list(found))
    if not seq:
        return []
    out, a = [], seq[0]
    while True:                      # fill any gap so the text runs continuously
        out.append(a)
        if a == seq[-1]:
            return out
        a = neighbor(a, 1)


class Local:
    def __init__(self):
        self.books = {}

    def aids(self, key, tractate, daf, tag="opus55"):
        if key == "chagigah_6":
            o = json.loads((DP / "outline" / "example_chagigah_6.json").read_text(encoding="utf-8"))
            t = json.loads((DP / "outline" / "key_terms_example_chagigah_6.json").read_text(encoding="utf-8"))
            return o, t["key_terms"]
        r = DP / "outline" / "results" / key
        o = json.loads((r / f"04_outline_{tag}.json").read_text(encoding="utf-8"))
        if o.get("key_terms"):                       # newer outlines carry their key terms inside
            return o, o["key_terms"]
        tp = r / "05_key_terms_opus55.json"
        return o, (json.loads(tp.read_text(encoding="utf-8"))["key_terms"] if tp.exists() else [])

    def text(self, tractate, amudim):
        if tractate not in self.books:
            self.books[tractate] = json.loads((DP / "daf_text" / f"{tractate}.json").read_text(encoding="utf-8"))
        am = self.books[tractate]["amudim"]
        return {a: am[a]["segments"] for a in amudim if a in am}

    def shiur(self, key, tractate, daf):
        p = DP / "output" / key / "03_final.md"
        return p.read_text(encoding="utf-8") if p.exists() else None


class Supa:
    def __init__(self):
        k = os.environ.get("SUPABASE_SERVICE_KEY") or sys.exit("SUPABASE_SERVICE_KEY not set")
        self.h = {"apikey": k, "Authorization": f"Bearer {k}"}

    def get(self, table, **q):
        params = {f: f"eq.{v}" for f, v in q.items() if f != "select"}
        params["select"] = q.get("select", "*")
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=self.h, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    def aids(self, key, tractate, daf):
        rows = self.get("daf_study_aids", tractate=tractate, daf=daf, select="outline,key_terms")
        if not rows:
            sys.exit(f"{key}: no daf_study_aids row for {tractate} {daf}")
        return rows[0]["outline"], rows[0]["key_terms"] or []

    def text(self, tractate, amudim):
        r = requests.get(f"{SUPABASE_URL}/rest/v1/daf_text", headers=self.h, timeout=60,
                         params={"tractate": f"eq.{tractate}", "amud": f"in.({','.join(amudim)})",
                                 "select": "amud,segments"})
        r.raise_for_status()
        return {x["amud"]: x["segments"] for x in r.json()}

    def shiur(self, key, tractate, daf):
        rows = self.get("shiur_content", tractate=tractate, daf=daf, select="final")
        return rows[0]["final"] if rows else None


def page_image(tractate: str, amud: str, pages: dict, key: str, out: Path) -> str | None:
    """key names the image file; two versions of one daf pass the same key and share it."""
    n, side = int(amud[:-1]), amud[-1]
    fid = pages.get(tractate, {}).get(str((n - 1) * 2 + (side == "b")))
    if not fid:
        return None
    IMG_CACHE.mkdir(parents=True, exist_ok=True)
    raw = IMG_CACHE / f"{fid}.jpg"
    if not raw.exists():
        r = requests.get(f"https://drive.google.com/thumbnail?id={fid}&sz=w1600", timeout=60)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            print(f"    no image for {tractate} {amud} (HTTP {r.status_code})")
            return None
        raw.write_bytes(r.content)
    name = f"{key}_{amud}.jpg"
    dst = out / "img" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 1300px wide at JPEG quality 45: readable when zoomed, about half the original size.
    subprocess.run(["sips", "--resampleWidth", "1300", "-s", "formatOptions", "45",
                    str(raw), "--out", str(dst)], check=True, capture_output=True)
    return f"img/{name}"


TRACTATE_GROUP = {}   # optional menu group per daf key; defaults to the tractate


def parse_spec(spec):
    """'kiddushin_3' -> the default outline; 'kiddushin_3@opus55_medium=M' -> that result tag,
    shown as 'Kiddushin 3 (M)' with its own data file (kiddushin_3_M)."""
    base, _, rest = spec.partition("@")
    tag, _, mark = rest.partition("=")
    return base, (tag or None), (mark or None)


def build_daf(spec, src, pages, out):
    key, tag, mark = parse_spec(spec)
    tractate, daf = parse_dir_name(key)
    outline, terms = src.aids(key, tractate, daf, tag) if tag else src.aids(key, tractate, daf)
    outline = {k: v for k, v in outline.items() if k not in EDITORIAL and k != "key_terms"}
    clean(outline.get("sections"))

    span = outline_amudim(outline)
    before, after = neighbor(span[0], -1), neighbor(span[-1], 1)
    text = src.text(tractate, [before] + span + [after])
    pool = [(f"{a}.{s['n']}", s["he"], s["en"]) for a in [before] + span + [after] for s in text.get(a, [])]
    order = {l: i for i, (l, _, _) in enumerate(pool)}

    first = next((s["text"]["from"] for s in outline["sections"] if s.get("text")), None)
    items = []
    for a in span:
        for s in text.get(a, []):
            lab = f"{a}.{s['n']}"
            ctx = "Before this daf's outline" if first and order.get(lab, 1e9) < order.get(first, -1) else None
            items.append({"l": lab, "he": s["he"], "en": s["en"], **({"ctx": ctx} if ctx else {})})
    # A few lines before and after, for context.
    if first and first.split(".")[0] == before:
        items = [{"l": f"{before}.{s['n']}", "he": s["he"], "en": s["en"]} for s in text.get(before, [])
                 if order[f"{before}.{s['n']}"] >= order[first]] + items
    items += [{"l": f"{after}.{s['n']}", "he": s["he"], "en": s["en"], "ctx": "Continues on the next daf"}
              for s in text.get(after, [])[:EDGE]]
    items = [it for it in items if not (it.get("ctx") == "Before this daf's outline" and
             order[it["l"]] < order[first] - 3)]

    heb_to_label = {}
    for l, h, _ in pool:
        heb_to_label.setdefault(norm_he(h), l)
    shiur = parse_shiur(src.shiur(key, tractate, daf), order, heb_to_label)
    quotes = [q for b in shiur if b["t"] == "q" for q in b["pairs"]]

    shown = amud_seq({it["l"].split(".")[0] for it in items})
    images = {a: im for a in shown if (im := page_image(tractate, a, pages, key, out))}
    dkey = f"{key}_{mark}" if mark else key
    title = title_of(key).replace(" (no shiur)", "") + (f" ({mark})" if mark else "")
    data = {"key": dkey, "title": title, "version": mark, "base": key, "tractate": tractate,
            "tractateHe": TRACTATE_HE.get(tractate, tractate),
            "amudim": shown, "amudHe": {a: amud_he(a) for a in shown}, "images": images,
            "outline": outline, "keyTerms": terms, "items": items, "order": order, "shiur": shiur,
            # Sages: the outline's own list when it has one, else the name-matching pilot's guesses;
            # read from daf-processor's local files in both --source modes for now.
            "sages": sages_panel(key, outline) or []}
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "data" / f"{dkey}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    anchored = sum(1 for s in outline["sections"] if s.get("text"))
    print(f"  {dkey:18s} amudim {'/'.join(shown)}; {len(items)} lines; {len(terms)} terms; "
          f"shiur quotes {sum(q['l'] is not None for q in quotes)}/{len(quotes)}; "
          f"images {len(images)}; {len(data['sages'])} sages; {'anchored' if anchored else 'amud-level sync'}")
    return {"key": dkey, "title": title, "group": TRACTATE_GROUP.get(key) or tractate if mark else "Test dafim"}


def anon_key() -> str:
    """The public anon key the apps ship with (AnyDaf/Secrets.swift, gitignored). Public by design;
    row-level security limits it to adding feedback. Never the service key."""
    src = (HERE.parent.parent / "AnyDaf" / "Secrets.swift").read_text(encoding="utf-8")
    m = re.search(r'supabaseAnonKey\s*=\s*"([^"]+)"', src)
    if not m:
        sys.exit("supabaseAnonKey not found in AnyDaf/Secrets.swift")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", default=DAFIM)
    ap.add_argument("--source", choices=["local", "supabase"], default="local")
    ap.add_argument("--out", required=True)
    ap.add_argument("--feedback", action="store_true",
                    help="hosted build: Flag notes go to Supabase outline_feedback (public anon key, insert only); "
                         "also marks the site noindex and writes vercel.json")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    src = Supa() if args.source == "supabase" else Local()
    pages = json.loads(PAGES_JSON.read_text(encoding="utf-8"))
    index = [build_daf(k, src, pages, out) for k in args.dafim]

    r = HERE.parent / "renderer"
    html = (HERE / "app.html").read_text(encoding="utf-8")
    html = (html.replace("__TITLE__", "AnyDaf Study Outlines")
                .replace("__RENDERER_CSS__", (r / "outline-renderer.css").read_text(encoding="utf-8"))
                .replace("__RENDERER_JS__", (r / "outline-renderer.js").read_text(encoding="utf-8"))
                .replace("__SPRITE__", (DP / "outline" / "sprite.svg").read_text(encoding="utf-8"))
                .replace("__DAFIM__", json.dumps(index, ensure_ascii=False))
                .replace("__FEEDBACK__", json.dumps({"url": SUPABASE_URL, "key": anon_key()}) if args.feedback else "null"))
    if args.feedback:
        html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex, nofollow">', 1)
        (out / "vercel.json").write_text(json.dumps({
            "headers": [{"source": "/(.*)", "headers": [{"key": "X-Robots-Tag", "value": "noindex, nofollow"}]}],
            "cleanUrls": True}, indent=1))
    (out / "index.html").write_text(html, encoding="utf-8")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"wrote {out}/index.html + {len(index)} dafim ({size / 1e6:.1f} MB total)")


if __name__ == "__main__":
    main()
