import Foundation

/// Scope of study: one side or full daf
enum StudyScope: String, CaseIterable {
    case amudA = "Amud A"
    case amudB = "Amud B"
    case fullDaf = "Full Daf"
}

/// A single quiz question with four choices
struct QuizQuestion: Identifiable {
    let id = UUID()
    let question: String
    let choices: [String]       // exactly 4
    let correctIndex: Int       // 0-3
    var selectedIndex: Int?     // nil until user answers

    var isAnswered: Bool { selectedIndex != nil }
    var isCorrect: Bool { selectedIndex == correctIndex }
}

/// One logical section of the daf (e.g., Mishna, Gemara, or an untitled block)
struct StudySection: Identifiable {
    let id = UUID()
    let title: String           // "MISHNA", "GEMARA", etc.
    let rawText: String         // original HTML text from Sefaria (joined segments)
    var summary: String?        // Claude-generated summary
    var quizQuestions: [QuizQuestion]
}

/// Full study session state
struct StudySession {
    let tractate: String
    let daf: Int
    let scope: StudyScope
    var sections: [StudySection]
    var currentSectionIndex: Int = 0

    var currentSection: StudySection? {
        guard currentSectionIndex < sections.count else { return nil }
        return sections[currentSectionIndex]
    }

    var isComplete: Bool {
        currentSectionIndex >= sections.count
    }

    var progress: Double {
        guard !sections.isEmpty else { return 0 }
        return Double(currentSectionIndex) / Double(sections.count)
    }
}
