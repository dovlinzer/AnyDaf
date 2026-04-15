package com.anydaf.ui

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.anydaf.viewmodel.AudioViewModel
import com.anydaf.viewmodel.BookmarkViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.PdfViewModel
import com.anydaf.viewmodel.ResourcesViewModel
import com.anydaf.viewmodel.StudySessionViewModel

@Composable
fun AnyDafNavGraph(
    contentViewModel: ContentViewModel,
    studyViewModel: StudySessionViewModel,
    audioViewModel: AudioViewModel,
    bookmarkViewModel: BookmarkViewModel,
    pdfViewModel: PdfViewModel,
    resourcesViewModel: ResourcesViewModel,
) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = "splash",
        enterTransition = { fadeIn() },
        exitTransition = { fadeOut() }
    ) {
        composable("splash") {
            SplashScreen(onDone = {
                navController.navigate("content") {
                    popUpTo("splash") { inclusive = true }
                }
            })
        }

        composable("content") {
            ContentScreen(
                contentViewModel = contentViewModel,
                audioViewModel = audioViewModel,
                bookmarkViewModel = bookmarkViewModel,
                pdfViewModel = pdfViewModel,
                onStartStudy = { tractate, daf, mode, quizMode ->
                    navController.navigate("study/$tractate/$daf")
                    studyViewModel.startSession(tractate, daf, mode, quizMode)
                },
                onOpenBookmarks = { navController.navigate("bookmarks") },
                onOpenSettings = { navController.navigate("settings") }
            )
        }

        composable("study/{tractate}/{daf}") {
            StudyModeScreen(
                studyViewModel = studyViewModel,
                bookmarkViewModel = bookmarkViewModel,
                contentViewModel = contentViewModel,
                resourcesViewModel = resourcesViewModel,
                onBack = {
                    resourcesViewModel.dismissArticle()
                    studyViewModel.endSession()
                    navController.popBackStack()
                }
            )
        }

        composable("bookmarks") {
            BookmarksScreen(
                bookmarkViewModel = bookmarkViewModel,
                onSelectBookmark = { tractateIndex, daf, _ ->
                    contentViewModel.selectTractate(tractateIndex)
                    contentViewModel.selectDaf(daf)
                    navController.popBackStack()
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable("settings") {
            SettingsScreen(
                contentViewModel = contentViewModel,
                onBack = { navController.popBackStack() },
                onAbout = { navController.navigate("about") }
            )
        }

        composable("about") {
            AboutScreen(onBack = { navController.popBackStack() })
        }
    }
}
