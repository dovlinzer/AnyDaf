package com.anydaf.ui

import android.app.AlertDialog
import android.content.Context
import android.graphics.BitmapFactory
import android.print.PrintAttributes
import android.print.PrintJob
import android.print.PrintManager
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import com.anydaf.R
import com.anydaf.model.TextDisplayMode
import com.anydaf.model.StudyFontSize
import com.anydaf.model.StudySection
import com.anydaf.model.YCTArticle
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

sealed class PrintableContent {
    data class Shiur(val tractate: String, val daf: String, val text: String) : PrintableContent()
    data class TalmudText(
        val tractate: String,
        val daf: String,
        val sections: List<StudySection>,
        val mode: TextDisplayMode,
        val precedingContext: String? = null,
        val followingContext: String? = null
    ) : PrintableContent()
    data class Article(val article: YCTArticle, val html: String) : PrintableContent()
}

// JavaScript injected after DOM load to wait for all <img> elements.
private val imagesReadyJs = """
(function(){
  var imgs = Array.from(document.images).filter(function(i){ return !i.complete; });
  if (!imgs.length) { Android.onImagesReady(); return; }
  var n = imgs.length;
  function done(){ if (--n === 0) Android.onImagesReady(); }
  imgs.forEach(function(i){ i.onload = done; i.onerror = done; });
})();
""".trimIndent()

object PrintHelper {
    private var active = false

    private val StudyFontSize.printPt: Int get() = when (this) {
        StudyFontSize.X_SMALL -> 10
        StudyFontSize.SMALL   -> 11
        StudyFontSize.MEDIUM  -> 12
        StudyFontSize.LARGE   -> 14
        StudyFontSize.X_LARGE -> 16
    }

