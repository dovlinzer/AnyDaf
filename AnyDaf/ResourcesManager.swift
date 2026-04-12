import Foundation

@MainActor
class ResourcesManager: ObservableObject {

    static let shared = ResourcesManager()
    private init() {}

    // MARK: - Published State

    @Published var exactArticles: [YCTArticle] = []
    @Published var nearbyArticles: [YCTArticle] = []
    @Published var tractateArticles: [YCTArticle] = []
    @Published var isLoading = false
    @Published var error: String? = nil

    var hasAnyArticles: Bool {
        !exactArticles.isEmpty || !nearbyArticles.isEmpty || !tractateArticles.isEmpty
    }

    // MARK: - Cache

    /// In-memory tractate-level article cache. Keyed by "<source>:<tractate>".
    /// All articles are stored with `.tractateWide(daf:)` so the daf is preserved.
    private var allArticlesCache: [String: [YCTArticle]] = [:]

    private var lastLoaded: (tractate: String, daf: Int)? = nil

    private let libraryClient = YCTLibraryClient.shared
    private let psakClient    = YCTLibraryClient.psak

    // MARK: - Public API

    func loadResources(tractate: String, daf: Int) async {
        guard lastLoaded?.tractate != tractate || lastLoaded?.daf != daf else { return }
        lastLoaded = (tractate, daf)

        // ── Step 1: re-categorise from in-memory cache (instant, no I/O) ────────────
        let libraryKey = cacheKey(.library, tractate)
        let psakKey    = cacheKey(.psak, tractate)

        if let lib = allArticlesCache[libraryKey], let psak = allArticlesCache[psakKey] {
            categorize(articles: lib + psak, forDaf: daf)
            return
        }

        // ── Step 2: try disk cache ────────────────────────────────────────────────
        let cachedLib  = allArticlesCache[libraryKey] ?? ResourcesDiskCache.load(tractate: tractate, source: .library)
        let cachedPsak = allArticlesCache[psakKey]    ?? ResourcesDiskCache.load(tractate: tractate, source: .psak)

        if let lib = cachedLib, let psak = cachedPsak {
            allArticlesCache[libraryKey] = lib
            allArticlesCache[psakKey]    = psak
            categorize(articles: lib + psak, forDaf: daf)
            return
        }

        // ── Step 3: cache miss — fetch from network ───────────────────────────────
        isLoading = true
        error = nil
        exactArticles = []
        nearbyArticles = []
        tractateArticles = []

        do {
            async let libraryFetch = fetchAllFromClient(libraryClient, tractate: tractate,
                                                        cached: cachedLib)
            async let psakFetch    = fetchAllFromClient(psakClient, tractate: tractate,
                                                        cached: cachedPsak)

            let (lib, psak) = try await (libraryFetch, psakFetch)

            // Persist any newly fetched data
            if cachedLib == nil {
                allArticlesCache[libraryKey] = lib
                ResourcesDiskCache.save(tractate: tractate, source: .library, articles: lib)
            } else {
                allArticlesCache[libraryKey] = cachedLib!
            }
            if cachedPsak == nil {
                allArticlesCache[psakKey] = psak
                ResourcesDiskCache.save(tractate: tractate, source: .psak, articles: psak)
            } else {
                allArticlesCache[psakKey] = cachedPsak!
            }

            categorize(articles: (allArticlesCache[libraryKey] ?? []) + (allArticlesCache[psakKey] ?? []),
                       forDaf: daf)

        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }

    /// Fetches the full HTML body of a single article, routing to the correct site.
    func fetchArticleContent(article: YCTArticle) async throws -> String {
        switch article.source {
        case .library: return try await libraryClient.fetchArticleContent(id: article.id)
        case .psak:    return try await psakClient.fetchArticleContent(id: article.id)
        }
    }

    func reset() {
        exactArticles = []
        nearbyArticles = []
        tractateArticles = []
        isLoading = false
        error = nil
        lastLoaded = nil
        // allArticlesCache is intentionally preserved: if the user returns to a
        // previously visited tractate the articles are available instantly.
    }

    // MARK: - Categorisation

    /// Splits a flat tractate article list into exact / nearby / tractate-wide
    /// sections based on `currentDaf`, then publishes the results.
    private func categorize(articles: [YCTArticle], forDaf daf: Int) {
        var exact:    [YCTArticle] = []
        var nearby:   [YCTArticle] = []
        var tractate: [YCTArticle] = []

        for var article in articles {
            let d = article.matchType.referencedDaf
            // daf 0 is the sentinel for psak articles tagged at the tractate level (no specific daf)
            if d == 0 {
                article.matchType = .tractateWide(daf: 0)
                tractate.append(article)
            } else if d == daf {
                article.matchType = .exact(daf: d)
                exact.append(article)
            } else if abs(d - daf) <= 2 {
                article.matchType = .nearby(daf: d)
                nearby.append(article)
            } else {
                article.matchType = .tractateWide(daf: d)
                tractate.append(article)
            }
        }

        // Sort nearby by ascending daf number
        nearby.sort { $0.matchType.referencedDaf < $1.matchType.referencedDaf }

        // Sort tractate-wide by daf number; daf 0 (tractate-level psak) goes last
        tractate.sort {
            let da = $0.matchType.referencedDaf, db = $1.matchType.referencedDaf
            if da == 0 { return false }
            if db == 0 { return true }
            return da < db
        }

        exactArticles    = exact
        nearbyArticles   = nearby
        tractateArticles = tractate
    }

    // MARK: - Private

    private func cacheKey(_ source: YCTSource, _ tractate: String) -> String {
        "\(source.rawValue):\(tractate)"
    }

    /// Fetches all articles for a tractate from a single client, or returns the
    /// already-loaded cached slice when available.
    private func fetchAllFromClient(
        _ client: YCTLibraryClient,
        tractate: String,
        cached: [YCTArticle]?
    ) async throws -> [YCTArticle] {
        if let cached { return cached }

        guard let tractateTermID = try await client.resolveTractateTermID(tractate: tractate) else {
            return []
        }

        let dafTermMap = try await client.resolveDafTermIDs(tractate: tractate,
                                                            tractateTermID: tractateTermID)
        var all: [YCTArticle] = []

        // Fetch articles for each daf-level term
        for dafNum in dafTermMap.keys.sorted() {
            guard let termID = dafTermMap[dafNum] else { continue }
            let articles = try await fetchAndTag(client: client, termIDs: [termID],
                                                 matchType: .tractateWide(daf: dafNum))
            all += articles
        }

        // For psak: also fetch articles tagged directly on the tractate term (daf = 0 sentinel)
        if client.fetchesTractateLevel {
            let tractateLevel = try await fetchAndTag(client: client, termIDs: [tractateTermID],
                                                      matchType: .tractateWide(daf: 0))
            all += tractateLevel
        }

        return mergeAndDeduplicate(all)
    }

    /// Two-pass deduplication:
    /// Pass 1 — same article ID, different daf: merge into one entry, collecting
    ///          extra dafs in `additionalDafs`; same ID + same daf = API duplicate, skip.
    /// Pass 2 — different ID, same title (WordPress duplicate posts): keep the more
    ///          recently published version at the first-encountered daf position.
    private func mergeAndDeduplicate(_ articles: [YCTArticle]) -> [YCTArticle] {
        // Pass 1: merge by article ID
        var idToIndex: [Int: Int] = [:]
        var merged: [YCTArticle] = []

        for article in articles {
            if let idx = idToIndex[article.id] {
                let newDaf = article.matchType.referencedDaf
                if newDaf != merged[idx].matchType.referencedDaf &&
                   !merged[idx].additionalDafs.contains(newDaf) {
                    merged[idx].additionalDafs.append(newDaf)
                    merged[idx].additionalDafs.sort()
                }
            } else {
                idToIndex[article.id] = merged.count
                merged.append(article)
            }
        }

        // Pass 2: deduplicate by title, keeping more recent content
        let fmt = DateFormatter()
        fmt.dateStyle = .medium
        fmt.timeStyle = .none

        var titleToIndex: [String: Int] = [:]
        var result: [YCTArticle] = []

        for article in merged {
            let key = article.title.lowercased().trimmingCharacters(in: .whitespaces)
            if let idx = titleToIndex[key] {
                // Merge additionalDafs from both entries
                let combined = Array(Set(result[idx].additionalDafs + article.additionalDafs))
                    .filter { $0 != result[idx].matchType.referencedDaf }
                    .sorted()
                if let newDate = fmt.date(from: article.date),
                   let oldDate = fmt.date(from: result[idx].date),
                   newDate > oldDate {
                    var newer = article
                    newer.matchType = result[idx].matchType
                    newer.additionalDafs = Array(Set(combined + [article.matchType.referencedDaf]))
                        .filter { $0 != newer.matchType.referencedDaf }
                        .sorted()
                    result[idx] = newer
                } else {
                    result[idx].additionalDafs = combined
                }
            } else {
                titleToIndex[key] = result.count
                result.append(article)
            }
        }
        return result
    }

    private func fetchAndTag(
        client: YCTLibraryClient,
        termIDs: [Int],
        matchType: ResourceMatchType
    ) async throws -> [YCTArticle] {
        let fetched = try await client.fetchArticles(termIDs: termIDs, dafTermMap: [:], currentDaf: 0)
        return fetched.map { var a = $0; a.matchType = matchType; return a }
    }
}
