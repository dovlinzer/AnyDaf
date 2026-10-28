"""Wording we change in every English text we show (author rule, 2026-10-28).

שוטה is "a person with psychosis", never "imbecile". The William Davidson translation says
"imbecile" (~250 times in Shas); Kulp's Mishnah says "an insane person" or "an idiot".
Of an animal it is "a *shoteh* (disoriented)". Where the Gemara uses the word as an insult ("Shoteh, go to the end of the verse!") it is
"fool", since a diagnosis makes no sense there.

The same rules live in AnyDafWeb/renderer/outline-renderer.js (fixTerms), which applies them
when the page shows any text. Keep the two in step.

    fix_terms(text)          -> text   ("imbecile" and its forms, anywhere)
    fix_terms(text, hebrew)  -> text   (also "insane" etc., when the Hebrew has שוטה)
"""
import re

_S = r"(\s+\**|\**\s+|\s+)"          # a space, with or without Sefaria's ** bold markers
_NOUNS = r"(man|woman|partner|priest|wife|husband|person|son|daughter|girl|boy|slave)"

ANIMAL = "a *shoteh* (disoriented)"
RULES = [
    # An animal that is a shoteh (Bava Kamma 52-54, Bekhorot 45b): "disoriented", as in AnyMishnahWeb
    (r"\b(ox|animal)([\s*]+that[\s*]+(?:is|was)(?:[\s*]+impaired by being)?[\s*]+(?:deaf,[\s*]+)?)an imbecile\b", r"\1\2" + ANIMAL),
    (r"\b([Aa])n imbecile among animals\b", r"\1 *shoteh* (a disoriented one) among animals"),
    (r"\(imbecile\)(?=,? or \*katan\* \(minor\) ox)", "(disoriented)"),
    # The Gemara's insults: "Imbecile, go to..." / "Imbeciles, from where..." / "greatest imbecile in the world"
    (r"(:\s*\**)Imbeciles\b", r"\1Fools"),
    (r"(:\s*\**)Imbecile\b(?=\**\s*[,!])", r"\1Fool"),
    (r"\b([Gg])reatest imbecile\b", r"\1reatest fool"),
    (r"\bcertain imbecile named\b", "certain fool named"),
    (r"\b(merely|essentially) an imbecile\b", r"\1 a fool"),
    # becoming one
    (r"\bbecame( \**| )imbecilic\b", r"developed\1psychosis"),
    (r"\bbecome( \**| )imbecilic\b", r"develop\1psychosis"),
    (r"\bbecame( \**| )an( \**| )imbecile\b", r"developed\1psychosis"),
    (r"\bbecome( \**| )an( \**| )imbecile\b", r"develop\1psychosis"),
    (r"\bbecomes( \**| )an( \**| )imbecile\b", r"develops\1psychosis"),
    (r"\btimes imbecilic\b", "times in a state of psychosis"),
    # "an imbecilic woman", "an imbecile priest" -> "a woman with psychosis", "a priest with psychosis"
    (r"\b(an|An|the|The|this|This|that|That|a|A)" + _S + r"imbecil(?:ic|e)" + _S + _NOUNS + r"\b",
     lambda m: _art(m.group(1)) + m.group(2) + m.group(4) + " with psychosis" + ("**" if "*" in m.group(3) else "")),
    (r"\bimbecilic" + _S + _NOUNS + r"\b",
     lambda m: m.group(2) + " with psychosis" + ("**" if "*" in m.group(1) else "")),
    (r"\(imbecile\)", "(a person with psychosis)"),
    # plurals
    (r"\bImbeciles\b", "People with psychosis"),
    (r"\bimbeciles\b", "people with psychosis"),
    # "an imbecile" -> "a person with psychosis"
    (r"\b(an|An)(\s+\**|\**\s+|\s+)imbecile\b", lambda m: _art(m.group(1)) + m.group(2) + "person with psychosis"),
    (r"\bImbecile\b", "Person with psychosis"),
    (r"\bimbecile\b", "person with psychosis"),
    (r"\b(is|was|are|were|be|being)( \**| )imbecilic\b", r"\1\2in a state of psychosis"),
    (r"\bimbecility\b", "psychosis"),
]
_COMPILED = [(re.compile(p), r) for p, r in RULES]

# Davidson also renders שוטה / נשתטה as "insane" or "mentally incompetent", but uses those words for
# other things too, so these apply only to a line whose Hebrew has the root (fix_terms(en, he)).
SHOTEH_HE = re.compile(r"(?<![א-ת])[והלבמשכד]{0,3}(שוט(ה|ים|ות|ית)|נשת?טה|נשתטית|נשתטו|שטיא|שוטא|שטותא)(?![א-ת])")
INSANE_RULES = [
    (r"\b(went|goes|go|gone|had gone|became|become|becomes)(\s+\**|\**\s+|\s+)insane\b",
     lambda m: {"went": "developed", "goes": "develops", "go": "develop", "gone": "developed", "had gone": "had developed",
                "became": "developed", "become": "develop", "becomes": "develops"}[m.group(1)] + m.group(2) + "psychosis"),
    (r"\b(an|An)( \**| )insane( \**| )person\b", lambda m: _art(m.group(1)) + m.group(2) + "person with psychosis" + ("**" if "*" in m.group(3) else "")),
    (r"\binsane( \**| )(person|people|man|woman)\b", lambda m: m.group(2) + " with psychosis" + ("**" if "*" in m.group(1) else "")),
    (r"\b(a|A)" + _S + r"mentally incompetent" + _S + r"(person|man|woman)\b", lambda m: m.group(1) + m.group(2) + m.group(4) + " with psychosis" + ("**" if "*" in m.group(3) else "")),
    (r"\bthe mentally incompetent\b", "people with psychosis"),
    (r"\b(a|A)( \**| )crazy( \**| )person\b", lambda m: m.group(1) + m.group(2) + "person with psychosis" + ("**" if "*" in m.group(3) else "")),
    (r"\bconsidered insane\b", "considered a person with psychosis"),
    (r"\bappear insane\b", "appear to be in a state of psychosis"),
    (r"\b(is|was|are|were|be|times)( \**| )insane\b", r"\1\2in a state of psychosis"),
    (r"\binsanity\b", "psychosis"),
]
_INSANE = [(re.compile(p), r) for p, r in INSANE_RULES]


def _art(a):
    return {"an": "a", "An": "A"}.get(a, a)


def fix_terms(text, hebrew=None):
    if not text:
        return text
    if "mbecil" in text:
        for p, r in _COMPILED:
            text = p.sub(r, text)
    he = re.sub(r"[\u0591-\u05C7]", "", hebrew or "")
    # שעמום (Davidson: "insane", "crazy") is a different condition; leave such lines alone
    if SHOTEH_HE.search(he) and "שעמ" not in he:
        for p, r in _INSANE:
            text = p.sub(r, text)
    return text


if __name__ == "__main__":
    for s in ["a deaf-mute, an imbecile, or a minor", "**an imbecile,** who", "said to him: Imbecile, go to",
              "to **an imbecilic man**", "statement, an imbecile** priest", "exclude this** imbecilic woman",
              "one who became an imbecile, one", "at times competent and at times imbecilic,",
              "to imbeciles and", "them: Imbeciles, from where", "Greatest imbecile in the world!",
              "*shoteh* (imbecile) or", "a certain imbecile named ben Tedal", "An imbecile does not",
              "the imbecile became lucid", "is merely an imbecile,", "an imbecile’s lack"]:
        print(f"{s!r:45} -> {fix_terms(s)!r}")
