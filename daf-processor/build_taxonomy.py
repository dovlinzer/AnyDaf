#!/usr/bin/env python3
"""
Build a unified seed taxonomy for the AnyDaf topical index.

Combines multiple authoritative sources across 4 focused segments,
then merges into a single seed_taxonomy.json.

Usage:
  python build_taxonomy.py --segment 1   # Halakha: Temple, Shabbat, Purity, Kashrut, Agriculture, Prayer, Civil
  python build_taxonomy.py --segment 2   # Family, Courts, Criminal, Ethics, Interpersonal
  python build_taxonomy.py --segment 3   # Aggada, Theology, Biblical Figures, History, Geography
  python build_taxonomy.py --segment 4   # Talmudic Methodology, Rabbinic Authorities
  python build_taxonomy.py --merge       # Combine all segment files → seed_taxonomy.json
  python build_taxonomy.py               # Run all segments + merge
  python build_taxonomy.py --save-partial  # Salvage seed_taxonomy.raw.txt → segment_1.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 32000


# ---------------------------------------------------------------------------
# Source material
# ---------------------------------------------------------------------------

RAMBAM_STRUCTURE = """
RAMBAM — MISHNEH TORAH: 14 Books

Book 1: Mada (Knowledge) — theology, character, Torah study, idolatry, repentance
Book 2: Ahavah (Love) — Shema, Prayer, Tefillin, Mezuzah, Tzitzit, Blessings, Circumcision
Book 3: Zmanim (Times) — Shabbat, Eruvin, Yom Kippur, Yom Tov, Pesach, Sukkot/Shofar/Lulav, Rosh Chodesh, Fast Days, Megillah/Chanukah
Book 4: Nashim (Women) — Marriage (Ishut), Divorce (Gerushin), Yibbum/Chalitzah, Sotah
Book 5: Kedushah (Holiness) — Forbidden Relations, Forbidden Foods (Maachalot Assurot), Shechitah
Book 6: Haflaah (Separation) — Oaths (Shevuot), Vows (Nedarim), Nazirite (Nezirut), Valuations (Arachim)
Book 7: Zeraim (Agriculture) — Kilayim, Gifts to the Poor, Terumot, Maasrot, Maaser Sheni, Bikkurim, Shemitah/Yovel
Book 8: Avodah (Temple Service) — Beit haBechira, Temple Vessels, Temple Entry, Altar Laws, Sacrifices, Daily Offerings, Meilah
Book 9: Korbanot (Offerings) — Korban Pesach, Chagigah, Bechorot, Unintentional Sins, Temurah
Book 10: Taharah (Purity) — Corpse Impurity, Red Heifer, Leprosy, Zavim, Niddah, Kelim, Mikvaot
Book 11: Nezikin (Damages) — Property Damage, Theft, Robbery/Lost Objects, Wounding, Murder
Book 12: Kinyan (Acquisition) — Sales, Gifts, Neighbors, Agents/Partners, Slaves
Book 13: Mishpatim (Civil Law) — Rental, Borrowing/Deposits, Loans, Plaintiff/Defendant, Inheritance
Book 14: Shoftim (Judges) — Courts/Penalties, Testimony, Rebellious Ones, Mourning, Kings/Wars
"""

SHULCHAN_ARUCH_STRUCTURE = """
SHULCHAN ARUCH:
- Orach Chaim: Prayer, Shabbat, Holidays, daily practice
- Yoreh Deah: Kashrut, Niddah/Family Purity, Tzedakah, Mourning, Vows, Idolatry, Ribbit
- Even HaEzer: Marriage, Divorce, Yibbum, Family law
- Choshen Mishpat: Courts, Loans, Sales, Partnerships, Damages, Theft, Inheritance
"""

WEBSHAS_FAMILY_COURTS = """
WebShas entries relevant to Family, Courts, Criminal Law, Ethics, Interpersonal:

From A: Agunah, Adultery and Sexual Immorality, Arbitration, Arevut
From B: Bankruptcy and creditors, Beelah, Ben Sorer UMoreh, Bills and Documents
From C: Capital Punishment, Capital Punishment Case Procedure, Chalitzah, Circumstances Evidence,
  Conflicts of Interest in Court, Conjugal rights and responsibilities, Contraception,
  Conversion, Court Appraisal of Value, Court Scribe, Courtroom Procedure, Courts, Cross-dressing
