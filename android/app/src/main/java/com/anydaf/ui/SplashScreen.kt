package com.anydaf.ui

import android.net.Uri
import android.widget.VideoView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.anydaf.R
import kotlinx.coroutines.delay

// Background colour matches iOS SplashView: #1B3A8A (r=0.106, g=0.227, b=0.541)
private val SplashBlue = Color(red = 0.106f, green = 0.227f, blue = 0.541f)
private val SubtitleBlue = Color(red = 0.75f, green = 0.85f, blue = 1f)

// yct_splash.mp4 is cropped to the YCT logo's own proportions (836x514) so the
// rounded box matches the logo's shape instead of leaving empty space above/below it.
private const val LogoAspectRatio: Float = 836f / 514f

@Composable
fun SplashScreen(onDone: () -> Unit) {
    LaunchedEffect(Unit) {
        delay(4200)
        onDone()
    }

    val configuration = LocalConfiguration.current
    val shortDp = minOf(configuration.screenWidthDp, configuration.screenHeightDp)
    val screenHeightDp = configuration.screenHeightDp
    val isTablet = configuration.smallestScreenWidthDp >= 600

    val rabbiImageSize = (shortDp * if (isTablet) 0.21f else 0.28f).dp
    // Matches AnyTorah's fixed 200dp logo size (AnyTorah isn't proportional to screen
    // width) on a typical phone; tablet keeps the same relative scale-down.
    val logoWidth = (shortDp * if (isTablet) 0.42f else 0.65f).dp
    val logoHeight = logoWidth / LogoAspectRatio
    val logoBottomPad = (screenHeightDp * 0.075f).dp

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(SplashBlue)
    ) {
        // Main content centered
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.Center)
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
                    .size(rabbiImageSize)
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

        // Logo animation pinned near the bottom
        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            AndroidView(
                factory = { ctx ->
                    VideoView(ctx).apply {
                        val uri = Uri.parse("android.resource://${ctx.packageName}/${R.raw.yct_splash}")
                        setVideoURI(uri)
                        setOnPreparedListener { mp ->
                            mp.isLooping = true
                            mp.setVolume(0f, 0f)
                            start()
                        }
                    }
                },
                modifier = Modifier
                    .width(logoWidth)
                    .height(logoHeight)
                    .clip(RoundedCornerShape(16.dp))
            )
            Spacer(Modifier.height(logoBottomPad))
        }
    }
}
