import Foundation

@MainActor
class ClaudeClient {

    private let model = "claude-haiku-4-5-20251001"
    private let apiURL = URL(string: "https://zewdazoijdpakugfvnzt.supabase.co/functions/v1/claude-proxy")!

    enum ClaudeError: LocalizedError {
        case networkError(Error)
        case apiError(String)
        case parsingError
        /// Anthropic returned HTTP 429 (rate limit exceeded).
        case rateLimited

        var errorDescription: String? {
            switch self {
            case .networkError(let e): return "Network error: \(e.localizedDescription)"
            case .apiError(let msg):   return "Claude API error: \(msg)"
            case .parsingError:        return "Could not parse Claude's response"
            case .rateLimited:         return "Rate limit reached — please wait a moment"
            }
        }
    }

    /// Sends a section's text to Claude and returns (summary, [QuizQuestion]).
    /// - Parameter shiurContext: Optional full-daf lecture rewrite from the daf-processor
    ///   pipeline. When provided, Claude uses it to enrich summaries with the lecturer's
    ///   reasoning and analysis. The rewrite covers the whole daf; Claude extracts the
    ///   portion relevant to the current section.
    func generateStudyContent(
        sectionTitle: String,
        sectionText: String,
        tractate: String,
        daf: Int,
        mode: StudyMode,
        quizMode: QuizMode,
        shiurContext: String? = nil
    ) async throws -> (String, [QuizQuestion]) {

        let prompt: String
        switch (mode, quizMode) {
        case (.facts, .multipleChoice):
            prompt = factsPrompt(sectionTitle: sectionTitle, sectionText: sectionText,
                                 tractate: tractate, daf: daf, shiurContext: shiurContext)
        case (.conceptual, .multipleChoice):
            prompt = conceptualPrompt(sectionTitle: sectionTitle, sectionText: sectionText,
                                      tractate: tractate, daf: daf, shiurContext: shiurContext)
        case (_, .flashcard):
            prompt = flashcardPrompt(sectionTitle: sectionTitle, sectionText: sectionText,
                                     tractate: tractate, daf: daf, studyMode: mode,
                                     shiurContext: shiurContext)
        case (_, .fillInBlank):
            prompt = fillInBlankPrompt(sectionTitle: sectionTitle, sectionText: sectionText,
                                       tractate: tractate, daf: daf, studyMode: mode,
                                       shiurContext: shiurContext)
        case (_, .shortAnswer):
            prompt = shortAnswerPrompt(sectionTitle: sectionTitle, sectionText: sectionText,
                                       tractate: tractate, daf: daf, studyMode: mode,
                                       shiurContext: shiurContext)
        }

        let responseText = try await callClaude(prompt: prompt, maxTokens: 1500)

        switch quizMode {
        case .multipleChoice:
            return try parseMCContent(from: responseText)
        case .flashcard:
            return try parseQAContent(from: responseText, quizMode: .flashcard)
        case .fillInBlank:
            return try parseQAContent(from: responseText, quizMode: .fillInBlank)
        case .shortAnswer:
            return try parseQAContent(from: responseText, quizMode: .shortAnswer)
        }
    }

    /// Grades a text answer leniently. Uses a more lenient prompt for short answer mode.
    func gradeAnswer(
        question: String,
        correctAnswer: String,
        userAnswer: String,
        mode: QuizMode = .fillInBlank
    ) async throws -> GradeResult {
        let prompt = mode == .shortAnswer
            ? shortAnswerGradingPrompt(question: question, correctAnswer: correctAnswer, userAnswer: userAnswer)
            : gradingPrompt(question: question, correctAnswer: correctAnswer, userAnswer: userAnswer)
        let text = try await callClaude(prompt: prompt, maxTokens: 250)
        return parseGradeResult(from: text, correctAnswer: correctAnswer)
    }

    // MARK: - Internal API call

    private func callClaude(prompt: String, maxTokens: Int) async throws -> String {
        let requestBody: [String: Any] = [
            "model": model,
            "max_tokens": maxTokens,
            "messages": [
                ["role": "user", "content": prompt]
            ]
        ]

        var request = URLRequest(url: apiURL)
        request.httpMethod = "POST"
        request.setValue(Secrets.appSecret, forHTTPHeaderField: "x-app-secret")
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw ClaudeError.networkError(error)
        }

        if let httpResponse = response as? HTTPURLResponse {
            if httpResponse.statusCode == 429 {
                throw ClaudeError.rateLimited
            }
            if httpResponse.statusCode != 200 {
                let body = String(data: data, encoding: .utf8) ?? "unknown"
                throw ClaudeError.apiError("HTTP \(httpResponse.statusCode): \(body)")
            }
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [[String: Any]],
              let firstBlock = content.first,
              let text = firstBlock["text"] as? String
        else {
            throw ClaudeError.parsingError
        }

        return text
    }

    // MARK: - Prompts

    /// Appends the lecturer's explanation block when shiurContext is available.
    private func shiurBlock(_ shiurContext: String?) -> String {
        guard let ctx = shiurContext, !ctx.isEmpty else { return "" }
        return """


        LECTURER'S EXPLANATION (full daf — focus on the section above):
        \(ctx)
        """
    }

