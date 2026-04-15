import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Maps any recognisable spelling/transliteration → canonical Sefaria tractate name.
# Keys are lowercase, spaces and punctuation removed.
MASECHTA_MAP = {
    # Seder Zeraim
    'berakhot': 'Berakhot', 'berachot': 'Berakhot', 'brachos': 'Berakhot', 'brachot': 'Berakhot',
    # Seder Moed
    'shabbat': 'Shabbat', 'shabbos': 'Shabbat', 'shabat': 'Shabbat',
    'eruvin': 'Eruvin', 'eiruvin': 'Eruvin',
    'pesachim': 'Pesachim', 'pesahim': 'Pesachim',
    'shekalim': 'Shekalim',
    'yoma': 'Yoma',
    'sukkah': 'Sukkah', 'sukka': 'Sukkah',
    'beitzah': 'Beitzah', 'beitza': 'Beitzah', 'beisa': 'Beitzah',
    'roshhashana': 'Rosh Hashanah', 'roshhashanah': 'Rosh Hashanah',
    'taanit': 'Taanit', 'taanis': 'Taanit', 'tanit': 'Taanit',
    'megillah': 'Megillah', 'megila': 'Megillah',
    'moadkatan': 'Moed Katan', 'moedkatan': 'Moed Katan', 'mkatan': 'Moed Katan',
    'chagigah': 'Chagigah', 'hagigah': 'Chagigah',
    # Seder Nashim
    'yevamot': 'Yevamot', 'yevamos': 'Yevamot', 'yavamos': 'Yevamot',
    'ketubot': 'Ketubot', 'ketuvot': 'Ketubot', 'kesuvos': 'Ketubot',
    'nedarim': 'Nedarim',
    'nazir': 'Nazir',
    'sotah': 'Sotah', 'sota': 'Sotah',
    'gittin': 'Gittin', 'gitin': 'Gittin',
    'kiddushin': 'Kiddushin', 'kidushin': 'Kiddushin', 'kidushim': 'Kiddushin',
    # Seder Nezikin
    'babakamma': 'Bava Kamma', 'bavakamma': 'Bava Kamma',
    'bavakama': 'Bava Kamma', 'babakama': 'Bava Kamma',
    'babametzia': 'Bava Metzia', 'bavametzia': 'Bava Metzia',
    'bavametsia': 'Bava Metzia', 'babametsia': 'Bava Metzia',
    'bababatra': 'Bava Batra', 'bavabatra': 'Bava Batra',
    'sanhedrin': 'Sanhedrin',
    'makkot': 'Makkot', 'makot': 'Makkot', 'makkos': 'Makkot',
    'shevuot': 'Shevuot', 'shevuos': 'Shevuot', 'shvuot': 'Shevuot',
    'avodahzarah': 'Avodah Zarah', 'avodazara': 'Avodah Zarah',
    'horayot': 'Horayot', 'horayos': 'Horayot',
    # Seder Kodashim
    'zevachim': 'Zevachim', 'zvachim': 'Zevachim', 'zevahim': 'Zevachim',
    'menachot': 'Menachot', 'menachos': 'Menachot', 'menahot': 'Menachot',
    'chullin': 'Hullin', 'hulin': 'Hullin', 'hullin': 'Hullin',
    'bekhorot': 'Bekhorot', 'bechorot': 'Bekhorot', 'bechoros': 'Bekhorot',
    'arakhin': 'Arakhin', 'erchin': 'Arakhin', 'erechin': 'Arakhin',
    'temurah': 'Temurah', 'temura': 'Temurah',
    'keritot': 'Keritot', 'kritot': 'Keritot', 'kerisos': 'Keritot',
    'meilah': 'Meilah', 'meila': 'Meilah',
    'tamid': 'Tamid',
    'middot': 'Middot', 'midot': 'Middot',
    'kinnim': 'Kinnim',
    # Seder Taharot
    'niddah': 'Niddah', 'nida': 'Niddah',
}


def _normalise(s: str) -> str:
    """Lowercase and strip spaces/punctuation for MASECHTA_MAP lookup."""
    return re.sub(r'[^a-z]', '', s.lower())


def _lookup(raw_name: str) -> Optional[str]:
    """Return canonical Sefaria masechta name or None."""
    return MASECHTA_MAP.get(_normalise(raw_name))


