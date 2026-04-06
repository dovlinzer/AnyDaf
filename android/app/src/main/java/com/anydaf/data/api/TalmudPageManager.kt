package com.anydaf.data.api

import com.anydaf.AnyDafApp
import org.json.JSONObject

/**
 * Loads pages.json from the app's assets and vends Google Drive thumbnail URLs
 * for each daf amud (side). Mirrors iOS TalmudPageManager.swift.
 *
 * pages.json format:
 *   { "Berakhot": { "0": "DRIVE_FILE_ID", "1": "DRIVE_FILE_ID", … }, … }
 *
 * Page number ↔ daf conversion:
 *   pageNumber = (daf - 1) × 2 + (0 if sideA, 1 if sideB)
 */
object TalmudPageManager {

    // [tractate: [pageNumber: driveFileId]]
    private var pages: Map<String, Map<String, String>> = emptyMap()
    private var loaded = false

    fun init() {
        if (loaded) return
        loaded = true
        try {
            val json = AnyDafApp.context.assets.open("pages.json")
                .bufferedReader().use { it.readText() }
            val root = JSONObject(json)
            val result = mutableMapOf<String, Map<String, String>>()
            for (tractate in root.keys()) {
                val dafObj = root.getJSONObject(tractate)
                val dafMap = mutableMapOf<String, String>()
                for (pageNum in dafObj.keys()) {
                    dafMap[pageNum] = dafObj.getString(pageNum)
                }
                result[tractate] = dafMap
            }
            pages = result
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    /** Whether any page images are available for the given tractate. */
    fun hasPages(tractate: String): Boolean {
        if (!loaded) init()
        return !(pages[tractate]?.isEmpty() ?: true)
    }

    /**
     * Returns a Google Drive thumbnail URL for the given daf amud, or null if not found.
     * @param tractate  e.g. "Berakhot"
     * @param daf       e.g. 11
     * @param sideA     true for amud aleph (a), false for amud bet (b)
     */
    fun imageUrl(tractate: String, daf: Int, sideA: Boolean): String? {
        if (!loaded) init()
        val pageNumber = (daf - 1) * 2 + (if (sideA) 0 else 1)
        val fileId = pages[tractate]?.get(pageNumber.toString()) ?: return null
        return "https://drive.google.com/thumbnail?id=$fileId&sz=w1200"
    }
}
