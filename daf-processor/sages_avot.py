"""Pirkei Avot 1-4: a selection of each tanna's own sayings (and R. Yochanan ben Zakkai's praise of his five students, Avot 2:8-9)
for the sages kit. Output: outline/sages/avot.json = {slug: [{ref, kind, he, en}]}, read by sages_kit.py.

Sources (facts only from Sefaria): Hebrew = Sefaria's 'Torat Emet 357' (Public Domain); English = Joseph I. Gorfinkle, 'Pirke Avot: The Sayings of the Jewish
Fathers' (New York 1913; Project Gutenberg #8548, public domain in the US), which is based on Taylor's 1897 translation in modern phrasing. Every
quotation is cut verbatim; the only edits are the removal of the _underscore_ italics, doubled spaces, two typos in the Gutenberg text ('night' for 'nigh', a missing 'is'), and a closing quotation mark added where a cut ends inside a quotation.
(Sefaria's own versions were not used: Kulp is excluded by the project's rule, the CC0 community translation lacks chapter 2, Taylor reads stiffly.)
Selection and which clause is quoted are editorial (the author approves). Sayings whose sage is not named uniquely in the mishnah are left out
(Avot 3:3 'R. Shimon', 3:7 'R. Yaakov', 4:6 'R. Yose', 4:7-8 'R. Yishmael', 4:9 'R. Yochanan', 4:11 'R. Eliezer b. Yaakov', 4:13 'R. Yehudah / R. Shimon',
4:16-17 'R. Yaakov', 4:15 'R. Yannai': no unique kit entry).
Run: venv/bin/python sages_avot.py"""
import json, re, urllib.parse, urllib.request

VT_HE = "Torat Emet 357"
VT_EN = "Sayings of the Jewish Fathers (Pirqe Aboth) translated by Charles Taylor [1897]"

def fetch(c, key, vt):
    p = "vhe" if key == "he" else "ven"
    u = f"https://www.sefaria.org/api/texts/Pirkei_Avot.{c}?context=0&commentary=0&pad=0&{p}={urllib.parse.quote(vt)}"
    d = json.load(urllib.request.urlopen(u))
    return [re.sub(r"<[^>]+>", "", t) for t in d["he" if key == "he" else "text"]]

TEXT = {c: {"he": fetch(c, "he", VT_HE)} for c in (1, 2, 3, 4)}

def gorfinkle():
    t = urllib.request.urlopen("https://www.gutenberg.org/cache/epub/8548/pg8548.txt").read().decode("utf-8", "ignore").replace("\r\n", "\n")
    body = t[t.index("CHAPTER I\n"): t.index("CHAPTER V\n")]
    chs = re.split(r"\nCHAPTER (?:I|II|III|IV)\n", "\n" + body)[1:]
    G = {}
    for c, txt in enumerate(chs, 1):
        txt = re.sub(r"\s*\n\s*", " ", txt).strip()
        parts = re.split(r'(?:(?<=\s)|^)(\d{1,2})\. (?=[A-Z"(\u201c])', txt)
        G[c] = {int(parts[i]): parts[i + 1].strip().replace("_", "") for i in range(1, len(parts), 2)}
    return G
G = gorfinkle()
NIKUD = re.compile(r"[֑-ׇ]")

def cut_he(seg, start, end):
    plain, idx = [], []
    for i, ch in enumerate(seg):
        if not NIKUD.match(ch): plain.append(ch); idx.append(i)
    plain = "".join(plain)
    a = 0
    if start:
        a = plain.index(start)
    b = len(plain)
    if end:
        b = plain.index(end, a) + len(end)
    out = seg[idx[a]: (idx[b - 1] + 1 if b <= len(idx) else len(seg))]
    # trailing combining marks of the last letter
    j = idx[b - 1] + 1 if b <= len(idx) else len(seg)
    while j < len(seg) and NIKUD.match(seg[j]): j += 1
    out = seg[idx[a]:j].strip().rstrip(":").strip()
    return out

def cut_en(c, gps, es, ee):
    seg = " ".join(G[c][g] for g in gps)
    a = seg.index(es) if es else 0
    b = len(seg)
    if ee:
        b = seg.index(ee, a) + len(ee)
    t = seg[a:b].strip()
    if t.count('"') % 2:   # a cut that ends inside a quotation closes it; one that starts inside it opens it
        t = ('"' + t) if t.endswith('"') else t.rstrip(" ,;.") + '."'
    t = re.sub(r"\s{2,}", " ", t)
    return t.replace("them night to", "them nigh to").replace("there no understanding", "there is no understanding")   # two typos in the Gutenberg text

ITEMS = []
def add(slug, ref, kind="saying", hs=None, he=None, gp=None, es=None, ee=None):
    c, m = (int(x) for x in ref.split(":"))
    ITEMS.append((slug, c, m, kind, hs, he, gp if isinstance(gp, list) else [gp], es, ee))

