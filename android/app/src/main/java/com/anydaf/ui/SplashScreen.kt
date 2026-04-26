package com.anydaf.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.ui.platform.LocalConfiguration
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

    val configuration = LocalConfiguration.current
    val shortDp = minOf(configuration.screenWidthDp, configuration.screenHeightDp)

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(SplashBlue),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(14.dp)
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
                    .size((shortDp * 0.28f).dp)
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
            Spacer(Modifier.height(8.dp))
            Image(
                painter = painterResource(id = R.drawable.yct_logo),
                contentDescription = "Yeshivat Chovevei Torah",
                modifier = Modifier.width((shortDp * 0.26f).dp),
                contentScale = ContentScale.Fit
            )
        }
    }
}
