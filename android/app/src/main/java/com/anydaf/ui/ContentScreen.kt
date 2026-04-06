package com.anydaf.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.material3.TopAppBar
import android.content.Intent
import android.net.Uri
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.anydaf.data.api.FeedManager
import com.anydaf.data.api.ShiurClient
import com.anydaf.model.Bookmark
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import com.anydaf.model.QuizMode
import com.anydaf.model.StudyMode
import com.anydaf.model.Tractate
import com.anydaf.model.allTractates
import com.anydaf.viewmodel.AudioViewModel
import com.anydaf.viewmodel.BookmarkViewModel
import com.anydaf.viewmodel.ContentViewModel
import com.anydaf.viewmodel.PdfViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContentScreen(
    contentViewModel: ContentViewModel,
    audioViewModel: AudioViewModel,
    bookmarkViewModel: BookmarkViewModel,
    pdfViewModel: PdfViewModel,
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
                contentViewModel.dismissDonationNudge()
            },
            onDismiss = { contentViewModel.dismissDonationNudge() }
        )
    }
    
    val scope = rememberCoroutineScope()
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

    // Always load on first appearance — mirrors iOS onAppear (no audio guard needed here).
    LaunchedEffect(Unit) {
        ShiurClient.load(tractate.name, selectedDaf)
    }

    // Reload when daf/tractate changes (includes when saved prefs load on startup).
    LaunchedEffect(tractate.name, selectedDaf) {
        ShiurClient.load(tractate.name, selectedDaf)
    }

    // When audio stops, sync segments to whatever daf the picker is now showing.
    LaunchedEffect(isAudioStopped) {
        if (isAudioStopped) ShiurClient.load(tractate.name, selectedDaf)
    }

    // Fall back to Daf view automatically if the new daf has no shiur text.
    LaunchedEffect(shiurRewrite) {
        if (shiurRewrite == null) showShiurText = false
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
            FeedManager.fetchAll()
            // Re-look up URL — may now be a direct RSS MP3 rather than a soundcloud-track stub
            val freshUrl = FeedManager.episodeIndex.value[tractate.name]?.get(selectedDaf)
            if (freshUrl != null) {
                audioViewModel.play(freshUrl, "${tractate.name} $selectedDaf")
            }
        }
    }

    val isBookmarked = bookmarkViewModel.isBookmarked(selectedTractateIndex, selectedDaf, selectedAmud)
    var pendingNewBookmark by remember { mutableStateOf<Bookmark?>(null) }

    // Derived synchronously from the StateFlow — updates automatically when feed loads
    val audioUrl = episodeIndex[tractate.name]?.get(selectedDaf)
    val hasAudio = audioUrl != null

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AnyDaf", fontWeight = FontWeight.Bold) },
                actions = {
                    if (isFetchingDafYomi) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp).padding(2.dp))
                    } else {
                        IconButton(onClick = { contentViewModel.fetchTodaysDaf() }) {
                            Icon(Icons.Default.Today, contentDescription = "Today's Daf")
                        }
                    }
                    IconButton(onClick = onOpenBookmarks) {
                        Icon(Icons.Default.Bookmark, contentDescription = "Bookmarks")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Spacer(Modifier.height(4.dp))

            // Picker row: [tractate + daf card] [A/B box on right] — fixed height so both cards match
            Row(
                modifier = Modifier.fillMaxWidth().height(88.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Card(
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    elevation = CardDefaults.cardElevation(4.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(8.dp),
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
                            DafWheelPicker(
                                dafRange = tractate.dafRange,
                                selectedDaf = selectedDaf,
                                onSelected = { contentViewModel.selectDaf(it) }
                            )
                        }
                    }
                }

                // A / B amud buttons — same fixed height as tractate card
                Card(
                    modifier = Modifier.fillMaxHeight(),
                    elevation = CardDefaults.cardElevation(4.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxHeight()
                            .padding(horizontal = 4.dp, vertical = 6.dp),
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

            // Audio player bar
            if (!isAudioStopped) {
                AudioPlayerBar(audioViewModel = audioViewModel)
            }

            // Chapter navigation strip — shown when segment data is available and audio is loaded
            if (shiurSegments.isNotEmpty() && duration > 0f) {
                val stripListState = rememberLazyListState()
                LaunchedEffect(shiurSegmentIndex) {
                    stripListState.animateScrollToItem(shiurSegmentIndex)
                }
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
                            androidx.compose.material3.Text(
                                text = seg.title,
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isActive) MaterialTheme.colorScheme.onPrimary
                                        else MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1
                            )
                        }
                    }
                }
            }

            // Daf / Shiur toggle — only when lecture text is available
            if (shiurRewrite != null) {
                TabRow(selectedTabIndex = if (showShiurText) 1 else 0) {
                    Tab(
                        selected = !showShiurText,
                        onClick = { showShiurText = false },
                        text = { Text("Daf") }
                    )
                    Tab(
                        selected = showShiurText,
                        onClick = { showShiurText = true },
                        text = { Text("Shiur") }
                    )
                }
            }

            // Main content area: daf image or lecture text
            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                val shiurDisplayText = if (shiurShowSources) shiurFinal ?: shiurRewrite else shiurRewrite
                if (showShiurText && shiurDisplayText != null) {
                    ShiurTextView(
                        rewriteText = shiurDisplayText,
                        currentSegmentIndex = shiurSegmentIndex,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    if (pdfViewModel.hasPages(tractate.name)) {
                        DafPageView(
                            tractate = tractate,
                            daf = selectedDaf,
                            amud = selectedAmud,
                            pdfViewModel = pdfViewModel,
                            onDafAmudChange = { newDaf, newAmud ->
                                contentViewModel.selectDaf(newDaf)
                                contentViewModel.selectAmud(newAmud)
                            },
                            modifier = Modifier.fillMaxSize()
                        )
                    }
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
                    modifier = Modifier.align(Alignment.TopEnd)
                ) {
                    Icon(
                        if (isBookmarked) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                        "Bookmark"
                    )
                }
            }

            // Action row — Listen | Study
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                FilledTonalButton(
                    onClick = {
                        if (!isAudioStopped) {
                            audioViewModel.stop()
                        } else {
                            val url = audioUrl ?: return@FilledTonalButton
                            hasAutoRefreshedForAudio = false
                            audioViewModel.play(url, "${tractate.name} $selectedDaf")
                        }
                    },
                    enabled = hasAudio || !isAudioStopped,
                    modifier = Modifier.weight(1f)
                ) {
                    if (isLoadingFeed && isAudioStopped && !hasAudio) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(6.dp))
                        Text("Loading…")
                    } else {
                        Icon(if (isAudioStopped) Icons.Default.PlayArrow else Icons.Default.Stop, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(if (isAudioStopped) "Listen" else "Stop")
                    }
                }

                FilledTonalButton(
                    onClick = { onStartStudy(tractate.name, selectedDaf, studyMode, quizMode) },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.MenuBook, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Study")
                }
            }
            Spacer(Modifier.height(4.dp))
        }
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
    dafRange: List<Int>,
    selectedDaf: Int,
    onSelected: (Int) -> Unit
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
                text = "$daf",
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
