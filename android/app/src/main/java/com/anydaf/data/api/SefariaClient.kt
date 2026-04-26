package com.anydaf.data.api

import android.util.Log
import com.anydaf.model.Tractate
import com.anydaf.model.StudySection
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val anyDafToSefaria = mapOf(
    "Eiruvin"       to "Eruvin",
    "Ta\u2019anit"  to "Taanit",
    "Hullin"        to "Chullin",
)

private fun sefariaName(tractate: String) = anyDafToSefaria[tractate] ?: tractate

/** Maps daf+amud keys to Sefaria refs for tractates with non-standard pagination. */

/** Shekalim: Jerusalem Talmud — Daf Yomi alt-struct maps to chapter:halakha:segment refs. */
private val shekalimDafYomiRefs = mapOf(
    "2a"  to "Jerusalem Talmud Shekalim 1:1:1-5",
    "2b"  to "Jerusalem Talmud Shekalim 1:1:5-10",
    "3a"  to "Jerusalem Talmud Shekalim 1:1:10-2:5",
    "3b"  to "Jerusalem Talmud Shekalim 1:2:5-4:1",
    "4a"  to "Jerusalem Talmud Shekalim 1:4:1-5",
    "4b"  to "Jerusalem Talmud Shekalim 1:4:5-9",
    "5a"  to "Jerusalem Talmud Shekalim 1:4:9-2:1:4",
    "5b"  to "Jerusalem Talmud Shekalim 2:1:4-3:1",
    "6a"  to "Jerusalem Talmud Shekalim 2:3:1-4:1",
    "6b"  to "Jerusalem Talmud Shekalim 2:4:1-5",
    "7a"  to "Jerusalem Talmud Shekalim 2:4:5-5:4",
    "7b"  to "Jerusalem Talmud Shekalim 2:5:4-3:1:3",
    "8a"  to "Jerusalem Talmud Shekalim 3:1:3-2:2",
    "8b"  to "Jerusalem Talmud Shekalim 3:2:2-8",
    "9a"  to "Jerusalem Talmud Shekalim 3:2:8-3:1",
    "9b"  to "Jerusalem Talmud Shekalim 3:3:1-4:1:1",
    "10a" to "Jerusalem Talmud Shekalim 4:1:1-2:1",
    "10b" to "Jerusalem Talmud Shekalim 4:2:1-4",
    "11a" to "Jerusalem Talmud Shekalim 4:2:4-3:2",
    "11b" to "Jerusalem Talmud Shekalim 4:3:2-4:1",
    "12a" to "Jerusalem Talmud Shekalim 4:4:1-5",
    "12b" to "Jerusalem Talmud Shekalim 4:4:5-9",
    "13a" to "Jerusalem Talmud Shekalim 4:4:9-5:1:3",
    "13b" to "Jerusalem Talmud Shekalim 5:1:3-12",
    "14a" to "Jerusalem Talmud Shekalim 5:1:12-21",
    "14b" to "Jerusalem Talmud Shekalim 5:1:21-3:2",
    "15a" to "Jerusalem Talmud Shekalim 5:3:2-4:10",
    "15b" to "Jerusalem Talmud Shekalim 5:4:10-6:1:5",
    "16a" to "Jerusalem Talmud Shekalim 6:1:5-11",
    "16b" to "Jerusalem Talmud Shekalim 6:1:11-2:1",
    "17a" to "Jerusalem Talmud Shekalim 6:2:1-7",
    "17b" to "Jerusalem Talmud Shekalim 6:2:7-3:3",
    "18a" to "Jerusalem Talmud Shekalim 6:3:3-4:2",
    "18b" to "Jerusalem Talmud Shekalim 6:4:2-7",
    "19a" to "Jerusalem Talmud Shekalim 6:4:7-7:2:1",
    "19b" to "Jerusalem Talmud Shekalim 7:2:1-7",
    "20a" to "Jerusalem Talmud Shekalim 7:2:7-3:2",
    "20b" to "Jerusalem Talmud Shekalim 7:3:2-7",
    "21a" to "Jerusalem Talmud Shekalim 7:3:7-8:1:1",
    "21b" to "Jerusalem Talmud Shekalim 8:1:1-3:1",
    "22a" to "Jerusalem Talmud Shekalim 8:3:1-4:4",
    "22b" to "Jerusalem Talmud Shekalim 8:4:4",
)

