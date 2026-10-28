package com.anydaf.data.api

/**
 * The author's wording for the English we show (2026-10-28): שוטה is "a person with psychosis",
 * never the William Davidson translation's "imbecile"; an animal that is a shoteh is "disoriented";
 * where the Gemara uses the word as an insult it is "Fool". Davidson's "insane" changes only on a
 * line whose Hebrew has שוטה (Sotah 27a's "insane person" is שעמום). Same rules as iOS's
 * TermFixes (SefariaClient.swift), daf-processor/term_fixes.py and the web renderer's fixTerms.
 */
object TermFixes {
    private const val TAG = "(?:</?(?:b|strong|i|em|big|small)>)"
    private const val SEP = "((?:\\s|$TAG)+)"
    private const val NOUNS = "(man|woman|partner|priest|wife|husband|person|son|daughter|girl|boy|slave)"
    private const val ANIMAL = "a <i>shoteh</i> (disoriented)"
    private val develop = mapOf(
        "went" to "developed", "goes" to "develops", "go" to "develop", "gone" to "developed",
        "had gone" to "had developed", "became" to "developed", "become" to "develop", "becomes" to "develops",
    )

    private class Rule(pattern: String, val make: (List<String>) -> String) {
        val re = Regex(pattern)
    }

    private fun rule(pattern: String, make: (List<String>) -> String) = Rule(pattern, make)
    private fun rule(pattern: String, template: String) = Rule(pattern) { g ->
        var out = template
        for (i in g.size - 1 downTo 1) out = out.replace("$$i", g[i])
        out
    }

    private fun art(a: String) = when (a) { "an" -> "a"; "An" -> "A"; else -> a }

    /** "an imbecile</b> priest" -> "a priest with psychosis</b>": opening tags stay before the noun, closing ones move after. */
    private fun withPsychosis(noun: String, between: String): String {
        val tags = between.replace(Regex("\\s+"), "")
        val opening = tags.replace(Regex("</[^>]+>"), "")
        val closing = tags.replace(Regex("<[^/][^>]*>"), "")
        return opening + noun + " with psychosis" + closing
    }

    private val rules = listOf(
        rule("\\b(ox|animal)((?:\\s|$TAG)+that(?:\\s|$TAG)+(?:is|was)(?:(?:\\s|$TAG)+impaired by being)?(?:\\s|$TAG)+(?:deaf,(?:\\s|$TAG)+)?)an imbecile\\b",
            "$1$2$ANIMAL"),
        rule("\\b([Aa])n imbecile among animals\\b", "$1 <i>shoteh</i> (a disoriented one) among animals"),
        rule("(:\\s*$TAG*)Imbeciles\\b", "$1Fools"),
        rule("(:\\s*$TAG*)Imbecile\\b(?=$TAG*\\s*[,!])", "$1Fool"),
        rule("\\b([Gg])reatest imbecile\\b", "$1reatest fool"),
        rule("\\bcertain imbecile named\\b", "certain fool named"),
        rule("\\b(merely|essentially) an imbecile\\b", "$1 a fool"),
        rule("\\b(became|become)${SEP}imbecilic\\b") { g -> develop.getValue(g[1]) + g[2] + "psychosis" },
        rule("\\b(became|become|becomes)${SEP}an${SEP}imbecile\\b") { g -> develop.getValue(g[1]) + g[2] + "psychosis" },
        rule("\\btimes imbecilic\\b", "times in a state of psychosis"),
        rule("\\b(an|An|the|The|this|This|that|That|a|A)${SEP}imbecil(?:ic|e)$SEP$NOUNS\\b") { g ->
            art(g[1]) + g[2] + withPsychosis(g[4], g[3]) },
        rule("\\bimbecilic$SEP$NOUNS\\b") { g -> withPsychosis(g[2], g[1]) },
        rule("\\(imbecile\\)", "(a person with psychosis)"),
        rule("\\bImbeciles\\b", "People with psychosis"),
        rule("\\bimbeciles\\b", "people with psychosis"),
        rule("\\b(an|An)${SEP}imbecile\\b") { g -> art(g[1]) + g[2] + "person with psychosis" },
        rule("\\bImbecile\\b", "Person with psychosis"),
        rule("\\bimbecile\\b", "person with psychosis"),
        rule("\\b(is|was|are|were|be|being)${SEP}imbecilic\\b", "$1$2in a state of psychosis"),
        rule("\\bimbecility\\b", "psychosis"),
    )

    private val insaneRules = listOf(
        rule("\\b(went|goes|go|gone|had gone|became|become|becomes)${SEP}insane\\b") { g -> develop.getValue(g[1]) + g[2] + "psychosis" },
        rule("\\b(an|An)${SEP}insane${SEP}person\\b") { g -> art(g[1]) + g[2] + withPsychosis("person", g[3]) },
        rule("\\binsane$SEP(person|people|man|woman)\\b") { g -> withPsychosis(g[2], g[1]) },
        rule("\\b(a|A)${SEP}mentally incompetent$SEP(person|man|woman)\\b") { g -> g[1] + g[2] + withPsychosis(g[4], g[3]) },
        rule("\\bthe mentally incompetent\\b", "people with psychosis"),
        rule("\\b(a|A)${SEP}crazy${SEP}person\\b") { g -> g[1] + g[2] + withPsychosis("person", g[3]) },
        rule("\\bconsidered insane\\b", "considered a person with psychosis"),
        rule("\\bappear insane\\b", "appear to be in a state of psychosis"),
        rule("\\b(is|was|are|were|be|times)${SEP}insane\\b", "$1$2in a state of psychosis"),
        rule("\\binsanity\\b", "psychosis"),
    )

    private val shotehHebrew =
        Regex("(?<![א-ת])[והלבמשכד]{0,3}(שוט(ה|ים|ות|ית)|נשת?טה|נשתטית|נשתטו|שטיא|שוטא|שטותא)(?![א-ת])")

    private fun apply(rules: List<Rule>, text: String) =
        rules.fold(text) { s, r -> r.re.replace(s) { m -> r.make(m.groupValues) } }

    /** Fix one English segment; pass its Hebrew to apply the "insane" rules too. */
    fun fix(english: String, hebrew: String? = null): String {
        var s = english
        if (s.contains("mbecil")) s = apply(rules, s)
        if (hebrew != null) {
            val plain = hebrew.replace(Regex("[\\u0591-\\u05C7]|<[^>]+>"), "")
            if (!plain.contains("שעמ") && shotehHebrew.containsMatchIn(plain)) s = apply(insaneRules, s)
        }
        return s
    }
}
