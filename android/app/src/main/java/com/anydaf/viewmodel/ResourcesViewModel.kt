package com.anydaf.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.data.ResourcesDiskCache
import com.anydaf.data.api.YCTLibraryClient
import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlin.math.abs

class ResourcesViewModel(application: Application) : AndroidViewModel(application) {

    private val context get() = getApplication<Application>().applicationContext

    // MARK: - Article list state

    private val _exactArticles = MutableStateFlow<List<YCTArticle>>(emptyList())
    val exactArticles: StateFlow<List<YCTArticle>> = _exactArticles

    private val _nearbyArticles = MutableStateFlow<List<YCTArticle>>(emptyList())
    val nearbyArticles: StateFlow<List<YCTArticle>> = _nearbyArticles

    private val _tractateArticles = MutableStateFlow<List<YCTArticle>>(emptyList())
    val tractateArticles: StateFlow<List<YCTArticle>> = _tractateArticles

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    val hasAnyArticles: Boolean get() =
        _exactArticles.value.isNotEmpty() ||
        _nearbyArticles.value.isNotEmpty() ||
        _tractateArticles.value.isNotEmpty()

    // MARK: - Article reader state

    private val _selectedArticle = MutableStateFlow<YCTArticle?>(null)
    val selectedArticle: StateFlow<YCTArticle?> = _selectedArticle

    private val _articleHtml = MutableStateFlow("")
    val articleHtml: StateFlow<String> = _articleHtml

    private val _isLoadingArticle = MutableStateFlow(false)
    val isLoadingArticle: StateFlow<Boolean> = _isLoadingArticle

    // MARK: - Cache

    /** In-memory tractate-level article cache. Keyed by tractate name. */
    private val allArticlesCache = mutableMapOf<String, List<YCTArticle>>()

    private val tractateTermCache = mutableMapOf<String, Int>()
    private val dafTermCache = mutableMapOf<String, Map<Int, Int>>()
    private var lastLoaded: Pair<String, Int>? = null

    // MARK: - Public: article list

    fun loadResources(tractate: String, daf: Int) {
        if (lastLoaded == tractate to daf) return
        lastLoaded = tractate to daf

        viewModelScope.launch {
            // Step 1: re-categorise from in-memory tractate cache (instant, no I/O)
            allArticlesCache[tractate]?.let { all ->
                categorize(all, daf)
                return@launch
            }

            // Step 2: try disk cache
            ResourcesDiskCache.load(context, tractate)?.let { all ->
                val clean = mergeAndDeduplicate(all)
                allArticlesCache[tractate] = clean
                categorize(clean, daf)
                return@launch
            }

            // Step 3: cache miss — fetch every daf in the tractate from the network
            _isLoading.value = true
            _error.value = null
            _exactArticles.value = emptyList()
            _nearbyArticles.value = emptyList()
            _tractateArticles.value = emptyList()

            try {
                val tractateTermID = resolveTractateTermID(tractate) ?: run {
                    _isLoading.value = false
                    return@launch
                }

                val dafTermMap = resolveDafTermIDs(tractate, tractateTermID)

                val all = mutableListOf<YCTArticle>()
                for (dafNum in dafTermMap.keys.sorted()) {
                    val termID = dafTermMap[dafNum] ?: continue
                    all += fetchAndTag(listOf(termID), ResourceMatchType.TractateWide(dafNum))
                }

                val merged = mergeAndDeduplicate(all)

                // Step 4: persist and categorise
                allArticlesCache[tractate] = merged
                ResourcesDiskCache.save(context, tractate, merged)
                categorize(merged, daf)

            } catch (e: Exception) {
                _error.value = e.message ?: "Unknown error"
            }

            _isLoading.value = false
        }
    }

    fun reset() {
        _exactArticles.value = emptyList()
        _nearbyArticles.value = emptyList()
        _tractateArticles.value = emptyList()
        _isLoading.value = false
        _error.value = null
        lastLoaded = null
        // allArticlesCache is intentionally preserved: if the user returns to a
        // previously visited tractate the articles are available instantly.
    }

    // MARK: - Public: article reader

    fun selectArticle(article: YCTArticle) {
        _selectedArticle.value = article
        _articleHtml.value = ""
        _isLoadingArticle.value = true
        viewModelScope.launch {
            try {
                _articleHtml.value = YCTLibraryClient.fetchArticleContent(article.id)
            } catch (e: Exception) {
                _articleHtml.value = "<p>Failed to load article.</p>"
            } finally {
                _isLoadingArticle.value = false
            }
        }
    }

    fun dismissArticle() {
        _selectedArticle.value = null
        _articleHtml.value = ""
        _isLoadingArticle.value = false
    }

