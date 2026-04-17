import SwiftUI

// MARK: - Adaptive study color environment
// fg:       foreground text/icon color (white on blue, .label on white)
// cardFill: subtle card/pill fill color

private struct StudyFgKey: EnvironmentKey      { static let defaultValue: Color = .white }
private struct StudyCardFillKey: EnvironmentKey { static let defaultValue: Color = .white.opacity(0.1) }

extension EnvironmentValues {
    fileprivate var studyFg: Color {
        get { self[StudyFgKey.self] }
        set { self[StudyFgKey.self] = newValue }
    }
    fileprivate var studyCardFill: Color {
        get { self[StudyCardFillKey.self] }
        set { self[StudyCardFillKey.self] = newValue }
    }
}

// MARK: - Study Mode Container

struct StudyModeView: View {
    @ObservedObject var manager: StudySessionManager
    @ObservedObject var readAloudManager: ReadAloudManager
    @ObservedObject private var resourcesManager = ResourcesManager.shared
    let onDismiss: () -> Void
    @State private var quizzedSectionIndices: Set<Int> = []
    /// Owned here so it survives loading-state transitions that unmount SectionStudyView.
    /// 0 = Translation, 1 = Summary, 2 = Quiz, 3 = Resources.
    @State private var selectedTab = 0

    // Article reader state — owned here so the overlay sits above the custom header.
    @State private var selectedArticle: YCTArticle? = nil
    @State private var articleHTML: String = ""
    @State private var isLoadingArticle = false

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @AppStorage("useWhiteBackground") private var useWhiteBackground: Bool = false
    private var studyBg: Color { useWhiteBackground ? .white : SplashView.background }
    private var studyFg: Color { useWhiteBackground ? Color(.label) : .white }
    private var studyCardFill: Color { useWhiteBackground ? Color(.systemGray5) : .white.opacity(0.1) }

