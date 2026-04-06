import Foundation

@MainActor
class FeedManager: ObservableObject {
    @Published var isLoading = false
    @Published var loadingProgress = ""
    @Published var episodeCount: Int = 0

    // tractate name → daf number → audio URL string
    private(set) var episodeIndex: [String: [Int: String]] = [:]

    private let feedBase = "https://feeds.soundcloud.com/users/soundcloud:users:958779193/sounds.rss"
    static let soundcloudClientID = "1IzwHiVxAHeYKAMqN0IIGD3ZARgJy2kl"

    private let supabaseURL = "https://zewdazoijdpakugfvnzt.supabase.co"
    private let anonKey = Secrets.supabaseAnonKey

    // Canonical tractate name → SoundCloud playlist ID
    // Covers tractates that fall outside the RSS feed's rolling window
    private let tractatePlaylistIDs: [String: Int] = [
        "Berakhot":      1224453841,
        "Shabbat":       1224957730,
        "Eiruvin":       1224604675,
        "Pesachim":      1223731237,
        "Yoma":          1224408415,
        "Sukkah":        1224961240,
        "Beitzah":       1224467716,
        "Rosh Hashanah": 1225124800,
        "Ta\u{2019}anit": 1947852215,
        "Moed Katan":    1947706063,
        "Chagigah":      1947633743,
        "Yevamot":       1225156528,
        "Ketubot":       1224649789,
        "Nedarim":       1224705577,
        "Nazir":         1950629151,
        "Sotah":         1595841331,
        "Gittin":        1224617542,
        "Kiddushin":     1224719668,
        "Bava Kamma":    1224873547,
        "Bava Metzia":   1224692203,
        "Bava Batra":    1224939157,
        "Sanhedrin":     1225177738,
        "Makkot":        1224421891,
        "Shevuot":       1954367887,
        "Avodah Zarah":  1224438616,
        "Horayot":       1224645901,
        "Zevachim":      1225250722,
        "Menachot":      1950820791,
        "Hullin":        1224735955,
        "Bekhorot":      1224596788,
        "Arakhin":       1224424696,
        "Temurah":       1225194493,
        "Meilah":       1224865387,
        "Kinnim":        1954771503,
        "Tamid":         1954771299,
        "Middot":        1954771395,
        "Niddah":        1225213678,
    ]

