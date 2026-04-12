import Foundation

// MARK: - YCT Library Models

/// Which YCT site an article comes from
enum YCTSource: String, Codable {
    case library // library.yctorah.org
    case psak    // psak.yctorah.org
}

/// How closely an article matches the current daf
enum ResourceMatchType: Equatable, Codable {
    case exact(daf: Int)          // matches current daf exactly
    case nearby(daf: Int)         // matches a nearby daf (±2)
    case tractateWide(daf: Int)   // matches tractate; daf is the article's specific daf reference

    var referencedDaf: Int {
        switch self {
        case .exact(let d), .nearby(let d), .tractateWide(let d): return d
        }
    }

    // MARK: Codable — manual implementation required for enums with associated values

    private enum CodingKeys: String, CodingKey { case type, daf }
    private enum TypeName: String, Codable { case exact, nearby, tractateWide }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .exact(let d):        try c.encode(TypeName.exact,        forKey: .type); try c.encode(d, forKey: .daf)
        case .nearby(let d):       try c.encode(TypeName.nearby,       forKey: .type); try c.encode(d, forKey: .daf)
        case .tractateWide(let d): try c.encode(TypeName.tractateWide, forKey: .type); try c.encode(d, forKey: .daf)
        }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let type_ = try c.decode(TypeName.self, forKey: .type)
        let daf   = try c.decode(Int.self,      forKey: .daf)
        switch type_ {
        case .exact:        self = .exact(daf: daf)
        case .nearby:       self = .nearby(daf: daf)
        case .tractateWide: self = .tractateWide(daf: daf)
        }
    }
}

/// A taxonomy term from the YCT Library reference hierarchy
struct YCTReferenceTerm: Identifiable {
    let id: Int
    let name: String
    let slug: String
    let parent: Int
}

/// An article/essay from the YCT Torah Library
struct YCTArticle: Identifiable, Codable {
    let id: Int
    let title: String
    let excerpt: String
    let date: String
    let link: String
    let authorName: String
    var matchType: ResourceMatchType
    /// Additional daf references beyond the primary one (sorted ascending).
    var additionalDafs: [Int]
    /// Which YCT site this article came from.
    var source: YCTSource

    init(id: Int, title: String, excerpt: String, date: String, link: String,
         authorName: String, matchType: ResourceMatchType, additionalDafs: [Int] = [],
         source: YCTSource = .library) {
        self.id = id; self.title = title; self.excerpt = excerpt; self.date = date
        self.link = link; self.authorName = authorName; self.matchType = matchType
        self.additionalDafs = additionalDafs; self.source = source
    }

    // Backward-compatible decoder: old cache files lack `additionalDafs` and `source`.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id             = try c.decode(Int.self,               forKey: .id)
        title          = try c.decode(String.self,            forKey: .title)
        excerpt        = try c.decode(String.self,            forKey: .excerpt)
        date           = try c.decode(String.self,            forKey: .date)
        link           = try c.decode(String.self,            forKey: .link)
        authorName     = try c.decode(String.self,            forKey: .authorName)
        matchType      = try c.decode(ResourceMatchType.self, forKey: .matchType)
        additionalDafs = try c.decodeIfPresent([Int].self,    forKey: .additionalDafs) ?? []
        source         = try c.decodeIfPresent(YCTSource.self, forKey: .source) ?? .library
    }
}

// MARK: - Study Models

/// Scope of study: one side or full daf
enum StudyScope: String, CaseIterable {
    case amudA = "Amud A"
    case amudB = "Amud B"
    case fullDaf = "Full Daf"
}

/// Quiz / question format — stored in AppStorage as a raw String
enum QuizMode: String, CaseIterable {
    case multipleChoice = "multipleChoice"
    case flashcard      = "flashcard"
    case fillInBlank    = "fillInBlank"
    case shortAnswer    = "shortAnswer"

    var displayName: String {
        switch self {
        case .multipleChoice: return "Multiple Choice"
        case .flashcard:      return "Flashcard"
        case .fillInBlank:    return "Fill in the Blank"
        case .shortAnswer:    return "Short Answer"
        }
    }

    var modeDescription: String {
        switch self {
        case .multipleChoice:
            return "Choose the correct answer from four options."
        case .flashcard:
            return "Read the question, think of your answer, then reveal and self-grade."
        case .fillInBlank:
            return "Type your answer. Claude grades it, accepting also Aramaic and Hebrew input."
        case .shortAnswer:
            return "Answer in your own words. Claude grades it, accepting paraphrases and alternate formulations."
        }
    }
}

