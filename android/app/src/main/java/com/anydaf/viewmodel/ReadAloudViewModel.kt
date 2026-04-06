package com.anydaf.viewmodel

import android.content.Context
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.AnyDafApp
import com.anydaf.data.api.SefariaClient
import com.anydaf.model.QuizMode
import com.anydaf.model.QuizQuestion
import com.anydaf.model.StudySection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.resume

enum class ReadAloudPhase {
    IDLE,
    READING_TRANSLATION,
    READING_SUMMARY,
    WAITING_FOR_CONTENT,
    READING_QUESTION,
    LISTENING_FOR_ANSWER,
    READING_FEEDBACK,
    TRANSITIONING,
    COMPLETED;

    val displayText: String get() = when (this) {
        IDLE -> ""
        READING_TRANSLATION -> "Reading translation…"
        READING_SUMMARY -> "Reading summary…"
        WAITING_FOR_CONTENT -> "Loading content…"
        READING_QUESTION -> "Reading question…"
        LISTENING_FOR_ANSWER -> "Listening…"
        READING_FEEDBACK -> "Reading feedback…"
        TRANSITIONING -> "Next section…"
        COMPLETED -> "Complete"
    }
}

enum class ViewSwitchTarget { TRANSLATION, STUDY, QUIZ }
data class ViewSwitchRequest(val target: ViewSwitchTarget, val serial: Long)

class ReadAloudViewModel : ViewModel() {

    private val _isActive = MutableStateFlow(false)
    val isActive: StateFlow<Boolean> = _isActive.asStateFlow()

    private val _isPaused = MutableStateFlow(false)
    val isPaused: StateFlow<Boolean> = _isPaused.asStateFlow()

    private val _phase = MutableStateFlow(ReadAloudPhase.IDLE)
    val phase: StateFlow<ReadAloudPhase> = _phase.asStateFlow()

    private val _isListening = MutableStateFlow(false)
    val isListening: StateFlow<Boolean> = _isListening.asStateFlow()

    private val _recognizedText = MutableStateFlow("")
    val recognizedText: StateFlow<String> = _recognizedText.asStateFlow()

    private val _permissionDenied = MutableStateFlow(false)
    val permissionDenied: StateFlow<Boolean> = _permissionDenied.asStateFlow()

    private val _viewRequest = MutableStateFlow(ViewSwitchRequest(ViewSwitchTarget.TRANSLATION, 0))
    val viewRequest: StateFlow<ViewSwitchRequest> = _viewRequest.asStateFlow()

    private val context: Context get() = AnyDafApp.context
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var speechRecognizer: SpeechRecognizer? = null
    private var sessionJob: Job? = null
    private val utteranceCounter = AtomicInteger(0)

    // Callbacks provided by UI
    var studySessionViewModel: StudySessionViewModel? = null
    var onSectionQuizzed: ((Int) -> Unit)? = null
    var skipRequested = false

    init {
        initTts()
    }

