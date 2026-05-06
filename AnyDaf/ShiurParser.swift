import Foundation

// MARK: - Parsed block types

enum ParsedBlock: Identifiable {
    case h2(id: String, segIdx: Int, text: String)
    case h3(id: String, text: String)
    case body(id: String, text: String)
    case blockquote(id: String, source: String, translation: String, showLabel: Bool)

    var id: String {
        switch self {
        case .h2(let id, _, _):             return id
        case .h3(let id, _):               return id
        case .body(let id, _):             return id
        case .blockquote(let id, _, _, _): return id
        }
    }
}

// MARK: - Parser

enum ShiurParser {
    /// Parse a shiur rewrite text string into displayable blocks.
    /// Safe to call off the main thread.
    nonisolated static func parseBlocks(from rewriteText: String) -> [ParsedBlock] {
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
                let lower = content.lowercased()
                if lower.hasPrefix("**hebrew") || lower.hasPrefix("**aramaic") {
                    inTranslation = false
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
