"""Page images (the apps' own Vilna scans) and the Sefaria texts that get aligned to them.

Images come from the same Google Drive files the apps show (pages.json), at full size (2617x3534
for the scans checked so far), so the coordinates written here match what a reader sees. Both are
cached under page_layout/cache/ (gitignored).

Texts, per the POC: Gemara = "Wikisource Talmud Bavli" (no nikud or punctuation, follows the
Vilna print), Rashi and Tosafot = "Vilna Edition". Sefaria keeps every version on the same segment
numbering, so Gemara segment N here is the same line label (e.g. 3a.4) the outlines and shiurim
use, and each Rashi/Tosafot comment is filed under the Gemara segment it comments on.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
PAGES_JSON = HERE.parent.parent.parent / "AnyTorah" / "AnyTorahWeb" / "public" / "pages.json"

GEMARA_VERSION = "Wikisource Talmud Bavli"
COMMENTARY_VERSION = "Vilna Edition"

_pages = None


def page_number(daf: int, amud: str) -> int:
    """The apps' page numbering (TalmudPageManager): 2a -> 2, 2b -> 3, 3a -> 4 ..."""
    return (daf - 1) * 2 + (0 if amud == "a" else 1)


def drive_id(tractate: str, daf: int, amud: str) -> str | None:
    global _pages
    if _pages is None:
        _pages = json.loads(PAGES_JSON.read_text())
    return _pages.get(tractate, {}).get(str(page_number(daf, amud)))


def page_image(tractate: str, daf: int, amud: str) -> Path | None:
    fid = drive_id(tractate, daf, amud)
    if not fid:
        return None
    p = CACHE / "img" / tractate / f"{daf}{amud}.jpg"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://drive.google.com/thumbnail?id={fid}&sz=w4000"
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(url, timeout=90).read()
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        p.write_bytes(data)
    return p


def _sefaria(ref: str, version: str) -> list:
    """The version's text for one amud: a list of segments (commentaries: a list of comments per segment)."""
    p = CACHE / "text" / f"{ref}__{version.replace(' ', '_')}.json"
    if p.exists():
        return json.loads(p.read_text())
    url = (f"https://www.sefaria.org/api/v3/texts/{urllib.parse.quote(ref)}"
           f"?version=hebrew|{urllib.parse.quote(version)}")
    for attempt in range(4):
        try:
            d = json.load(urllib.request.urlopen(url, timeout=60))
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    vs = d.get("versions") or []
    text = vs[0]["text"] if vs else []
    if isinstance(text, str):
        text = [text]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(text, ensure_ascii=False))
    return text


TAG = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    s = TAG.sub("", s).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def sefaria_ref(tractate: str, daf: int, amud: str) -> str:
    return f"{tractate.replace(' ', '_')}.{daf}{amud}"


def gemara(tractate: str, daf: int, amud: str) -> list[str]:
    """Gemara segments for the amud, in order; index i is line label f'{daf}{amud}.{i+1}'."""
    return [clean(s) for s in _sefaria(sefaria_ref(tractate, daf, amud), GEMARA_VERSION)]


def inner_commentator(name: str, tractate: str, daf: int) -> str:
    """The commentary printed in the inner column: Rashi, except where the Vilna prints another
    in its place (Rashbam on Bava Batra from 29a, where Rashi's own commentary breaks off)."""
    if name == "Rashi" and tractate == "Bava Batra" and daf >= 29:
        return "Rashbam"
    return name


def commentary(name: str, tractate: str, daf: int, amud: str) -> list[tuple[str, str]]:
    """[(ref, text)] for Rashi (or the commentary printed in its place) or Tosafot on the amud,
    in Sefaria's order ('Rashi on Yevamot 3a:4:2')."""
    name = inner_commentator(name, tractate, daf)
    t = _sefaria(f"{name}_on_{sefaria_ref(tractate, daf, amud)}", COMMENTARY_VERSION)
    out = []
    for si, seg in enumerate(t, 1):
        for ci, c in enumerate(seg if isinstance(seg, list) else [seg], 1):
            if c and clean(c):
                out.append((f"{name} on {tractate} {daf}{amud}:{si}:{ci}", clean(c)))
    return out


def previous_amud(daf: int, amud: str) -> tuple[int, str]:
    return (daf, "a") if amud == "b" else (daf - 1, "b")
