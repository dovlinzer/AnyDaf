package com.anydaf.data.api

import com.anydaf.model.QuizMode
import com.anydaf.model.QuizQuestion
import com.anydaf.model.StudyMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

// ── Supabase Configuration ──────────────────────────────────────────────────
// After creating your Supabase project, replace these two values with your own.
// Find them at: Project Dashboard → Settings → API
private const val SUPABASE_BASE_URL = "https://zewdazoijdpakugfvnzt.supabase.co/rest/v1/study_cache"
private const val SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpld2Rhem9pamRwYWt1Z2Z2bnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzIwODYsImV4cCI6MjA5MDA0ODA4Nn0.HJxIG18vEpt-exzoQwRLeXiKLAinWfBl7gMORKjxIz8"
// ───────────────────────────────────────────────────────────────────────────

/**
 * Shared read-through cache for Claude-generated study content, backed by Supabase.
 *
 * Cache key format: {tractate}_{daf}_{sectionIndex}_{studyMode}_{quizMode}
 * Example:          Berakhot_2_0_facts_multipleChoice
 *
 * - Cache reads return null on any failure; the caller falls back to Claude.
 * - Cache writes are fire-and-forget; failures are silently ignored.
 * - Write-once: if a key already exists the insert is ignored, preserving the
 *   first-generated content for all future users.
 *
 * Keys are identical to those produced by the iOS StudyCache, so the cache is
 * shared across both platforms.
 */
object StudyCache {

    data class CachedContent(val summary: String, val questions: List<QuizQuestion>, val shiurUsed: Boolean)

    private val client = OkHttpClient()
    private val JSON_MEDIA = "application/json".toMediaType()

    // MARK: - Fetch

    suspend fun fetch(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode
    ): CachedContent? = withContext(Dispatchers.IO) {
        val key = cacheKey(tractate, daf, sectionIndex, studyMode, quizMode)
        val url = "$SUPABASE_BASE_URL?key=eq.$key&select=summary,questions_json,shiur_used&limit=1"

        val request = Request.Builder()
            .url(url)
            .header("apikey", SUPABASE_ANON_KEY)
            .header("Authorization", "Bearer $SUPABASE_ANON_KEY")
            .build()

        try {
            val body = client.newCall(request).execute().use { it.body?.string() } ?: return@withContext null
            val array = JSONArray(body)
            if (array.length() == 0) return@withContext null
            val row = array.getJSONObject(0)
            val summary = row.getString("summary")
            val questionsJson = row.getString("questions_json")
            val shiurUsed = row.optBoolean("shiur_used", false)
            CachedContent(summary, deserializeQuestions(questionsJson), shiurUsed)
        } catch (e: Exception) {
            null
        }
    }

    // MARK: - Store

    suspend fun store(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode,
        summary: String, questions: List<QuizQuestion>,
        shiurUsed: Boolean
    ) = withContext(Dispatchers.IO) {
        val key = cacheKey(tractate, daf, sectionIndex, studyMode, quizMode)
        val questionsJson = serializeQuestions(questions) ?: return@withContext

        // shiurUsed=true: upsert to overwrite any existing non-shiur entry.
        // shiurUsed=false: write-once so we never downgrade a shiur-enriched entry.
        val url = if (shiurUsed) "$SUPABASE_BASE_URL?on_conflict=key" else SUPABASE_BASE_URL
        val preferHeader = if (shiurUsed) "resolution=merge-duplicates" else "resolution=ignore-duplicates"

        val body = JSONObject().apply {
            put("key", key)
            put("summary", summary)
            put("questions_json", questionsJson)
            put("shiur_used", shiurUsed)
        }.toString().toRequestBody(JSON_MEDIA)

        val request = Request.Builder()
            .url(url)
            .post(body)
            .header("apikey", SUPABASE_ANON_KEY)
            .header("Authorization", "Bearer $SUPABASE_ANON_KEY")
            .header("Content-Type", "application/json")
            .header("Prefer", preferHeader)
            .build()

        try {
            client.newCall(request).execute().close()
        } catch (e: Exception) {
            // Fire-and-forget: cache write failures are silently ignored
        }
    }

    // MARK: - Serialization

    private fun serializeQuestions(questions: List<QuizQuestion>): String? = try {
        val array = JSONArray()
        questions.forEach { q ->
            val obj = JSONObject()
            when (q.mode) {
                QuizMode.MULTIPLE_CHOICE -> {
                    obj.put("mode", "multipleChoice")
                    obj.put("question", q.question)
                    obj.put("choices", JSONArray(q.choices))
                    obj.put("correctIndex", q.correctIndex)
                }
                QuizMode.FLASHCARD -> {
                    obj.put("mode", "flashcard")
                    obj.put("question", q.question)
                    obj.put("answer", q.correctAnswer)
                }
                QuizMode.FILL_IN_BLANK -> {
                    obj.put("mode", "fillInBlank")
                    obj.put("question", q.question)
                    obj.put("answer", q.correctAnswer)
                }
                QuizMode.SHORT_ANSWER -> {
                    obj.put("mode", "shortAnswer")
                    obj.put("question", q.question)
                    obj.put("answer", q.correctAnswer)
                }
            }
            array.put(obj)
        }
        array.toString()
    } catch (e: Exception) { null }

    private fun deserializeQuestions(json: String): List<QuizQuestion> = try {
        val array = JSONArray(json)
        (0 until array.length()).mapNotNull { i ->
            val q = array.getJSONObject(i)
            val modeStr = q.getString("mode")
            val question = q.getString("question")
            when (modeStr) {
                "multipleChoice" -> {
                    val choicesArr = q.getJSONArray("choices")
                    val choices = (0 until choicesArr.length()).map { choicesArr.getString(it) }
                    QuizQuestion.multipleChoice(question, choices, q.getInt("correctIndex"))
                }
                "flashcard"   -> QuizQuestion.flashcard(question, q.getString("answer"))
                "fillInBlank" -> QuizQuestion.fillInBlank(question, q.getString("answer"))
                "shortAnswer" -> QuizQuestion.shortAnswer(question, q.getString("answer"))
                else          -> null
            }
        }
    } catch (e: Exception) { emptyList() }

    // MARK: - Cache Key

    private fun cacheKey(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode
    ): String {
        // studyMode and quizMode values match iOS rawValue conventions
        // so the cache is shared across platforms.
        val modeStr = if (studyMode == StudyMode.FACTS) "facts" else "conceptual"
        val quizModeStr = when (quizMode) {
            QuizMode.MULTIPLE_CHOICE -> "multipleChoice"
            QuizMode.FLASHCARD       -> "flashcard"
            QuizMode.FILL_IN_BLANK   -> "fillInBlank"
            QuizMode.SHORT_ANSWER    -> "shortAnswer"
        }
        val safeTractate = tractate.replace(" ", "_")
        return "${safeTractate}_${daf}_${sectionIndex}_${modeStr}_${quizModeStr}"
    }
}
