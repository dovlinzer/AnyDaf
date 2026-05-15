import UIKit
import WebKit

// MARK: - Printable content

enum PrintableContent {
    case shiur(tractate: String, daf: String, text: String)
    case talmudText(tractate: String, daf: String, sections: [StudySection], mode: SourceDisplayMode)
    case article(article: YCTArticle, html: String)
}

// MARK: - Page renderer
//
// headerHeight / footerHeight carve zones from the top/bottom of printableRect.
// WKWebView's viewPrintFormatter() properly respects contentRectForPage (unlike
// UIMarkupTextPrintFormatter which draws from printableRect.minY and ignores it).
//
// Page 0: header zone is intentionally empty — no separator line — so the HTML
// document header (logo + title) is not bisected.

private final class AnyDafPrintRenderer: UIPrintPageRenderer {
    private let runningTitle: String
    private let appBlue   = UIColor(red: 0.106, green: 0.227, blue: 0.541, alpha: 1)
    private let sideMargin: CGFloat = 36  // matches CSS body padding

    init(title: String) {
        self.runningTitle = title
        super.init()
        headerHeight = 14
        footerHeight = 14
    }

    // Running header — right-aligned, pages 2+ only. Page 0 draws nothing
    // so the first-page logo/title block isn't bisected by a separator line.
    override func drawHeaderForPage(at pageIndex: Int, in headerRect: CGRect) {
        guard pageIndex > 0 else { return }

        // Separator line at the bottom of the header zone.
        appBlue.withAlphaComponent(0.18).setStroke()
        let rule = UIBezierPath()
        rule.move(to:    CGPoint(x: headerRect.minX + sideMargin, y: headerRect.maxY - 1))
        rule.addLine(to: CGPoint(x: headerRect.maxX - sideMargin, y: headerRect.maxY - 1))
        rule.lineWidth = 0.6
        rule.stroke()

        // Running title — right-aligned, just above the rule.
        let attrs: [NSAttributedString.Key: Any] = [
            .font: UIFont.systemFont(ofSize: 9, weight: .regular),
            .foregroundColor: appBlue.withAlphaComponent(0.75)
        ]
        let str  = NSAttributedString(string: runningTitle, attributes: attrs)
        let size = str.size()
        str.draw(at: CGPoint(
            x: headerRect.maxX - sideMargin - size.width,
            y: headerRect.maxY - 1 - size.height - 4
        ))
    }

    // Footer — separator line at top of zone, attribution centered, page number right.
    override func drawFooterForPage(at pageIndex: Int, in footerRect: CGRect) {
        appBlue.withAlphaComponent(0.18).setStroke()
        let rule = UIBezierPath()
        rule.move(to:    CGPoint(x: footerRect.minX + sideMargin, y: footerRect.minY + 1))
        rule.addLine(to: CGPoint(x: footerRect.maxX - sideMargin, y: footerRect.minY + 1))
        rule.lineWidth = 0.6
        rule.stroke()

        let attribution = "Printed from AnyDaf \u{2022} Powered by YCT \u{2022} yctorah.org"
        let pageNum     = "\(pageIndex + 1)"
        let attrs: [NSAttributedString.Key: Any] = [
            .font: UIFont.systemFont(ofSize: 8),
            .foregroundColor: UIColor.gray
        ]
        let textY = footerRect.minY + 6

        let attrStr  = NSAttributedString(string: attribution, attributes: attrs)
        let attrSize = attrStr.size()
        let midX     = (footerRect.minX + sideMargin + footerRect.maxX - sideMargin) / 2
        attrStr.draw(at: CGPoint(x: midX - attrSize.width / 2, y: textY))

        let pageStr  = NSAttributedString(string: pageNum, attributes: attrs)
        let pageSize = pageStr.size()
        pageStr.draw(at: CGPoint(x: footerRect.maxX - sideMargin - pageSize.width, y: textY))
    }
}

// MARK: - Print coordinator
//
// Manages the off-screen WKWebView that renders the HTML.
// WKWebView.viewPrintFormatter() respects contentRectForPage, so content stays
// within the zones defined by headerHeight / footerHeight.  It also loads remote
// images (article photos) via normal HTTP, so images appear in the printout.

