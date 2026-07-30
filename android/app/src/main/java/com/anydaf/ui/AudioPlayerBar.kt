package com.anydaf.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.drag
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.anydaf.ui.theme.AppBlue
import com.anydaf.viewmodel.AudioViewModel
import kotlin.math.roundToInt

/**
 * @param imageURL episode artwork (Resources-tab episodes only — daf/shiur audio has none).
 *   When present, shown as a small leading thumbnail next to [nowPlayingLabel].
 * @param useWhiteBackground drives an inverted, deliberately high-contrast surface (blue-on-white
 *   or white-on-blue) rather than the ambient Material surface color — so the bar always reads
 *   as a distinct floating control, not a panel that blends into whichever page theme (blue or
 *   white) happens to be showing underneath.
 */
@Composable
fun AudioPlayerBar(
    audioViewModel: AudioViewModel,
    nowPlayingLabel: String = "",
    imageURL: String? = null,
    useWhiteBackground: Boolean = false,
    onStop: () -> Unit = { audioViewModel.stop() },
    modifier: Modifier = Modifier
) {
    val isPlaying by audioViewModel.isPlaying.collectAsState()
    val currentTime by audioViewModel.currentTime.collectAsState()
    val duration by audioViewModel.duration.collectAsState()
    val playbackRate by audioViewModel.playbackRate.collectAsState()

    val barBg = if (useWhiteBackground) AppBlue else Color.White
    val barFg = if (useWhiteBackground) Color.White else AppBlue

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = barBg, contentColor = barFg),
        elevation = CardDefaults.cardElevation(6.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)) {

            // Now-playing label (tractate + daf, or episode title + artwork)
            if (nowPlayingLabel.isNotEmpty() || !imageURL.isNullOrEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = if (imageURL.isNullOrEmpty()) Arrangement.Center else Arrangement.Start
                ) {
                    if (!imageURL.isNullOrEmpty()) {
                        AsyncImage(
                            model = imageURL,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(20.dp).clip(RoundedCornerShape(4.dp))
                        )
                        Spacer(Modifier.width(6.dp))
                    }
                    Text(
                        text = nowPlayingLabel,
                        style = MaterialTheme.typography.labelSmall,
                        color = barFg.copy(alpha = 0.75f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        textAlign = if (imageURL.isNullOrEmpty()) TextAlign.Center else TextAlign.Start,
                        modifier = if (imageURL.isNullOrEmpty()) Modifier.fillMaxWidth() else Modifier.weight(1f)
                    )
                }
            }

            // Progress row: show seek bar once duration is known; spinner for initial load only
            if (duration <= 0f) {
                LinearProgressIndicator(
                    color = barFg,
                    trackColor = barFg.copy(alpha = 0.25f),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .height(2.dp)
                )
            } else {
                SeekBar(
                    currentTime = currentTime,
                    duration = duration,
                    color = barFg,
                    onSeek = { audioViewModel.seekTo(it) }
                )
            }

            // Controls row
            Row(
                modifier = Modifier.fillMaxWidth().padding(bottom = 1.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Back / play / forward tightly grouped
                Row(
                    horizontalArrangement = Arrangement.spacedBy(2.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = { audioViewModel.skip(-30f) },
                        modifier = Modifier.size(30.dp)
                    ) {
                        SkipIcon(forward = false)
                    }
                    IconButton(
                        onClick = { audioViewModel.togglePlayPause() },
                        modifier = Modifier.size(30.dp)
                    ) {
                        Icon(
                            if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                            if (isPlaying) "Pause" else "Play",
                            Modifier.size(22.dp)
                        )
                    }
                    IconButton(
                        onClick = { audioViewModel.skip(30f) },
                        modifier = Modifier.size(30.dp)
                    ) {
                        SkipIcon(forward = true)
                    }
                }

                IconButton(
                    onClick = onStop,
                    modifier = Modifier.size(30.dp)
                ) {
                    Icon(Icons.Default.Stop, "Stop", Modifier.size(18.dp))
                }

                val speeds = listOf(0.5f, 0.75f, 1f, 1.25f, 1.5f, 2f)
                var speedMenuOpen by remember { mutableStateOf(false) }
                Box {
                    TextButton(
                        onClick = { speedMenuOpen = true },
                        colors = ButtonDefaults.textButtonColors(contentColor = barFg),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
                    ) {
                        Text("${playbackRate}x", style = MaterialTheme.typography.labelMedium)
                    }
                    DropdownMenu(
                        expanded = speedMenuOpen,
                        onDismissRequest = { speedMenuOpen = false }
                    ) {
                        speeds.forEach { speed ->
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        "${speed}x",
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = if (speed == playbackRate) FontWeight.Bold else null
                                    )
                                },
                                onClick = {
                                    audioViewModel.setRate(speed)
                                    speedMenuOpen = false
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SeekBar(
    currentTime: Float,
    duration: Float,
    color: Color,
    onSeek: (Float) -> Unit
) {
    var isDragging by remember { mutableStateOf(false) }
    var dragFraction by remember { mutableFloatStateOf(0f) }
    val displayFraction = if (isDragging) dragFraction else if (duration > 0) currentTime / duration else 0f
    val displayTime = if (isDragging) dragFraction * duration else currentTime

    val primaryColor = color
    val trackColor = color.copy(alpha = 0.25f)

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            formatTime(displayTime),
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.width(34.dp)
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .height(16.dp)
                .pointerInput(duration) {
                    awaitEachGesture {
                        val down = awaitFirstDown()
                        isDragging = true
                        dragFraction = (down.position.x / size.width.toFloat()).coerceIn(0f, 1f)
                        drag(down.id) { change ->
                            change.consume()
                            dragFraction = (change.position.x / size.width.toFloat()).coerceIn(0f, 1f)
                        }
                        onSeek(dragFraction)
                        isDragging = false
                    }
                }
        ) {
            Canvas(modifier = Modifier.matchParentSize()) {
                val cy = size.height / 2f
                val trackH = 3.dp.toPx()
                val thumbR = 6.dp.toPx()
                val activeX = displayFraction * size.width

                // Inactive track (full width)
                drawLine(
                    color = trackColor,
                    start = Offset(0f, cy),
                    end = Offset(size.width, cy),
                    strokeWidth = trackH,
                    cap = StrokeCap.Round
                )
                // Active track
                if (activeX > 0f) {
                    drawLine(
                        color = primaryColor,
                        start = Offset(0f, cy),
                        end = Offset(activeX, cy),
                        strokeWidth = trackH,
                        cap = StrokeCap.Round
                    )
                }
                // Thumb
                drawCircle(
                    color = primaryColor,
                    radius = thumbR,
                    center = Offset(activeX, cy)
                )
            }
        }
        Text(
            formatTime(duration),
            style = MaterialTheme.typography.labelSmall,
            textAlign = TextAlign.End,
            modifier = Modifier.width(34.dp)
        )
    }
}

@Composable
private fun SkipIcon(forward: Boolean) {
    Box(
        modifier = Modifier.size(20.dp),
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = Icons.Default.Replay,
            contentDescription = if (forward) "Skip forward 30s" else "Skip back 30s",
            modifier = Modifier
                .size(20.dp)
                .then(if (forward) Modifier.scale(-1f, 1f) else Modifier)
        )
        Text(
            text = "30",
            style = MaterialTheme.typography.labelSmall,
            fontSize = 6.sp,
            lineHeight = 6.sp,
            modifier = Modifier.padding(top = 4.dp)
        )
    }
}

private fun formatTime(seconds: Float): String {
    val total = seconds.roundToInt()
    val m = total / 60
    val s = total % 60
    return "%d:%02d".format(m, s)
}
