package com.anydaf.data.api

import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import com.anydaf.model.YCTReferenceTerm
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Locale

object YCTLibraryClient {

    private val httpClient = OkHttpClient()
    private const val BASE_URL = "https://library.yctorah.org/wp-json/wp/v2"
    private const val TALMUD_TERM_ID = 1899

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

    // MARK: - Term Lookup

    suspend fun fetchTractateTermID(tractate: String): Int? = withContext(Dispatchers.IO) {
        val name = yctName(tractate)
        val url = "$BASE_URL/reference?search=${encode(name)}&parent=$TALMUD_TERM_ID&per_page=10"
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
    suspend fun fetchDafTermIDs(tractateTermID: Int): Map<Int, Int> = withContext(Dispatchers.IO) {
        val url = "$BASE_URL/reference?parent=$tractateTermID&per_page=100"
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
     * Fetches articles for the given term IDs.
     * [exactTermIDs] are matched to current daf; [nearbyTermIDs] map to nearby dafs.
     * English-only filter applied via slug suffix check.
     */
    suspend fun fetchArticles(
        exactTermIDs: List<Int>,
        nearbyTermIDs: Map<Int, Int>,  // termID → daf number
        tractateTermID: Int? = null
    ): List<YCTArticle> = withContext(Dispatchers.IO) {
        val allTermIDs = (exactTermIDs + nearbyTermIDs.keys + listOfNotNull(tractateTermID)).distinct()
        if (allTermIDs.isEmpty()) return@withContext emptyList()

        val ids = allTermIDs.joinToString(",")
        val url = "$BASE_URL/posts?reference=$ids&per_page=20&_fields=id,title,excerpt,date,link,slug"
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
            val excerpt = stripHtml(post.getJSONObject("excerpt").getString("rendered"))
            val date = formatDate(post.optString("date", ""))
            val link = post.getString("link")

            val matchType = resolveMatchType(id, exactTermIDs, nearbyTermIDs, tractateTermID)

            articles.add(YCTArticle(
                id = id,
                title = title,
                excerpt = excerpt,
                date = date,
                link = link,
                authorName = "",
                matchType = matchType
            ))
        }

        // Sort: exact first, nearby second, tractate-wide last
        articles.sortedBy { matchRank(it.matchType) }
    }

    // MARK: - Article Content

    suspend fun fetchArticleContent(id: Int): String = withContext(Dispatchers.IO) {
        val url = "$BASE_URL/posts/$id?_fields=id,content"
        val body = fetchString(url) ?: return@withContext ""
        val json = JSONObject(body)
        json.getJSONObject("content").getString("rendered")
    }

    // MARK: - Private Helpers

    private fun resolveMatchType(
        postID: Int,
        exactTermIDs: List<Int>,
        nearbyTermIDs: Map<Int, Int>,
        tractateTermID: Int?
    ): ResourceMatchType {
        // Since we can't cheaply determine which term matched a post without a separate API call,
        // ResourcesViewModel passes exact vs nearby term IDs separately. Here we default to
        // exact if any exact term was requested, nearby otherwise, tractate-wide as fallback.
        // Note: this return value is overridden by fetchAndTag's .copy(matchType = …) call,
        // so the daf placeholder of 0 here is never surfaced in the UI.
        return when {
            exactTermIDs.isNotEmpty() -> ResourceMatchType.Exact(0)
            nearbyTermIDs.isNotEmpty() -> {
                val daf = nearbyTermIDs.values.firstOrNull() ?: 0
                ResourceMatchType.Nearby(daf)
            }
            else -> ResourceMatchType.TractateWide(0)
        }
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

    private fun stripHtml(html: String): String {
        // Html.fromHtml handles all named and numeric HTML entities and strips tags
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
