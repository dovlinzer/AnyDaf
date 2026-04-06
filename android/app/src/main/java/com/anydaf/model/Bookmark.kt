package com.anydaf.model

import java.util.Date
import java.util.UUID

data class Bookmark(
    val id: UUID = UUID.randomUUID(),
    var name: String,
    var notes: String = "",
    val tractateIndex: Int,
    val daf: Int,
    val amud: Int,              // 0 = amud a, 1 = amud b
    val studySectionIndex: Int? = null,
    val createdAt: Date = Date()
) {
    val tractate: Tractate get() = allTractates[tractateIndex]
    val amudLabel: String get() = if (amud == 0) "a" else "b"
    val subtitle: String get() = "${tractate.name} Daf $daf$amudLabel"

    fun matches(query: String): Boolean {
        val q = query.lowercase()
        return name.lowercase().contains(q) || notes.lowercase().contains(q)
    }

    companion object {
        fun defaultName(tractateIndex: Int, daf: Int, amud: Int): String {
            val amudLabel = if (amud == 0) "a" else "b"
            return "${allTractates[tractateIndex].name} $daf$amudLabel"
        }
    }
}