# --- chapter 1   (gp = Gorfinkle's paragraph number; es/ee = start/end markers in his English)
add("shimon-hatzaddik", "1:2", gp=2)
add("antigonus-of-sokho", "1:3", gp=3)
add("yose-b-yoezer", "1:4", hs="יוסי בן יועזר איש צרדה אומר", gp=4, es="Jose, the son of Joezer, of Zeredah said")
add("yose-b-yochanan", "1:5", he="ואל תרבה שיחה עם האשה", gp=5, ee='with woman."')
add("yehoshua-b-perachya", "1:6", hs="יהושע בן פרחיה אומר", gp=6, es="Joshua, the son of Perachyah, said")
add("nittai-haarbeli", "1:7", gp=7)
add("yehudah-b-tabbai", "1:8", hs="יהודה בן טבאי אומר", gp=8, es="Judah, the son of Tabbi, said")
add("shimon-b-shetach", "1:9", gp=9)
add("shemaiah", "1:10", hs="שמעיה אומר", gp=10, es="Shemaiah said")
add("avtalyon", "1:11", gp=11)
add("hillel", "1:12", hs="הלל אומר", gp=12, es="Hillel said")
add("hillel", "1:14", gp=14)
add("shammai", "1:15", gp=15)
add("rabban-gamliel-hazaken-(i)", "1:16", gp=16)
add("rabban-shimon-b-gamliel", "1:17", gp=17)
add("rabban-shimon-b-gamliel-(ii)", "1:18", gp=18, ee="in your gates.'\"")
# --- chapter 2
add("rabi", "2:1", gp=1)
add("rabban-gamliel-b-rabbi-(iii)", "2:2", gp=2)
add("rabban-gamliel-b-rabbi-(iii)", "2:4", hs="עשה רצונו כרצונך", he="רצון אחרים מפני רצונך", gp=4)
add("hillel", "2:4", hs="הלל אומר, אל תפרש", gp=5)
add("hillel", "2:5", gp=6)
add("rabban-yochanan-b-zakkai", "2:8", hs="אם למדת תורה הרבה", he="כי לכך נוצרת", gp=9, es="He used to say", ee='wast thou created."')
# R. Yochanan ben Zakkai's praise of his five students (2:8) and their answers to 'which is the good way' (2:9)
for slug, hh, en_s, en_e in [
    ("rabbi-eliezer-b-hyrcanus", ("רבי אליעזר בן הורקנוס, בור סוד", "שאינו מאבד טפה"), "Eliezer, the son of Hyrcanus, is a cemented cistern", "loses not a drop"),
    ("rabbi-yehoshua-b-hananyah", ("רבי יהושע בן חנניה, אשרי יולדתו", "אשרי יולדתו"), "Joshua, the son of Hananiah, happy", "that bare him"),
    ("rabbi-yose-hakohen", ("רבי יוסי הכהן, חסיד", "חסיד"), "Jose, the Priest, is a pious man", "pious man"),
    ("shimon-b-netanel", ("רבי שמעון בן נתנאל, ירא חטא", "ירא חטא"), "Simeon, the son of Nataniel, is a fearer of sin", "fearer of sin"),
    ("rabbi-elazar-b-arakh", ("אלעזר בן ערך, מעין המתגבר", "מעין המתגבר"), "Eleazar, the son of Arach, is like a spring", "ever-sustained vigor"),
]:
    add(slug, "2:8", "praise", hh[0], hh[1], 11, en_s, en_e)
for slug, hs_, en_ in [
    ("rabbi-eliezer-b-hyrcanus", "רבי אליעזר אומר, עין טובה", 'R. Eliezer said, "A good eye"'),
    ("rabbi-yehoshua-b-hananyah", "רבי יהושע אומר, חבר טוב", 'R. Joshua said, "A good friend"'),
    ("rabbi-yose-hakohen", "רבי יוסי אומר, שכן טוב", 'R. Jose said, "A good neighbor"'),
    ("shimon-b-netanel", "רבי שמעון אומר, הרואה את הנולד", 'R. Simeon said, "One who foresees the fruit of an action"'),
    ("rabbi-elazar-b-arakh", "רבי אלעזר אומר, לב טוב", 'R. Eleazar said, "A good heart."'),
]:
    add(slug, "2:9", "answer", hs_, hs_.split("אומר, ")[1], 13, en_, en_)
add("rabbi-elazar-b-arakh", "2:9", "praise", "אמר להם, רואה אני את דברי אלעזר בן ערך מדבריכם", "שבכלל דבריו דבריכם",
    13, 'Thereupon he said to them, "I approve', 'yours are included."')
