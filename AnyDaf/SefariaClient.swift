import Foundation

// MARK: - AnyDaf → Sefaria name mapping

/// Only tractates whose AnyDaf canonical name differs from Sefaria's.
private let anyDafToSefaria: [String: String] = [
    "Eiruvin":      "Eruvin",
    "Ta\u{2019}anit": "Taanit",
    "Hullin":       "Chullin",
]

private func sefariaName(for tractate: String) -> String {
    anyDafToSefaria[tractate] ?? tractate
}

/// Maps daf+amud keys to the Sefaria ref to fetch for tractates that use non-standard
/// pagination (Jerusalem Talmud, Mishnah-only). Missing keys mean no text for that amud.
///
/// Shekalim: Jerusalem Talmud — Daf Yomi alt-struct maps to chapter:halakha:segment refs.
private let shekalimDafYomiRefs: [String: String] = [
    "2a":  "Jerusalem Talmud Shekalim 1:1:1-5",
    "2b":  "Jerusalem Talmud Shekalim 1:1:5-10",
    "3a":  "Jerusalem Talmud Shekalim 1:1:10-2:5",
    "3b":  "Jerusalem Talmud Shekalim 1:2:5-4:1",
    "4a":  "Jerusalem Talmud Shekalim 1:4:1-5",
    "4b":  "Jerusalem Talmud Shekalim 1:4:5-9",
    "5a":  "Jerusalem Talmud Shekalim 1:4:9-2:1:4",
    "5b":  "Jerusalem Talmud Shekalim 2:1:4-3:1",
    "6a":  "Jerusalem Talmud Shekalim 2:3:1-4:1",
    "6b":  "Jerusalem Talmud Shekalim 2:4:1-5",
    "7a":  "Jerusalem Talmud Shekalim 2:4:5-5:4",
    "7b":  "Jerusalem Talmud Shekalim 2:5:4-3:1:3",
    "8a":  "Jerusalem Talmud Shekalim 3:1:3-2:2",
    "8b":  "Jerusalem Talmud Shekalim 3:2:2-8",
    "9a":  "Jerusalem Talmud Shekalim 3:2:8-3:1",
    "9b":  "Jerusalem Talmud Shekalim 3:3:1-4:1:1",
    "10a": "Jerusalem Talmud Shekalim 4:1:1-2:1",
    "10b": "Jerusalem Talmud Shekalim 4:2:1-4",
    "11a": "Jerusalem Talmud Shekalim 4:2:4-3:2",
    "11b": "Jerusalem Talmud Shekalim 4:3:2-4:1",
    "12a": "Jerusalem Talmud Shekalim 4:4:1-5",
    "12b": "Jerusalem Talmud Shekalim 4:4:5-9",
    "13a": "Jerusalem Talmud Shekalim 4:4:9-5:1:3",
    "13b": "Jerusalem Talmud Shekalim 5:1:3-12",
    "14a": "Jerusalem Talmud Shekalim 5:1:12-21",
    "14b": "Jerusalem Talmud Shekalim 5:1:21-3:2",
    "15a": "Jerusalem Talmud Shekalim 5:3:2-4:10",
    "15b": "Jerusalem Talmud Shekalim 5:4:10-6:1:5",
    "16a": "Jerusalem Talmud Shekalim 6:1:5-11",
    "16b": "Jerusalem Talmud Shekalim 6:1:11-2:1",
    "17a": "Jerusalem Talmud Shekalim 6:2:1-7",
    "17b": "Jerusalem Talmud Shekalim 6:2:7-3:3",
    "18a": "Jerusalem Talmud Shekalim 6:3:3-4:2",
    "18b": "Jerusalem Talmud Shekalim 6:4:2-7",
    "19a": "Jerusalem Talmud Shekalim 6:4:7-7:2:1",
    "19b": "Jerusalem Talmud Shekalim 7:2:1-7",
    "20a": "Jerusalem Talmud Shekalim 7:2:7-3:2",
    "20b": "Jerusalem Talmud Shekalim 7:3:2-7",
    "21a": "Jerusalem Talmud Shekalim 7:3:7-8:1:1",
    "21b": "Jerusalem Talmud Shekalim 8:1:1-3:1",
    "22a": "Jerusalem Talmud Shekalim 8:3:1-4:4",
    "22b": "Jerusalem Talmud Shekalim 8:4:4",
]

