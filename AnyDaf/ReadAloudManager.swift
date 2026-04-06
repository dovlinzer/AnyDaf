import AVFoundation
import Speech
import MediaPlayer

// MARK: - Read-Aloud Manager

/// Drives hands-free study: reads translation, summary, and quiz questions aloud;
/// captures spoken answers via STT; grades via Claude (same calls as the text UI).
@MainActor
final class ReadAloudManager: NSObject, ObservableObject {

    // MARK: - Phase

    enum Phase: Equatable {
        case idle
        case readingTranslation
        case readingSummary
        case waitingForContent
        case readingQuestion(Int)
        case listeningForAnswer(Int)
        case readingFeedback(Int)
        case transitioning
        case completed

        var displayText: String {
            switch self {
            case .idle:                   return ""
            case .readingTranslation:     return "Reading translation…"
            case .readingSummary:         return "Reading summary…"
            case .waitingForContent:      return "Loading content…"
            case .readingQuestion(let i): return "Question \(i + 1)…"
            case .listeningForAnswer:     return "Listening…"
            case .readingFeedback:        return "Reading feedback…"
            case .transitioning:          return "Next section…"
            case .completed:              return "Complete"
            }
        }
    }

    // MARK: - Published state

    @Published var isActive        = false
    @Published var isPaused        = false
    @Published var phase: Phase    = .idle
    @Published var isListening     = false
    @Published var recognizedText  = ""
    @Published var permissionDenied = false
    /// Published so the UI can sync tabs/quiz visibility with the read-aloud flow.
    /// Uses a serial number so onChange fires even when switching to the same target
    /// (e.g. .translation → next section → .translation).
    @Published var viewRequest = ViewSwitchRequest(target: .translation, serial: 0)

    struct ViewSwitchRequest: Equatable {
        let target: ViewSwitchTarget
        let serial: UInt64
    }

    // MARK: - Dependencies (set by ContentView before session starts)

    weak var studyManager: StudySessionManager?
    weak var audioPlayer:  AudioPlayer?

    /// Invoked when each section's quiz begins so the UI can track score.
    var onSectionQuizzed: ((Int) -> Void)?

    enum ViewSwitchTarget {
        case translation
        case study
        case quiz
    }

    /// Where to start the flow within a section (set by userDidSwitchTo).
    private enum FlowStartPoint { case beginning, summary, quiz }
    private var flowStartPoint: FlowStartPoint = .beginning
    /// True when the user manually switched tabs, signaling the flow to restart the loop.
    private var skipRequested = false
    private var viewRequestSerial: UInt64 = 0

    // MARK: - TTS

    private let synthesizer = AVSpeechSynthesizer()
    private var speechFinishedContinuation: CheckedContinuation<Void, Never>?

    // MARK: - STT

    private let audioEngine      = AVAudioEngine()
    private var speechRecognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var hasMicTap        = false
    private var listeningContinuation: CheckedContinuation<String, Never>?
    private var silenceTask: Task<Void, Never>?

    // MARK: - Flow

    private var flowTask: Task<Void, Never>?

    // MARK: - Init

    override init() {
        super.init()
        synthesizer.delegate = self
        observeAudioInterruptions()
    }

    // MARK: - Public Control

    func startReadAloud() async {
        guard !isActive else { return }

        audioPlayer?.stop()

        // Permissions only needed for modes that use the microphone.
        let quizMode = studyManager?.quizMode ?? .multipleChoice
        if quizMode != .flashcard {
            guard await requestPermissions() else {
                permissionDenied = true
                return
            }
        }

        isActive = true
        isPaused = false
        phase    = .idle

        configureAudioSessionForPlayback()
        setupNowPlayingCommands()

        flowTask = Task { [weak self] in await self?.runSectionLoop() }
    }

    func stopReadAloud() {
        isActive = false
        isPaused = false
        flowTask?.cancel()
        flowTask = nil
        synthesizer.stopSpeaking(at: .immediate)
        resumeSpeechContinuationIfNeeded()
        stopListening()
        teardownNowPlaying()
        configureAudioSessionForPlayback()
        phase          = .idle
        recognizedText = ""
    }

    func togglePauseResume() {
        if isPaused {
            isPaused = false
            if synthesizer.isPaused { synthesizer.continueSpeaking() }
        } else {
            isPaused = true
            if synthesizer.isSpeaking { synthesizer.pauseSpeaking(at: .word) }
            if isListening { stopListening() }
        }
        updateNowPlaying()
    }