From D: Dan leKaf Zechut, Dayyan Mumcheh, Deaf and mute people in business, Deathbed gifts,
  Declaration of War, Dinei Nefashot, Divorce
From E: Edim Zomimin, Eglah Arufah, Ein ed naaseh dayyan, Embarrassing others,
  Employer/Employee relations, Erkaot, Eved Ivri, Eved Kenaani, Extra-judicial punishment
From F: Fairness, False Testimony, Family Psychology, Fines, Flogging, Forgiveness
From G: Gambling, Geneivah, Gerama, Gerut, Get (divorce document), Get al tenai, Get me'useh,
  Gezeilah, Gifts, Guaranteeing a loan, Guardians of Property
From H: Hashavat Aveidah, Hatraah, Heirs, Hermaphrodites, Hesped, Hezek Ri'eeyah, Honest weights
From I: Imprisonment, Incest, Inheritance, Interest on loans, Intermarriage
From J: Jealousy, Judicial malpractice, Judicial System, Jurisprudence, Judging others favorably
From K: Katan, Katlanit, Ketubah, Kiddushin, Kinyanim (acquisition methods), Kings
From L: Lashon Hara, Lav she'ein bo maaseh, Lawyers, Leasing, Legal Documents, Legal Guardian,
  Liability for damage caused by my property, Libel, Liens, Lifnei Iver, Lifnim MiShurat haDin,
  Lineage, Loans
From M: Maalah asu b'yuchsin, Matan b'Seter, Mamzer, Marital psychology, Marriage, Mechilah,
  Mekach Taut, Minors in Transactions, Misleading people, Modeh beMiktzat, Modest Behavior,
  Mordechai, Moser, Motzi Shem Ra, Mourning Issues, Murder
From N: Nazirite, Nedarim, Nichum Aveilim, Niddah Issues, Nisuin
From O: Oaths, Onaah, Onaat Devarim, Onah, Oral loans
From P: Pain, Palgais, Polygamy, Pregnancy, Pre-marital relations, Price gouging,
  Prozbul, Pru uRvu, Psak, Psychology
From R: Rage, Rape, Rebellious Son, Rebuke, Receipts, Redeeming captives, Rental, Repentance,
  Rescinding Vows, Reward and Punishment, Ribbit
From S: Sales, Second Marriages, Secular courts, Seduction, Shalom Bayit, Shanah Rishonah,
  Shidduch, Shoteh, Shutafin, Sichah beteilah, Slander, Social Contract, Sotah,
  Stam Yeinam, Subpeonas, Suicide
From T: Testimony, Theft, Tochachah
From W: War, Witnesses
From Y: Yibbum, Yichud, Yerushah
"""

WEBSHAS_AGGADA_HISTORY = """
WebShas entries relevant to Aggada, Theology, Biblical Figures, History, Geography:

From A: Aaron, Abraham, Adam and Eve, Amulets, Angels, Apikorsut, Astrology, Astronomy,
  Atonement, Awe of Heaven
From B: Babylon, Babylonian Captivity, Bat Kol, Bayit Rishon, Bayit Sheni, Bayit Sh'lishi,
  Bechirah chofshit, Belshazzar, Beriat haOlam, Biblical Names, Boethusians
From C: Cemetery, Cities of Israel, City of Refuge
From D: Daniel, Death: Beyond the Laws, Depression, Dreams, Drunkenness, Dying
From E: Elisha the Prophet, Eliyahu the Prophet (natural lifetime), Eliyahu the Prophet (after),
  Esther, Evil Eye, Exile, Ezra
From F: Family Psychology, Fear and Worry, Free Will, The Flood of the Bible
From G: Gan Eden, God, God's Names, Gehennom, Ghosts, Gog and Magog, Gratitude
From H: Hakarat haTov, Haman, Hashgachah Pratit, Hebrew Language, Hester Panim, Holiness,
  Honoring a Deceased Person's Wishes, Honoring Elders, Honoring Living Things, Human nature,
  Humility
