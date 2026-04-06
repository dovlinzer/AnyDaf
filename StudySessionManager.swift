import Foundation

@MainActor
class StudySessionManager: ObservableObject {
    @Published var session: StudySession?
    @Published var isLoadingText = false
    @Published var isLoadingStudyContent = false
    @Published var error: String?
    @Published var selectedScope: StudyScope = .amudA

    private let sefariaClient = SefariaClient()
    private let claudeClient = ClaudeClient()

    /// Phase 1: Fetch text from Sefaria and parse into sections.
    /// Phase 2: Generate study content for the first section.
    func startSession(tractate: String, daf: Int) async {
        isLoadingText = true
        error = nil

        do {
            let segments: [String]
            switch selectedScope {
            case .amudA:
                segments = try await sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "a")
            case .amudB:
                segments = try await sefariaClient.fetchText(tractate: tractate, daf: daf, amud: "b")
            case .fullDaf:
                segments = try await sefariaClient.fetchFullDaf(tractate: tractate, daf: daf)
            }

            let sections = SefariaClient.parseSections(from: segments)

            session = StudySession(
                tractate: tractate,
                daf: daf,
                scope: selectedScope,
                sections: sections
            )

            isLoadingText = false

            // Load Claude content for the first section
            await loadStudyContentForCurrentSection()

        } catch {
            self.error = error.localizedDescription
            isLoadingText = false
        }
    }

    /// Send current section to Claude for summary + quiz.
    func loadStudyContentForCurrentSection() async {
        guard var session = session,
              session.currentSectionIndex < session.sections.count
        else { return }

        let section = session.sections[session.currentSectionIndex]

        // Skip if already loaded
        guard section.summary == nil else { return }

        isLoadingStudyContent = true

        do {
            let plainText = SefariaClient.stripHTML(section.rawText)
            let (summary, questions) = try await claudeClient.generateStudyContent(
                sectionTitle: section.title,
                sectionText: plainText,
                tractate: session.tractate,
                daf: session.daf
            )

            session.sections[session.currentSectionIndex].summary = summary
            session.sections[session.currentSectionIndex].quizQuestions = questions
            self.session = session

        } catch {
            self.error = error.localizedDescription
        }

        isLoadingStudyContent = false
    }

    /// Move to next section and load its study content.
    func advanceToNextSection() async {
        guard var session = session else { return }
        session.currentSectionIndex += 1
        self.session = session

        if !session.isComplete {
            await loadStudyContentForCurrentSection()
        }
    }

    /// Record a quiz answer.
    func answerQuestion(questionIndex: Int, choiceIndex: Int) {
        guard var session = session else { return }
        let si = session.currentSectionIndex
        guard si < session.sections.count,
              questionIndex < session.sections[si].quizQuestions.count
        else { return }

        session.sections[si].quizQuestions[questionIndex].selectedIndex = choiceIndex
        self.session = session
    }

    /// Reset and dismiss study mode.
    func endSession() {
        session = nil
        error = nil
        isLoadingText = false
        isLoadingStudyContent = false
    }
}
