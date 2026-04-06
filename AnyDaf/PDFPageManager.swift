import Foundation

/// Manages downloading, caching, and page-number arithmetic for tractate PDFs
/// stored in a shared Google Drive folder.
///
/// Page mapping (standard tractates, offset = 0):
///   PDF page 1 → daf 2a,  page 2 → daf 2b,  page 3 → daf 3a, …
///
/// For tractates that begin mid-volume the `pageOffsets` table shifts the
/// mapping so that PDF page 1 lands on the correct starting daf/amud.
///
/// Forward:  pdfPage = (daf - 2) × 2 + amud + 1 - offset   (amud: 0=a, 1=b)
/// Inverse:  virtualPage = pdfPage + offset
///           daf  = (virtualPage + 1) / 2 + 1   (integer division)
///           amud = (virtualPage + 1) % 2 == 1 ? 1 : 0
@MainActor
class PDFPageManager: ObservableObject {
    static let shared = PDFPageManager()
    private init() {}

    // MARK: - Configuration

    /// Google Drive folder ID containing all tractate PDFs.
    private let folderID = "1vXMXSsmNGGdibS1k4kcH4_dLmW5k_fFM"

    /// Google Drive API key — the same key used in the build-pages.py script.
    /// Replace this placeholder before building.
    var apiKey = "AIzaSyAS7oJowNLnVQ6ywKrHambzzNWRb1dk0uU"

    /// Maximum number of tractate PDFs to keep cached on device at once.
    private let maxCached = 3

    /// Shift applied to page numbers for tractates whose PDF does not begin at daf 2a.
    /// offset = (startDaf - 2) × 2 + startAmud  where startAmud: 0=a, 1=b
    private let pageOffsets: [String: Int] = [
        "Kinnim": 40,   // PDF page 1 = daf 22a  → offset (22-2)×2+0 = 40
        "Tamid":  47,   // PDF page 1 = daf 25b  → offset (25-2)×2+1 = 47
        "Middos": 64,   // PDF page 1 = daf 34a  → offset (34-2)×2+0 = 64
    ]

    // MARK: - Published state

    @Published var isDownloading = false
    @Published var downloadError: String?

    // MARK: - Page arithmetic

    /// Convert daf + amud (0=a, 1=b) to a 1-based PDF page number.
    func pdfPage(daf: Int, amud: Int, tractate: String) -> Int {
        let offset = pageOffsets[tractate] ?? 0
        let virtualPage = (daf - 2) * 2 + amud + 1
        return max(1, virtualPage - offset)
    }

    // MARK: - File names & local URLs

    /// The filename used on Google Drive (and locally).
    /// Replaces the Unicode right-quote in "Ta'anit" with a plain apostrophe
    /// so the filename is safe on all file systems.
    func pdfFileName(for tractate: String) -> String {
        tractate.replacingOccurrences(of: "\u{2019}", with: "'") + ".pdf"
    }

    func localURL(for tractate: String) -> URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent(pdfFileName(for: tractate))
    }

    func isCached(_ tractate: String) -> Bool {
        FileManager.default.fileExists(atPath: localURL(for: tractate).path)
    }

    // MARK: - Download

    /// Downloads the PDF for `tractate` from Google Drive, saves it locally,
    /// and evicts the oldest cached tractate if the cache exceeds `maxCached`.
    func download(tractate: String) async {
        isDownloading = true
        downloadError = nil

        do {
            let fileID = try await getFileID(for: tractate)
            let remoteURL = URL(string:
                "https://www.googleapis.com/drive/v3/files/\(fileID)?alt=media&key=\(apiKey)")!
            let localDest = localURL(for: tractate)

            let (tempURL, response) = try await URLSession.shared.download(from: remoteURL)

            if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                let snippet = (try? String(contentsOf: tempURL, encoding: .utf8))
                    .map { String($0.prefix(200)) } ?? ""
                throw PDFError.downloadFailed("HTTP \(http.statusCode): \(snippet)")
            }

            try? FileManager.default.removeItem(at: localDest)
            try FileManager.default.moveItem(at: tempURL, to: localDest)
            updateCacheOrder(tractate: tractate)

        } catch {
            downloadError = error.localizedDescription
        }

        isDownloading = false
    }

    func clearError() { downloadError = nil }

    // MARK: - Private helpers

    private func getFileID(for tractate: String) async throws -> String {
        let filename = pdfFileName(for: tractate)
        // Single-quote the filename value and escape any embedded single quotes
        let safeName = filename.replacingOccurrences(of: "'", with: "\\'")
        let query = "name='\(safeName)' and '\(folderID)' in parents and trashed=false"

        var components = URLComponents(string: "https://www.googleapis.com/drive/v3/files")!
        components.queryItems = [
            URLQueryItem(name: "q",      value: query),
            URLQueryItem(name: "key",    value: apiKey),
            URLQueryItem(name: "fields", value: "files(id,name)"),
        ]

        let (data, _) = try await URLSession.shared.data(from: components.url!)

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let files = json["files"] as? [[String: Any]],
              let first  = files.first,
              let id     = first["id"] as? String
        else {
            throw PDFError.fileNotFound(tractate)
        }
        return id
    }

    private let cacheOrderKey = "pdfCacheOrder"

    private func updateCacheOrder(tractate: String) {
        var order = UserDefaults.standard.stringArray(forKey: cacheOrderKey) ?? []
        order.removeAll { $0 == tractate }
        order.append(tractate)

        // Evict oldest until within limit
        while order.count > maxCached {
            let oldest = order.removeFirst()
            try? FileManager.default.removeItem(at: localURL(for: oldest))
        }
        UserDefaults.standard.set(order, forKey: cacheOrderKey)
    }

    // MARK: - Errors

    enum PDFError: LocalizedError {
        case fileNotFound(String)
        case downloadFailed(String)

        var errorDescription: String? {
            switch self {
            case .fileNotFound(let name):
                return "'\(name).pdf' was not found in the Google Drive folder. Make sure the file has been uploaded."
            case .downloadFailed(let msg):
                return "Download failed: \(msg)"
            }
        }
    }
}
