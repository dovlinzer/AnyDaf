import Foundation

// MARK: - Data models

struct ShiurSegment: Identifiable, Decodable {
    let title: String
    /// Short label (≤25 chars) for audio navigation pills; falls back to title if absent.
    let displayTitle: String
    let timestamp: String   // "MM:SS"
    var microSegments: [ShiurMicroSegment]
    /// 0-based index into the flat Sefaria segment array (amud A + B concatenated).
    /// Nil if find_sefaria_indices.py has not been run for this daf.
    let sefariaIndex: Int?

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
        case sefariaIndex = "sefaria_index"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        displayTitle = (try? c.decode(String.self, forKey: .displayTitle)) ?? title
        timestamp = try c.decode(String.self, forKey: .timestamp)
        microSegments = (try? c.decode([ShiurMicroSegment].self, forKey: .microSegments)) ?? []
        sefariaIndex = try? c.decode(Int.self, forKey: .sefariaIndex)
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
    let amudBSegmentIndex: Int?
    let amudBTimestamp: String?
    /// Display title of the ### micro-segment where amud B begins (nil if amud B starts at a ## boundary).
    let amudBMicroTitle: String?
    /// 0-based index of the first amud B segment in the flat Sefaria array (= amud A segment count).
    /// Nil if find_sefaria_indices.py has not been run for this daf.
    let amudBSefariaIndex: Int?

    var amudBSeconds: Double? {
        guard let ts = amudBTimestamp else { return nil }
        let parts = ts.split(separator: ":").compactMap { Double($0) }
        guard parts.count == 2 else { return nil }
        return parts[0] * 60 + parts[1]
    }

    enum CodingKeys: String, CodingKey {
        case macroSegments = "macro_segments"
        case amudBSegmentIndex = "amud_b_segment_index"
        case amudBTimestamp = "amud_b_timestamp"
        case amudBMicroTitle = "amud_b_micro_title"
        case amudBSefariaIndex = "amud_b_sefaria_index"
    }
}

// MARK: - Client

@MainActor
class ShiurClient: ObservableObject {
    static let shared = ShiurClient()

    @Published var segments: [ShiurSegment] = []
    @Published var currentSegmentIndex: Int = 0
    /// Segment index where amud B begins (nil if not detected for this daf).
    @Published var amudBSegmentIndex: Int? = nil
    /// Seconds into the audio where amud B begins (nil if not detected).
    @Published var amudBSeconds: Double? = nil
    /// Display title of the ### micro-segment where amud B begins (nil if at a ## boundary or not detected).
    @Published var amudBMicroTitle: String? = nil
    /// 0-based Sefaria flat-array index where amud B begins (nil if not yet computed).
    @Published var amudBSefariaIndex: Int? = nil
    /// Lecture rewrite text (pass 2) for the loaded daf, or nil if not available.
    @Published var shiurRewrite: String? = nil
    /// Lecture text with Sefaria sources inserted (pass 3), or nil if not available.
    @Published var shiurFinal: String? = nil
    /// Segments frozen at audio play-start — independent of which daf the user is viewing.
    @Published var audioSegments: [ShiurSegment] = []
    /// Position within the audio episode — driven by updateCurrentSegment, never touches currentSegmentIndex.
    @Published var audioCurrentSegmentIndex: Int = 0

    private let edgeFunctionURL = "https://zewdazoijdpakugfvnzt.supabase.co/functions/v1/get-shiur"

    private var loadedKey: String? = nil   // "Tractate-daf_float" — avoids redundant fetches

    func loadSegments(tractate: String, daf: Double) async {
        let key = "\(tractate)-\(daf)"
        guard key != loadedKey else { return }
        segments = []
        currentSegmentIndex = 0
        amudBSegmentIndex = nil
        amudBSeconds = nil
        amudBMicroTitle = nil
        amudBSefariaIndex = nil
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
                amudBSegmentIndex = decoded.amudBSegmentIndex
                amudBSeconds = decoded.amudBSeconds
                amudBMicroTitle = decoded.amudBMicroTitle
                amudBSefariaIndex = decoded.amudBSefariaIndex
            }

            shiurRewrite = first["rewrite"] as? String
            shiurFinal = first["final"] as? String
            loadedKey = key
        } catch {
            // Silently fail — chapter markers and lecture context are enhancements, not critical
        }
    }

    /// Snapshot current segments as the audio segments; call when audio starts playing.
    func snapshotAudioSegments() {
        audioSegments = segments
        audioCurrentSegmentIndex = currentSegmentIndex
    }

    /// Jump the audio chapter strip to a segment — does not affect shiur text.
    func jumpToAudioSegment(_ idx: Int) {
        guard !audioSegments.isEmpty else { return }
        audioCurrentSegmentIndex = max(0, min(idx, audioSegments.count - 1))
    }

    /// Update audioCurrentSegmentIndex based on audio playback position — never touches currentSegmentIndex.
    func updateCurrentSegment(currentTime: Double) {
        guard !audioSegments.isEmpty else { return }
        var idx = 0
        for (i, seg) in audioSegments.enumerated() {
            if currentTime >= seg.seconds { idx = i }
        }
        if idx != audioCurrentSegmentIndex { audioCurrentSegmentIndex = idx }
    }

    /// Clear all state when stopping audio or navigating to a new daf.
    func reset() {
        segments = []
        currentSegmentIndex = 0
        amudBSegmentIndex = nil
        amudBSeconds = nil
        amudBMicroTitle = nil
        amudBSefariaIndex = nil
        shiurRewrite = nil
        shiurFinal = nil
        audioSegments = []
        audioCurrentSegmentIndex = 0
        loadedKey = nil
    }
}
