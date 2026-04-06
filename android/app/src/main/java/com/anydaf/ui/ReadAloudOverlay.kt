package com.anydaf.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.anydaf.viewmodel.ReadAloudPhase
import com.anydaf.viewmodel.ReadAloudViewModel

@Composable
fun ReadAloudStatusBar(
    readAloudViewModel: ReadAloudViewModel,
    phase: ReadAloudPhase
) {
    val isPaused by readAloudViewModel.isPaused.collectAsState()
    val isListening by readAloudViewModel.isListening.collectAsState()
    val recognizedText by readAloudViewModel.recognizedText.collectAsState()

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.tertiaryContainer)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = if (isListening && recognizedText.isNotEmpty()) "\"$recognizedText\"" else phase.displayText,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onTertiaryContainer,
            modifier = Modifier.weight(1f)
        )

        Row {
            IconButton(onClick = { readAloudViewModel.pauseResume() }) {
                Icon(
                    if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                    if (isPaused) "Resume" else "Pause",
                    tint = MaterialTheme.colorScheme.onTertiaryContainer
                )
            }
            IconButton(onClick = { readAloudViewModel.skip() }) {
                Icon(
                    Icons.Default.SkipNext,
                    "Skip",
                    tint = MaterialTheme.colorScheme.onTertiaryContainer
                )
            }
        }
    }
}
