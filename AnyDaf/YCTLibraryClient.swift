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

    /// Client for the "Iggros Moshe A to Z" podcast — a custom "audio" post type on
    /// library.yctorah.org (same site/host as `shared`, so it shares the same reference
    /// taxonomy term tree — hence the same `talmudTermID`).
    ///
    /// ⚠️ As of 2026-07-22 this post type is NOT exposed via the WordPress REST API at all
    /// (confirmed via the site's full `/wp-json/` route index — no `audio` route of any name
    /// exists yet). Every request through this client will fail until that's fixed on the
    /// WordPress side (`show_in_rest` needs to be set on the post type's registration).
    /// `restBase: "audio"` is a **guess** matching the post type's URL slug
    /// (`library.yctorah.org/audio/[slug]/`) and WordPress's own default behavior of using
    /// the post type slug as the REST base when none is explicitly configured — but the
    /// theme/plugin code could set an explicit different `rest_base`. Once REST access is
    /// enabled, check `/wp-json/wp/v2/types` for the real value and update this constant if
    /// it differs. See "WordPress Audio Posts" in CLAUDE.md for full context.
    static let audio = YCTLibraryClient(
        baseURL: "https://library.yctorah.org/wp-json/wp/v2",
        source: .audio,
        talmudTermID: 1899,
        fetchesTractateLevel: true,
        restBase: "audio"
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
    /// The WordPress REST collection name for this post type (e.g. "posts", "audio").
    private let restBase: String

    /// Per-session term ID caches.
    private var tractateTermCache: [String: Int] = [:]
    private var dafTermCache: [String: [Int: Int]] = [:]

    init(baseURL: String, source: YCTSource, talmudTermID: Int?, fetchesTractateLevel: Bool,
         restBase: String = "posts") {
        self.baseURL = baseURL
        self.source = source
        self.talmudTermID = talmudTermID
        self.fetchesTractateLevel = fetchesTractateLevel
        self.restBase = restBase
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

    /// Fetches all articles for a tractate in a single bulk request.
    ///
    /// `allTermIDs` is every daf-level (and optionally tractate-level) term ID to query.
    /// `termToDaf` maps each term ID back to its daf number (0 = tractate-level sentinel).
    /// Each returned article has `matchType.referencedDaf` set from the post's own
    /// `reference` field, so one HTTP call replaces the old per-daf loop.
    func fetchBulkArticles(allTermIDs: [Int], termToDaf: [Int: Int]) async throws -> [YCTArticle] {
        guard !allTermIDs.isEmpty else { return [] }
        let ids = allTermIDs.map(String.init).joined(separator: ",")
        var components = URLComponents(string: "\(baseURL)/\(restBase)")!
        components.queryItems = [
            URLQueryItem(name: "reference", value: ids),
            URLQueryItem(name: "per_page",  value: "100"),
            URLQueryItem(name: "_fields",   value: "id,title,excerpt,content,date,link,slug,reference,_links,_embedded"),
            URLQueryItem(name: "_embed",    value: "author,wp:featuredmedia"),
        ]
        guard let url = components.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let posts = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw YCTError.decodingError
        }

        var articles: [YCTArticle] = []
        for post in posts {
            guard let id = post["id"] as? Int,
                  let slug = post["slug"] as? String,
                  let titleObj = post["title"] as? [String: Any],
                  let titleRaw = titleObj["rendered"] as? String,
                  let date = post["date"] as? String,
                  let link = post["link"] as? String
            else { continue }

            // The "audio" custom post type doesn't declare excerpt support, so the
            // `excerpt` key is absent entirely from its REST response — fall back to ""
            // (the existing content-derived-excerpt logic below fills it in from there).
            let excerptRaw = ((post["excerpt"] as? [String: Any])?["rendered"] as? String) ?? ""

            if nonEnglishSuffixes.contains(where: { slug.hasSuffix($0) }) { continue }

            let contentRaw = (post["content"] as? [String: Any])?["rendered"] as? String ?? ""
            let isAudio = contentRaw.range(of: "<audio", options: .caseInsensitive) != nil

            let title = stripHTML(titleRaw)
            var excerpt = stripHTML(excerptRaw)
            if excerpt.isEmpty, !contentRaw.isEmpty {
                // Audio posts (podcast episodes) embed a PowerPress player + link/subscribe
                // boilerplate ahead of any real description — strip it so the fallback
                // excerpt shows the actual episode blurb instead of "Podcast: Play in new
                // window | Download ... Subscribe: RSS".
                let cleaned = isAudio ? stripAudioPlayerBoilerplate(contentRaw) : contentRaw
                let full = stripHTML(cleaned)
                excerpt = full.count > 200 ? String(full.prefix(200)).trimmingCharacters(in: .whitespaces) + "…" : full
            }
            if source == .psak {
                // WordPress's auto-generated excerpt strips all HTML before we ever see it,
                // so by this point "QUESTION"/"QUETSION" + the location are just flat text
                // ("QUESTION Riverdale, NY Dear Rabbi Linzer, ...") — there's no h3/h4 left
                // to target the way `formatPsakQuestionHeader` does for the full article.
                // Strip the redundant "QUESTION <City, ST>" prefix so the card preview
                // leads with the actual question instead.
                excerpt = stripPsakExcerptPrefix(excerpt)
            }
            let authorName = authorName(from: post)
            let imageURL = featuredImageURL(from: post)
            let formattedDate = formatDate(date)

            // Determine daf associations from the post's own reference term list.
            // 0 is the tractate-root sentinel (from fetchesTractateLevel) — a post can be
            // tagged with both the root term AND specific daf terms at once, so prefer any
            // real daf number over 0 rather than letting 0 win just by being numerically
            // smallest; only fall back to 0 when there's no daf-specific tag at all.
            let postRefIDs = post["reference"] as? [Int] ?? []
            let allDafs = postRefIDs.compactMap { termToDaf[$0] }
            let specificDafs = Array(Set(allDafs.filter { $0 != 0 })).sorted()
            let primaryDaf = specificDafs.first ?? 0
            let additionalDafs = specificDafs.dropFirst()

            articles.append(YCTArticle(
                id: id,
                title: title,
                excerpt: excerpt,
                date: formattedDate,
                link: link,
                authorName: authorName,
                matchType: .tractateWide(daf: primaryDaf),
                additionalDafs: Array(additionalDafs),
                source: source,
                isAudio: isAudio,
                imageURL: imageURL
            ))
        }

        return articles
    }

    // MARK: - Article Content

    /// Fetches the full rendered HTML body of a single post by its WordPress ID.
    func fetchArticleContent(id: Int) async throws -> String {
        var comps = URLComponents(string: "\(baseURL)/\(restBase)/\(id)")!
        comps.queryItems = [URLQueryItem(name: "_fields", value: "id,content")]
        guard let url = comps.url else { throw YCTError.invalidURL }
        let data = try await fetch(url)
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [String: Any],
              let rendered = content["rendered"] as? String
        else { throw YCTError.decodingError }
        // Some embedded media (older audio posts especially) still link http:// sources.
        // App Transport Security blocks plain HTTP, so upgrade before it ever reaches a WebView.
        let httpsFixed = rendered.replacingOccurrences(of: "src=\"http://", with: "src=\"https://")
        if source == .psak  { return formatPsakQuestionHeader(httpsFixed) }
        if source == .audio { return stripSoundCloudEmbed(httpsFixed) }
        return httpsFixed
    }

    /// Fetches the live page (not the REST API) for an audio episode and extracts its
    /// SoundCloud track ID from the embedded player's iframe `src`. The REST API's
    /// `content` field is NOT a reliable source for this: some episodes have the iframe
    /// manually embedded in the post body (REST-visible), but others get it injected by
    /// the WordPress theme from post meta that isn't exposed via REST at all — confirmed
    /// by comparing `content.rendered` (no iframe) against the live page (iframe present)
    /// for the same post. The live page always renders the player either way, so scraping
    /// it directly is the only approach that works uniformly across all episodes.
    func extractSoundCloudTrackID(pageURL: String) async -> String? {
        guard let url = URL(string: pageURL) else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        guard let html = String(data: data, encoding: .utf8) else { return nil }
        guard let regex = try? NSRegularExpression(
            pattern: "soundcloud\\.com[^\"']*?tracks(?:%2F|/)(\\d+)",
            options: [.caseInsensitive]
        ) else { return nil }
        let range = NSRange(html.startIndex..., in: html)
        guard let match = regex.firstMatch(in: html, range: range),
              let idRange = Range(match.range(at: 1), in: html)
        else { return nil }
        return String(html[idRange])
    }

    // MARK: - Private Helpers

    /// Strips a leading "QUESTION <City, ST>" (or "QUETSION", etc. — real editorial typos
    /// exist on the site) prefix from a plain-text psak excerpt, so the card preview leads
    /// with the actual question instead of running the label and location straight into it.
    /// Best-effort: only matches a "City[, ...], XX" (2-letter state/region code) shape;
    /// leaves the excerpt untouched if the location doesn't look like that (e.g. a country
    /// name) rather than risk mangling real question text.
    private func stripPsakExcerptPrefix(_ excerpt: String) -> String {
        let range = NSRange(excerpt.startIndex..., in: excerpt)
        // First try the full "QUESTION <City, ST>" shape (most common — a US city plus a
        // 2-letter state code).
        if let fullRegex = try? NSRegularExpression(
            pattern: "^QUE[A-Za-z]*ION\\s+[^,]+,\\s*[A-Za-z]{2}\\.?\\s+",
            options: [.caseInsensitive]
        ), fullRegex.firstMatch(in: excerpt, range: range) != nil {
            return fullRegex.stringByReplacingMatches(in: excerpt, range: range, withTemplate: "")
        }
        // Fallback: locations don't always fit that shape (e.g. "QUESTION Israel" — no
        // comma, no state code), so just strip the redundant "QUESTION" label itself
        // rather than risk mangling real question text by guessing further.
        guard let labelRegex = try? NSRegularExpression(
            pattern: "^QUE[A-Za-z]*ION\\s+",
            options: [.caseInsensitive]
        ) else { return excerpt }
        return labelRegex.stringByReplacingMatches(in: excerpt, range: range, withTemplate: "")
    }

    /// Removes an embedded SoundCloud iframe from audio-episode content when present
    /// (only true for episodes where it happens to be manually embedded in the post body
    /// — see `extractSoundCloudTrackID`). The app now provides its own native "Play"
    /// control backed by the extracted track ID, so leaving the iframe in would just show
    /// a second, often non-functional-inside-a-WebView copy of the same player.
    private func stripSoundCloudEmbed(_ html: String) -> String {
        var s = html
        let patterns = [
            "(?is)<p>\\s*<iframe[^>]*soundcloud[^>]*>.*?</iframe>\\s*</p>",
            "(?is)<iframe[^>]*soundcloud[^>]*>.*?</iframe>"
        ]
        for pattern in patterns {
            s = s.replacingOccurrences(of: pattern, with: "", options: .regularExpression)
        }
        return s
    }

    /// Psak articles open with `<h3>QUESTION</h3>` immediately followed by
    /// `<h4>Location</h4>`. Rendered with default heading styles these sit right on top of
    /// the question text with no visual separation. Replace the pair with a single
    /// right-aligned "QUESTION | Location" header block (styled in `styledHTML`), which
    /// also guarantees the actual question text starts on a fresh line below it.
    private func formatPsakQuestionHeader(_ html: String) -> String {
        var result = html
        // Match loosely on "QUE...ION" rather than an exact "QUESTION" string — the site
        // has real editorial typos (e.g. "QUETSION") that would otherwise silently fail
        // to match and leave the raw h3/h4 unstyled.
        if let qRegex = try? NSRegularExpression(
            pattern: "<h3>\\s*QUE[A-Za-z]*ION\\s*</h3>\\s*<h4>(.*?)</h4>",
            options: [.caseInsensitive]
        ) {
            let range = NSRange(result.startIndex..., in: result)
            result = qRegex.stringByReplacingMatches(
                in: result, range: range,
                withTemplate: "<div class=\"psak-qheader\"><span class=\"psak-qlabel\">QUESTION</span><span class=\"psak-qloc\">$1</span></div>"
            )
        }
        // Normalize the "ANSWER" heading (also tolerating the "ANWER" typo seen on the
        // site) to the same custom label class as QUESTION, so they render at the same
        // size/weight instead of QUESTION being a styled div while ANSWER stays a plain,
        // larger-by-default <h3>.
        if let aRegex = try? NSRegularExpression(
            pattern: "<h3>\\s*(?:<strong>)?AN[A-Za-z]*WER(?:</strong>)?\\s*</h3>",
            options: [.caseInsensitive]
        ) {
            let range = NSRange(result.startIndex..., in: result)
            result = aRegex.stringByReplacingMatches(
                in: result, range: range,
                withTemplate: "<div class=\"psak-alabel\">ANSWER</div>"
            )
        }
        return result
    }

    private func fetch(_ url: URL) async throws -> Data {
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return data
        } catch {
            throw YCTError.networkError(error)
        }
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

    /// The post's featured-image URL, embedded via ?_embed=wp:featuredmedia and living at:
    ///   post["_embedded"]["wp:featuredmedia"][0]["media_details"]["sizes"]["medium"|"thumbnail"]["source_url"]
    /// Falls back to the media object's own top-level `source_url` (full size) if no sized
    /// variant is present. Returns nil when the post has no featured image at all.
    private func featuredImageURL(from post: [String: Any]) -> String? {
        guard let embedded = post["_embedded"] as? [String: Any],
              let mediaArr = embedded["wp:featuredmedia"] as? [[String: Any]],
              let media    = mediaArr.first
        else { return nil }
        if let details = media["media_details"] as? [String: Any],
           let sizes   = details["sizes"] as? [String: Any] {
            if let medium = sizes["medium"] as? [String: Any],
               let url = medium["source_url"] as? String { return url }
            if let thumb = sizes["thumbnail"] as? [String: Any],
               let url = thumb["source_url"] as? String { return url }
        }
        return media["source_url"] as? String
    }

    private func matchRank(_ type: ResourceMatchType) -> Int {
        switch type {
        case .exact:        return 0
        case .nearby:       return 1
        case .tractateWide: return 2
        }
    }

    /// Strips the PowerPress audio-player widget and its "Podcast: ... | Download ..." /
    /// "Subscribe: RSS" link paragraphs from a post's raw content HTML, so an excerpt
    /// derived from it (when the post has no WordPress excerpt) shows the real episode
    /// description instead of that boilerplate.
    private func stripAudioPlayerBoilerplate(_ html: String) -> String {
        var s = html
        let patterns = [
            "(?s)<div class=\"powerpress_player\"[^>]*>.*?</div>",
            "(?s)<p class=\"powerpress_links[^\"]*\"[^>]*>.*?</p>"
        ]
        for pattern in patterns {
            s = s.replacingOccurrences(of: pattern, with: "", options: .regularExpression)
        }
        return s
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
