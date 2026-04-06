import Foundation

@MainActor
class BookmarkManager: ObservableObject {
    @Published var bookmarks: [Bookmark] = []

    private static let fileURL: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("bookmarks.json")
    }()

    init() { load() }

    // MARK: - CRUD

    func add(_ bookmark: Bookmark) {
        bookmarks.insert(bookmark, at: 0)
        save()
    }

    func delete(at offsets: IndexSet) {
        bookmarks.remove(atOffsets: offsets)
        save()
    }

    func delete(_ bookmark: Bookmark) {
        bookmarks.removeAll { $0.id == bookmark.id }
        save()
    }

    func update(_ bookmark: Bookmark) {
        if let idx = bookmarks.firstIndex(where: { $0.id == bookmark.id }) {
            bookmarks[idx] = bookmark
            save()
        }
    }

    func isBookmarked(tractateIndex: Int, daf: Int, amud: Int) -> Bool {
        bookmarks.contains { $0.tractateIndex == tractateIndex && $0.daf == daf && $0.amud == amud }
    }

    func existing(tractateIndex: Int, daf: Int, amud: Int) -> Bookmark? {
        bookmarks.first { $0.tractateIndex == tractateIndex && $0.daf == daf && $0.amud == amud }
    }

    // MARK: - Persistence

    private func load() {
        guard FileManager.default.fileExists(atPath: Self.fileURL.path) else { return }
        do {
            let data = try Data(contentsOf: Self.fileURL)
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            bookmarks = try decoder.decode([Bookmark].self, from: data)
        } catch {
            print("BookmarkManager: failed to load — \(error.localizedDescription)")
        }
    }

    private func save() {
        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = .prettyPrinted
            let data = try encoder.encode(bookmarks)
            try data.write(to: Self.fileURL, options: .atomic)
        } catch {
            print("BookmarkManager: failed to save — \(error.localizedDescription)")
        }
    }
}
