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
    val fetchesTractateLevel: Boolean
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

    /** Fetches articles tagged with any of the given term IDs. English-only filter applied. */
    suspend fun fetchArticles(termIDs: List<Int>): List<YCTArticle> = withContext(Dispatchers.IO) {
        if (termIDs.isEmpty()) return@withContext emptyList()

        val ids = termIDs.joinToString(",")
        val url = "$baseURL/posts?reference=$ids&per_page=20&_embed=author"
        val body = fetchString(url) ?: return@withContext emptyList()
        val arr = JSONArray(body)

        val articles = mutableListOf<YCTArticle>()
        for (i in 0 until arr.length()) {
            val post = arr.getJSONObject(i)
            val id = post.getInt("id")
            val slug = post.getString("slug")

            // Skip non-English
            if (nonEnglishSuffixes.any { slug.endsWith(it) }) continue

            val title = stripHtml(post.getJSONObject("title").getString("rendered"))
            var excerpt = stripHtml(post.getJSONObject("excerpt").getString("rendered"))
            if (excerpt.isEmpty()) {
                val full = stripHtml(post.optJSONObject("content")?.getString("rendered") ?: "")
                excerpt = if (full.length > 200) full.take(200).trimEnd() + "…" else full
            }
            val date = formatDate(post.optString("date", ""))
            val link = post.getString("link")
            val authorName = post.optJSONObject("_embedded")
                ?.optJSONArray("author")
                ?.optJSONObject(0)
                ?.optString("name", "") ?: ""

            articles.add(YCTArticle(
                id = id,
                title = title,
                excerpt = excerpt,
                date = date,
                link = link,
                authorName = authorName,
                matchType = ResourceMatchType.Exact(0),
                source = source
            ))
        }

        articles.sortedBy { matchRank(it.matchType) }
    }

    // MARK: - Article Content

    suspend fun fetchArticleContent(id: Int): String = withContext(Dispatchers.IO) {
        val url = "$baseURL/posts/$id?_fields=id,content"
        val body = fetchString(url) ?: return@withContext ""
        val json = JSONObject(body)
        json.getJSONObject("content").getString("rendered")
    }

    // MARK: - Private Helpers

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