    /// Cancels the current utterance so the flow loop advances to the next step.
    func skipForward() {
        synthesizer.stopSpeaking(at: .immediate)
        if isListening { stopListening() }
    }

    /// Called by the UI when the user manually switches tabs while read-aloud is active.
    /// Cancels current speech and restarts the flow from the selected phase.
    func userDidSwitchTo(_ target: ViewSwitchTarget) {
        guard isActive else { return }
        switch target {
        case .translation: flowStartPoint = .beginning
        case .study:       flowStartPoint = .summary
        case .quiz:        flowStartPoint = .quiz
        }
        skipRequested = true
        synthesizer.stopSpeaking(at: .immediate)
        resumeSpeechContinuationIfNeeded()
        if isListening { stopListening() }
    }

    /// Bumps the serial and publishes so `.onChange` always fires.
    private func requestView(_ target: ViewSwitchTarget) {
        viewRequestSerial += 1
        viewRequest = ViewSwitchRequest(target: target, serial: viewRequestSerial)
    }

    // MARK: - Section Loop

    private func runSectionLoop() async {
        guard let manager = studyManager else { await finish(); return }

        while isActive {
            guard let session = manager.session,
                  !session.isComplete,
                  let section = session.currentSection
            else { break }

            updateNowPlaying()

            // Consume any pending skip request
            let startPoint = flowStartPoint
            flowStartPoint = .beginning
            skipRequested = false

            // ── Translation ─────────────────────────────────────────────────
            if startPoint == .beginning {
                phase = .readingTranslation
                requestView(.translation)
                await speak(SefariaClient.stripHTML(section.rawText))
                guard isActive else { break }
                if skipRequested { continue }   // user tapped Study or Quiz mid-read
            }

            // ── Summary — trigger load if not prefetched yet ─────────────────
            if startPoint != .quiz {
                if manager.session?.currentSection?.summary == nil {
                    phase = .waitingForContent
                    requestView(.study)
                    await speak("Loading study content, please wait.")
                    await manager.loadStudyContentForCurrentSection()
                    while isActive && !skipRequested
                            && manager.session?.currentSection?.summary == nil {
                        try? await Task.sleep(nanoseconds: 300_000_000)
                    }
                }
                guard isActive else { break }
                if skipRequested { continue }

                if let summary = manager.session?.currentSection?.summary {
                    phase = .readingSummary
                    requestView(.study)
                    await speak("Summary. \(summary)")
                }
                guard isActive else { break }
                if skipRequested { continue }
            }

            // ── Quiz ─────────────────────────────────────────────────────────
            let sectionIdx = manager.session?.currentSectionIndex ?? 0
            if let questions = manager.session?.currentSection?.quizQuestions,
               !questions.isEmpty {
                onSectionQuizzed?(sectionIdx)
                requestView(.quiz)
                await speak("Now for the quiz.")
                for (idx, question) in questions.enumerated() {
                    guard isActive && !skipRequested else { break }
                    await handleQuestion(question, at: idx)
                }
            }
            guard isActive else { break }
            if skipRequested { continue }

            // ── Advance or finish ────────────────────────────────────────────
            let isLast = manager.session
                .map { $0.currentSectionIndex + 1 >= $0.sections.count } ?? true
            if isLast { await finish(); return }

            phase = .transitioning
            await speak("Section complete. Moving to the next section.")
            await manager.advanceToNextSection()
        }

        await finish()
    }

    private func finish() async {
        guard isActive else { return }
        await speak("Study session complete. Great work!")
        phase    = .completed
        isActive = false
        teardownNowPlaying()
    }

    // MARK: - Question Handlers

    private func handleQuestion(_ q: QuizQuestion, at idx: Int) async {
        switch q.mode {
        case .multipleChoice: await handleMultipleChoice(q, at: idx)
        case .flashcard:      await handleFlashcard(q, at: idx)
        case .fillInBlank:    await handleFillInBlank(q, at: idx)
        case .shortAnswer:    await handleShortAnswer(q, at: idx)
        }
    }

