package com.anydaf.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.anydaf.BuildConfig
import com.anydaf.data.api.Dedication
import com.anydaf.ui.theme.AppBlue

@Composable
fun DedicationDialog(dedication: Dedication, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            if (!dedication.photoURL.isNullOrBlank()) {
                val authedUrl = dedication.photoURL.replace(
                    "/storage/v1/object/public/",
                    "/storage/v1/object/"
                )
                val imageRequest = ImageRequest.Builder(LocalContext.current)
                    .data(authedUrl)
                    .addHeader("apikey", BuildConfig.SUPABASE_ANON_KEY)
                    .addHeader("Authorization", "Bearer ${BuildConfig.SUPABASE_ANON_KEY}")
                    .build()
                SubcomposeAsyncImage(
                    model = imageRequest,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(160.dp)
                        .clip(CircleShape),
                    error = {
                        Icon(
                            imageVector = Icons.Default.MenuBook,
                            contentDescription = null,
                            tint = AppBlue,
                            modifier = Modifier.size(40.dp)
                        )
                    }
                )
            } else {
                Icon(
                    imageVector = Icons.Default.MenuBook,
                    contentDescription = null,
                    tint = AppBlue,
                    modifier = Modifier.size(40.dp)
                )
            }
        },
        title = {
            Text(
                text = dedication.periodTitle,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        },
        text = {
            Text(
                text = dedication.formattedMessage,
                textAlign = TextAlign.Center,
                lineHeight = 22.sp
            )
        },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Continue Learning")
            }
        }
    )
}
