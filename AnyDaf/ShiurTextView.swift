import SwiftUI

// Collects {segIdx → Y-position-in-scroll-space} for all visible ## headings.
private struct SegmentAnchorKey: PreferenceKey {
    static var defaultValue: [Int: CGFloat] = [:]
    static func reduce(value: inout [Int: CGFloat], nextValue: () -> [Int: CGFloat]) {
        value.merge(nextValue()) { $1 }
    }
}

// Reference-type flag used to suppress the programmatic scrollTo that would
// otherwise fire when currentSegmentIndex changes due to user-scroll detection.
private class ScrollDetectionState {
    var suppressNextScrollTo: Int? = nil
    /// True while animateScrollTo is in flight — suppresses onSegmentVisible to prevent
    /// intermediate scroll positions from triggering mode-sync feedback loops.
    var isProgrammaticScrolling: Bool = false
}

/// Displays the lecture rewrite as a formatted scrollable document.
/// Auto-scrolls to the current audio chapter as the segment index advances.
struct ShiurTextView: View {
    let rewriteText: String
    let currentSegmentIndex: Int
    let foreground: Color
    var useWhiteBackground: Bool = false
    /// When set, pressing B scrolls to this ### micro-segment title within the amud B macro segment.
    var amudBSegmentIndex: Int? = nil
    var amudBMicroTitle: String? = nil
    /// Macro segment where Amud A's real content begins — may be > 0 when the shiur opens with
    /// introductory material or leftover discussion of the previous daf. Drives the inline
    /// "Amud A" divider; see ShiurClient.amudASegmentIndex.
    var amudASegmentIndex: Int = 0
    /// Set by the caller to force-scroll to a specific segment index. Consumed (reset to nil) after scrolling.
    /// Using Binding<Int?> instead of a counter ensures onChange always fires (nil→N is always a change),
    /// avoids reading a potentially stale currentSegmentIndex, and cannot fire spuriously on view recreation.
    @Binding var scrollRequest: Int?
    /// Called (on main thread) when the user scrolls past a new macro segment heading.
    /// Only fired when the heading enters the upper portion of the visible scroll area.
    var onSegmentVisible: ((Int) -> Void)? = nil

    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium

    /// Returns the scroll target ID for a given segment index.
    /// When the index is the amud B segment and a micro-title is known, returns the
    /// h3 anchor so the view scrolls to the exact ### heading rather than the ## heading.
    private func scrollTarget(for idx: Int) -> String {
        if idx == amudBSegmentIndex, let microTitle = amudBMicroTitle {
            return "h3-\(microTitle)"
        }
        return "seg-\(idx)"
    }

    /// Parsed representation of rewriteText, computed off the main thread.
    @State private var parsedBlocks: [ParsedBlock] = []
    @State private var scrollDetectionState = ScrollDetectionState()

    /// Amber for Talmudic source words on the blue background; app blue on white background.
    private static let amber    = Color(red: 1.0,   green: 0.72,  blue: 0.0)
    private static let appBlue  = SplashView.background

