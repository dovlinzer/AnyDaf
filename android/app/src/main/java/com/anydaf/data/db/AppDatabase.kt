package com.anydaf.data.db

import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.anydaf.AnyDafApp

@Database(entities = [BookmarkEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun bookmarkDao(): BookmarkDao

    companion object {
        @Volatile private var instance: AppDatabase? = null

        fun get(): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                AnyDafApp.context,
                AppDatabase::class.java,
                "anydaf.db"
            ).build().also { instance = it }
        }
    }
}
