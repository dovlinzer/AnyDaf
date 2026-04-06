package com.anydaf.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.anydaf.model.QuizMode
import com.anydaf.model.QuizQuestion
import com.anydaf.model.StudySection
import com.anydaf.viewmodel.StudySessionViewModel

@Composable
fun QuizTab(
    section: StudySection?,
    isLoading: Boolean,
    studyViewModel: StudySessionViewModel,
    onLoad: () -> Unit
) {
    when {
        section == null -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        isLoading -> Box(Modifier.fillMaxSize(), Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Spacer(Modifier.height(12.dp))
                Text("Generating questions…")
            }
        }
        section.quizQuestions.isEmpty() && section.summary == null -> {
            Box(Modifier.fillMaxSize(), Alignment.Center) {
                Button(onClick = onLoad) { Text("Load Questions") }
            }
        }
        section.quizQuestions.isEmpty() -> {
            Box(Modifier.fillMaxSize(), Alignment.Center) { Text("No questions available.") }
        }
        else -> {
            val scrollState = rememberScrollState()
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp)
            ) {
                section.quizQuestions.forEachIndexed { idx, question ->
                    QuizQuestionCard(
                        questionIndex = idx,
                        question = question,
                        onAnswerMultipleChoice = { studyViewModel.answerQuestion(idx, it) },
                        onMarkFlashcard = { studyViewModel.markFlashcard(idx, it) },
                        onGradeAnswer = { studyViewModel.gradeAnswer(idx, it) }
                    )
                }

                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
fun QuizQuestionCard(
    questionIndex: Int,
    question: QuizQuestion,
    onAnswerMultipleChoice: (Int) -> Unit,
    onMarkFlashcard: (Boolean) -> Unit,
    onGradeAnswer: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "Q${questionIndex + 1}. ${question.question}",
            style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Medium)
        )

        when (question.mode) {
            QuizMode.MULTIPLE_CHOICE -> MultipleChoiceQuestion(question, onAnswerMultipleChoice)
            QuizMode.FLASHCARD -> FlashcardQuestion(question, onMarkFlashcard)
            QuizMode.FILL_IN_BLANK, QuizMode.SHORT_ANSWER -> TextAnswerQuestion(question, onGradeAnswer)
        }

        // Show grade result if available
        question.gradeResult?.let { result ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = 4.dp)
            ) {
                Icon(
                    if (result.isCorrect) Icons.Default.Check else Icons.Default.Close,
                    null,
                    tint = if (result.isCorrect) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error
                )
                Text(
                    result.feedback,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (result.isCorrect) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(start = 4.dp)
                )
            }
        }
    }
}

@Composable
fun MultipleChoiceQuestion(question: QuizQuestion, onAnswer: (Int) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        question.choices.forEachIndexed { idx, choice ->
            val isSelected = question.selectedIndex == idx
            val isCorrect = idx == question.correctIndex
            val isAnswered = question.selectedIndex != null
            val bgColor = when {
                !isAnswered -> if (isSelected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent
                isCorrect -> Color(0xFFE8F5E9)
                isSelected -> Color(0xFFFFEBEE)
                else -> Color.Transparent
            }
            val borderColor = when {
                !isAnswered && isSelected -> MaterialTheme.colorScheme.primary
                isAnswered && isCorrect -> Color(0xFF4CAF50)
                isAnswered && isSelected -> MaterialTheme.colorScheme.error
                else -> MaterialTheme.colorScheme.outline
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(bgColor, RoundedCornerShape(8.dp))
                    .border(1.dp, borderColor, RoundedCornerShape(8.dp))
                    .clickable(enabled = !isAnswered) { onAnswer(idx) }
                    .padding(12.dp)
            ) {
                Text(choice, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
fun FlashcardQuestion(question: QuizQuestion, onMark: (Boolean) -> Unit) {
    var revealed by remember { mutableStateOf(false) }

    if (!revealed) {
        Button(
            onClick = { revealed = true },
            modifier = Modifier.fillMaxWidth()
        ) { Text("Reveal Answer") }
    } else {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(8.dp))
                    .padding(12.dp)
            ) {
                Text(question.correctAnswer, style = MaterialTheme.typography.bodyMedium)
            }
            if (question.selfMarkedCorrect == null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilledTonalButton(
                        onClick = { onMark(false) },
                        modifier = Modifier.weight(1f)
                    ) { Text("Got it wrong") }
                    Button(
                        onClick = { onMark(true) },
                        modifier = Modifier.weight(1f)
                    ) { Text("Got it right") }
                }
            } else {
                Text(
                    if (question.selfMarkedCorrect == true) "✓ Marked correct" else "✗ Marked incorrect",
                    color = if (question.selfMarkedCorrect == true) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
fun TextAnswerQuestion(question: QuizQuestion, onGrade: (String) -> Unit) {
    var text by remember { mutableStateOf("") }

    if (question.gradeResult == null && !question.isGrading) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Type your answer…") },
                maxLines = 4
            )
            Button(
                onClick = { if (text.isNotBlank()) onGrade(text) },
                enabled = text.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) { Text("Submit Answer") }
        }
    } else if (question.isGrading) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            Text("Grading…")
        }
    } else {
        // Show what was typed
        question.userText?.let {
            Text("Your answer: $it", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
