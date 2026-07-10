package com.anydaf.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.doublePreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.datastore.core.DataMigration
import com.anydaf.AnyDafApp
import com.anydaf.model.QuizMode
import com.anydaf.model.StudyFontSize
import com.anydaf.model.TextDisplayMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

// Migration: "lastDaf" was stored as Int in v1; renamed to "lastDafDouble" (Double) for half-daf support.
private val LEGACY_LAST_DAF_INT = intPreferencesKey("lastDaf")
private val NEW_LAST_DAF_DOUBLE = doublePreferencesKey("lastDafDouble")

private val lastDafMigration = object : DataMigration<Preferences> {
    override suspend fun shouldMigrate(currentData: Preferences): Boolean =
        currentData[LEGACY_LAST_DAF_INT] != null

    override suspend fun migrate(currentData: Preferences): Preferences =
        currentData.toMutablePreferences().apply {
            this[NEW_LAST_DAF_DOUBLE] = (currentData[LEGACY_LAST_DAF_INT] ?: 2).toDouble()
            remove(LEGACY_LAST_DAF_INT)
        }.toPreferences()

    override suspend fun cleanUp() {}
}

private val Context.dataStore by preferencesDataStore(
    name = "anydaf_prefs",
    produceMigrations = { listOf(lastDafMigration) }
)

object AppPreferences {

    private val store get() = AnyDafApp.context.dataStore

    private val TOTAL_ENGAGEMENT_SECONDS = longPreferencesKey("totalEngagementSeconds")
    private val LAST_DONATION_NUDGE_TIMESTAMP = longPreferencesKey("lastDonationNudgeTimestamp")
    private val ENGAGEMENT_SECONDS_AT_LAST_NUDGE = longPreferencesKey("engagementSecondsAtLastNudge")
    private val DID_CLICK_DONATE = booleanPreferencesKey("didClickDonate")
    private val HAS_ACCEPTED_TERMS = booleanPreferencesKey("hasAcceptedTerms")
    private val LAST_TRACTATE_INDEX = intPreferencesKey("lastTractateIndex")
    private val LAST_DAF = NEW_LAST_DAF_DOUBLE
    private val LAST_AMUD = intPreferencesKey("lastAmud")
    private val QUIZ_MODE = stringPreferencesKey("quizMode")
    private val TEXT_DISPLAY_MODE = stringPreferencesKey("textDisplayMode")
    private val SHIUR_SHOW_SOURCES = booleanPreferencesKey("shiurShowSources")
    private val STUDY_FONT_SIZE = stringPreferencesKey("studyFontSize")
    private val USE_WHITE_BACKGROUND = booleanPreferencesKey("useWhiteBackground")
    private val TABLET_RIGHT_PANEL = stringPreferencesKey("tabletRightPanel")
    private val TABLET_COLLAPSED_SIDE = stringPreferencesKey("tabletCollapsedSide")
    private val TABLET_SPLIT_DP = doublePreferencesKey("tabletSplitDp")
    private val PRINT_FONT_SIZE = stringPreferencesKey("printFontSize")
    private val PRINT_LINE_SPACING = doublePreferencesKey("printLineSpacing")
    private val LAST_CONTENT_MODE = stringPreferencesKey("lastContentMode")
    private val LAST_TEXT_SECTION_INDEX = intPreferencesKey("lastTextSectionIndex")
    private val LAST_TEXT_TRACTATE = stringPreferencesKey("lastTextTractate")
    private val LAST_TEXT_DAF = doublePreferencesKey("lastTextDaf")
    private val LAST_SHIUR_SEGMENT_INDEX = intPreferencesKey("lastShiurSegmentIndex")
    private val LAST_SHIUR_TRACTATE = stringPreferencesKey("lastShiurTractate")
    private val LAST_SHIUR_DAF = doublePreferencesKey("lastShiurDaf")
    private val LAST_DEDICATION_DATE_SHOWN = stringPreferencesKey("lastDedicationDateShown")
    val totalEngagementSeconds: Flow<Long> = store.data.map { it[TOTAL_ENGAGEMENT_SECONDS] ?: 0L }
    val lastDonationNudgeTimestamp: Flow<Long> = store.data.map { it[LAST_DONATION_NUDGE_TIMESTAMP] ?: 0L }
    val engagementSecondsAtLastNudge: Flow<Long> = store.data.map { it[ENGAGEMENT_SECONDS_AT_LAST_NUDGE] ?: 0L }
    val didClickDonate: Flow<Boolean> = store.data.map { it[DID_CLICK_DONATE] ?: false }
    val hasAcceptedTerms: Flow<Boolean> = store.data.map { it[HAS_ACCEPTED_TERMS] ?: false }
    val lastTractateIndex: Flow<Int> = store.data.map { it[LAST_TRACTATE_INDEX] ?: 0 }
    val lastDaf: Flow<Double> = store.data.map { it[LAST_DAF] ?: 2.0 }
    val lastAmud: Flow<Int> = store.data.map { it[LAST_AMUD] ?: 0 }
    val quizMode: Flow<QuizMode> = store.data.map {
        QuizMode.entries.firstOrNull { m -> m.name == it[QUIZ_MODE] } ?: QuizMode.MULTIPLE_CHOICE
    }
    val textDisplayMode: Flow<TextDisplayMode> = store.data.map {
        TextDisplayMode.entries.firstOrNull { m -> m.name == it[TEXT_DISPLAY_MODE] } ?: TextDisplayMode.TRANSLATION
    }
    val shiurShowSources: Flow<Boolean> = store.data.map { it[SHIUR_SHOW_SOURCES] ?: true }
    val studyFontSize: Flow<StudyFontSize> = store.data.map {
        StudyFontSize.entries.firstOrNull { f -> f.name == it[STUDY_FONT_SIZE] } ?: StudyFontSize.MEDIUM
    }
    val useWhiteBackground: Flow<Boolean> = store.data.map { it[USE_WHITE_BACKGROUND] ?: false }
    // Empty string = never set (auto-detect on first use); "SHIUR" or "STUDY" = explicit preference
    val tabletRightPanel: Flow<String> = store.data.map { it[TABLET_RIGHT_PANEL] ?: "" }
    // Empty string = not yet persisted (composable uses default "NONE"); -1.0 = split dp not yet persisted
    val tabletCollapsedSide: Flow<String> = store.data.map { it[TABLET_COLLAPSED_SIDE] ?: "" }
    val tabletSplitDp: Flow<Double> = store.data.map { it[TABLET_SPLIT_DP] ?: -1.0 }
    val printFontSize: Flow<StudyFontSize> = store.data.map {
        StudyFontSize.entries.firstOrNull { f -> f.name == it[PRINT_FONT_SIZE] } ?: StudyFontSize.SMALL
    }
    val printLineSpacing: Flow<Double> = store.data.map { it[PRINT_LINE_SPACING] ?: 1.5 }
    // "" = not yet persisted (composable defaults to DAF)
    val lastContentMode: Flow<String> = store.data.map { it[LAST_CONTENT_MODE] ?: "" }
    val lastTextSectionIndex: Flow<Int> = store.data.map { it[LAST_TEXT_SECTION_INDEX] ?: 0 }
    val lastTextTractate: Flow<String> = store.data.map { it[LAST_TEXT_TRACTATE] ?: "" }
    val lastTextDaf: Flow<Double> = store.data.map { it[LAST_TEXT_DAF] ?: 0.0 }
    val lastShiurSegmentIndex: Flow<Int> = store.data.map { it[LAST_SHIUR_SEGMENT_INDEX] ?: 0 }
    val lastShiurTractate: Flow<String> = store.data.map { it[LAST_SHIUR_TRACTATE] ?: "" }
    val lastShiurDaf: Flow<Double> = store.data.map { it[LAST_SHIUR_DAF] ?: 0.0 }
    val lastDedicationDateShown: Flow<String> = store.data.map { it[LAST_DEDICATION_DATE_SHOWN] ?: "" }
    suspend fun saveEngagementSeconds(seconds: Long) {
        store.edit { it[TOTAL_ENGAGEMENT_SECONDS] = seconds }
    }

