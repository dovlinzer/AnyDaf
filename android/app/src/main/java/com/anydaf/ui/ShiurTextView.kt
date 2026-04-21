package com.anydaf.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp

// Source-word accent colors: amber on blue background, app blue on white background
private val Amber   = Color(0xFFFFB700)
private val AppBlue = Color(0xFF1B3A8A)

// MARK: - Block model

private sealed class ShiurBlock {
    data class Header2(val segIdx: Int, val text: String) : ShiurBlock()
    data class Header3(val text: String) : ShiurBlock()
    data class Body(val text: String) : ShiurBlock()
    data class Blockquote(val source: String, val translation: String, val showLabel: Boolean = true) : ShiurBlock()
}

private fun parseShiurBlocks(rewriteText: String): List<ShiurBlock> {
    val result = mutableListOf<ShiurBlock>()
    var segIdx = -1
    val bodyLines = mutableListOf<String>()
    val bqSourceLines = mutableListOf<String>()
    val bqTranslationLines = mutableListOf<String>()
    var inTranslation = false

    fun flushBody() {
        val joined = bodyLines.joinToString(" ").trim()
        if (joined.isNotEmpty()) result.add(ShiurBlock.Body(joined))
        bodyLines.clear()
    }

    fun flushBlockquote() {
        val src = bqSourceLines.joinToString(" ").trim()
        val trans = bqTranslationLines.joinToString(" ").trim()
        if (src.isNotEmpty() || trans.isNotEmpty()) {
            val showLabel = result.lastOrNull() !is ShiurBlock.Blockquote
            result.add(ShiurBlock.Blockquote(source = src, translation = trans, showLabel = showLabel))
        }
        bqSourceLines.clear()
        bqTranslationLines.clear()
        inTranslation = false
    }

    for (raw in rewriteText.lines()) {
        val line = raw.trim()
        when {
            line.startsWith("## ") -> {
                flushBody(); flushBlockquote()
                segIdx++
                result.add(ShiurBlock.Header2(segIdx, line.removePrefix("## ")))
            }
            line.startsWith("### ") -> {
                flushBody(); flushBlockquote()
                result.add(ShiurBlock.Header3(line.removePrefix("### ")))
            }
            line.startsWith("# ")  -> { /* skip top-level daf title */ }
            line.startsWith("> ") || line == ">" -> {
                flushBody()
                val content = if (line.startsWith("> ")) line.removePrefix("> ") else ""
                val lower = content.lowercase()
                when {
                    lower.startsWith("**hebrew") || lower.startsWith("**aramaic") -> {
                        inTranslation = false
                        // Grab inline text after the label (e.g. "**Hebrew/Aramaic:** text")
                        val colonIdx = content.indexOf(":** ")
                        if (colonIdx >= 0) {
                            val rest = content.substring(colonIdx + 4).trim()
                            if (rest.isNotEmpty()) bqSourceLines.add(rest)
                        }
                    }
                    lower.startsWith("**translation") || lower.startsWith("**english") -> {
                        inTranslation = true
                        val colonIdx = content.indexOf(":** ")
                        if (colonIdx >= 0) {
                            val rest = content.substring(colonIdx + 4).trim()
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
    flushBody()
    flushBlockquote()
    return result
}

/** `*word*` → italic if Latin. Optional `baseColor` applies to all spans (used for source-word coloring). */
private fun italicLatinAnnotatedString(text: String, baseColor: Color? = null): AnnotatedString = buildAnnotatedString {
    text.split("*").forEachIndexed { i, part ->
        val isItalic = i % 2 == 1 && !containsHebrew(part)
        val style = when {
            isItalic && baseColor != null -> SpanStyle(fontStyle = FontStyle.Italic, color = baseColor)
            isItalic                      -> SpanStyle(fontStyle = FontStyle.Italic)
            baseColor != null             -> SpanStyle(color = baseColor)
            else                          -> null
        }
        if (style != null) { pushStyle(style); append(part); pop() } else append(part)
    }
}

/** Translation text: `**word**` → source-word accent color (italic still applied within),
 *  `*word*` → italic. Normalises `***` → `*` to avoid split confusion. */
private fun translationAnnotatedString(text: String, sourceWordColor: Color): AnnotatedString = buildAnnotatedString {
    val normalized = text.replace("***", "*")
    normalized.split("**").forEachIndexed { i, part ->
        if (i % 2 == 1) {
            // Source word: accent color + italic for any *...* within the span
            append(italicLatinAnnotatedString(part, baseColor = sourceWordColor))
        } else {
            append(italicLatinAnnotatedString(part))
        }
    }
}

/** Returns true if the string contains Hebrew/Aramaic Unicode characters. */
private fun containsHebrew(text: String): Boolean =
    text.any { it.code in 0x0590..0x05FF }

// MARK: - Composable

@Composable
fun ShiurTextView(
    rewriteText: String,
    currentSegmentIndex: Int,
    modifier: Modifier = Modifier
) {
    val blueMode = LocalIsBlueMode.current
    // Amber on blue background or dark theme; brand blue on white/parchment light theme
    val sourceWordColor = if (blueMode || isSystemInDarkTheme()) Amber else AppBlue
    val blocks = remember(rewriteText) { parseShiurBlocks(rewriteText) }
    val listState = rememberLazyListState()

    // Scroll to the current segment's header block whenever the index changes.
    LaunchedEffect(currentSegmentIndex) {
        val idx = blocks.indexOfFirst { it is ShiurBlock.Header2 && it.segIdx == currentSegmentIndex }
        if (idx >= 0) listState.animateScrollToItem(idx)
    }

    LazyColumn(
        state = listState,
        modifier = modifier.padding(horizontal = 18.dp)
    ) {
        itemsIndexed(blocks) { _, block ->
            when (block) {
                is ShiurBlock.Header2 -> {
                    val isActive = block.segIdx == currentSegmentIndex
                    Spacer(Modifier.height(if (block.segIdx == 0) 8.dp else 20.dp))
                    val h2Color = when {
                        blueMode && isActive  -> Color.White
                        blueMode              -> Color.White.copy(alpha = 0.65f)
                        isActive              -> MaterialTheme.colorScheme.primary
                        else                  -> MaterialTheme.colorScheme.onSurface
                    }
                    Text(
                        text = block.text,
                        style = MaterialTheme.typography.titleMedium.copy(
                            fontWeight = FontWeight.Bold,
                            color = h2Color
                        ),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp)
                    )
                }
                is ShiurBlock.Header3 -> {
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = block.text,
                        style = MaterialTheme.typography.titleSmall.copy(
                            fontWeight = FontWeight.SemiBold,
                            color = if (blueMode) Color.White.copy(alpha = 0.75f)
                                    else MaterialTheme.colorScheme.onSurfaceVariant
                        ),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 2.dp)
                    )
                }
                is ShiurBlock.Body -> {
                    Text(
                        text = italicLatinAnnotatedString(block.text),
                        style = MaterialTheme.typography.bodyMedium,
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight * 1.35f,
                        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp)
                    )
                }
                is ShiurBlock.Blockquote -> {
                    val barColor = if (blueMode) Color.White.copy(alpha = 0.35f)
                                   else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.35f)
                    val bgColor  = if (blueMode) Color.White.copy(alpha = 0.07f)
                                   else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.07f)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 12.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .drawBehind { drawRect(bgColor) }
                    ) {
                        // Left accent bar
                        Spacer(
                            Modifier
                                .width(3.dp)
                                .height(0.dp) // height stretches via Row alignment
                                .drawBehind {
                                    drawLine(
                                        color = barColor,
                                        start = Offset(size.width / 2, 0f),
                                        end = Offset(size.width / 2, size.height),
                                        strokeWidth = size.width
                                    )
                                }
                                .padding(top = 8.dp, bottom = 8.dp)
                        )
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(start = 10.dp, end = 6.dp, top = 8.dp, bottom = 8.dp)
                        ) {
                            if (block.showLabel) {
                                Text(
                                    text = "Text and Translation",
                                    style = MaterialTheme.typography.labelSmall.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                                    color = if (blueMode) Color.White.copy(alpha = 0.55f)
                                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
                                )
                                Spacer(Modifier.height(6.dp))
                            }
                            // Hebrew/Aramaic source — RTL if it contains Hebrew characters
                            val srcColor = if (blueMode) Amber.copy(alpha = 0.9f)
                                           else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f)
                            if (block.source.isNotEmpty()) {
                                val isHebrew = containsHebrew(block.source)
                                if (isHebrew) {
                                    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                                        Text(
                                            text = italicLatinAnnotatedString(block.source),
                                            style = MaterialTheme.typography.bodySmall.copy(
                                                textDirection = TextDirection.Rtl,
                                                textAlign = TextAlign.Start  // "start" = right in RTL
                                            ),
                                            color = srcColor,
                                            modifier = Modifier.fillMaxWidth()
                                        )
                                    }
                                } else {
                                    Text(
                                        text = italicLatinAnnotatedString(block.source),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = srcColor,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            }
                            // English translation: source words amber, added words white (blue mode) or muted
                            val addedColor = if (blueMode) Color.White.copy(alpha = 0.75f)
                                             else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f)
                            if (block.translation.isNotEmpty()) {
                                if (block.source.isNotEmpty()) Spacer(Modifier.height(6.dp))
                                Text(
                                    text = translationAnnotatedString(block.translation, sourceWordColor),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = addedColor,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