    private func handleMultipleChoice(_ q: QuizQuestion, at idx: Int) async {
        phase = .readingQuestion(idx)
        // Choices already include "A) …" labels from Claude
        let choicesSpoken = q.choices.joined(separator: ". ")
        await speak("Question \(idx + 1). \(q.question). Options: \(choicesSpoken).")
        guard isActive else { return }

        phase = .listeningForAnswer(idx)
        await speak("Say A, B, C, or D. You can also say 1, 2, 3, or 4.")
        let spoken = await listenForSpeech(timeout: 10)
        guard isActive else { return }

        phase = .readingFeedback(idx)
        if let choice = parseMultipleChoiceLetter(spoken) {
            studyManager?.answerQuestion(questionIndex: idx, choiceIndex: choice)
            let correct = choice == q.correctIndex
            await speak(correct
                ? "Correct!"
                : "Incorrect. The correct answer was \(q.choices[q.correctIndex]).")
        } else {
            // Didn't catch the answer — give credit and explain.
            studyManager?.answerQuestion(questionIndex: idx, choiceIndex: q.correctIndex)
            await speak("I didn't catch your answer. The correct answer was \(q.choices[q.correctIndex]).")
        }
    }

    private func handleFlashcard(_ q: QuizQuestion, at idx: Int) async {
        phase = .readingQuestion(idx)
        await speak("Question \(idx + 1). \(q.question)")
        guard isActive else { return }

        phase = .listeningForAnswer(idx)
        await speak("Think about your answer.")
        // 3-second thinking pause (15 × 200 ms — lets isActive checks fire)
        for _ in 0..<15 {
            guard isActive else { return }
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
        guard isActive else { return }

        phase = .readingFeedback(idx)
        await speak("The answer is: \(q.correctAnswer)")
        studyManager?.markFlashcard(questionIndex: idx, correct: true)
    }

    private func handleFillInBlank(_ q: QuizQuestion, at idx: Int) async {
        phase = .readingQuestion(idx)
        let spokenQ = q.question.replacingOccurrences(of: "_____", with: "blank")
        await speak("Question \(idx + 1). Fill in the blank: \(spokenQ)")
        guard isActive else { return }

        phase = .listeningForAnswer(idx)
        await speak("Say your answer now.")
        let spoken = await listenForSpeech(timeout: 8)
        guard isActive else { return }

        phase = .readingFeedback(idx)
        let answer = spoken.trimmingCharacters(in: .whitespaces)
        if !answer.isEmpty {
            await speak("Checking your answer.")
            await studyManager?.gradeAnswer(questionIndex: idx, userText: answer)
            await speakGradeResult(for: idx, correctAnswer: q.correctAnswer, isShortAnswer: false)
        } else {
            await studyManager?.gradeAnswer(questionIndex: idx, userText: "(no answer)")
            await speak("No answer detected. The correct answer was: \(q.correctAnswer).")
        }
    }

    private func handleShortAnswer(_ q: QuizQuestion, at idx: Int) async {
        phase = .readingQuestion(idx)
        await speak("Question \(idx + 1). \(q.question)")
        guard isActive else { return }

        phase = .listeningForAnswer(idx)
        await speak("Say your answer now. You have up to fifteen seconds.")
        let spoken = await listenForSpeech(timeout: 15)
        guard isActive else { return }

        phase = .readingFeedback(idx)
        let answer = spoken.trimmingCharacters(in: .whitespaces)
        if !answer.isEmpty {
            await speak("Checking your answer.")
            await studyManager?.gradeAnswer(questionIndex: idx, userText: answer)
            await speakGradeResult(for: idx, correctAnswer: q.correctAnswer, isShortAnswer: true)
        } else {
            await studyManager?.gradeAnswer(questionIndex: idx, userText: "(no answer)")
            await speak("No answer detected. The model answer was: \(q.correctAnswer).")
        }
    }

    /// Reads the Claude grading result aloud after `gradeAnswer` returns.
    private func speakGradeResult(for idx: Int, correctAnswer: String, isShortAnswer: Bool) async {
        let sectionIdx = studyManager?.session?.currentSectionIndex ?? 0
        guard let sections = studyManager?.session?.sections,
              sectionIdx < sections.count,
              idx < sections[sectionIdx].quizQuestions.count,
              let result = sections[sectionIdx].quizQuestions[idx].gradeResult
        else { return }

        if result.isCorrect {
            await speak("Correct! \(result.feedback)")
        } else {
            let label = isShortAnswer ? "The model answer was" : "The correct answer was"
            await speak("Incorrect. \(result.feedback). \(label): \(correctAnswer).")
        }
    }

    // MARK: - TTS

    /// Cached best-quality voice for en-US. Computed once on first use.
    private lazy var preferredVoice: AVSpeechSynthesisVoice? = {
        let enVoices = AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix("en") }

        // Prefer premium > enhanced > default quality
        if let premium = enVoices.first(where: { $0.quality == .premium }) {
            return premium
        }
        if let enhanced = enVoices.first(where: { $0.quality == .enhanced }) {
            return enhanced
        }
        // Fall back to the default en-US voice
        return AVSpeechSynthesisVoice(language: "en-US")
    }()