add("rabbi-eliezer-b-hyrcanus", "2:10", gp=15)
add("rabbi-yehoshua-b-hananyah", "2:11", gp=16)
add("rabbi-yose-hakohen", "2:12", gp=17)
add("shimon-b-netanel", "2:13", gp=18)
add("rabbi-elazar-b-arakh", "2:14", gp=19)
add("rabbi-tarfon", "2:15", gp=20)
add("rabbi-tarfon", "2:16", gp=21)
# --- chapter 3
add("akavyah-b-mahalalel", "3:1", gp=1)
add("rabbi-hanina-segan-hakohanim", "3:2", hs="רבי חנינא סגן הכהנים אומר", he="חיים בלעו", gp=2)
add("rabbi-hananyah-b-teradyon", "3:2", hs="רבי חנינא בן תרדיון אומר", he="שכינה שרויה ביניהם", gp=3, ee="Presence abides among them")
add("rabbi-hananyah-b-hakhinai", "3:4", gp=5)
add("rabbi-nehunya-b-hakanah", "3:5", gp=6)
add("rabbi-halafta-of-kefar-hanania", "3:6", he="שכינה שרויה ביניהם", gp=7, ee="Shechinah abides among them")
add("rabbi-elazar-b-yehudah-of-bartota", "3:7", he="ומידך נתנו לך", gp=8)
add("rabbi-chanina-b-dosa", "3:9", gp=[11, 12])
add("rabbi-chanina-b-dosa", "3:10", he="אין רוח המקום נוחה הימנו", gp=13)
add("rabbi-dosa-b-harkinas", "3:10", hs="רבי דוסא בן הרכינס אומר", gp=14)
add("rabbi-elazar-hamodai", "3:11", gp=15)
add("rabbi-yishmael-b-elisha", "3:12", gp=16)
add("rabbi-akiva", "3:13", gp=17)
add("rabbi-akiva", "3:15", gp=19)
add("rabbi-elazar-b-azaryah", "3:17", he="אם אין תורה, אין קמח", gp=21)
add("rabbi-elazar-hisma", "3:18", gp=23)
# --- chapter 4
add("shimon-b-zoma", "4:1", he="הכובש את יצרו", gp=1, ee="He who controls his passions")
add("shimon-b-azzai", "4:2", gp=2)
add("shimon-b-azzai", "4:3", gp=3)
add("rabbi-levitas-of-yavneh", "4:4", hs="רבי לויטס איש יבנה אומר", he="שתקות אנוש רמה", gp=4)
add("rabbi-yohanan-b-berokah", "4:4", hs="רבי יוחנן בן ברוקא אומר", gp=5)
add("rabbi-yishmael-b-yohanan-b-berokah", "4:5", hs="רבי ישמעאל בנו אומר", he="לשמר ולעשות", gp=6)
add("rabbi-tzadok-(i)", "4:5", hs="רבי צדוק אומר", he="ולא קרדם לחפר בהם", gp=7, ee='wherewith to dig."')
add("rabbi-yohanan-hasandlar", "4:11", hs="רבי יוחנן הסנדלר אומר", gp=14)
add("rabbi-elazar-b-shamua", "4:12", gp=15)
add("rabbi-nehorai", "4:14", gp=18)
add("rabbi-mattia-b-heresh", "4:15", hs="רבי מתיא בן חרש אומר", gp=20)
add("rabbi-shimon-b-elazar", "4:18", gp=23)
add("shmuel-the-little", "4:19", gp=24)
add("elisha-ben-abuya", "4:20", hs="אלישע בן אבויה אומר", he="על ניר מחוק", gp=25)
add("rabbi-yose-b-yehudah-of-kefar-habavli", "4:20", hs="רבי יוסי בר יהודה איש כפר הבבלי אומר", he="ושותה יין ישן", gp=26)
add("rabi", "4:20", hs="רבי אומר, אל תסתכל בקנקן", gp=27, es="Look not at the flask")   # Gorfinkle attributes this to R. Meir; the Hebrew here says 'Rabbi'
add("rabbi-elazar-hakappar", "4:21", gp=28)

out = {}
for slug, c, m, kind, hs, he, gps, es, ee in ITEMS:
    h = TEXT[c]["he"][m - 1]
    try:
        out.setdefault(slug, []).append({"ref": f"Avot {c}:{m}", "kind": kind, "he": cut_he(h, hs, he), "en": cut_en(c, gps, es, ee)})
    except (ValueError, KeyError) as err:
        raise SystemExit(f"marker not found: {slug} {c}:{m}: {err!r}\nHE: {NIKUD.sub('', h)[:300]}\nEN: {' / '.join(G[c][g][:300] for g in gps)}")
json.dump(out, open("outline/sages/avot.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "sages,", sum(len(v) for v in out.values()), "quotations")
