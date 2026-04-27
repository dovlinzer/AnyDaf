package com.anydaf.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.requiredWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.FormatListBulleted
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.TopAppBarDefaults
import android.content.Intent
import android.net.Uri
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.compose.ui.graphics.Color
import com.anydaf.ui.theme.AppBlue
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.anydaf.data.api.FeedManager
import com.anydaf.data.api.ShiurClient
import com.anydaf.model.Bookmark
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.sp
import com.anydaf.model.QuizMode
import com.anydaf.model.StudyMode
import com.anydaf.model.Tractate
import com.anydaf.model.allTractates
import com.anydaf.viewmodel.AudioViewModel
import com.anydaf.viewmodel.BookmarkViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.PdfViewModel
import com.anydaf.viewmodel.ResourcesViewModel
import com.anydaf.viewmodel.StudySessionViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContentScreen(
    contentViewModel: ContentViewModel,
    audioViewModel: AudioViewModel,
    bookmarkViewModel: BookmarkViewModel,
    pdfViewModel: PdfViewModel,
    studyViewModel: StudySessionViewModel,
    resourcesViewModel: ResourcesViewModel,
    onStartStudy: (tractate: String, daf: Int, mode: StudyMode, quizMode: QuizMode) -> Unit,
    onOpenBookmarks: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val selectedTractateIndex by contentViewModel.selectedTractateIndex.collectAsState()
    val selectedDaf by contentViewModel.selectedDaf.collectAsState()
    val selectedAmud by contentViewModel.selectedAmud.collectAsState()
    val quizMode by contentViewModel.quizMode.collectAsState()
    val studyMode by contentViewModel.studyMode.collectAsState()
    val isFetchingDafYomi by contentViewModel.isFetchingDafYomi.collectAsState()
    val isAudioStopped by audioViewModel.isStopped.collectAsState()
    val showDonationNudge by contentViewModel.showDonationNudge.collectAsState()

    val studyFontSize by contentViewModel.studyFontSize.collectAsState()
    val useWhiteBackground by contentViewModel.useWhiteBackground.collectAsState()
    val tabletRightPanelMode by contentViewModel.tabletRightPanelMode.collectAsState()
    val isTablet = LocalConfiguration.current.screenWidthDp >= 600
    val appBg = if (useWhiteBackground) MaterialTheme.colorScheme.background else AppBlue
    val appFg = if (useWhiteBackground) MaterialTheme.colorScheme.onBackground else Color.White

    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) { contentViewModel.onAppForegrounded() }
            override fun onStop(owner: LifecycleOwner) { contentViewModel.onAppBackgrounded() }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    if (showDonationNudge) {
        DonationNudgeDialog(
            onDonate = {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://wl.donorperfect.net/weblink/weblink.aspx?name=yctorah&id=2"))
                context.startActivity(intent)
                contentViewModel.recordDonateClicked()
                contentViewModel.dismissDonationNudge()
            },
            onDismiss = { contentViewModel.dismissDonationNudge() }
        )
    }
    
    val episodeIndex by FeedManager.episodeIndex.collectAsState()
    val isLoadingFeed by FeedManager.isLoading.collectAsState()
    val shiurSegments by ShiurClient.segments.collectAsState()
    val shiurSegmentIndex by ShiurClient.currentSegmentIndex.collectAsState()
    val shiurRewrite by ShiurClient.shiurRewrite.collectAsState()
    val shiurFinal by ShiurClient.shiurFinal.collectAsState()
    val shiurShowSources by contentViewModel.shiurShowSources.collectAsState()
    val currentTime by audioViewModel.currentTime.collectAsState()
    val duration by audioViewModel.duration.collectAsState()
    var showShiurText by remember { mutableStateOf(false) }

    val tractate = allTractates[selectedTractateIndex]

    // Tractate/daf frozen at the moment audio starts — stays fixed while picker freely moves.
    var audioLockedTractate by remember { mutableStateOf(tractate.name) }
    var audioLockedDaf by remember { mutableStateOf(selectedDaf) }

    // Tractate/daf to display and use for study sessions (locked to playing daf while audio plays).
    val playingTractate = if (isAudioStopped) tractate.name else audioLockedTractate
    val playingDaf = if (isAudioStopped) selectedDaf else audioLockedDaf

    // Always load on first appearance — mirrors iOS onAppear (no audio guard needed here).
    LaunchedEffect(Unit) {
        ShiurClient.load(tractate.name, selectedDaf)
    }

    // Reload when daf/tractate changes — skip when audio is playing (locked to playing daf).
    LaunchedEffect(tractate.name, selectedDaf) {
        if (isAudioStopped) ShiurClient.load(tractate.name, selectedDaf)
    }

    // When audio starts, freeze the locked daf. When it stops, sync to selected daf.
    LaunchedEffect(isAudioStopped) {
        if (!isAudioStopped) {
            audioLockedTractate = tractate.name
            audioLockedDaf = selectedDaf
        } else {
            ShiurClient.load(tractate.name, selectedDaf)
        }
    }

    // Fall back to Daf view automatically if the new daf has no shiur text.
    LaunchedEffect(shiurRewrite) {
        if (shiurRewrite == null) showShiurText = false
    }

    // Reset study session when daf/tractate changes — skip when audio is playing.
    LaunchedEffect(tractate.name, selectedDaf) {
        if (isAudioStopped) studyViewModel.endSession()
    }

    // Keep the active chapter marker in sync with audio playback.
    LaunchedEffect(currentTime) {
        ShiurClient.updateCurrentSegment(currentTime)
    }
    // Auto-refresh episode index when SoundCloud stream resolution fails, then retry once.
    val resolutionFailed by audioViewModel.resolutionFailed.collectAsState()
    var hasAutoRefreshedForAudio by remember { mutableStateOf(false) }
    LaunchedEffect(resolutionFailed) {
        if (resolutionFailed && !hasAutoRefreshedForAudio) {
            hasAutoRefreshedForAudio = true
            FeedManager.forceRefresh()
            // Re-look up URL — may now be a direct RSS MP3 rather than a soundcloud-track stub
            val freshUrl = FeedManager.episodeIndex.value[tractate.name]?.get(selectedDaf)
            if (freshUrl != null) {
                audioViewModel.play(freshUrl, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}")
            }
        }
    }

    val isBookmarked = bookmarkViewModel.isBookmarked(selectedTractateIndex, selectedDaf, selectedAmud)
    var pendingNewBookmark by remember { mutableStateOf<Bookmark?>(null) }

    // Derived synchronously from the StateFlow — updates automatically when feed loads
    val audioUrl = episodeIndex[tractate.name]?.get(selectedDaf)
    val hasAudio = audioUrl != null

    // Hoisted above Scaffold so the TopAppBar can show compact pickers when collapsed.
    var collapsedSide by remember { mutableStateOf("NONE") } // "NONE", "LEFT", "RIGHT"

    // Tablet split state — hoisted so drag geometry and collapse handle share the same state.
    val density = LocalDensity.current
    var leftWidthPx by remember { mutableFloatStateOf(with(density) { 380.dp.toPx() }) }
    var savedWidthPx by remember { mutableFloatStateOf(with(density) { 380.dp.toPx() }) }

    // Restore persisted tablet layout state once the ViewModel has loaded from DataStore.
    val tabletCollapsedSide by contentViewModel.tabletCollapsedSide.collectAsState()
    val tabletSplitDp by contentViewModel.tabletSplitDp.collectAsState()
    LaunchedEffect(tabletCollapsedSide, tabletSplitDp) {
        if (tabletCollapsedSide.isNotEmpty() && tabletSplitDp >= 0.0) {
            collapsedSide = tabletCollapsedSide
            val px = with(density) { tabletSplitDp.toFloat().dp.toPx() }
            leftWidthPx = px
            savedWidthPx = px
        }
    }

    Scaffold(
        containerColor = appBg,
        topBar = {
            CenterAlignedTopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = appBg,
                    titleContentColor = appFg,
                    actionIconContentColor = appFg,
                    navigationIconContentColor = appFg
                ),
                navigationIcon = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = onOpenSettings) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                        if (isFetchingDafYomi) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp))
                        } else {
                            IconButton(onClick = { contentViewModel.fetchTodaysDaf() }) {
                                Column(horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                                    Icon(
                                        Icons.Default.Today,
                                        contentDescription = "Today's Daf Yomi",
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Text(
                                        text = "דף יומי",
                                        fontSize = 7.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        lineHeight = 7.sp
                                    )
                                }
                            }
                        }
                    }
                },
                title = {
                if (isTablet && collapsedSide == "RIGHT") {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        CompactTabletPickers(
                            selectedTractateIndex = selectedTractateIndex,
                            selectedDaf = selectedDaf,
                            selectedAmud = selectedAmud,
                            tractate = tractate,
                            episodeIndex = episodeIndex,
                            contentViewModel = contentViewModel,
                            contentColor = appFg
                        )
                    }
                } else {
                    Text(
                        "AnyDaf",
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.fillMaxWidth(),
                        textAlign = TextAlign.Center
                    )
                }
            },
                actions = {
                    IconButton(
                        onClick = onOpenBookmarks,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(Icons.Default.FormatListBulleted, contentDescription = "Bookmark List")
                    }
                    IconButton(
                        onClick = {
                            if (isBookmarked) {
                                bookmarkViewModel.existing(selectedTractateIndex, selectedDaf, selectedAmud)
                                    ?.let { bookmarkViewModel.delete(it) }
                            } else {
                                pendingNewBookmark = Bookmark(
                                    name = Bookmark.defaultName(selectedTractateIndex, selectedDaf, selectedAmud),
                                    tractateIndex = selectedTractateIndex,
                                    daf = selectedDaf,
                                    amud = selectedAmud
                                )
                            }
                        },
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            if (isBookmarked) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                            contentDescription = if (isBookmarked) "Remove Bookmark" else "Add Bookmark"
                        )
                    }
                }
            )
        }
    ) { padding ->
        if (isTablet) {
            // ── Tablet: two-column layout with draggable divider ──────────────
            val minLeftPx = with(density) { 200.dp.toPx() }
            val maxLeftPx = with(density) { 540.dp.toPx() }
            // Collapse intent: dragging this far in one direction triggers collapse regardless
            // of absolute panel position.
            val collapseIntentPx = with(density) { 100.dp.toPx() }

            val rightPanelMode = when (tabletRightPanelMode) {
                "STUDY" -> "STUDY"
                "SHIUR" -> "SHIUR"
                else -> if (shiurRewrite != null) "SHIUR" else "STUDY"
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
            ) {
                // ── Two-column split: daf image (left) | divider | Shiur/Study (right) ──
                // Pickers live inside the left Column — clipped by requiredWidth + clip(RectangleShape).
                // Collapse is intent-based (cumulative drag ≥ 100 dp) so the pickers' intrinsic
                // minimum width no longer blocks the divider from reaching either edge.
                Row(modifier = Modifier.weight(1f).fillMaxWidth()) {

                    // ── Left panel ────────────────────────────────────────────────
                    if (collapsedSide != "LEFT") Column(
                        modifier = Modifier
                            .then(
                                if (collapsedSide == "RIGHT") Modifier.weight(1f)
                                else Modifier.requiredWidth(with(density) { leftWidthPx.toDp() })
                            )
                            .fillMaxHeight()
                            .clip(RectangleShape)
                            .padding(horizontal = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        // Pickers at top — hidden when right panel is collapsed (shown in TopAppBar instead).
                        if (collapsedSide != "RIGHT") {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .border(1.dp, appFg.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
                                        .padding(horizontal = 12.dp, vertical = 4.dp)
                                ) {
                                    CompactTabletPickers(
                                        selectedTractateIndex = selectedTractateIndex,
                                        selectedDaf = selectedDaf,
                                        selectedAmud = selectedAmud,
                                        tractate = tractate,
                                        episodeIndex = episodeIndex,
                                        contentViewModel = contentViewModel,
                                        contentColor = appFg
                                    )
                                }
                            } // Row (centering)
                        }
                        Box(modifier = Modifier.weight(1f).fillMaxWidth().background(appBg)) {
                            if (pdfViewModel.hasPages(tractate.name)) {
                                DafPageView(
                                    tractate = tractate,
                                    daf = selectedDaf,
                                    amud = selectedAmud,
                                    pdfViewModel = pdfViewModel,
                                    onDafAmudChange = { newDaf, newAmud ->
                                        contentViewModel.selectDaf(newDaf.toDouble())
                                        contentViewModel.selectAmud(newAmud)
                                    },
                                    modifier = Modifier.fillMaxSize(),
                                    foregroundColor = appFg
                                )
                            }
                        }
                        if (!isAudioStopped) {
                            if (shiurSegments.isNotEmpty() && duration > 0f) {
                                val stripListState = rememberLazyListState()
                                LaunchedEffect(shiurSegmentIndex) { stripListState.animateScrollToItem(shiurSegmentIndex) }
                                LazyRow(
                                    state = stripListState,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                                    contentPadding = PaddingValues(horizontal = 4.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    itemsIndexed(shiurSegments) { index, seg ->
                                        val isActive = index == shiurSegmentIndex
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(50))
                                                .background(
                                                    if (isActive) MaterialTheme.colorScheme.primary
                                                    else MaterialTheme.colorScheme.surfaceVariant
                                                )
                                                .clickable { audioViewModel.seekToSeconds(seg.seconds.toFloat()) }
                                                .padding(horizontal = 10.dp, vertical = 4.dp)
                                        ) {
                                            Text(
                                                text = seg.displayTitle,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = if (isActive) MaterialTheme.colorScheme.onPrimary
                                                        else MaterialTheme.colorScheme.onSurfaceVariant,
                                                maxLines = 1
                                            )
                                        }
                                    }
                                }
                            }
                            AudioPlayerBar(audioViewModel = audioViewModel)
                        }
                        if (isAudioStopped) {
                            Box(
                                modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                FilledTonalButton(
                                    onClick = {
                                        val url = audioUrl ?: return@FilledTonalButton
                                        hasAutoRefreshedForAudio = false
                                        audioViewModel.play(url, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}")
                                    },
                                    enabled = hasAudio,
                                    colors = ButtonDefaults.filledTonalButtonColors(
                                        disabledContainerColor = appFg.copy(alpha = 0.12f),
                                        disabledContentColor = appFg.copy(alpha = 0.45f)
                                    )
                                ) {
                                    if (isLoadingFeed && !hasAudio) {
                                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                                        Spacer(Modifier.width(6.dp))
                                        Text("Loading…")
                                    } else {
                                        Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp))
                                        Spacer(Modifier.width(6.dp))
                                        Text("Listen")
                                    }
                                }
                            }
                        }
                    } // left panel Column — also ends the if (collapsedSide != "LEFT") expr

                    // ── Draggable divider / collapse handle ──────────────────────
                    when (collapsedSide) {
                        "LEFT" -> Box(
                            modifier = Modifier
                                .width(20.dp)
                                .fillMaxHeight()
                                .background(MaterialTheme.colorScheme.surfaceVariant)
                                .clickable {
                                    leftWidthPx = savedWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                    collapsedSide = "NONE"
                                    contentViewModel.saveTabletLayout("NONE", with(density) { leftWidthPx.toDp().value.toDouble() })
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "Expand left panel",
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        "RIGHT" -> Box(
                            modifier = Modifier
                                .width(20.dp)
                                .fillMaxHeight()
                                .background(MaterialTheme.colorScheme.surfaceVariant)
                                .clickable {
                                    leftWidthPx = savedWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                    collapsedSide = "NONE"
                                    contentViewModel.saveTabletLayout("NONE", with(density) { leftWidthPx.toDp().value.toDouble() })
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, "Expand right panel",
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        else -> Box(
                            modifier = Modifier
                                .width(32.dp)
                                .fillMaxHeight()
                                .pointerInput(Unit) {
                                    // Track cumulative drag locally so collapse intent is based
                                    // purely on how far the user dragged, not on subtracting
                                    // state values (which can be stale or zero on emulators).
                                    var cumulativeDrag = 0f
                                    detectHorizontalDragGestures(
                                        onDragStart = { _ -> cumulativeDrag = 0f },
                                        onDragEnd = {
                                            when {
                                                cumulativeDrag <= -collapseIntentPx -> {
                                                    savedWidthPx = leftWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                                    collapsedSide = "LEFT"
                                                    contentViewModel.saveTabletLayout("LEFT", with(density) { savedWidthPx.toDp().value.toDouble() })
                                                }
                                                cumulativeDrag >= collapseIntentPx -> {
                                                    savedWidthPx = leftWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                                    collapsedSide = "RIGHT"
                                                    contentViewModel.saveTabletLayout("RIGHT", with(density) { savedWidthPx.toDp().value.toDouble() })
                                                }
                                                else -> {
                                                    leftWidthPx = leftWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                                    contentViewModel.saveTabletLayout(collapsedSide, with(density) { leftWidthPx.toDp().value.toDouble() })
                                                }
                                            }
                                        },
                                        onDragCancel = {
                                            leftWidthPx = leftWidthPx.coerceIn(minLeftPx, maxLeftPx)
                                        }
                                    ) { _, dragAmount ->
                                        cumulativeDrag += dragAmount
                                        leftWidthPx = (leftWidthPx + dragAmount).coerceAtLeast(0f)
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            VerticalDivider()
                        }
                    }

                    // ── Right panel: Shiur/Study tab + content ───────────────────
                    if (collapsedSide != "RIGHT") Column(
                        modifier = Modifier.weight(1f).fillMaxHeight()
                    ) {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                        ) {
                            FilterChip(
                                selected = rightPanelMode == "SHIUR",
                                onClick = { contentViewModel.setTabletRightPanelMode("SHIUR") },
                                label = { Text("Shiur") },
                                colors = FilterChipDefaults.filterChipColors(labelColor = appFg),
                                border = FilterChipDefaults.filterChipBorder(
                                    enabled = true, selected = rightPanelMode == "SHIUR",
                                    borderColor = appFg.copy(alpha = 0.5f), selectedBorderColor = Color.Transparent
                                )
                            )
                            FilterChip(
                                selected = rightPanelMode == "STUDY",
                                onClick = { contentViewModel.setTabletRightPanelMode("STUDY") },
                                label = { Text("Study") },
                                colors = FilterChipDefaults.filterChipColors(labelColor = appFg),
                                border = FilterChipDefaults.filterChipBorder(
                                    enabled = true, selected = rightPanelMode == "STUDY",
                                    borderColor = appFg.copy(alpha = 0.5f), selectedBorderColor = Color.Transparent
                                )
                            )
                        }
                        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                            when (rightPanelMode) {
                                "SHIUR" -> {
                                    val shiurDisplayText = if (shiurShowSources) shiurFinal ?: shiurRewrite else shiurRewrite
                                    if (shiurDisplayText != null) {
                                        Column(Modifier.fillMaxSize()) {
                                            // Shiur header — tractate + daf (lock icon when audio is playing)
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)
                                            ) {
                                                if (!isAudioStopped) {
                                                    Icon(Icons.Default.Lock, null, Modifier.size(14.dp), tint = appFg.copy(alpha = 0.55f))
                                                    Spacer(Modifier.width(6.dp))
                                                }
                                                Text(
                                                    "${playingTractate} ${playingDaf.toInt()}",
                                                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                                                    color = appFg
                                                )
                                            }
                                            CompositionLocalProvider(
                                                LocalStudyFontSize provides studyFontSize.spSize.sp,
                                                LocalIsBlueMode provides !useWhiteBackground
                                            ) {
                                                ShiurTextView(
                                                    rewriteText = shiurDisplayText,
                                                    currentSegmentIndex = shiurSegmentIndex,
                                                    modifier = Modifier.weight(1f).fillMaxWidth()
                                                )
                                            }
                                        }
                                    } else {
                                        Box(Modifier.fillMaxSize(), Alignment.Center) {
                                            Text("No written shiur available",
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = appFg)
                                        }
                                    }
                                }
                                else -> {
                                    StudyModeContent(
                                        studyViewModel = studyViewModel,
                                        bookmarkViewModel = bookmarkViewModel,
                                        contentViewModel = contentViewModel,
                                        resourcesViewModel = resourcesViewModel,
                                        isInline = true,
                                        isAudioStopped = isAudioStopped,
                                        onStartStudy = {
                                            resourcesViewModel.reset()
                                            studyViewModel.startSession(playingTractate, playingDaf.toInt(), studyMode, quizMode)
                                        },
                                        modifier = Modifier.fillMaxSize()
                                    )
                                }
                            }
                        }
                    }
                } // inner Row (two-column split)
            } // outer Column (tablet layout)
        } else {
        // ── Phone: original single-column layout ─────────────────────────────
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Picker row — compact dropdown style; Daf/Shiur chips inline to the right when available
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .border(1.dp, appFg.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
                        .padding(start = 12.dp, end = 6.dp, top = 2.dp, bottom = 2.dp)
                ) {
                    CompactTabletPickers(
                        selectedTractateIndex = selectedTractateIndex,
                        selectedDaf = selectedDaf,
                        selectedAmud = selectedAmud,
                        tractate = tractate,
                        episodeIndex = episodeIndex,
                        contentViewModel = contentViewModel,
                        contentColor = appFg
                    )
                }
                // Daf / Shiur chips — stacked vertically to the right of picker box
                if (shiurRewrite != null) {
                    Spacer(Modifier.width(14.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy((-4).dp)) {
                        FilterChip(
                            selected = !showShiurText,
                            onClick = { showShiurText = false },
                            label = { Text("Daf") },
                            colors = FilterChipDefaults.filterChipColors(labelColor = appFg),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled = true, selected = !showShiurText,
                                borderColor = appFg.copy(alpha = 0.5f), selectedBorderColor = Color.Transparent
                            )
                        )
                        FilterChip(
                            selected = showShiurText,
                            onClick = { showShiurText = true },
                            label = { Text("Shiur") },
                            colors = FilterChipDefaults.filterChipColors(labelColor = appFg),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled = true, selected = showShiurText,
                                borderColor = appFg.copy(alpha = 0.5f), selectedBorderColor = Color.Transparent
                            )
                        )
                    }
                }
            }

            // Main content area: daf image or lecture text
            Box(modifier = Modifier.weight(1f).fillMaxWidth().background(appBg)) {
                val shiurDisplayText = if (shiurShowSources) shiurFinal ?: shiurRewrite else shiurRewrite
                if (showShiurText && shiurDisplayText != null) {
                    Column(Modifier.fillMaxSize()) {
                        if (!isAudioStopped) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(horizontal = 18.dp, vertical = 5.dp)
                            ) {
                                Icon(Icons.Default.Lock, null, Modifier.size(12.dp), tint = appFg.copy(alpha = 0.55f))
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    "${audioLockedTractate} ${audioLockedDaf.toInt()}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = appFg.copy(alpha = 0.55f)
                                )
                            }
                        }
                        CompositionLocalProvider(
                            LocalStudyFontSize provides studyFontSize.spSize.sp,
                            LocalIsBlueMode provides !useWhiteBackground
                        ) {
                            ShiurTextView(
                                rewriteText = shiurDisplayText,
                                currentSegmentIndex = shiurSegmentIndex,
                                modifier = Modifier.weight(1f).fillMaxWidth()
                            )
                        }
                    }
                } else {
                    if (pdfViewModel.hasPages(tractate.name)) {
                        DafPageView(
                            tractate = tractate,
                            daf = selectedDaf,
                            amud = selectedAmud,
                            pdfViewModel = pdfViewModel,
                            onDafAmudChange = { newDaf, newAmud ->
                                contentViewModel.selectDaf(newDaf.toDouble())
                                contentViewModel.selectAmud(newAmud)
                            },
                            modifier = Modifier.fillMaxSize(),
                            foregroundColor = appFg
                        )
                    }
                }

                // Action row overlaid at the bottom of the image — maximises image height
                Row(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth()
                        .background(appBg.copy(alpha = 0.88f))
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (isAudioStopped && (hasAudio || isLoadingFeed)) {
                        FilledTonalButton(
                            onClick = {
                                val url = audioUrl ?: return@FilledTonalButton
                                hasAutoRefreshedForAudio = false
                                audioViewModel.play(url, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}")
                            },
                            enabled = hasAudio,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.filledTonalButtonColors(
                                disabledContainerColor = appFg.copy(alpha = 0.12f),
                                disabledContentColor = appFg.copy(alpha = 0.45f)
                            )
                        ) {
                            if (isLoadingFeed && !hasAudio) {
                                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                                Spacer(Modifier.width(6.dp))
                                Text("Loading…")
                            } else {
                                Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Listen")
                            }
                        }
                    }

                    FilledTonalButton(
                        onClick = { onStartStudy(playingTractate, playingDaf.toInt(), studyMode, quizMode) },
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.MenuBook, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Study")
                    }
                }
            }

            // Audio player bar and chapter strip — shown below the daf
            if (!isAudioStopped) {
                if (shiurSegments.isNotEmpty() && duration > 0f) {
                    val stripListState = rememberLazyListState()
                    LaunchedEffect(shiurSegmentIndex) {
                        stripListState.animateScrollToItem(shiurSegmentIndex)
                    }
                    LazyRow(
                        state = stripListState,
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        contentPadding = PaddingValues(horizontal = 16.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        itemsIndexed(shiurSegments) { index, seg ->
                            val isActive = index == shiurSegmentIndex
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(50))
                                    .background(
                                        if (isActive) MaterialTheme.colorScheme.primary
                                        else MaterialTheme.colorScheme.surfaceVariant
                                    )
                                    .clickable { audioViewModel.seekToSeconds(seg.seconds.toFloat()) }
                                    .padding(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                androidx.compose.material3.Text(
                                    text = seg.displayTitle,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isActive) MaterialTheme.colorScheme.onPrimary
                                            else MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1
                                )
                            }
                        }
                    }
                }
                AudioPlayerBar(audioViewModel = audioViewModel)
            }
        }
        } // end phone else-branch
    }

    // ── New-bookmark edit dialog (shown immediately after tapping the bookmark icon) ──
    pendingNewBookmark?.let { bm ->
        BookmarkEditDialog(
            bookmark = bm,
            title = "Add Bookmark",
            onDismiss = { pendingNewBookmark = null },
            onSave = { name, notes ->
                bookmarkViewModel.add(bm.copy(name = name, notes = notes))
                pendingNewBookmark = null
            }
        )
    }
}

