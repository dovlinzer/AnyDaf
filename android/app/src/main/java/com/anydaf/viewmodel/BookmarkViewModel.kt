package com.anydaf.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.anydaf.data.db.AppDatabase
import com.anydaf.data.db.BookmarkEntity
import com.anydaf.model.Bookmark
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class BookmarkViewModel : ViewModel() {

    private val dao = AppDatabase.get().bookmarkDao()

    val bookmarks: StateFlow<List<Bookmark>> = dao.observeAll()
        .map { entities -> entities.map { it.toBookmark() } }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    fun add(bookmark: Bookmark) {
        viewModelScope.launch { dao.insert(BookmarkEntity.from(bookmark)) }
    }

    fun delete(bookmark: Bookmark) {
        viewModelScope.launch { dao.deleteById(bookmark.id.toString()) }
    }

    fun update(bookmark: Bookmark) {
        viewModelScope.launch { dao.update(BookmarkEntity.from(bookmark)) }
    }

    fun isBookmarked(tractateIndex: Int, daf: Double, amud: Int): Boolean =
        bookmarks.value.any { it.tractateIndex == tractateIndex && it.daf == daf && it.amud == amud }

    fun existing(tractateIndex: Int, daf: Double, amud: Int): Bookmark? =
        bookmarks.value.firstOrNull { it.tractateIndex == tractateIndex && it.daf == daf && it.amud == amud }
}
