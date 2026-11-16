"""Pirkei Avot 1-4: a selection of each tanna's own sayings (and R. Yochanan ben Zakkai's praise of his five students, Avot 2:8-9)
for the sages kit. Output: outline/sages/avot.json = {slug: [{ref, kind, he, en}]}, read by sages_kit.py.

Sources (facts only from Sefaria): Hebrew = Sefaria's 'Torat Emet 357' (Public Domain). English = the Sefaria Community Translation (CC0) for Avot 3-5 and 1:14,
cut verbatim; Avot 1-2 are not in it (chapter 2 not at all), so those quotations are OUR OWN rendering of the Hebrew clause quoted (marked en_src 'ours'
in the data and '(our translation)' on screen) and need the author's review. Tried and rejected: Kulp (project rule), Taylor 1897 and Gorfinkle 1913 (public
domain but dated), Silverstein/Bartenura (modern, CC-BY, but Bartenura's notes are interleaved in brackets with his own mishnah words, so it cannot be cut cleanly).
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

TEXT = {c: {"he": fetch(c, "he", VT_HE)} for c in (1, 2, 3, 4, 5, 6)}

def community():
    C = {}
    for c in (1, 2, 3, 4, 5, 6):
        u = f"https://www.sefaria.org/api/texts/Pirkei_Avot.{c}?context=0&commentary=0&pad=0&ven={urllib.parse.quote('Sefaria Community Translation')}"
        C[c] = [re.sub(r"<[^>]+>", "", t) if isinstance(t, str) else "" for t in json.load(urllib.request.urlopen(u))["text"]]
    return C
COMM = community()
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

def cut_en(c, m, es, ee):
    seg = re.sub(r"\s{2,}", " ", COMM[c][m - 1]).strip()
    a = seg.index(es) if es else 0
    b = len(seg)
    if ee:
        b = seg.index(ee, a) + len(ee)
    t = seg[a:b].strip()
    if t.count('"') % 2: t = t.rstrip(" ,;.") + '."'
    if t[-1].isalnum(): t += "."
    return t

ITEMS = []
def add(slug, ref, kind="saying", hs=None, he=None, es=None, ee=None):
    c, m = (int(x) for x in ref.split(":"))
    ITEMS.append((slug, c, m, kind, hs, he, es, ee))

# Avot 1-2: our own rendering of the Hebrew clause quoted (keyed by slug, ref, kind). Community Translation has no chapter 2 and only 1:1 and 1:14 of chapter 1.
TR = {
 ("shimon-hatzaddik", "1:2", "saying"): "Shimon the Righteous was one of the last members of the Great Assembly. He used to say: The world stands on three things: on Torah, on the Temple service, and on acts of kindness.",
 ("antigonus-of-sokho", "1:3", "saying"): "Antigonus of Sokho received [the tradition] from Shimon the Righteous. He used to say: Do not be like servants who serve their master in order to receive a reward; be like servants who serve their master not in order to receive a reward. And let the fear of Heaven be upon you.",
 ("yose-b-yoezer", "1:4", "saying"): "Yose ben Yoezer of Tzeredah says: Let your house be a meeting place for the sages; cover yourself in the dust of their feet; and drink in their words thirstily.",
 ("yose-b-yochanan", "1:5", "saying"): "Yose ben Yochanan of Jerusalem says: Let your house be wide open; let the poor be members of your household; and do not talk too much with a woman.",
 ("yehoshua-b-perachya", "1:6", "saying"): "Yehoshua ben Perachya says: Make for yourself a teacher; acquire for yourself a friend; and judge every person favorably.",
 ("nittai-haarbeli", "1:7", "saying"): "Nittai the Arbelite says: Keep away from a bad neighbor; do not become attached to a wicked person; and do not give up on [the thought of] punishment.",
 ("yehudah-b-tabbai", "1:8", "saying"): "Yehuda ben Tabbai says: Do not make yourself like the lawyers [literally, \u201cthose who arrange the judges\u201d]. When litigants stand before you, regard them as guilty; and when they leave you, regard them as innocent, once they have accepted the judgment.",
 ("shimon-b-shetach", "1:9", "saying"): "Shimon ben Shetach says: Examine the witnesses thoroughly, and be careful with your words, lest from them they learn to lie.",
 ("shemaiah", "1:10", "saying"): "Shemaya says: Love work; hate positions of power; and do not seek to become known to the authorities.",
 ("avtalyon", "1:11", "saying"): "Avtalyon says: Sages, be careful with your words, lest you incur the penalty of exile and be exiled to a place of evil waters, and the students who come after you drink and die, and it turns out that Heaven\u2019s name is desecrated.",
 ("hillel", "1:12", "saying"): "Hillel says: Be among the disciples of Aaron: loving peace and pursuing peace, loving people and bringing them close to Torah.",
 ("shammai", "1:15", "saying"): "Shammai says: Make your Torah study a fixed practice; say little and do much; and receive every person with a pleasant face.",
 ("rabban-gamliel-hazaken-(i)", "1:16", "saying"): "Rabban Gamliel used to say: Make for yourself a teacher, and remove yourself from doubt; and do not make a habit of tithing by estimation.",
 ("rabban-shimon-b-gamliel", "1:17", "saying"): "His son Shimon says: All my days I grew up among the sages, and I have found nothing better for a person than silence. Study is not the main thing, but action; and whoever talks too much brings sin.",
 ("rabban-shimon-b-gamliel-(ii)", "1:18", "saying"): "Rabban Shimon ben Gamliel says: The world stands on three things: on justice, on truth, and on peace, as it is said (Zechariah 8:16): \u201cJudge truth and the justice of peace in your gates.\u201d",
 ("rabi", "2:1", "saying"): "Rabbi says: Which is the right path for a person to choose? Whatever is a source of pride for the one who follows it and brings him honor from others. Be as careful with a light commandment as with a serious one, for you do not know the reward given for each commandment. Weigh the loss from [performing] a commandment against its reward, and the gain from a transgression against its loss. Consider three things and you will not come to transgression: know what is above you\u2014an eye that sees, an ear that hears, and all your deeds written in a book.",
 ("rabban-gamliel-b-rabbi-(iii)", "2:2", "saying"): "Rabban Gamliel, son of Rabbi Yehuda the Prince, says: Torah study is excellent together with a worldly occupation, for the effort of both makes one forget sin. All Torah without work ends in failure and leads to sin. Let all who work for the community work for them for the sake of Heaven, for the merit of their ancestors supports them and their righteousness stands forever. And as for you, [God says,] I credit you with great reward as if you had done it yourselves.",
 ("rabban-gamliel-b-rabbi-(iii)", "2:4", "saying"): "Do His will as if it were your will, so that He will do your will as if it were His will. Nullify your will before His will, so that He will nullify the will of others before your will.",
 ("hillel", "2:4", "saying"): "Hillel says: Do not separate yourself from the community; do not trust yourself until the day of your death; do not judge your fellow until you reach his place; do not say something that cannot be understood [at once], on the grounds that in the end it will be understood; and do not say, \u201cWhen I have free time I will study,\u201d for perhaps you will never have free time.",
 ("hillel", "2:5", "saying"): "He used to say: A boor cannot be sin-fearing, nor can an ignorant person be pious; the shy cannot learn, nor the short-tempered teach; and not everyone who does much business becomes wise. And in a place where there are no [real] people, strive to be a person.",
 ("rabban-yochanan-b-zakkai", "2:8", "saying"): "If you have learned much Torah, do not take credit for yourself, for this is what you were created for.",
 ("rabbi-eliezer-b-hyrcanus", "2:8", "praise"): "Rabbi Eliezer ben Hyrcanus is a plastered cistern that does not lose a drop.",
 ("rabbi-eliezer-b-hyrcanus", "2:9", "answer"): "Rabbi Eliezer says: A good eye.",
 ("rabbi-eliezer-b-hyrcanus", "2:10", "saying"): "They said three things each. Rabbi Eliezer says: Let your friend\u2019s honor be as dear to you as your own; do not be quick to anger; and repent one day before you die. And warm yourself by the fire of the sages, but be careful of their coals so that you are not burned, for their bite is the bite of a fox, their sting is the sting of a scorpion, their hiss is the hiss of a serpent, and all their words are like fiery coals.",
 ("rabbi-yehoshua-b-hananyah", "2:8", "praise"): "Rabbi Yehoshua ben Hananya\u2014happy is the one who bore him.",
 ("rabbi-yehoshua-b-hananyah", "2:9", "answer"): "Rabbi Yehoshua says: A good friend.",
 ("rabbi-yehoshua-b-hananyah", "2:11", "saying"): "Rabbi Yehoshua says: The evil eye, the evil inclination, and hatred of people take a person out of the world.",
 ("rabbi-yose-hakohen", "2:8", "praise"): "Rabbi Yose the Priest is pious.",
 ("rabbi-yose-hakohen", "2:9", "answer"): "Rabbi Yose says: A good neighbor.",
 ("rabbi-yose-hakohen", "2:12", "saying"): "Rabbi Yose says: Let your friend\u2019s property be as dear to you as your own; prepare yourself to study Torah, for it is not an inheritance for you; and let all your actions be for the sake of Heaven.",
 ("shimon-b-netanel", "2:8", "praise"): "Rabbi Shimon ben Netanel is sin-fearing.",
 ("shimon-b-netanel", "2:9", "answer"): "Rabbi Shimon says: One who sees what is to come [literally, \u201cwhat will be born\u201d].",
 ("shimon-b-netanel", "2:13", "saying"): "Rabbi Shimon says: Be careful in reciting the Shema and in prayer. When you pray, do not make your prayer a fixed routine, but [a plea for] mercy and supplication before God, as it is said (Joel 2:13): \u201cFor He is gracious and compassionate, slow to anger, abounding in kindness, and relents from punishing.\u201d And do not be wicked in your own eyes.",
 ("rabbi-elazar-b-arakh", "2:8", "praise"): "Rabbi Elazar ben Arach is an ever-strengthening spring.",
 ("rabbi-elazar-b-arakh", "2:9", "answer"): "Rabbi Elazar says: A good heart.",
 ("rabbi-elazar-b-arakh", "2:9", "praise"): "He [Rabban Yochanan] said to them: I prefer the words of Elazar ben Arach to your words, because your words are included in his words.",
 ("rabbi-elazar-b-arakh", "2:14", "saying"): "Rabbi Elazar says: Be diligent in studying Torah, and know how to answer an unbeliever (apikoros); know before whom you toil, and that your Employer can be trusted to pay you the reward for your work.",

 ("hillel", "1:13", "saying"): "He used to say: One who makes his name great destroys his name; one who does not add [to his learning] loses; one who does not learn deserves death; and one who makes use of the crown [of Torah] passes away.",
 ("rabban-gamliel-b-rabbi-(iii)", "2:3", "saying"): "Be careful with the authorities, for they bring a person close only for their own needs. They appear as friends when it benefits them, but they do not stand by a person in his time of need.",
 ("hillel", "2:6", "saying"): "He also saw a skull floating on the water. He said to it: Because you drowned [others], you were drowned; and in the end, those who drowned you will be drowned.",
 ("hillel", "2:7", "saying"): "He used to say: The more flesh, the more worms; the more property, the more worry; the more wives, the more witchcraft; the more maidservants, the more lewdness; the more male servants, the more theft; the more Torah, the more life; the more study, the more wisdom; the more counsel, the more understanding; the more charity, the more peace. One who has acquired a good name has acquired it for himself; one who has acquired words of Torah has acquired for himself life in the World to Come.",

 ("rabban-yochanan-b-zakkai", "2:8", "verdict"): "He used to say: If all the sages of Israel were on one pan of a scale, and Eliezer ben Hyrcanus on the other pan, he would outweigh them all.",
 ("abba-shaul", "2:8", "saying"): "Abba Shaul says in his [Rabban Yochanan\u2019s] name: If all the sages of Israel were on one pan of a scale, with Rabbi Eliezer ben Hyrcanus among them, and Rabbi Elazar ben Arach on the other pan, he would outweigh them all.",
 ("rabbi-tarfon", "2:15", "saying"): "Rabbi Tarfon says: The day is short, the work is great, the workers are lazy, the reward is great, and the Master of the house is pressing.",
 ("rabbi-tarfon", "2:16", "saying"): "He used to say: It is not your duty to finish the work, but you are not free to desist from it. If you have learned much Torah, you will be given much reward; your Employer can be trusted to pay you the reward for your work; and know that the reward of the righteous is in the time to come.",
}

# --- chapter 1   (hs/he = start/end markers in the Hebrew; es/ee = start/end markers in the Community Translation, for Avot 3-5 and 1:14)
add("shimon-hatzaddik", "1:2")
add("antigonus-of-sokho", "1:3")
add("yose-b-yoezer", "1:4", hs="יוסי בן יועזר איש צרדה אומר")
add("yose-b-yochanan", "1:5", he="ואל תרבה שיחה עם האשה")
add("yehoshua-b-perachya", "1:6", hs="יהושע בן פרחיה אומר")
add("nittai-haarbeli", "1:7")
add("yehudah-b-tabbai", "1:8", hs="יהודה בן טבאי אומר")
add("shimon-b-shetach", "1:9")
add("shemaiah", "1:10", hs="שמעיה אומר")
add("avtalyon", "1:11")
add("hillel", "1:12", hs="הלל אומר")
add("hillel", "1:13")
add("hillel", "1:14")
add("shammai", "1:15")
add("rabban-gamliel-hazaken-(i)", "1:16")
add("rabban-shimon-b-gamliel", "1:17")
add("rabban-shimon-b-gamliel-(ii)", "1:18")
# --- chapter 2
add("rabi", "2:1")
add("rabban-gamliel-b-rabbi-(iii)", "2:2")
add("rabban-gamliel-b-rabbi-(iii)", "2:3")
add("rabban-gamliel-b-rabbi-(iii)", "2:4", hs="עשה רצונו כרצונך", he="רצון אחרים מפני רצונך")
add("hillel", "2:4", hs="הלל אומר, אל תפרש")
add("hillel", "2:6")
add("hillel", "2:7")
add("hillel", "2:5")
add("rabban-yochanan-b-zakkai", "2:8", hs="אם למדת תורה הרבה", he="כי לכך נוצרת")
add("rabban-yochanan-b-zakkai", "2:8", "verdict", "הוא היה אומר, אם יהיו כל חכמי ישראל בכף מאזנים, ואליעזר", "מכריע את כלם")
add("abba-shaul", "2:8", hs="אבא שאול אומר משמו")
# R. Yochanan ben Zakkai's praise of his five students (2:8) and their answers to 'which is the good way' (2:9)
for slug, hh in [
    ("rabbi-eliezer-b-hyrcanus", ("רבי אליעזר בן הורקנוס, בור סוד", "שאינו מאבד טפה")),
    ("rabbi-yehoshua-b-hananyah", ("רבי יהושע בן חנניה, אשרי יולדתו", "אשרי יולדתו")),
    ("rabbi-yose-hakohen", ("רבי יוסי הכהן, חסיד", "חסיד")),
    ("shimon-b-netanel", ("רבי שמעון בן נתנאל, ירא חטא", "ירא חטא")),
    ("rabbi-elazar-b-arakh", ("אלעזר בן ערך, מעין המתגבר", "מעין המתגבר")),
]:
    add(slug, "2:8", "praise", hh[0], hh[1])
for slug, hs_ in [
    ("rabbi-eliezer-b-hyrcanus", "רבי אליעזר אומר, עין טובה"),
    ("rabbi-yehoshua-b-hananyah", "רבי יהושע אומר, חבר טוב"),
    ("rabbi-yose-hakohen", "רבי יוסי אומר, שכן טוב"),
    ("shimon-b-netanel", "רבי שמעון אומר, הרואה את הנולד"),
    ("rabbi-elazar-b-arakh", "רבי אלעזר אומר, לב טוב"),
]:
    add(slug, "2:9", "answer", hs_, hs_.split("אומר, ")[1])
add("rabbi-elazar-b-arakh", "2:9", "praise", "אמר להם, רואה אני את דברי אלעזר בן ערך מדבריכם", "שבכלל דבריו דבריכם")
add("rabbi-eliezer-b-hyrcanus", "2:10")
add("rabbi-yehoshua-b-hananyah", "2:11")
add("rabbi-yose-hakohen", "2:12")
add("shimon-b-netanel", "2:13")
add("rabbi-elazar-b-arakh", "2:14")
add("rabbi-tarfon", "2:15")
add("rabbi-tarfon", "2:16")
# --- chapter 3
add("akavyah-b-mahalalel", "3:1")
add("rabbi-hanina-segan-hakohanim", "3:2", hs="רבי חנינא סגן הכהנים אומר", he="חיים בלעו", ee="swallow his fellow alive.")
add("rabbi-hananyah-b-teradyon", "3:2", hs="רבי חנינא בן תרדיון אומר", he="שכינה שרויה ביניהם", es="Rabbi Chananya ben Teradyon says", ee="the Divine Presence rests with them")
add("rabbi-hananyah-b-hakhinai", "3:4")
add("rabbi-nehunya-b-hakanah", "3:5")
add("rabbi-halafta-of-kefar-hanania", "3:6", he="שכינה שרויה ביניהם", ee="the Divine Presence rests among them")
add("shimon-bar-yochai", "3:7", hs="רבי שמעון אומר, המהלך", es="Rabbi Shimon says: He who is walking")
add("rabbi-dostai-b-r-yannai", "3:8", he="אשר ראו עיניך", ee="which your eyes saw.\"")
add("rabbi-meir", "3:8", "inname", he="אשר ראו עיניך", ee="which your eyes saw.\"")   # taught in his name by R. Dostai b. Yannai
add("shimon-bar-yochai", "3:3", he="אשר לפני ה'")
add("rabbi-elazar-b-yehudah-of-bartota", "3:7", he="ומידך נתנו לך", ee="we have given to You\" (I Chronicles 29:14).")
add("rabbi-chanina-b-dosa", "3:9")
add("rabbi-chanina-b-dosa", "3:10", he="אין רוח המקום נוחה הימנו", ee="the spirit of God does not find pleasure.")
add("rabbi-dosa-b-harkinas", "3:10", hs="רבי דוסא בן הרכינס אומר", es="Rabbi Dosa ben Harkinus says")
add("rabbi-elazar-hamodai", "3:11")
add("rabbi-yishmael-b-elisha", "3:12")
add("rabbi-akiva", "3:13")
add("rabbi-akiva", "3:14", he="עשה את האדם", ee="He made man.\"")
add("rabbi-akiva", "3:15")
add("rabbi-akiva", "3:16", he="והיד כותבת", ee="the hand writes")
add("rabbi-elazar-b-azaryah", "3:17", he="אם אין תורה, אין קמח", ee="there is no flour.")
add("rabbi-elazar-hisma", "3:18")
# --- chapter 4
add("shimon-b-zoma", "4:1", he="הכובש את יצרו", ee="He who conquers his impulse")
add("shimon-b-azzai", "4:2")
add("shimon-b-azzai", "4:3")
add("rabbi-levitas-of-yavneh", "4:4", hs="רבי לויטס איש יבנה אומר", he="שתקות אנוש רמה", es="Rabbi Levitas", ee="the hope of man is worms.")
add("rabbi-yohanan-b-berokah", "4:4", hs="רבי יוחנן בן ברוקא אומר", es="Rabbi Yochanan ben Beroka says")
add("rabbi-yishmael-b-yohanan-b-berokah", "4:5", hs="רבי ישמעאל בנו אומר", he="לשמר ולעשות", ee="to observe, and to practice.")
add("hillel", "4:5", hs="וכך היה הלל אומר", es="And thus Hillel used to say")
add("rabbi-tzadok-(i)", "4:5", hs="רבי צדוק אומר", he="ולא קרדם לחפר בהם", es="Rabbi Tzadok says", ee="with which to dig into them.")
add("rabbi-yose-b-chalafta", "4:6")      # 'R. Yose', whose son R. Yishmael follows in 4:7 (R. Yose b. Chalafta's son is R. Yishmael b. Yose)
add("rabbi-yishmael-b-yose", "4:7", he="ושבועת שוא", es="One who withholds", ee="and the false oath.")   # cut before 'imbecile' (project rule: never)
add("rabbi-yishmael-b-yose", "4:8")
add("rabbi-yonatan", "4:9")
add("rabbi-meir", "4:10")
add("rabbi-eliezer-b-yaakov-(ii)", "4:11", hs="רבי אליעזר בן יעקב אומר", he="כתריס בפני הפרענות", es="Rabbi Eliezer ben Yaakov says", ee="shield against punishment.")
add("rabbi-yohanan-hasandlar", "4:11", hs="רבי יוחנן הסנדלר אומר", es="Rabbi Yochanan the shoemaker says")
add("rabbi-elazar-b-shamua", "4:12")
add("rabbi-yehudah-b-ilai", "4:13", hs="רבי יהודה אומר", he="עולה זדון", es="Rabbi Yehuda says", ee="intentional transgression.")
add("shimon-bar-yochai", "4:13", hs="רבי שמעון אומר", es="Rabbi Shimon says")
add("rabbi-nehorai", "4:14")
add("rabbi-yaakov-b-qorshai", "4:16")
add("rabbi-yaakov-b-qorshai", "4:17")
add("rabbi-mattia-b-heresh", "4:15", hs="רבי מתיא בן חרש אומר", es="Rabbi Mattia ben Charash says")
add("rabbi-shimon-b-elazar", "4:18")
add("shmuel-the-little", "4:19")
add("elisha-ben-abuya", "4:20", hs="אלישע בן אבויה אומר", he="על ניר מחוק", ee="scraped parchment.")
add("rabbi-yose-b-yehudah-of-kefar-habavli", "4:20", hs="רבי יוסי בר יהודה איש כפר הבבלי אומר", he="ושותה יין ישן", es="Rabbi Yose bar Yehuda", ee="aged wine.")
add("rabi", "4:20", hs="רבי אומר, אל תסתכל בקנקן", es="Rebbi says")
add("rabbi-elazar-hakappar", "4:21")

# --- chapter 5 (Avot 5 is mostly anonymous lists; these are the named sages)
add("yehudah-b-tema", "5:20", hs="יהודה בן תימא אומר", he="לעשות רצון אביך שבשמים", es="Yehudah ben Teimah says", ee="the Will of your Father Who is in Heaven.")
add("yochanan-ben-bag-bag", "5:22")
add("ben-he-he", "5:23")

# --- chapter 6 (Kinyan Torah, a later addition; the sages the kit's Mishnah census places there)
add("rabbi-meir", "6:1", hs="רבי מאיר אומר", he="כדי הוא לו", es="Rabbi Meir says", ee="worthwhile for his sake")
add("rabbi-shimon-b-yehudah", "6:8", he="נאה לצדיקים ונאה לעולם", ee="fitting for the righteous and fitting for the world")
add("shimon-bar-yochai", "6:8", "inname", he="נאה לצדיקים ונאה לעולם", ee="fitting for the righteous and fitting for the world")
add("rabbi-shimon-b-menasya", "6:8", hs="רבי שמעון בן מנסיא אומר", es="Rabbi Shimon ben Menasya says")
add("rabbi-yose-b-kisma", "6:9", he="איני דר אלא במקום תורה", ee="in a place of Torah.\"")

out = {}
for slug, c, m, kind, hs, he, es, ee in ITEMS:
    h = TEXT[c]["he"][m - 1]
    try:
        if (slug, f"{c}:{m}", kind) in TR:
            en, src = TR[(slug, f"{c}:{m}", kind)], "ours"
        else:
            en, src = cut_en(c, m, es, ee), "community"
        item = {"ref": f"Avot {c}:{m}", "kind": kind, "he": cut_he(h, hs, he), "en": en}
        if src == "ours": item["en_src"] = "ours"
        out.setdefault(slug, []).append(item)
    except (ValueError, KeyError, IndexError) as err:
        raise SystemExit(f"marker not found: {slug} {c}:{m}: {err!r}\nHE: {NIKUD.sub('', h)[:300]}\nEN: {COMM[c][m-1][:400]}")
# Smoothing pass (author, 2026-11-15): every quotation re-read and put into easy modern English, staying close to the Hebrew; keyed by (slug, ref, kind).
# The Community Translation text above is the starting point for Avot 3-6; Avot 1-2 are our own rendering. Anything not listed here is used as is.
SMOOTH = {
 ("antigonus-of-sokho", "Avot 1:3", "saying"): "Do not be like servants who serve their master in order to receive a reward; be like servants who serve without expecting a reward. And let the fear of Heaven be upon you.",
 ("yose-b-yoezer", "Avot 1:4", "saying"): "Let your house be a meeting place for the sages; sit in the dust at their feet; and drink in their words thirstily.",
 ("nittai-haarbeli", "Avot 1:7", "saying"): "Keep away from a bad neighbor; do not become attached to a wicked person; and do not give up believing that wrongdoing is punished.",
 ("shemaiah", "Avot 1:10", "saying"): "Love work; hate lording it over others; and do not seek to become known to the authorities.",
 ("hillel", "Avot 1:14", "saying"): "If I am not for myself, who will be for me? And when I am for myself alone, what am I? And if not now, when?",
 ("hillel", "Avot 2:4", "saying"): "Do not separate yourself from the community; do not trust yourself until the day of your death; do not judge your fellow until you reach his place; do not say something that cannot be understood now, thinking it will be understood in the end; and do not say, \u2018When I have free time I will study,\u2019 for perhaps you will never have free time.",
 ("hillel", "Avot 2:5", "saying"): "An uncultured person cannot be sin-fearing, nor can an ignorant person be pious; the shy cannot learn, nor the short-tempered teach; and not everyone who does much business becomes wise. And in a place where no one is acting like a person, strive to be a person.",
 ("rabi", "Avot 2:1", "saying"): "Which is the right path for a person to choose? Whatever is a source of pride for the one who follows it and earns him the respect of others. Be as careful with a light commandment as with a serious one, for you do not know the reward given for each commandment. Weigh what a commandment costs you against what it earns, and what a transgression earns you against what it costs. Consider three things and you will not come to transgression: know what is above you\u2014an eye that sees, an ear that hears, and all your deeds written in a book.",
 ("rabi", "Avot 4:20", "saying"): "Do not look at the jug, but at what is in it. There are new jugs full of old wine, and old jugs without even new wine in them.",
 ("rabban-gamliel-b-rabbi-(iii)", "Avot 2:2", "saying"): "Torah study is excellent together with a worldly occupation, for the effort of doing both makes one forget sin. Torah study without work comes to nothing and leads to sin. Let all who work for the community do so for the sake of Heaven, for the merit of their ancestors supports them, and their righteousness lasts forever. And as for you, [God says,] I will count it for you as great reward, as if you had done it all yourselves.",
 ("rabban-gamliel-b-rabbi-(iii)", "Avot 2:3", "saying"): "Be wary of those in power, for they draw a person close only when they need him. They appear to be friends when it suits them, but they do not stand by a person in his hour of need.",
 ("rabban-gamliel-b-rabbi-(iii)", "Avot 2:4", "saying"): "Make His will your own, so that He will make your will His. Set aside your will for the sake of His will, so that He will set aside the will of others for the sake of yours.",
 ("rabbi-yehoshua-b-hananyah", "Avot 2:8", "praise"): "Rabbi Yehoshua ben Hananya\u2014happy is she who bore him.",
 ("shimon-b-netanel", "Avot 2:9", "answer"): "One who foresees the outcome.",
 ("shimon-b-netanel", "Avot 2:13", "saying"): "Be careful in reciting the Shema and in prayer. When you pray, do not make your prayer a fixed routine, but a plea for mercy and supplication before God... And do not be wicked in your own eyes.",
 ("rabbi-elazar-b-arakh", "Avot 2:9", "praise"): "I prefer the words of Elazar ben Arach to yours, because your words are included in his.",
 ("akavyah-b-mahalalel", "Avot 3:1", "saying"): "Keep three things in mind and you will not come to sin: Know where you came from, where you are going, and before Whom you will have to give an account. Where did you come from? From a putrid drop. Where are you going? To a place of dust, worms, and maggots. And before Whom will you give an account? Before the King of kings, the Holy One, blessed be He.",
 ("rabbi-hanina-segan-hakohanim", "Avot 3:2", "saying"): "Pray for the welfare of the government, for were it not for fear of it, people would swallow one another alive.",
 ("rabbi-hananyah-b-teradyon", "Avot 3:2", "saying"): "If two people sit together and no words of Torah pass between them, this is a gathering of scoffers... But if two sit together and words of Torah pass between them, the Divine Presence rests among them.",
 ("rabbi-halafta-of-kefar-hanania", "Avot 3:6", "saying"): "When ten people sit together and engage in Torah, the Divine Presence rests among them.",
 ("shimon-bar-yochai", "Avot 3:3", "saying"): "Three who ate at one table without speaking words of Torah over it\u2014it is as if they ate from offerings to the dead... But three who ate at one table and spoke words of Torah over it\u2014it is as if they ate from the table of the Omnipresent.",
 ("shimon-bar-yochai", "Avot 3:7", "saying"): "Someone walking along the road, reviewing his studies, who breaks off his studying to say, \u2018How lovely is this tree! How lovely is this plowed field!\u2019\u2014Scripture considers it as if he has forfeited his life.",
 ("shimon-bar-yochai", "Avot 4:13", "saying"): "There are three crowns: the crown of Torah, the crown of priesthood, and the crown of monarchy\u2014but the crown of a good name outweighs them all.",
 ("shimon-bar-yochai", "Avot 6:8", "inname"): "Beauty, strength, wealth, honor, wisdom, old age, gray hair, and children are fitting for the righteous and good for the world.",
 ("rabbi-shimon-b-yehudah", "Avot 6:8", "saying"): "Beauty, strength, wealth, honor, wisdom, old age, gray hair, and children are fitting for the righteous and good for the world.",
 ("rabbi-meir", "Avot 4:10", "saying"): "Cut back on business and engage in Torah. Be humble before everyone. If you neglect Torah, many reasons to neglect it will come your way. But if you labor in Torah, God has abundant reward to give you.",
 ("rabbi-meir", "Avot 6:1", "saying"): "Anyone who engages in Torah for its own sake merits many things; moreover, the entire world is worthwhile for his sake.",
 ("rabbi-elazar-b-yehudah-of-bartota", "Avot 3:7", "saying"): "Give to Him from what is His, for you and everything you have are His.",
 ("rabbi-chanina-b-dosa", "Avot 3:9", "saying"): "Anyone whose fear of sin comes before his wisdom, his wisdom endures; but anyone whose wisdom comes before his fear of sin, his wisdom does not endure. He used to say: Anyone whose actions exceed his wisdom, his wisdom endures; but anyone whose wisdom exceeds his actions, his wisdom does not endure.",
 ("rabbi-chanina-b-dosa", "Avot 3:10", "saying"): "Anyone whom people are pleased with, God is pleased with. And anyone whom people are not pleased with, God is not pleased with.",
 ("rabbi-dosa-b-harkinas", "Avot 3:10", "saying"): "Sleeping late in the morning, drinking wine at midday, children\u2019s chatter, and sitting in the gathering places of the ignorant take a person out of the world.",
 ("rabbi-yishmael-b-elisha", "Avot 3:12", "saying"): "Be yielding to a leader, easygoing with the young, and receive everyone cheerfully.",
 ("rabbi-akiva", "Avot 3:13", "saying"): "Laughter and frivolity lead a person toward immorality. Tradition is a fence around the Torah. Tithes are a fence around wealth. Vows are a fence around self-restraint. A fence around wisdom is silence.",
 ("rabbi-akiva", "Avot 3:14", "saying"): "Beloved is a person, for he was created in the image of God. It is a sign of even greater love that he is told he was created in the image of God.",
 ("rabbi-akiva", "Avot 3:15", "saying"): "Everything is foreseen, yet freedom is given; the world is judged with goodness, yet everything depends on the abundance of one\u2019s deeds.",
 ("rabbi-akiva", "Avot 3:16", "saying"): "Everything is given as a pledge, and a net is spread over all the living. The shop is open, the shopkeeper extends credit, the ledger lies open, and the hand writes.",
 ("shimon-b-zoma", "Avot 4:1", "saying"): "Who is wise? One who learns from every person. Who is mighty? One who masters his impulses.",
 ("shimon-b-azzai", "Avot 4:2", "saying"): "Hurry to perform even a minor commandment as you would a major one, and flee from sin; for one commandment leads to another, and one sin leads to another; the reward of a commandment is another commandment, and the reward of a sin is another sin.",
 ("shimon-b-azzai", "Avot 4:3", "saying"): "Do not look down on anyone, and do not dismiss anything, for there is no person who does not have his hour, and nothing that does not have its place.",
 ("rabbi-levitas-of-yavneh", "Avot 4:4", "saying"): "Be very, very humble in spirit, for all a person can hope for in the end is worms.",
 ("rabbi-tzadok-(i)", "Avot 4:5", "saying"): "Do not make the Torah a crown with which to glorify yourself, nor a spade with which to dig.",
 ("rabbi-yose-b-chalafta", "Avot 4:6", "saying"): "Anyone who honors the Torah will himself be honored by people. Anyone who dishonors the Torah will himself be dishonored by people.",
 ("rabbi-yishmael-b-yose", "Avot 4:8", "saying"): "Do not judge alone, for only One [God] judges alone. And do not say to your fellow judges, \u2018Accept my opinion,\u2019 for they are free to decide, and you are not.",
 ("rabbi-yonatan", "Avot 4:9", "saying"): "Anyone who keeps the Torah in poverty will in the end keep it in wealth. And anyone who neglects the Torah in wealth will in the end neglect it in poverty.",
 ("rabbi-eliezer-b-yaakov-(ii)", "Avot 4:11", "saying"): "Whoever performs one commandment acquires one defender; whoever commits one sin acquires one accuser. Repentance and good deeds are like a shield against punishment.",
 ("rabbi-yohanan-hasandlar", "Avot 4:11", "saying"): "Every gathering that is for the sake of Heaven will in the end endure; and every gathering that is not for the sake of Heaven will not endure.",
 ("rabbi-elazar-b-shamua", "Avot 4:12", "saying"): "Let the honor of your student be as dear to you as your own, the honor of your colleague as dear as the reverence you have for your teacher, and the reverence you have for your teacher as dear as the reverence for Heaven.",
 ("rabbi-nehorai", "Avot 4:14", "saying"): "Go off to a place of Torah, and do not say that it will come after you, that your colleagues will make sure you keep it. And do not rely on your own understanding.",
 ("rabbi-yaakov-b-qorshai", "Avot 4:16", "saying"): "This world is like a hallway before the world to come. Prepare yourself in the hallway so that you may enter the reception hall.",
 ("rabbi-yaakov-b-qorshai", "Avot 4:17", "saying"): "One hour of repentance and good deeds in this world is better than all of life in the World to Come. And one hour of contentment in the World to Come is better than all of life in this world.",
 ("rabbi-mattia-b-heresh", "Avot 4:15", "saying"): "Be the first to greet everyone. And be a tail to lions rather than a head to foxes.",
 ("rabbi-shimon-b-elazar", "Avot 4:18", "saying"): "Do not try to calm your friend while he is angry; do not comfort him while his dead lies before him; do not question him at the moment he makes a vow; and do not try to see him at the moment of his downfall.",
 ("shmuel-the-little", "Avot 4:19", "saying"): "When your enemy falls, do not rejoice, and when he stumbles, let your heart not be glad, lest God see it, and it displease Him, and He turn His anger away from him.",
 ("elisha-ben-abuya", "Avot 4:20", "saying"): "One who learns as a child\u2014what is he like? Ink written on fresh paper. One who learns as an old person\u2014what is he like? Ink written on erased paper.",
 ("rabbi-yose-b-yehudah-of-kefar-habavli", "Avot 4:20", "saying"): "One who learns from the young\u2014what is he like? Someone who eats unripe grapes and drinks wine straight from the press. One who learns from the old\u2014what is he like? Someone who eats ripe grapes and drinks aged wine.",
 ("rabbi-elazar-hakappar", "Avot 4:21", "saying"): "Envy, desire, and the pursuit of honor take a person out of the world.",
 ("yehudah-b-tema", "Avot 5:20", "saying"): "Be bold as a leopard, light as an eagle, swift as a deer, and strong as a lion to do the will of your Father in Heaven.",
 ("yochanan-ben-bag-bag", "Avot 5:22", "saying"): "Turn it over and over, for everything is in it. Look into it, grow old and worn in it, and do not move away from it, for there is no better quality than it.",
 ("ben-he-he", "Avot 5:23", "saying"): "According to the effort is the reward.",
 ("rabbi-yose-b-kisma", "Avot 6:9", "saying"): "Once I was walking on the road, and a man met me and greeted me, and I returned his greeting. He said to me, \u2018Rabbi, where are you from?\u2019 I said to him, \u2018I am from a great city of sages and scribes.\u2019 He said to me, \u2018Rabbi, would you like to live with us in our place? I will give you a thousand thousand gold dinars, and precious stones and pearls.\u2019 I said to him, \u2018If you gave me all the silver, gold, precious stones and pearls in the world, I would live nowhere but in a place of Torah.\u2019",
}
for k, v in out.items():
    for it in v:
        sm = SMOOTH.get((k, it["ref"], it["kind"]))
        if sm: it["en"] = sm; it["en_src"] = "ours" if it.get("en_src") else "smoothed"

# Cut as obscure or not relatable for casual and young readers (author, 2026-11-15: a case-by-case judgement; restore any by deleting its line here).
DROP = {
    ("rabbi-elazar-hisma", "Avot 3:18"),                  # laws of bird offerings and niddah; astronomy and gematria
    ("rabbi-elazar-hamodai", "Avot 3:11"),                # a list of grave offences
    ("rabbi-hananyah-b-hakhinai", "Avot 3:4"),            # cryptic
    ("rabbi-nehunya-b-hakanah", "Avot 3:5"),              # the yoke of government and of worldly care
    ("yose-b-yochanan", "Avot 1:5"),                      # 'do not talk too much with a woman'
    ("yehudah-b-tabbai", "Avot 1:8"),                     # the lawyers who 'arrange the judges'
    ("avtalyon", "Avot 1:11"),                            # exile to the place of evil waters
    ("hillel", "Avot 1:13"),                              # Aramaic proverbs
    ("rabban-gamliel-hazaken-(i)", "Avot 1:16"),          # tithing by estimation
    ("hillel", "Avot 2:6"),                               # the skull
    ("hillel", "Avot 2:7"),                               # more flesh, more worms ... more wives, more witchcraft
    ("abba-shaul", "Avot 2:8"),                           # the pan of the scale
    ("rabban-yochanan-b-zakkai", "Avot 2:8:verdict"),     # the same image
    ("rabbi-elazar-b-arakh", "Avot 2:14"),                # answering the unbeliever (apikoros)
    ("rabbi-dostai-b-r-yannai", "Avot 3:8"),              # forgetting one's study is a sin of the soul
    ("rabbi-meir", "Avot 3:8:inname"),                    # the same, quoted in his name
    ("rabbi-yohanan-b-berokah", "Avot 4:4"),              # desecrating the Name in secret
    ("hillel", "Avot 4:5"),                               # 'one who uses the crown'
    ("rabbi-yishmael-b-yose", "Avot 4:7"),                # shunning judicial office
    ("rabbi-yehudah-b-ilai", "Avot 4:13"),                # an error in study is an intentional sin
    ("rabbi-shimon-b-menasya", "Avot 6:8"),               # the seven qualities fulfilled in Rebbi and his sons
}
out = {k: [it for it in v if (k, it["ref"]) not in DROP and (k, it["ref"] + ":" + it["kind"]) not in DROP] for k, v in out.items()}
out = {k: v for k, v in out.items() if v}
for v in out.values(): v.sort(key=lambda it: tuple(int(x) for x in it["ref"].split()[1].split(":")))   # in the order of the book (stable within a mishnah)

def bare(t):
    """The words of the saying alone: drop the 'Rabbi X says:' lead-in, and turn inner double quotes into single ones (the page wraps the whole in double quotes)."""
    m = re.match(r"^([^:\u201c\"]{0,170}\b(?:says?|said|saying)\b[^:\u201c\"]{0,80}:)\s*", t, re.I)
    if m: t = t[m.end():]
    t = t[0].upper() + t[1:]
    t = re.sub(r'[\u201c"]([^\u201c\u201d"]*)[\u201d"]', "\u2018\\1\u2019", t)
    return t.replace("\u2019\u2019", "\u2019").replace(",\u2018", ", \u2018")
PROOF = re.compile(r",?\s*(?:and (?:thus|so) with David it says|as it is (?:said|written|stated)|as it says|for it is said),?\s*(?:\([^)]*\):?)?\s*\u2018[^\u2019]*\u2019(?:\s*\([^)]*\))?")
def drop_proof(t):
    """Prooftexts ('as it is said (Isaiah 28:8): ...') are cut (author's rule): an ellipsis where more of the saying follows, a full stop where it ends."""
    while True:
        m = PROOF.search(t)
        if not m: return t
        before, rest = t[:m.start()].rstrip(" ,;"), t[m.end():]
        if re.match(r"\s*\.", rest or ".") or not rest.strip():   # the verse ended the sentence: a full stop
            rest = re.sub(r"^\s*\.\s*", "", rest)
            t = before + "." + (" " + rest if rest else "")
        else:                                                      # the saying goes on: an ellipsis
            t = before + "... " + rest.strip()
for v in out.values():
    for it in v:
        it["en"] = drop_proof(bare(it["en"])).replace("table of the Omnipresent, blessed be He.", "table of the Omnipresent.")
        if it["en"].startswith("\u2018") and it["en"].endswith("\u2019"): it["en"] = it["en"][1:-1]   # a saying that is itself one quotation
        it["en"] = re.sub(r"^\((?:[1-3] )?[A-Z][a-z]+ \d+:\d+(?:-\d+)?\)\s*", "", it["en"])   # Shmuel haKatan's saying is a verse: no reference in front
json.dump(out, open("outline/sages/avot.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "sages,", sum(len(v) for v in out.values()), "quotations,", sum(1 for v in out.values() for i in v if i.get("en_src")), "of them our own rendering")
