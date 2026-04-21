package com.anydaf.model

import java.util.UUID

// YCT Library Models

enum class YCTSource { LIBRARY, PSAK }

sealed class ResourceMatchType {
    data class Exact(val daf: Int) : ResourceMatchType()
    data class Nearby(val daf: Int) : ResourceMatchType()
    data class TractateWide(val daf: Int) : ResourceMatchType()

    val referencedDaf: Int get() = when (this) {
        is Exact -> daf
        is Nearby -> daf
        is TractateWide -> daf
    }
}

data class YCTReferenceTerm(
    val id: Int,
    val name: String,
    val slug: String,
    val parent: Int
)

data class YCTArticle(
    val id: Int,
    val title: String,
    val excerpt: String,
    val date: String,
    val link: String,
    val authorName: String,
    val matchType: ResourceMatchType = ResourceMatchType.Exact(0),
    /** Additional daf references beyond the primary one (sorted ascending). */
    val additionalDafs: List<Int> = emptyList(),
    /** Which YCT site this article came from. */
    val source: YCTSource = YCTSource.LIBRARY
)

// Study Models

enum class StudyScope(val displayName: String) {
    AMUD_A("Amud A"),
    AMUD_B("Amud B"),
    FULL_DAF("Full Daf")
}

enum class StudyMode { FACTS, CONCEPTUAL }

enum class QuizMode(val displayName: String, val description: String) {
    MULTIPLE_CHOICE(
        "Multiple Choice",
        "Choose the correct answer from four options."
    ),
    FLASHCARD(
        "Flashcard",
        "Read the question, think of your answer, then reveal and self-grade."
    ),
    FILL_IN_BLANK(
        "Fill in the Blank",
        "Type your answer. Claude grades it, accepting also Aramaic and Hebrew input."
    ),
    SHORT_ANSWER(
        "Short Answer",
        "Answer in your own words. Claude grades it, accepting paraphrases and alternate formulations."
    )
}

enum class SourceDisplayMode(val displayName: String, val description: String) {
    TOGGLE("Toggle", "Tap a button to switch between source text and translation."),
    STACKED("Top & Bottom", "Each paragraph shown as source above translation, scroll through paired paragraphs.")
}

enum class StudyFontSize(val displayName: String, val spSize: Float, val articleFontPx: Int) {
    X_SMALL("Extra Small", 12f, 14),
    SMALL("Small", 15f, 17),
    MEDIUM("Medium", 18f, 20),
    LARGE("Large", 21f, 23),
    X_LARGE("Extra Large", 26f, 28);

    companion object {
        /** X_SMALL is tablet-only — it maps to iOS system default size, already small on phones. */
        fun displayEntries(isTablet: Boolean): List<StudyFontSize> =
            if (isTablet) entries else entries.filter { it != X_SMALL }
    }
}

data class GradeResult(
    val isCorrect: Boolean,
    val feedback: String
)

data class QuizQuestion(
    val id: UUID = UUID.randomUUID(),
    val mode: QuizMode,
    val question: String,
    val correctAnswer: String,
    // Multiple choice
    val choices: List<String> = emptyList(),
    val correctIndex: Int = -1,
    var selectedIndex: Int? = null,
    // Flashcard
    var selfMarkedCorrect: Boolean? = null,
    // Fill-in-blank / Short answer
    var userText: String? = null,
    var isGrading: Boolean = false,
    var gradeResult: GradeResult? = null
) {
    val isAnswered: Boolean get() = when (mode) {
        QuizMode.MULTIPLE_CHOICE -> selectedIndex != null
        QuizMode.FLASHCARD -> selfMarkedCorrect != null
        QuizMode.FILL_IN_BLANK, QuizMode.SHORT_ANSWER -> gradeResult != null
    }

    val isCorrect: Boolean get() = when (mode) {
        QuizMode.MULTIPLE_CHOICE -> selectedIndex == correctIndex
        QuizMode.FLASHCARD -> selfMarkedCorrect == true
        QuizMode.FILL_IN_BLANK, QuizMode.SHORT_ANSWER -> gradeResult?.isCorrect == true
    }

    companion object {
        fun multipleChoice(question: String, choices: List<String>, correctIndex: Int) =
            QuizQuestion(
                mode = QuizMode.MULTIPLE_CHOICE,
                question = question,
                correctAnswer = choices.getOrElse(correctIndex) { "" },
                choices = choices,
                correctIndex = correctIndex
            )

        fun flashcard(question: String, answer: String) =
            QuizQuestion(mode = QuizMode.FLASHCARD, question = question, correctAnswer = answer)

        fun fillInBlank(question: String, answer: String) =
            QuizQuestion(mode = QuizMode.FILL_IN_BLANK, question = question, correctAnswer = answer)

        fun shortAnswer(question: String, answer: String) =
            QuizQuestion(mode = QuizMode.SHORT_ANSWER, question = question, correctAnswer = answer)
    }
}

data class StudySection(
    val id: UUID = UUID.randomUUID(),
    val title: String,
    val rawText: String,
    val rawSegments: List<String>,
    val hebrewText: String?,
    val hebrewSegments: List<String>,
    var summary: String? = null,
    var quizQuestions: List<QuizQuestion> = emptyList()
)

data class StudySession(
    val tractate: String,
    val daf: Int,
    val scope: StudyScope,
    val sections: List<StudySection>,
    val currentSectionIndex: Int = 0,
    val amudBSectionIndex: Int? = null,
    val precedingContext: String? = null,
    val followingContext: String? = null
) {
    val currentSection: StudySection? get() =
        sections.getOrNull(currentSectionIndex)

    val isComplete: Boolean get() =
        currentSectionIndex >= sections.size

    val progress: Double get() =
        if (sections.isEmpty()) 0.0
        else currentSectionIndex.toDouble() / sections.size
}