/// Kinnim: Mishnah-only tractate. User-specified mapping: daf 22=ch1, 23=ch2, 24-25a=ch3.
/// Only amud 'a' of each daf has content; 'b' amudim are absent (no text).
private let kinnimMishnahRefs: [String: String] = [
    "22a": "Mishnah Kinnim 1",
    "23a": "Mishnah Kinnim 2",
    "24a": "Mishnah Kinnim 3:1-5",
    "25a": "Mishnah Kinnim 3:6",
]

/// Middot: Mishnah-only tractate. Mapping derived from Vilna Shas page markers.
/// Chapter 1 (9 mishnayot): 34a=1-4, 34b=5-9
/// Chapter 2 (6 mishnayot): 35a=1-3, 35b=4-6
/// Chapter 3 (8 mishnayot): 36a (fits on one amud)
/// Chapter 4 (7 mishnayot): 36b=4:1-2, 37a=4:3-7
/// Chapter 5 (4 mishnayot): 37b
private let middotMishnahRefs: [String: String] = [
    "34a": "Mishnah Middot 1:1-4",
    "34b": "Mishnah Middot 1:5-9",
    "35a": "Mishnah Middot 2:1-3",
    "35b": "Mishnah Middot 2:4-6",
    "36a": "Mishnah Middot 3",
    "36b": "Mishnah Middot 4:1-2",
    "37a": "Mishnah Middot 4:3-7",
    "37b": "Mishnah Middot 5",
]

// MARK: - Sefaria API Client

@MainActor
class SefariaClient {

    enum SefariaError: LocalizedError {
        case invalidURL
        case networkError(Error)
        case noTextFound
        case decodingError

        var errorDescription: String? {
            switch self {
            case .invalidURL:          return "Invalid Sefaria URL"
            case .networkError(let e): return "Network error: \(e.localizedDescription)"
            case .noTextFound:         return "No text found for this daf"
            case .decodingError:       return "Could not parse Sefaria response"
            }
        }
    }

    // MARK: - Ref resolution

    /// Returns the Sefaria ref string for the given tractate/daf/amud.
    /// Throws `noTextFound` for tractates with special pagination (Shekalim, Kinnim, Middot)
    /// when the specific amud has no mapped text.
    private func sefariaRef(tractate: String, daf: Int, amud: String) throws -> String {
        let key = "\(daf)\(amud)"
        switch tractate {
        case "Shekalim":
            guard let ref = shekalimDafYomiRefs[key] else { throw SefariaError.noTextFound }
            return ref
        case "Kinnim":
            guard let ref = kinnimMishnahRefs[key] else { throw SefariaError.noTextFound }
            return ref
        case "Middot":
            guard let ref = middotMishnahRefs[key] else { throw SefariaError.noTextFound }
            return ref
        default:
            return "\(sefariaName(for: tractate)).\(daf)\(amud)"
        }
    }

