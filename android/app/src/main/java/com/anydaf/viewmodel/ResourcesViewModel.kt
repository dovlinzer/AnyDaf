package com.anydaf.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.data.ResourcesDiskCache
import com.anydaf.data.api.YCTLibraryClient
import com.anydaf.model.ResourceMatchType
import com.anydaf.model.YCTArticle
import com.anydaf.model.YCTSource
import kotlinx.coroutines.async
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

    /** In-memory tractate-level article cache. Keyed by "<source>:<tractate>". */
    private val allArticlesCache = mutableMapOf<String, List<YCTArticle>>()

    private val libraryClient = YCTLibraryClient.library
    private val psakClient    = YCTLibraryClient.psak

    private var lastLoaded: Pair<String, Int>? = null

    // MARK: - Public: article list

    fun loadResources(tractate: String, daf: Int) {
        if (lastLoaded == tractate to daf) return
        lastLoaded = tractate to daf

        viewModelScope.launch {
            val libraryKey = cacheKey(YCTSource.LIBRARY, tractate)
            val psakKey    = cacheKey(YCTSource.PSAK, tractate)

            // Step 1: re-categorise from in-memory cache (instant, no I/O)
            val memLib  = allArticlesCache[libraryKey]
            val memPsak = allArticlesCache[psakKey]
            if (memLib != null && memPsak != null) {
                categorize(memLib + memPsak, daf)
                return@launch
            }

            // Step 2: try disk cache
            val cachedLib  = memLib  ?: ResourcesDiskCache.load(context, tractate, YCTSource.LIBRARY)
            val cachedPsak = memPsak ?: ResourcesDiskCache.load(context, tractate, YCTSource.PSAK)

            if (cachedLib != null && cachedPsak != null) {
                allArticlesCache[libraryKey] = cachedLib
                allArticlesCache[psakKey]    = cachedPsak
                categorize(cachedLib + cachedPsak, daf)
                return@launch
            }

            // Step 3: cache miss — fetch from network (both sources in parallel)
            _isLoading.value = true
            _error.value = null
            _exactArticles.value = emptyList()
            _nearbyArticles.value = emptyList()
            _tractateArticles.value = emptyList()

            try {
                val libraryDeferred = async { fetchAllFromClient(libraryClient, tractate, cachedLib) }
                val psakDeferred    = async { fetchAllFromClient(psakClient,    tractate, cachedPsak) }

                val lib  = libraryDeferred.await()
                val psak = psakDeferred.await()

                if (cachedLib == null) {
                    allArticlesCache[libraryKey] = lib
                    ResourcesDiskCache.save(context, tractate, YCTSource.LIBRARY, lib)
                } else {
                    allArticlesCache[libraryKey] = cachedLib
                }
                if (cachedPsak == null) {
                    allArticlesCache[psakKey] = psak
                    ResourcesDiskCache.save(context, tractate, YCTSource.PSAK, psak)
                } else {
                    allArticlesCache[psakKey] = cachedPsak
                }

                categorize(
                    (allArticlesCache[libraryKey] ?: emptyList()) +
                    (allArticlesCache[psakKey]    ?: emptyList()),
                    daf
                )

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
        // allArticlesCache is intentionally preserved.
    }

    // MARK: - Public: article reader

    fun selectArticle(article: YCTArticle) {
        _selectedArticle.value = article
        _articleHtml.value = ""
        _isLoadingArticle.value = true
        viewModelScope.launch {
            try {
                _articleHtml.value = when (article.source) {
                    YCTSource.LIBRARY -> libraryClient.fetchArticleContent(article.id)
                    YCTSource.PSAK    -> psakClient.fetchArticleContent(article.id)
                }
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

    // MARK: - Categorisation

    private fun categorize(articles: List<YCTArticle>, currentDaf: Int) {
        val exact    = mutableListOf<YCTArticle>()
        val nearby   = mutableListOf<YCTArticle>()
        val tractate = mutableListOf<YCTArticle>()

        for (article in articles) {
            val d = article.matchType.referencedDaf
            when {
                // daf 0 is the sentinel for psak articles tagged at the tractate level
                d == 0              -> tractate.add(article.copy(matchType = ResourceMatchType.TractateWide(0)))
                d == currentDaf     -> exact.add(article.copy(matchType = ResourceMatchType.Exact(d)))
                abs(d - currentDaf) <= 2 -> nearby.add(article.copy(matchType = ResourceMatchType.Nearby(d)))
                else                -> tractate.add(article.copy(matchType = ResourceMatchType.TractateWide(d)))
            }
        }

        // Sort nearby by ascending daf number
        nearby.sortBy { it.matchType.referencedDaf }

        // Sort tractate-wide by daf number; daf 0 (tractate-level psak) goes last
        tractate.sortWith(Comparator { a, b ->
            val da = a.matchType.referencedDaf
            val db = b.matchType.referencedDaf
            when {
                da == 0 -> 1
                db == 0 -> -1
                else    -> da - db
            }
        })

        _exactArticles.value    = exact
        _nearbyArticles.value   = nearby
        _tractateArticles.value = tractate
    }

    // MARK: - Private

    private fun cacheKey(source: YCTSource, tractate: String) = "${source.name}:$tractate"

    /**
     * Fetches all articles for a tractate from a single client, or returns the
     * cached slice when available.
     */
    private suspend fun fetchAllFromClient(
        client: YCTLibraryClient,
        tractate: String,
        cached: List<YCTArticle>?
    ): List<YCTArticle> {
        if (cached != null) return cached

        val tractateTermID = client.resolveTractateTermID(tractate) ?: return emptyList()
        val dafTermMap = client.resolveDafTermIDs(tractate, tractateTermID)

        val all = mutableListOf<YCTArticle>()

        // Fetch articles for each daf-level term
        for (dafNum in dafTermMap.keys.sorted()) {
            val termID = dafTermMap[dafNum] ?: continue
            all += fetchAndTag(client, listOf(termID), ResourceMatchType.TractateWide(dafNum))
        }

        // For psak: also fetch articles tagged directly on the tractate term (daf = 0 sentinel)
        if (client.fetchesTractateLevel) {
            all += fetchAndTag(client, listOf(tractateTermID), ResourceMatchType.TractateWide(0))
        }

        return mergeAndDeduplicate(all)
    }

    /**
     * Two-pass deduplication:
     * Pass 1 — same article ID, different daf: merge into one entry.
     * Pass 2 — different ID, same title: keep the more recently published version.
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
        client: YCTLibraryClient,
        termIDs: List<Int>,
        matchType: ResourceMatchType
    ): List<YCTArticle> {
        val fetched = client.fetchArticles(termIDs)
        return fetched.map { it.copy(matchType = matchType) }
    }
}
