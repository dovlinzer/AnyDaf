package com.anydaf.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.anydaf.data.api.ShiurSegment
import com.anydaf.model.TextDisplayMode
import com.anydaf.model.StudySection

// Provides the body font size for study content — set at the screen level, consumed here.
val LocalStudyFontSize = compositionLocalOf { 18.sp }

// True when the blue-background theme is active; used to flip accent colors in study content.
val LocalIsBlueMode = compositionLocalOf { false }

// MARK: - Translation Tab

@Composable
fun TranslationTab(
    section: StudySection?,
    tractate: String,
    textDisplayMode: TextDisplayMode,
    onModeChange: (TextDisplayMode) -> Unit,
    precedingContext: String?,
    followingContext: String?,
    isFirstSection: Boolean,
    isLastSection: Boolean,
    amudBStart: Boolean = false,
    daf: Int = 0,
    // Full shiur segment list (matched + carried-forward) — filtered internally to genuinely
    // matched segments to build the sefariaIndex -> title map for inline headers.
    shiurSegments: List<ShiurSegment> = emptyList(),
    // Set (by StudySessionViewModel.jumpToSection) when the text should scroll to a segment's
    // exact raw position — e.g. a pill tap landing within the section already on screen, or a
    // Shiur<->Text mode-switch sync. Consumed once and cleared via onScrollTargetConsumed.
    pendingScrollSefariaIndex: Int? = null,
    onScrollTargetConsumed: () -> Unit = {},
    // Composable slot rendered at the bottom of the scroll content — used in textOnly mode
    // to place Prev/Next navigation inside the scrollable area rather than below it.
    bottomContent: (@Composable () -> Unit)? = null
) {
    if (section == null) {
        Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        return
    }

    val listState = rememberLazyListState()
    val allDirect = tractate == "Shekalim"
    // Local val (not section.hebrewText directly) so nullability is resolved once, up front —
    // avoids relying on smart-cast of a property through the nested item{} composable lambdas.
    val hebrewText: String? = section.hebrewText

    // sefariaIndex -> title, genuinely-matched segments only (mirrors StudyModeView.swift's
    // matchedSegmentByIndex) — a carried-forward placeholder ("Introduction") only inherits its
    // index, so it must never show as a header at another segment's real position.
    val headerByIndex = remember(shiurSegments) {
        val map = mutableMapOf<Int, String>()
        for (seg in shiurSegments) {
            if (seg.matched == true) {
                val idx = seg.sefariaIndex
                if (idx != null && !map.containsKey(idx)) map[idx] = seg.displayTitle
            }
        }
        map
    }

    // Content items (one per raw segment) always start at LazyColumn index 1 — item 0 is the
    // fixed pill/legend header row below. Keep in sync if items are added/removed above.
    val contentStartOffset = 1

    LazyColumn(
        state = listState,
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        item(key = "header") {
            Column {
                if (hebrewText != null) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        TextDisplayPill(mode = textDisplayMode, onModeChange = onModeChange)
                        Spacer(Modifier.weight(1f))
                        if (textDisplayMode != TextDisplayMode.SOURCE) {
                            TranslationLegend()
                        }
                    }
                } else {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TranslationLegend()
                    }
                }
                androidx.compose.material3.HorizontalDivider(
                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                )
                Spacer(Modifier.height(12.dp))
                if (amudBStart && daf > 0) {
                    val amudHebrewFormat = hebrewText != null && textDisplayMode != TextDisplayMode.TRANSLATION
                    AmudMarker(daf, hebrewFormat = amudHebrewFormat, alignEnd = amudHebrewFormat)
                }
            }
        }

        if (hebrewText != null) {
            when (textDisplayMode) {
                TextDisplayMode.SOURCE -> {
                    if (section.hebrewSegments.isEmpty()) {
                        item(key = "source-blob") {
                            HebrewText(html = hebrewText, modifier = Modifier.fillMaxWidth())
                        }
                    } else {
                        itemsIndexed(
                            section.hebrewSegments,
                            key = { i, _ -> "raw-${section.firstSegmentIndex + i}" }
                        ) { i, hebrewSeg ->
                            val absIdx = section.firstSegmentIndex + i
                            Column {
                                InlineSegmentHeader(headerByIndex[absIdx])
                                HebrewText(html = hebrewSeg, modifier = Modifier.fillMaxWidth())
                                Spacer(Modifier.height(12.dp))
                            }
                        }
                    }
                }
                TextDisplayMode.TRANSLATION -> {
                    translationOnlyItems(
                        section = section, isFirstSection = isFirstSection,
                        precedingContext = precedingContext, allDirect = allDirect,
                        headerByIndex = headerByIndex
                    )
                }
                TextDisplayMode.BOTH -> {
                    itemsIndexed(
                        section.rawSegments,
                        key = { i, _ -> "raw-${section.firstSegmentIndex + i}" }
                    ) { idx, seg ->
                        val absIdx = section.firstSegmentIndex + idx
                        Column {
                            InlineSegmentHeader(headerByIndex[absIdx])
                            if (idx < section.hebrewSegments.size) {
                                HebrewText(html = section.hebrewSegments[idx], modifier = Modifier.fillMaxWidth())
                                Spacer(Modifier.height(8.dp))
                            }
                            val prefix = if (idx == 0 && isFirstSection && precedingContext != null)
                                "[…${SefariaClient.stripHtml(precedingContext)}] " else ""
                            HtmlTextWithItalicPrefix(prefix = prefix, html = seg, modifier = Modifier.fillMaxWidth(), forceDirectColor = allDirect)
                            if (idx < section.rawSegments.size - 1) {
                                Spacer(Modifier.height(12.dp))
                                androidx.compose.material3.HorizontalDivider(
                                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
                                )
                            }
                            Spacer(Modifier.height(12.dp))
                        }
                    }
                }
            }
        } else {
            translationOnlyItems(
                section = section, isFirstSection = isFirstSection,
                precedingContext = precedingContext, allDirect = allDirect,
                headerByIndex = headerByIndex
            )
        }

        // Following context (last section only)
        if (isLastSection && followingContext != null) {
            item(key = "following") {
                Column {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "[$followingContext…]",
                        style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        // Prev/Next navigation rendered inside the scroll content (textOnly mode)
        if (bottomContent != null) {
            item(key = "bottom") {
                Column {
                    Spacer(Modifier.height(16.dp))
                    androidx.compose.material3.HorizontalDivider(
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
                    )
                    bottomContent()
                    Spacer(Modifier.height(16.dp))
                }
            }
        }
    }

    LaunchedEffect(pendingScrollSefariaIndex, section.id) {
        val idx = pendingScrollSefariaIndex ?: return@LaunchedEffect
        val contentPos = idx - section.firstSegmentIndex
        val rawCount = if (hebrewText != null && textDisplayMode == TextDisplayMode.SOURCE)
            section.hebrewSegments.size else section.rawSegments.size
        if (contentPos in 0 until rawCount) {
            listState.animateScrollToItem(contentStartOffset + contentPos)
        }
        onScrollTargetConsumed()
    }
}

/** Inline guidepost header shown immediately before the raw segment where a matched shiur
 *  segment's own anchor begins. No-op when [title] is null. */
@Composable
private fun InlineSegmentHeader(title: String?) {
    if (title != null) {
        val headerFg = if (LocalIsBlueMode.current) Color.White else MaterialTheme.colorScheme.onSurface
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = headerFg.copy(alpha = 0.85f),
            modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
        )
    }
}