// JavaScript injected after DOM load to detect when all <img> elements have
// finished loading (or errored). Posts the "imagesReady" message to Swift.
private let imagesReadyJS = """
(function(){
  var imgs = Array.from(document.images).filter(function(i){ return !i.complete; });
  if (!imgs.length) { window.webkit.messageHandlers.imagesReady.postMessage(1); return; }
  var n = imgs.length;
  function done(){ if (--n === 0) window.webkit.messageHandlers.imagesReady.postMessage(1); }
  imgs.forEach(function(i){ i.onload = done; i.onerror = done; });
})();
"""

private final class PrintCoordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    private let htmlString:    String
    private let baseURL:       URL?
    private let rendererTitle: String
    private let jobName:       String
    private let overlay:       UIView
    private weak var window:   UIWindow?
    private var webView:       WKWebView?
    // Guards against presenting the dialog twice (message handler + fallback timer).
    private var presented = false
    private var imageDeadline: DispatchWorkItem?

    init(html: String, baseURL: URL?, title: String, jobName: String,
         overlay: UIView, window: UIWindow) {
        self.htmlString    = html
        self.baseURL       = baseURL
        self.rendererTitle = title
        self.jobName       = jobName
        self.overlay       = overlay
        self.window        = window
    }

    func start() {
        guard let window else { cleanup(); return }
        // Register the "imagesReady" message handler before creating the web view.
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "imagesReady")
        // Place off-screen but within the window so rendering isn't suppressed.
        let wv = WKWebView(frame: CGRect(x: window.bounds.maxX + 10, y: 0,
                                         width: 540, height: 720),
                           configuration: config)
        wv.navigationDelegate = self
        window.addSubview(wv)
        webView = wv
        wv.loadHTMLString(htmlString, baseURL: baseURL)
    }

    // DOM is ready; inject JS to wait for images.  Start a 10-second fallback
    // in case network images hang (e.g. no Wi-Fi) — we still show the dialog.
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let fallback = DispatchWorkItem { [weak self] in self?.presentPrintDialog() }
        imageDeadline = fallback
        DispatchQueue.main.asyncAfter(deadline: .now() + 10, execute: fallback)
        webView.evaluateJavaScript(imagesReadyJS, completionHandler: nil)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!,
                 withError error: Error) {
        presentPrintDialog()
    }

    // Called by the injected JS once all images are loaded (or errored).
    func userContentController(_ uc: WKUserContentController,
                                didReceive message: WKScriptMessage) {
        imageDeadline?.cancel()
        imageDeadline = nil
        presentPrintDialog()
    }

    private func presentPrintDialog() {
        guard !presented else { return }
        presented = true
        guard let webView, let window else { cleanup(); return }
        overlay.removeFromSuperview()

        let formatter = webView.viewPrintFormatter()
        let renderer  = AnyDafPrintRenderer(title: rendererTitle)
        renderer.addPrintFormatter(formatter, startingAtPageAt: 0)

        let ctrl        = UIPrintInteractionController.shared
        let info        = UIPrintInfo(dictionary: nil)
        info.jobName    = jobName
        info.outputType = .general
        ctrl.printInfo         = info
        ctrl.printPageRenderer = renderer

        let anchor = CGRect(x: window.bounds.midX, y: window.bounds.midY,
                            width: 1, height: 1)
        ctrl.present(from: anchor, in: window, animated: true) { [weak self] _, _, _ in
            self?.cleanup()
        }
    }

    private func cleanup() {
        imageDeadline?.cancel()
        imageDeadline = nil
        overlay.removeFromSuperview()
        // Remove the script handler to break the retain cycle before releasing the web view.
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "imagesReady")
        webView?.removeFromSuperview()
        webView = nil
        PrintManager.activeCoordinator = nil
    }
}

// MARK: - Print manager

enum PrintManager {

    // Prevents concurrent print operations (and stacked overlays).
    fileprivate static var activeCoordinator: PrintCoordinator?

    // MARK: - Present

    static func present(_ content: PrintableContent) {
        guard activeCoordinator == nil else { return }

        guard let scene  = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first
        else { return }

        let overlay = makeLoadingOverlay(in: window)

        // Build the HTML on a background thread (ShiurParser can be slow for long texts).
        Task.detached(priority: .userInitiated) {
            let html  = buildHTML(for: content)
            let base  = baseURL(for: content)
            let title = runningTitle(for: content)
            let job   = jobTitle(for: content)

            await MainActor.run {
                let coordinator = PrintCoordinator(
                    html: html, baseURL: base, title: title, jobName: job,
                    overlay: overlay, window: window
                )
                activeCoordinator = coordinator
                coordinator.start()
            }
        }
    }