    private var sourceWordColor: Color {
        useWhiteBackground ? Self.appBlue : Self.amber
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(parsedBlocks) { item in
                        blockView(item)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.top, 4)
                .padding(.bottom, 12)
            }
            .coordinateSpace(name: "shiurScroll")
            .dynamicTypeSize(studyFontSize.dynamicTypeSize)
            // Reparse whenever the text changes — runs on a background thread so large
            // shiur texts cannot hang the main thread and trigger a watchdog kill.
            .task(id: rewriteText) {
                let text = rewriteText
                let idx  = currentSegmentIndex
                let innerTask = Task.detached(priority: .userInitiated) {
                    Self.parseBlocks(from: text)
                }
                let computed = await innerTask.value
                guard !Task.isCancelled else { return }
                // Suppress onPreferenceChange during initial layout: setting parsedBlocks
                // causes geometry readers to fire with scroll position 0, which would
                // call onSegmentVisible(0) and corrupt the active segment.
                scrollDetectionState.isProgrammaticScrolling = true
                parsedBlocks = computed
                if idx > 0 {
                    // Allow SwiftUI to commit the new parsedBlocks layout before scrolling.
                    try? await Task.sleep(nanoseconds: 50_000_000)
                    proxy.scrollTo(scrollTarget(for: idx), anchor: .top)
                } else {
                    proxy.scrollTo(scrollTarget(for: idx), anchor: .top)
                }
                Task {
                    try? await Task.sleep(nanoseconds: 650_000_000)
                    scrollDetectionState.isProgrammaticScrolling = false
                }
            }
            .onChange(of: currentSegmentIndex) { _, newIdx in
                // Suppress if this change originated from user scroll detection.
                if scrollDetectionState.suppressNextScrollTo == newIdx {
                    scrollDetectionState.suppressNextScrollTo = nil
                    return
                }
                scrollDetectionState.isProgrammaticScrolling = true
                proxy.scrollTo(scrollTarget(for: newIdx), anchor: .top)
                Task {
                    try? await Task.sleep(nanoseconds: 650_000_000)
                    scrollDetectionState.isProgrammaticScrolling = false
                }
            }
            // Fires on every pill tap (nil→idx is always a change). Scrolls to the explicit
            // requested index rather than reading currentSegmentIndex, then resets to nil so
            // the same pill can be tapped again and onChange fires a second time (idx→nil→idx).
            .onChange(of: scrollRequest) { _, newIdx in
                guard let idx = newIdx, !parsedBlocks.isEmpty else { return }
                scrollDetectionState.isProgrammaticScrolling = true
                // Always scroll to segment top ("seg-N"), never to the amud-B h3.
                // scrollTarget(for:) is intentionally NOT used here — that h3 redirect
                // is only correct for the B-toggle (onChange(of: currentSegmentIndex)).
                proxy.scrollTo("seg-\(idx)", anchor: .top)
                Task {
                    try? await Task.sleep(nanoseconds: 650_000_000)
                    scrollDetectionState.isProgrammaticScrolling = false
                }
                // Consume the request so the next tap (even to the same segment) sees a change.
                scrollRequest = nil
            }
            .onAppear {
                // Re-appear with already-parsed blocks (e.g. switching back from Study tab).
                if !parsedBlocks.isEmpty {
                    scrollDetectionState.isProgrammaticScrolling = true
                    proxy.scrollTo(scrollTarget(for: currentSegmentIndex), anchor: .top)
                    Task {
                        try? await Task.sleep(nanoseconds: 650_000_000)
                        scrollDetectionState.isProgrammaticScrolling = false
                    }
                }
            }
            .onPreferenceChange(SegmentAnchorKey.self) { anchors in
                guard onSegmentVisible != nil, !parsedBlocks.isEmpty else { return }
                guard !scrollDetectionState.isProgrammaticScrolling else { return }
                // Find the segment heading closest to the top of the scroll area (Y ≤ 80pt).
                let passed = anchors.filter { $0.value <= 80 }
                guard let top = passed.max(by: { $0.value < $1.value }) else { return }
                let newIdx = top.key
                guard newIdx != currentSegmentIndex else { return }
                scrollDetectionState.suppressNextScrollTo = newIdx
                onSegmentVisible?(newIdx)
            }
        }
    }

    // MARK: - Block rendering

    @ViewBuilder
    private func blockView(_ item: ParsedBlock) -> some View {
        switch item {
        case .h2(let id, let segIdx, let text):
            let isActive = segIdx == currentSegmentIndex
            VStack(alignment: .leading, spacing: 4) {
                if segIdx == amudASegmentIndex {
                    amudDivider("Amud A")
                }
                if segIdx == amudBSegmentIndex, amudBMicroTitle == nil {
                    amudDivider("Amud B")
                }
                Text(text)
                    .font(.headline)
                    .foregroundStyle(isActive ? foreground : foreground.opacity(0.75))
            }
            .padding(.top, segIdx == 0 ? 0 : 20)
            .padding(.bottom, 4)
            .id(id)
            .background(
                GeometryReader { geo in
                    Color.clear.preference(
                        key: SegmentAnchorKey.self,
                        value: [segIdx: geo.frame(in: .named("shiurScroll")).minY]
                    )
                }
            )

        case .h3(_, let text):
            VStack(alignment: .leading, spacing: 4) {
                if text == amudBMicroTitle {
                    amudDivider("Amud B")
                }
                Text(text)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(foreground.opacity(0.7))
            }
            .padding(.top, 12)
            .padding(.bottom, 2)
            .id("h3-\(text)")

        case .body(let id, let text):
            Text(italicLatinAttributedString(text, font: .body))
                .font(.body)
                .foregroundStyle(foreground.opacity(0.88))
                .lineSpacing(4)
                .padding(.bottom, 10)
                .id(id)

        case .blockquote(let id, let source, let translation, let showLabel):
            HStack(alignment: .top, spacing: 0) {
                Rectangle()
                    .fill(foreground.opacity(0.35))
                    .frame(width: 3)
                VStack(alignment: .leading, spacing: 6) {
                    if showLabel {
                        Text("Text and Translation")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(foreground.opacity(0.55))
                    }
                    // Hebrew/Aramaic source — RTL if it contains Hebrew characters
                    if !source.isEmpty {
                        let isHebrew = containsHebrew(source)
                        Text(italicLatinAttributedString(source, font: .callout))
                            .font(.callout)
                            .foregroundStyle(foreground.opacity(0.85))
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .environment(\.layoutDirection, isHebrew ? .rightToLeft : .leftToRight)
                    }
                    // English translation — Talmudic source words in amber, transliterated in italic
                    if !translation.isEmpty {
                        Text(translationAttributedString(translation))
                            .font(.callout)
                            .foregroundStyle(foreground.opacity(0.75))
                    }
                }
                .padding(.leading, 10)
                .padding(.trailing, 6)
                .padding(.vertical, 8)
            }
            .background(foreground.opacity(0.07))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .padding(.bottom, 12)
            .id(id)

        case .dafMarker(_, let label):
            Text("[\(label)]")
                .font(.caption.weight(.medium))
                .foregroundStyle(foreground.opacity(0.45))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 6)
        }
    }

    // MARK: - Helpers

    /// Inline "── AMUD A ──" / "── AMUD B ──" divider marking where an amud actually begins,
    /// which may land a few paragraphs into the shiur rather than at its very start.
    private func amudDivider(_ label: String) -> some View {
        HStack(spacing: 6) {
            Rectangle().fill(foreground.opacity(0.25)).frame(height: 1)
            Text(label.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(foreground.opacity(0.55))
                .fixedSize()
            Rectangle().fill(foreground.opacity(0.25)).frame(height: 1)
        }
    }

    private func containsHebrew(_ text: String) -> Bool {
        text.unicodeScalars.contains { $0.value >= 0x0590 && $0.value <= 0x05FF }
    }

    /// `*word*` → italic (if Latin). Optional `baseColor` applies to all spans (used for source-word coloring).
    private func italicLatinAttributedString(_ text: String, font: Font,
                                             baseColor: Color? = nil) -> AttributedString {
        var result = AttributedString()
        let parts = text.components(separatedBy: "*")
        for (i, part) in parts.enumerated() {
            var chunk = AttributedString(part)
            if let c = baseColor { chunk.foregroundColor = c }
            if i % 2 == 1 && !containsHebrew(part) { chunk.font = font.italic() }
            result += chunk
        }
        return result
    }

    /// Translation text: `**word**` → source-word color (italic still applied within),
    /// `*word*` → italic. Normalises `***` → `*` to avoid split confusion.
    private func translationAttributedString(_ text: String) -> AttributedString {
        var result = AttributedString()
        // *** means bold+italic in markdown; simplify to * so our split-on-** logic isn't confused
        let normalized = text.replacingOccurrences(of: "***", with: "*")
        let boldParts = normalized.components(separatedBy: "**")
        for (i, part) in boldParts.enumerated() {
            if i % 2 == 1 {
                // Source word: accent color + italic for any *...* within the span
                result += italicLatinAttributedString(part, font: .callout, baseColor: sourceWordColor)
            } else {
                result += italicLatinAttributedString(part, font: .callout)
            }
        }
        return result
    }

    // MARK: - Data model

    private enum ParsedBlock: Identifiable {
        case h2(id: String, segIdx: Int, text: String)
        case h3(id: String, text: String)
        case body(id: String, text: String)
        case blockquote(id: String, source: String, translation: String, showLabel: Bool)
        case dafMarker(id: String, label: String)

        var id: String {
            switch self {
            case .h2(let id, _, _):               return id
            case .h3(let id, _):                  return id
            case .body(let id, _):                return id
            case .blockquote(let id, _, _, _):    return id
            case .dafMarker(let id, _):           return id
            }
        }
    }

    // MARK: - Parsing

    // Static so Task.detached can call it without capturing self.
    private nonisolated static func parseBlocks(from rewriteText: String) -> [ParsedBlock] {
        var result: [ParsedBlock] = []
        var segIdx = -1
        var bodyLines: [String] = []
        var bqSourceLines: [String] = []
        var bqTranslationLines: [String] = []
        var inTranslation = false
        var counter = 0

        func flushBody() {
            let joined = bodyLines.joined(separator: " ")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !joined.isEmpty {
                result.append(.body(id: "body-\(counter)", text: joined))
                counter += 1
            }
            bodyLines = []
        }

        func flushBlockquote() {
            let src = bqSourceLines.joined(separator: " ")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let trans = bqTranslationLines.joined(separator: " ")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !src.isEmpty || !trans.isEmpty {
                // Only show the "Text and Translation" label on the first of a run of consecutive blockquotes
                let prevIsBlockquote: Bool
                if case .blockquote = result.last { prevIsBlockquote = true } else { prevIsBlockquote = false }
                result.append(.blockquote(id: "bq-\(counter)", source: src, translation: trans,
                                          showLabel: !prevIsBlockquote))
                counter += 1
            }
            bqSourceLines = []
            bqTranslationLines = []
            inTranslation = false
        }

        for line in rewriteText.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("## ") {
                flushBody(); flushBlockquote()
                segIdx += 1
                result.append(.h2(id: "seg-\(segIdx)", segIdx: segIdx,
                                  text: String(trimmed.dropFirst(3))))
            } else if trimmed.hasPrefix("### ") {
                flushBody(); flushBlockquote()
                result.append(.h3(id: "h3-\(counter)", text: String(trimmed.dropFirst(4))))
                counter += 1
            } else if trimmed.hasPrefix("# ") {
                continue  // skip top-level daf title header
            } else if trimmed.hasPrefix("> ") || trimmed == ">" {
                flushBody()
                let content = trimmed.hasPrefix("> ") ? String(trimmed.dropFirst(2)) : ""
                // Detect section labels and switch context; strip label text
                let lower = content.lowercased()
                if lower.hasPrefix("**hebrew") || lower.hasPrefix("**aramaic") {
                    inTranslation = false
                    // If the label has inline text (e.g. "**Hebrew/Aramaic:** text"), grab it
                    if let colonRange = content.range(of: ":** ") {
                        let rest = String(content[colonRange.upperBound...]).trimmingCharacters(in: .whitespaces)
                        if !rest.isEmpty { bqSourceLines.append(rest) }
                    }
                } else if lower.hasPrefix("**translation") || lower.hasPrefix("**english") {
                    inTranslation = true
                    if let colonRange = content.range(of: ":** ") {
                        let rest = String(content[colonRange.upperBound...]).trimmingCharacters(in: .whitespaces)
                        if !rest.isEmpty { bqTranslationLines.append(rest) }
                    }
                } else if !content.isEmpty {
                    if inTranslation { bqTranslationLines.append(content) }
                    else             { bqSourceLines.append(content) }
                }
            } else if trimmed.isEmpty {
                flushBody(); flushBlockquote()
            } else if trimmed.hasPrefix("[DAF:") && trimmed.hasSuffix("]") {
                flushBody(); flushBlockquote()
                let label = String(trimmed.dropFirst(5).dropLast())
                result.append(.dafMarker(id: "daf-\(counter)", label: label))
                counter += 1
            } else {
                flushBlockquote()
                bodyLines.append(trimmed)
            }
        }
        flushBody()
        flushBlockquote()
        return result
    }
}
