import SwiftUI

/// Displays the lecture rewrite as a formatted scrollable document.
/// Auto-scrolls to the current audio chapter as the segment index advances.
struct ShiurTextView: View {
    let rewriteText: String
    let currentSegmentIndex: Int
    let foreground: Color
    var useWhiteBackground: Bool = false

    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium

    /// Amber for Talmudic source words on the blue background; app blue on white background.
    private static let amber    = Color(red: 1.0,   green: 0.72,  blue: 0.0)
    private static let appBlue  = SplashView.background

    private var sourceWordColor: Color {
        useWhiteBackground ? Self.appBlue : Self.amber
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(blocks) { item in
                        blockView(item)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
            }
            .dynamicTypeSize(studyFontSize.dynamicTypeSize)
            .onChange(of: currentSegmentIndex) { _, newIdx in
                withAnimation(.easeInOut(duration: 0.4)) {
                    proxy.scrollTo("seg-\(newIdx)", anchor: .top)
                }
            }
            .onAppear {
                proxy.scrollTo("seg-\(currentSegmentIndex)", anchor: .top)
            }
        }
    }

    // MARK: - Block rendering

    @ViewBuilder
    private func blockView(_ item: ParsedBlock) -> some View {
        switch item {
        case .h2(let id, let segIdx, let text):
            let isActive = segIdx == currentSegmentIndex
            Text(text)
                .font(.headline)
                .foregroundStyle(isActive ? foreground : foreground.opacity(0.75))
                .padding(.top, segIdx == 0 ? 0 : 20)
                .padding(.bottom, 4)
                .id(id)

        case .h3(let id, let text):
            Text(text)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(foreground.opacity(0.7))
                .padding(.top, 12)
                .padding(.bottom, 2)
                .id(id)

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
        }
    }

    // MARK: - Helpers

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

        var id: String {
            switch self {
            case .h2(let id, _, _):         return id
            case .h3(let id, _):            return id
            case .body(let id, _):          return id
            case .blockquote(let id, _, _, _): return id
            }
        }
    }

    // MARK: - Parsing

    private var blocks: [ParsedBlock] {
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
