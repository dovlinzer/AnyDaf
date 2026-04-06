package com.anydaf.viewmodel

import androidx.lifecycle.ViewModel
import com.anydaf.data.api.TalmudPageManager

class PdfViewModel : ViewModel() {

    fun hasPages(tractate: String): Boolean = TalmudPageManager.hasPages(tractate)

    fun imageUrl(tractate: String, daf: Int, sideA: Boolean): String? =
        TalmudPageManager.imageUrl(tractate, daf, sideA)
}