    private func speak(_ text: String) async {
        while isPaused && isActive {
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
        guard isActive else { return }

        configureAudioSessionForPlayback()

        let utterance = AVSpeechUtterance(string: text)
        utterance.voice             = preferredVoice
        utterance.rate              = 0.52   // slightly slower than default for clarity while driving
        utterance.preUtteranceDelay = 0.05
        utterance.postUtteranceDelay = 0.15

        await withCheckedContinuation { continuation in
            speechFinishedContinuation = continuation
            synthesizer.speak(utterance)
        }
    }

    private func resumeSpeechContinuationIfNeeded() {
        speechFinishedContinuation?.resume()
        speechFinishedContinuation = nil
    }

    // MARK: - STT

    private func listenForSpeech(timeout: TimeInterval) async -> String {
        guard isActive else { return "" }

        configureAudioSessionForRecording()

        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        guard speechRecognizer?.isAvailable == true else {
            configureAudioSessionForPlayback()
            return ""
        }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        recognitionRequest?.shouldReportPartialResults = true
        if speechRecognizer?.supportsOnDeviceRecognition == true {
            recognitionRequest?.requiresOnDeviceRecognition = true
        }

        recognizedText = ""
        isListening    = true

        let inputNode = audioEngine.inputNode
        let format    = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }
        hasMicTap = true

        do {
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            stopListening()
            configureAudioSessionForPlayback()
            return ""
        }

        let result = await withCheckedContinuation { (continuation: CheckedContinuation<String, Never>) in
            listeningContinuation = continuation

            recognitionTask = speechRecognizer?.recognitionTask(
                with: recognitionRequest!
            ) { [weak self] result, error in
                Task { @MainActor [weak self] in
                    guard let self else { return }
                    if let result, !result.isFinal {
                        self.recognizedText = result.bestTranscription.formattedString
                        // Reset 2-second silence timer on each new partial result
                        self.silenceTask?.cancel()
                        self.silenceTask = Task { [weak self] in
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                            guard let self, self.listeningContinuation != nil else { return }
                            self.stopListening()
                        }
                    } else if let result, result.isFinal {
                        self.recognizedText = result.bestTranscription.formattedString
                        self.stopListening()
                    } else if error != nil {
                        self.stopListening()
                    }
                }
            }

            // Absolute timeout
            Task { [weak self] in
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                guard let self, self.listeningContinuation != nil else { return }
                self.stopListening()
            }
        }

        listeningContinuation = nil
        return result
    }

    private func stopListening() {
        silenceTask?.cancel()
        silenceTask = nil
        audioEngine.stop()
        if hasMicTap {
            audioEngine.inputNode.removeTap(onBus: 0)
            hasMicTap = false
        }
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask    = nil
        isListening        = false
        // Resume any suspended continuation (e.g. when skipForward() is called mid-listen)
        listeningContinuation?.resume(returning: recognizedText)
        listeningContinuation = nil
    }

    // MARK: - MC Answer Parsing

