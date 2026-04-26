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
    'megillah': 'Megillah', 'megila': 'Megillah', 'megilah': 'Megillah',
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


# Shekalim is a Yerushalmi tractate. Sefaria doesn't index it as "Shekalim.Xa";
# instead each daf/amud maps to a Jerusalem Talmud chapter:halacha:segment range.
# These refs match the AnyDaf iOS/Android SefariaClient maps exactly.
SHEKALIM_REFS: dict = {
    "2a":  "Jerusalem Talmud Shekalim 1:1:1-5",
    "2b":  "Jerusalem Talmud Shekalim 1:1:5-10",
    "3a":  "Jerusalem Talmud Shekalim 1:1:10-2:5",
    "3b":  "Jerusalem Talmud Shekalim 1:2:5-4:1",
    "4a":  "Jerusalem Talmud Shekalim 1:4:1-5",
    "4b":  "Jerusalem Talmud Shekalim 1:4:5-9",
    "5a":  "Jerusalem Talmud Shekalim 1:4:9-2:1:4",
    "5b":  "Jerusalem Talmud Shekalim 2:1:4-3:1",
    "6a":  "Jerusalem Talmud Shekalim 2:3:1-4:1",
    "6b":  "Jerusalem Talmud Shekalim 2:4:1-5",
    "7a":  "Jerusalem Talmud Shekalim 2:4:5-5:4",
    "7b":  "Jerusalem Talmud Shekalim 2:5:4-3:1:3",
    "8a":  "Jerusalem Talmud Shekalim 3:1:3-2:2",
    "8b":  "Jerusalem Talmud Shekalim 3:2:2-8",
    "9a":  "Jerusalem Talmud Shekalim 3:2:8-3:1",
    "9b":  "Jerusalem Talmud Shekalim 3:3:1-4:1:1",
    "10a": "Jerusalem Talmud Shekalim 4:1:1-2:1",
    "10b": "Jerusalem Talmud Shekalim 4:2:1-4",
    "11a": "Jerusalem Talmud Shekalim 4:2:4-3:2",
    "11b": "Jerusalem Talmud Shekalim 4:3:2-4:1",
    "12a": "Jerusalem Talmud Shekalim 4:4:1-5",
    "12b": "Jerusalem Talmud Shekalim 4:4:5-9",
    "13a": "Jerusalem Talmud Shekalim 4:4:9-5:1:3",
    "13b": "Jerusalem Talmud Shekalim 5:1:3-12",
    "14a": "Jerusalem Talmud Shekalim 5:1:12-21",
    "14b": "Jerusalem Talmud Shekalim 5:1:21-3:2",
    "15a": "Jerusalem Talmud Shekalim 5:3:2-4:10",
    "15b": "Jerusalem Talmud Shekalim 5:4:10-6:1:5",
    "16a": "Jerusalem Talmud Shekalim 6:1:5-11",
    "16b": "Jerusalem Talmud Shekalim 6:1:11-2:1",
    "17a": "Jerusalem Talmud Shekalim 6:2:1-7",
    "17b": "Jerusalem Talmud Shekalim 6:2:7-3:3",
    "18a": "Jerusalem Talmud Shekalim 6:3:3-4:2",
    "18b": "Jerusalem Talmud Shekalim 6:4:2-7",
    "19a": "Jerusalem Talmud Shekalim 6:4:7-7:2:1",
    "19b": "Jerusalem Talmud Shekalim 7:2:1-7",
    "20a": "Jerusalem Talmud Shekalim 7:2:7-3:2",
    "20b": "Jerusalem Talmud Shekalim 7:3:2-7",
    "21a": "Jerusalem Talmud Shekalim 7:3:7-8:1:1",
    "21b": "Jerusalem Talmud Shekalim 8:1:1-3:1",
    "22a": "Jerusalem Talmud Shekalim 8:3:1-4:4",
    "22b": "Jerusalem Talmud Shekalim 8:4:4",
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
    # Try with underscores removed first — handles names split by underscore (e.g. 'Ta_anit').
    # _normalise inside _try_parse strips non-alpha chars, so 'ta_anit17' → 'taanit17'.
    result = _try_parse(s.replace('_', ''))
    if result:
        return result
    # Fall back to first underscore segment — drops suffixes like '_hybrid', '_v2'.
    return _try_parse(s.split('_')[0])


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
    display_ref = f"{masechta} {daf}{amud}"

    if masechta == 'Shekalim':
        sefaria_ref = SHEKALIM_REFS.get(f"{daf}{amud}")
        if not sefaria_ref:
            return None
        ref_for_url = requests.utils.quote(sefaria_ref, safe='')
    else:
        sefaria_ref = display_ref
        # Sefaria API ref format: tractate name (spaces → underscores) + dot + daf+amud
        # e.g. "Avodah Zarah 10a" → "Avodah_Zarah.10a"
        ref_for_url = f"{masechta.replace(' ', '_')}.{daf}{amud}"

    url = f"https://www.sefaria.org/api/texts/{ref_for_url}?lang=bi&commentary=0&context=0"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Sefaria request failed for {display_ref}: {e}")
        return None

    data = resp.json()
    if 'error' in data:
        logger.warning(f"Sefaria error for {display_ref}: {data['error']}")
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
    parts = [f"### {display_ref}\n"]
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
