package com.anydaf.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.AnyDafApp
import com.anydaf.data.api.Dedication
import com.anydaf.data.api.DafYomiService
import com.anydaf.data.api.DedicationService
import com.anydaf.data.api.FeedManager
import com.anydaf.data.prefs.AppPreferences
import com.anydaf.model.QuizMode
import com.anydaf.model.StudyFontSize
import com.anydaf.model.StudyMode
import com.anydaf.model.TextDisplayMode
import com.anydaf.model.allTractates
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

private const val REGULAR_ENGAGEMENT_HOURS = 20.0
private const val REGULAR_INTERVAL_DAYS    = 30.0
private const val DONOR_ENGAGEMENT_HOURS   = 60.0
private const val DONOR_INTERVAL_DAYS      = 90.0

class ContentViewModel : ViewModel() {

    private val _showDonationNudge = MutableStateFlow(false)
    val showDonationNudge: StateFlow<Boolean> = _showDonationNudge.asStateFlow()

    private val _dedication = MutableStateFlow<Dedication?>(null)
    val dedication: StateFlow<Dedication?> = _dedication.asStateFlow()

    private var sessionStartMs: Long? = null
    private var nudgeCheckedThisSession = false
    private var persistedEngagementSeconds = 0L
    private var engagementSecondsAtLastNudge = 0L
    private var didClickDonate = false

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

    private val _textDisplayMode = MutableStateFlow(TextDisplayMode.TRANSLATION)
    val textDisplayMode: StateFlow<TextDisplayMode> = _textDisplayMode.asStateFlow()

    private val _shiurShowSources = MutableStateFlow(true)
    val shiurShowSources: StateFlow<Boolean> = _shiurShowSources.asStateFlow()

    private val _studyFontSize = MutableStateFlow(StudyFontSize.MEDIUM)
    val studyFontSize: StateFlow<StudyFontSize> = _studyFontSize.asStateFlow()

    private val _printFontSize = MutableStateFlow(StudyFontSize.SMALL)
    val printFontSize: StateFlow<StudyFontSize> = _printFontSize.asStateFlow()

    private val _printLineSpacing = MutableStateFlow(1.5)
    val printLineSpacing: StateFlow<Double> = _printLineSpacing.asStateFlow()

    private val _useWhiteBackground = MutableStateFlow(false)
    val useWhiteBackground: StateFlow<Boolean> = _useWhiteBackground.asStateFlow()

    // "" = not yet loaded (composable defaults to DAF); "DAF"|"TEXT"|"SHIUR" = persisted mode
    private val _lastContentMode = MutableStateFlow("")
    val lastContentMode: StateFlow<String> = _lastContentMode.asStateFlow()

    // In-memory mode — survives navigation back from Settings without waiting for DataStore.
    val currentContentMode = MutableStateFlow("")

    private val _lastTextSectionIndex = MutableStateFlow(0)
    val lastTextSectionIndex: StateFlow<Int> = _lastTextSectionIndex.asStateFlow()
    private val _lastTextTractate = MutableStateFlow("")
    val lastTextTractate: StateFlow<String> = _lastTextTractate.asStateFlow()
    private val _lastTextDaf = MutableStateFlow(0.0)
    val lastTextDaf: StateFlow<Double> = _lastTextDaf.asStateFlow()

    private val _lastShiurSegmentIndex = MutableStateFlow(0)
    val lastShiurSegmentIndex: StateFlow<Int> = _lastShiurSegmentIndex.asStateFlow()
    private val _lastShiurTractate = MutableStateFlow("")
    val lastShiurTractate: StateFlow<String> = _lastShiurTractate.asStateFlow()
    private val _lastShiurDaf = MutableStateFlow(0.0)
    val lastShiurDaf: StateFlow<Double> = _lastShiurDaf.asStateFlow()

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

    private val _hasAcceptedTerms = MutableStateFlow(false)
    val hasAcceptedTerms: StateFlow<Boolean> = _hasAcceptedTerms.asStateFlow()

    val tractate get() = allTractates[_selectedTractateIndex.value]

