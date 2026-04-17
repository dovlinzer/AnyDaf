package com.anydaf.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.anydaf.data.api.SefariaClient
import com.anydaf.model.SourceDisplayMode
import com.anydaf.model.StudySection

// Provides the body font size for study content — set at the screen level, consumed here.
val LocalStudyFontSize = compositionLocalOf { 18.sp }

// MARK: - Translation Tab

@Composable
fun TranslationTab(
    section: StudySection?,
    tractate: String,
    sourceDisplayMode: SourceDisplayMode,
    precedingContext: String?,
    followingContext: String?,
    isFirstSection: Boolean,
    isLastSection: Boolean
) {
    if (section == null) {
        Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        return
    }

    val scrollState = rememberScrollState()
    var showHebrew by remember { mutableStateOf(true) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(16.dp)
    ) {
        // Colour key — always visible at the top of the translation tab
        TranslationLegend(modifier = Modifier.padding(bottom = 10.dp))
        androidx.compose.material3.HorizontalDivider(
            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
        )
        Spacer(Modifier.height(12.dp))

        when (sourceDisplayMode) {
            SourceDisplayMode.TOGGLE -> {
                // Toggle button always at the very top
                if (section.hebrewText != null) {
                    FilledTonalButton(
                        onClick = { showHebrew = !showHebrew },
                        modifier = Modifier.padding(bottom = 12.dp)
                    ) {
                        Text(if (showHebrew) "Show English" else "Show Hebrew")
                    }
                }
                if (showHebrew) {
                    // Hebrew: RTL, right-aligned, no preceding context
                    HebrewText(html = section.hebrewText ?: section.rawText, modifier = Modifier.fillMaxWidth())
                } else {
                    // English: preceding context (italic) flows inline into the daf text
                    val prefix = if (isFirstSection && precedingContext != null)
                        "[…${SefariaClient.stripHtml(precedingContext)}] " else ""
                    val allDirect = tractate == "Shekalim"
                    HtmlTextWithItalicPrefix(prefix = prefix, html = section.rawText, forceDirectColor = allDirect)
                }
            }
            SourceDisplayMode.STACKED -> {
                // Interleaved: Hebrew para then English para, with a line between pairs
                val allDirect = tractate == "Shekalim"
                section.rawSegments.forEachIndexed { idx, seg ->
                    // Hebrew for this paragraph
                    if (idx < section.hebrewSegments.size) {
                        HebrewText(html = section.hebrewSegments[idx], modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                    }
                    // English for this paragraph, with preceding context (italic) on first
                    val prefix = if (idx == 0 && isFirstSection && precedingContext != null)
                        "[…${SefariaClient.stripHtml(precedingContext)}] " else ""
                    HtmlTextWithItalicPrefix(prefix = prefix, html = seg, modifier = Modifier.fillMaxWidth(), forceDirectColor = allDirect)
                    // Subtle divider between pairs (not after the last one)
                    if (idx < section.rawSegments.size - 1) {
                        Spacer(Modifier.height(12.dp))
                        androidx.compose.material3.HorizontalDivider(
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
                        )
                        Spacer(Modifier.height(12.dp))
                    }
                }
            }
        }

        // Following context (last section only)
        if (isLastSection && followingContext != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                "[$followingContext…]",
                style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

// MARK: - Skeleton

/** Single animated placeholder bar. [widthFraction] is 0–1 relative to the parent width. */
@Composable
internal fun SkeletonBlock(
    modifier: Modifier = Modifier,
    height: Dp = 14.dp,
    widthFraction: Float = 1f
) {
    val infiniteTransition = rememberInfiniteTransition(label = "skeleton")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.25f,
        targetValue = 0.55f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "skeleton_alpha"
    )
    Box(
        modifier
            .fillMaxWidth(widthFraction)
            .height(height)
            .clip(RoundedCornerShape(height / 2))
            .background(MaterialTheme.colorScheme.onSurface.copy(alpha = alpha))
    )
}

@Composable
fun StudySkeleton() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        SkeletonBlock(height = 18.dp, widthFraction = 0.32f)
        Spacer(Modifier.height(4.dp))
        SkeletonBlock(widthFraction = 1.00f)
        SkeletonBlock(widthFraction = 0.92f)
        SkeletonBlock(widthFraction = 1.00f)
        SkeletonBlock(widthFraction = 0.75f)
        SkeletonBlock(widthFraction = 0.85f)
        SkeletonBlock(widthFraction = 0.60f)
    }
}

// MARK: - Study Tab

@Composable
fun StudyTab(
    section: StudySection?,
    isLoading: Boolean,
    onLoad: () -> Unit
) {
    when {
        section == null -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        isLoading -> StudySkeleton()
        section.summary == null -> Box(Modifier.fillMaxSize(), Alignment.Center) {
            Button(onClick = onLoad) { Text("Load Summary") }
        }
        else -> {
            val scrollState = rememberScrollState()
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(16.dp)
            ) {
                Text(
                    "Summary",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.primary
                )
                Spacer(Modifier.height(8.dp))
                Text(section.summary!!, style = MaterialTheme.typography.bodyLarge.copy(fontSize = LocalStudyFontSize.current))
            }
        }
    }
}