From I: Idolatry, In-gathering of exiles, Isaac, Isaiah, Israel, Iyov (Job)
From J: Jacob, Jerusalem, Job, Joshua, Judea
From K: Kedushah, Kiddush Hashem, Kiddush Levanah
From L: Life After Death, Lo Tachmod, Lost Tribes, Lying
From M: Malachim (angels), Manifestation of God, Manna, Manners, Mashiach, Matan Torah,
  Mazal, Mazikin, Memory, Men of the Great Assembly, Messiah, Miracles, Moses
From N: Near Death Experiences, Neshamah, Nevuah (prophecy), Noah
From O: Olam haBa, Omens, Origin of the Universe
From P: Pacifism, Peace, Political Leaders of the Jewish People, Prophecy
From R: Red Sea, Reish Galuta, Resurrection of the Dead, Revelation at Sinai
From S: Sadducees, Sages of the Gemara, Sages of the Mishnah, Satan, Seances, Self-righteousness,
  Sheidim, The Soul, Speaking with the dead, Supernatural phenomena
From T: Tannaim, The Third Temple
From Y: Yeravam ben Nevat, Yetzer haTov and Yetzer haRa, Yosef Sheida, Yoshiyahu
"""

WEBSHAS_METHODOLOGY_AUTHORITIES = """
WebShas entries relevant to Talmudic Methodology, Principles, and Authorities:

From A: Amoraim, Asmachta (transactions), Asmachta (exegesis)
From B: Baraita, Batlah daato eitzel kol adam, Bereirah
From C: Chazakah, Circumstantial Evidence
From D: Dibrah Torah k'Lshon Bnei Adam, Dichuy, Dina d'Malchuta Dina
From E: Ein issur chal al issur, Ein maavirin al haMitzvot, Ein omrin l'adam Chatay bishvil sheyizkeh,
  Ein osin mitzvot chavilot chavilot, Ein ruach chachamim nochah heimenu, Ein shaliach l'dvar aveirah
From G: Gematria, Gezeirah l'Gezeirah, Gezeirah Shavah, Gezeirot v'Takkanot, Guzma
From H: Haalchah leMoshe miSinai, Hermeneutics, Ho'il
From I: Ibbur Shanah, Intercalation, Israel vs. Bavel, Issur Kollel and Issur Mosif
From K: Kal vaChomer, Kelal uPerat, Kol d'parish meiRuba parish, Kol haRa'uy l'beelah,
  Kol kavua k'mechetzah al mechetzah dami, Koach d'hetera adif
From L: Lav haBa michlal Aseh, Lav haNitak la'Aseh, Lav haNitan l'Azharat Mitat Beit Din,
  Lav shebiChlalot, Lavud, Lehodia kochan, Lo Mibaya, Lo Plug
From M: Minhag, Minhag haMedinah, Miluim, Milta d'lo schechicha lo gazru beih rabbanan,
  Min b'Mino and Min b'she'Eino Mino, Mitasek, Mitzvah haba'ah ba'Aveirah,
  Mitzvah min haMuvchar, Mitzvot aseh shehaZ'man gerama, Mutav sheyihyu shogigin
From O: Oness rachmana patreih
From P: Psik Reisha
From R: Rabbinic edicts, Rabbinic enactments, Rabbinic law, Rov and Miut
From S: Safek d'Orayta/d'Rabbanan, Sages, Sfek Sfeika, Stam mishnah
From T: Talmudic exaggeration, Talmudic lists, Talmudic Methodology, Tannaim, Toch Kedei Dibbur
From U: Urim veTummim, Uvda d'Chol beShabbat v'Yom Tov
"""

WEBSHAS_ALL = None  # loaded from file

TALMUDIC_PRINCIPLES = """
TALMUDIC HERMENEUTICAL PRINCIPLES (13 Middot of Rabbi Yishmael):
1. Kal vaChomer (a fortiori inference)
2. Gezerah Shavah (verbal analogy)
3. Binyan Av (building a general principle)
4. Kelal uFerat (general and particular)
5. Perat uKlal (particular and general)
6. Kelal uFerat uKlal
7. Kelal shehu tzarich liPerat
8. Perat shehu tzarich liKlal
9-11. Exceptions from general rules (3 variants)
12. Davar haLamed meInyano (inference from context)
13. Shnei Ketuvim haMachishim (two contradictory verses)