/** Translation-only (English) content, one raw segment per item, with inline segment headers.
 *  Used both for TextDisplayMode.TRANSLATION and the no-Hebrew fallback. */
private fun androidx.compose.foundation.lazy.LazyListScope.translationOnlyItems(
    section: StudySection,
    isFirstSection: Boolean,
    precedingContext: String?,
    allDirect: Boolean,
    headerByIndex: Map<Int, String>
) {
    if (section.rawSegments.isEmpty()) {
        item(key = "translation-blob") {
            val prefix = if (isFirstSection && precedingContext != null)
                "[…${SefariaClient.stripHtml(precedingContext)}] " else ""
            HtmlTextWithItalicPrefix(prefix = prefix, html = section.rawText, forceDirectColor = allDirect)
        }
    } else {
        itemsIndexed(
            section.rawSegments,
            key = { i, _ -> "raw-${section.firstSegmentIndex + i}" }
        ) { idx, seg ->
            val absIdx = section.firstSegmentIndex + idx
            Column {
                InlineSegmentHeader(headerByIndex[absIdx])
                val prefix = if (idx == 0 && isFirstSection && precedingContext != null)
                    "[…${SefariaClient.stripHtml(precedingContext)}] " else ""
                HtmlTextWithItalicPrefix(prefix = prefix, html = seg, modifier = Modifier.fillMaxWidth(), forceDirectColor = allDirect)
                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

// MARK: - Text Display Pill

/** א | A | אA three-option pill for choosing source/translation/both display. */
@Composable
fun TextDisplayPill(
    mode: TextDisplayMode,
    onModeChange: (TextDisplayMode) -> Unit
) {
    val fg = if (LocalIsBlueMode.current) Color.White else MaterialTheme.colorScheme.onSurface
    Row(
        modifier = Modifier.border(0.5.dp, fg.copy(alpha = 0.22f), RoundedCornerShape(8.dp))
    ) {
        PillSegment("א", TextDisplayMode.SOURCE, mode, onModeChange, fg)
        PillSegment("A", TextDisplayMode.TRANSLATION, mode, onModeChange, fg)
        // ‭ = LTR override so alef displays left of A
        PillSegment("‭א‎A‬", TextDisplayMode.BOTH, mode, onModeChange, fg)
    }
}

@Composable
private fun PillSegment(
    label: String,
    segMode: TextDisplayMode,
    current: TextDisplayMode,
    onClick: (TextDisplayMode) -> Unit,
    fg: Color
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(if (current == segMode) fg.copy(alpha = 0.28f) else Color.Transparent)
            .clickable { onClick(segMode) }
            .padding(horizontal = 10.dp, vertical = 4.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
            color = fg
        )
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
            val fontSize = LocalStudyFontSize.current
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
                Text(
                    section.summary!!,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        fontSize = fontSize,
                        lineHeight = (fontSize.value * 1.45f).sp
                    )
                )
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
            withStyle(SpanStyle(color = directColor, fontWeight = FontWeight.Normal)) {
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
                // Colour-only — no bold weight. FontWeight.Normal is explicit to prevent
                // any accidental inheritance from the HTML <b> semantic.
                withStyle(SpanStyle(color = directColor, fontWeight = FontWeight.Normal)) {
                    append(bold)
                }
            }
            cursor = match.range.last + 1
        }
        if (cursor < html.length) append(stripHtmlTags(html.substring(cursor)))
    }
}

private val AmberDirect = androidx.compose.ui.graphics.Color(0xFFFFC107)

@Composable
private fun AmudMarker(daf: Int, hebrewFormat: Boolean, alignEnd: Boolean) {
    val label = if (hebrewFormat) "[${toHebrewNumeral(daf)} ע״ב]" else "[${daf}b]"
    Text(
        text = label,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
        textAlign = if (alignEnd) TextAlign.End else TextAlign.Start
    )
}

@Composable
private fun TranslationLegend(modifier: Modifier = Modifier) {
    val blueMode = LocalIsBlueMode.current
    val directColor = if (blueMode) AmberDirect else MaterialTheme.colorScheme.primary
    val addedColor  = if (blueMode) androidx.compose.ui.graphics.Color.White.copy(alpha = 0.7f)
                      else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
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
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyLarge.copy(
        fontSize = LocalStudyFontSize.current,
        lineHeight = (LocalStudyFontSize.current.value * 1.45f).sp,
        fontWeight = FontWeight.Normal
    )
) {
    val directColor = if (LocalIsBlueMode.current) AmberDirect else MaterialTheme.colorScheme.primary
    val annotated: AnnotatedString = parseTranslationHtml(html, directColor)
    Text(text = annotated, style = style, modifier = modifier)
}

@Composable
fun HtmlTextWithItalicPrefix(
    prefix: String,
    html: String,
    modifier: Modifier = Modifier,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyLarge.copy(
        fontSize = LocalStudyFontSize.current,
        lineHeight = (LocalStudyFontSize.current.value * 1.45f).sp,
        fontWeight = FontWeight.Normal
    ),
    forceDirectColor: Boolean = false
) {
    val blueMode = LocalIsBlueMode.current
    val directColor = if (blueMode) AmberDirect else MaterialTheme.colorScheme.primary
    // Preceding-context prefix: italic + subtly shaded so it reads as background context
    val prefixColor = if (blueMode) androidx.compose.ui.graphics.Color.White.copy(alpha = 0.45f)
                      else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
    val parsed = parseTranslationHtml(html, directColor, forceDirectColor)
    val annotated: AnnotatedString = if (prefix.isNotEmpty()) {
        buildAnnotatedString {
            withStyle(SpanStyle(fontStyle = FontStyle.Italic, color = prefixColor)) { append(prefix) }
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
            lineHeight = (fontSize.value * 1.45f).sp,
            fontWeight = FontWeight.Normal,
            textDirection = TextDirection.Rtl,
            textAlign = TextAlign.Right
        ),
        textAlign = TextAlign.Right,
        modifier = modifier
    )
}

// Gematria — converts an integer to Hebrew numeral notation with geresh/gershayim.
// Handles special cases for 15 (ט״ו) and 16 (ט״ז) to avoid spelling divine names.
fun toHebrewNumeral(n: Int): String {
    if (n <= 0) return ""
    var remaining = n
    val sb = StringBuilder()

    for ((v, l) in listOf(400 to "ת", 300 to "ש", 200 to "ר", 100 to "ק")) {
        while (remaining >= v) { sb.append(l); remaining -= v }
    }
    when {
        remaining == 15 -> { sb.append("טו"); remaining = 0 }
        remaining == 16 -> { sb.append("טז"); remaining = 0 }
        else -> {
            for ((v, l) in listOf(90 to "צ", 80 to "פ", 70 to "ע", 60 to "ס", 50 to "נ",
                                  40 to "מ", 30 to "ל", 20 to "כ", 10 to "י")) {
                while (remaining >= v) { sb.append(l); remaining -= v }
            }
            for ((v, l) in listOf(9 to "ט", 8 to "ח", 7 to "ז", 6 to "ו", 5 to "ה",
                                  4 to "ד", 3 to "ג", 2 to "ב", 1 to "א")) {
                while (remaining >= v) { sb.append(l); remaining -= v }
            }
        }
    }

    val s = sb.toString()
    return if (s.length == 1) "$s׳"
    else "${s.dropLast(1)}״${s.last()}"
}