/** Kinnim: Mishnah-only. daf 22=ch1, 23=ch2, 24-25a=ch3. Only 'a' amudim have content. */
private val kinnimMishnahRefs = mapOf(
    "22a" to "Mishnah Kinnim 1",
    "23a" to "Mishnah Kinnim 2",
    "24a" to "Mishnah Kinnim 3:1-5",
    "25a" to "Mishnah Kinnim 3:6",
)

/**
 * Middot: Mishnah-only. Mapping derived from Vilna Shas page markers.
 * Ch1 (9 mishnayot): 34a=1-4, 34b=5-9 | Ch2 (6): 35a=1-3, 35b=4-6
 * Ch3 (8): all on 36a | Ch4 (7): 36b=4:1-2, 37a=4:3-7
 * Ch5 (4): 37b
 */
private val middotMishnahRefs = mapOf(
    "34a" to "Mishnah Middot 1:1-4",
    "34b" to "Mishnah Middot 1:5-9",
    "35a" to "Mishnah Middot 2:1-3",
    "35b" to "Mishnah Middot 2:4-6",
    "36a" to "Mishnah Middot 3",
    "36b" to "Mishnah Middot 4:1-2",
    "37a" to "Mishnah Middot 4:3-7",
    "37b" to "Mishnah Middot 5",
)

private fun sefariaRef(tractate: String, daf: Int, amud: String): String? {
    val key = "$daf$amud"
    return when (tractate) {
        "Shekalim" -> shekalimDafYomiRefs[key]
        "Kinnim"   -> kinnimMishnahRefs[key]
        "Middot"   -> middotMishnahRefs[key]
        else       -> null  // null = use standard ref
    }
}

object SefariaClient {
    private const val TAG = "SefariaClient"
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    private const val BASE_URL = "https://www.sefaria.org/api"

    suspend fun getTractateList(): List<Tractate> {
        val request = Request.Builder().url("$BASE_URL/index").build()
        val response = try {
            kotlinx.coroutines.Dispatchers.IO.run {
                client.newCall(request).execute()
            }
        } catch (e: Exception) {
            return emptyList()
        }

        val body = response.body?.string() ?: return emptyList()
        val index = JSONArray(body)
        val talmudCategory = (0 until index.length()).map { index.getJSONObject(it) }
            .find { it.getString("category") == "Talmud" } ?: return emptyList()

        val bavli = talmudCategory.getJSONArray("contents")
            .let { (0 until it.length()).map { i -> it.getJSONObject(i) } }
            .find { it.getString("category") == "Bavli" } ?: return emptyList()

        val orders = bavli.getJSONArray("contents")
        val tractates = mutableListOf<Tractate>()

        for (i in 0 until orders.length()) {
            val order = orders.getJSONObject(i)
            val contents = order.getJSONArray("contents")
            for (j in 0 until contents.length()) {
                val tractate = contents.getJSONObject(j)
                val title = tractate.getString("title")
                // For now, placeholders for start/end daf
                tractates.add(Tractate(title, 2, 100))
            }
        }
        return tractates
    }

    suspend fun fetchText(tractate: String, daf: Int, amud: String? = null, language: String = "en"): List<String> {
        // Tractates with non-standard Sefaria pagination (Jerusalem Talmud, Mishnah-only).
        // sefariaRef returns the mapped ref, or null meaning "no text for this amud".
        if (amud != null) {
            val special = sefariaRef(tractate, daf, amud)
            if (special != null) {
                val segments = fetchTextV3(special, language)
                return if (tractate == "Kinnim" || tractate == "Middot")
                    applyMishnaLabels(segments, special, hebrew = language == "he")
                else segments
            }
            // tractate IS special but this amud has no mapped ref → no text
            val isSpecial = tractate == "Shekalim" || tractate == "Kinnim" || tractate == "Middot"
            if (isSpecial) return emptyList()
        }

        val dafStr = if (amud != null) "$daf$amud" else dafToSefaria(daf)
        val url = "$BASE_URL/texts/${sefariaName(tractate)}.$dafStr?context=0&commentary=0"
        val request = Request.Builder().url(url).build()

        val response = try {
            kotlinx.coroutines.Dispatchers.IO.run {
                client.newCall(request).execute()
            }
        } catch (e: Exception) {
            return emptyList()
        }

        val body = response.body?.string() ?: return emptyList()
        val json = JSONObject(body)
        val key = if (language == "he") "he" else "text"

        return flattenTextValue(json.opt(key))
    }

