package com.anydaf.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import com.anydaf.data.api.FeedManager
import com.anydaf.model.QuizMode
import com.anydaf.model.SourceDisplayMode
import com.anydaf.model.StudyFontSize
import com.anydaf.viewmodel.ContentViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    contentViewModel: ContentViewModel,
    onBack: () -> Unit,
    onAbout: () -> Unit = {}
) {
    val quizMode by contentViewModel.quizMode.collectAsState()
    val sourceDisplayMode by contentViewModel.sourceDisplayMode.collectAsState()
    val shiurShowSources by contentViewModel.shiurShowSources.collectAsState()
    val studyFontSize by contentViewModel.studyFontSize.collectAsState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var isReloading by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
        ) {
            SectionHeader("Support AnyDaf")
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://wl.donorperfect.net/weblink/weblink.aspx?name=yctorah&id=2"))
                        context.startActivity(intent)
                    }
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.Favorite, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(16.dp))
                Text("Donate to YCT", style = MaterialTheme.typography.bodyLarge)
            }
            Text(
                "AnyDaf is provided free by Yeshivat Chovevei Torah. Your donation supports Torah learning.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp)
            )

            SectionDivider()

            SectionHeader("Translation Display")
            SourceDisplayMode.entries.forEach { mode ->
                RadioRow(
                    label = mode.displayName,
                    selected = sourceDisplayMode == mode,
                    onClick = { contentViewModel.selectSourceDisplayMode(mode) }
                )
            }

            SectionDivider()

            SectionHeader("Quiz Mode")
            QuizMode.entries.forEach { mode ->
                RadioRow(
                    label = mode.displayName,
                    selected = quizMode == mode,
                    onClick = { contentViewModel.selectQuizMode(mode) }
                )
            }

            SectionDivider()

            SectionHeader("Shiur")
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { contentViewModel.setShiurShowSources(!shiurShowSources) }
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Include source text", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                Switch(
                    checked = shiurShowSources,
                    onCheckedChange = { contentViewModel.setShiurShowSources(it) }
                )
            }

            SectionDivider()

            SectionHeader("Appearance")
            Text(
                "Study text size",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 2.dp)
            )
            FontSizeControl(
                studyFontSize = studyFontSize,
                onSizeChange = { contentViewModel.setStudyFontSize(it) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
            )
            Text(
                studyFontSize.displayName,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
            Text(
                "Applies to translations, summaries, shiur, and quiz content.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp)
            )

            SectionDivider()

            SectionHeader("About")
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onAbout() }
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.Info, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(16.dp))
                Text("About AnyDaf", style = MaterialTheme.typography.bodyLarge)
            }

            SectionDivider()

            SectionHeader("Audio")
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        if (!isReloading) {
                            scope.launch {
                                isReloading = true
                                FeedManager.forceRefresh()
                                isReloading = false
                            }
                        }
                    }
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isReloading) {
                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Default.Refresh, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                }
                Spacer(Modifier.width(16.dp))
                Text(
                    if (isReloading) "Reloading…" else "Reload Audio Episodes",
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp)
    )
}

@Composable
private fun SectionDivider() {
    HorizontalDivider(modifier = Modifier.padding(top = 8.dp))
}

@Composable
fun FontSizeControl(
    studyFontSize: StudyFontSize,
    onSizeChange: (StudyFontSize) -> Unit,
    modifier: Modifier = Modifier
) {
    val cases = StudyFontSize.entries
    val idx = cases.indexOf(studyFontSize)

    Row(
        modifier = modifier.height(44.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Small A — decrease
        androidx.compose.material3.TextButton(
            onClick = { if (idx > 0) onSizeChange(cases[idx - 1]) },
            enabled = idx > 0,
            modifier = Modifier.size(44.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
        ) {
            Text(
                "A",
                style = MaterialTheme.typography.labelMedium,
                color = if (idx > 0) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
            )
        }

        // Step dots — growing sizes spanning the space between the two A buttons
        Row(
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            cases.forEachIndexed { i, _ ->
                val dotSize = (5 + i * 2).dp
                Box(
                    modifier = Modifier
                        .size(dotSize)
                        .background(
                            color = if (i == idx) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.2f),
                            shape = CircleShape
                        )
                )
            }
        }

        // Large A — increase
        androidx.compose.material3.TextButton(
            onClick = { if (idx < cases.size - 1) onSizeChange(cases[idx + 1]) },
            enabled = idx < cases.size - 1,
            modifier = Modifier.size(44.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)
        ) {
            Text(
                "A",
                style = MaterialTheme.typography.titleMedium,
                color = if (idx < cases.size - 1) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
            )
        }
    }
}

@Composable
private fun RadioRow(
    label: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        RadioButton(selected = selected, onClick = onClick)
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}
