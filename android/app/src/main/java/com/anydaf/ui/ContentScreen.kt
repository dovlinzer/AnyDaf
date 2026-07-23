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
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.material.icons.filled.Print
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChipDefaults
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
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.material3.AlertDialog
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
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
import com.anydaf.data.api.Dedication
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

private enum class MainContentMode { DAF, TEXT, SHIUR }

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
    val printFontSize by contentViewModel.printFontSize.collectAsState()
    val printLineSpacing by contentViewModel.printLineSpacing.collectAsState()
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

    val dedication by contentViewModel.dedication.collectAsState()
    dedication?.let {
        DedicationDialog(dedication = it, onDismiss = { contentViewModel.dismissDedication() })
    }

    val episodeIndex by FeedManager.episodeIndex.collectAsState()
    val isLoadingFeed by FeedManager.isLoading.collectAsState()
    val shiurSegments by ShiurClient.segments.collectAsState()
    val shiurSegmentIndex by ShiurClient.currentSegmentIndex.collectAsState()
    val audioSegments by ShiurClient.audioSegments.collectAsState()
    val audioSegmentIndex by ShiurClient.audioCurrentSegmentIndex.collectAsState()
    val amudBSegmentIndex by ShiurClient.amudBSegmentIndex.collectAsState()
    val amudBSeconds by ShiurClient.amudBSeconds.collectAsState()
    val amudBMicroTitle by ShiurClient.amudBMicroTitle.collectAsState()
    val shiurRewrite by ShiurClient.shiurRewrite.collectAsState()
    val shiurFinal by ShiurClient.shiurFinal.collectAsState()
    val shiurShowSources by contentViewModel.shiurShowSources.collectAsState()
    val currentTime by audioViewModel.currentTime.collectAsState()
    val duration by audioViewModel.duration.collectAsState()
    val lastContentModeStr by contentViewModel.lastContentMode.collectAsState()
    val lastTextSectionIndex by contentViewModel.lastTextSectionIndex.collectAsState()
    val lastTextTractate by contentViewModel.lastTextTractate.collectAsState()
    val lastTextDaf by contentViewModel.lastTextDaf.collectAsState()
    val lastShiurSegmentIndex by contentViewModel.lastShiurSegmentIndex.collectAsState()
    val lastShiurTractate by contentViewModel.lastShiurTractate.collectAsState()
    val lastShiurDaf by contentViewModel.lastShiurDaf.collectAsState()
    var shiurInitialRestoreDone by remember { mutableStateOf(false) }
    // Guards against re-running the daf-change LaunchedEffect below when selectedDaf is set
    // programmatically to mirror Study Mode's own daf navigation (Prev Daf/Next Daf). Without
    // this, that effect would call studyViewModel.endSession() (outside Text mode) or restart
    // the session, clobbering the position Study Mode just navigated to.
    var suppressDafSessionSync by remember { mutableStateOf(false) }
    var mainContentMode by remember {
        mutableStateOf(
            contentViewModel.currentContentMode.value.let { name ->
                if (name.isNotEmpty()) MainContentMode.entries.firstOrNull { it.name == name } ?: MainContentMode.DAF
                else MainContentMode.DAF
            }
        )
    }

    val tractate = allTractates[selectedTractateIndex]

    // Tractate/daf frozen at the moment audio starts — stays fixed while picker freely moves.
    var audioLockedTractate by remember { mutableStateOf(tractate.name) }
    var audioLockedDaf by remember { mutableStateOf(selectedDaf) }

    // Always load on first appearance — mirrors iOS onAppear (no audio guard needed here).
    LaunchedEffect(Unit) {
        ShiurClient.load(tractate.name, selectedDaf)
    }

    // Reload whenever daf/tractate changes, regardless of audio state.
    LaunchedEffect(tractate.name, selectedDaf) {
        ShiurClient.load(tractate.name, selectedDaf)
    }

    // When audio starts, freeze the locked daf and snapshot the audio segments.
    LaunchedEffect(isAudioStopped) {
        if (!isAudioStopped) {
            audioLockedTractate = tractate.name
            audioLockedDaf = selectedDaf
            ShiurClient.snapshotAudioSegments()
        }
    }

    // Reset study session when daf/tractate changes — always follow the selector.
    // In Text mode, restart the session rather than ending it.
    LaunchedEffect(tractate.name, selectedDaf) {
        if (suppressDafSessionSync) {
            suppressDafSessionSync = false
        } else {
            shiurInitialRestoreDone = true  // daf/tractate change is not a launch restore
            if (mainContentMode == MainContentMode.TEXT) {
                studyViewModel.startSession(tractate.name, selectedDaf.toInt(), studyMode, quizMode,
                    startAtAmudB = selectedAmud == 1)
            } else {
                studyViewModel.endSession()
            }
        }
    }
    // Keep the picker readout (selectedDaf/selectedAmud) in sync with Study Mode's own
    // navigation — crossing a daf boundary via Prev Daf/Next Daf, or crossing the amud A/B
    // boundary while paging through sections within the same daf.
    //
    // selectedDaf here must stay a whole daf number, never daf+0.5 for "amud b" — the .5 suffix
    // is reserved for genuine half-daf *audio episodes* (see dafPickerItems in
    // CompactTabletPickers, which only appends daf+0.5 when episodeIndex actually has an entry
    // there). Study Mode sessions always key on a whole daf (StudySession.daf: Int); amud is
    // carried separately via selectedAmud. This mirrors the iOS fix in ContentView.swift —
    // there, setting selectedDaf to a daf+0.5 that wasn't a real episode entry fell outside
    // dafPickerItems and made the UIKit-backed picker render the daf number blank; Compose's
    // DropdownMenu doesn't blank out the same way, but the same needless conflation was here.
    val studySessionSnapshot by studyViewModel.session.collectAsState()
    val studySessionAmudSide = studySessionSnapshot?.let { s ->
        val bIdx = s.amudBSectionIndex
        if (bIdx != null && s.currentSectionIndex >= bIdx) 1 else 0
    }
    LaunchedEffect(studySessionSnapshot?.daf, studySessionAmudSide) {
        val s = studySessionSnapshot ?: return@LaunchedEffect
        val side = studySessionAmudSide ?: 0
        val newSelectedDaf = s.daf.toDouble()
        val dafChanged = newSelectedDaf != selectedDaf
        val amudChanged = side != selectedAmud
        if (!dafChanged && !amudChanged) return@LaunchedEffect
        if (dafChanged) suppressDafSessionSync = true
        contentViewModel.selectDaf(newSelectedDaf)
        contentViewModel.selectAmud(side)
    }

    // Drive audioCurrentSegmentIndex from playback position — always fires regardless of which
    // daf is selected, since updateCurrentSegment only touches audioCurrentSegmentIndex.
    LaunchedEffect(currentTime) {
        ShiurClient.updateCurrentSegment(currentTime)
    }
    // Mirror audio position into shiur text only when viewing the same daf that is playing.
    LaunchedEffect(audioSegmentIndex) {
        if (!isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf) {
            ShiurClient.jumpToSegment(audioSegmentIndex)
            val sefariaIdx = ShiurClient.audioSegments.value.getOrNull(audioSegmentIndex)?.sefariaIndex
            if (sefariaIdx != null && mainContentMode == MainContentMode.TEXT) {
                studyViewModel.jumpToSection(sefariaIdx)
            }
        }
    }
    // Sync the a/b picker to the shiur's actual segment position when in Shiur mode,
    // both on mode entry and as the segment changes (e.g. audio crossing the amud B boundary).
    LaunchedEffect(mainContentMode, shiurSegmentIndex, amudBSegmentIndex) {
        if (mainContentMode != MainContentMode.SHIUR) return@LaunchedEffect
        val bIdx = amudBSegmentIndex ?: return@LaunchedEffect
        val correctAmud = if (shiurSegmentIndex >= bIdx) 1 else 0
        if (correctAmud != selectedAmud) contentViewModel.selectAmud(correctAmud)
    }
    // Tracks the mode before the most recent change, so a direct Shiur<->Text switch can be
    // told apart from entering either mode via the Daf image or on launch.
    var previousMainContentMode by remember { mutableStateOf(mainContentMode) }
    // On a direct Shiur<->Text switch, carry the exact position across via sefariaIndex
    // (mirrors the iOS fix in ContentView.swift). Any other transition — from the Daf image,
    // or on launch — keeps restoring each mode's own last-remembered position, unchanged.
    //
    // studySessionIsCurrent guards against a stale studyViewModel.session: Shiur mode does not
    // restart the study session on a daf change (the LaunchedEffect(tractate.name, selectedDaf)
    // above calls endSession() instead when not in Text mode), so studyViewModel.session can
    // be null, or briefly still reference a previous daf, right as this fires. Without this
    // guard, jumpToSection would silently no-op against a null/stale session and this effect
    // would return early without ever starting a fresh session for the daf actually selected —
    // leaving Text mode stuck, or (if the session was stale rather than null) showing the wrong
    // daf's text while the shiur pill strip (always fresh per daf) shows the current daf's titles.
    LaunchedEffect(mainContentMode) {
        val fromMode = previousMainContentMode
        previousMainContentMode = mainContentMode
        val studySessionIsCurrent = studyViewModel.session.value?.tractate == tractate.name
            && studyViewModel.session.value?.daf == selectedDaf.toInt()
        if (mainContentMode == MainContentMode.TEXT) {
            if (fromMode == MainContentMode.SHIUR && studySessionIsCurrent) {
                val segs = ShiurClient.segments.value
                val sefariaIdx = segs.getOrNull(ShiurClient.currentSegmentIndex.value)?.sefariaIndex
                if (sefariaIdx != null) {
                    studyViewModel.jumpToSection(sefariaIdx)
                    return@LaunchedEffect
                }
            }
            val session = studyViewModel.session.value ?: return@LaunchedEffect
            val sameDaf = lastTextTractate == tractate.name && lastTextDaf == selectedDaf
            if (sameDaf && lastTextSectionIndex > 0) {
                studyViewModel.jumpToSectionAt(minOf(lastTextSectionIndex, session.sections.size - 1))
            } else if (selectedAmud == 1) {
                val bIdx = session.amudBSectionIndex
                if (bIdx != null) studyViewModel.jumpToSectionAt(bIdx)
            }
        } else if (mainContentMode == MainContentMode.SHIUR && fromMode == MainContentMode.TEXT && studySessionIsCurrent) {
            val curSession = studyViewModel.session.value
            val firstSegIdx = curSession?.currentSection?.firstSegmentIndex
            if (curSession != null && firstSegIdx != null) {
                val nextIndex = curSession.currentSectionIndex + 1
                val rangeEnd = if (nextIndex < curSession.sections.size)
                    curSession.sections[nextIndex].firstSegmentIndex else Int.MAX_VALUE
                val segs = ShiurClient.segments.value
                // Prefer the segment explicitly navigated to (a pill tap), as long as it's still
                // within the current section's range — the user may have tapped a segment
                // anchored mid-section, and switching to Shiur should land on exactly that one.
                // Falls back to a point lookup at the section's start otherwise (a section
                // reached by scrolling or Prev/Next, not a pill tap).
                val activeIdx = studyViewModel.activeSefariaIndex.value
                val explicitIdx = activeIdx?.takeIf { it >= firstSegIdx && it < rangeEnd }?.let { idx ->
                    segs.indexOfFirst { it.sefariaIndex == idx && it.matched == true }.takeIf { it >= 0 }
                }
                val owning = explicitIdx ?: ShiurClient.owningSegmentIndex(firstSegIdx, segs)
                owning?.let { ShiurClient.jumpToSegment(it) }
            }
        }
    }
    // Restore persisted content mode on first app launch only (sentinel "" = not yet loaded).
    // If currentContentMode is already set (non-empty), we are returning from in-session
    // navigation (e.g. Settings) and the remember initializer already has the correct mode —
    // do NOT override it with the DataStore value, which may be stale from a previous session.
    LaunchedEffect(lastContentModeStr) {
        if (lastContentModeStr.isEmpty()) return@LaunchedEffect
        if (contentViewModel.currentContentMode.value.isNotEmpty()) return@LaunchedEffect
        val restored = MainContentMode.entries.firstOrNull { it.name == lastContentModeStr }
            ?: MainContentMode.DAF
        if (restored != mainContentMode) {
            mainContentMode = restored
            if (restored == MainContentMode.TEXT &&
                studyViewModel.session.value == null && !studyViewModel.isLoadingText.value) {
                val sameDaf = lastTextTractate == tractate.name && lastTextDaf == selectedDaf
                studyViewModel.startSession(tractate.name, selectedDaf.toInt(), studyMode, quizMode,
                    startAtAmudB = !sameDaf && selectedAmud == 1,
                    startAtSectionIndex = if (sameDaf && lastTextSectionIndex > 0) lastTextSectionIndex else null)
            }
        }
    }
    // Persist content mode whenever it changes — in-memory first (instant), DataStore async.
    LaunchedEffect(mainContentMode) {
        contentViewModel.currentContentMode.value = mainContentMode.name
        contentViewModel.saveContentMode(mainContentMode.name)
    }
    // Save text section position whenever it changes in text mode.
    val currentSectionIndex = studyViewModel.session.collectAsState().value?.currentSectionIndex
    LaunchedEffect(currentSectionIndex) {
        if (mainContentMode == MainContentMode.TEXT && currentSectionIndex != null) {
            contentViewModel.saveTextPosition(tractate.name, selectedDaf, currentSectionIndex)
        }
    }
    // Save shiur segment position whenever it changes (in shiur mode or on tablet where shiur is always visible).
    LaunchedEffect(shiurSegmentIndex) {
        if (mainContentMode == MainContentMode.SHIUR) {
            contentViewModel.saveShiurPosition(tractate.name, selectedDaf, shiurSegmentIndex)
        }
    }
    // On first segment load after launch, restore shiur to the exact saved position (or amud B).
    LaunchedEffect(amudBSegmentIndex) {
        val bIdx = amudBSegmentIndex ?: return@LaunchedEffect
        if (shiurInitialRestoreDone) return@LaunchedEffect
        shiurInitialRestoreDone = true
        if (mainContentMode != MainContentMode.SHIUR) return@LaunchedEffect
        if (ShiurClient.currentSegmentIndex.value != 0) return@LaunchedEffect
        val sameDaf = lastShiurTractate == tractate.name && lastShiurDaf == selectedDaf
        if (sameDaf && lastShiurSegmentIndex > 0) {
            ShiurClient.jumpToSegment(lastShiurSegmentIndex)
        } else if (selectedAmud == 1) {
            ShiurClient.jumpToSegment(bIdx)
        }
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
                            contentColor = appFg,
                            onAmudChange = { newAmud ->
                                val bIdx = amudBSegmentIndex
                                if (bIdx != null) {
                                    ShiurClient.jumpToSegment(if (newAmud == 1) bIdx else 0)
                                    if (!isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf) {
                                        val seekSecs = if (newAmud == 1)
                                            amudBSeconds?.toFloat() ?: shiurSegments.getOrNull(bIdx)?.seconds?.toFloat()
                                        else 0f
                                        if (seekSecs != null) audioViewModel.seekToSeconds(seekSecs)
                                    }
                                }
                            }
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
        // isTablet is derived from configuration — compute rightPanelMode here for use below
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
                                        contentColor = appFg,
                                        onAmudChange = { newAmud ->
                                            amudBSegmentIndex?.let { bIdx ->
                                                ShiurClient.jumpToSegment(if (newAmud == 1) bIdx else 0)
                                            }
                                            if (!isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf) {
                                                amudBSeconds?.let { bSecs ->
                                                    audioViewModel.seekToSeconds(if (newAmud == 1) bSecs.toFloat() else 0f)
                                                }
                                            }
                                        }
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
                            if (audioSegments.isNotEmpty() && duration > 0f) {
                                val stripListState = rememberLazyListState()
                                LaunchedEffect(audioSegmentIndex) { stripListState.animateScrollToItem(audioSegmentIndex) }
                                LazyRow(
                                    state = stripListState,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                                    contentPadding = PaddingValues(horizontal = 4.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    itemsIndexed(audioSegments) { index, seg ->
                                        val isActive = index == audioSegmentIndex
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(50))
                                                .background(if (isActive) appFg.copy(alpha = 0.85f) else appFg.copy(alpha = 0.15f))
                                                .clickable {
                                                    audioViewModel.seekToSeconds(seg.seconds.toFloat())
                                                    ShiurClient.jumpToAudioSegment(index)
                                                }
                                                .padding(horizontal = 10.dp, vertical = 4.dp)
                                        ) {
                                            Text(
                                                text = seg.displayTitle,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = if (isActive) { if (useWhiteBackground) Color.White else AppBlue } else appFg.copy(alpha = 0.8f),
                                                maxLines = 1
                                            )
                                        }
                                    }
                                }
                            }
                            AudioPlayerBar(
                                audioViewModel = audioViewModel,
                                nowPlayingLabel = if (!isAudioStopped) "${audioLockedTractate} ${FeedManager.dafLabel(audioLockedDaf)}" else ""
                            )
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
                                        val startAt = shiurSegments.getOrNull(shiurSegmentIndex)
                                            ?.takeIf { shiurSegmentIndex > 0 }?.seconds?.toFloat() ?: 0f
                                        audioViewModel.play(url, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}", startAt)
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
                                                modifier = Modifier.padding(start = 16.dp, end = 4.dp, top = 6.dp, bottom = 6.dp)
                                            ) {
                                                Text(
                                                    "${tractate.name} ${selectedDaf.toInt()}",
                                                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                                                    color = appFg,
                                                    modifier = Modifier.weight(1f)
                                                )
                                                val shiurDisplayForPrint = if (shiurShowSources) shiurFinal ?: shiurRewrite else shiurRewrite
                                                IconButton(
                                                    onClick = {
                                                        val txt = shiurDisplayForPrint
                                                        if (txt != null) PrintHelper.print(context, PrintableContent.Shiur(tractate.name, selectedDaf.toInt().toString(), txt), printFontSize, printLineSpacing)
                                                    },
                                                    modifier = Modifier.size(36.dp)
                                                ) {
                                                    Icon(Icons.Default.Print, "Print", Modifier.size(18.dp), tint = appFg.copy(alpha = 0.5f))
                                                }
                                            }
                                            // Chapter navigation chips — always visible
                                            if (shiurSegments.isNotEmpty()) {
                                                val stripListState = rememberLazyListState()
                                                LaunchedEffect(shiurSegmentIndex) { stripListState.animateScrollToItem(shiurSegmentIndex) }
                                                LazyRow(
                                                    state = stripListState,
                                                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                                                    contentPadding = PaddingValues(horizontal = 12.dp),
                                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                                                ) {
                                                    itemsIndexed(shiurSegments) { index, seg ->
                                                        val isActive = index == shiurSegmentIndex
                                                        Box(
                                                            modifier = Modifier
                                                                .clip(RoundedCornerShape(50))
                                                                .background(if (isActive) appFg.copy(alpha = 0.85f) else appFg.copy(alpha = 0.15f))
                                                                .clickable {
                                                                    ShiurClient.jumpToSegment(index)
                                                                    val isSameDaf = !isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf
                                                                    if (isSameDaf) {
                                                                        audioViewModel.seekToSeconds(seg.seconds.toFloat())
                                                                        ShiurClient.jumpToAudioSegment(index)
                                                                    }
                                                                }
                                                                .padding(horizontal = 10.dp, vertical = 4.dp)
                                                        ) {
                                                            Text(
                                                                text = seg.displayTitle,
                                                                style = MaterialTheme.typography.labelSmall,
                                                                color = if (isActive) { if (useWhiteBackground) Color.White else AppBlue } else appFg.copy(alpha = 0.8f),
                                                                maxLines = 1
                                                            )
                                                        }
                                                    }
                                                }
                                            }
                                            CompositionLocalProvider(
                                                LocalStudyFontSize provides studyFontSize.spSize.sp,
                                                LocalIsBlueMode provides !useWhiteBackground
                                            ) {
                                                ShiurTextView(
                                                    rewriteText = shiurDisplayText,
                                                    currentSegmentIndex = shiurSegmentIndex,
                                                    modifier = Modifier.weight(1f).fillMaxWidth(),
                                                    amudBSegmentIndex = amudBSegmentIndex,
                                                    amudBMicroTitle = amudBMicroTitle,
                                                    onSegmentVisible = { idx -> ShiurClient.jumpToSegment(idx) }
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
                                        contentViewModel = contentViewModel,
                                        resourcesViewModel = resourcesViewModel,
                                        isInline = true,
                                        isAudioStopped = isAudioStopped,
                                        onStartStudy = {
                                            resourcesViewModel.reset()
                                            studyViewModel.startSession(tractate.name, selectedDaf.toInt(), studyMode, quizMode)
                                        },
                                        onPrintTranslation = {
                                            val s = studyViewModel.session.value
                                            if (s != null) PrintHelper.print(context, PrintableContent.TalmudText(s.tractate, s.daf.toString(), s.sections, contentViewModel.textDisplayMode.value, s.precedingContext, s.followingContext), printFontSize, printLineSpacing)
                                        },
                                        onAudioPlay = { if (audioViewModel.isPlaying.value) audioViewModel.togglePlayPause() },
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
                        .weight(1f)
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
                        contentColor = appFg,
                        onAmudChange = { newAmud ->
                            amudBSegmentIndex?.let { bIdx ->
                                ShiurClient.jumpToSegment(if (newAmud == 1) bIdx else 0)
                            }
                            if (!isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf) {
                                amudBSeconds?.let { bSecs ->
                                    audioViewModel.seekToSeconds(if (newAmud == 1) bSecs.toFloat() else 0f)
                                }
                            }
                        }
                    )
                }
                // Daf / Text / Shiur pill
                Spacer(Modifier.width(14.dp))
                Row(
                    modifier = Modifier.border(1.dp, appFg.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
                ) {
                    ContentModeSegment("Daf", mainContentMode == MainContentMode.DAF, appFg) {
                        mainContentMode = MainContentMode.DAF
                    }
                    ContentModeSegment("Text", mainContentMode == MainContentMode.TEXT, appFg) {
                        mainContentMode = MainContentMode.TEXT
                        if (studyViewModel.session.value == null && !studyViewModel.isLoadingText.value) {
                            resourcesViewModel.reset()
                            studyViewModel.startSession(tractate.name, selectedDaf.toInt(), studyMode, quizMode,
                                startAtAmudB = selectedAmud == 1)
                        }
                    }
                    if (shiurRewrite != null) {
                        ContentModeSegment("Shiur", mainContentMode == MainContentMode.SHIUR, appFg) {
                            mainContentMode = MainContentMode.SHIUR
                        }
                    }
                }
            }

            // Main content area: daf image, Sefaria text, or lecture text
            Box(modifier = Modifier.weight(1f).fillMaxWidth().background(appBg)) {
                val shiurDisplayText = if (shiurShowSources) shiurFinal ?: shiurRewrite else shiurRewrite
                when {
                    mainContentMode == MainContentMode.TEXT -> {
                        Column(Modifier.fillMaxSize()) {
                            StudyModeContent(
                                studyViewModel = studyViewModel,
                                contentViewModel = contentViewModel,
                                resourcesViewModel = resourcesViewModel,
                                textOnly = true,
                                isAudioStopped = isAudioStopped,
                                onStartStudy = {
                                    resourcesViewModel.reset()
                                    studyViewModel.startSession(tractate.name, selectedDaf.toInt(), studyMode, quizMode)
                                },
                                onPrintTranslation = {
                                    val s = studyViewModel.session.value
                                    if (s != null) PrintHelper.print(context, PrintableContent.TalmudText(s.tractate, s.daf.toString(), s.sections, contentViewModel.textDisplayMode.value), printFontSize, printLineSpacing)
                                },
                                onAudioPlay = { if (audioViewModel.isPlaying.value) audioViewModel.togglePlayPause() },
                                modifier = Modifier.weight(1f).fillMaxWidth()
                            )
                        }
                    }
                    mainContentMode == MainContentMode.SHIUR && shiurDisplayText != null -> {
                        Column(Modifier.fillMaxSize()) {
                            if (shiurSegments.isNotEmpty()) {
                                // Chapter navigation chips — always visible in shiur mode
                                val stripListState = rememberLazyListState()
                                LaunchedEffect(shiurSegmentIndex) { stripListState.animateScrollToItem(shiurSegmentIndex) }
                                LazyRow(
                                    state = stripListState,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                                    contentPadding = PaddingValues(horizontal = 16.dp),
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                                ) {
                                    itemsIndexed(shiurSegments) { index, seg ->
                                        val isActive = index == shiurSegmentIndex
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(50))
                                                .background(if (isActive) appFg.copy(alpha = 0.85f) else appFg.copy(alpha = 0.15f))
                                                .clickable {
                                                    ShiurClient.jumpToSegment(index)
                                                    val isSameDaf = !isAudioStopped && tractate.name == audioLockedTractate && selectedDaf == audioLockedDaf
                                                    if (isSameDaf) {
                                                        audioViewModel.seekToSeconds(seg.seconds.toFloat())
                                                        ShiurClient.jumpToAudioSegment(index)
                                                    }
                                                }
                                                .padding(horizontal = 10.dp, vertical = 4.dp)
                                        ) {
                                            Text(
                                                text = seg.displayTitle,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = if (isActive) { if (useWhiteBackground) Color.White else AppBlue } else appFg.copy(alpha = 0.8f),
                                                maxLines = 1
                                            )
                                        }
                                    }
                                }
                            }
                            CompositionLocalProvider(
                                LocalStudyFontSize provides studyFontSize.spSize.sp,
                                LocalIsBlueMode provides !useWhiteBackground
                            ) {
                                ShiurTextView(
                                    rewriteText = shiurDisplayText,
                                    currentSegmentIndex = shiurSegmentIndex,
                                    modifier = Modifier.weight(1f).fillMaxWidth(),
                                    amudBSegmentIndex = amudBSegmentIndex,
                                    amudBMicroTitle = amudBMicroTitle,
                                    onPrint = {
                                        PrintHelper.print(context, PrintableContent.Shiur(tractate.name, selectedDaf.toInt().toString(), shiurDisplayText), printFontSize, printLineSpacing)
                                    },
                                    onSegmentVisible = { idx -> ShiurClient.jumpToSegment(idx) }
                                )
                            }
                        }
                    }
                    else -> {
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
                }

                // Action row overlaid at the bottom of the image — hidden in Text mode
                if (mainContentMode != MainContentMode.TEXT) Row(
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
                                val startAt = shiurSegments.getOrNull(shiurSegmentIndex)
                                    ?.takeIf { shiurSegmentIndex > 0 }?.seconds?.toFloat() ?: 0f
                                audioViewModel.play(url, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}", startAt)
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

                    if (isAudioStopped && mainContentMode != MainContentMode.TEXT) {
                        FilledTonalButton(
                            onClick = { onStartStudy(tractate.name, selectedDaf.toInt(), studyMode, quizMode) },
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.AutoMirrored.Filled.MenuBook, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Study")
                        }
                    }
                }
            }

            // Text mode action row — Listen + Study buttons below the text content.
            // Only shown when audio is stopped; audio-playing state is handled by the bar below.
            if (mainContentMode == MainContentMode.TEXT && isAudioStopped) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(appBg)
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (hasAudio || isLoadingFeed) {
                        FilledTonalButton(
                            onClick = {
                                val url = audioUrl ?: return@FilledTonalButton
                                hasAutoRefreshedForAudio = false
                                val startAt = shiurSegments.getOrNull(shiurSegmentIndex)
                                    ?.takeIf { shiurSegmentIndex > 0 }?.seconds?.toFloat() ?: 0f
                                audioViewModel.play(url, "${tractate.name} ${FeedManager.dafLabel(selectedDaf)}", startAt)
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
                        onClick = { onStartStudy(tractate.name, selectedDaf.toInt(), studyMode, quizMode) },
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
                if (audioSegments.isNotEmpty() && duration > 0f) {
                    val stripListState = rememberLazyListState()
                    LaunchedEffect(audioSegmentIndex) {
                        stripListState.animateScrollToItem(audioSegmentIndex)
                    }
                    LazyRow(
                        state = stripListState,
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        contentPadding = PaddingValues(horizontal = 16.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        itemsIndexed(audioSegments) { index, seg ->
                            val isActive = index == audioSegmentIndex
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(50))
                                    .background(if (isActive) appFg.copy(alpha = 0.85f) else appFg.copy(alpha = 0.15f))
                                    .clickable {
                                        audioViewModel.seekToSeconds(seg.seconds.toFloat())
                                        ShiurClient.jumpToAudioSegment(index)
                                    }
                                    .padding(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                androidx.compose.material3.Text(
                                    text = seg.displayTitle,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isActive) { if (useWhiteBackground) Color.White else AppBlue } else appFg.copy(alpha = 0.8f),
                                    maxLines = 1
                                )
                            }
                        }
                    }
                }
                AudioPlayerBar(
                    audioViewModel = audioViewModel,
                    nowPlayingLabel = if (!isAudioStopped) "${audioLockedTractate} ${FeedManager.dafLabel(audioLockedDaf)}" else ""
                )
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
    contentColor: Color = Color.Unspecified,
    onAmudChange: ((Int) -> Unit)? = null
) {
    var tractateExpanded by remember { mutableStateOf(false) }
    var dafExpanded by remember { mutableStateOf(false) }

    val dafPickerItems = remember(tractate.name, episodeIndex) {
        buildList {
            for (n in tractate.dafRange) {
                add(n.toDouble())
                val half = n.toDouble() + 0.5
                if (episodeIndex[tractate.name]?.containsKey(half) == true) add(half)
            }
        }
    }

    // Initialize each LazyListState already scrolled to the selected item.
    // Keying on (expanded, selectedIndex) recreates the state each time the popup
    // opens so it is pre-positioned with no async jump on first frame.
    val tractateListState = remember(tractateExpanded, selectedTractateIndex) {
        LazyListState(firstVisibleItemIndex = if (tractateExpanded) selectedTractateIndex.coerceAtLeast(0) else 0)
    }
    val selectedDafIndex = remember(selectedDaf, dafPickerItems) {
        dafPickerItems.indexOf(selectedDaf).coerceAtLeast(0)
    }
    val dafListState = remember(dafExpanded, selectedDafIndex) {
        LazyListState(firstVisibleItemIndex = if (dafExpanded) selectedDafIndex else 0)
    }

    Row(
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        val useCustomColor = contentColor != Color.Unspecified
        val buttonColors = if (useCustomColor)
            ButtonDefaults.outlinedButtonColors(contentColor = contentColor) else ButtonDefaults.outlinedButtonColors()
        val buttonBorder = androidx.compose.foundation.BorderStroke(0.dp, Color.Transparent)

        // Tractate picker — Popup anchored below the button + LazyColumn.
        // Popup has no internal verticalScroll (unlike DropdownMenu) so LazyColumn
        // works without the nested-scrollable crash. Only visible rows are composed.
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
            if (tractateExpanded) {
                Popup(
                    alignment = Alignment.BottomStart,
                    onDismissRequest = { tractateExpanded = false },
                    properties = PopupProperties(focusable = true)
                ) {
                    // Column gives ColumnScope so AnimatedVisibility resolves to the
                    // correct overload (not RowScope.AnimatedVisibility from the outer Row).
                    var visible by remember { mutableStateOf(false) }
                    LaunchedEffect(Unit) { visible = true }
                    Column {
                    AnimatedVisibility(
                        visible = visible,
                        enter = expandVertically(
                            animationSpec = tween(durationMillis = 120),
                            expandFrom = Alignment.Top
                        ) + fadeIn(animationSpec = tween(durationMillis = 120))
                    ) {
                        androidx.compose.material3.Surface(
                            shape = RoundedCornerShape(4.dp),
                            shadowElevation = 8.dp,
                            color = MaterialTheme.colorScheme.surface
                        ) {
                            LazyColumn(
                                state = tractateListState,
                                modifier = Modifier
                                    .width(200.dp)
                                    .heightIn(max = 300.dp)
                            ) {
                                itemsIndexed(allTractates) { index, t ->
                                    val isSelected = index == selectedTractateIndex
                                    Text(
                                        text = t.name,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) MaterialTheme.colorScheme.primary
                                                else MaterialTheme.colorScheme.onSurface,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable {
                                                contentViewModel.selectTractate(index)
                                                tractateExpanded = false
                                            }
                                            .padding(horizontal = 16.dp, vertical = 10.dp)
                                    )
                                }
                            }
                        }
                    }
                    } // Column
                }
            }
        }

        // Daf picker — same Popup + LazyColumn approach
        Box {
            OutlinedButton(
                onClick = { dafExpanded = true },
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp),
                colors = buttonColors,
                border = buttonBorder
            ) {
                Text(FeedManager.dafLabel(selectedDaf), maxLines = 1, fontSize = 14.sp, fontWeight = FontWeight.Normal)
            }
            if (dafExpanded) {
                Popup(
                    alignment = Alignment.BottomStart,
                    onDismissRequest = { dafExpanded = false },
                    properties = PopupProperties(focusable = true)
                ) {
                    var visible by remember { mutableStateOf(false) }
                    LaunchedEffect(Unit) { visible = true }
                    Column {
                    AnimatedVisibility(
                        visible = visible,
                        enter = expandVertically(
                            animationSpec = tween(durationMillis = 120),
                            expandFrom = Alignment.Top
                        ) + fadeIn(animationSpec = tween(durationMillis = 120))
                    ) {
                        androidx.compose.material3.Surface(
                            shape = RoundedCornerShape(4.dp),
                            shadowElevation = 8.dp,
                            color = MaterialTheme.colorScheme.surface
                        ) {
                            LazyColumn(
                                state = dafListState,
                                modifier = Modifier
                                    .width(120.dp)
                                    .heightIn(max = 300.dp)
                            ) {
                                items(dafPickerItems) { daf ->
                                    val isSelected = daf == selectedDaf
                                    Text(
                                        text = FeedManager.dafLabel(daf),
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) MaterialTheme.colorScheme.primary
                                                else MaterialTheme.colorScheme.onSurface,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable {
                                                contentViewModel.selectDaf(daf)
                                                dafExpanded = false
                                            }
                                            .padding(horizontal = 16.dp, vertical = 10.dp)
                                    )
                                }
                            }
                        }
                    }
                    } // Column
                }
            }
        }

        // Single amud toggle — custom Box to avoid OutlinedButton's 58dp min-width
        val amudBorderColor = if (useCustomColor) contentColor.copy(alpha = 0.5f)
                              else MaterialTheme.colorScheme.outline
        val amudTextColor = if (useCustomColor) contentColor
                            else MaterialTheme.colorScheme.onSurface
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(6.dp))
                .background(amudBorderColor.copy(alpha = 0.15f)),
            verticalAlignment = Alignment.CenterVertically
        ) {
            listOf(0 to "a", 1 to "b").forEach { (amud, label) ->
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (selectedAmud == amud) amudBorderColor.copy(alpha = 0.5f) else Color.Transparent)
                        .clickable {
                            contentViewModel.selectAmud(amud)
                            onAmudChange?.invoke(amud)
                        }
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(label, color = amudTextColor, fontSize = 14.sp, fontWeight = if (selectedAmud == amud) FontWeight.SemiBold else FontWeight.Normal)
                }
            }
        }
    }
}

@Composable
private fun ContentModeSegment(
    label: String,
    selected: Boolean,
    fg: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(9.dp))
            .background(if (selected) fg.copy(alpha = 0.25f) else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            style = androidx.compose.material3.MaterialTheme.typography.labelMedium,
            color = fg
        )
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
