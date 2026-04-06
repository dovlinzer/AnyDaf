package com.anydaf.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.NavigateNext
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.anydaf.model.StudyScope
import com.anydaf.model.allTractates
import com.anydaf.viewmodel.BookmarkViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.ResourcesViewModel
import com.anydaf.viewmodel.StudySessionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyModeScreen(
    studyViewModel: StudySessionViewModel,
    bookmarkViewModel: BookmarkViewModel,
    contentViewModel: ContentViewModel,
    resourcesViewModel: ResourcesViewModel,
    onBack: () -> Unit
) {
    val session by studyViewModel.session.collectAsState()
    val isLoadingText by studyViewModel.isLoadingText.collectAsState()
    val isLoadingStudyContent by studyViewModel.isLoadingStudyContent.collectAsState()
    val error by studyViewModel.error.collectAsState()
    val isRateLimited by studyViewModel.isRateLimited.collectAsState()
    val rateLimitCountdown by studyViewModel.rateLimitCountdown.collectAsState()

    var selectedTab by remember { mutableIntStateOf(0) }  // 0=Translation, 1=Study, 2=Quiz, 3=Resources

    BackHandler { onBack() }

    LaunchedEffect(session?.currentSectionIndex) {
        if (selectedTab == 1 || selectedTab == 2) {
            studyViewModel.loadStudyContentForCurrentSection()
        }
    }

    // Load resources when tab 3 is shown; reset when daf changes
    LaunchedEffect(selectedTab, session?.tractate, session?.daf) {
        val s = session ?: return@LaunchedEffect
        if (selectedTab == 3) {
            resourcesViewModel.loadResources(s.tractate, s.daf)
        }
    }
    LaunchedEffect(session?.daf) {
        resourcesViewModel.reset()
    }

    val currentSection = session?.currentSection
    val sessionObj = session

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    if (sessionObj != null) {
                        Column {
                            Text(
                                "${sessionObj.tractate} ${sessionObj.daf}",
                                style = MaterialTheme.typography.titleLarge
                            )
                            currentSection?.let {
                                Text(it.title, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    } else {
                        Text("Study")
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
                actions = {
                    // Amud A/B jump buttons
                    if (sessionObj != null && sessionObj.scope == StudyScope.FULL_DAF) {
                        FilledTonalButton(
                            onClick = { studyViewModel.jumpToAmudA() },
                            modifier = Modifier.padding(end = 4.dp)
                        ) { Text("A") }
                        FilledTonalButton(
                            onClick = { studyViewModel.jumpToAmudB() },
                            modifier = Modifier.padding(end = 8.dp)
                        ) { Text("B") }
                    }
                    // Bookmark
                    if (sessionObj != null) {
                        val tractateIndex = allTractates.indexOfFirst { it.name == sessionObj.tractate }
                        val amud = if ((sessionObj.amudBSectionIndex ?: Int.MAX_VALUE) <= sessionObj.currentSectionIndex) 1 else 0
                        val isBookmarked = tractateIndex >= 0 && bookmarkViewModel.isBookmarked(tractateIndex, sessionObj.daf, amud)
                        IconButton(onClick = {
                            if (tractateIndex < 0) return@IconButton
                            if (isBookmarked) {
                                bookmarkViewModel.existing(tractateIndex, sessionObj.daf, amud)?.let { bookmarkViewModel.delete(it) }
                            } else {
                                bookmarkViewModel.add(
                                    com.anydaf.model.Bookmark(
                                        name = com.anydaf.model.Bookmark.defaultName(tractateIndex, sessionObj.daf, amud),
                                        tractateIndex = tractateIndex,
                                        daf = sessionObj.daf,
                                        amud = amud,
                                        studySectionIndex = sessionObj.currentSectionIndex
                                    )
                                )
                            }
                        }) {
                            Icon(
                                if (isBookmarked) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                                "Bookmark"
                            )
                        }
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Progress bar
            sessionObj?.let {
                LinearProgressIndicator(
                    progress = { it.progress.toFloat() },
                    modifier = Modifier.fillMaxWidth()
                )
            }

            // Rate limit warning
            if (isRateLimited) {
                androidx.compose.material3.Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        "Rate limit reached. Retrying in $rateLimitCountdown seconds…",
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                }
            }

            when {
                isLoadingText -> {
                    Box(Modifier.fillMaxSize(), Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator()
                            Spacer(Modifier.height(12.dp))
                            Text("Loading text…")
                        }
                    }
                }
                error != null -> {
                    Box(Modifier.fillMaxSize(), Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                            Text("Error: $error", color = MaterialTheme.colorScheme.error)
                            Spacer(Modifier.height(12.dp))
                            Button(onClick = { studyViewModel.clearError() }) { Text("Dismiss") }
                        }
                    }
                }
                sessionObj == null -> {
                    Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                }
                sessionObj.isComplete -> {
                    Box(Modifier.fillMaxSize(), Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Session complete!", style = MaterialTheme.typography.headlineMedium)
                            Spacer(Modifier.height(16.dp))
                            Button(onClick = onBack) { Text("Done") }
                        }
                    }
                }
                else -> {
                    // Tab bar
                    ScrollableTabRow(selectedTabIndex = selectedTab) {
                        listOf("Text", "Summary", "Quiz", "Resources").forEachIndexed { index, title ->
                            Tab(
                                selected = selectedTab == index,
                                onClick = {
                                    selectedTab = index
                                    if (index == 1 || index == 2) {
                                        studyViewModel.loadStudyContentForCurrentSection()
                                    }
                                },
                                text = { Text(title) }
                            )
                        }
                    }

                    // Tab content
                    Box(modifier = Modifier.weight(1f)) {
                        when (selectedTab) {
                            0 -> TranslationTab(
                                section = currentSection,
                                tractate = sessionObj.tractate,
                                sourceDisplayMode = contentViewModel.sourceDisplayMode.collectAsState().value,
                                precedingContext = sessionObj.precedingContext,
                                followingContext = sessionObj.followingContext,
                                isFirstSection = sessionObj.currentSectionIndex == 0,
                                isLastSection = sessionObj.currentSectionIndex == sessionObj.sections.size - 1
                            )
                            1 -> StudyTab(
                                section = currentSection,
                                isLoading = isLoadingStudyContent,
                                onLoad = { studyViewModel.loadStudyContentForCurrentSection() }
                            )
                            2 -> QuizTab(
                                section = currentSection,
                                isLoading = isLoadingStudyContent,
                                studyViewModel = studyViewModel,
                                onLoad = { studyViewModel.loadStudyContentForCurrentSection() }
                            )
                            3 -> ResourcesTab(viewModel = resourcesViewModel)
                        }
                    }

                    // Previous / Next section buttons
                    if (!sessionObj.isComplete) {
                        val isFirst = sessionObj.currentSectionIndex == 0
                        val isLast = sessionObj.currentSectionIndex == sessionObj.sections.size - 1
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            if (!isFirst) {
                                androidx.compose.material3.OutlinedButton(
                                    onClick = { studyViewModel.goToPreviousSection() },
                                    modifier = Modifier.weight(1f)
                                ) {
                                    Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                                    Spacer(Modifier.width(4.dp))
                                    Text("Previous")
                                }
                            }
                            if (!isLast) {
                                Button(
                                    onClick = { studyViewModel.advanceToNextSection() },
                                    modifier = Modifier.weight(1f)
                                ) {
                                    Text("Next")
                                    Spacer(Modifier.width(4.dp))
                                    Icon(Icons.Default.NavigateNext, null)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
