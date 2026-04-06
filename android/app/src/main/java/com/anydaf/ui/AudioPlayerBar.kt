package com.anydaf.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FastForward
import androidx.compose.material.icons.filled.FastRewind
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.anydaf.viewmodel.AudioViewModel
import kotlin.math.roundToInt

@Composable
fun AudioPlayerBar(audioViewModel: AudioViewModel) {
    val isPlaying by audioViewModel.isPlaying.collectAsState()
    val isBuffering by audioViewModel.isBuffering.collectAsState()
    val currentTime by audioViewModel.currentTime.collectAsState()
    val duration by audioViewModel.duration.collectAsState()
    val playbackRate by audioViewModel.playbackRate.collectAsState()

    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(4.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)) {

            // Progress row: time + slider/indicator + duration
            if (isBuffering) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .height(2.dp)
                )
            } else if (duration > 0) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        formatTime(currentTime),
                        style = MaterialTheme.typography.labelSmall,
                        modifier = Modifier.width(34.dp)
                    )
                    Slider(
                        value = if (duration > 0) currentTime / duration else 0f,
                        onValueChange = { audioViewModel.seekTo(it) },
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        formatTime(duration),
                        style = MaterialTheme.typography.labelSmall,
                        textAlign = TextAlign.End,
                        modifier = Modifier.width(34.dp)
                    )
                }
            }

            // Controls row: rew | play/pause | fwd | speed — compact icons
            Row(
                modifier = Modifier.fillMaxWidth().padding(bottom = 2.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { audioViewModel.skip(-15f) },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(Icons.Default.FastRewind, "Skip back 15s", Modifier.size(20.dp))
                }
                IconButton(
                    onClick = { audioViewModel.togglePlayPause() },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(
                        if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                        if (isPlaying) "Pause" else "Play",
                        Modifier.size(26.dp)
                    )
                }
                IconButton(
                    onClick = { audioViewModel.skip(15f) },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(Icons.Default.FastForward, "Skip forward 15s", Modifier.size(20.dp))
                }

                val speeds = listOf(0.75f, 1f, 1.25f, 1.5f, 2f)
                val currentIdx = speeds.indexOf(playbackRate).coerceAtLeast(0)
                val nextSpeed = speeds[(currentIdx + 1) % speeds.size]
                TextButton(
                    onClick = { audioViewModel.setRate(nextSpeed) },
                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
                ) {
                    Text("${playbackRate}x", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

private fun formatTime(seconds: Float): String {
    val total = seconds.roundToInt()
    val m = total / 60
    val s = total % 60
    return "%d:%02d".format(m, s)
}
