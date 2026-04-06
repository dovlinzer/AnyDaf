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

    /// In-memory tractate-level article cache. Keyed by tractate name.
    /// All articles are stored with `.tractateWide(daf:)` so the daf is preserved.
    private var allArticlesCache: [String: [YCTArticle]] = [:]

    private var tractateTermCache: [String: Int] = [:]
    private var dafTermCache: [String: [Int: Int]] = [:]
    private var lastLoaded: (tractate: String, daf: Int)? = nil

    private let client = YCTLibraryClient.shared

    // MARK: - Public API

    func loadResources(tractate: String, daf: Int) async {
        guard lastLoaded?.tractate != tractate || lastLoaded?.daf != daf else { return }
        lastLoaded = (tractate, daf)

        // ── Step 1: re-categorise from in-memory tractate cache (instant, no I/O) ──
        if let all = allArticlesCache[tractate] {
            categorize(articles: all, forDaf: daf)
            return
        }

        // ── Step 2: try disk cache ────────────────────────────────────────────────
        if let all = ResourcesDiskCache.load(tractate: tractate) {
            let clean = mergeAndDeduplicate(all)
            allArticlesCache[tractate] = clean
            categorize(articles: clean, forDaf: daf)
            return
        }

        // ── Step 3: cache miss — fetch every daf in the tractate from the network ─
        isLoading = true
        error = nil
        exactArticles = []
        nearbyArticles = []
        tractateArticles = []

        do {
            // 3a. Resolve tractate term ID (in-memory cache per session)
            guard let tractateTermID = try await resolveTractateTermID(tractate: tractate) else {
                isLoading = false
                return
            }

            // 3b. Resolve all daf-level term IDs for this tractate (in-memory cache)
            let dafTermMap = try await resolveDafTermIDs(tractate: tractate, tractateTermID: tractateTermID)

            // 3c. Fetch all articles for every daf, tagged with their daf number.
            //     We store everything as .tractateWide(daf:); categorize() re-assigns
            //     the match tier based on the caller's current daf.
            //     seenIDs is NOT used here — mergeAndDeduplicate handles all dedup.
            var all: [YCTArticle] = []
            for dafNum in dafTermMap.keys.sorted() {
                guard let termID = dafTermMap[dafNum] else { continue }
                let articles = try await fetchAndTag(
                    termIDs: [termID],
                    matchType: .tractateWide(daf: dafNum)
                )
                all += articles
            }
            all = mergeAndDeduplicate(all)

            // ── Step 4: persist and categorise ───────────────────────────────────
            allArticlesCache[tractate] = all
            ResourcesDiskCache.save(tractate: tractate, articles: all)
            categorize(articles: all, forDaf: daf)

        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }

    /// Fetches the full HTML body of a single article by its WordPress post ID.
    func fetchArticleContent(id: Int) async throws -> String {
        try await client.fetchArticleContent(id: id)
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
            if d == daf {
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

        // Sort nearby by proximity so ±1 appears before ±2
        nearby.sort { abs($0.matchType.referencedDaf - daf) < abs($1.matchType.referencedDaf - daf) }

        exactArticles    = exact
        nearbyArticles   = nearby
        tractateArticles = tractate
    }

    // MARK: - Private

    private func resolveTractateTermID(tractate: String) async throws -> Int? {
        if let cached = tractateTermCache[tractate] { return cached }
        let id = try await client.fetchTractateTermID(tractate: tractate)
        if let id { tractateTermCache[tractate] = id }
        return id
    }

    private func resolveDafTermIDs(tractate: String, tractateTermID: Int) async throws -> [Int: Int] {
        if let cached = dafTermCache[tractate] { return cached }
        let map = try await client.fetchDafTermIDs(tractateTermID: tractateTermID)
        dafTermCache[tractate] = map
        return map
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
        termIDs: [Int],
        matchType: ResourceMatchType
    ) async throws -> [YCTArticle] {
        let fetched = try await client.fetchArticles(termIDs: termIDs, dafTermMap: [:], currentDaf: 0)
        return fetched.map { var a = $0; a.matchType = matchType; return a }
    }
}
