package com.anydaf.data.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.temporal.WeekFields
import java.util.Locale

data class Dedication(
    val date: LocalDate,
    val dedicatedBy: String,
    val honoreeName: String,   // may be empty
    val period: String,        // "today" | "week" | "month"
    val preposition: String,   // "in honor of" | "in memory of" | "on the occasion of" | ""
    val occasion: String,      // supplemental text, may be empty
    val displayText: String?,  // full override
    val photoURL: String?      // optional photo URL
) {
    val periodTitle: String get() = when (period) {
        "week"  -> "This Week's Learning"
        "month" -> "This Month's Learning"
        else    -> "Today's Learning"
    }

    val formattedMessage: String get() {
        displayText?.takeIf { it.isNotBlank() }?.let { return it }
        val periodPhrase = when (period) {
            "week"  -> "This week's learning"
            "month" -> "This month's learning"
            else    -> "Today's learning"
        }
        val parts = mutableListOf("$periodPhrase with AnyDaf is dedicated by $dedicatedBy")
        if (preposition.isNotBlank()) parts.add(preposition)
        if (honoreeName.isNotBlank()) parts.add(honoreeName)
        if (occasion.isNotBlank())    parts.add(occasion)
        return parts.joinToString(" ") + "."
    }

    fun isActiveToday(today: LocalDate): Boolean = when (period) {
        "week" -> {
            val weekFields = WeekFields.of(Locale.getDefault())
            date.get(weekFields.weekOfWeekBasedYear()) == today.get(weekFields.weekOfWeekBasedYear()) &&
                date.year == today.year
        }
        "month" -> date.month == today.month && date.year == today.year
        else    -> date == today
    }
}

object DedicationService {
    private const val SUPABASE_URL = "https://zewdazoijdpakugfvnzt.supabase.co"
    private val ANON_KEY get() = com.anydaf.BuildConfig.SUPABASE_ANON_KEY

    // Returns nil if nothing is active — caller should NOT mark the date as shown.
    suspend fun fetch(): Dedication? = withContext(Dispatchers.IO) {
        try {
            val today = LocalDate.now()
            val startDate = today.minusDays(31)
            val urlStr = "$SUPABASE_URL/rest/v1/dedications" +
                "?date=gte.$startDate" +
                "&date=lte.$today" +
                "&status=eq.approved" +
                "&for_anydaf=eq.true" +
                "&select=date,dedicated_by,honoree_name,period,preposition,occasion,display_text,photo_url" +
                "&order=date.desc,id.desc" +
                "&limit=10"
            val connection = URL(urlStr).openConnection() as HttpURLConnection
            connection.setRequestProperty("apikey", ANON_KEY)
            connection.setRequestProperty("Authorization", "Bearer $ANON_KEY")
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            if (connection.responseCode != 200) return@withContext null
            val body = connection.inputStream.bufferedReader().readText()
            JSONArray(body)
                .let { arr -> (0 until arr.length()).mapNotNull { decode(arr.getJSONObject(it)) } }
                .filter { it.isActiveToday(today) }
                .sortedByDescending { periodPriority(it.period) }
                .firstOrNull()
        } catch (_: Exception) { null }
    }

    private fun decode(row: JSONObject): Dedication? {
        val dateStr = row.optString("date").takeIf { it.isNotBlank() } ?: return null
        val dedicatedBy = row.optString("dedicated_by").takeIf { it.isNotBlank() } ?: return null
        return Dedication(
            date        = LocalDate.parse(dateStr),
            dedicatedBy = dedicatedBy,
            honoreeName = row.optString("honoree_name"),
            period      = row.optString("period").ifBlank { "today" },
            preposition = row.optString("preposition"),
            occasion    = row.optString("occasion"),
            displayText = row.optString("display_text").takeIf { it.isNotBlank() },
            photoURL    = row.optString("photo_url").takeIf { it.isNotBlank() }
        )
    }

    private fun periodPriority(period: String): Int = when (period) {
        "today" -> 3
        "week"  -> 2
        else    -> 1
    }
}
