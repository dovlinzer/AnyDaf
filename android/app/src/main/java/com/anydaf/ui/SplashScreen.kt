package com.anydaf.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.anydaf.R
import kotlinx.coroutines.delay

// Background colour matches iOS SplashView: #1B3A8A (r=0.106, g=0.227, b=0.541)
private val SplashBlue = Color(red = 0.106f, green = 0.227f, blue = 0.541f)
private val SubtitleBlue = Color(red = 0.75f, green = 0.85f, blue = 1f)

@Composable
fun SplashScreen(onDone: () -> Unit) {
    LaunchedEffect(Unit) {
        delay(2000)
        onDone()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(SplashBlue)
    ) {
        // Centre column: app name, photo, subtitle
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.Center)
                .padding(horizontal = 32.dp)
                .padding(bottom = 120.dp),   // shift up to leave room for YCT logo
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = "AnyDaf",
                fontSize = 42.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )

            Image(
                painter = painterResource(id = R.drawable.rabbi_linzer),
                contentDescription = "Rabbi Dov Linzer",
                modifier = Modifier
                    .size(100.dp)
                    .clip(CircleShape),
                contentScale = ContentScale.Crop
            )

            Text(
                text = "Learn any daf with Rabbi Dov Linzer",
                fontSize = 17.sp,
                color = SubtitleBlue,
                textAlign = TextAlign.Center
            )
            Text(
                text = "Powered by YCT and Sefaria",
                fontSize = 14.sp,
                fontStyle = FontStyle.Italic,
                color = SubtitleBlue.copy(alpha = 0.75f),
                textAlign = TextAlign.Center
            )
        }

        // YCT logo anchored near the bottom, 50% screen width (mirrors iOS)
        Image(
            painter = painterResource(id = R.drawable.yct_logo),
            contentDescription = "Yeshivat Chovevei Torah",
            modifier = Modifier
                .fillMaxWidth(0.5f)
                .align(Alignment.BottomCenter)
                .padding(bottom = 96.dp),
            contentScale = ContentScale.Fit
        )
    }
}
