"""Pirkei Avot 1-4: a selection of each tanna's own sayings (and R. Yochanan ben Zakkai's praise of his five students, Avot 2:8-9)
for the sages kit. Output: outline/sages/avot.json = {slug: [{ref, kind, he, en}]}, read by sages_kit.py.

Sources (facts only from Sefaria): Hebrew = Sefaria's 'Torat Emet 357' (Public Domain); English = 'Sayings of the Jewish Fathers (Pirqe Aboth)
translated by Charles Taylor [1897]' (published 1897; complete for chapters 1-4, unlike the CC0 community translation). Every quotation is cut
verbatim from the segment named; the only edits to the English are Thorah -> Torah, Thalmud -> Talmud and one OCR slip ('yokel' -> 'yoke').
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

TEXT = {c: {"he": fetch(c, "he", VT_HE), "en": fetch(c, "en", VT_EN)} for c in (1, 2, 3, 4)}
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

def fix_en(t):
    t = re.sub(r"\s\d{1,2}\.\s", " ", " " + t).strip()
    t = re.sub(r"^\d+\.\s*", "", t)
    return t.replace("Thorah", "Torah").replace("Thalmud", "Talmud").replace("yokel,", "yoke")

def cut_en(seg, start, end):
    seg = re.sub(r"^\d+\.\s*", "", seg)
    a = seg.index(start) if start else 0
    b = len(seg)
    if end:
        b = seg.index(end, a) + len(end)
    return fix_en(seg[a:b].rstrip(" ,;"))

ITEMS = []
def add(slug, ref, kind="saying", hs=None, he=None, es=None, ee=None):
    c, m = (int(x) for x in ref.split(":"))
    ITEMS.append((slug, c, m, kind, hs, he, es, ee))

# --- chapter 1
add("shimon-hatzaddik", "1:2")
add("antigonus-of-sokho", "1:3")
add("yose-b-yoezer", "1:4", hs="יוסי בן יועזר איש צרדה אומר", es="Jose ben Jo'ezer of Çeredah said")
add("yose-b-yochanan", "1:5", he="ואל תרבה שיחה עם האשה", ee="converse with woman")
add("yehoshua-b-perachya", "1:6", hs="יהושע בן פרחיה אומר", es="Jehoshua' ben Perachiah said")
add("nittai-haarbeli", "1:7")
add("yehudah-b-tabbai", "1:8", hs="יהודה בן טבאי אומר", es="Jehudah ben Tabai said")
add("shimon-b-shetach", "1:9")
add("shemaiah", "1:10", hs="שמעיה אומר", es="Shema'iah said")
add("avtalyon", "1:11")
add("hillel", "1:12", hs="הלל אומר", es="Hillel said")
add("hillel", "1:14")
add("shammai", "1:15")
add("rabban-gamliel-hazaken-(i)", "1:16")
add("rabban-shimon-b-gamliel", "1:17")
add("rabban-shimon-b-gamliel-(ii)", "1:18")
# --- chapter 2
add("rabi", "2:1")
add("rabban-gamliel-b-rabbi-(iii)", "2:2")
add("rabban-gamliel-b-rabbi-(iii)", "2:4", hs="עשה רצונו כרצונך", he="רצון אחרים מפני רצונך", es="Do His will", ee="will of others before thy will")
add("hillel", "2:4", hs="הלל אומר, אל תפרש", es="Hillel said, Separate not")
add("hillel", "2:5")
add("rabban-yochanan-b-zakkai", "2:8", hs="אם למדת תורה הרבה", he="כי לכך נוצרת", es="If thou hast practised Thorah much", ee="wast thou created")
# R. Yochanan ben Zakkai's praise of his five students (2:8) and their answers to 'which is the good way' (2:9)
for slug, hh, ee_, en_s, en_e in [
    ("rabbi-eliezer-b-hyrcanus", ("רבי אליעזר בן הורקנוס, בור סוד", "שאינו מאבד טפה"), None, "Eli'ezer ben Hyrqanos is a plastered cistern", "loseth not a drop"),
    ("rabbi-yehoshua-b-hananyah", ("רבי יהושע בן חנניה, אשרי יולדתו", "אשרי יולדתו"), None, "Jehoshua' ben Chananiah--happy is she that bare him", "that bare him"),
    ("rabbi-yose-hakohen", ("רבי יוסי הכהן, חסיד", "חסיד"), None, "Jose the Priest is pious", "pious"),
    ("shimon-b-netanel", ("רבי שמעון בן נתנאל, ירא חטא", "ירא חטא"), None, "Shim'eon ben Nathanael is a sinfearer", "sinfearer"),
    ("rabbi-elazar-b-arakh", ("אלעזר בן ערך, מעין המתגבר", "מעין המתגבר"), None, "Ele'azar ben 'Arak is a welling spring", "welling spring"),
]:
    add(slug, "2:8", "praise", hh[0], hh[1], en_s, en_e)
for slug, hs_, es_, ee_ in [
    ("rabbi-eliezer-b-hyrcanus", "רבי אליעזר אומר, עין טובה", "Rabbi Li'ezer said, A good eye", "A good eye"),
    ("rabbi-yehoshua-b-hananyah", "רבי יהושע אומר, חבר טוב", "R. Jehoshua' said, A good friend", "A good friend"),
    ("rabbi-yose-hakohen", "רבי יוסי אומר, שכן טוב", "R. Jose said, A good neighbour", "A good neighbour"),
    ("shimon-b-netanel", "רבי שמעון אומר, הרואה את הנולד", "R. Shime'on said, He that foresees what is to be", "what is to be"),
    ("rabbi-elazar-b-arakh", "רבי אלעזר אומר, לב טוב", "R. La'zar said, A good heart", "A good heart"),
]:
    add(slug, "2:9", "answer", hs_, hs_.split("אומר, ")[1], es_, ee_)
add("rabbi-elazar-b-arakh", "2:9", "praise", "אמר להם, רואה אני את דברי אלעזר בן ערך מדבריכם", "שבכלל דבריו דבריכם",
    "He said to them, I approve the words of Ele'azar ben 'Arak rather than your words", "for his words include your words")
add("rabbi-eliezer-b-hyrcanus", "2:10")
add("rabbi-yehoshua-b-hananyah", "2:11")
add("rabbi-yose-hakohen", "2:12")
add("shimon-b-netanel", "2:13")
add("rabbi-elazar-b-arakh", "2:14")
add("rabbi-tarfon", "2:15")
add("rabbi-tarfon", "2:16")
# --- chapter 3
add("akavyah-b-mahalalel", "3:1")
add("rabbi-hanina-segan-hakohanim", "3:2", hs="רבי חנינא סגן הכהנים אומר", he="חיים בלעו", es="R. Chananiah, prefect of the priests, said", ee="alive")
add("rabbi-hananyah-b-teradyon", "3:2", hs="רבי חנינא בן תרדיון אומר", he="שכינה שרויה ביניהם", es="R. Chananiah ben Thradyon said", ee="Shekinah")
add("rabbi-hananyah-b-hakhinai", "3:4")
add("rabbi-nehunya-b-hakanah", "3:5")
add("rabbi-halafta-of-kefar-hanania", "3:6", he="שכינה שרויה ביניהם", ee="the Shekinah is among them")
add("rabbi-elazar-b-yehudah-of-bartota", "3:7", he="ומידך נתנו לך", ee="have we given thee")
add("rabbi-chanina-b-dosa", "3:9")
add("rabbi-chanina-b-dosa", "3:10", he="אין רוח המקום נוחה הימנו", ee="the Spirit of God is not pleased")
add("rabbi-dosa-b-harkinas", "3:10", hs="רבי דוסא בן הרכינס אומר", es="R. Dosa ben Horkinas said")
add("rabbi-elazar-hamodai", "3:11")
add("rabbi-yishmael-b-elisha", "3:12")
add("rabbi-akiva", "3:13")
add("rabbi-akiva", "3:15")
add("rabbi-elazar-b-azaryah", "3:17", he="אם אין תורה, אין קמח", ee="no Thorah, no meal")
add("rabbi-elazar-hisma", "3:18")
# --- chapter 4
add("shimon-b-zoma", "4:1", he="הכובש את יצרו", ee="subdues his nature")
add("shimon-b-azzai", "4:2")
add("shimon-b-azzai", "4:3")
add("rabbi-levitas-of-yavneh", "4:4", hs="רבי לויטס איש יבנה אומר", he="שתקות אנוש רמה", es="R. Levitas of Jabneh said", ee="the worm")
add("rabbi-yohanan-b-berokah", "4:4", hs="רבי יוחנן בן ברוקא אומר", es="R. Jochanan ben Baroqah said")
add("rabbi-yishmael-b-yohanan-b-berokah", "4:5", hs="רבי ישמעאל בנו אומר", he="לשמר ולעשות", es="R. Ishma'el his son said", ee="to learn, and to teach, and to practise")
add("rabbi-tzadok-(i)", "4:5", hs="רבי צדוק אומר", he="ולא קרדם לחפר בהם", es="R. Çadoq said", ee="to live by them")
add("rabbi-yohanan-hasandlar", "4:11", hs="רבי יוחנן הסנדלר אומר", es="R. Jochanan Sandalarius said")
add("rabbi-elazar-b-shamua", "4:12")
add("rabbi-nehorai", "4:14")
add("rabbi-mattia-b-heresh", "4:15", hs="רבי מתיא בן חרש אומר", es="R. Matthiah ben Charash said")
add("rabbi-shimon-b-elazar", "4:18")
add("shmuel-the-little", "4:19")
add("elisha-ben-abuya", "4:20", hs="אלישע בן אבויה אומר", he="על ניר מחוק", es="Elisha' ben Abiyyah said", ee="used paper")
add("rabbi-yose-b-yehudah-of-kefar-habavli", "4:20", hs="רבי יוסי בר יהודה איש כפר הבבלי אומר", he="ושותה יין ישן", es="R. Jose ben Jehudah of Kaphar ha-Babli said", ee="old wine")
add("rabi", "4:20", hs="רבי אומר, אל תסתכל בקנקן", es="Regard not the flask")
add("rabbi-elazar-hakappar", "4:21")

out = {}
for slug, c, m, kind, hs, he, es, ee in ITEMS:
    h = TEXT[c]["he"][m - 1]; e = TEXT[c]["en"][m - 1]
    try:
        out.setdefault(slug, []).append({"ref": f"Avot {c}:{m}", "kind": kind, "he": cut_he(h, hs, he), "en": cut_en(e, es, ee)})
    except ValueError as err:
        raise SystemExit(f"marker not found: {slug} {c}:{m}: {err}\nHE: {NIKUD.sub('', h)[:300]}\nEN: {e[:400]}")
json.dump(out, open("outline/sages/avot.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "sages,", sum(len(v) for v in out.values()), "quotations")
