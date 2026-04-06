package com.anydaf.model

data class Tractate(
    val name: String,
    val startDaf: Int,
    val endDaf: Int,
    /** 0 = amud aleph (a), 1 = amud bet (b). Tamid starts at 25b. */
    val startAmud: Int = 0
) {
    val dafRange: List<Int> get() = (startDaf..endDaf).toList()
}

val allTractates: List<Tractate> = listOf(
    // Seder Zeraim
    Tractate("Berakhot",      2,  64),
    // Seder Moed
    Tractate("Shabbat",       2,  157),
    Tractate("Eiruvin",       2,  105),
    Tractate("Pesachim",      2,  121),
    Tractate("Shekalim",      2,  22),
    Tractate("Rosh Hashanah", 2,  35),
    Tractate("Yoma",          2,  88),
    Tractate("Sukkah",        2,  56),
    Tractate("Beitzah",       2,  40),
    Tractate("Ta\u2019anit",  2,  31),
    Tractate("Megillah",      2,  32),
    Tractate("Moed Katan",    2,  29),
    Tractate("Chagigah",      2,  27),
    // Seder Nashim
    Tractate("Yevamot",       2,  122),
    Tractate("Ketubot",       2,  112),
    Tractate("Nedarim",       2,  91),
    Tractate("Nazir",         2,  66),
    Tractate("Sotah",         2,  49),
    Tractate("Gittin",        2,  90),
    Tractate("Kiddushin",     2,  82),
    // Seder Nezikin
    Tractate("Bava Kamma",    2,  119),
    Tractate("Bava Metzia",   2,  119),
    Tractate("Bava Batra",    2,  176),
    Tractate("Sanhedrin",     2,  113),
    Tractate("Makkot",        2,  24),
    Tractate("Shevuot",       2,  49),
    Tractate("Avodah Zarah",  2,  76),
    Tractate("Horayot",       2,  14),
    // Seder Kodashim
    Tractate("Zevachim",      2,  120),
    Tractate("Menachot",      2,  110),
    Tractate("Hullin",        2,  142),
    Tractate("Bekhorot",      2,  61),
    Tractate("Arakhin",       2,  34),
    Tractate("Temurah",       2,  34),
    Tractate("Keritot",       2,  28),
    Tractate("Meilah",        2,  22),
    Tractate("Kinnim",        22, 25),
    Tractate("Tamid",         25, 33, startAmud = 1),
    Tractate("Middot",        34, 37),
    // Seder Taharot
    Tractate("Niddah",        2,  73),
)
