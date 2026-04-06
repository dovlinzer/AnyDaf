package com.anydaf.data.api

import com.anydaf.BuildConfig
import com.anydaf.model.GradeResult
import com.anydaf.model.QuizMode
import com.anydaf.model.QuizQuestion
import com.anydaf.model.StudyMode
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

sealed class ClaudeError : Exception() {
    class NetworkError(cause: Throwable) : ClaudeError()
    class ApiError(override val message: String) : ClaudeError()
    object ParsingError : ClaudeError()
    object RateLimited : ClaudeError()
}

object ClaudeClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    private val appSecret: String get() = BuildConfig.APP_SECRET
    private const val MODEL = "claude-haiku-4-5-20251001"
    private const val API_URL = "https://zewdazoijdpakugfvnzt.supabase.co/functions/v1/claude-proxy"

    suspend fun generateStudyContent(
        sectionTitle: String,
        sectionText: String,
        tractate: String,
        daf: Int,
        mode: StudyMode,
        quizMode: QuizMode,
        shiurContext: String? = null
    ): Pair<String, List<QuizQuestion>> {
        val prompt = when {
            mode == StudyMode.FACTS && quizMode == QuizMode.MULTIPLE_CHOICE ->
                factsPrompt(sectionTitle, sectionText, tractate, daf, shiurContext)
            mode == StudyMode.CONCEPTUAL && quizMode == QuizMode.MULTIPLE_CHOICE ->
                conceptualPrompt(sectionTitle, sectionText, tractate, daf, shiurContext)
            quizMode == QuizMode.FLASHCARD ->
                flashcardPrompt(sectionTitle, sectionText, tractate, daf, mode, shiurContext)
            quizMode == QuizMode.FILL_IN_BLANK ->
                fillInBlankPrompt(sectionTitle, sectionText, tractate, daf, mode, shiurContext)
            else ->
                shortAnswerPrompt(sectionTitle, sectionText, tractate, daf, mode, shiurContext)
        }

        val responseText = callClaude(prompt, maxTokens = 1500)

        return when (quizMode) {
            QuizMode.MULTIPLE_CHOICE -> parseMcContent(responseText)
            QuizMode.FLASHCARD -> parseQaContent(responseText, QuizMode.FLASHCARD)
            QuizMode.FILL_IN_BLANK -> parseQaContent(responseText, QuizMode.FILL_IN_BLANK)
            QuizMode.SHORT_ANSWER -> parseQaContent(responseText, QuizMode.SHORT_ANSWER)
        }
    }

    suspend fun gradeAnswer(
        question: String,
        correctAnswer: String,
        userAnswer: String,
        mode: QuizMode = QuizMode.FILL_IN_BLANK
    ): GradeResult {
        val prompt = if (mode == QuizMode.SHORT_ANSWER) {
            shortAnswerGradingPrompt(question, correctAnswer, userAnswer)
        } else {
            gradingPrompt(question, correctAnswer, userAnswer)
        }
        val text = callClaude(prompt, maxTokens = 250)
        return parseGradeResult(text, correctAnswer)
    }

    // MARK: - Internal API call

    private suspend fun callClaude(prompt: String, maxTokens: Int): String {
        val requestBody = JSONObject().apply {
            put("model", MODEL)
            put("max_tokens", maxTokens)
            put("messages", JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "user")
                    put("content", prompt)
                })
            })
        }.toString()

        val request = Request.Builder()
            .url(API_URL)
            .post(requestBody.toRequestBody("application/json".toMediaType()))
            .header("x-app-secret", appSecret)
            .header("content-type", "application/json")
            .build()

        val response = try {
            kotlinx.coroutines.Dispatchers.IO.run {
                client.newCall(request).execute()
            }
        } catch (e: Exception) {
            throw ClaudeError.NetworkError(e)
        }

        if (response.code == 429) throw ClaudeError.RateLimited
        if (response.code != 200) {
            val body = response.body?.string() ?: "unknown"
            throw ClaudeError.ApiError("HTTP ${response.code}: $body")
        }

        val body = response.body?.string() ?: throw ClaudeError.ParsingError

        return try {
            val json = JSONObject(body)
            val content = json.getJSONArray("content")
            content.getJSONObject(0).getString("text")
        } catch (e: Exception) {
            throw ClaudeError.ParsingError
        }
    }

    // MARK: - Prompts

    /** Appends the lecturer's explanation block when shiurContext is available. */
    private fun shiurBlock(shiurContext: String?): String {
        if (shiurContext.isNullOrEmpty()) return ""
        return "\n\nLECTURER'S EXPLANATION (full daf — focus on the section above):\n$shiurContext"
    }

    private fun factsPrompt(title: String, text: String, tractate: String, daf: Int,
                             shiurContext: String?): String {
        val questionScope = "Questions may draw from any detail in the provided text, not just what appears in the summary."
        val contextNote = if (shiurContext != null) " A lecturer's explanation of the full daf follows the text — use the relevant portion to enrich your summary." else ""
        return """
            You are a Talmud study assistant. Below is the English translation of the $title section from $tractate $daf.$contextNote

            TEXT:
            $text${shiurBlock(shiurContext)}

            Please provide:
            1. A clear summary (3-5 sentences) covering the key topics, rulings, and conclusions in this section. Write for someone who wants to understand the main facts and outcomes.

            2. Exactly 3 multiple choice questions testing comprehension of this section. $questionScope Each question should have exactly 4 options labeled A, B, C, D, with exactly one correct answer.

            Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
            {"summary":"Your summary here...","questions":[{"question":"Question text?","choices":["A) ...","B) ...","C) ...","D) ..."],"correctIndex":0}]}
        """.trimIndent()
    }

    private fun conceptualPrompt(title: String, text: String, tractate: String, daf: Int,
                                  shiurContext: String?): String {
        val questionScope = "Questions may draw from any reasoning or detail in the provided text, not just what appears in the summary."
        val contextNote = if (shiurContext != null) " A lecturer's explanation of the full daf follows the text — use the relevant portion to enrich your summary of the reasoning." else ""
        return """
            You are a Talmud study assistant. Below is the English translation of the $title section from $tractate $daf.$contextNote

            TEXT:
            $text${shiurBlock(shiurContext)}

            Please provide:
            1. A summary (3-5 sentences) focused on the REASONING and DEBATE in this section: What question or problem is being discussed? Who holds what position and what is the logic behind each view? How is the debate resolved, and why? Prioritize the flow of argumentation over listing facts.

            2. Exactly 3 multiple choice questions that test understanding of the reasoning and logic in this section. $questionScope Frame questions at the conceptual level: WHY was one position accepted over another? WHAT logical principle underlies the resolution? HOW do the two views differ in their reasoning? WHAT follows from the conclusion? Each question should have exactly 4 options labeled A, B, C, D, with exactly one correct answer.

            Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
            {"summary":"Your summary here...","questions":[{"question":"Question text?","choices":["A) ...","B) ...","C) ...","D) ..."],"correctIndex":0}]}
        """.trimIndent()
    }

    private fun flashcardPrompt(title: String, text: String, tractate: String, daf: Int,
                                 mode: StudyMode, shiurContext: String?): String {
        val focus = if (mode == StudyMode.FACTS) "facts, rulings, names, and key terms"
        else "reasoning, debates, logical principles, and how conclusions are reached"
        val source = "drawn from anywhere in the provided text."
        val contextNote = if (shiurContext != null) " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." else ""
        return """
            You are a Talmud study assistant. Below is the English translation of the $title section from $tractate $daf.$contextNote

            TEXT:
            $text${shiurBlock(shiurContext)}

            Please provide:
            1. A clear summary (3-5 sentences) focusing on the $focus.

            2. Exactly 3 flashcard-style Q&A pairs $source Each question should have a concise, specific answer (one phrase or sentence).

            Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
            {"summary":"...","questions":[{"question":"...","answer":"..."}]}
        """.trimIndent()
    }

    private fun fillInBlankPrompt(title: String, text: String, tractate: String, daf: Int,
                                   mode: StudyMode, shiurContext: String?): String {
        val focus = if (mode == StudyMode.FACTS) "facts, rulings, names, and key terms"
        else "reasoning, debates, logical principles, and how conclusions are reached"
        val source = "drawn from anywhere in the provided text."
        val contextNote = if (shiurContext != null) " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." else ""
        return """
            You are a Talmud study assistant. Below is the English translation of the $title section from $tractate $daf.$contextNote

            TEXT:
            $text${shiurBlock(shiurContext)}

            Please provide:
            1. A clear summary (3-5 sentences) focusing on the $focus.

            2. Exactly 3 fill-in-the-blank questions $source Each question is a sentence with one key term or phrase replaced by a blank (shown as _____). Provide the exact word or phrase that fills the blank as the answer. Keep answers short (1-5 words).

            Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
            {"summary":"...","questions":[{"question":"The _____ ruled that...","answer":"rabbi's name"}]}
        """.trimIndent()
    }

    private fun shortAnswerPrompt(title: String, text: String, tractate: String, daf: Int,
                                   mode: StudyMode, shiurContext: String?): String {
        val focus = if (mode == StudyMode.FACTS) "facts, rulings, names, and key terms"
        else "reasoning, debates, logical principles, and how conclusions are reached"
        val source = "drawn from anywhere in the provided text."
        val contextNote = if (shiurContext != null) " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." else ""
        return """
            You are a Talmud study assistant. Below is the English translation of the $title section from $tractate $daf.$contextNote

            TEXT:
            $text${shiurBlock(shiurContext)}

            Please provide:
            1. A clear summary (3-5 sentences) focusing on the $focus.

            2. Exactly 3 short-answer questions $source Each question should require a 1-2 sentence answer that demonstrates understanding — not just recall of a single word. The model answer should be concise but complete.

            Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
            {"summary":"...","questions":[{"question":"...","answer":"..."}]}
        """.trimIndent()
    }

    private fun gradingPrompt(question: String, correctAnswer: String, userAnswer: String) = """
        You are grading a Talmud study fill-in-the-blank answer. Be VERY lenient with spelling, capitalization, and transliteration of Hebrew/Aramaic names and terms. Accept synonyms, reasonable paraphrases, plural/singular variations, and common alternate spellings as correct. For example: "Rav" and "Rabbi", "Shmuel" and "Samuel" and "Shemuel", "halacha" and "halakha", etc.

        Question: $question
        Correct answer: $correctAnswer
        Your answer: $userAnswer

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"correct":true,"feedback":"Brief explanation (one concise sentence)."}

        Set "correct" to true if the user's answer is essentially right even if not worded exactly like the correct answer. Set it to false only if the answer is clearly wrong or unrelated.
    """.trimIndent()

    private fun shortAnswerGradingPrompt(question: String, correctAnswer: String, userAnswer: String) = """
        You are grading a Talmud study short-answer question. Be lenient: accept paraphrases, synonyms, and alternate formulations. The user does not need to match the model answer word-for-word — they just need to demonstrate that they understood the key idea. Also be lenient with spelling and transliteration of Hebrew/Aramaic names and terms.

        Question: $question
        Model answer: $correctAnswer
        Your answer: $userAnswer

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"correct":true,"feedback":"Brief explanation (one concise sentence)."}

        Set "correct" to true if the user's answer captures the essential idea, even if incomplete or differently worded. Set it to false only if the answer is clearly wrong, irrelevant, or missing the key concept entirely.
    """.trimIndent()

    // MARK: - Parsing

    private fun cleanJson(text: String): String =
        text.replace("```json", "").replace("```", "").trim()

    private fun parseMcContent(text: String): Pair<String, List<QuizQuestion>> {
        val cleaned = cleanJson(text)
        val json = try { JSONObject(cleaned) } catch (e: Exception) { throw ClaudeError.ParsingError }
        val summary = json.optString("summary").ifEmpty { throw ClaudeError.ParsingError }
        val questionsArray = json.optJSONArray("questions") ?: throw ClaudeError.ParsingError

        val questions = (0 until questionsArray.length()).mapNotNull { i ->
            val q = questionsArray.getJSONObject(i)
            val question = q.optString("question").ifEmpty { return@mapNotNull null }
            val choicesArray = q.optJSONArray("choices") ?: return@mapNotNull null
            val correctIndex = q.optInt("correctIndex", -1)
            if (choicesArray.length() != 4 || correctIndex !in 0..3) return@mapNotNull null
            val choices = (0 until choicesArray.length()).map { choicesArray.getString(it) }
            val labels = listOf("A) ", "B) ", "C) ", "D) ")
            val stripped = choices.map { c -> labels.firstOrNull { c.startsWith(it) }?.let { c.removePrefix(it) } ?: c }
            val correctBareText = stripped[correctIndex]
            val shuffledBare = stripped.shuffled()
            val newCorrectIndex = shuffledBare.indexOf(correctBareText)
            val relabeled = labels.zip(shuffledBare).map { (label, text) -> label + text }
            QuizQuestion.multipleChoice(question, relabeled, newCorrectIndex)
        }
        return summary to questions
    }

    private fun parseQaContent(text: String, quizMode: QuizMode): Pair<String, List<QuizQuestion>> {
        val cleaned = cleanJson(text)
        val json = try { JSONObject(cleaned) } catch (e: Exception) { throw ClaudeError.ParsingError }
        val summary = json.optString("summary").ifEmpty { throw ClaudeError.ParsingError }
        val questionsArray = json.optJSONArray("questions") ?: throw ClaudeError.ParsingError

        val questions = (0 until questionsArray.length()).mapNotNull { i ->
            val q = questionsArray.getJSONObject(i)
            val question = q.optString("question").ifEmpty { return@mapNotNull null }
            val answer = q.optString("answer").ifEmpty { return@mapNotNull null }
            when (quizMode) {
                QuizMode.FLASHCARD -> QuizQuestion.flashcard(question, answer)
                QuizMode.FILL_IN_BLANK -> QuizQuestion.fillInBlank(question, answer)
                QuizMode.SHORT_ANSWER -> QuizQuestion.shortAnswer(question, answer)
                QuizMode.MULTIPLE_CHOICE -> null
            }
        }
        return summary to questions
    }

    private fun parseGradeResult(text: String, correctAnswer: String): GradeResult {
        val cleaned = cleanJson(text)
        return try {
            val json = JSONObject(cleaned)
            val correct = json.getBoolean("correct")
            val feedback = json.getString("feedback")
            GradeResult(correct, feedback)
        } catch (e: Exception) {
            GradeResult(false, "Could not grade. The answer was: $correctAnswer")
        }
    }
}

// Extension to run OkHttp synchronously on IO dispatcher
private suspend fun kotlinx.coroutines.CoroutineDispatcher.run(block: () -> okhttp3.Response): okhttp3.Response =
    kotlinx.coroutines.withContext(this) { block() }