KEY TALMUDIC LEGAL PRINCIPLES:
Safek (doubt) | Sfek Sfeika (double doubt) | Rov (majority) | Chazakah (presumptive status)
Umdena (logical assumption) | Breira (retroactive clarification) | Kavua (fixed status)
Ein shaliach l'dvar aveirah | Lifnei iver | Grama | Davar she'eino mitkavein
Psik Reisha | Melacha she'einah tzerichah l'gufah | Mutav sheyihyu shogigin
Ho'il | Lo Plug | Miggo | Umdena de'mukhach | Hekesh
Deorayta vs. Derabanan | Takkanah | Gezeirah | Minhag | Hora'at Sha'ah
Aseh docheh lo taaseh | Lav haNitak la'aseh | Issur Chal al Issur
Issur Kolel | Issur Mosif | Ein maavirin al hamitzvot | Zerizin makdimin
Ha'oseh b'mitzvah patur | Mitzvah haba'ah ba'aveirah | Kol kavua | Kol DeParish
Davar sheb'minyan | Halachah leMoshe miSinai | Dibrah Torah kilshon bnei adam
Stam Mishnah | Baraita | Teku (unresolved) | Miggo | Shibuda d'Rabbi Natan

TALMUDIC REASONING TERMS:
Ibaya lehu | Teiku | Taku | Aseh docheh | Lo Plug | Kofin | Lifnim miShurat haDin
"""

AGGADIC_CATEGORIES = """
AGGADIC AND NARRATIVE CATEGORIES:

CREATION AND COSMOLOGY: Beriat haOlam, Six Days of Creation, Gan Eden, Adam and Eve, Flood,
Tower of Babel, Heavenly realms, Celestial bodies, Angels/Malachim, Satan/Yetzer haRa,
Demons/Sheidim, Afterlife/Olam haBa, Gehinnom, Resurrection/Techiyat haMeitim,
Messianic Era, End of Days/Acharit haYamim

DIVINE THEMES: Divine Providence/Hashgachah Pratit, Reward and Punishment/Sachar vaOnesh,
Prophecy/Nevuah, Divine Names and Attributes, Miracles/Nissim, Revelation at Sinai/Matan Torah,
Hidden Face of God/Hester Panim, Love and Fear of God, Free Will/Bechirah Chofshit

BIBLICAL NARRATIVES: Patriarchs (Abraham, Isaac, Jacob), Matriarchs (Sarah, Rebecca, Rachel, Leah),
Moses and Exodus, Aaron, Miriam, Joshua and conquest, Judges period, King Saul, King David,
King Solomon, Major Prophets (Elijah, Elisha, Isaiah, Jeremiah, Ezekiel), Twelve Tribes,
Esther and Mordechai, Daniel, Ezra and Nehemiah, Job/Iyov

ETHICAL AND WISDOM: Humility/Anavah, Arrogance, Jealousy/Kinah, Gratitude/Hakarat haTov,
Repentance/Teshuvah, Character/Mussar, Yetzer haTov and Yetzer haRa, Friendship,
Wealth and Poverty, Suffering, Embarrassing others, Flattery/Chanifah

ESCHATOLOGY: Gog and Magog, Mashiach/Messiah, Kibbutz Galuyot, Third Temple/Bayit Shlishi,
World to Come/Olam haBa

JEWISH HISTORY: Egyptian bondage and Exodus, Wilderness period, First Temple/Bayit Rishon,
Babylonian exile, Second Temple/Bayit Sheni, Hasmonean period, Roman period, Churban/Destruction
"""

AUTHORITIES_BY_ERA = """
RABBINIC AUTHORITIES BY ERA:

TANNAIM (10-220 CE): Hillel, Shammai, Rabban Gamliel, Rabban Yochanan ben Zakkai,
Rabbi Eliezer ben Hyrcanus, Rabbi Yehoshua, Rabbi Akiva, Rabbi Yishmael, Rabbi Tarfon,
Rabbi Meir, Rabbi Yehudah bar Ilai, Rabbi Shimon bar Yochai, Rabbi Yosi bar Chalafta,
Rabbi Elazar ben Azaryah, Ben Azzai, Ben Zoma, Rabbi Yehudah haNasi (Rebbi), Bar Kappara

PALESTINIAN AMORAIM (220-375 CE): Rabbi Yochanan bar Nafcha, Reish Lakish,
Rabbi Chanina, Rabbi Oshiya, Rabbi Yannai, Rabbi Yehoshua ben Levi, Rabbi Elazar ben Pedat,
Rabbi Ami, Rabbi Asi, Rabbi Abbahu, Rav Zeira, Rabbi Jeremiah, Rabbi Mana