    init {
        viewModelScope.launch {
            _selectedTractateIndex.value = AppPreferences.lastTractateIndex.first()
            _selectedDaf.value = AppPreferences.lastDaf.first()  // now Double
            _selectedAmud.value = AppPreferences.lastAmud.first()
            _quizMode.value = AppPreferences.quizMode.first()
            _textDisplayMode.value = AppPreferences.textDisplayMode.first()
            _shiurShowSources.value = AppPreferences.shiurShowSources.first()
            _studyFontSize.value = AppPreferences.studyFontSize.first()
            _printFontSize.value = AppPreferences.printFontSize.first()
            _printLineSpacing.value = AppPreferences.printLineSpacing.first()
            _useWhiteBackground.value = AppPreferences.useWhiteBackground.first()
            _lastContentMode.value = AppPreferences.lastContentMode.first()
            _lastTextSectionIndex.value = AppPreferences.lastTextSectionIndex.first()
            _lastTextTractate.value = AppPreferences.lastTextTractate.first()
            _lastTextDaf.value = AppPreferences.lastTextDaf.first()
            _lastShiurSegmentIndex.value = AppPreferences.lastShiurSegmentIndex.first()
            _lastShiurTractate.value = AppPreferences.lastShiurTractate.first()
            _lastShiurDaf.value = AppPreferences.lastShiurDaf.first()
            _tabletRightPanelMode.value = AppPreferences.tabletRightPanel.first()
            _tabletCollapsedSide.value = AppPreferences.tabletCollapsedSide.first()
            _tabletSplitDp.value = AppPreferences.tabletSplitDp.first()
            persistedEngagementSeconds = AppPreferences.totalEngagementSeconds.first()
            engagementSecondsAtLastNudge = AppPreferences.engagementSecondsAtLastNudge.first()
            didClickDonate = AppPreferences.didClickDonate.first()
            _hasAcceptedTerms.value = AppPreferences.hasAcceptedTerms.first()
        }
        FeedManager.init()
        viewModelScope.launch { FeedManager.refreshIfNeeded() }
        viewModelScope.launch {
            val lastShown = AppPreferences.lastDedicationDateShown.first()
            val today = java.time.LocalDate.now().toString()
            if (today != lastShown) {
                val ded = DedicationService.fetch()
                if (ded != null) {
                    _dedication.value = ded
                    AppPreferences.saveLastDedicationDateShown(today)  // only mark when found
                }
                // If null, don't mark — we'll check again on the next open.
            }
        }
    }

    fun dismissDedication() {
        _dedication.value = null
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

    fun saveContentMode(mode: String) {
        viewModelScope.launch { AppPreferences.saveLastContentMode(mode) }
    }

    fun saveTextPosition(tractate: String, daf: Double, sectionIndex: Int) {
        viewModelScope.launch { AppPreferences.saveLastTextPosition(tractate, daf, sectionIndex) }
    }

    fun saveShiurPosition(tractate: String, daf: Double, segmentIndex: Int) {
        viewModelScope.launch { AppPreferences.saveLastShiurPosition(tractate, daf, segmentIndex) }
    }

    fun selectQuizMode(mode: QuizMode) {
        _quizMode.value = mode
        viewModelScope.launch { AppPreferences.saveQuizMode(mode) }
    }

    fun selectStudyMode(mode: StudyMode) {
        _studyMode.value = mode
    }

    fun selectTextDisplayMode(mode: TextDisplayMode) {
        _textDisplayMode.value = mode
        viewModelScope.launch { AppPreferences.saveTextDisplayMode(mode) }
    }

    fun setShiurShowSources(enabled: Boolean) {
        _shiurShowSources.value = enabled
        viewModelScope.launch { AppPreferences.saveShiurShowSources(enabled) }
    }

    fun setStudyFontSize(size: StudyFontSize) {
        _studyFontSize.value = size
        viewModelScope.launch { AppPreferences.saveStudyFontSize(size) }
    }

    fun setPrintFontSize(size: StudyFontSize) {
        _printFontSize.value = size
        viewModelScope.launch { AppPreferences.savePrintFontSize(size) }
    }

    fun setPrintLineSpacing(spacing: Double) {
        _printLineSpacing.value = spacing
        viewModelScope.launch { AppPreferences.savePrintLineSpacing(spacing) }
    }

    fun setUseWhiteBackground(enabled: Boolean) {
        _useWhiteBackground.value = enabled
        viewModelScope.launch { AppPreferences.saveUseWhiteBackground(enabled) }
    }

    fun acceptTerms() {
        _hasAcceptedTerms.value = true
        viewModelScope.launch { AppPreferences.saveHasAcceptedTerms(true) }
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
        val snapshotSeconds = persistedEngagementSeconds
        engagementSecondsAtLastNudge = snapshotSeconds
        viewModelScope.launch {
            AppPreferences.saveDonationNudgeTimestamp(System.currentTimeMillis())
            AppPreferences.saveEngagementSecondsAtLastNudge(snapshotSeconds)
        }
    }

    fun recordDonateClicked() {
        didClickDonate = true
        viewModelScope.launch { AppPreferences.saveDidClickDonate(true) }
    }

    private fun checkDonationNudge() {
        viewModelScope.launch {
            val hoursThreshold = if (didClickDonate) DONOR_ENGAGEMENT_HOURS else REGULAR_ENGAGEMENT_HOURS
            val daysThreshold  = if (didClickDonate) DONOR_INTERVAL_DAYS   else REGULAR_INTERVAL_DAYS
            val hoursSinceLastNudge = (persistedEngagementSeconds - engagementSecondsAtLastNudge) / 3600.0
            val lastNudgeMs = AppPreferences.lastDonationNudgeTimestamp.first()
            val shouldShow = if (lastNudgeMs == 0L) {
                hoursSinceLastNudge >= hoursThreshold
            } else {
                val daysSinceLastNudge = (System.currentTimeMillis() - lastNudgeMs) / 86_400_000.0
                hoursSinceLastNudge >= hoursThreshold || daysSinceLastNudge >= daysThreshold
            }
            if (shouldShow) _showDonationNudge.value = true
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
