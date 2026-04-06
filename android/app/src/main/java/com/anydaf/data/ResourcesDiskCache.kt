package com.anydaf.data

import android.content.Context
import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Disk cache for YCT Library article lists keyed by tractate name only.
 * One cache file per tractate (e.g. yct_Berakhot.json) holds all articles for
 * that tractate, each tagged with its daf via matchType.referencedDaf.
 * TTL is 7 days; expired entries can be evicted via [evictExpired].
 *
 * Callers should call categorize() on the returned list to split articles into
 * exact / nearby / tractate-wide sections for the current daf.
 */
object ResourcesDiskCache {

    private const val TTL_MS = 7L * 24 * 60 * 60 * 1000  // 7 days

    // MARK: - Public API

    /**
     * Loads all cached articles for a tractate.
     * Returns null if no entry exists or the entry has expired.
     * Articles are stored with TractateWide(daf) so the daf number is preserved.
     */
    fun load(context: Context, tractate: String): List<YCTArticle>? {
        val file = cacheFile(context, tractate)
        if (!file.exists()) return null
        return try {
            val root = JSONObject(file.readText())
            val savedAt = root.getLong("savedAt")
            if (System.currentTimeMillis() - savedAt > TTL_MS) {
                file.delete()
                return null
            }
            parseArticleArray(root.getJSONArray("articles"))
        } catch (e: Exception) {
            file.delete()
            null
        }
    }

    /**
     * Saves a flat list of tractate articles to disk.
     * Articles should use TractateWide(daf) so the daf is recoverable.
     */
    fun save(context: Context, tractate: String, articles: List<YCTArticle>) {
        try {
            val root = JSONObject()
            root.put("savedAt", System.currentTimeMillis())
            root.put("articles", serializeArticleArray(articles))
            val file = cacheFile(context, tractate)
            file.parentFile?.mkdirs()
            file.writeText(root.toString())
        } catch (_: Exception) {}
    }

    /** Deletes all cache files whose TTL has expired. Call at app startup. */
    fun evictExpired(context: Context) {
        try {
            val dir = cacheDir(context)
            if (!dir.exists()) return
            val now = System.currentTimeMillis()
            dir.listFiles { f -> f.name.startsWith("yct_") && f.name.endsWith(".json") }
                ?.forEach { file ->
                    try {
                        val root = JSONObject(file.readText())
                        val savedAt = root.getLong("savedAt")
                        if (now - savedAt > TTL_MS) file.delete()
                    } catch (_: Exception) {
                        file.delete()
                    }
                }
        } catch (_: Exception) {}
    }

    // MARK: - Private helpers

    private fun cacheDir(context: Context): File =
        File(context.cacheDir, "yct_resources")

    private fun cacheFile(context: Context, tractate: String): File {
        val safeTractate = tractate.replace(Regex("[^A-Za-z0-9]"), "_")
        return File(cacheDir(context), "yct_${safeTractate}.json")
    }

    private fun serializeArticleArray(articles: List<YCTArticle>): JSONArray {
        val arr = JSONArray()
        articles.forEach { article ->
            val obj = JSONObject()
            obj.put("id", article.id)
            obj.put("title", article.title)
            obj.put("excerpt", article.excerpt)
            obj.put("date", article.date)
            obj.put("link", article.link)
            obj.put("authorName", article.authorName)
            obj.put("matchTypeTag", matchTypeTag(article.matchType))
            obj.put("matchTypeDaf", article.matchType.referencedDaf)
            val dafsArr = JSONArray()
            article.additionalDafs.forEach { dafsArr.put(it) }
            obj.put("additionalDafs", dafsArr)
            arr.put(obj)
        }
        return arr
    }

    private fun parseArticleArray(arr: JSONArray): List<YCTArticle> {
        val result = mutableListOf<YCTArticle>()
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            val tag = obj.optString("matchTypeTag", "tractate")
            val daf = obj.optInt("matchTypeDaf", 0)
            val matchType: ResourceMatchType = when (tag) {
                "exact"    -> ResourceMatchType.Exact(daf)
                "nearby"   -> ResourceMatchType.Nearby(daf)
                else       -> ResourceMatchType.TractateWide(daf)
            }
            val additionalDafs = mutableListOf<Int>()
            val dafsArr = obj.optJSONArray("additionalDafs")
            if (dafsArr != null) {
                for (j in 0 until dafsArr.length()) additionalDafs.add(dafsArr.getInt(j))
            }
            result.add(
                YCTArticle(
                    id             = obj.getInt("id"),
                    title          = obj.getString("title"),
                    excerpt        = obj.getString("excerpt"),
                    date           = obj.getString("date"),
                    link           = obj.getString("link"),
                    authorName     = obj.optString("authorName", ""),
                    matchType      = matchType,
                    additionalDafs = additionalDafs
                )
            )
        }
        return result
    }

    private fun matchTypeTag(type: ResourceMatchType): String = when (type) {
        is ResourceMatchType.Exact        -> "exact"
        is ResourceMatchType.Nearby       -> "nearby"
        is ResourceMatchType.TractateWide -> "tractate"
    }
}
