import Foundation

struct Tractate: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let startDaf: Int
    let endDaf: Int
    /// 0 = amud aleph (a), 1 = amud bet (b). Tamid starts at 25b.
    let startAmud: Int

    init(name: String, startDaf: Int, endDaf: Int, startAmud: Int = 0) {
        self.name = name
        self.startDaf = startDaf
        self.endDaf = endDaf
        self.startAmud = startAmud
    }

    var dafRange: [Int] {
        Array(startDaf...endDaf)
    }
}

let allTractates: [Tractate] = [
    // Seder Zeraim
    Tractate(name: "Berakhot",      startDaf: 2,  endDaf: 64),
    // Seder Moed
    Tractate(name: "Shabbat",       startDaf: 2,  endDaf: 157),
    Tractate(name: "Eiruvin",       startDaf: 2,  endDaf: 105),
    Tractate(name: "Pesachim",      startDaf: 2,  endDaf: 121),
    Tractate(name: "Shekalim",      startDaf: 2,  endDaf: 22),
    Tractate(name: "Rosh Hashanah", startDaf: 2,  endDaf: 35),
    Tractate(name: "Yoma",          startDaf: 2,  endDaf: 88),
    Tractate(name: "Sukkah",        startDaf: 2,  endDaf: 56),
    Tractate(name: "Beitzah",       startDaf: 2,  endDaf: 40),
    Tractate(name: "Ta\u{2019}anit", startDaf: 2,  endDaf: 31),
    Tractate(name: "Megillah",      startDaf: 2,  endDaf: 32),
    Tractate(name: "Moed Katan",    startDaf: 2,  endDaf: 29),
    Tractate(name: "Chagigah",      startDaf: 2,  endDaf: 27),
    // Seder Nashim
    Tractate(name: "Yevamot",       startDaf: 2,  endDaf: 122),
    Tractate(name: "Ketubot",       startDaf: 2,  endDaf: 112),
    Tractate(name: "Nedarim",       startDaf: 2,  endDaf: 91),
    Tractate(name: "Nazir",         startDaf: 2,  endDaf: 66),
    Tractate(name: "Sotah",         startDaf: 2,  endDaf: 49),
    Tractate(name: "Gittin",        startDaf: 2,  endDaf: 90),
    Tractate(name: "Kiddushin",     startDaf: 2,  endDaf: 82),
    // Seder Nezikin
    Tractate(name: "Bava Kamma",    startDaf: 2,  endDaf: 119),
    Tractate(name: "Bava Metzia",   startDaf: 2,  endDaf: 119),
    Tractate(name: "Bava Batra",    startDaf: 2,  endDaf: 176),
    Tractate(name: "Sanhedrin",     startDaf: 2,  endDaf: 113),
    Tractate(name: "Makkot",        startDaf: 2,  endDaf: 24),
    Tractate(name: "Shevuot",       startDaf: 2,  endDaf: 49),
    Tractate(name: "Avodah Zarah",  startDaf: 2,  endDaf: 76),
    Tractate(name: "Horayot",       startDaf: 2,  endDaf: 14),
    // Seder Kodashim
    Tractate(name: "Zevachim",     startDaf: 2,  endDaf: 120),
    Tractate(name: "Menachot",      startDaf: 2,  endDaf: 110),
    Tractate(name: "Hullin",        startDaf: 2,  endDaf: 142),
    Tractate(name: "Bekhorot",      startDaf: 2,  endDaf: 61),
    Tractate(name: "Arakhin",       startDaf: 2,  endDaf: 34),
    Tractate(name: "Temurah",       startDaf: 2,  endDaf: 34),
    Tractate(name: "Keritot",       startDaf: 2,  endDaf: 28),
    Tractate(name: "Meilah",        startDaf: 2,  endDaf: 22),
    Tractate(name: "Kinnim",        startDaf: 22, endDaf: 25),
    Tractate(name: "Tamid",         startDaf: 25, endDaf: 33, startAmud: 1),
    Tractate(name: "Middot",        startDaf: 34, endDaf: 37),
    // Seder Taharot
    Tractate(name: "Niddah",        startDaf: 2,  endDaf: 73),
]
