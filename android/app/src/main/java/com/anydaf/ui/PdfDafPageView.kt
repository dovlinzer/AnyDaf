package com.anydaf.ui

import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import coil.size.Size
import com.anydaf.model.Tractate
import com.anydaf.viewmodel.PdfViewModel

/**
 * Displays a Talmud daf page image loaded from Google Drive.
 * Mirrors iOS DafPageView + ZoomableAsyncImage.
 *
 * When no image is available for the tractate, renders nothing (caller
 * should check [PdfViewModel.hasPages] and conditionally show this view).
 */
@Composable
fun DafPageView(
    tractate: Tractate,
    daf: Double,
    amud: Int,                              // 0 = amud aleph (a), 1 = amud bet (b)
    pdfViewModel: PdfViewModel,
    onDafAmudChange: (daf: Int, amud: Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val dafInt = daf.toInt()
    val sideA = amud == 0
    val imageUrl = pdfViewModel.imageUrl(tractate.name, dafInt, sideA)

    // Reset zoom when page changes
    var scale by remember { mutableFloatStateOf(1f) }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(tractate.name, daf, amud) {
        scale = 1f; offsetX = 0f; offsetY = 0f
    }

    fun advanceAmud() {
        if (amud == 0) onDafAmudChange(dafInt, 1)
        else if (dafInt < tractate.endDaf) onDafAmudChange(dafInt + 1, 0)
    }

    fun retreatAmud() {
        if (amud == 1) onDafAmudChange(dafInt, 0)
        else if (dafInt > tractate.startDaf) onDafAmudChange(dafInt - 1, 1)
    }

    if (imageUrl == null) {
        Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            Text(
                "No image for daf $dafInt${if (sideA) "a" else "b"}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
        return
    }

    val context = LocalContext.current

    Box(modifier = modifier.fillMaxWidth()) {

        // ── Image with pinch-to-zoom ──────────────────────────────────────
        // Size.ORIGINAL bypasses Coil's layout-size measurement (unreliable in
        // weight(1f) layouts on physical devices). FilterQuality.High enables
        // bicubic resampling on Android 12+.
        SubcomposeAsyncImage(
            model = ImageRequest.Builder(context)
                .data(imageUrl)
                .size(Size.ORIGINAL)
                .build(),
            contentDescription = "${tractate.name} $dafInt${if (sideA) "a" else "b"}",
            contentScale = ContentScale.Fit,
            alignment = Alignment.TopCenter,
            filterQuality = FilterQuality.High,
            loading = {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(modifier = Modifier.size(32.dp))
                }
            },
            error = {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Image unavailable", style = MaterialTheme.typography.bodySmall)
                }
            },
            modifier = Modifier
                .fillMaxSize()
                .clip(RoundedCornerShape(16.dp))
                .pointerInput(Unit) {
                    detectTransformGestures { _, pan, zoom, _ ->
                        val newScale = (scale * zoom).coerceIn(1f, 6f)
                        scale = newScale
                        if (newScale > 1f) {
                            offsetX += pan.x
                            offsetY += pan.y
                        } else {
                            // At 1× snap back to center and detect swipe
                            val dx = pan.x
                            if (kotlin.math.abs(dx) > 40) {
                                if (dx < 0) advanceAmud() else retreatAmud()
                            }
                            offsetX = 0f
                            offsetY = 0f
                        }
                    }
                }
                .graphicsLayer(
                    scaleX = scale,
                    scaleY = scale,
                    translationX = offsetX,
                    translationY = offsetY
                )
        )

        // ── Left / right chevron arrows at mid-height ─────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.Center)
                .padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { retreatAmud() }) {
                Icon(
                    Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                    contentDescription = "Previous amud",
                    modifier = Modifier.size(36.dp),
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
                )
            }
            Spacer(Modifier.width(0.dp).weight(1f))
            IconButton(onClick = { advanceAmud() }) {
                Icon(
                    Icons.AutoMirrored.Filled.KeyboardArrowRight,
                    contentDescription = "Next amud",
                    modifier = Modifier.size(36.dp),
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
                )
            }
        }
    }
}