    private func factsPrompt(sectionTitle: String, sectionText: String,
                             tractate: String, daf: Int, shiurContext: String?) -> String {
        let questionScope = "Questions may draw from any detail in the provided text, not just what appears in the summary."
        return """
        You are a Talmud study assistant. Below is the English translation of the \
        \(sectionTitle) section from \(tractate) \(daf).\(shiurContext != nil ? " A lecturer's explanation of the full daf follows the text — use the relevant portion to enrich your summary." : "")

        TEXT:
        \(sectionText)\(shiurBlock(shiurContext))

        Please provide:
        1. A clear summary (3-5 sentences) covering the key topics, rulings, and \
        conclusions in this section. Write for someone who wants to understand the \
        main facts and outcomes.

        2. Exactly 3 multiple choice questions testing comprehension of this section. \
        \(questionScope) \
        Each question should have exactly 4 options labeled A, B, C, D, with exactly \
        one correct answer.

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"summary":"Your summary here...","questions":[{"question":"Question text?","choices":["A) ...","B) ...","C) ...","D) ..."],"correctIndex":0}]}
        """
    }

    private func conceptualPrompt(sectionTitle: String, sectionText: String,
                                   tractate: String, daf: Int, shiurContext: String?) -> String {
        let questionScope = "Questions may draw from any reasoning or detail in the provided text, not just what appears in the summary."
        return """
        You are a Talmud study assistant. Below is the English translation of the \
        \(sectionTitle) section from \(tractate) \(daf).\(shiurContext != nil ? " A lecturer's explanation of the full daf follows the text — use the relevant portion to enrich your summary of the reasoning." : "")

        TEXT:
        \(sectionText)\(shiurBlock(shiurContext))

        Please provide:
        1. A summary (3-5 sentences) focused on the REASONING and DEBATE in this \
        section: What question or problem is being discussed? Who holds what position \
        and what is the logic behind each view? How is the debate resolved, and why? \
        Prioritize the flow of argumentation over listing facts.

        2. Exactly 3 multiple choice questions that test understanding of the \
        reasoning and logic in this section. \(questionScope) \
        Frame questions at the conceptual level: WHY was one position \
        accepted over another? WHAT logical principle underlies the resolution? HOW \
        do the two views differ in their reasoning? WHAT follows from the conclusion? \
        Each question should have exactly 4 options labeled A, B, C, D, with exactly \
        one correct answer.

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"summary":"Your summary here...","questions":[{"question":"Question text?","choices":["A) ...","B) ...","C) ...","D) ..."],"correctIndex":0}]}
        """
    }

    private func flashcardPrompt(sectionTitle: String, sectionText: String,
                                  tractate: String, daf: Int, studyMode: StudyMode,
                                  shiurContext: String?) -> String {
        let focus = studyMode == .facts
            ? "facts, rulings, names, and key terms"
            : "reasoning, debates, logical principles, and how conclusions are reached"
        let source = "drawn from anywhere in the provided text."
        return """
        You are a Talmud study assistant. Below is the English translation of the \
        \(sectionTitle) section from \(tractate) \(daf).\(shiurContext != nil ? " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." : "")

        TEXT:
        \(sectionText)\(shiurBlock(shiurContext))

        Please provide:
        1. A clear summary (3-5 sentences) focusing on the \(focus).

        2. Exactly 3 flashcard-style Q&A pairs \(source) Each question \
        should have a concise, specific answer (one phrase or sentence).

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"summary":"...","questions":[{"question":"...","answer":"..."}]}
        """
    }

    private func fillInBlankPrompt(sectionTitle: String, sectionText: String,
                                    tractate: String, daf: Int, studyMode: StudyMode,
                                    shiurContext: String?) -> String {
        let focus = studyMode == .facts
            ? "facts, rulings, names, and key terms"
            : "reasoning, debates, logical principles, and how conclusions are reached"
        let source = "drawn from anywhere in the provided text."
        return """
        You are a Talmud study assistant. Below is the English translation of the \
        \(sectionTitle) section from \(tractate) \(daf).\(shiurContext != nil ? " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." : "")

        TEXT:
        \(sectionText)\(shiurBlock(shiurContext))

        Please provide:
        1. A clear summary (3-5 sentences) focusing on the \(focus).

        2. Exactly 3 fill-in-the-blank questions \(source) Each question \
        is a sentence with one key term or phrase replaced by a blank (shown as _____). \
        Provide the exact word or phrase that fills the blank as the answer. Keep \
        answers short (1-5 words).

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"summary":"...","questions":[{"question":"The _____ ruled that...","answer":"rabbi's name"}]}
        """
    }

