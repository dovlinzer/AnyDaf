package com.anydaf.data.api

import com.anydaf.model.allTractates
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject

data class DafYomi(
    val tractateName: String,
    val tractateIndex: Int,
    val daf: Int
)

sealed class DafYomiError : Exception() {
    class NetworkError(cause: Throwable) : DafYomiError()
    object NotFound : DafYomiError()
    object ParseError : DafYomiError()
    class UnknownTractate(val name: String) : DafYomiError()
}

object DafYomiService {

    private val client = OkHttpClient.Builder().build()

    private val sefariaToAnyDaf = mapOf(
        "Eruvin"  to "Eiruvin",
        "Taanit"  to "Ta\u2019anit",
        "Chullin" to "Hullin",
        "Middot"  to "Middos",
    )

    suspend fun fetchToday(): DafYomi = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("https://www.sefaria.org/api/calendars")
            .build()

        val response = try {
            client.newCall(request).execute()
        } catch (e: Exception) {
            throw DafYomiError.NetworkError(e)
        }

        val body = response.body?.string() ?: throw DafYomiError.ParseError

        val json = try { JSONObject(body) } catch (e: Exception) { throw DafYomiError.ParseError }
        val items = json.optJSONArray("calendar_items") ?: throw DafYomiError.ParseError

        // Find the Daf Yomi entry
        var dafYomiItem: JSONObject? = null
        for (i in 0 until items.length()) {
            val item = items.getJSONObject(i)
            val title = item.optJSONObject("title")
            if (title?.optString("en") == "Daf Yomi") {
                dafYomiItem = item
                break
            }
        }
        dafYomiItem ?: throw DafYomiError.NotFound

        val displayValue = dafYomiItem.optJSONObject("displayValue") ?: throw DafYomiError.ParseError
        val displayEn = displayValue.optString("en").ifEmpty { throw DafYomiError.ParseError }

        val parts = displayEn.split(" ")
        if (parts.size < 2) throw DafYomiError.ParseError
        val dafNum = parts.last().toIntOrNull() ?: throw DafYomiError.ParseError

        val sefariaName = parts.dropLast(1).joinToString(" ")
        val anyDafName = sefariaToAnyDaf[sefariaName] ?: sefariaName

        val index = allTractates.indexOfFirst { it.name == anyDafName }
        if (index < 0) throw DafYomiError.UnknownTractate(anyDafName)

        DafYomi(tractateName = anyDafName, tractateIndex = index, daf = dafNum)
    }
}
