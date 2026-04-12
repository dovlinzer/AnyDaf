package com.anydaf.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import com.anydaf.viewmodel.ResourcesViewModel

@Composable
fun ResourcesTab(viewModel: ResourcesViewModel) {
    val exactArticles by viewModel.exactArticles.collectAsState()
    val nearbyArticles by viewModel.nearbyArticles.collectAsState()
    val tractateArticles by viewModel.tractateArticles.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val selectedArticle by viewModel.selectedArticle.collectAsState()
    val articleHtml by viewModel.articleHtml.collectAsState()
    val isLoadingArticle by viewModel.isLoadingArticle.collectAsState()

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
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
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
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
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
                    onDismiss = { viewModel.dismissArticle() }
                )
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        text = title.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
        letterSpacing = 0.8.sp,
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
    )
}

@Composable
private fun ArticleCard(article: YCTArticle, onTap: () -> Unit) {
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
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Text(
                    text = article.title,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    modifier = Modifier.padding(start = 8.dp)
                ) {
                    (listOf(referencedDaf) + article.additionalDafs).filter { it > 0 }.sorted().forEach { d ->
                        SuggestionChip(
                            onClick = {},
                            label = {
                                Text(
                                    "Daf $d",
                                    style = MaterialTheme.typography.labelSmall
                                )
                            }
                        )
                    }
                }
            }
            if (article.authorName.isNotEmpty()) {
                Spacer(Modifier.height(2.dp))
                Text(
                    text = article.authorName,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            if (article.excerpt.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    text = article.excerpt,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f)
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = article.date,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
