import Foundation

// MARK: - Supabase Configuration
// After creating your Supabase project, replace these two values with your own.
// Find them at: Project Dashboard → Settings → API
private let supabaseBaseURL = "https://zewdazoijdpakugfvnzt.supabase.co/rest/v1/study_cache"
private let supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpld2Rhem9pamRwYWt1Z2Z2bnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzIwODYsImV4cCI6MjA5MDA0ODA4Nn0.HJxIG18vEpt-exzoQwRLeXiKLAinWfBl7gMORKjxIz8"

/// Shared read-through cache for Claude-generated study content, backed by Supabase.
///
/// Cache key format: {tractate}_{daf}_{sectionIndex}_{studyMode}_{quizMode}
/// Example:          Berakhot_2_0_facts_multipleChoice
///
/// - Cache reads return nil on any failure; the caller falls back to Claude.
/// - Cache writes are fire-and-forget; failures are silently ignored.
/// - Write-once: if a key already exists the insert is ignored, preserving the
///   first-generated content for all future users.
actor StudyCache {
    static let shared = StudyCache()

    struct CachedContent {
        let summary: String
        let questions: [QuizQuestion]
        let shiurUsed: Bool
    }

    // MARK: - Fetch

    func fetch(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode
    ) async -> CachedContent? {
        let key = cacheKey(tractate: tractate, daf: daf, sectionIndex: sectionIndex,
                           studyMode: studyMode, quizMode: quizMode)

        guard var components = URLComponents(string: supabaseBaseURL) else { return nil }
        components.queryItems = [
            URLQueryItem(name: "key",    value: "eq.\(key)"),
            URLQueryItem(name: "select", value: "summary,questions_json,shiur_used"),
            URLQueryItem(name: "limit",  value: "1"),
        ]
        guard let url = components.url else { return nil }

        var request = URLRequest(url: url)
        request.setValue(supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(supabaseAnonKey)", forHTTPHeaderField: "Authorization")

        guard let (data, _) = try? await URLSession.shared.data(for: request),
              let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]],
              let row = rows.first,
              let summary = row["summary"] as? String,
              let questionsJson = row["questions_json"] as? String
        else { return nil }

        let shiurUsed = (row["shiur_used"] as? Bool) ?? false
        let questions = deserializeQuestions(questionsJson, quizMode: quizMode)
        return CachedContent(summary: summary, questions: questions, shiurUsed: shiurUsed)
    }

    // MARK: - Store

    func store(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode,
        summary: String, questions: [QuizQuestion],
        shiurUsed: Bool
    ) async {
        let key = cacheKey(tractate: tractate, daf: daf, sectionIndex: sectionIndex,
                           studyMode: studyMode, quizMode: quizMode)

        // shiurUsed=true: upsert so we overwrite any existing non-shiur entry.
        // shiurUsed=false: write-once so we never downgrade a shiur-enriched entry.
        let urlStr = shiurUsed
            ? "\(supabaseBaseURL)?on_conflict=key"
            : supabaseBaseURL
        let preferHeader = shiurUsed
            ? "resolution=merge-duplicates"
            : "resolution=ignore-duplicates"

        guard let url = URL(string: urlStr),
              let questionsJson = serializeQuestions(questions)
        else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(preferHeader, forHTTPHeaderField: "Prefer")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "key":            key,
            "summary":        summary,
            "questions_json": questionsJson,
            "shiur_used":     shiurUsed,
        ])

        _ = try? await URLSession.shared.data(for: request)
    }

    // MARK: - Serialization

    private func serializeQuestions(_ questions: [QuizQuestion]) -> String? {
        let maps: [[String: Any]] = questions.map { q in
            switch q.mode {
            case .multipleChoice:
                return ["mode": "multipleChoice",
                        "question": q.question,
                        "choices": q.choices,
                        "correctIndex": q.correctIndex]
            case .flashcard:
                return ["mode": "flashcard",
                        "question": q.question,
                        "answer": q.correctAnswer]
            case .fillInBlank:
                return ["mode": "fillInBlank",
                        "question": q.question,
                        "answer": q.correctAnswer]
            case .shortAnswer:
                return ["mode": "shortAnswer",
                        "question": q.question,
                        "answer": q.correctAnswer]
            }
        }
        guard let data = try? JSONSerialization.data(withJSONObject: maps),
              let str = String(data: data, encoding: .utf8)
        else { return nil }
        return str
    }

    private func deserializeQuestions(_ json: String, quizMode: QuizMode) -> [QuizQuestion] {
        guard let data = json.data(using: .utf8),
              let array = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]
        else { return [] }

        return array.compactMap { q in
            guard let modeStr = q["mode"] as? String,
                  let question = q["question"] as? String
            else { return nil }

            switch modeStr {
            case "multipleChoice":
                guard let choices = q["choices"] as? [String],
                      let correctIndex = q["correctIndex"] as? Int
                else { return nil }
                return .multipleChoice(question: question, choices: choices, correctIndex: correctIndex)
            case "flashcard":
                guard let answer = q["answer"] as? String else { return nil }
                return .flashcard(question: question, answer: answer)
            case "fillInBlank":
                guard let answer = q["answer"] as? String else { return nil }
                return .fillInBlank(question: question, answer: answer)
            case "shortAnswer":
                guard let answer = q["answer"] as? String else { return nil }
                return .shortAnswer(question: question, answer: answer)
            default: return nil
            }
        }
    }

    // MARK: - Cache Key

    private func cacheKey(
        tractate: String, daf: Int, sectionIndex: Int,
        studyMode: StudyMode, quizMode: QuizMode
    ) -> String {
        let modeStr = studyMode == .facts ? "facts" : "conceptual"
        let safeTractate = tractate.replacingOccurrences(of: " ", with: "_")
        return "\(safeTractate)_\(daf)_\(sectionIndex)_\(modeStr)_\(quizMode.rawValue)"
    }
}