@Composable
private fun TabletPickerRow(
    selectedTractateIndex: Int,
    selectedDaf: Double,
    selectedAmud: Int,
    tractate: com.anydaf.model.Tractate,
    episodeIndex: Map<String, Map<Double, String>>,
    contentViewModel: ContentViewModel,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth().height(88.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Card(
            modifier = Modifier.weight(1f).fillMaxHeight(),
            elevation = CardDefaults.cardElevation(4.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(modifier = Modifier.weight(1f)) {
                    TractateWheelPicker(
                        tractates = allTractates,
                        selectedIndex = selectedTractateIndex,
                        onSelected = { contentViewModel.selectTractate(it) }
                    )
                }
                Box(modifier = Modifier.width(56.dp)) {
                    val dafPickerItems = remember(tractate.name, episodeIndex) {
                        buildList {
                            for (n in tractate.dafRange) {
                                add(n.toDouble())
                                val half = n.toDouble() + 0.5
                                if (episodeIndex[tractate.name]?.containsKey(half) == true) add(half)
                            }
                        }
                    }
                    DafWheelPicker(
                        dafRange = dafPickerItems,
                        selectedDaf = selectedDaf,
                        onSelected = { contentViewModel.selectDaf(it) }
                    )
                }
            }
        }
        Card(
            modifier = Modifier.fillMaxHeight(),
            elevation = CardDefaults.cardElevation(4.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(
                modifier = Modifier.fillMaxHeight().padding(horizontal = 4.dp, vertical = 6.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                listOf(0 to "A", 1 to "B").forEach { (amud, label) ->
                    FilledTonalButton(
                        onClick = { contentViewModel.selectAmud(amud) },
                        modifier = Modifier.weight(1f).width(44.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
                        colors = if (selectedAmud == amud) {
                            ButtonDefaults.filledTonalButtonColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                                contentColor = MaterialTheme.colorScheme.onPrimary
                            )
                        } else ButtonDefaults.filledTonalButtonColors()
                    ) { Text(label) }
                }
            }
        }
    }
}

@Composable
fun TractateWheelPicker(
    tractates: List<Tractate>,
    selectedIndex: Int,
    onSelected: (Int) -> Unit
) {
    val listState = rememberLazyListState(selectedIndex)
    LaunchedEffect(selectedIndex) { listState.animateScrollToItem(selectedIndex) }

    LazyColumn(
        state = listState,
        modifier = Modifier.height(72.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        itemsIndexed(tractates) { index, tractate ->
            val isSelected = index == selectedIndex
            Text(
                text = tractate.name,
                style = if (isSelected) MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Bold)
                else MaterialTheme.typography.bodyMedium,
                color = if (isSelected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        if (isSelected) MaterialTheme.colorScheme.primary else Color.Transparent,
                        RoundedCornerShape(6.dp)
                    )
                    .clickable { onSelected(index) }
                    .padding(vertical = 6.dp, horizontal = 8.dp)
            )
        }
    }
}

@Composable
fun DafWheelPicker(
    dafRange: List<Double>,
    selectedDaf: Double,
    onSelected: (Double) -> Unit
) {
    val startIdx = dafRange.indexOf(selectedDaf).coerceAtLeast(0)
    val listState = rememberLazyListState(startIdx)
    LaunchedEffect(selectedDaf) {
        val idx = dafRange.indexOf(selectedDaf).coerceAtLeast(0)
        listState.animateScrollToItem(idx)
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.height(72.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        itemsIndexed(dafRange) { _, daf ->
            val isSelected = daf == selectedDaf
            Text(
                text = FeedManager.dafLabel(daf),
                style = if (isSelected) MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Bold)
                else MaterialTheme.typography.bodyMedium,
                color = if (isSelected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        if (isSelected) MaterialTheme.colorScheme.primary else Color.Transparent,
                        RoundedCornerShape(6.dp)
                    )
                    .clickable { onSelected(daf) }
                    .padding(vertical = 6.dp),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    }
}

@Composable
private fun CompactTabletPickers(
    selectedTractateIndex: Int,
    selectedDaf: Double,
    selectedAmud: Int,
    tractate: com.anydaf.model.Tractate,
    episodeIndex: Map<String, Map<Double, String>>,
    contentViewModel: ContentViewModel,
    contentColor: Color = Color.Unspecified
) {
    var tractateExpanded by remember { mutableStateOf(false) }
    var dafExpanded by remember { mutableStateOf(false) }
    val tractateScrollState = rememberScrollState()
    val dafScrollState = rememberScrollState()
    val density = LocalDensity.current
    val itemHeightPx = with(density) { 48.dp.roundToPx() }

    LaunchedEffect(tractateExpanded) {
        if (tractateExpanded) tractateScrollState.scrollTo(selectedTractateIndex * itemHeightPx)
    }

    val dafPickerItems = remember(tractate.name, episodeIndex) {
        buildList {
            for (n in tractate.dafRange) {
                add(n.toDouble())
                val half = n.toDouble() + 0.5
                if (episodeIndex[tractate.name]?.containsKey(half) == true) add(half)
            }
        }
    }

    LaunchedEffect(dafExpanded) {
        if (dafExpanded) {
            val idx = dafPickerItems.indexOf(selectedDaf).coerceAtLeast(0)
            dafScrollState.scrollTo(idx * itemHeightPx)
        }
    }

    Row(
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        val useCustomColor = contentColor != Color.Unspecified
        val buttonColors = if (useCustomColor)
            ButtonDefaults.outlinedButtonColors(contentColor = contentColor) else ButtonDefaults.outlinedButtonColors()
        val buttonBorder = androidx.compose.foundation.BorderStroke(0.dp, Color.Transparent)

        // Tractate dropdown
        Box {
            OutlinedButton(
                onClick = { tractateExpanded = true },
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp),
                colors = buttonColors,
                border = buttonBorder
            ) {
                Text(
                    tractate.name,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.widthIn(max = 120.dp),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Normal
                )
            }
            DropdownMenu(expanded = tractateExpanded, onDismissRequest = { tractateExpanded = false }, scrollState = tractateScrollState, modifier = Modifier.heightIn(max = 300.dp)) {
                allTractates.forEachIndexed { index, t ->
                    DropdownMenuItem(
                        text = { Text(t.name) },
                        onClick = {
                            contentViewModel.selectTractate(index)
                            tractateExpanded = false
                        }
                    )
                }
            }
        }

        // Daf dropdown
        Box {
            OutlinedButton(
                onClick = { dafExpanded = true },
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp),
                colors = buttonColors,
                border = buttonBorder
            ) {
                Text(FeedManager.dafLabel(selectedDaf), maxLines = 1, fontSize = 14.sp, fontWeight = FontWeight.Normal)
            }
            DropdownMenu(
                expanded = dafExpanded,
                onDismissRequest = { dafExpanded = false },
                scrollState = dafScrollState,
                modifier = Modifier.heightIn(max = 300.dp)
            ) {
                dafPickerItems.forEach { daf ->
                    DropdownMenuItem(
                        text = { Text(FeedManager.dafLabel(daf)) },
                        onClick = {
                            contentViewModel.selectDaf(daf)
                            dafExpanded = false
                        }
                    )
                }
            }
        }

        // Single amud toggle — custom Box to avoid OutlinedButton's 58dp min-width
        val amudBorderColor = if (useCustomColor) contentColor.copy(alpha = 0.5f)
                              else MaterialTheme.colorScheme.outline
        val amudTextColor = if (useCustomColor) contentColor
                            else MaterialTheme.colorScheme.onSurface
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier
                .clip(RoundedCornerShape(50))
                .clickable { contentViewModel.selectAmud(if (selectedAmud == 0) 1 else 0) }
                .padding(horizontal = 10.dp, vertical = 8.dp)
        ) {
            Text(if (selectedAmud == 0) "a" else "b", color = amudTextColor, fontSize = 14.sp, fontWeight = FontWeight.Normal)
        }
    }
}

@Composable
private fun DonationNudgeDialog(onDonate: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(
                Icons.Default.Favorite,
                contentDescription = null,
                tint = androidx.compose.ui.graphics.Color.Red
            )
        },
        title = { Text("Support AnyDaf") },
        text = {
            Text("AnyDaf is provided free by Yeshivat Chovevei Torah. If you find it valuable, please consider making a donation to support Torah learning.")
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Maybe Later") }
        },
        dismissButton = {
            TextButton(onClick = onDonate) { Text("Donate to YCT") }
        }
    )
}
