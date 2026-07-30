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
    /// True if sefariaIndex is a genuine blockquote match; false if it's a carried-forward
    /// placeholder (e.g. a shiur-discussion segment with no Talmudic quote of its own); nil
    /// if find_sefaria_indices.py hasn't been re-run with this field for this daf yet.
    let matched: Bool?

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
        case matched
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        displayTitle = (try? c.decode(String.self, forKey: .displayTitle)) ?? title
        timestamp = try c.decode(String.self, forKey: .timestamp)
        microSegments = (try? c.decode([ShiurMicroSegment].self, forKey: .microSegments)) ?? []
        sefariaIndex = try? c.decode(Int.self, forKey: .sefariaIndex)
        matched = try? c.decode(Bool.self, forKey: .matched)
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

    /// "Tractate-daf_float" — avoids redundant fetches; published so callers can observe
    /// "a fresh daf's shiur just finished loading" (fires exactly once per successful load,
    /// unlike amudBSegmentIndex which can coincidentally repeat across dafs).
    @Published var loadedKey: String? = nil

    /// `resolveInitialIndex`, if provided, is called once segments/amudB* are decoded but
    /// *before* shiurRewrite/shiurFinal are published — returning a non-nil index sets
    /// currentSegmentIndex to it at that point. This must happen before the text publishes:
    /// ShiurTextView's `.task(id: rewriteText)` captures `currentSegmentIndex` synchronously
    /// the instant the text changes, so setting the index via a separate onChange *after* the
    /// text already changed loses the race — the pill ends up on the right segment (since it
    /// reads currentSegmentIndex directly) but the initial scroll lands wherever the task's
    /// stale captured value pointed, not where the index was moved to.
    func loadSegments(tractate: String, daf: Double,
                       resolveInitialIndex: ((ShiurClient) -> Int?)? = nil) async {
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

            if let resolved = resolveInitialIndex?(self) {
                currentSegmentIndex = resolved
            }

            shiurRewrite = first["rewrite"] as? String
            shiurFinal = first["final"] as? String
            loadedKey = key
        } catch {
            // Silently fail — chapter markers and lecture context are enhancements, not critical
        }
    }

    /// Index of the first segment with a genuine (non-carried-forward) match into the current
    /// daf's Sefaria text — i.e. where the shiur actually starts covering Amud A's real content,
    /// as opposed to introductory material or leftover discussion of the previous daf's Amud B.
    /// Segments before the first real match are always intro/carry-forward content (see
    /// find_sefaria_indices.py's carry-forward rule), so this is a reliable anchor with no
    /// backend changes needed. Falls back to 0 if no segment has been matched yet.
    var amudASegmentIndex: Int {
        segments.firstIndex(where: { $0.matched == true }) ?? 0
    }

    /// Amud B segment, falling back to a sefariaIndex-based lookup when find_amud_b.py couldn't
    /// confidently place Amud B via its heading-text matching (amudBSegmentIndex is nil — a
    /// "MISS" in that script's own terms) but find_sefaria_indices.py's coarser boundary
    /// (amudBSefariaIndex) is available, which has much wider corpus coverage since it's just
    /// the amud A item count, not a text-matching heuristic. Same "owning segment" pattern used
    /// elsewhere (see ContentView.shiurSegmentIndex(forRangeStarting:)): the last segment with a
    /// genuine match whose own sefariaIndex is ≤ the boundary.
    var effectiveAmudBSegmentIndex: Int? {
        if let amudBSegmentIndex { return amudBSegmentIndex }
        guard let target = amudBSefariaIndex else { return nil }
        var best: Int? = nil
        for (idx, seg) in segments.enumerated() {
            guard seg.matched != false, let sIdx = seg.sefariaIndex, sIdx <= target else { continue }
            best = idx
        }
        return best
    }

    /// Snapshot current segments as the audio segments; call when audio starts playing.
    func snapshotAudioSegments() {
        audioSegments = segments
        audioCurrentSegmentIndex = currentSegmentIndex
    }

    /// Drop the audio snapshot without touching the selected daf's own shiur state.
    /// Used when playback starts on something that has no shiur segments at all (a
    /// Resources-tab episode), so the chapter strip stays hidden rather than showing
    /// whatever daf happened to be selected.
    func clearAudioSegments() {
        audioSegments = []
        audioCurrentSegmentIndex = 0
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