def _try_parse(s: str) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Try to extract (masechta, daf, amud) from a normalised string.
    amud is 'a', 'b', or None (whole daf).
    Handles both concatenated ('menachot79', 'berakhot11b') and
    space-separated ('menachot 79', 'berakhot 11b') forms.
    """
    # Space-separated form: "menachot 79" or "berakhot 11b"
    m = re.search(r'([a-z]+(?:\s+[a-z]+)?)\s+(\d+)([ab])?(?:\b|$)', s, re.IGNORECASE)
    if m:
        masechta = _lookup(m.group(1))
        if masechta:
            amud = m.group(3).lower() if m.group(3) else None
            return masechta, int(m.group(2)), amud

    # Concatenated form: "menachot79" or "berakhot11b"
    m = re.match(r'([a-zA-Z]+?)(\d+)([ab])?$', s.strip(), re.IGNORECASE)
    if m:
        masechta = _lookup(m.group(1))
        if masechta:
            amud = m.group(3).lower() if m.group(3) else None
            return masechta, int(m.group(2)), amud

    return None


def parse_filename(stem: str) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Extract (masechta, daf, amud) from a filename stem like 'rdldafyomimenachot79'
    or 'rdldafyomibrakhot11b'.  amud is 'a', 'b', or None (whole daf).
    Strips known prefixes and any underscore-delimited suffixes (e.g. '_hybrid', '_v2').
    Returns None if parsing fails.
    """
    s = stem.lower()
    for prefix in ('rdldafyomi', 'dafyomi', 'rdl'):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    # Strip trailing underscore suffixes — keep only the part before the first '_'
    s = s.split('_')[0]
    return _try_parse(s)


def parse_srt_header(srt_path: Path, n_entries: int = 8) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Scan the first n_entries of an SRT file for a spoken daf identification,
    e.g. "today's daf is Menachos 80" or "we are on Bava Kamma 15".
    Returns (masechta, daf, amud) or None.  amud is 'a', 'b', or None.
    """
    try:
        text = srt_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None

    # Grab just the first ~30 lines to keep it fast
    lines = text.split('\n')[:30]
    combined = ' '.join(lines)

    # Look for tractate name followed by a number and optional amud letter
    for m in re.finditer(r'([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(\d+)([ab])?(?:\b|$)', combined):
        masechta = _lookup(m.group(1))
        if masechta:
            daf = int(m.group(2))
            amud = m.group(3).lower() if m.group(3) else None
            logger.info(f"  Identified from SRT header: {masechta} {daf}{amud or ''}")
            return masechta, daf, amud
    return None


def identify_daf(srt_path: Path) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Try to identify (masechta, daf, amud) for an SRT file.
    amud is 'a', 'b', or None (whole daf).
    Priority: filename → SRT opening lines.
    Returns None if both fail.
    """
    result = parse_filename(srt_path.stem)
    if result:
        return result
    result = parse_srt_header(srt_path)
    if result:
        return result
    return None


def _flatten(obj) -> str:
    """Recursively flatten nested lists of strings to a single string."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return ' '.join(_flatten(item) for item in obj if item)
    return ''


def _html_to_md(text: str) -> str:
    """Convert Sefaria HTML markup to Markdown, preserving bold distinction."""
    # <b>word</b> → **word**  (Steinsaltz: bold = actual Talmudic text)
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    # <i>...</i> → *...*
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
    # <br> variants → space
    text = re.sub(r'<br\s*/?>', ' ', text)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _fetch_amud(masechta: str, daf: int, amud: str) -> Optional[str]:
    """Fetch one amud from Sefaria and return formatted markdown, or None on failure."""
    ref = f"{masechta} {daf}{amud}"
    url = f"https://www.sefaria.org/api/texts/{ref.replace(' ', '.')}?lang=bi&commentary=0&context=0"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Sefaria request failed for {ref}: {e}")
        return None

    data = resp.json()
    if 'error' in data:
        logger.warning(f"Sefaria error for {ref}: {data['error']}")
        return None

    he_segments = data.get('he', [])
    en_segments = data.get('text', [])

    # Normalise to flat lists
    if isinstance(he_segments, str):
        he_segments = [he_segments]
    if isinstance(en_segments, str):
        en_segments = [en_segments]

    # Zip segments together
    length = max(len(he_segments), len(en_segments))
    parts = [f"### {ref}\n"]
    for i in range(length):
        he = _html_to_md(_flatten(he_segments[i])) if i < len(he_segments) else ''
        en = _html_to_md(_flatten(en_segments[i])) if i < len(en_segments) else ''
        if he or en:
            parts.append(f"**{i + 1}.**\n*Hebrew/Aramaic:* {he}\n*Translation:* {en}\n")

    return '\n'.join(parts)


def fetch_daf_text(masechta: str, daf: int) -> str:
    """
    Fetch both amudim of a daf from Sefaria.
    Returns formatted markdown with Hebrew and English (bold preserved).
    """
    sections = []
    for amud in ('a', 'b'):
        text = _fetch_amud(masechta, daf, amud)
        if text:
            sections.append(text)

    if not sections:
        logger.warning(f"No Sefaria text retrieved for {masechta} {daf}")
        return f"[Sefaria text not available for {masechta} {daf}]"

    return '\n\n---\n\n'.join(sections)


def fetch_daf_tail(masechta: str, daf: int) -> Optional[str]:
    """
    Fetch only the b-side (second amud) of a daf — useful for getting the
    tail of the preceding daf when a shiur may have started slightly before
    the current daf.  Returns formatted markdown or None on failure.
    """
    return _fetch_amud(masechta, daf, 'b')


def fetch_daf_head(masechta: str, daf: int) -> Optional[str]:
    """
    Fetch only the a-side (first amud) of a daf — useful for getting the
    head of the following daf when a shiur may run slightly past the current
    daf.  Returns formatted markdown or None on failure.
    """
    return _fetch_amud(masechta, daf, 'a')