BABYLONIAN AMORAIM (220-500 CE):
1st-2nd gen: Rav (Abba Areka), Shmuel, Rav Huna, Rav Yehudah bar Yechezkel,
  Rav Chisda, Rav Sheshet, Rav Nachman bar Yaakov
3rd gen: Rabba bar Nachmani, Rav Yosef, Rav Nachman bar Yitzchak
4th gen: Abaye, Rava
5th gen: Rav Papa, Rav Ashi, Ravina

GEONIM (600-1050): Rav Saadia Gaon, Rav Hai Gaon, Rav Sherira Gaon, Rav Amram Gaon

RISHONIM (1050-1500):
- Rashi (France, 1040-1105)
- Rabbenu Tam / Tosafot (France, 1100-1171)
- Ri / Tosafot (France, 1120-1200)
- Rif / Alfasi (Morocco/Spain, 1013-1103)
- Rambam / Maimonides (Spain/Egypt, 1138-1204)
- Ramban / Nachmanides (Spain/Israel, 1194-1270)
- Rashba (Spain, 1235-1310)
- Rosh (Germany/Spain, 1259-1327)
- Tur (Spain, 1269-1343)
- Ritva (Spain, 1250-1330)
- Meiri (France, 1249-1310)
- Ran (Spain, 1320-1376)
- Mordechai (Germany, 1250-1298)
- Sefer haChinuch (Spain, 13th c.)

ACHARONIM (1500-present):
- Beit Yosef / Shulchan Aruch — Rabbi Yosef Karo (1488-1575)
- Rama — Rabbi Moshe Isserles (Poland, 1530-1572)
- Maharsha — Rabbi Shmuel Eidels (Poland, 1555-1631)
- Maharshal — Rabbi Shlomo Luria (Poland, 1510-1573)
- Magen Avraham (Poland, 1633-1683)
- Sha'agat Aryeh (Lithuania, 1695-1785)
- Vilna Gaon / GRA (Lithuania, 1720-1797)
- Chatam Sofer (Hungary, 1762-1839)
- Aruch HaShulchan (Russia, 1829-1908)
- Mishnah Berurah / Chofetz Chaim (Poland, 1838-1933)
- Chazon Ish (Israel, 1878-1953)
"""

MITZVOT_CATEGORIES = """
613 MITZVOT CATEGORIES: Belief/Fundamentals, Torah Study/Teaching, Prayer/Temple Service,
Signs and Symbols (Tefillin/Mezuzah/Tzitzit), Shabbat and Holidays (24 mitzvot),
Circumcision, Birkat haMazon/Priestly Blessing, Dietary Laws (kashrut - 34 mitzvot),
Agriculture and Land (sabbatical/jubilee/tithes/gleanings - 28 mitzvot),
Temple and Offerings (71 mitzvot), Purity Laws (23 mitzvot),
Marriage and Family (35 mitzvot), Nazirite (4), Vows and Oaths (7),
Judicial System (32 mitzvot), Civil Law/Commerce (56), Workers and Slaves (18),
Tzedakah/Poor (8), Treatment of Others (21), Mourning/Death (5),
Kingship (3), Prophets (3), Idolatry (47), War (6)
"""


# ---------------------------------------------------------------------------
# Segment definitions
# ---------------------------------------------------------------------------

SEGMENTS = {
    1: {
        "name": "Halakha — Temple, Shabbat, Purity, Kashrut, Agriculture, Prayer, Civil",
        "focus_categories": [
            "PRAYER AND LITURGY",
            "SHABBAT AND HOLIDAYS",
            "TEMPLE AND SACRIFICES",
            "PURITY AND IMPURITY",
            "AGRICULTURE AND TITHES",
            "KASHRUT",
            "CIVIL AND COMMERCIAL LAW",
            "RITUAL OBJECTS AND SIGNS",
            "KOHANIM AND LEVITES",
        ],
        "target_entries": 400,
    },
    2: {
        "name": "Family, Courts, Criminal Law, Ethics, Interpersonal",
        "focus_categories": [
            "FAMILY AND PERSONAL STATUS",
            "MARRIAGE AND DIVORCE",
            "COURTS AND JURISPRUDENCE",
            "CRIMINAL AND CAPITAL LAW",
            "INTERPERSONAL ETHICS",
            "MONETARY AND PROPERTY LAW",
            "PERSONAL VOWS AND OATHS",
            "SLAVERY AND SERVITUDE",
        ],
        "target_entries": 400,
    },
    3: {
        "name": "Aggada, Theology, Biblical Figures, History, Geography",
        "focus_categories": [
            "AGGADA AND THEOLOGY",
            "DIVINE ATTRIBUTES AND THEMES",
            "BIBLICAL FIGURES AND NARRATIVES",
            "ESCHATOLOGY AND AFTERLIFE",
            "JEWISH HISTORY",
            "ETHICS AND CHARACTER",
            "GEOGRAPHY AND PLACES",
        ],
        "target_entries": 350,
    },
    4: {
        "name": "Talmudic Methodology, Hermeneutics, Rabbinic Authorities",
        "focus_categories": [
            "TALMUDIC METHODOLOGY",
            "HERMENEUTICAL PRINCIPLES",
            "RABBINIC INSTITUTIONS AND COURTS",
            "RABBINIC AUTHORITIES — TANNAIM",
            "RABBINIC AUTHORITIES — AMORAIM",
            "RABBINIC AUTHORITIES — GEONIM AND RISHONIM",
            "RABBINIC AUTHORITIES — ACHARONIM",
        ],
        "target_entries": 300,
    },
}


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def load_webshas(taxonomy_dir: Path) -> str:
    path = taxonomy_dir / "webshas_entries_raw.txt"
    if not path.exists():
        print(f"WARNING: {path} not found")
        return ""
    return path.read_text(encoding="utf-8")


def build_segment_prompt(segment_num: int, webshas_text: str) -> str:
    seg = SEGMENTS[segment_num]
    categories_str = "\n".join(f"  - {c}" for c in seg["focus_categories"])

    # Select relevant source material per segment
    if segment_num == 1:
        extra_sources = f"""
