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
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.material3.LocalContentColor
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.anydaf.model.StudyFontSize
import com.anydaf.model.YCTArticle

@Composable
fun ArticleReaderScreen(
    article: YCTArticle,
    html: String,
    isLoading: Boolean,
    studyFontSize: StudyFontSize,
    onSizeChange: (StudyFontSize) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val darkTheme = isSystemInDarkTheme()

    // Track the last HTML/theme/fontPx actually loaded to avoid unnecessary reloads
    val lastLoadedKey = remember { mutableStateOf("") }
    val lastLoadedFontPx = remember { mutableIntStateOf(0) }
    val webViewHolder = remember { mutableListOf<WebView>() }

    val referencedDaf = article.matchType.referencedDaf
    val isTablet = androidx.compose.ui.platform.LocalConfiguration.current.smallestScreenWidthDp >= 600
    val cases = StudyFontSize.displayEntries(isTablet)
    val idx = cases.indexOf(studyFontSize).coerceAtLeast(0)

    // Reset LocalContentColor to dark — the article reader has its own parchment background
    // and must not inherit white from a blue-mode parent Scaffold.
    CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onBackground) {
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
                                Text("Daf $referencedDaf", style = MaterialTheme.typography.labelSmall)
                            }
                        )
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = onDismiss, modifier = Modifier.size(40.dp)) {
                Icon(Icons.Default.Close, "Close", tint = MaterialTheme.colorScheme.onSurface)
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.15f))

        // Content area
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            if (isLoading) {
                Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
            } else {
                val stateKey = "${html.hashCode()}_$darkTheme"
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
                                buildStyledHtml(html, studyFontSize.articleFontPx, darkTheme),
                                "text/html", "UTF-8", null
                            )
                            webViewHolder.clear(); webViewHolder.add(this)
                            lastLoadedKey.value = stateKey
                            lastLoadedFontPx.intValue = studyFontSize.articleFontPx
                        }
                    },
                    update = { webView ->
                        if (lastLoadedKey.value != stateKey) {
                            webView.loadDataWithBaseURL(
                                "https://library.yctorah.org",
                                buildStyledHtml(html, studyFontSize.articleFontPx, darkTheme),
                                "text/html", "UTF-8", null
                            )
                            lastLoadedKey.value = stateKey
                            lastLoadedFontPx.intValue = studyFontSize.articleFontPx
                        } else if (lastLoadedFontPx.intValue != studyFontSize.articleFontPx) {
                            webView.evaluateJavascript(
                                "document.body.style.fontSize='${studyFontSize.articleFontPx}px'", null
                            )
                            lastLoadedFontPx.intValue = studyFontSize.articleFontPx
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.15f))

        // Footer: A•dots•A font controls + open in browser
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 4.dp, end = 12.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Small A — decrease
            TextButton(
                onClick = { if (idx > 0) onSizeChange(cases[idx - 1]) },
                enabled = idx > 0,
                modifier = Modifier.size(44.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
            ) {
                Text(
                    "A",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (idx > 0) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
                )
            }

            // Growing step dots
            Row(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                cases.forEachIndexed { i, _ ->
                    val dotSize = (5 + i * 2).dp
                    Box(
                        modifier = Modifier
                            .size(dotSize)
                            .background(
                                color = if (i == idx) MaterialTheme.colorScheme.primary
                                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.2f),
                                shape = CircleShape
                            )
                    )
                }
            }

            // Large A — increase
            TextButton(
                onClick = { if (idx < cases.size - 1) onSizeChange(cases[idx + 1]) },
                enabled = idx < cases.size - 1,
                modifier = Modifier.size(44.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
            ) {
                Text(
                    "A",
                    style = MaterialTheme.typography.titleMedium,
                    color = if (idx < cases.size - 1) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
                )
            }

            Spacer(Modifier.width(8.dp))

            // Open in browser
            TextButton(
                onClick = {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(article.link))
                    context.startActivity(intent)
                }
            ) {
                Icon(Icons.Default.OpenInBrowser, null, Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
                Text("Open in Browser", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
    } // CompositionLocalProvider(LocalContentColor)
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
