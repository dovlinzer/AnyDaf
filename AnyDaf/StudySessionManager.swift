import Foundation

enum StudyMode {
    case facts
    case conceptual
}

@MainActor
class StudySessionManager: ObservableObject {
    @Published var session: StudySession?
    @Published var isLoadingText = false
    @Published var isLoadingStudyContent = false
    @Published var error: String?

    private let sefariaClient = SefariaClient()
    private let claudeClient = ClaudeClient()

    @Published var studyMode: StudyMode = .facts
    @Published var quizMode: QuizMode = .multipleChoice
    /// True while waiting out a rate-limit pause before retrying a user-triggered request.
    @Published var isRateLimited = false
    /// Seconds remaining in the current rate-limit countdown (0 when not rate-limited).
    @Published var rateLimitCountdown: Int = 0

    /// Indices currently being fetched by a background prefetch task.
    /// Prevents duplicate concurrent API calls for the same section.
    private var loadingIndices: Set<Int> = []

    // MARK: - Session lifecycle

    func startSession(tractate: String, daf: Int, mode: StudyMode, quizMode: QuizMode, startAtLastSection: Bool = false) async {
        studyMode = mode
        self.quizMode = quizMode
        isLoadingText = true
        error = nil
        loadingIndices = []

        do {
            // Fetch the daf's two amudim AND adjacent-daf context all in parallel.
            async let amudASegs = sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "a")
            async let amudBSegs = sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "b")
            async let prevCtx   = fetchAdjacentContext(tractate: tractate, daf: daf - 1, amud: "b", fromEnd: true)
            async let nextCtx   = fetchAdjacentContext(tractate: tractate, daf: daf + 1, amud: "a", fromEnd: false)

