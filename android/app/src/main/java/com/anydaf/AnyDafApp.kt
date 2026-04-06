package com.anydaf

import android.app.Application
import android.content.Context
import com.anydaf.data.ResourcesDiskCache
import com.anydaf.data.api.FeedManager
import com.anydaf.data.api.TalmudPageManager

class AnyDafApp : Application() {

    companion object {
        lateinit var instance: AnyDafApp
            private set

        val context: Context get() = instance.applicationContext
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        TalmudPageManager.init()
        FeedManager.init()
        ResourcesDiskCache.evictExpired(applicationContext)
    }
}
