package com.anydaf

import android.app.Application
import android.content.Context
import com.anydaf.data.ResourcesDiskCache
import com.anydaf.data.api.FeedManager
import com.anydaf.data.api.TalmudPageManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class AnyDafApp : Application() {

    companion object {
        lateinit var instance: AnyDafApp
            private set

        val context: Context get() = instance.applicationContext
    }

    override fun onCreate() {
        super.onCreate()
        instance = this

        // All three calls do disk I/O (JSON parsing). Running them on the main thread
        // blocks the first Compose frame from rendering, keeping the system splash screen
        // visible for 10+ seconds on slower devices. Moving to IO thread lets the app
        // reach its first frame immediately. Each manager handles the not-yet-loaded
        // state gracefully via StateFlow defaults / lazy-init guards.
        CoroutineScope(Dispatchers.IO).launch {
            TalmudPageManager.init()
            FeedManager.init()
            ResourcesDiskCache.evictExpired(applicationContext)
        }
    }
}
