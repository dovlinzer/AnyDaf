import SwiftUI
import WebKit

// MARK: - Article Reader Overlay

/// Full-screen in-app article reader.
/// Presented as an overlay that springs up from the tapped card.
struct ArticleReaderView: View {
    let article: YCTArticle
    /// `nil` while the content is still loading; set to HTML string once fetched.
    let html: String?
    let onDismiss: () -> Void

    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false

    // MARK: Adaptive colours

    private var bg: Color {
        useWhiteBackground ? .white : Color(red: 0.106, green: 0.227, blue: 0.541)
    }
    private var fg: Color {
        useWhiteBackground ? Color(.label) : .white
    }
    private var mutedFg: Color { fg.opacity(0.65) }
    private var subtleFg: Color { fg.opacity(0.50) }
    private var divider: Color { fg.opacity(0.20) }
    private var tagBg: Color { fg.opacity(0.12) }

    var body: some View {
        ZStack(alignment: .top) {
            bg.ignoresSafeArea()

            VStack(spacing: 0) {

                // ── Header ────────────────────────────────────────────────────
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(article.title)
                            .font(.headline)
                            .foregroundStyle(fg)
                            .fixedSize(horizontal: false, vertical: true)

                        if !article.authorName.isEmpty {
                            Text(article.authorName)
                                .font(.subheadline.italic())
                                .foregroundStyle(fg.opacity(0.80))
                        }

                        HStack(spacing: 8) {
                            if !article.date.isEmpty {
                                Text(article.date)
                                    .font(.caption)
                                    .foregroundStyle(subtleFg)
                            }
                            ForEach(
                                ([article.matchType.referencedDaf] + article.additionalDafs)
                                    .filter { $0 > 0 }.sorted(),
                                id: \.self
                            ) { d in
                                Text("Daf \(d)")
                                    .font(.caption2)
                                    .foregroundStyle(mutedFg)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(
                                        RoundedRectangle(cornerRadius: 4).fill(tagBg)
                                    )
                            }
                        }
                    }

                    Spacer()

                    Button(action: onDismiss) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .foregroundStyle(fg.opacity(0.6))
                    }
                    .accessibilityLabel("Close article")
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 12)

                Rectangle()
                    .fill(divider)
                    .frame(height: 1)