### Rambam Books (relevant):
{RAMBAM_STRUCTURE}

### Shulchan Aruch (relevant):
{SHULCHAN_ARUCH_STRUCTURE}

### 613 Mitzvot categories:
{MITZVOT_CATEGORIES}

### WebShas complete index (use entries relevant to YOUR focus categories):
{webshas_text}
"""
    elif segment_num == 2:
        extra_sources = f"""
### Rambam Books 4, 6, 11, 12, 13, 14 (relevant to family/courts/civil):
Book 4: Nashim — Marriage (Ishut), Divorce (Gerushin), Yibbum/Chalitzah, Sotah
Book 6: Haflaah — Oaths (Shevuot), Vows (Nedarim), Nazirite, Valuations (Arachim)
Book 11: Nezikin — Property Damage, Theft (Geneivah), Robbery/Lost Objects, Wounding, Murder
Book 12: Kinyan — Sales, Gifts, Neighbors, Agents/Partners, Slaves
Book 13: Mishpatim — Rental, Borrowing/Deposits, Loans, Plaintiff/Defendant, Inheritance
Book 14: Shoftim — Courts/Penalties, Testimony, Mourning, Kings/Wars

### Shulchan Aruch relevant parts:
Even HaEzer: Marriage, Divorce, Yibbum, Ketubah, Conjugal rights, Sotah
Choshen Mishpat: Courts, Legal procedure, Loans, Sales, Partnerships, Theft, Damages, Inheritance

### WebShas entries relevant to family, courts, criminal, ethics, interpersonal:
{WEBSHAS_FAMILY_COURTS}
"""
    elif segment_num == 3:
        extra_sources = f"""
### Rambam Book 1 (Mada): theology, character, idolatry, repentance
### Rambam Book 14 last chapters: Melachim (Kings/Wars/Messianic era)

### Aggadic and narrative categories:
{AGGADIC_CATEGORIES}

### WebShas entries relevant to aggada, biblical figures, history, geography:
{WEBSHAS_AGGADA_HISTORY}
"""
    else:  # segment 4
        extra_sources = f"""
### Talmudic Hermeneutical Principles and Methodology:
{TALMUDIC_PRINCIPLES}

### Rabbinic Authorities by era:
{AUTHORITIES_BY_ERA}

