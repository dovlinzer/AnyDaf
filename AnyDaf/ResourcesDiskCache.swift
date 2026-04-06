import Foundation

/// Persists fetched YCT Library articles to the app's Caches directory so they
/// survive tractate switches and app restarts.
///
/// Cache files are JSON, keyed by tractate name only (one file per tractate),
/// and expire after `ttl` seconds (default 7 days).  Each article retains its
/// daf association via `matchType.referencedDaf`; callers re-categorise into
/// exact / nearby / tractate-wide purely in memory when the current daf changes.
///
/// Thread-safety: all methods are called from `@MainActor` code (ResourcesManager),
/// but the underlying FileManager calls are quick and non-blocking.
struct ResourcesDiskCache {

    // MARK: - Types

    private struct CacheEnvelope: Codable {
        let savedAt: Date
        let articles: [YCTArticle]
    }

    // MARK: - Configuration

    /// How long a cache entry is considered fresh (7 days).
    static let ttl: TimeInterval = 7 * 24 * 60 * 60

    // MARK: - Public API

    /// Reads cached articles for the given tractate.
    /// Returns `nil` if no entry exists or the entry has expired.
    /// Articles are stored with `.tractateWide(daf:)` so the daf number is preserved;
    /// callers should run `categorize(articles:forDaf:)` to split into sections.
    static func load(tractate: String) -> [YCTArticle]? {
        guard let url = cacheURL(tractate: tractate),
              let data = try? Data(contentsOf: url),
              let envelope = try? JSONDecoder().decode(CacheEnvelope.self, from: data)
        else { return nil }

        guard Date().timeIntervalSince(envelope.savedAt) < ttl else {
            try? FileManager.default.removeItem(at: url)
            return nil
        }

        return envelope.articles
    }

    /// Writes a flat list of tractate articles to disk.
    /// Articles should be stored with `.tractateWide(daf:)` so the daf is recoverable.
    static func save(tractate: String, articles: [YCTArticle]) {
        guard let url = cacheURL(tractate: tractate) else { return }
        let envelope = CacheEnvelope(savedAt: Date(), articles: articles)
        guard let data = try? JSONEncoder().encode(envelope) else { return }
        try? data.write(to: url, options: .atomic)
    }

    /// Removes all cached files whose modification date is older than `ttl`.
    /// Call this once at app launch to keep the Caches directory tidy.
    static func evictExpired() {
        guard let dir = cacheDirectory() else { return }
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: [.contentModificationDateKey]
        ) else { return }

        let cutoff = Date().addingTimeInterval(-ttl)
        for file in files where file.lastPathComponent.hasPrefix("yct_") {
            let mod = (try? file.resourceValues(forKeys: [.contentModificationDateKey])
                .contentModificationDate) ?? .distantPast
            if mod < cutoff { try? fm.removeItem(at: file) }
        }
    }

    // MARK: - Helpers

    private static func cacheDirectory() -> URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("YCTLibrary", isDirectory: true)
    }

    private static func cacheURL(tractate: String) -> URL? {
        guard let dir = cacheDirectory() else { return nil }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let safe = tractate
            .replacingOccurrences(of: " ", with: "_")
            .replacingOccurrences(of: "/", with: "-")
            .replacingOccurrences(of: "'", with: "")
        return dir.appendingPathComponent("yct_\(safe).json")
    }
}
