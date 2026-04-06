package com.anydaf.data.api

import android.content.Context
import android.util.Log
import com.anydaf.AnyDafApp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Mirrors iOS FeedManager.swift.
 *
 * Phase 1: Walk the SoundCloud RSS feed (paginated) for direct MP3 URLs.
 * Phase 2: Fetch each tractate's SoundCloud playlist to fill in any missing dafs
 *          (the RSS feed only covers the most recent ~1,200 episodes).
 *
 * Result is cached to filesDir/episode_index.json with a 7-day TTL.
 */
object FeedManager {
    private const val TAG = "FeedManager"
    private const val FEED_BASE = "https://feeds.soundcloud.com/users/soundcloud:users:958779193/sounds.rss"
    const val SOUNDCLOUD_CLIENT_ID = "1IzwHiVxAHeYKAMqN0IIGD3ZARgJy2kl"
    private const val SUPABASE_URL = "https://zewdazoijdpakugfvnzt.supabase.co"
    private const val SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpld2Rhem9pamRwYWt1Z2Z2bnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzIwODYsImV4cCI6MjA5MDA0ODA4Nn0.HJxIG18vEpt-exzoQwRLeXiKLAinWfBl7gMORKjxIz8"
    private const val CACHE_FILE = "episode_index.json"
    private const val CACHE_TIMESTAMP_KEY = "episodeIndexTimestamp"
    private const val CACHE_TTL_MS = 7L * 24 * 60 * 60 * 1000

    // Canonical tractate name → SoundCloud playlist ID
    private val tractatePlaylistIds = mapOf(
        "Berakhot"      to 1224453841L,
        "Shabbat"       to 1224957730L,
        "Eiruvin"       to 1224604675L,
        "Pesachim"      to 1223731237L,
        "Yoma"          to 1224408415L,
        "Sukkah"        to 1224961240L,
        "Beitzah"       to 1224467716L,
        "Rosh Hashanah" to 1225124800L,
        "Ta\u2019anit"  to 1947852215L,
        "Moed Katan"    to 1947706063L,
        "Chagigah"      to 1947633743L,
        "Yevamot"       to 1225156528L,
        "Ketubot"       to 1224649789L,
        "Nedarim"       to 1224705577L,
        "Nazir"         to 1950629151L,
        "Sotah"         to 1595841331L,
        "Gittin"        to 1224617542L,
        "Kiddushin"     to 1224719668L,
        "Bava Kamma"    to 1224873547L,
        "Bava Metzia"   to 1224692203L,
        "Bava Batra"    to 1224939157L,
        "Sanhedrin"     to 1225177738L,
        "Makkot"        to 1224421891L,
        "Shevuot"       to 1954367887L,
        "Avodah Zarah"  to 1224438616L,
        "Horayot"       to 1224645901L,
        "Zevachim"      to 1225250722L,
        "Menachot"      to 1950820791L,
        "Hullin"        to 1224735955L,
        "Bekhorot"      to 1224596788L,
        "Arakhin"       to 1224424696L,
        "Temurah"       to 1225194493L,
        "Meilah"        to 1224865387L,
        "Kinnim"        to 1954771503L,
        "Tamid"         to 1954771299L,
        "Middot"        to 1954771395L,
        "Niddah"        to 1225213678L,
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val prefs get() =
        AnyDafApp.context.getSharedPreferences("feed_prefs", Context.MODE_PRIVATE)

    private val cacheFile get() =
        File(AnyDafApp.context.filesDir, CACHE_FILE)

    // tractate → daf → "soundcloud-track://ID" or direct MP3 URL
    private val _episodeIndex = MutableStateFlow<Map<String, Map<Int, String>>>(emptyMap())
    val episodeIndex: StateFlow<Map<String, Map<Int, String>>> = _episodeIndex.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    val hasIndex: Boolean get() = _episodeIndex.value.isNotEmpty()

    fun init() {
        loadFromCache()
    }

    /** Returns the audio URL string for a given tractate+daf, or null if not in the index. */
    fun audioUrl(tractate: String, daf: Int): String? =
        _episodeIndex.value[tractate]?.get(daf)

    /** Fetch only if cache is missing or older than 7 days.
     *  Tries Supabase first (fast single request); falls back to RSS crawl if unavailable. */
    suspend fun refreshIfNeeded() {
        val lastFetch = prefs.getLong(CACHE_TIMESTAMP_KEY, 0L)
        val age = System.currentTimeMillis() - lastFetch
        if (hasIndex && age <= CACHE_TTL_MS) return

        val supabaseIndex = fetchFromSupabase()
        if (supabaseIndex != null && supabaseIndex.isNotEmpty()) {
            _episodeIndex.value = supabaseIndex
            saveToCache(supabaseIndex)
            prefs.edit().putLong(CACHE_TIMESTAMP_KEY, System.currentTimeMillis()).apply()
            Log.d(TAG, "Loaded ${supabaseIndex.values.sumOf { it.size }} episodes from Supabase")
        } else {
            fetchAll()
        }
    }

    /** Fetch the full episode index from Supabase episode_audio table.
     *  Returns null if the request fails (caller should fall back to RSS crawl). */
    private suspend fun fetchFromSupabase(): Map<String, Map<Int, String>>? = withContext(Dispatchers.IO) {
        val url = "$SUPABASE_URL/rest/v1/episode_audio?select=tractate,daf,audio_url"
        val body = try {
            val req = Request.Builder()
                .url(url)
                .addHeader("apikey", SUPABASE_ANON_KEY)
                .addHeader("Authorization", "Bearer $SUPABASE_ANON_KEY")
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.code != 200) {
                    Log.w(TAG, "Supabase episode_audio HTTP ${resp.code}")
                    return@withContext null
                }
                resp.body?.string()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Supabase episode_audio fetch failed", e)
            return@withContext null
        } ?: return@withContext null

        try {
            val arr = org.json.JSONArray(body)
            val index = mutableMapOf<String, MutableMap<Int, String>>()
            for (i in 0 until arr.length()) {
                val row      = arr.getJSONObject(i)
                val tractate = row.optString("tractate").takeIf { it.isNotEmpty() } ?: continue
                val daf      = row.optInt("daf", -1).takeIf { it > 0 } ?: continue
                val audioUrl = row.optString("audio_url").takeIf { it.isNotEmpty() } ?: continue
                index.getOrPut(tractate) { mutableMapOf() }[daf] = audioUrl
            }
            if (index.isEmpty()) null else index.mapValues { it.value.toMap() }
        } catch (e: Exception) {
            Log.w(TAG, "Supabase episode_audio JSON parse failed", e)
            null
        }
    }