    private func parseMultipleChoiceLetter(_ text: String) -> Int? {
        let upper = text.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        // Phonetic variants: STT often transcribes spoken letters as words
        let map: [String: Int] = [
            "A": 0, "B": 1, "C": 2, "D": 3,
            // Phonetic spellings of letters
            "AY": 0, "EH": 0, "EY": 0, "AE": 0, "HEY": 0, "AYE": 0,
            "BEE": 1, "BE": 1, "BEA": 1, "B.": 1,
            "SEE": 2, "CEE": 2, "CE": 2, "SEA": 2, "SI": 2, "C.": 2,
            "DEE": 3, "DE": 3, "D.": 3,
            // Numbers
            "1": 0, "2": 1, "3": 2, "4": 3,
            "ONE": 0, "TWO": 1, "THREE": 2, "FOUR": 3,
            "FIRST": 0, "SECOND": 1, "THIRD": 2, "FOURTH": 3,
            // Common STT mishearings
            "OPTION A": 0, "OPTION B": 1, "OPTION C": 2, "OPTION D": 3,
            "LETTER A": 0, "LETTER B": 1, "LETTER C": 2, "LETTER D": 3,
            "ANSWER A": 0, "ANSWER B": 1, "ANSWER C": 2, "ANSWER D": 3,
        ]
        if let idx = map[upper] { return idx }
        // Try each token individually
        for token in upper.components(separatedBy: .whitespaces) {
            if let idx = map[token] { return idx }
        }
        // Try multi-word matches (e.g. "OPTION A" in "I'll say option A")
        for (key, idx) in map where key.contains(" ") && upper.contains(key) {
            return idx
        }
        return nil
    }

    // MARK: - Permissions

    private func requestPermissions() async -> Bool {
        let status = await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { cont.resume(returning: $0) }
        }
        guard status == .authorized else { return false }

        if #available(iOS 17.0, *) {
            return await AVAudioApplication.requestRecordPermission()
        } else {
            return await withCheckedContinuation { cont in
                AVAudioSession.sharedInstance().requestRecordPermission {
                    cont.resume(returning: $0)
                }
            }
        }
    }

    // MARK: - Audio Session

    private func configureAudioSessionForPlayback() {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true,
                                                       options: .notifyOthersOnDeactivation)
    }

    private func configureAudioSessionForRecording() {
        try? AVAudioSession.sharedInstance().setCategory(
            .playAndRecord,
            mode: .measurement,
            options: [.defaultToSpeaker, .allowBluetoothHFP]
        )
        try? AVAudioSession.sharedInstance().setActive(true)
    }

    // MARK: - Now Playing

    private func setupNowPlayingCommands() {
        let cc = MPRemoteCommandCenter.shared()
        cc.togglePlayPauseCommand.removeTarget(nil)
        cc.playCommand.removeTarget(nil)
        cc.pauseCommand.removeTarget(nil)
        cc.nextTrackCommand.removeTarget(nil)

        cc.togglePlayPauseCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in self?.togglePauseResume() }
            return .success
        }
        cc.playCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in
                if self?.isPaused == true { self?.togglePauseResume() }
            }
            return .success
        }
        cc.pauseCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in
                if self?.isPaused == false { self?.togglePauseResume() }
            }
            return .success
        }
        cc.nextTrackCommand.isEnabled = true
        cc.nextTrackCommand.addTarget { [weak self] _ in
            Task { @MainActor [weak self] in self?.skipForward() }
            return .success
        }
        updateNowPlaying()
    }

    private func updateNowPlaying() {
        guard isActive, let session = studyManager?.session else { return }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle:
                session.currentSection?.title ?? "AnyDaf Study",
            MPMediaItemPropertyArtist:
                "\(session.tractate) \(session.daf)",
            MPNowPlayingInfoPropertyPlaybackRate: isPaused ? 0.0 : 1.0,
        ]
    }

    private func teardownNowPlaying() {
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
    }

    // MARK: - Audio Interruptions

    private func observeAudioInterruptions() {
        NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            guard let info = notification.userInfo,
                  let typeVal = info[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: typeVal)
            else { return }
            Task { @MainActor [weak self] in
                guard let self, self.isActive else { return }
                if type == .began, !self.isPaused {
                    self.isPaused = true
                    if self.synthesizer.isSpeaking {
                        self.synthesizer.pauseSpeaking(at: .word)
                    }
                }
            }
        }
    }
}

// MARK: - AVSpeechSynthesizerDelegate

extension ReadAloudManager: AVSpeechSynthesizerDelegate {
    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        Task { @MainActor [weak self] in
            self?.speechFinishedContinuation?.resume()
            self?.speechFinishedContinuation = nil
        }
    }

    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didCancel utterance: AVSpeechUtterance
    ) {
        Task { @MainActor [weak self] in
            self?.speechFinishedContinuation?.resume()
            self?.speechFinishedContinuation = nil
        }
    }
}