    private func shortAnswerPrompt(sectionTitle: String, sectionText: String,
                                    tractate: String, daf: Int, studyMode: StudyMode,
                                    shiurContext: String?) -> String {
        let focus = studyMode == .facts
            ? "facts, rulings, names, and key terms"
            : "reasoning, debates, logical principles, and how conclusions are reached"
        let source = "drawn from anywhere in the provided text."
        return """
        You are a Talmud study assistant. Below is the English translation of the \
        \(sectionTitle) section from \(tractate) \(daf).\(shiurContext != nil ? " A lecturer's explanation of the full daf follows — use the relevant portion to enrich your summary." : "")

        TEXT:
        \(sectionText)\(shiurBlock(shiurContext))

        Please provide:
        1. A clear summary (3-5 sentences) focusing on the \(focus).

        2. Exactly 3 short-answer questions \(source) Each question \
        should require a 1-2 sentence answer that demonstrates understanding — not \
        just recall of a single word. The model answer should be concise but complete.

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"summary":"...","questions":[{"question":"...","answer":"..."}]}
        """
    }

    private func gradingPrompt(question: String, correctAnswer: String, userAnswer: String) -> String {
        """
        You are grading a Talmud study fill-in-the-blank answer. Be VERY lenient with \
        spelling, capitalization, and transliteration of Hebrew/Aramaic names and terms. \
        Accept synonyms, reasonable paraphrases, plural/singular variations, and common \
        alternate spellings as correct. For example: "Rav" and "Rabbi", "Shmuel" and \
        "Samuel" and "Shemuel", "halacha" and "halakha", etc.

        Question: \(question)
        Correct answer: \(correctAnswer)
        Your answer: \(userAnswer)

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"correct":true,"feedback":"Brief explanation (one concise sentence)."}

        Set "correct" to true if the user's answer is essentially right even if not \
        worded exactly like the correct answer. Set it to false only if the answer is \
        clearly wrong or unrelated.
        """
    }

    private func shortAnswerGradingPrompt(question: String, correctAnswer: String, userAnswer: String) -> String {
        """
        You are grading a Talmud study short-answer question. Be lenient: accept \
        paraphrases, synonyms, and alternate formulations. The user does not need \
        to match the model answer word-for-word — they just need to demonstrate that \
        they understood the key idea. Also be lenient with spelling and transliteration \
        of Hebrew/Aramaic names and terms.

        Question: \(question)
        Model answer: \(correctAnswer)
        Your answer: \(userAnswer)

        Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
        {"correct":true,"feedback":"Brief explanation (one concise sentence)."}

        Set "correct" to true if the user's answer captures the essential idea, \
        even if incomplete or differently worded. Set it to false only if the answer \
        is clearly wrong, irrelevant, or missing the key concept entirely.
        """
    }

    // MARK: - Parsing

    private func cleanJSON(_ text: String) -> String {
        text.replacingOccurrences(of: "```json", with: "")
            .replacingOccurrences(of: "```", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func parseMCContent(from text: String) throws -> (String, [QuizQuestion]) {
        let cleaned = cleanJSON(text)

        guard let data = cleaned.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let summary = json["summary"] as? String,
              let questionsArray = json["questions"] as? [[String: Any]]
        else {
            throw ClaudeError.parsingError
        }

        let questions: [QuizQuestion] = questionsArray.compactMap { q in
            guard let question = q["question"] as? String,
                  let choices = q["choices"] as? [String],
                  let correctIndex = q["correctIndex"] as? Int,
                  choices.count == 4,
                  (0..<4).contains(correctIndex)
            else { return nil }
            let labels = ["A) ", "B) ", "C) ", "D) "]
            let stripped = choices.map { c in
                labels.first(where: { c.hasPrefix($0) }).map { String(c.dropFirst($0.count)) } ?? c
            }
            let correctBareText = stripped[correctIndex]
            var shuffledBare = stripped
            shuffledBare.shuffle()
            let newCorrectIndex = shuffledBare.firstIndex(of: correctBareText) ?? correctIndex
            let relabeled = zip(labels, shuffledBare).map { $0 + $1 }
            return .multipleChoice(question: question, choices: relabeled, correctIndex: newCorrectIndex)
        }

        return (summary, questions)
    }

    private func parseQAContent(from text: String, quizMode: QuizMode) throws -> (String, [QuizQuestion]) {
        let cleaned = cleanJSON(text)

        guard let data = cleaned.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let summary = json["summary"] as? String,
              let questionsArray = json["questions"] as? [[String: Any]]
        else {
            throw ClaudeError.parsingError
        }

        let questions: [QuizQuestion] = questionsArray.compactMap { q in
            guard let question = q["question"] as? String,
                  let answer = q["answer"] as? String
            else { return nil }
            switch quizMode {
            case .flashcard:      return .flashcard(question: question, answer: answer)
            case .fillInBlank:    return .fillInBlank(question: question, answer: answer)
            case .shortAnswer:    return .shortAnswer(question: question, answer: answer)
            case .multipleChoice: return nil
            }
        }

        return (summary, questions)
    }

    private func parseGradeResult(from text: String, correctAnswer: String) -> GradeResult {
        let cleaned = cleanJSON(text)

        if let data = cleaned.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let correct = json["correct"] as? Bool,
           let feedback = json["feedback"] as? String {
            return GradeResult(isCorrect: correct, feedback: feedback)
        }

        // Fallback: simple string comparison
        return GradeResult(isCorrect: false,
                           feedback: "Could not grade. The answer was: \(correctAnswer)")
    }
}
