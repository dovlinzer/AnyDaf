package com.anydaf.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.AnyDafApp
import com.anydaf.data.api.DafYomiService
import com.anydaf.data.api.FeedManager
import com.anydaf.data.prefs.AppPreferences
import com.anydaf.model.QuizMode
import com.anydaf.model.SourceDisplayMode
import com.anydaf.model.StudyFontSize
import com.anydaf.model.StudyMode
import com.anydaf.model.allTractates
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

private const val ENGAGEMENT_NUDGE_THRESHOLD_SECONDS = 3 * 3600L   // 3 hours
private const val NUDGE_MIN_INTERVAL_MS = 60L * 24 * 3600 * 1000  // 60 days

class ContentViewModel : ViewModel() {

    private val _showDonationNudge = MutableStateFlow(false)
    val showDonationNudge: StateFlow<Boolean> = _showDonationNudge.asStateFlow()

    private var sessionStartMs: Long? = null
    private var nudgeCheckedThisSession = false
    private var persistedEngagementSeconds = 0L

    private val _selectedTractateIndex = MutableStateFlow(0)
    val selectedTractateIndex: StateFlow<Int> = _selectedTractateIndex.asStateFlow()

    private val _selectedDaf = MutableStateFlow(2.0)
    val selectedDaf: StateFlow<Double> = _selectedDaf.asStateFlow()

    private val _selectedAmud = MutableStateFlow(0)
    val selectedAmud: StateFlow<Int> = _selectedAmud.asStateFlow()

    private val _quizMode = MutableStateFlow(QuizMode.MULTIPLE_CHOICE)
    val quizMode: StateFlow<QuizMode> = _quizMode.asStateFlow()

    private val _studyMode = MutableStateFlow(StudyMode.FACTS)
    val studyMode: StateFlow<StudyMode> = _studyMode.asStateFlow()

    private val _sourceDisplayMode = MutableStateFlow(SourceDisplayMode.TOGGLE)
    val sourceDisplayMode: StateFlow<SourceDisplayMode> = _sourceDisplayMode.asStateFlow()

    private val _shiurShowSources = MutableStateFlow(true)
    val shiurShowSources: StateFlow<Boolean> = _shiurShowSources.asStateFlow()

    private val _studyFontSize = MutableStateFlow(StudyFontSize.MEDIUM)
    val studyFontSize: StateFlow<StudyFontSize> = _studyFontSize.asStateFlow()

    private val _useWhiteBackground = MutableStateFlow(false)
    val useWhiteBackground: StateFlow<Boolean> = _useWhiteBackground.asStateFlow()

    // "" = not yet set (auto-detect); "SHIUR" or "STUDY" = explicit user preference
    private val _tabletRightPanelMode = MutableStateFlow("")
    val tabletRightPanelMode: StateFlow<String> = _tabletRightPanelMode.asStateFlow()

    // "" = not yet loaded; "NONE"|"LEFT"|"RIGHT" = persisted collapse state
    private val _tabletCollapsedSide = MutableStateFlow("")
    val tabletCollapsedSide: StateFlow<String> = _tabletCollapsedSide.asStateFlow()
    // -1.0 = not yet loaded; otherwise left-panel width in dp
    private val _tabletSplitDp = MutableStateFlow(-1.0)
    val tabletSplitDp: StateFlow<Double> = _tabletSplitDp.asStateFlow()

    private val _isFetchingDafYomi = MutableStateFlow(false)
    val isFetchingDafYomi: StateFlow<Boolean> = _isFetchingDafYomi.asStateFlow()

    private val _dafYomiError = MutableStateFlow<String?>(null)
    val dafYomiError: StateFlow<String?> = _dafYomiError.asStateFlow()

    val tractate get() = allTractates[_selectedTractateIndex.value]

    init {
        viewModelScope.launch {
            _selectedTractateIndex.value = AppPreferences.lastTractateIndex.first()
            _selectedDaf.value = AppPreferences.lastDaf.first()  // now Double
            _selectedAmud.value = AppPreferences.lastAmud.first()
            _quizMode.value = AppPreferences.quizMode.first()
            _sourceDisplayMode.value = AppPreferences.sourceDisplayMode.first()
            _shiurShowSources.value = AppPreferences.shiurShowSources.first()
            _studyFontSize.value = AppPreferences.studyFontSize.first()
            _useWhiteBackground.value = AppPreferences.useWhiteBackground.first()
            _tabletRightPanelMode.value = AppPreferences.tabletRightPanel.first()
            _tabletCollapsedSide.value = AppPreferences.tabletCollapsedSide.first()
            _tabletSplitDp.value = AppPreferences.tabletSplitDp.first()
            persistedEngagementSeconds = AppPreferences.totalEngagementSeconds.first()
        }
        FeedManager.init()
        viewModelScope.launch { FeedManager.refreshIfNeeded() }
    }