    private fun initTts() {
        tts = TextToSpeech(context) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) {
                tts?.language = Locale.US
                tts?.setSpeechRate(0.9f)  // slightly slower for clarity
            }
        }
    }

    fun startSession() {
        if (_isActive.value) return
        _isActive.value = true
        _isPaused.value = false
        skipRequested = false
        sessionJob = viewModelScope.launch {
            try {
                runLoop()
            } catch (e: CancellationException) {
                // Normal cancellation
            } finally {
                _phase.value = ReadAloudPhase.IDLE
                _isActive.value = false
                _isPaused.value = false
            }
        }
    }

    fun stop() {
        sessionJob?.cancel()
        tts?.stop()
        speechRecognizer?.stopListening()
        _isListening.value = false
        _isActive.value = false
        _isPaused.value = false
        _phase.value = ReadAloudPhase.IDLE
    }

    fun pauseResume() {
        if (_isPaused.value) {
            _isPaused.value = false
            tts?.speak("", TextToSpeech.QUEUE_FLUSH, null, null)
        } else {
            _isPaused.value = true
            tts?.stop()
            speechRecognizer?.stopListening()
            _isListening.value = false
        }
    }

    fun skip() {
        skipRequested = true
        tts?.stop()
        speechRecognizer?.stopListening()
        _isListening.value = false
    }

    private fun emitViewRequest(target: ViewSwitchTarget) {
        _viewRequest.value = ViewSwitchRequest(target, System.currentTimeMillis())
    }

    // MARK: - Main loop

    private suspend fun runLoop() {
        val manager = studySessionViewModel ?: return
        while (true) {
            val session = manager.session.value ?: break
            if (session.isComplete) { _phase.value = ReadAloudPhase.COMPLETED; break }
            val sectionIdx = session.currentSectionIndex
            val section = session.currentSection ?: break

            if (!runSection(section, sectionIdx, manager)) break
            if (!_isActive.value) break
        }
    }

    private suspend fun runSection(
        section: StudySection,
        sectionIdx: Int,
        manager: StudySessionViewModel
    ): Boolean {
        skipRequested = false

        // 1. Read translation
        emitViewRequest(ViewSwitchTarget.TRANSLATION)
        _phase.value = ReadAloudPhase.READING_TRANSLATION
        val plainText = SefariaClient.stripHtml(section.rawText)
        speak(plainText)
        if (!_isActive.value) return false

        // 2. Wait for study content if not yet loaded
        if (section.summary == null) {
            _phase.value = ReadAloudPhase.WAITING_FOR_CONTENT
            manager.loadStudyContentForCurrentSection()
            var waited = 0
            while (manager.session.value?.sections?.getOrNull(sectionIdx)?.summary == null && waited < 60000) {
                delay(500)
                waited += 500
            }
        }

        // 3. Read summary
        val summary = manager.session.value?.sections?.getOrNull(sectionIdx)?.summary
        if (summary != null) {
            emitViewRequest(ViewSwitchTarget.STUDY)
            _phase.value = ReadAloudPhase.READING_SUMMARY
            speak(summary)
            if (!_isActive.value) return false
        }

        // 4. Read questions
        val questions = manager.session.value?.sections?.getOrNull(sectionIdx)?.quizQuestions ?: emptyList()
        if (questions.isNotEmpty()) {
            emitViewRequest(ViewSwitchTarget.QUIZ)
            for ((qIdx, question) in questions.withIndex()) {
                if (!_isActive.value) return false
                if (!runQuestion(qIdx, question, sectionIdx, manager)) return false
            }
            onSectionQuizzed?.invoke(sectionIdx)
        }

        // 5. Advance
        _phase.value = ReadAloudPhase.TRANSITIONING
        manager.advanceToNextSection()
        return true
    }

    private suspend fun runQuestion(
        qIdx: Int,
        question: QuizQuestion,
        sectionIdx: Int,
        manager: StudySessionViewModel
    ): Boolean {
        _phase.value = ReadAloudPhase.READING_QUESTION

        val questionText = buildString {
            append("Question ${qIdx + 1}. ")
            append(question.question)
            if (question.mode == QuizMode.MULTIPLE_CHOICE) {
                append(". ")
                question.choices.forEach { append("$it. ") }
            }
        }
        speak(questionText)
        if (!_isActive.value) return false

        // Listen for answer
        _phase.value = ReadAloudPhase.LISTENING_FOR_ANSWER
        val answer = listenForAnswer() ?: ""
        _recognizedText.value = answer
        if (!_isActive.value) return false

        // Process answer based on mode
        when (question.mode) {
            QuizMode.MULTIPLE_CHOICE -> {
                val parsed = parseMcAnswer(answer)
                if (parsed != null) manager.answerQuestion(qIdx, parsed)
            }
            QuizMode.FLASHCARD -> {
                // Read out the answer and let user self-grade
                val answerText = "The answer is: ${question.correctAnswer}. Did you get it right? Say yes or no."
                speak(answerText)
                if (!_isActive.value) return false
                val selfGrade = listenForAnswer() ?: ""
                val correct = selfGrade.lowercase().contains("yes")
                manager.markFlashcard(qIdx, correct)
            }
            QuizMode.FILL_IN_BLANK, QuizMode.SHORT_ANSWER -> {
                if (answer.isNotEmpty()) manager.gradeAnswer(qIdx, answer)
            }
        }

        // Read feedback
        delay(500)
        val updatedQuestion = manager.session.value?.sections?.getOrNull(sectionIdx)?.quizQuestions?.getOrNull(qIdx)
        _phase.value = ReadAloudPhase.READING_FEEDBACK
        val feedbackText = when (question.mode) {
            QuizMode.MULTIPLE_CHOICE -> {
                val isCorrect = updatedQuestion?.isCorrect == true
                if (isCorrect) "Correct!" else "The answer is: ${question.correctAnswer}."
            }
            QuizMode.FLASHCARD -> {
                val isCorrect = updatedQuestion?.selfMarkedCorrect == true
                if (isCorrect) "Great job!" else "The answer was: ${question.correctAnswer}."
            }
            QuizMode.FILL_IN_BLANK, QuizMode.SHORT_ANSWER -> {
                val grade = updatedQuestion?.gradeResult
                if (grade != null) {
                    (if (grade.isCorrect) "Correct! " else "Incorrect. ") + grade.feedback
                } else "Answer: ${question.correctAnswer}."
            }
        }
        speak(feedbackText)
        return _isActive.value
    }

    private fun parseMcAnswer(text: String): Int? {
        val lower = text.lowercase().trim()
        return when {
            lower.startsWith("a") || lower == "ay" || lower == "first" -> 0
            lower.startsWith("b") || lower == "bee" || lower == "second" -> 1
            lower.startsWith("c") || lower == "see" || lower == "sea" || lower == "third" -> 2
            lower.startsWith("d") || lower == "dee" || lower == "fourth" -> 3
            else -> null
        }
    }

    // MARK: - TTS

    private suspend fun speak(text: String) = suspendCancellableCoroutine<Unit> { cont ->
        val utteranceId = "utt_${utteranceCounter.incrementAndGet()}"
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onDone(id: String?) { if (id == utteranceId) cont.resume(Unit) }
            @Deprecated("Deprecated in Java")
            override fun onError(id: String?) { cont.resume(Unit) }
        })

        val params = Bundle().apply { putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId) }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, params, utteranceId)

        cont.invokeOnCancellation { tts?.stop() }
    }

    // MARK: - STT

    private suspend fun listenForAnswer(): String? = suspendCancellableCoroutine { cont ->
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            cont.resume(null)
            return@suspendCancellableCoroutine
        }

        var silenceJob: Job? = null
        val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        speechRecognizer = recognizer
        _isListening.value = true

        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}

            override fun onPartialResults(partialResults: Bundle?) {
                // Reset 2-second silence timer on each partial result
                silenceJob?.cancel()
                silenceJob = viewModelScope.launch {
                    delay(2000)
                    recognizer.stopListening()
                }
            }

            override fun onResults(results: Bundle?) {
                silenceJob?.cancel()
                _isListening.value = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                cont.resume(matches?.firstOrNull())
            }

            override fun onError(error: Int) {
                silenceJob?.cancel()
                _isListening.value = false
                cont.resume(null)
            }

            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        recognizer.startListening(intent)

        cont.invokeOnCancellation {
            silenceJob?.cancel()
            recognizer.stopListening()
            recognizer.destroy()
            _isListening.value = false
        }
    }

    override fun onCleared() {
        stop()
        tts?.shutdown()
        speechRecognizer?.destroy()
        super.onCleared()
    }
}