### WebShas entries relevant to methodology and authorities:
{WEBSHAS_METHODOLOGY_AUTHORITIES}
"""

    return f"""You are building a partial seed taxonomy for a topical index of the Babylonian Talmud. This is SEGMENT {segment_num} of 4.

## Your Task for This Segment

Generate taxonomy entries ONLY for these specific categories:
{categories_str}

Do NOT include entries that clearly belong to other segments (halakha already covered in segment 1 includes: Temple, Shabbat, Prayer, Purity, Kashrut, Agriculture).

## Purpose

This taxonomy maps ~30,000 raw topic terms from 2,350 Talmud lecture transcripts into a consistent browsable index. Think of it as entries in a scholarly "Index to the Talmud" reference work.

## Source Material for This Segment

{extra_sources}

## Rules

1. **Comprehensive for your focus area**: Include all meaningful topics in your assigned categories. Be granular — specific legal concepts, specific principles, specific authorities all deserve their own entries.

2. **Deduplicated**: Merge entries that are truly the same concept. Keep legitimate distinctions.

3. **Hierarchy**: Use at most 2 levels. Most entries: parent_id = one of the focus category names (lowercase snake_case). Category headers themselves have parent_id = null.

4. **IDs**: lowercase snake_case. Hebrew terms transliterated: "beit_hamikdash", "kiddushin". English: "civil_law". Must be globally unique — prefix with category if needed (e.g., "auth_rashi", "meth_kal_vachomer").

5. **Hebrew field**: Hebrew/Aramaic script where it exists. Null for purely English concepts.

6. **For SEGMENT 4 only (authorities)**: Include EACH individual rabbinic authority as a separate entry with their period as parent_id. These are critical for "where does Rashi discuss X" lookup.

7. **Target**: approximately {seg['target_entries']} entries for this segment.

## Output Format

Return ONLY valid JSON (no explanation, no markdown fences):

{{
  "segment": {segment_num},
  "segment_name": "{seg['name']}",
  "entries": [
    {{
      "id": "example_id",
      "name": "Example Name",
      "hebrew": "עברית",
      "parent_id": null,
      "category": "CATEGORY NAME",
      "sources": ["webshas"],
      "notes": null
    }}
  ]
}}

Sources values: "webshas", "rambam", "shulchan_aruch", "mitzvot_613", "talmudic_principles", "aggada", "authorities".