    /** Fetches text via the Sefaria v3 API using a direct ref string (e.g. a chapter:halakha range). */
    private suspend fun fetchTextV3(ref: String, language: String): List<String> {
        val encodedRef = ref.replace(" ", "%20")
        val versionParam = if (language == "he") "primary" else "english"
        val langParam = if (language == "he") "he" else "en"
        val url = "https://www.sefaria.org/api/v3/texts/$encodedRef?version=$versionParam&language=$langParam"

        val body = try {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                val req = Request.Builder().url(url).build()
                client.newCall(req).execute().use { it.body?.string() }
            }
        } catch (e: Exception) {
            Log.e(TAG, "V3 fetch error for $ref", e)
            return emptyList()
        } ?: return emptyList()

        val json = try { JSONObject(body) } catch (e: Exception) { return emptyList() }
        val versions = json.optJSONArray("versions") ?: return emptyList()
        if (versions.length() == 0) return emptyList()
        return flattenTextValue(versions.getJSONObject(0).opt("text"))
    }

    /**
     * Prepends [ch:mishna] labels to each segment of a Mishnah-only tractate fetch.
     * English: [3:4]  Hebrew: [ג:ד]
     * Parses chapter and optional start mishna from the ref string,
     * e.g. "Mishnah Middot 4:3-7" → chapter 4, starting mishna 3.
     */
    private fun applyMishnaLabels(segments: List<String>, ref: String, hebrew: Boolean): List<String> {
        val match = Regex("""Mishnah \w+ (\d+)(?::(\d+))?""").find(ref) ?: return segments
        val chapter = match.groupValues[1].toIntOrNull() ?: return segments
        val startMishna = match.groupValues[2].toIntOrNull() ?: 1
        return segments.mapIndexed { idx, seg ->
            val mishna = startMishna + idx
            val label = if (hebrew) "[${hebrewNumeral(chapter)}:${hebrewNumeral(mishna)}]"
                        else "[$chapter:$mishna]"
            "$label <b>$seg</b>"
        }
    }

    /** Converts an integer (1–22) to its Hebrew letter numeral (gematria). */
    private fun hebrewNumeral(n: Int): String {
        val letters = arrayOf("", "א","ב","ג","ד","ה","ו","ז","ח","ט","י",
                              "יא","יב","יג","יד","טו","טז","יז","יח","יט","כ","כא","כב")
        return if (n >= 1 && n < letters.size) letters[n] else n.toString()
    }

    /** Recursively flattens Sefaria text values: String, JSONArray of String, or nested JSONArrays. */
    private fun flattenTextValue(value: Any?): List<String> = when (value) {
        is String -> if (value.isNotEmpty()) listOf(value) else emptyList()
        is JSONArray -> (0 until value.length()).flatMap { flattenTextValue(value.opt(it)) }
        else -> emptyList()
    }

    private fun dafToSefaria(daf: Int): String {
        val num = (daf + 1) / 2
        val side = if (daf % 2 == 1) "a" else "b"
        return "$num$side"
    }

    fun parseSections(enSegs: List<String>, heSegs: List<String>?): List<StudySection> {
        if (enSegs.isEmpty()) return emptyList()

        val maxSegments = 6
        val headerPattern = Regex("""<(?:strong|b)>([A-Z][A-Z ]*):?</(?:strong|b)>""")

        // Phase 1: split by bold headers (MISHNA:, GEMARA:, etc.)
        data class RawPart(val title: String, val segs: MutableList<String>, val indices: MutableList<Int>)

        val rawParts = mutableListOf<RawPart>()
        var current = RawPart("Introduction", mutableListOf(), mutableListOf())

        for ((segIdx, segment) in enSegs.withIndex()) {
            val match = headerPattern.find(segment)
            if (match != null) {
                val location = match.range.first
                // Text before the header stays with current section
                if (location > 0) {
                    val before = segment.substring(0, location).trim()
                    if (before.isNotEmpty()) current.segs.add(before)
                }
                if (current.segs.isNotEmpty()) rawParts.add(current)

                val headerTitle = match.groupValues[1].trim()
                val afterTag = segment.substring(match.range.last + 1).trim()
                current = RawPart(headerTitle, mutableListOf(), mutableListOf())
                val leadingText = if (afterTag.isNotEmpty()) "$headerTitle. $afterTag" else "$headerTitle."
                current.segs.add(leadingText)
                current.indices.add(segIdx)
            } else {
                current.segs.add(segment)
                current.indices.add(segIdx)
            }
        }
        if (current.segs.isNotEmpty()) rawParts.add(current)

        // Rename lone untitled section
        if (rawParts.size == 1 && rawParts[0].title == "Introduction") {
            rawParts[0] = rawParts[0].copy(title = "Full Text")
        }

        fun hebrewTextFor(indices: List<Int>): String? {
            val hSegs = heSegs ?: return null
            val mapped = indices.mapNotNull { if (it < hSegs.size) hSegs[it] else null }
            return if (mapped.isEmpty()) null else mapped.joinToString("\n\n")
        }

        fun hebrewSegsFor(indices: List<Int>): List<String> {
            val hSegs = heSegs ?: return emptyList()
            return indices.mapNotNull { if (it < hSegs.size) hSegs[it] else null }
        }

        // Phase 2: subdivide sections that exceed maxSegments
        val studySections = mutableListOf<StudySection>()
        for (part in rawParts) {
            if (part.segs.size <= maxSegments) {
                studySections.add(StudySection(
                    title = part.title,
                    rawText = part.segs.joinToString("\n\n"),
                    rawSegments = part.segs.toList(),
                    hebrewText = hebrewTextFor(part.indices),
                    hebrewSegments = hebrewSegsFor(part.indices)
                ))
            } else {
                val totalChunks = (part.segs.size + maxSegments - 1) / maxSegments
                for (i in 0 until totalChunks) {
                    val start = i * maxSegments
                    val end = minOf(start + maxSegments, part.segs.size)
                    val idxStart = minOf(start, part.indices.size)
                    val idxEnd = minOf(end, part.indices.size)
                    studySections.add(StudySection(
                        title = "${part.title}, Part ${i + 1}",
                        rawText = part.segs.subList(start, end).joinToString("\n\n"),
                        rawSegments = part.segs.subList(start, end),
                        hebrewText = hebrewTextFor(part.indices.subList(idxStart, idxEnd)),
                        hebrewSegments = hebrewSegsFor(part.indices.subList(idxStart, idxEnd))
                    ))
                }
            }
        }

        // Fallback: chunk all segments if nothing parsed
        if (studySections.isEmpty()) {
            val totalChunks = (enSegs.size + maxSegments - 1) / maxSegments
            for (i in 0 until totalChunks) {
                val start = i * maxSegments
                val end = minOf(start + maxSegments, enSegs.size)
                val indices = (start until end).toList()
                studySections.add(StudySection(
                    title = "Section ${i + 1}",
                    rawText = enSegs.subList(start, end).joinToString("\n\n"),
                    rawSegments = enSegs.subList(start, end),
                    hebrewText = hebrewTextFor(indices),
                    hebrewSegments = hebrewSegsFor(indices)
                ))
            }
        }

        return studySections
    }

    /** Removes `<sup …>N</sup>` footnote-number markers and
     *  `<i class="footnote">…</i>` blocks (including nested `<i>` tags). */
    private fun stripFootnoteBlocks(html: String): String {
        // Remove <sup …>N</sup> footnote-marker spans (class attr varies)
        var s = html.replace(Regex("<sup\\b[^>]*>[^<]*</sup>"), "")

        // Remove <i class="footnote">…</i> blocks.
        // The footnote text may contain nested <i> tags, so we track depth
        // rather than relying on a simple regex.
        val result = StringBuilder()
        var idx = 0
        while (idx < s.length) {
            val tagOpen = s.indexOf("<i", idx, ignoreCase = true)
            if (tagOpen == -1) { result.append(s.substring(idx)); break }
            val tagClose = s.indexOf(">", tagOpen)
            if (tagClose == -1) { result.append(s.substring(idx)); break }
            val fullTag = s.substring(tagOpen, tagClose + 1)
            if (!fullTag.contains("""class="footnote"""")) {
                // Not a footnote tag — keep everything up to and including it
                result.append(s.substring(idx, tagClose + 1))
                idx = tagClose + 1
                continue
            }
            // It's a footnote opening tag — keep text before it, skip the block
            result.append(s.substring(idx, tagOpen))
            var pos = tagClose + 1
            var depth = 1
            while (depth > 0 && pos < s.length) {
                val nextOpen  = s.indexOf("<i",  pos, ignoreCase = true)
                val nextClose = s.indexOf("</i>", pos, ignoreCase = true)
                when {
                    nextOpen != -1 && nextClose != -1 && nextOpen < nextClose -> {
                        val end = s.indexOf(">", nextOpen)
                        if (end == -1) { pos = s.length; break }
                        depth++
                        pos = end + 1
                    }
                    nextClose != -1 -> {
                        depth--
                        pos = nextClose + 4 // "</i>".length
                    }
                    else -> pos = s.length
                }
            }
            idx = pos
        }
        return result.toString()
    }

    fun stripHtml(html: String): String {
        return stripFootnoteBlocks(html)
            .replace(Regex("<[^>]*>"), "")
            .replace("&nbsp;", " ")
            .trim()
    }

    fun endsInMidSentence(segs: List<String>): Boolean {
        val last = segs.lastOrNull() ?: return false
        val clean = stripHtml(last)
        if (clean.isEmpty()) return false
        return !clean.last().let { it == '.' || it == '?' || it == '!' }
    }

    // MARK: - Sentence Detection logic

    fun isSentenceTerminal(c: Char, idx: Int, text: String): Boolean {
        if (c !in ".!?") return false

        var tokenStart = idx
        while (tokenStart > 0) {
            val ch = text[tokenStart - 1]
            if (ch.isWhitespace() || ch == '.' || ch == ',' || ch == ';') break
            tokenStart--
        }
        val preceding = text.substring(tokenStart, idx).lowercase()
        if (preceding.length == 1) return false

        val known = setOf("i.e", "e.g", "etc", "vs", "cf", "ibid", "dr", "mr", "mrs", "ms",
            "prof", "rev", "sr", "jr", "jan", "feb", "mar", "apr", "jun", "jul",
            "aug", "sep", "oct", "nov", "dec")
        if (known.contains(preceding)) return false

        val afterIdx = idx + 1
        if (afterIdx < text.length) {
            val nextChar = text.substring(afterIdx).trimStart().firstOrNull()
            if (nextChar != null && (nextChar.isLowerCase() || nextChar == ',')) return false
        }
        return true
    }

    fun lastSentenceTerminal(text: String): Int? {
        if (text.isEmpty()) return null
        for (i in text.indices.reversed()) {
            val c = text[i]
            if (c in ".!?" && isSentenceTerminal(c, i, text)) return i
        }
        return null
    }

    fun firstSentenceTerminal(text: String): Int? {
        if (text.isEmpty()) return null
        for (i in text.indices) {
            val c = text[i]
            if (c in ".!?" && isSentenceTerminal(c, i, text)) return i
        }
        return null
    }

    // Extension to run OkHttp synchronously on IO dispatcher
    private suspend fun kotlinx.coroutines.CoroutineDispatcher.run(block: () -> okhttp3.Response): okhttp3.Response =
        kotlinx.coroutines.withContext(this) { block() }
}
