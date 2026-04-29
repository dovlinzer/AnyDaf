package com.anydaf

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.viewmodel.compose.viewModel
import com.anydaf.ui.AnyDafNavGraph
import com.anydaf.ui.theme.AnyDafTheme
import com.anydaf.viewmodel.AudioViewModel
import com.anydaf.viewmodel.BookmarkViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.PdfViewModel
import com.anydaf.viewmodel.ResourcesViewModel
import com.anydaf.viewmodel.StudySessionViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Must be called before super.onCreate() — installs the splash screen
        // and transitions seamlessly into our custom SplashScreen composable.
        // Dismiss the system splash screen at the earliest possible moment —
        // our custom SplashScreen composable handles the branded delay.
        installSplashScreen().setKeepOnScreenCondition { false }
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val contentViewModel: ContentViewModel = viewModel()
            AnyDafTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val studyViewModel: StudySessionViewModel = viewModel()
                    val audioViewModel: AudioViewModel = viewModel()
                    val bookmarkViewModel: BookmarkViewModel = viewModel()
                    val pdfViewModel: PdfViewModel = viewModel()
                    val resourcesViewModel: ResourcesViewModel = viewModel()

                    AnyDafNavGraph(
                        contentViewModel = contentViewModel,
                        studyViewModel = studyViewModel,
                        audioViewModel = audioViewModel,
                        bookmarkViewModel = bookmarkViewModel,
                        pdfViewModel = pdfViewModel,
                        resourcesViewModel = resourcesViewModel,
                    )
                }
            }
        }
    }
}