    /// Fetches text segments for one amud from Sefaria.
    /// - Parameter language: `"en"` for English translation (default), `"he"` for Hebrew/Aramaic source.
    func fetchText(tractate: String, daf: Int, amud: String, language: String = "en") async throws -> [String] {
        let ref = try sefariaRef(tractate: tractate, daf: daf, amud: amud)

        var components = URLComponents()
        components.scheme = "https"
        components.host = "www.sefaria.org"
        components.path = "/api/v3/texts/\(ref)"
        components.queryItems = language == "he"
            ? [URLQueryItem(name: "version", value: "primary"),
               URLQueryItem(name: "language", value: "he")]
            : [URLQueryItem(name: "version", value: "english"),
               URLQueryItem(name: "language", value: "en")]

        guard let url = components.url else {
            throw SefariaError.invalidURL
        }

        let (data, _): (Data, URLResponse)
        do {
            (data, _) = try await URLSession.shared.data(from: url)
        } catch {
            throw SefariaError.networkError(error)
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let versions = json["versions"] as? [[String: Any]],
              let firstVersion = versions.first,
              let textValue = firstVersion["text"]
        else {
            throw SefariaError.noTextFound
        }

        let textArray = flattenTextValue(textValue)
        guard !textArray.isEmpty else { throw SefariaError.noTextFound }
        let filtered = textArray.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        guard !filtered.isEmpty else { throw SefariaError.noTextFound }
        if tractate == "Kinnim" || tractate == "Middot" {
            return applyMishnaLabels(to: filtered, ref: ref, hebrew: language == "he")
        }
        return filtered
    }

    /// Prepends [ch:mishna] labels to each segment of a Mishnah-only tractate fetch.
    /// English: [3:4]  Hebrew: [ג:ד]
    /// Parses chapter and optional start mishna from the ref, e.g. "Mishnah Middot 4:3-7" → ch4, m3.
    private func applyMishnaLabels(to segments: [String], ref: String, hebrew: Bool) -> [String] {
        let pattern = #"Mishnah \w+ (\d+)(?::(\d+))?"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: ref, range: NSRange(ref.startIndex..., in: ref)),
              let chRange = Range(match.range(at: 1), in: ref),
              let chapter = Int(ref[chRange])
        else { return segments }

        let startMishna: Int
        if match.range(at: 2).location != NSNotFound,
           let mRange = Range(match.range(at: 2), in: ref),
           let m = Int(ref[mRange]) {
            startMishna = m
        } else {
            startMishna = 1
        }

        return segments.enumerated().map { (idx, seg) in
            let mishna = startMishna + idx
            let label = hebrew
                ? "[\(hebrewNumeral(chapter)):\(hebrewNumeral(mishna))]"
                : "[\(chapter):\(mishna)]"
            return "\(label) <b>\(seg)</b>"
        }
    }

    /// Converts an integer (1–22) to its Hebrew letter numeral (gematria).
    private func hebrewNumeral(_ n: Int) -> String {
        let letters = ["", "א","ב","ג","ד","ה","ו","ז","ח","ט","י",
                       "יא","יב","יג","יד","טו","טז","יז","יח","יט","כ","כא","כב"]
        guard n >= 1, n < letters.count else { return "\(n)" }
        return letters[n]
    }

    /// Recursively flattens Sefaria's text value, which may be a String, [String],
    /// or nested [[String]] (Jerusalem Talmud responses can be multi-level).
    private func flattenTextValue(_ value: Any) -> [String] {
        if let string = value as? String { return [string] }
        if let array = value as? [Any] { return array.flatMap { flattenTextValue($0) } }
        return []
    }

    /// Fetches text for a full daf (both amudim).
    /// Uses `try?` per amud so Mishnah-only tractates (where one amud may have no text)
    /// don't fail the entire fetch — only throws if both amudim return nothing.
    func fetchFullDaf(tractate: String, daf: Int) async throws -> [String] {
        async let amudA = fetchText(tractate: tractate, daf: daf, amud: "a")
        async let amudB = fetchText(tractate: tractate, daf: daf, amud: "b")
        let a = (try? await amudA) ?? []
        let b = (try? await amudB) ?? []
        let combined = a + b
        if combined.isEmpty { throw SefariaError.noTextFound }
        return combined
    }

    // MARK: - Section parsing

    /// Maximum number of Sefaria segments per study section.
    /// Sections exceeding this are subdivided so that no single quiz covers too much material.
    private static let maxSegmentsPerSection = 10

    /// Parses raw HTML segments into StudySections.
    ///
    /// **Phase 1 – header split:** detects `<strong>MISHNA:</strong>` / `<strong>GEMARA:</strong>`
    /// anywhere in a segment (they often appear mid-segment after `<br><br>`).
    ///
    /// **Phase 2 – size cap:** any header-defined section that exceeds `maxSegmentsPerSection`
    /// is split into equal sub-sections labelled "GEMARA, Part 1", "GEMARA, Part 2", etc.
    /// This ensures that a long Gemara spanning both amudim is broken into balanced chunks
    /// rather than one giant section.
    ///
    /// - Parameter hebrewSegments: optional parallel Hebrew/Aramaic segments (same count as
    ///   `segments`). When provided, each `StudySection.hebrewText` is built from the
    ///   corresponding Hebrew segments using the same index boundaries.
    static func parseSections(from segments: [String],
                              hebrewSegments: [String]? = nil) -> [StudySection] {

        // ── Phase 1: header-based split, tracking original segment indices ──────
        // Each part stores its English text fragments AND the original segment indices
        // that contributed to it (used to slice the Hebrew array later).
        var rawParts: [(title: String, segs: [String], segIndices: [Int])] = []
        var currentTitle = "Introduction"
        var currentSegs: [String] = []
        var currentIndices: [Int] = []

        for (segIdx, segment) in segments.enumerated() {
            if let headerInfo = extractSectionHeader(from: segment) {
                // Text before the header stays with the current section
                if headerInfo.location > 0 {
                    let idx = segment.index(segment.startIndex, offsetBy: headerInfo.location)
                    let before = String(segment[..<idx]).trimmingCharacters(in: .whitespacesAndNewlines)
                    if !before.isEmpty {
                        currentSegs.append(before)
                        // Don't add segIdx here — the Hebrew segment goes with the new section
                    }
                }

                if !currentSegs.isEmpty {
                    rawParts.append((currentTitle, currentSegs, currentIndices))
                }

                currentTitle = headerInfo.title
                let idx = segment.index(segment.startIndex, offsetBy: headerInfo.location)
                let from = String(segment[idx...]).trimmingCharacters(in: .whitespacesAndNewlines)
                currentSegs = from.isEmpty ? [] : [from]
                // For mid-segment splits, the Hebrew segment goes with the new section
                currentIndices = [segIdx]
            } else {
                currentSegs.append(segment)
                currentIndices.append(segIdx)
            }
        }
        if !currentSegs.isEmpty { rawParts.append((currentTitle, currentSegs, currentIndices)) }

        // Rename a lone untitled section
        if rawParts.count == 1 && rawParts[0].title == "Introduction" {
            rawParts[0] = (title: "Full Text", segs: rawParts[0].segs, segIndices: rawParts[0].segIndices)
        }

        // Helper: join Hebrew segments for given indices
        func hebrewText(for indices: [Int]) -> String? {
            guard let hSegs = hebrewSegments else { return nil }
            let mapped = indices.compactMap { $0 < hSegs.count ? hSegs[$0] : nil }
            return mapped.isEmpty ? nil : mapped.joined(separator: "\n\n")
        }

        // Helper: return array of individual Hebrew segments for given indices
        func hebrewSegsArray(for indices: [Int]) -> [String] {
            guard let hSegs = hebrewSegments else { return [] }
            return indices.compactMap { $0 < hSegs.count ? hSegs[$0] : nil }
        }

        // ── Phase 2: subdivide any section that's too long ────────────────────────
        var studySections: [StudySection] = []

        for (title, segs, indices) in rawParts {
            if segs.count <= maxSegmentsPerSection {
                studySections.append(StudySection(
                    title: title,
                    rawText: segs.joined(separator: "\n\n"),
                    rawSegments: segs,
                    hebrewText: hebrewText(for: indices),
                    hebrewSegments: hebrewSegsArray(for: indices),
                    quizQuestions: []
                ))
            } else {
                let totalChunks = (segs.count + maxSegmentsPerSection - 1) / maxSegmentsPerSection
                for i in 0..<totalChunks {
                    let start = i * maxSegmentsPerSection
                    let end   = min(start + maxSegmentsPerSection, segs.count)
                    // Slice the same range from indices
                    let idxStart = min(start, indices.count)
                    let idxEnd   = min(end, indices.count)
                    studySections.append(StudySection(
                        title: "\(title), Part \(i + 1)",
                        rawText: segs[start..<end].joined(separator: "\n\n"),
                        rawSegments: Array(segs[start..<end]),
                        hebrewText: hebrewText(for: Array(indices[idxStart..<idxEnd])),
                        hebrewSegments: hebrewSegsArray(for: Array(indices[idxStart..<idxEnd])),
                        quizQuestions: []
                    ))
                }
            }
        }

        // Final fallback: if nothing parsed, chunk all segments with numbered titles
        if studySections.isEmpty {
            let totalChunks = (segments.count + maxSegmentsPerSection - 1) / maxSegmentsPerSection
            for i in 0..<totalChunks {
                let start = i * maxSegmentsPerSection
                let end   = min(start + maxSegmentsPerSection, segments.count)
                let indices = Array(start..<end)
                studySections.append(StudySection(
                    title: "Section \(i + 1)",
                    rawText: segments[start..<end].joined(separator: "\n\n"),
                    rawSegments: Array(segments[start..<end]),
                    hebrewText: hebrewText(for: indices),
                    hebrewSegments: hebrewSegsArray(for: indices),
                    quizQuestions: []
                ))
            }
        }

        return studySections
    }

    /// Result type for header detection, carrying both the header title and its
    /// character offset within the segment so callers can split mid-segment text.
    private struct SectionHeaderMatch {
        let title: String
        let location: Int  // character offset in the original string
    }

    /// Detects a bold header ANYWHERE in the segment, e.g. <strong>MISHNA:</strong>
    /// or <b>GEMARA:</b>. Returns the header text and its character offset if found.
    private static func extractSectionHeader(from html: String) -> SectionHeaderMatch? {
        // Match <strong>WORD:</strong> or <b>WORD:</b> anywhere in the segment
        let pattern = #"<(?:strong|b)>([A-Z][A-Z ]*):?</(?:strong|b)>"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: html, range: NSRange(html.startIndex..., in: html)),
              let titleRange = Range(match.range(at: 1), in: html)
        else { return nil }

        let title = String(html[titleRange]).trimmingCharacters(in: .whitespaces)
        let location = match.range.location  // NSRange location (== character offset for BMP text)
        return SectionHeaderMatch(title: title, location: location)
    }

    /// Removes `<sup …>N</sup>` footnote-number markers and
    /// `<i class="footnote">…</i>` blocks (including nested `<i>` tags).
    private static func stripFootnoteBlocks(_ html: String) -> String {
        // Remove <sup …>N</sup> footnote-marker spans (class attr varies)
        var s = html.replacingOccurrences(
            of: #"<sup\b[^>]*>[^<]*</sup>"#,
            with: "", options: .regularExpression)

        // Remove <i class="footnote">…</i> blocks.
        // The footnote text may contain nested <i> tags, so we track depth
        // rather than relying on a simple regex.
        var result = ""
        var idx = s.startIndex
        while idx < s.endIndex {
            // Find the next opening <i tag
            guard let tagOpen = s[idx...].range(of: "<i", options: .caseInsensitive) else {
                result += s[idx...]
                break
            }
            guard let tagClose = s[tagOpen.lowerBound...].range(of: ">") else {
                result += s[idx...]
                break
            }
            let fullTag = s[tagOpen.lowerBound..<tagClose.upperBound]
            guard fullTag.contains(#"class="footnote""#) else {
                // Not a footnote tag — keep everything up to and including it
                result += s[idx..<tagClose.upperBound]
                idx = tagClose.upperBound
                continue
            }
            // It's a footnote opening tag — keep text before it, skip the block
            result += s[idx..<tagOpen.lowerBound]
            var pos = tagClose.upperBound
            var depth = 1
            while depth > 0, pos < s.endIndex {
                let rem = s[pos...]
                let nextOpen  = rem.range(of: "<i",  options: .caseInsensitive)
                let nextClose = rem.range(of: "</i>", options: .caseInsensitive)
                if let open = nextOpen, let close = nextClose,
                   open.lowerBound < close.lowerBound {
                    // Another <i> opens before the next </i> — go deeper
                    if let end = s[open.upperBound...].range(of: ">") {
                        depth += 1
                        pos = end.upperBound
                    } else { break }
                } else if let close = nextClose {
                    depth -= 1
                    pos = close.upperBound
                } else { break }
            }
            idx = pos
        }
        return result
    }

    /// Strip HTML tags to produce plain text for sending to Claude.
    static func stripHTML(_ html: String) -> String {
        stripFootnoteBlocks(html)
            .replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&nbsp;", with: " ")
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&#x27;", with: "'")
            .replacingOccurrences(of: "&quot;", with: "\"")
    }
}
