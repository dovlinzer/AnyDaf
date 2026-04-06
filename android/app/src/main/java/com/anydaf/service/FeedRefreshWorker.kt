package com.anydaf.service

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.anydaf.data.api.FeedManager

class FeedRefreshWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            FeedManager.fetchAll()
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
