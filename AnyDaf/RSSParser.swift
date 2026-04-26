import Foundation

struct ParsedItem {
    let tractate: String?
    let daf: Double?
    let audioURL: String
}

// Maps feed title names to canonical names used in allTractates
private let feedToCanonical: [String: String] = [
    "eruvin":       "Eiruvin",
    "menahot":      "Menachot",
    "zevachim":     "Zevachim",
    "zevahim":      "Zevachim",
    "taanit":       "Ta\u{2019}anit",
    "meilah":       "Me'ilah",
    "berachot":     "Berakhot",
    "berachos":     "Berakhot",
    "brachot":      "Berakhot",
    "shabbos":      "Shabbat",
    "kesubos":      "Ketubot",
    "shevuos":      "Shevuot",
    "moed katan":   "Moed Katan",
    "avodah zarah": "Avodah Zarah",
    "avoda zara":   "Avodah Zarah",
    "megilah":      "Megillah",
    "rosh hashana": "Rosh Hashanah",
    "rosh hashanah":"Rosh Hashanah",
    "bava kama":    "Bava Kamma",
    "bava metzia":  "Bava Metzia",
    "bava batra":   "Bava Batra",
    "middos":       "Middot",
    "middoth":      "Middot",
]

func canonicalTractate(feedName: String) -> String? {
    let lower = feedName.lowercased()
        .replacingOccurrences(of: "'", with: "")
        .trimmingCharacters(in: .whitespaces)
    if let mapped = feedToCanonical[lower] { return mapped }
    return allTractates.first(where: {
        $0.name.lowercased().replacingOccurrences(of: "'", with: "") == lower
    })?.name
}

class RSSParser: NSObject, XMLParserDelegate {
    private let xmlParser: XMLParser
    private(set) var items: [ParsedItem] = []
    private(set) var nextPageURL: URL?

    private var inItem = false
    private var inTitle = false
    private var currentTitle = ""
    private var currentAudioURL = ""

    init(data: Data) {
        xmlParser = XMLParser(data: data)
        super.init()
        // Enable both namespace modes so atom:link is caught whether the
        // parser sees it as "link" (namespaced) or "atom:link" (prefixed).
        xmlParser.shouldProcessNamespaces = true
        xmlParser.shouldReportNamespacePrefixes = true
        xmlParser.delegate = self
    }

    func parse() {
        xmlParser.parse()
    }

    // MARK: - XMLParserDelegate

    func parser(_ parser: XMLParser,
                didStartElement element: String,
                namespaceURI: String?,
                qualifiedName qName: String?,
                attributes: [String: String] = [:]) {
        // element is the local name when namespace processing is on;
        // qName is the prefixed name ("atom:link"). Check both.
        let isLinkElement = element == "link" || element == "atom:link"
                         || qName == "atom:link" || qName == "link"

        switch element {
        case "item":
            inItem = true
            currentTitle = ""
            currentAudioURL = ""
        case "title" where inItem:
            inTitle = true
        case "enclosure" where inItem:
            currentAudioURL = attributes["url"] ?? ""
        default:
            if isLinkElement, !inItem,
               attributes["rel"] == "next",
               let href = attributes["href"] {
                nextPageURL = URL(string: href)
            }
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        if inTitle { currentTitle += string }
    }

    func parser(_ parser: XMLParser,
                didEndElement element: String,
                namespaceURI: String?,
                qualifiedName qName: String?) {
        switch element {
        case "item":
            inItem = false
            if let parsed = parseTitle(currentTitle) {
                items.append(ParsedItem(tractate: parsed.tractate, daf: parsed.daf, audioURL: currentAudioURL))
            }
        case "title":
            inTitle = false
        default:
            break
        }
    }

    // MARK: - Title parsing

    // Titles look like: "Menachot 48 (5786)" or "Menahot 29b (5786)" or "Berakhot 5b-6a"
    // Returns daf as Double: N+0.0 for a-side (plain or explicit "a"), N+0.5 for b-side.
    private func parseTitle(_ title: String) -> (tractate: String, daf: Double)? {
        // Strip the year suffix
        let cleaned = title.replacingOccurrences(
            of: #"\s*\(\d+\)\s*$"#, with: "", options: .regularExpression
        ).trimmingCharacters(in: .whitespaces)

        let parts = cleaned.split(separator: " ")
        guard parts.count >= 2 else { return nil }

        let dafToken = String(parts.last!)
        let digits = dafToken.prefix(while: { $0.isNumber })
        guard let base = Int(digits), base > 0 else { return nil }

        // "b" suffix (or range starting at b like "5b-6a") → half-daf
        let afterDigits = dafToken.dropFirst(digits.count).lowercased()
        let isHalf = afterDigits.hasPrefix("b")
        let daf = Double(base) + (isHalf ? 0.5 : 0.0)

        let feedName = parts.dropLast().joined(separator: " ")
        guard let canonical = canonicalTractate(feedName: feedName) else { return nil }

        return (canonical, daf)
    }
}