    var body: some View {
        VStack(spacing: 0) {
            header

            // Read-Aloud (commented out — re-enable when ready)
//            if readAloudManager.isActive {
//                readAloudStatusBar
//            }

            if manager.isLoadingText {
                loadingState("Fetching text from Sefaria…")
            } else if let error = manager.error {
                errorState(error)
            } else if let session = manager.session {
                if session.isComplete {
                    completionState(session: session)
                } else if let section = session.currentSection {
                    SectionStudyView(
                        section: section,
                        tractate: session.tractate,
                        sectionNumber: session.currentSectionIndex + 1,
                        totalSections: session.sections.count,
                        studyMode: manager.studyMode,
                        isLoadingContent: manager.isLoadingStudyContent,
                        isRateLimited: manager.isRateLimited,
                        rateLimitCountdown: manager.rateLimitCountdown,
                        selectedTab: $selectedTab,
                        // Adjacent-daf context for mid-sentence continuations
                        precedingContext: session.currentSectionIndex == 0
                            ? session.precedingContext : nil,
                        followingContext: session.currentSectionIndex == session.sections.count - 1
                            ? session.followingContext : nil,
                        onAnswer: { qIdx, choice in
                            manager.answerQuestion(questionIndex: qIdx, choiceIndex: choice)
                        },
                        onMarkFlashcard: { qIdx, correct in
                            manager.markFlashcard(questionIndex: qIdx, correct: correct)
                        },
                        onSubmitFillBlank: { qIdx, text in
                            await manager.gradeAnswer(questionIndex: qIdx, userText: text)
                            guard let s = manager.session,
                                  s.currentSectionIndex < s.sections.count,
                                  qIdx < s.sections[s.currentSectionIndex].quizQuestions.count
                            else { return false }
                            return s.sections[s.currentSectionIndex].quizQuestions[qIdx].gradeResult?.isCorrect ?? false
                        },
                        onNext: {
                            Task { await manager.advanceToNextSection() }
                        },
                        onPrevious: {
                            Task { await manager.goToPreviousSection() }
                        },
                        onNextDaf: {
                            guard let s = manager.session else { return }
                            Task {
                                await manager.startSession(
                                    tractate: s.tractate,
                                    daf: s.daf + 1,
                                    mode: manager.studyMode,
                                    quizMode: manager.quizMode
                                )
                            }
                        },
                        onPreviousDaf: {
                            guard let s = manager.session, s.daf > 2 else { return }
                            Task {
                                await manager.startSession(
                                    tractate: s.tractate,
                                    daf: s.daf - 1,
                                    mode: manager.studyMode,
                                    quizMode: manager.quizMode,
                                    startAtLastSection: true
                                )
                            }
                        },
                        readAloudManager: readAloudManager,
                        resourcesManager: resourcesManager,
                        onArticleTapped: { article in
                            selectedArticle = article
                            articleHTML = ""
                            isLoadingArticle = true
                            Task {
                                do {
                                    let content = try await resourcesManager.fetchArticleContent(article: article)
                                    withAnimation { articleHTML = content }
                                } catch {
                                    articleHTML = "<p style='color:rgba(255,255,255,0.6)'>Could not load article. Please use \"Open in Browser\" below.</p>"
                                }
                                isLoadingArticle = false
                            }
                        }
                    )
                    // Load Summary/Quiz content when the user switches to those tabs,
                    // and track which sections have been quizzed for the score screen.
                    .onChange(of: selectedTab) { _, newTab in
                        if newTab == 1 || newTab == 2 {
                            Task { await manager.loadStudyContentForCurrentSection() }
                        }
                        if newTab == 2, let idx = manager.session?.currentSectionIndex {
                            quizzedSectionIndices.insert(idx)
                        }
                        if newTab == 3, let session = manager.session {
                            Task { await resourcesManager.loadResources(tractate: session.tractate, daf: session.daf) }
                        }
                    }
                    // Also load when navigating sections while already on Summary or Quiz tab.
                    .onChange(of: manager.session?.currentSectionIndex) { _, _ in
                        if selectedTab == 1 || selectedTab == 2 {
                            Task { await manager.loadStudyContentForCurrentSection() }
                        }
                        if selectedTab == 2, let idx = manager.session?.currentSectionIndex {
                            quizzedSectionIndices.insert(idx)
                        }
                    }
                }
            }
        }
        .background(studyBg)
        .environment(\.studyFg, studyFg)
        .environment(\.studyCardFill, studyCardFill)
        // Article reader — overlay here so it covers the custom header row too.
        .overlay {
            if let article = selectedArticle {
                ArticleReaderView(
                    article: article,
                    html: isLoadingArticle ? nil : (articleHTML.isEmpty ? nil : articleHTML),
                    onDismiss: {
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                            selectedArticle = nil
                        }
                    }
                )
                .transition(
                    .asymmetric(
                        insertion: .move(edge: .bottom).combined(with: .scale(scale: 0.92)).combined(with: .opacity),
                        removal:   .move(edge: .bottom).combined(with: .scale(scale: 0.92)).combined(with: .opacity)
                    )
                )
            }
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: selectedArticle?.id)
        // isLoadingText goes true→false once per startSession, on the OUTER VStack so it
        // fires even though SectionStudyView (where this logic was) doesn't exist while loading.
        .onChange(of: manager.isLoadingText) { _, isLoading in
            guard !isLoading, let session = manager.session else { return }
            resourcesManager.reset()
            if selectedTab == 3 {
                Task { await resourcesManager.loadResources(tractate: session.tractate, daf: session.daf) }
            }
        }
        // Read-Aloud (commented out — re-enable when ready)
//        .overlay(alignment: .bottom) {
//            if readAloudManager.isListening {
//                listeningOverlay
//                    .padding(.horizontal)
//                    .padding(.bottom, 12)
//            }
//        }
//        .onAppear {
//            readAloudManager.onSectionQuizzed = { idx in
//                quizzedSectionIndices.insert(idx)
//            }
//        }
//        .alert("Permission Required",
//               isPresented: $readAloudManager.permissionDenied) {
//            Button("Open Settings") {
//                if let url = URL(string: UIApplication.openSettingsURLString) {
//                    UIApplication.shared.open(url)
//                }
//            }
//            Button("Cancel", role: .cancel) { }
//        } message: {
//            Text("AnyDaf needs microphone and speech recognition access for Read-Aloud quiz mode. Please enable both in Settings.")
//        }
    }

    // MARK: - Header

    private var header: some View {
        ZStack {
            // Centered daf + amud + mode title
            if let session = manager.session {
                let onAmudB = session.amudBSectionIndex.map { session.currentSectionIndex >= $0 } ?? false
                Text("\(session.tractate) \(session.daf)\(onAmudB ? "b" : "a")")
                    .font(.headline)
                    .foregroundStyle(studyFg)
            }
            // Back button (left, iPhone only) + Jump to Amud B (right)
            HStack {
                if horizontalSizeClass != .regular {
                    Button {
                        onDismiss()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("Back")
                        }
                        .foregroundStyle(studyFg)
                    }
                }
                Spacer()

                if let session = manager.session,
                   let amudBIdx = session.amudBSectionIndex,
                   amudBIdx < session.sections.count {
                    let onAmudA = session.currentSectionIndex < amudBIdx
                    Button {
                        Task {
                            if onAmudA {
                                await manager.jumpToAmudB()
                            } else {
                                await manager.jumpToAmudA()
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            if !onAmudA {
                                Image(systemName: "chevron.left")
                                    .font(.caption2.bold())
                            }
                            Text(onAmudA ? "Amud b" : "Amud a")
                            if onAmudA {
                                Image(systemName: "chevron.right")
                                    .font(.caption2.bold())
                            }
                        }
                        .font(.subheadline.bold())
                        .foregroundStyle(studyFg)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(
                            Capsule()
                                .fill(studyFg.opacity(0.15))
                        )
                    }
                    .disabled(manager.isLoadingStudyContent)
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
    }

    // MARK: - Read-Aloud UI

    private var readAloudStatusBar: some View {
        HStack(spacing: 10) {
            Image(systemName: readAloudManager.isListening ? "mic.fill" : "speaker.wave.2.fill")
                .foregroundStyle(readAloudManager.isListening ? .red : .green)
                .frame(width: 20)

            Text(readAloudManager.phase.displayText)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.9))
                .lineLimit(1)

            Spacer()

            if readAloudManager.isPaused {
                Text("Paused")
                    .font(.caption2)
                    .foregroundStyle(.yellow.opacity(0.9))
            }

            // Skip-forward — advances past the current utterance
            Button {
                readAloudManager.skipForward()
            } label: {
                Image(systemName: "forward.fill")
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.8))
                    .frame(width: 40, height: 36)
            }

            // Pause / Resume — large tap target suitable for driving
            Button {
                readAloudManager.togglePauseResume()
            } label: {
                Image(systemName: readAloudManager.isPaused ? "play.fill" : "pause.fill")
                    .font(.body)
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 36)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.40))
    }

    private var listeningOverlay: some View {
        HStack(spacing: 10) {
            Image(systemName: "mic.fill")
                .foregroundStyle(.red)
            Text(readAloudManager.recognizedText.isEmpty
                 ? "Listening…"
                 : readAloudManager.recognizedText)
                .foregroundStyle(.white)
                .lineLimit(2)
                .font(.body)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial)
        .cornerRadius(16)
    }

    // MARK: - Loading

    private func loadingState(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView()
                .tint(studyFg)
            Text(message)
                .foregroundStyle(studyFg.opacity(0.8))
            Spacer()
        }
    }

    // MARK: - Error

    private func errorState(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.yellow)
            Text(message)
                .foregroundStyle(studyFg.opacity(0.8))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            if horizontalSizeClass != .regular {
                Button("Dismiss") { onDismiss() }
                    .buttonStyle(.borderedProminent)
            }
            Spacer()
        }
    }

    // MARK: - Completion

    private func completionState(session: StudySession) -> some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundStyle(.green)
            Text("Study Complete!")
                .font(.title2.bold())
                .foregroundStyle(studyFg)

            let quizzedQuestions = session.sections
                .enumerated()
                .filter { quizzedSectionIndices.contains($0.offset) }
                .flatMap { $0.element.quizQuestions }
            let correct = quizzedQuestions.filter { $0.isCorrect }.count
            let total = quizzedQuestions.count
            if total > 0 {
                Text("\(correct)/\(total) questions correct")
                    .font(.title3)
                    .foregroundStyle(studyFg.opacity(0.8))
            }

            if horizontalSizeClass != .regular {
                Button("Back to Daf") { onDismiss() }
                    .buttonStyle(.borderedProminent)
            }
            Spacer()
        }
    }
}

