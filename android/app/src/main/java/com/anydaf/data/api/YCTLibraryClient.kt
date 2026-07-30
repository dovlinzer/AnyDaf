package com.anydaf.data.api

import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import com.anydaf.model.YCTSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Locale

class YCTLibraryClient(
    private val baseURL: String,
    val source: YCTSource,
    /** Term ID for the root "Talmud" node. null = tractate terms are at root level. */
    private val talmudTermID: Int?,
    /** When true, articles tagged directly on the tractate term are also fetched (daf = 0). */
    val fetchesTractateLevel: Boolean,
    /** The WordPress REST collection name for this post type (e.g. "posts", "audio"). */
    private val restBase: String = "posts"
) {

    companion object {
        private val httpClient = OkHttpClient()

        /** Client for library.yctorah.org — tractate terms live under the Talmud root (ID 1899). */
        val library = YCTLibraryClient(
            baseURL = "https://library.yctorah.org/wp-json/wp/v2",
            source = YCTSource.LIBRARY,
            talmudTermID = 1899,
            fetchesTractateLevel = false
        )

        /** Client for psak.yctorah.org — tractate terms are at root level. */
        val psak = YCTLibraryClient(
            baseURL = "https://psak.yctorah.org/wp-json/wp/v2",
            source = YCTSource.PSAK,
            talmudTermID = null,
            fetchesTractateLevel = true
        )

        /**
         * Client for the "Iggros Moshe A to Z" podcast — a custom "audio" post type on
         * library.yctorah.org (same site/host as [library], so it shares the same reference
         * taxonomy term tree — hence the same talmudTermID).
         *
         * WARNING: as of 2026-07-22 this post type is NOT exposed via the WordPress REST API
         * at all (confirmed via the site's full /wp-json/ route index — no "audio" route of
         * any name exists yet). Every request through this client will fail until that's fixed
         * on the WordPress side (show_in_rest needs to be set on the post type's registration).
         * restBase = "audio" is a GUESS matching the post type's URL slug
         * (library.yctorah.org/audio/[slug]/) and WordPress's own default behavior of using the
         * post type slug as the REST base when none is explicitly configured — but the
         * theme/plugin code could set an explicit different rest_base. Once REST access is
         * enabled, check /wp-json/wp/v2/types for the real value and update this constant if it
         * differs. See "WordPress Audio Posts" in CLAUDE.md for full context.
         */
        val audio = YCTLibraryClient(
            baseURL = "https://library.yctorah.org/wp-json/wp/v2",
            source = YCTSource.AUDIO,
            talmudTermID = 1899,
            fetchesTractateLevel = true,
            restBase = "audio"
        )

        private val anyDafToYCT = mapOf(
            "Eiruvin" to "Eruvin",
            "Ta\u2019anit" to "Taanit",
            "Hullin" to "Chullin",
            "Middos" to "Middot",
            "Moed Katan" to "Moed Katan",
            "Beitzah" to "Beitza",
            "Zevachim" to "Zevahim",
            "Shevuot" to "Shevu'ot",
            "Rosh Hashanah" to "Rosh HaShanah",
            "Bekhorot" to "Bekhorot",
            "Avodah Zarah" to "Avoda Zarah",
            "Bava Kamma" to "Bava Kamma",
        )

        private val nonEnglishSuffixes = listOf("-he", "-fr", "-sp", "-ar", "-ru", "-de", "-pt")

        private fun yctName(tractate: String) = anyDafToYCT[tractate] ?: tractate
    }

    // Per-instance term ID caches
    private val tractateTermCache = mutableMapOf<String, Int>()
    private val dafTermCache = mutableMapOf<String, Map<Int, Int>>()

    // MARK: - Term Lookup (with in-session caching)

    suspend fun resolveTractateTermID(tractate: String): Int? {
        tractateTermCache[tractate]?.let { return it }
        val id = fetchTractateTermID(tractate) ?: return null
        tractateTermCache[tractate] = id
        return id
    }

    suspend fun resolveDafTermIDs(tractate: String, tractateTermID: Int): Map<Int, Int> {
        dafTermCache[tractate]?.let { return it }
        val map = fetchDafTermIDs(tractateTermID)
        dafTermCache[tractate] = map
        return map
    }

    private suspend fun fetchTractateTermID(tractate: String): Int? = withContext(Dispatchers.IO) {
        val name = yctName(tractate)
        val parentParam = talmudTermID?.let { "&parent=$it" } ?: ""
        val url = "$baseURL/reference?search=${encode(name)}$parentParam&per_page=10"
        val body = fetchString(url) ?: return@withContext null
        val arr = JSONArray(body)
        for (i in 0 until arr.length()) {
            val term = arr.getJSONObject(i)
            if (term.getString("name").equals(name, ignoreCase = true)) {
                return@withContext term.getInt("id")
            }
        }
        null
    }

    /** Returns a map of daf number → term ID for all daf-level children of a tractate term. */
    private suspend fun fetchDafTermIDs(tractateTermID: Int): Map<Int, Int> = withContext(Dispatchers.IO) {
        val url = "$baseURL/reference?parent=$tractateTermID&per_page=100"
        val body = fetchString(url) ?: return@withContext emptyMap()
        val arr = JSONArray(body)
        val result = mutableMapOf<Int, Int>()
        for (i in 0 until arr.length()) {
            val term = arr.getJSONObject(i)
            val id = term.getInt("id")
            val name = term.getString("name")
            // Format: "Berakhot 28" — extract number after last space
            val dafNum = name.substringAfterLast(" ").toIntOrNull() ?: continue
            result[dafNum] = id
        }
        result
    }

    // MARK: - Post Fetching

    /**
     * Fetches all articles for a tractate in a single bulk request.
     *
     * [allTermIDs] is every daf-level (and optionally tractate-level) term ID to query.
     * [termToDaf] maps each term ID back to its daf number (0 = tractate-level sentinel).
     * Each returned article has matchType.referencedDaf set from the post's own
     * `reference` field, so one HTTP call replaces the old per-daf loop.
     */
    suspend fun fetchBulkArticles(
        allTermIDs: List<Int>,
        termToDaf: Map<Int, Int>
    ): List<YCTArticle> = withContext(Dispatchers.IO) {
        if (allTermIDs.isEmpty()) return@withContext emptyList()

        val ids = allTermIDs.joinToString(",")
        val fields = "id,title,excerpt,content,date,link,slug,reference,_links,_embedded"
        val url = "$baseURL/$restBase?reference=$ids&per_page=100&_fields=${encode(fields)}&_embed=author,wp:featuredmedia"
        val body = fetchString(url) ?: return@withContext emptyList()
        val arr = JSONArray(body)

        val articles = mutableListOf<YCTArticle>()
        for (i in 0 until arr.length()) {
            val post = arr.getJSONObject(i)
            val id = post.getInt("id")
            val slug = post.getString("slug")

            if (nonEnglishSuffixes.any { slug.endsWith(it) }) continue

            val contentRaw = post.optJSONObject("content")?.getString("rendered") ?: ""
            val isAudio = contentRaw.contains("<audio", ignoreCase = true)

            val title = stripHtml(post.getJSONObject("title").getString("rendered"))
            // The "audio" custom post type doesn't declare excerpt support, so the
            // `excerpt` key is absent entirely from its REST response — fall back to ""
            // (the existing content-derived-excerpt logic below fills it in from there).
            var excerpt = stripHtml(post.optJSONObject("excerpt")?.optString("rendered", "") ?: "")
            if (excerpt.isEmpty() && contentRaw.isNotEmpty()) {
                // Audio posts (podcast episodes) embed a PowerPress player + link/subscribe
                // boilerplate ahead of any real description — strip it so the fallback
                // excerpt shows the actual episode blurb instead of "Podcast: Play in new
                // window | Download ... Subscribe: RSS".
                val cleaned = if (isAudio) stripAudioPlayerBoilerplate(contentRaw) else contentRaw
                val full = stripHtml(cleaned)
                excerpt = if (full.length > 200) full.take(200).trimEnd() + "…" else full
            }
            if (source == YCTSource.PSAK) {
                // WordPress's auto-generated excerpt strips all HTML before we ever see it,
                // so by this point "QUESTION"/"QUETSION" + the location are just flat text
                // ("QUESTION Riverdale, NY Dear Rabbi Linzer, ...") — there's no h3/h4 left
                // to target the way formatPsakQuestionHeader does for the full article.
                // Strip the redundant "QUESTION <City, ST>" prefix so the card preview
                // leads with the actual question instead.
                excerpt = stripPsakExcerptPrefix(excerpt)
            }
            val date = formatDate(post.optString("date", ""))
            val link = post.getString("link")
            val authorName = post.optJSONObject("_embedded")
                ?.optJSONArray("author")
                ?.optJSONObject(0)
                ?.optString("name", "") ?: ""
            val imageURL = featuredImageURL(post)

            // Determine daf associations from the post's own reference term list.
            // 0 is the tractate-root sentinel (from fetchesTractateLevel) — a post can be
            // tagged with both the root term AND specific daf terms at once, so prefer any
            // real daf number over 0 rather than letting 0 win just by being numerically
            // smallest; only fall back to 0 when there's no daf-specific tag at all.
            val refArray = post.optJSONArray("reference")
            val allDafs = mutableListOf<Int>()
            if (refArray != null) {
                for (j in 0 until refArray.length()) {
                    termToDaf[refArray.getInt(j)]?.let { allDafs.add(it) }
                }
            }
            val specificDafs = allDafs.filter { it != 0 }.toSortedSet().toList()
            val primaryDaf = specificDafs.firstOrNull() ?: 0
            val additionalDafs = specificDafs.drop(1)

            articles.add(YCTArticle(
                id = id,
                title = title,
                excerpt = excerpt,
                date = date,
                link = link,
                authorName = authorName,
                matchType = ResourceMatchType.TractateWide(primaryDaf),
                additionalDafs = additionalDafs,
                source = source,
                isAudio = isAudio,
                imageURL = imageURL
            ))
        }

        articles
    }

    // MARK: - Article Content

    suspend fun fetchArticleContent(id: Int): String = withContext(Dispatchers.IO) {
        val url = "$baseURL/$restBase/$id?_fields=id,content"
        val body = fetchString(url) ?: return@withContext ""
        val json = JSONObject(body)
        val rendered = json.getJSONObject("content").getString("rendered")
        // Some embedded media (older audio posts especially) still link http:// sources.
        // WebView blocks cleartext by default, so upgrade before it ever reaches one.
        val httpsFixed = rendered.replace("src=\"http://", "src=\"https://")
        when (source) {
            YCTSource.PSAK -> formatPsakQuestionHeader(httpsFixed)
            YCTSource.AUDIO -> stripSoundCloudEmbed(httpsFixed)
            else -> httpsFixed
        }
    }

    /** Fetches the live page (not the REST API) for an audio episode and extracts its
     * SoundCloud track ID from the embedded player's iframe `src`. The REST API's
     * `content` field is NOT a reliable source for this: some episodes have the iframe
     * manually embedded in the post body (REST-visible), but others get it injected by
     * the WordPress theme from post meta that isn't exposed via REST at all — confirmed
     * by comparing `content.rendered` (no iframe) against the live page (iframe present)
     * for the same post. The live page always renders the player either way, so scraping
     * it directly is the only approach that works uniformly across all episodes. */
    suspend fun extractSoundCloudTrackID(pageURL: String): String? = withContext(Dispatchers.IO) {
        val html = fetchString(pageURL) ?: return@withContext null
        val regex = Regex("soundcloud\\.com[^\"']*?tracks(?:%2F|/)(\\d+)", RegexOption.IGNORE_CASE)
        regex.find(html)?.groupValues?.get(1)
    }

    /** Removes an embedded SoundCloud iframe from audio-episode content when present
     * (only true for episodes where it happens to be manually embedded in the post body
     * — see [extractSoundCloudTrackID]). The app now provides its own native "Play"
     * control backed by the extracted track ID, so leaving the iframe in would just show
     * a second, often non-functional-inside-a-WebView copy of the same player. */
    private fun stripSoundCloudEmbed(html: String): String {
        var s = html
        val patterns = listOf(
            "(?is)<p>\\s*<iframe[^>]*soundcloud[^>]*>.*?</iframe>\\s*</p>",
            "(?is)<iframe[^>]*soundcloud[^>]*>.*?</iframe>"
        )
        for (pattern in patterns) {
            s = s.replace(Regex(pattern), "")
        }
        return s
    }

    /** Psak articles open with `<h3>QUESTION</h3>` immediately followed by
     * `<h4>Location</h4>`. Rendered with default heading styles these sit right on top of
     * the question text with no visual separation. Replace the pair with a single
     * right-aligned "QUESTION | Location" header block (styled in buildStyledHtml), which
     * also guarantees the actual question text starts on a fresh line below it. */
    private fun formatPsakQuestionHeader(html: String): String {
        // Match loosely on "QUE...ION" rather than an exact "QUESTION" string — the site
        // has real editorial typos (e.g. "QUETSION") that would otherwise silently fail
        // to match and leave the raw h3/h4 unstyled.
        val qRegex = Regex("<h3>\\s*QUE[A-Za-z]*ION\\s*</h3>\\s*<h4>(.*?)</h4>", RegexOption.IGNORE_CASE)
        var result = qRegex.replace(html) { m ->
            "<div class=\"psak-qheader\"><span class=\"psak-qlabel\">QUESTION</span><span class=\"psak-qloc\">${m.groupValues[1]}</span></div>"
        }
        // Normalize the "ANSWER" heading (also tolerating the "ANWER" typo seen on the
        // site) to the same custom label class as QUESTION, so they render at the same
        // size/weight instead of QUESTION being a styled div while ANSWER stays a plain,
        // larger-by-default <h3>.
        val aRegex = Regex("<h3>\\s*(?:<strong>)?AN[A-Za-z]*WER(?:</strong>)?\\s*</h3>", RegexOption.IGNORE_CASE)
        result = aRegex.replace(result, "<div class=\"psak-alabel\">ANSWER</div>")
        return result
    }

    /** Strips a leading "QUESTION <City, ST>" (or "QUETSION", etc. — real editorial typos
     * exist on the site) prefix from a plain-text psak excerpt, so the card preview leads
     * with the actual question instead of running the label and location straight into it.
     * Best-effort: only matches a "City[, ...], XX" (2-letter state/region code) shape;
     * leaves the excerpt untouched if the location doesn't look like that (e.g. a country
     * name) rather than risk mangling real question text. */
    private fun stripPsakExcerptPrefix(excerpt: String): String {
        // First try the full "QUESTION <City, ST>" shape (most common — a US city plus a
        // 2-letter state code).
        val fullRegex = Regex("^QUE[A-Za-z]*ION\\s+[^,]+,\\s*[A-Za-z]{2}\\.?\\s+", RegexOption.IGNORE_CASE)
        if (fullRegex.containsMatchIn(excerpt)) {
            return fullRegex.replace(excerpt, "")
        }
        // Fallback: locations don't always fit that shape (e.g. "QUESTION Israel" — no
        // comma, no state code), so just strip the redundant "QUESTION" label itself
        // rather than risk mangling real question text by guessing further.
        val labelRegex = Regex("^QUE[A-Za-z]*ION\\s+", RegexOption.IGNORE_CASE)
        return labelRegex.replace(excerpt, "")
    }

    // MARK: - Private Helpers

    /** The post's featured-image URL, embedded via ?_embed=wp:featuredmedia and living at:
     *  post["_embedded"]["wp:featuredmedia"][0]["media_details"]["sizes"]["medium"|"thumbnail"]["source_url"]
     *  Falls back to the media object's own top-level `source_url` (full size) if no sized
     *  variant is present. Returns null when the post has no featured image at all. */
    private fun featuredImageURL(post: JSONObject): String? {
        val media = post.optJSONObject("_embedded")
            ?.optJSONArray("wp:featuredmedia")
            ?.optJSONObject(0) ?: return null
        val sizes = media.optJSONObject("media_details")?.optJSONObject("sizes")
        sizes?.optJSONObject("medium")?.optString("source_url")?.takeIf { it.isNotEmpty() }?.let { return it }
        sizes?.optJSONObject("thumbnail")?.optString("source_url")?.takeIf { it.isNotEmpty() }?.let { return it }
        return media.optString("source_url").takeIf { it.isNotEmpty() }
    }

    private fun matchRank(type: ResourceMatchType) = when (type) {
        is ResourceMatchType.Exact -> 0
        is ResourceMatchType.Nearby -> 1
        is ResourceMatchType.TractateWide -> 2
    }

    private fun fetchString(url: String): String? {
        return try {
            val request = Request.Builder().url(url).build()
            httpClient.newCall(request).execute().use { it.body?.string() }
        } catch (e: Exception) {
            null
        }
    }

    private fun encode(value: String) = java.net.URLEncoder.encode(value, "UTF-8")

    /** Strips the PowerPress audio-player widget and its "Podcast: ... | Download ..." /
     * "Subscribe: RSS" link paragraphs from a post's raw content HTML, so an excerpt
     * derived from it (when the post has no WordPress excerpt) shows the real episode
     * description instead of that boilerplate. */
    private fun stripAudioPlayerBoilerplate(html: String): String {
        var s = html
        val patterns = listOf(
            "(?s)<div class=\"powerpress_player\"[^>]*>.*?</div>",
            "(?s)<p class=\"powerpress_links[^\"]*\"[^>]*>.*?</p>"
        )
        for (pattern in patterns) {
            s = s.replace(Regex(pattern), "")
        }
        return s
    }

    private fun stripHtml(html: String): String {
        val spanned = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
            android.text.Html.fromHtml(html, android.text.Html.FROM_HTML_MODE_LEGACY)
        } else {
            @Suppress("DEPRECATION")
            android.text.Html.fromHtml(html)
        }
        return spanned.toString().trim()
    }

    private fun formatDate(iso: String): String {
        return try {
            val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            val fmt = SimpleDateFormat("MMM d, yyyy", Locale.US)
            val date = parser.parse(iso) ?: return iso
            fmt.format(date)
        } catch (e: Exception) { iso }
    }
}
