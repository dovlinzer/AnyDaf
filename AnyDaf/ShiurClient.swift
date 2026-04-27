import Foundation

// MARK: - Data models

struct ShiurSegment: Identifiable, Decodable {
    let title: String
    /// Short label (≤25 chars) for audio navigation pills; falls back to title if absent.
    let displayTitle: String
    let timestamp: String   // "MM:SS"
    var microSegments: [ShiurMicroSegment]

    var id: String { timestamp }

    /// Seconds from the timestamp string "MM:SS"
    var seconds: Double {
        let parts = timestamp.split(separator: ":").compactMap { Double($0) }
        guard parts.count == 2 else { return 0 }
        return parts[0] * 60 + parts[1]
    }

    enum CodingKeys: String, CodingKey {
        case title, timestamp
        case displayTitle = "display_title"
        case microSegments = "micro_segments"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        displayTitle = (try? c.decode(String.self, forKey: .displayTitle)) ?? title
        timestamp = try c.decode(String.self, forKey: .timestamp)
        microSegments = (try? c.decode([ShiurMicroSegment].self, forKey: .microSegments)) ?? []
    }
}

struct ShiurMicroSegment: Identifiable, Decodable {
    let title: String
    /// Short label (≤25 chars) for audio chapter markers; falls back to title if absent.
    let displayTitle: String
    let timestamp: String

    var id: String { timestamp }

    var seconds: Double {
        let parts = timestamp.split(separator: ":").compactMap { Double($0) }
        guard parts.count == 2 else { return 0 }
        return parts[0] * 60 + parts[1]
    }

    enum CodingKeys: String, CodingKey {
        case title, timestamp
        case displayTitle = "display_title"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        displayTitle = (try? c.decode(String.self, forKey: .displayTitle)) ?? title
        timestamp = try c.decode(String.self, forKey: .timestamp)
    }
}

struct ShiurSegmentation: Decodable {
    let macroSegments: [ShiurSegment]

    enum CodingKeys: String, CodingKey {
        case macroSegments = "macro_segments"
    }
}

// MARK: - Client

@MainActor
class ShiurClient: ObservableObject {
    static let shared = ShiurClient()

    @Published var segments: [ShiurSegment] = []
    @Published var currentSegmentIndex: Int = 0
    /// Lecture rewrite text (pass 2) for the loaded daf, or nil if not available.
    @Published var shiurRewrite: String? = nil
    /// Lecture text with Sefaria sources inserted (pass 3), or nil if not available.
    @Published var shiurFinal: String? = nil

    private let edgeFunctionURL = "https://zewdazoijdpakugfvnzt.supabase.co/functions/v1/get-shiur"

    private var loadedKey: String? = nil   // "Tractate-daf_float" — avoids redundant fetches

    func loadSegments(tractate: String, daf: Double) async {
        let key = "\(tractate)-\(daf)"
        guard key != loadedKey else { return }
        segments = []
        currentSegmentIndex = 0
        shiurRewrite = nil
        shiurFinal = nil

        let encodedTractate = tractate.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? tractate
        let urlString = "\(edgeFunctionURL)?tractate=\(encodedTractate)&daf=\(daf)"
        guard let url = URL(string: urlString) else { return }

        var request = URLRequest(url: url)
        request.setValue(Secrets.appSecret, forHTTPHeaderField: "x-app-secret")

        do {
            let (data, _) = try await URLSession.shared.data(for: request)

            // Response is an array: [{"segmentation": {...}, "rewrite": "..."}]
            guard let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]],
                  let first = rows.first
            else { return }

            if let segJSON = first["segmentation"], !(segJSON is NSNull),
               let segData = try? JSONSerialization.data(withJSONObject: segJSON),
               let decoded = try? JSONDecoder().decode(ShiurSegmentation.self, from: segData) {
                segments = decoded.macroSegments
            }

            shiurRewrite = first["rewrite"] as? String
            shiurFinal = first["final"] as? String
            loadedKey = key
        } catch {
            // Silently fail — chapter markers and lecture context are enhancements, not critical
        }
    }

    /// Update currentSegmentIndex based on the audio's current playback position.
    func updateCurrentSegment(currentTime: Double) {
        guard !segments.isEmpty else { return }
        var idx = 0
        for (i, seg) in segments.enumerated() {
            if currentTime >= seg.seconds { idx = i }
        }
        if idx != currentSegmentIndex { currentSegmentIndex = idx }
    }

    /// Clear when navigating to a different daf.
    func reset() {
        segments = []
        currentSegmentIndex = 0
        shiurRewrite = nil
        shiurFinal = nil
        loadedKey = nil
    }
}
