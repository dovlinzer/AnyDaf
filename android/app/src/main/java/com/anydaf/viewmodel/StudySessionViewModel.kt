package com.anydaf.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.data.api.ClaudeClient
import com.anydaf.data.api.ClaudeError
import com.anydaf.data.api.SefariaClient
import com.anydaf.data.api.ShiurClient
import com.anydaf.data.api.StudyCache
import com.anydaf.model.QuizMode
import com.anydaf.model.StudyMode
import com.anydaf.model.StudyScope
import com.anydaf.model.StudySession
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class StudySessionViewModel : ViewModel() {

    private val _session = MutableStateFlow<StudySession?>(null)
    val session: StateFlow<StudySession?> = _session.asStateFlow()

    private val _isLoadingText = MutableStateFlow(false)
    val isLoadingText: StateFlow<Boolean> = _isLoadingText.asStateFlow()

    private val _isLoadingStudyContent = MutableStateFlow(false)
    val isLoadingStudyContent: StateFlow<Boolean> = _isLoadingStudyContent.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _isRateLimited = MutableStateFlow(false)
    val isRateLimited: StateFlow<Boolean> = _isRateLimited.asStateFlow()

    private val _rateLimitCountdown = MutableStateFlow(0)
    val rateLimitCountdown: StateFlow<Int> = _rateLimitCountdown.asStateFlow()

    var studyMode: StudyMode = StudyMode.FACTS
    var quizMode: QuizMode = QuizMode.MULTIPLE_CHOICE

    private val loadingIndices = mutableSetOf<Int>()

    // MARK: - Session lifecycle

    fun startSession(tractate: String, daf: Int, mode: StudyMode, quizMode: QuizMode, startAtLastSection: Boolean = false) {
        studyMode = mode
        this.quizMode = quizMode
        loadingIndices.clear()
        _isLoadingText.value = true
        _error.value = null

        viewModelScope.launch {
            try {
                // Fetch all amudim + adjacent context + Hebrew in parallel
                val amudADeferred = async { SefariaClient.fetchText(tractate, daf, "a") }
                val amudBDeferred = async { SefariaClient.fetchText(tractate, daf, "b") }
                val prevCtxDeferred = async { fetchAdjacentContext(tractate, daf - 1, "b", fromEnd = true) }
                val nextCtxDeferred = async { fetchAdjacentContext(tractate, daf + 1, "a", fromEnd = false) }
                val hebrewADeferred = async { runCatching { SefariaClient.fetchText(tractate, daf, "a", "he") }.getOrNull() }
                val hebrewBDeferred = async { runCatching { SefariaClient.fetchText(tractate, daf, "b", "he") }.getOrNull() }

                val segsA = amudADeferred.await()
                val segsB = amudBDeferred.await()
                val prevContext = prevCtxDeferred.await()
                val nextContext = nextCtxDeferred.await()
                val hebrewA = hebrewADeferred.await()
                val hebrewB = hebrewBDeferred.await()

                val sectionsA = SefariaClient.parseSections(segsA, hebrewA)
                val sectionsB = SefariaClient.parseSections(segsB, hebrewB)
                val combined = sectionsA + sectionsB
                val total = combined.size
                val numbered = combined.mapIndexed { i, s -> s.copy(title = "Section ${i + 1}/$total") }

                _session.value = StudySession(
                    tractate = tractate,
                    daf = daf,
                    scope = StudyScope.FULL_DAF,
                    sections = numbered,
                    currentSectionIndex = if (startAtLastSection) maxOf(0, numbered.size - 1) else 0,
                    amudBSectionIndex = sectionsA.size,
                    precedingContext = prevContext,
                    followingContext = if (SefariaClient.endsInMidSentence(segsB)) nextContext else null
                )

                _isLoadingText.value = false
                prefetchAllSections()

            } catch (e: Exception) {
                _error.value = e.message ?: "Failed to load text"
                _isLoadingText.value = false
            }
        }
    }

    private fun prefetchAllSections() {
        val count = _session.value?.sections?.size ?: 0
        for (idx in 0 until minOf(2, count)) {
            viewModelScope.launch { prefetchSection(idx) }
        }
    }

    private suspend fun fetchAdjacentContext(tractate: String, daf: Int, amud: String, fromEnd: Boolean): String? {
        if (daf <= 0) return null
        val segs = runCatching { SefariaClient.fetchText(tractate, daf, amud) }.getOrNull()
            ?.takeIf { it.isNotEmpty() } ?: return null

        return if (fromEnd) {
            val joined = SefariaClient.stripHtml(segs.joinToString(" ")).trim()
            val termIdx = SefariaClient.lastSentenceTerminal(joined) ?: return null
            val fragment = joined.substring(termIdx + 1).trim()
            if (fragment.any { it.isLetterOrDigit() }) fragment else null
        } else {
            val plain = SefariaClient.stripHtml(segs.first()).trim()
            val termIdx = SefariaClient.firstSentenceTerminal(plain)
            if (termIdx != null) plain.substring(0, termIdx + 1).trim().ifEmpty { null }
            else plain.ifEmpty { null }
        }
    }

    // MARK: - Study content loading

    fun loadStudyContentForCurrentSection() {
        val session = _session.value ?: return
        val idx = session.currentSectionIndex
        if (idx >= session.sections.size) return
        if (session.sections[idx].summary != null) return

        _isLoadingStudyContent.value = true
        viewModelScope.launch {
            if (loadingIndices.contains(idx)) {
                // Wait for background prefetch
                while (loadingIndices.contains(idx) && _session.value?.sections?.get(idx)?.summary == null) {
                    delay(300)
                }
                if (_session.value?.sections?.getOrNull(idx)?.summary == null) {
                    fetchAndStoreContent(idx, surfaceError = true)
                }
            } else {
                fetchAndStoreContent(idx, surfaceError = true)
            }
            _isLoadingStudyContent.value = false
        }
    }

    private suspend fun prefetchSection(idx: Int) {
        val session = _session.value ?: return
        if (idx >= session.sections.size) return
        if (session.sections[idx].summary != null) return
        if (loadingIndices.contains(idx)) return

        loadingIndices.add(idx)
        try {
            fetchAndStoreContent(idx, surfaceError = false)
        } finally {
            loadingIndices.remove(idx)
        }
    }

    private suspend fun fetchAndStoreContent(idx: Int, surfaceError: Boolean, attempt: Int = 0) {
        val session = _session.value ?: return
        if (idx >= session.sections.size) return

        val tractate = session.tractate
        val daf = session.daf

        try {
            val shiurContext = ShiurClient.shiurRewrite.value

            // Check shared cache first — returns null on any failure (network, not found, etc.)
            val cached = StudyCache.fetch(tractate, daf, idx, studyMode, quizMode)
            if (cached != null) {
                // Use cache if: already enriched with shiur, OR no shiur available to improve it.
                // Only regenerate when we can produce a better result.
                if (cached.shiurUsed || shiurContext == null) {
                    _session.update { current ->
                        current ?: return@update null
                        if (idx >= current.sections.size) return@update current
                        if (current.sections[idx].summary != null) return@update current
                        val updatedSections = current.sections.toMutableList()
                        updatedSections[idx] = updatedSections[idx].copy(
                            summary = cached.summary,
                            quizQuestions = cached.questions
                        )
                        current.copy(sections = updatedSections)
                    }
                    return
                }
                // cached.shiurUsed == false && shiurContext != null:
                // fall through to regenerate with lecture context.
            }

            // Cache miss (or stale non-shiur entry) — call Claude
            val plainText = SefariaClient.stripHtml(session.sections[idx].rawText)
            val (summary, questions) = ClaudeClient.generateStudyContent(
                sectionTitle = session.sections[idx].title,
                sectionText = plainText,
                tractate = tractate,
                daf = daf,
                mode = studyMode,
                quizMode = quizMode,
                shiurContext = shiurContext
            )

            _session.update { current ->
                current ?: return@update null
                if (idx >= current.sections.size) return@update current
                if (current.sections[idx].summary != null) return@update current
                val updatedSections = current.sections.toMutableList()
                updatedSections[idx] = updatedSections[idx].copy(
                    summary = summary,
                    quizQuestions = questions
                )
                current.copy(sections = updatedSections)
            }

            // Write to shared cache (fire-and-forget — failure does not affect the user)
            viewModelScope.launch {
                StudyCache.store(tractate, daf, idx, studyMode, quizMode, summary, questions,
                    shiurUsed = shiurContext != null)
            }

        } catch (e: Exception) {
            if (surfaceError) {
                if (e is ClaudeError.RateLimited && attempt == 0) {
                    _isRateLimited.value = true
                    for (remaining in 65 downTo 1) {
                        if (_session.value == null) {
                            _isRateLimited.value = false
                            _rateLimitCountdown.value = 0
                            return
                        }
                        _rateLimitCountdown.value = remaining
                        delay(1000)
                    }
                    _rateLimitCountdown.value = 0
                    _isRateLimited.value = false
                    fetchAndStoreContent(idx, surfaceError = true, attempt = 1)
                } else {
                    _error.value = e.message ?: "Failed to load study content"
                }
            }
        }
    }

    // MARK: - Navigation

    fun advanceToNextSection() {
        viewModelScope.launch {
            _session.update { it?.copy(currentSectionIndex = (it.currentSectionIndex + 1)) }
            // Content loading is driven by StudyModeScreen's LaunchedEffect(session?.currentSectionIndex)
            // observer — no eager Claude calls here so navigating the Translation tab stays free.
        }
    }

    fun goToPreviousSection() {
        viewModelScope.launch {
            _session.update { it?.copy(currentSectionIndex = maxOf(0, it.currentSectionIndex - 1)) }
            // Content loading is driven by StudyModeScreen's LaunchedEffect observer.
        }
    }

    fun jumpToAmudA() {
        viewModelScope.launch {
            _session.update { it?.copy(currentSectionIndex = 0) }
            // Content loading is driven by StudyModeScreen's LaunchedEffect observer.
        }
    }

    fun jumpToAmudB() {
        val session = _session.value ?: return
        val idx = session.amudBSectionIndex ?: return
        if (idx >= session.sections.size) return
        viewModelScope.launch {
            _session.update { it?.copy(currentSectionIndex = idx) }
            // Content loading is driven by StudyModeScreen's LaunchedEffect observer.
        }
    }

    // MARK: - Quiz — Multiple Choice

    fun answerQuestion(questionIndex: Int, choiceIndex: Int) {
        _session.update { session ->
            session ?: return@update null
            val si = session.currentSectionIndex
            if (si >= session.sections.size) return@update session
            if (questionIndex >= session.sections[si].quizQuestions.size) return@update session
            val updatedSections = session.sections.toMutableList()
            val updatedQuestions = updatedSections[si].quizQuestions.toMutableList()
            updatedQuestions[questionIndex] = updatedQuestions[questionIndex].copy(selectedIndex = choiceIndex)
            updatedSections[si] = updatedSections[si].copy(quizQuestions = updatedQuestions)
            session.copy(sections = updatedSections)
        }
    }

    // MARK: - Quiz — Flashcard

    fun markFlashcard(questionIndex: Int, correct: Boolean) {
        _session.update { session ->
            session ?: return@update null
            val si = session.currentSectionIndex
            if (si >= session.sections.size) return@update session
            val updatedSections = session.sections.toMutableList()
            val updatedQuestions = updatedSections[si].quizQuestions.toMutableList()
            updatedQuestions[questionIndex] = updatedQuestions[questionIndex].copy(selfMarkedCorrect = correct)
            updatedSections[si] = updatedSections[si].copy(quizQuestions = updatedQuestions)
            session.copy(sections = updatedSections)
        }
    }

    // MARK: - Quiz — Fill in Blank / Short Answer

    fun gradeAnswer(questionIndex: Int, userText: String) {
        val session = _session.value ?: return
        val si = session.currentSectionIndex
        if (si >= session.sections.size) return
        if (questionIndex >= session.sections[si].quizQuestions.size) return

        // Mark as grading
        _session.update { s ->
            s ?: return@update null
            val updatedSections = s.sections.toMutableList()
            val updatedQuestions = updatedSections[si].quizQuestions.toMutableList()
            updatedQuestions[questionIndex] = updatedQuestions[questionIndex].copy(
                userText = userText,
                isGrading = true
            )
            updatedSections[si] = updatedSections[si].copy(quizQuestions = updatedQuestions)
            s.copy(sections = updatedSections)
        }

        val question = session.sections[si].quizQuestions[questionIndex].question
        val correctAnswer = session.sections[si].quizQuestions[questionIndex].correctAnswer

        viewModelScope.launch {
            try {
                val result = ClaudeClient.gradeAnswer(question, correctAnswer, userText, quizMode)
                _session.update { s ->
                    s ?: return@update null
                    if (si >= s.sections.size || questionIndex >= s.sections[si].quizQuestions.size) return@update s
                    val updatedSections = s.sections.toMutableList()
                    val updatedQuestions = updatedSections[si].quizQuestions.toMutableList()
                    updatedQuestions[questionIndex] = updatedQuestions[questionIndex].copy(
                        isGrading = false,
                        gradeResult = result
                    )
                    updatedSections[si] = updatedSections[si].copy(quizQuestions = updatedQuestions)
                    s.copy(sections = updatedSections)
                }
            } catch (e: Exception) {
                _session.update { s ->
                    s ?: return@update null
                    if (si >= s.sections.size || questionIndex >= s.sections[si].quizQuestions.size) return@update s
                    val updatedSections = s.sections.toMutableList()
                    val updatedQuestions = updatedSections[si].quizQuestions.toMutableList()
                    updatedQuestions[questionIndex] = updatedQuestions[questionIndex].copy(
                        isGrading = false,
                        gradeResult = com.anydaf.model.GradeResult(false, "Grading failed. The answer was: $correctAnswer")
                    )
                    updatedSections[si] = updatedSections[si].copy(quizQuestions = updatedQuestions)
                    s.copy(sections = updatedSections)
                }
            }
        }
    }

    // MARK: - Teardown

    fun endSession() {
        _session.value = null
        _error.value = null
        _isLoadingText.value = false
        _isLoadingStudyContent.value = false
        loadingIndices.clear()
        _isRateLimited.value = false
        _rateLimitCountdown.value = 0
    }

    fun clearError() { _error.value = null }
}