    fun selectTractate(index: Int) {
        _selectedTractateIndex.value = index
        _selectedDaf.value = allTractates[index].startDaf.toDouble()
        _selectedAmud.value = allTractates[index].startAmud
        saveSelection()
    }

    fun selectDaf(daf: Double) {
        _selectedDaf.value = daf
        val isHalf = daf % 1.0 != 0.0
        _selectedAmud.value = when {
            isHalf -> 1  // half-daf entries are always b-side
            daf == tractate.startDaf.toDouble() -> tractate.startAmud
            else -> 0
        }
        saveSelection()
    }

    fun selectAmud(amud: Int) {
        _selectedAmud.value = amud
        saveSelection()
    }

    fun selectQuizMode(mode: QuizMode) {
        _quizMode.value = mode
        viewModelScope.launch { AppPreferences.saveQuizMode(mode) }
    }

    fun selectStudyMode(mode: StudyMode) {
        _studyMode.value = mode
    }

    fun selectSourceDisplayMode(mode: SourceDisplayMode) {
        _sourceDisplayMode.value = mode
        viewModelScope.launch { AppPreferences.saveSourceDisplayMode(mode) }
    }

    fun setShiurShowSources(enabled: Boolean) {
        _shiurShowSources.value = enabled
        viewModelScope.launch { AppPreferences.saveShiurShowSources(enabled) }
    }

    fun setStudyFontSize(size: StudyFontSize) {
        _studyFontSize.value = size
        viewModelScope.launch { AppPreferences.saveStudyFontSize(size) }
    }

    fun setUseWhiteBackground(enabled: Boolean) {
        _useWhiteBackground.value = enabled
        viewModelScope.launch { AppPreferences.saveUseWhiteBackground(enabled) }
    }

    fun setTabletRightPanelMode(mode: String) {
        _tabletRightPanelMode.value = mode
        viewModelScope.launch { AppPreferences.saveTabletRightPanel(mode) }
    }

    fun saveTabletLayout(collapsedSide: String, splitDp: Double) {
        _tabletCollapsedSide.value = collapsedSide
        _tabletSplitDp.value = splitDp
        viewModelScope.launch { AppPreferences.saveTabletLayout(collapsedSide, splitDp) }
    }

    fun fetchTodaysDaf() {
        _isFetchingDafYomi.value = true
        _dafYomiError.value = null
        viewModelScope.launch {
            try {
                val dafYomi = DafYomiService.fetchToday()
                _selectedTractateIndex.value = dafYomi.tractateIndex
                _selectedDaf.value = dafYomi.daf.toDouble()
                _selectedAmud.value = 0
                saveSelection()
            } catch (e: Exception) {
                _dafYomiError.value = e.message ?: "Could not fetch today's Daf Yomi"
            } finally {
                _isFetchingDafYomi.value = false
            }
        }
    }

    fun clearDafYomiError() { _dafYomiError.value = null }

    fun onAppForegrounded() {
        sessionStartMs = System.currentTimeMillis()
        if (!nudgeCheckedThisSession) {
            nudgeCheckedThisSession = true
            checkDonationNudge()
        }
    }

    fun onAppBackgrounded() {
        val start = sessionStartMs ?: return
        val sessionSeconds = (System.currentTimeMillis() - start) / 1000
        persistedEngagementSeconds += sessionSeconds
        sessionStartMs = null
        nudgeCheckedThisSession = false
        viewModelScope.launch {
            AppPreferences.saveEngagementSeconds(persistedEngagementSeconds)
        }
    }

    fun dismissDonationNudge() {
        _showDonationNudge.value = false
        viewModelScope.launch {
            AppPreferences.saveDonationNudgeTimestamp(System.currentTimeMillis())
        }
    }

    private fun checkDonationNudge() {
        viewModelScope.launch {
            if (persistedEngagementSeconds >= ENGAGEMENT_NUDGE_THRESHOLD_SECONDS) {
                val lastNudgeMs = AppPreferences.lastDonationNudgeTimestamp.first()
                if (System.currentTimeMillis() - lastNudgeMs >= NUDGE_MIN_INTERVAL_MS) {
                    _showDonationNudge.value = true
                }
            }
        }
    }

    private fun saveSelection() {
        viewModelScope.launch {
            AppPreferences.saveLastSelection(
                tractateIndex = _selectedTractateIndex.value,
                daf = _selectedDaf.value,
                amud = _selectedAmud.value
            )
        }
    }
}