    // MARK: - Loading overlay

    private static func makeLoadingOverlay(in window: UIWindow) -> UIView {
        let overlay = UIView(frame: window.bounds)
        // Semi-transparent so the user sees something is happening and
        // subsequent taps are absorbed by the overlay's background.
        overlay.backgroundColor = UIColor.black.withAlphaComponent(0.18)

        let card = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        card.layer.cornerRadius = 14
        card.clipsToBounds = true
        card.translatesAutoresizingMaskIntoConstraints = false
        overlay.addSubview(card)

        let stack = UIStackView()
        stack.axis      = .horizontal
        stack.alignment = .center
        stack.spacing   = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        card.contentView.addSubview(stack)

        let spinner = UIActivityIndicatorView(style: .medium)
        spinner.startAnimating()
        stack.addArrangedSubview(spinner)

        let label = UILabel()
        label.text      = "Preparing document\u{2026}"
        label.font      = .systemFont(ofSize: 15)
        label.textColor = .label
        stack.addArrangedSubview(label)

        NSLayoutConstraint.activate([
            card.centerXAnchor.constraint(equalTo: overlay.centerXAnchor),
            card.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            stack.topAnchor.constraint(equalTo: card.contentView.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: card.contentView.bottomAnchor, constant: -16),
            stack.leadingAnchor.constraint(equalTo: card.contentView.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(equalTo: card.contentView.trailingAnchor, constant: -20)
        ])

        window.addSubview(overlay)
        return overlay
    }

    // MARK: - Helpers (fileprivate so PrintCoordinator can call them if needed)

    fileprivate static func jobTitle(for content: PrintableContent) -> String {
        switch content {
        case .shiur(let t, let d, _):         return "Shiur — \(t) \(d)"
        case .talmudText(let t, let d, _, _): return "\(t) \(d)"
        case .article(let a, _):              return a.title
        }
    }

    fileprivate static func runningTitle(for content: PrintableContent) -> String {
        switch content {
        case .shiur(let t, let d, _):         return "\(t) \(d) — Shiur"
        case .talmudText(let t, let d, _, _): return "\(t) \(d)"
        case .article(let a, _):
            return a.authorName.isEmpty ? a.title : "\(a.title) — \(a.authorName)"
        }
    }

    // Base URL enables WKWebView to load article images from the article's origin.
    // Shiur and talmud have no remote images so nil is fine.
    fileprivate static func baseURL(for content: PrintableContent) -> URL? {
        guard case .article(let article, _) = content,
              let url  = URL(string: article.link),
              let host = url.host,
              let scheme = url.scheme
        else { return nil }
        return URL(string: "\(scheme)://\(host)")
    }

    // MARK: - Font size + line spacing

    private static func bodyFontSizePt() -> Int {
        switch UserDefaults.standard.string(forKey: "printFontSize") ?? "small" {
        case "xSmall": return 10
        case "small":  return 11
        case "large":  return 14
        case "xLarge": return 16
        default:       return 12
        }
    }

    private static func bodyLineSpacing() -> Double {
        let v = UserDefaults.standard.double(forKey: "printLineSpacing")
        return v > 0 ? v : 1.15
    }

    // MARK: - HTML assembly

    fileprivate static func buildHTML(for content: PrintableContent) -> String {
        let logo = logoTag()
        let fs   = bodyFontSizePt()
        let ls   = bodyLineSpacing()
        let css  = commonCSS(fontSize: fs, lineSpacing: ls)

        let title: String
        let subtitle: String
        let body: String

        switch content {
        case .shiur(let tractate, let daf, let text):
            title    = "\(tractate) \(daf)"
            subtitle = "Shiur"
            body     = shiurBodyHTML(from: text)

        case .talmudText(let tractate, let daf, let sections, let mode):
            title    = "\(tractate) \(daf)"
            subtitle = mode == .stacked ? "Text and Translation" : "Translation"
            body     = talmudBodyHTML(sections: sections, mode: mode)

        case .article(let article, let html):
            title    = article.title
            let parts = [article.authorName, article.date].filter { !$0.isEmpty }
            subtitle = parts.joined(separator: " · ")
            body     = articleBodyHTML(article: article, html: html)
        }

        let subtitleTag = subtitle.isEmpty
            ? ""
            : "<div class=\"daf-subtitle\">\(escapeHTML(subtitle))</div>"

        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <style>\(css)</style>
        </head>
        <body>
        <div class="page-header">
          \(logo)
          <div class="header-right">
            <div class="daf-title">\(escapeHTML(title))</div>
            \(subtitleTag)
          </div>
        </div>
        <div class="content">\(body)</div>
        </body>
        </html>
        """
    }

    // MARK: - Logo

    private static func logoTag() -> String {
        guard let image = UIImage(named: "Image"),
              let data  = image.jpegData(compressionQuality: 0.9)
        else {
            return "<span class=\"logo-text\">YCT</span>"
        }
        return "<img src=\"data:image/jpeg;base64,\(data.base64EncodedString())\" alt=\"YCT\">"
    }

    // MARK: - CSS
    // body { padding: 0 36pt } provides side margins. Top/bottom margins come
    // from AnyDafPrintRenderer's headerHeight / footerHeight (36pt each), which
    // WKWebView's viewPrintFormatter() respects via contentRectForPage.

    private static func commonCSS(fontSize fs: Int, lineSpacing ls: Double) -> String {
        """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          font-family: Georgia, serif;
          font-size: \(fs)pt;
          line-height: \(ls);
          color: #1a1a1a;
          padding: 0 36pt;
        }

        /* ── First-page document header ── */
        .page-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-bottom: 12pt;
          border-bottom: 2pt solid #1B3A8A;
          margin-bottom: 20pt;
        }
        .page-header img { height: 52pt; width: auto; }
        .logo-text { font-size: 22pt; font-weight: bold; color: #1B3A8A; }
        .header-right { text-align: right; }
        .daf-title { font-size: \(fs + 6)pt; font-weight: bold; color: #1B3A8A; }
        .daf-subtitle { font-size: \(max(fs - 2, 8))pt; color: #666; margin-top: 3pt; }

        /* ── Shiur content ── */
        h2 {
          font-size: \(fs + 2)pt; font-weight: bold; color: #1B3A8A;
          margin: 22pt 0 6pt 0;
          page-break-after: avoid; break-after: avoid;
          page-break-inside: avoid; break-inside: avoid;
        }
        h3 {
          font-size: \(fs)pt; font-weight: 600; color: #444;
          margin: 12pt 0 4pt 0;
          page-break-after: avoid; break-after: avoid;
          page-break-inside: avoid; break-inside: avoid;
        }
        p { margin-bottom: 9pt; }

        .blockquote {
          border-left: 3pt solid #1B3A8A;
          background: #f4f6fb;
          padding: 8pt 12pt;
          margin: 0 0 12pt 0;
          border-radius: 3pt;
          /* Allow long blockquotes to split across pages rather than
             creating large blank gaps at the bottom of a page. */
          page-break-inside: auto; break-inside: auto;
        }
        .blockquote-label {
          font-size: \(max(fs - 4, 7))pt; font-weight: bold;
          color: #999; letter-spacing: 0.5pt;
          text-transform: uppercase; margin-bottom: 5pt;
        }
        .hebrew-source {
          direction: rtl; text-align: right;
          font-size: \(fs + 1)pt; line-height: \(ls);
          margin-bottom: 6pt;
        }
        .translation { font-size: \(max(fs - 1, 9))pt; color: #333; line-height: \(ls); }
        .translation strong { color: #1B3A8A; font-weight: normal; }
        em { font-style: italic; }

        /* ── Talmud text ── */
        .section-label {
          font-size: \(max(fs - 2, 8))pt; font-weight: bold; color: #1B3A8A;
          letter-spacing: 1pt; text-transform: uppercase;
          margin: 18pt 0 8pt 0;
        }
        .hebrew-block {
          direction: rtl; text-align: right;
          font-size: \(fs + 1)pt; line-height: \(ls);
          margin-bottom: 8pt;
        }
        .english-block { margin-bottom: 14pt; }
        .english-block b, .english-block strong { color: #1B3A8A; font-weight: normal; }
        .pair-divider {
          border: none; border-top: 1px dashed #ccc;
          margin: 8pt 0 10pt 0;
        }

        /* ── Article ── */
        .article-meta  { font-size: \(max(fs - 2, 8))pt; color: #666; margin-bottom: 14pt; }
        .article-body  { font-size: \(fs)pt; line-height: \(ls); }
        .article-body p { margin-bottom: 9pt; }
        .article-body h1, .article-body h2, .article-body h3 {
          font-size: \(fs + 1)pt; font-weight: bold; margin: 12pt 0 5pt 0; color: #1B3A8A;
        }
        .article-body img { max-width: 100%; height: auto; display: block; margin: 10pt 0; }
        .article-url {
          font-size: \(max(fs - 3, 7))pt; color: #888;
          margin-top: 14pt; word-break: break-all;
        }
        """
    }

    // MARK: - Shiur HTML

    private static func shiurBodyHTML(from text: String) -> String {
        var html = ""
        for block in ShiurParser.parseBlocks(from: text) {
            switch block {
            case .h2(_, _, let t):
                html += "<h2>\(escapeHTML(t))</h2>\n"
            case .h3(_, let t):
                html += "<h3>\(escapeHTML(t))</h3>\n"
            case .body(_, let t):
                html += "<p>\(formatMarkdownInline(t))</p>\n"
            case .blockquote(_, let source, let translation, let showLabel):
                var bq = "<div class=\"blockquote\">"
                if showLabel { bq += "<div class=\"blockquote-label\">Text &amp; Translation</div>" }
                if !source.isEmpty      { bq += "<div class=\"hebrew-source\">\(escapeHTML(source))</div>" }
                if !translation.isEmpty { bq += "<div class=\"translation\">\(formatTranslation(translation))</div>" }
                bq += "</div>"
                html += bq + "\n"
            }
        }
        return html
    }

    // MARK: - Talmud text HTML

    private static func talmudBodyHTML(sections: [StudySection], mode: SourceDisplayMode) -> String {
        var html = ""
        let showHebrew = (mode == .stacked)
        for section in sections {
            if !section.title.isEmpty {
                html += "<div class=\"section-label\">\(escapeHTML(section.title))</div>\n"
            }
            if showHebrew, let hebrewHTML = section.hebrewText, !hebrewHTML.isEmpty {
                let stripped = stripHTMLTags(hebrewHTML)
                if !stripped.isEmpty {
                    html += "<div class=\"hebrew-block\">\(escapeHTML(stripped))</div>\n"
                    html += "<hr class=\"pair-divider\">\n"
                }
            }
            if !section.rawText.isEmpty {
                html += "<div class=\"english-block\">\(section.rawText)</div>\n"
            }
        }
        return html
    }

    // MARK: - Article HTML

    private static func articleBodyHTML(article: YCTArticle, html: String) -> String {
        let safeMeta = escapeHTML(
            [article.authorName, article.date].filter { !$0.isEmpty }.joined(separator: " · ")
        )
        let safeURL     = escapeHTML(article.link)
        // Use the raw HTML body as-is; WKWebView will load images from the article origin.
        let bodyContent = html.isEmpty ? "<p>\(escapeHTML(article.excerpt))</p>" : html
        return """
        \(safeMeta.isEmpty ? "" : "<div class=\"article-meta\">\(safeMeta)</div>")
        <div class="article-body">\(bodyContent)</div>
        <div class="article-url">\(safeURL)</div>
        """
    }

    // MARK: - Markdown inline formatting

    private static func formatMarkdownInline(_ text: String) -> String {
        var result = ""
        let parts = text.components(separatedBy: "*")
        for (i, part) in parts.enumerated() {
            let escaped = escapeHTML(part)
            result += (i % 2 == 1 && !part.isEmpty) ? "<em>\(escaped)</em>" : escaped
        }
        return result
    }

    private static func formatTranslation(_ text: String) -> String {
        var result = ""
        let normalized = text.replacingOccurrences(of: "***", with: "*")
        let boldParts  = normalized.components(separatedBy: "**")
        for (i, part) in boldParts.enumerated() {
            result += i % 2 == 1
                ? "<strong>\(formatMarkdownInline(part))</strong>"
                : formatMarkdownInline(part)
        }
        return result
    }

    // MARK: - Utilities

    private static func escapeHTML(_ text: String) -> String {
        text
            .replacingOccurrences(of: "&",  with: "&amp;")
            .replacingOccurrences(of: "<",  with: "&lt;")
            .replacingOccurrences(of: ">",  with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }

    private static func stripHTMLTags(_ html: String) -> String {
        html
            .replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&nbsp;", with: " ")
            .replacingOccurrences(of: "&amp;",  with: "&")
            .replacingOccurrences(of: "&lt;",   with: "<")
            .replacingOccurrences(of: "&gt;",   with: ">")
            .replacingOccurrences(of: "&#x27;", with: "'")
            .replacingOccurrences(of: "&quot;", with: "\"")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
