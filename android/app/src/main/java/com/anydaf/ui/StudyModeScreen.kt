package com.anydaf.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.NavigateNext
import androidx.compose.material.icons.filled.Print
import androidx.compose.foundation.BorderStroke
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.anydaf.data.api.ShiurClient
import com.anydaf.model.StudyScope
import com.anydaf.model.TextDisplayMode
import com.anydaf.model.allTractates
import com.anydaf.viewmodel.AudioViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.ResourcesViewModel
import com.anydaf.viewmodel.StudySessionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyModeScreen(
    studyViewModel: StudySessionViewModel,
    audioViewModel: AudioViewModel,
    contentViewModel: ContentViewModel,
    resourcesViewModel: ResourcesViewModel,
    onBack: () -> Unit
) {
    val session by studyViewModel.session.collectAsState()
    val sessionObj = session
    val useWhiteBackground by contentViewModel.useWhiteBackground.collectAsState()
    val appBg = if (useWhiteBackground) MaterialTheme.colorScheme.background else AppBlue
    val appFg = if (useWhiteBackground) MaterialTheme.colorScheme.onBackground else Color.White
    val isAudioStopped by audioViewModel.isStopped.collectAsState()

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
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (!isAudioStopped) {
                                    Icon(Icons.Default.Lock, null, Modifier.size(14.dp), tint = appFg.copy(alpha = 0.55f))
                                    Spacer(Modifier.width(6.dp))
                                }
                                Text(
                                    "${sessionObj.tractate} ${sessionObj.daf}",
                                    style = MaterialTheme.typography.titleLarge
                                )
                            }
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
                }
            )
        }
    ) { padding ->
        val context = LocalContext.current
        val printFontSize by contentViewModel.printFontSize.collectAsState()
        val printLineSpacing by contentViewModel.printLineSpacing.collectAsState()
        StudyModeContent(
            studyViewModel = studyViewModel,
            contentViewModel = contentViewModel,
            resourcesViewModel = resourcesViewModel,
            isAudioStopped = isAudioStopped,
            onComplete = onBack,
            onPrintTranslation = {
                val s = studyViewModel.session.value
                if (s != null) {
                    PrintHelper.print(
                        context,
                        PrintableContent.TalmudText(s.tractate, s.daf.toString(), s.sections, contentViewModel.textDisplayMode.value),
                        printFontSize,
                        printLineSpacing
                    )
                }
            },
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
    contentViewModel: ContentViewModel,
    resourcesViewModel: ResourcesViewModel,
    isInline: Boolean = false,
    textOnly: Boolean = false,
    isAudioStopped: Boolean = true,
    onComplete: (() -> Unit)? = null,
    onStartStudy: (() -> Unit)? = null,
    onPrintTranslation: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val session by studyViewModel.session.collectAsState()
    val isLoadingText by studyViewModel.isLoadingText.collectAsState()
    val isLoadingStudyContent by studyViewModel.isLoadingStudyContent.collectAsState()
    val error by studyViewModel.error.collectAsState()
    val isRateLimited by studyViewModel.isRateLimited.collectAsState()
    val rateLimitCountdown by studyViewModel.rateLimitCountdown.collectAsState()
    val studyFontSize by contentViewModel.studyFontSize.collectAsState()
    val printFontSize by contentViewModel.printFontSize.collectAsState()
    val printLineSpacing by contentViewModel.printLineSpacing.collectAsState()
    val useWhiteBackground by contentViewModel.useWhiteBackground.collectAsState()
    val appFg = if (useWhiteBackground) MaterialTheme.colorScheme.onBackground else Color.White

    // Phone Study mode (not textOnly, not inline): hide Text tab and start on Summary.
    val isPhoneStudy = !textOnly && !isInline
    val tabOffset = if (isPhoneStudy) 1 else 0
    val displayTabs = if (isPhoneStudy) listOf("Summary", "Quiz", "Resources") else listOf("Text", "Summary", "Quiz", "Resources")
    var selectedTab by remember { mutableIntStateOf(tabOffset) }

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

            // Inline tablet header — session info + A/B jumps
            if (isInline && sessionObj != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    val blueMode = LocalIsBlueMode.current
                    if (!isAudioStopped) {
                        Icon(Icons.Default.Lock, null, Modifier.size(12.dp), tint = (if (blueMode) Color.White else MaterialTheme.colorScheme.onSurfaceVariant).copy(alpha = 0.55f))
                        Spacer(Modifier.width(4.dp))
                    }
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
                }
                androidx.compose.material3.HorizontalDivider()
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
                    if (isInline || textOnly) {
                        LaunchedEffect(Unit) { onStartStudy?.invoke() }
                    }
                    Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                }
                sessionObj.isComplete -> {
                    if (textOnly) {
                        LaunchedEffect(Unit) { onStartStudy?.invoke() }
                        Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                    } else {
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
                }
                else -> {
                    // Section counter + print button row — always shown
                    val activeTabForHeader = if (textOnly) 0 else selectedTab
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(start = 16.dp, end = 16.dp, top = 2.dp, bottom = 2.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "Section ${sessionObj.currentSectionIndex + 1} / ${sessionObj.sections.size}",
                            style = MaterialTheme.typography.labelSmall,
                            color = appFg.copy(alpha = 0.6f)
                        )
                        Spacer(Modifier.weight(1f))
                        if (activeTabForHeader == 0 && onPrintTranslation != null) {
                            val blueMode = LocalIsBlueMode.current
                            IconButton(
                                onClick = onPrintTranslation,
                                modifier = Modifier.size(32.dp)
                            ) {
                                Icon(
                                    Icons.Default.Print,
                                    contentDescription = "Print",
                                    modifier = Modifier.size(18.dp),
                                    tint = (if (blueMode) Color.White else MaterialTheme.colorScheme.onSurface).copy(alpha = 0.5f)
                                )
                            }
                        }
                    }

                    if (!textOnly) {
                        val displaySelectedTab = selectedTab - tabOffset
                        ScrollableTabRow(
                            selectedTabIndex = displaySelectedTab,
                            edgePadding = 0.dp,
                            divider = {},
                            indicator = { tabPositions ->
                                TabRowDefaults.SecondaryIndicator(
                                    modifier = Modifier.tabIndicatorOffset(tabPositions[displaySelectedTab]),
                                    height = 4.dp,
                                    color = Color(0xFF0059EA)
                                )
                            }
                        ) {
                            displayTabs.forEachIndexed { displayIndex, title ->
                                val logicalTab = displayIndex + tabOffset
                                Tab(
                                    selected = selectedTab == logicalTab,
                                    onClick = {
                                        selectedTab = logicalTab
                                        if (logicalTab == 1 || logicalTab == 2) {
                                            studyViewModel.loadStudyContentForCurrentSection()
                                        }
                                    },
                                    text = { Text(title) }
                                )
                            }
                        }
                    }

                    val activeTab = if (textOnly) 0 else selectedTab
                    // Pre-compute nav state here so it can be captured by the bottomContent lambda
                    val isFirst = sessionObj.currentSectionIndex == 0
                    val isLast = sessionObj.currentSectionIndex == sessionObj.sections.size - 1
                    val tractateObj = allTractates.find { it.name == sessionObj.tractate }
                    val canGoPrevDaf = tractateObj != null && sessionObj.daf > tractateObj.startDaf
                    val canGoNextDaf = tractateObj != null && sessionObj.daf < tractateObj.endDaf

                    // Inline segment headers now render at each matched segment's exact raw
                    // position inside TranslationTab itself (see SectionStudyView.kt), rather
                    // than once per coarse section — just pass the full shiur segment list.
                    val shiurSegmentsForHeader by ShiurClient.segments.collectAsState()
                    val pendingScrollSefariaIndex by studyViewModel.pendingScrollSefariaIndex.collectAsState()
                    val activeSefariaIndex by studyViewModel.activeSefariaIndex.collectAsState()

                    // Segment pill strip — Translation tab only, same segments/titles as the
                    // shiur strip in ContentScreen.kt. Pinned above the scrollable tab content
                    // rather than inside it, mirroring how the shiur strip sits above ShiurTextView.
                    if (activeTab == 0) {
                        val curIdx = sessionObj.currentSectionIndex
                        val curRangeEnd = if (curIdx + 1 < sessionObj.sections.size)
                            sessionObj.sections[curIdx + 1].firstSegmentIndex else Int.MAX_VALUE
                        TextNavigationStrip(
                            currentSection = currentSection,
                            currentSectionRangeEnd = curRangeEnd,
                            appFg = appFg,
                            useWhiteBackground = useWhiteBackground,
                            activeSefariaIndex = activeSefariaIndex,
                            onJumpToSefariaIndex = { studyViewModel.jumpToSection(it) }
                        )
                    }

                    Box(modifier = Modifier.weight(1f)) {
                        when (activeTab) {
                            0 -> TranslationTab(
                                section = currentSection,
                                shiurSegments = shiurSegmentsForHeader,
                                pendingScrollSefariaIndex = pendingScrollSefariaIndex,
                                onScrollTargetConsumed = { studyViewModel.clearPendingScrollTarget() },
                                tractate = sessionObj.tractate,
                                textDisplayMode = contentViewModel.textDisplayMode.collectAsState().value,
                                onModeChange = { contentViewModel.selectTextDisplayMode(it) },
                                precedingContext = sessionObj.precedingContext,
                                followingContext = sessionObj.followingContext,
                                isFirstSection = sessionObj.currentSectionIndex == 0,
                                isLastSection = sessionObj.currentSectionIndex == sessionObj.sections.size - 1,
                                amudBStart = sessionObj.currentSectionIndex == (sessionObj.amudBSectionIndex ?: -1),
                                daf = sessionObj.daf,
                                // In textOnly mode the nav buttons live inside the scroll content
                                bottomContent = if (textOnly) {
                                    {
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(horizontal = 0.dp, vertical = 8.dp),
                                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            if (isFirst) {
                                                if (canGoPrevDaf) {
                                                    OutlinedButton(
                                                        onClick = {
                                                            studyViewModel.startSession(
                                                                tractate = sessionObj.tractate,
                                                                daf = sessionObj.daf - 1,
                                                                mode = studyViewModel.studyMode,
                                                                quizMode = studyViewModel.quizMode,
                                                                startAtLastSection = true
                                                            )
                                                        },
                                                        modifier = Modifier.weight(1f),
                                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                                        border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                                    ) {
                                                        Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                                                        Spacer(Modifier.width(4.dp))
                                                        Text("Prev Daf")
                                                    }
                                                } else {
                                                    Spacer(Modifier.weight(1f))
                                                }
                                            } else {
                                                OutlinedButton(
                                                    onClick = { studyViewModel.goToPreviousSection() },
                                                    modifier = Modifier.weight(1f),
                                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                                    border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                                ) {
                                                    Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                                                    Spacer(Modifier.width(4.dp))
                                                    Text("Previous")
                                                }
                                            }
                                            if (isLast) {
                                                if (canGoNextDaf) {
                                                    OutlinedButton(
                                                        onClick = {
                                                            studyViewModel.startSession(
                                                                tractate = sessionObj.tractate,
                                                                daf = sessionObj.daf + 1,
                                                                mode = studyViewModel.studyMode,
                                                                quizMode = studyViewModel.quizMode
                                                            )
                                                        },
                                                        modifier = Modifier.weight(1f),
                                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                                        border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                                    ) {
                                                        Text("Next Daf")
                                                        Spacer(Modifier.width(4.dp))
                                                        Icon(Icons.Default.NavigateNext, null)
                                                    }
                                                } else {
                                                    Spacer(Modifier.weight(1f))
                                                }
                                            } else {
                                                OutlinedButton(
                                                    onClick = { studyViewModel.advanceToNextSection() },
                                                    modifier = Modifier.weight(1f),
                                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                                    border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                                ) {
                                                    Text("Next")
                                                    Spacer(Modifier.width(4.dp))
                                                    Icon(Icons.Default.NavigateNext, null)
                                                }
                                            }
                                        }
                                    }
                                } else null
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
                                onSizeChange = { contentViewModel.setStudyFontSize(it) },
                                printFontSize = printFontSize,
                                printLineSpacing = printLineSpacing
                            )
                        }
                    }

                    // Nav row below the content area — only for non-textOnly modes
                    // (in textOnly mode the buttons are inside the TranslationTab scroll content)
                    if (!textOnly) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            // Left: "← Prev Daf" at first section, "← Previous" otherwise
                            if (isFirst) {
                                if (canGoPrevDaf) {
                                    OutlinedButton(
                                        onClick = {
                                            studyViewModel.startSession(
                                                tractate = sessionObj.tractate,
                                                daf = sessionObj.daf - 1,
                                                mode = studyViewModel.studyMode,
                                                quizMode = studyViewModel.quizMode,
                                                startAtLastSection = true
                                            )
                                        },
                                        modifier = Modifier.weight(1f),
                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                        border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                    ) {
                                        Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                                        Spacer(Modifier.width(4.dp))
                                        Text("Prev Daf")
                                    }
                                } else {
                                    Spacer(Modifier.weight(1f))
                                }
                            } else {
                                OutlinedButton(
                                    onClick = { studyViewModel.goToPreviousSection() },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                    border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                ) {
                                    Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                                    Spacer(Modifier.width(4.dp))
                                    Text("Previous")
                                }
                            }
                            // Right: "Next →" within daf, "Next Daf →" at last section
                            if (isLast) {
                                if (canGoNextDaf) {
                                    OutlinedButton(
                                        onClick = {
                                            studyViewModel.startSession(
                                                tractate = sessionObj.tractate,
                                                daf = sessionObj.daf + 1,
                                                mode = studyViewModel.studyMode,
                                                quizMode = studyViewModel.quizMode
                                            )
                                        },
                                        modifier = Modifier.weight(1f),
                                        colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                        border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
                                    ) {
                                        Text("Next Daf")
                                        Spacer(Modifier.width(4.dp))
                                        Icon(Icons.Default.NavigateNext, null)
                                    }
                                } else {
                                    Spacer(Modifier.weight(1f))
                                }
                            } else {
                                OutlinedButton(
                                    onClick = { studyViewModel.advanceToNextSection() },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = appFg),
                                    border = BorderStroke(1.dp, appFg.copy(alpha = 0.5f))
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

/**
 * Pill strip for jumping the Sefaria text to a shiur macro segment — the Translation-tab
 * counterpart of the shiur chip strip in ContentScreen.kt. Uses the same ShiurClient.segments
 * (same shiur, same titles) so the two navigation strips always agree.
 */
@Composable
private fun TextNavigationStrip(
    currentSection: com.anydaf.model.StudySection?,
    currentSectionRangeEnd: Int,
    appFg: Color,
    useWhiteBackground: Boolean,
    // The segment explicitly navigated to (pill tap or mode-switch sync) — see
    // StudySessionViewModel.activeSefariaIndex.
    activeSefariaIndex: Int?,
    onJumpToSefariaIndex: (Int) -> Unit
) {
    val shiurSegments by ShiurClient.segments.collectAsState()
    if (shiurSegments.isEmpty() || currentSection == null) return

    // Prefers the segment explicitly navigated to, as long as it's still within the current
    // section's range: several matched segments can share one coarse section, and without this,
    // tapping any of the earlier ones would always show whichever has the largest anchor as
    // active instead of the one actually tapped. Falls back to a point lookup at the section's
    // start otherwise (e.g. after Prev/Next-section navigation, or on first load — a fresh look
    // at the top of the section should resolve to the FIRST segment it contains, not whichever
    // anchors last). Mirrors activeShiurSegmentIndex in iOS's StudyModeView.swift.
    val activeIndex = remember(shiurSegments, currentSection.firstSegmentIndex, currentSectionRangeEnd, activeSefariaIndex) {
        val start = currentSection.firstSegmentIndex
        val explicitIdx = activeSefariaIndex?.takeIf { it >= start && it < currentSectionRangeEnd }?.let { idx ->
            shiurSegments.indexOfFirst { it.sefariaIndex == idx && it.matched == true }.takeIf { it >= 0 }
        }
        explicitIdx ?: ShiurClient.owningSegmentIndex(start, shiurSegments)
    }

    val stripListState = rememberLazyListState()
    LaunchedEffect(activeIndex) {
        activeIndex?.let { stripListState.animateScrollToItem(it) }
    }
    LazyRow(
        state = stripListState,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        contentPadding = PaddingValues(horizontal = 12.dp),
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
    ) {
        itemsIndexed(shiurSegments) { index, seg ->
            val isActive = index == activeIndex
            // Disabled when we KNOW this segment has no real anchor of its own (matched ==
            // false — a carried-forward placeholder like "Introduction" that only inherits its
            // sefariaIndex from whatever it followed). matched == null (not yet computed for
            // this daf) stays enabled, same as before this field existed.
            val isUnmatched = seg.matched == false
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(50))
                    .background(if (isActive) appFg.copy(alpha = 0.85f) else appFg.copy(alpha = 0.15f))
                    .clickable(enabled = seg.sefariaIndex != null && !isUnmatched) {
                        seg.sefariaIndex?.let(onJumpToSefariaIndex)
                    }
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            ) {
                Text(
                    text = seg.displayTitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isActive) {
                        if (useWhiteBackground) Color.White else AppBlue
                    } else appFg.copy(alpha = if (seg.sefariaIndex == null || isUnmatched) 0.4f else 0.8f),
                    maxLines = 1
                )
            }
        }
    }
}
