package com.anydaf.data.db

import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.anydaf.AnyDafApp

@Database(entities = [BookmarkEntity::class], version = 2, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun bookmarkDao(): BookmarkDao

    companion object {
        @Volatile private var instance: AppDatabase? = null

        // v1→v2: migrate daf column from INTEGER to REAL to support half-daf (amud b) bookmarks
        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("""
                    CREATE TABLE bookmarks_new (
                        id TEXT NOT NULL PRIMARY KEY,
                        name TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        tractateIndex INTEGER NOT NULL,
                        daf REAL NOT NULL,
                        amud INTEGER NOT NULL,
                        studySectionIndex INTEGER,
                        createdAt INTEGER NOT NULL
                    )
                """.trimIndent())
                db.execSQL("INSERT INTO bookmarks_new SELECT id, name, notes, tractateIndex, CAST(daf AS REAL), amud, studySectionIndex, createdAt FROM bookmarks")
                db.execSQL("DROP TABLE bookmarks")
                db.execSQL("ALTER TABLE bookmarks_new RENAME TO bookmarks")
            }
        }

        fun get(): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                AnyDafApp.context,
                AppDatabase::class.java,
                "anydaf.db"
            ).addMigrations(MIGRATION_1_2).build().also { instance = it }
        }
    }
}
