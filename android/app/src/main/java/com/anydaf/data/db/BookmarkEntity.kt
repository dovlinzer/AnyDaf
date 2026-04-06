package com.anydaf.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.anydaf.model.Bookmark
import java.util.Date
import java.util.UUID

@Entity(tableName = "bookmarks")
data class BookmarkEntity(
    @PrimaryKey val id: String,
    val name: String,
    val notes: String,
    val tractateIndex: Int,
    val daf: Int,
    val amud: Int,
    val studySectionIndex: Int?,
    val createdAt: Long  // epoch millis
) {
    fun toBookmark() = Bookmark(
        id = UUID.fromString(id),
        name = name,
        notes = notes,
        tractateIndex = tractateIndex,
        daf = daf,
        amud = amud,
        studySectionIndex = studySectionIndex,
        createdAt = Date(createdAt)
    )

    companion object {
        fun from(bookmark: Bookmark) = BookmarkEntity(
            id = bookmark.id.toString(),
            name = bookmark.name,
            notes = bookmark.notes,
            tractateIndex = bookmark.tractateIndex,
            daf = bookmark.daf,
            amud = bookmark.amud,
            studySectionIndex = bookmark.studySectionIndex,
            createdAt = bookmark.createdAt.time
        )
    }
}
