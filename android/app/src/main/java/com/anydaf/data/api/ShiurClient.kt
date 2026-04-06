package com.anydaf.data.api

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.net.URLEncoder

// MARK: - Data models

data class ShiurMicroSegment(
    val title: String,
    val timestamp: String   // "MM:SS"
) {
    val seconds: Double get() = parseShiurTimestamp(timestamp)
}

data class ShiurSegment(
    val title: String,
    val timestamp: String,  // "MM:SS"
    val microSegments: List<ShiurMicroSegment>
) {
    val seconds: Double get() = parseShiurTimestamp(timestamp)
}

private fun parseShiurTimestamp(ts: String): Double {
    val parts = ts.trim().split(":").mapNotNull { it.toDoubleOrNull() }
    return when (parts.size) {
        2 -> parts[0] * 60 + parts[1]
        3 -> parts[0] * 3600 + parts[1] * 60 + parts[2]
        else -> 0.0
    }
}

// MARK: - Client

object ShiurClient {

    private const val SUPABASE_URL = "https://zewdazoijdpakugfvnzt.supabase.co"
    private const val SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpld2Rhem9pamRwYWt1Z2Z2bnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzIwODYsImV4cCI6MjA5MDA0ODA4Nn0.HJxIG18vEpt-exzoQwRLeXiKLAinWfBl7gMORKjxIz8"

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val httpClient = OkHttpClient()

    private val _segments = MutableStateFlow<List<ShiurSegment>>(emptyList())
    val segments: StateFlow<List<ShiurSegment>> = _segments.asStateFlow()

    private val _currentSegmentIndex = MutableStateFlow(0)
    val currentSegmentIndex: StateFlow<Int> = _currentSegmentIndex.asStateFlow()

    /** Lecture rewrite text (pass 2) for the loaded daf, or null if not available. */
    private val _shiurRewrite = MutableStateFlow<String?>(null)
    val shiurRewrite: StateFlow<String?> = _shiurRewrite.asStateFlow()

    /** Lecture text with Sefaria sources inserted (pass 3), or null if not available. */
    private val _shiurFinal = MutableStateFlow<String?>(null)
    val shiurFinal: StateFlow<String?> = _shiurFinal.asStateFlow()

    private var loadedKey: String? = null   // "Tractate-daf" — avoids redundant fetches

    fun load(tractate: String, daf: Int) {
        val key = "$tractate-$daf"
        if (key == loadedKey) return
        _segments.value = emptyList()
        _currentSegmentIndex.value = 0
        _shiurRewrite.value = null
        _shiurFinal.value = null

        scope.launch {
            try {
                val encodedTractate = URLEncoder.encode(tractate, "UTF-8").replace("+", "%20")
                val url = "$SUPABASE_URL/rest/v1/shiur_content" +
                        "?tractate=eq.$encodedTractate" +
                        "&daf=eq.$daf" +
                        "&select=segmentation,rewrite,final"

                android.util.Log.d("ShiurClient", "Loading: $url")

                val request = Request.Builder()
                    .url(url)
                    .header("apikey", SUPABASE_ANON_KEY)
                    .header("Authorization", "Bearer $SUPABASE_ANON_KEY")
                    .build()

                val response = withContext(Dispatchers.IO) {
                    httpClient.newCall(request).execute()
                }
                val body = response.body?.string() ?: return@launch
                android.util.Log.d("ShiurClient", "Response ${response.code}: ${body.take(300)}")

                val rows = JSONArray(body)
                if (rows.length() == 0) {
                    android.util.Log.d("ShiurClient", "No rows returned for $tractate $daf")
                    return@launch
                }
                val row = rows.getJSONObject(0)

                // Parse segmentation JSON → ShiurSegment list
                val segJSON = row.optJSONObject("segmentation")
                if (segJSON != null) {
                    val macrosArr = segJSON.optJSONArray("macro_segments")
                    if (macrosArr != null) {
                        val parsed = (0 until macrosArr.length()).map { i ->
                            val macro = macrosArr.getJSONObject(i)
                            val microsArr = macro.optJSONArray("micro_segments")
                            val micros = if (microsArr != null) {
                                (0 until microsArr.length()).map { j ->
                                    val m = microsArr.getJSONObject(j)
                                    ShiurMicroSegment(
                                        title = m.optString("title"),
                                        timestamp = m.optString("timestamp")
                                    )
                                }
                            } else emptyList()
                            ShiurSegment(
                                title = macro.optString("title"),
                                timestamp = macro.optString("timestamp"),
                                microSegments = micros
                            )
                        }
                        _segments.value = parsed
                    }
                }

                _shiurRewrite.value = row.optString("rewrite").ifEmpty { null }
                _shiurFinal.value = row.optString("final").ifEmpty { null }
                loadedKey = key

            } catch (e: Exception) {
                android.util.Log.e("ShiurClient", "Failed to load $tractate $daf", e)
            }
        }
    }

    /** Update currentSegmentIndex based on the audio's current playback position. */
    fun updateCurrentSegment(currentTimeSecs: Float) {
        val segs = _segments.value
        if (segs.isEmpty()) return
        var idx = 0
        for (i in segs.indices) {
            if (currentTimeSecs >= segs[i].seconds) idx = i
        }
        if (idx != _currentSegmentIndex.value) _currentSegmentIndex.value = idx
    }

    /** Clear when navigating to a different daf. */
    fun reset() {
        _segments.value = emptyList()
        _currentSegmentIndex.value = 0
        _shiurRewrite.value = null
        _shiurFinal.value = null
        loadedKey = null
    }
}
