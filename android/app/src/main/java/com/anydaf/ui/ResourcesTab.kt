package com.anydaf.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.PlayCircleFilled
import androidx.compose.material.icons.filled.QuestionAnswer
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.anydaf.model.ResourceMatchType
import com.anydaf.model.StudyFontSize
import com.anydaf.model.YCTArticle
import com.anydaf.viewmodel.ResourcesViewModel

@Composable
fun ResourcesTab(
    viewModel: ResourcesViewModel,
    studyFontSize: StudyFontSize = StudyFontSize.MEDIUM,
    onSizeChange: (StudyFontSize) -> Unit = {},
    printFontSize: StudyFontSize = StudyFontSize.SMALL,
    printLineSpacing: Double = 1.15,
    /** Called when an embedded <audio> element (podcast episode) starts playing, so the
     *  caller can pause the app's main daf/shiur audio to avoid overlap. */
    onAudioPlay: () -> Unit = {},
    /** Called when the user taps "Play Episode" for a resolved SoundCloud track —
     *  (trackID, title) — so the caller can start it on the app's shared audio player. */
    onPlayAudioTrack: (String, String, String?) -> Unit = { _, _, _ -> }
) {
    val exactArticles by viewModel.exactArticles.collectAsState()
    val nearbyArticles by viewModel.nearbyArticles.collectAsState()
    val tractateArticles by viewModel.tractateArticles.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val selectedArticle by viewModel.selectedArticle.collectAsState()
    val articleHtml by viewModel.articleHtml.collectAsState()
    val isLoadingArticle by viewModel.isLoadingArticle.collectAsState()
    val episodeTrackID by viewModel.episodeTrackID.collectAsState()

    val hasAny = exactArticles.isNotEmpty() || nearbyArticles.isNotEmpty() || tractateArticles.isNotEmpty()

    Box(Modifier.fillMaxSize()) {
        when {
            isLoading -> {
                Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(Modifier.height(12.dp))
                        Text("Loading articles…", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            !hasAny -> {
                Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(24.dp)
                    ) {
                        Text(
                            "No articles found for this tractate",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        error?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Tier 1: exact daf
                    if (exactArticles.isNotEmpty()) {
                        item { SectionHeader("On the daf") }
                        items(exactArticles, key = { it.id }) { article ->
                            ArticleCard(article, onTap = { viewModel.selectArticle(article) })
                        }
                    }

                    // Divider between exact and nearby
                    if (exactArticles.isNotEmpty() && (nearbyArticles.isNotEmpty() || tractateArticles.isNotEmpty())) {
                        item {
                            HorizontalDivider(
                                color = if (LocalIsBlueMode.current) androidx.compose.ui.graphics.Color.White.copy(alpha = 0.3f)
                                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
                                modifier = Modifier.padding(vertical = 8.dp)
                            )
                        }
                    }

                    // Tier 2: nearby ±2 dafs
                    if (nearbyArticles.isNotEmpty()) {
                        item { SectionHeader("In the vicinity") }
                        items(nearbyArticles, key = { it.id }) { article ->
                            ArticleCard(article, onTap = { viewModel.selectArticle(article) })
                        }
                    }

                    // Divider between nearby and tractate
                    if (nearbyArticles.isNotEmpty() && tractateArticles.isNotEmpty()) {
                        item {
                            HorizontalDivider(
                                color = if (LocalIsBlueMode.current) androidx.compose.ui.graphics.Color.White.copy(alpha = 0.3f)
                                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
                                modifier = Modifier.padding(vertical = 8.dp)
                            )
                        }
                    }

                    // Tier 3: all tractate articles in daf order
                    if (tractateArticles.isNotEmpty()) {
                        item { SectionHeader("On the tractate") }
                        items(tractateArticles, key = { it.id }) { article ->
                            ArticleCard(article, onTap = { viewModel.selectArticle(article) })
                        }
                    }

                    item { Spacer(Modifier.height(8.dp)) }
                }
            }
        }

        // In-app article reader overlay
        AnimatedVisibility(
            visible = selectedArticle != null,
            enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
            exit = slideOutVertically(targetOffsetY = { it }) + fadeOut()
        ) {
            selectedArticle?.let { article ->
                ArticleReaderScreen(
                    article = article,
                    html = articleHtml,
                    isLoading = isLoadingArticle,
                    studyFontSize = studyFontSize,
                    onSizeChange = onSizeChange,
                    onDismiss = { viewModel.dismissArticle() },
                    printFontSize = printFontSize,
                    printLineSpacing = printLineSpacing,
                    onAudioPlay = onAudioPlay,
                    trackID = episodeTrackID,
                    onPlayAudioTrack = onPlayAudioTrack
                )
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    val fg = if (LocalIsBlueMode.current) androidx.compose.ui.graphics.Color.White.copy(alpha = 0.7f)
             else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
    Text(
        text = title.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = fg,
        letterSpacing = 0.8.sp,
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
    )
}

@Composable
private fun ArticleCard(article: YCTArticle, onTap: () -> Unit) {
    val fontSize = LocalStudyFontSize.current
    val alpha = when (article.matchType) {
        is ResourceMatchType.Exact -> 1f
        is ResourceMatchType.Nearby -> 0.8f
        is ResourceMatchType.TractateWide -> 0.8f
    }
    val referencedDaf = article.matchType.referencedDaf

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(alpha)
            .clickable { onTap() },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (!article.imageURL.isNullOrEmpty()) {
                ArticleThumbnail(article.imageURL, showPlayIcon = article.source == com.anydaf.model.YCTSource.AUDIO)
            }
            Column(modifier = Modifier.weight(1f)) {
                val titleSize = fontSize
                val bodySize = fontSize * 0.85f
                val labelSize = fontSize * 0.75f
                // Title gets the full card width so it wraps normally — putting the
                // icon/daf-tag row on the same line as the title constrains every wrapped
                // line (not just the first) to the width left over after the trailing
                // content, wasting the rest of the card's width on long titles.
                Text(
                    text = article.title,
                    style = MaterialTheme.typography.titleSmall.copy(
                        fontSize = titleSize,
                        lineHeight = (titleSize.value * 1.35f).sp
                    ),
                    modifier = Modifier.fillMaxWidth(),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(Modifier.height(4.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (article.source == com.anydaf.model.YCTSource.AUDIO) {
                        Icon(
                            Icons.Default.Headphones,
                            contentDescription = "Audio episode",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(14.dp)
                        )
                    } else if (article.source == com.anydaf.model.YCTSource.PSAK) {
                        Icon(
                            Icons.Filled.QuestionAnswer,
                            contentDescription = "Psak question",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(14.dp)
                        )
                    }
                    (listOf(referencedDaf) + article.additionalDafs).filter { it > 0 }.sorted().forEach { d ->
                        SuggestionChip(
                            onClick = {},
                            label = {
                                Text(
                                    "Daf $d",
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = labelSize)
                                )
                            }
                        )
                    }
                }
                if (article.authorName.isNotEmpty()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = article.authorName,
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontSize = bodySize,
                            lineHeight = (bodySize.value * 1.4f).sp
                        ),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (article.excerpt.isNotEmpty()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = article.excerpt,
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontSize = bodySize,
                            lineHeight = (bodySize.value * 1.4f).sp
                        ),
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f)
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    text = article.date,
                    style = MaterialTheme.typography.labelSmall.copy(fontSize = labelSize),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** Article thumbnail, shown on any card whose post has a WordPress featured image (library
 *  essays commonly do; psak posts rarely do). Audio episodes additionally get a small
 *  play-button overlay, SoundCloud-style, so a listen reads as distinct from a read. */
@Composable
private fun ArticleThumbnail(imageURL: String, showPlayIcon: Boolean) {
    Box(
        modifier = Modifier
            .size(56.dp)
            .clip(RoundedCornerShape(8.dp))
    ) {
        AsyncImage(
            model = imageURL,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize()
        )
        if (showPlayIcon) {
            Box(modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.2f)))
            Icon(
                Icons.Filled.PlayCircleFilled,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(22.dp).align(Alignment.Center)
            )
        }
    }
}
