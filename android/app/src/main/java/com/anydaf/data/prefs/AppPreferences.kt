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
import com.anydaf.model.SourceDisplayMode
import com.anydaf.model.StudyFontSize
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
    private val LAST_TRACTATE_INDEX = intPreferencesKey("lastTractateIndex")
    private val LAST_DAF = NEW_LAST_DAF_DOUBLE
    private val LAST_AMUD = intPreferencesKey("lastAmud")
    private val QUIZ_MODE = stringPreferencesKey("quizMode")
    private val SOURCE_DISPLAY_MODE = stringPreferencesKey("sourceDisplayMode")
    private val SHIUR_SHOW_SOURCES = booleanPreferencesKey("shiurShowSources")
    private val STUDY_FONT_SIZE = stringPreferencesKey("studyFontSize")
    val totalEngagementSeconds: Flow<Long> = store.data.map { it[TOTAL_ENGAGEMENT_SECONDS] ?: 0L }
    val lastDonationNudgeTimestamp: Flow<Long> = store.data.map { it[LAST_DONATION_NUDGE_TIMESTAMP] ?: 0L }
    val lastTractateIndex: Flow<Int> = store.data.map { it[LAST_TRACTATE_INDEX] ?: 0 }
    val lastDaf: Flow<Double> = store.data.map { it[LAST_DAF] ?: 2.0 }
    val lastAmud: Flow<Int> = store.data.map { it[LAST_AMUD] ?: 0 }
    val quizMode: Flow<QuizMode> = store.data.map {
        QuizMode.entries.firstOrNull { m -> m.name == it[QUIZ_MODE] } ?: QuizMode.MULTIPLE_CHOICE
    }
    val sourceDisplayMode: Flow<SourceDisplayMode> = store.data.map {
        SourceDisplayMode.entries.firstOrNull { m -> m.name == it[SOURCE_DISPLAY_MODE] } ?: SourceDisplayMode.TOGGLE
    }
    val shiurShowSources: Flow<Boolean> = store.data.map { it[SHIUR_SHOW_SOURCES] ?: true }
    val studyFontSize: Flow<StudyFontSize> = store.data.map {
        StudyFontSize.entries.firstOrNull { f -> f.name == it[STUDY_FONT_SIZE] } ?: StudyFontSize.MEDIUM
    }
    suspend fun saveEngagementSeconds(seconds: Long) {
        store.edit { it[TOTAL_ENGAGEMENT_SECONDS] = seconds }
    }

    suspend fun saveDonationNudgeTimestamp(timestamp: Long) {
        store.edit { it[LAST_DONATION_NUDGE_TIMESTAMP] = timestamp }
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

    suspend fun saveSourceDisplayMode(mode: SourceDisplayMode) {
        store.edit { it[SOURCE_DISPLAY_MODE] = mode.name }
    }

    suspend fun saveShiurShowSources(enabled: Boolean) {
        store.edit { it[SHIUR_SHOW_SOURCES] = enabled }
    }

    suspend fun saveStudyFontSize(size: StudyFontSize) {
        store.edit { it[STUDY_FONT_SIZE] = size.name }
    }

}
