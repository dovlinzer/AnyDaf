package com.anydaf.ui

import android.content.Intent
import android.net.Uri
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.OpenInBrowser
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.anydaf.model.YCTArticle

private const val FONT_SIZE_MIN = 12
private const val FONT_SIZE_MAX = 28
private const val FONT_SIZE_STEP = 2
private const val FONT_SIZE_DEFAULT = 16

@Composable
fun ArticleReaderScreen(
    article: YCTArticle,
    html: String,
    isLoading: Boolean,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val darkTheme = isSystemInDarkTheme()
    var fontSize by remember { mutableIntStateOf(FONT_SIZE_DEFAULT) }

    // Mutable container so the update lambda can reference the WebView without capture issues
    val webViewHolder = remember { mutableListOf<WebView>() }
    // Track the last HTML actually loaded so we only reload when content changes, not on font changes
    val lastLoadedHtml = remember { mutableListOf<String>() }

    val referencedDaf = article.matchType.referencedDaf

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        // Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 4.dp),
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = article.title,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )
                if (article.authorName.isNotEmpty()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = article.authorName,
                        style = MaterialTheme.typography.bodySmall.copy(fontStyle = FontStyle.Italic),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(Modifier.height(4.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = article.date,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (referencedDaf > 0) {
                        SuggestionChip(
                            onClick = {},
                            label = {
                                Text(
                                    "Daf $referencedDaf",
                                    style = MaterialTheme.typography.labelSmall
                                )
                            }
                        )
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = onDismiss, modifier = Modifier.size(40.dp)) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Close",
                    tint = MaterialTheme.colorScheme.onSurface
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.15f))

        // Content area
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
        ) {
            if (isLoading) {
                Box(Modifier.fillMaxSize(), Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                // Build styled HTML using the current default font size embedded in CSS.
                // Subsequent font-size changes are applied via JS without a page reload.
                val initialHtml = buildStyledHtml(html, fontSize, darkTheme)

                AndroidView(
                    factory = { ctx ->
                        WebView(ctx).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = false
                            setBackgroundColor(android.graphics.Color.TRANSPARENT)
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(
                                    view: WebView,
                                    request: WebResourceRequest
                                ): Boolean {
                                    val intent = Intent(Intent.ACTION_VIEW, request.url)
                                    ctx.startActivity(intent)
                                    return true
                                }
                            }
                            loadDataWithBaseURL(
                                "https://library.yctorah.org",
                                initialHtml,
                                "text/html",
                                "UTF-8",
                                null
                            )
                            webViewHolder.clear()
                            webViewHolder.add(this)
                            lastLoadedHtml.clear()
                            lastLoadedHtml.add(html)
                        }
                    },
                    update = { webView ->
                        // Only reload if the underlying HTML changed (e.g. new article)
                        if (lastLoadedHtml.firstOrNull() != html) {
                            val newHtml = buildStyledHtml(html, fontSize, darkTheme)
                            webView.loadDataWithBaseURL(
                                "https://library.yctorah.org",
                                newHtml,
                                "text/html",
                                "UTF-8",
                                null
                            )
                            lastLoadedHtml.clear()
                            lastLoadedHtml.add(html)
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.15f))

        // Footer: font size controls + open in browser
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            // Font size controls
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(
                    onClick = {
                        if (fontSize > FONT_SIZE_MIN) {
                            fontSize -= FONT_SIZE_STEP
                            webViewHolder.firstOrNull()?.evaluateJavascript(
                                "document.body.style.fontSize='${fontSize}px'", null
                            )
                        }
                    },
                    enabled = fontSize > FONT_SIZE_MIN
                ) {
                    Text("A−", style = MaterialTheme.typography.labelLarge)
                }
                Text(
                    text = "${fontSize}sp",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                TextButton(
                    onClick = {
                        if (fontSize < FONT_SIZE_MAX) {
                            fontSize += FONT_SIZE_STEP
                            webViewHolder.firstOrNull()?.evaluateJavascript(
                                "document.body.style.fontSize='${fontSize}px'", null
                            )
                        }
                    },
                    enabled = fontSize < FONT_SIZE_MAX
                ) {
                    Text("A+", style = MaterialTheme.typography.labelLarge)
                }
            }

            // Open in browser
            TextButton(
                onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(article.link))
                    context.startActivity(intent)
                }
            ) {
                Icon(
                    imageVector = Icons.Default.OpenInBrowser,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(Modifier.width(4.dp))
                Text("Open in Browser", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

private fun buildStyledHtml(bodyHtml: String, fontSize: Int, darkTheme: Boolean): String {
    val bodyColor    = if (darkTheme) "rgba(255,255,255,0.90)" else "rgba(26,26,26,0.87)"
    val headingColor = if (darkTheme) "#ffffff"                else "#111111"
    val linkColor    = if (darkTheme) "#90BAFF"                else "#1B3A8A"
    val bqBorder     = if (darkTheme) "rgba(255,255,255,0.35)" else "rgba(0,0,0,0.25)"
    val bqColor      = if (darkTheme) "rgba(255,255,255,0.65)" else "rgba(0,0,0,0.55)"
    val css = """
        body {
            background: transparent;
            color: $bodyColor;
            font-family: sans-serif;
            font-size: ${fontSize}px;
            line-height: 1.75;
            padding: 16px 20px 60px;
            margin: 0;
        }
        a { color: $linkColor; }
        h1,h2,h3,h4 { color: $headingColor; margin: 20px 0 8px; }
        p { margin: 0 0 14px; }
        blockquote {
            border-left: 3px solid $bqBorder;
            margin: 12px 0; padding-left: 14px;
            color: $bqColor;
        }
        ul,ol { padding-left: 20px; margin-bottom: 14px; }
        li { margin-bottom: 6px; }
        img { max-width: 100%; height: auto; }
    """.trimIndent()

    return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>$css</style>
        </head>
        <body>$bodyHtml</body>
        </html>
    """.trimIndent()
}