/// How the original Hebrew/Aramaic source text is displayed alongside the English translation.
/// Stored in AppStorage as a raw String.
enum SourceDisplayMode: String, CaseIterable {
    case toggle  = "toggle"
    case stacked = "stacked"

    var displayName: String {
        switch self {
        case .toggle:  return "Toggle"
        case .stacked: return "Top & Bottom"
        }
    }

    var modeDescription: String {
        switch self {
        case .toggle:  return "Tap a button to switch between source text and translation."
        case .stacked: return "Each paragraph shown as source above translation, scroll through paired paragraphs."
        }
    }
}

/// Result from AI-graded fill-in-the-blank answer
struct GradeResult: Equatable {
    let isCorrect: Bool
    let feedback: String
}

/// A single quiz question — supports multiple choice, flashcard, and fill-in-blank
struct QuizQuestion: Identifiable {
    let id = UUID()
    let mode: QuizMode
    let question: String
    let correctAnswer: String           // used by all modes

    // ── Multiple Choice ────────────────────────────────────────
    let choices: [String]               // exactly 4 for MC; empty otherwise
    let correctIndex: Int               // 0–3 for MC; -1 for other modes
    var selectedIndex: Int?             // nil until answered

    // ── Flashcard ──────────────────────────────────────────────
    var selfMarkedCorrect: Bool?        // nil until self-graded

    // ── Fill-in-blank ──────────────────────────────────────────
    var userText: String?               // what the user typed
    var isGrading: Bool = false
    var gradeResult: GradeResult?

    // MARK: - Computed

    var isAnswered: Bool {
        switch mode {
        case .multipleChoice:            return selectedIndex != nil
        case .flashcard:                 return selfMarkedCorrect != nil
        case .fillInBlank, .shortAnswer: return gradeResult != nil
        }
    }

    var isCorrect: Bool {
        switch mode {
        case .multipleChoice:            return selectedIndex == correctIndex
        case .flashcard:                 return selfMarkedCorrect == true
        case .fillInBlank, .shortAnswer: return gradeResult?.isCorrect == true
        }
    }

    // MARK: - Factory methods

    static func multipleChoice(question: String,
                               choices: [String],
                               correctIndex: Int) -> QuizQuestion {
        QuizQuestion(mode: .multipleChoice,
                     question: question,
                     correctAnswer: choices[correctIndex],
                     choices: choices,
                     correctIndex: correctIndex)
    }

    static func flashcard(question: String, answer: String) -> QuizQuestion {
        QuizQuestion(mode: .flashcard,
                     question: question,
                     correctAnswer: answer,
                     choices: [],
                     correctIndex: -1)
    }

    static func fillInBlank(question: String, answer: String) -> QuizQuestion {
        QuizQuestion(mode: .fillInBlank,
                     question: question,
                     correctAnswer: answer,
                     choices: [],
                     correctIndex: -1)
    }

    static func shortAnswer(question: String, answer: String) -> QuizQuestion {
        QuizQuestion(mode: .shortAnswer,
                     question: question,
                     correctAnswer: answer,
                     choices: [],
                     correctIndex: -1)
    }
}

/// One logical section of the daf (e.g., Mishna, Gemara, or an untitled block)
struct StudySection: Identifiable {
    let id = UUID()
    let title: String            // "MISHNA", "GEMARA", etc.
    let rawText: String          // joined English HTML (used by quiz, summary, read-aloud)
    let rawSegments: [String]    // individual English HTML segments (for paragraph-aligned display)
    let hebrewText: String?      // joined Hebrew/Aramaic HTML (used by toggle mode)
    let hebrewSegments: [String] // individual Hebrew HTML segments (for paragraph-aligned display)
    var summary: String?         // Claude-generated summary
    var quizQuestions: [QuizQuestion]
}

/// Full study session state
struct StudySession {
    let tractate: String
    let daf: Int
    let scope: StudyScope
    var sections: [StudySection]
    var currentSectionIndex: Int = 0
    var amudBSectionIndex: Int?
    /// Tail of the previous daf, shown in brackets when amud a starts mid-sentence.
    var precedingContext: String? = nil
    /// Head of the next daf, shown in brackets when amud b ends mid-sentence.
    var followingContext: String? = nil

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