    private let cacheURL: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("episode_index.json")
    }()
    private let cacheTimestampKey = "episodeIndexTimestamp"

    var hasIndex: Bool { !episodeIndex.isEmpty }

    init() {
        loadFromCache()
    }

    func audioURL(tractate: String, daf: Int) -> URL? {
        guard let str = episodeIndex[tractate]?[daf] else { return nil }
        return URL(string: str)
    }

    // Force a fresh fetch regardless of cache age.
    // Always tries Supabase first; falls back to RSS+playlist crawl only if Supabase is unavailable.
    // Use this for the "Refresh Episodes" button and auto-retry on playback failure.
    func forceRefresh() async {
        isLoading = true
        loadingProgress = "Loading episodes…"
        defer {
            isLoading = false
            loadingProgress = ""
        }
        if let supabaseIndex = await fetchFromSupabase(), !supabaseIndex.isEmpty {
            episodeIndex = supabaseIndex
            episodeCount = supabaseIndex.values.reduce(0) { $0 + $1.count }
            saveToCache(supabaseIndex)
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: cacheTimestampKey)
        } else {
            await fetchAll()
        }
    }

    // Fetch only if cache is missing, older than 7 days, or suspiciously small
    // (e.g. populated before the Supabase row-limit fix — full index is 2000+).
    // Tries Supabase first (fast single request); falls back to RSS crawl if unavailable.
    func refreshIfNeeded() async {
        let lastFetch = UserDefaults.standard.double(forKey: cacheTimestampKey)
        let age = Date().timeIntervalSince1970 - lastFetch
        guard !hasIndex || age > 7 * 24 * 3600 || episodeCount < 2000 else { return }

        if let supabaseIndex = await fetchFromSupabase(), !supabaseIndex.isEmpty {
            episodeIndex = supabaseIndex
            episodeCount = supabaseIndex.values.reduce(0) { $0 + $1.count }
            saveToCache(supabaseIndex)
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: cacheTimestampKey)
        } else {
            await fetchAll()
        }
    }

    /// Fetch the full episode index from Supabase episode_audio table.
    /// Paginates in batches of 1000 to work around PostgREST's server-side max-rows cap.
    /// Returns nil if the request fails (caller should fall back to RSS crawl).
    private func fetchFromSupabase() async -> [String: [Int: String]]? {
        var index: [String: [Int: String]] = [:]
        let batchSize = 1000
        var offset = 0

        while true {
            let urlStr = "\(supabaseURL)/rest/v1/episode_audio"
                + "?select=tractate,daf,audio_url"
                + "&limit=\(batchSize)&offset=\(offset)"
                + "&order=tractate,daf"
            guard let url = URL(string: urlStr) else { return nil }
            var request = URLRequest(url: url)
            request.setValue(anonKey, forHTTPHeaderField: "apikey")
            request.setValue("Bearer \(anonKey)", forHTTPHeaderField: "Authorization")

            guard let (data, response) = try? await URLSession.shared.data(for: request),
                  (response as? HTTPURLResponse)?.statusCode == 200,
                  let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]
            else { return index.isEmpty ? nil : index }

            for row in rows {
                guard let tractate = row["tractate"] as? String,
                      let daf      = row["daf"]      as? Int,
                      let audioURL = row["audio_url"] as? String
                else { continue }
                if index[tractate] == nil { index[tractate] = [:] }
                index[tractate]![daf] = audioURL
            }

            if rows.count < batchSize { break }  // last page
            offset += batchSize
        }

        return index.isEmpty ? nil : index
    }

    func fetchAll() async {
        isLoading = true
        var index: [String: [Int: String]] = [:]

        // Phase 1: RSS feed (covers the most recent ~1,200 episodes)
        var nextURL: URL? = URL(string: feedBase)
        var pageCount = 0
        while let url = nextURL {
            pageCount += 1
            loadingProgress = "Loading episodes… (page \(pageCount))"
            guard let (data, _) = try? await URLSession.shared.data(from: url) else { break }
            let parser = RSSParser(data: data)
            parser.parse()
            for item in parser.items {
                guard let tractate = item.tractate, let daf = item.daf, !item.audioURL.isEmpty else { continue }
                if index[tractate] == nil { index[tractate] = [:] }
                if index[tractate]![daf] == nil { index[tractate]![daf] = item.audioURL }
            }
            nextURL = parser.nextPageURL
        }

        // Phase 2: SoundCloud playlist API — fills in dafs missing from the RSS
        loadingProgress = "Loading playlists…"
        let clientID = FeedManager.soundcloudClientID
        let playlistResults = await withTaskGroup(of: (String, [Int: String]).self) { group in
            for (tractate, playlistID) in tractatePlaylistIDs {
                group.addTask {
                    await FeedManager.fetchPlaylist(tractate: tractate,
                                                   playlistID: playlistID,
                                                   clientID: clientID)
                }
            }
            var collected: [(String, [Int: String])] = []
            for await result in group { collected.append(result) }
            return collected
        }

        for (tractate, dafs) in playlistResults {
            if index[tractate] == nil { index[tractate] = [:] }
            for (daf, url) in dafs {
                // Don't overwrite RSS URLs — they're direct MP3s (no resolution step needed)
                if index[tractate]![daf] == nil { index[tractate]![daf] = url }
            }
        }

        episodeIndex = index
        episodeCount = index.values.reduce(0) { $0 + $1.count }
        saveToCache(index)
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: cacheTimestampKey)
        isLoading = false
        loadingProgress = ""
    }

    // Fetch all tracks from a SoundCloud playlist and return daf → soundcloud-track://ID URLs.
    // Static so it runs off the main actor, enabling true parallelism in the task group.
    private static func fetchPlaylist(tractate: String, playlistID: Int, clientID: String) async -> (String, [Int: String]) {
        var dafs: [Int: String] = [:]
        guard let url = URL(string: "https://api-v2.soundcloud.com/playlists/\(playlistID)?client_id=\(clientID)"),
              let (data, _) = try? await URLSession.shared.data(from: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let tracks = json["tracks"] as? [[String: Any]]
        else { return (tractate, dafs) }

        // SoundCloud only hydrates the first ~5 tracks in a playlist response.
        // The rest come back as stubs (have an "id" but no "title"/"urn").
        // Collect stub IDs and batch-fetch full track data separately.
        var fullTracks: [[String: Any]] = []
        var stubIDs: [Int] = []
        for track in tracks {
            if track["title"] is String {
                fullTracks.append(track)
            } else if let id = track["id"] as? Int {
                stubIDs.append(id)
            }
        }

        // Fetch stubs in batches of 50 (SoundCloud API limit)
        let batchSize = 50
        var i = stubIDs.startIndex
        while i < stubIDs.endIndex {
            let batchEnd = stubIDs.index(i, offsetBy: batchSize, limitedBy: stubIDs.endIndex) ?? stubIDs.endIndex
            let batch = stubIDs[i..<batchEnd]
            let idsParam = batch.map(String.init).joined(separator: ",")
            if let batchURL = URL(string: "https://api-v2.soundcloud.com/tracks?ids=\(idsParam)&client_id=\(clientID)"),
               let (batchData, _) = try? await URLSession.shared.data(from: batchURL),
               let batchTracks = try? JSONSerialization.jsonObject(with: batchData) as? [[String: Any]] {
                fullTracks.append(contentsOf: batchTracks)
            }
            i = batchEnd
        }

        for track in fullTracks {
            guard let title = track["title"] as? String,
                  let urn = track["urn"] as? String else { continue }

            // Parse daf number (same logic as RSSParser.parseTitle)
            let cleaned = title.replacingOccurrences(of: #"\s*\(\d+\)\s*$"#, with: "",
                                                      options: .regularExpression)
            let parts = cleaned.split(separator: " ")
            guard parts.count >= 2,
                  let daf = Int(String(parts.last!).prefix(while: { $0.isNumber })),
                  daf > 0
            else { continue }

            // urn looks like "soundcloud:tracks:1004549059"
            guard let trackID = urn.split(separator: ":").last.map(String.init),
                  !trackID.isEmpty
            else { continue }

            if dafs[daf] == nil {
                dafs[daf] = "soundcloud-track://\(trackID)"
            }
        }

        return (tractate, dafs)
    }

    // MARK: - Cache

    private func loadFromCache() {
        guard let data = try? Data(contentsOf: cacheURL),
              var raw = try? JSONDecoder().decode([String: [String: String]].self, from: data)
        else { return }
        // Migrate stale "Middos" key from before the rename to "Middot"
        if let middos = raw["Middos"] {
            raw["Middot"] = (raw["Middot"] ?? [:]).merging(middos) { existing, _ in existing }
            raw.removeValue(forKey: "Middos")
        }
        episodeIndex = raw.mapValues { dafMap in
            Dictionary(uniqueKeysWithValues: dafMap.compactMap { key, url in
                guard let daf = Int(key) else { return nil }
                return (daf, url)
            })
        }
        episodeCount = episodeIndex.values.reduce(0) { $0 + $1.count }
    }

    private func saveToCache(_ index: [String: [Int: String]]) {
        let raw = index.mapValues { dafMap in
            Dictionary(uniqueKeysWithValues: dafMap.map { (String($0.key), $0.value) })
        }
        if let data = try? JSONEncoder().encode(raw) {
            try? data.write(to: cacheURL)
        }
    }
}
