import SwiftUI

// MARK: - Study Mode Container

struct StudyModeView: View {
    @ObservedObject var manager: StudySessionManager
    let onDismiss: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            header

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
                        sectionNumber: session.currentSectionIndex + 1,
                        totalSections: session.sections.count,
                        isLoadingContent: manager.isLoadingStudyContent,
                        onAnswer: { qIdx, choice in
                            manager.answerQuestion(questionIndex: qIdx, choiceIndex: choice)
                        },
                        onNext: {
                            Task { await manager.advanceToNextSection() }
                        }
                    )
                }
            }
        }
        .background(SplashView.background)
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            Button {
                onDismiss()
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "chevron.left")
                    Text("Back to Daf")
                }
                .foregroundStyle(.white)
            }
            Spacer()
            if let session = manager.session {
                Text("\(session.tractate) \(session.daf) — \(session.scope.rawValue)")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.7))
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
    }

    // MARK: - Loading

    private func loadingState(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView()
                .tint(.white)
            Text(message)
                .foregroundStyle(.white.opacity(0.8))
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
                .foregroundStyle(.white.opacity(0.8))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Button("Dismiss") { onDismiss() }
                .buttonStyle(.borderedProminent)
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
                .foregroundStyle(.white)

            let allQuestions = session.sections.flatMap { $0.quizQuestions }
            let correct = allQuestions.filter { $0.isCorrect }.count
            Text("\(correct)/\(allQuestions.count) questions correct")
                .font(.title3)
                .foregroundStyle(.white.opacity(0.8))

            Button("Back to Daf") { onDismiss() }
                .buttonStyle(.borderedProminent)
            Spacer()
        }
    }
}

// MARK: - Section Study View

struct SectionStudyView: View {
    let section: StudySection
    let sectionNumber: Int
    let totalSections: Int
    let isLoadingContent: Bool
    let onAnswer: (Int, Int) -> Void
    let onNext: () -> Void

    @State private var showQuiz = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Section header
                HStack {
                    Text(section.title)
                        .font(.title3.bold())
                        .foregroundStyle(.white)
                    Spacer()
                    Text("Section \(sectionNumber)/\(totalSections)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.6))
                }

                if isLoadingContent {
                    VStack(spacing: 12) {
                        ProgressView()
                            .tint(.white)
                        Text("Generating summary and quiz…")
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.7))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
                } else if let summary = section.summary {
                    // Summary card
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Summary", systemImage: "text.book.closed")
                            .font(.headline)
                            .foregroundStyle(.white)
                        Text(summary)
                            .foregroundStyle(.white.opacity(0.9))
                            .lineSpacing(4)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(.white.opacity(0.1))
                    )

                    // Quiz toggle
                    if !showQuiz {
                        Button {
                            withAnimation { showQuiz = true }
                        } label: {
                            Label("Start Quiz", systemImage: "questionmark.circle")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                    } else {
                        quizContent
                    }
                }
            }
            .padding()
        }
    }

    @ViewBuilder
    private var quizContent: some View {
        VStack(alignment: .leading, spacing: 16) {
            ForEach(Array(section.quizQuestions.enumerated()), id: \.offset) { idx, question in
                QuizQuestionView(
                    question: question,
                    questionNumber: idx + 1,
                    onSelect: { choice in onAnswer(idx, choice) }
                )
            }

            if allQuestionsAnswered {
                let correct = section.quizQuestions.filter { $0.isCorrect }.count
                let total = section.quizQuestions.count

                VStack(spacing: 12) {
                    Text("\(correct)/\(total) correct")
                        .font(.headline)
                        .foregroundStyle(correct == total ? .green : .yellow)

                    Button {
                        onNext()
                    } label: {
                        Text(sectionNumber < totalSections ? "Next Section" : "Finish")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding(.top, 8)
            }
        }
    }

    private var allQuestionsAnswered: Bool {
        section.quizQuestions.allSatisfy { $0.isAnswered }
    }
}

// MARK: - Quiz Question View

struct QuizQuestionView: View {
    let question: QuizQuestion
    let questionNumber: Int
    let onSelect: (Int) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Q\(questionNumber): \(question.question)")
                .font(.subheadline.bold())
                .foregroundStyle(.white)

            ForEach(Array(question.choices.enumerated()), id: \.offset) { idx, choice in
                Button {
                    if !question.isAnswered {
                        onSelect(idx)
                    }
                } label: {
                    HStack {
                        Text(choice)
                            .foregroundStyle(.white)
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
                .fill(.white.opacity(0.08))
        )
    }

    private func choiceBackground(_ idx: Int) -> Color {
        guard question.isAnswered else {
            return .white.opacity(0.1)
        }
        if idx == question.correctIndex {
            return .green.opacity(0.2)
        }
        if idx == question.selectedIndex {
            return .red.opacity(0.2)
        }
        return .white.opacity(0.05)
    }
}

// MARK: - Scope Picker Sheet

struct StudyScopePicker: View {
    let tractate: String
    let daf: Int
    @ObservedObject var manager: StudySessionManager
    let onStart: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Text("Study \(tractate) \(daf)")
                .font(.headline)
                .padding(.top)

            Picker("Scope", selection: $manager.selectedScope) {
                ForEach(StudyScope.allCases, id: \.self) { scope in
                    Text(scope.rawValue).tag(scope)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)

            Button {
                Task {
                    await manager.startSession(tractate: tractate, daf: daf)
                    onStart()
                }
            } label: {
                Text("Start Studying")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .padding(.horizontal)

            Spacer()
        }
    }
}
