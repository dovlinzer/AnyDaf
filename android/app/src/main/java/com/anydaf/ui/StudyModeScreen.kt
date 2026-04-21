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
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.ui.graphics.Color
import androidx.activity.compose.BackHandler
import com.anydaf.ui.theme.AppBlue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
    val sessionObj = session
    val useWhiteBackground by contentViewModel.useWhiteBackground.collectAsState()
    val appBg = if (useWhiteBackground) MaterialTheme.colorScheme.background else AppBlue
    val appFg = if (useWhiteBackground) MaterialTheme.colorScheme.onBackground else Color.White

    BackHandler { onBack() }

    Scaffold(
        containerColor = appBg,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = appBg,
                    titleContentColor = appFg,
                    actionIconContentColor = appFg,
                    navigationIconContentColor = appFg
                ),
                title = {
                    if (sessionObj != null) {
                        Column {
                            Text(
                                "${sessionObj.tractate} ${sessionObj.daf}",
                                style = MaterialTheme.typography.titleLarge
                            )
                            sessionObj.currentSection?.let {
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
                    if (sessionObj != null && sessionObj.scope == StudyScope.FULL_DAF) {
                        val currentAmud = if ((sessionObj.amudBSectionIndex ?: Int.MAX_VALUE) <= sessionObj.currentSectionIndex) 1 else 0
                        val activeColors = if (!useWhiteBackground)
                            androidx.compose.material3.ButtonDefaults.buttonColors(
                                containerColor = Color.White.copy(alpha = 0.9f),
                                contentColor = AppBlue
                            ) else androidx.compose.material3.ButtonDefaults.buttonColors()
                        val inactiveColors = if (!useWhiteBackground)
                            androidx.compose.material3.ButtonDefaults.filledTonalButtonColors(
                                containerColor = Color.White.copy(alpha = 0.15f),
                                contentColor = Color.White
                            ) else androidx.compose.material3.ButtonDefaults.filledTonalButtonColors()
                        if (currentAmud == 0) {
                            Button(onClick = { studyViewModel.jumpToAmudA() }, modifier = Modifier.padding(end = 4.dp), colors = activeColors) { Text("a") }
                            FilledTonalButton(onClick = { studyViewModel.jumpToAmudB() }, modifier = Modifier.padding(end = 8.dp), colors = inactiveColors) { Text("b") }
                        } else {
                            FilledTonalButton(onClick = { studyViewModel.jumpToAmudA() }, modifier = Modifier.padding(end = 4.dp), colors = inactiveColors) { Text("a") }
                            Button(onClick = { studyViewModel.jumpToAmudB() }, modifier = Modifier.padding(end = 8.dp), colors = activeColors) { Text("b") }
                        }
                    }
                    if (sessionObj != null) {
                        val tractateIndex = allTractates.indexOfFirst { it.name == sessionObj.tractate }
                        val amud = if ((sessionObj.amudBSectionIndex ?: Int.MAX_VALUE) <= sessionObj.currentSectionIndex) 1 else 0
                        val isBookmarked = tractateIndex >= 0 && bookmarkViewModel.isBookmarked(tractateIndex, sessionObj.daf.toDouble(), amud)
                        IconButton(onClick = {
                            if (tractateIndex < 0) return@IconButton
                            if (isBookmarked) {
                                bookmarkViewModel.existing(tractateIndex, sessionObj.daf.toDouble(), amud)?.let { bookmarkViewModel.delete(it) }
                            } else {
                                bookmarkViewModel.add(
                                    com.anydaf.model.Bookmark(
                                        name = com.anydaf.model.Bookmark.defaultName(tractateIndex, sessionObj.daf.toDouble(), amud),
                                        tractateIndex = tractateIndex,
                                        daf = sessionObj.daf.toDouble(),
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
        StudyModeContent(
            studyViewModel = studyViewModel,
            bookmarkViewModel = bookmarkViewModel,
            contentViewModel = contentViewModel,
            resourcesViewModel = resourcesViewModel,
            onComplete = onBack,
            modifier = Modifier.padding(padding)
        )
    }
}

/**
 * The core study session content — tabs, loading states, prev/next buttons.
 * Used directly by [StudyModeScreen] (phone full-screen) and embedded in the
 * tablet right panel inside [ContentScreen].
 */
@Composable
fun StudyModeContent(
    studyViewModel: StudySessionViewModel,
    bookmarkViewModel: BookmarkViewModel,
    contentViewModel: ContentViewModel,
    resourcesViewModel: ResourcesViewModel,
    isInline: Boolean = false,
    onComplete: (() -> Unit)? = null,
    onStartStudy: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val session by studyViewModel.session.collectAsState()
    val isLoadingText by studyViewModel.isLoadingText.collectAsState()
    val isLoadingStudyContent by studyViewModel.isLoadingStudyContent.collectAsState()
    val error by studyViewModel.error.collectAsState()
    val isRateLimited by studyViewModel.isRateLimited.collectAsState()
    val rateLimitCountdown by studyViewModel.rateLimitCountdown.collectAsState()
    val studyFontSize by contentViewModel.studyFontSize.collectAsState()
    val useWhiteBackground by contentViewModel.useWhiteBackground.collectAsState()

    var selectedTab by remember { mutableIntStateOf(0) }

    LaunchedEffect(session?.currentSectionIndex) {
        if (selectedTab == 1 || selectedTab == 2) {
            studyViewModel.loadStudyContentForCurrentSection()
        }
    }

    LaunchedEffect(selectedTab, session?.tractate, session?.daf) {
        val s = session ?: return@LaunchedEffect
        if (selectedTab == 3) {
            resourcesViewModel.loadResources(s.tractate, s.daf)
        }
    }

    val currentSection = session?.currentSection
    val sessionObj = session

    CompositionLocalProvider(
        LocalStudyFontSize provides studyFontSize.spSize.sp,
        LocalIsBlueMode provides !useWhiteBackground
    ) {
        Column(modifier = modifier.fillMaxSize()) {

            // Inline tablet header — session info + A/B jump + bookmark
            // Inline tablet action bar — single compact row so it never grows tall.
            // The tractate/daf headline is omitted (visible in the left-panel pickers);
            // only the current-section label + A/B jumps + bookmark are shown.
            if (isInline && sessionObj != null) {
                val tractateIndex = allTractates.indexOfFirst { it.name == sessionObj.tractate }
                val amud = if ((sessionObj.amudBSectionIndex ?: Int.MAX_VALUE) <= sessionObj.currentSectionIndex) 1 else 0
                val isBookmarked = tractateIndex >= 0 && bookmarkViewModel.isBookmarked(tractateIndex, sessionObj.daf.toDouble(), amud)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    val blueMode = LocalIsBlueMode.current
                    Text(
                        text = currentSection?.title ?: "${sessionObj.tractate} ${sessionObj.daf}",
                        style = MaterialTheme.typography.bodySmall,
                        color = if (blueMode) Color.White.copy(alpha = 0.75f)
                                else MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                    if (sessionObj.scope == StudyScope.FULL_DAF) {
                        FilledTonalButton(onClick = { studyViewModel.jumpToAmudA() }) { Text("A") }
                        FilledTonalButton(onClick = { studyViewModel.jumpToAmudB() }) { Text("B") }
                    }
                    IconButton(onClick = {
                        if (tractateIndex < 0) return@IconButton
                        if (isBookmarked) {
                            bookmarkViewModel.existing(tractateIndex, sessionObj.daf.toDouble(), amud)?.let { bookmarkViewModel.delete(it) }
                        } else {
                            bookmarkViewModel.add(
                                com.anydaf.model.Bookmark(
                                    name = com.anydaf.model.Bookmark.defaultName(tractateIndex, sessionObj.daf.toDouble(), amud),
                                    tractateIndex = tractateIndex,
                                    daf = sessionObj.daf.toDouble(),
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
                androidx.compose.material3.HorizontalDivider()
            }

            sessionObj?.let {
                LinearProgressIndicator(
                    progress = { it.progress.toFloat() },
                    modifier = Modifier.fillMaxWidth()
                )
            }

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
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            Text("Error: $error", color = MaterialTheme.colorScheme.error)
                            Spacer(Modifier.height(12.dp))
                            Button(onClick = { studyViewModel.clearError() }) { Text("Dismiss") }
                        }
                    }
                }
                sessionObj == null -> {
                    if (isInline) {
                        LaunchedEffect(Unit) { onStartStudy?.invoke() }
                        Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                    } else {
                        Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                    }
                }
                sessionObj.isComplete -> {
                    Box(Modifier.fillMaxSize(), Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Session complete!", style = MaterialTheme.typography.headlineMedium)
                            Spacer(Modifier.height(16.dp))
                            Button(onClick = {
                                studyViewModel.endSession()
                                onComplete?.invoke()
                            }) { Text("Done") }
                        }
                    }
                }
                else -> {
                    ScrollableTabRow(
                        selectedTabIndex = selectedTab,
                        edgePadding = 0.dp,
                        indicator = { tabPositions ->
                            TabRowDefaults.SecondaryIndicator(
                                modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                                height = 4.dp,
                                color = Color(0xFF0059EA)
                            )
                        }
                    ) {
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
                            3 -> ResourcesTab(
                                viewModel = resourcesViewModel,
                                studyFontSize = studyFontSize,
                                onSizeChange = { contentViewModel.setStudyFontSize(it) }
                            )
                        }
                    }

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