    /** Force a full re-fetch from RSS + SoundCloud playlists. */
    suspend fun fetchAll() = withContext(Dispatchers.IO) {
        _isLoading.value = true
        val index = mutableMapOf<String, MutableMap<Int, String>>()

        // ── Phase 1: RSS feed ─────────────────────────────────────────────
        var nextUrl: String? = FEED_BASE
        var pageCount = 0
        while (nextUrl != null) {
            pageCount++
            Log.d(TAG, "RSS page $pageCount: $nextUrl")
            val xml = try {
                val req = Request.Builder().url(nextUrl).build()
                client.newCall(req).execute().use { it.body?.string() }
            } catch (e: Exception) {
                Log.e(TAG, "RSS fetch error", e); break
            } ?: break

            val parser = RssParser(xml)
            parser.parse()
            for (item in parser.items) {
                val tractate = item.tractate ?: continue
                val daf = item.daf ?: continue
                if (item.audioUrl.isEmpty()) continue
                index.getOrPut(tractate) { mutableMapOf() }.putIfAbsent(daf, item.audioUrl)
            }
            nextUrl = parser.nextPageUrl
        }

        // ── Phase 2: SoundCloud playlists (fill missing dafs) ─────────────
        Log.d(TAG, "Fetching ${tractatePlaylistIds.size} SoundCloud playlists in parallel")
        val playlistResults = coroutineScope {
            tractatePlaylistIds.map { (tractate, playlistId) ->
                async { fetchPlaylist(tractate, playlistId) }
            }.awaitAll()
        }

        for ((tractate, dafs) in playlistResults) {
            val existing = index.getOrPut(tractate) { mutableMapOf() }
            for ((daf, url) in dafs) {
                existing.putIfAbsent(daf, url) // don't overwrite RSS URLs
            }
        }

        _episodeIndex.value = index.mapValues { it.value.toMap() }
        saveToCache(index)
        prefs.edit().putLong(CACHE_TIMESTAMP_KEY, System.currentTimeMillis()).apply()
        Log.d(TAG, "fetchAll complete: ${_episodeIndex.value.values.sumOf { it.size }} total episodes")
        _isLoading.value = false
    }