    suspend fun fetchArticleContent(id: Int): String =
        YCTLibraryClient.fetchArticleContent(id)

    // MARK: - Categorisation

    /**
     * Splits a flat tractate article list into exact / nearby / tractate-wide
     * sections based on [currentDaf], then publishes the results.
     */
    private fun categorize(articles: List<YCTArticle>, currentDaf: Int) {
        val exact    = mutableListOf<YCTArticle>()
        val nearby   = mutableListOf<YCTArticle>()
        val tractate = mutableListOf<YCTArticle>()

        for (article in articles) {
            val d = article.matchType.referencedDaf
            when {
                d == currentDaf        -> exact.add(article.copy(matchType = ResourceMatchType.Exact(d)))
                abs(d - currentDaf) <= 2 -> nearby.add(article.copy(matchType = ResourceMatchType.Nearby(d)))
                else                   -> tractate.add(article.copy(matchType = ResourceMatchType.TractateWide(d)))
            }
        }

        // Sort nearby by proximity so ±1 appears before ±2
        nearby.sortBy { abs(it.matchType.referencedDaf - currentDaf) }

        _exactArticles.value    = exact
        _nearbyArticles.value   = nearby
        _tractateArticles.value = tractate
    }

    // MARK: - Private

    private suspend fun resolveTractateTermID(tractate: String): Int? {
        tractateTermCache[tractate]?.let { return it }
        val id = YCTLibraryClient.fetchTractateTermID(tractate) ?: return null
        tractateTermCache[tractate] = id
        return id
    }

    private suspend fun resolveDafTermIDs(tractate: String, tractateTermID: Int): Map<Int, Int> {
        dafTermCache[tractate]?.let { return it }
        val map = YCTLibraryClient.fetchDafTermIDs(tractateTermID)
        dafTermCache[tractate] = map
        return map
    }

    /**
     * Two-pass deduplication:
     * Pass 1 — same article ID, different daf: merge into one entry, collecting
     *          extra dafs in additionalDafs; same ID + same daf = API duplicate, skip.
     * Pass 2 — different ID, same title (WordPress duplicate posts): keep the more
     *          recently published version at the first-encountered daf position.
     */
    private fun mergeAndDeduplicate(articles: List<YCTArticle>): List<YCTArticle> {
        // Pass 1: merge by article ID
        val idToIndex = mutableMapOf<Int, Int>()
        val merged = mutableListOf<YCTArticle>()

        for (article in articles) {
            val idx = idToIndex[article.id]
            if (idx != null) {
                val newDaf = article.matchType.referencedDaf
                if (newDaf != merged[idx].matchType.referencedDaf &&
                    !merged[idx].additionalDafs.contains(newDaf)) {
                    merged[idx] = merged[idx].copy(
                        additionalDafs = (merged[idx].additionalDafs + newDaf).sorted()
                    )
                }
            } else {
                idToIndex[article.id] = merged.size
                merged.add(article)
            }
        }

        // Pass 2: deduplicate by title, keeping more recent content
        val fmt = java.text.SimpleDateFormat("MMM d, yyyy", java.util.Locale.US)
        val titleToIndex = mutableMapOf<String, Int>()
        val result = mutableListOf<YCTArticle>()

        for (article in merged) {
            val key = article.title.trim().lowercase()
            val idx = titleToIndex[key]
            if (idx != null) {
                val combined = (result[idx].additionalDafs + article.additionalDafs)
                    .toSortedSet()
                    .filter { it != result[idx].matchType.referencedDaf }
                val newDate = runCatching { fmt.parse(article.date) }.getOrNull()
                val oldDate = runCatching { fmt.parse(result[idx].date) }.getOrNull()
                if (newDate != null && oldDate != null && newDate > oldDate) {
                    result[idx] = article.copy(
                        matchType = result[idx].matchType,
                        additionalDafs = (combined + article.matchType.referencedDaf)
                            .toSortedSet()
                            .filter { it != result[idx].matchType.referencedDaf }
                    )
                } else {
                    result[idx] = result[idx].copy(additionalDafs = combined)
                }
            } else {
                titleToIndex[key] = result.size
                result.add(article)
            }
        }
        return result
    }

    private suspend fun fetchAndTag(
        termIDs: List<Int>,
        matchType: ResourceMatchType
    ): List<YCTArticle> {
        val fetched = YCTLibraryClient.fetchArticles(
            exactTermIDs = termIDs,
            nearbyTermIDs = emptyMap(),
            tractateTermID = null
        )
        return fetched.map { it.copy(matchType = matchType) }
    }
}
