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
    /** Short label (≤25 chars) for audio chapter markers; falls back to title if absent in JSON. */
    val displayTitle: String,
    val timestamp: String   // "MM:SS"
) {
    val seconds: Double get() = parseShiurTimestamp(timestamp)
}

data class ShiurSegment(
    val title: String,
    /** Short label (≤25 chars) for audio navigation pills; falls back to title if absent in JSON. */
    val displayTitle: String,
    val timestamp: String,  // "MM:SS"
    val microSegments: List<ShiurMicroSegment>,
    /** 0-based index into the flat Sefaria segment array (amud A + B concatenated). Null if not yet computed. */
    val sefariaIndex: Int? = null,
    /** True if sefariaIndex is a genuine blockquote match; false if carried-forward from a
     *  previous match (e.g. shiur-discussion segment with no quote of its own); null if not
     *  yet computed for this daf. */
    val matched: Boolean? = null
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

    private const val EDGE_FUNCTION_URL = "https://zewdazoijdpakugfvnzt.supabase.co/functions/v1/get-shiur"
    private val APP_SECRET get() = com.anydaf.BuildConfig.APP_SECRET

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val httpClient = OkHttpClient()

    private val _segments = MutableStateFlow<List<ShiurSegment>>(emptyList())
    val segments: StateFlow<List<ShiurSegment>> = _segments.asStateFlow()

    private val _currentSegmentIndex = MutableStateFlow(0)
    val currentSegmentIndex: StateFlow<Int> = _currentSegmentIndex.asStateFlow()

    /** Segments for the audio episode currently playing — frozen at play-start, independent of selected daf. */
    private val _audioSegments = MutableStateFlow<List<ShiurSegment>>(emptyList())
    val audioSegments: StateFlow<List<ShiurSegment>> = _audioSegments.asStateFlow()

    /** Position within the audio episode — driven by updateCurrentSegment, independent of currentSegmentIndex. */
    private val _audioCurrentSegmentIndex = MutableStateFlow(0)
    val audioCurrentSegmentIndex: StateFlow<Int> = _audioCurrentSegmentIndex.asStateFlow()

    /** Segment index where amud B begins, or null if not detected for this daf. */
    private val _amudBSegmentIndex = MutableStateFlow<Int?>(null)
    val amudBSegmentIndex: StateFlow<Int?> = _amudBSegmentIndex.asStateFlow()

    /** Seconds into the audio where amud B begins, or null if not detected. */
    private val _amudBSeconds = MutableStateFlow<Double?>(null)
    val amudBSeconds: StateFlow<Double?> = _amudBSeconds.asStateFlow()

    /** Display title of the ### micro-segment where amud B begins, or null if at a ## boundary. */
    private val _amudBMicroTitle = MutableStateFlow<String?>(null)
    val amudBMicroTitle: StateFlow<String?> = _amudBMicroTitle.asStateFlow()

    /** 0-based Sefaria flat-array index where amud B begins (= amud A segment count). Null if not yet computed. */
    private val _amudBSefariaIndex = MutableStateFlow<Int?>(null)
    val amudBSefariaIndex: StateFlow<Int?> = _amudBSefariaIndex.asStateFlow()

    /** Lecture rewrite text (pass 2) for the loaded daf, or null if not available. */
    private val _shiurRewrite = MutableStateFlow<String?>(null)
    val shiurRewrite: StateFlow<String?> = _shiurRewrite.asStateFlow()

    /** Lecture text with Sefaria sources inserted (pass 3), or null if not available. */
    private val _shiurFinal = MutableStateFlow<String?>(null)
    val shiurFinal: StateFlow<String?> = _shiurFinal.asStateFlow()

    private var loadedKey: String? = null   // "Tractate-daf_float" — avoids redundant fetches

    fun load(tractate: String, daf: Double) {
        val key = "$tractate-$daf"
        if (key == loadedKey) return
        _segments.value = emptyList()
        _currentSegmentIndex.value = 0
        _amudBSegmentIndex.value = null
        _amudBSeconds.value = null
        _amudBMicroTitle.value = null
        _amudBSefariaIndex.value = null
        _shiurRewrite.value = null
        _shiurFinal.value = null

        scope.launch {
            try {
                val encodedTractate = URLEncoder.encode(tractate, "UTF-8").replace("+", "%20")
                val url = "$EDGE_FUNCTION_URL?tractate=$encodedTractate&daf=$daf"

                android.util.Log.d("ShiurClient", "Loading: $url")

                val request = Request.Builder()
                    .url(url)
                    .header("x-app-secret", APP_SECRET)
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
                                        displayTitle = m.optString("display_title").ifEmpty { m.optString("title") },
                                        timestamp = m.optString("timestamp")
                                    )
                                }
                            } else emptyList()
                            val sefariaIdx = macro.optInt("sefaria_index", -1).takeIf { it >= 0 }
                            val matchedFlag = if (macro.has("matched") && !macro.isNull("matched"))
                                macro.getBoolean("matched") else null
                            ShiurSegment(
                                title = macro.optString("title"),
                                displayTitle = macro.optString("display_title").ifEmpty { macro.optString("title") },
                                timestamp = macro.optString("timestamp"),
                                microSegments = micros,
                                sefariaIndex = sefariaIdx,
                                matched = matchedFlag
                            )
                        }
                        _segments.value = parsed

                        val bIdx = segJSON.optInt("amud_b_segment_index", -1)
                        if (bIdx >= 0) {
                            _amudBSegmentIndex.value = bIdx
                            val bTs = segJSON.optString("amud_b_timestamp")
                            _amudBSeconds.value = if (bTs.isNotEmpty()) parseShiurTimestamp(bTs) else null
                            val bMicro = segJSON.optString("amud_b_micro_title")
                            _amudBMicroTitle.value = bMicro.ifEmpty { null }
                        }
                        val bSefaria = segJSON.optInt("amud_b_sefaria_index", -1).takeIf { it >= 0 }
                        _amudBSefariaIndex.value = bSefaria
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

    /** Jump the shiur-text view to a segment (content daf only — does not affect audio). */
    fun jumpToSegment(index: Int) {
        _currentSegmentIndex.value = index.coerceIn(0, (_segments.value.size - 1).coerceAtLeast(0))
    }

    /** Snapshot the current content segments as the audio segments; called when audio starts. */
    fun snapshotAudioSegments() {
        _audioSegments.value = _segments.value
        _audioCurrentSegmentIndex.value = _currentSegmentIndex.value
    }

    /** Drops the audio snapshot without touching the selected daf's own shiur state. Used when
     *  playback starts on something with no shiur segments at all (a Resources-tab episode), so
     *  the chapter strip stays hidden rather than showing whatever daf happened to be selected. */
    fun clearAudioSegments() {
        _audioSegments.value = emptyList()
        _audioCurrentSegmentIndex.value = 0
    }

    /** Jump the audio chapter strip to a segment (audio daf only — does not affect shiur text). */
    fun jumpToAudioSegment(index: Int) {
        _audioCurrentSegmentIndex.value = index.coerceIn(0, (_audioSegments.value.size - 1).coerceAtLeast(0))
    }

    /** Update audioCurrentSegmentIndex based on audio playback position — never touches currentSegmentIndex. */
    fun updateCurrentSegment(currentTimeSecs: Float) {
        val segs = _audioSegments.value
        if (segs.isEmpty()) return
        var idx = 0
        for (i in segs.indices) {
            if (currentTimeSecs >= segs[i].seconds) idx = i
        }
        if (idx != _audioCurrentSegmentIndex.value) _audioCurrentSegmentIndex.value = idx
    }

    /**
     * The shiur segment that governs a given Sefaria position — the last genuinely-matched
     * segment (real blockquote match, not a carried-forward placeholder like "Introduction")
     * whose own sefariaIndex is <= [position]. Used as the "nothing specific was navigated to
     * yet" fallback (fresh section load, Prev/Next-section, a newly-selected daf) — in that
     * state the user is looking at the TOP of the section, so this answers "which segment
     * governs this exact starting position", not "which segment anchors somewhere within the
     * whole section". Callers that DO have a specific tapped/synced target (StudySessionViewModel
     * .activeSefariaIndex) should prefer that directly instead of calling this, as long as it
     * falls within the current section's range — see TextNavigationStrip and ContentScreen.kt's
     * Text<->Shiur mode-switch sync.
     *
     * A placeholder's sefariaIndex is just inherited from whatever it followed, not its own
     * anchor, so it must never outrank a real match. Segments whose `matched` flag hasn't been
     * computed yet (null) are treated as eligible, same as before this field existed, so dafs
     * not yet re-processed don't regress.
     *
     * Mirrors owningShiurSegmentIndex(at:) in iOS's StudyModeView.swift / ContentView.swift.
     */
    fun owningSegmentIndex(position: Int, segments: List<ShiurSegment>): Int? {
        var best: Int? = null
        segments.forEachIndexed { i, seg ->
            val sIdx = seg.sefariaIndex
            if (sIdx != null && sIdx <= position && seg.matched != false) best = i
        }
        return best
    }

    /** Clear all state when stopping audio or navigating to a new daf. */
    fun reset() {
        _segments.value = emptyList()
        _currentSegmentIndex.value = 0
        _amudBSegmentIndex.value = null
        _amudBSeconds.value = null
        _amudBMicroTitle.value = null
        _amudBSefariaIndex.value = null
        _shiurRewrite.value = null
        _shiurFinal.value = null
        _audioSegments.value = emptyList()
        _audioCurrentSegmentIndex.value = 0
        loadedKey = null
    }
}
