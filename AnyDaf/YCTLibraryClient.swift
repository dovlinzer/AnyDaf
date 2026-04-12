import Foundation

// MARK: - YCT Library name mapping

/// AnyDaf canonical names that differ from the YCT Library's WordPress taxonomy names.
let anyDafToYCT: [String: String] = [
    "Eiruvin":       "Eruvin",
    "Ta\u{2019}anit": "Taanit",
    "Hullin":        "Chullin",
    "Middos":        "Middot",
    "Moed Katan":    "Moed Katan",
    "Beitzah":      "Beitza",
    "Zevachim":       "Zevahim",
    "Rosh Hashanah": "Rosh HaShanah",
    "Bekhorot":      "Bekhorot",
    "Avodah Zarah":  "Avodah Zarah",
    "Bava Kamma":    "Bava Kamma",
    "Shevuot":       "Shevu'ot"
]

private func yctName(for tractate: String) -> String {
    anyDafToYCT[tractate] ?? tractate
}

// Non-English slug suffixes to filter out
private let nonEnglishSuffixes = ["-he", "-fr", "-sp", "-ar", "-ru", "-de", "-pt"]

// MARK: - YCT Library API Client

@MainActor
class YCTLibraryClient {

    /// Client for library.yctorah.org.
    /// Tractate terms live under a shared "Talmud" root term (ID 1899).
    static let shared = YCTLibraryClient(
        baseURL: "https://library.yctorah.org/wp-json/wp/v2",
        source: .library,
        talmudTermID: 1899,
        fetchesTractateLevel: false
    )

    /// Client for psak.yctorah.org (Rosh Yeshiva Responds).
    /// Tractate terms live at root level (no Talmud parent); articles are often tagged
    /// at the tractate level rather than a specific daf.
    static let psak = YCTLibraryClient(
        baseURL: "https://psak.yctorah.org/wp-json/wp/v2",
        source: .psak,
        talmudTermID: nil,
        fetchesTractateLevel: true
    )

    let source: YCTSource
    /// When true, articles tagged directly on the tractate term (not a daf child) are
    /// also fetched and tagged as `.tractateWide(daf: 0)`.
    let fetchesTractateLevel: Bool

    enum YCTError: LocalizedError {
        case invalidURL
        case networkError(Error)
        case decodingError

        var errorDescription: String? {
            switch self {
            case .invalidURL:          return "Invalid YCT Library URL"
            case .networkError(let e): return "Network error: \(e.localizedDescription)"
            case .decodingError:       return "Could not decode YCT Library response"
            }
        }
    }

    private let baseURL: String
    /// Term ID for the root "Talmud" node in the reference taxonomy.
    /// `nil` means tractate terms are at root level (no parent filter when searching).
    private let talmudTermID: Int?

    /// Per-session term ID caches.
    private var tractateTermCache: [String: Int] = [:]
    private var dafTermCache: [String: [Int: Int]] = [:]

    init(baseURL: String, source: YCTSource, talmudTermID: Int?, fetchesTractateLevel: Bool) {
        self.baseURL = baseURL
        self.source = source
        self.talmudTermID = talmudTermID
        self.fetchesTractateLevel = fetchesTractateLevel
    }

    // MARK: - Term Lookup (with in-session caching)

    func resolveTractateTermID(tractate: String) async throws -> Int? {
        if let cached = tractateTermCache[tractate] { return cached }
        let id = try await fetchTractateTermID(tractate: tractate)
        if let id { tractateTermCache[tractate] = id }
        return id
    }

    func resolveDafTermIDs(tractate: String, tractateTermID: Int) async throws -> [Int: Int] {
        if let cached = dafTermCache[tractate] { return cached }
        let map = try await fetchDafTermIDs(tractateTermID: tractateTermID)
        dafTermCache[tractate] = map
        return map
    }