// MARK: - Section Study View

struct SectionStudyView: View {
    let section: StudySection
    let tractate: String
    let sectionNumber: Int
    let totalSections: Int
    let studyMode: StudyMode
    let isLoadingContent: Bool
    /// True while the manager is waiting out a rate-limit backoff.
    let isRateLimited: Bool
    /// Seconds remaining in the current rate-limit countdown.
    let rateLimitCountdown: Int
    /// 0 = Translation, 1 = Summary, 2 = Quiz. Owned by StudyModeView so it survives transitions.
    @Binding var selectedTab: Int
    /// Tail of the previous daf — non-nil only for the very first section when it starts mid-sentence.
    let precedingContext: String?
    /// Head of the next daf — non-nil only for the very last section when it ends mid-sentence.
    let followingContext: String?
    let onAnswer: (Int, Int) -> Void
    let onMarkFlashcard: (Int, Bool) -> Void
    let onSubmitFillBlank: (Int, String) async -> Bool
    let onNext: () -> Void
    let onPrevious: () -> Void
    let onNextDaf: () -> Void
    let onPreviousDaf: () -> Void
    @ObservedObject var readAloudManager: ReadAloudManager

    @ObservedObject var resourcesManager: ResourcesManager
    let onArticleTapped: (YCTArticle) -> Void

    @AppStorage("sourceDisplayMode") private var sourceDisplayMode: SourceDisplayMode = .toggle
    @AppStorage("studyFontSize") private var studyFontSize: StudyFontSize = .medium
    @Environment(\.studyFg)            private var fg
    @Environment(\.studyCardFill)      private var cardFill
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    @State private var revealedCount: Int = 1
    @State private var showHebrew = true

    // Scroll anchor IDs
    private let topID = "sectionTop"
    private let quizTopID = "quizTop"
    private func questionID(_ idx: Int) -> String { "question_\(idx)" }
    private let nextButtonID = "nextButton"

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Static header — stays on screen while quiz questions scroll past.
            VStack(alignment: .leading, spacing: 20) {
                // Section header
                HStack {
                    Text("Section \(sectionNumber)/\(totalSections)")
                        .font(.caption)
                        .foregroundStyle(fg.opacity(0.6))
                    Spacer()
                    // Read-Aloud button (commented out — re-enable when ready)
//                        Button {
//                            if readAloudManager.isActive {
//                                readAloudManager.stopReadAloud()
//                            } else {
//                                Task { await readAloudManager.startReadAloud() }
//                            }
//                        } label: {
//                            Image(systemName: readAloudManager.isActive
//                                  ? "speaker.wave.3.fill"
//                                  : "speaker.wave.2")
//                                .foregroundStyle(readAloudManager.isActive ? .green : .white)
//                                .font(.title3)
//                        }
                }

                // Translation / Summary / Quiz / Resources tab pill
                HStack(spacing: 0) {
                    tabPillButton("Text",      tag: 0)
                    tabPillButton("Summary",   tag: 1)
                    tabPillButton("Quiz",      tag: 2)
                    tabPillButton("Resources", tag: 3)
                }
                .padding(.trailing, 8)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(fg.opacity(0.22), lineWidth: 0.5)
                )
                .padding(.horizontal, 4)
            }
            .padding([.horizontal, .top])
            .padding(.bottom, 8)
            .frame(maxWidth: horizontalSizeClass == .regular ? 700 : .infinity)
            .frame(maxWidth: .infinity)

            // Scrollable content — quiz questions advance within this area only.
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        Color.clear.frame(height: 0).id(topID)

                        switch selectedTab {
                        case 1:
                            summaryTabContent(proxy: proxy)
                        case 2:
                            quizTabContent(proxy: proxy)
                        case 3:
                            resourcesTabContent
                        default:
                            translationCard
                        }
                    }
                    .padding([.horizontal, .bottom])
                    .frame(maxWidth: horizontalSizeClass == .regular ? 700 : .infinity)
                    .frame(maxWidth: .infinity)
                }
                .dynamicTypeSize(studyFontSize.dynamicTypeSize)
                // Lets the scroll view co-exist cleanly with the keyboard —
                // reduces the layout-recalculation lag on first text-field focus.
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: section.id) { _, _ in
                    // showHebrew intentionally NOT reset — user's language toggle persists across sections.
                    // selectedTab intentionally NOT reset — user stays in
                    // whichever tab they were in when they advance or jump amud.
                    revealedCount = 1
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        proxy.scrollTo(topID, anchor: .top)
                    }
                }
            // Read-Aloud view-request handler (commented out — re-enable when ready)