    suspend fun saveDonationNudgeTimestamp(timestamp: Long) {
        store.edit { it[LAST_DONATION_NUDGE_TIMESTAMP] = timestamp }
    }

    suspend fun saveEngagementSecondsAtLastNudge(seconds: Long) {
        store.edit { it[ENGAGEMENT_SECONDS_AT_LAST_NUDGE] = seconds }
    }

    suspend fun saveDidClickDonate(clicked: Boolean) {
        store.edit { it[DID_CLICK_DONATE] = clicked }
    }

    suspend fun saveHasAcceptedTerms(accepted: Boolean) {
        store.edit { it[HAS_ACCEPTED_TERMS] = accepted }
    }

    suspend fun saveLastSelection(tractateIndex: Int, daf: Double, amud: Int) {
        store.edit {
            it[LAST_TRACTATE_INDEX] = tractateIndex
            it[LAST_DAF] = daf
            it[LAST_AMUD] = amud
        }
    }

    suspend fun saveQuizMode(mode: QuizMode) {
        store.edit { it[QUIZ_MODE] = mode.name }
    }

    suspend fun saveTextDisplayMode(mode: TextDisplayMode) {
        store.edit { it[TEXT_DISPLAY_MODE] = mode.name }
    }

    suspend fun saveShiurShowSources(enabled: Boolean) {
        store.edit { it[SHIUR_SHOW_SOURCES] = enabled }
    }

    suspend fun saveStudyFontSize(size: StudyFontSize) {
        store.edit { it[STUDY_FONT_SIZE] = size.name }
    }

    suspend fun saveUseWhiteBackground(enabled: Boolean) {
        store.edit { it[USE_WHITE_BACKGROUND] = enabled }
    }

    suspend fun saveTabletRightPanel(mode: String) {
        store.edit { it[TABLET_RIGHT_PANEL] = mode }
    }

    suspend fun saveTabletLayout(collapsedSide: String, splitDp: Double) {
        store.edit {
            it[TABLET_COLLAPSED_SIDE] = collapsedSide
            it[TABLET_SPLIT_DP] = splitDp
        }
    }

    suspend fun saveLastContentMode(mode: String) {
        store.edit { it[LAST_CONTENT_MODE] = mode }
    }

    suspend fun saveLastTextPosition(tractate: String, daf: Double, sectionIndex: Int) {
        store.edit {
            it[LAST_TEXT_TRACTATE] = tractate
            it[LAST_TEXT_DAF] = daf
            it[LAST_TEXT_SECTION_INDEX] = sectionIndex
        }
    }

    suspend fun saveLastShiurPosition(tractate: String, daf: Double, segmentIndex: Int) {
        store.edit {
            it[LAST_SHIUR_TRACTATE] = tractate
            it[LAST_SHIUR_DAF] = daf
            it[LAST_SHIUR_SEGMENT_INDEX] = segmentIndex
        }
    }

    suspend fun savePrintFontSize(size: StudyFontSize) {
        store.edit { it[PRINT_FONT_SIZE] = size.name }
    }

    suspend fun savePrintLineSpacing(spacing: Double) {
        store.edit { it[PRINT_LINE_SPACING] = spacing }
    }

    suspend fun saveLastDedicationDateShown(date: String) {
        store.edit { it[LAST_DEDICATION_DATE_SHOWN] = date }
    }

}