                // ── Content ───────────────────────────────────────────────────
                if let html = html {
                    ArticleWebView(html: html, fontSize: studyFontSize.articleFontSize, useWhiteBackground: useWhiteBackground)
                } else {
                    VStack(spacing: 12) {
                        ProgressView().tint(fg)
                        Text("Loading article…")
                            .font(.caption)
                            .foregroundStyle(mutedFg)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }

                Rectangle()
                    .fill(divider)
                    .frame(height: 1)

                // ── Footer: font controls + open-in-browser ───────────────────
                HStack(spacing: 0) {
                    let cases = StudyFontSize.displayCases
                    let idx = cases.firstIndex(of: studyFontSize) ?? 1

                    Button {
                        if idx > 0 { studyFontSize = cases[idx - 1] }
                    } label: {
                        Text("A")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(idx > 0 ? fg : fg.opacity(0.3))
                            .frame(width: 36, height: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)

                    HStack(spacing: 0) {
                        Spacer(minLength: 4)
                        ForEach(cases.indices, id: \.self) { i in
                            let dotSize: CGFloat = 5 + CGFloat(i) * 2
                            Circle()
                                .fill(i == idx ? fg : fg.opacity(0.25))
                                .frame(width: dotSize, height: dotSize)
                                .animation(.spring(response: 0.25), value: studyFontSize)
                            if i < cases.count - 1 { Spacer(minLength: 4) }
                        }
                        Spacer(minLength: 4)
                    }
                    .frame(maxWidth: 120)

                    Button {
                        if idx < cases.count - 1 { studyFontSize = cases[idx + 1] }
                    } label: {
                        Text("A")
                            .font(.title2.weight(.semibold))
                            .foregroundStyle(idx < cases.count - 1 ? fg : fg.opacity(0.3))
                            .frame(width: 36, height: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)

                    Spacer()

                    // Open-in-browser
                    Button {
                        if let url = URL(string: article.link) {
                            UIApplication.shared.open(url)
                        }
                    } label: {
                        Label("Open in Browser", systemImage: "safari")
                            .font(.subheadline)
                            .foregroundStyle(fg.opacity(0.75))
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
        }
    }
}

// MARK: - Web view

/// WKWebView wrapper that renders WordPress HTML with an injected stylesheet.
///
/// - When `html` changes the view does a full reload.
/// - When only `fontSize` changes it injects a one-line JS call so the text
///   resizes instantly without any flash or scroll-position reset.
/// - All link taps are intercepted and forwarded to Safari.
private struct ArticleWebView: UIViewRepresentable {
    let html: String
    let fontSize: CGFloat
    let useWhiteBackground: Bool

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.navigationDelegate = context.coordinator
        webView.backgroundColor = .clear
        webView.isOpaque = false
        webView.scrollView.backgroundColor = .clear
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let stateKey = "\(html.hashValue)_\(useWhiteBackground)"
        if context.coordinator.loadedHTML != stateKey {
            // Full reload — content or theme changed.
            context.coordinator.loadedHTML    = stateKey
            context.coordinator.loadedFontSize = fontSize
            webView.loadHTMLString(
                styledHTML(fontSize: fontSize),
                baseURL: URL(string: "https://library.yctorah.org")
            )
        } else if context.coordinator.loadedFontSize != fontSize {
            // Only the font size changed — update via JS to preserve scroll position.
            context.coordinator.loadedFontSize = fontSize
            webView.evaluateJavaScript(
                "document.body.style.fontSize = '\(fontSize)px'"
            ) { _, _ in }
        }
    }

    // MARK: Helpers

    private func styledHTML(fontSize: CGFloat) -> String {
        let bodyColor    = useWhiteBackground ? "rgba(0,0,0,0.87)"        : "rgba(255,255,255,0.90)"
        let headingColor = useWhiteBackground ? "#111111"                  : "#ffffff"
        let linkColor    = useWhiteBackground ? "#1B3A8A"                  : "#90BAFF"
        let bqBorder     = useWhiteBackground ? "rgba(0,0,0,0.25)"         : "rgba(255,255,255,0.35)"
        let bqColor      = useWhiteBackground ? "rgba(0,0,0,0.55)"         : "rgba(255,255,255,0.65)"
        let hrColor      = useWhiteBackground ? "rgba(0,0,0,0.15)"         : "rgba(255,255,255,0.20)"

        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <style>
        * { box-sizing: border-box; }
        body {
            background: transparent;
            color: \(bodyColor);
            font-family: -apple-system, 'Helvetica Neue', sans-serif;
            font-size: \(fontSize)px;
            line-height: 1.75;
            padding: 16px 20px 60px;
            margin: 0;
        }
        a               { color: \(linkColor); }
        h1, h2, h3, h4  { color: \(headingColor); margin: 20px 0 8px; }
        p               { margin: 0 0 14px; }
        blockquote {
            border-left: 3px solid \(bqBorder);
            margin: 12px 0;
            padding-left: 14px;
            color: \(bqColor);
        }
        ul, ol { padding-left: 20px; margin-bottom: 14px; }
        li     { margin-bottom: 6px; }
        img    { max-width: 100%; height: auto; }
        hr     { border: none; border-top: 1px solid \(hrColor); margin: 20px 0; }
        </style>
        </head>
        <body>\(html)</body>
        </html>
        """
    }

    // MARK: Coordinator

    /// Tracks what the WebView last loaded so `updateUIView` can decide
    /// whether to do a full reload or a lightweight JS font update.
    final class Coordinator: NSObject, WKNavigationDelegate {
        var loadedHTML: String      = ""
        var loadedFontSize: CGFloat = 0

        func webView(_ webView: WKWebView,
                     decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if action.navigationType == .linkActivated,
               let url = action.request.url {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
        }
    }
}