    fun print(
        context: Context,
        content: PrintableContent,
        printFontSize: StudyFontSize,
        printLineSpacing: Double
    ) {
        if (active) return
        active = true

        Toast.makeText(context, "Preparing document…", Toast.LENGTH_SHORT).show()

        CoroutineScope(Dispatchers.Main).launch {
            try {
                val logoBase64 = withContext(Dispatchers.IO) { loadLogoBase64(context) }
                val html = withContext(Dispatchers.Default) {
                    buildHtml(content, printFontSize.printPt, printLineSpacing, logoBase64)
                }

                val webView = WebView(context)
                webView.settings.javaScriptEnabled = true
                webView.settings.domStorageEnabled = false

                var presented = false

                fun presentPrint() {
                    if (presented) return
                    presented = true
                    try {
                        val printManager = context.getSystemService(Context.PRINT_SERVICE) as PrintManager
                        val jobName = jobName(content)
                        val adapter = webView.createPrintDocumentAdapter(jobName)
                        val job: PrintJob = printManager.print(jobName, adapter, PrintAttributes.Builder().build())
                        // Monitor job state — release resources once it's no longer active
                        CoroutineScope(Dispatchers.Main).launch {
                            var waited = 0
                            while (waited < 120_000) {
                                delay(2_000)
                                waited += 2_000
                                if (job.isCancelled || job.isCompleted || job.isFailed) break
                            }
                            webView.destroy()
                            active = false
                        }
                    } catch (e: Exception) {
                        webView.destroy()
                        active = false
                        showPrintError(context)
                    }
                }

                webView.addJavascriptInterface(object : Any() {
                    @JavascriptInterface
                    fun onImagesReady() {
                        CoroutineScope(Dispatchers.Main).launch { presentPrint() }
                    }
                }, "Android")

                webView.webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView, url: String) {
                        if (content is PrintableContent.Article) {
                            view.evaluateJavascript(imagesReadyJs, null)
                            // 10-second fallback in case some images never fire onload/onerror
                            CoroutineScope(Dispatchers.Main).launch {
                                delay(10_000)
                                presentPrint()
                            }
                        } else {
                            presentPrint()
                        }
                    }
                }

                val baseUrl = if (content is PrintableContent.Article) "https://library.yctorah.org" else null
                webView.loadDataWithBaseURL(baseUrl, html, "text/html", "UTF-8", null)

            } catch (e: Exception) {
                active = false
                showPrintError(context)
            }
        }
    }

    private fun showPrintError(context: Context) {
        try {
            AlertDialog.Builder(context)
                .setTitle("Print Unavailable")
                .setMessage("Printing could not be started. Make sure a printer or PDF service is available, or try again. Note: printing may not work on all emulators.")
                .setPositiveButton("OK", null)
                .show()
        } catch (_: Exception) {
            Toast.makeText(context, "Print failed. Try on a physical device.", Toast.LENGTH_LONG).show()
        }
    }

    private fun jobName(content: PrintableContent): String = when (content) {
        is PrintableContent.Shiur      -> "AnyDaf Shiur — ${content.tractate} ${content.daf}"
        is PrintableContent.TalmudText -> "AnyDaf — ${content.tractate} ${content.daf}"
        is PrintableContent.Article    -> "AnyDaf — ${content.article.title}"
    }

    private fun loadLogoBase64(context: Context): String? = try {
        val bmp = BitmapFactory.decodeResource(context.resources, R.drawable.yct_logo_wide)
            ?: return null
        val baos = ByteArrayOutputStream()
        bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG, 90, baos)
        Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
    } catch (_: Exception) { null }

    // ── HTML generation ────────────────────────────────────────────────────────

    private fun buildHtml(
        content: PrintableContent,
        fontPt: Int,
        lineSpacing: Double,
        logoBase64: String?
    ): String {
        val body = when (content) {
            is PrintableContent.Shiur      -> buildShiurBody(content.text)
            is PrintableContent.TalmudText -> buildTalmudBody(
                content.sections, content.mode,
                content.precedingContext, content.followingContext
            )
            is PrintableContent.Article    -> content.html
        }

        val (title, subtitle) = when (content) {
            is PrintableContent.Shiur      -> "${content.tractate} ${content.daf}" to "Shiur"
            is PrintableContent.TalmudText -> "${content.tractate} ${content.daf}" to "Talmud Text"
            is PrintableContent.Article    -> content.article.title to
                content.article.authorName.ifEmpty { "YCT Torah Library" }
        }

        // Compact logo for the running header (smaller than the cover block)
        val logoHeaderHtml = if (logoBase64 != null) {
            """<img src="data:image/jpeg;base64,$logoBase64" style="height:22pt;max-width:100pt;object-fit:contain;vertical-align:middle;" alt="YCT">"""
        } else {
            """<span style="font-size:8pt;font-weight:bold;color:#1B3A8A;">Yeshivat Chovevei Torah</span>"""
        }

        // ── CSS ────────────────────────────────────────────────────────────────
        // Running header/footer via HTML <thead>/<tfoot> on a full-page wrapper
        // table. WebView (Chromium) natively repeats table-header-group and
        // table-footer-group on every printed page, ensuring the header and footer
        // never overlap body text — more reliable than position:fixed approaches.
        val css = """
            @page {
                margin: 36pt;
                @bottom-right {
                    content: counter(page);
                    font-family: Georgia, serif;
                    font-size: ${maxOf(fontPt - 3, 7)}pt;
                    color: #999;
                }
            }
            * { box-sizing: border-box; }
            body {
                font-family: Georgia, serif;
                font-size: ${fontPt}pt;
                line-height: $lineSpacing;
                color: #1a1a1a;
                margin: 0; padding: 0;
            }
            /* Full-page layout table — thead/tfoot repeat on every page */
            .print-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
            thead { display: table-header-group; }
            tfoot { display: table-footer-group; }
            /* Header cell */
            .header-cell {
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 0.5pt solid #ccc;
                padding: 4pt 0 6pt;
            }
            .page-header-title {
                font-size: ${maxOf(fontPt - 1, 8)}pt;
                font-weight: bold;
                color: #1B3A8A;
            }
            .page-header-sub {
                font-size: ${maxOf(fontPt - 2, 7)}pt;
                color: #777;
                text-align: right;
            }
            /* Footer cell */
            .footer-cell {
                border-top: 0.5pt solid #ccc;
                padding-top: 4pt;
                text-align: center;
                font-size: ${maxOf(fontPt - 3, 7)}pt;
                color: #999;
            }
            /* Body cell — top padding keeps content clear of the header rule */
            .body-cell { vertical-align: top; padding-top: 10pt; }
            h2 {
                font-size: ${fontPt + 2}pt;
                margin: 20pt 0 4pt;
                page-break-after: avoid; break-after: avoid;
            }
            h3 {
                font-size: ${fontPt + 1}pt;
                margin: 12pt 0 2pt;
                page-break-after: avoid; break-after: avoid;
            }
            p { margin: 0 0 10pt; }
            .blockquote {
                border-left: 2pt solid #ccc;
                margin: 6pt 0 12pt;
                padding: 6pt 8pt 6pt 10pt;
                background: #f7f7f7;
                border-radius: 3pt;
                page-break-inside: auto; break-inside: auto;
            }
            .bq-label {
                font-size: ${maxOf(fontPt - 2, 7)}pt;
                font-weight: bold;
                color: #888;
                margin-bottom: 4pt;
            }
            .bq-source { color: #1B3A8A; margin-bottom: 4pt; }
            .bq-source.rtl { direction: rtl; text-align: right; }
            .bq-translation { color: #444; }
            .bq-translation b, .bq-translation strong,
            p b, p strong { color: #1B3A8A; font-weight: normal; }
            .source-word { color: #1B3A8A; }
            .section-title {
                font-size: ${fontPt + 2}pt;
                font-weight: bold;
                margin: 16pt 0 6pt;
                page-break-after: avoid; break-after: avoid;
            }
            .adj-context {
                font-style: italic;
                color: #666;
                background: #f2f2f2;
                padding: 5pt 10pt;
                border-radius: 3pt;
                margin-bottom: 12pt;
            }
            .hebrew { direction: rtl; text-align: right; margin-bottom: 4pt; }
            /* Article styles */
            img { max-width: 100%; height: auto; }
            a { color: #1B3A8A; }
            h1, h4 { color: #111; }
            blockquote {
                border-left: 2pt solid #ccc;
                margin: 10pt 0; padding-left: 12pt;
                color: #555;
            }
            ul, ol { padding-left: 20pt; margin-bottom: 12pt; }
            li { margin-bottom: 4pt; }
            hr { border: none; border-top: 0.5pt solid #ccc; margin: 16pt 0; }
        """.trimIndent()

        val escapedTitle   = escHtml(title)
        val escapedSubtitle = escHtml(subtitle)

        return """
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>$css</style>
            </head>
            <body>
            <table class="print-table">
              <thead>
                <tr>
                  <td>
                    <div class="header-cell">
                      <div>$logoHeaderHtml</div>
                      <div style="text-align:right;">
                        <div class="page-header-title">$escapedTitle</div>
                        <div class="page-header-sub">$escapedSubtitle</div>
                      </div>
                    </div>
                  </td>
                </tr>
              </thead>
              <tfoot>
                <tr>
                  <td>
                    <div class="footer-cell">
                      Printed from AnyDaf &bull; Yeshivat Chovevei Torah &bull; yctorah.org
                    </div>
                  </td>
                </tr>
              </tfoot>
              <tbody>
                <tr>
                  <td class="body-cell">
                    $body
                  </td>
                </tr>
              </tbody>
            </table>
            </body>
            </html>
        """.trimIndent()
    }

    // ── Shiur HTML builder ─────────────────────────────────────────────────────

    private fun buildShiurBody(text: String): String {
        val sb = StringBuilder()
        val bodyLines = mutableListOf<String>()
        val bqSourceLines = mutableListOf<String>()
        val bqTranslationLines = mutableListOf<String>()
        var inTranslation = false
        var showLabel = true

        fun flushBody() {
            val joined = bodyLines.joinToString(" ").trim()
            if (joined.isNotEmpty()) sb.append("<p>${inlineMarkdown(escHtml(joined))}</p>\n")
            bodyLines.clear()
        }

        fun flushBlockquote() {
            val src = bqSourceLines.joinToString(" ").trim()
            val trans = bqTranslationLines.joinToString(" ").trim()
            if (src.isNotEmpty() || trans.isNotEmpty()) {
                sb.append("<div class=\"blockquote\">")
                if (showLabel) sb.append("<div class=\"bq-label\">Text and Translation</div>")
                if (src.isNotEmpty()) {
                    val rtl = containsHebrew(src)
                    val cls = if (rtl) "bq-source rtl" else "bq-source"
                    sb.append("<div class=\"$cls\">${escHtml(src)}</div>")
                }
                if (trans.isNotEmpty()) {
                    sb.append("<div class=\"bq-translation\">${translationHtml(trans)}</div>")
                }
                sb.append("</div>\n")
                showLabel = false
            }
            bqSourceLines.clear()
            bqTranslationLines.clear()
            inTranslation = false
        }

        for (raw in text.lines()) {
            val line = raw.trim()
            when {
                line.startsWith("## ") -> {
                    flushBody(); flushBlockquote(); showLabel = true
                    sb.append("<h2>${escHtml(line.removePrefix("## "))}</h2>\n")
                }
                line.startsWith("### ") -> {
                    flushBody(); flushBlockquote()
                    sb.append("<h3>${escHtml(line.removePrefix("### "))}</h3>\n")
                }
                line.startsWith("# ")  -> { /* skip top-level daf title */ }
                line.startsWith("> ") || line == ">" -> {
                    flushBody()
                    val content = if (line.startsWith("> ")) line.removePrefix("> ") else ""
                    val lower = content.lowercase()
                    when {
                        lower.startsWith("**hebrew") || lower.startsWith("**aramaic") -> {
                            inTranslation = false
                            val colon = content.indexOf(":** ")
                            if (colon >= 0) {
                                val rest = content.substring(colon + 4).trim()
                                if (rest.isNotEmpty()) bqSourceLines.add(rest)
                            }
                        }
                        lower.startsWith("**translation") || lower.startsWith("**english") -> {
                            inTranslation = true
                            val colon = content.indexOf(":** ")
                            if (colon >= 0) {
                                val rest = content.substring(colon + 4).trim()
                                if (rest.isNotEmpty()) bqTranslationLines.add(rest)
                            }
                        }
                        content.isNotEmpty() -> {
                            if (inTranslation) bqTranslationLines.add(content)
                            else              bqSourceLines.add(content)
                        }
                    }
                }
                line.isEmpty() -> { flushBody(); flushBlockquote() }
                else -> { flushBlockquote(); bodyLines.add(line) }
            }
        }
        flushBody(); flushBlockquote()
        return sb.toString()
    }

    // ── Talmud text HTML builder ───────────────────────────────────────────────

    private fun buildTalmudBody(
        sections: List<StudySection>,
        mode: TextDisplayMode,
        precedingContext: String? = null,
        followingContext: String? = null
    ): String {
        val sb = StringBuilder()

        // Preceding-daf context: shown when this daf opens mid-sentence.
        if (!precedingContext.isNullOrBlank()) {
            sb.append("<p class=\"adj-context\">[…${escHtml(precedingContext)}]</p>\n")
        }

        val total = sections.size
        for ((i, section) in sections.withIndex()) {
            sb.append("<h2>Section ${i + 1}/$total</h2>\n")
            when (mode) {
                TextDisplayMode.SOURCE -> {
                    for (heb in section.hebrewSegments) {
                        if (heb.isNotBlank()) sb.append("<div class=\"bq-source rtl hebrew\">${escHtml(heb)}</div>\n")
                    }
                }
                TextDisplayMode.TRANSLATION -> {
                    for (seg in section.rawSegments) {
                        if (seg.isNotBlank()) sb.append("<p>$seg</p>\n")
                    }
                }
                TextDisplayMode.BOTH -> {
                    val hebrewSegs = section.hebrewSegments
                    val englishSegs = section.rawSegments
                    for (j in 0 until maxOf(hebrewSegs.size, englishSegs.size)) {
                        val heb = hebrewSegs.getOrNull(j)
                        val eng = englishSegs.getOrNull(j)
                        if (!heb.isNullOrBlank() || !eng.isNullOrBlank()) {
                            sb.append("<div class=\"blockquote\">")
                            if (!heb.isNullOrBlank()) {
                                sb.append("<div class=\"bq-source rtl hebrew\">${escHtml(heb)}</div>")
                            }
                            if (!eng.isNullOrBlank()) {
                                sb.append("<div class=\"bq-translation\">$eng</div>")
                            }
                            sb.append("</div>\n")
                        }
                    }
                }
            }
        }

        // Following-daf context: shown when this daf ends mid-sentence.
        if (!followingContext.isNullOrBlank()) {
            sb.append("<p class=\"adj-context\">[${escHtml(followingContext)}…]</p>\n")
        }

        return sb.toString()
    }

    // ── Markdown inline helpers ────────────────────────────────────────────────

    /** `**word**` → blue source-word span; `*word*` → italic for Latin text. */
    private fun translationHtml(text: String): String {
        val normalized = text.replace("***", "*")
        return buildString {
            normalized.split("**").forEachIndexed { i, part ->
                if (i % 2 == 1) {
                    append("<span class=\"source-word\">")
                    append(inlineMarkdown(escHtml(part)))
                    append("</span>")
                } else {
                    append(inlineMarkdown(escHtml(part)))
                }
            }
        }
    }

    /** `*word*` → `<em>word</em>` (Latin only; Hebrew text left plain). */
    private fun inlineMarkdown(escaped: String): String = buildString {
        escaped.split("*").forEachIndexed { i, part ->
            if (i % 2 == 1 && !containsHebrew(part)) {
                append("<em>$part</em>")
            } else {
                append(part)
            }
        }
    }

    private fun escHtml(text: String): String = text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")

    private fun containsHebrew(text: String): Boolean =
        text.any { it.code in 0x0590..0x05FF }
}
