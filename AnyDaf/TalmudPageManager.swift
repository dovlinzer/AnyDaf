import Foundation

/// Loads pages.json from the app bundle and vends Google Drive image URLs
/// for each daf amud (side).
///
/// pages.json format:
///   { "Berakhot": { "2": "DRIVE_FILE_ID", "3": "DRIVE_FILE_ID", … }, … }
///
/// Page number ↔ daf conversion:
///   page = (daf - 1) * 2           for amud aleph (side a)
///   page = (daf - 1) * 2 + 1       for amud bet   (side b)
class TalmudPageManager {
    static let shared = TalmudPageManager()

    /// [tractate: [pageNumber: driveFileId]]
    private let pages: [String: [String: String]]

    private init() {
        guard
            let url  = Bundle.main.url(forResource: "pages", withExtension: "json"),
            let data = try? Data(contentsOf: url),
            let decoded = try? JSONSerialization.jsonObject(with: data) as? [String: [String: String]]
        else {
            pages = [:]
            return
        }
        pages = decoded
    }

    /// Whether any page images are available for the given tractate.
    func hasPages(for tractate: String) -> Bool {
        !(pages[tractate]?.isEmpty ?? true)
    }

    /// Returns a Google Drive thumbnail URL for the given daf amud.
    /// - Parameters:
    ///   - tractate: e.g. "Berakhot"
    ///   - daf:      e.g. 11
    ///   - sideA:    true for amud aleph (a), false for amud bet (b)
    func imageURL(tractate: String, daf: Int, sideA: Bool) -> URL? {
        let pageNumber = (daf - 1) * 2 + (sideA ? 0 : 1)
        guard let fileId = pages[tractate]?[String(pageNumber)] else { return nil }
        // Google Drive thumbnail endpoint — works for publicly link-shared files.
        // sz=w1200 gives a ~1200-px-wide image suitable for retina displays.
        return URL(string: "https://drive.google.com/thumbnail?id=\(fileId)&sz=w1200")
    }
}