// MARK: - HTML rendering helpers

/**
 * Strip HTML tags and decode &amp;nbsp; without trimming surrounding whitespace.
 * Used inside [parseTranslationHtml] so that the space between a normal word and
 * a `<b>` word is preserved — e.g. "He <b>issues</b>" must not become "Heissues".
 */
private fun stripHtmlTags(html: String): String =
    html.replace(Regex("<[^>]*>"), "").replace("&nbsp;", " ")

/**
 * Parse Sefaria translation HTML into an AnnotatedString, colouring `<b>` spans
 * (direct Aramaic/Hebrew translation words) with [directColor] and leaving the
 * rest at the default colour.  Any other HTML tags are stripped.
 *
 * When [forceDirectColor] is true (e.g. Shekalim / Jerusalem Talmud, which uses no
 * bold markers), all text is rendered in [directColor].
 */
private fun parseTranslationHtml(
    html: String,
    directColor: Color,
    forceDirectColor: Boolean = false
): AnnotatedString {
    if (forceDirectColor) {
        return buildAnnotatedString {
            withStyle(SpanStyle(color = directColor)) {
                append(stripHtmlTags(html))
            }
        }
    }
    val bPattern = Regex("""<(?:b|strong)>(.*?)</(?:b|strong)>""", RegexOption.DOT_MATCHES_ALL)
    return buildAnnotatedString {
        var cursor = 0
        for (match in bPattern.findAll(html)) {
            // Use no-trim stripping so spaces adjacent to <b> tags are preserved.
            val before = stripHtmlTags(html.substring(cursor, match.range.first))
            if (before.isNotEmpty()) append(before)
            val bold = stripHtmlTags(match.groupValues[1])
            if (bold.isNotEmpty()) {
                withStyle(SpanStyle(color = directColor, fontWeight = FontWeight.Medium)) {
                    append(bold)
                }
            }
            cursor = match.range.last + 1
        }
        if (cursor < html.length) append(stripHtmlTags(html.substring(cursor)))
    }
}

/** Colour key shown at the top of the translation pane. */
@Composable
private fun TranslationLegend(modifier: Modifier = Modifier) {
    val directColor = MaterialTheme.colorScheme.primary
    val addedColor  = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
    Text(
        text = buildAnnotatedString {
            withStyle(SpanStyle(color = directColor)) { append("● Direct   ") }
            withStyle(SpanStyle(color = addedColor))  { append("● Added") }
        },
        style = MaterialTheme.typography.labelSmall,
        modifier = modifier
    )
}

@Composable
fun HtmlText(
    html: String,
    modifier: Modifier = Modifier,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyLarge.copy(fontSize = LocalStudyFontSize.current)
) {
    val directColor = MaterialTheme.colorScheme.primary
    val annotated: AnnotatedString = parseTranslationHtml(html, directColor)
    Text(text = annotated, style = style, modifier = modifier)
}

@Composable
fun HtmlTextWithItalicPrefix(
    prefix: String,
    html: String,
    modifier: Modifier = Modifier,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyLarge.copy(fontSize = LocalStudyFontSize.current),
    forceDirectColor: Boolean = false
) {
    val directColor = MaterialTheme.colorScheme.primary
    val parsed = parseTranslationHtml(html, directColor, forceDirectColor)
    val annotated: AnnotatedString = if (prefix.isNotEmpty()) {
        buildAnnotatedString {
            withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(prefix) }
        } + parsed
    } else {
        parsed
    }
    Text(text = annotated, style = style, modifier = modifier)
}

@Composable
fun HebrewText(
    html: String,
    modifier: Modifier = Modifier
) {
    val plain = SefariaClient.stripHtml(html)
    val fontSize = LocalStudyFontSize.current
    Text(
        plain,
        style = MaterialTheme.typography.bodyLarge.copy(
            fontSize = fontSize,
            textDirection = TextDirection.Rtl,
            textAlign = TextAlign.Right
        ),
        textAlign = TextAlign.Right,
        modifier = modifier
    )
}
