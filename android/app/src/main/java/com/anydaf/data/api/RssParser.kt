package com.anydaf.data.api

import android.util.Xml
import com.anydaf.model.allTractates
import org.xmlpull.v1.XmlPullParser
import java.io.StringReader

data class ParsedItem(
    val tractate: String?,
    val daf: Int?,
    val audioUrl: String
)

private val feedToCanonical = mapOf(
    "eruvin"        to "Eiruvin",
    "menahot"       to "Menachot",
    "zevachim"      to "Zevachim",
    "zevahim"       to "Zevachim",
    "taanit"        to "Ta\u2019anit",
    "meilah"        to "Meilah",
    "berachot"      to "Berakhot",
    "berachos"      to "Berakhot",
    "brachot"       to "Berakhot",
    "shabbos"       to "Shabbat",
    "kesubos"       to "Ketubot",
    "shevuos"       to "Shevuot",
    "moed katan"    to "Moed Katan",
    "avodah zarah"  to "Avodah Zarah",
    "avoda zara"    to "Avodah Zarah",
    "megilah"       to "Megillah",
    "rosh hashana"  to "Rosh Hashanah",
    "rosh hashanah" to "Rosh Hashanah",
    "bava kama"     to "Bava Kamma",
    "bava metzia"   to "Bava Metzia",
    "bava batra"    to "Bava Batra",
    "middos"        to "Middot",
    "middoth"       to "Middot",
)

fun canonicalTractate(feedName: String): String? {
    val lower = feedName.lowercase().replace("'", "").trim()
    feedToCanonical[lower]?.let { return it }
    return allTractates.firstOrNull {
        it.name.lowercase().replace("'", "").replace("\u2019", "") == lower
    }?.name
}

class RssParser(private val xmlData: String) {
    val items = mutableListOf<ParsedItem>()
    var nextPageUrl: String? = null

    fun parse() {
        val parser = Xml.newPullParser()
        parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, true)
        parser.setInput(StringReader(xmlData))

        var inItem = false
        var inTitle = false
        var currentTitle = StringBuilder()
        var currentAudioUrl = ""

        var eventType = parser.eventType
        while (eventType != XmlPullParser.END_DOCUMENT) {
            when (eventType) {
                XmlPullParser.START_TAG -> {
                    val name = parser.name ?: ""
                    val qName = "${parser.prefix ?: ""}${if (parser.prefix != null) ":" else ""}$name"
                    when {
                        name == "item" -> {
                            inItem = true
                            currentTitle = StringBuilder()
                            currentAudioUrl = ""
                        }
                        name == "title" && inItem -> inTitle = true
                        name == "enclosure" && inItem -> {
                            for (i in 0 until parser.attributeCount) {
                                if (parser.getAttributeName(i) == "url") {
                                    currentAudioUrl = parser.getAttributeValue(i)
                                }
                            }
                        }
                        (name == "link" || qName.endsWith(":link")) && !inItem -> {
                            var rel = ""
                            var href = ""
                            for (i in 0 until parser.attributeCount) {
                                when (parser.getAttributeName(i)) {
                                    "rel" -> rel = parser.getAttributeValue(i)
                                    "href" -> href = parser.getAttributeValue(i)
                                }
                            }
                            if (rel == "next" && href.isNotEmpty()) nextPageUrl = href
                        }
                    }
                }
                XmlPullParser.TEXT -> {
                    if (inTitle) currentTitle.append(parser.text)
                }
                XmlPullParser.END_TAG -> {
                    when (parser.name) {
                        "item" -> {
                            inItem = false
                            val parsed = parseTitle(currentTitle.toString())
                            items.add(ParsedItem(parsed?.first, parsed?.second, currentAudioUrl))
                        }
                        "title" -> inTitle = false
                    }
                }
            }
            eventType = parser.next()
        }
    }

    private fun parseTitle(title: String): Pair<String, Int>? {
        val cleaned = title.replace(Regex("""\s*\(\d+\)\s*$"""), "").trim()
        val parts = cleaned.split(" ")
        if (parts.size < 2) return null

        val dafStr = parts.last()
        val daf = dafStr.takeWhile { it.isDigit() }.toIntOrNull() ?: return null
        if (daf <= 0) return null

        val feedName = parts.dropLast(1).joinToString(" ")
        val canonical = canonicalTractate(feedName) ?: return null
        return canonical to daf
    }
}