            // Hebrew/Aramaic source text — always fetched in parallel; errors silently ignored.
            async let hebrewASegs = sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "a", language: "he")
            async let hebrewBSegs = sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "b", language: "he")

            // Either amud may not exist (e.g. Tamid starts at 25b, Mishnah-only tractates
            // have content on 'a' only) — treat missing amudim as empty rather than fatal.
            let segsA = (try? await amudASegs) ?? []
            let segsB = (try? await amudBSegs) ?? []
            let prevContext = await prevCtx
            let nextContext = await nextCtx
            let hebrewA = try? await hebrewASegs
            let hebrewB = try? await hebrewBSegs

            let sectionsA = SefariaClient.parseSections(from: segsA, hebrewSegments: hebrewA)
            let sectionsB = SefariaClient.parseSections(from: segsB, hebrewSegments: hebrewB)

            let allSections = sectionsA + sectionsB
            session = StudySession(
                tractate: tractate,
                daf: daf,
                scope: .fullDaf,
                sections: allSections,
                amudBSectionIndex: sectionsA.count,
                // precedingContext: fetchAdjacentContext returns nil when previous daf ends
                // cleanly (nothing after last period), so nil already means "no context needed."
                // followingContext: only shown when current daf genuinely ends mid-sentence.
                precedingContext: prevContext,
                followingContext: endsInMidSentence(segsB) ? nextContext : nil
            )

            if startAtLastSection, !allSections.isEmpty {
                session!.currentSectionIndex = allSections.count - 1
            }

            isLoadingText = false

            // All sections (0…N): prefetch in the background immediately.
            // Section 0 is included so its summary is likely ready by the time
            // the user taps the Study tab. No awaiting — user lands on Translation first.
            prefetchAllSections()

        } catch {
            self.error = error.localizedDescription
            isLoadingText = false
        }
    }

    /// Prefetch the first two sections at session start so they're silently ready by the
    /// time the user taps Study tab.  Only two calls — not all sections at once — to stay
    /// comfortably within the 5 requests/minute rate limit.  Remaining sections are
    /// prefetched one step ahead as the user advances (see advanceToNextSection).
    private func prefetchAllSections() {
        let count = session?.sections.count ?? 0
        for idx in 0..<min(2, count) {
            Task { await prefetchSection(at: idx) }
        }
    }

    // MARK: - Adjacent-daf context helpers

    /// Fetches a sentence fragment from the start or end of an adjacent daf amud.
    ///
    /// - fromEnd=true  (preceding): returns text AFTER the last sentence-terminal in the
    ///   last segment. If the segment ends cleanly (nothing after the final period), returns
    ///   nil — meaning no context is needed. If there is no terminal at all, the whole
    ///   segment is treated as a continuation fragment.
    /// - fromEnd=false (following): returns text UP TO AND INCLUDING the first
    ///   sentence-terminal in the first segment, giving just the tail of the cut sentence.
    ///
    /// Returns nil on any error (silently ignored — purely cosmetic context).
    private func fetchAdjacentContext(tractate: String, daf: Int,
                                      amud: String, fromEnd: Bool) async -> String? {
        guard daf > 0 else { return nil }
        guard let segs = try? await sefariaClient.fetchText(tractate: tractate, daf: daf, amud: amud),
              !segs.isEmpty else { return nil }

        if fromEnd {
            // Join ALL segments of the amud to reliably find the last sentence boundary,
            // regardless of how far back it sits. "I" in Menachot 63b, for example, may be
            // many segments before the final one — suffix(N) guesses always risk missing it.
            // We're already holding all segments in memory, so joining is O(n) in characters.
            let joined = SefariaClient.stripHTML(segs.joined(separator: " "))
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let lastTermIdx = Self.lastSentenceTerminal(in: joined) {
                let fragment = String(joined[joined.index(after: lastTermIdx)...])
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                return fragment.isEmpty ? nil : fragment   // nil = ends cleanly, no context needed
            }
            // No terminal in the entire amud — treat the whole daf as a single continuation.
            // This is extremely rare; return nil to avoid showing the full amud as context.
            return nil
        } else {
            // Following context: text up to and including the first terminal.
            let plain = SefariaClient.stripHTML(segs.first!)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let firstTermIdx = Self.firstSentenceTerminal(in: plain) {
                return String(plain[...firstTermIdx])
                    .trimmingCharacters(in: .whitespacesAndNewlines)
            }
            // No terminal found — show the whole first segment
            return plain.isEmpty ? nil : plain
        }
    }

    // MARK: - Sentence terminal helpers

    /// True if the character at `idx` in `text` is a genuine sentence-ending terminal —
    /// not a period inside an abbreviation like "i.e.", "e.g.", "R.", or "etc."
    ///
    /// Two-rule check for `.` (! and ? are always terminals):
    ///   1. The token immediately before the period is not a known abbreviation or single letter.
    ///   2. The next non-whitespace character (if any) is not lowercase.
    private static func isSentenceTerminal(_ c: Character, at idx: String.Index,
                                           in text: String) -> Bool {
        guard c == "." else { return true }   // ! and ? are unconditionally terminals

        // Extract the token directly before this period (stop at whitespace, period, comma).
        var tokenStart = idx
        while tokenStart > text.startIndex {
            let prev = text.index(before: tokenStart)
            let ch = text[prev]
            if ch.isWhitespace || ch == "." || ch == "," || ch == ";" { break }
            tokenStart = prev
        }
        let preceding = String(text[tokenStart..<idx]).lowercased()

        // Single-letter token → abbreviation ("R." for Rabbi, initials, etc.).
        if preceding.count == 1 { return false }

        // Known multi-character abbreviations.
        let known: Set<String> = [
            "i.e", "e.g", "etc", "vs", "cf", "ibid",
            "dr", "mr", "mrs", "ms", "prof", "rev", "sr", "jr",
            "jan", "feb", "mar", "apr", "jun", "jul", "aug",
            "sep", "oct", "nov", "dec",
        ]
        if known.contains(preceding) { return false }

        // If the next non-whitespace character is lowercase or a comma, the period is
        // mid-sentence (covers "e.g., green" and "i.e., the rule" patterns).
        let afterIdx = text.index(after: idx)
        if afterIdx < text.endIndex,
           let nextChar = text[afterIdx...].first(where: { !$0.isWhitespace }),
           nextChar.isLowercase || nextChar == "," {
            return false
        }

        return true
    }

    /// Index of the last genuine sentence terminal in `text`, scanning backwards.
    private static func lastSentenceTerminal(in text: String) -> String.Index? {
        guard !text.isEmpty else { return nil }
        var idx = text.index(before: text.endIndex)
        while true {
            let c = text[idx]
            if ".!?".contains(c) && isSentenceTerminal(c, at: idx, in: text) {
                return idx
            }
            guard idx > text.startIndex else { return nil }
            idx = text.index(before: idx)
        }
    }

    /// Index of the first genuine sentence terminal in `text`, scanning forwards.
    private static func firstSentenceTerminal(in text: String) -> String.Index? {
        for idx in text.indices where ".!?".contains(text[idx]) {
            if isSentenceTerminal(text[idx], at: idx, in: text) { return idx }
        }
        return nil
    }

    /// True if the last segment does not end with a standard sentence-terminal character.
    private func endsInMidSentence(_ segs: [String]) -> Bool {
        guard let last = segs.last else { return false }
        let plain = SefariaClient.stripHTML(last).trimmingCharacters(in: .whitespacesAndNewlines)
        guard let lastChar = plain.last else { return false }
        let terminals: Set<Character> = [".", "!", "?", ":", ";"]
        return !terminals.contains(lastChar)
    }

    // MARK: - Study content loading

    func loadStudyContentForCurrentSection() async {
        guard let session = session,
              session.currentSectionIndex < session.sections.count
        else { return }

        let idx = session.currentSectionIndex

        // Fast-path: already loaded (prefetch beat us here).
        guard session.sections[idx].summary == nil else { return }

        isLoadingStudyContent = true

        if loadingIndices.contains(idx) {
            // Wait-path: background prefetch is running — poll until done.
            while loadingIndices.contains(idx),
                  self.session?.sections[idx].summary == nil {
                try? await Task.sleep(nanoseconds: 300_000_000)
            }
            if self.session?.sections[idx].summary == nil {
                await fetchAndStoreContent(for: idx, surfaceError: true)
            }
        } else {
            await fetchAndStoreContent(for: idx, surfaceError: true)
        }

        isLoadingStudyContent = false
    }

    private func prefetchSection(at idx: Int) async {
        guard self.session != nil,
              idx < self.session!.sections.count,
              self.session!.sections[idx].summary == nil,
              !loadingIndices.contains(idx)
        else { return }

        loadingIndices.insert(idx)
        defer { loadingIndices.remove(idx) }

        await fetchAndStoreContent(for: idx, surfaceError: false)
    }

    /// - Parameters:
    ///   - surfaceError: show the error in the UI (true for user-triggered loads).
    ///   - attempt: 0 = first try, 1 = retry after rate-limit pause (no further retries).
    private func fetchAndStoreContent(for idx: Int, surfaceError: Bool, attempt: Int = 0) async {
        guard let session = self.session, idx < session.sections.count else { return }

        let tractate = session.tractate
        let daf = session.daf

        do {
            let shiurContext = ShiurClient.shared.shiurRewrite

            // Check shared cache first — returns nil on any failure (network, not found, etc.)
            if let cached = await StudyCache.shared.fetch(
                tractate: tractate, daf: daf, sectionIndex: idx,
                studyMode: studyMode, quizMode: quizMode
            ) {
                // Use cache if: already enriched with shiur, OR no shiur available to improve it.
                // Only regenerate when we can produce a better result.
                if cached.shiurUsed || shiurContext == nil {
                    guard self.session != nil, idx < self.session!.sections.count else { return }
                    if self.session!.sections[idx].summary == nil {
                        self.session!.sections[idx].summary = cached.summary
                        self.session!.sections[idx].quizQuestions = cached.questions
                    }
                    return
                }
                // cached.shiurUsed == false && shiurContext != nil:
                // fall through to regenerate with lecture context.
            }

            // Cache miss (or stale non-shiur entry) — call Claude
            let plainText = SefariaClient.stripHTML(session.sections[idx].rawText)
            let (summary, questions) = try await claudeClient.generateStudyContent(
                sectionTitle: session.sections[idx].title,
                sectionText: plainText,
                tractate: tractate,
                daf: daf,
                mode: studyMode,
                quizMode: quizMode,
                shiurContext: shiurContext
            )

            guard self.session != nil, idx < self.session!.sections.count else { return }

            if self.session!.sections[idx].summary == nil {
                self.session!.sections[idx].summary = summary
                self.session!.sections[idx].quizQuestions = questions

                // Write to shared cache (fire-and-forget — failure does not affect the user)
                Task {
                    await StudyCache.shared.store(
                        tractate: tractate, daf: daf, sectionIndex: idx,
                        studyMode: studyMode, quizMode: quizMode,
                        summary: summary, questions: questions,
                        shiurUsed: shiurContext != nil
                    )
                }
            }

        } catch {
            if surfaceError {
                if let claudeErr = error as? ClaudeClient.ClaudeError,
                   case .rateLimited = claudeErr,
                   attempt == 0 {
                    // First rate-limit hit: show a live countdown, then retry once.
                    isRateLimited = true
                    for remaining in stride(from: 65, through: 1, by: -1) {
                        // Stop countdown early if the user ends the session.
                        guard self.session != nil else {
                            isRateLimited = false
                            rateLimitCountdown = 0
                            return
                        }
                        rateLimitCountdown = remaining
                        try? await Task.sleep(nanoseconds: 1_000_000_000)
                    }
                    rateLimitCountdown = 0
                    isRateLimited = false
                    await fetchAndStoreContent(for: idx, surfaceError: true, attempt: 1)
                } else {
                    self.error = error.localizedDescription
                }
            }
            // surfaceError = false (background prefetch): silently drop rate-limit failures.
            // The section will be loaded on demand when the user reaches it.
        }
    }

    // MARK: - Navigation

    func advanceToNextSection() async {
        guard self.session != nil else { return }
        self.session!.currentSectionIndex += 1
        // Content loading is driven by StudyModeView's tab-aware onChange(of: currentSectionIndex)
        // observer — no eager Claude calls here so navigating the Translation tab stays free.
    }

    func goToPreviousSection() async {
        guard self.session != nil,
              self.session!.currentSectionIndex > 0 else { return }
        self.session!.currentSectionIndex -= 1
        // Content loading is driven by StudyModeView's tab-aware onChange observer.
    }

    func jumpToAmudA() async {
        guard self.session != nil else { return }
        self.session!.currentSectionIndex = 0
        // Content loading is driven by StudyModeView's tab-aware onChange observer.
    }

    func jumpToAmudB() async {
        guard self.session != nil,
              let idx = self.session!.amudBSectionIndex,
              idx < self.session!.sections.count
        else { return }
        self.session!.currentSectionIndex = idx
        // Content loading is driven by StudyModeView's tab-aware onChange observer.
    }

    // MARK: - Quiz — Multiple Choice

    func answerQuestion(questionIndex: Int, choiceIndex: Int) {
        guard var session = session else { return }
        let si = session.currentSectionIndex
        guard si < session.sections.count,
              questionIndex < session.sections[si].quizQuestions.count
        else { return }

        session.sections[si].quizQuestions[questionIndex].selectedIndex = choiceIndex
        self.session = session
    }

    // MARK: - Quiz — Flashcard

    func markFlashcard(questionIndex: Int, correct: Bool) {
        guard var session = session else { return }
        let si = session.currentSectionIndex
        guard si < session.sections.count,
              questionIndex < session.sections[si].quizQuestions.count
        else { return }

        session.sections[si].quizQuestions[questionIndex].selfMarkedCorrect = correct
        self.session = session
    }

    // MARK: - Quiz — Fill in the Blank

    func gradeAnswer(questionIndex: Int, userText: String) async {
        guard var session = session else { return }
        let si = session.currentSectionIndex
        guard si < session.sections.count,
              questionIndex < session.sections[si].quizQuestions.count
        else { return }

        // Mark as grading
        session.sections[si].quizQuestions[questionIndex].userText = userText
        session.sections[si].quizQuestions[questionIndex].isGrading = true
        self.session = session

        let question = session.sections[si].quizQuestions[questionIndex].question
        let correctAnswer = session.sections[si].quizQuestions[questionIndex].correctAnswer

        do {
            let result = try await claudeClient.gradeAnswer(
                question: question,
                correctAnswer: correctAnswer,
                userAnswer: userText,
                mode: quizMode
            )

            guard self.session != nil,
                  si < self.session!.sections.count,
                  questionIndex < self.session!.sections[si].quizQuestions.count
            else { return }

            self.session!.sections[si].quizQuestions[questionIndex].isGrading = false
            self.session!.sections[si].quizQuestions[questionIndex].gradeResult = result
        } catch {
            guard self.session != nil,
                  si < self.session!.sections.count,
                  questionIndex < self.session!.sections[si].quizQuestions.count
            else { return }

            self.session!.sections[si].quizQuestions[questionIndex].isGrading = false
            self.session!.sections[si].quizQuestions[questionIndex].gradeResult =
                GradeResult(isCorrect: false, feedback: "Grading failed. The answer was: \(correctAnswer)")
        }
    }

    // MARK: - Teardown

    func endSession() {
        session = nil
        error = nil
        isLoadingText = false
        isLoadingStudyContent = false
        loadingIndices = []
        isRateLimited = false
        rateLimitCountdown = 0
    }
}