Begin the JSON immediately."""


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_claude(prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    print(f"  Model: {MODEL}, max_tokens: {MAX_TOKENS}")
    print(f"  Prompt: {len(prompt):,} chars")

    chunks = []
    stop_reason = None

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
            if len(chunks) % 300 == 0:
                print(f"  streaming... {sum(len(c) for c in chunks):,} chars", end="\r", flush=True)
        message = stream.get_final_message()
        stop_reason = message.stop_reason
        usage = message.usage

    full_text = "".join(chunks)
    print(f"  received {len(full_text):,} chars          ")

    if stop_reason == "max_tokens":
        print("  WARNING: Truncated at max_tokens — JSON may be incomplete!")

    print(f"  Tokens — input: {usage.input_tokens:,}, output: {usage.output_tokens:,}")

    return full_text, stop_reason


# ---------------------------------------------------------------------------
# Parse and save segment
# ---------------------------------------------------------------------------

def parse_segment(raw: str, out_path: Path) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raw_path = out_path.with_suffix(".raw.txt")
        raw_path.write_text(raw, encoding="utf-8")
        print(f"  JSON parse error: {e}")
        print(f"  Raw saved to {raw_path}")
        return None

    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(data.get("entries", []))
    print(f"  Saved {n} entries → {out_path}")
    return data


# ---------------------------------------------------------------------------
# Merge segments
# ---------------------------------------------------------------------------

def merge_segments(out_dir: Path) -> dict:
    all_entries = []
    seen_ids = {}

    for seg_num in range(1, 5):
        path = out_dir / f"segment_{seg_num}.json"
        if not path.exists():
            print(f"  WARNING: {path} not found — skipping")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        print(f"  Segment {seg_num}: {len(entries)} entries")

        for e in entries:
            eid = e.get("id", "")
            if eid in seen_ids:
                # Deduplicate: merge sources lists
                existing = seen_ids[eid]
                existing_sources = set(existing.get("sources") or [])
                new_sources = set(e.get("sources") or [])
                existing["sources"] = sorted(existing_sources | new_sources)
            else:
                seen_ids[eid] = e
                all_entries.append(e)

    taxonomy = {
        "version": "1.0",
        "generated": "2026-04-27",
        "total_entries": len(all_entries),
        "entries": all_entries,
    }

    out_path = out_dir / "seed_taxonomy.json"
    out_path.write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8")
    return taxonomy


# ---------------------------------------------------------------------------
# Save partial (salvage from truncated first run)
# ---------------------------------------------------------------------------

def save_partial(out_dir: Path):
    """Extract valid entries from seed_taxonomy.raw.txt into segment_1.json."""
    raw_path = out_dir / "seed_taxonomy.raw.txt"
    if not raw_path.exists():
        print(f"No raw file at {raw_path}")
        return

    text = raw_path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]

    # Find last complete entry by walking back to last }
    last = text.rfind("    }")
    if last == -1:
        print("Could not find last entry boundary")
        return

    truncated = text[:last + 5]  # include the closing }
    # Wrap as valid JSON array
    # Find the "entries": [ opening
    bracket = truncated.find('"entries": [')
    if bracket == -1:
        print("Could not find entries array")
        return
    entries_text = truncated[bracket + len('"entries": ['):].strip()
    # Remove trailing comma if any
    if entries_text.endswith(","):
        entries_text = entries_text[:-1]

    try:
        entries = json.loads(f"[{entries_text}]")
    except json.JSONDecodeError as e:
        print(f"Parse error: {e}")
        return

    data = {
        "segment": 1,
        "segment_name": SEGMENTS[1]["name"],
        "entries": entries,
    }
    out_path = out_dir / "segment_1.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvaged {len(entries)} entries → {out_path}")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def print_stats(taxonomy: dict):
    entries = taxonomy.get("entries", [])
    categories = {}
    for e in entries:
        cat = e.get("category", "UNKNOWN")
        categories[cat] = categories.get(cat, 0) + 1

    print()
    print("=" * 60)
    print("SEED TAXONOMY")
    print("=" * 60)
    print(f"  Total entries: {len(entries)}")
    print()
    print("BY CATEGORY:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}  {cat}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build seed taxonomy from multiple sources")
    parser.add_argument("--out-dir", default="./topic_analysis/taxonomy")
    parser.add_argument("--segment", type=int, choices=[1, 2, 3, 4],
                        help="Run a specific segment only")
    parser.add_argument("--merge", action="store_true",
                        help="Merge all segment files into seed_taxonomy.json")
    parser.add_argument("--save-partial", action="store_true",
                        help="Salvage seed_taxonomy.raw.txt into segment_1.json")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.save_partial:
        save_partial(out_dir)
        return

    if args.merge:
        print("Merging segments...")
        taxonomy = merge_segments(out_dir)
        print_stats(taxonomy)
        print(f"Wrote {out_dir / 'seed_taxonomy.json'}")
        return

    webshas_text = load_webshas(out_dir)

    segments_to_run = [args.segment] if args.segment else [1, 2, 3, 4]

    for seg_num in segments_to_run:
        out_path = out_dir / f"segment_{seg_num}.json"
        if out_path.exists() and not args.segment:
            print(f"Segment {seg_num} already exists — skipping ({out_path})")
            continue

        print(f"\nSegment {seg_num}: {SEGMENTS[seg_num]['name']}")
        prompt = build_segment_prompt(seg_num, webshas_text)
        raw, stop_reason = call_claude(prompt)

        if stop_reason == "max_tokens":
            # Try to salvage
            raw_path = out_dir / f"segment_{seg_num}.raw.txt"
            raw_path.write_text(raw, encoding="utf-8")
            print(f"  Saved raw to {raw_path} — truncated, attempting partial salvage")
            # Try parse anyway
        result = parse_segment(raw, out_path)
        if result is None and stop_reason == "max_tokens":
            print(f"  Segment {seg_num} failed — fix and re-run with --segment {seg_num}")
            if not args.segment:
                break

    if not args.segment:
        print("\nMerging all segments...")
        taxonomy = merge_segments(out_dir)
        print_stats(taxonomy)
        print(f"\nWrote {out_dir / 'seed_taxonomy.json'}")


if __name__ == "__main__":
    main()