    private func fetchTractateTermID(tractate: String) async throws -> Int? {
        let name = yctName(for: tractate)
        var components = URLComponents(string: "\(baseURL)/reference")!
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "search", value: name),
            URLQueryItem(name: "per_page", value: "10"),
        ]
        if let parentID = talmudTermID {
            queryItems.append(URLQueryItem(name: "parent", value: "\(parentID)"))
        }
        components.queryItems = queryItems
        guard let url = components.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let terms = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw YCTError.decodingError
        }
        // Find exact match (case-insensitive)
        for term in terms {
            if let id = term["id"] as? Int,
               let termName = term["name"] as? String,
               termName.lowercased() == name.lowercased() {
                return id
            }
        }
        return nil
    }

    /// Fetches all daf-level children of a tractate term.
    /// Returns a dict mapping daf number → term ID (e.g. 28 → 2486).
    private func fetchDafTermIDs(tractateTermID: Int) async throws -> [Int: Int] {
        var components = URLComponents(string: "\(baseURL)/reference")!
        components.queryItems = [
            URLQueryItem(name: "parent", value: "\(tractateTermID)"),
            URLQueryItem(name: "per_page", value: "100"),
        ]
        guard let url = components.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let terms = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw YCTError.decodingError
        }

        var result: [Int: Int] = [:]
        for term in terms {
            guard let id = term["id"] as? Int,
                  let name = term["name"] as? String else { continue }
            // Name format: "Berakhot 28" — extract the number after the last space
            let parts = name.split(separator: " ")
            if let last = parts.last, let dafNum = Int(last) {
                result[dafNum] = id
            }
        }
        return result
    }

    // MARK: - Post Fetching

    /// Fetches articles tagged with any of the given term IDs.
    /// Filters to English-only posts (excludes slugs ending in known non-English suffixes).
    func fetchArticles(termIDs: [Int], dafTermMap: [Int: Int], currentDaf: Int) async throws -> [YCTArticle] {
        guard !termIDs.isEmpty else { return [] }
        let ids = termIDs.map(String.init).joined(separator: ",")
        var components = URLComponents(string: "\(baseURL)/posts")!
        components.queryItems = [
            URLQueryItem(name: "reference", value: ids),
            URLQueryItem(name: "per_page", value: "20"),
            URLQueryItem(name: "_fields", value: "id,title,excerpt,content,date,link,slug,_links,_embedded"),
            URLQueryItem(name: "_embed",   value: "author"),
        ]
        guard let url = components.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let posts = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw YCTError.decodingError
        }

        // Build reverse map: termID → daf number (for match type resolution)
        let termToDaf = Dictionary(uniqueKeysWithValues: dafTermMap.map { ($1, $0) })

        var articles: [YCTArticle] = []
        for post in posts {
            guard let id = post["id"] as? Int,
                  let slug = post["slug"] as? String,
                  let titleObj = post["title"] as? [String: Any],
                  let titleRaw = titleObj["rendered"] as? String,
                  let excerptObj = post["excerpt"] as? [String: Any],
                  let excerptRaw = excerptObj["rendered"] as? String,
                  let date = post["date"] as? String,
                  let link = post["link"] as? String
            else { continue }

            // Skip non-English articles
            if nonEnglishSuffixes.contains(where: { slug.hasSuffix($0) }) { continue }

            let title = stripHTML(titleRaw)
            var excerpt = stripHTML(excerptRaw)
            if excerpt.isEmpty, let contentObj = post["content"] as? [String: Any],
               let contentRaw = contentObj["rendered"] as? String {
                let full = stripHTML(contentRaw)
                excerpt = full.count > 200 ? String(full.prefix(200)).trimmingCharacters(in: .whitespaces) + "…" : full
            }
            let authorName = authorName(from: post)
            let matchType = resolveMatchType(postID: id, termIDs: termIDs, termToDaf: termToDaf, currentDaf: currentDaf)
            let formattedDate = formatDate(date)

            articles.append(YCTArticle(
                id: id,
                title: title,
                excerpt: excerpt,
                date: formattedDate,
                link: link,
                authorName: authorName,
                matchType: matchType,
                source: source
            ))
        }

        // Sort: exact first, then nearby, then tractate-wide
        return articles.sorted { a, b in
            matchRank(a.matchType) < matchRank(b.matchType)
        }
    }

    // MARK: - Article Content

    /// Fetches the full rendered HTML body of a single post by its WordPress ID.
    func fetchArticleContent(id: Int) async throws -> String {
        var comps = URLComponents(string: "\(baseURL)/posts/\(id)")!
        comps.queryItems = [URLQueryItem(name: "_fields", value: "id,content")]
        guard let url = comps.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [String: Any],
              let rendered = content["rendered"] as? String
        else { throw YCTError.decodingError }
        return rendered
    }

    // MARK: - Private Helpers

    private func fetch(_ url: URL) async throws -> Data {
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return data
        } catch {
            throw YCTError.networkError(error)
        }
    }

    private func resolveMatchType(postID: Int, termIDs: [Int], termToDaf: [Int: Int], currentDaf: Int) -> ResourceMatchType {
        // We can't easily know which term matched a post without fetching post terms separately.
        // Use a heuristic: if the current daf's term is in termIDs, assume exact for all returned
        // posts (the API returns posts matching ANY of the IDs). For more precision the caller
        // separates exact vs nearby term IDs before calling.
        // This function is used by the batch path; see ResourcesManager for the tiered approach.
        return .exact(daf: currentDaf)
    }

    private func authorName(from post: [String: Any]) -> String {
        // The author object is embedded via ?_embed=author and lives at:
        //   post["_embedded"]["author"][0]["name"]
        guard let embedded  = post["_embedded"]  as? [String: Any],
              let authorArr = embedded["author"]  as? [[String: Any]],
              let name      = authorArr.first?["name"] as? String
        else { return "" }
        return name
    }

    private func matchRank(_ type: ResourceMatchType) -> Int {
        switch type {
        case .exact:        return 0
        case .nearby:       return 1
        case .tractateWide: return 2
        }
    }

    private func stripHTML(_ html: String) -> String {
        // 1. Remove all HTML tags
        var s = html.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        // 2. Decode all decimal and hex numeric entities: &#8211; &#x2013; etc.
        s = decodeNumericHTMLEntities(s)
        // 3. Decode common named entities
        let named: [String: String] = [
            "&nbsp;": " ",  "&amp;": "&",   "&lt;": "<",    "&gt;": ">",
            "&quot;": "\"", "&apos;": "'",  "&mdash;": "—", "&ndash;": "–",
            "&lsquo;": "\u{2018}", "&rsquo;": "\u{2019}",
            "&ldquo;": "\u{201C}", "&rdquo;": "\u{201D}",
            "&hellip;": "…", "&bull;": "•",
        ]
        for (entity, char) in named {
            s = s.replacingOccurrences(of: entity, with: char)
        }
        return s.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Decodes all numeric HTML entities (decimal &#N; and hex &#xN;) in a string.
    private func decodeNumericHTMLEntities(_ input: String) -> String {
        guard let regex = try? NSRegularExpression(pattern: "&#(x?)([0-9a-fA-F]+);",
                                                   options: .caseInsensitive) else { return input }
        let ns = input as NSString
        let matches = regex.matches(in: input, range: NSRange(location: 0, length: ns.length))
        // Process in reverse so earlier ranges stay valid after replacements
        var result = input as NSString
        for match in matches.reversed() {
            guard let prefixRange = Range(match.range(at: 1), in: input),
                  let valueRange  = Range(match.range(at: 2), in: input) else { continue }
            let isHex = !input[prefixRange].isEmpty
            let valueStr = String(input[valueRange])
            guard let codePoint = UInt32(valueStr, radix: isHex ? 16 : 10),
                  let scalar = Unicode.Scalar(codePoint) else { continue }
            result = result.replacingCharacters(in: match.range, with: String(scalar)) as NSString
        }
        return result as String
    }

    private func formatDate(_ iso: String) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime]
        guard let date = parser.date(from: iso) else { return iso }
        let fmt = DateFormatter()
        fmt.dateStyle = .medium
        fmt.timeStyle = .none
        return fmt.string(from: date)
    }
}