//            .onChange(of: readAloudManager.viewRequest) { _, request in
//                guard readAloudManager.isActive else { return }
//                switch request.target {
//                case .translation:
//                    withAnimation(.easeInOut(duration: 0.18)) { showTranslation = true }
//                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
//                        proxy.scrollTo(topID, anchor: .top)
//                    }
//                case .study:
//                    withAnimation(.easeInOut(duration: 0.18)) { showTranslation = false }
//                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
//                        proxy.scrollTo(topID, anchor: .top)
//                    }
//                case .quiz:
//                    withAnimation(.easeInOut(duration: 0.18)) { showTranslation = false }
//                    if !showQuiz {
//                        onStartQuiz()
//                        withAnimation { showQuiz = true }
//                        // Reveal all questions at once for read-aloud (flow controls pacing)
//                        revealedCount = section.quizQuestions.count
//                    }
//                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
//                        withAnimation { proxy.scrollTo(quizTopID, anchor: .top) }
//                    }
//                }
//            }
            }
        }
    }

    @ViewBuilder
    private func questionView(for question: QuizQuestion, idx: Int, proxy: ScrollViewProxy) -> some View {
        switch question.mode {
        case .multipleChoice:
            QuizQuestionView(
                question: question,
                questionNumber: idx + 1,
                onSelect: { choice in
                    onAnswer(idx, choice)
                    let isCorrect = choice == section.quizQuestions[idx].correctIndex
                    let delay: Double = isCorrect ? 0.5 : 2.5
                    DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                        advanceAfterAnswer(idx: idx, proxy: proxy)
                    }
                }
            )

        case .flashcard:
            FlashcardQuestionView(
                question: question,
                questionNumber: idx + 1,
                onMark: { correct in
                    onMarkFlashcard(idx, correct)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                        advanceAfterAnswer(idx: idx, proxy: proxy)
                    }
                }
            )

        case .fillInBlank:
            FillBlankQuestionView(
                question: question,
                questionNumber: idx + 1,
                onSubmit: { text in
                    Task { @MainActor in
                        let isCorrect = await onSubmitFillBlank(idx, text)
                        // 1 s on correct (time to read feedback), 2.5 s on wrong
                        let delay: Double = isCorrect ? 1.0 : 2.5
                        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                        advanceAfterAnswer(idx: idx, proxy: proxy)
                    }
                }
            )

        case .shortAnswer:
            ShortAnswerQuestionView(
                question: question,
                questionNumber: idx + 1,
                onSubmit: { text in
                    Task { @MainActor in
                        let isCorrect = await onSubmitFillBlank(idx, text)
                        // 3 s on correct, 4 s on wrong (model answer shown, needs more reading time)
                        let delay: Double = isCorrect ? 3.0 : 4.0
                        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                        advanceAfterAnswer(idx: idx, proxy: proxy)
                    }
                }
            )
        }
    }

    @ViewBuilder
    private func quizContent(proxy: ScrollViewProxy) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Color.clear.frame(height: 0).id(quizTopID)

            ForEach(Array(section.quizQuestions.prefix(revealedCount).enumerated()), id: \.offset) { idx, question in
                questionView(for: question, idx: idx, proxy: proxy)
                    .id(questionID(idx))
            }

            if allQuestionsAnswered {
                let correct = section.quizQuestions.filter { $0.isCorrect }.count
                let total = section.quizQuestions.count
                let isLastSection = sectionNumber >= totalSections

                VStack(spacing: 12) {
                    Text("\(correct)/\(total) correct")
                        .font(.headline)
                        .foregroundStyle(correct == total ? .green : .yellow)

                    HStack(spacing: 12) {
                        if sectionNumber > 1 {
                            Button { onPrevious() } label: {
                                Label("Previous", systemImage: "arrow.left")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                            .tint(fg)
                        }
                        Button { onNext() } label: {
                            Text(isLastSection ? "Finish" : "Next")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(.top, 8)
                .id(nextButtonID)
            }

            Color.clear.frame(height: 600)
        }
    }

    private func advanceAfterAnswer(idx: Int, proxy: ScrollViewProxy) {
        if idx + 1 < section.quizQuestions.count {
            revealedCount = idx + 2
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                withAnimation {
                    proxy.scrollTo(questionID(idx + 1), anchor: .top)
                }
            }
        } else {
            withAnimation {
                proxy.scrollTo(nextButtonID, anchor: .top)
            }
        }
    }

    private var allQuestionsAnswered: Bool {
        section.quizQuestions.allSatisfy { $0.isAnswered }
    }

    // MARK: - Tab pill helper

    private func tabPillButton(_ title: String, tag: Int) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.18)) { selectedTab = tag }
        } label: {
            Text(title)
                .font(.footnote.bold())
                .lineLimit(1)
                .minimumScaleFactor(0.85)   // shrinks slightly rather than truncating on small screens
                .foregroundStyle(fg)
                // Padding and background applied before the frame so the highlight
                // wraps the text proportionally: "Text" gets a narrow chip,
                // "Resources" gets a wider one — each centred in its equal-width slot.
                .padding(.horizontal, 4)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(selectedTab == tag ? fg.opacity(0.28) : Color.clear)
                )
                .frame(maxWidth: .infinity)
        }
    }

    // MARK: - Skeleton views

    /// Animated placeholder card matching the summary layout.
    @ViewBuilder
    private var summarySkeleton: some View {
        VStack(alignment: .leading, spacing: 8) {
            SkeletonBlock(widthFraction: 0.32, height: 16, color: fg)
            Spacer().frame(height: 2)
            SkeletonBlock(widthFraction: 1.00, color: fg)
            SkeletonBlock(widthFraction: 0.92, color: fg)
            SkeletonBlock(widthFraction: 1.00, color: fg)
            SkeletonBlock(widthFraction: 0.75, color: fg)
            SkeletonBlock(widthFraction: 0.85, color: fg)
            SkeletonBlock(widthFraction: 0.60, color: fg)
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(cardFill))
    }

    /// Animated placeholder cards matching the quiz layout (3 MC questions).
    @ViewBuilder
    private var quizSkeleton: some View {
        VStack(alignment: .leading, spacing: 16) {
            quizSkeletonQuestion(choices: [0.70, 0.55, 0.80, 0.60])
            quizSkeletonQuestion(choices: [0.65, 0.80, 0.50, 0.75])
            quizSkeletonQuestion(choices: [0.75, 0.60, 0.85, 0.55])
        }
    }

    @ViewBuilder
    private func quizSkeletonQuestion(choices: [CGFloat]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            SkeletonBlock(widthFraction: 1.00, color: fg)
            SkeletonBlock(widthFraction: 0.70, color: fg)
            Spacer().frame(height: 2)
            ForEach(Array(choices.enumerated()), id: \.offset) { _, w in
                HStack(spacing: 8) {
                    Circle()
                        .fill(fg.opacity(0.28))
                        .frame(width: 16, height: 16)
                    SkeletonBlock(widthFraction: w, color: fg)
                }
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(cardFill))
    }

    // MARK: - Summary tab

    @ViewBuilder
    private func summaryTabContent(proxy: ScrollViewProxy) -> some View {
        if isLoadingContent || section.summary == nil {
            if isRateLimited {
                VStack(spacing: 12) {
                    ProgressView().tint(fg)
                    Text("Too many requests — please wait (\(rateLimitCountdown)s)…")
                        .font(.caption)
                        .foregroundStyle(.yellow.opacity(0.85))
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else {
                summarySkeleton
            }
        } else if let summary = section.summary {
            VStack(alignment: .leading, spacing: 12) {
                // Summary card
                VStack(alignment: .leading, spacing: 8) {
                    Label("Summary", systemImage: "text.book.closed")
                        .font(.headline)
                        .foregroundStyle(fg)
                    Text(summary)
                        .foregroundStyle(fg.opacity(0.9))
                        .lineSpacing(4)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(cardFill)
                )

                // Navigation buttons
                HStack(spacing: 12) {
                    if sectionNumber > 1 {
                        Button { onPrevious() } label: {
                            Label("Previous", systemImage: "arrow.left")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .tint(fg)
                    }
                    if sectionNumber < totalSections {
                        Button { onNext() } label: {
                            Label("Next", systemImage: "arrow.right")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
            }
        }
        // If neither loading nor loaded, the onChange will trigger the load — no extra button needed.
    }

    // MARK: - Quiz tab

    @ViewBuilder
    private func quizTabContent(proxy: ScrollViewProxy) -> some View {
        if isLoadingContent || section.quizQuestions.isEmpty {
            if isRateLimited {
                VStack(spacing: 12) {
                    ProgressView().tint(fg)
                    Text("Too many requests — please wait (\(rateLimitCountdown)s)…")
                        .font(.caption)
                        .foregroundStyle(.yellow.opacity(0.85))
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else {
                quizSkeleton
            }
        } else {
            quizContent(proxy: proxy)
        }
    }

    // MARK: - Translation View

    /// Highlight colour for direct Aramaic/Hebrew translation words.
    /// Amber on the dark-blue background; dark indigo on the white background.
    @AppStorage("useWhiteBackground") private var _editorialUseWhite: Bool = false
    private var editorialColor: Color {
        _editorialUseWhite
            ? Color(red: 0.10, green: 0.20, blue: 0.60)   // dark indigo — readable on white
            : Color(red: 0.94, green: 0.80, blue: 0.45)   // amber — readable on dark blue
    }
    /// Colour for the "added" (non-direct, explanatory) translation text.
    /// On the white background it is softened to a secondary grey so the coloured
    /// direct-translation words stand out more clearly.
    private var addedTextColor: Color {
        _editorialUseWhite ? Color(.secondaryLabel) : fg
    }
    /// Muted colour for bracketed context from adjacent dafs.
    private var contextColor: Color { fg.opacity(0.42) }

    /// Full translation body with optional adjacent-daf context in brackets.
    private var translationBody: Text {
        let mainText = buildTranslationText(from: parseTranslationHTML(section.rawText))

        let withPreceding: Text
        if let ctx = precedingContext {
            withPreceding = Text("[")     .foregroundColor(contextColor)
                          + Text(ctx)     .foregroundColor(contextColor).italic()
                          + Text("] ")    .foregroundColor(contextColor)
                          + mainText
        } else {
            withPreceding = mainText
        }

        if let ctx = followingContext {
            return withPreceding
                 + Text(" [")  .foregroundColor(contextColor)
                 + Text(ctx)   .foregroundColor(contextColor).italic()
                 + Text("]")   .foregroundColor(contextColor)
        }
        return withPreceding
    }

    // MARK: Translation card sub-views

    /// Source | Translation toggle pill (toggle mode only).
    private var languageTogglePill: some View {
        HStack(spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.18)) { showHebrew = true }
            } label: {
                Text("Source")
                    .font(.caption.bold())
                    .foregroundStyle(fg)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(showHebrew ? fg.opacity(0.28) : Color.clear)
                    )
            }
            Button {
                withAnimation(.easeInOut(duration: 0.18)) { showHebrew = false }
            } label: {
                Text("Translation")
                    .font(.caption.bold())
                    .foregroundStyle(fg)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(!showHebrew ? fg.opacity(0.28) : Color.clear)
                    )
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 8)
                .stroke(fg.opacity(0.22), lineWidth: 0.5)
        )
    }

    /// Colour key for the English translation (Direct / Added).
    private var colorLegend: some View {
        HStack(spacing: 10) {
            legendDot(color: editorialColor, label: "Direct")
            legendDot(color: fg,                  label: "Added")
        }
    }

    /// Styled English translation text (full section, with preceding/following context).
    private var englishTextView: some View {
        translationBody
            .lineSpacing(6)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Builds a `Text` for a single English HTML segment, optionally wrapping
    /// preceding/following daf context in muted italic brackets.
    private func englishSegmentText(_ html: String,
                                    preceding: String? = nil,
                                    following: String? = nil) -> Text {
        let base = buildTranslationText(from: parseTranslationHTML(html))
        let withPre: Text
        if let ctx = preceding {
            withPre = Text("[")    .foregroundColor(contextColor)
                    + Text(ctx)    .foregroundColor(contextColor).italic()
                    + Text("] ")   .foregroundColor(contextColor)
                    + base
        } else {
            withPre = base
        }
        if let ctx = following {
            return withPre
                 + Text(" [")  .foregroundColor(contextColor)
                 + Text(ctx)   .foregroundColor(contextColor).italic()
                 + Text("]")   .foregroundColor(contextColor)
        }
        return withPre
    }

    /// Styled English text for a single HTML segment, with optional adjacent-daf context.
    private func englishSegmentView(_ html: String,
                                    preceding: String? = nil,
                                    following: String? = nil) -> some View {
        englishSegmentText(html, preceding: preceding, following: following)
            .lineSpacing(4)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Dashed separator used between Hebrew and English within a stacked paragraph pair.
    private var stackedSeparator: some View {
        GeometryReader { geo in
            Path { path in
                path.move(to: .zero)
                path.addLine(to: CGPoint(x: geo.size.width, y: 0))
            }
            .stroke(style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
            .foregroundColor(fg.opacity(0.45))
        }
        .frame(height: 1)
    }

    /// Styled Hebrew/Aramaic text — RTL via U+200F paragraph mark.
    private func hebrewTextView(_ hebrewText: String) -> some View {
        Text("\u{200F}" + SefariaClient.stripHTML(hebrewText))
            .foregroundStyle(fg.opacity(0.95))
            .lineSpacing(8)
            .frame(maxWidth: .infinity, alignment: .trailing)
            .multilineTextAlignment(.trailing)
    }

    /// Styled Hebrew/Aramaic text for a single segment — RTL via U+200F.
    private func hebrewSegmentView(_ html: String) -> some View {
        Text("\u{200F}" + SefariaClient.stripHTML(html))
            .foregroundStyle(fg.opacity(0.95))
            .lineSpacing(6)
            .frame(maxWidth: .infinity, alignment: .trailing)
            .multilineTextAlignment(.trailing)
    }

    /// Stacked: segment pairs rendered together (Hebrew above, English below per paragraph).
    /// Both languages are visible simultaneously — user scrolls through matched pairs
    /// rather than seeing all Hebrew then all English.
    @ViewBuilder
    private func stackedContent(hebrewText: String) -> some View {
        let pairs = Array(zip(section.rawSegments, section.hebrewSegments))
        if pairs.isEmpty {
            // Fallback: Hebrew block then English block
            VStack(alignment: .leading, spacing: 10) {
                hebrewTextView(hebrewText)
                Divider().background(fg.opacity(0.3))
                VStack(alignment: .leading, spacing: 4) {
                    colorLegend
                    englishTextView
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 14) {
                ForEach(pairs.indices, id: \.self) { idx in
                    VStack(alignment: .leading, spacing: 8) {
                        // Hebrew on top
                        hebrewSegmentView(pairs[idx].1)
                        // Dashed divider between languages
                        stackedSeparator
                        // English below
                        englishSegmentView(
                            pairs[idx].0,
                            preceding: idx == 0 ? precedingContext : nil,
                            following: idx == pairs.count - 1 ? followingContext : nil
                        )
                    }
                    .padding(.vertical, 6)
                    .padding(.horizontal, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(fg.opacity(0.04))
                    )
                    // Separator between paragraph pairs
                    if idx < pairs.count - 1 {
                        Divider()
                            .background(fg.opacity(0.12))
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var translationCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Header row — only shown for English-only and toggle mode
            if section.hebrewText == nil {
                // English only: title + color legend
                HStack {
                    Label("Translation", systemImage: "scroll")
                        .font(.headline)
                        .foregroundStyle(fg)
                    Spacer()
                    colorLegend
                }
                Divider()
                    .background(fg.opacity(0.3))
            } else if sourceDisplayMode == .toggle {
                // Toggle mode: pill on the left IS the header — no separate title
                HStack {
                    languageTogglePill
                    Spacer()
                }
                Divider()
                    .background(fg.opacity(0.3))
            } else if sourceDisplayMode == .stacked {
                // Stacked mode: legend on the right so users can see the colour key
                HStack {
                    Spacer()
                    colorLegend
                }
                Divider()
                    .background(fg.opacity(0.3))
            }

            // Content — switches on display mode
            if let hebrewText = section.hebrewText {
                switch sourceDisplayMode {
                case .toggle:
                    if showHebrew {
                        hebrewTextView(hebrewText)
                    } else {
                        VStack(alignment: .leading, spacing: 6) {
                            colorLegend
                            englishTextView
                        }
                    }
                case .stacked:
                    stackedContent(hebrewText: hebrewText)
                }
            } else {
                // No Hebrew — English only
                translationBody
                    .lineSpacing(6)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Divider()
                .background(fg.opacity(0.3))

            HStack(spacing: 12) {
                // Left button: "Prev Daf" on the first section, "Previous" otherwise
                if sectionNumber == 1 {
                    Button { onPreviousDaf() } label: {
                        Label("Prev Daf", systemImage: "arrow.left")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(fg)
                } else {
                    Button { onPrevious() } label: {
                        Label("Previous", systemImage: "arrow.left")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(fg)
                }

                // Right button: "Next" within the daf, "Next Daf" on the last section
                if sectionNumber < totalSections {
                    Button { onNext() } label: {
                        Label("Next", systemImage: "arrow.right")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button { onNextDaf() } label: {
                        Label("Next Daf", systemImage: "arrow.right")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(cardFill)
        )
    }

    private func legendDot(color: Color, label: String) -> some View {
        HStack(spacing: 3) {
            Circle()
                .fill(color)
                .frame(width: 7, height: 7)
            Text(label)
                .font(.caption2)
                .foregroundStyle(fg.opacity(0.65))
        }
    }

    // MARK: - HTML Parsing

    private struct TranslationSegment {
        let text: String
        let isDirect: Bool   // true = literal Aramaic/Hebrew translation (was bold in HTML)
    }

    private func parseTranslationHTML(_ html: String) -> [TranslationSegment] {
        var segments: [TranslationSegment] = []

        // Strip section-header bold tags (e.g. <strong>GEMARA:</strong>) — the section
        // title is already shown above so we don't repeat it here.
        var cleaned = html.replacingOccurrences(
            of: #"<(?:strong|b)>[A-Z][A-Z ]*:?</(?:strong|b)>"#,
            with: "", options: .regularExpression)

        // Normalise line-breaks
        for br in ["<br/>", "<br />", "<br>"] {
            cleaned = cleaned.replacingOccurrences(of: br, with: "\n")
        }

        // Find all remaining bold spans — these are the direct Aramaic/Hebrew translations
        let boldPattern = #"<(?:b|strong)>(.*?)</(?:b|strong)>"#
        guard let regex = try? NSRegularExpression(
                pattern: boldPattern, options: [.dotMatchesLineSeparators]) else {
            return [TranslationSegment(text: SefariaClient.stripHTML(html), isDirect: false)]
        }

        let ns = cleaned as NSString
        let matches = regex.matches(in: cleaned,
                                    range: NSRange(location: 0, length: ns.length))
        var lastEnd = 0

        for match in matches {
            // Non-bold text before this match (editorial additions)
            if match.range.location > lastEnd {
                let raw = ns.substring(with: NSRange(location: lastEnd,
                                                     length: match.range.location - lastEnd))
                let s = SefariaClient.stripHTML(raw)
                if !s.trimmingCharacters(in: .whitespaces).isEmpty {
                    segments.append(.init(text: s, isDirect: false))
                }
            }
            // Bold span (direct translation)
            if let r = Range(match.range(at: 1), in: cleaned) {
                let s = SefariaClient.stripHTML(String(cleaned[r]))
                if !s.isEmpty { segments.append(.init(text: s, isDirect: true)) }
            }
            lastEnd = match.range.location + match.range.length
        }

        // Trailing non-bold text
        if lastEnd < ns.length {
            let raw = ns.substring(with: NSRange(location: lastEnd,
                                                 length: ns.length - lastEnd))
            let s = SefariaClient.stripHTML(raw)
            if !s.trimmingCharacters(in: .whitespaces).isEmpty {
                segments.append(.init(text: s, isDirect: false))
            }
        }

        return segments
    }

    private func buildTranslationText(from segments: [TranslationSegment]) -> Text {
        // Shekalim (Jerusalem Talmud) uses no bold/direct markers, so render all text
        // in the direct/highlight color rather than the muted "added" color.
        let allDirect = tractate == "Shekalim"
        return segments.reduce(Text("")) { acc, seg in
            acc + Text(seg.text)
                .foregroundColor((seg.isDirect || allDirect) ? editorialColor : addedTextColor)
        }
    }

    // MARK: - Resources tab

    @ViewBuilder
    private var resourcesTabContent: some View {
        if resourcesManager.isLoading {
            VStack(spacing: 12) {
                ProgressView().tint(fg)
                Text("Loading articles…")
                    .font(.caption)
                    .foregroundStyle(fg.opacity(0.7))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 40)
        } else if !resourcesManager.hasAnyArticles {
            VStack(spacing: 16) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.largeTitle)
                    .foregroundStyle(fg.opacity(0.4))
                Text("No articles found for this tractate")
                    .foregroundStyle(fg.opacity(0.65))
                    .multilineTextAlignment(.center)
                if let error = resourcesManager.error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red.opacity(0.8))
                        .multilineTextAlignment(.center)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 40)
        } else {
            let exact = resourcesManager.exactArticles
            let nearby = resourcesManager.nearbyArticles
            let tractate = resourcesManager.tractateArticles

            VStack(alignment: .leading, spacing: 12) {
                // Tier 1: exact daf
                if !exact.isEmpty {
                    resourcesSectionHeader("On the daf")
                    ForEach(exact) { article in articleCard(article) }
                }

                // Separator between tiers
                if !exact.isEmpty && (!nearby.isEmpty || !tractate.isEmpty) {
                    resourcesSectionDivider()
                }

                // Tier 2: nearby ±2 dafs
                if !nearby.isEmpty {
                    resourcesSectionHeader("In the vicinity")
                    ForEach(nearby) { article in articleCard(article) }
                }

                if !nearby.isEmpty && !tractate.isEmpty {
                    resourcesSectionDivider()
                }

                // Tier 3: all tractate articles in daf order
                if !tractate.isEmpty {
                    resourcesSectionHeader("On the tractate")
                    ForEach(tractate) { article in articleCard(article) }
                }
            }
        }
    }

    @ViewBuilder
    private func resourcesSectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.caption.bold())
            .foregroundStyle(fg.opacity(0.55))
            .textCase(.uppercase)
            .kerning(0.8)
            .padding(.top, 4)
    }

    private func resourcesSectionDivider() -> some View {
        HStack {
            Rectangle()
                .fill(fg.opacity(0.5))
                .frame(height: 1)
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func articleCard(_ article: YCTArticle) -> some View {
        let opacity: Double = {
            switch article.matchType {
            case .exact:        return 1.0
            case .nearby:       return 0.8
            case .tractateWide: return 0.8
            }
        }()

        Button {
            onArticleTapped(article)
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top) {
                    Text(article.title)
                        .font(.subheadline.bold())
                        .foregroundStyle(fg)
                        .multilineTextAlignment(.leading)
                    Spacer()
                    HStack(spacing: 4) {
                        ForEach(
                            ([article.matchType.referencedDaf] + article.additionalDafs)
                                .filter { $0 > 0 }.sorted(),
                            id: \.self
                        ) { d in
                            Text("Daf \(d)")
                                .font(.caption2)
                                .foregroundStyle(fg.opacity(0.65))
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(
                                    RoundedRectangle(cornerRadius: 4).fill(fg.opacity(0.15))
                                )
                        }
                    }
                }
                if !article.authorName.isEmpty {
                    Text(article.authorName)
                        .font(.caption)
                        .foregroundStyle(fg.opacity(0.65))
                }
                if !article.excerpt.isEmpty {
                    Text(article.excerpt)
                        .font(.caption)
                        .foregroundStyle(fg.opacity(0.75))
                        .lineLimit(3)
                }
                Text(article.date)
                    .font(.caption2)
                    .foregroundStyle(fg.opacity(0.45))
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(cardFill)
            )
        }
        .opacity(opacity)
    }
}

// MARK: - Multiple Choice Question View

struct QuizQuestionView: View {
    @Environment(\.studyFg)       private var fg
    @Environment(\.studyCardFill) private var cardFill
    let question: QuizQuestion
    let questionNumber: Int
    let onSelect: (Int) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Q\(questionNumber): \(question.question)")
                .font(.subheadline.bold())
                .foregroundStyle(fg)

            ForEach(Array(question.choices.enumerated()), id: \.offset) { idx, choice in
                Button {
                    if !question.isAnswered {
                        onSelect(idx)
                    }
                } label: {
                    HStack {
                        Text(choice)
                            .foregroundStyle(fg)
                            .multilineTextAlignment(.leading)
                        Spacer()
                        if question.isAnswered {
                            if idx == question.correctIndex {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(.green)
                            } else if idx == question.selectedIndex {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.red)
                            }
                        }
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(choiceBackground(idx))
                    )
                }
                .disabled(question.isAnswered)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(fg.opacity(0.08))
        )
    }

    private func choiceBackground(_ idx: Int) -> Color {
        guard question.isAnswered else {
            return fg.opacity(0.1)
        }
        if idx == question.correctIndex {
            return .green.opacity(0.2)
        }
        if idx == question.selectedIndex {
            return .red.opacity(0.2)
        }
        return fg.opacity(0.05)
    }
}

// MARK: - Flashcard Question View

struct FlashcardQuestionView: View {
    @Environment(\.studyFg)       private var fg
    @Environment(\.studyCardFill) private var cardFill
    let question: QuizQuestion
    let questionNumber: Int
    let onMark: (Bool) -> Void

    @State private var showAnswer = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Q\(questionNumber): \(question.question)")
                .font(.subheadline.bold())
                .foregroundStyle(fg)

            if question.isAnswered {
                // Final state after self-grading
                HStack {
                    Image(systemName: question.isCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(question.isCorrect ? .green : .red)
                    Text(question.correctAnswer)
                        .foregroundStyle(fg.opacity(0.9))
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 8)
                    .fill(question.isCorrect ? .green.opacity(0.2) : .red.opacity(0.2)))
            } else if !showAnswer {
                Button {
                    withAnimation { showAnswer = true }
                } label: {
                    Label("Show Answer", systemImage: "eye")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .foregroundStyle(fg)
            } else {
                // Answer revealed — user self-grades
                Text(question.correctAnswer)
                    .foregroundStyle(fg.opacity(0.9))
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 8).fill(fg.opacity(0.15)))

                HStack(spacing: 16) {
                    Button {
                        onMark(false)
                    } label: {
                        Label("Didn't know", systemImage: "xmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red.opacity(0.7))

                    Button {
                        onMark(true)
                    } label: {
                        Label("Knew it", systemImage: "checkmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green.opacity(0.7))
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(fg.opacity(0.08))
        )
    }
}

// MARK: - Fill-in-the-Blank Question View

struct FillBlankQuestionView: View {
    @Environment(\.studyFg)       private var fg
    @Environment(\.studyCardFill) private var cardFill
    let question: QuizQuestion
    let questionNumber: Int
    let onSubmit: (String) -> Void

    @State private var inputText = ""
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Q\(questionNumber): \(question.question)")
                .font(.subheadline.bold())
                .foregroundStyle(fg)

            if question.isGrading {
                HStack(spacing: 8) {
                    ProgressView().tint(fg)
                    Text("Grading…")
                        .foregroundStyle(fg.opacity(0.7))
                        .font(.caption)
                }
            } else if let result = question.gradeResult {
                // Show grading result
                HStack(alignment: .top) {
                    Image(systemName: result.isCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(result.isCorrect ? .green : .red)
                    VStack(alignment: .leading, spacing: 2) {
                        if let userText = question.userText {
                            Text("Your answer: \(userText)")
                                .foregroundStyle(fg.opacity(0.7))
                                .font(.caption)
                        }
                        Text(result.feedback)
                            .foregroundStyle(fg.opacity(0.9))
                            .font(.caption)
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 8)
                    .fill(result.isCorrect ? .green.opacity(0.2) : .red.opacity(0.2)))
            } else {
                // Text input + submit
                HStack {
                    TextField("Your answer…", text: $inputText)
                        .textFieldStyle(.plain)
                        .foregroundStyle(fg)
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 8).fill(fg.opacity(0.15)))
                        .focused($isFocused)
                        .onTapGesture { isFocused = true }
                        .onSubmit { submitIfReady() }

                    Button("Submit") {
                        submitIfReady()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(fg.opacity(0.08))
        )
    }

    private func submitIfReady() {
        let trimmed = inputText.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        isFocused = false
        onSubmit(trimmed)
    }
}

// MARK: - Skeleton block

/// A single animated placeholder bar used by the skeleton loading views.
/// Width is expressed as a fraction (0–1) of the available container width.
private struct SkeletonBlock: View {
    var widthFraction: CGFloat = 1.0
    var height: CGFloat = 14
    var color: Color

    @State private var opacity: Double = 0.28

    var body: some View {
        GeometryReader { geo in
            RoundedRectangle(cornerRadius: height / 2)
                .fill(color.opacity(opacity))
                .frame(width: geo.size.width * widthFraction, height: height)
        }
        .frame(height: height)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                opacity = 0.58
            }
        }
    }
}

// MARK: - Short Answer Question View

struct ShortAnswerQuestionView: View {
    @Environment(\.studyFg)       private var fg
    @Environment(\.studyCardFill) private var cardFill
    let question: QuizQuestion
    let questionNumber: Int
    let onSubmit: (String) -> Void

    @State private var inputText = ""
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Q\(questionNumber): \(question.question)")
                .font(.subheadline.bold())
                .foregroundStyle(fg)

            if question.isGrading {
                HStack(spacing: 8) {
                    ProgressView().tint(fg)
                    Text("Grading…")
                        .foregroundStyle(fg.opacity(0.7))
                        .font(.caption)
                }
            } else if let result = question.gradeResult {
                // Show grading result + model answer on wrong
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .top) {
                        Image(systemName: result.isCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundStyle(result.isCorrect ? .green : .red)
                        Text(result.feedback)
                            .foregroundStyle(fg.opacity(0.9))
                            .font(.caption)
                    }
                    if !result.isCorrect {
                        Text("Model answer: \(question.correctAnswer)")
                            .foregroundStyle(fg.opacity(0.65))
                            .font(.caption)
                            .italic()
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 8)
                    .fill(result.isCorrect ? .green.opacity(0.2) : .red.opacity(0.2)))
            } else {
                // Multi-line text input
                TextField("Your answer…", text: $inputText, axis: .vertical)
                    .lineLimit(3...6)
                    .textFieldStyle(.plain)
                    .foregroundStyle(fg)
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 8).fill(fg.opacity(0.15)))
                    .focused($isFocused)
                    .onTapGesture { isFocused = true }

                Button("Submit") {
                    submitIfReady()
                }
                .buttonStyle(.borderedProminent)
                .frame(maxWidth: .infinity)
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(fg.opacity(0.08))
        )
    }

    private func submitIfReady() {
        let trimmed = inputText.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        isFocused = false
        onSubmit(trimmed)
    }
}