    // ── SoundCloud playlist fetch ─────────────────────────────────────────

    private suspend fun fetchPlaylist(tractate: String, playlistId: Long): Pair<String, Map<Int, String>> {
        val dafs = mutableMapOf<Int, String>()
        val url = "https://api-v2.soundcloud.com/playlists/$playlistId?client_id=$SOUNDCLOUD_CLIENT_ID"
        val body = try {
            val req = Request.Builder().url(url).build()
            client.newCall(req).execute().use { it.body?.string() }
        } catch (e: Exception) {
            Log.e(TAG, "Playlist fetch error for $tractate", e)
            return tractate to dafs
        } ?: return tractate to dafs

        val json = try { JSONObject(body) } catch (e: Exception) { return tractate to dafs }
        val tracks = json.optJSONArray("tracks") ?: return tractate to dafs

        val fullTracks = mutableListOf<JSONObject>()
        val stubIds = mutableListOf<Long>()

        for (i in 0 until tracks.length()) {
            val track = tracks.getJSONObject(i)
            if (track.has("title")) fullTracks.add(track)
            else stubIds.add(track.optLong("id"))
        }

        // Batch-fetch stub tracks (SoundCloud only hydrates the first ~5 in a playlist)
        stubIds.chunked(50).forEach { batch ->
            val batchUrl = "https://api-v2.soundcloud.com/tracks" +
                    "?ids=${batch.joinToString(",")}&client_id=$SOUNDCLOUD_CLIENT_ID"
            try {
                val batchBody = client.newCall(Request.Builder().url(batchUrl).build())
                    .execute().use { it.body?.string() } ?: return@forEach
                val arr = JSONArray(batchBody)
                for (i in 0 until arr.length()) fullTracks.add(arr.getJSONObject(i))
            } catch (e: Exception) { /* skip batch */ }
        }

        for (track in fullTracks) {
            val title = track.optString("title")
            if (title.isEmpty()) continue
            val urn = track.optString("urn")
            if (urn.isEmpty()) continue
            val cleaned = title.replace(Regex("""\s*\(\d+\)\s*$"""), "").trim()
            val parts = cleaned.split(" ")
            if (parts.size < 2) continue
            val daf = parts.last().takeWhile { it.isDigit() }.toIntOrNull() ?: continue
            if (daf <= 0) continue
            val trackId = urn.split(":").lastOrNull()?.takeIf { it.isNotEmpty() } ?: continue
            dafs.putIfAbsent(daf, "soundcloud-track://$trackId")
        }

        return tractate to dafs
    }

    // ── Cache ─────────────────────────────────────────────────────────────

    private fun loadFromCache() {
        val file = cacheFile
        if (!file.exists()) return
        try {
            val root = JSONObject(file.readText())
            val index = mutableMapOf<String, MutableMap<Int, String>>()
            for (tractate in root.keys()) {
                // Migrate stale "Middos" key from before the rename to "Middot"
                val canonicalTractate = if (tractate == "Middos") "Middot" else tractate
                val dafObj = root.getJSONObject(tractate)
                val existing = index.getOrPut(canonicalTractate) { mutableMapOf() }
                for (key in dafObj.keys()) {
                    val dafNum = key.toIntOrNull() ?: continue
                    existing.putIfAbsent(dafNum, dafObj.getString(key))
                }
            }
            _episodeIndex.value = index.mapValues { it.value.toMap() }
            Log.d(TAG, "Loaded ${index.values.sumOf { it.size }} episodes from cache")
        } catch (e: Exception) {
            Log.e(TAG, "Cache load error", e)
        }
    }

    private fun saveToCache(index: Map<String, Map<Int, String>>) {
        try {
            val root = JSONObject()
            for ((tractate, dafs) in index) {
                val dafObj = JSONObject()
                for ((daf, url) in dafs) dafObj.put(daf.toString(), url)
                root.put(tractate, dafObj)
            }
            cacheFile.writeText(root.toString())
        } catch (e: Exception) {
            Log.e(TAG, "Cache save error", e)
        }
    }
}
